"""Outils GitHub : monitor + fix automatique de la CI sur une PR.

Permet à l'orchestrateur de boucler "regarde la CI, fix les erreurs, re-push,
re-attends" jusqu'à PR verte. À combiner avec l'auto-approve policy moderate
qui auto-approuve push agent/* et gh pr edit.

Tools exposés à l'orchestrateur :
- `gh_pr_status(pr_number)` : état détaillé de la CI sur une PR
- `gh_pr_failed_logs(pr_number, max_chars)` : extraits des logs des jobs
  qui ont échoué (ce qui permet à l'agent de comprendre quoi fixer)
- `gh_wait_for_ci(pr_number, timeout_minutes)` : bloque jusqu'à fin des
  checks (success ou failure)

L'orchestrateur peut combiner ces outils avec les outils file_write/git_commit
existants pour créer une boucle correctrice.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Any

from langchain_core.tools import tool

from ..journal import log_event
from ..orchestrator.config import get_settings


def _run_gh(args: list[str], timeout: int = 60) -> tuple[int, str, str]:
    """Lance gh CLI avec un timeout, retourne (code, stdout, stderr)."""
    try:
        proc = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(get_settings().repo_root),
            env={**os.environ},
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"gh timed out after {timeout}s"


# ─────────────────────────────────────────────────────────────────────
# Tools
# ─────────────────────────────────────────────────────────────────────
@tool
def gh_pr_status(pr_number: int) -> str:
    """Récupère le statut détaillé d'une PR sur Max-cfn/Stonks.

    Retourne un JSON avec :
    - state : OPEN / CLOSED / MERGED
    - mergeable : MERGEABLE / CONFLICTING / UNKNOWN
    - checks : liste de {name, status, conclusion} pour chaque job CI
    - summary : counts pass/fail/pending pour décision rapide

    À utiliser pour décider si la PR est prête à merger ou s'il faut fixer.
    """
    s = get_settings()
    repo = s.target_github_repo

    code, out, err = _run_gh([
        "pr", "view", str(pr_number),
        "--repo", repo,
        "--json", "state,mergeable,statusCheckRollup,headRefName,title",
    ])
    if code != 0:
        return json.dumps({"error": err.strip() or out.strip(), "code": code})

    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"json decode failed: {exc}", "raw": out[:500]})

    checks = data.get("statusCheckRollup") or []
    success = sum(1 for c in checks if c.get("conclusion") == "SUCCESS")
    failure = sum(1 for c in checks if c.get("conclusion") == "FAILURE")
    skipped = sum(1 for c in checks if c.get("conclusion") == "SKIPPED")
    pending = sum(1 for c in checks if c.get("status") in ("QUEUED", "IN_PROGRESS"))

    summary = {
        "pr_number": pr_number,
        "title": data.get("title"),
        "branch": data.get("headRefName"),
        "state": data.get("state"),
        "mergeable": data.get("mergeable"),
        "ci_total": len(checks),
        "ci_success": success,
        "ci_failure": failure,
        "ci_skipped": skipped,
        "ci_pending": pending,
        "ci_all_green": failure == 0 and pending == 0 and success > 0,
        "checks": [
            {
                "name": c.get("name"),
                "status": c.get("status"),
                "conclusion": c.get("conclusion"),
            }
            for c in checks
        ],
    }

    log_event(
        agent="orchestrator",
        phase="ci_loop",
        action="gh_pr_status",
        output_summary=f"PR#{pr_number} success={success} failure={failure} pending={pending}",
    )
    return json.dumps(summary, indent=2)


@tool
def gh_pr_failed_logs(pr_number: int, max_chars: int = 10000) -> str:
    """Récupère un extrait des logs des jobs CI qui ont échoué sur une PR.

    Lance `gh run list` pour la branche de la PR, prend le run le plus récent,
    et extrait les sections "error" ou les dernières lignes des jobs en
    failure. Limité à max_chars (défaut 10000) pour éviter de tout cramer
    en context — c'est largement suffisant pour identifier le problème.

    À utiliser après gh_pr_status quand ci_failure > 0, pour comprendre
    QUOI fixer.
    """
    s = get_settings()
    repo = s.target_github_repo

    # 1. Trouver la branche de la PR
    code, out, err = _run_gh([
        "pr", "view", str(pr_number),
        "--repo", repo,
        "--json", "headRefName",
    ])
    if code != 0:
        return json.dumps({"error": err.strip() or out.strip()})

    try:
        branch = json.loads(out).get("headRefName")
    except json.JSONDecodeError:
        return json.dumps({"error": "could not decode pr view output"})

    if not branch:
        return json.dumps({"error": "no headRefName found"})

    # 2. Le run le plus récent sur cette branche
    code, out, err = _run_gh([
        "run", "list",
        "--repo", repo,
        "--branch", branch,
        "--limit", "1",
        "--json", "databaseId,name,conclusion,status",
    ])
    if code != 0:
        return json.dumps({"error": err.strip() or out.strip()})

    try:
        runs = json.loads(out)
    except json.JSONDecodeError:
        return json.dumps({"error": "could not decode runs"})

    if not runs:
        return json.dumps({"error": f"no runs found for branch {branch}"})

    run_id = runs[0].get("databaseId")

    # 3. Récupère les logs des jobs failed
    code, logs, err = _run_gh([
        "run", "view", str(run_id),
        "--repo", repo,
        "--log-failed",
    ], timeout=120)

    if code != 0:
        return json.dumps({"error": err.strip() or "log fetch failed", "run_id": run_id})

    # Tronquer en gardant la fin (où l'erreur se manifeste typiquement)
    if len(logs) > max_chars:
        logs = "...[TRUNCATED]...\n" + logs[-(max_chars - 30):]

    log_event(
        agent="orchestrator",
        phase="ci_loop",
        action="gh_pr_failed_logs",
        output_summary=f"PR#{pr_number} run={run_id} logs_len={len(logs)}",
    )

    return json.dumps({
        "pr_number": pr_number,
        "branch": branch,
        "run_id": run_id,
        "logs_excerpt": logs,
    })


@tool
def gh_wait_for_ci(pr_number: int, timeout_minutes: int = 15) -> str:
    """Bloque jusqu'à ce que tous les checks CI aient terminé (ou timeout).

    Utile après un push : tu push, tu appelles ce tool, il revient quand
    tous les checks sont done. Polling toutes les 30s.

    Returns:
        JSON avec :
        - all_done : True si tous les checks ont conclu
        - all_green : True si tous SUCCESS
        - timeout : True si on a atteint timeout_minutes
        - elapsed_seconds
        - final_status (résultat du dernier gh_pr_status)
    """
    deadline = time.time() + timeout_minutes * 60
    poll_interval = 30
    start = time.time()

    while time.time() < deadline:
        result_str = gh_pr_status.invoke({"pr_number": pr_number})
        try:
            data = json.loads(result_str)
        except json.JSONDecodeError:
            return json.dumps({"error": "could not parse pr status during wait"})

        if "error" in data:
            return result_str  # propage l'erreur

        pending = data.get("ci_pending", 0)
        if pending == 0 and data.get("ci_total", 0) > 0:
            elapsed = time.time() - start
            log_event(
                agent="orchestrator",
                phase="ci_loop",
                action="gh_wait_for_ci_done",
                output_summary=(
                    f"PR#{pr_number} settled in {elapsed:.0f}s "
                    f"green={data.get('ci_all_green')} "
                    f"failure={data.get('ci_failure')}"
                ),
            )
            return json.dumps({
                "all_done": True,
                "all_green": data.get("ci_all_green"),
                "timeout": False,
                "elapsed_seconds": int(elapsed),
                "final_status": data,
            })

        time.sleep(poll_interval)

    elapsed = time.time() - start
    log_event(
        agent="orchestrator",
        phase="ci_loop",
        action="gh_wait_for_ci_timeout",
        output_summary=f"PR#{pr_number} timed out after {elapsed:.0f}s",
    )
    return json.dumps({
        "all_done": False,
        "all_green": False,
        "timeout": True,
        "elapsed_seconds": int(elapsed),
        "final_status": json.loads(gh_pr_status.invoke({"pr_number": pr_number})),
    })


# ─────────────────────────────────────────────────────────────────────
# Tools agrégés (export)
# ─────────────────────────────────────────────────────────────────────
GH_CI_TOOLS = [gh_pr_status, gh_pr_failed_logs, gh_wait_for_ci]
