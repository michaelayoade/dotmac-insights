from __future__ import annotations

from sqlalchemy import String, Text, Enum, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from typing import List
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
import enum
from app.database import Base, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.document_lines import SalesOrderItem, QuotationItem
    # Forward references for sales FKs (Territory and SalesPerson are defined later in this file)


# ============= SALES ORDER STATUS =============
class SalesOrderStatus(enum.Enum):
    DRAFT = "draft"
    TO_DELIVER_AND_BILL = "to_deliver_and_bill"
    TO_BILL = "to_bill"
    TO_DELIVER = "to_deliver"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    CLOSED = "closed"
    ON_HOLD = "on_hold"


class SalesOrder(Base):
    """Sales orders from ERPNext."""

    __tablename__ = "sales_orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Customer
    customer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True)

    # Order details
    order_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    # Dates
    transaction_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Amounts
    total_qty: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    net_total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    grand_total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    rounded_total: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Taxes
    total_taxes_and_charges: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Billing/Delivery status
    per_delivered: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    per_billed: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    billing_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    delivery_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Status
    status: Mapped[SalesOrderStatus] = mapped_column(Enum(SalesOrderStatus), default=SalesOrderStatus.DRAFT, index=True)
    docstatus: Mapped[int] = mapped_column(default=0)

    # Sales team (TEXT fields for ERPNext sync)
    sales_partner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    territory: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Sales team FKs (for local queries)
    sales_partner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sales_persons.id"), nullable=True, index=True
    )
    territory_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("territories.id"), nullable=True, index=True
    )

    # Source
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    campaign: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    items: Mapped[List["SalesOrderItem"]] = relationship(
        back_populates="sales_order", cascade="all, delete-orphan"
    )
    sales_partner_rel: Mapped[Optional["SalesPerson"]] = relationship(
        "SalesPerson",
        foreign_keys=[sales_partner_id],
        backref="sales_orders"
    )
    territory_rel: Mapped[Optional["Territory"]] = relationship(
        "Territory",
        foreign_keys=[territory_id],
        backref="sales_orders"
    )

    def __repr__(self) -> str:
        return f"<SalesOrder {self.erpnext_id} - {self.customer_name}>"


# ============= QUOTATION STATUS =============
class QuotationStatus(enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    REPLIED = "replied"
    ORDERED = "ordered"
    LOST = "lost"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Quotation(SoftDeleteMixin, Base):
    """Price quotations from ERPNext."""

    __tablename__ = "quotations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Party
    quotation_to: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Customer or Lead
    party_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Order details
    order_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    # Dates
    transaction_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    valid_till: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Amounts
    total_qty: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    net_total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    grand_total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    rounded_total: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Taxes
    total_taxes_and_charges: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Status
    status: Mapped[QuotationStatus] = mapped_column(Enum(QuotationStatus), default=QuotationStatus.DRAFT, index=True)
    docstatus: Mapped[int] = mapped_column(default=0)

    # Sales team (TEXT fields for ERPNext sync)
    sales_partner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    territory: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Sales team FKs (for local queries)
    sales_partner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sales_persons.id"), nullable=True, index=True
    )
    territory_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("territories.id"), nullable=True, index=True
    )

    # Source
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    campaign: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Conversion
    order_lost_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    items: Mapped[List["QuotationItem"]] = relationship(
        back_populates="quotation", cascade="all, delete-orphan"
    )
    sales_partner_rel: Mapped[Optional["SalesPerson"]] = relationship(
        "SalesPerson",
        foreign_keys=[sales_partner_id],
        backref="quotations"
    )
    territory_rel: Mapped[Optional["Territory"]] = relationship(
        "Territory",
        foreign_keys=[territory_id],
        backref="quotations"
    )

    def __repr__(self) -> str:
        return f"<Quotation {self.erpnext_id} - {self.party_name}>"


# ============= LEAD STATUS =============
class ERPNextLeadStatus(enum.Enum):
    LEAD = "lead"
    OPEN = "open"
    REPLIED = "replied"
    OPPORTUNITY = "opportunity"
    QUOTATION = "quotation"
    LOST_QUOTATION = "lost_quotation"
    INTERESTED = "interested"
    CONVERTED = "converted"
    DO_NOT_CONTACT = "do_not_contact"


class ERPNextLead(Base):
    """Sales leads from ERPNext CRM."""

    __tablename__ = "erpnext_leads"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Lead info
    lead_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Contact
    email_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    mobile_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Classification
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    lead_owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    territory: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    market_segment: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status
    status: Mapped[ERPNextLeadStatus] = mapped_column(Enum(ERPNextLeadStatus), default=ERPNextLeadStatus.LEAD)
    qualification_status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Address
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Conversion tracking
    converted: Mapped[bool] = mapped_column(default=False)
    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ERPNextLead {self.lead_name}>"


# ============= ITEM (PRODUCT/SERVICE) =============
class Item(Base):
    """Products/Services from ERPNext."""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Item info
    item_code: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    item_group: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Description
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Type
    is_stock_item: Mapped[bool] = mapped_column(default=True)
    is_fixed_asset: Mapped[bool] = mapped_column(default=False)
    is_sales_item: Mapped[bool] = mapped_column(default=True)
    is_purchase_item: Mapped[bool] = mapped_column(default=True)

    # Stock
    stock_uom: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    default_warehouse: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Pricing
    standard_rate: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    valuation_rate: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # GL Accounts for inventory posting
    stock_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Inventory asset account
    expense_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # COGS account
    income_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Revenue account

    # Reorder settings
    reorder_level: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    reorder_qty: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    safety_stock: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Batch/Serial tracking
    has_batch_no: Mapped[bool] = mapped_column(default=False)
    has_serial_no: Mapped[bool] = mapped_column(default=False)

    # Status
    disabled: Mapped[bool] = mapped_column(default=False)
    has_variants: Mapped[bool] = mapped_column(default=False)
    variant_of: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Item {self.item_code} - {self.item_name}>"


# ============= CUSTOMER GROUP =============
class CustomerGroup(Base):
    """Customer groups/categories from ERPNext."""

    __tablename__ = "customer_groups"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    customer_group_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    parent_customer_group: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    is_group: Mapped[bool] = mapped_column(default=False)
    default_price_list: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    default_payment_terms_template: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Tree structure
    lft: Mapped[Optional[int]] = mapped_column(nullable=True)
    rgt: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<CustomerGroup {self.customer_group_name}>"


# ============= TERRITORY =============
class Territory(Base):
    """Sales territories from ERPNext."""

    __tablename__ = "territories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    territory_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    parent_territory: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    is_group: Mapped[bool] = mapped_column(default=False)
    territory_manager: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Tree structure
    lft: Mapped[Optional[int]] = mapped_column(nullable=True)
    rgt: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Territory {self.territory_name}>"


# ============= SALES PERSON =============
class SalesPerson(Base):
    """Sales team members from ERPNext."""

    __tablename__ = "sales_persons"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    sales_person_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    parent_sales_person: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    is_group: Mapped[bool] = mapped_column(default=False)
    employee: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # FK to Employee
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)

    enabled: Mapped[bool] = mapped_column(default=True)

    # Commission
    commission_rate: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Tree structure
    lft: Mapped[Optional[int]] = mapped_column(nullable=True)
    rgt: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    employee_rel: Mapped[Optional["Employee"]] = relationship()

    def __repr__(self) -> str:
        return f"<SalesPerson {self.sales_person_name}>"


# ============= ITEM GROUP =============
class ItemGroup(Base):
    """Product categories from ERPNext."""

    __tablename__ = "item_groups"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    item_group_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    parent_item_group: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    is_group: Mapped[bool] = mapped_column(default=False)

    # Tree structure
    lft: Mapped[Optional[int]] = mapped_column(nullable=True)
    rgt: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ItemGroup {self.item_group_name}>"
