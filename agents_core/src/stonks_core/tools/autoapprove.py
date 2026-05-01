"""Politique d'auto-approbation pour les demandes `request_human_approval`.

Quand tu n'es pas devant ton écran et que tu veux que l'orchestrateur tranche
seul certaines décisions tout en bloquant pour les vraiment importantes, tu
configures une policy :

  STONKS_AUTOAPPROVE_LEVEL=conservative|moderate|yolo|off
  STONKS_AUTOAPPROVE_POLICY=/path/to/custom_policy.yaml   (optionnel, override)
  STONKS_AUTOAPPROVE_BUDGET_LIMIT_USD=5.0                 (au-delà → bloque)

Niveaux preset :

- **off** (défaut) : aucune auto-approbation. Tout passe par toi.
- **conservative** : auto-approuve les actions purement sandbox (commandes
  shell read-only, lectures de fichiers, queries GitNexus, indexation,
  installations de packages dans .venv local, création de branches, commits
  non-destructifs). Bloque tout ce qui touche au réseau externe, secrets,
  bases de données, écritures sur main, suppression.
- **moderate** : conservative + auto-approuve les ouvertures de PR vers main
  (le merge reste à toi via GitHub), les migrations Alembic non-destructives,
  les requêtes LLM jusqu'à $5 par appel, les pushs sur branches `agent/**`.
- **yolo** : auto-approuve TOUT sauf actions explicitement listées dans
  `ALWAYS_BLOCK` (ci-dessous). Pour les briefs de nuit où tu fais 100%
  confiance et tu veux 0 friction. Reste safe sur les trucs vraiment
  destructifs (force push main, drop database, rm -rf, suppression vault).

Format custom_policy.yaml (override total) :

```yaml
auto_approve:
  - reason_pattern: ^install dev deps in venv$
  - action_pattern: ^npm install
  - tool: shell_exec
    args_pattern:
      command: "^(pnpm|npm|uv) (install|add|run) "
  - reason_pattern: open pr.*agent/.*->.*main
    cost_max_usd: 0.5
always_block:
  - action_pattern: force[- ]push.*(main|master)
  - action_pattern: drop database
  - tool: shell_exec
    args_pattern:
      command: "rm -rf|chmod 777|chown root"
budget_limit_usd: 5.0
```
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

try:
    import yaml  # type: ignore[import-untyped]

    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


AutoApproveLevel = Literal["off", "conservative", "moderate", "yolo"]


# ─────────────────────────────────────────────────────────────────────
# Règles toujours bloquantes (override yolo)
# ─────────────────────────────────────────────────────────────────────
ALWAYS_BLOCK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"force[- ]push.*\b(main|master|release)\b", re.IGNORECASE),
    re.compile(r"\brm\s+-rf?\s+(/|~|\$HOME|/opt(?!/stonks)|\.\.)", re.IGNORECASE),
    re.compile(r"chmod\s+(-R\s+)?777", re.IGNORECASE),
    re.compile(r"chown\s+(-R\s+)?root", re.IGNORECASE),
    re.compile(r"drop\s+(database|schema|table\s+\w+\s+cascade)", re.IGNORECASE),
    re.compile(r"DELETE\s+FROM\s+\w+\s*(?!WHERE)", re.IGNORECASE),  # DELETE sans WHERE
    re.compile(r"truncate\s+table", re.IGNORECASE),
    re.compile(r"vault\s+(token\s+revoke|secrets\s+disable)", re.IGNORECASE),
    re.compile(r"git\s+push\s+(--force|-f)\s+.*\b(main|master)\b", re.IGNORECASE),
    re.compile(r"sudo\s+(rm|dd|mkfs|fdisk|parted)", re.IGNORECASE),
    re.compile(r"docker\s+(rm\s+-f|volume\s+rm|system\s+prune)", re.IGNORECASE),
    re.compile(r"\bpasswd\b|\bsudoers\b|\b/etc/shadow\b", re.IGNORECASE),
]


# ─────────────────────────────────────────────────────────────────────
# Presets
# ─────────────────────────────────────────────────────────────────────
@dataclass
class Rule:
    """Une règle qui peut matcher une demande d'approbation."""

    reason_pattern: str | None = None
    action_pattern: str | None = None
    tool: str | None = None
    args_pattern: dict[str, str] = field(default_factory=dict)
    cost_max_usd: float | None = None  # Bloque si payload.cost_estimate_usd dépasse

    def matches(self, reason: str, payload: dict[str, Any]) -> bool:
        if self.reason_pattern and not re.search(self.reason_pattern, reason, re.IGNORECASE):
            return False
        if self.action_pattern:
            action = str(payload.get("action") or payload.get("command") or "")
            if not re.search(self.action_pattern, action, re.IGNORECASE):
                return False
        if self.tool and payload.get("tool") != self.tool:
            return False
        for key, pat in self.args_pattern.items():
            val = str(payload.get(key) or payload.get("args", {}).get(key) or "")
            if not re.search(pat, val, re.IGNORECASE):
                return False
        if self.cost_max_usd is not None:
            cost = float(payload.get("cost_estimate_usd") or 0)
            if cost > self.cost_max_usd:
                return False
        return True


@dataclass
class Policy:
    """Policy d'auto-approbation."""

    level: AutoApproveLevel = "off"
    auto_approve: list[Rule] = field(default_factory=list)
    always_block: list[Rule] = field(default_factory=list)
    budget_limit_usd: float = 5.0
    auto_comment: str = "auto-approved by policy"


# Règles "lecture seule" (toujours OK même en conservative)
_READ_ONLY_RULES = [
    Rule(tool="file_read"),
    Rule(tool="file_list"),
    Rule(tool="git_status"),
    Rule(tool="git_log"),
    Rule(tool="git_diff"),
    Rule(tool="gitnexus_query"),
    Rule(tool="gitnexus_context"),
    Rule(tool="gitnexus_impact"),
    Rule(action_pattern=r"^(ls|cat|head|tail|grep|find|wc|stat|file|du|df|free|ps|whoami|pwd|env|which|date|uptime)\b"),
]

# Règles sandbox local (conservative)
_SANDBOX_LOCAL_RULES = _READ_ONLY_RULES + [
    Rule(tool="file_write"),  # écriture dans /opt/stonks (déjà sandboxée)
    Rule(tool="file_append"),
    Rule(tool="gitnexus_index"),
    Rule(tool="git_branch"),
    Rule(tool="git_commit"),
    Rule(action_pattern=r"^(pnpm|npm|uv|pip)\s+(install|add|run|exec|sync|lock|tree)\b"),
    Rule(action_pattern=r"^(pytest|ruff|mypy|black|prettier|eslint|tsc)\b"),
    Rule(action_pattern=r"^docker\s+compose\s+(up|down|ps|logs|restart|build)\b"),
    Rule(action_pattern=r"^task\s+\w+"),
    Rule(action_pattern=r"^mkdir\s+-p\b"),
    Rule(action_pattern=r"^cp\s+.*[^\s]\s+.*[^\s]\s*$"),
    Rule(action_pattern=r"^mv\s+.*[^\s]\s+.*[^\s]\s*$"),
    Rule(reason_pattern=r"^(install|setup|configure|index|lint|format|test)\s+"),
    Rule(reason_pattern=r"^(create|add)\s+(branch|file|directory|test)"),
    Rule(reason_pattern=r"^run\s+(test|lint|format|migration)"),
]

# Règles moderate (sandbox + git push branches agent/* + PR + migrations)
_MODERATE_EXTRA_RULES = [
    Rule(action_pattern=r"^git\s+push\s+(?!.*\bmain\b)(?!.*\bmaster\b)(?!.*--force).*\bagent/"),
    Rule(action_pattern=r"^gh\s+pr\s+(create|edit|comment|view|list)\b"),
    Rule(action_pattern=r"^alembic\s+(upgrade|current|history|heads)\b"),
    Rule(reason_pattern=r"^open\s+(pr|pull request).*agent/.*->.*main", cost_max_usd=0.5),
    Rule(reason_pattern=r"^run\s+migration\s+(upgrade|head)"),
    Rule(reason_pattern=r"^llm\s+call", cost_max_usd=5.0),
]


def _make_preset(level: AutoApproveLevel) -> Policy:
    if level == "off":
        return Policy(level="off")
    if level == "conservative":
        return Policy(level="conservative", auto_approve=list(_SANDBOX_LOCAL_RULES))
    if level == "moderate":
        return Policy(
            level="moderate",
            auto_approve=list(_SANDBOX_LOCAL_RULES) + list(_MODERATE_EXTRA_RULES),
        )
    if level == "yolo":
        # Tout passe sauf ALWAYS_BLOCK_PATTERNS
        # Match-all rule
        return Policy(
            level="yolo",
            auto_approve=[Rule(reason_pattern=r".*")],
        )
    return Policy(level="off")


# ─────────────────────────────────────────────────────────────────────
# Loading
# ─────────────────────────────────────────────────────────────────────
def _load_custom_policy(path: Path) -> Policy:
    if not path.exists():
        raise FileNotFoundError(f"STONKS_AUTOAPPROVE_POLICY={path} not found")
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        if not _HAS_YAML:
            raise RuntimeError("PyYAML required to load YAML policy. pip install pyyaml")
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)

    auto_rules = [Rule(**r) for r in (data.get("auto_approve") or [])]
    block_rules = [Rule(**r) for r in (data.get("always_block") or [])]
    return Policy(
        level=data.get("level", "custom"),  # type: ignore[arg-type]
        auto_approve=auto_rules,
        always_block=block_rules,
        budget_limit_usd=float(data.get("budget_limit_usd", 5.0)),
        auto_comment=data.get("auto_comment", "auto-approved by custom policy"),
    )


_cached_policy: Policy | None = None


def get_policy(force_reload: bool = False) -> Policy:
    """Charge la policy une seule fois (cached). force_reload pour relire."""
    global _cached_policy
    if _cached_policy is not None and not force_reload:
        return _cached_policy

    custom_path = os.environ.get("STONKS_AUTOAPPROVE_POLICY")
    if custom_path:
        _cached_policy = _load_custom_policy(Path(custom_path).expanduser())
        return _cached_policy

    level = os.environ.get("STONKS_AUTOAPPROVE_LEVEL", "off").lower()
    if level not in ("off", "conservative", "moderate", "yolo"):
        level = "off"
    policy = _make_preset(level)  # type: ignore[arg-type]

    budget = os.environ.get("STONKS_AUTOAPPROVE_BUDGET_LIMIT_USD")
    if budget:
        try:
            policy.budget_limit_usd = float(budget)
        except ValueError:
            pass

    _cached_policy = policy
    return policy


# ─────────────────────────────────────────────────────────────────────
# Decision
# ─────────────────────────────────────────────────────────────────────
@dataclass
class Decision:
    """Décision de la policy pour une demande donnée."""

    auto_approved: bool
    reason: str  # explication de la décision (utile pour l'audit)
    rule_matched: str | None = None  # description de la règle qui a matché


def evaluate(
    reason: str,
    payload: dict[str, Any] | None = None,
    cost_estimate_usd: float = 0.0,
) -> Decision:
    """Évalue si une demande peut être auto-approuvée.

    Args:
        reason: la raison passée à request_human_approval
        payload: le payload contextuel
        cost_estimate_usd: si la demande implique un coût LLM ou un budget

    Returns:
        Decision avec auto_approved=True si la policy autorise, False sinon.
    """
    payload = payload or {}
    if cost_estimate_usd:
        payload = {**payload, "cost_estimate_usd": cost_estimate_usd}

    policy = get_policy()

    if policy.level == "off":
        return Decision(False, "auto-approve disabled (level=off)")

    # 1. Hard-block patterns (jamais auto-approuvé)
    full_text = f"{reason} {json.dumps(payload, default=str)}"
    for pat in ALWAYS_BLOCK_PATTERNS:
        if pat.search(full_text):
            return Decision(False, f"matches ALWAYS_BLOCK pattern: {pat.pattern}", pat.pattern)

    # 2. Custom always_block (si policy custom)
    for rule in policy.always_block:
        if rule.matches(reason, payload):
            return Decision(False, "matches custom always_block rule", str(rule))

    # 3. Budget global
    if cost_estimate_usd > policy.budget_limit_usd:
        return Decision(
            False,
            f"cost_estimate {cost_estimate_usd:.2f} > budget_limit {policy.budget_limit_usd:.2f}",
        )

    # 4. Auto-approve patterns
    for rule in policy.auto_approve:
        if rule.matches(reason, payload):
            return Decision(True, policy.auto_comment, str(rule))

    return Decision(False, f"no auto-approve rule matched (level={policy.level})")


# ─────────────────────────────────────────────────────────────────────
# Helpers d'audit
# ─────────────────────────────────────────────────────────────────────
def audit_record(
    req_id: str,
    decision: Decision,
    reason: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Construit l'enregistrement audit pour log_event."""
    return {
        "req_id": req_id,
        "auto_approved": decision.auto_approved,
        "decision_reason": decision.reason,
        "rule_matched": decision.rule_matched,
        "policy_level": get_policy().level,
        "request_reason": reason[:300],
        "ts": datetime.now(UTC).isoformat(),
    }
