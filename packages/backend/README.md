# `packages/backend` — API FastAPI

> ⚠️ **Stub Phase 1.** Implémentation par l'agent **Backend** en Phase 2.

## Stack prévue

| Composant | Choix | Justification |
|---|---|---|
| Framework | FastAPI 0.115+ | Async natif, OpenAPI auto, perf |
| ORM | SQLAlchemy 2.0 (async) + Alembic | Standard Python, migrations propres |
| DB relationnelle | PostgreSQL 16 | Robustesse, JSON natif, RLS |
| DB time-series | TimescaleDB | Hypertables sur prix boursiers |
| Cache / queue | Redis | Pub/sub WebSockets, rate limit |
| Auth | JWT + HttpOnly cookies | Voir `docs/SECURITY.md` |
| Crypto | `cryptography` (AES-256-GCM) | Données chiffrées en base |
| Vault | HashiCorp Vault (dev mode local) | Stockage clés API tiers |
| Open Banking | Enable Banking SDK | PSD2/OAuth, ~2000 banques EU |
| Marché | yfinance + CoinGecko + Alpha Vantage | Multi-source avec fallback |

## Architecture cible (ports & adapters)

```
src/
├── api/              # FastAPI routers (HTTP)
├── domain/           # Entités, value objects, règles métier
├── application/      # Use-cases (orchestration domaine)
├── infrastructure/   # Adapters (DB, Vault, Enable Banking, CoinGecko, …)
└── ports/            # Interfaces abstraites (BankConnectorPort, PriceProviderPort, …)
```

Inspiré de la structure de `Zoeille/picsou-finance` (mais réimplémenté en Python/FastAPI au lieu de Spring Boot).
