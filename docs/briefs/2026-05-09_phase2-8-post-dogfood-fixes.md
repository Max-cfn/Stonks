# Brief — Phase 2.8 : Corrections post-dogfood (logout, hydration, WS, UX)

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
- Branche de départ : `main` (HEAD actuel après merge PR #10 — fix hydratation).

## 🎯 Objectif global

Le fix d'hydratation React (Phase 2.7) est mergé et fonctionne — les pages sont
interactives, le simulateur auto-calcule, le login soumet en POST. Un test
dogfood complet a révélé 5 bugs restants à corriger avant que le site soit
pleinement utilisable.

**Mission : corriger les 5 bugs listés ci-dessous, par ordre de priorité.**

---

## 🌐 État de l'environnement runtime (snapshot pré-brief, vérifié)

| Service | URL/Port | Statut |
|---|---|---|
| Frontend Next.js | http://localhost:4173 | UP (login → dashboard fonctionnel) |
| Backend FastAPI | http://localhost:4174 | UP, /ready → `{"status":"ready","checks":{"database":"ok","vault":"ok"}}` |
| Postgres + TimescaleDB | localhost:5432 | container `stonks-postgres` healthy |
| Redis | localhost:6379 | container `stonks-redis` healthy |
| Vault dev | localhost:8200 | container `stonks-vault` healthy |

**Compte de test :**
- email : `hermes-test@stonks.fr`
- password : `Test1234!`

---

## 🐛 Problème 1 (🔴 HIGH) — Logout cassé : endpoint API manquant

### Symptôme

Le bouton "Déconnexion" dans `/fr/settings` ne déconnecte pas l'utilisateur.
Après clic, on reste sur le dashboard avec la session toujours active.
La navigation vers `/fr/login` redirige vers `/fr/dashboard` (preuve qu'on
est toujours authentifié).

### Cause racine

Le frontend appelle `POST /api/auth/logout` (fichier
`apps/web/src/lib/api/client.ts:155`), mais **le backend n'a PAS d'endpoint
`/auth/logout`**. Les routes existantes sont : `/auth/register`, `/auth/login`,
`/auth/refresh`, `/auth/me`.

Le 404 est silencieux car `apiLogout()` dans `client.ts` fait un try/catch
qui avale l'erreur et clear les tokens locaux quand même — mais sans clear
les cookies HttpOnly côté serveur, la session survit.

### Ce qu'il faut faire

1. **Backend** : Ajouter `POST /auth/logout` dans
   `packages/backend/src/stonks_backend/interfaces/api/routes/auth.py`
   - Lire `current_user` via `Depends(get_current_user)` (nécessite d'être auth)
   - Supprimer les cookies `access_token` et `refresh_token` (mettre `max_age=0`
     ou `expires=0`)
   - Retourner `{"status": "ok"}` (200)
   - Gérer le cas où le refresh token doit être invalidé côté serveur
     (optionnel — le simple clear cookie suffit si pas de blacklist)

2. **Frontend** : Vérifier que `apiLogout()` dans `client.ts` gère correctement
   la réponse 200 (ne plus avaler l'erreur silencieusement — logger si échec).

3. **Test** : Se connecter → cliquer Déconnexion → vérifier qu'on est redirigé
   vers `/fr/login` et que la navigation vers `/fr/dashboard` redirige vers
   login (pas de session résiduelle).

**Fichiers concernés :**
- `packages/backend/src/stonks_backend/interfaces/api/routes/auth.py` — ajout endpoint
- `apps/web/src/lib/api/client.ts:153-161` — amélioration gestion réponse

---

## 🐛 Problème 2 (🟡 MEDIUM) — Hydratation mismatch : style color-scheme sur `<html>`

### Symptôme

Dans la console navigateur sur chaque page :
```
A tree hydrated but some attributes of the server rendered HTML didn't match
the client properties.
  <html lang="en"
-   data-theme="light"
-   style={{color-scheme:"light"}}
  >
```

React hydrate (ne bail out pas) mais signale un mismatch entre le HTML SSR
et le rendu client sur `<html>`. Le fix Phase 2.7 a changé `attribute="class"`
en `attribute="data-theme"`, mais `next-themes` injecte aussi un style inline
`color-scheme` que le serveur ne produit pas.

### Cause racine

`next-themes` v0.4+ ajoute automatiquement `style="color-scheme: light/dark"`
sur `<html>` côté client via un script d'injection. Le SSR ne produit pas ce
style → mismatch.

Fichier : `apps/web/src/components/providers/Providers.tsx`

### Ce qu'il faut faire

1. Ajouter `enableColorScheme={false}` au `NextThemesProvider` pour désactiver
   l'injection automatique du style `color-scheme`.

2. Alternative si `enableColorScheme` n'est pas supporté par la version
   installée : forcer le thème à `"light"` uniquement (pas de `enableSystem`)
   OU passer `defaultTheme="light"` sans `enableSystem` et retirer le
   `attribute="data-theme"` pour revenir à `"class"` (moins propre).

3. **Vérifier** : recharger chaque page, console vide de warnings hydration.

**Fichiers concernés :**
- `apps/web/src/components/providers/Providers.tsx`

---

## 🐛 Problème 3 (🟡 MEDIUM) — WebSocket `/portfolio/stream` → 500

### Symptôme

Sur la page Portefeuille (`/fr/portfolio`) et Simulateur, la console affiche
en boucle :
```
WebSocket connection to 'ws://localhost:4174/portfolio/stream?token=...'
failed: Error during WebSocket handshake: Unexpected response code: 500
```

Le frontend tente de se connecter au stream temps réel mais le backend répond
500 — probablement une exception non catchée AVANT `websocket.accept()`.

### Cause racine probable

Dans `packages/backend/src/stonks_backend/interfaces/api/routes/portfolio.py:609-644` :

```python
@router.websocket("/stream")
async def portfolio_stream(websocket: WebSocket, token: str = Query(...)):
    # Auth via JWT — si exception ici, FastAPI envoie une erreur HTTP
    # au lieu d'un WebSocket close → 500
    try:
        jwt_service.decode_access_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    await websocket.accept()
    price_feed: PriceFeedPort = get_price_feed()  # ← peut crasher ici
```

Si `get_price_feed()` lève une exception (ex: service externe indisponible,
config manquante), l'erreur est propagée à FastAPI **après** `websocket.accept()`
mais avant le `try/except` principal → FastAPI tente d'envoyer une réponse HTTP
sur une connexion WebSocket → 500.

### Ce qu'il faut faire

1. **Wrapper try/except autour de `get_price_feed()`** AVANT le `while True`.
   Si le price feed n'est pas disponible, fermer proprement le websocket avec
   un code d'erreur (`4000`) plutôt que de crasher.

2. **Wrapper try/except autour du bloc d'auth JWT** pour éviter qu'une
   exception inattendue (pas juste un token invalide) ne remonte en 500.

3. **Vérifier que le price feed est correctement initialisé** — si c'est un
   mock ou un stub pour le dev, s'assurer qu'il ne crashe pas.

4. **Test** : ouvrir `/fr/portfolio` dans le navigateur, console = 0 erreur
   WebSocket (ou au pire un close propre 4000 au lieu de 500).

**Fichiers concernés :**
- `packages/backend/src/stonks_backend/interfaces/api/routes/portfolio.py:609-726`

---

## 🐛 Problème 4 (🔵 LOW) — Email lent dans Settings

### Symptôme

Première visite de `/fr/settings` après login : "Email —" (valeur absente).
Deuxième visite (ou refresh) : "Email hermes-test@stonks.fr" correct.

### Cause racine

Le `useAuth()` context fetch `/auth/me` de manière asynchrone au mount
(`AuthContext.tsx:42-71`). Le composant Settings render avant que la réponse
API n'arrive → `user` est null → affiche "—". Au deuxième render, `user`
est peuplé.

C'est une race condition classique : le provider ne bloque pas le render
initial sur le fetch utilisateur.

### Ce qu'il faut faire

1. **Vérifier que `isLoading` est bien utilisé** dans la page Settings.
   Si `isLoading` est true et `user` est null, afficher un skeleton/spinner
   au lieu du placeholder "—".

2. **Alternative** : faire un `Suspense` ou utiliser le `isLoading` du
   contexte Auth pour afficher un état de chargement.

3. **Test** : première visite Settings → spinner ou skeleton visible, puis
   l'email apparaît. Pas de "—" visible.

**Fichiers concernés :**
- `apps/web/src/app/[locale]/(app)/settings/page.tsx` (vérifier usage de `useAuth()`)
- `apps/web/src/lib/auth/AuthContext.tsx` (vérifier isLoading)

---

## 🐛 Problème 5 (🔵 LOW) — Pas de validation client sur le formulaire login

### Symptôme

Soumettre le formulaire login vide → aucun message d'erreur, pas de feedback
utilisateur. Le formulaire est soumis (POST au backend) qui retourne 401,
mais rien n'est affiché à l'utilisateur.

### Cause racine

`react-hook-form` est probablement utilisé sans validation rules ou sans
affichage des erreurs. Les champs n'ont pas de `required` ou de règles
`minLength`.

### Ce qu'il faut faire

1. **Ajouter des règles de validation** dans `react-hook-form` :
   - Email : `required: "L'email est requis"`, `pattern` email valide
   - Mot de passe : `required: "Le mot de passe est requis"`, `minLength: 8`

2. **Afficher les messages d'erreur** sous chaque champ (via `formState.errors`)

3. **Afficher l'erreur API** (401 "Invalid email or password") dans un
   message toast ou une alerte au-dessus du formulaire.

4. **Désactiver le bouton** pendant le chargement (éviter double submit).

5. **Test** : soumettre formulaire vide → 2 messages d'erreur visibles.
   Soumettre mauvais credentials → message "Email ou mot de passe invalide".

**Fichiers concernés :**
- `apps/web/src/app/[locale]/(auth)/login/page.tsx`

---

## 📋 Plan d'exécution (ordre IMPOSÉ)

- [ ] **ÉTAPE 0** — Branche dédiée `agent/fullstack/phase-2-8-post-dogfood-fixes`
- [ ] **ÉTAPE 1** — Fix logout (backend `POST /auth/logout` + frontend gestion)
- [ ] **ÉTAPE 2** — Fix hydration mismatch (`enableColorScheme={false}`)
- [ ] **ÉTAPE 3** — Fix WebSocket 500 (try/except autour de `get_price_feed()`)
- [ ] **ÉTAPE 4** — Fix Settings email lent (gérer `isLoading` dans la page)
- [ ] **ÉTAPE 5** — Fix validation login (react-hook-form rules + affichage erreurs)
- [ ] **ÉTAPE 6** — Tests manuels : login → dashboard → cashflow → portfolio → simulator → settings → logout → vérifier redirect login
- [ ] **ÉTAPE 7** — Vérification console : 0 erreur JS, 0 warning hydratation
- [ ] **ÉTAPE 8** — PR + boucle CI auto-fix (toute verte avant merge)

## ❌ Hors-périmètre (NE PAS toucher)

- **NE PAS** modifier la structure de la base de données
- **NE PAS** refactorer l'authentification (JWT, refresh token flow)
- **NE PAS** toucher aux services externes (GoCardless, CoinGecko)
- **NE PAS** modifier les CI workflows
- **NE PAS** modifier les seeds ou données de test existantes
- **NE PAS** modifier le thème (dark/light) au-delà du fix hydratation
- **NE PAS** ajouter de nouvelles features ou pages
- **NE PAS** toucher à `agents_core/`

## 📊 Mode d'exécution

```
mode: autonomous_long_run
budget_usd_max: 3
human_checkpoint_every_steps: 0
approval_timeout_minutes: 720
```

## ✅ Définition de "fait"

- [ ] Logout fonctionnel : clic Déconnexion → redirigé vers `/fr/login`, session tuée
- [ ] Console navigateur vide sur toutes les pages (0 erreur, 0 warning hydratation)
- [ ] WebSocket `/portfolio/stream` ne crashe plus en 500
- [ ] Settings affiche l'email au premier chargement (pas de "—")
- [ ] Formulaire login montre des messages d'erreur sur champs vides
- [ ] Formulaire login montre "Email ou mot de passe invalide" sur mauvais credentials
- [ ] Login → Dashboard → navigation toutes pages → Settings → Logout fonctionnel
- [ ] Tous les tests backend passent : `pnpm test` dans `packages/backend/`
- [ ] Tous les tests frontend passent : `pnpm test` dans `apps/web/`
- [ ] CI GitHub toute verte sur la PR
