# `packages/backend` — API FastAPI (Stonks Backend)

> Architecture **ports & adapters** (hexagonale), production-ready.

## Structure

```
src/stonks_backend/
├── domain/             # Entités, value objects (pure Python, zéro dep)
│   └── user.py         # User, Email, HashedPassword (bcrypt cost 12)
├── application/        # Use cases, ports (interfaces)
│   ├── ports/
│   │   └── repositories.py  # UserRepositoryPort, RefreshTokenRepositoryPort
│   └── use_cases/
│       └── auth/
│           └── auth_service.py  # Register, login, refresh, get_current_user
├── infrastructure/     # Adapters (DB, JWT, AES, Vault)
│   ├── config.py       # Pydantic Settings (env + Vault)
│   ├── database.py     # SQLAlchemy async engine + session
│   ├── persistence/    # Repos SQLAlchemy + Redis
│   │   ├── models.py   # UserModel, AuditLogModel (TimescaleDB hypertable)
│   │   ├── user_repo.py
│   │   └── refresh_token_repo.py
│   └── security/
│       ├── aes_gcm.py      # AES-256-GCM encryption (Vault-backed key)
│       ├── jwt_service.py  # HS256 access 15min + refresh 7j
│       └── vault_client.py # HashiCorp Vault, fallback .env en dev
├── interfaces/
│   └── api/
│       ├── routes/
│       │   ├── health.py   # GET /health (liveness) + /ready (DB+Vault)
│       │   └── auth.py     # /auth/register, /login, /refresh, /me
│       ├── dependencies/
│       │   └── auth.py     # get_current_user, get_auth_use_cases
│       └── schemas.py      # Pydantic models for requests/responses
└── app.py              # Application factory
```

## Démarrage rapide

```bash
# 1. Lancer les services Docker (Postgres, Vault, Redis)
task stack:up

# 2. Lancer les migrations
task migrate

# 3. Démarrer le backend
task backend:dev            # Mode dev (reload auto)
# ou
python -m stonks_backend   # Mode production
```

## Configuration

Copier `.env.example` → `.env` et renseigner les valeurs.

En production, les secrets JWT et AES viennent de HashiCorp Vault.
En dev, ils sont lus depuis `.env`.

## Tests

```bash
task backend:test    # 53 tests, couverture ≥ 80%
task backend:lint    # ruff + mypy strict
```

## Endpoints principaux

| Méthode | Path | Description |
|---------|------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/ready` | Readiness probe (DB + Vault) |
| POST | `/auth/register` | Inscription |
| POST | `/auth/login` | Connexion → access + refresh tokens |
| POST | `/auth/refresh` | Rotation refresh token |
| GET | `/auth/me` | Profil utilisateur (authentifié) |
| GET | `/docs` | Documentation OpenAPI (Swagger) |

## Migrations

```bash
task migrate           # Applique toutes les migrations
task migrate:new -- 'description'  # Crée une migration autogenerate
task migrate:rollback  # Annule la dernière migration
task db:reset          # Réinitialise la DB de dev
```

## Stack technique

| Composant | Choix |
|---|---|
| Framework | FastAPI 0.136, Uvicorn 0.46 |
| ORM | SQLAlchemy 2.0 (async) + Alembic |
| Base de données | PostgreSQL 16 + TimescaleDB |
| Cache | Redis 7 |
| Auth | JWT HS256 + bcrypt (cost 12) |
| Crypto | AES-256-GCM (cryptography) |
| Secrets | HashiCorp Vault |
| Tests | pytest + pytest-asyncio + coverage |
| Lint | ruff + mypy strict |
