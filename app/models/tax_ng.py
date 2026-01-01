"""
Nigerian Tax Administration Models

Implements Nigerian-specific tax compliance models for:
- VAT (Value Added Tax) - 7.5%
- WHT (Withholding Tax) - Variable rates
- CIT (Company Income Tax) - 0-30% progressive
- PAYE (Pay As You Earn) - 7-24% progressive bands
- E-Invoicing (FIRS BIS 3.0 UBL format)
"""

from __future__ import annotations

import enum
from sqlalchemy import String, Text, ForeignKey, Numeric, Date, Enum, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from app.database import Base


# ============= ENUMS =============

class NigerianTaxType(enum.Enum):
    """Nigerian tax types."""
    VAT = "vat"           # Value Added Tax - 7.5%
    WHT = "wht"           # Withholding Tax - Variable
    CIT = "cit"           # Company Income Tax - 0-30%
    PAYE = "paye"         # Pay As You Earn - 7-24%
    TET = "tet"           # Tertiary Education Tax - 3%
    EDT = "edt"           # Education Development Tax
    CGT = "cgt"           # Capital Gains Tax - 10%
    STAMP_DUTY = "stamp_duty"  # Stamp Duties


class TaxJurisdiction(enum.Enum):
    """Tax jurisdiction - determines remittance authority."""
    FEDERAL = "federal"   # FIRS - Federal Inland Revenue Service
    STATE = "state"       # SIRS - State Internal Revenue Service


class WHTPaymentType(enum.Enum):
    """Withholding tax payment types with different rates."""
    DIVIDEND = "dividend"           # 10%
    INTEREST = "interest"           # 10%
    RENT = "rent"                   # 10%
    ROYALTY = "royalty"             # 10%
    COMMISSION = "commission"       # 10%
    CONSULTANCY = "consultancy"     # 10%
    TECHNICAL_SERVICE = "technical_service"  # 10%
    MANAGEMENT_FEE = "management_fee"        # 10%
    DIRECTOR_FEE = "director_fee"   # 10%
    CONTRACT = "contract"           # 5%
    SUPPLY = "supply"               # 5% (corporate) / 2% (individual)
    CONSTRUCTION = "construction"   # 5%
    PROFESSIONAL_FEE = "professional_fee"    # 5%
    HIRE_OF_EQUIPMENT = "hire_of_equipment"  # 10%
    ALL_ASPECTS_CONTRACT = "all_aspects"     # 2.5%


class CITCompanySize(enum.Enum):
    """Company size classification for CIT rates."""
    SMALL = "small"       # Turnover <= N25M, 0% rate
    MEDIUM = "medium"     # N25M < Turnover <= N100M, 20% rate
    LARGE = "large"       # Turnover > N100M, 30% rate


class VATTransactionType(enum.Enum):
    """VAT transaction direction."""
    OUTPUT = "output"     # VAT collected on sales
    INPUT = "input"       # VAT paid on purchases


class EInvoiceStatus(enum.Enum):
    """E-invoice lifecycle status for FIRS compliance."""
    DRAFT = "draft"
    VALIDATED = "validated"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class PAYEFilingFrequency(enum.Enum):
    """PAYE filing frequency."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


# ============= TAX SETTINGS =============

class TaxSettings(Base):
    """
    Company-level Nigerian tax configuration.

    Stores TIN, VAT registration, jurisdiction preferences,
    and thresholds for tax calculations.
    """

    __tablename__ = "ng_tax_settings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Company reference
    company: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    # Tax Identification
    tin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # Federal TIN
    vat_registration_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    cac_registration_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # State tax registration (for PAYE, etc.)
    state_tin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    state_of_residence: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Jurisdiction configuration
    default_jurisdiction: Mapped[TaxJurisdiction] = mapped_column(
        Enum(TaxJurisdiction), default=TaxJurisdiction.FEDERAL
    )

    # Company size classification (affects CIT rate)
    company_size: Mapped[CITCompanySize] = mapped_column(
        Enum(CITCompanySize), default=CITCompanySize.MEDIUM
    )
    annual_turnover: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))

    # VAT settings
    vat_registered: Mapped[bool] = mapped_column(default=True)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.0750"))  # 7.5%
    vat_filing_frequency: Mapped[str] = mapped_column(String(20), default="monthly")

    # WHT settings
    is_wht_agent: Mapped[bool] = mapped_column(default=True)  # Authorized to deduct WHT
    apply_tin_penalty: Mapped[bool] = mapped_column(default=True)  # 2x rate for no TIN

    # E-invoicing settings
    einvoice_enabled: Mapped[bool] = mapped_column(default=False)
    einvoice_threshold: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("50000")  # B2C threshold
    )

    # PAYE settings
    paye_filing_frequency: Mapped[PAYEFilingFrequency] = mapped_column(
        Enum(PAYEFilingFrequency), default=PAYEFilingFrequency.MONTHLY
    )

    # Fiscal year settings
    fiscal_year_start_month: Mapped[int] = mapped_column(default=1)  # January

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<TaxSettings {self.company} TIN:{self.tin}>"


# ============= TAX RATES =============

class NigerianTaxRate(Base):
    """
    Historical Nigerian tax rates with effective dates.

    Allows rate changes over time while maintaining audit trail.
    """

    __tablename__ = "ng_tax_rates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Tax classification
    tax_type: Mapped[NigerianTaxType] = mapped_column(Enum(NigerianTaxType), nullable=False, index=True)

    # For WHT, specify the payment type
    wht_payment_type: Mapped[Optional[WHTPaymentType]] = mapped_column(
        Enum(WHTPaymentType), nullable=True, index=True
    )

    # Rate details
    rate: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)  # e.g., 0.075000 for 7.5%
    rate_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Applicability
    is_corporate: Mapped[bool] = mapped_column(default=True)  # Corporate rate
    is_individual: Mapped[bool] = mapped_column(default=False)  # Individual rate

    # Thresholds (for CIT bands)
    min_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    max_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)

    # Validity period
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Jurisdiction
    jurisdiction: Mapped[TaxJurisdiction] = mapped_column(
        Enum(TaxJurisdiction), default=TaxJurisdiction.FEDERAL
    )

    # Status
    is_active: Mapped[bool] = mapped_column(default=True, index=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<NigerianTaxRate {self.tax_type.value} {self.rate*100:.2f}%>"

    @property
    def is_current(self) -> bool:
        """Check if rate is currently in effect."""
        today = date.today()
        if today < self.effective_from:
            return False
        if self.effective_to and today > self.effective_to:
            return False
        return self.is_active


# ============= VAT TRANSACTIONS =============

class VATTransaction(Base):
    """
    VAT ledger entry for input/output VAT tracking.

    Records individual VAT transactions for return preparation.
    """

    __tablename__ = "ng_vat_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Transaction identification
    reference_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)

    # Transaction type
    transaction_type: Mapped[VATTransactionType] = mapped_column(
        Enum(VATTransactionType), nullable=False, index=True
    )

    # Date
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Party details
    party_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "customer" or "supplier"
    party_id: Mapped[Optional[int]] = mapped_column(nullable=True, index=True)
    party_name: Mapped[str] = mapped_column(String(255), nullable=False)
    party_tin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    party_vat_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Source document
    source_doctype: Mapped[str] = mapped_column(String(50), nullable=False)  # invoice, credit_note, etc.
    source_docname: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Amounts
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.0750"))
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Currency
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1"))

    # Period for filing
    filing_period: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # "2024-01"

    # Filing status
    is_filed: Mapped[bool] = mapped_column(default=False, index=True)
    filed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    filing_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # VAT classification
    is_exempt: Mapped[bool] = mapped_column(default=False)
    is_zero_rated: Mapped[bool] = mapped_column(default=False)
    exemption_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Company scope
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<VATTransaction {self.reference_number} {self.transaction_type.value} {self.vat_amount}>"


# ============= WHT TRANSACTIONS =============

class WHTTransaction(Base):
    """
    Withholding Tax transaction record.

    Tracks WHT deductions from payments to suppliers.
    """

    __tablename__ = "ng_wht_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Transaction identification
    reference_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)

    # Transaction date
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Payment type determines rate
    payment_type: Mapped[WHTPaymentType] = mapped_column(
        Enum(WHTPaymentType), nullable=False, index=True
    )

    # Supplier details
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("suppliers.id"), nullable=True, index=True)
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    supplier_tin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    supplier_is_corporate: Mapped[bool] = mapped_column(default=True)

    # TIN validation
    has_valid_tin: Mapped[bool] = mapped_column(default=True)  # False triggers 2x rate

    # Source document
    source_doctype: Mapped[str] = mapped_column(String(50), nullable=False)
    source_docname: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Amounts
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    wht_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)  # Actual rate applied
    standard_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)  # Base rate
    wht_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Currency
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1"))

    # Jurisdiction - determines remittance deadline
    jurisdiction: Mapped[TaxJurisdiction] = mapped_column(
        Enum(TaxJurisdiction), default=TaxJurisdiction.FEDERAL
    )

    # Remittance tracking
    remittance_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_remitted: Mapped[bool] = mapped_column(default=False, index=True)
    remitted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    remittance_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Certificate tracking
    certificate_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ng_wht_certificates.id"), nullable=True, index=True
    )

    # Company scope
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<WHTTransaction {self.reference_number} {self.payment_type.value} {self.wht_amount}>"


# ============= WHT CERTIFICATES =============

class WHTCertificate(Base):
    """
    Withholding Tax Credit Certificate.

    Generated for suppliers to claim WHT credits.
    """

    __tablename__ = "ng_wht_certificates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Certificate number
    certificate_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)

    # Issue details
    issue_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    valid_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Beneficiary (supplier)
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("suppliers.id"), nullable=True, index=True)
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    supplier_tin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    supplier_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Tax period covered
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    # Amounts
    total_gross_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_wht_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Transaction count
    transaction_count: Mapped[int] = mapped_column(default=0)

    # Status
    is_issued: Mapped[bool] = mapped_column(default=False)
    issued_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    issued_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    is_cancelled: Mapped[bool] = mapped_column(default=False)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Deducting company details
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company_tin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    company_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    transactions: Mapped[List["WHTTransaction"]] = relationship(
        back_populates="certificate", foreign_keys="WHTTransaction.certificate_id"
    )

    def __repr__(self) -> str:
        return f"<WHTCertificate {self.certificate_number} {self.total_wht_amount}>"


# Add back reference to WHTTransaction
WHTTransaction.certificate = relationship("WHTCertificate", back_populates="transactions")


# ============= PAYE CALCULATIONS =============

class PAYECalculation(Base):
    """
    PAYE calculation for employee payroll.

    Implements Nigerian progressive tax bands with CRA relief.
    """

    __tablename__ = "ng_paye_calculations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Employee reference
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    employee_name: Mapped[str] = mapped_column(String(255), nullable=False)
    employee_tin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Period
    payroll_period: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # "2024-01"
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    # Gross income components
    basic_salary: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    housing_allowance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    transport_allowance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    other_allowances: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    bonus: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    gross_income: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Annual equivalents (for progressive calculation)
    annual_gross_income: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Consolidated Relief Allowance (CRA)
    cra_fixed: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)  # N200,000 or 1% of gross
    cra_percentage: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)  # 20% of gross
    total_cra: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Other reliefs
    pension_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))  # 8% employee
    nhf_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))  # 2.5%
    nhis_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    life_assurance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    other_reliefs: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    total_reliefs: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Taxable income
    annual_taxable_income: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Tax calculation by bands (stored as JSON for auditability)
    tax_bands_breakdown: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Computed tax
    annual_tax: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    monthly_tax: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Effective rate
    effective_rate: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)

    # Filing status
    is_filed: Mapped[bool] = mapped_column(default=False, index=True)
    filed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # State remittance
    state_of_residence: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Company scope
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<PAYECalculation {self.employee_name} {self.payroll_period} {self.monthly_tax}>"


# ============= CIT ASSESSMENTS =============

class CITAssessment(Base):
    """
    Company Income Tax assessment record.

    Tracks annual CIT computation including TET (Tertiary Education Tax).
    """

    __tablename__ = "ng_cit_assessments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Assessment identification
    assessment_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)

    # Fiscal year
    fiscal_year: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # "2024"
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    # Company classification
    company_size: Mapped[CITCompanySize] = mapped_column(Enum(CITCompanySize), nullable=False)

    # Gross revenue
    gross_turnover: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    gross_profit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Adjustments
    disallowed_expenses: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    capital_allowances: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    loss_brought_forward: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    investment_allowances: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))

    # Assessable profit
    adjusted_profit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    assessable_profit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Tax computation
    cit_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    cit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Tertiary Education Tax (TET) - 3% of assessable profit
    tet_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.03"))
    tet_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Minimum tax (where applicable)
    minimum_tax: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    is_minimum_tax_applicable: Mapped[bool] = mapped_column(default=False)

    # Total tax liability
    total_tax_liability: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Payment tracking
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    balance_due: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Filing status
    is_self_assessment: Mapped[bool] = mapped_column(default=True)
    is_filed: Mapped[bool] = mapped_column(default=False, index=True)
    filed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Company scope
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company_tin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<CITAssessment {self.assessment_number} {self.fiscal_year} {self.total_tax_liability}>"


# ============= E-INVOICING =============

class EInvoice(Base):
    """
    FIRS E-Invoice for BIS 3.0 UBL compliance.

    Stores 55 mandatory fields required for electronic invoicing.
    """

    __tablename__ = "ng_einvoices"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # UBL Header fields
    ubl_version_id: Mapped[str] = mapped_column(String(10), default="2.1")
    customization_id: Mapped[str] = mapped_column(String(100), default="urn:firs.gov.ng:einvoice:1.0")
    profile_id: Mapped[str] = mapped_column(String(100), default="urn:firs.gov.ng:profile:bis:billing:3.0")

    # Invoice identification
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    uuid: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    issue_time: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Invoice type
    invoice_type_code: Mapped[str] = mapped_column(String(10), default="380")  # Commercial invoice

    # Document reference
    source_doctype: Mapped[str] = mapped_column(String(50), nullable=False)
    source_docname: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Currency
    document_currency_code: Mapped[str] = mapped_column(String(3), default="NGN")
    tax_currency_code: Mapped[str] = mapped_column(String(3), default="NGN")

    # Order reference
    order_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Contract reference
    contract_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Supplier (Seller) details - 15 fields
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    supplier_tin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    supplier_vat_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    supplier_registration_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    supplier_street: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    supplier_building: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    supplier_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    supplier_postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    supplier_state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    supplier_country_code: Mapped[str] = mapped_column(String(2), default="NG")
    supplier_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    supplier_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    supplier_contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    supplier_bank_account: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    supplier_bank_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Customer (Buyer) details - 10 fields
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_tin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    customer_vat_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    customer_street: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    customer_postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    customer_state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    customer_country_code: Mapped[str] = mapped_column(String(2), default="NG")
    customer_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Delivery information
    delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    delivery_location: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Payment means
    payment_means_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # 30=Credit, 42=Bank
    payment_terms: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Totals
    line_extension_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)  # Sum before tax
    tax_exclusive_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tax_inclusive_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    allowance_total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    charge_total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    prepaid_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    payable_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Tax summary
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tax_category_code: Mapped[str] = mapped_column(String(10), default="S")  # Standard
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.0750"))

    # Status
    status: Mapped[EInvoiceStatus] = mapped_column(
        Enum(EInvoiceStatus), default=EInvoiceStatus.DRAFT, index=True
    )

    # Validation
    validation_errors: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    validated_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Submission to FIRS
    submitted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    submission_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    firs_response: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # QR code data (for printed invoices)
    qr_code_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Notes
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Company scope
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Line items relationship
    lines: Mapped[List["EInvoiceLine"]] = relationship(
        back_populates="einvoice", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<EInvoice {self.invoice_number} {self.status.value}>"


class EInvoiceLine(Base):
    """
    Line item within an e-invoice.
    """

    __tablename__ = "ng_einvoice_lines"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Parent invoice
    einvoice_id: Mapped[int] = mapped_column(ForeignKey("ng_einvoices.id"), nullable=False, index=True)

    # Line identification
    line_id: Mapped[str] = mapped_column(String(20), nullable=False)  # Sequential: "1", "2", etc.

    # Item details
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    item_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    item_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Quantity and unit
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_code: Mapped[str] = mapped_column(String(10), default="EA")  # Each

    # Pricing
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_extension_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Discounts/Charges
    allowance_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    charge_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))

    # Tax
    tax_category_code: Mapped[str] = mapped_column(String(10), default="S")
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.0750"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Total
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationship
    einvoice: Mapped["EInvoice"] = relationship(back_populates="lines")

    def __repr__(self) -> str:
        return f"<EInvoiceLine {self.line_id} {self.item_name}>"
