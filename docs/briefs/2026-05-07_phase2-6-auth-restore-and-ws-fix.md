# Brief — Phase 2.6 : Restaurer l'auth + fixer le WebSocket + tester OAuth E2E

## ⚙️ Contexte d'exécution

- Auto-approve: `STONKS_AUTOAPPROVE_LEVEL=moderate` → tes commits, push
  `agent/*`, `gh pr create`, `alembic upgrade`, lecture/écriture sandbox
  `/opt/stonks/`, appels LLM ≤ $5 sont **auto-approuvés sans bloquer**.
- Hard-blocks gardent leur veto absolu : jamais de force push main, drop DB,
  rm -rf hors stonks, `git reset --hard` sur main, etc.
- LLM : DeepSeek V4 Pro via OpenRouter, provider DeepSeek officiel uniquement
  (vérifié UP au moment du lancement de ce brief).
- **Boucle CI auto-fix obligatoire** sur la PR finale : tu utilises
  `gh_pr_status`, `gh_pr_failed_logs`, `gh_wait_for_ci` jusqu'à toute verte
  avant de demander le merge.
- Branche de départ : `main` (HEAD actuel `0c721fe`).

## 🎯 Objectif global

L'humain rapporte que l'app frontend tourne (http://192.168.1.56:4173) mais :
1. Le WebSocket Portfolio spame des erreurs en console à chaque chargement
2. L'auth a été cassée par une série de "fix" qui ont désactivé tout
   l'authentification "en mode guest" → il faut **revert** ça
3. Les redirections OAuth Enable Banking n'ont jamais été testées E2E

**Mission : restaurer une auth fonctionnelle, fixer le WebSocket proprement,
puis tester en live le flow OAuth Enable Banking sandbox depuis le browser.**

## 🌐 État de l'environnement runtime (snapshot pré-brief, vérifié)

| Service | URL/Port | Statut |
|---|---|---|
| Frontend Next.js | http://192.168.1.56:4173 (LAN) / http://localhost:4173 | UP (PID 663129) |
| Backend FastAPI | http://localhost:4174 | UP, /health renvoie 200 |
| Postgres + TimescaleDB | localhost:5432 | container `stonks-postgres` healthy |
| Redis | localhost:6379 | container `stonks-redis` healthy |
| Vault dev | localhost:8200 | container `stonks-vault` healthy |
| GitNexus | localhost:4747 | container `stonks-gitnexus` UP |

**Compte de test fourni par l'humain (existe en DB) :**
- email : `a@a.com`
- password : `123456789`

**Credentials Enable Banking sandbox** : déjà configurés dans `/opt/stonks/.env`
sous les variables `ENABLE_BANKING_*`. **Filtre obligatoire** : ne JAMAIS
afficher leur valeur dans les logs, commits, descriptions de PR ou commentaires
GitHub. Si tu dois en parler, écris `<set>` ou `<masked>`.

## 🐛 Problème 1 — Auth désactivée par 6 commits cascadés (à revert)

Entre `4b2bc80` (7 mai 22:16) et `0c721fe` (HEAD, 7 mai 22:33), une série de
commits a progressivement neutralisé l'auth pour contourner des bugs au lieu
de les corriger. Liste chronologique :

```
4b2bc80  fix: desactiver toute authentification — mode guest
ee85711  fix: cle AES 32 bytes, cashflow None-safe, WebSocket dynamique
6635238  fix: cle AES exactement 32 bytes + guards cashflow restants
023a355  fix: get_current_user retourne None au lieu de 401
7a201ca  fix: auth dependency propre — retourne None sans casser la syntaxe
0c721fe  fix: ajouter guard None pour get_summary
```

Fichiers touchés à restaurer dans leur état pré-`4b2bc80` :
- `apps/web/src/middleware.ts`
- `apps/web/src/lib/auth/AuthContext.tsx`
- `apps/web/src/lib/auth/useAuth.ts`
- `apps/web/src/lib/api/client.ts`
- `packages/backend/src/stonks_backend/interfaces/api/dependencies/auth.py`
- `packages/backend/src/stonks_backend/interfaces/api/routes/cashflow.py`

⚠️ **Le commit `4795b5c` (du 7 mai 20:50, "corriger la boucle de redirection
sur la page login") est ANTÉRIEUR à la cascade et il est BON.** Tu ne dois
PAS le toucher. Le fix `isAuthPage` qu'il contient dans `client.ts` doit
survivre. Le revert ne doit défaire que les changements introduits par les
6 commits listés ci-dessus.

## 🐛 Problème 2 — Clé AES mal encodée

Pendant la cascade, la clé AES a été "fixée" plusieurs fois en l'écrivant
directement comme une chaîne de 32 caractères. **C'est faux.** AES-256-GCM
exige **32 bytes**, à fournir en **base64** (44 caractères + padding).

**Solution attendue** :
```bash
python -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"
```
Tu mets la valeur générée dans `/opt/stonks/.env` sur la variable AES
(probablement `STONKS_AES_KEY` ou `AES_KEY` — vérifie avec `grep AES .env.example`).
Tu mets aussi à jour `.env.example` avec un placeholder explicite et un
commentaire qui explique le format (pas la vraie valeur).

**Vérification** : le code de chiffrement (`infrastructure/security/aes_gcm.py`)
décode déjà la clé via `base64.b64decode()`. Si ce n'est pas le cas, tu le
corriges.

## 🐛 Problème 3 — WebSocket Portfolio spam infini (CRITIQUE)

**Symptôme console browser** sur http://192.168.1.56:4173 après login :
```
usePortfolioStream.ts:35 WebSocket connection to 'ws://localhost:4174/portfolio/stream' failed:
[répété ~25 fois en quelques secondes, jusqu'à freeze de la console]
```

**Diagnostic technique attendu** (à vérifier toi-même par `file_read`) :

1. `apps/web/src/lib/hooks/usePortfolioStream.ts` ligne 12 (état actuel
   après les 6 commits cascadés) :
   ```ts
   const WS_URL = `ws://${typeof window !== 'undefined' ? window.location.hostname : 'localhost'}:4174/portfolio/stream`
   ```
   → **construit l'URL sans `?token=...`**

2. `packages/backend/src/stonks_backend/interfaces/api/routes/portfolio.py`
   ligne ~611 :
   ```python
   @router.websocket("/stream")
   async def portfolio_stream(
       websocket: WebSocket,
       token: str = Query(..., description="JWT access token for authentication"),
   ):
   ```
   → **`token` est obligatoire** (`...` Ellipsis dans `Query`). FastAPI rejette
   la connexion AVANT `await websocket.accept()` → côté browser tu vois
   "WebSocket connection failed" sans détail.

3. Le hook a un backoff exponentiel + reconnect → spam infini parce que la
   condition d'arrêt est uniquement "manualReconnectRef" et "mountedRef".
   Pas de check "ai-je un token avant de tenter ?".

4. Bug bonus probable : l'URL utilise `window.location.hostname` ce qui
   donne `192.168.1.56` quand l'humain accède en LAN, mais le port `4174`
   peut ne pas être exposé sur cette IP — à vérifier avec
   `ss -tlnp | grep 4174` et tester `curl http://192.168.1.56:4174/health`
   depuis le serveur.

**Critères de fix (TOUS obligatoires) :**

- [ ] Le hook lit le JWT depuis le store d'auth (probablement
      `useAuth()` / `AuthContext` après le revert) et l'ajoute en query
      string : `ws://host:port/portfolio/stream?token=${encodeURIComponent(token)}`
- [ ] **Si pas de token, le hook NE TENTE PAS la connexion** : il retourne
      `status: "disconnected"` immédiatement et ne planifie aucun reconnect.
      C'est le critère qui élimine le spam.
- [ ] Si le WS reçoit un close code 4001 (Invalid or expired token), le
      hook arrête les reconnexions et émet `status: "disconnected"`
- [ ] L'URL gère le cas LAN vs localhost via une variable
      `NEXT_PUBLIC_WS_URL` (lue depuis `process.env.NEXT_PUBLIC_WS_URL`)
      avec fallback dynamique sur `window.location.host` SANS hardcoder
      `:4174`. Tu mets à jour `.env.example` et `apps/web/.env.local` si
      pertinent.
- [ ] Tu importes le hook dans une page Portfolio uniquement, pas dans le
      layout global — le hook ne doit s'instancier que quand l'utilisateur
      est sur la page Portfolio
- [ ] La console browser doit être **propre après login** (zéro WS error,
      zéro reconnect spam, zéro 401)
- [ ] Test E2E manuel : `wscat` ou `curl --include --no-buffer
      --header "Connection: Upgrade" --header "Upgrade: websocket"
      --header "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ=="
      --header "Sec-WebSocket-Version: 13"
      "ws://localhost:4174/portfolio/stream?token=$VALID_JWT"` doit
      répondre `HTTP/1.1 101 Switching Protocols`

## 🐛 Problème 4 — Vérifier les redirections E2E

Une fois l'auth restaurée et le WS fixé, vérifie chacune des redirections
suivantes via curl + un browser headless (Playwright si dispo dans
`apps/web/`, sinon test manuel décrit dans la PR description) :

- [ ] `POST /auth/login` avec `a@a.com` / `123456789` → 200 + JWT valide
- [ ] `GET /dashboard` (Next.js) sans cookie → 302 redirect `/login`
- [ ] `GET /dashboard` avec cookie session → 200 page rendue
- [ ] `GET /cashflow` authentifié → 200, page liste les comptes
- [ ] `GET /cashflow/banks/connect` (à créer si absent) → 200 ou 302 vers
      l'URL OAuth Enable Banking sandbox
- [ ] `GET /cashflow/banks/callback?code=...&state=...` (depuis le retour
      Enable Banking) → traite le code, échange contre token, sauve
      l'account, redirige vers `/cashflow` avec un toast/flash de succès
- [ ] Logout → clear cookies + redirect `/login`

## 🏦 Problème 5 — Tester le flow OAuth Enable Banking E2E

L'humain a configuré ses credentials sandbox Enable Banking. Tu dois
vérifier que le flow complet fonctionne :

1. **Backend** :
   - [ ] `POST /cashflow/banks/connect` retourne une URL OAuth Enable
         Banking valide (en sandbox) : domaine `auth.tilisy.com` ou
         équivalent sandbox
   - [ ] L'URL contient bien `client_id`, `redirect_uri`, `scope`,
         `state`, `code_challenge` (PKCE)
   - [ ] Le `state` est stocké côté serveur (Redis ou table DB) pour la
         vérification CSRF au callback
   - [ ] Le `redirect_uri` pointe vers `https://192.168.1.56:4173/cashflow/banks/callback`
         ou `http://localhost:4173/...` selon ce qui est enregistré côté
         Enable Banking sandbox (NE LE CHANGE PAS sans ask)

2. **Tests d'intégration** :
   - [ ] Crée un fichier `packages/backend/tests/integration/test_enable_banking_oauth.py`
   - [ ] Skip si `ENABLE_BANKING_CLIENT_ID` n'est pas défini en env (pour
         que la CI passe sans creds)
   - [ ] Si dispo : test full flow : connect → mock callback → verify
         token sauvé en Vault → list_accounts retourne au moins 1 compte
         sandbox

3. **Frontend — page "Connecter ma banque"** :
   - [ ] `apps/web/src/app/cashflow/banks/connect/page.tsx` (ou route
         équivalente) : bouton "Connecter ma banque" qui appelle
         `POST /cashflow/banks/connect`, récupère l'URL, redirige
         `window.location.href = url`
   - [ ] `apps/web/src/app/cashflow/banks/callback/page.tsx` : récupère
         `code` et `state` de la query string, appelle
         `GET /cashflow/banks/callback?code=...&state=...`, affiche un
         spinner pendant l'échange, puis redirige vers `/cashflow` avec
         un toast de succès (ou erreur)
   - [ ] Gestion des erreurs : code expiré, state invalide, refus
         utilisateur (`?error=access_denied`)

## 📋 Plan d'exécution (ordre IMPOSÉ)

### ÉTAPE 0 — Branche dédiée AVANT tout revert (3 min)

⚠️ Important : tu crées la branche AVANT d'undo l'auth, parce que l'humain
veut conserver une trace propre du "before" même si on revert.

- [ ] `git_status` propre, sur main
- [ ] `git checkout main && git pull origin main`
- [ ] `git checkout -b agent/fullstack/phase-2-6-auth-restore-ws-fix`
- [ ] Log dans `execution_log.txt` : `phase=branch_created sha=$(HEAD)`

### ÉTAPE 1 — Audit live + login fonctionnel SANS le revert (10 min)

Avant de toucher quoi que ce soit, prouve que tu peux te connecter au
backend en l'état actuel (auth désactivée). C'est ton baseline.

- [ ] `curl http://localhost:4174/health` → 200
- [ ] `curl -s -X POST http://localhost:4174/auth/login -H "Content-Type: application/json" -d '{"email":"a@a.com","password":"123456789"}'`
      → soit 200 + JWT, soit comportement guest (note ce que tu reçois)
- [ ] `curl -s -o /dev/null -w "%{http_code}" http://localhost:4173/` → 200/307
- [ ] Note dans le log : phase=audit_baseline status=ok

### ÉTAPE 2 — Revert des 6 commits cascadés (15 min)

Ordre **inversé** (du plus récent au plus ancien) pour limiter les conflits :

- [ ] `git revert --no-edit 0c721fe`
- [ ] `git revert --no-edit 7a201ca`
- [ ] `git revert --no-edit 023a355`
- [ ] `git revert --no-edit 6635238`
- [ ] `git revert --no-edit ee85711`
- [ ] `git revert --no-edit 4b2bc80`

Après chaque revert, si conflit : tu résous proprement (jamais de
`--abort`). Tu vérifies que `4795b5c` n'est pas dans la liste de fichiers
touchés (le fix isAuthPage doit survivre).

Si conflits sur `usePortfolioStream.ts` : **garde la version pré-cascade**
(celle d'avant `ee85711`) car tu vas la modifier toi-même à l'étape 4.

### ÉTAPE 3 — Régénérer la clé AES proprement (5 min)

- [ ] `grep -E "AES" /opt/stonks/.env.example` pour identifier le nom
      exact de la variable
- [ ] Générer la clé : `python3 -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"`
- [ ] Mettre à jour `/opt/stonks/.env` avec la nouvelle valeur
- [ ] Mettre à jour `.env.example` avec un placeholder explicite :
      `STONKS_AES_KEY=<base64 of 32 random bytes — generate with: python -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())">`
- [ ] Vérifier dans `infrastructure/security/aes_gcm.py` que la clé est
      lue via `base64.b64decode(env_value)` et qu'un assert force la
      longueur 32 bytes après decode (sinon ajouter)
- [ ] Lancer les tests AES : `cd packages/backend && .venv/bin/pytest tests/unit/test_aes_gcm.py -v`

### ÉTAPE 4 — Fix WebSocket usePortfolioStream.ts (30 min)

Suis les **critères de fix du Problème 3** ci-dessus. Vérifie chaque
hypothèse avec `file_read` AVANT de coder :

- [ ] `file_read` sur `usePortfolioStream.ts` (intégral)
- [ ] `file_read` sur `portfolio.py` route, sections WebSocket (lignes
      605-700)
- [ ] `file_read` sur le store d'auth front (`apps/web/src/lib/auth/AuthContext.tsx`
      après revert)
- [ ] `gitnexus_query "WebSocket portfolio stream"` pour voir tous les
      fichiers liés
- [ ] Code le fix
- [ ] Test local : lance `wscat -c "ws://localhost:4174/portfolio/stream?token=$JWT"`
      où `$JWT` est obtenu via login en curl
- [ ] Si Playwright dispo dans `apps/web/`, ajoute un test E2E qui :
      login → navigue vers Portfolio → vérifie qu'il n'y a aucune
      WebSocket error en console pendant 5s
- [ ] Commit atomique : `fix(web): WebSocket Portfolio — pass JWT in query, no spam reconnect, env-aware URL`

### ÉTAPE 5 — Vérifier les redirections (Problème 4) (20 min)

Suis la liste du Problème 4. Pour chaque ligne :
- Si ça marche déjà → coche-la et passe à la suivante
- Si ça ne marche pas → tu fixes, commit atomique, coche

### ÉTAPE 6 — Flow OAuth Enable Banking E2E (60 min)

Suis le Problème 5 (Backend / Tests / Frontend). Crée les fichiers
manquants si nécessaire. Si une partie est déjà implémentée par l'agent
de Phase 2.2, vérifie qu'elle marche et complète seulement ce qui
manque.

### ÉTAPE 7 — PR + boucle CI auto-fix (jusqu'à toute verte)

- [ ] `git push -u origin agent/fullstack/phase-2-6-auth-restore-ws-fix`
- [ ] `gh pr create` avec un titre clair :
      `fix(stonks): restore auth + WebSocket Portfolio + Enable Banking OAuth E2E`
- [ ] Description PR structurée :
      - "What's wrong" (recap des 4 problèmes)
      - "What's fixed" (par problème, avec commits associés)
      - "How to test manually" (étapes browser pour l'humain)
      - Section "WebSocket fix details" avec snippet `ws://host:port/portfolio/stream?token=…`
      - **Pas de credentials** dans la description
- [ ] Boucle CI auto-fix : `gh_wait_for_ci(N, 15)` puis `gh_pr_status(N)`
      puis `gh_pr_failed_logs(N)` si rouge → fix → push → re-attendre
- [ ] Max 8 itérations. Si même erreur 3× → escalade humain.
- [ ] À la fin (CI verte) : `request_human_approval` avec
      `reason="Phase 2.6 ready to merge — all CI green, manual E2E browser test recommended"`
      et `payload={"pr_url":"...","ci_status":"all_green","manual_steps":"..."}`

## ❌ Hors-périmètre (NE PAS toucher)

- ❌ Force push, rewrite history, merge direct sur main
- ❌ Modifier `agents_core/`, `system_prompt.py`, `Taskfile.yml` sauf
      pour ajouter UN script de test E2E si vraiment justifié
- ❌ Ajouter de nouvelles features non listées dans ce brief
- ❌ Démarrer Phase 2.7 ou autre
- ❌ Changer le port `:4174` du backend ou `:4173` du frontend
- ❌ Modifier le `redirect_uri` enregistré chez Enable Banking sans
      `request_human_approval`

## 📊 Mode d'exécution

```
mode: autonomous_long_run
budget_usd_max: 12
human_checkpoint_every_steps: 20
approval_timeout_minutes: 720
escalation_policy: minimal
```

## ✅ Définition de "fait"

✅ La PR a tous ses checks CI verts.
✅ L'humain peut, depuis http://192.168.1.56:4173 :
   - Login avec `a@a.com` / `123456789`
   - Voir la page Portfolio sans **aucune** erreur WebSocket en console
   - Cliquer "Connecter ma banque" → être redirigé vers Enable Banking
     sandbox → revenir avec un compte ajouté
✅ `request_human_approval` a été émis avec le payload spécifié à l'étape 7
✅ `phase=completion status=ok pr_url=...` loggé dans `execution_log.txt`

❌ Tout autre état = brief non terminé. Continue ou escalade humain via
   `request_human_approval` avec `reason="Phase 2.6 — bloqué sur ..."`.
