"""
Nigerian Tax Constants and Calculation Utilities

Contains all statutory rates, thresholds, and helper functions
for Nigerian tax administration compliance.
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
from typing import Dict, List, Tuple, Optional, Any
from calendar import monthrange

from app.models.tax_ng import (
    WHTPaymentType,
    CITCompanySize,
    TaxJurisdiction,
    NigerianTaxType,
)


# ============= VAT CONSTANTS =============

# Standard VAT rate (effective Feb 1, 2020)
VAT_RATE = Decimal("0.075")  # 7.5%

# VAT filing deadline - 21st of the following month
VAT_FILING_DEADLINE_DAY = 21

# B2C e-invoice threshold
VAT_B2C_THRESHOLD = Decimal("50000")  # N50,000

# VAT exempt items/services categories
VAT_EXEMPT_CATEGORIES = [
    "medical_pharmaceutical",
    "basic_food",
    "educational_materials",
    "baby_products",
    "agricultural_inputs",
    "plant_machinery_agriculture",
    "exported_goods",
    "diplomatic_supplies",
]

# Zero-rated categories
VAT_ZERO_RATED_CATEGORIES = [
    "exports",
    "goods_in_transit",
    "aircraft_spare_parts",
    "oil_exploration_equipment",
]


# ============= WHT CONSTANTS =============

# WHT rates by payment type (corporate rates)
WHT_RATES_CORPORATE: Dict[WHTPaymentType, Decimal] = {
    WHTPaymentType.DIVIDEND: Decimal("0.10"),           # 10%
    WHTPaymentType.INTEREST: Decimal("0.10"),           # 10%
    WHTPaymentType.RENT: Decimal("0.10"),               # 10%
    WHTPaymentType.ROYALTY: Decimal("0.10"),            # 10%
    WHTPaymentType.COMMISSION: Decimal("0.10"),         # 10%
    WHTPaymentType.CONSULTANCY: Decimal("0.10"),        # 10%
    WHTPaymentType.TECHNICAL_SERVICE: Decimal("0.10"),  # 10%
    WHTPaymentType.MANAGEMENT_FEE: Decimal("0.10"),     # 10%
    WHTPaymentType.DIRECTOR_FEE: Decimal("0.10"),       # 10%
    WHTPaymentType.CONTRACT: Decimal("0.05"),           # 5%
    WHTPaymentType.SUPPLY: Decimal("0.05"),             # 5%
    WHTPaymentType.CONSTRUCTION: Decimal("0.05"),       # 5%
    WHTPaymentType.PROFESSIONAL_FEE: Decimal("0.05"),   # 5%
    WHTPaymentType.HIRE_OF_EQUIPMENT: Decimal("0.10"),  # 10%
    WHTPaymentType.ALL_ASPECTS_CONTRACT: Decimal("0.025"),  # 2.5%
}

# WHT rates for individuals (differs for supply)
WHT_RATES_INDIVIDUAL: Dict[WHTPaymentType, Decimal] = {
    **WHT_RATES_CORPORATE,
    WHTPaymentType.SUPPLY: Decimal("0.05"),  # 5% for individuals too
}

# Special case: supply to individuals at lower rate
WHT_SUPPLY_INDIVIDUAL_RATE = Decimal("0.05")  # 5%

# Non-TIN penalty multiplier
WHT_NON_TIN_MULTIPLIER = Decimal("2")  # 2x rate if no TIN

# Federal WHT remittance deadline (21 days after deduction)
WHT_FEDERAL_REMITTANCE_DAYS = 21

# State WHT remittance deadline (30 days after deduction)
WHT_STATE_REMITTANCE_DAYS = 30


# ============= CIT CONSTANTS =============

# CIT thresholds and rates (Companies Income Tax Act)
# Effective from Jan 1, 2020 (Finance Act 2019)
CIT_THRESHOLDS: List[Tuple[Optional[Decimal], Optional[Decimal], Decimal, CITCompanySize]] = [
    # (min_turnover, max_turnover, rate, size)
    (None, Decimal("25000000"), Decimal("0.00"), CITCompanySize.SMALL),           # 0% for <=N25M
    (Decimal("25000000"), Decimal("100000000"), Decimal("0.20"), CITCompanySize.MEDIUM),  # 20% for N25M-N100M
    (Decimal("100000000"), None, Decimal("0.30"), CITCompanySize.LARGE),          # 30% for >N100M
]

# Tertiary Education Tax (TET) rate - 3% of assessable profit
TET_RATE = Decimal("0.03")  # 3%

# Minimum tax rate (when company is in loss or low profit)
MINIMUM_TAX_RATE = Decimal("0.005")  # 0.5% of gross turnover

# CIT filing deadline - 6 months after financial year end
CIT_FILING_MONTHS_AFTER_YEAR_END = 6


# ============= PAYE CONSTANTS =============

# Minimum wage exemption (July 2024 update)
MINIMUM_WAGE_MONTHLY = Decimal("70000")  # N70,000/month
MINIMUM_WAGE_ANNUAL = Decimal("840000")  # N840,000/year
PAYE_EXEMPTION_THRESHOLD = MINIMUM_WAGE_ANNUAL  # Income <= this is PAYE exempt

# ---- CURRENT LAW (PITA - valid until Dec 2025) ----
# PAYE progressive tax bands (annual income)
# Personal Income Tax Act (PITA) as amended
PAYE_BANDS_PITA: List[Tuple[Decimal, Decimal, Decimal]] = [
    # (lower_limit, upper_limit, rate)
    (Decimal("0"), Decimal("300000"), Decimal("0.07")),       # First N300,000 @ 7%
    (Decimal("300000"), Decimal("600000"), Decimal("0.11")),  # Next N300,000 @ 11%
    (Decimal("600000"), Decimal("1100000"), Decimal("0.15")), # Next N500,000 @ 15%
    (Decimal("1100000"), Decimal("1600000"), Decimal("0.19")), # Next N500,000 @ 19%
    (Decimal("1600000"), Decimal("3200000"), Decimal("0.21")), # Next N1,600,000 @ 21%
    (Decimal("3200000"), None, Decimal("0.24")),               # Over N3,200,000 @ 24%
]

# Consolidated Relief Allowance (CRA) - PITA (valid until Dec 2025)
CRA_FIXED_AMOUNT = Decimal("200000")  # N200,000 fixed
CRA_PERCENTAGE_OF_GROSS = Decimal("0.01")  # 1% of gross income (minimum of the two)
CRA_VARIABLE_PERCENTAGE = Decimal("0.20")  # 20% of gross income

# ---- NTA 2025 (Nigeria Tax Act - effective Jan 2026) ----
# New tax-free threshold replaces CRA
NTA_2025_TAX_FREE_THRESHOLD = Decimal("800000")  # N800,000/year fixed

# NTA 2025 PAYE progressive tax bands (0%-25%)
PAYE_BANDS_NTA_2025: List[Tuple[Decimal, Decimal, Decimal]] = [
    # (lower_limit, upper_limit, rate) - Updated bands for NTA 2025
    (Decimal("0"), Decimal("800000"), Decimal("0.00")),        # First N800,000 @ 0% (tax-free)
    (Decimal("800000"), Decimal("1100000"), Decimal("0.15")),  # Next N300,000 @ 15%
    (Decimal("1100000"), Decimal("1600000"), Decimal("0.19")), # Next N500,000 @ 19%
    (Decimal("1600000"), Decimal("3200000"), Decimal("0.21")), # Next N1,600,000 @ 21%
    (Decimal("3200000"), None, Decimal("0.25")),               # Over N3,200,000 @ 25%
]

# NTA 2025 Rent Relief (replaces part of CRA)
NTA_2025_RENT_RELIEF_RATE = Decimal("0.20")  # 20% of rent paid
NTA_2025_RENT_RELIEF_MAX = Decimal("500000")  # Max N500,000/year

# NTA 2025 Development Levy (replaces TET, IT Levy, NASENI, PTF)
NTA_2025_DEVELOPMENT_LEVY_RATE = Decimal("0.04")  # 4% consolidated

# Note: Under NTA 2025, gratuity becomes TAXABLE (previously exempt)

# Default to current law (PITA) - switch to NTA_2025 from Jan 2026
PAYE_BANDS = PAYE_BANDS_PITA

# ---- STATUTORY CONTRIBUTIONS ----
# Pension contribution rates (PFA 2014)
PENSION_EMPLOYEE_RATE = Decimal("0.08")  # 8% employee contribution
PENSION_EMPLOYER_RATE = Decimal("0.10")  # 10% employer contribution

# National Housing Fund (NHF)
NHF_RATE = Decimal("0.025")  # 2.5% (voluntary for private sector)

# National Health Insurance Scheme (NHIS)
NHIS_EMPLOYEE_RATE = Decimal("0.05")  # 5% employee contribution
NHIS_EMPLOYER_RATE = Decimal("0.10")  # 10% employer contribution

# Nigeria Social Insurance Trust Fund (NSITF)
NSITF_EMPLOYER_RATE = Decimal("0.01")  # 1% employer only

# Industrial Training Fund (ITF)
ITF_RATE = Decimal("0.01")  # 1% of annual payroll (employers with 5+ staff or N50M+ turnover)

# PAYE filing deadline - 10th of the following month
PAYE_FILING_DEADLINE_DAY = 10


# ============= STATUTORY CALCULATION FUNCTIONS =============

def calculate_pension_contributions(
    basic_salary: Decimal,
    housing_allowance: Decimal = Decimal("0"),
    transport_allowance: Decimal = Decimal("0"),
) -> Dict[str, Decimal]:
    """
    Calculate pension contributions under PFA 2014.

    Pensionable earnings = Basic + Housing + Transport
    Employee: 8%, Employer: 10%

    Args:
        basic_salary: Monthly basic salary
        housing_allowance: Monthly housing allowance
        transport_allowance: Monthly transport allowance

    Returns:
        Dict with employee_contribution, employer_contribution, total, pensionable_earnings
    """
    pensionable = basic_salary + housing_allowance + transport_allowance
    employee = (pensionable * PENSION_EMPLOYEE_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    employer = (pensionable * PENSION_EMPLOYER_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "pensionable_earnings": pensionable,
        "employee_contribution": employee,
        "employer_contribution": employer,
        "total_contribution": employee + employer,
        "employee_rate": PENSION_EMPLOYEE_RATE,
        "employer_rate": PENSION_EMPLOYER_RATE,
    }


def calculate_nhf_contribution(basic_salary: Decimal) -> Dict[str, Decimal]:
    """
    Calculate National Housing Fund contribution.

    Rate: 2.5% of basic salary (employee only, voluntary for private sector)

    Args:
        basic_salary: Monthly basic salary

    Returns:
        Dict with contribution amount and rate
    """
    contribution = (basic_salary * NHF_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "contribution": contribution,
        "rate": NHF_RATE,
        "is_mandatory": False,  # Voluntary for private sector
    }


def calculate_nhis_contributions(basic_salary: Decimal) -> Dict[str, Decimal]:
    """
    Calculate National Health Insurance Scheme contributions.

    Employee: 5% of basic, Employer: 10% of basic

    Args:
        basic_salary: Monthly basic salary

    Returns:
        Dict with employee and employer contributions
    """
    employee = (basic_salary * NHIS_EMPLOYEE_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    employer = (basic_salary * NHIS_EMPLOYER_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "employee_contribution": employee,
        "employer_contribution": employer,
        "total_contribution": employee + employer,
        "employee_rate": NHIS_EMPLOYEE_RATE,
        "employer_rate": NHIS_EMPLOYER_RATE,
    }


def calculate_nsitf_contribution(gross_salary: Decimal) -> Dict[str, Decimal]:
    """
    Calculate Nigeria Social Insurance Trust Fund contribution.

    Rate: 1% of gross salary (employer only)

    Args:
        gross_salary: Monthly gross salary

    Returns:
        Dict with contribution amount
    """
    contribution = (gross_salary * NSITF_EMPLOYER_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "employer_contribution": contribution,
        "rate": NSITF_EMPLOYER_RATE,
        "is_employer_only": True,
    }


def calculate_itf_contribution(annual_payroll: Decimal) -> Dict[str, Decimal]:
    """
    Calculate Industrial Training Fund contribution.

    Rate: 1% of annual payroll
    Applicable to: Employers with 5+ staff OR N50M+ turnover

    Args:
        annual_payroll: Total annual payroll cost

    Returns:
        Dict with contribution amount
    """
    contribution = (annual_payroll * ITF_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "annual_contribution": contribution,
        "monthly_provision": (contribution / 12).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "rate": ITF_RATE,
        "is_employer_only": True,
    }


def calculate_all_statutory_deductions(
    basic_salary: Decimal,
    housing_allowance: Decimal = Decimal("0"),
    transport_allowance: Decimal = Decimal("0"),
    other_allowances: Decimal = Decimal("0"),
    include_paye: bool = True,
    include_pension: bool = True,
    include_nhf: bool = True,
    include_nhis: bool = True,
    include_nsitf: bool = True,
    include_itf: bool = True,
    tax_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Calculate all statutory deductions for payroll.

    Returns complete breakdown of:
    - PAYE (personal income tax) - if include_paye
    - Pension (employee & employer) - if include_pension
    - NHF (if include_nhf)
    - NHIS (if include_nhis)
    - Employer-only: NSITF (if include_nsitf), ITF provision (if include_itf)

    Args:
        basic_salary: Monthly basic salary
        housing_allowance: Monthly housing allowance
        transport_allowance: Monthly transport allowance
        other_allowances: Other monthly allowances
        include_paye: Include PAYE calculation (based on employment type)
        include_pension: Include pension calculation (based on employment type)
        include_nhf: Include NHF calculation (based on employment type)
        include_nhis: Include NHIS calculation (based on employment type)
        include_nsitf: Include NSITF calculation (based on employment type)
        include_itf: Include ITF calculation (based on employment type)
        tax_date: Date for tax law determination

    Returns:
        Comprehensive dict with all deductions and totals
    """
    # Calculate gross
    gross_monthly = basic_salary + housing_allowance + transport_allowance + other_allowances
    gross_annual = gross_monthly * 12

    # Check minimum wage exemption
    is_exempt = is_paye_exempt(gross_annual)

    # Zero result for disabled deductions
    zero_pension = {
        "pensionable_earnings": Decimal("0"),
        "employee_contribution": Decimal("0"),
        "employer_contribution": Decimal("0"),
        "total_contribution": Decimal("0"),
        "employee_rate": PENSION_EMPLOYEE_RATE,
        "employer_rate": PENSION_EMPLOYER_RATE,
    }
    zero_nsitf = {
        "employer_contribution": Decimal("0"),
        "rate": NSITF_EMPLOYER_RATE,
    }
    zero_itf = {
        "annual_contribution": Decimal("0"),
        "monthly_provision": Decimal("0"),
        "rate": ITF_RATE,
        "is_employer_only": True,
    }

    # Pension
    pension = calculate_pension_contributions(basic_salary, housing_allowance, transport_allowance) if include_pension else zero_pension

    # NHF
    nhf = calculate_nhf_contribution(basic_salary) if include_nhf else None

    # NHIS
    nhis = calculate_nhis_contributions(basic_salary) if include_nhis else None

    # NSITF (employer only)
    nsitf = calculate_nsitf_contribution(gross_monthly) if include_nsitf else zero_nsitf

    # ITF provision (employer only, monthly accrual)
    itf = calculate_itf_contribution(gross_annual) if include_itf else zero_itf

    # PAYE calculation
    if is_exempt or not include_paye:
        paye_monthly = Decimal("0")
        paye_annual = Decimal("0")
        effective_rate = Decimal("0")
        cra = (Decimal("0"), Decimal("0"), Decimal("0"))
        bands_breakdown = []
    else:
        # Get CRA
        cra = calculate_cra(gross_annual, tax_date)

        # Total reliefs for PAYE
        annual_pension = pension["employee_contribution"] * 12
        annual_nhf = (nhf["contribution"] * 12) if nhf else Decimal("0")

        total_reliefs = cra[2] + annual_pension + annual_nhf  # CRA + pension + NHF

        # Taxable income
        annual_taxable = max(gross_annual - total_reliefs, Decimal("0"))

        # Calculate PAYE
        paye_annual, bands_breakdown, effective_rate = calculate_paye(annual_taxable, tax_date)
        paye_monthly = (paye_annual / 12).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Total employee deductions
    employee_deductions = pension["employee_contribution"] + paye_monthly
    if nhf:
        employee_deductions += nhf["contribution"]
    if nhis:
        employee_deductions += nhis["employee_contribution"]

    # Total employer contributions
    employer_contributions = pension["employer_contribution"] + nsitf["employer_contribution"] + itf["monthly_provision"]
    if nhis:
        employer_contributions += nhis["employer_contribution"]

    # Net pay
    net_pay = gross_monthly - employee_deductions

    return {
        "gross_monthly": gross_monthly,
        "gross_annual": gross_annual,
        "is_paye_exempt": is_exempt,
        "tax_law": get_applicable_tax_law(tax_date),

        "paye": {
            "monthly": paye_monthly,
            "annual": paye_annual,
            "effective_rate": effective_rate,
            "bands_breakdown": bands_breakdown,
        },

        "reliefs": {
            "cra_fixed": cra[0],
            "cra_variable": cra[1],
            "total_cra": cra[2],
        },

        "pension": pension,
        "nhf": nhf,
        "nhis": nhis,
        "nsitf": nsitf,
        "itf": itf,

        "totals": {
            "employee_deductions": employee_deductions,
            "employer_contributions": employer_contributions,
            "net_pay": net_pay,
        },

        "breakdown": {
            "paye": paye_monthly,
            "pension_employee": pension["employee_contribution"],
            "nhf": nhf["contribution"] if nhf else Decimal("0"),
            "nhis_employee": nhis["employee_contribution"] if nhis else Decimal("0"),
        }
    }


# ============= NIGERIAN STATES =============

NIGERIAN_STATES = [
    "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue",
    "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu",
    "FCT", "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi",
    "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo", "Osun",
    "Oyo", "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara"
]


# ============= CALCULATION FUNCTIONS =============

def get_wht_rate(
    payment_type: WHTPaymentType,
    is_corporate: bool = True,
    has_tin: bool = True
) -> Decimal:
    """
    Get WHT rate for a payment type.

    Args:
        payment_type: Type of payment
        is_corporate: True if payee is corporate, False if individual
        has_tin: True if payee has valid TIN

    Returns:
        Applicable WHT rate as decimal (e.g., 0.10 for 10%)
    """
    rates = WHT_RATES_CORPORATE if is_corporate else WHT_RATES_INDIVIDUAL
    base_rate = rates.get(payment_type, Decimal("0.05"))  # Default 5%

    if not has_tin:
        # Double rate for non-TIN suppliers
        return base_rate * WHT_NON_TIN_MULTIPLIER

    return base_rate


def calculate_wht(
    gross_amount: Decimal,
    payment_type: WHTPaymentType,
    is_corporate: bool = True,
    has_tin: bool = True
) -> Tuple[Decimal, Decimal, Decimal]:
    """
    Calculate WHT deduction.

    Args:
        gross_amount: Gross payment amount
        payment_type: Type of payment
        is_corporate: True if payee is corporate
        has_tin: True if payee has valid TIN

    Returns:
        Tuple of (wht_rate, wht_amount, net_amount)
    """
    rate = get_wht_rate(payment_type, is_corporate, has_tin)
    wht_amount = (gross_amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    net_amount = gross_amount - wht_amount

    return rate, wht_amount, net_amount


def get_wht_remittance_deadline(
    transaction_date: date,
    jurisdiction: TaxJurisdiction
) -> date:
    """
    Calculate WHT remittance deadline.

    Args:
        transaction_date: Date of WHT deduction
        jurisdiction: Federal or State

    Returns:
        Deadline date for remittance
    """
    if jurisdiction == TaxJurisdiction.FEDERAL:
        return transaction_date + timedelta(days=WHT_FEDERAL_REMITTANCE_DAYS)
    else:
        return transaction_date + timedelta(days=WHT_STATE_REMITTANCE_DAYS)


def calculate_vat(
    taxable_amount: Decimal,
    rate: Optional[Decimal] = None
) -> Tuple[Decimal, Decimal]:
    """
    Calculate VAT on taxable amount.

    Args:
        taxable_amount: Amount before VAT
        rate: Optional custom rate (defaults to 7.5%)

    Returns:
        Tuple of (vat_amount, total_amount)
    """
    vat_rate = rate or VAT_RATE
    vat_amount = (taxable_amount * vat_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total_amount = taxable_amount + vat_amount

    return vat_amount, total_amount


def get_vat_filing_deadline(period: str) -> date:
    """
    Get VAT filing deadline for a period.

    Args:
        period: Period string like "2024-01"

    Returns:
        Filing deadline date (21st of following month)
    """
    year, month = map(int, period.split("-"))

    # Move to next month
    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1

    return date(next_year, next_month, VAT_FILING_DEADLINE_DAY)


def get_cit_rate(annual_turnover: Decimal) -> Tuple[Decimal, CITCompanySize]:
    """
    Get CIT rate based on annual turnover.

    Args:
        annual_turnover: Company's annual turnover

    Returns:
        Tuple of (cit_rate, company_size)
    """
    for min_threshold, max_threshold, rate, size in CIT_THRESHOLDS:
        min_ok = min_threshold is None or annual_turnover > min_threshold
        max_ok = max_threshold is None or annual_turnover <= max_threshold

        if min_ok and max_ok:
            return rate, size

    # Default to large company rate
    return Decimal("0.30"), CITCompanySize.LARGE


def calculate_cit(
    assessable_profit: Decimal,
    gross_turnover: Decimal
) -> Tuple[Decimal, Decimal, Decimal, Decimal, bool]:
    """
    Calculate Company Income Tax.

    Args:
        assessable_profit: Profit after adjustments
        gross_turnover: Total turnover

    Returns:
        Tuple of (cit_rate, cit_amount, tet_amount, total_tax, is_minimum_tax)
    """
    cit_rate, _ = get_cit_rate(gross_turnover)

    # Calculate CIT
    cit_amount = (assessable_profit * cit_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Calculate TET (3% of assessable profit)
    tet_amount = (assessable_profit * TET_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Calculate minimum tax (0.5% of gross turnover)
    minimum_tax = (gross_turnover * MINIMUM_TAX_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Use minimum tax if higher than CIT (for small/medium companies or loss situations)
    is_minimum_tax = minimum_tax > cit_amount
    actual_cit = max(cit_amount, minimum_tax) if cit_rate > 0 else cit_amount

    total_tax = actual_cit + tet_amount

    return cit_rate, actual_cit, tet_amount, total_tax, is_minimum_tax


def get_applicable_tax_law(tax_date: Optional[date] = None) -> str:
    """
    Determine which tax law applies based on date.

    Args:
        tax_date: Date to check (defaults to today)

    Returns:
        "PITA" for current law, "NTA_2025" for new law (effective Jan 2026)
    """
    if tax_date is None:
        tax_date = date.today()

    # NTA 2025 becomes effective January 1, 2026
    nta_effective_date = date(2026, 1, 1)

    if tax_date >= nta_effective_date:
        return "NTA_2025"
    return "PITA"


def calculate_cra(annual_gross_income: Decimal, tax_date: Optional[date] = None) -> Tuple[Decimal, Decimal, Decimal]:
    """
    Calculate Consolidated Relief Allowance for PAYE.

    Under PITA (until Dec 2025):
        CRA = Higher of (N200,000 or 1% of gross) + 20% of gross income

    Under NTA 2025 (from Jan 2026):
        CRA is ELIMINATED - replaced by N800,000 tax-free threshold

    Args:
        annual_gross_income: Total annual gross income
        tax_date: Date to determine applicable law

    Returns:
        Tuple of (cra_fixed, cra_variable, total_cra)
    """
    tax_law = get_applicable_tax_law(tax_date)

    if tax_law == "NTA_2025":
        # CRA eliminated under NTA 2025 - return zeros
        # Tax-free threshold is handled in the PAYE bands instead
        return Decimal("0"), Decimal("0"), Decimal("0")

    # PITA calculation (current law)
    # Fixed component: higher of N200,000 or 1% of gross
    one_percent = annual_gross_income * CRA_PERCENTAGE_OF_GROSS
    cra_fixed = max(CRA_FIXED_AMOUNT, one_percent)

    # Variable component: 20% of gross income
    cra_variable = annual_gross_income * CRA_VARIABLE_PERCENTAGE

    total_cra = cra_fixed + cra_variable

    return cra_fixed, cra_variable, total_cra


def calculate_rent_relief_nta_2025(annual_rent_paid: Decimal) -> Decimal:
    """
    Calculate rent relief under NTA 2025.

    20% of rent paid, capped at N500,000/year.

    Args:
        annual_rent_paid: Total annual rent paid

    Returns:
        Rent relief amount
    """
    relief = annual_rent_paid * NTA_2025_RENT_RELIEF_RATE
    return min(relief, NTA_2025_RENT_RELIEF_MAX)


def is_paye_exempt(annual_gross_income: Decimal) -> bool:
    """
    Check if employee is exempt from PAYE based on minimum wage.

    Employees earning <= N70,000/month (N840,000/year) are exempt.

    Args:
        annual_gross_income: Annual gross income

    Returns:
        True if exempt from PAYE
    """
    return annual_gross_income <= PAYE_EXEMPTION_THRESHOLD


def calculate_paye(
    annual_taxable_income: Decimal,
    tax_date: Optional[date] = None
) -> Tuple[Decimal, List[Dict], Decimal]:
    """
    Calculate PAYE using progressive tax bands.

    Automatically selects appropriate bands based on date:
    - PITA (until Dec 2025): 7%-24% bands
    - NTA 2025 (from Jan 2026): 0%-25% bands with N800,000 tax-free

    Args:
        annual_taxable_income: Annual income after reliefs
        tax_date: Date to determine applicable tax law

    Returns:
        Tuple of (annual_tax, bands_breakdown, effective_rate)
    """
    if annual_taxable_income <= 0:
        return Decimal("0"), [], Decimal("0")

    # Select appropriate tax bands
    tax_law = get_applicable_tax_law(tax_date)
    if tax_law == "NTA_2025":
        bands = PAYE_BANDS_NTA_2025
    else:
        bands = PAYE_BANDS_PITA

    remaining_income = annual_taxable_income
    total_tax = Decimal("0")
    bands_breakdown = []

    for lower, upper, rate in bands:
        if remaining_income <= 0:
            break

        # Calculate band width
        if upper is None:
            band_width = remaining_income
        else:
            band_width = min(remaining_income, upper - lower)

        if band_width <= 0:
            continue

        # Calculate tax for this band
        band_tax = (band_width * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_tax += band_tax

        bands_breakdown.append({
            "lower_limit": str(lower),
            "upper_limit": str(upper) if upper else "unlimited",
            "rate": str(rate),
            "taxable_in_band": str(band_width),
            "tax_amount": str(band_tax)
        })

        remaining_income -= band_width

    # Calculate effective rate
    effective_rate = Decimal("0")
    if annual_taxable_income > 0:
        effective_rate = (total_tax / annual_taxable_income).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )

    return total_tax, bands_breakdown, effective_rate


def calculate_employee_paye(
    basic_salary: Decimal,
    housing_allowance: Decimal = Decimal("0"),
    transport_allowance: Decimal = Decimal("0"),
    other_allowances: Decimal = Decimal("0"),
    bonus: Decimal = Decimal("0"),
    pension_contribution: Optional[Decimal] = None,
    nhf_contribution: Optional[Decimal] = None,
    life_assurance: Decimal = Decimal("0"),
    other_reliefs: Decimal = Decimal("0"),
    months_in_period: int = 1,
    tax_date: Optional[date] = None,
) -> Dict:
    """
    Complete PAYE calculation for an employee.

    Args:
        basic_salary: Monthly basic salary
        housing_allowance: Monthly housing allowance
        transport_allowance: Monthly transport allowance
        other_allowances: Other monthly allowances
        bonus: Monthly bonus (taxable)
        pension_contribution: Optional custom pension (default 8% of basic + housing + transport)
        nhf_contribution: Optional custom NHF (default 2.5% of basic)
        life_assurance: Monthly life assurance premium (deductible)
        other_reliefs: Other relief amounts
        months_in_period: Number of months (for annual projection)
        tax_date: Date to determine applicable tax law

    Returns:
        Dictionary with complete PAYE breakdown
    """
    # Calculate gross income
    monthly_gross = basic_salary + housing_allowance + transport_allowance + other_allowances + bonus
    annual_gross = monthly_gross * 12

    # Calculate pension if not provided (8% of basic + housing + transport)
    if pension_contribution is None:
        pensionable = basic_salary + housing_allowance + transport_allowance
        pension_contribution = (pensionable * PENSION_EMPLOYEE_RATE).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    # Calculate NHF if not provided (2.5% of basic)
    if nhf_contribution is None:
        nhf_contribution = (basic_salary * NHF_RATE).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    # Annualize contributions
    annual_pension = pension_contribution * 12
    annual_nhf = nhf_contribution * 12
    annual_other_reliefs = (other_reliefs + life_assurance) * 12

    # Calculate CRA
    cra_fixed, cra_variable, total_cra = calculate_cra(annual_gross, tax_date)

    # Total reliefs
    total_reliefs = total_cra + annual_pension + annual_nhf + annual_other_reliefs

    # Taxable income
    annual_taxable = max(annual_gross - total_reliefs, Decimal("0"))

    # Calculate tax
    annual_tax, bands_breakdown, effective_rate = calculate_paye(annual_taxable, tax_date)

    # Monthly tax
    monthly_tax = (annual_tax / 12).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "gross_income": {
            "basic_salary": str(basic_salary),
            "housing_allowance": str(housing_allowance),
            "transport_allowance": str(transport_allowance),
            "other_allowances": str(other_allowances),
            "monthly_gross": str(monthly_gross),
            "annual_gross": str(annual_gross),
        },
        "reliefs": {
            "cra_fixed": str(cra_fixed),
            "cra_variable": str(cra_variable),
            "total_cra": str(total_cra),
            "pension_contribution": str(annual_pension),
            "nhf_contribution": str(annual_nhf),
            "other_reliefs": str(annual_other_reliefs),
            "total_reliefs": str(total_reliefs),
        },
        "tax_calculation": {
            "annual_taxable_income": str(annual_taxable),
            "tax_bands_breakdown": bands_breakdown,
            "annual_tax": str(annual_tax),
            "monthly_tax": str(monthly_tax),
            "effective_rate": str(effective_rate),
        }
    }


def get_paye_filing_deadline(period: str) -> date:
    """
    Get PAYE filing deadline for a period.

    Args:
        period: Period string like "2024-01"

    Returns:
        Filing deadline date (10th of following month)
    """
    year, month = map(int, period.split("-"))

    # Move to next month
    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1

    return date(next_year, next_month, PAYE_FILING_DEADLINE_DAY)


def get_tax_filing_calendar(
    year: int,
    tax_types: Optional[List[NigerianTaxType]] = None
) -> List[Dict]:
    """
    Generate tax filing calendar for a year.

    Args:
        year: Calendar year
        tax_types: Optional list of tax types to include

    Returns:
        List of filing deadlines with dates and descriptions
    """
    if tax_types is None:
        tax_types = [NigerianTaxType.VAT, NigerianTaxType.WHT, NigerianTaxType.PAYE]

    calendar = []

    for month in range(1, 13):
        period = f"{year}-{month:02d}"
        _, last_day = monthrange(year, month)

        if NigerianTaxType.VAT in tax_types:
            calendar.append({
                "tax_type": NigerianTaxType.VAT.value,
                "period": period,
                "period_start": date(year, month, 1),
                "period_end": date(year, month, last_day),
                "due_date": get_vat_filing_deadline(period),
                "description": f"VAT Return for {period}"
            })

        if NigerianTaxType.PAYE in tax_types:
            calendar.append({
                "tax_type": NigerianTaxType.PAYE.value,
                "period": period,
                "period_start": date(year, month, 1),
                "period_end": date(year, month, last_day),
                "due_date": get_paye_filing_deadline(period),
                "description": f"PAYE Return for {period}"
            })

    # Add annual CIT deadline (6 months after year end)
    if NigerianTaxType.CIT in tax_types:
        cit_due = date(year + 1, 6, 30)  # Assuming Dec year-end
        calendar.append({
            "tax_type": NigerianTaxType.CIT.value,
            "period": str(year),
            "period_start": date(year, 1, 1),
            "period_end": date(year, 12, 31),
            "due_date": cit_due,
            "description": f"CIT Return for {year}"
        })

    # Sort by due date
    calendar.sort(key=lambda x: x["due_date"])

    return calendar


def format_naira(amount: Decimal) -> str:
    """Format amount as Nigerian Naira."""
    return f"₦{amount:,.2f}"


def generate_tin_format() -> str:
    """
    Nigerian TIN format validation pattern.
    Format: XXXXXXXXXX (10 digits for individual) or XXXXXXXX-XXXX (for corporate)
    """
    return r"^\d{8,10}(-\d{4})?$"


def validate_tin(tin: str) -> bool:
    """
    Validate Nigerian TIN format.

    Args:
        tin: Tax Identification Number

    Returns:
        True if valid format
    """
    import re
    pattern = generate_tin_format()
    return bool(re.match(pattern, tin.replace(" ", "").replace("-", "")))
