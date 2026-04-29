# `agents_core` — Flotte d'agents IA Stonks

> Le **cerveau autonome** de Stonks. Ce package contient l'orchestrateur principal et tous les sous-agents qui construisent et maintiennent l'application financière.

## 🧠 Architecture LangGraph

```
                  ┌──────────────────────────────┐
                  │    ORCHESTRATEUR PRINCIPAL   │
                  │  (DeepSeek V4 Pro, MoE 1.6T) │
                  │                              │
                  │  • Plan global               │
                  │  • Délégation                │
                  │  • Validation               │
                  │  • Code-review final         │
                  └──────┬───────────────────────┘
                         │
        ┌────────────────┼────────────────┬─────────────────┬──────────────┐
        ▼                ▼                ▼                 ▼              ▼
  ┌──────────┐    ┌──────────┐    ┌──────────────┐  ┌────────────┐  ┌──────────┐
  │ Backend  │    │ Frontend │    │   Sécurité   │  │   Data     │  │ Reviewer │
  │ Agent    │    │ Agent    │    │   Agent      │  │   Agent    │  │ Agent    │
  │          │    │          │    │              │  │            │  │          │
  │ FastAPI  │    │ Next.js  │    │ AES-256      │  │ Postgres   │  │ GitNexus │
  │ SQLAlch. │    │ Expo     │    │ JWT, Vault   │  │ Timescale  │  │ Tests    │
  │ Alembic  │    │ Tailwind │    │ Audit        │  │ Migrations │  │ Diff     │
  └────┬─────┘    └────┬─────┘    └──────┬───────┘  └─────┬──────┘  └─────┬────┘
       │               │                 │                │               │
       └───────────────┴────────┬────────┴────────────────┴───────────────┘
                                ▼
                  ┌──────────────────────────────┐
                  │      OUTILS NATIFS           │
                  │  • file_tools (read/write)   │
                  │  • shell_tools (exec)        │
                  │  • git_tools (commit/PR)     │
                  │  • gitnexus_tools (graph)    │
                  │  • agent_spawn               │
                  └──────────────────────────────┘
                                │
                                ▼
                       execution_log.txt
                       (JSONL, append-only)
```

## 📂 Structure

```
agents_core/
├── pyproject.toml
├── src/
│   ├── orchestrator/
│   │   ├── main.py            # Entry point (Typer CLI)
│   │   ├── config.py          # Settings via Pydantic
│   │   ├── llm.py             # Client OpenRouter
│   │   ├── state.py           # État LangGraph
│   │   ├── graph.py           # Définition du graphe
│   │   ├── system_prompt.py   # Prompt MAÎTRE de l'orchestrateur
│   │   └── cli.py             # Commandes auxiliaires
│   ├── agents/
│   │   ├── backend_agent.py
│   │   ├── frontend_agent.py
│   │   ├── security_agent.py
│   │   ├── data_agent.py
│   │   └── reviewer_agent.py
│   ├── tools/
│   │   ├── file_tools.py      # read/write/list/edit (sandboxed)
│   │   ├── shell_tools.py     # exec avec allowlist
│   │   ├── git_tools.py       # clone/branch/commit/push/PR
│   │   ├── gitnexus_tools.py  # impact/query/context
│   │   └── agent_spawn.py     # délégation à sous-agents
│   ├── logging/
│   │   └── execution_log.py   # Logger JSONL append-only
│   └── ui/
│       └── streamlit_app.py   # Dashboard temps réel
└── tests/
```

## 🚀 Quickstart

```bash
# Setup (depuis la racine du monorepo)
task setup:agents

# Lancer l'orchestrateur en mode interactif
task agents:dev

# Lancer en mode autonome avec un brief
task agents:run -- --brief docs/briefs/phase2.md

# UI monitoring
task ui    # http://localhost:8501

# Suivre les logs
task agents:logs
```

## 🔒 Garde-fous

- **Allowlist shell** : seules certaines commandes (`pnpm`, `pip`, `git`, `task`, `pytest`, `npx`, etc.) sont autorisées par défaut. Tout le reste demande confirmation.
- **Sandbox file** : les écritures sont restreintes à `/opt/stonks/`.
- **Budget tokens** : `ORCHESTRATOR_TOKEN_BUDGET` plafonne le coût par session.
- **Anti-boucle** : `MAX_AUTONOMOUS_ITERATIONS` arrête l'orchestrateur s'il s'enferme.
- **Confirmation humaine** : actions critiques (force push, suppression DB, install global) demandent un OK manuel.
- **Code-review obligatoire** : aucun merge sans passage du Reviewer (qui interroge GitNexus).

Voir `docs/AGENT_PROTOCOL.md` pour le protocole complet de communication avec l'orchestrateur.
