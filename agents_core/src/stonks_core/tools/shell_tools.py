"""Outil shell avec allowlist et timeout.

Toute commande hors allowlist passe par `request_human_approval`.
"""
from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from langchain_core.tools import tool

from ..journal import log_event
from ..orchestrator.config import get_settings


# Première occurrence de la commande après expansion shell.
ALLOWED_COMMANDS = {
    # JS / pnpm
    "pnpm", "npm", "npx", "yarn", "node",
    # Python
    "python", "python3", "pip", "uv", "pytest", "ruff", "mypy", "streamlit",
    # Build / orchestration
    "task", "make",
    # Git / GitHub
    "git", "gh", "gitnexus",
    # Docker
    "docker", "docker-compose",
    # Filesystem (lecture)
    "ls", "cat", "head", "tail", "grep", "find", "wc", "stat",
    # Filesystem (écriture limitée)
    "mkdir", "touch", "mv", "cp", "rm", "chmod", "chown",
    # Réseau lecture
    "curl", "wget",
    # Divers
    "echo", "true", "false", "test", "which", "env", "pwd",
}


def _command_allowed(cmd: str) -> bool:
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        return False
    if not tokens:
        return False
    base = Path(tokens[0]).name  # `/usr/bin/git` → `git`
    return base in ALLOWED_COMMANDS


@tool
def shell_exec(
    command: str,
    cwd: str | None = None,
    timeout_seconds: int = 300,
    allow_unrestricted: bool = False,
) -> str:
    """Exécute une commande shell sous l'allowlist.

    Args:
        command: La commande complète (ex. `pnpm install`).
        cwd: Working directory relatif au monorepo (défaut : racine).
        timeout_seconds: Tue après ce délai (défaut 5 min).
        allow_unrestricted: Si True, bypass l'allowlist — UNIQUEMENT après
            confirmation humaine (le sous-agent doit appeler
            `request_human_approval` au préalable).

    Returns:
        Texte de la forme `EXIT=<code>\\nSTDOUT:\\n…\\nSTDERR:\\n…` (tronqué).
    """
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_call",
              tool="shell_exec", input={"command": command, "cwd": cwd,
                                         "unrestricted": allow_unrestricted})

    if not allow_unrestricted and not _command_allowed(command):
        msg = f"ERROR: commande hors allowlist: '{command}'. Demander request_human_approval."
        log_event(agent="orchestrator", phase="ad_hoc", action="tool_result",
                  tool="shell_exec", output_summary=msg)
        return msg

    settings = get_settings()
    work_dir = settings.repo_root if cwd is None else (settings.repo_root / cwd).resolve()
    try:
        work_dir.relative_to(settings.repo_root.resolve())
    except ValueError:
        return f"ERROR: cwd hors sandbox: {work_dir}"

    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        stdout = proc.stdout[-10_000:] if proc.stdout else ""
        stderr = proc.stderr[-5_000:] if proc.stderr else ""
        out = f"EXIT={proc.returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        log_event(agent="orchestrator", phase="ad_hoc", action="tool_result",
                  tool="shell_exec",
                  output_summary=f"exit={proc.returncode} stdout_len={len(stdout)} stderr_len={len(stderr)}")
        return out
    except subprocess.TimeoutExpired:
        msg = f"ERROR: timeout ({timeout_seconds}s) pour: {command}"
        log_event(agent="orchestrator", phase="ad_hoc", action="error",
                  tool="shell_exec", output_summary=msg)
        return msg
    except Exception as exc:  # noqa: BLE001
        msg = f"ERROR: {type(exc).__name__}: {exc}"
        log_event(agent="orchestrator", phase="ad_hoc", action="error",
                  tool="shell_exec", output_summary=msg)
        return msg
