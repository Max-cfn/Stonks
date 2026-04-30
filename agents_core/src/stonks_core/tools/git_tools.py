"""Outils Git/GitHub.

Tous les commits sont signés par l'auteur configuré dans `git config --global`
(défaut : Max-cfn). Les PR sont créées via `gh` qui utilise le token déjà
authentifié.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from langchain_core.tools import tool

from ..journal import log_event
from ..orchestrator.config import get_settings


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 60) -> tuple[int, str, str]:
    """Helper subprocess avec capture."""
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else str(get_settings().repo_root),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


@tool
def git_status() -> str:
    """git status -sb + dernier commit."""
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_call", tool="git_status")
    code, out, err = _run(["git", "status", "-sb"])
    _code2, last, _ = _run(["git", "log", "--oneline", "-1"])
    msg = f"=== status ===\n{out}\n=== last commit ===\n{last}"
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_result",
              tool="git_status", output_summary=f"code={code}")
    return msg if code == 0 else f"ERROR: {err}"


@tool
def git_branch(name: str | None = None, checkout: bool = True) -> str:
    """Liste les branches, ou crée/checkout `name` si fourni.

    Args:
        name: Nom de la nouvelle branche (ex. `agent/backend/phase2/sqla-models`).
        checkout: Bascule sur la nouvelle branche après création (défaut True).
    """
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_call",
              tool="git_branch", input={"name": name, "checkout": checkout})
    if name is None:
        code, out, _ = _run(["git", "branch", "-a"])
        return out if code == 0 else "ERROR"
    if checkout:
        code, out, err = _run(["git", "checkout", "-b", name])
    else:
        code, out, err = _run(["git", "branch", name])
    msg = f"OK branch {name}" if code == 0 else f"ERROR: {err}"
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_result",
              tool="git_branch", output_summary=msg)
    return msg


@tool
def git_commit(message: str, paths: list[str] | None = None, sign_off: bool = True) -> str:
    """Stage et commit.

    Args:
        message: Message de commit (format conventional commits recommandé).
        paths: Liste de chemins à staged (défaut : tous les changements).
        sign_off: Ajoute un trailer Co-authored-by stonks-orchestrator (défaut True).
    """
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_call",
              tool="git_commit", input={"message": message[:200], "paths": paths})

    if paths is None:
        _run(["git", "add", "-A"])
    else:
        _run(["git", "add", *paths])

    full_msg = message
    if sign_off and "Co-authored-by:" not in full_msg:
        full_msg += "\n\nCo-authored-by: stonks-orchestrator <bot@stonks.local>"

    code, out, err = _run(["git", "commit", "-m", full_msg], timeout=30)
    msg = f"NO-COMMIT: {err or out}" if code != 0 else f"OK commit\n{out}"
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_result",
              tool="git_commit", output_summary=msg[:300])
    return msg


@tool
def git_push(remote: str = "origin", branch: str | None = None, set_upstream: bool = True) -> str:
    """Push vers remote (défaut origin)."""
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_call",
              tool="git_push", input={"remote": remote, "branch": branch})
    args = ["git", "push"]
    if set_upstream:
        args.append("-u")
    args.append(remote)
    if branch:
        args.append(branch)
    code, out, err = _run(args, timeout=120)
    msg = "OK push" if code == 0 else f"ERROR: {err or out}"
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_result",
              tool="git_push", output_summary=msg)
    return f"{msg}\n{out}\n{err}".strip()


@tool
def git_pull(remote: str = "origin", branch: str | None = None) -> str:
    """Pull avec rebase off (config par défaut)."""
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_call",
              tool="git_pull", input={"remote": remote, "branch": branch})
    args = ["git", "pull", remote]
    if branch:
        args.append(branch)
    code, out, err = _run(args, timeout=120)
    msg = f"OK pull\n{out}" if code == 0 else f"ERROR: {err}"
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_result",
              tool="git_pull", output_summary=msg[:300])
    return msg


@tool
def git_diff(staged: bool = False, paths: list[str] | None = None) -> str:
    """Affiche le diff (HEAD vs working tree, ou staged)."""
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_call",
              tool="git_diff", input={"staged": staged, "paths": paths})
    args = ["git", "diff"]
    if staged:
        args.append("--staged")
    if paths:
        args.extend(["--", *paths])
    code, out, err = _run(args, timeout=30)
    if code != 0:
        return f"ERROR: {err}"
    return out[-20_000:] if len(out) > 20_000 else out


@tool
def gh_pr_create(title: str, body: str, base: str = "main", draft: bool = False) -> str:
    """Crée une PR via `gh`.

    Args:
        title: Titre de la PR.
        body: Corps en Markdown.
        base: Branche de destination (défaut main).
        draft: Si True, PR en draft.
    """
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_call",
              tool="gh_pr_create", input={"title": title, "base": base, "draft": draft})
    args = ["gh", "pr", "create", "--title", title, "--body", body, "--base", base]
    if draft:
        args.append("--draft")
    code, out, err = _run(args, timeout=60)
    msg = f"OK PR\n{out}" if code == 0 else f"ERROR: {err}"
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_result",
              tool="gh_pr_create", output_summary=msg[:300])
    return msg


@tool
def gh_pr_merge(number: int | None = None, squash: bool = True, delete_branch: bool = True) -> str:
    """Merge une PR (la courante si number est None)."""
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_call",
              tool="gh_pr_merge", input={"number": number, "squash": squash})
    args = ["gh", "pr", "merge"]
    if number is not None:
        args.append(str(number))
    if squash:
        args.append("--squash")
    if delete_branch:
        args.append("--delete-branch")
    args.append("--auto")
    code, out, err = _run(args, timeout=60)
    msg = f"OK merge\n{out}" if code == 0 else f"ERROR: {err}"
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_result",
              tool="gh_pr_merge", output_summary=msg[:300])
    return msg
