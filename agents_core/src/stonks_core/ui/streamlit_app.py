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
  7. ⚙️ Config          — édition rapide de quelques variables .env
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

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
          background: rgba(74, 143, 255, 0.08);
          border-left: 3px solid #4a8fff;
          padding: 0.4rem 0.8rem;
          margin: 0.3rem 0;
          font-family: 'JetBrains Mono', monospace;
          font-size: 0.82rem;
      }
      .tool-result {
          background: rgba(74, 209, 122, 0.05);
          border-left: 3px solid #4ad17a;
          padding: 0.4rem 0.8rem;
          margin: 0.3rem 0;
          font-family: 'JetBrains Mono', monospace;
          font-size: 0.78rem;
          color: #aaa;
          white-space: pre-wrap;
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
        with (
            open(run_dir / "stdout.log", "w", encoding="utf-8") as log_out,
            open(run_dir / "stderr.log", "w", encoding="utf-8") as log_err,
        ):
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
                env={
                    **os.environ,
                    "PYTHONPATH": str(SETTINGS.repo_root / "agents_core" / "src"),
                },
            )
            pid = proc.pid
            status["status"] = "running"
            status["pid"] = pid
            status["started_at"] = datetime.utcnow().isoformat() + "Z"
            # subprocess.Popen detaches the child; we close the file handles
            # subprocess.Popen detaches the child
    (run_dir / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    return run_dir, pid


# ─────────────────────────────────────────────────────────────────────
# .env editor (limité à un sous-ensemble safe)
# ─────────────────────────────────────────────────────────────────────
_ENV_PATH = SETTINGS.repo_root / ".env"


def _read_env_var(key: str) -> str | None:
    if not _ENV_PATH.exists():
        return None
    pat = re.compile(rf"^{re.escape(key)}\s*=\s*(.*)$", re.MULTILINE)
    m = pat.search(_ENV_PATH.read_text(encoding="utf-8"))
    return m.group(1).strip() if m else None


def _write_env_var(key: str, value: str) -> bool:
    """Met à jour ou ajoute KEY=value dans le .env. Retourne True si modifié."""
    if not _ENV_PATH.exists():
        return False
    text = _ENV_PATH.read_text(encoding="utf-8")
    pat = re.compile(rf"^{re.escape(key)}\s*=.*$", re.MULTILINE)
    if pat.search(text):
        new_text = pat.sub(f"{key}={value}", text)
    else:
        new_text = text.rstrip() + f"\n{key}={value}\n"
    if new_text == text:
        return False
    _ENV_PATH.write_text(new_text, encoding="utf-8")
    return True


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


_INVALID_HISTORY_MARKERS = (
    "INVALID_CHAT_HISTORY",
    "do not have a corresponding ToolMessage",
)


def _is_invalid_history_error(exc: Exception) -> bool:
    msg = str(exc)
    return any(m in msg for m in _INVALID_HISTORY_MARKERS)


def _run_orchestrator(
    graph: Any,
    user_message: str,
    thread_id: str,
    container: Any,
) -> tuple[str, bool]:
    """Exécute l'orchestrateur sur 1 message user + render dans le container.

    Utilise stream_mode='values' qui renvoie l'état complet à chaque step
    (cohérence garantie : impossible d'avoir un AIMessage avec tool_calls
    sans son ToolMessage correspondant).

    Returns:
        (final_text, ok). Si ok=False et que c'est une erreur d'historique
        corrompu, l'appelant peut décider de regénérer le thread_id.
    """
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": SETTINGS.max_autonomous_iterations * 2,
    }
    payload = {"messages": [HumanMessage(content=user_message)]}

    rendered_tool_calls: set[str] = set()
    rendered_tool_results: set[str] = set()
    last_state: dict[str, Any] = {}
    final_placeholder = container.empty()
    tools_box = container.container()

    try:
        for state in graph.stream(payload, config=config, stream_mode="values"):
            last_state = state
            messages = state.get("messages", []) if isinstance(state, dict) else []
            for msg in messages:
                # Tool calls (à afficher dès qu'ils apparaissent)
                if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                    for tc in msg.tool_calls:
                        tc_id = tc.get("id", "") or f"{tc.get('name', '')}-{id(tc)}"
                        if tc_id in rendered_tool_calls:
                            continue
                        rendered_tool_calls.add(tc_id)
                        tools_box.markdown(
                            f"<div class='tool-call'>🔧 <b>{tc['name']}</b>"
                            f"({_format_tool_args(tc.get('args', {}))})</div>",
                            unsafe_allow_html=True,
                        )
                # Tool results
                elif isinstance(msg, ToolMessage):
                    tc_id = getattr(msg, "tool_call_id", "") or str(id(msg))
                    if tc_id in rendered_tool_results:
                        continue
                    rendered_tool_results.add(tc_id)
                    text = str(msg.content)
                    preview = text[:600] + ("…" if len(text) > 600 else "")
                    tools_box.markdown(
                        f"<div class='tool-result'>↳ {preview}</div>",
                        unsafe_allow_html=True,
                    )
    except Exception as exc:
        if _is_invalid_history_error(exc):
            container.warning(
                "⚠️ État de conversation incohérent détecté (probablement un crash "
                "lors du tour précédent). Le thread va être réinitialisé — "
                "renvoie ton message."
            )
            return "", False
        container.error(f"❌ Erreur orchestrateur : {type(exc).__name__}: {exc}")
        return f"ERROR::{exc}", True

    # Récupère le dernier AIMessage texte (réponse finale)
    final_text = ""
    messages = last_state.get("messages", []) if isinstance(last_state, dict) else []
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
            final_text = msg.content if isinstance(msg.content, str) else str(msg.content)
            break

    if final_text:
        final_placeholder.markdown(final_text)
    elif not rendered_tool_calls:
        final_placeholder.info("(L'orchestrateur n'a pas produit de réponse texte.)")

    return final_text, True


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
            "⚙️ Config",
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
    st.caption("📊 [Coûts réels sur OpenRouter](https://openrouter.ai/activity)")
    st.caption("_Pour modifier : onglet ⚙️ Config_")

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
        if st.button("🔄 Nouveau chat", help="Reset complet : nouveau thread, historique vidé"):
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

        # Run
        with st.chat_message("assistant"), st.spinner("L'orchestrateur réfléchit…"):
            graph = _build_graph()
            container = st.container()
            response, ok = _run_orchestrator(
                graph=graph,
                user_message=user_input,
                thread_id=st.session_state.chat_thread_id,
                container=container,
            )
            # Auto-recovery : état corrompu → on regénère le thread, on retente UNE fois
            if not ok:
                st.session_state.chat_thread_id = f"chat-{uuid.uuid4().hex[:8]}"
                _build_graph.clear()
                container.info(
                    f"↻ Nouveau thread : `{st.session_state.chat_thread_id}` — retry…"
                )
                graph = _build_graph()
                retry_container = st.container()
                response, ok = _run_orchestrator(
                    graph=graph,
                    user_message=user_input,
                    thread_id=st.session_state.chat_thread_id,
                    container=retry_container,
                )
        st.session_state.chat_history.append(
            {"role": "assistant", "content": response or "(pas de réponse)"}
        )


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
            except Exception:
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
        cols = ["ts", "agent", "phase", "action", "tool", "output_summary", "tokens"]
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
    c1, c2, c3 = st.columns(3)
    c1.metric("Tokens IN (locaux)", f"{tokens_in:,}")
    c2.metric("Tokens OUT (locaux)", f"{tokens_out:,}")
    c3.markdown(
        "### Coût réel\n"
        "👉 [OpenRouter Activity](https://openrouter.ai/activity)\n\n"
        "_Les compteurs ci-contre sont indicatifs — la facturation réelle est sur OpenRouter._"
    )

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


# ═════════════════════════════════════════════════════════════════════
# Section : ⚙️ CONFIG
# ═════════════════════════════════════════════════════════════════════
elif section == "⚙️ Config":
    st.header("⚙️ Configuration runtime")
    st.caption(
        "Modifie quelques variables clés du `.env`. **Les changements ne prennent effet "
        "qu'après redémarrage de l'UI** (`Ctrl+C` puis `task ui`)."
    )

    if not _ENV_PATH.exists():
        st.error(f"Pas de `.env` trouvé à `{_ENV_PATH}`. Lance `task setup` d'abord.")
        st.stop()

    # Budget tokens
    st.subheader("Budget de tokens (par run)")
    current_budget = int(_read_env_var("ORCHESTRATOR_TOKEN_BUDGET") or SETTINGS.orchestrator_token_budget)
    new_budget = st.number_input(
        "ORCHESTRATOR_TOKEN_BUDGET",
        min_value=10_000,
        max_value=100_000_000,
        value=current_budget,
        step=100_000,
        help=(
            "Plafond cumulé tokens (in+out) pour 1 run autonome. "
            "Au-delà, l'orchestrateur s'arrête et demande une approbation. "
            "Indicatif coût DeepSeek V4 Pro : ~$0.65/M tokens (mix in+out)."
        ),
    )
    st.caption("📊 Coût réel suivi sur [OpenRouter Activity](https://openrouter.ai/activity)")
    if st.button("💾 Sauvegarder le budget", type="primary"):
        if _write_env_var("ORCHESTRATOR_TOKEN_BUDGET", str(int(new_budget))):
            st.success(f"`.env` mis à jour : ORCHESTRATOR_TOKEN_BUDGET={int(new_budget):,}")
            st.warning("⚠️ Redémarre l'UI pour que le changement soit pris en compte.")
        else:
            st.info("Pas de changement.")

    st.divider()

    # Reasoning effort
    st.subheader("Reasoning effort")
    current_reasoning = _read_env_var("OPENROUTER_REASONING_EFFORT") or "high"
    new_reasoning = st.selectbox(
        "OPENROUTER_REASONING_EFFORT",
        options=["minimal", "low", "medium", "high", "xhigh"],
        index=["minimal", "low", "medium", "high", "xhigh"].index(current_reasoning)
        if current_reasoning in {"minimal", "low", "medium", "high", "xhigh"}
        else 3,
        help=(
            "Niveau de reasoning DeepSeek V4 Pro. `xhigh` = max (lent et cher mais "
            "plus rigoureux pour orchestration). `low`/`minimal` = sous-tâches rapides."
        ),
    )
    if st.button("💾 Sauvegarder le reasoning"):
        if _write_env_var("OPENROUTER_REASONING_EFFORT", new_reasoning):
            st.success(f"`.env` mis à jour : OPENROUTER_REASONING_EFFORT={new_reasoning}")
            st.warning("⚠️ Redémarre l'UI pour appliquer.")
        else:
            st.info("Pas de changement.")

    st.divider()

    # Modèle principal
    st.subheader("Modèle OpenRouter")
    current_model = _read_env_var("OPENROUTER_MODEL") or SETTINGS.openrouter_model
    new_model = st.text_input(
        "OPENROUTER_MODEL",
        value=current_model,
        help="Slug OpenRouter exact. Voir https://openrouter.ai/models",
    )
    if st.button("💾 Sauvegarder le modèle"):
        if _write_env_var("OPENROUTER_MODEL", new_model.strip()):
            st.success(f"`.env` mis à jour : OPENROUTER_MODEL={new_model.strip()}")
            st.warning("⚠️ Redémarre l'UI pour appliquer.")
        else:
            st.info("Pas de changement.")

    st.divider()
    st.caption(
        f"Pour les autres variables (DB, Vault, RSS, GitHub, etc.), édite directement "
        f"`{_ENV_PATH}` avec ton éditeur préféré."
    )
