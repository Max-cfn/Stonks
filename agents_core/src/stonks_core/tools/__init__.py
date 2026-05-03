"""Outils natifs de la flotte d'agents.

Tous ces outils sont des `@tool` LangChain — on peut les binder directement
sur un ChatModel via `model.bind_tools([...])`.
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
    gh_pr_merge,
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
    gh_pr_merge,
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


__all__ = [
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
