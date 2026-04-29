# Stonks — Plateforme de finance personnelle pilotée par flotte d'agents IA

> **Status :** 🚧 Bootstrap (Phase 1 en cours)
> **Stack :** Monorepo polyglotte (TypeScript + Python) — Next.js (web), Expo (mobile), FastAPI (backend), LangGraph (agents)
> **Modèle agent :** DeepSeek V4 Pro via OpenRouter (1M tokens contexte, MoE 1.6T)

## 🎯 Objectif

Stonks est :
1. **Une plateforme de finance personnelle** : agrégation bancaire (PSD2 / Enable Banking), portefeuille d'investissement, calcul TWR/MWR, alertes de marché, simulateur d'intérêts composés.
2. **Une flotte d'agents IA autonome** qui construit, maintient et fait évoluer cette plateforme, opérant 100% en headless via API LLM, sans intervention humaine sur les tâches d'implémentation courantes.

## 🏗️ Architecture du monorepo

```
stonks/
├── apps/
│   ├── web/                  # Next.js 14 (App Router)
│   └── mobile/               # Expo (React Native)
├── packages/
│   ├── backend/              # FastAPI + SQLAlchemy + Alembic
│   ├── shared-types/         # Types TS/Pydantic partagés (générés)
│   └── ui/                   # Design system (shadcn-style)
├── agents_core/              # Flotte d'agents (LangGraph)
│   ├── src/orchestrator/     # Orchestrateur principal (DeepSeek V4 Pro)
│   ├── src/agents/           # Sous-agents spécialisés
│   ├── src/tools/            # Outils natifs (file, shell, git, gitnexus)
│   └── src/ui/               # UI Streamlit de monitoring
├── infra/
│   ├── docker/               # Dockerfiles
│   └── compose/              # docker-compose.yml
├── scripts/                  # Bootstrap, helpers
├── docs/                     # Architecture, runbooks, agent protocol
└── execution_log.txt         # Journal chronologique de TOUTES les actions agent
```

## 🚀 Quickstart

```bash
# Prérequis : Node 20+, Python 3.12+, pnpm 10+, Task 3+, Docker, uv
task setup           # Installe toutes les deps (JS + Python)
task agents:dev      # Lance l'orchestrateur en mode interactif
task ui              # Lance l'UI de monitoring sur http://localhost:8501
task stack:up        # Lance tout via docker-compose
```

## 📚 Documentation

- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — Architecture détaillée
- [`docs/AGENT_PROTOCOL.md`](./docs/AGENT_PROTOCOL.md) — **Comment parler à l'orchestrateur**
- [`docs/RUNBOOK.md`](./docs/RUNBOOK.md) — Opérations courantes
- [`docs/SECURITY.md`](./docs/SECURITY.md) — Modèle de sécurité

## 📝 Licence

Privé — propriété de Max-cfn.
