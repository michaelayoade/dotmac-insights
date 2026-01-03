"""
Generic Payroll Configuration Models

Provides a country-agnostic framework for payroll configuration:
- PayrollRegion: Country/region-specific payroll settings
- DeductionRule: Configurable deduction/contribution rules
- TaxBand: Progressive tax bracket definitions

Architecture designed for multi-country support. Region codes use ISO 3166-1 alpha-2
(e.g., NG, KE, GH, US) to identify countries.
"""
from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Enum, Index, Numeric, CheckConstraint
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


class CalcMethod(enum.Enum):
    """Calculation method for deduction rules."""
    FLAT = "flat"  # Fixed amount
    PERCENTAGE = "percentage"  # Percentage of base components
    PROGRESSIVE = "progressive"  # Progressive tax bands


class DeductionType(enum.Enum):
    """Type/category of deduction or contribution."""
    TAX = "tax"  # Income tax, PAYE, etc.
    PENSION = "pension"  # Pension contributions
    INSURANCE = "insurance"  # Health insurance, social insurance
    LEVY = "levy"  # Government levies (NHF, ITF, etc.)
    OTHER = "other"  # Other deductions


class PayrollFrequency(enum.Enum):
    """Pay frequency options."""
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    SEMIMONTHLY = "semimonthly"
    MONTHLY = "monthly"


class RuleApplicability(enum.Enum):
    """Who the rule applies to."""
    EMPLOYEE = "employee"  # Employee deduction
    EMPLOYER = "employer"  # Employer contribution
    BOTH = "both"  # Both employee and employer


# ============= PAYROLL REGION =============


class PayrollRegion(Base):
    """
    Country/region-specific payroll configuration.

    Each region defines currency, pay frequency, fiscal year settings,
    and whether statutory calculations require a compliance add-on.
    """

    __tablename__ = "payroll_regions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Region identification
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True)  # ISO 3166-1 alpha-2
    name: Mapped[str] = mapped_column(String(100))
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    # Payroll defaults
    default_pay_frequency: Mapped[PayrollFrequency] = mapped_column(
        Enum(PayrollFrequency), default=PayrollFrequency.MONTHLY
    )
    fiscal_year_start_month: Mapped[int] = mapped_column(default=1)  # 1 = January
    payment_day: Mapped[int] = mapped_column(default=28)  # Day of month for salary payment

    # Statutory configuration
    has_statutory_deductions: Mapped[bool] = mapped_column(default=False)
    requires_compliance_addon: Mapped[bool] = mapped_column(default=False)
    compliance_addon_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # e.g., "NIGERIA_COMPLIANCE", "KENYA_COMPLIANCE"

    # Tax authority info
    tax_authority_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tax_id_label: Mapped[str] = mapped_column(String(50), default="Tax ID")  # "TIN", "SSN", etc.
    tax_id_format: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Regex pattern

    # Filing requirements
    paye_filing_frequency: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # monthly, quarterly
    paye_filing_deadline_day: Mapped[Optional[int]] = mapped_column(nullable=True)  # Day after period end

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    deduction_rules: Mapped[List["DeductionRule"]] = relationship(
        back_populates="region", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PayrollRegion {self.code} ({self.name})>"


# ============= DEDUCTION RULE =============


class DeductionRule(Base):
    """
    Configurable deduction or contribution rule.

    Supports three calculation methods:
    - FLAT: Fixed amount (use flat_amount)
    - PERCENTAGE: Percentage of base components (use rate + base_components)
    - PROGRESSIVE: Progressive tax bands (use linked TaxBand records)

    Rules can be filtered by employment type and service duration.
    """

    __tablename__ = "deduction_rules"
    __table_args__ = (
        Index("ix_deduction_rules_region_code", "region_id", "code"),
        Index("ix_deduction_rules_effective", "region_id", "effective_from", "effective_to"),
        CheckConstraint(
            "(calc_method = 'flat' AND flat_amount IS NOT NULL) OR "
            "(calc_method = 'percentage' AND rate IS NOT NULL) OR "
            "(calc_method = 'progressive')",
            name="ck_deduction_rules_calc_method_values"
        ),
        CheckConstraint(
            "(applicability != 'both') OR "
            "(employee_share IS NOT NULL AND employer_share IS NOT NULL AND "
            "employee_share + employer_share = 1)",
            name="ck_deduction_rules_both_split"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("payroll_regions.id"), index=True)

    # Rule identification
    code: Mapped[str] = mapped_column(String(50), index=True)  # e.g., "PAYE", "PENSION_EE", "NHF"
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deduction_type: Mapped[DeductionType] = mapped_column(Enum(DeductionType), index=True)

    # Applicability
    applicability: Mapped[RuleApplicability] = mapped_column(
        Enum(RuleApplicability), default=RuleApplicability.EMPLOYEE
    )
    is_statutory: Mapped[bool] = mapped_column(default=False)  # Statutory vs custom deduction

    # Calculation method and values
    calc_method: Mapped[CalcMethod] = mapped_column(Enum(CalcMethod))
    rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)  # For PERCENTAGE
    flat_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)  # For FLAT
    employee_share: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), nullable=True)
    employer_share: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), nullable=True)

    # Base components for PERCENTAGE calculation
    # JSON array of component name patterns, e.g., ["basic_salary", "housing_allowance"]
    base_components: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)

    # Thresholds and caps
    min_base: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    max_base: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    cap_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    floor_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)

    # Employment type applicability
    # JSON array of employment types, e.g., ["PERMANENT", "CONTRACT"]
    # null means applies to all types
    employment_types: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)

    # Service requirements
    min_service_months: Mapped[int] = mapped_column(default=0)

    # Validity period
    effective_from: Mapped[date] = mapped_column()
    effective_to: Mapped[Optional[date]] = mapped_column(nullable=True)

    # Filing/remittance info
    statutory_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., "PITA", "PFA2014"
    filing_frequency: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    remittance_deadline_days: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Display order
    display_order: Mapped[int] = mapped_column(default=0)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    region: Mapped["PayrollRegion"] = relationship(back_populates="deduction_rules")
    tax_bands: Mapped[List["TaxBand"]] = relationship(
        back_populates="deduction_rule", cascade="all, delete-orphan", order_by="TaxBand.band_order"
    )

    def __repr__(self) -> str:
        return f"<DeductionRule {self.code} ({self.calc_method.value})>"


# ============= TAX BAND =============


class TaxBand(Base):
    """
    Progressive tax bracket definition.

    Used with DeductionRule.calc_method = PROGRESSIVE.
    Each band defines a range and the rate applied to income within that range.
    """

    __tablename__ = "tax_bands"
    __table_args__ = (
        Index("ix_tax_bands_rule_order", "deduction_rule_id", "band_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    deduction_rule_id: Mapped[int] = mapped_column(ForeignKey("deduction_rules.id"), index=True)

    # Band limits (annual amounts)
    lower_limit: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    upper_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)  # null = unlimited

    # Rate for this band
    rate: Mapped[Decimal] = mapped_column(Numeric(10, 6))  # e.g., 0.07 for 7%

    # Order for calculation
    band_order: Mapped[int] = mapped_column(default=0)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    deduction_rule: Mapped["DeductionRule"] = relationship(back_populates="tax_bands")

    def __repr__(self) -> str:
        upper = f"{self.upper_limit:,.0f}" if self.upper_limit else "unlimited"
        return f"<TaxBand {self.lower_limit:,.0f}-{upper} @ {float(self.rate)*100:.1f}%>"
