"""Streamlit UI — interface principale pour parler à l'orchestrateur.

Lance avec : `task ui` (équivalent : `streamlit run agents_core/src/stonks_core/ui/streamlit_app.py`)
URL :        http://serveurmax:8501

Sections (par ordre d'usage) :
  1. 💬 Chat            — conversation live avec l'orchestrateur (interactions courtes)
  2. 📝 Brief autonome  — missions longues (24 h+), queue → subprocess
  3. ⏳ Approbations    — accepter/rejeter les request_human_approval
  4. 📜 Logs            — tail du execution_log.txt
  5. 📊 Métriques       — tokens, coût, agents
  6. 📚 Briefs          — historique
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from stonks_core.journal import init_logger, read_recent
from stonks_core.orchestrator.config import get_settings
from stonks_core.tools.human_tools import list_pending_requests, respond_to_request


SETTINGS = get_settings()
init_logger(SETTINGS.execution_log_path)


# ─────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Stonks — Orchestrator",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.2rem; padding-bottom: 1rem; max-width: 1400px; }
      .stCodeBlock { font-size: 0.82rem; }
      [data-testid="stChatMessage"] { padding: 0.6rem 1rem; }
      .small-muted { color: #888; font-size: 0.82rem; }
      .tool-call {
          background: rgba(255,255,255,0.04);
          border-left: 3px solid #4a8fff;
          padding: 0.4rem 0.8rem;
          margin: 0.3rem 0;
          font-family: 'JetBrains Mono', monospace;
          font-size: 0.82rem;
      }
      .tool-result {
          background: rgba(255,255,255,0.02);
          border-left: 3px solid #4ad17a;
          padding: 0.4rem 0.8rem;
          margin: 0.3rem 0;
          font-family: 'JetBrains Mono', monospace;
          font-size: 0.78rem;
          color: #aaa;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────
def _check_api_key() -> tuple[bool, str]:
    """Retourne (ok, message). Vérifie que la clé OpenRouter est configurée."""
    key = SETTINGS.openrouter_api_key.get_secret_value()
    if not key or "xxxx" in key or len(key) < 20:
        return False, (
            "⚠️ La clé `OPENROUTER_API_KEY` n'est pas configurée. "
            "Édite `/opt/stonks/.env` et relance l'UI."
        )
    return True, ""


@st.cache_resource(show_spinner="Initialisation de l'orchestrateur…")
def _build_graph() -> Any:
    """Construit le graphe LangGraph (cache resource = 1 instance par process Streamlit)."""
    from stonks_core.orchestrator.graph import build_orchestrator_graph
    return build_orchestrator_graph()


def _briefs_dir() -> Path:
    p = SETTINGS.repo_root / "docs" / "briefs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _runs_dir() -> Path:
    p = SETTINGS.repo_root / "agents_core" / "runtime" / "runs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _save_brief(name: str, content: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name) or "brief"
    if not safe.endswith(".md"):
        safe += ".md"
    p = _briefs_dir() / safe
    p.write_text(content, encoding="utf-8")
    return p


def _enqueue_run(brief_path: Path, autostart: bool) -> tuple[Path, int | None]:
    """Place le brief en queue. Si autostart=True, lance un subprocess détaché."""
    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = _runs_dir() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "brief.md").write_text(brief_path.read_text(encoding="utf-8"), encoding="utf-8")
    status = {
        "status": "queued",
        "brief_path": str(brief_path),
        "queued_at": datetime.utcnow().isoformat() + "Z",
    }
    pid: int | None = None
    if autostart:
        log_out = open(run_dir / "stdout.log", "w", encoding="utf-8")
        log_err = open(run_dir / "stderr.log", "w", encoding="utf-8")
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "stonks_core.orchestrator.main",
                "autonomous",
                "--brief",
                str(brief_path),
                "--thread-id",
                f"run-{run_id}",
            ],
            cwd=str(SETTINGS.repo_root / "agents_core"),
            stdout=log_out,
            stderr=log_err,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            env={**os.environ, "PYTHONPATH": str(SETTINGS.repo_root / "agents_core" / "src")},
        )
        pid = proc.pid
        status["status"] = "running"
        status["pid"] = pid
        status["started_at"] = datetime.utcnow().isoformat() + "Z"
    (run_dir / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    return run_dir, pid


# ─────────────────────────────────────────────────────────────────────
# Chat helpers : streaming d'un ReAct LangGraph dans Streamlit
# ─────────────────────────────────────────────────────────────────────
def _format_tool_args(args: dict[str, Any]) -> str:
    """Représentation compacte des args d'un tool call."""
    if not args:
        return "()"
    parts: list[str] = []
    for k, v in args.items():
        s = json.dumps(v, ensure_ascii=False, default=str) if not isinstance(v, str) else v
        if len(s) > 120:
            s = s[:117] + "…"
        parts.append(f"{k}={s}")
    return ", ".join(parts)


def _stream_orchestrator(
    graph: Any,
    user_message: str,
    thread_id: str,
    container: Any,
) -> str:
    """Stream la réponse de l'orchestrateur dans le container Streamlit donné.

    Affiche les tool calls + résultats au fil de l'eau, puis la réponse finale.
    Retourne le texte final (pour ajout à l'historique).
    """
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": SETTINGS.max_autonomous_iterations * 2,
    }
    payload = {"messages": [HumanMessage(content=user_message)]}

    final_text = ""
    seen_tool_calls: set[str] = set()
    final_placeholder = container.empty()

    try:
        for update in graph.stream(payload, config=config, stream_mode="updates"):
            # update = {"agent": {"messages": [...]}} ou {"tools": {"messages": [...]}}
            for node_name, node_state in update.items():
                msgs = node_state.get("messages", []) if isinstance(node_state, dict) else []
                for msg in msgs:
                    # Tool calls émis par l'agent
                    if isinstance(msg, AIMessage) and msg.tool_calls:
                        for tc in msg.tool_calls:
                            tc_id = tc.get("id", "")
                            if tc_id in seen_tool_calls:
                                continue
                            seen_tool_calls.add(tc_id)
                            container.markdown(
                                f"<div class='tool-call'>🔧 <b>{tc['name']}</b>"
                                f"({_format_tool_args(tc.get('args', {}))})</div>",
                                unsafe_allow_html=True,
                            )
                    # Résultats des tools
                    elif isinstance(msg, ToolMessage):
                        text = str(msg.content)
                        preview = text[:400] + ("…" if len(text) > 400 else "")
                        container.markdown(
                            f"<div class='tool-result'>↳ {preview}</div>",
                            unsafe_allow_html=True,
                        )
                    # Réponse texte de l'agent (peut être finale ou intermédiaire)
                    elif isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                        final_text = msg.content if isinstance(msg.content, str) else str(msg.content)
                        final_placeholder.markdown(final_text)
    except Exception as exc:  # noqa: BLE001
        container.error(f"❌ Erreur orchestrateur : {type(exc).__name__}: {exc}")
        return f"ERROR::{exc}"

    return final_text


# ─────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📈 Stonks")
    st.caption("Orchestrator UI · Phase 1")
    section = st.radio(
        "Section",
        [
            "💬 Chat",
            "📝 Brief autonome",
            "⏳ Approbations",
            "📜 Logs",
            "📊 Métriques",
            "📚 Briefs",
        ],
        label_visibility="collapsed",
    )
    st.divider()

    # Health check
    api_ok, api_msg = _check_api_key()
    if api_ok:
        st.success("API ✓")
    else:
        st.error("API ✗")

    st.caption(f"**Modèle** `{SETTINGS.openrouter_model}`")
    st.caption(f"**Reasoning** `{SETTINGS.openrouter_reasoning_effort}`")
    st.caption(f"**Repo** `{SETTINGS.target_github_repo}`")
    st.caption(f"**Budget** {SETTINGS.orchestrator_token_budget:,} tk")

    # Pending approvals badge
    pending_count = len(list_pending_requests())
    if pending_count > 0:
        st.warning(f"⏳ {pending_count} approbation(s) en attente")


# ═════════════════════════════════════════════════════════════════════
# Section : 💬 CHAT (défaut)
# ═════════════════════════════════════════════════════════════════════
if section == "💬 Chat":
    st.header("💬 Chat avec l'orchestrateur")
    st.caption(
        "Pose tes questions, donne des tâches courtes, demande un état des lieux. "
        "Pour des missions longues (>30 min), utilise plutôt la section "
        "**📝 Brief autonome** qui ne bloque pas l'UI."
    )

    if not api_ok:
        st.error(api_msg)
        st.stop()

    # Init session state
    if "chat_thread_id" not in st.session_state:
        st.session_state.chat_thread_id = f"chat-{uuid.uuid4().hex[:8]}"
    if "chat_history" not in st.session_state:
        st.session_state.chat_history: list[dict[str, str]] = []

    # Toolbar
    c1, c2, c3 = st.columns([1, 1, 6])
    with c1:
        if st.button("🔄 Nouveau chat"):
            st.session_state.chat_thread_id = f"chat-{uuid.uuid4().hex[:8]}"
            st.session_state.chat_history = []
            _build_graph.clear()  # reset le checkpointer en mémoire
            st.rerun()
    with c2:
        st.caption(f"Thread : `{st.session_state.chat_thread_id}`")

    # Affiche l'historique
    for turn in st.session_state.chat_history:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])

    # Input
    if user_input := st.chat_input("Pose ta question ou ta demande à l'orchestrateur…"):
        # Affiche le message user
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Stream la réponse
        with st.chat_message("assistant"):
            with st.spinner("L'orchestrateur réfléchit…"):
                graph = _build_graph()
                container = st.container()
                response = _stream_orchestrator(
                    graph=graph,
                    user_message=user_input,
                    thread_id=st.session_state.chat_thread_id,
                    container=container,
                )
        st.session_state.chat_history.append({"role": "assistant", "content": response or "(pas de réponse)"})


# ═════════════════════════════════════════════════════════════════════
# Section : 📝 BRIEF AUTONOME
# ═════════════════════════════════════════════════════════════════════
elif section == "📝 Brief autonome":
    st.header("📝 Brief autonome (mission longue)")
    st.caption(
        "Pour les missions de plusieurs heures (jusqu'à 24 h). Le brief lance un subprocess "
        "détaché — tu peux fermer l'UI, l'orchestrateur continue. Suis l'avancée dans **📜 Logs**."
    )

    if not api_ok:
        st.error(api_msg)
        st.stop()

    template_path = SETTINGS.repo_root / "docs" / "briefs" / "_template.md"
    template = template_path.read_text(encoding="utf-8") if template_path.exists() else ""

    name = st.text_input(
        "Nom du brief (sera sauvegardé sous docs/briefs/)",
        value=datetime.utcnow().strftime("%Y-%m-%d_%H%M_brief.md"),
    )
    content = st.text_area("Contenu du brief", value=template, height=420, key="brief_content")

    autostart = st.toggle(
        "🚀 Lancer immédiatement en subprocess (sinon : juste mise en queue, lancement manuel via task)",
        value=True,
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        save_btn = st.button("💾 Sauvegarder", use_container_width=True)
    with col2:
        run_btn = st.button("▶️ Envoyer à l'orchestrateur", type="primary", use_container_width=True)

    if save_btn and content.strip():
        path = _save_brief(name, content)
        st.success(f"Sauvegardé : `{path.relative_to(SETTINGS.repo_root)}`")

    if run_btn and content.strip():
        path = _save_brief(name, content)
        run_dir, pid = _enqueue_run(path, autostart=autostart)
        if autostart:
            st.success(f"✅ Orchestrateur lancé en subprocess (PID {pid}). Run : `{run_dir.name}`")
            st.info("Suis l'avancée dans **📜 Logs** ou avec `tail -f execution_log.txt`.")
        else:
            st.info(f"📦 Brief en queue : `{run_dir.relative_to(SETTINGS.repo_root)}`")
            st.code(
                f"cd {SETTINGS.repo_root}\n"
                f"task agents:run -- --brief {path.relative_to(SETTINGS.repo_root)}",
                language="bash",
            )

    # Liste des runs en cours
    st.divider()
    st.subheader("Runs récents")
    runs = sorted(_runs_dir().glob("*/status.json"), reverse=True)[:10]
    if not runs:
        st.caption("_Aucun run pour l'instant._")
    else:
        for s_path in runs:
            try:
                data = json.loads(s_path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            run_id = s_path.parent.name
            status = data.get("status", "?")
            emoji = {"queued": "⏸", "running": "▶️", "completed": "✅", "failed": "❌"}.get(status, "❓")
            with st.expander(f"{emoji} `{run_id}` — {status}"):
                st.json(data)
                stdout_p = s_path.parent / "stdout.log"
                if stdout_p.exists() and stdout_p.stat().st_size > 0:
                    st.code(stdout_p.read_text(encoding="utf-8")[-2000:], language="bash")


# ═════════════════════════════════════════════════════════════════════
# Section : ⏳ APPROBATIONS
# ═════════════════════════════════════════════════════════════════════
elif section == "⏳ Approbations":
    st.header("⏳ Demandes d'approbation en attente")
    st.caption(
        "L'orchestrateur appelle `request_human_approval` quand il a besoin de ton OK "
        "(force push, suppression, dépense LLM > $5, etc.). Il bloque jusqu'à ta réponse."
    )
    pending = list_pending_requests()

    if not pending:
        st.success("✅ Aucune demande en attente. L'orchestrateur travaille tranquillement.")
    else:
        for req in pending:
            with st.container(border=True):
                st.subheader(f"#{req['id']}")
                st.markdown(f"**Raison** : {req.get('reason', '(non fourni)')}")
                st.caption(f"Créé : {req.get('created_at')} · expire : {req.get('expires_at')}")
                payload = req.get("payload") or {}
                if payload:
                    with st.expander("Payload"):
                        st.json(payload)
                comment = st.text_input(
                    "Commentaire (optionnel)",
                    key=f"c_{req['id']}",
                    placeholder="ex: 'OK mais ne push pas main directement'",
                )
                c1, c2, _ = st.columns([1, 1, 4])
                with c1:
                    if st.button("✅ Approuver", key=f"a_{req['id']}", use_container_width=True):
                        respond_to_request(req["id"], "approved", comment)
                        st.success("Approuvé.")
                        st.rerun()
                with c2:
                    if st.button("⛔ Rejeter", key=f"r_{req['id']}", type="secondary", use_container_width=True):
                        respond_to_request(req["id"], "rejected", comment)
                        st.warning("Rejeté.")
                        st.rerun()


# ═════════════════════════════════════════════════════════════════════
# Section : 📜 LOGS
# ═════════════════════════════════════════════════════════════════════
elif section == "📜 Logs":
    st.header("📜 Execution log")
    st.caption("`execution_log.txt` (JSONL append-only). Tout side-effect y est tracé.")

    c1, c2 = st.columns([1, 1])
    with c1:
        n = st.slider("Nombre d'entrées", 10, 1000, 120)
    with c2:
        auto_refresh = st.toggle("Auto-refresh (3 s)", value=False, key="logs_refresh")

    entries = read_recent(n=n)
    if not entries:
        st.info("Aucune entrée encore — l'orchestrateur n'a pas tourné, ou le log est vide.")
    else:
        df = pd.DataFrame(entries)
        cols = ["ts", "agent", "phase", "action", "tool", "output_summary", "cost_usd"]
        cols = [c for c in cols if c in df.columns]
        st.dataframe(df[cols], use_container_width=True, height=620)

    if auto_refresh:
        time.sleep(3)
        st.rerun()


# ═════════════════════════════════════════════════════════════════════
# Section : 📊 MÉTRIQUES
# ═════════════════════════════════════════════════════════════════════
elif section == "📊 Métriques":
    st.header("📊 Métriques cumulées")
    entries = read_recent(n=5000)

    tokens_in = sum((e.get("tokens") or {}).get("in", 0) or 0 for e in entries)
    tokens_out = sum((e.get("tokens") or {}).get("out", 0) or 0 for e in entries)
    cost = sum(float(e.get("cost_usd") or 0.0) for e in entries)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tokens IN", f"{tokens_in:,}")
    c2.metric("Tokens OUT", f"{tokens_out:,}")
    c3.metric("Coût cumulé (USD)", f"${cost:.4f}")
    budget_used_pct = (
        (tokens_in + tokens_out) / max(SETTINGS.orchestrator_token_budget, 1) * 100
    )
    c4.metric("Budget consommé", f"{budget_used_pct:.1f}%")

    st.divider()
    st.subheader("Activité par agent")
    if entries:
        df = pd.DataFrame(entries)
        if "agent" in df.columns:
            counts = df.groupby("agent").size().sort_values(ascending=False)
            st.bar_chart(counts, height=240)

        if "action" in df.columns:
            st.subheader("Actions les plus fréquentes")
            top = df.groupby("action").size().sort_values(ascending=False).head(15)
            st.bar_chart(top, height=240)


# ═════════════════════════════════════════════════════════════════════
# Section : 📚 BRIEFS
# ═════════════════════════════════════════════════════════════════════
elif section == "📚 Briefs":
    st.header("📚 Briefs sauvegardés")
    briefs = sorted(_briefs_dir().glob("*.md"), reverse=True)
    if not briefs:
        st.info("Aucun brief sauvegardé. Va sur **📝 Brief autonome** pour en créer un.")
    else:
        for b in briefs:
            label = (
                f"📄 {b.name}  ·  "
                f"{datetime.fromtimestamp(b.stat().st_mtime).isoformat(timespec='seconds')}"
            )
            with st.expander(label):
                st.markdown(b.read_text(encoding="utf-8"))
