from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Numeric, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
import enum
from app.database import Base


# ============= WAREHOUSE =============
class Warehouse(Base):
    """Warehouses/storage locations from ERPNext."""

    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    warehouse_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    parent_warehouse: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Classification
    warehouse_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Hierarchy
    is_group: Mapped[bool] = mapped_column(default=False)
    lft: Mapped[Optional[int]] = mapped_column(nullable=True)
    rgt: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Status
    disabled: Mapped[bool] = mapped_column(default=False)
    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    deleted_by_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Audit / write-back
    origin_system: Mapped[str] = mapped_column(String(50), default="external")
    write_back_status: Mapped[str] = mapped_column(String(50), default="synced")
    write_back_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    write_back_attempted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Warehouse {self.warehouse_name}>"


# ============= STOCK ENTRY =============
class StockEntryType(enum.Enum):
    MATERIAL_ISSUE = "Material Issue"
    MATERIAL_RECEIPT = "Material Receipt"
    MATERIAL_TRANSFER = "Material Transfer"
    MATERIAL_TRANSFER_FOR_MANUFACTURE = "Material Transfer for Manufacture"
    MATERIAL_CONSUMPTION_FOR_MANUFACTURE = "Material Consumption for Manufacture"
    MANUFACTURE = "Manufacture"
    REPACK = "Repack"
    SEND_TO_SUBCONTRACTOR = "Send to Subcontractor"


class StockEntry(Base):
    """Stock entries (inventory transactions) from ERPNext."""

    __tablename__ = "stock_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Entry type and purpose
    stock_entry_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    purpose: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Dates
    posting_date: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    posting_time: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Warehouses (for simple transfers)
    from_warehouse: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    to_warehouse: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Company
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Amounts
    total_incoming_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    total_outgoing_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    value_difference: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))

    # References
    work_order: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    purchase_order: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sales_order: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    delivery_note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    purchase_receipt: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status
    docstatus: Mapped[int] = mapped_column(default=0)
    is_opening: Mapped[bool] = mapped_column(default=False)
    is_return: Mapped[bool] = mapped_column(default=False)
    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    deleted_by_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Remarks
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit / write-back
    origin_system: Mapped[str] = mapped_column(String(50), default="external")
    write_back_status: Mapped[str] = mapped_column(String(50), default="synced")
    write_back_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    write_back_attempted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to detail rows
    items: Mapped[List["StockEntryDetail"]] = relationship(
        back_populates="stock_entry", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<StockEntry {self.erpnext_id} - {self.stock_entry_type}>"


class StockEntryDetail(Base):
    """Stock entry line items (individual item movements)."""

    __tablename__ = "stock_entry_details"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    stock_entry_id: Mapped[int] = mapped_column(ForeignKey("stock_entries.id"), nullable=False, index=True)

    # Item details
    item_code: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    item_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    uom: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    stock_uom: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    conversion_factor: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1"))

    # Quantity
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    transfer_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))

    # Warehouses
    s_warehouse: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)  # Source
    t_warehouse: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)  # Target

    # Valuation
    basic_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    basic_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    valuation_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))

    # Batch/Serial
    batch_no: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    serial_no: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationship
    stock_entry: Mapped["StockEntry"] = relationship(back_populates="items")

    def __repr__(self) -> str:
        return f"<StockEntryDetail {self.item_code} qty={self.qty}>"


# ============= STOCK LEDGER ENTRY =============
class StockLedgerEntry(Base):
    """Stock ledger entries (audit trail of all inventory movements) from ERPNext."""

    __tablename__ = "stock_ledger_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Item and Location
    item_code: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    warehouse: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Posting info
    posting_date: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    posting_time: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Quantities
    actual_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))  # Change in qty
    qty_after_transaction: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))  # Running balance

    # Valuation
    incoming_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    outgoing_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    valuation_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    stock_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    stock_value_difference: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))

    # Source document
    voucher_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    voucher_no: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    voucher_detail_no: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Batch/Serial
    batch_no: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    serial_no: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Fiscal
    fiscal_year: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Status
    is_cancelled: Mapped[bool] = mapped_column(default=False)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<StockLedgerEntry {self.item_code} @ {self.warehouse} qty={self.actual_qty}>"


# ============= LANDED COST VOUCHER =============
class LandedCostVoucher(Base):
    """Landed cost voucher for allocating additional costs to inventory items."""

    __tablename__ = "landed_cost_vouchers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Basic info
    posting_date: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    distribute_charges_based_on: Mapped[str] = mapped_column(String(50), default="Qty")  # Qty, Amount, Manual

    # References
    purchase_receipt: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    purchase_invoice: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Totals
    total_taxes_and_charges: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))

    # Status
    docstatus: Mapped[int] = mapped_column(default=0)  # 0=Draft, 1=Submitted, 2=Cancelled
    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    deleted_by_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Remarks
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit / write-back
    origin_system: Mapped[str] = mapped_column(String(50), default="local")
    write_back_status: Mapped[str] = mapped_column(String(50), default="pending")
    write_back_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    write_back_attempted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    items: Mapped[List["LandedCostItem"]] = relationship(
        back_populates="voucher", cascade="all, delete-orphan"
    )
    taxes: Mapped[List["LandedCostTax"]] = relationship(
        back_populates="voucher", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<LandedCostVoucher {self.id} - {self.total_taxes_and_charges}>"


class LandedCostItem(Base):
    """Items affected by landed cost allocation."""

    __tablename__ = "landed_cost_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    voucher_id: Mapped[int] = mapped_column(ForeignKey("landed_cost_vouchers.id"), nullable=False, index=True)

    # Item details
    item_code: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    item_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Quantity and amounts
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))

    # Landed cost allocation
    applicable_charges: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    purchase_receipt_item: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Warehouse
    warehouse: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationship
    voucher: Mapped["LandedCostVoucher"] = relationship(back_populates="items")

    def __repr__(self) -> str:
        return f"<LandedCostItem {self.item_code} charges={self.applicable_charges}>"


class LandedCostTax(Base):
    """Taxes/charges to be allocated in landed cost."""

    __tablename__ = "landed_cost_taxes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    voucher_id: Mapped[int] = mapped_column(ForeignKey("landed_cost_vouchers.id"), nullable=False, index=True)

    # Charge details
    expense_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationship
    voucher: Mapped["LandedCostVoucher"] = relationship(back_populates="taxes")

    def __repr__(self) -> str:
        return f"<LandedCostTax {self.expense_account} amount={self.amount}>"
