# Brief — Phase 2.1 : Fondations Backend & Sécurité

## Objectif
Mettre en place les fondations production-ready du backend Stonks : FastAPI 
0.115+ async, Postgres 16 + TimescaleDB 2.x, SQLAlchemy 2.0 async, Alembic, 
JWT + bcrypt, AES-256-GCM pour chiffrement applicatif, Vault pour les secrets, 
architecture ports & adapters. Aucune feature business — juste le squelette 
robuste sur lequel Cashflow et Portfolio se brancheront.

## Contexte
- Phase 1 bootstrapée et fonctionnelle, packages/backend/ existe en stub
- DeepSeek V4 Pro forcé sur DeepSeek officiel uniquement
- ATM10 arrêté → ~13 Go RAM dispo
- Repo cible : Max-cfn/Stonks, branche main protégée
- Architecture imposée : ports & adapters (hexagonal)
  - domain/ : entités, value objects. Pure Python, zéro dep externe
  - application/ : use cases, ports (interfaces)
  - infrastructure/ : adapters (SQLAlchemy, JWT, Vault, AES)
  - interfaces/api/ : FastAPI routers, schemas Pydantic, dépendances
- Stack figée :
  - fastapi ~=0.115, uvicorn[standard] ~=0.32, pydantic ~=2.9
  - sqlalchemy[asyncio] ~=2.0, asyncpg ~=0.30, alembic ~=1.14
  - python-jose[cryptography] ~=3.3, passlib[bcrypt] ~=1.7
  - cryptography ~=43, hvac ~=2.3, structlog ~=24
  - pytest, pytest-asyncio, pytest-cov, httpx[asyncio]

## Critères d'acceptation

### Structure code
- [ ] packages/backend/src/stonks_backend/ avec ports & adapters
- [ ] pyproject.toml : deps figées, scripts dev/test/migrate
- [ ] README.md du package documente structure et démarrage

### Configuration & secrets
- [ ] infrastructure/config.py via Pydantic Settings, lit env + Vault
- [ ] infrastructure/security/vault_client.py adapter hvac, fallback .env en dev
- [ ] Vault tourne en mode dev via docker-compose (port 8200)
- [ ] AUCUN secret en dur, AUCUN dans les tests

### Base de données
- [ ] Postgres 16 + TimescaleDB 2.x dans docker-compose (timescale/timescaledb:latest-pg16)
- [ ] SQLAlchemy 2.0 async avec AsyncSession, declarative Base
- [ ] Alembic init avec env.py async, autogenerate fonctionnel
- [ ] Migration 0001_users : table users (id UUID, email unique, hashed_password, ts)
- [ ] Migration 0002_audit_log : hypertable Timescale (ts, user_id, action, payload jsonb)
- [ ] task migrate lance les migrations

### Authentification
- [ ] domain/user.py avec value objects Email, HashedPassword
- [ ] application/use_cases/auth/ : register, login, refresh_token
- [ ] bcrypt cost 12, JWT HS256 access 15min + refresh 7j, secret depuis Vault
- [ ] Endpoints /auth/register, /auth/login, /auth/refresh, /auth/me
- [ ] Dépendance get_current_user retourne 401 si invalide
- [ ] Rate limiting slowapi 5 req/min/IP sur /auth/login

### Chiffrement applicatif
- [ ] infrastructure/security/aes_gcm.py : encrypt/decrypt, clé Vault, 
      nonce 96 bits, tag 128 bits
- [ ] Tests round-trip + tampering détecté

### Observabilité
- [ ] GET /health (liveness) + GET /ready (DB + Vault)
- [ ] structlog JSON en prod, console en dev
- [ ] Middleware request-id propagé

### Tests
- [ ] Coverage ≥ 80% global, ≥ 95% sur infrastructure/security/
- [ ] Tests intégration auth full flow
- [ ] Tests AES-GCM round-trip + tampering
- [ ] Tests JWT : valide, expiré, mauvais secret/issuer

### CI / Git
- [ ] Branche agent/backend/phase-2-1-foundations
- [ ] Commits atomiques Conventional Commits
- [ ] PR vers main avec description structurée
- [ ] CI verte : ruff, mypy strict, pytest+coverage
- [ ] Reviewer Agent appelé, rapport dans la PR

### Docker & infra
- [ ] infra/compose/docker-compose.yml étendu : postgres, vault (dev)
- [ ] task stack:up démarre tout
- [ ] packages/backend/Dockerfile multi-stage, prod < 200 MB

## Hors-périmètre
- ❌ Cashflow, Portfolio, banking, boursier
- ❌ Frontend apps/web et apps/mobile
- ❌ agents_core/ (orchestrateur lui-même)
- ❌ system_prompt
- ❌ Force push, merge direct sur main

## Workflow imposé
1. PLAN d'abord (numéroté, agents assignés, durées) → request_human_approval
2. Checkpoint dans execution_log.txt toutes les 5-7 étapes majeures
3. Reviewer Agent obligatoire avant chaque commit (GitNexus impact + relecture diff)
4. PR finale uniquement quand TOUS les critères cochés

## Mode d'exécution
mode: autonomous_long_run
budget_usd_max: 18
human_checkpoint_every_steps: 25
approval_timeout_minutes: 720
escalation_policy: minimal

## Définition de "fait"
✅ PR ouverte, CI verte, Reviewer Agent validé, `task stack:up && task migrate 
   && task test` passe sur machine vierge après git clone, log avec 
   phase=completion status=ok + SHA + URL PR.
❌ Toute autre situation = brief non terminé.