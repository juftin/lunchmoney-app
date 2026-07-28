"""
Pydantic schemas and response models for FastAPI endpoints and MCP tools.
"""

import datetime

from pydantic import BaseModel, Field


class RootResponse(BaseModel):
    """Health check / root endpoint response schema."""

    message: str = Field(default="Hello World", description="Status message")


class SyncDetails(BaseModel):
    """Counts of records synchronized per model."""

    user: int = Field(description="User records synced")
    plaid_accounts: int = Field(description="Plaid accounts synced")
    manual_accounts: int = Field(description="Manual accounts synced")
    categories: int = Field(description="Categories synced")
    tags: int = Field(description="Tags synced")
    transactions: int = Field(description="Transactions synced")
    total: int = Field(description="Total records synced")


class SyncResponse(BaseModel):
    """FastAPI POST /sync response schema."""

    message: str = Field(default="Synchronization complete")
    synced: SyncDetails


class UserInfo(BaseModel):
    """User profile details."""

    id: int
    name: str
    email: str
    budget_name: str
    primary_currency: str


class CategoryInfo(BaseModel):
    """Budget category details."""

    id: int
    name: str
    is_income: bool
    exclude_from_budget: bool
    exclude_from_totals: bool
    is_group: bool
    group_id: int | None = None


class AccountInfo(BaseModel):
    """Financial account details."""

    id: int
    name: str
    balance: float
    currency: str
    type_or_status: str | None = None
    institution_name: str | None = None


class AccountsSummary(BaseModel):
    """Connected Plaid and manual accounts."""

    plaid_accounts: list[AccountInfo] = Field(default_factory=list)
    manual_accounts: list[AccountInfo] = Field(default_factory=list)


class TransactionInfo(BaseModel):
    """Transaction summary item."""

    id: int
    date: datetime.date
    payee: str
    amount: float
    currency: str
    category_id: int | None = None
    notes: str | None = None
    status: str


class SyncResult(BaseModel):
    """MCP tool sync_data response schema."""

    status: str = Field(default="success")
    synced_records: SyncDetails
