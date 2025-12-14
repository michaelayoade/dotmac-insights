"""
Nigerian Tax Administration Pydantic Schemas

Request/response schemas for all Nigerian tax endpoints.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator

from app.models.tax_ng import (
    NigerianTaxType,
    TaxJurisdiction,
    WHTPaymentType,
    CITCompanySize,
    VATTransactionType,
    EInvoiceStatus,
    PAYEFilingFrequency,
)

DEFAULT_COMPANY = "default"


# ============= BASE SCHEMAS =============

class TaxBaseSchema(BaseModel):
    """Base schema with common fields."""
    company: str = Field(default=DEFAULT_COMPANY)


class PaginatedResponse(BaseModel):
    """Paginated list response."""
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int


# ============= TAX SETTINGS SCHEMAS =============

class TaxSettingsCreate(TaxBaseSchema):
    """Create tax settings."""
    tin: Optional[str] = None
    vat_registration_number: Optional[str] = None
    cac_registration_number: Optional[str] = None
    state_tin: Optional[str] = None
    state_of_residence: Optional[str] = None
    default_jurisdiction: TaxJurisdiction = TaxJurisdiction.FEDERAL
    company_size: CITCompanySize = CITCompanySize.MEDIUM
    annual_turnover: Decimal = Decimal("0")
    vat_registered: bool = True
    is_wht_agent: bool = True
    apply_tin_penalty: bool = True
    einvoice_enabled: bool = False
    paye_filing_frequency: PAYEFilingFrequency = PAYEFilingFrequency.MONTHLY


class TaxSettingsUpdate(BaseModel):
    """Update tax settings."""
    tin: Optional[str] = None
    vat_registration_number: Optional[str] = None
    cac_registration_number: Optional[str] = None
    state_tin: Optional[str] = None
    state_of_residence: Optional[str] = None
    default_jurisdiction: Optional[TaxJurisdiction] = None
    company_size: Optional[CITCompanySize] = None
    annual_turnover: Optional[Decimal] = None
    vat_registered: Optional[bool] = None
    is_wht_agent: Optional[bool] = None
    apply_tin_penalty: Optional[bool] = None
    einvoice_enabled: Optional[bool] = None
    paye_filing_frequency: Optional[PAYEFilingFrequency] = None


class TaxSettingsResponse(TaxBaseSchema):
    """Tax settings response."""
    id: int
    tin: Optional[str]
    vat_registration_number: Optional[str]
    cac_registration_number: Optional[str]
    state_tin: Optional[str]
    state_of_residence: Optional[str]
    default_jurisdiction: TaxJurisdiction
    company_size: CITCompanySize
    annual_turnover: Decimal
    vat_registered: bool
    vat_rate: Decimal
    is_wht_agent: bool
    apply_tin_penalty: bool
    einvoice_enabled: bool
    einvoice_threshold: Decimal
    paye_filing_frequency: PAYEFilingFrequency
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============= VAT SCHEMAS =============

class VATTransactionCreate(TaxBaseSchema):
    """Record VAT transaction."""
    transaction_type: VATTransactionType
    transaction_date: date
    party_type: str = Field(..., pattern="^(customer|supplier)$")
    party_id: Optional[int] = None
    party_name: str
    party_tin: Optional[str] = None
    party_vat_number: Optional[str] = None
    source_doctype: str
    source_docname: str
    taxable_amount: Decimal = Field(..., gt=0)
    vat_rate: Decimal = Field(default=Decimal("0.0750"))
    currency: str = "NGN"
    exchange_rate: Decimal = Field(default=Decimal("1"))
    is_exempt: bool = False
    is_zero_rated: bool = False
    exemption_reason: Optional[str] = None


class VATTransactionResponse(TaxBaseSchema):
    """VAT transaction response."""
    id: int
    reference_number: str
    transaction_type: VATTransactionType
    transaction_date: date
    party_type: str
    party_id: Optional[int]
    party_name: str
    party_tin: Optional[str]
    taxable_amount: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    total_amount: Decimal
    currency: str
    filing_period: str
    is_filed: bool
    is_exempt: bool
    is_zero_rated: bool
    created_at: datetime

    class Config:
        from_attributes = True


class VATSummaryResponse(BaseModel):
    """VAT period summary."""
    period: str
    period_start: date
    period_end: date
    due_date: date
    output_vat: Decimal
    input_vat: Decimal
    net_vat_payable: Decimal
    transaction_count: int
    is_filed: bool
    company: str


class VATFilingPrepResponse(BaseModel):
    """VAT filing preparation data."""
    period: str
    summary: VATSummaryResponse
    output_transactions: List[VATTransactionResponse]
    input_transactions: List[VATTransactionResponse]
    filing_deadline: date
    days_until_deadline: int


# ============= WHT SCHEMAS =============

class WHTTransactionCreate(TaxBaseSchema):
    """Record WHT deduction."""
    transaction_date: date
    payment_type: WHTPaymentType
    supplier_id: Optional[int] = None
    supplier_name: str
    supplier_tin: Optional[str] = None
    supplier_is_corporate: bool = True
    source_doctype: str
    source_docname: str
    gross_amount: Decimal = Field(..., gt=0)
    jurisdiction: TaxJurisdiction = TaxJurisdiction.FEDERAL
    currency: str = "NGN"
    exchange_rate: Decimal = Field(default=Decimal("1"))


class WHTTransactionResponse(TaxBaseSchema):
    """WHT transaction response."""
    id: int
    reference_number: str
    transaction_date: date
    payment_type: WHTPaymentType
    supplier_id: Optional[int]
    supplier_name: str
    supplier_tin: Optional[str]
    has_valid_tin: bool
    gross_amount: Decimal
    standard_rate: Decimal
    wht_rate: Decimal
    wht_amount: Decimal
    net_amount: Decimal
    currency: str
    jurisdiction: TaxJurisdiction
    remittance_due_date: date
    is_remitted: bool
    certificate_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class WHTSupplierSummaryResponse(BaseModel):
    """WHT summary for a supplier."""
    supplier_id: int
    supplier_name: str
    supplier_tin: Optional[str]
    total_gross_amount: Decimal
    total_wht_deducted: Decimal
    total_net_paid: Decimal
    transaction_count: int
    certificates_issued: int
    pending_certificate_amount: Decimal


class WHTRemittanceDueResponse(BaseModel):
    """Pending WHT remittances."""
    transactions: List[WHTTransactionResponse]
    total_amount: Decimal
    overdue_count: int
    overdue_amount: Decimal
    due_this_week: int
    due_this_week_amount: Decimal


# ============= WHT CERTIFICATE SCHEMAS =============

class WHTCertificateCreate(BaseModel):
    """Generate WHT certificate."""
    supplier_id: int
    period_start: date
    period_end: date
    company: str


class WHTCertificateResponse(BaseModel):
    """WHT certificate response."""
    id: int
    certificate_number: str
    issue_date: date
    supplier_id: Optional[int]
    supplier_name: str
    supplier_tin: Optional[str]
    period_start: date
    period_end: date
    total_gross_amount: Decimal
    total_wht_amount: Decimal
    transaction_count: int
    is_issued: bool
    is_cancelled: bool
    company: str
    company_tin: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ============= PAYE SCHEMAS =============

class PAYECalculationCreate(TaxBaseSchema):
    """Calculate PAYE for employee."""
    employee_id: int
    employee_name: str
    employee_tin: Optional[str] = None
    payroll_period: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    period_start: date
    period_end: date
    basic_salary: Decimal = Field(..., gt=0)
    housing_allowance: Decimal = Decimal("0")
    transport_allowance: Decimal = Decimal("0")
    other_allowances: Decimal = Decimal("0")
    bonus: Decimal = Decimal("0")
    pension_contribution: Optional[Decimal] = None
    nhf_contribution: Optional[Decimal] = None
    life_assurance: Decimal = Decimal("0")
    other_reliefs: Decimal = Decimal("0")
    state_of_residence: Optional[str] = None


class PAYECalculationResponse(TaxBaseSchema):
    """PAYE calculation response."""
    id: int
    employee_id: int
    employee_name: str
    employee_tin: Optional[str]
    payroll_period: str
    period_start: date
    period_end: date
    gross_income: Decimal
    annual_gross_income: Decimal
    total_cra: Decimal
    pension_contribution: Decimal
    nhf_contribution: Decimal
    total_reliefs: Decimal
    annual_taxable_income: Decimal
    tax_bands_breakdown: Optional[Dict]
    annual_tax: Decimal
    monthly_tax: Decimal
    effective_rate: Decimal
    state_of_residence: Optional[str]
    is_filed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PAYESummaryResponse(BaseModel):
    """PAYE period summary."""
    period: str
    period_start: date
    period_end: date
    due_date: date
    employee_count: int
    total_gross_income: Decimal
    total_tax: Decimal
    is_filed: bool
    company: str


# ============= CIT SCHEMAS =============

class CITAssessmentCreate(TaxBaseSchema):
    """Create CIT assessment."""
    fiscal_year: str = Field(..., pattern=r"^\d{4}$")
    period_start: date
    period_end: date
    gross_turnover: Decimal = Field(..., ge=0)
    gross_profit: Decimal
    disallowed_expenses: Decimal = Decimal("0")
    capital_allowances: Decimal = Decimal("0")
    loss_brought_forward: Decimal = Decimal("0")
    investment_allowances: Decimal = Decimal("0")
    company_tin: Optional[str] = None


class CITAssessmentResponse(TaxBaseSchema):
    """CIT assessment response."""
    id: int
    assessment_number: str
    fiscal_year: str
    period_start: date
    period_end: date
    company_size: CITCompanySize
    gross_turnover: Decimal
    gross_profit: Decimal
    disallowed_expenses: Decimal
    capital_allowances: Decimal
    loss_brought_forward: Decimal
    adjusted_profit: Decimal
    assessable_profit: Decimal
    cit_rate: Decimal
    cit_amount: Decimal
    tet_rate: Decimal
    tet_amount: Decimal
    minimum_tax: Decimal
    is_minimum_tax_applicable: bool
    total_tax_liability: Decimal
    amount_paid: Decimal
    balance_due: Decimal
    due_date: date
    is_filed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CITComputationResponse(BaseModel):
    """CIT computation breakdown."""
    fiscal_year: str
    company_size: CITCompanySize
    gross_turnover: Decimal
    gross_profit: Decimal
    adjustments: Dict[str, Decimal]
    adjusted_profit: Decimal
    assessable_profit: Decimal
    cit_computation: Dict[str, Decimal]
    tet_computation: Dict[str, Decimal]
    minimum_tax_computation: Dict[str, Decimal]
    total_tax_liability: Decimal
    payment_status: Dict[str, Decimal]


# ============= FILING SCHEMAS =============

class FilingCalendarEntry(BaseModel):
    """Filing calendar entry."""
    tax_type: str
    period: str
    period_start: date
    period_end: date
    due_date: date
    description: str
    is_overdue: bool = False
    is_filed: bool = False


class FilingCalendarResponse(BaseModel):
    """Filing calendar response."""
    year: int
    entries: List[FilingCalendarEntry]
    upcoming_count: int
    overdue_count: int


class UpcomingFilingsResponse(BaseModel):
    """Upcoming filings response."""
    filings: List[FilingCalendarEntry]
    total: int
    next_deadline: Optional[date]


# ============= TAX PAYMENT SCHEMAS =============

class TaxPaymentCreate(BaseModel):
    """Record tax payment."""
    tax_type: NigerianTaxType
    period: str
    payment_date: date
    amount: Decimal = Field(..., gt=0)
    payment_reference: Optional[str] = None
    payment_method: Optional[str] = None
    bank_account: Optional[str] = None
    company: str


class TaxPaymentResponse(BaseModel):
    """Tax payment response."""
    id: int
    tax_type: NigerianTaxType
    period: str
    payment_date: date
    amount: Decimal
    payment_reference: Optional[str]
    payment_method: Optional[str]
    bank_account: Optional[str]
    company: str
    created_at: datetime

    class Config:
        from_attributes = True


# ============= DASHBOARD SCHEMAS =============

class TaxDashboardSummary(BaseModel):
    """Tax overview dashboard."""
    company: str
    period: str

    # VAT Summary
    vat_output: Decimal
    vat_input: Decimal
    vat_payable: Decimal
    vat_status: str

    # WHT Summary
    wht_deducted: Decimal
    wht_remitted: Decimal
    wht_pending: Decimal
    wht_overdue_count: int

    # PAYE Summary
    paye_calculated: Decimal
    paye_remitted: Decimal
    paye_pending: Decimal
    employee_count: int

    # CIT Summary
    cit_liability: Optional[Decimal]
    cit_paid: Optional[Decimal]
    cit_status: Optional[str]

    # Upcoming Deadlines
    next_deadline: Optional[date]
    deadlines_this_month: int


# ============= E-INVOICE SCHEMAS =============

class EInvoiceCreate(TaxBaseSchema):
    """Create e-invoice."""
    source_doctype: str
    source_docname: str
    issue_date: date
    due_date: Optional[date] = None

    # Supplier details
    supplier_name: str
    supplier_tin: Optional[str] = None
    supplier_vat_number: Optional[str] = None
    supplier_street: Optional[str] = None
    supplier_city: Optional[str] = None
    supplier_state: Optional[str] = None
    supplier_phone: Optional[str] = None
    supplier_email: Optional[str] = None

    # Customer details
    customer_name: str
    customer_tin: Optional[str] = None
    customer_street: Optional[str] = None
    customer_city: Optional[str] = None
    customer_state: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None

    # Payment
    payment_means_code: Optional[str] = None
    payment_terms: Optional[str] = None

    # Line items
    lines: List["EInvoiceLineCreate"]

    # Optional notes
    note: Optional[str] = None


class EInvoiceLineCreate(BaseModel):
    """E-invoice line item."""
    item_name: str
    item_description: Optional[str] = None
    item_code: Optional[str] = None
    quantity: Decimal = Field(..., gt=0)
    unit_code: str = "EA"
    unit_price: Decimal = Field(..., ge=0)
    tax_rate: Decimal = Field(default=Decimal("0.0750"))
    allowance_amount: Decimal = Decimal("0")
    charge_amount: Decimal = Decimal("0")


class EInvoiceResponse(TaxBaseSchema):
    """E-invoice response."""
    id: int
    invoice_number: str
    uuid: str
    issue_date: date
    due_date: Optional[date]
    status: EInvoiceStatus
    supplier_name: str
    supplier_tin: Optional[str]
    customer_name: str
    customer_tin: Optional[str]
    line_extension_amount: Decimal
    tax_amount: Decimal
    tax_rate: Decimal
    payable_amount: Decimal
    validation_errors: Optional[List[Dict]]
    created_at: datetime

    class Config:
        from_attributes = True


class EInvoiceValidationResult(BaseModel):
    """E-invoice validation result."""
    is_valid: bool
    errors: List[Dict[str, str]]
    warnings: List[Dict[str, str]]


class EInvoiceUBLResponse(BaseModel):
    """E-invoice UBL XML response."""
    invoice_number: str
    ubl_version: str
    xml_content: str
    qr_code_data: Optional[str]


# Fix forward reference
EInvoiceCreate.model_rebuild()
