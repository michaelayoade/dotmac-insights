"""Type definitions for ledger service.

These dataclasses define the contract for Chart of Accounts and GL Entry operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

from app.models.accounting import AccountType

__all__ = [
    # Account types
    "AccountFilters",
    "AccountCreateData",
    "AccountUpdateData",
    "AccountBalanceInfo",
    "AccountLedgerFilters",
    "LedgerEntry",
    "AccountLedgerResult",
    "ChartOfAccountsNode",
    # GL Entry types
    "GLEntryFilters",
    "GLEntryCreateData",
    "GLEntryUpdateData",
]


# ============= ACCOUNT TYPES =============

@dataclass
class AccountFilters:
    """Filters for listing accounts."""

    root_type: Optional[AccountType] = None
    account_type: Optional[str] = None
    is_group: Optional[bool] = None
    include_disabled: bool = False
    search: Optional[str] = None
    sort_by: str = "account_name"
    sort_dir: str = "asc"


@dataclass
class AccountCreateData:
    """Data for creating an account."""

    account_name: str
    account_number: Optional[str] = None
    parent_account: Optional[str] = None
    root_type: Optional[AccountType] = None
    account_type: Optional[str] = None
    company: Optional[str] = None
    is_group: bool = False
    disabled: bool = False
    balance_must_be: Optional[str] = None


@dataclass
class AccountUpdateData:
    """Data for updating an account (all fields optional)."""

    account_name: Optional[str] = None
    account_number: Optional[str] = None
    parent_account: Optional[str] = None
    root_type: Optional[AccountType] = None
    account_type: Optional[str] = None
    company: Optional[str] = None
    is_group: Optional[bool] = None
    disabled: Optional[bool] = None
    balance_must_be: Optional[str] = None


@dataclass
class AccountBalanceInfo:
    """Account balance information."""

    total_debit: Decimal
    total_credit: Decimal
    balance: Decimal
    balance_type: str  # "Dr" or "Cr"
    normal_balance: str  # "debit" or "credit"


@dataclass
class AccountLedgerFilters:
    """Filters for account ledger."""

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    party_type: Optional[str] = None
    party: Optional[str] = None
    voucher_type: Optional[str] = None


@dataclass
class LedgerEntry:
    """Single ledger entry with running balance."""

    id: int
    posting_date: Optional[date]
    party_type: Optional[str]
    party: Optional[str]
    debit: Decimal
    credit: Decimal
    balance: Decimal
    voucher_type: Optional[str]
    voucher_no: Optional[str]
    cost_center: Optional[str]


@dataclass
class AccountLedgerResult:
    """Result of account ledger query."""

    account_id: int
    account_name: str
    root_type: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    opening_balance: Decimal
    closing_balance: Decimal
    total: int
    entries: List[LedgerEntry] = field(default_factory=list)


@dataclass
class ChartOfAccountsNode:
    """Node in the chart of accounts tree."""

    id: int
    name: str
    account_number: Optional[str]
    root_type: Optional[str]
    account_type: Optional[str]
    is_group: bool
    disabled: bool
    balance: float
    children: List["ChartOfAccountsNode"] = field(default_factory=list)


# ============= GL ENTRY TYPES =============

@dataclass
class GLEntryFilters:
    """Filters for listing GL entries."""

    account: Optional[str] = None
    voucher_type: Optional[str] = None
    voucher_no: Optional[str] = None
    party_type: Optional[str] = None
    party: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_cancelled: Optional[bool] = None
    search: Optional[str] = None
    sort_by: str = "posting_date"
    sort_dir: str = "desc"


@dataclass
class GLEntryCreateData:
    """Data for creating a GL entry."""

    posting_date: Optional[date] = None
    account: Optional[str] = None
    party_type: Optional[str] = None
    party: Optional[str] = None
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    debit_in_account_currency: Optional[Decimal] = None
    credit_in_account_currency: Optional[Decimal] = None
    voucher_type: Optional[str] = None
    voucher_no: Optional[str] = None
    cost_center: Optional[str] = None
    company: Optional[str] = None
    fiscal_year: Optional[str] = None
    is_cancelled: bool = False


@dataclass
class GLEntryUpdateData:
    """Data for updating a GL entry (all fields optional)."""

    posting_date: Optional[date] = None
    account: Optional[str] = None
    party_type: Optional[str] = None
    party: Optional[str] = None
    debit: Optional[Decimal] = None
    credit: Optional[Decimal] = None
    debit_in_account_currency: Optional[Decimal] = None
    credit_in_account_currency: Optional[Decimal] = None
    voucher_type: Optional[str] = None
    voucher_no: Optional[str] = None
    cost_center: Optional[str] = None
    company: Optional[str] = None
    fiscal_year: Optional[str] = None
    is_cancelled: Optional[bool] = None
