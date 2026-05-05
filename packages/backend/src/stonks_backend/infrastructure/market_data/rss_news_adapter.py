"""RSS News adapter — implements NewsFeedPort.

Aggregates financial news from multiple RSS feeds. Deduplicates by GUID.
Uses feedparser for RSS/Atom parsing.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx
import structlog

try:
    import feedparser  # type: ignore[import-untyped]

    _FEEDPARSER_AVAILABLE = True
except ImportError:
    _FEEDPARSER_AVAILABLE = False

from stonks_backend.application.ports.portfolio import NewsFeedPort, NewsItem
from stonks_backend.infrastructure.config import Settings

logger = structlog.get_logger(__name__)

# ── Financial RSS feed sources ────────────────────────────────────────────
_DEFAULT_RSS_FEEDS: list[dict[str, str]] = [
    {
        "source": "reuters_business",
        "url": "https://feeds.content.dowjones.io/public/rss/reutersbusinessnews",
    },
    {
        "source": "cnbc_markets",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml"
        "?partnerId=wrss01&id=10001147",
    },
    {
        "source": "marketwatch_top",
        "url": "https://feeds.marketwatch.com/marketwatch/topstories",
    },
    {
        "source": "bloomberg_markets",
        "url": "https://feeds.bloomberg.com/markets/news.rss",
    },
    {
        "source": "wsj_markets",
        "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    },
    {
        "source": "investing_com",
        "url": "https://www.investing.com/rss/news.rss",
    },
    {
        "source": "coindesk",
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    },
    {
        "source": "cointelegraph",
        "url": "https://cointelegraph.com/rss",
    },
]


class RssNewsAdapter(NewsFeedPort):
    """News feed adapter that aggregates financial RSS/Atom feeds.

    Uses feedparser for parsing. Deduplicates articles by GUID.
    Each feed has its own timeout.

    Attributes:
        _timeout: httpx timeout per feed in seconds.
    """

    _timeout: float = 10.0
    _feeds: list[dict[str, str]]

    def __init__(
        self,
        settings: Settings,
        feeds: list[dict[str, str]] | None = None,
    ) -> None:
        """Initialize the RSS news adapter.

        Args:
            settings: Application settings.
            feeds: Optional custom feed list; defaults to _DEFAULT_RSS_FEEDS.
        """
        self._settings = settings
        self._feeds = feeds or list(_DEFAULT_RSS_FEEDS)
        self._client: httpx.AsyncClient | None = None

        if not _FEEDPARSER_AVAILABLE:
            logger.warning(
                "feedparser_not_installed",
                hint="pip install feedparser for RSS news support",
            )

    async def _get_client(self) -> httpx.AsyncClient:
        """Return (or create) the shared httpx async client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                headers={
                    "User-Agent": "Stonks/0.1 (market-news-aggregator)",
                    "Accept": "application/rss+xml, application/atom+xml, "
                    "application/xml, text/xml",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ── NewsFeedPort implementation ───────────────────────────────────────

    async def fetch_recent(
        self,
        sources: list[str] | None = None,
        since: datetime | None = None,
    ) -> list[NewsItem]:
        """Fetch recent financial news articles from RSS feeds.

        Fetches all configured feeds in parallel, deduplicates by GUID,
        filters by source and date, and sorts by published_at descending.

        Args:
            sources: Optional filter by source names (e.g. ['reuters_business']).
            since: Only return articles published after this UTC datetime.

        Returns:
            List of NewsItem, most recent first.
        """
        if not _FEEDPARSER_AVAILABLE:
            logger.warning("rss_news_feedparser_unavailable_returning_empty")
            return []

        if sources is not None:
            source_set = set(sources)
            feeds_to_fetch = [
                f for f in self._feeds if f["source"] in source_set
            ]
        else:
            feeds_to_fetch = list(self._feeds)

        if not feeds_to_fetch:
            logger.warning("rss_news_no_feeds_to_fetch")
            return []

        # Fetch all feeds concurrently
        tasks = [self._fetch_single_feed(feed) for feed in feeds_to_fetch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect items
        all_items: list[NewsItem] = []
        seen_guids: set[str] = set()

        for i, result in enumerate(results):
            feed_info = feeds_to_fetch[i]
            if isinstance(result, Exception):
                logger.warning(
                    "rss_news_feed_failed",
                    source=feed_info["source"],
                    error=str(result),
                )
                continue

            for item in result:
                # Deduplication by GUID
                if item.guid in seen_guids:
                    continue
                seen_guids.add(item.guid)

                # Filter by since
                if since is not None and item.published_at < since:
                    continue

                all_items.append(item)

        # Sort by published_at descending (most recent first)
        all_items.sort(key=lambda x: x.published_at, reverse=True)

        logger.info(
            "rss_news_fetch_complete",
            total_feeds=len(feeds_to_fetch),
            articles=len(all_items),
            sources=list({item.source for item in all_items}),
        )
        return all_items

    # ── Private helpers ───────────────────────────────────────────────────

    async def _fetch_single_feed(
        self, feed: dict[str, str]
    ) -> list[NewsItem]:
        """Fetch and parse a single RSS feed.

        Strategy:
        1. Fetch XML via httpx (fast, with timeout).
        2. Parse with feedparser (sync, but fast — no threading needed).

        Args:
            feed: Dict with 'source' and 'url' keys.

        Returns:
            List of NewsItem from this feed.

        Raises:
            httpx.TimeoutException, RssNewsError, etc.
        """
        source = feed["source"]
        url = feed["url"]

        try:
            client = await self._get_client()
            resp = await client.get(url)
            resp.raise_for_status()
            xml_text = resp.text
        except httpx.TimeoutException:
            logger.warning("rss_news_feed_timeout", source=source, url=url)
            raise
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "rss_news_feed_http_error",
                source=source,
                status=exc.response.status_code,
            )
            raise
        except Exception as exc:
            logger.warning("rss_news_feed_unexpected_error", source=source, error=str(exc))
            raise

        # Parse RSS/Atom with feedparser (synchronous but fast)
        parsed = await asyncio.to_thread(feedparser.parse, xml_text)

        if parsed.bozo:
            logger.debug(
                "rss_news_feed_bozo",
                source=source,
                bozo_exception=str(parsed.bozo_exception),
            )

        items: list[NewsItem] = []
        for entry in parsed.entries:
            guid = entry.get("id") or entry.get("link") or ""
            if not guid:
                continue

            title = entry.get("title", "Untitled")
            link = entry.get("link", "")

            # Parse published date (multiple formats to try)
            published_at = self._parse_date(entry)
            if published_at is None:
                published_at = datetime.now(UTC)

            summary = entry.get("summary", "")
            # Strip HTML from summary
            if summary:
                import re
                summary = re.sub(r"<[^>]+>", "", summary)
                summary = summary.strip()

            items.append(
                NewsItem(
                    guid=str(guid),
                    source=source,
                    title=title,
                    url=link,
                    published_at=published_at,
                    summary=summary or None,
                )
            )

        logger.debug("rss_news_feed_fetched", source=source, count=len(items))
        return items

    @staticmethod
    def _parse_date(entry: dict) -> datetime | None:
        """Attempt to parse a date from a feedparser entry.

        Tries multiple fields and formats.

        Args:
            entry: A single entry dict from feedparser.

        Returns:
            Aware UTC datetime, or None if parsing fails.
        """
        # feedparser provides a parsed tuple via `published_parsed` / `updated_parsed`
        for key in ("published_parsed", "updated_parsed"):
            tp = entry.get(key)
            if tp is not None:
                try:
                    return datetime(*tp[:6], tzinfo=UTC)
                except (TypeError, ValueError, OverflowError):
                    pass

        # Fallback: try string fields
        for key in ("published", "updated"):
            raw = entry.get(key)
            if raw:
                try:
                    # feedparser can parse these
                    parsed = feedparser._parse_date(raw)  # type: ignore[attr-defined]
                    if parsed is not None:
                        return datetime(*parsed[:6], tzinfo=UTC)
                except Exception:
                    pass

        return None
