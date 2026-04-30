"""Entry point CLI de l'Orchestrateur.

Usage :
  python -m orchestrator.main interactive
  python -m orchestrator.main autonomous --brief docs/briefs/2026-04-29.md
  python -m orchestrator.main autonomous --brief - < brief.md   # stdin
  python -m orchestrator.main dry-run                            # validation config
"""
from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from ..journal import init_logger, log_event
from .config import get_settings
from .graph import build_orchestrator_graph, run_brief, run_interactive

app = typer.Typer(
    name="stonks-orchestrator",
    help="Orchestrateur principal de la flotte d'agents Stonks.",
    no_args_is_help=True,
)
console = Console()


def _bootstrap() -> None:
    """Vérifie la config, initialise le logger, prêt à servir."""
    s = get_settings()
    init_logger(s.execution_log_path)
    log_event(
        agent="orchestrator",
        phase="phase_1_bootstrap",
        action="orchestrator_started",
        input={
            "model": s.openrouter_model,
            "reasoning": s.openrouter_reasoning_effort,
            "log_path": str(s.execution_log_path),
            "repo_root": str(s.repo_root),
        },
    )


@app.command()
def interactive(
    thread_id: str = typer.Option("interactive", help="ID de session (mémoire LangGraph)."),
    mode: str = typer.Option(
        "interactive",
        "--mode",
        help="Compat Taskfile : interactive|autonomous|dry-run.",
    ),
) -> None:
    """REPL — discute avec l'orchestrateur dans le terminal."""
    if mode == "autonomous":
        console.print("[yellow]Mode autonomous demandé — bascule sur la commande dédiée.[/yellow]")
        raise typer.Exit(code=2)
    if mode == "dry-run":
        dry_run()
        return
    _bootstrap()
    console.print(Panel.fit(
        "[bold]Stonks Orchestrator — mode interactif[/bold]\n"
        f"Modèle : {get_settings().openrouter_model}\n"
        f"Logs : {get_settings().execution_log_path}",
        border_style="cyan",
    ))
    graph = build_orchestrator_graph()
    run_interactive(graph, thread_id=thread_id)


@app.command()
def autonomous(
    brief: str = typer.Option(
        ...,
        "--brief",
        help="Chemin du brief markdown, ou '-' pour lire stdin.",
    ),
    thread_id: str = typer.Option("autonomous", help="ID de session."),
    mode: str = typer.Option("autonomous", "--mode", hidden=True),
) -> None:
    """Lance l'orchestrateur sur un brief — peut tourner pendant des heures."""
    _bootstrap()
    if brief == "-":
        brief_text = sys.stdin.read()
        source = "<stdin>"
    else:
        p = Path(brief)
        if not p.exists():
            console.print(f"[red]Brief introuvable : {p}[/red]")
            raise typer.Exit(code=1)
        brief_text = p.read_text(encoding="utf-8")
        source = str(p)

    console.print(Panel.fit(
        f"[bold]Brief reçu[/bold] depuis [cyan]{source}[/cyan]\n"
        f"Longueur : {len(brief_text)} caractères\n"
        f"Modèle : {get_settings().openrouter_model}",
        border_style="green",
    ))

    graph = build_orchestrator_graph()
    response = run_brief(graph, brief_text, thread_id=thread_id)

    console.print(Panel(response, title="Réponse finale", border_style="magenta"))


@app.command("dry-run")
def dry_run() -> None:
    """Valide la config et termine — utile pour vérifier le .env."""
    try:
        s = get_settings()
    except Exception as exc:
        console.print(f"[red]❌ Config invalide : {exc}[/red]")
        raise typer.Exit(code=1) from exc

    init_logger(s.execution_log_path)
    table = (
        f"  Repo root        : [cyan]{s.repo_root}[/cyan]\n"
        f"  Execution log    : [cyan]{s.execution_log_path}[/cyan]\n"
        f"  OpenRouter model : [cyan]{s.openrouter_model}[/cyan]\n"
        f"  Light model      : [cyan]{s.openrouter_model_light}[/cyan]\n"
        f"  Reasoning effort : [cyan]{s.openrouter_reasoning_effort}[/cyan]\n"
        f"  Token budget     : [cyan]{s.orchestrator_token_budget:,}[/cyan]\n"
        f"  Target repo      : [cyan]{s.target_github_repo}[/cyan]\n"
        f"  Streamlit        : [cyan]http://{s.streamlit_server_address}:{s.streamlit_server_port}[/cyan]\n"
        f"  GitNexus URL     : [cyan]{s.gitnexus_backend_url}[/cyan]\n"
        f"  Redis URL        : [cyan]{s.redis_url}[/cyan]\n"
        f"  Human confirm    : [cyan]{s.require_human_confirmation}[/cyan]"
    )
    console.print(Panel(table, title="✅ Config OK", border_style="green"))

    # Vérifications optionnelles
    issues: list[str] = []
    if "sk-or-v1-xxxx" in s.openrouter_api_key.get_secret_value():
        issues.append("OPENROUTER_API_KEY semble être encore le placeholder du .env.example.")
    if not (s.repo_root / ".env").exists():
        issues.append("Pas de .env à la racine — l'orchestrateur tournera avec les valeurs par défaut.")
    for i in issues:
        console.print(f"[yellow]⚠ {i}[/yellow]")


if __name__ == "__main__":
    app()
