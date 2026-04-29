"""Sous-agents spécialisés.

Chaque sous-agent est un nœud LangGraph avec :
- Un system prompt spécifique à son rôle
- Un toolset restreint (cf. tools/__init__.py)
- Un budget d'itérations (max_iterations)
- Le state partagé en lecture/écriture

Ils sont instanciés à la demande par l'Orchestrateur via `spawn_agent`.
"""
from __future__ import annotations

from .runner import run_subagent

__all__ = ["run_subagent"]
