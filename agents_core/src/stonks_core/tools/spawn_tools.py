"""Outil `spawn_agent` — instancie un sous-agent et lui passe un brief.

Le sous-agent est un autre nœud LangGraph (cf. `agents/`). On l'instancie
en injectant son prompt système spécifique, ses outils restreints, et le
state courant.

Note : pour Phase 1, l'implémentation est synchrone (un agent à la fois).
La parallélisation viendra en Phase 2 via Redis Streams + workers.
"""
from __future__ import annotations

from typing import Literal

from langchain_core.tools import tool

from ..journal import log_event


SubAgentRole = Literal["backend", "frontend", "security", "data", "reviewer"]


@tool
def spawn_agent(role: SubAgentRole, brief: str, max_iterations: int = 50) -> str:
    """Délègue une tâche à un sous-agent spécialisé.

    Args:
        role: Type d'agent — "backend" (FastAPI/SQLA), "frontend" (Next/RN),
              "security" (auth/crypto/Vault), "data" (PG/Timescale/migrations),
              "reviewer" (code review systématique avant merge).
        brief: Brief markdown détaillé (objectif + contexte + critères + hors-périmètre).
        max_iterations: Garde-fou anti-boucle (défaut 50).

    Returns:
        Résumé de l'exécution du sous-agent (ce qu'il a fait, livrables, erreurs).
    """
    # Import paresseux pour éviter cycle d'imports avec graph.py
    from ..agents import run_subagent

    log_event(
        agent="orchestrator",
        phase="ad_hoc",
        action="spawn_agent",
        tool="spawn_agent",
        input={"role": role, "brief_preview": brief[:300], "max_iterations": max_iterations},
    )

    summary = run_subagent(role=role, brief=brief, max_iterations=max_iterations)

    log_event(
        agent="orchestrator",
        phase="ad_hoc",
        action="subagent_completed",
        tool="spawn_agent",
        output_summary=summary[:500],
        extra={"role": role},
    )
    return summary
