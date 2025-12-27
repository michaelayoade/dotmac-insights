"""
Generic Tax Configuration Models

Provides a country-agnostic framework for tax configuration:
- TaxRegion: Country/region-specific tax settings
- TaxCategory: Tax types (VAT, sales tax, WHT, income tax)
- TaxRate: Rate definitions with validity periods
- TaxTransaction: Generic tax transaction ledger

Architecture designed for multi-country support. Region codes use ISO 3166-1 alpha-2
(e.g., NG, KE, GH, US) to identify countries.
"""
from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Enum, Index, Numeric, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.auth import User


# ============= ENUMS =============


class TaxCategoryType(enum.Enum):
    """High-level tax category classification."""
    SALES_TAX = "sales_tax"  # VAT, GST, sales tax
    WITHHOLDING = "withholding"  # WHT deducted at source
    INCOME_TAX = "income_tax"  # PAYE, corporate income tax
    EXCISE = "excise"  # Excise duties
    CUSTOMS = "customs"  # Import/export duties
    STAMP_DUTY = "stamp_duty"  # Stamp duties
    OTHER = "other"


class TaxTransactionType(enum.Enum):
    """Direction of tax transaction."""
    OUTPUT = "output"  # Tax collected (e.g., VAT on sales)
    INPUT = "input"  # Tax paid (e.g., VAT on purchases)
    WITHHOLDING = "withholding"  # Tax withheld at source
    REMITTANCE = "remittance"  # Tax payment to authority


class TaxFilingFrequency(enum.Enum):
    """Tax filing frequency options."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"


class TaxTransactionStatus(enum.Enum):
    """Status of a tax transaction."""
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    FILED = "filed"
    PAID = "paid"
    VOID = "void"


# ============= TAX REGION =============


class TaxRegion(Base):
    """
    Country/region-specific tax configuration.

    Defines tax authority info, filing requirements, and
    whether the region requires a compliance add-on.
    """

    __tablename__ = "tax_regions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Region identification (links to PayrollRegion if exists)
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True)  # ISO 3166-1 alpha-2
    name: Mapped[str] = mapped_column(String(100))
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    # Tax authority info
    tax_authority_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tax_authority_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tax_id_label: Mapped[str] = mapped_column(String(50), default="Tax ID")  # "TIN", "VAT Number", etc.
    tax_id_format: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Regex pattern

    # Default rates
    default_sales_tax_rate: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0"))
    default_withholding_rate: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0"))

    # Filing configuration
    default_filing_frequency: Mapped[TaxFilingFrequency] = mapped_column(
        Enum(TaxFilingFrequency), default=TaxFilingFrequency.MONTHLY
    )
    filing_deadline_day: Mapped[int] = mapped_column(default=21)  # Day of month after period

    # Fiscal year
    fiscal_year_start_month: Mapped[int] = mapped_column(default=1)

    # Compliance add-on requirement
    requires_compliance_addon: Mapped[bool] = mapped_column(default=False)
    compliance_addon_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # e.g., "NIGERIA_COMPLIANCE", "KENYA_COMPLIANCE"

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    categories: Mapped[List["GenericTaxCategory"]] = relationship(
        back_populates="region", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TaxRegion {self.code} ({self.name})>"


# ============= TAX CATEGORY =============


class GenericTaxCategory(Base):
    """
    Tax category definition (VAT, WHT, etc.) for a region.

    Each category defines the tax type, default rate, and
    whether input credits are recoverable.
    """

    __tablename__ = "generic_tax_categories"
    __table_args__ = (
        UniqueConstraint("region_id", "code", name="uq_generic_tax_categories_region_code"),
        Index("ix_generic_tax_categories_region", "region_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("tax_regions.id"), index=True)

    # Category identification
    code: Mapped[str] = mapped_column(String(50), index=True)  # e.g., "VAT", "WHT", "SALES_TAX"
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category_type: Mapped[TaxCategoryType] = mapped_column(Enum(TaxCategoryType), index=True)

    # Default rate
    default_rate: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0"))

    # Behavior flags
    is_recoverable: Mapped[bool] = mapped_column(default=True)  # Can claim input credits
    is_inclusive: Mapped[bool] = mapped_column(default=False)  # Price includes tax
    applies_to_purchases: Mapped[bool] = mapped_column(default=True)
    applies_to_sales: Mapped[bool] = mapped_column(default=True)

    # Filing configuration
    filing_frequency: Mapped[Optional[TaxFilingFrequency]] = mapped_column(
        Enum(TaxFilingFrequency), nullable=True
    )
    filing_deadline_day: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Accounting
    output_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    input_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Display order
    display_order: Mapped[int] = mapped_column(default=0)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    region: Mapped["TaxRegion"] = relationship(back_populates="categories")
    rates: Mapped[List["TaxRate"]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TaxCategory {self.code} @ {float(self.default_rate)*100:.2f}%>"


# ============= TAX RATE =============


class TaxRate(Base):
    """
    Tax rate definition with validity period.

    Allows for rate changes over time without modifying
    the base category configuration.
    """

    __tablename__ = "tax_rates"
    __table_args__ = (
        Index("ix_tax_rates_category_effective", "category_id", "effective_from", "effective_to"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("generic_tax_categories.id"), index=True)

    # Rate definition
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Sub-rate code if applicable
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(10, 6))

    # Conditions (JSON for flexibility)
    # e.g., {"payment_type": "dividend"} for WHT rates
    conditions: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Thresholds
    min_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    max_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)

    # Validity period
    effective_from: Mapped[date] = mapped_column()
    effective_to: Mapped[Optional[date]] = mapped_column(nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    category: Mapped["GenericTaxCategory"] = relationship(back_populates="rates")

    def __repr__(self) -> str:
        return f"<TaxRate {self.code or 'default'} @ {float(self.rate)*100:.2f}%>"


# ============= TAX TRANSACTION =============


class TaxTransaction(Base):
    """
    Generic tax transaction ledger.

    Records all tax-related transactions (output VAT, input VAT,
    WHT deductions, etc.) for reporting and filing.
    """

    __tablename__ = "tax_transactions"
    __table_args__ = (
        Index("ix_tax_transactions_period", "region_id", "filing_period"),
        Index("ix_tax_transactions_company_period", "company", "filing_period"),
        Index("ix_tax_transactions_source", "source_doctype", "source_docname"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("tax_regions.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("generic_tax_categories.id"), index=True)

    # Transaction identification
    reference_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    transaction_type: Mapped[TaxTransactionType] = mapped_column(Enum(TaxTransactionType), index=True)
    transaction_date: Mapped[date] = mapped_column(index=True)

    # Company
    company: Mapped[str] = mapped_column(String(255), index=True)

    # Party (customer/supplier)
    party_type: Mapped[str] = mapped_column(String(50))  # customer, supplier
    party_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    party_name: Mapped[str] = mapped_column(String(255))
    party_tax_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Amounts
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    # Exchange rate for multi-currency
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("1"))
    base_tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))  # In company currency

    # Filing period (YYYY-MM format)
    filing_period: Mapped[str] = mapped_column(String(10), index=True)

    # Status
    status: Mapped[TaxTransactionStatus] = mapped_column(
        Enum(TaxTransactionStatus), default=TaxTransactionStatus.DRAFT, index=True
    )
    is_exempt: Mapped[bool] = mapped_column(default=False)
    is_zero_rated: Mapped[bool] = mapped_column(default=False)
    exemption_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Source document reference
    source_doctype: Mapped[str] = mapped_column(String(50))  # invoice, bill, payment, etc.
    source_docname: Mapped[str] = mapped_column(String(255))  # Document ID or number

    # Filing tracking
    filed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    filed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    filing_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Metadata for extensibility
    meta: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<TaxTransaction {self.reference_number} {self.transaction_type.value} {self.tax_amount}>"


# ============= COMPANY TAX SETTINGS =============


class CompanyTaxSettings(Base):
    """
    Company-specific tax configuration.

    Links a company to a tax region and stores company-specific
    tax identifiers and preferences.
    """

    __tablename__ = "company_tax_settings"
    __table_args__ = (
        UniqueConstraint("company", "region_id", name="uq_company_tax_settings"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("tax_regions.id"), index=True)

    # Company reference
    company: Mapped[str] = mapped_column(String(255), index=True)

    # Tax identification
    tax_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    vat_registration_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    registration_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Filing preferences
    filing_frequency: Mapped[Optional[TaxFilingFrequency]] = mapped_column(
        Enum(TaxFilingFrequency), nullable=True
    )

    # Status flags
    is_registered: Mapped[bool] = mapped_column(default=True)
    is_withholding_agent: Mapped[bool] = mapped_column(default=False)

    # Fiscal year (if different from region default)
    fiscal_year_start_month: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<CompanyTaxSettings {self.company} region={self.region_id}>"
