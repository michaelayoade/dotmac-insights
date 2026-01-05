"""Pydantic schemas for inventory API endpoints.

These schemas define the request/response contracts for the API.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field

__all__ = [
    # Item Group schemas
    "ItemGroupCreateRequest",
    "ItemGroupUpdateRequest",
    "ItemGroupResponse",
    # Item schemas
    "ItemCreateRequest",
    "ItemUpdateRequest",
    "ItemResponse",
    # Warehouse schemas
    "WarehouseCreateRequest",
    "WarehouseUpdateRequest",
    "WarehouseResponse",
    # Stock Entry schemas
    "StockEntryLineRequest",
    "StockEntryCreateRequest",
    "StockEntryUpdateRequest",
    "StockEntryResponse",
    # Landed Cost schemas
    "LandedCostItemRequest",
    "LandedCostTaxRequest",
    "LandedCostCreateRequest",
    "LandedCostResponse",
    # Batch schemas
    "BatchCreateRequest",
    "BatchUpdateRequest",
    "BatchResponse",
    # Serial schemas
    "SerialCreateRequest",
    "SerialBulkCreateRequest",
    "SerialUpdateRequest",
    "SerialDeliverRequest",
    "SerialResponse",
]


# =============================================================================
# Item Group Schemas
# =============================================================================

class ItemGroupCreateRequest(BaseModel):
    """Request schema for creating an item group."""
    item_group_name: str = Field(..., min_length=1)
    parent_item_group: Optional[str] = None
    is_group: bool = False
    lft: Optional[int] = None
    rgt: Optional[int] = None


class ItemGroupUpdateRequest(BaseModel):
    """Request schema for updating an item group."""
    item_group_name: Optional[str] = None
    parent_item_group: Optional[str] = None
    is_group: Optional[bool] = None
    lft: Optional[int] = None
    rgt: Optional[int] = None


class ItemGroupResponse(BaseModel):
    """Response schema for an item group."""
    id: int
    erpnext_id: Optional[str] = None
    item_group_name: str
    parent_item_group: Optional[str] = None
    is_group: bool
    lft: Optional[int] = None
    rgt: Optional[int] = None

    class Config:
        from_attributes = True


# =============================================================================
# Item Schemas
# =============================================================================

class ItemCreateRequest(BaseModel):
    """Request schema for creating an item."""
    item_code: str = Field(..., min_length=1)
    item_name: str = Field(..., min_length=1)
    description: Optional[str] = None
    item_group: Optional[str] = None
    uom: Optional[str] = None
    default_warehouse: Optional[str] = None
    valuation_rate: Optional[float] = None
    standard_selling_rate: Optional[float] = None
    is_stock_item: bool = True
    status: str = Field(default="active", pattern="^(active|inactive)$")


class ItemUpdateRequest(BaseModel):
    """Request schema for updating an item."""
    item_name: Optional[str] = None
    description: Optional[str] = None
    item_group: Optional[str] = None
    uom: Optional[str] = None
    default_warehouse: Optional[str] = None
    valuation_rate: Optional[float] = None
    standard_selling_rate: Optional[float] = None
    is_stock_item: Optional[bool] = None
    status: Optional[str] = Field(default=None, pattern="^(active|inactive)$")


class ItemResponse(BaseModel):
    """Response schema for an item."""
    id: int
    item_code: str
    item_name: str
    description: Optional[str] = None
    item_group: Optional[str] = None
    uom: Optional[str] = None
    default_warehouse: Optional[str] = None
    valuation_rate: Optional[Decimal] = None
    standard_selling_rate: Optional[Decimal] = None
    is_stock_item: bool
    status: str

    class Config:
        from_attributes = True


# =============================================================================
# Warehouse Schemas
# =============================================================================

class WarehouseCreateRequest(BaseModel):
    """Request schema for creating a warehouse."""
    name: str = Field(..., min_length=1)
    parent_warehouse: Optional[str] = None
    warehouse_type: Optional[str] = None
    company: Optional[str] = None
    account: Optional[str] = None
    is_group: bool = False


class WarehouseUpdateRequest(BaseModel):
    """Request schema for updating a warehouse."""
    name: Optional[str] = None
    parent_warehouse: Optional[str] = None
    warehouse_type: Optional[str] = None
    company: Optional[str] = None
    account: Optional[str] = None
    is_group: Optional[bool] = None
    disabled: Optional[bool] = None


class WarehouseResponse(BaseModel):
    """Response schema for a warehouse."""
    id: int
    warehouse_name: str
    parent_warehouse: Optional[str] = None
    warehouse_type: Optional[str] = None
    company: Optional[str] = None
    account: Optional[str] = None
    is_group: bool
    disabled: bool

    class Config:
        from_attributes = True


# =============================================================================
# Stock Entry Schemas
# =============================================================================

class StockEntryLineRequest(BaseModel):
    """Request schema for a stock entry line item."""
    item_code: str
    qty: float
    uom: Optional[str] = None
    s_warehouse: Optional[str] = None
    t_warehouse: Optional[str] = None
    rate: float = 0
    batch_no: Optional[str] = None
    serial_nos: Optional[List[str]] = None


class StockEntryCreateRequest(BaseModel):
    """Request schema for creating a stock entry."""
    entry_type: str = Field(..., description="material_receipt|material_issue|material_transfer|...")
    posting_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    company: Optional[str] = None
    remarks: Optional[str] = None
    lines: List[StockEntryLineRequest]


class StockEntryUpdateRequest(BaseModel):
    """Request schema for updating a stock entry."""
    posting_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    remarks: Optional[str] = None


class StockEntryResponse(BaseModel):
    """Response schema for a stock entry."""
    id: int
    stock_entry_type: Optional[str] = None
    posting_date: Optional[date] = None
    from_warehouse: Optional[str] = None
    to_warehouse: Optional[str] = None
    company: Optional[str] = None
    total_amount: Decimal
    docstatus: int
    remarks: Optional[str] = None

    class Config:
        from_attributes = True


# =============================================================================
# Landed Cost Schemas
# =============================================================================

class LandedCostItemRequest(BaseModel):
    """Request schema for a landed cost item."""
    receipt_document_type: str
    receipt_document: str
    item_code: str
    description: Optional[str] = None
    qty: float = 0
    rate: float = 0
    amount: float = 0


class LandedCostTaxRequest(BaseModel):
    """Request schema for a landed cost tax."""
    expense_account: str
    description: Optional[str] = None
    amount: float = 0


class LandedCostCreateRequest(BaseModel):
    """Request schema for creating a landed cost voucher."""
    posting_date: str = Field(..., description="YYYY-MM-DD")
    company: Optional[str] = None
    distribute_charges_based_on: str = Field(default="Amount", pattern="^(Amount|Qty)$")
    items: List[LandedCostItemRequest]
    taxes: List[LandedCostTaxRequest]


class LandedCostResponse(BaseModel):
    """Response schema for a landed cost voucher."""
    id: int
    posting_date: Optional[date] = None
    company: Optional[str] = None
    distribute_charges_based_on: str
    total_taxes_and_charges: Decimal
    docstatus: int

    class Config:
        from_attributes = True


# =============================================================================
# Batch Schemas
# =============================================================================

class BatchCreateRequest(BaseModel):
    """Request schema for creating a batch."""
    batch_id: str = Field(..., min_length=1)
    item_code: str = Field(..., min_length=1)
    expiry_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    manufacturing_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    batch_qty: float = 0
    reference_doctype: Optional[str] = None
    reference_name: Optional[str] = None


class BatchUpdateRequest(BaseModel):
    """Request schema for updating a batch."""
    expiry_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    manufacturing_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    description: Optional[str] = None


class BatchResponse(BaseModel):
    """Response schema for a batch."""
    id: int
    batch_id: str
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    manufacturing_date: Optional[date] = None
    expiry_date: Optional[date] = None
    batch_qty: Decimal
    disabled: bool

    class Config:
        from_attributes = True


# =============================================================================
# Serial Schemas
# =============================================================================

class SerialCreateRequest(BaseModel):
    """Request schema for creating a serial number."""
    serial_no: str = Field(..., min_length=1)
    item_code: str = Field(..., min_length=1)
    warehouse: Optional[str] = None
    batch_no: Optional[str] = None
    status: str = "Active"
    purchase_document_type: Optional[str] = None
    purchase_document_no: Optional[str] = None


class SerialBulkCreateRequest(BaseModel):
    """Request schema for creating multiple serial numbers."""
    item_code: str = Field(..., min_length=1)
    serial_nos: List[str] = Field(..., min_items=1)
    warehouse: Optional[str] = None
    batch_no: Optional[str] = None


class SerialUpdateRequest(BaseModel):
    """Request schema for updating a serial number."""
    warehouse: Optional[str] = None
    batch_no: Optional[str] = None
    description: Optional[str] = None
    warranty_expiry_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    amc_expiry_date: Optional[str] = Field(None, description="YYYY-MM-DD")


class SerialDeliverRequest(BaseModel):
    """Request schema for delivering a serial number."""
    customer: str = Field(..., min_length=1)
    delivery_document_type: str
    delivery_document_no: str
    delivery_date: Optional[str] = Field(None, description="YYYY-MM-DD")


class SerialResponse(BaseModel):
    """Response schema for a serial number."""
    id: int
    serial_no: str
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    warehouse: Optional[str] = None
    batch_no: Optional[str] = None
    status: str
    customer: Optional[str] = None

    class Config:
        from_attributes = True
