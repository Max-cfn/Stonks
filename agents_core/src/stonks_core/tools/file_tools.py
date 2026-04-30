"""Outils file system sandboxés à la racine du monorepo (`/opt/stonks/`).

Toutes les opérations sont limitées à cette racine ; toute tentative de sortie
(via `..`, lien symbolique, chemin absolu hors zone) est refusée.
"""
from __future__ import annotations

from pathlib import Path

from langchain_core.tools import tool

from ..journal import log_event
from ..orchestrator.config import get_settings


def _resolve_safe(path: str) -> Path:
    """Résout `path` à l'intérieur du sandbox, sinon lève ValueError."""
    root = get_settings().repo_root.resolve()
    p = (root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    try:
        p.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path hors sandbox: {p} (sandbox={root})") from exc
    return p


@tool
def file_read(path: str, max_chars: int = 50_000) -> str:
    """Lit un fichier texte du monorepo.

    Args:
        path: Chemin relatif à `/opt/stonks/` ou absolu (doit rester dans le sandbox).
        max_chars: Tronque la lecture (sécurité contexte LLM).

    Returns:
        Contenu du fichier (tronqué si > max_chars).
    """
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_call",
              tool="file_read", input={"path": path, "max_chars": max_chars})
    p = _resolve_safe(path)
    if not p.exists():
        out = f"ERROR: file not found: {path}"
        log_event(agent="orchestrator", phase="ad_hoc", action="tool_result",
                  tool="file_read", output_summary=out)
        return out
    content = p.read_text(encoding="utf-8", errors="replace")
    truncated = ""
    if len(content) > max_chars:
        content = content[:max_chars]
        truncated = f"\n[...tronqué à {max_chars} caractères...]"
    out = content + truncated
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_result",
              tool="file_read", output_summary=f"read {p}: {len(out)} chars")
    return out


@tool
def file_write(path: str, content: str, create_parents: bool = True) -> str:
    """Écrit (écrase) un fichier texte. Crée les dossiers parents si besoin.

    Args:
        path: Chemin relatif au monorepo.
        content: Nouveau contenu complet.
        create_parents: Crée les dossiers parents (défaut True).

    Returns:
        Message de confirmation.
    """
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_call",
              tool="file_write", input={"path": path, "size": len(content)})
    p = _resolve_safe(path)
    if create_parents:
        p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    msg = f"OK file_write {p} ({len(content)} chars)"
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_result",
              tool="file_write", output_summary=msg)
    return msg


@tool
def file_append(path: str, content: str) -> str:
    """Ajoute du contenu à la fin d'un fichier (le crée s'il n'existe pas)."""
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_call",
              tool="file_append", input={"path": path, "size": len(content)})
    p = _resolve_safe(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(content)
    msg = f"OK file_append {p}"
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_result",
              tool="file_append", output_summary=msg)
    return msg


@tool
def file_list(path: str = ".", pattern: str = "*", recursive: bool = False) -> str:
    """Liste les fichiers d'un dossier.

    Args:
        path: Chemin du dossier (relatif au monorepo).
        pattern: Glob pattern (défaut '*').
        recursive: Si True, descend récursivement.
    """
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_call",
              tool="file_list", input={"path": path, "pattern": pattern, "recursive": recursive})
    p = _resolve_safe(path)
    if not p.is_dir():
        return f"ERROR: not a directory: {path}"
    entries = sorted(p.rglob(pattern)) if recursive else sorted(p.glob(pattern))
    root = get_settings().repo_root.resolve()
    out = "\n".join(str(e.relative_to(root)) for e in entries)
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_result",
              tool="file_list", output_summary=f"{len(entries)} entries")
    return out or "(empty)"


@tool
def file_delete(path: str) -> str:
    """Supprime un fichier (refuse les dossiers — utiliser shell_exec rm -rf si nécessaire)."""
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_call",
              tool="file_delete", input={"path": path})
    p = _resolve_safe(path)
    if not p.exists():
        return f"already absent: {path}"
    if p.is_dir():
        return f"ERROR: refus de supprimer un dossier via file_delete (utiliser shell_exec): {path}"
    p.unlink()
    msg = f"OK file_delete {p}"
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_result",
              tool="file_delete", output_summary=msg)
    return msg
