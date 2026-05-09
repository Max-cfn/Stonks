# Brief — Phase 2.7 : Fixer l'hydratation React cassée (site inutilisable)

## ⚙️ Contexte d'exécution

- Auto-approve: `STONKS_AUTOAPPROVE_LEVEL=moderate` → tes commits, push
  `agent/*`, `gh pr create`, `alembic upgrade`, lecture/écriture sandbox
  `/opt/stonks/`, appels LLM ≤ $5 sont **auto-approuvés sans bloquer**.
- Hard-blocks gardent leur veto absolu : jamais de force push main, drop DB,
  rm -rf hors stonks, `git reset --hard` sur main, etc.
- LLM : DeepSeek V4 Pro via OpenRouter, provider DeepSeek officiel uniquement.
- **Boucle CI auto-fix obligatoire** sur la PR finale : tu utilises
  `gh_pr_status`, `gh_pr_failed_logs`, `gh_wait_for_ci` jusqu'à toute verte
  avant de demander le merge.
- Branche de départ : `main` (HEAD actuel après merge PR #9).

## 🎯 Objectif global

L'audit UX du 2026-05-08 a révélé un bug critique : **l'hydratation React est
cassée sur tout le frontend**. Le SSR rend le HTML correctement (titres,
sidebar, formulaires visibles), mais React ne prend **jamais** le relais côté
client. Résultat :

- Formulaire login → soumission ignorée (GET au lieu de POST intercepté)
- Dashboard → "Loading" infini (les hooks `useQuery` / `useEffect` ne s'exécutent pas)
- Simulateur → bouton "Calculer" sans effet, `useEffect` auto-calc jamais déclenché
- Settings → email affiché "—" au lieu de la valeur réelle
- Trésorerie → "Loading" infini
- Tous les `onClick`, `onSubmit`, `useState`, `useEffect` sont morts

Seule la **navigation** fonctionne (via `<Link>`, géré nativement par Next.js).

**Mission : diagnostiquer et corriger la cause racine de l'échec d'hydratation,
puis vérifier que toutes les pages interactives fonctionnent.** 

## 🌐 État de l'environnement runtime (snapshot pré-brief, vérifié)

| Service | URL/Port | Statut |
|---|---|---|
| Frontend Next.js | http://localhost:4173 | UP (PID 663129, Next 15.4.11) |
| Backend FastAPI | http://localhost:4174 | UP, /ready → 200 |
| Postgres + TimescaleDB | localhost:5432 | container `stonks-postgres` healthy |
| Redis | localhost:6379 | container `stonks-redis` healthy |
| Vault dev | localhost:8200 | container `stonks-vault` healthy |

**Compte de test :**
- email : `a@a.com`
- password : `123456789`

## 🐛 Problème — Hydratation React silencieusement cassée

### Symptômes observés (navigateur headless, 2026-05-08)

1. **Login** (`/fr/login`) : les champs email/mot de passe sont visibles, mais
   cliquer sur "Connexion" soumet le formulaire en GET natif HTML (les valeurs
   apparaissent dans l'URL : `?email=...&password=...`). `react-hook-form`
   n'intercepte jamais le `submit`.

2. **Dashboard** (`/fr/dashboard`) : le `useDashboardData()` hook (React Query)
   reste bloqué en `isLoading: true`. Aucun skeleton, aucun empty state — juste
   le titre. L'API backend répond pourtant (testé en curl).

3. **Simulateur** (`/fr/portfolio/simulator`) : le `useEffect` qui doit
   auto-calculer au montage (`useEffect(() => { if (!result) setResult(...) }, [result])`)
   ne se déclenche jamais. Les résultats restent "—". Le bouton "Calculer"
   ne fait rien.

4. **Settings** (`/fr/settings`) : l'email utilisateur affiche "—" au lieu de
   la valeur du `useAuth()` context.

5. **Trésorerie** (`/fr/cashflow`) : "Loading" perpétuel comme le dashboard.

6. **Console browser** : **aucune erreur JavaScript**. Des warnings 404 sur des
   ressources statiques (possiblement des icônes ou fonts) mais rien qui
   indique un crash React. C'est un échec **silencieux**.

### Ce qui marche

- La **navigation** entre pages (les `<Link>` Next.js)
- Le **rendu serveur** (SSR) — le HTML arrive complet avec titres, sidebar,
  formulaires
- L'**API backend** — curl direct vers `/auth/login`, `/auth/me`, etc.
  fonctionne parfaitement
- Le **proxy Next.js** — `/api/auth/login` proxie correctement vers le
  backend (`:4174`)

### Hypothèses à investiguer (par ordre de probabilité)

1. **Erreur d'hydratation silencieuse** : le HTML serveur et le rendu client
   diffèrent (ex: `Date.now()` dans le JSX, `typeof window` dans le render,
   balises HTML mal fermées). React abandonne l'hydratation sans erreur
   visible en production/dev.

2. **Module ESM/CJS mismatch** : un package importé (shadcn/ui, recharts,
   react-hook-form, etc.) a un problème de résolution de module qui empêche
   le bundle client de s'exécuter.

3. **Configuration Next.js** : `next.config.ts` a un `basePath`, `assetPrefix`,
   ou des headers CSP qui cassent le chargement des chunks JS.

4. **Turbopack vs Webpack** : le process Next tourne peut-être avec Turbopack
   (`next dev --turbo`) qui a un bug d'hydratation connu sur certaines
   versions.

5. **`useSearchParams` ou `usePathname` dans un layout non wrappé** : peut
   provoquer un bailout d'hydratation silencieux dans Next.js App Router.

## 📋 Plan d'exécution (ordre IMPOSÉ)

### ÉTAPE 0 — Branche dédiée (2 min)

- [ ] `git_status` propre, sur main
- [ ] `git checkout main && git pull origin main`
- [ ] `git checkout -b agent/fullstack/phase-2-7-fix-react-hydration`

### ÉTAPE 1 — Diagnostic de la cause racine (30 min)

Tu DOIS trouver la cause exacte avant de coder. Procédure :

⚠️ **RAPPEL SANDBOX** : Tu es confiné à `/opt/stonks/`. Pas de `ps aux`, pas de
`/proc/`, pas de `systemctl`. Tu ne peux PAS gérer les process. Utilise
uniquement `file_read`, `search_files`, `curl`, `grep -rn`, et les outils git.

1. **Vérifier si Turbopack est activé** :
   - `file_read` sur `apps/web/package.json` → regarde le script `"dev"`.
     S'il contient `--turbo`, c'est la cause probable.
   - `file_read` sur `apps/web/next.config.ts` → cherche `turbo: {}` ou
     `experimental.turbo`.
   - **Si `--turbo` est présent** : le fix est de l'enlever. Passe directement
     à l'ÉTAPE 2, item 1.

2. **Vérifier next.config.ts** :
   - `file_read` sur `apps/web/next.config.ts`
   - Cherche `basePath`, `assetPrefix`, `headers()`
   - Vérifie que `output` n'est pas `export`
   - Cherche toute config qui pourrait bloquer le JS client (CSP headers, etc.)

3. **Vérifier les composants layout racine** :
   - `file_read` sur `apps/web/src/app/layout.tsx`
   - `file_read` sur `apps/web/src/app/[locale]/layout.tsx`
   - Cherche `useSearchParams()`, `usePathname()` sans `<Suspense>` autour
   - Cherche `typeof window`, `Date.now()` dans le JSX (cause divergence SSR)

4. **Vérifier le middleware** :
   - `file_read` sur `apps/web/src/middleware.ts`
   - Cherche des redirections ou headers qui pourraient casser le chargement JS

5. **Isoler le problème (test décisif)** :
   - Crée UN fichier `apps/web/src/app/test/page.tsx` (pas un dossier !) avec :
     ```tsx
     "use client";
     import { useState } from "react";
     export default function TestPage() {
       const [count, setCount] = useState(0);
       return (
         <div style={{padding:50}}>
           <h1>Test Hydration</h1>
           <p>Count: {count}</p>
           <button onClick={() => setCount(c => c+1)}>+1</button>
         </div>
       );
     }
     ```
   - Teste avec `curl -s http://localhost:4173/test 2>&1 | grep -c "Count"` →
     doit retourner ≥1 (SSR ok).
   - **Important** : supprime ce fichier APRÈS le test pour éviter qu'un
     `file_read` futur sur le dossier `/test` ne crashe (IsADirectoryError).

6. **Check rapide des dépendances** :
   - `search_files` sur `apps/web/src` cherchant `"use client"` → confirme que
     les pages interactives utilisent bien la directive.
   - Vérifie que React 19 et Next.js 15 sont compatibles (regarde les versions
     dans `apps/web/package.json`).

### ÉTAPE 2 — Appliquer le fix (30 min)

Une fois la cause identifiée :

- [ ] Fixer la config Next.js si nécessaire (supprimer `--turbo`, corriger
      `headers()`, enlever `basePath`, etc.)
- [ ] Wrapper `useSearchParams` dans un `<Suspense>` si c'est la cause
- [ ] Si erreur d'hydratation : corriger le HTML serveur/client divergent
- [ ] Si module ESM/CJS : corriger l'import ou le `transpilePackages`
- [ ] Commit atomique : `fix(web): resolve React hydration failure — restore client-side interactivity`

### ÉTAPE 3 — Vérification sur toutes les pages (20 min)

Pour CHAQUE page, vérifier **depuis le navigateur** :

- [ ] `/fr/login` — le formulaire login fonctionne (POST via JS, pas GET)
- [ ] `/fr/register` — le formulaire inscription fonctionne
- [ ] `/fr/dashboard` — passe de "Loading" à l'empty state (pas de comptes
      connectés) ou aux KPIs si données existantes
- [ ] `/fr/cashflow` — passe de "Loading" à l'empty state
- [ ] `/fr/portfolio` — les données simulées s'affichent
- [ ] `/fr/portfolio/simulator` — les résultats s'affichent dès le chargement
      ET le bouton "Calculer" met à jour les résultats + graphique
- [ ] `/fr/settings` — l'email utilisateur s'affiche correctement
- [ ] La console browser est **propre** (0 erreur JS, 0 warning React)

### ÉTAPE 4 — Tests et build (10 min)

- [ ] `cd apps/web && pnpm build` — le build Next.js passe sans erreur
- [ ] `cd apps/web && pnpm test` — les tests existants passent toujours
- [ ] `cd apps/web && pnpm lint` — pas de nouveaux warnings

### ÉTAPE 5 — PR + CI (jusqu'à toute verte)

- [ ] `git push -u origin agent/fullstack/phase-2-7-fix-react-hydration`
- [ ] `gh pr create` avec titre : `fix(web): restore React hydration — all interactive pages functional`
- [ ] Description PR structurée :
  - "Problème" : récap des symptômes
  - "Cause racine" : ce que tu as trouvé à l'étape 1
  - "Fix" : ce que tu as changé
  - "Vérification" : checklist de l'étape 3
- [ ] Boucle CI auto-fix : `gh_wait_for_ci(N, 15)` puis `gh_pr_status(N)`
      → si rouge : `gh_pr_failed_logs(N)` → fix → push → re-attendre
- [ ] Max 5 itérations. Si même erreur 3× → escalade humain.
- [ ] CI verte → `request_human_approval` avec
      `reason="Phase 2.7 — React hydration fix ready to merge. All interactive pages verified."`

## ❌ Hors-périmètre (NE PAS toucher)

- ❌ Force push, rewrite history, merge direct sur main
- ❌ Modifier `agents_core/`, `system_prompt.py`, `Taskfile.yml`
- ❌ Ajouter de nouvelles features non listées dans ce brief
- ❌ Modifier le backend (`packages/backend/`)
- ❌ Modifier le package mobile (`apps/mobile/`)
- ❌ Changer les ports `:4173` (frontend) ou `:4174` (backend)
- ❌ Modifier les credentials, `.env`, ou variables d'environnement
- ❌ Mettre à jour les dépendances (sauf si c'est la cause racine identifiée)

## 📊 Mode d'exécution

```
mode: autonomous_long_run
budget_usd_max: 5
human_checkpoint_every_steps: 15
approval_timeout_minutes: 720
escalation_policy: minimal
```

## ✅ Définition de "fait"

✅ La cause racine de l'échec d'hydratation est identifiée et documentée.
✅ Toutes les pages listées à l'ÉTAPE 3 sont interactives (formulaires,
   boutons, effets React fonctionnent).
✅ La console browser ne montre **aucune** erreur JS ni warning React.
✅ `pnpm build` et `pnpm test` passent sans erreur.
✅ La PR a tous ses checks CI verts.
✅ L'humain peut, depuis http://192.168.1.56:4173 :
   - Login avec `a@a.com` / `123456789`
   - Voir le dashboard sans loading infini
   - Utiliser le simulateur avec des résultats qui s'affichent
   - Naviguer entre toutes les pages sans erreur console

❌ Tout autre état = brief non terminé.
