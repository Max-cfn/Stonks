"""Runner des sous-agents.

Pattern : ReAct minimal LangGraph (un nœud LLM + un nœud ToolNode + boucle).
On utilise `create_react_agent` de langgraph.prebuilt pour ne pas réinventer
la roue, mais on encapsule pour :
- Logger chaque tour
- Compter les tokens et le coût
- Plafonner le nombre d'itérations
- Retourner un résumé textuel utilisable par l'orchestrateur
"""
from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from ..journal import log_event
from ..orchestrator.llm import make_chat_model, make_light_model
from ..tools import REVIEWER_TOOLS, SUBAGENT_TOOLS
from .prompts import get_subagent_prompt


def _select_model_and_tools(role: str) -> tuple[Any, list[Any]]:
    """Reviewer = modèle léger Flash, sous-agents code = Pro."""
    if role == "reviewer":
        return make_light_model(), REVIEWER_TOOLS
    return make_chat_model(), SUBAGENT_TOOLS


def run_subagent(role: str, brief: str, max_iterations: int = 50) -> str:
    """Exécute un sous-agent jusqu'à terminaison ou max_iterations."""
    log_event(
        agent=role,
        phase="ad_hoc",
        action="subagent_started",
        input={"brief_preview": brief[:300]},
    )

    model, tools = _select_model_and_tools(role)
    system = get_subagent_prompt(role)
    agent = create_react_agent(model=model, tools=tools, prompt=system)

    messages = [
        SystemMessage(content=system),
        HumanMessage(content=f"Brief :\n\n{brief}"),
    ]

    try:
        result: dict[str, Any] = agent.invoke(
            {"messages": messages},
            config={"recursion_limit": max_iterations * 2},  # 2 = un pas LLM + un pas Tool
        )
    except Exception as exc:
        err = f"subagent {role} crashed: {type(exc).__name__}: {exc}"
        log_event(agent=role, phase="ad_hoc", action="subagent_error", output_summary=err)
        return f"ERROR::{err}"

    final_messages = result.get("messages", [])
    final_text = ""
    tokens_in = 0
    tokens_out = 0
    for msg in final_messages:
        if isinstance(msg, AIMessage):
            usage = (msg.response_metadata or {}).get("token_usage") or {}
            tokens_in += int(usage.get("prompt_tokens", 0) or 0)
            tokens_out += int(usage.get("completion_tokens", 0) or 0)
            if isinstance(msg.content, str) and msg.content:
                final_text = msg.content  # on garde le dernier message texte

        log_event(
        agent=role,
        phase="ad_hoc",
        action="subagent_finished",
        output_summary=final_text[:500] or "(pas de message texte final)",
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=0.0,  # estimation locale supprimée — voir https://openrouter.ai/activity
    )
    return final_text or f"(sous-agent {role} terminé sans message final)"
