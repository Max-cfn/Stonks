# Brief — Phase 2.3 : Portfolio (investissements bourse + crypto)

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

**Pré-requis :** la PR Phase 2.1 (PR #2) doit être **mergée sur `main`**. Phase 2.2 (Cashflow) peut être mergée OU non — pas de dépendance directe code à code. Vérifie au démarrage : `gh pr list --repo Max-cfn/Stonks --state open`.



## Objectif
Implémenter l'espace Portfolio : suivi temps réel d'actions/ETF/cryptos en 
multi-devises, calcul TWR/MWR rigoureux, alertes de prix par webhook, 
simulateur d'intérêts composés 10-30 ans, agent LLM analyste qui surveille 
des flux RSS financiers. Stockage des prix en hypertable Timescale.

## Contexte
- Phase 2.1 mergée
- Phase 2.2 PEUT être mergée ou non (pas de dépendance directe)
- APIs externes :
  - CoinGecko (gratuit, rate-limited) pour cryptos
  - Yahoo Finance (yfinance) ou Twelve Data (clé API) pour actions/ETF
  - WebSocket Binance pour prix crypto temps réel optionnel
  - Flux RSS Bloomberg/Reuters/FT (parser feedparser)
- Toutes les clés API dans Vault

## Critères d'acceptation

### Domain
- [ ] Holding (instrument, quantity, avg_cost), Lot (achat individuel), 
      Trade (buy/sell/dividend), Quote (price + ts + currency)
- [ ] Value objects : Currency (ISO 4217), Ticker (symbol + exchange), Money
- [ ] CompoundReturn calculator (TWR, MWR via xirr de scipy ou impl perso)

### Ports
- [ ] PriceFeedPort : get_current(ticker), subscribe_realtime(tickers)
- [ ] FxRatePort : get_rate(from, to, at=now), get_history(from, to, since, until)
- [ ] NewsFeedPort : fetch_recent(sources, since)

### Adapters
- [ ] CoinGeckoAdapter (cryptos), YahooFinanceAdapter ou TwelveDataAdapter (stocks)
- [ ] BinanceWebSocketAdapter pour realtime crypto (asyncio, reconnect auto)
- [ ] FxRateECBAdapter (taux EUR de l'ECB, cache journalier)
- [ ] RssNewsAdapter (feedparser, dédup par GUID)
- [ ] MarketDataSqlRepository : prices en hypertable Timescale

### Use cases
- [ ] AddTrade (buy/sell/dividend, met à jour holdings + lots)
- [ ] GetPortfolioValuation (mark-to-market, en EUR avec FX du jour)
- [ ] ComputePerformance : TWR (par période) + MWR (XIRR)
- [ ] CreatePriceAlert (ticker, threshold, direction, webhook_url)
- [ ] SimulateCompoundGrowth (capital, monthly_contrib, annual_rate, years, scenarios)
- [ ] AnalyzeMarketSentiment (LLM Flash sur RSS récents → digest + alertes)

### API
- [ ] POST /portfolio/trades (add buy/sell/dividend)
- [ ] GET /portfolio/holdings (avec valuation EUR live)
- [ ] GET /portfolio/performance?period=YTD|1M|1Y|ALL → TWR + MWR + benchmark
- [ ] GET /portfolio/quote/{ticker} (cached 30s)
- [ ] WebSocket /portfolio/stream pour prix realtime (auth via query token)
- [ ] POST /portfolio/alerts + GET/DELETE
- [ ] POST /portfolio/simulate (compound growth)
- [ ] GET /portfolio/news/digest (dernier digest sentiment)

### Tâches background
- [ ] Worker async qui pull les prix toutes les 60s pour les holdings actifs
- [ ] Worker qui consomme RSS toutes les 15 min, filtre, soumet à LLM Flash, 
      écrit digest en DB, push alertes si signal fort

### Migrations
- [ ] 0006_portfolio_holdings + lots + trades
- [ ] 0007_portfolio_quotes (hypertable Timescale, index ticker+ts)
- [ ] 0008_portfolio_alerts + 0009_portfolio_news

### Tests
- [ ] Coverage ≥ 80% portfolio/, ≥ 95% sur calculs TWR/MWR
- [ ] Tests TWR/MWR contre des cas connus (validation manuelle dans le code)
- [ ] Tests WebSocket reconnect, dédup news, alerte trigger

### CI / Git
- [ ] Branche agent/backend/phase-2-3-portfolio
- [ ] PR vers main, Reviewer Agent

## Hors-périmètre
- ❌ Frontend
- ❌ Notifications push mobile (Phase 2.5)
- ❌ Modifications Phase 2.1/2.2 sauf bug

## Mode d'exécution
mode: autonomous_long_run
budget_usd_max: 30
human_checkpoint_every_steps: 30
approval_timeout_minutes: 720
escalation_policy: minimal

## Définition de "fait"
✅ PR mergée localement validable, tous les endpoints répondent, 1 trade 
   d'exemple peut être ajouté avec calcul TWR/MWR vérifié à la main, alertes 
   testées en webhook, digest sentiment généré au moins une fois.