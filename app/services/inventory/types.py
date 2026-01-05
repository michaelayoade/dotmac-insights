"""Type definitions for inventory services.

These dataclasses define the contract for inventory operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

__all__ = [
    # Enums
    "StockEntryType",
    "TransferStatus",
    # Warehouse types
    "WarehouseFilters",
    "WarehouseCreateData",
    "WarehouseUpdateData",
    # Stock entry types
    "StockEntryFilters",
    "StockEntryCreateData",
    "StockEntryItemData",
    "StockEntryUpdateData",
    # Stock balance types
    "StockBalanceQuery",
    "StockBalanceResult",
    "WarehouseStock",
    "ItemStock",
    # Transfer request types
    "TransferFilters",
    "TransferCreateData",
    "TransferItemData",
    "TransferApprovalData",
]


# =============================================================================
# Enums
# =============================================================================

class StockEntryType(str, Enum):
    """Type of stock entry/movement."""
    MATERIAL_ISSUE = "Material Issue"
    MATERIAL_RECEIPT = "Material Receipt"
    MATERIAL_TRANSFER = "Material Transfer"
    MATERIAL_TRANSFER_FOR_MANUFACTURE = "Material Transfer for Manufacture"
    MATERIAL_CONSUMPTION_FOR_MANUFACTURE = "Material Consumption for Manufacture"
    MANUFACTURE = "Manufacture"
    REPACK = "Repack"
    SEND_TO_SUBCONTRACTOR = "Send to Subcontractor"


class TransferStatus(str, Enum):
    """Status of a transfer request."""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_TRANSIT = "in_transit"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# =============================================================================
# Warehouse Types
# =============================================================================

@dataclass
class WarehouseFilters:
    """Filters for listing warehouses."""

    search: Optional[str] = None
    warehouse_type: Optional[str] = None
    parent_warehouse: Optional[str] = None
    company: Optional[str] = None
    is_group: Optional[bool] = None
    include_disabled: bool = False
    sort_by: str = "warehouse_name"
    sort_dir: str = "asc"


@dataclass
class WarehouseCreateData:
    """Data for creating a warehouse."""

    warehouse_name: str
    warehouse_type: Optional[str] = None
    parent_warehouse: Optional[str] = None
    company: Optional[str] = None
    account: Optional[str] = None
    is_group: bool = False


@dataclass
class WarehouseUpdateData:
    """Data for updating a warehouse."""

    warehouse_name: Optional[str] = None
    warehouse_type: Optional[str] = None
    parent_warehouse: Optional[str] = None
    company: Optional[str] = None
    account: Optional[str] = None
    is_group: Optional[bool] = None
    disabled: Optional[bool] = None


# =============================================================================
# Stock Entry Types
# =============================================================================

@dataclass
class StockEntryFilters:
    """Filters for listing stock entries."""

    search: Optional[str] = None
    stock_entry_type: Optional[str] = None
    from_warehouse: Optional[str] = None
    to_warehouse: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    company: Optional[str] = None
    docstatus: Optional[int] = None  # 0=Draft, 1=Submitted, 2=Cancelled
    sort_by: str = "posting_date"
    sort_dir: str = "desc"


@dataclass
class StockEntryItemData:
    """Data for a stock entry line item."""

    item_code: str
    qty: Decimal
    item_name: Optional[str] = None
    description: Optional[str] = None
    uom: Optional[str] = None
    s_warehouse: Optional[str] = None  # Source warehouse
    t_warehouse: Optional[str] = None  # Target warehouse
    basic_rate: Decimal = Decimal("0")
    batch_no: Optional[str] = None
    serial_no: Optional[str] = None


@dataclass
class StockEntryCreateData:
    """Data for creating a stock entry."""

    stock_entry_type: str
    posting_date: date
    posting_time: Optional[str] = None
    from_warehouse: Optional[str] = None
    to_warehouse: Optional[str] = None
    company: Optional[str] = None
    purpose: Optional[str] = None
    remarks: Optional[str] = None
    items: List[StockEntryItemData] = field(default_factory=list)
    # Reference documents
    work_order: Optional[str] = None
    purchase_order: Optional[str] = None
    sales_order: Optional[str] = None


@dataclass
class StockEntryUpdateData:
    """Data for updating a stock entry."""

    stock_entry_type: Optional[str] = None
    posting_date: Optional[date] = None
    posting_time: Optional[str] = None
    from_warehouse: Optional[str] = None
    to_warehouse: Optional[str] = None
    purpose: Optional[str] = None
    remarks: Optional[str] = None


# =============================================================================
# Stock Balance Types
# =============================================================================

@dataclass
class StockBalanceQuery:
    """Query parameters for stock balance."""

    item_code: Optional[str] = None
    warehouse: Optional[str] = None
    company: Optional[str] = None
    as_of_date: Optional[date] = None
    include_zero_stock: bool = False


@dataclass
class ItemStock:
    """Stock balance for a single item."""

    item_code: str
    item_name: Optional[str]
    warehouse: str
    actual_qty: Decimal
    valuation_rate: Decimal
    stock_value: Decimal
    batch_no: Optional[str] = None


@dataclass
class WarehouseStock:
    """Stock summary for a warehouse."""

    warehouse: str
    warehouse_type: Optional[str]
    total_items: int
    total_qty: Decimal
    total_value: Decimal


@dataclass
class StockBalanceResult:
    """Result of stock balance query."""

    items: List[ItemStock]
    total_qty: Decimal
    total_value: Decimal
    as_of_date: date


# =============================================================================
# Transfer Request Types
# =============================================================================

@dataclass
class TransferFilters:
    """Filters for listing transfer requests."""

    search: Optional[str] = None
    status: Optional[TransferStatus] = None
    from_warehouse: Optional[str] = None
    to_warehouse: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    requested_by_id: Optional[int] = None
    sort_by: str = "request_date"
    sort_dir: str = "desc"


@dataclass
class TransferItemData:
    """Data for a transfer request line item."""

    item_code: str
    qty: Decimal
    item_name: Optional[str] = None
    description: Optional[str] = None
    uom: Optional[str] = None
    batch_no: Optional[str] = None
    serial_no: Optional[str] = None


@dataclass
class TransferCreateData:
    """Data for creating a transfer request."""

    from_warehouse: str
    to_warehouse: str
    required_date: Optional[date] = None
    company: Optional[str] = None
    remarks: Optional[str] = None
    items: List[TransferItemData] = field(default_factory=list)


@dataclass
class TransferApprovalData:
    """Data for approving/rejecting a transfer request."""

    approved: bool
    rejection_reason: Optional[str] = None
    remarks: Optional[str] = None


# =============================================================================
# Item Group Types
# =============================================================================

@dataclass
class ItemGroupFilters:
    """Filters for listing item groups."""

    search: Optional[str] = None
    parent_item_group: Optional[str] = None
    is_group: Optional[bool] = None
    sort_by: str = "item_group_name"
    sort_dir: str = "asc"


@dataclass
class ItemGroupCreateData:
    """Data for creating an item group."""

    item_group_name: str
    parent_item_group: Optional[str] = None
    is_group: bool = False
    lft: Optional[int] = None
    rgt: Optional[int] = None


@dataclass
class ItemGroupUpdateData:
    """Data for updating an item group."""

    item_group_name: Optional[str] = None
    parent_item_group: Optional[str] = None
    is_group: Optional[bool] = None
    lft: Optional[int] = None
    rgt: Optional[int] = None


# =============================================================================
# Item Types
# =============================================================================

@dataclass
class ItemFilters:
    """Filters for listing items."""

    search: Optional[str] = None
    item_group: Optional[str] = None
    status: Optional[str] = None
    is_stock_item: Optional[bool] = None
    warehouse: Optional[str] = None
    sort_by: str = "item_name"
    sort_dir: str = "asc"


@dataclass
class ItemCreateData:
    """Data for creating an item."""

    item_code: str
    item_name: str
    description: Optional[str] = None
    item_group: Optional[str] = None
    uom: Optional[str] = None
    default_warehouse: Optional[str] = None
    valuation_rate: Optional[Decimal] = None
    standard_selling_rate: Optional[Decimal] = None
    is_stock_item: bool = True
    status: str = "active"


@dataclass
class ItemUpdateData:
    """Data for updating an item."""

    item_name: Optional[str] = None
    description: Optional[str] = None
    item_group: Optional[str] = None
    uom: Optional[str] = None
    default_warehouse: Optional[str] = None
    valuation_rate: Optional[Decimal] = None
    standard_selling_rate: Optional[Decimal] = None
    is_stock_item: Optional[bool] = None
    status: Optional[str] = None


# =============================================================================
# Landed Cost Types
# =============================================================================

@dataclass
class LandedCostFilters:
    """Filters for listing landed cost vouchers."""

    search: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    company: Optional[str] = None
    docstatus: Optional[int] = None
    sort_by: str = "posting_date"
    sort_dir: str = "desc"


@dataclass
class LandedCostItemData:
    """Data for a landed cost item (receipt reference)."""

    receipt_document_type: str  # e.g., "Purchase Receipt"
    receipt_document: str  # Document name/ID
    item_code: str
    description: Optional[str] = None
    qty: Decimal = Decimal("0")
    rate: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")


@dataclass
class LandedCostTaxData:
    """Data for a landed cost tax/charge."""

    expense_account: str
    description: Optional[str] = None
    amount: Decimal = Decimal("0")


@dataclass
class LandedCostCreateData:
    """Data for creating a landed cost voucher."""

    posting_date: date
    company: Optional[str] = None
    distribute_charges_based_on: str = "Amount"  # Amount, Qty
    items: List[LandedCostItemData] = field(default_factory=list)
    taxes: List[LandedCostTaxData] = field(default_factory=list)


# =============================================================================
# Batch Types
# =============================================================================

@dataclass
class BatchFilters:
    """Filters for listing batches."""

    search: Optional[str] = None
    item_code: Optional[str] = None
    warehouse: Optional[str] = None
    has_expiry: Optional[bool] = None
    expired: Optional[bool] = None
    sort_by: str = "batch_id"
    sort_dir: str = "asc"


@dataclass
class BatchCreateData:
    """Data for creating a batch."""

    batch_id: str
    item_code: str
    expiry_date: Optional[date] = None
    manufacturing_date: Optional[date] = None
    batch_qty: Decimal = Decimal("0")
    reference_doctype: Optional[str] = None
    reference_name: Optional[str] = None


# =============================================================================
# Serial Number Types
# =============================================================================

@dataclass
class SerialFilters:
    """Filters for listing serial numbers."""

    search: Optional[str] = None
    item_code: Optional[str] = None
    warehouse: Optional[str] = None
    status: Optional[str] = None  # Active, Inactive, Delivered, etc.
    sort_by: str = "serial_no"
    sort_dir: str = "asc"


@dataclass
class SerialCreateData:
    """Data for creating a serial number."""

    serial_no: str
    item_code: str
    warehouse: Optional[str] = None
    batch_no: Optional[str] = None
    status: str = "Active"
    purchase_document_type: Optional[str] = None
    purchase_document_no: Optional[str] = None
