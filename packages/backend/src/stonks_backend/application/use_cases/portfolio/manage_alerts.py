"""ManageAlerts use case — CRUD for price alerts + trigger checking.

Handles creation, retrieval, deletion, and periodic checking of price alerts.
When an alert triggers, a webhook POST is fired.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import structlog

from stonks_backend.application.ports.portfolio import (
    PortfolioRepositoryPort,
    PriceAlert,
    PriceFeedPort,
)
from stonks_backend.domain.portfolio.ticker import Ticker

logger = structlog.get_logger(__name__)

_VALID_DIRECTIONS = frozenset({"above", "below"})


class ManageAlertsError(ValueError):
    """Raised when alert operations fail (e.g. invalid threshold direction)."""


class ManageAlerts:
    """Manage price alert lifecycle — create, list, delete, and check triggers.

    Args:
        repo: Portfolio persistence port.
    """

    def __init__(self, repo: PortfolioRepositoryPort) -> None:
        self._repo = repo

    # ── Create ────────────────────────────────────────────────────────────

    async def create(
        self,
        user_id: uuid.UUID,
        ticker: Ticker,
        threshold: Decimal,
        direction: str,
        webhook_url: str,
    ) -> PriceAlert:
        """Create a new price alert.

        Args:
            user_id: Owner of the alert.
            ticker: The instrument to watch.
            threshold: Price level that triggers the alert.
            direction: ``"above"`` — triggers when price ≥ threshold;
                ``"below"`` — triggers when price ≤ threshold.
            webhook_url: URL to POST when the alert fires.

        Returns:
            The persisted PriceAlert.

        Raises:
            ManageAlertsError: If direction is invalid or threshold is non-positive.
        """
        direction = direction.lower().strip()
        if direction not in _VALID_DIRECTIONS:
            raise ManageAlertsError(
                f"Invalid direction '{direction}'. Must be one of: "
                f"{', '.join(sorted(_VALID_DIRECTIONS))}"
            )
        if threshold <= 0:
            raise ManageAlertsError(
                f"Threshold must be positive, got {threshold}"
            )
        if not webhook_url.strip():
            raise ManageAlertsError("Webhook URL must not be empty")

        now = datetime.now(UTC)
        alert = PriceAlert(
            id=uuid.uuid4(),
            user_id=user_id,
            ticker=ticker,
            threshold=threshold,
            direction=direction,
            webhook_url=webhook_url,
            triggered=False,
            triggered_at=None,
            created_at=now,
        )
        await self._repo.save_alert(alert)

        logger.info(
            "alert_created",
            alert_id=str(alert.id),
            user_id=str(user_id),
            ticker=str(ticker),
            threshold=str(threshold),
            direction=direction,
        )
        return alert

    # ── Get for user ──────────────────────────────────────────────────────

    async def get_for_user(
        self,
        user_id: uuid.UUID,
        triggered: bool | None = None,
    ) -> list[PriceAlert]:
        """Retrieve price alerts for a user, optionally filtered by triggered status.

        Args:
            user_id: Owner of the alerts.
            triggered: If True, only triggered alerts; if False, only pending;
                if None, all alerts.

        Returns:
            List of PriceAlert objects.
        """
        alerts = await self._repo.get_alerts(user_id, triggered=triggered)
        logger.debug(
            "alerts_fetched",
            user_id=str(user_id),
            count=len(alerts),
            triggered_filter=triggered,
        )
        return alerts

    # ── Delete ────────────────────────────────────────────────────────────

    async def delete(self, alert_id: uuid.UUID) -> None:
        """Remove a price alert by ID.

        Args:
            alert_id: Unique alert identifier.
        """
        await self._repo.delete_alert(alert_id)
        logger.info("alert_deleted", alert_id=str(alert_id))

    # ── Check & trigger ───────────────────────────────────────────────────

    async def check_and_trigger(
        self,
        price_feed: PriceFeedPort,
        user_ids: list[uuid.UUID],
    ) -> list[PriceAlert]:
        """Check all pending alerts for given users and trigger if threshold crossed.

        For each pending alert:
        1. Fetches current price for the alert's ticker via ``price_feed``.
        2. Compares against threshold according to direction.
        3. If triggered, marks as triggered in the repository and POSTs a
           JSON payload to the alert's webhook URL.

        Args:
            price_feed: Market data port to fetch current prices.
            user_ids: Users whose alerts should be checked.

        Returns:
            List of PriceAlert objects that were newly triggered.
        """
        # Collect all pending (non-triggered) alerts across users
        all_pending: list[PriceAlert] = []
        for uid in user_ids:
            pending = await self._repo.get_alerts(uid, triggered=False)
            all_pending.extend(pending)

        if not all_pending:
            logger.debug("alert_check_no_pending", user_count=len(user_ids))
            return []

        triggered_list: list[PriceAlert] = []
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            for alert in all_pending:
                # ── Fetch current price ────────────────────────────────
                try:
                    quote = await price_feed.get_current(alert.ticker)
                except Exception as exc:
                    logger.warning(
                        "alert_check_quote_failed",
                        alert_id=str(alert.id),
                        ticker=str(alert.ticker),
                        error=str(exc),
                    )
                    continue

                # ── Evaluate threshold ─────────────────────────────────
                triggered = False
                if alert.direction == "above" and quote.mid_price >= alert.threshold:
                    triggered = True
                elif alert.direction == "below" and quote.mid_price <= alert.threshold:
                    triggered = True

                if not triggered:
                    continue

                # ── Mark triggered ─────────────────────────────────────
                await self._repo.mark_alert_triggered(alert.id)
                now = datetime.now(UTC)

                # ── Fire webhook ───────────────────────────────────────
                try:
                    resp = await client.post(
                        alert.webhook_url,
                        json={
                            "alert_id": str(alert.id),
                            "user_id": str(alert.user_id),
                            "ticker": str(alert.ticker),
                            "threshold": str(alert.threshold),
                            "direction": alert.direction,
                            "current_price": str(quote.mid_price),
                            "triggered_at": now.isoformat(),
                        },
                    )
                    if resp.status_code >= 400:
                        logger.warning(
                            "alert_webhook_failed",
                            alert_id=str(alert.id),
                            webhook_url=alert.webhook_url,
                            status=resp.status_code,
                        )
                except Exception as exc:
                    logger.warning(
                        "alert_webhook_error",
                        alert_id=str(alert.id),
                        error=str(exc),
                    )

                # ── Build triggered alert DTO ─────────────────────────
                triggered_alert = PriceAlert(
                    id=alert.id,
                    user_id=alert.user_id,
                    ticker=alert.ticker,
                    threshold=alert.threshold,
                    direction=alert.direction,
                    webhook_url=alert.webhook_url,
                    triggered=True,
                    triggered_at=now,
                    created_at=alert.created_at,
                )
                triggered_list.append(triggered_alert)

                logger.info(
                    "alert_triggered",
                    alert_id=str(alert.id),
                    ticker=str(alert.ticker),
                    threshold=str(alert.threshold),
                    direction=alert.direction,
                    current_price=str(quote.mid_price),
                )

        return triggered_list
