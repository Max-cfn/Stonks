"""Logging structuré JSONL pour le execution_log.txt.

RÈGLE ABSOLUE : tout side-effect (file, shell, git, LLM) DOIT être loggé via
ce module, AVANT et APRÈS l'opération. C'est non-négociable et c'est
contrôlé par le Reviewer Agent à chaque code-review.

Format : 1 ligne JSON par entrée (JSONL).
Append-only (jamais d'écrasement).
"""
from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_LOG_LOCK = threading.Lock()
_LOG_PATH: Path | None = None


def init_logger(log_path: Path | str) -> Path:
    """Initialise le logger global. À appeler une fois au démarrage."""
    global _LOG_PATH
    p = Path(log_path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.touch()
    _LOG_PATH = p
    return p


def _ensure_initialized() -> Path:
    """Retourne le path du log. Init paresseuse si pas encore appelé init_logger.

    Pour éviter une dépendance circulaire avec orchestrator.config (qui
    importe lui-même journal pour logger sa propre init), on tente d'abord
    une variable d'env STONKS_EXECUTION_LOG, puis on fallback sur la racine
    repo détectée par config.
    """
    if _LOG_PATH is not None:
        return _LOG_PATH

    env_path = os.environ.get("STONKS_EXECUTION_LOG")
    if env_path:
        return init_logger(env_path)

    # Import paresseux pour éviter le cycle orchestrator.config ↔ journal
    from stonks_core.orchestrator.config import get_settings

    return init_logger(get_settings().execution_log_path)


def log_event(
    *,
    agent: str,
    phase: str,
    action: str,
    tool: str | None = None,
    input: dict[str, Any] | None = None,
    output_summary: str = "",
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_usd: float = 0.0,
    checkpoint_id: str | None = None,
    human_intervention: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Inscrit une entrée dans execution_log.txt (JSONL, append-only).

    Retourne le dict loggé (utile pour debug / chaining).
    """
    path = _ensure_initialized()
    entry: dict[str, Any] = {
        "ts": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "pid": os.getpid(),
        "agent": agent,
        "phase": phase,
        "action": action,
        "tool": tool,
        "input": _truncate_dict(input) if input else None,
        "output_summary": _truncate(output_summary, 500),
        "tokens": {"in": tokens_in, "out": tokens_out},
        "cost_usd": round(cost_usd, 6),
        "checkpoint_id": checkpoint_id,
        "human_intervention": human_intervention,
    }
    if extra:
        entry["extra"] = _truncate_dict(extra)

    line = json.dumps(entry, ensure_ascii=False, default=str)
    with _LOG_LOCK, path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return entry


def _truncate(s: str, max_len: int = 500) -> str:
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def _truncate_dict(d: dict[str, Any] | None, max_value_len: int = 1000) -> dict[str, Any] | None:
    if d is None:
        return None
    out: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, str):
            out[k] = _truncate(v, max_value_len)
        else:
            out[k] = v
    return out


def read_recent(n: int = 100) -> list[dict[str, Any]]:
    """Lit les n dernières entrées du log (pour l'UI Streamlit)."""
    path = _ensure_initialized()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    # Skip les lignes de commentaires (#) qui forment l'entête
    json_lines = [ln for ln in lines if ln.startswith("{")]
    out: list[dict[str, Any]] = []
    for ln in json_lines[-n:]:
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out
