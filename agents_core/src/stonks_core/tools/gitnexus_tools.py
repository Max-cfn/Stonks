"""Wrappers GitNexus.

GitNexus est lancé en backend HTTP (`gitnexus serve` sur :4747) et expose une
API multi-repo. On peut aussi appeler le CLI directement pour les opérations
locales (analyze).

Doc : https://github.com/abhigyanpatwari/GitNexus
"""
from __future__ import annotations

import json
import subprocess

import httpx
from langchain_core.tools import tool

from ..journal import log_event
from ..orchestrator.config import get_settings


def _http_client() -> httpx.Client:
    s = get_settings()
    return httpx.Client(base_url=s.gitnexus_backend_url, timeout=60.0)


@tool
def gitnexus_index(force: bool = False, skip_embeddings: bool = True) -> str:
    """Indexe le monorepo (à lancer après chaque gros changement structurel).

    Args:
        force: Force la ré-indexation complète.
        skip_embeddings: Skip la génération d'embeddings (plus rapide).
    """
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_call",
              tool="gitnexus_index", input={"force": force, "skip_embeddings": skip_embeddings})
    s = get_settings()
    args = ["gitnexus", "analyze"]
    if force:
        args.append("--force")
    if skip_embeddings:
        args.append("--skip-embeddings")
    proc = subprocess.run(
        args, cwd=str(s.repo_root), capture_output=True, text=True, timeout=600
    )
    msg = f"EXIT={proc.returncode}\n{proc.stdout[-3000:]}\n{proc.stderr[-1000:]}"
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_result",
              tool="gitnexus_index",
              output_summary=f"exit={proc.returncode}, stdout_len={len(proc.stdout)}")
    return msg


@tool
def gitnexus_impact(
    target: str,
    direction: str = "upstream",
    max_depth: int = 3,
    min_confidence: float = 0.7,
) -> str:
    """Analyse le blast radius d'un symbole.

    Args:
        target: Nom du symbole (fonction, classe, module).
        direction: 'upstream' (qui dépend de moi), 'downstream' (de qui je dépends), 'both'.
        max_depth: Profondeur max (défaut 3).
        min_confidence: Seuil de confiance (défaut 0.7).

    À appeler AVANT toute modification structurelle critique.
    """
    log_event(agent="reviewer", phase="ad_hoc", action="tool_call",
              tool="gitnexus_impact",
              input={"target": target, "direction": direction, "max_depth": max_depth})
    try:
        with _http_client() as client:
            r = client.post("/api/tool/impact", json={
                "target": target,
                "direction": direction,
                "maxDepth": max_depth,
                "minConfidence": min_confidence,
            })
            r.raise_for_status()
            out = json.dumps(r.json(), indent=2, ensure_ascii=False)[:15_000]
    except httpx.HTTPError as exc:
        out = f"ERROR HTTP: {exc}. Vérifie que `gitnexus serve` tourne sur {get_settings().gitnexus_backend_url}."
    log_event(agent="reviewer", phase="ad_hoc", action="tool_result",
              tool="gitnexus_impact", output_summary=f"chars={len(out)}")
    return out


@tool
def gitnexus_query(query: str, repo: str | None = None) -> str:
    """Recherche hybride (BM25 + sémantique) dans le graphe de connaissances.

    Args:
        query: Question en langage naturel ou mots-clés.
        repo: Nom du repo si plusieurs indexés (défaut : auto).
    """
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_call",
              tool="gitnexus_query", input={"query": query, "repo": repo})
    try:
        with _http_client() as client:
            payload: dict = {"query": query}
            if repo:
                payload["repo"] = repo
            r = client.post("/api/tool/query", json=payload)
            r.raise_for_status()
            out = json.dumps(r.json(), indent=2, ensure_ascii=False)[:10_000]
    except httpx.HTTPError as exc:
        out = f"ERROR HTTP: {exc}"
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_result",
              tool="gitnexus_query", output_summary=f"chars={len(out)}")
    return out


@tool
def gitnexus_context(name: str, repo: str | None = None) -> str:
    """Vue 360° d'un symbole : tous ses callers, callees, et participation aux processes."""
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_call",
              tool="gitnexus_context", input={"name": name, "repo": repo})
    try:
        with _http_client() as client:
            payload: dict = {"name": name}
            if repo:
                payload["repo"] = repo
            r = client.post("/api/tool/context", json=payload)
            r.raise_for_status()
            out = json.dumps(r.json(), indent=2, ensure_ascii=False)[:10_000]
    except httpx.HTTPError as exc:
        out = f"ERROR HTTP: {exc}"
    log_event(agent="orchestrator", phase="ad_hoc", action="tool_result",
              tool="gitnexus_context", output_summary=f"chars={len(out)}")
    return out


@tool
def gitnexus_detect_changes(scope: str = "all") -> str:
    """Analyse les changements pré-commit : quels symboles changés, quels processes affectés.

    Args:
        scope: 'staged' (changements stagés), 'unstaged', 'all' (défaut).
    """
    log_event(agent="reviewer", phase="ad_hoc", action="tool_call",
              tool="gitnexus_detect_changes", input={"scope": scope})
    try:
        with _http_client() as client:
            r = client.post("/api/tool/detect_changes", json={"scope": scope})
            r.raise_for_status()
            out = json.dumps(r.json(), indent=2, ensure_ascii=False)[:15_000]
    except httpx.HTTPError as exc:
        out = f"ERROR HTTP: {exc}"
    log_event(agent="reviewer", phase="ad_hoc", action="tool_result",
              tool="gitnexus_detect_changes", output_summary=f"chars={len(out)}")
    return out
