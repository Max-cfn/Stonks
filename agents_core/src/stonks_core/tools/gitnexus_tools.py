"""Wrappers GitNexus.

GitNexus est installé comme devDependency du monorepo (`pnpm add -wD gitnexus`).
Le binaire est résolu via `node_modules/.bin/gitnexus` à la racine du repo.

Modes d'utilisation :
- **CLI** (utilisé ici) : on shell out le binaire avec timeout. Simple et fiable.
- **MCP HTTP** : disponible via le container Docker `stonks-gitnexus` sur :4747/api/mcp.
  À utiliser plus tard pour de la perf si on fait beaucoup de queries.

Doc :  https://github.com/abhigyanpatwari/GitNexus
Setup : `pnpm add -wD gitnexus@latest && node_modules/.bin/gitnexus analyze .`
"""
from __future__ import annotations

import os
import subprocess

from langchain_core.tools import tool

from ..journal import log_event
from ..orchestrator.config import get_settings


def _gitnexus_bin() -> str:
    """Résout le chemin du binaire gitnexus.

    Priorité :
    1. node_modules/.bin/gitnexus à la racine du repo (devDependency pnpm)
    2. gitnexus dans le PATH (install global, fallback)
    """
    s = get_settings()
    local = s.repo_root / "node_modules" / ".bin" / "gitnexus"
    if local.exists() and local.is_file():
        return str(local)
    return "gitnexus"


def _run_gitnexus(args: list[str], timeout: int = 600) -> str:
    """Lance le CLI gitnexus avec args, capture stdout/stderr."""
    s = get_settings()
    cmd = [_gitnexus_bin(), *args]

    # Forcer GITNEXUS_HOME dans le repo car /home est ro sur serveurmax
    env = os.environ.copy()
    gitnexus_home = str(s.repo_root / ".gitnexus")
    env.setdefault("GITNEXUS_HOME", gitnexus_home)

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(s.repo_root),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except FileNotFoundError:
        return (
            "ERROR: binaire gitnexus introuvable. Installe via "
            "`pnpm add -wD gitnexus@latest` à la racine du monorepo."
        )
    except subprocess.TimeoutExpired:
        return f"ERROR: timeout après {timeout}s sur `gitnexus {' '.join(args)}`"

    out = proc.stdout or ""
    err = proc.stderr or ""
    if proc.returncode != 0:
        return f"EXIT={proc.returncode}\n{out[-3000:]}\n--- stderr ---\n{err[-1500:]}"
    return out[-15000:] if len(out) > 15000 else out


# ───────────────────────────────────────────────────────────────────────
# Indexation
# ───────────────────────────────────────────────────────────────────────
@tool
def gitnexus_index(force: bool = False, with_embeddings: bool = False) -> str:
    """Indexe (ou ré-indexe) le monorepo Stonks.

    Args:
        force: Force un full re-index même si l'index est à jour.
        with_embeddings: Active la génération d'embeddings pour la recherche
            sémantique. Plus lent et nécessite un modèle d'embeddings configuré.

    À lancer une fois après bootstrap, et après chaque gros changement
    structurel (refactor majeur, déplacement de modules).
    """
    log_event(
        agent="orchestrator",
        phase="ad_hoc",
        action="tool_call",
        tool="gitnexus_index",
        input={"force": force, "with_embeddings": with_embeddings},
    )
    args = ["analyze", "--skip-agents-md", "."]
    if force:
        args.insert(1, "--force")
    if with_embeddings:
        args.insert(1, "--embeddings")

    out = _run_gitnexus(args, timeout=600)
    log_event(
        agent="orchestrator",
        phase="ad_hoc",
        action="tool_result",
        tool="gitnexus_index",
        output_summary=out[:300],
    )
    return out


# ───────────────────────────────────────────────────────────────────────
# Impact analysis
# ───────────────────────────────────────────────────────────────────────
@tool
def gitnexus_impact(
    target: str,
    direction: str = "upstream",
    depth: int = 3,
    include_tests: bool = False,
    repo: str | None = None,
) -> str:
    """Analyse le blast radius d'un symbole.

    À appeler **AVANT toute modification structurelle** (rename, suppression,
    changement de signature). C'est la garantie anti-régression du Reviewer.

    Args:
        target: Nom de la fonction/classe/module/fichier à analyser.
        direction: 'upstream' (qui dépend de target) ou 'downstream' (de qui
            target dépend).
        depth: Profondeur max de l'analyse (défaut 3).
        include_tests: Inclure les fichiers de test dans les résultats.
        repo: Nom du repo si plusieurs sont indexés (défaut : auto).
    """
    log_event(
        agent="reviewer",
        phase="ad_hoc",
        action="tool_call",
        tool="gitnexus_impact",
        input={"target": target, "direction": direction, "depth": depth},
    )
    args = ["impact", target, "--direction", direction, "--depth", str(depth)]
    if include_tests:
        args.append("--include-tests")
    if repo:
        args.extend(["--repo", repo])

    out = _run_gitnexus(args, timeout=120)
    log_event(
        agent="reviewer",
        phase="ad_hoc",
        action="tool_result",
        tool="gitnexus_impact",
        output_summary=out[:300],
    )
    return out


# ───────────────────────────────────────────────────────────────────────
# Query (semantic search dans le knowledge graph)
# ───────────────────────────────────────────────────────────────────────
@tool
def gitnexus_query(
    query: str,
    goal: str | None = None,
    limit: int = 5,
    include_content: bool = False,
    repo: str | None = None,
) -> str:
    """Recherche dans le knowledge graph (BM25 + sémantique si embeddings).

    Args:
        query: Question en langage naturel ou mots-clés.
        goal: Description de ce qu'on cherche (améliore le ranking).
        limit: Nombre max de processes à retourner.
        include_content: Inclure le code source complet des symboles.
        repo: Nom du repo si plusieurs indexés.
    """
    log_event(
        agent="orchestrator",
        phase="ad_hoc",
        action="tool_call",
        tool="gitnexus_query",
        input={"query": query, "goal": goal, "limit": limit},
    )
    args = ["query", query, "--limit", str(limit)]
    if goal:
        args.extend(["--goal", goal])
    if include_content:
        args.append("--content")
    if repo:
        args.extend(["--repo", repo])

    out = _run_gitnexus(args, timeout=60)
    log_event(
        agent="orchestrator",
        phase="ad_hoc",
        action="tool_result",
        tool="gitnexus_query",
        output_summary=out[:300],
    )
    return out


# ───────────────────────────────────────────────────────────────────────
# Context (vue 360° d'un symbole)
# ───────────────────────────────────────────────────────────────────────
@tool
def gitnexus_context(
    name: str,
    file_path: str | None = None,
    include_content: bool = False,
    repo: str | None = None,
) -> str:
    """Vue 360° d'un symbole : callers, callees, processes auxquels il participe.

    Args:
        name: Nom du symbole (fonction, classe, module).
        file_path: Chemin du fichier si plusieurs symboles ont le même nom.
        include_content: Inclure le code source du symbole.
        repo: Nom du repo si plusieurs indexés.
    """
    log_event(
        agent="orchestrator",
        phase="ad_hoc",
        action="tool_call",
        tool="gitnexus_context",
        input={"name": name, "file_path": file_path},
    )
    args = ["context", name]
    if file_path:
        args.extend(["--file", file_path])
    if include_content:
        args.append("--content")
    if repo:
        args.extend(["--repo", repo])

    out = _run_gitnexus(args, timeout=60)
    log_event(
        agent="orchestrator",
        phase="ad_hoc",
        action="tool_result",
        tool="gitnexus_context",
        output_summary=out[:300],
    )
    return out


# ───────────────────────────────────────────────────────────────────────
# Detect changes (pré-commit / pré-PR)
# ───────────────────────────────────────────────────────────────────────
@tool
def gitnexus_detect_changes(
    scope: str = "unstaged",
    base_ref: str | None = None,
    repo: str | None = None,
) -> str:
    """Map git diff hunks → symboles indexés + flows affectés.

    À lancer pré-commit pour comprendre ce qu'on est en train de casser.

    Args:
        scope: 'unstaged', 'staged', 'all', ou 'compare' (avec base_ref).
        base_ref: Branche/commit pour le scope 'compare' (ex: 'main').
        repo: Nom du repo si plusieurs indexés.
    """
    log_event(
        agent="reviewer",
        phase="ad_hoc",
        action="tool_call",
        tool="gitnexus_detect_changes",
        input={"scope": scope, "base_ref": base_ref},
    )
    args = ["detect-changes", "--scope", scope]
    if base_ref:
        args.extend(["--base-ref", base_ref])
    if repo:
        args.extend(["--repo", repo])

    out = _run_gitnexus(args, timeout=60)
    log_event(
        agent="reviewer",
        phase="ad_hoc",
        action="tool_result",
        tool="gitnexus_detect_changes",
        output_summary=out[:300],
    )
    return out


# ───────────────────────────────────────────────────────────────────────
# Cypher (low-level query — pour les cas complexes)
# ───────────────────────────────────────────────────────────────────────
@tool
def gitnexus_cypher(query: str, repo: str | None = None) -> str:
    """Exécute une query Cypher brute sur le knowledge graph.

    À utiliser quand `query`/`context`/`impact` ne suffisent pas. Le schéma
    de noeuds typique : (:File), (:Symbol), (:Process), (:Cluster).

    Args:
        query: Cypher query (syntax similaire à Neo4j).
        repo: Nom du repo si plusieurs indexés.
    """
    log_event(
        agent="orchestrator",
        phase="ad_hoc",
        action="tool_call",
        tool="gitnexus_cypher",
        input={"query": query[:300]},
    )
    args = ["cypher", query]
    if repo:
        args.extend(["--repo", repo])

    out = _run_gitnexus(args, timeout=60)
    log_event(
        agent="orchestrator",
        phase="ad_hoc",
        action="tool_result",
        tool="gitnexus_cypher",
        output_summary=out[:300],
    )
    return out
