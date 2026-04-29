"""État LangGraph partagé entre l'orchestrateur et les sous-agents."""
from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import BaseMessage


AgentRole = Literal[
    "orchestrator",
    "backend",
    "frontend",
    "security",
    "data",
    "reviewer",
]

Phase = Literal[
    "phase_1_bootstrap",
    "phase_2_foundations",
    "phase_2_cashflow",
    "phase_2_portfolio",
    "phase_2_news_agent",
    "phase_3_cicd",
    "maintenance",
    "ad_hoc",
]


class OrchestratorState(TypedDict, total=False):
    """État partagé du graphe LangGraph.

    Tout sous-agent reçoit ce state, peut le muter, et le renvoie. Les champs
    `messages` et `tool_calls_history` sont accumulatifs (annotation operator.add).
    """

    # Conversation principale (avec l'humain ou l'auto-briefing)
    messages: Annotated[list[BaseMessage], operator.add]

    # Brief courant (objectif explicite donné par l'humain ou inféré)
    brief: str
    phase: Phase

    # Délégation
    current_agent: AgentRole
    next_agent: AgentRole | None

    # Historique des tool calls (pour debug et audit)
    tool_calls_history: Annotated[list[dict[str, Any]], operator.add]

    # Compteurs
    iteration: int
    total_tokens_in: int
    total_tokens_out: int
    total_cost_usd: float

    # Validation humaine
    pending_human_approval: bool
    human_approval_reason: str | None

    # Code-review
    last_review_passed: bool
    review_findings: list[dict[str, Any]]

    # Plan global décomposé par l'orchestrateur
    plan: list[dict[str, Any]]
    completed_steps: list[str]

    # Erreurs récentes (pour retry / escalation)
    last_error: str | None
    error_count: int
