# Trade Republic Integration Research

Status: **Research phase** — no implementation yet.

## Context

Trade Republic is a German neobroker, not a bank. It has two distinct parts:
1. **Cash account** — an IBAN-backed account provided by a partner bank
2. **Investment portfolio** — securities (stocks, ETFs) held via custody

## Cash Account (PSD2)

Trade Republic provides an IBAN for each user. The actual custodian bank varies by country:
- Germany: Solarisbank / Deutsche Bank
- France: likely Solarisbank or another EU-licensed bank
- Other EU: depends on local subsidiary

The cash account **should be accessible via Enable Banking PSD2** since it's a standard payment account with an IBAN. The ASPSP name in Enable Banking would need to be verified (likely "TradeRepublic" or the partner bank's name).

**Action required**: Test connecting to Trade Republic via Enable Banking sandbox to confirm ASPSP name and available account types.

## Investment Portfolio

Trade Republic does **not** expose portfolio data via a public API. Options considered:

### Option A: Unofficial API (community)
- GitHub projects exist that reverse-engineer Trade Republic's mobile app API
- Risk: breaks without notice, legal grey area
- Not recommended for production

### Option B: CSV import
- Trade Republic provides monthly PDF/CSV statements
- User exports from Trade Republic app → imports into Stonks
- Safe, legal, but manual
- Could be semi-automated (upload → parse → create trades)

### Option C: Screen scraping
- Extract data from Trade Republic web/app interface
- High maintenance burden, legal risks, ToS violation potential
- **Rejected**

### Recommendation
**Option B (CSV import)** is the pragmatic short-term path:
1. User downloads their Trade Republic activity statement (CSV/PDF)
2. Uploads to Stonks
3. Backend parses and creates `Trade` records
4. Portfolio system computes holdings and performance

## Architecture Preparation

### PortfolioConnectorPort

A new abstract port has been added at `application/ports/portfolio.py`:

```python
class PortfolioConnectorPort(ABC):
    async def get_authorization_url(...)  # For brokers with OAuth
    async def handle_callback(...)
    async def import_holdings(...)  # Bulk import positions
    async def import_transactions(...)  # Bulk import trades
```

This follows the same port/adapter pattern as `BankConnectorPort`.

### Planned adapters

| Adapter | Type | Status |
|---------|------|--------|
| `ManualEntryAdapter` | No-op (user enters trades manually via UI) | Already functional |
| `CsvImportAdapter` | Parse Trade Republic CSV statements | Planned |
| `TradeRepublicApiAdapter` | Use community API (risky) | Deferred |
| `DegiroConnector` | Degiro CSV/API | Deferred |

### Data linking

When Trade Republic integration is active:
- Cash account: `AccountType.CHECKING` via Enable Banking, `bank_name="Trade Republic"`
- Portfolio: `Holding` records linked via `user_id`
- The dashboard should show combined net worth (cash + portfolio mark-to-market)

## Next Steps

1. Verify Enable Banking ASPSP name for Trade Republic (sandbox test)
2. Obtain sample Trade Republic CSV/PDF statements for format analysis
3. Implement CSV parser as `CsvImportAdapter`
4. Wire into the bank selection page (connector_type="csv_import")
