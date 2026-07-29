"""
Pydantic schemas and response models for FastAPI endpoints and MCP tools.
"""

import datetime

from pydantic import BaseModel, Field


class RootResponse(BaseModel):
    """Health check / root endpoint response schema."""

    message: str = Field(default="Hello World", description="Status message")
    """Status message returned by the health check endpoint."""


class SyncDetails(BaseModel):
    """Counts of records synchronized per model."""

    user: int = Field(description="User records synced")
    """Number of user profile records synchronized."""
    plaid_accounts: int = Field(description="Plaid accounts synced")
    """Number of Plaid account records synchronized."""
    manual_accounts: int = Field(description="Manual accounts synced")
    """Number of manual account records synchronized."""
    categories: int = Field(description="Categories synced")
    """Number of category records synchronized."""
    tags: int = Field(description="Tags synced")
    """Number of tag records synchronized."""
    transactions: int = Field(description="Transactions synced")
    """Number of transaction records synchronized."""
    total: int = Field(description="Total records synchronized")
    """Aggregate count of all synchronized database objects."""


class SyncResponse(BaseModel):
    """FastAPI POST /sync response schema."""

    message: str = Field(default="Synchronization complete")
    """Status message summarizing synchronization execution."""
    synced: SyncDetails
    """Detailed count of synchronized records by model."""


class UserInfo(BaseModel):
    """User profile details."""

    id: int
    """Unique identifier for the Lunch Money user."""
    name: str
    """User's display name."""
    email: str
    """User's email address."""
    budget_name: str
    """Title of the user's primary budget."""
    primary_currency: str
    """Three-letter ISO currency code of the user's primary budget."""


class CategoryInfo(BaseModel):
    """Budget category details."""

    id: int
    """Unique category identifier."""
    name: str
    """Category display name."""
    is_income: bool
    """Whether the category represents income rather than an expense."""
    exclude_from_budget: bool
    """Whether the category is excluded from budget calculations."""
    exclude_from_totals: bool
    """Whether the category is excluded from financial totals."""
    is_group: bool
    """Whether this category acts as a parent category group."""
    group_id: int | None = None
    """Optional identifier of the parent category group."""


class AccountInfo(BaseModel):
    """Financial account details."""

    id: int
    """Unique account identifier."""
    name: str
    """Account display name."""
    balance: float
    """Current account balance."""
    currency: str
    """Three-letter ISO currency code for the account balance."""
    type_or_status: str | None = None
    """Account status (Plaid) or account type (Manual)."""
    institution_name: str | None = None
    """Name of the financial institution hosting the account."""


class AccountsSummary(BaseModel):
    """Connected Plaid and manual accounts."""

    plaid_accounts: list[AccountInfo] = Field(default_factory=list)
    """List of connected Plaid accounts."""
    manual_accounts: list[AccountInfo] = Field(default_factory=list)
    """List of user-managed manual accounts."""


class TransactionInfo(BaseModel):
    """Transaction summary item."""

    id: int
    """Unique transaction identifier."""
    date: datetime.date
    """Date on which the transaction occurred."""
    payee: str
    """Payee or merchant name."""
    amount: float
    """Transaction amount in original currency."""
    currency: str
    """Three-letter ISO currency code of the transaction."""
    category_id: int | None = None
    """Optional identifier of the assigned category."""
    notes: str | None = None
    """Optional notes attached to the transaction."""
    status: str
    """Transaction review status (cleared, uncleared, etc.)."""


class SyncResult(BaseModel):
    """MCP tool sync_data response schema."""

    status: str = Field(default="success")
    """Overall status of the sync operation."""
    synced_records: SyncDetails
    """Detailed breakdown of synchronized record counts."""


class ChildCategorySpending(BaseModel):
    """Spending breakdown for a child category."""

    category_id: int
    """Unique child category identifier."""
    category_name: str
    """Child category display name."""
    is_income: bool
    """Whether child category represents income."""
    total_amount: float
    """Total net transaction amount for this child category."""
    transaction_count: int
    """Number of transactions for this child category."""


class CategorySpending(BaseModel):
    """Category spending summary with rollup parent/child aggregation."""

    category_id: int
    """Category identifier (or -1 for Uncategorized)."""
    category_name: str
    """Category display name."""
    is_group: bool
    """Whether category is a parent category group."""
    is_income: bool
    """Whether category represents income."""
    total_amount: float
    """Total net transaction amount including child category rollups."""
    transaction_count: int
    """Total number of transactions including child category rollups."""
    children: list[ChildCategorySpending] = Field(default_factory=list)
    """Breakdown of spending for nested child categories, if any."""


class GroupedSpendingResponse(BaseModel):
    """Grouped spending response by category over specified date range."""

    start_date: datetime.date
    """Start date of the spending analysis window."""
    end_date: datetime.date
    """End date of the spending analysis window."""
    total_spending: float
    """Aggregate spending total across expense categories."""
    total_income: float
    """Aggregate income total across income categories."""
    categories: list[CategorySpending] = Field(default_factory=list)
    """Category spending rollups grouped by top-level category."""
