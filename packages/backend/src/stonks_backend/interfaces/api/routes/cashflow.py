"""Cashflow API routes — bank connection, accounts, transactions, and summaries.

All endpoints require authentication via get_current_user.
Rate limiting: /sync is limited to 1/minute/account.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from stonks_backend.application.ports.cashflow import CashflowRepositoryPort
from stonks_backend.application.use_cases.cashflow.connect_bank import ConnectBankAccount
from stonks_backend.application.use_cases.cashflow.get_summary import (
    GetCashflowSummary,
)
from stonks_backend.application.use_cases.cashflow.sync_transactions import SyncTransactions
from stonks_backend.domain.user import User
from stonks_backend.infrastructure.bank_connectors import EnableBankingAdapter
from stonks_backend.infrastructure.config import get_settings
from stonks_backend.infrastructure.database import get_session
from stonks_backend.infrastructure.persistence.cashflow_repo import CashflowSqlRepository
from stonks_backend.infrastructure.security.aes_gcm import AESCipher
from stonks_backend.infrastructure.security.vault_client import VaultClient
from stonks_backend.interfaces.api.dependencies.auth import get_current_user
from stonks_backend.interfaces.api.schemas import (
    AccountListResponse,
    AccountResponse,
    CashflowSummaryResponse,
    CategoryResponse,
    ConnectResponse,
    ErrorResponse,
    SyncResponse,
    TransactionListResponse,
    TransactionResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cashflow", tags=["cashflow"])
limiter = Limiter(key_func=get_remote_address)


# ── Dependencies ──────────────────────────────────────────────────


async def get_cashflow_repo(
    session: AsyncSession = Depends(get_session),
) -> CashflowRepositoryPort:
    """Return a CashflowSqlRepository with AES cipher from settings."""
    settings = get_settings()
    aes_key = settings.aes_key.get_secret_value()
    cipher = AESCipher(aes_key)
    return CashflowSqlRepository(session, cipher)


async def get_vault_client() -> VaultClient:
    """Return an initialized VaultClient."""
    settings = get_settings()
    client = VaultClient.from_settings(settings)
    await client.initialize()
    return client


async def get_bank_connector(
    vault: VaultClient = Depends(get_vault_client),
) -> EnableBankingAdapter:
    """Return the EnableBankingAdapter (2026 JWT API) for PSD2 connections."""
    settings = get_settings()
    application_id = settings.enable_banking_application_id.get_secret_value()
    return EnableBankingAdapter(
        vault=vault,
        key_path=settings.enable_banking_key_path,
        application_id=application_id,
    )


# ── Bank Connection ───────────────────────────────────────────────


@router.post(
    "/banks/connect",
    response_model=ConnectResponse,
    responses={401: {"model": ErrorResponse}},
)
async def connect_bank(
    request: Request,
    current_user: User = Depends(get_current_user),
    bank_connector: EnableBankingAdapter = Depends(get_bank_connector),
) -> ConnectResponse:
    """Initiate bank connection: returns the URL the user must visit to authorize."""
    settings = get_settings()
    redirect_uri = f"{settings.public_url}/cashflow/banks/callback"

    use_case = ConnectBankAccount(bank_connector, None)  # repo not needed yet
    auth_url = await use_case.get_authorization_url(
        user_id=current_user.id, redirect_uri=redirect_uri
    )
    return ConnectResponse(authorization_url=auth_url)


@router.get(
    "/banks/callback",
    response_model=AccountListResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)
async def bank_callback(
    code: str = Query(..., description="Authorization code from Enable Banking redirect"),
    state: str = Query(None, description="OAuth state parameter"),
    current_user: User = Depends(get_current_user),
    bank_connector: EnableBankingAdapter = Depends(get_bank_connector),
    repo: CashflowRepositoryPort = Depends(get_cashflow_repo),
) -> AccountListResponse:
    """Session callback: exchange code for session, fetch and persist accounts."""
    use_case = ConnectBankAccount(bank_connector, repo)
    try:
        accounts = await use_case.handle_callback(
            user_id=current_user.id,
            code=code,
        )
    except Exception as exc:
        logger.error("Bank connection failed for user %s: %s", current_user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Bank connection failed: {exc}",
        ) from exc

    return AccountListResponse(
        accounts=[
            AccountResponse(
                id=str(a.id),
                bank_connector=a.bank_connector,
                bank_id=a.bank_id,
                iban=a.iban.pretty if a.iban else "N/A",
                account_name=a.account_name,
                account_type=a.account_type.value,
                currency=a.currency,
                current_balance=str(a.current_balance) if a.current_balance else None,
                status=a.status.value,
                last_synced_at=a.last_synced_at.isoformat() if a.last_synced_at else None,
            )
            for a in accounts
        ]
    )


# ── Accounts ──────────────────────────────────────────────────────


@router.get(
    "/accounts",
    response_model=AccountListResponse,
    responses={401: {"model": ErrorResponse}},
)
async def list_accounts(
    current_user: User = Depends(get_current_user),
    repo: CashflowRepositoryPort = Depends(get_cashflow_repo),
) -> AccountListResponse:
    """List all cashflow accounts for the authenticated user."""
    accounts = await repo.get_accounts_by_user(current_user.id)
    return AccountListResponse(
        accounts=[
            AccountResponse(
                id=str(a.id),
                bank_connector=a.bank_connector,
                bank_id=a.bank_id,
                iban=a.iban.pretty if a.iban else "N/A",
                account_name=a.account_name,
                account_type=a.account_type.value,
                currency=a.currency,
                current_balance=str(a.current_balance) if a.current_balance else None,
                status=a.status.value,
                last_synced_at=a.last_synced_at.isoformat() if a.last_synced_at else None,
            )
            for a in accounts
        ]
    )


# ── Sync ──────────────────────────────────────────────────────────


@router.post(
    "/accounts/{account_id}/sync",
    response_model=SyncResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
@limiter.limit("1/minute")
async def sync_transactions(
    request: Request,
    account_id: UUID,
    current_user: User = Depends(get_current_user),
    bank_connector: EnableBankingAdapter = Depends(get_bank_connector),
    repo: CashflowRepositoryPort = Depends(get_cashflow_repo),
) -> SyncResponse:
    """Trigger transaction sync for an account. Rate limited: 1/minute/account."""
    # Verify ownership
    account = await repo.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    use_case = SyncTransactions(bank_connector, repo)
    try:
        result = await use_case.sync(account_id)
    except Exception as exc:
        logger.error("Sync failed for account %s: %s", account_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Sync failed: {exc}",
        ) from exc

    return SyncResponse(
        new_transactions=result.new,
        total_fetched=result.total,
    )


# ── Transactions ──────────────────────────────────────────────────


@router.get(
    "/transactions",
    response_model=TransactionListResponse,
    responses={401: {"model": ErrorResponse}},
)
async def list_transactions(
    account_id: UUID = Query(..., description="Account UUID"),
    since: str | None = Query(None, description="Start date ISO 8601"),
    until: str | None = Query(None, description="End date ISO 8601"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    repo: CashflowRepositoryPort = Depends(get_cashflow_repo),
) -> TransactionListResponse:
    """List paginated transactions for an account, with optional date filtering."""
    # Verify ownership
    account = await repo.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Parse dates
    from datetime import datetime as dt

    since_dt = dt.fromisoformat(since.replace("Z", "+00:00")) if since else None
    until_dt = dt.fromisoformat(until.replace("Z", "+00:00")) if until else None

    transactions = await repo.get_transactions(
        account_id=account_id,
        since=since_dt,
        until=until_dt,
        limit=limit,
        offset=offset,
    )

    return TransactionListResponse(
        transactions=[
            TransactionResponse(
                id=tx.id.value,
                account_id=str(tx.account_id),
                bank_tx_id=tx.bank_tx_id,
                amount=str(tx.amount),
                currency=tx.currency,
                description=tx.description,
                booking_date=tx.booking_date.isoformat() if tx.booking_date else None,
                value_date=tx.value_date.isoformat() if tx.value_date else None,
                status=tx.status.value,
                source=tx.source.value,
                creditor_name=tx.creditor_name,
                debtor_name=tx.debtor_name,
                category_id=str(tx.category_id) if tx.category_id else None,
            )
            for tx in transactions
        ],
        total=len(transactions),
        offset=offset,
        limit=limit,
    )


# ── Summary ───────────────────────────────────────────────────────


@router.get(
    "/summary",
    response_model=CashflowSummaryResponse,
    responses={401: {"model": ErrorResponse}},
)
async def get_summary(
    period: str = Query("month", pattern="^(month|year)$"),
    current_user: User = Depends(get_current_user),
    repo: CashflowRepositoryPort = Depends(get_cashflow_repo),
) -> CashflowSummaryResponse:
    """Get cashflow summary for the current period (month or year)."""
    use_case = GetCashflowSummary(repo)
    summary = await use_case.compute(current_user.id, period=period)

    return CashflowSummaryResponse(
        period_label=summary.period_label,
        period_type=summary.period_type,
        total_income=str(summary.total_income),
        total_expenses=str(summary.total_expenses),
        net_flow=str(summary.net_flow),
        account_count=summary.account_count,
        total_balance=str(summary.total_balance) if summary.total_balance else None,
        categories=[
            CategoryResponse(
                category_id=str(c.category_id),
                name=c.category_name,
                icon=c.category_icon,
                group=c.category_group,
                total_amount=str(c.total_amount),
                currency=c.currency,
                transaction_count=c.transaction_count,
            )
            for c in summary.categories
        ],
    )
