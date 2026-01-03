"""Type definitions for asset services.

These dataclasses define the contract for asset operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from app.models.asset import AssetStatus

__all__ = [
    # Enums
    "DepreciationMethod",
    "DisposalType",
    # Asset filters and data
    "AssetFilters",
    "AssetCreateData",
    "AssetUpdateData",
    "AssetFinanceBookData",
    # Category filters and data
    "CategoryFilters",
    "CategoryCreateData",
    "CategoryUpdateData",
    "CategoryFinanceBookData",
    # Depreciation
    "DepreciationScheduleRow",
    "PendingDepreciation",
    "DepreciationPostResult",
    # Disposal
    "DisposalData",
    "DisposalResult",
    # Capitalization
    "CapitalizationData",
    "CapitalizationAccounts",
    "CapitalizationResult",
    # Maintenance
    "MaintenanceFilters",
    "MaintenanceCompleteData",
    "AssetAlert",
]


# =============================================================================
# Enums
# =============================================================================

class DepreciationMethod(str, Enum):
    """Depreciation calculation method."""
    STRAIGHT_LINE = "straight_line"
    DOUBLE_DECLINING_BALANCE = "double_declining_balance"
    WRITTEN_DOWN_VALUE = "written_down_value"
    MANUAL = "manual"


class DisposalType(str, Enum):
    """Asset disposal type."""
    SALE = "sale"
    SCRAP = "scrap"
    WRITE_OFF = "write_off"


# =============================================================================
# Asset Types
# =============================================================================

@dataclass
class AssetFilters:
    """Filters for listing assets."""

    search: Optional[str] = None
    status: Optional[AssetStatus] = None
    category: Optional[str] = None
    location: Optional[str] = None
    custodian_id: Optional[int] = None
    department: Optional[str] = None
    purchase_date_from: Optional[date] = None
    purchase_date_to: Optional[date] = None
    include_disposed: bool = False
    sort_by: str = "asset_name"
    sort_dir: str = "asc"


@dataclass
class AssetFinanceBookData:
    """Data for asset finance book child record."""

    finance_book: Optional[str] = None
    depreciation_method: str = DepreciationMethod.STRAIGHT_LINE.value
    total_number_of_depreciations: int = 60  # 5 years monthly
    frequency_of_depreciation: int = 12  # monthly
    depreciation_start_date: Optional[date] = None
    expected_value_after_useful_life: Decimal = Decimal("0")
    rate_of_depreciation: Decimal = Decimal("0")


@dataclass
class AssetCreateData:
    """Data for creating an asset."""

    asset_name: str
    asset_category: str
    gross_purchase_amount: Decimal
    purchase_date: Optional[date] = None
    available_for_use_date: Optional[date] = None
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    location: Optional[str] = None
    custodian_id: Optional[int] = None
    department: Optional[str] = None
    cost_center: Optional[str] = None
    company: Optional[str] = None
    description: Optional[str] = None
    serial_no: Optional[str] = None
    asset_quantity: int = 1
    calculate_depreciation: bool = True
    is_existing_asset: bool = False
    opening_accumulated_depreciation: Decimal = Decimal("0")
    # Insurance
    insured_value: Decimal = Decimal("0")
    insurance_start_date: Optional[date] = None
    insurance_end_date: Optional[date] = None
    comprehensive_insurance: Optional[str] = None
    # Warranty
    warranty_expiry_date: Optional[date] = None
    # Maintenance
    maintenance_required: bool = False
    # Finance books (depreciation settings)
    finance_books: List[AssetFinanceBookData] = field(default_factory=list)


@dataclass
class AssetUpdateData:
    """Data for updating an asset (all fields optional)."""

    asset_name: Optional[str] = None
    asset_category: Optional[str] = None
    location: Optional[str] = None
    custodian_id: Optional[int] = None
    department: Optional[str] = None
    cost_center: Optional[str] = None
    description: Optional[str] = None
    serial_no: Optional[str] = None
    # Insurance
    insured_value: Optional[Decimal] = None
    insurance_start_date: Optional[date] = None
    insurance_end_date: Optional[date] = None
    comprehensive_insurance: Optional[str] = None
    # Warranty
    warranty_expiry_date: Optional[date] = None
    # Maintenance
    maintenance_required: Optional[bool] = None


# =============================================================================
# Category Types
# =============================================================================

@dataclass
class CategoryFilters:
    """Filters for listing asset categories."""

    search: Optional[str] = None
    enable_cwip_accounting: Optional[bool] = None
    sort_by: str = "asset_category_name"
    sort_dir: str = "asc"


@dataclass
class CategoryFinanceBookData:
    """Data for category finance book defaults."""

    finance_book: Optional[str] = None
    depreciation_method: str = DepreciationMethod.STRAIGHT_LINE.value
    total_number_of_depreciations: int = 60
    frequency_of_depreciation: int = 12
    # GL Accounts
    fixed_asset_account: Optional[str] = None
    accumulated_depreciation_account: Optional[str] = None
    depreciation_expense_account: Optional[str] = None
    capital_work_in_progress_account: Optional[str] = None


@dataclass
class CategoryCreateData:
    """Data for creating an asset category."""

    asset_category_name: str
    enable_cwip_accounting: bool = False
    finance_books: List[CategoryFinanceBookData] = field(default_factory=list)


@dataclass
class CategoryUpdateData:
    """Data for updating an asset category."""

    asset_category_name: Optional[str] = None
    enable_cwip_accounting: Optional[bool] = None


# =============================================================================
# Depreciation Types
# =============================================================================

@dataclass
class DepreciationScheduleRow:
    """A single row in the depreciation schedule."""

    schedule_date: date
    depreciation_amount: Decimal
    accumulated_depreciation: Decimal
    book_value: Decimal
    # Only set if already booked
    schedule_id: Optional[int] = None
    journal_entry_id: Optional[int] = None
    is_booked: bool = False


@dataclass
class PendingDepreciation:
    """Asset with pending depreciation to be posted."""

    asset_id: int
    asset_name: str
    asset_category: str
    schedule_id: int
    schedule_date: date
    depreciation_amount: Decimal
    accumulated_depreciation: Decimal
    book_value_before: Decimal
    book_value_after: Decimal
    # GL Accounts for posting
    depreciation_expense_account: Optional[str] = None
    accumulated_depreciation_account: Optional[str] = None


@dataclass
class DepreciationPostResult:
    """Result of posting depreciation entries."""

    journal_entry_id: int
    journal_entry_number: str
    schedules_posted: int
    total_depreciation: Decimal


# =============================================================================
# Disposal Types
# =============================================================================

@dataclass
class DisposalData:
    """Data for disposing an asset."""

    disposal_date: date
    disposal_type: DisposalType
    sale_amount: Decimal = Decimal("0")
    buyer_name: Optional[str] = None
    buyer_party_id: Optional[int] = None
    remarks: Optional[str] = None
    # For sale: create receivable invoice
    create_invoice: bool = False


@dataclass
class DisposalResult:
    """Result of asset disposal."""

    asset_id: int
    disposal_type: DisposalType
    disposal_date: date
    book_value_at_disposal: Decimal
    sale_amount: Decimal
    gain_loss: Decimal  # Positive = gain, negative = loss
    journal_entry_id: Optional[int] = None
    journal_entry_number: Optional[str] = None
    invoice_id: Optional[int] = None


# =============================================================================
# Capitalization Types
# =============================================================================

@dataclass
class CapitalizationData:
    """Data for capitalizing an asset (moving from CWIP to fixed asset)."""

    capitalization_date: date
    remarks: Optional[str] = None


@dataclass
class CapitalizationAccounts:
    """GL accounts for asset capitalization."""

    fixed_asset_account: str
    accumulated_depreciation_account: str
    depreciation_expense_account: str
    capital_work_in_progress_account: Optional[str] = None
    gain_loss_on_disposal_account: Optional[str] = None


@dataclass
class CapitalizationResult:
    """Result of asset capitalization."""

    asset_id: int
    capitalization_date: date
    amount_capitalized: Decimal
    journal_entry_id: int
    journal_entry_number: str


# =============================================================================
# Maintenance Types
# =============================================================================

@dataclass
class MaintenanceFilters:
    """Filters for maintenance queries."""

    status: Optional[AssetStatus] = None
    due_within_days: int = 7
    location: Optional[str] = None
    custodian_id: Optional[int] = None


@dataclass
class MaintenanceCompleteData:
    """Data for completing asset maintenance."""

    completion_date: date
    maintenance_cost: Decimal = Decimal("0")
    next_maintenance_date: Optional[date] = None
    remarks: Optional[str] = None
    # If cost should be capitalized (added to asset value)
    capitalize_cost: bool = False


@dataclass
class AssetAlert:
    """Alert for upcoming maintenance, warranty, or insurance expiry."""

    alert_type: str  # "maintenance", "warranty", "insurance"
    asset_id: int
    asset_name: str
    location: Optional[str]
    custodian_id: Optional[int]
    custodian_name: Optional[str]
    due_date: date
    days_until_due: int
