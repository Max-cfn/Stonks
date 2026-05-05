"""Pure unit tests for portfolio domain objects.

Tests Ticker, Quote, Holding, Lot, Trade, and currency helpers without
any database or external dependencies.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from stonks_backend.domain.portfolio.currency import is_crypto, is_fiat
from stonks_backend.domain.portfolio.holding import Holding, HoldingValidationError
from stonks_backend.domain.portfolio.lot import Lot, LotValidationError
from stonks_backend.domain.portfolio.quote import Quote
from stonks_backend.domain.portfolio.ticker import (
    Exchange,
    InstrumentType,
    Ticker,
    TickerValidationError,
)
from stonks_backend.domain.portfolio.trade import Trade, TradeType, TradeValidationError

# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def user_id() -> str:
    return uuid4()


@pytest.fixture
def now_utc() -> datetime:
    return datetime.now(UTC)


# ═══════════════════════════════════════════════════════════════════════════════
# Ticker
# ═══════════════════════════════════════════════════════════════════════════════


class TestTickerCreation:
    def test_ticker_creation_valid(self) -> None:
        """Ticker("AAPL", Exchange.NASDAQ) → symbol="AAPL", exchange=NASDAQ."""
        t = Ticker("AAPL", Exchange.NASDAQ)
        assert t.symbol == "AAPL"
        assert t.exchange is Exchange.NASDAQ

    def test_ticker_creation_crypto(self) -> None:
        """Ticker("BTC", Exchange.CRYPTO) → is_crypto=True."""
        t = Ticker("BTC", Exchange.CRYPTO)
        assert t.symbol == "BTC"
        assert t.exchange is Exchange.CRYPTO
        assert t.is_crypto is True

    def test_ticker_creation_without_exchange(self) -> None:
        """Ticker("AAPL") → exchange=None, is_crypto=False."""
        t = Ticker("AAPL")
        assert t.symbol == "AAPL"
        assert t.exchange is None
        assert t.is_crypto is False

    def test_ticker_lowercase_normalized(self) -> None:
        """Ticker with lowercase input → uppercased."""
        t = Ticker("aapl", Exchange.NASDAQ)
        assert t.symbol == "AAPL"

    def test_ticker_stripped(self) -> None:
        """Ticker with leading/trailing spaces → stripped and uppercased."""
        t = Ticker("  aapl  ")
        assert t.symbol == "AAPL"

    def test_ticker_validation_empty(self) -> None:
        """Ticker("") → TickerValidationError."""
        with pytest.raises(TickerValidationError, match="must not be empty"):
            Ticker("")

    def test_ticker_validation_too_long(self) -> None:
        """Ticker("VERYLONGSYMBOL") → TickerValidationError (max 10 chars)."""
        with pytest.raises(TickerValidationError, match="exceeds 10"):
            Ticker("VERYLONGSYMBOL")

    def test_ticker_validation_invalid_chars(self) -> None:
        """Ticker with invalid characters → TickerValidationError."""
        with pytest.raises(TickerValidationError, match="invalid characters"):
            Ticker("AAPL@#!")

    def test_ticker_valid_with_dot(self) -> None:
        """Ticker with dot is allowed (e.g. BRK.A)."""
        t = Ticker("BRK.A", Exchange.NYSE)
        assert t.symbol == "BRK.A"

    def test_ticker_valid_with_dash(self) -> None:
        """Ticker with dash is allowed (e.g. some indices)."""
        t = Ticker("SP-500")
        assert t.symbol == "SP-500"


class TestTickerEquality:
    def test_ticker_eq_same(self) -> None:
        """Two identical Tickers should be equal."""
        t1 = Ticker("AAPL", Exchange.NASDAQ)
        t2 = Ticker("AAPL", Exchange.NASDAQ)
        assert t1 == t2

    def test_ticker_eq_hash(self) -> None:
        """Two identical Tickers should have the same hash."""
        t1 = Ticker("AAPL", Exchange.NASDAQ)
        t2 = Ticker("AAPL", Exchange.NASDAQ)
        assert hash(t1) == hash(t2)

    def test_ticker_not_eq_different_symbol(self) -> None:
        """Different symbols → not equal."""
        t1 = Ticker("AAPL", Exchange.NASDAQ)
        t2 = Ticker("GOOGL", Exchange.NASDAQ)
        assert t1 != t2

    def test_ticker_not_eq_different_exchange(self) -> None:
        """Same symbol, different exchange → not equal."""
        t1 = Ticker("AAPL", Exchange.NASDAQ)
        t2 = Ticker("AAPL", Exchange.NYSE)
        assert t1 != t2

    def test_ticker_not_eq_none_exchange(self) -> None:
        """One has exchange=None, other has one → not equal."""
        t1 = Ticker("BTC", Exchange.CRYPTO)
        t2 = Ticker("BTC")
        assert t1 != t2

    def test_ticker_not_eq_non_ticker(self) -> None:
        """Comparison with non-Ticker returns NotImplemented → False."""
        t = Ticker("AAPL", Exchange.NASDAQ)
        assert t != "AAPL"


class TestTickerStr:
    def test_ticker_str_with_exchange(self) -> None:
        """str(Ticker("AAPL", Exchange.NASDAQ)) → "AAPL.NASDAQ"."""
        t = Ticker("AAPL", Exchange.NASDAQ)
        assert str(t) == "AAPL.NASDAQ"

    def test_ticker_str_without_exchange(self) -> None:
        """str(Ticker("BTC")) → "BTC"."""
        t = Ticker("BTC")
        assert str(t) == "BTC"

    def test_ticker_str_crypto(self) -> None:
        """str(Ticker("BTC", Exchange.CRYPTO)) → "BTC.CRYPTO"."""
        t = Ticker("BTC", Exchange.CRYPTO)
        assert str(t) == "BTC.CRYPTO"


# ═══════════════════════════════════════════════════════════════════════════════
# Quote
# ═══════════════════════════════════════════════════════════════════════════════


class TestQuoteCreation:
    def test_quote_creation(self) -> None:
        """Quote with valid data → all fields accessible."""
        ticker = Ticker("AAPL", Exchange.NASDAQ)
        ts = datetime.now(UTC)
        q = Quote(
            ticker=ticker,
            price=Decimal("150.25"),
            currency="USD",
            timestamp=ts,
            source="yahoo",
            bid=Decimal("150.00"),
            ask=Decimal("150.50"),
            volume=Decimal("1000000"),
        )
        assert q.ticker == ticker
        assert q.price == Decimal("150.25")
        assert q.currency == "USD"
        assert q.timestamp == ts
        assert q.source == "yahoo"

    def test_quote_mid_price_with_bid_ask(self) -> None:
        """mid_price = (bid + ask) / 2 when both present."""
        ticker = Ticker("AAPL")
        q = Quote(
            ticker=ticker,
            price=Decimal("150.25"),
            currency="USD",
            timestamp=datetime.now(UTC),
            source="yahoo",
            bid=Decimal("150.00"),
            ask=Decimal("150.50"),
        )
        assert q.mid_price == Decimal("150.25")

    def test_quote_mid_price_without_bid_ask(self) -> None:
        """mid_price = price when bid/ask missing."""
        ticker = Ticker("AAPL")
        q = Quote(
            ticker=ticker,
            price=Decimal("150.25"),
            currency="USD",
            timestamp=datetime.now(UTC),
            source="yahoo",
        )
        assert q.mid_price == Decimal("150.25")

    def test_quote_spread(self) -> None:
        """spread = ask - bid."""
        ticker = Ticker("AAPL")
        q = Quote(
            ticker=ticker,
            price=Decimal("150.25"),
            currency="USD",
            timestamp=datetime.now(UTC),
            source="yahoo",
            bid=Decimal("150.00"),
            ask=Decimal("150.50"),
        )
        assert q.spread == Decimal("0.50")

    def test_quote_spread_none(self) -> None:
        """spread = None when bid or ask missing."""
        ticker = Ticker("AAPL")
        q = Quote(
            ticker=ticker,
            price=Decimal("150.25"),
            currency="USD",
            timestamp=datetime.now(UTC),
            source="yahoo",
        )
        assert q.spread is None

    def test_quote_timezone_validation(self) -> None:
        """Naive datetime → ValueError."""
        ticker = Ticker("AAPL")
        naive_dt = datetime.now()
        with pytest.raises(ValueError, match="timezone-aware"):
            Quote(
                ticker=ticker,
                price=Decimal("150"),
                currency="USD",
                timestamp=naive_dt,
                source="yahoo",
            )

    def test_quote_negative_price(self) -> None:
        """Negative price → ValueError."""
        ticker = Ticker("AAPL")
        with pytest.raises(ValueError, match="price must be positive"):
            Quote(
                ticker=ticker,
                price=Decimal("-1"),
                currency="USD",
                timestamp=datetime.now(UTC),
                source="yahoo",
            )

    def test_quote_negative_bid(self) -> None:
        """Negative bid → ValueError."""
        ticker = Ticker("AAPL")
        with pytest.raises(ValueError, match="Bid price must be positive"):
            Quote(
                ticker=ticker,
                price=Decimal("150"),
                currency="USD",
                timestamp=datetime.now(UTC),
                source="yahoo",
                bid=Decimal("-1"),
            )

    def test_quote_negative_volume(self) -> None:
        """Negative volume → ValueError."""
        ticker = Ticker("AAPL")
        with pytest.raises(ValueError, match="Volume must be non-negative"):
            Quote(
                ticker=ticker,
                price=Decimal("150"),
                currency="USD",
                timestamp=datetime.now(UTC),
                source="yahoo",
                volume=Decimal("-1"),
            )

    def test_quote_empty_source(self) -> None:
        """Empty source → ValueError."""
        ticker = Ticker("AAPL")
        with pytest.raises(ValueError, match="source must not be empty"):
            Quote(
                ticker=ticker,
                price=Decimal("150"),
                currency="USD",
                timestamp=datetime.now(UTC),
                source="   ",
            )

    def test_quote_age_seconds(self) -> None:
        """age_seconds should be a positive float for a past quote."""
        ticker = Ticker("AAPL")
        past_time = datetime.now(UTC) - timedelta(seconds=30)
        q = Quote(
            ticker=ticker,
            price=Decimal("150"),
            currency="USD",
            timestamp=past_time,
            source="yahoo",
        )
        assert q.age_seconds > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Holding
# ═══════════════════════════════════════════════════════════════════════════════


class TestHoldingValidation:
    def test_holding_validation_quantity_negative(self) -> None:
        """quantity=-1 → HoldingValidationError."""
        with pytest.raises(HoldingValidationError, match="Quantity must be non-negative"):
            Holding(
                id=uuid4(),
                user_id=uuid4(),
                ticker=Ticker("AAPL", Exchange.NASDAQ),
                instrument_type=InstrumentType.STOCK,
                quantity=Decimal("-1"),
                avg_cost=Decimal("100"),
                currency="USD",
            )

    def test_holding_validation_avg_cost_negative(self) -> None:
        """avg_cost=-1 → HoldingValidationError."""
        with pytest.raises(HoldingValidationError, match="Average cost must be non-negative"):
            Holding(
                id=uuid4(),
                user_id=uuid4(),
                ticker=Ticker("AAPL", Exchange.NASDAQ),
                instrument_type=InstrumentType.STOCK,
                quantity=Decimal("10"),
                avg_cost=Decimal("-1"),
                currency="USD",
            )

    def test_holding_validation_crypto_type_mismatch(self) -> None:
        """InstrumentType CRYPTO with non-crypto ticker → error."""
        with pytest.raises(HoldingValidationError, match="not a crypto"):
            Holding(
                id=uuid4(),
                user_id=uuid4(),
                ticker=Ticker("AAPL", Exchange.NASDAQ),
                instrument_type=InstrumentType.CRYPTO,
                quantity=Decimal("10"),
                avg_cost=Decimal("100"),
                currency="USD",
            )


class TestHoldingValuation:
    @pytest.fixture
    def sample_holding(self) -> Holding:
        return Holding(
            id=uuid4(),
            user_id=uuid4(),
            ticker=Ticker("AAPL", Exchange.NASDAQ),
            instrument_type=InstrumentType.STOCK,
            quantity=Decimal("10"),
            avg_cost=Decimal("100"),
            currency="USD",
        )

    @pytest.fixture
    def sample_quote(self, sample_holding: Holding) -> Quote:
        return Quote(
            ticker=sample_holding.ticker,
            price=Decimal("150"),
            currency="USD",
            timestamp=datetime.now(UTC),
            source="yahoo",
        )

    def test_holding_current_value(self, sample_holding: Holding, sample_quote: Quote) -> None:
        """Holding(10 AAPL @ $100 avg) + Quote($150) → Money(1500, USD)."""
        value = sample_holding.current_value(sample_quote)
        assert value.amount == Decimal("1500")
        assert value.currency == "USD"

    def test_holding_pnl_positive(self, sample_holding: Holding, sample_quote: Quote) -> None:
        """avg_cost=100, price=150, qty=10 → pnl=500."""
        pnl = sample_holding.pnl(sample_quote)
        assert pnl.amount == Decimal("500")
        assert pnl.currency == "USD"

    def test_holding_pnl_negative(self) -> None:
        """avg_cost=100, price=80, qty=10 → pnl=-200."""
        holding = Holding(
            id=uuid4(),
            user_id=uuid4(),
            ticker=Ticker("AAPL", Exchange.NASDAQ),
            instrument_type=InstrumentType.STOCK,
            quantity=Decimal("10"),
            avg_cost=Decimal("100"),
            currency="USD",
        )
        quote = Quote(
            ticker=holding.ticker,
            price=Decimal("80"),
            currency="USD",
            timestamp=datetime.now(UTC),
            source="yahoo",
        )
        pnl = holding.pnl(quote)
        assert pnl.amount == Decimal("-200")

    def test_holding_pnl_pct(self, sample_holding: Holding, sample_quote: Quote) -> None:
        """avg_cost=100, price=150 → pnl_pct = 50%."""
        pct = sample_holding.pnl_pct(sample_quote)
        assert pct == Decimal("50")

    def test_holding_pnl_pct_negative(self) -> None:
        """avg_cost=100, price=80 → pnl_pct = -20%."""
        holding = Holding(
            id=uuid4(),
            user_id=uuid4(),
            ticker=Ticker("AAPL", Exchange.NASDAQ),
            instrument_type=InstrumentType.STOCK,
            quantity=Decimal("10"),
            avg_cost=Decimal("100"),
            currency="USD",
        )
        quote = Quote(
            ticker=holding.ticker,
            price=Decimal("80"),
            currency="USD",
            timestamp=datetime.now(UTC),
            source="yahoo",
        )
        pct = holding.pnl_pct(quote)
        assert pct == Decimal("-20")

    def test_holding_pnl_pct_zero_cost_raises(self) -> None:
        """avg_cost=0 → ZeroDivisionError on pnl_pct."""
        holding = Holding(
            id=uuid4(),
            user_id=uuid4(),
            ticker=Ticker("AAPL", Exchange.NASDAQ),
            instrument_type=InstrumentType.STOCK,
            quantity=Decimal("10"),
            avg_cost=Decimal("0"),
            currency="USD",
        )
        quote = Quote(
            ticker=holding.ticker,
            price=Decimal("150"),
            currency="USD",
            timestamp=datetime.now(UTC),
            source="yahoo",
        )
        with pytest.raises(ZeroDivisionError):
            holding.pnl_pct(quote)

    def test_holding_current_value_wrong_ticker(self, sample_holding: Holding) -> None:
        """Quote for different ticker → HoldingValidationError."""
        wrong_quote = Quote(
            ticker=Ticker("MSFT", Exchange.NASDAQ),
            price=Decimal("150"),
            currency="USD",
            timestamp=datetime.now(UTC),
            source="yahoo",
        )
        with pytest.raises(HoldingValidationError, match="ticker"):
            sample_holding.current_value(wrong_quote)

    def test_holding_current_value_wrong_currency(self, sample_holding: Holding) -> None:
        """Quote in different currency → HoldingValidationError."""
        wrong_quote = Quote(
            ticker=sample_holding.ticker,
            price=Decimal("150"),
            currency="EUR",
            timestamp=datetime.now(UTC),
            source="yahoo",
        )
        with pytest.raises(HoldingValidationError, match="currency"):
            sample_holding.current_value(wrong_quote)


# ═══════════════════════════════════════════════════════════════════════════════
# Lot
# ═══════════════════════════════════════════════════════════════════════════════


class TestLot:
    @pytest.fixture
    def holding_id(self) -> str:
        return uuid4()

    @pytest.fixture
    def lot_buy(self, holding_id: str) -> Lot:
        return Lot(
            id=uuid4(),
            holding_id=holding_id,
            trade_type="buy",
            quantity=Decimal("5"),
            price=Decimal("100"),
            currency="USD",
            date=datetime.now(UTC),
            fees=Decimal("2"),
        )

    @pytest.fixture
    def lot_sell(self, holding_id: str) -> Lot:
        return Lot(
            id=uuid4(),
            holding_id=holding_id,
            trade_type="sell",
            quantity=Decimal("5"),
            price=Decimal("100"),
            currency="USD",
            date=datetime.now(UTC),
        )

    def test_lot_cost_basis(self, lot_buy: Lot) -> None:
        """Lot(price=100, qty=5, fees=2) → cost_basis=502."""
        cost = lot_buy.cost_basis()
        assert cost.amount == Decimal("502")
        assert cost.currency == "USD"

    def test_lot_cost_basis_no_fees(self) -> None:
        """Lot(price=100, qty=5) → cost_basis=500."""
        lot = Lot(
            id=uuid4(),
            holding_id=uuid4(),
            trade_type="buy",
            quantity=Decimal("5"),
            price=Decimal("100"),
            currency="USD",
            date=datetime.now(UTC),
        )
        cost = lot.cost_basis()
        assert cost.amount == Decimal("500")

    def test_lot_proceeds(self, lot_buy: Lot) -> None:
        """Lot(price=100, qty=5) → proceeds=500."""
        proceeds = lot_buy.proceeds
        assert proceeds.amount == Decimal("500")

    def test_lot_validation_naive_date(self) -> None:
        """Naive datetime → LotValidationError."""
        with pytest.raises(LotValidationError, match="timezone-aware"):
            Lot(
                id=uuid4(),
                holding_id=uuid4(),
                trade_type="buy",
                quantity=Decimal("5"),
                price=Decimal("100"),
                currency="USD",
                date=datetime.now(),
            )

    def test_lot_validation_negative_quantity(self) -> None:
        """quantity <= 0 → LotValidationError."""
        with pytest.raises(LotValidationError, match="Quantity must be positive"):
            Lot(
                id=uuid4(),
                holding_id=uuid4(),
                trade_type="buy",
                quantity=Decimal("0"),
                price=Decimal("100"),
                currency="USD",
                date=datetime.now(UTC),
            )

    def test_lot_validation_negative_price(self) -> None:
        """price < 0 → LotValidationError."""
        with pytest.raises(LotValidationError, match="Price must be non-negative"):
            Lot(
                id=uuid4(),
                holding_id=uuid4(),
                trade_type="buy",
                quantity=Decimal("5"),
                price=Decimal("-1"),
                currency="USD",
                date=datetime.now(UTC),
            )

    def test_lot_validation_negative_fees(self) -> None:
        """fees < 0 → LotValidationError."""
        with pytest.raises(LotValidationError, match="Fees must be non-negative"):
            Lot(
                id=uuid4(),
                holding_id=uuid4(),
                trade_type="buy",
                quantity=Decimal("5"),
                price=Decimal("100"),
                currency="USD",
                date=datetime.now(UTC),
                fees=Decimal("-1"),
            )

    def test_lot_validation_invalid_trade_type(self) -> None:
        """trade_type not 'buy' or 'sell' → LotValidationError."""
        with pytest.raises(LotValidationError, match="trade_type"):
            Lot(
                id=uuid4(),
                holding_id=uuid4(),
                trade_type="dividend",  # type: ignore[arg-type]
                quantity=Decimal("5"),
                price=Decimal("100"),
                currency="USD",
                date=datetime.now(UTC),
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Trade
# ═══════════════════════════════════════════════════════════════════════════════


class TestTrade:
    def test_trade_buy(self) -> None:
        """Create a BUY trade."""
        trade = Trade(
            id=uuid4(),
            holding_id=uuid4(),
            trade_type=TradeType.BUY,
            quantity=Decimal("10"),
            price=Decimal("150"),
            currency="USD",
            date=datetime.now(UTC),
        )
        assert trade.trade_type is TradeType.BUY
        assert trade.quantity == Decimal("10")
        assert trade.price == Decimal("150")

    def test_trade_sell(self) -> None:
        """Create a SELL trade."""
        trade = Trade(
            id=uuid4(),
            holding_id=uuid4(),
            trade_type=TradeType.SELL,
            quantity=Decimal("5"),
            price=Decimal("150"),
            currency="USD",
            date=datetime.now(UTC),
            fees=Decimal("1"),
        )
        assert trade.trade_type is TradeType.SELL

    def test_trade_dividend(self) -> None:
        """Create a DIVIDEND trade with dividend_amount.

        Note: the Trade domain requires quantity > 0 for all trade types
        (the check runs before type-specific validation).
        """
        trade = Trade(
            id=uuid4(),
            holding_id=uuid4(),
            trade_type=TradeType.DIVIDEND,
            quantity=Decimal("1"),
            price=Decimal("0"),
            currency="USD",
            date=datetime.now(UTC),
            dividend_amount=Decimal("5"),
        )
        assert trade.trade_type is TradeType.DIVIDEND
        assert trade.dividend_amount == Decimal("5")
        assert trade.price == Decimal("0")

    def test_trade_dividend_with_notes(self) -> None:
        """DIVIDEND trade with notes."""
        trade = Trade(
            id=uuid4(),
            holding_id=uuid4(),
            trade_type=TradeType.DIVIDEND,
            quantity=Decimal("1"),
            price=Decimal("0"),
            currency="USD",
            date=datetime.now(UTC),
            notes="Quarterly dividend",
            dividend_amount=Decimal("5"),
        )
        assert trade.notes == "Quarterly dividend"

    def test_trade_validation_naive_date(self) -> None:
        """Naive datetime → TradeValidationError."""
        with pytest.raises(TradeValidationError, match="timezone-aware"):
            Trade(
                id=uuid4(),
                holding_id=uuid4(),
                trade_type=TradeType.BUY,
                quantity=Decimal("10"),
                price=Decimal("150"),
                currency="USD",
                date=datetime.now(),
            )

    def test_trade_validation_negative_quantity(self) -> None:
        """quantity <= 0 → TradeValidationError (all trade types)."""
        with pytest.raises(TradeValidationError, match="Quantity must be positive"):
            Trade(
                id=uuid4(),
                holding_id=uuid4(),
                trade_type=TradeType.BUY,
                quantity=Decimal("0"),
                price=Decimal("150"),
                currency="USD",
                date=datetime.now(UTC),
            )

    def test_trade_validation_nonzero_price_for_dividend(self) -> None:
        """DIVIDEND with non-zero price → TradeValidationError."""
        with pytest.raises(TradeValidationError, match="Price must be 0 for DIVIDEND"):
            Trade(
                id=uuid4(),
                holding_id=uuid4(),
                trade_type=TradeType.DIVIDEND,
                quantity=Decimal("1"),
                price=Decimal("5"),
                currency="USD",
                date=datetime.now(UTC),
            )

    def test_trade_validation_negative_dividend_amount(self) -> None:
        """Negative dividend_amount → TradeValidationError."""
        with pytest.raises(
            TradeValidationError, match="Dividend amount must be non-negative"
        ):
            Trade(
                id=uuid4(),
                holding_id=uuid4(),
                trade_type=TradeType.DIVIDEND,
                quantity=Decimal("1"),
                price=Decimal("0"),
                currency="USD",
                date=datetime.now(UTC),
                dividend_amount=Decimal("-1"),
            )

    def test_trade_validation_negative_fees(self) -> None:
        """Negative fees → TradeValidationError."""
        with pytest.raises(TradeValidationError, match="Fees must be non-negative"):
            Trade(
                id=uuid4(),
                holding_id=uuid4(),
                trade_type=TradeType.BUY,
                quantity=Decimal("10"),
                price=Decimal("150"),
                currency="USD",
                date=datetime.now(UTC),
                fees=Decimal("-1"),
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Currency helpers
# ═══════════════════════════════════════════════════════════════════════════════


class TestCurrencyHelpers:
    def test_currency_is_crypto(self) -> None:
        """BTC → True, AAPL → False."""
        assert is_crypto("BTC") is True
        assert is_crypto("ETH") is True
        assert is_crypto("USDT") is True
        assert is_crypto("AAPL") is False
        assert is_crypto("TSLA") is False

    def test_currency_is_crypto_case_insensitive(self) -> None:
        """is_crypto is case-insensitive."""
        assert is_crypto("btc") is True
        assert is_crypto("Eth") is True

    def test_currency_is_crypto_stripped(self) -> None:
        """is_crypto strips whitespace."""
        assert is_crypto("  BTC  ") is True

    def test_currency_is_fiat(self) -> None:
        """EUR → True, BTC → False."""
        assert is_fiat("EUR") is True
        assert is_fiat("USD") is True
        assert is_fiat("GBP") is True
        assert is_fiat("BTC") is False
        assert is_fiat("ETH") is False

    def test_currency_is_fiat_case_insensitive(self) -> None:
        """is_fiat is case-insensitive."""
        assert is_fiat("eur") is True
        assert is_fiat("Usd") is True
