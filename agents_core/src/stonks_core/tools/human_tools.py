"""Outil `request_human_approval` — bloque l'orchestrateur jusqu'à validation humaine.

Implémentation file-based (JSON) : chaque demande crée un fichier dans
`agents_core/runtime/approvals/<id>.json`. Le `state.status` passe de
`pending` à `approved` ou `rejected` quand l'humain répond via :
  - L'UI Streamlit (bouton Approuver / Rejeter)
  - Le REPL : `> approve <id> [comment]` / `> reject <id> [comment]`
  - Manuellement : éditer le JSON et changer le champ `status`

Le fichier comporte aussi un `expires_at` (défaut +30 min) ; au-delà, la
demande est considérée timeout et l'orchestrateur escalade ou abandonne.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from langchain_core.tools import tool

from ..journal import log_event
from ..orchestrator.config import get_settings


ApprovalStatus = Literal["pending", "approved", "rejected", "timeout"]


def _approvals_dir() -> Path:
    d = get_settings().repo_root / "agents_core" / "runtime" / "approvals"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_request(req_id: str) -> dict[str, Any] | None:
    p = _approvals_dir() / f"{req_id}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _write_request(req_id: str, data: dict[str, Any]) -> None:
    p = _approvals_dir() / f"{req_id}.json"
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def list_pending_requests() -> list[dict[str, Any]]:
    """Retourne toutes les demandes `pending` (utile pour l'UI Streamlit)."""
    out: list[dict[str, Any]] = []
    for f in sorted(_approvals_dir().glob("*.json")):
        data = _read_request(f.stem)
        if data and data.get("status") == "pending":
            out.append(data)
    return out


def respond_to_request(
    req_id: str,
    decision: Literal["approved", "rejected"],
    comment: str = "",
    responder: str = "max",
) -> bool:
    """Met à jour une demande (appelée depuis l'UI Streamlit ou le REPL)."""
    data = _read_request(req_id)
    if not data or data.get("status") != "pending":
        return False
    data["status"] = decision
    data["responded_at"] = datetime.now(UTC).isoformat()
    data["responder"] = responder
    data["response_comment"] = comment
    _write_request(req_id, data)
    log_event(
        agent="human",
        phase=data.get("phase", "ad_hoc"),
        action="approval_response",
        tool="request_human_approval",
        output_summary=f"req={req_id} decision={decision} comment={comment[:200]}",
        human_intervention=True,
    )
    return True


@tool
def request_human_approval(
    reason: str,
    payload: dict[str, Any] | None = None,
    timeout_minutes: int = 30,
    poll_seconds: float = 2.0,
) -> str:
    """Bloque jusqu'à ce que l'humain approuve ou rejette.

    Écrit une demande dans agents_core/runtime/approvals/, polle son statut,
    et retourne le verdict + commentaire humain.

    Args:
        reason: Pourquoi tu demandes (visible par l'humain).
        payload: Données contextuelles (diff, plan, commande à exécuter, etc.)
        timeout_minutes: Timeout (défaut 30 min). Au-delà, retourne 'timeout'.
        poll_seconds: Intervalle de polling.

    Returns:
        String formatté `STATUS::comment` — ex. `approved::go ahead`,
        `rejected::pas de docker exposed sur internet`, `timeout::`.
    """
    req_id = uuid.uuid4().hex[:12]
    now = datetime.now(UTC)
    data = {
        "id": req_id,
        "status": "pending",
        "reason": reason,
        "payload": payload or {},
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=timeout_minutes)).isoformat(),
        "phase": "ad_hoc",
    }
    _write_request(req_id, data)

    log_event(
        agent="orchestrator",
        phase="ad_hoc",
        action="approval_requested",
        tool="request_human_approval",
        input={"reason": reason, "req_id": req_id, "timeout_minutes": timeout_minutes},
        human_intervention=True,
    )

    deadline = time.time() + timeout_minutes * 60
    while time.time() < deadline:
        time.sleep(poll_seconds)
        current = _read_request(req_id)
        if not current:
            return "rejected::request file disappeared"
        status = current.get("status", "pending")
        if status in ("approved", "rejected"):
            comment = current.get("response_comment", "")
            log_event(
                agent="orchestrator",
                phase="ad_hoc",
                action="approval_received",
                tool="request_human_approval",
                output_summary=f"req={req_id} status={status} comment={comment[:200]}",
                human_intervention=True,
            )
            return f"{status}::{comment}"

    # Timeout
    data["status"] = "timeout"
    _write_request(req_id, data)
    log_event(
        agent="orchestrator",
        phase="ad_hoc",
        action="approval_timeout",
        tool="request_human_approval",
        output_summary=f"req={req_id} expired after {timeout_minutes}min",
        human_intervention=True,
    )
    return "timeout::"
