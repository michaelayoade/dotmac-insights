"""Document Line models for invoices, bills, credit notes, and debit notes."""
from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Numeric, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from app.database import Base

if TYPE_CHECKING:
    from app.models.invoice import Invoice
    from app.models.credit_note import CreditNote
    from app.models.books_settings import DebitNote
    from app.models.accounting import PurchaseInvoice
    from app.models.sales import SalesOrder, Quotation
    from app.models.purchasing_order import PurchaseOrder


class DocumentLineMixin:
    """
    Mixin providing common fields for all document line types.

    Includes item info, amounts, tax, withholding, and base currency fields.
    """

    # Item information
    item_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    item_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Quantity and rate
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1"))
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    uom: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Unit of measure

    # Amounts
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))  # qty * rate
    discount_percentage: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    net_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))  # after discount

    # Tax
    tax_code_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tax_codes.id"), nullable=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    is_tax_inclusive: Mapped[bool] = mapped_column(default=False)

    # Withholding tax
    withholding_tax_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    withholding_tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # Base currency amounts (company currency)
    base_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    base_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    base_net_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    base_tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # Accounting
    account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cost_center: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Ordering
    idx: Mapped[int] = mapped_column(default=0)


class InvoiceLine(DocumentLineMixin, Base):
    """
    Line item for customer invoices.

    Supports service period dates for revenue recognition.
    """

    __tablename__ = "invoice_lines"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Parent link
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id"), nullable=False, index=True
    )

    # Service period (for revenue recognition / IFRS 15)
    service_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    service_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    invoice: Mapped["Invoice"] = relationship(back_populates="lines")

    def __repr__(self) -> str:
        return f"<InvoiceLine {self.item_name or self.item_code} @ {self.rate}>"


class BillLine(DocumentLineMixin, Base):
    """
    Line item for purchase invoices (bills).

    Supports linking to purchase orders and goods receipts.
    """

    __tablename__ = "bill_lines"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Parent link
    purchase_invoice_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_invoices.id"), nullable=False, index=True
    )

    # Source document links
    purchase_order_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    purchase_order_line_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    goods_receipt_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    goods_receipt_line_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Expense type for direct expenses
    expense_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    purchase_invoice: Mapped["PurchaseInvoice"] = relationship(back_populates="lines")

    def __repr__(self) -> str:
        return f"<BillLine {self.item_name or self.item_code} @ {self.rate}>"


class CreditNoteLine(DocumentLineMixin, Base):
    """
    Line item for credit notes (customer returns/adjustments).

    Can link back to original invoice line for traceability.
    """

    __tablename__ = "credit_note_lines"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Parent link
    credit_note_id: Mapped[int] = mapped_column(
        ForeignKey("credit_notes.id"), nullable=False, index=True
    )

    # Original document link
    original_invoice_line_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("invoice_lines.id"), nullable=True
    )

    # Return/adjustment reason
    return_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    credit_note: Mapped["CreditNote"] = relationship(back_populates="lines")

    def __repr__(self) -> str:
        return f"<CreditNoteLine {self.item_name or self.item_code} @ {self.rate}>"


class DebitNoteLine(DocumentLineMixin, Base):
    """
    Line item for debit notes (vendor returns/adjustments).

    Can link back to original bill line for traceability.
    """

    __tablename__ = "debit_note_lines"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Parent link
    debit_note_id: Mapped[int] = mapped_column(
        ForeignKey("debit_notes.id"), nullable=False, index=True
    )

    # Original document link
    original_bill_line_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bill_lines.id"), nullable=True
    )

    # Return/adjustment reason
    return_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    debit_note: Mapped["DebitNote"] = relationship(back_populates="lines")

    def __repr__(self) -> str:
        return f"<DebitNoteLine {self.item_name or self.item_code} @ {self.rate}>"


class SalesOrderItem(DocumentLineMixin, Base):
    """
    Line item for sales orders.

    Tracks delivery and billing status per item.
    """

    __tablename__ = "sales_order_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Parent link
    sales_order_id: Mapped[int] = mapped_column(
        ForeignKey("sales_orders.id"), nullable=False, index=True
    )

    # Stock/Delivery
    stock_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    stock_uom: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    conversion_factor: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1"))
    warehouse: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    delivered_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Billing
    price_list_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    billed_amt: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # ERPNext reference
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sales_order: Mapped["SalesOrder"] = relationship(back_populates="items")

    def __repr__(self) -> str:
        return f"<SalesOrderItem {self.item_name or self.item_code} @ {self.rate}>"


class QuotationItem(DocumentLineMixin, Base):
    """
    Line item for quotations.

    Tracks quoted prices and validity.
    """

    __tablename__ = "quotation_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Parent link
    quotation_id: Mapped[int] = mapped_column(
        ForeignKey("quotations.id"), nullable=False, index=True
    )

    # Stock
    stock_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    stock_uom: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    conversion_factor: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1"))
    warehouse: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Pricing
    price_list_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    margin_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    margin_rate_or_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))

    # ERPNext reference
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    quotation: Mapped["Quotation"] = relationship(back_populates="items")

    def __repr__(self) -> str:
        return f"<QuotationItem {self.item_name or self.item_code} @ {self.rate}>"


class PurchaseOrderItem(DocumentLineMixin, Base):
    """
    Line item for purchase orders.

    Tracks receipt and billing status per item.
    """

    __tablename__ = "purchase_order_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Parent link
    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id"), nullable=False, index=True
    )

    # Stock/Receipt
    stock_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    stock_uom: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    conversion_factor: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1"))
    warehouse: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    received_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    expected_delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Billing
    price_list_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    billed_amt: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # ERPNext reference
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="items")

    def __repr__(self) -> str:
        return f"<PurchaseOrderItem {self.item_name or self.item_code} @ {self.rate}>"
