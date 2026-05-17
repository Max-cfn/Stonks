"""Cashflow API routes — bank connection, accounts, transactions, and summaries.

All endpoints require authentication via get_current_user.
Rate limiting: /sync is limited to 1/minute/account.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
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
from stonks_backend.infrastructure.bank_connectors.bank_registry import BankRegistry
from stonks_backend.infrastructure.config import get_settings
from stonks_backend.infrastructure.database import get_session
from stonks_backend.infrastructure.persistence.cashflow_repo import CashflowSqlRepository
from stonks_backend.infrastructure.security.aes_gcm import AESCipher
from stonks_backend.infrastructure.security.vault_client import VaultClient
from stonks_backend.interfaces.api.dependencies.auth import get_current_user
from stonks_backend.interfaces.api.schemas import (
    AccountListResponse,
    AccountResponse,
    BankListResponse,
    BankResponse,
    CashflowSummaryResponse,
    CategoryResponse,
    ConnectBankRequest,
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


async def get_bank_registry() -> BankRegistry:
    """Return the bank registry loaded from banks.json."""
    return BankRegistry.from_default_path()


# ── Bank Connection ───────────────────────────────────────────────


@router.get(
    "/banks/available",
    response_model=BankListResponse,
)
async def list_available_banks(
    registry: BankRegistry = Depends(get_bank_registry),
) -> BankListResponse:
    """Return the list of supported banks available for connection."""
    banks = registry.list_supported()
    return BankListResponse(
        banks=[
            BankResponse(
                id=b.id,
                name=b.name,
                country=b.country,
                connector_type=b.connector_type,
                logo_path=b.logo_path,
                supported=b.supported,
                account_types=b.account_types,
                notes=b.notes,
            )
            for b in banks
        ]
    )


@router.post(
    "/banks/connect",
    response_model=ConnectResponse,
    responses={401: {"model": ErrorResponse}},
)
async def connect_bank(
    request: Request,
    body: ConnectBankRequest,
    current_user: User = Depends(get_current_user),
    bank_connector: EnableBankingAdapter = Depends(get_bank_connector),
    registry: BankRegistry = Depends(get_bank_registry),
) -> ConnectResponse:
    """Initiate bank connection: returns the URL the user must visit to authorize."""
    settings = get_settings()
    redirect_uri = f"{settings.public_url}/cashflow/banks/callback"

    use_case = ConnectBankAccount(bank_connector, None, registry)
    auth_url = await use_case.get_authorization_url(
        user_id=current_user.id,
        redirect_uri=redirect_uri,
        bank_id=body.bank_id,
    )
    return ConnectResponse(authorization_url=auth_url)


@router.get(
    "/banks/callback",
    responses={
        400: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)
async def bank_callback(
    code: str = Query(..., description="Authorization code from Enable Banking redirect"),
    state: str = Query(..., description="State parameter with encoded user_id"),
    bank_connector: EnableBankingAdapter = Depends(get_bank_connector),
    repo: CashflowRepositoryPort = Depends(get_cashflow_repo),
    registry: BankRegistry = Depends(get_bank_registry),
) -> RedirectResponse:
    """Session callback: exchange code for session, fetch and persist accounts.

    No authentication required — the user_id is encoded in the state parameter
    (format: "{user_id}:{random_token}") created during get_authorization_url().

    Redirects the user's browser to the frontend dashboard on completion.
    """
    settings = get_settings()
    frontend = settings.frontend_url.rstrip("/")

    # Decode user_id from state parameter
    try:
        user_id_str = state.split(":")[0]
        user_id = UUID(user_id_str)
    except (ValueError, IndexError) as exc:
        logger.warning("Invalid state parameter in bank callback: %s", exc)
        return RedirectResponse(
            url=f"{frontend}/en/dashboard?bank_connect=error&reason=invalid_state"
        )

    use_case = ConnectBankAccount(bank_connector, repo, registry)
    try:
        await use_case.handle_callback(
            user_id=user_id,
            code=code,
        )
    except Exception as exc:
        logger.error("Bank connection failed for user %s: %s", user_id, exc)
        return RedirectResponse(
            url=f"{frontend}/en/dashboard?bank_connect=error&reason=connection_failed"
        )

    return RedirectResponse(url=f"{frontend}/en/dashboard?bank_connect=success")


@router.delete(
    "/banks/{account_id}",
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def disconnect_bank(
    account_id: UUID,
    current_user: User = Depends(get_current_user),
    repo: CashflowRepositoryPort = Depends(get_cashflow_repo),
    bank_connector: EnableBankingAdapter = Depends(get_bank_connector),
) -> dict[str, str]:
    """Disconnect a bank account. Marks it as disconnected — no data is deleted."""
    use_case = ConnectBankAccount(bank_connector, repo)
    try:
        await use_case.disconnect_bank(current_user.id, account_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Disconnect failed: {exc}",
        ) from exc
    return {"status": "disconnected"}


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
                bank_name=a.bank_name,
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
    force: bool = Query(False, description="Force full resync from 2020-01-01"),
    current_user: User = Depends(get_current_user),
    bank_connector: EnableBankingAdapter = Depends(get_bank_connector),
    repo: CashflowRepositoryPort = Depends(get_cashflow_repo),
) -> SyncResponse:
    """Trigger transaction sync for an account. Rate limited: 1/minute/account.
    Use force=true to re-fetch all historical transactions and refresh amounts."""
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
        result = await use_case.sync(account_id, force=force)
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
    account_id: UUID | None = Query(None, description="Account UUID (omit for all accounts)"),
    since: str | None = Query(None, description="Start date ISO 8601"),
    until: str | None = Query(None, description="End date ISO 8601"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    repo: CashflowRepositoryPort = Depends(get_cashflow_repo),
) -> TransactionListResponse:
    """List paginated transactions for an account, or across all active accounts if no account_id."""
    # Parse dates
    from datetime import datetime as dt

    since_dt = dt.fromisoformat(since.replace("Z", "+00:00")) if since else None
    until_dt = dt.fromisoformat(until.replace("Z", "+00:00")) if until else None

    # Resolve account_name map for multi-account mode
    account_map: dict[str, str] = {}

    if account_id is not None:
        # Single-account mode: verify ownership
        account = await repo.get_account(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if account.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        account_map[str(account.id)] = account.account_name or str(account.id)
        transactions = await repo.get_transactions(
            account_id=account_id,
            since=since_dt,
            until=until_dt,
            limit=limit,
            offset=offset,
        )
    else:
        # Multi-account mode: fetch from all active accounts
        user_accounts = await repo.get_accounts_by_user(current_user.id)
        account_map = {str(a.id): a.account_name or str(a.id) for a in user_accounts}
        transactions = await repo.get_transactions_by_user(
            user_id=current_user.id,
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
                account_name=account_map.get(str(tx.account_id)),
                bank_tx_id=tx.bank_tx_id,
                amount=str(tx.amount),
                currency=tx.currency,
                description=tx.description,
                transaction_date=tx.booking_date.isoformat()
                if tx.booking_date
                else (tx.value_date.isoformat() if tx.value_date else None),
                booking_date=tx.booking_date.isoformat() if tx.booking_date else None,
                value_date=tx.value_date.isoformat() if tx.value_date else None,
                status=tx.status.value,
                source=tx.source.value,
                is_expense=tx.amount.is_negative,
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
