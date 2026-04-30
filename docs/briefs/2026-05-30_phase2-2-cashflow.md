# Brief — Phase 2.2 : Cashflow (agrégation bancaire PSD2)

## Objectif
Implémenter l'espace Cashflow : connexion à des banques européennes via Enable 
Banking (PSD2 OAuth), synchronisation des comptes/transactions, catégorisation 
automatique, vue agrégée. Données chiffrées en base avec l'AES-256-GCM de 
Phase 2.1. Fallback de scraping inspiré de Zoeille/picsou-finance désactivé 
par défaut (feature flag).

## Contexte
- Phase 2.1 mergée : FastAPI + Postgres + TimescaleDB + Vault + JWT + AES-GCM dispo
- Compte Enable Banking sandbox dispo (sinon : créer + documenter dans .env.example)
- Picsou-finance (Spring Boot) à analyser pour comprendre la logique PSD2 et 
  la structure de catégorisation, NE PAS importer leur code
- Architecture ports & adapters strictement respectée

## Critères d'acceptation

### Domain
- [ ] domain/cashflow/ : Account, Transaction, Category, BalanceSnapshot
- [ ] Value objects : Money (amount Decimal + Currency ISO 4217), TransactionId, IBAN
- [ ] Invariants : Money même Currency pour addition, IBAN validé MOD 97

### Ports
- [ ] BankConnectorPort : list_accounts, fetch_transactions(account_id, since, until)
- [ ] CategorizationPort : categorize(transaction) -> Category
- [ ] CashflowRepository : save_account, save_transactions, get_balance_history

### Adapters
- [ ] EnableBankingAdapter : OAuth2 PKCE flow, tokens dans Vault, refresh auto
- [ ] RuleBasedCategorizer : règles regex sur libellé + montant + créancier
- [ ] LLMCategorizer (V4 Flash via OpenRouter) en fallback si règles ambiguës
- [ ] CashflowSqlRepository : SQLAlchemy async, chiffrement AES-GCM sur les 
      colonnes sensibles (iban, holder_name, raw_label)

### Use cases
- [ ] ConnectBankAccount : OAuth flow → token → fetch + persist accounts
- [ ] SyncTransactions : depuis cursor, pagination, dédup par bank_tx_id
- [ ] CategorizeBatch : règles → LLM si nécessaire → save category
- [ ] GetCashflowSummary : solde courant, in/out par mois, top catégories

### API
- [ ] POST /cashflow/banks/connect (renvoie URL OAuth)
- [ ] GET /cashflow/banks/callback (intercepte le code, échange contre token)
- [ ] GET /cashflow/accounts (liste comptes user authentifié)
- [ ] POST /cashflow/accounts/{id}/sync (déclenche SyncTransactions)
- [ ] GET /cashflow/transactions?account_id&since&until (paginé)
- [ ] GET /cashflow/summary?period=month|year
- [ ] Tous derrière get_current_user, RBAC user-scoped

### Migrations
- [ ] 0003_cashflow_accounts (id UUID, user_id FK, bank_id, iban_encrypted, ...)
- [ ] 0004_cashflow_transactions (hypertable Timescale par ts, FK account_id)
- [ ] 0005_cashflow_categories + categorization_rules

### Sécurité
- [ ] Tokens OAuth bank stockés UNIQUEMENT dans Vault (jamais en DB)
- [ ] iban, holder_name, raw_label chiffrés AES-GCM en DB
- [ ] Logs ne fuitent JAMAIS un IBAN ou un libellé brut
- [ ] Rate limiting strict sur /sync (1/min/account)

### Fallback scraping (feature flagged, OFF par défaut)
- [ ] FEATURE_BANK_SCRAPING_FALLBACK env var (default false)
- [ ] Si activé : ScrapingFallbackAdapter (selon les patterns de picsou-finance, 
      adapté au contexte Stonks, code original)
- [ ] Documente clairement les risques (CGU bank, blocage IP, ...)

### Tests
- [ ] Coverage ≥ 80% sur cashflow/, ≥ 90% sur use_cases/
- [ ] Tests intégration full flow avec Enable Banking sandbox (skip si pas de creds)
- [ ] Tests catégorisation : 50+ libellés FR/EN couvrant les patterns courants
- [ ] Tests sécurité : SQL injection, IDOR, fuite IBAN dans logs

### CI / Git
- [ ] Branche agent/backend/phase-2-2-cashflow
- [ ] PR vers main, Reviewer Agent obligatoire
- [ ] CI verte : lint + mypy + tests + coverage

## Hors-périmètre
- ❌ Portfolio (Phase 2.3)
- ❌ Frontend
- ❌ Notifications push (Phase 2.5)
- ❌ Modification Phase 2.1 sauf bug bloquant (et alors → PR séparée d'abord)

## Mode d'exécution
mode: autonomous_long_run
budget_usd_max: 25
human_checkpoint_every_steps: 30
approval_timeout_minutes: 720
escalation_policy: minimal

## Définition de "fait"
✅ PR mergée localement validable : `task stack:up && task migrate && pytest 
   packages/backend/tests/integration/cashflow/` passe, un compte sandbox 
   Enable Banking peut être connecté de bout en bout via curl + récupère ses 
   transactions, log phase=completion status=ok.