# CLAUDE.md — Guide de l'agent Claude Code pour Stonks

Tu es Claude Code, en train d'aider à développer Stonks, une app personal finance + investment **multi-app** (web, mobile, backend, agents). Ce fichier te dit tout ce que tu dois savoir avant d'agir.

---

## 🎯 But du projet en 2 lignes

App de gestion patrimoniale qui combine **agrégation bancaire PSD2** (cashflow) et **suivi d'investissements multi-devises** (portfolio). Backend Python/FastAPI, frontend Next.js, mobile Expo, le tout dans un monorepo polyglotte.

---

## 🗂️ Structure du monorepo

```
/opt/stonks/
├── apps/
│   ├── web/              # Next.js 15 App Router + Tailwind 4 + shadcn/ui — :4173 en dev
│   └── mobile/           # Expo SDK 52 + React Native 0.76 + NativeWind
├── packages/
│   ├── backend/          # FastAPI 0.115 async + SQLAlchemy 2.0 + Alembic — :4174
│   ├── shared-types/     # Types TS partagés (placeholder)
│   └── ui/               # Composants UI partagés web/mobile (placeholder)
├── agents_core/          # Orchestrateur LangGraph + sous-agents (DeepSeek V4 Pro via OpenRouter)
├── infra/
│   ├── compose/          # docker-compose.yml (postgres, redis, vault, gitnexus)
│   ├── docker/           # Dockerfiles
│   └── systemd/          # Services systemd (stonks-ui, stonks-queue, stonks-brief@)
├── docs/
│   ├── AGENT_PROTOCOL.md # Comment parler à l'orchestrateur (chat / brief / queue)
│   ├── QUICKSTART.md     # Démarrage local
│   └── briefs/           # Briefs Markdown pour l'orchestrateur
├── scripts/              # bootstrap.sh, install-systemd.sh
├── .env                  # Secrets locaux (gitignoré, jamais commiter)
├── .env.example          # Template versionné
├── Taskfile.yml          # Toutes les commandes (`task -l` pour la liste)
└── pnpm-workspace.yaml   # Monorepo pnpm
```

**Architecture backend** : ports & adapters (hexagonal), strict.
- `domain/` : entités, value objects. Pure Python, zéro dep externe.
- `application/` : use cases, ports (interfaces).
- `infrastructure/` : adapters (SQLAlchemy, JWT, Vault, AES, Enable Banking, CoinGecko…).
- `interfaces/api/` : FastAPI routers, schemas Pydantic, dépendances.

**Ne casse jamais cette séparation.** Pas de SQLAlchemy dans `domain/`. Pas de FastAPI dans `application/`.

---

## 🛠️ Stack figée — ne pas changer sans demander

| Couche | Techno | Versions |
|---|---|---|
| Backend | FastAPI async | 0.115 |
| ORM | SQLAlchemy async + asyncpg | 2.0 / 0.30 |
| Migrations | Alembic | 1.14 |
| DB | Postgres + TimescaleDB | 16 / 2.x |
| Secrets | Vault dev | 1.18 |
| Auth | python-jose + passlib bcrypt | 3.3 / 1.7 |
| Crypto applicatif | cryptography (AES-256-GCM) | 43 |
| Frontend | Next.js + React | 15 / 19 |
| CSS | Tailwind | 4 |
| UI kit | shadcn/ui | latest |
| Mobile | Expo SDK / React Native | 52 / 0.76 |
| Mobile CSS | NativeWind | 4 |
| Tests Python | pytest + pytest-asyncio + pytest-cov | latest |
| Tests JS | vitest + @testing-library/react | latest |
| Lint Python | ruff (check + format) | 0.15+ |
| Type Python | mypy `--strict` | 1.x |
| Lint JS | eslint + prettier | latest |
| Package JS | pnpm workspaces | 10.33+ |
| Package Python | uv | 0.11+ |
| Orchestration tasks | go-task (Taskfile) | 3.50+ |

---

## 🚦 Services qui tournent (snapshot)

Vérifie toujours avec `ss -tlnp` ou `docker ps` avant de supposer un état.

| Service | URL | Statut typique |
|---|---|---|
| **Frontend Next.js** | http://localhost:4173 (LAN: http://192.168.1.69:4173) | dev server, lance avec `task web:dev` ou `pnpm --filter web dev` |
| **Backend FastAPI** | http://localhost:4174 — `/health`, `/docs` | `task backend:dev` ou `uvicorn stonks_backend.app:create_app --factory --port 4174` |
| **Postgres + TimescaleDB** | localhost:5432 (`stonks` / `stonks_dev` / `stonks_dev`) | container `stonks-postgres` |
| **Redis** | localhost:6379 | container `stonks-redis` |
| **Vault dev** | localhost:8200 (token `dev-token`) | container `stonks-vault` |
| **GitNexus** (knowledge graph) | localhost:4747 | container `stonks-gitnexus` |
| **Streamlit UI orchestrateur** | http://localhost:8501 | service systemd `stonks-ui` |

Pour les démarrer : `task stack:up`. Pour les arrêter : `task stack:down`.

---

## 🔧 Commandes essentielles (Taskfile)

```bash
task -l                      # liste toutes les tâches dispo

# Setup initial
task setup                   # installe deps Python + JS, init venv

# Dev quotidien
task backend:dev             # backend FastAPI hot-reload :4174
task web:dev                 # frontend Next.js :4173
task mobile:start            # Expo dev server

# Tests
task test                    # tout
task backend:test            # backend uniquement (pytest + cov)
task mobile:test             # mobile uniquement (jest)

# Lint / format
task lint                    # ruff + eslint
task format                  # ruff format + prettier
task backend:lint            # mypy --strict + ruff backend

# DB
task migrate                 # alembic upgrade head
task migrate:new -- "desc"   # nouvelle migration autogenerate
task migrate:status
task db:reset                # drop + recreate (DEV UNIQUEMENT)

# Stack Docker
task stack:up                # postgres + redis + vault + gitnexus + UI
task stack:down
task stack:logs

# Orchestrateur agents
task agents:dev              # REPL interactif
task agents:run -- --brief docs/briefs/X.md   # lance un brief
task agents:logs             # tail execution_log.txt

# Queue de briefs (séquentiel)
task queue:add -- docs/briefs/X.md
task queue:list
task queue:start             # systemd daemon
task queue:logs

# Approbations agent
task agents:status           # voir les req_id en attente
task agents:approve -- <req_id> "ok"
task agents:reject -- <req_id> "non parce que..."
```

---

## 📐 Règles de contribution — non-négociables

### Git

1. **Jamais de force push** sur `main`, `master`, `release/*`. Ne jamais réécrire l'historique partagé.
2. **Branches courtes**, format imposé : `agent/<role>/<phase-ou-slug>` (ex: `agent/backend/phase-2-1-foundations`, `agent/fullstack/phase-2-9-fix-banking`).
3. **Commits atomiques**, format **Conventional Commits** : `feat(scope):`, `fix(scope):`, `test(scope):`, `chore:`, `docs:`, `refactor:`, `ci:`, `style:`, `perf:`. Le scope est optionnel mais bienvenu (`feat(backend):`, `fix(web):`).
4. **Une feature = une PR**. Pas de PR fourre-tout.
5. **Jamais de merge direct sur `main`** : toujours via PR + review humain.
6. Si tu as fait > 5 commits sur la même branche sans push, push pour permettre le suivi distant.

### Code

1. **Lint + types passent toujours** avant commit : `task lint && task backend:lint`. Si rouge, tu fixes avant de committer (pas après).
2. **Tests obligatoires** sur :
   - Tout module dans `infrastructure/security/` (cible coverage ≥ 95%)
   - Tout calcul financier (TWR, MWR, AES, JWT)
   - Tout parsing PSD2 / banking
3. **Coverage seuil actuel** : 70% (pyproject) / 60% (backend-ci.yml). Phase 2.6+ doit remonter ça. Ne baisse jamais le seuil sans `request_human_approval`.
4. **Mypy `--strict`** sur backend. Si tu mets `# type: ignore`, tu mets un commentaire qui explique pourquoi.
5. **Jamais de secret en dur** dans le code, même un faux secret de test. Utilise `.env`, des fixtures, ou `monkeypatch`.
6. **Jamais de `print()` dans le code prod** — `structlog` partout côté backend.

### Sécurité

1. **Aucun secret dans une PR description**, dans un log d'exécution, dans un commit message. Filtre `OPENROUTER_API_KEY`, `JWT_SECRET`, `AES_KEY`, `ENABLE_BANKING_*`, `VAULT_TOKEN`, `DATABASE_URL`.
2. **AES_KEY** doit être 32 bytes en base64 (44 caractères avant `=` de padding). Génération : `python -c "import base64,os;print(base64.b64encode(os.urandom(32)).decode())"`. Validation au boot dans `infrastructure/security/aes_gcm.py`.
3. **Hard-blocks** (interdits même en mode autonome) :
   - `git push --force` sur main/master/release
   - `rm -rf` hors `/opt/stonks/`
   - `drop database`, `truncate`, `DELETE` sans `WHERE`
   - `chmod 777`, `chown root`
   - `vault token revoke`, `vault secrets disable`
   - `sudo rm/dd/mkfs/fdisk`
   - `docker rm -f`, `docker volume rm`, `docker system prune`
   - Modifier `/etc/passwd`, `/etc/sudoers`, `/etc/shadow`

### Auth

L'auth a déjà été cassée puis restaurée (Phase 2.6). **Ne la désactive jamais** "temporairement pour debug" — utilise un compte test (`a@a.com / 123456789`) à la place. Si tu touches à `get_current_user`, `middleware.ts`, `AuthContext.tsx`, `useAuth.ts`, ou `client.ts`, tu réfléchis à 2 fois et tu testes avec login/logout complet avant de pousser.

---

## 🌐 Configuration runtime importante

Lis `/opt/stonks/.env` pour les valeurs réelles (jamais affiché dans tes outputs).

| Variable | Sens | Valeur typique |
|---|---|---|
| `OPENROUTER_API_KEY` | LLM | `sk-or-v1-...` |
| `OPENROUTER_MODEL` | Modèle principal | `deepseek/deepseek-v4-pro` |
| `OPENROUTER_MODEL_LIGHT` | Sous-agents | `deepseek/deepseek-v4-flash` |
| `OPENROUTER_PROVIDER_ORDER` | Routing strict | `deepseek` (officiel uniquement) |
| `OPENROUTER_ALLOW_FALLBACKS` | Fallback à d'autres providers | `false` (volontaire — coût) |
| `STONKS_AUTOAPPROVE_LEVEL` | Auto-approbation des actions par les agents | `moderate` |
| `JWT_SECRET` | Auth | secret 32+ chars |
| `AES_KEY` | Chiffrement applicatif | base64 32 bytes |
| `DATABASE_URL` | Postgres | `postgresql+asyncpg://stonks:...` |
| `ENABLE_BANKING_*` | PSD2 sandbox | sandbox creds |

---

## 🤖 Comportement attendu en tant qu'agent

### Avant d'agir

1. **Lis ce CLAUDE.md** (tu es en train de le faire).
2. Regarde `git status` et `git branch --show-current`.
3. Si tu travailles sur une PR existante, regarde `gh pr view <num>` et `gh pr checks <num>` pour comprendre l'état CI.
4. Si tu vas modifier un fichier, **lis-le d'abord** entièrement (Read tool) — ne te fie pas à un nom de fichier ou un `grep`. Pas d'hallucination.
5. Pour les changements structurels (rename, suppression, refactor), interroge GitNexus avant : `curl http://localhost:4747/...` ou via les tools `gitnexus_query` / `gitnexus_impact` si tu y as accès. Sinon, fais un `grep -rn` complet pour voir tous les usages.

### Pendant l'action

1. **Une chose à la fois.** Pas de PR géante. Plutôt 4 PRs petites que 1 énorme.
2. **Tests locaux avant push.** Au minimum `task lint && task backend:test` (ou l'équivalent du package que tu touches).
3. **Branche dédiée** : `git checkout -b agent/<role>/<slug>` toujours, jamais sur `main`.
4. **Commit message clair** : un humain doit comprendre le diff sans lire le code.

### Après push

1. `gh pr create` avec une description structurée :
   - **Contexte** (pourquoi cette PR)
   - **Changements** (liste atomique)
   - **Comment tester en local** (commandes exactes)
   - **Points d'attention pour le reviewer** (s'il y en a)
2. **Boucle CI auto-fix obligatoire** :
   ```
   LOOP (max 8 itérations):
     gh pr checks <num> --watch
     SI all green → request_human_approval pour merge
     SINON: gh run view <run_id> --log-failed → analyse → fix → push → loop
   ```
3. Si même erreur 3× de suite → escalade humain (`request_human_approval` avec `reason="bloqué sur ..."`)
4. Si > 8 itérations → escalade humain.

### Quand tu ne sais pas

- **N'invente pas un fichier.** S'il n'existe pas, dis-le.
- **N'invente pas une API.** Vérifie dans la doc officielle ou les sources.
- **N'invente pas un comportement métier.** Demande confirmation à l'humain via `request_human_approval` si ce n'est pas couvert par le brief.
- Si un commit récent t'intrigue, lis-le : `git show <sha>`.
- Si tu hésites entre 2 designs : pose la question, ne tranche pas seul sur l'archi.

---

## 🧪 Workflows fréquents

### Bug fix simple

```bash
git checkout main && git pull
git checkout -b agent/<role>/<slug>
# 1. reproduis le bug en local
# 2. écris un test qui échoue
# 3. fix le code
# 4. test passe maintenant
task lint && task backend:test
git add -p && git commit -m "fix(<scope>): <verbe au présent — sujet>"
git push -u origin agent/<role>/<slug>
gh pr create --base main --title "..." --body "..."
# boucle CI
```

### Nouvelle feature

Lis le brief associé dans `docs/briefs/`. Si pas de brief → demande à l'humain d'en écrire un (`request_human_approval` reason: "feature sans brief, je propose ce plan : ...").

### Investigation d'un crash

1. `tail -200 execution_log.txt | grep -i error`
2. `journalctl -u stonks-ui -n 200` ou `journalctl -u stonks-queue -n 200`
3. Si frontend : ouvre la page, regarde la console DevTools, copie l'erreur
4. Si backend : `curl -v` l'endpoint problématique, lis le code de la route + les middlewares

### Restauration d'un état cassé

Toujours **créer une branche backup** avant tout `git revert` massif :
```bash
git checkout main && git pull
git branch backup/$(date +%Y-%m-%d)-pre-<raison>
git push origin backup/$(date +%Y-%m-%d)-pre-<raison>
# puis tu fais tes revert sur une autre branche
```

---

## 🚨 Signaux d'alerte (stop et demande à l'humain)

- Tu es sur le point de **modifier > 50 fichiers en un seul commit** → split.
- Tu es sur le point de **drop une migration**, **truncate une table**, **modifier `0001_*` ou `0002_*`** → demande.
- Tu es sur le point de **désactiver un test** ou un **check CI** → demande.
- Tu es sur le point de **baisser le seuil coverage** → demande.
- Tu es sur le point de **modifier le system prompt de l'orchestrateur** (`agents_core/src/stonks_core/orchestrator/system_prompt.py`) → demande.
- Tu es sur le point de **modifier `.env.example`** pour ajouter/retirer des variables → demande (juste pour valider la liste).
- Tu vois un message du type "Insufficient Balance" / 402 / 429 → c'est OpenRouter ou DeepSeek, pas notre code. Voir `docs/AGENT_PROTOCOL.md` section LLM.
- L'utilisateur te demande quelque chose qui semble enfreindre les hard-blocks → refuse poliment, propose une alternative safe.

---

## 📚 Pour aller plus loin

- `docs/AGENT_PROTOCOL.md` — comment l'orchestrateur tourne, comment lui parler, comment fonctionne la queue
- `docs/QUICKSTART.md` — démarrage local from scratch
- `docs/briefs/` — historique des briefs lancés (utile pour comprendre le pourquoi de tel ou tel commit)
- `agents_core/src/stonks_core/orchestrator/system_prompt.py` — règles que s'impose l'orchestrateur (cohérent avec ce CLAUDE.md, ne pas drift)

---

## 📝 Checklist mentale avant chaque action

- [ ] J'ai bien `git pull origin main` récemment ?
- [ ] Je suis sur une branche dédiée, pas main ?
- [ ] Je vais lire les fichiers que je vais modifier avant de les écrire ?
- [ ] Je vais lancer les tests locaux avant de push ?
- [ ] Je n'expose aucun secret dans mon output ?
- [ ] Mon commit message est en Conventional Commits ?
- [ ] Je sais quelle PR je vais ouvrir et son scope est < 500 lignes de diff ?

Si une case n'est pas cochée, ralentis.
