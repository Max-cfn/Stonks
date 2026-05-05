"""ECB Foreign Exchange adapter — implements FxRatePort.

Parses the ECB's daily eurofxref XML:
    https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml
    https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml

Uses EUR as pivot: non-EUR pairs are converted via EUR.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from xml.etree import ElementTree

import httpx
import structlog

from stonks_backend.application.ports.portfolio import FxRatePort
from stonks_backend.infrastructure.config import Settings

logger = structlog.get_logger(__name__)

# ── ECB endpoints ─────────────────────────────────────────────────────────
_ECB_DAILY_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
_ECB_HISTORICAL_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"

# ── Cache ─────────────────────────────────────────────────────────────────
_CACHE_TTL_SECONDS = 24 * 3600  # 24h


class FxRateECBError(Exception):
    """Raised when ECB FX rate operations fail."""


class FxRateECBAdapter(FxRatePort):
    """FX rate adapter backed by ECB daily reference rates.

    Rates are expressed as amount of foreign currency per 1 EUR.
    Non-EUR conversions go through EUR pivot:
        X → EUR → Y
        rate(X→Y) = rate(EUR→Y) / rate(EUR→X)

    Attributes:
        _timeout: httpx timeout in seconds.
    """

    _timeout: float = 10.0

    def __init__(self, settings: Settings) -> None:
        """Initialize the ECB FX adapter.

        Args:
            settings: Application settings.
        """
        self._settings = settings
        self._client: httpx.AsyncClient | None = None
        self._daily_cache: dict[str, Decimal] = {}
        self._daily_cache_ts: float = 0.0
        self._historical_cache: dict[str, list[tuple[datetime, Decimal]]] = {}
        self._historical_cache_ts: float = 0.0

    async def _get_client(self) -> httpx.AsyncClient:
        """Return (or create) the shared httpx async client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                headers={"Accept": "application/xml"},
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ── FxRatePort implementation ─────────────────────────────────────────

    async def get_rate(
        self,
        from_currency: str,
        to_currency: str,
        at: datetime | None = None,
    ) -> Decimal:
        """Retrieve the exchange rate between two currencies.

        Args:
            from_currency: ISO 4217 source currency code (e.g. 'USD').
            to_currency: ISO 4217 target currency code.
            at: Point-in-time for historical rate (None = latest).

        Returns:
            The exchange rate as Decimal.

        Raises:
            FxRateECBError: If the currency pair is unsupported or ECB fails.
        """
        from_cur = from_currency.upper()
        to_cur = to_currency.upper()

        if from_cur == to_cur:
            return Decimal("1")

        rates = await self._fetch_daily_rates()

        return self._convert_rate(rates, from_cur, to_cur)

    async def get_history(
        self,
        from_currency: str,
        to_currency: str,
        since: datetime,
        until: datetime,
    ) -> list[tuple[datetime, Decimal]]:
        """Retrieve historical exchange rates from ECB.

        ECB publishes rate history for the last ~90 days.

        Args:
            from_currency: ISO 4217 source currency code.
            to_currency: ISO 4217 target currency code.
            since: Start of the range (inclusive, UTC).
            until: End of the range (inclusive, UTC).

        Returns:
            Chronologically ordered list of (timestamp, rate) tuples.

        Raises:
            FxRateECBError: If ECB is unreachable.
        """
        from_cur = from_currency.upper()
        to_cur = to_currency.upper()
        now = datetime.now(UTC)
        ninety_days_ago = now - timedelta(days=90)

        # Clamp since to ECB max history
        since_clamped = max(since, ninety_days_ago)

        series = await self._fetch_historical_series()

        results: list[tuple[datetime, Decimal]] = []
        for ts, rates in series:
            if ts < since_clamped:
                continue
            if ts > until:
                break
            try:
                rate = self._convert_rate(rates, from_cur, to_cur)
                results.append((ts, rate))
            except FxRateECBError:
                logger.debug(
                    "ecb_missing_rate_for_date",
                    date=ts.isoformat(),
                    from_cur=from_cur,
                    to_cur=to_cur,
                )

        if not results:
            logger.warning(
                "ecb_no_historical_data",
                from_cur=from_cur,
                to_cur=to_cur,
                since=since.isoformat(),
                until=until.isoformat(),
            )

        return results

    # ── Internal fetchers ─────────────────────────────────────────────────

    async def _fetch_daily_rates(self) -> dict[str, Decimal]:
        """Fetch and cache the latest ECB daily rates.

        Returns:
            Dict of currency → rate vs EUR (1 EUR = X currency units).

        Raises:
            FxRateECBError: If the ECB endpoint fails.
        """
        now = time.time()
        if self._daily_cache and (now - self._daily_cache_ts) < _CACHE_TTL_SECONDS:
            return self._daily_cache

        try:
            client = await self._get_client()
            resp = await client.get(_ECB_DAILY_URL)
            resp.raise_for_status()
            xml_text = resp.text
        except httpx.TimeoutException:
            logger.error("ecb_daily_timeout")
            if self._daily_cache:
                logger.warning("ecb_using_stale_daily_cache")
                return self._daily_cache
            raise FxRateECBError("ECB daily XML fetch timed out") from None
        except httpx.HTTPStatusError as exc:
            logger.error("ecb_daily_http_error", status=exc.response.status_code)
            if self._daily_cache:
                logger.warning("ecb_using_stale_daily_cache")
                return self._daily_cache
            raise FxRateECBError(f"ECB daily XML HTTP {exc.response.status_code}") from exc
        except Exception as exc:
            logger.error("ecb_daily_unexpected_error", error=str(exc))
            if self._daily_cache:
                logger.warning("ecb_using_stale_daily_cache")
                return self._daily_cache
            raise FxRateECBError(f"ECB daily XML error: {exc}") from exc

        rates = self._parse_daily_xml(xml_text)
        self._daily_cache = rates
        self._daily_cache_ts = now
        logger.info("ecb_daily_rates_updated", count=len(rates))
        return rates

    async def _fetch_historical_series(
        self,
    ) -> list[tuple[datetime, dict[str, Decimal]]]:
        """Fetch and cache the ECB 90-day historical rates.

        Returns:
            List of (date, rates_dict) tuples, oldest first.
        """
        now = time.time()
        if self._historical_cache and (now - self._historical_cache_ts) < _CACHE_TTL_SECONDS:
            # Flatten from {date_iso: [(ts, rates)]} cache format
            result: list[tuple[datetime, dict[str, Decimal]]] = []
            for _iso_str, entries in sorted(self._historical_cache.items()):
                for ts, rates in entries:
                    result.append((ts, rates))
            return result

        try:
            client = await self._get_client()
            resp = await client.get(_ECB_HISTORICAL_URL)
            resp.raise_for_status()
            xml_text = resp.text
        except httpx.TimeoutException:
            logger.error("ecb_historical_timeout")
            if any(self._historical_cache):
                logger.warning("ecb_using_stale_historical_cache")
                return self._flatten_historical_cache()
            raise FxRateECBError("ECB historical XML fetch timed out") from None
        except httpx.HTTPStatusError as exc:
            logger.error("ecb_historical_http_error", status=exc.response.status_code)
            if any(self._historical_cache):
                logger.warning("ecb_using_stale_historical_cache")
                return self._flatten_historical_cache()
            raise FxRateECBError(f"ECB historical XML HTTP {exc.response.status_code}") from exc
        except Exception as exc:
            logger.error("ecb_historical_unexpected_error", error=str(exc))
            if any(self._historical_cache):
                logger.warning("ecb_using_stale_historical_cache")
                return self._flatten_historical_cache()
            raise FxRateECBError(f"ECB historical XML error: {exc}") from exc

        series = self._parse_historical_xml(xml_text)
        # Cache as {date_iso: [(ts, rates)]}
        self._historical_cache = {}
        for ts, rates in series:
            key = ts.date().isoformat()
            self._historical_cache.setdefault(key, []).append((ts, rates))
        self._historical_cache_ts = now
        logger.info("ecb_historical_rates_updated", days=len(self._historical_cache))
        return series

    def _flatten_historical_cache(self) -> list[tuple[datetime, dict[str, Decimal]]]:
        """Flatten cached historical data."""
        result: list[tuple[datetime, dict[str, Decimal]]] = []
        for _iso_str in sorted(self._historical_cache):
            for ts, rates in self._historical_cache[_iso_str]:
                result.append((ts, rates))
        return result

    # ── XML Parsers ───────────────────────────────────────────────────────

    @staticmethod
    def _parse_daily_xml(xml_text: str) -> dict[str, Decimal]:
        """Parse ECB daily XML into rates dict.

        Args:
            xml_text: Raw XML from ECB daily endpoint.

        Returns:
            Dict of currency → rate (1 EUR = X units).

        Raises:
            FxRateECBError: If parsing fails.
        """
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as exc:
            raise FxRateECBError(f"ECB daily XML parse error: {exc}") from exc

        ns = {
            "gesmes": "http://www.gesmes.org/xml/2002-08-01",
            "ecb": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref",
        }
        rates: dict[str, Decimal] = {"EUR": Decimal("1")}

        for cube in root.findall(".//ecb:Cube/ecb:Cube[@time]/ecb:Cube", ns):
            currency = cube.attrib.get("currency")
            rate_str = cube.attrib.get("rate")
            if currency and rate_str:
                rates[currency] = Decimal(rate_str)

        if not rates or len(rates) <= 1:
            raise FxRateECBError("ECB daily XML contained no rates")

        logger.debug("ecb_daily_parsed", currencies=sorted(rates.keys()))
        return rates

    @staticmethod
    def _parse_historical_xml(
        xml_text: str,
    ) -> list[tuple[datetime, dict[str, Decimal]]]:
        """Parse ECB historical XML into a time series.

        Args:
            xml_text: Raw XML from ECB historical endpoint.

        Returns:
            List of (date, rates_dict) tuples, oldest first.

        Raises:
            FxRateECBError: If parsing fails.
        """
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as exc:
            raise FxRateECBError(f"ECB historical XML parse error: {exc}") from exc

        ns = {
            "gesmes": "http://www.gesmes.org/xml/2002-08-01",
            "ecb": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref",
        }
        series: list[tuple[datetime, dict[str, Decimal]]] = []

        for time_cube in root.findall(".//ecb:Cube/ecb:Cube[@time]", ns):
            time_str = time_cube.attrib.get("time")
            if not time_str:
                continue
            try:
                date = datetime.strptime(time_str, "%Y-%m-%d").replace(tzinfo=UTC)
            except ValueError:
                continue

            rates: dict[str, Decimal] = {"EUR": Decimal("1")}
            for rate_cube in time_cube.findall("ecb:Cube", ns):
                currency = rate_cube.attrib.get("currency")
                rate_str = rate_cube.attrib.get("rate")
                if currency and rate_str:
                    rates[currency] = Decimal(rate_str)

            if len(rates) > 1:  # at least EUR + one other
                series.append((date, rates))

        series.sort(key=lambda x: x[0])
        logger.debug("ecb_historical_parsed", days=len(series))
        return series

    # ── Rate conversion ───────────────────────────────────────────────────

    @staticmethod
    def _convert_rate(rates: dict[str, Decimal], from_cur: str, to_cur: str) -> Decimal:
        """Convert between two currencies via EUR pivot.

        Both from_cur and to_cur must be present in rates.
        EUR is the base: rates[X] = X units per 1 EUR.

        rate(A→B) = rates[B] / rates[A]

        Args:
            rates: Dict of currency → units per 1 EUR.
            from_cur: Source currency.
            to_cur: Target currency.

        Returns:
            The exchange rate as Decimal.

        Raises:
            FxRateECBError: If either currency is missing from rates.
        """
        from_rate = rates.get(from_cur)
        if from_rate is None:
            raise FxRateECBError(f"Currency not in ECB rates: {from_cur}")
        to_rate = rates.get(to_cur)
        if to_rate is None:
            raise FxRateECBError(f"Currency not in ECB rates: {to_cur}")

        return to_rate / from_rate
