"""
FICHIER CORRIGÉ : /opt/stonks/agents_core/src/tools/__init__.py

Changement principal :
- gh_pr_merge RETIRÉ de ORCHESTRATOR_TOOLS (l'orchestrateur ne peut plus merger)
- Ajout d'un commentaire explicite sur l'interdiction de merge automatique
"""

from .file_tools import (
    file_append,
    file_delete,
    file_list,
    file_read,
    file_write,
)
from .git_tools import (
    gh_pr_create,
    gh_pr_merge,  # conservé pour usage humain uniquement (UI Streamlit / REPL)
    git_branch,
    git_commit,
    git_diff,
    git_pull,
    git_push,
    git_status,
)
from .gh_ci_tools import (
    gh_pr_failed_logs,
    gh_pr_status,
    gh_wait_for_ci,
)
from .gitnexus_tools import (
    gitnexus_context,
    gitnexus_cypher,
    gitnexus_detect_changes,
    gitnexus_impact,
    gitnexus_index,
    gitnexus_query,
)
from .human_tools import (
    list_pending_requests,
    request_human_approval,
    respond_to_request,
)
from .shell_tools import shell_exec
from .spawn_tools import spawn_agent

# Toolsets prêts à binder selon le rôle.
#
# ⚠️ RÈGLE CRITIQUE (2026-05-05) :
# gh_pr_merge est VOLONTAIREMENT absent des outils de l'orchestrateur
# et des sous-agents. Le merge est une ACTION HUMAINE EXCLUSIVE.
# Voir décision post-mortem PR feat(web) 2.4 mergée malgré CI rouge.

ORCHESTRATOR_TOOLS = [
    file_read,
    file_write,
    file_append,
    file_list,
    file_delete,
    shell_exec,
    git_status,
    git_branch,
    git_commit,
    git_push,
    git_pull,
    git_diff,
    gh_pr_create,
    # gh_pr_merge → RETIRÉ. Merge = humain uniquement.
    gitnexus_index,
    gitnexus_impact,
    gitnexus_query,
    gitnexus_context,
    gitnexus_detect_changes,
    gitnexus_cypher,
    spawn_agent,
    gh_pr_status,
    gh_pr_failed_logs,
    gh_wait_for_ci,
    request_human_approval,
]

# Sous-agents : pas de spawn_agent (anti-récursion), pas de gh_pr_merge (le
# Reviewer décide), pas de file_delete (passer par le Reviewer).
SUBAGENT_TOOLS = [
    file_read,
    file_write,
    file_append,
    file_list,
    shell_exec,
    git_status,
    git_branch,
    git_commit,
    git_push,
    git_diff,
    gh_pr_create,
    # gh_pr_merge → RETIRÉ. Merge = humain uniquement.
    gh_pr_status,
    gh_pr_failed_logs,
    gh_wait_for_ci,
    gitnexus_impact,
    gitnexus_query,
    gitnexus_context,
    request_human_approval,
]

# Reviewer : lecture-only sur le code, peut commenter une PR et la rejeter.
REVIEWER_TOOLS = [
    file_read,
    file_list,
    shell_exec,  # pour lancer pytest, ruff, mypy
    git_status,
    git_diff,
    gitnexus_impact,
    gitnexus_detect_changes,
    gitnexus_query,
    gitnexus_context,
]

# Outil de merge accessible uniquement depuis l'UI Streamlit / le REPL humain.
# Les agents (orchestrateur, sous-agents, reviewer) n'y ont PAS accès.
HUMAN_ONLY_TOOLS = [
    gh_pr_merge,
]


__all__ = [
    "HUMAN_ONLY_TOOLS",
    "ORCHESTRATOR_TOOLS",
    "REVIEWER_TOOLS",
    "SUBAGENT_TOOLS",
    "file_append",
    "file_delete",
    "file_list",
    "file_read",
    "file_write",
    "gh_pr_create",
    "gh_pr_failed_logs",
    "gh_pr_merge",
    "gh_pr_status",
    "gh_wait_for_ci",
    "git_branch",
    "git_commit",
    "git_diff",
    "git_pull",
    "git_push",
    "git_status",
    "gitnexus_context",
    "gitnexus_cypher",
    "gitnexus_detect_changes",
    "gitnexus_impact",
    "gitnexus_index",
    "gitnexus_query",
    "list_pending_requests",
    "request_human_approval",
    "respond_to_request",
    "shell_exec",
    "spawn_agent",
]
