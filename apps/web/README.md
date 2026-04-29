# `apps/web` — Frontend Next.js

> ⚠️ **Stub Phase 1.** Ce dossier sera initialisé par l'agent **Frontend** durant la Phase 2.

## Stack prévue

- Next.js 14+ (App Router)
- TypeScript
- Tailwind CSS + shadcn/ui (importé depuis `@stonks/ui`)
- TanStack Query pour la data fetching
- Zustand pour le state global
- TradingView Lightweight Charts pour les graphes financiers

## Initialisation par l'orchestrateur

Quand l'orchestrateur lance la phase Frontend, il :

1. Lance `pnpm dlx create-next-app@latest . --ts --tailwind --app --eslint --src-dir --import-alias "@/*"`
2. Configure les types partagés depuis `@stonks/shared-types`
3. Génère les pages : `/login`, `/dashboard`, `/portfolio`, `/settings`
4. Met en place les composants Cashflow, Portfolio, Alerts
5. Indexe le code via GitNexus (`gitnexus analyze`)

Voir `docs/AGENT_PROTOCOL.md` pour le briefing exact à passer à l'orchestrateur.
