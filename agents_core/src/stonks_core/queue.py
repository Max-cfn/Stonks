"""Queue séquentielle de briefs autonomes.

Permet d'enchaîner plusieurs briefs sans intervention humaine entre eux.
Chaque brief est exécuté en sous-process Python (pas systemd individuel)
pour qu'on puisse propagement le tuer, voir son état, etc.

Le fichier de state est `agents_core/runtime/queue/queue.json` :

```json
{
  "version": 1,
  "current": null,                          # brief_id en cours, ou null
  "items": [
    {
      "id": "20260501_120000_phase2-1",
      "brief_path": "docs/briefs/phase-2-1.md",
      "status": "queued",                   # queued|running|done|failed|skipped
      "added_at": "2026-04-30T22:00:00Z",
      "started_at": null,
      "ended_at": null,
      "exit_code": null,
      "stop_on_failure": true,
      "depends_on_pr_merge": true           # attend que la PR soit mergée avant d'enchaîner
    }
  ]
}
```

Usage :
  - python -m stonks_core.queue add docs/briefs/phase-2-1.md
  - python -m stonks_core.queue list
  - python -m stonks_core.queue run                  # bloquant, processe la queue
  - python -m stonks_core.queue clear

Ou via Taskfile : task queue:add -- <chemin>, task queue:run, task queue:list.

Pour tourner en daemon : `sudo systemctl start stonks-queue.service`
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from .journal import init_logger, log_event
from .orchestrator.config import get_settings

SETTINGS = get_settings()
init_logger(SETTINGS.execution_log_path)


ItemStatus = Literal["queued", "running", "done", "failed", "skipped"]


def _queue_dir() -> Path:
    p = SETTINGS.repo_root / "agents_core" / "runtime" / "queue"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _queue_file() -> Path:
    return _queue_dir() / "queue.json"


def _read_queue() -> dict[str, Any]:
    f = _queue_file()
    if not f.exists():
        return {"version": 1, "current": None, "items": []}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "current": None, "items": []}


def _write_queue(data: dict[str, Any]) -> None:
    _queue_file().write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def _gen_id(brief_path: Path) -> str:
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    slug = brief_path.stem[:50]
    return f"{ts}_{slug}"


# ─────────────────────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────────────────────
def add(
    brief_path: str | Path,
    *,
    stop_on_failure: bool = True,
    depends_on_pr_merge: bool = False,
) -> str:
    """Ajoute un brief en fin de queue. Retourne l'ID."""
    p = Path(brief_path)
    if not p.is_absolute():
        p = SETTINGS.repo_root / p
    if not p.exists():
        raise FileNotFoundError(f"Brief not found: {p}")

    queue = _read_queue()
    item_id = _gen_id(p)
    queue["items"].append(
        {
            "id": item_id,
            "brief_path": str(p.relative_to(SETTINGS.repo_root)),
            "status": "queued",
            "added_at": datetime.now(UTC).isoformat(),
            "started_at": None,
            "ended_at": None,
            "exit_code": None,
            "stop_on_failure": stop_on_failure,
            "depends_on_pr_merge": depends_on_pr_merge,
        }
    )
    _write_queue(queue)

    log_event(
        agent="queue",
        phase="management",
        action="brief_queued",
        output_summary=f"id={item_id} brief={p.name} stop_on_failure={stop_on_failure}",
    )
    return item_id


def list_items() -> list[dict[str, Any]]:
    return _read_queue()["items"]


def remove(item_id: str) -> bool:
    queue = _read_queue()
    before = len(queue["items"])
    queue["items"] = [i for i in queue["items"] if i["id"] != item_id]
    _write_queue(queue)
    return len(queue["items"]) < before


def clear(only_done: bool = False) -> int:
    queue = _read_queue()
    if only_done:
        before = len(queue["items"])
        queue["items"] = [i for i in queue["items"] if i["status"] not in ("done", "failed", "skipped")]
        _write_queue(queue)
        return before - len(queue["items"])
    queue["items"] = []
    queue["current"] = None
    _write_queue(queue)
    return -1


def _set_status(
    item_id: str,
    status: ItemStatus,
    *,
    exit_code: int | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    queue = _read_queue()
    for item in queue["items"]:
        if item["id"] == item_id:
            item["status"] = status
            if status == "running" and not item["started_at"]:
                item["started_at"] = datetime.now(UTC).isoformat()
                queue["current"] = item_id
            elif status in ("done", "failed", "skipped"):
                item["ended_at"] = datetime.now(UTC).isoformat()
                item["exit_code"] = exit_code
                if queue.get("current") == item_id:
                    queue["current"] = None
            if extra:
                item.update(extra)
            break
    _write_queue(queue)


# ─────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────
def _run_one(item: dict[str, Any]) -> int:
    """Lance un brief en sous-process et bloque jusqu'à sa fin. Retourne exit_code."""
    item_id = item["id"]
    brief_path = SETTINGS.repo_root / item["brief_path"]

    log_dir = _queue_dir() / item_id
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_log = log_dir / "stdout.log"
    stderr_log = log_dir / "stderr.log"

    _set_status(item_id, "running")
    log_event(
        agent="queue",
        phase="management",
        action="brief_started",
        output_summary=f"id={item_id} brief={brief_path.name}",
    )

    cmd = [
        sys.executable,
        "-m",
        "stonks_core.orchestrator.main",
        "autonomous",
        "--brief",
        str(brief_path),
        "--thread-id",
        f"queue-{item_id}",
    ]
    env = {
        **os.environ,
        "PYTHONPATH": str(SETTINGS.repo_root / "agents_core" / "src"),
    }

    with open(stdout_log, "w", encoding="utf-8") as out, open(stderr_log, "w", encoding="utf-8") as err:
        proc = subprocess.Popen(
            cmd,
            cwd=str(SETTINGS.repo_root / "agents_core"),
            stdout=out,
            stderr=err,
            stdin=subprocess.DEVNULL,
            env=env,
        )
        exit_code = proc.wait()

    status: ItemStatus = "done" if exit_code == 0 else "failed"
    _set_status(item_id, status, exit_code=exit_code)
    log_event(
        agent="queue",
        phase="management",
        action="brief_ended",
        output_summary=f"id={item_id} exit={exit_code} status={status}",
    )
    return exit_code


def run(stop_on_first_failure: bool | None = None) -> None:
    """Processe la queue de manière séquentielle. Bloquant.

    stop_on_first_failure : si True, s'arrête à la première erreur.
    Si None (défaut), respecte le flag `stop_on_failure` de chaque item.
    """
    log_event(agent="queue", phase="management", action="queue_run_start")

    while True:
        queue = _read_queue()
        # Premier item queued
        next_item = next((i for i in queue["items"] if i["status"] == "queued"), None)
        if not next_item:
            log_event(agent="queue", phase="management", action="queue_run_end_empty")
            return

        exit_code = _run_one(next_item)

        if exit_code != 0:
            should_stop = (
                stop_on_first_failure
                if stop_on_first_failure is not None
                else next_item.get("stop_on_failure", True)
            )
            if should_stop:
                # Marque les suivants comme skipped
                queue = _read_queue()
                for it in queue["items"]:
                    if it["status"] == "queued":
                        it["status"] = "skipped"
                        it["ended_at"] = datetime.now(UTC).isoformat()
                _write_queue(queue)
                log_event(
                    agent="queue",
                    phase="management",
                    action="queue_run_aborted",
                    output_summary=f"after failure of {next_item['id']}",
                )
                return

        # Petit délai entre 2 briefs (laisser le temps de finaliser logs/git)
        time.sleep(5)


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────
def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="stonks_core.queue")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Ajouter un brief en queue")
    p_add.add_argument("brief", help="Chemin vers le brief .md (relatif ou absolu)")
    p_add.add_argument("--no-stop-on-failure", action="store_true")

    sub.add_parser("list", help="Liste la queue")
    sub.add_parser("run", help="Processe la queue séquentiellement (bloquant)")
    p_clear = sub.add_parser("clear", help="Vide la queue")
    p_clear.add_argument("--only-done", action="store_true", help="Garder seulement les non-terminés")
    p_rm = sub.add_parser("remove", help="Retire un item par id")
    p_rm.add_argument("id")

    args = parser.parse_args()

    if args.cmd == "add":
        item_id = add(args.brief, stop_on_failure=not args.no_stop_on_failure)
        print(f"✅ ajouté: {item_id}")
    elif args.cmd == "list":
        items = list_items()
        if not items:
            print("(queue vide)")
            return
        for it in items:
            emoji = {
                "queued": "⏸",
                "running": "▶️",
                "done": "✅",
                "failed": "❌",
                "skipped": "⏭",
            }.get(it["status"], "?")
            print(f"  {emoji} [{it['status']:7s}] {it['id']}  →  {it['brief_path']}")
    elif args.cmd == "run":
        run()
    elif args.cmd == "clear":
        clear(only_done=args.only_done)
        print(f"✅ {'kept non-terminated, cleared done items' if args.only_done else 'queue vidée'}")
    elif args.cmd == "remove":
        ok = remove(args.id)
        print("✅ removed" if ok else "❌ id introuvable")


if __name__ == "__main__":
    _cli()
