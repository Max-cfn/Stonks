# Brief — Phase 3.0 : Migration Enable Banking → API 2026 (JWT)

## ⚙️ Contexte d'exécution
- **Auto-approve policy** : standard (les étapes 0-3 sont auto, étape 4 PR avec CI loop)
- **Hard-blocks** : Aucun
- **Config LLM** : N/A (default orchestrator)
- **Branche de départ** : `main` (commit `1418c9b`)

## 🎯 Objectif global
L'adapteur `EnableBankingAdapter` est **complètement obsolète** : il utilise OAuth2 PKCE avec les URLs `auth.sandbox.enablebanking.com` et `api.sandbox.enablebanking.com` qui n'existent plus (NXDOMAIN). L'API Enable Banking 2026 utilise **JWT + certificat** pour l'auth, et un flow différent basé sur des sessions (`POST /auth` → redirect → callback avec `session_id`).

**Mission** : Réécrire l'adapteur pour l'API 2026 et adapter le flow de connexion bancaire.

## 🌐 État de l'environnement runtime (snapshot pré-brief)

| Service | URL | Port | Statut |
|---------|-----|------|--------|
| Frontend (Next.js) | http://localhost:4173 | 4173 | UP (Turbopack hot-reload) |
| Backend (FastAPI) | http://localhost:4174 | 4174 | UP (avec --reload) |
| Streamlit | http://localhost:8501 | 8501 | UP |

- **Clé privée** : `/opt/stonks/secrets/enablebanking.pem` (51 lignes, format PKCS#8 standard)
- **Application ID Enable Banking** : `36a2c3af-f771-4ae1-b56c-123e7f123d6a`
- **Aucun certificat x509** généré à partir de cette clé. Le certificat devra être uploadé manuellement dans le Control Panel Enable Banking (étape hors-périmètre de ce brief).

## 🐛 Problème — Détail complet

### API actuelle (OBSOLÈTE) vs API 2026

| Aspect | Code actuel (enable_banking.py) | API 2026 réelle |
|--------|-------------------------------|-----------------|
| Auth URL | `auth.sandbox.enablebanking.com` ❌ NXDOMAIN | `api.enablebanking.com` ✅ |
| API URL | `api.sandbox.enablebanking.com` ❌ NXDOMAIN | `api.enablebanking.com` ✅ |
| Auth method | OAuth2 PKCE (`/oauth/authorize`, `client_id`, `code_challenge`) | JWT RS256 signé avec clé privée |
| Start flow | `get_authorization_url()` → URL `/oauth/authorize?client_id=...` | `POST /auth` → JSON body → réponse `{url, authorization_id}` |
| Callback | `?code=...&state=...` → `exchange_code_for_token()` → token | `?session_id=...` → `GET /sessions/{id}` → accounts |
| Accounts | `GET /v2/accounts` | `GET /accounts/{id}/details` après avoir récupéré les IDs de `/sessions/{id}` |
| Transactions | `GET /v2/accounts/{id}/transactions` | `GET /accounts/{id}/transactions` (plus de `/v2`) |
| Balances | `GET /v2/balances` | `GET /accounts/{id}/balances` (par compte, pas global) |
| Token storage | Access token + refresh token dans Vault | JWT généré à la volée (pas de token stocké côté Enable Banking) |

### JWT Format (Enable Banking 2026)
```
Header: {"typ":"JWT","alg":"RS256","kid":"<application_id>"}
Body:   {"iss":"enablebanking.com","aud":"api.enablebanking.com","iat":<ts>,"exp":<ts+86400>}
```
- TTL max : 86400s (24h)
- Signé avec la clé privée RSA
- Envoyé en `Authorization: Bearer <JWT>` sur chaque requête

### Flow 2026 complet
1. `POST /auth` avec body JSON `{access, aspsp, state, redirect_url, language}`
2. Réponse : `{url: "...", authorization_id: "..."}`
3. Rediriger l'utilisateur vers `url` (page Enable Banking)
4. L'utilisateur s'authentifie auprès de sa banque
5. Enable Banking redirige vers notre `redirect_url?session_id=XXX`
6. `GET /sessions/XXX` → liste des `account_ids`
7. Pour chaque compte : `GET /accounts/{id}/details`, `GET /accounts/{id}/balances`, `GET /accounts/{id}/transactions`

## 📋 Plan d'exécution (ordre IMPOSÉ)

### ÉTAPE 0 — Branche dédiée
- [ ] Créer branche `agent/phase-3-0-enable-banking-jwt`
- [ ] Vérifier que main est à jour (`git pull origin main`)

### ÉTAPE 1 — Ajouter les settings JWT dans config.py
**Fichier** : `packages/backend/src/stonks_backend/infrastructure/config.py`

- [ ] Ajouter `enable_banking_key_path: str` → chemin vers la clé privée (défaut: `./secrets/enablebanking.pem`)
- [ ] Ajouter `enable_banking_application_id: str` → application ID Enable Banking (actuellement `ENABLEBANKING_APPLICATION_ID` dans `.env`)
- [ ] Renommer `enable_banking_client_id` → `enable_banking_application_id` pour refléter le nouveau flow (garder l'ancien alias `.env` pour backward compat)
- [ ] Lire `ENABLEBANKING_APPLICATION_ID` et `ENABLEBANKING_PRIVATE_KEY_PATH` depuis `.env`

### ÉTAPE 2 — Réécrire enable_banking.py (JWT + sessions)
**Fichier** : `packages/backend/src/stonks_backend/infrastructure/bank_connectors/enable_banking.py`

- [ ] **Supprimer** tout le code PKCE (`_generate_code_verifier`, `_compute_code_challenge`, `_token_request`, `_get_valid_access_token`, `exchange_code_for_token`, `_api_request_with_retry`)
- [ ] **Ajouter** `_generate_jwt()` → signe un JWT RS256 avec la clé privée. Utiliser la lib `PyJWT` (`jwt.encode()`). Le JWT header/kid = application_id.
- [ ] **Réécrire** `get_authorization_url()` → `POST /auth` avec body JSON `{access: {valid_until: ...}, aspsp: {name, country}, state, redirect_url, language: "fr"}`. Stocker `authorization_id` dans Vault. Retourner le `url` de la réponse.
- [ ] **Réécrire** `exchange_code_for_token()` → renommé en `handle_session_callback(user_id, session_id)`. Faire `GET /sessions/{session_id}` avec JWT. Stocker les `account_ids` dans Vault.
- [ ] **Réécrire** `_api_get()` → utiliser `Authorization: Bearer <JWT>` (généré à chaque appel)
- [ ] **Réécrire** `list_accounts()` → itérer sur les `account_ids` stockés, faire `GET /accounts/{id}/details` pour chacun
- [ ] **Réécrire** `fetch_transactions()` → utiliser `GET /accounts/{id}/transactions` (sans `/v2`, sans continuation_token — vérifier si la pagination existe en 2026)
- [ ] **Réécrire** `get_balances()` → itérer sur les comptes, `GET /accounts/{id}/balances` pour chacun
- [ ] **Garder** les parsers `_parse_transaction`, `_map_account_type`, `_parse_date` (ils restent valides)
- [ ] **Mettre à jour** les URLs : `https://api.enablebanking.com` pour tout (plus de sous-domaine sandbox)
- [ ] **Mettre à jour** `__init__` : accepter `key_path` et `application_id` au lieu de `client_id`/`client_secret`

### ÉTAPE 3 — Mettre à jour les routes et le use case
**Fichiers** :
- `packages/backend/src/stonks_backend/interfaces/api/routes/cashflow.py`
- `packages/backend/src/stonks_backend/application/use_cases/cashflow/connect_bank.py`
- `packages/backend/src/stonks_backend/application/ports/cashflow.py`

- [ ] **Route `/banks/connect`** — inchangée (retourne toujours l'URL d'auth)
- [ ] **Route `/banks/callback`** — changer le paramètre `code` → `session_id` (Query param). Appeler `handle_session_callback` au lieu de `handle_callback`
- [ ] **Port `BankConnectorPort`** — remplacer `exchange_code_for_token(user_id, code, redirect_uri)` par `handle_session_callback(user_id, session_id)`
- [ ] **Use case `ConnectBankAccount`** — adapter `handle_callback()` pour accepter `session_id` au lieu de `code`/`redirect_uri`

### ÉTAPE 4 — Mettre à jour les dépendances et .env
- [ ] Ajouter `PyJWT` dans `packages/backend/pyproject.toml` (déjà peut-être présent — vérifier)
- [ ] Mettre à jour `packages/backend/.env` :
  - Remplacer `STONKS_ENABLE_BANKING_CLIENT_ID` → `STONKS_ENABLE_BANKING_APPLICATION_ID`
  - Ajouter `STONKS_ENABLE_BANKING_KEY_PATH=./secrets/enablebanking.pem`
- [ ] Mettre à jour `get_bank_connector()` dans `cashflow.py` pour passer `key_path` et `application_id`

### ÉTAPE 5 — Tests et PR
- [ ] Vérifier que le backend compile sans erreur : `cd /opt/stonks/packages/backend && .venv/bin/python -c "from stonks_backend.infrastructure.bank_connectors.enable_banking import EnableBankingAdapter; print('OK')"`
- [ ] Tester `POST /cashflow/banks/connect` → doit retourner un `authorization_url` valide pointant vers `api.enablebanking.com`
- [ ] Push + créer PR
- [ ] Boucle CI : si tests fail → fix auto, repush, re-check

## ❌ Hors-périmètre (NE PAS toucher)
- **NE PAS** générer ou uploader le certificat x509 — c'est une étape manuelle pour l'utilisateur
- **NE PAS** modifier le frontend (Next.js)
- **NE PAS** toucher à `scraping_fallback.py`
- **NE PAS** modifier la config Vault
- **NE PAS** modifier le domain model (`Account`, `Transaction`, etc.)
- **NE PAS** créer de nouveaux endpoints API

## 📊 Mode d'exécution
```
mode: autonomous_long_run
budget_usd_max: 20
human_checkpoint_every_steps: 5
approval_timeout_minutes: 720
```

## ✅ Définition de "fait"
- [ ] `POST /cashflow/banks/connect` retourne une URL qui pointe vers `api.enablebanking.com` (ou `tilisy.enablebanking.com`)
- [ ] La route `/banks/callback` accepte `session_id` au lieu de `code`
- [ ] `from stonks_backend.infrastructure.bank_connectors.enable_banking import EnableBankingAdapter` importe sans erreur
- [ ] Tous les anciens appels OAuth PKCE (`/oauth/authorize`, `/oauth/token`, `code_verifier`, `code_challenge`) sont supprimés
- [ ] Les appels API utilisent `Authorization: Bearer <JWT>` signé avec la clé privée
- [ ] Les parsers de transactions/comptes existants sont préservés
- [ ] PR créée sur GitHub, prête à être mergée

## ⚠️ Note pour l'utilisateur (post-merge)
Après le merge, il faudra **manuellement** :
1. Générer un certificat x509 à partir de `enablebanking.pem` : `openssl req -new -x509 -key enablebanking.pem -out enablebanking.crt -days 365 -subj "/CN=Stonks"`
2. Uploader ce certificat dans le [Control Panel Enable Banking](https://enablebanking.com/control-panel)
3. Noter l'Application ID retourné après l'upload
4. Mettre à jour `STONKS_ENABLE_BANKING_APPLICATION_ID` dans `.env` avec cet ID
5. Tester le flow complet en vrai navigateur