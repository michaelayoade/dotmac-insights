from __future__ import annotations

import enum
from sqlalchemy import String, Text, ForeignKey, Numeric, Date, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from app.database import Base


# ============= TAX CATEGORY =============
class TaxCategory(Base):
    """Tax categories from ERPNext for VAT classification."""

    __tablename__ = "tax_categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    category_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Classification
    is_inter_state: Mapped[bool] = mapped_column(default=False)
    is_reverse_charge: Mapped[bool] = mapped_column(default=False)
    disabled: Mapped[bool] = mapped_column(default=False)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<TaxCategory {self.category_name}>"


# ============= SALES TAX TEMPLATE =============
class SalesTaxTemplate(Base):
    """Sales Taxes and Charges Template from ERPNext."""

    __tablename__ = "sales_tax_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    template_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Tax settings
    tax_category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    is_default: Mapped[bool] = mapped_column(default=False)
    disabled: Mapped[bool] = mapped_column(default=False)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to detail rows
    taxes: Mapped[List["SalesTaxTemplateDetail"]] = relationship(
        back_populates="template", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<SalesTaxTemplate {self.template_name}>"


class SalesTaxTemplateDetail(Base):
    """Individual tax lines within a Sales Tax Template."""

    __tablename__ = "sales_tax_template_details"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("sales_tax_templates.id"), nullable=False, index=True)

    # Tax details
    charge_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    account_head: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))

    # Row and cost center
    row_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    cost_center: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    included_in_print_rate: Mapped[bool] = mapped_column(default=False)

    # Ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationship
    template: Mapped["SalesTaxTemplate"] = relationship(back_populates="taxes")

    def __repr__(self) -> str:
        return f"<SalesTaxTemplateDetail {self.account_head} @ {self.rate}%>"


# ============= PURCHASE TAX TEMPLATE =============
class PurchaseTaxTemplate(Base):
    """Purchase Taxes and Charges Template from ERPNext."""

    __tablename__ = "purchase_tax_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    template_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Tax settings
    tax_category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    is_default: Mapped[bool] = mapped_column(default=False)
    disabled: Mapped[bool] = mapped_column(default=False)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to detail rows
    taxes: Mapped[List["PurchaseTaxTemplateDetail"]] = relationship(
        back_populates="template", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PurchaseTaxTemplate {self.template_name}>"


class PurchaseTaxTemplateDetail(Base):
    """Individual tax lines within a Purchase Tax Template."""

    __tablename__ = "purchase_tax_template_details"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("purchase_tax_templates.id"), nullable=False, index=True)

    # Tax details
    charge_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    account_head: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))

    # Row and cost center
    row_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    cost_center: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    add_deduct_tax: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    included_in_print_rate: Mapped[bool] = mapped_column(default=False)

    # Ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationship
    template: Mapped["PurchaseTaxTemplate"] = relationship(back_populates="taxes")

    def __repr__(self) -> str:
        return f"<PurchaseTaxTemplateDetail {self.account_head} @ {self.rate}%>"


# ============= ITEM TAX TEMPLATE =============
class ItemTaxTemplate(Base):
    """Item-specific tax templates from ERPNext."""

    __tablename__ = "item_tax_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    template_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    disabled: Mapped[bool] = mapped_column(default=False)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to detail rows
    taxes: Mapped[List["ItemTaxTemplateDetail"]] = relationship(
        back_populates="template", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ItemTaxTemplate {self.template_name}>"


class ItemTaxTemplateDetail(Base):
    """Tax rates per account within an Item Tax Template."""

    __tablename__ = "item_tax_template_details"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("item_tax_templates.id"), nullable=False, index=True)

    # Tax type is the account (e.g., "VAT - Company")
    tax_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))

    # Ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationship
    template: Mapped["ItemTaxTemplate"] = relationship(back_populates="taxes")

    def __repr__(self) -> str:
        return f"<ItemTaxTemplateDetail {self.tax_type} @ {self.tax_rate}%>"


# ============= TAX WITHHOLDING CATEGORY =============
class TaxWithholdingCategory(Base):
    """Tax Withholding Categories from ERPNext."""

    __tablename__ = "tax_withholding_categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    category_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Withholding settings
    round_off_tax_amount: Mapped[bool] = mapped_column(default=False)
    consider_party_ledger_amount: Mapped[bool] = mapped_column(default=False)

    # Account for TDS postings
    account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<TaxWithholdingCategory {self.category_name}>"


# ============= TAX RULE =============
class TaxRule(Base):
    """Tax Rules from ERPNext for automatic tax application."""

    __tablename__ = "tax_rules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Rule identification
    rule_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tax_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # "Sales" or "Purchase"

    # Templates to apply
    sales_tax_template: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    purchase_tax_template: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Tax classification
    tax_category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Party filters
    customer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    supplier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_group: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    supplier_group: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Geographic conditions - billing
    billing_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    billing_state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    billing_country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    billing_zipcode: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Geographic conditions - shipping
    shipping_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    shipping_state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    shipping_country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    shipping_zipcode: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Item conditions
    item: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    item_group: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Company scope
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Priority for rule matching
    priority: Mapped[int] = mapped_column(default=1)
    use_for_shopping_cart: Mapped[bool] = mapped_column(default=False)

    # From/To dates for validity
    from_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    to_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<TaxRule {self.erpnext_id} - {self.tax_type}>"


# ============= TAX FILING =============
class TaxFilingStatus(enum.Enum):
    """Status of tax filing period."""
    OPEN = "open"
    FILED = "filed"
    PAID = "paid"
    CLOSED = "closed"


class TaxFilingType(enum.Enum):
    """Type of tax."""
    VAT = "vat"
    WHT = "wht"  # Withholding Tax
    CIT = "cit"  # Corporate Income Tax
    PAYE = "paye"  # Pay As You Earn
    OTHER = "other"


class TaxFilingPeriod(Base):
    """Tax filing period for tracking tax obligations and payments."""

    __tablename__ = "tax_filing_periods"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Period details
    tax_type: Mapped[TaxFilingType] = mapped_column(Enum(TaxFilingType), index=True)
    period_name: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "2024-Q1", "2024-01"
    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Status tracking
    status: Mapped[TaxFilingStatus] = mapped_column(
        Enum(TaxFilingStatus), default=TaxFilingStatus.OPEN, index=True
    )

    # Calculated amounts
    tax_base: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))

    # Filing details
    filed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    filed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    filing_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Company scope
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<TaxFilingPeriod {self.tax_type.value} {self.period_name}>"

    @property
    def outstanding_amount(self) -> Decimal:
        return self.tax_amount - self.amount_paid

    @property
    def is_overdue(self) -> bool:
        return self.status == TaxFilingStatus.OPEN and date.today() > self.due_date


class TaxPayment(Base):
    """Record of tax payment made for a filing period."""

    __tablename__ = "tax_payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Link to filing period
    filing_period_id: Mapped[int] = mapped_column(ForeignKey("tax_filing_periods.id"), nullable=False, index=True)

    # Payment details
    payment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    payment_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Bank details
    bank_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<TaxPayment {self.amount} on {self.payment_date}>"
