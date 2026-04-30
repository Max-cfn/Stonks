"""Graphe LangGraph principal de l'Orchestrateur.

L'Orchestrateur est lui-même un ReAct agent : il tourne en boucle
"thought → tool → observation → thought" jusqu'à ce qu'il décide d'arrêter
(ou jusqu'à `max_autonomous_iterations`).

Sa puissance vient de ses outils (file/shell/git/gitnexus) et surtout de
`spawn_agent` qui lui permet de déléguer à des sous-agents spécialisés.

On garde le graphe minimal en Phase 1. La Phase 2 ajoutera :
- Persistance d'état (Redis/Postgres)
- Parallélisation des sous-agents
- Timeline visualisable dans l'UI
"""
from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from ..journal import log_event
from ..tools import ORCHESTRATOR_TOOLS
from .config import get_settings
from .llm import make_orchestrator_model
from .system_prompt import render_system_prompt


def build_orchestrator_graph() -> Any:
    """Construit le graphe ReAct de l'Orchestrateur Principal.

    On utilise un MemorySaver in-process en Phase 1 (suffisant pour un seul
    user). En Phase 2, on remplacera par un checkpointer Redis ou Postgres
    pour permettre le redémarrage / reprise après crash.
    """
    model = make_orchestrator_model()
    system = render_system_prompt()
    checkpointer = MemorySaver()

    return create_react_agent(
        model=model,
        tools=ORCHESTRATOR_TOOLS,
        prompt=system,
        checkpointer=checkpointer,
    )


def run_brief(graph: Any, brief: str, thread_id: str = "main") -> str:
    """Lance l'orchestrateur sur un brief humain.

    Args:
        graph: Le graphe construit par build_orchestrator_graph().
        brief: Texte du brief (idéalement markdown structuré).
        thread_id: Identifiant de session pour le checkpointer.

    Returns:
        Réponse finale de l'orchestrateur (texte).
    """
    s = get_settings()
    log_event(
        agent="orchestrator",
        phase="ad_hoc",
        action="brief_received",
        input={"brief_preview": brief[:500], "thread_id": thread_id},
    )

    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": s.max_autonomous_iterations * 2,
    }
    messages = [HumanMessage(content=brief)]

    try:
        result: dict[str, Any] = graph.invoke({"messages": messages}, config=config)
    except Exception as exc:
        err = f"Orchestrator crashed: {type(exc).__name__}: {exc}"
        log_event(agent="orchestrator", phase="ad_hoc", action="orchestrator_error",
                  output_summary=err)
        return f"ERROR::{err}"

    final_msgs = result.get("messages", [])
    last = final_msgs[-1] if final_msgs else None
    text = getattr(last, "content", "") if last else ""

    log_event(
        agent="orchestrator",
        phase="ad_hoc",
        action="brief_completed",
        output_summary=str(text)[:500],
    )
    return str(text)


def run_interactive(graph: Any, thread_id: str = "interactive") -> None:
    """REPL — lit stdin, envoie au graph, affiche la réponse."""
    print("─" * 70)
    print("  Stonks Orchestrator — mode interactif")
    print("  Tape ton brief, puis ligne vide pour envoyer.")
    print("  Tape 'exit' pour quitter, 'reset' pour repartir d'une session vierge.")
    print("─" * 70)

    while True:
        print("\n>>> Brief (ligne vide = envoyer) :")
        lines: list[str] = []
        while True:
            try:
                line = input()
            except EOFError:
                return
            if line == "":
                break
            lines.append(line)
        brief = "\n".join(lines).strip()
        if not brief:
            continue
        if brief.lower() == "exit":
            print("Bye.")
            return
        if brief.lower() == "reset":
            thread_id = f"interactive-{id(brief)}"
            print("(thread reset)")
            continue
        response = run_brief(graph, brief, thread_id=thread_id)
        print("\n" + "─" * 70)
        print(response)
        print("─" * 70)
