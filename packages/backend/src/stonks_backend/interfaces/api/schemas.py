"""Pydantic schemas for API endpoints."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


# ── Auth ──────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    is_active: bool
    created_at: str


class ErrorResponse(BaseModel):
    detail: str


# ── Cashflow ──────────────────────────────────────────────────────

class ConnectResponse(BaseModel):
    authorization_url: str


class AccountResponse(BaseModel):
    id: str
    bank_connector: str
    bank_id: str
    iban: str
    account_name: str
    account_type: str
    currency: str
    current_balance: str | None = None
    status: str
    last_synced_at: str | None = None


class AccountListResponse(BaseModel):
    accounts: list[AccountResponse]


class SyncResponse(BaseModel):
    new_transactions: int
    total_fetched: int


class TransactionResponse(BaseModel):
    id: str
    account_id: str
    bank_tx_id: str | None = None
    amount: str
    currency: str
    description: str
    booking_date: str | None = None
    value_date: str | None = None
    status: str
    source: str
    creditor_name: str | None = None
    debtor_name: str | None = None
    category_id: str | None = None


class TransactionListResponse(BaseModel):
    transactions: list[TransactionResponse]
    total: int
    offset: int
    limit: int


class CategoryResponse(BaseModel):
    category_id: str
    name: str
    icon: str
    group: str
    total_amount: str
    currency: str
    transaction_count: int


class CashflowSummaryResponse(BaseModel):
    period_label: str
    period_type: str
    total_income: str
    total_expenses: str
    net_flow: str
    account_count: int
    total_balance: str | None = None
    categories: list[CategoryResponse]
