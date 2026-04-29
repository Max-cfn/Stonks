"""CLI utilitaire — `stonks-agent` pour les opérations d'observabilité.

Utilisé par `task agents:status` et pour debug rapide.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ..journal import read_recent
from ..tools.human_tools import list_pending_requests
from .config import get_settings
from .llm import estimate_cost

app = typer.Typer(name="stonks-agent", help="Observabilité de la flotte.", no_args_is_help=True)
console = Console()


@app.command()
def status() -> None:
    """État de la flotte : derniers logs, agents actifs, coût cumulé."""
    s = get_settings()
    recent = read_recent(n=500)

    actions_by_agent: Counter[str] = Counter()
    cost_by_model: Counter[str] = Counter()
    tokens_in_total = 0
    tokens_out_total = 0
    cost_total = 0.0

    for e in recent:
        actions_by_agent[e.get("agent", "?")] += 1
        ti = (e.get("tokens") or {}).get("in", 0) or 0
        to = (e.get("tokens") or {}).get("out", 0) or 0
        tokens_in_total += ti
        tokens_out_total += to
        cost_total += float(e.get("cost_usd") or 0.0)

    t1 = Table(title=f"Activité (dernières {len(recent)} entrées de execution_log.txt)")
    t1.add_column("Agent")
    t1.add_column("Actions", justify="right")
    for agent, count in actions_by_agent.most_common():
        t1.add_row(agent, str(count))
    console.print(t1)

    t2 = Table(title="Consommation LLM cumulée")
    t2.add_column("Métrique")
    t2.add_column("Valeur", justify="right")
    t2.add_row("Tokens in (cumul)", f"{tokens_in_total:,}")
    t2.add_row("Tokens out (cumul)", f"{tokens_out_total:,}")
    t2.add_row("Coût USD (cumul)", f"${cost_total:.4f}")
    t2.add_row("Budget restant", f"{s.orchestrator_token_budget - tokens_in_total - tokens_out_total:,} tokens")
    console.print(t2)

    pending = list_pending_requests()
    if pending:
        console.print(f"[yellow]{len(pending)} demande(s) d'approbation en attente :[/yellow]")
        for p in pending:
            console.print(f"  • [cyan]{p['id']}[/cyan] — {p['reason'][:80]}")
    else:
        console.print("[green]Aucune demande d'approbation en attente.[/green]")


@app.command()
def tail(n: int = 20) -> None:
    """Affiche les n derniers logs en JSON pretty."""
    for e in read_recent(n=n):
        console.print_json(json.dumps(e, ensure_ascii=False, default=str))


@app.command()
def approve(req_id: str, comment: str = "") -> None:
    """Approuve une demande humaine (depuis le terminal)."""
    from ..tools.human_tools import respond_to_request

    ok = respond_to_request(req_id, "approved", comment)
    console.print(f"[green]✅ approved[/green] {req_id}" if ok else f"[red]❌ pas trouvé : {req_id}[/red]")


@app.command()
def reject(req_id: str, comment: str = "") -> None:
    """Rejette une demande humaine."""
    from ..tools.human_tools import respond_to_request

    ok = respond_to_request(req_id, "rejected", comment)
    console.print(f"[yellow]⛔ rejected[/yellow] {req_id}" if ok else f"[red]❌ pas trouvé : {req_id}[/red]")


@app.command()
def cost_estimate(model: str, tokens_in: int, tokens_out: int) -> None:
    """Calcule le coût d'un appel LLM (utile en debug)."""
    cost = estimate_cost(model, tokens_in, tokens_out)
    console.print(f"Coût estimé pour {model} ({tokens_in}/{tokens_out}) : [cyan]${cost:.6f}[/cyan]")


if __name__ == "__main__":
    app()
