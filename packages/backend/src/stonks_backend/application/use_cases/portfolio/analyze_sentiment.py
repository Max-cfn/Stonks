"""AnalyzeMarketSentiment use case — enrich news with LLM sentiment analysis.

Fetches recent financial news, classifies each article's sentiment using
OpenRouter LLM (deepseek/deepseek-v4-flash), and stores a NewsDigest.
Falls back to keyword-based sentiment if the LLM key is not configured.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import structlog

from stonks_backend.application.ports.portfolio import (
    NewsDigest,
    NewsFeedPort,
    PortfolioRepositoryPort,
)
from stonks_backend.infrastructure.config import get_settings

logger = structlog.get_logger(__name__)

# ── OpenRouter ────────────────────────────────────────────────────────────
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_LLM_MODEL = "deepseek/deepseek-v4-flash"
_LLM_TIMEOUT = 15.0

# ── Keyword-based fallback ────────────────────────────────────────────────
_POSITIVE_KEYWORDS: list[str] = [
    "surge", "rally", "jump", "soar", "record high", "beat", "upgrade",
    "bullish", "outperform", "strong", "growth", "profit", "gain", "boost",
    "optimistic", "raised guidance", "dividend increase", "buyback",
]
_NEGATIVE_KEYWORDS: list[str] = [
    "plunge", "crash", "tumble", "sink", "drop", "decline", "loss", "downgrade",
    "bearish", "underperform", "weak", "recession", "layoff", "bankruptcy",
    "lawsuit", "fine", "penalty", "default", "cut guidance", "sell-off",
]

# ── Ticker extraction regex ───────────────────────────────────────────────
_TICKER_RE = re.compile(r"\b[A-Z]{1,5}(?:\.[A-Z]+)?\b")


class SentimentAnalyzerError(ValueError):
    """Raised when sentiment analysis fails completely."""


class AnalyzeMarketSentiment:
    """Fetch and analyse financial news sentiment.

    Args:
        news_feed: News aggregation port.
        repo: Portfolio persistence port for storing digests.
    """

    def __init__(
        self,
        news_feed: NewsFeedPort,
        repo: PortfolioRepositoryPort,
    ) -> None:
        self._news_feed = news_feed
        self._repo = repo
        self._settings = get_settings()

    async def execute(
        self, since: datetime | None = None
    ) -> NewsDigest:
        """Fetch, analyse, and persist a news sentiment digest.

        Workflow:
        1. Fetch recent news articles from the RSS feed.
        2. For each article, determine sentiment via LLM (or keyword fallback).
        3. Extract ticker symbols mentioned.
        4. Build and persist a NewsDigest.
        5. Return the digest.

        The digest aggregates the *most recent* articles up to a reasonable
        batch size (max 25 items).

        Args:
            since: Only process articles published after this UTC datetime.
                Defaults to the last 24 hours.

        Returns:
            A NewsDigest containing sentiment-enriched articles.

        Raises:
            SentimentAnalyzerError: If news fetching fails entirely.
        """
        if since is None:
            since = datetime.now(UTC) - timedelta(hours=24)

        # ── Fetch news ────────────────────────────────────────────────
        news_items = await self._news_feed.fetch_recent(since=since)
        if not news_items:
            logger.warning("sentiment_no_news_fetched", since=since.isoformat())
            now = datetime.now(UTC)
            return NewsDigest(
                id=uuid.uuid4(),
                source="rss_aggregator",
                title="No recent news",
                url="",
                published_at=now,
                sentiment_label="neutral",
                sentiment_score=Decimal("0"),
                summary="No news articles found in the requested period.",
                affected_tickers=None,
                processed_at=now,
            )

        # Limit batch size
        items_to_process = news_items[:25]
        logger.info(
            "sentiment_processing_batch",
            total_fetched=len(news_items),
            processing=len(items_to_process),
        )

        # ── Determine if LLM is available ─────────────────────────────
        api_key = self._settings.openrouter_api_key
        use_llm = api_key is not None and api_key.get_secret_value().strip() != ""

        # ── Analyse each item ─────────────────────────────────────────
        processed_items: list[dict] = []
        for item in items_to_process:
            if use_llm:
                result = await self._llm_sentiment(item.title, item.summary or "")
            else:
                result = self._keyword_sentiment(item.title, item.summary or "")

            # Extract tickers from title + summary
            tickers = self._extract_tickers(item.title, item.summary or "")

            processed_items.append(
                {
                    "title": item.title,
                    "url": item.url,
                    "source": item.source,
                    "published_at": item.published_at,
                    "sentiment_label": result["label"],
                    "sentiment_score": Decimal(str(result["score"])),
                    "summary": item.summary or "",
                    "affected_tickers": tickers if tickers else None,
                }
            )

        # ── Build digest summary ──────────────────────────────────────
        avg_score = sum(
            (p["sentiment_score"] for p in processed_items), Decimal("0")
        ) / Decimal(str(len(processed_items)))

        if avg_score > Decimal("0.2"):
            overall_label = "positive"
        elif avg_score < Decimal("-0.2"):
            overall_label = "negative"
        else:
            overall_label = "neutral"

        # Concatenate top headlines as digest summary
        digest_summary = "; ".join(
            p["title"] for p in processed_items[:5]
        )

        # Collect all affected tickers
        all_tickers: list[str] = []
        seen_tickers: set[str] = set()
        for p in processed_items:
            if p["affected_tickers"]:
                for t in p["affected_tickers"]:
                    if t not in seen_tickers:
                        seen_tickers.add(t)
                        all_tickers.append(t)

        now = datetime.now(UTC)
        digest = NewsDigest(
            id=uuid.uuid4(),
            source="sentiment_analyzer",
            title=f"Market Sentiment Digest — {now.strftime('%Y-%m-%d %H:%M UTC')}",
            url="",
            published_at=min(p["published_at"] for p in processed_items),
            sentiment_label=overall_label,
            sentiment_score=avg_score.quantize(Decimal("0.0001")),
            summary=digest_summary[:1000],
            affected_tickers=all_tickers if all_tickers else None,
            processed_at=now,
        )

        # ── Persist ───────────────────────────────────────────────────
        await self._repo.save_news_digest(digest)

        logger.info(
            "sentiment_digest_complete",
            digest_id=str(digest.id),
            articles=len(processed_items),
            overall_label=overall_label,
            avg_score=str(avg_score),
            ticker_count=len(all_tickers),
        )

        return digest

    # ── LLM sentiment (OpenRouter) ────────────────────────────────────────

    async def _llm_sentiment(
        self, title: str, summary: str
    ) -> dict:
        """Call OpenRouter LLM for sentiment classification.

        Args:
            title: Article headline.
            summary: Article summary or excerpt.

        Returns:
            Dict with keys ``label`` (str) and ``score`` (float).
        """
        prompt = (
            "Analyze the sentiment of this financial news article. "
            "Respond with ONLY a JSON object with two fields:\n"
            '  "label": one of "positive", "negative", or "neutral"\n'
            '  "score": a number between -1.0 (extremely negative) and 1.0 '
            "(extremely positive)\n\n"
            f"Title: {title}\n"
            f"Summary: {summary[:500]}"
        )

        api_key = self._settings.openrouter_api_key.get_secret_value()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://stonks.local",
            "X-Title": "Stonks Market Sentiment",
        }
        payload = {
            "model": _LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 100,
        }

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(_LLM_TIMEOUT)) as client:
                resp = await client.post(
                    _OPENROUTER_URL, json=payload, headers=headers
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException:
            logger.warning("sentiment_llm_timeout", title=title[:60])
            return self._keyword_sentiment(title, summary)
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "sentiment_llm_http_error",
                title=title[:60],
                status=exc.response.status_code,
            )
            return self._keyword_sentiment(title, summary)
        except Exception as exc:
            logger.warning("sentiment_llm_unexpected_error", error=str(exc))
            return self._keyword_sentiment(title, summary)

        # Extract response content
        choices = data.get("choices", [])
        if not choices:
            logger.warning("sentiment_llm_no_choices", title=title[:60])
            return self._keyword_sentiment(title, summary)

        content = choices[0].get("message", {}).get("content", "")

        # Parse JSON from LLM response (may be wrapped in markdown code fences)
        try:
            content = content.strip()
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\s*", "", content)
                content = re.sub(r"\s*```$", "", content)
            result = json.loads(content)
            label = str(result.get("label", "neutral")).lower().strip()
            if label not in ("positive", "negative", "neutral"):
                label = "neutral"
            score = float(result.get("score", 0))
            score = max(-1.0, min(1.0, score))
            return {"label": label, "score": score}
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning(
                "sentiment_llm_parse_error",
                title=title[:60],
                content=content[:100],
                error=str(exc),
            )
            return self._keyword_sentiment(title, summary)

    # ── Keyword-based fallback ────────────────────────────────────────────

    @staticmethod
    def _keyword_sentiment(title: str, summary: str) -> dict:
        """Estimate sentiment by counting positive/negative keywords.

        Args:
            title: Article headline.
            summary: Article summary or excerpt.

        Returns:
            Dict with ``label`` and ``score``.
        """
        text = f"{title} {summary}".lower()

        positive_count = sum(1 for kw in _POSITIVE_KEYWORDS if kw.lower() in text)
        negative_count = sum(1 for kw in _NEGATIVE_KEYWORDS if kw.lower() in text)

        total = positive_count + negative_count
        if total == 0:
            return {"label": "neutral", "score": 0.0}

        score = (positive_count - negative_count) / (positive_count + negative_count)

        if score > 0.2:
            label = "positive"
        elif score < -0.2:
            label = "negative"
        else:
            label = "neutral"

        logger.debug(
            "sentiment_keyword_based",
            positive=positive_count,
            negative=negative_count,
            score=score,
            label=label,
        )
        return {"label": label, "score": round(score, 4)}

    # ── Ticker extraction ─────────────────────────────────────────────────

    @staticmethod
    def _extract_tickers(title: str, summary: str) -> list[str]:
        """Extract potential ticker symbols from article text.

        Uses a regex to find uppercase sequences of 1-5 letters,
        then filters out common English words that match the pattern.

        Args:
            title: Article headline.
            summary: Article summary.

        Returns:
            Deduplicated list of uppercase ticker symbols.
        """
        text = f"{title} {summary}"
        raw_matches = _TICKER_RE.findall(text)

        excludes: frozenset[str] = frozenset({
            "A", "I", "AM", "PM", "US", "UK", "EU", "CEO", "CFO", "IPO",
            "ETF", "GDP", "CPI", "FED", "ECB", "IMF", "YTD", "Q1", "Q2",
            "Q3", "Q4", "AI", "IT", "HR", "PR", "R&D", "ESG", "FX",
            "THE", "AND", "FOR", "ARE", "BUT", "NOT", "WAS", "HAS",
            "NEW", "NOW", "ONE", "TWO", "ALL", "ALSO", "JUST",
        })

        seen: set[str] = set()
        result: list[str] = []
        for m in raw_matches:
            if m in excludes:
                continue
            if m.isdigit():
                continue
            if m not in seen:
                seen.add(m)
                result.append(m)

        return result
