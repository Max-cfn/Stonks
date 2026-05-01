# Brief — Phase 2.4 : Frontend Web (Next.js dashboard)

## ⚙️ Contexte d'exécution en queue

Ce brief tourne dans une **queue séquentielle** lancée via `task queue:start`.
Configuration runtime active :

- **Auto-approve policy** : `STONKS_AUTOAPPROVE_LEVEL=moderate`
  → Tes commits, pushes sur `agent/*`, ouvertures de PR, migrations Alembic,
    et appels LLM ≤ $5 sont **auto-approuvés sans bloquer**. N'utilise
    `request_human_approval` que pour de **vraies** décisions humaines (choix
    de design ambigu, conflit, action destructive).
- **Hard-blocks** : force push main/master, drop database, rm -rf hors
  /opt/stonks, chmod 777, etc. → impossibles même en moderate.
- **Budget** : `budget_usd_max` ci-dessous est un plafond strict. Au-delà,
  l'orchestrateur s'arrête.
- **Branche de départ** : tu pars de **`main`** (la queue te checkout dessus
  au démarrage). Si une PR de phase précédente n'est pas encore mergée,
  vérifie son état avec `gh pr list --repo Max-cfn/Stonks --state open`.
  Si bloqué > 30 min : escalade via `request_human_approval`.

## 🔗 Dépendance sur phase précédente

**Pré-requis :** Phase 2.1 mergée + AU MOINS UNE feature business (Cashflow ou Portfolio) mergée sur main. Il faut quelque chose à afficher dans le dashboard.
- Vérifie avec `gh pr list --repo Max-cfn/Stonks --state merged --limit 10`
- Si seulement Phase 2.1 mergée : escalade humain pour décider quoi afficher
- L'API de la/les feature(s) business est consommée via `apps/web` proxy.



## Objectif
Construire le dashboard web : Next.js 15 App Router + Tailwind 4 + shadcn/ui, 
auth JWT plug sur Phase 2.1, écrans Dashboard / Cashflow / Portfolio / Settings, 
graphes interactifs (TradingView Lightweight Charts pour Portfolio, Recharts 
pour Cashflow). Aucune logique métier dupliquée — tout passe par le backend API.

## Contexte
- apps/web/ existe en stub (Next.js)
- Phase 2.1 mergée (auth dispo)
- Phase 2.2 ou 2.3 mergée (au moins une feature business à afficher)
- Stack figée :
  - next ~=15, react ~=19, typescript ~=5.6
  - tailwindcss ~=4, shadcn/ui (cli init)
  - @tanstack/react-query ~=5, axios ou fetch wrapper
  - lightweight-charts ~=4.2 pour Portfolio
  - recharts ~=2.13 pour Cashflow
  - zod pour validation, react-hook-form pour formulaires
  - vitest + @testing-library/react pour tests

## Critères d'acceptation

### Setup & layout
- [ ] Next.js 15 App Router, src/ folder, alias @/* configuré
- [ ] Tailwind 4 avec config tokens (couleurs primaires, font, radii)
- [ ] shadcn/ui initialisé, Button/Input/Card/Dialog/Toast importés
- [ ] Layout principal : sidebar navigation + topbar (user menu, theme toggle)
- [ ] Dark mode persistant (next-themes)
- [ ] i18n FR (default) + EN via next-intl ou équivalent

### Auth
- [ ] Page /login (email + password, validation zod)
- [ ] Page /register
- [ ] Route Handler /api/auth/* qui proxy le backend (cookies httpOnly pour le JWT)
- [ ] Middleware Next.js : redirect vers /login si pas authentifié sur les pages protégées
- [ ] Logout (clear cookies + redirect)
- [ ] Refresh token automatique via interceptor react-query

### Pages
- [ ] /dashboard : KPIs synthétiques (cash total, portfolio total, mouvement du mois)
- [ ] /cashflow : tableau transactions paginé, filtres (date/catégorie/compte), 
      graphes mensuels (Recharts)
- [ ] /portfolio : table holdings avec valuation live, graphe candle 
      (Lightweight Charts) sur ticker sélectionné, performance TWR/MWR
- [ ] /portfolio/simulator : formulaire compound growth + courbe résultat
- [ ] /settings : profil, banques connectées, alertes prix, déconnexion

### Realtime
- [ ] Hook usePortfolioStream qui maintient la WebSocket /portfolio/stream
- [ ] Indicator de connexion (vert/orange/rouge) en topbar
- [ ] Reconnexion auto avec backoff

### UX
- [ ] Loading skeletons sur toutes les data tables
- [ ] Empty states avec CTA contextuel (ex: "Connecte ta première banque")
- [ ] Error boundaries par route, toast pour les erreurs API
- [ ] Responsive desktop + tablet (≥ 768px), mobile pris en charge mais Phase 2.5 

### Tests
- [ ] Tests composants critiques (auth forms, table portfolio) : ≥ 70% coverage
- [ ] 1 test e2e Playwright : login → voir dashboard → logout

### CI / Git
- [ ] Branche agent/frontend/phase-2-4-web
- [ ] CI verte : eslint, tsc --noEmit, vitest, playwright (1 test)
- [ ] PR vers main, Reviewer Agent

## Hors-périmètre
- ❌ Mobile (Phase 2.5)
- ❌ Modifications backend sauf bug ou nouveaux endpoints clairement justifiés
- ❌ Server Components avec accès DB direct (toujours via API)

## Mode d'exécution
mode: autonomous_long_run
budget_usd_max: 20
human_checkpoint_every_steps: 25
approval_timeout_minutes: 720
escalation_policy: minimal

## Définition de "fait"
✅ pnpm --filter web dev lance, login fonctionne, les 4 pages affichent des 
   données réelles depuis le backend, CI verte, PR mergeable.