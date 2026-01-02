"""Type definitions for banking service.

These dataclasses define the contract for Bank Account and Bank Transaction operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

__all__ = [
    # Bank Account types
    "BankAccountFilters",
    "BankAccountCreateData",
    "BankAccountUpdateData",
    "BankAccountBalanceInfo",
    # Bank Transaction types
    "BankTransactionFilters",
    "BankTransactionSplitData",
    "BankTransactionCreateData",
    "BankTransactionUpdateData",
    # Import types
    "ImportColumnMapping",
    "ParsedTransaction",
    "ImportResult",
]


# ============= BANK ACCOUNT TYPES =============

@dataclass
class BankAccountFilters:
    """Filters for listing bank accounts."""

    include_disabled: bool = False
    as_of_date: Optional[date] = None


@dataclass
class BankAccountCreateData:
    """Data for creating a bank account."""

    account_name: str
    bank: Optional[str] = None
    bank_account_no: Optional[str] = None
    account: Optional[str] = None  # GL account
    company: Optional[str] = None
    currency: str = "NGN"
    is_company_account: bool = True
    is_default: bool = False
    disabled: bool = False


@dataclass
class BankAccountUpdateData:
    """Data for updating a bank account (all fields optional)."""

    account_name: Optional[str] = None
    bank: Optional[str] = None
    bank_account_no: Optional[str] = None
    account: Optional[str] = None
    company: Optional[str] = None
    currency: Optional[str] = None
    is_company_account: Optional[bool] = None
    is_default: Optional[bool] = None
    disabled: Optional[bool] = None


@dataclass
class BankAccountBalanceInfo:
    """Bank account with balance information."""

    id: int
    erpnext_id: Optional[str]
    name: str
    bank: Optional[str]
    account_no: Optional[str]
    gl_account: Optional[str]
    company: Optional[str]
    currency: str
    is_default: bool
    balance: float


# ============= BANK TRANSACTION TYPES =============

@dataclass
class BankTransactionFilters:
    """Filters for listing bank transactions."""

    bank_account: Optional[str] = None
    status: Optional[str] = None
    transaction_type: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    unallocated_only: bool = False
    search: Optional[str] = None
    sort_by: str = "date"
    sort_dir: str = "desc"


@dataclass
class BankTransactionSplitData:
    """Data for a bank transaction split."""

    amount: Decimal
    account: Optional[str] = None
    cost_center: Optional[str] = None
    tax_code_id: Optional[int] = None
    tax_rate: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    memo: Optional[str] = None
    party_type: Optional[str] = None
    party: Optional[str] = None


@dataclass
class BankTransactionCreateData:
    """Data for creating a bank transaction."""

    date: datetime
    bank_account: str
    deposit: Decimal = Decimal("0")
    withdrawal: Decimal = Decimal("0")
    currency: str = "NGN"
    description: Optional[str] = None
    reference_number: Optional[str] = None
    transaction_type: Optional[str] = None
    payee_name: Optional[str] = None
    payee_account: Optional[str] = None
    party_type: Optional[str] = None
    party: Optional[str] = None
    splits: List[BankTransactionSplitData] = field(default_factory=list)


@dataclass
class BankTransactionUpdateData:
    """Data for updating a bank transaction (all fields optional)."""

    date: Optional[datetime] = None
    bank_account: Optional[str] = None
    deposit: Optional[Decimal] = None
    withdrawal: Optional[Decimal] = None
    description: Optional[str] = None
    reference_number: Optional[str] = None
    transaction_type: Optional[str] = None
    payee_name: Optional[str] = None
    payee_account: Optional[str] = None
    party_type: Optional[str] = None
    party: Optional[str] = None


# ============= IMPORT TYPES =============

@dataclass
class ImportColumnMapping:
    """Column mapping for CSV import."""

    date_column: str
    amount_column: Optional[str] = None
    deposit_column: Optional[str] = None
    withdrawal_column: Optional[str] = None
    description_column: Optional[str] = None
    reference_column: Optional[str] = None


@dataclass
class ParsedTransaction:
    """Parsed transaction from import file."""

    date: datetime
    deposit: Decimal
    withdrawal: Decimal
    description: str = ""
    reference_number: str = ""
    row_num: int = 0
    fitid: str = ""  # For OFX imports


@dataclass
class ImportResult:
    """Result of bank transaction import."""

    imported_count: int = 0
    skipped_count: int = 0
    errors: List[dict] = field(default_factory=list)
    transaction_ids: List[int] = field(default_factory=list)
