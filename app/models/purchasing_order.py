"""Purchase Order model for vendor purchase orders."""
from __future__ import annotations

from sqlalchemy import String, Text, Enum, Date, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.document_lines import PurchaseOrderItem
    from app.models.accounting import CostCenter
    from app.models.project import Project


class PurchaseOrderStatus(enum.Enum):
    DRAFT = "draft"
    TO_RECEIVE_AND_BILL = "to_receive_and_bill"
    TO_BILL = "to_bill"
    TO_RECEIVE = "to_receive"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    CLOSED = "closed"
    ON_HOLD = "on_hold"


class PurchaseOrder(Base):
    """Purchase orders from ERPNext."""

    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Supplier
    supplier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    supplier_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("suppliers.id"), nullable=True)

    # Order details
    order_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    # Dates
    transaction_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    schedule_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Amounts
    total_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    net_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    grand_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    rounded_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # Taxes
    total_taxes_and_charges: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # Receipt/Billing status
    per_received: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    per_billed: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    billing_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    receipt_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Status
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        Enum(PurchaseOrderStatus), default=PurchaseOrderStatus.DRAFT, index=True
    )
    docstatus: Mapped[int] = mapped_column(default=0)

    # Buying team (TEXT fields for ERPNext sync)
    buying_price_list: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cost_center: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    project: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Buying team FKs (for local queries)
    cost_center_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cost_centers.id"), nullable=True, index=True
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )

    # Terms
    payment_terms_template: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    terms: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    items: Mapped[List["PurchaseOrderItem"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )
    cost_center_rel: Mapped[Optional["CostCenter"]] = relationship(
        "CostCenter",
        foreign_keys=[cost_center_id],
        backref="purchase_orders"
    )
    project_rel: Mapped[Optional["Project"]] = relationship(
        "Project",
        foreign_keys=[project_id],
        backref="purchase_orders"
    )

    def __repr__(self) -> str:
        return f"<PurchaseOrder {self.erpnext_id} - {self.supplier_name}>"
