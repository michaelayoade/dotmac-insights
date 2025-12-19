"""
Payroll Tax Integration Endpoints

Provides tax calculation services for HR payroll module.
Called during salary slip generation to compute statutory deductions.
Respects employment type eligibility for each deduction type.
"""

from datetime import date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.database import get_db
from app.api.tax.helpers import (
    calculate_all_statutory_deductions,
    calculate_pension_contributions,
    calculate_nhf_contribution,
    calculate_nhis_contributions,
    calculate_nsitf_contribution,
    calculate_itf_contribution,
    is_paye_exempt,
    get_applicable_tax_law,
    MINIMUM_WAGE_MONTHLY,
    MINIMUM_WAGE_ANNUAL,
)
from app.api.tax.deps import get_single_company
from app.models.hr_settings import EmploymentType, EmploymentTypeDeductionConfig

router = APIRouter(prefix="/payroll-tax", tags=["Payroll Tax Integration"])

# Cache for employment type configs (cleared on app restart)
_employment_type_config_cache: Dict[str, Dict[str, Any]] = {}


# ============= HELPER FUNCTIONS =============

def get_employment_type_config(
    db: Session,
    employment_type: Optional[str],
    company: str = "default",
) -> Dict[str, Any]:
    """
    Get deduction eligibility configuration for an employment type.

    Returns dict with boolean flags for each deduction type:
    - paye_applicable
    - pension_applicable
    - nhf_applicable
    - nhis_applicable
    - nsitf_applicable
    - itf_applicable
    """
    # Default config (all deductions apply)
    default_config = {
        "paye_applicable": True,
        "pension_applicable": True,
        "nhf_applicable": True,
        "nhis_applicable": True,
        "nsitf_applicable": True,
        "itf_applicable": True,
        "pension_min_service_months": 0,
        "is_payroll_employee": True,
    }

    if not employment_type:
        return default_config

    # Normalize employment type to enum value
    emp_type_upper = employment_type.upper().replace("-", "_").replace(" ", "_")

    # Check cache first
    cache_key = f"{company}:{emp_type_upper}"
    if cache_key in _employment_type_config_cache:
        return _employment_type_config_cache[cache_key]

    # Try to match to enum
    try:
        emp_type_enum = EmploymentType(emp_type_upper)
    except ValueError:
        # Try common mappings
        type_mappings = {
            "FULL_TIME": EmploymentType.PERMANENT,
            "FULLTIME": EmploymentType.PERMANENT,
            "PART_TIME": EmploymentType.PART_TIME,
            "PARTTIME": EmploymentType.PART_TIME,
            "CONTRACTUAL": EmploymentType.CONTRACT,
            "INTERNSHIP": EmploymentType.INTERN,
            "SIWES": EmploymentType.INTERN,
            "CORPER": EmploymentType.NYSC,
            "PROBATIONARY": EmploymentType.PROBATION,
            "DAILY": EmploymentType.CASUAL,
            "EXPAT": EmploymentType.EXPATRIATE,
        }
        emp_type_enum = type_mappings.get(emp_type_upper)

        if emp_type_enum is None:
            # Unknown type - use default (all deductions apply)
            _employment_type_config_cache[cache_key] = default_config
            return default_config

    # Look up in database
    config = db.query(EmploymentTypeDeductionConfig).filter(
        and_(
            EmploymentTypeDeductionConfig.company == company,
            EmploymentTypeDeductionConfig.employment_type == emp_type_enum,
            EmploymentTypeDeductionConfig.is_active == True,
        )
    ).first()

    if not config:
        # Try default company
        config = db.query(EmploymentTypeDeductionConfig).filter(
            and_(
                EmploymentTypeDeductionConfig.company == "default",
                EmploymentTypeDeductionConfig.employment_type == emp_type_enum,
                EmploymentTypeDeductionConfig.is_active == True,
            )
        ).first()

    if config:
        result = {
            "paye_applicable": config.paye_applicable,
            "pension_applicable": config.pension_applicable,
            "nhf_applicable": config.nhf_applicable,
            "nhis_applicable": config.nhis_applicable,
            "nsitf_applicable": config.nsitf_applicable,
            "itf_applicable": config.itf_applicable,
            "pension_min_service_months": config.pension_min_service_months,
            "is_payroll_employee": config.is_payroll_employee,
        }
    else:
        result = default_config

    # Cache result
    _employment_type_config_cache[cache_key] = result
    return result


def clear_employment_type_config_cache():
    """Clear the employment type config cache (call after config updates)."""
    global _employment_type_config_cache
    _employment_type_config_cache = {}


# ============= SCHEMAS =============

class SalaryInput(BaseModel):
    """Input for salary tax calculation."""
    employee_id: int
    employee_name: str
    employment_type: Optional[str] = None  # PERMANENT, CONTRACT, INTERN, etc.
    months_of_service: Optional[int] = None  # For pension eligibility check
    basic_salary: Decimal = Field(..., gt=0)
    housing_allowance: Decimal = Field(default=Decimal("0"), ge=0)
    transport_allowance: Decimal = Field(default=Decimal("0"), ge=0)
    other_allowances: Decimal = Field(default=Decimal("0"), ge=0)
    # These are now derived from employment_type config, but can be overridden
    include_paye: Optional[bool] = None
    include_pension: Optional[bool] = None
    include_nhf: Optional[bool] = None
    include_nhis: Optional[bool] = None


class BulkSalaryInput(BaseModel):
    """Input for bulk salary tax calculation."""
    employees: List[SalaryInput]
    payroll_period: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    include_employer_costs: bool = True


class PensionBreakdown(BaseModel):
    """Pension contribution breakdown."""
    pensionable_earnings: Decimal
    employee_contribution: Decimal
    employer_contribution: Decimal
    total_contribution: Decimal
    employee_rate: Decimal
    employer_rate: Decimal


class PAYEBreakdown(BaseModel):
    """PAYE tax breakdown."""
    monthly: Decimal
    annual: Decimal
    effective_rate: Decimal
    bands_breakdown: List[dict]


class ReliefsBreakdown(BaseModel):
    """Tax reliefs breakdown."""
    cra_fixed: Decimal
    cra_variable: Decimal
    total_cra: Decimal


class EmployeeDeductionsTotals(BaseModel):
    """Employee deduction totals."""
    employee_deductions: Decimal
    employer_contributions: Decimal
    net_pay: Decimal


class EmploymentTypeEligibility(BaseModel):
    """Employment type deduction eligibility."""
    employment_type: Optional[str] = None
    paye_applicable: bool = True
    pension_applicable: bool = True
    nhf_applicable: bool = True
    nhis_applicable: bool = True
    nsitf_applicable: bool = True
    itf_applicable: bool = True


class StatutoryDeductionsResponse(BaseModel):
    """Complete statutory deductions response."""
    employee_id: int
    employee_name: str
    employment_type: Optional[str] = None
    gross_monthly: Decimal
    gross_annual: Decimal
    is_paye_exempt: bool
    tax_law: str

    # Employment type eligibility info
    eligibility: EmploymentTypeEligibility

    paye: PAYEBreakdown
    reliefs: ReliefsBreakdown
    pension: PensionBreakdown

    nhf_contribution: Optional[Decimal] = None
    nhis_employee: Optional[Decimal] = None
    nhis_employer: Optional[Decimal] = None
    nsitf_employer: Decimal
    itf_monthly_provision: Decimal

    totals: EmployeeDeductionsTotals

    # For salary slip integration
    deductions_for_slip: dict


class BulkDeductionsResponse(BaseModel):
    """Bulk calculation response."""
    payroll_period: str
    tax_law: str
    employee_count: int
    total_gross: Decimal
    total_paye: Decimal
    total_pension_employee: Decimal
    total_pension_employer: Decimal
    total_nhf: Decimal
    total_nhis_employee: Decimal
    total_nhis_employer: Decimal
    total_nsitf: Decimal
    total_itf: Decimal
    total_employee_deductions: Decimal
    total_employer_contributions: Decimal
    total_net_pay: Decimal
    employees: List[StatutoryDeductionsResponse]


class TaxRatesResponse(BaseModel):
    """Current tax rates for display."""
    tax_law: str
    effective_date: str
    minimum_wage_monthly: Decimal
    minimum_wage_annual: Decimal
    paye_exempt_threshold: Decimal
    paye_bands: List[dict]
    pension_employee_rate: Decimal
    pension_employer_rate: Decimal
    nhf_rate: Decimal
    nhis_employee_rate: Decimal
    nhis_employer_rate: Decimal
    nsitf_rate: Decimal
    itf_rate: Decimal


# ============= ENDPOINTS =============

@router.post("/calculate", response_model=StatutoryDeductionsResponse)
def calculate_employee_deductions(
    data: SalaryInput,
    payroll_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """
    Calculate all statutory deductions for a single employee.

    This endpoint is called by HR payroll during salary slip generation.
    Respects employment type eligibility for each deduction type.

    Returns:
    - PAYE (income tax) - if applicable for employment type
    - Pension (employee & employer) - if applicable
    - NHF (if applicable)
    - NHIS (if applicable)
    - NSITF (employer) - if applicable
    - ITF provision (employer) - if applicable

    Also returns `deductions_for_slip` dict ready for salary slip integration.
    """
    # Get employment type deduction configuration
    emp_config = get_employment_type_config(db, data.employment_type)

    # Determine which deductions to include (explicit override > config > default)
    include_paye = data.include_paye if data.include_paye is not None else emp_config["paye_applicable"]
    include_pension = data.include_pension if data.include_pension is not None else emp_config["pension_applicable"]
    include_nhf = data.include_nhf if data.include_nhf is not None else emp_config["nhf_applicable"]
    include_nhis = data.include_nhis if data.include_nhis is not None else emp_config["nhis_applicable"]

    # Check pension minimum service requirement
    if include_pension and emp_config["pension_min_service_months"] > 0:
        if data.months_of_service is not None and data.months_of_service < emp_config["pension_min_service_months"]:
            include_pension = False

    result = calculate_all_statutory_deductions(
        basic_salary=data.basic_salary,
        housing_allowance=data.housing_allowance,
        transport_allowance=data.transport_allowance,
        other_allowances=data.other_allowances,
        include_paye=include_paye,
        include_pension=include_pension,
        include_nhf=include_nhf,
        include_nhis=include_nhis,
        include_nsitf=emp_config["nsitf_applicable"],
        include_itf=emp_config["itf_applicable"],
        tax_date=payroll_date,
    )

    # Build deductions dict for salary slip
    deductions_for_slip = {}
    if include_paye and result["paye"]["monthly"] > Decimal("0"):
        deductions_for_slip["PAYE"] = result["paye"]["monthly"]
    if include_pension and result["pension"]["employee_contribution"] > Decimal("0"):
        deductions_for_slip["Pension - Employee"] = result["pension"]["employee_contribution"]
    if include_nhf and result["nhf"] and result["nhf"]["contribution"] > Decimal("0"):
        deductions_for_slip["NHF"] = result["nhf"]["contribution"]
    if include_nhis and result["nhis"] and result["nhis"]["employee_contribution"] > Decimal("0"):
        deductions_for_slip["NHIS - Employee"] = result["nhis"]["employee_contribution"]

    eligibility = EmploymentTypeEligibility(
        employment_type=data.employment_type,
        paye_applicable=emp_config["paye_applicable"],
        pension_applicable=emp_config["pension_applicable"],
        nhf_applicable=emp_config["nhf_applicable"],
        nhis_applicable=emp_config["nhis_applicable"],
        nsitf_applicable=emp_config["nsitf_applicable"],
        itf_applicable=emp_config["itf_applicable"],
    )

    return StatutoryDeductionsResponse(
        employee_id=data.employee_id,
        employee_name=data.employee_name,
        employment_type=data.employment_type,
        gross_monthly=result["gross_monthly"],
        gross_annual=result["gross_annual"],
        is_paye_exempt=result["is_paye_exempt"],
        tax_law=result["tax_law"],
        eligibility=eligibility,
        paye=PAYEBreakdown(**result["paye"]),
        reliefs=ReliefsBreakdown(**result["reliefs"]),
        pension=PensionBreakdown(**result["pension"]),
        nhf_contribution=result["nhf"]["contribution"] if result["nhf"] else None,
        nhis_employee=result["nhis"]["employee_contribution"] if result["nhis"] else None,
        nhis_employer=result["nhis"]["employer_contribution"] if result["nhis"] else None,
        nsitf_employer=result["nsitf"]["employer_contribution"] if emp_config["nsitf_applicable"] else Decimal("0"),
        itf_monthly_provision=result["itf"]["monthly_provision"] if emp_config["itf_applicable"] else Decimal("0"),
        totals=EmployeeDeductionsTotals(**result["totals"]),
        deductions_for_slip=deductions_for_slip,
    )


@router.post("/calculate-bulk", response_model=BulkDeductionsResponse)
def calculate_bulk_deductions(
    data: BulkSalaryInput,
    db: Session = Depends(get_db),
):
    """
    Calculate statutory deductions for multiple employees.

    Used for batch payroll processing. Returns individual breakdowns
    plus company-wide totals for reporting.
    """
    # Parse payroll period to get tax date
    year, month = map(int, data.payroll_period.split("-"))
    payroll_date = date(year, month, 1)

    employees = []
    totals = {
        "gross": Decimal("0"),
        "paye": Decimal("0"),
        "pension_employee": Decimal("0"),
        "pension_employer": Decimal("0"),
        "nhf": Decimal("0"),
        "nhis_employee": Decimal("0"),
        "nhis_employer": Decimal("0"),
        "nsitf": Decimal("0"),
        "itf": Decimal("0"),
        "employee_deductions": Decimal("0"),
        "employer_contributions": Decimal("0"),
        "net_pay": Decimal("0"),
    }

    for emp in data.employees:
        emp_config = get_employment_type_config(db, emp.employment_type)
        include_paye = emp.include_paye if emp.include_paye is not None else emp_config["paye_applicable"]
        include_pension = emp.include_pension if emp.include_pension is not None else emp_config["pension_applicable"]
        include_nhf = emp.include_nhf if emp.include_nhf is not None else emp_config["nhf_applicable"]
        include_nhis = emp.include_nhis if emp.include_nhis is not None else emp_config["nhis_applicable"]
        include_nsitf = emp_config["nsitf_applicable"]
        include_itf = emp_config["itf_applicable"]

        if include_pension and emp_config["pension_min_service_months"] > 0:
            if emp.months_of_service is not None and emp.months_of_service < emp_config["pension_min_service_months"]:
                include_pension = False

        result = calculate_all_statutory_deductions(
            basic_salary=emp.basic_salary,
            housing_allowance=emp.housing_allowance,
            transport_allowance=emp.transport_allowance,
            other_allowances=emp.other_allowances,
            include_paye=include_paye,
            include_pension=include_pension,
            include_nhf=include_nhf,
            include_nhis=include_nhis,
            include_nsitf=include_nsitf,
            include_itf=include_itf,
            tax_date=payroll_date,
        )

        # Build deductions for slip
        deductions_for_slip = {}
        if include_paye and result["paye"]["monthly"] > Decimal("0"):
            deductions_for_slip["PAYE"] = result["paye"]["monthly"]
        if include_pension and result["pension"]["employee_contribution"] > Decimal("0"):
            deductions_for_slip["Pension - Employee"] = result["pension"]["employee_contribution"]
        if include_nhf and result["nhf"] and result["nhf"]["contribution"] > Decimal("0"):
            deductions_for_slip["NHF"] = result["nhf"]["contribution"]
        if include_nhis and result["nhis"] and result["nhis"]["employee_contribution"] > Decimal("0"):
            deductions_for_slip["NHIS - Employee"] = result["nhis"]["employee_contribution"]

        eligibility = EmploymentTypeEligibility(
            employment_type=emp.employment_type,
            paye_applicable=emp_config["paye_applicable"],
            pension_applicable=emp_config["pension_applicable"],
            nhf_applicable=emp_config["nhf_applicable"],
            nhis_applicable=emp_config["nhis_applicable"],
            nsitf_applicable=emp_config["nsitf_applicable"],
            itf_applicable=emp_config["itf_applicable"],
        )

        emp_response = StatutoryDeductionsResponse(
            employee_id=emp.employee_id,
            employee_name=emp.employee_name,
            employment_type=emp.employment_type,
            gross_monthly=result["gross_monthly"],
            gross_annual=result["gross_annual"],
            is_paye_exempt=result["is_paye_exempt"],
            tax_law=result["tax_law"],
            eligibility=eligibility,
            paye=PAYEBreakdown(**result["paye"]),
            reliefs=ReliefsBreakdown(**result["reliefs"]),
            pension=PensionBreakdown(**result["pension"]),
            nhf_contribution=result["nhf"]["contribution"] if result["nhf"] else None,
            nhis_employee=result["nhis"]["employee_contribution"] if result["nhis"] else None,
            nhis_employer=result["nhis"]["employer_contribution"] if result["nhis"] else None,
            nsitf_employer=result["nsitf"]["employer_contribution"] if include_nsitf else Decimal("0"),
            itf_monthly_provision=result["itf"]["monthly_provision"] if include_itf else Decimal("0"),
            totals=EmployeeDeductionsTotals(**result["totals"]),
            deductions_for_slip=deductions_for_slip,
        )
        employees.append(emp_response)

        # Accumulate totals
        totals["gross"] += result["gross_monthly"]
        totals["paye"] += result["paye"]["monthly"]
        totals["pension_employee"] += result["pension"]["employee_contribution"]
        totals["pension_employer"] += result["pension"]["employer_contribution"]
        if result["nhf"]:
            totals["nhf"] += result["nhf"]["contribution"]
        if result["nhis"]:
            totals["nhis_employee"] += result["nhis"]["employee_contribution"]
            totals["nhis_employer"] += result["nhis"]["employer_contribution"]
        totals["nsitf"] += result["nsitf"]["employer_contribution"]
        totals["itf"] += result["itf"]["monthly_provision"]
        totals["employee_deductions"] += result["totals"]["employee_deductions"]
        totals["employer_contributions"] += result["totals"]["employer_contributions"]
        totals["net_pay"] += result["totals"]["net_pay"]

    return BulkDeductionsResponse(
        payroll_period=data.payroll_period,
        tax_law=get_applicable_tax_law(payroll_date),
        employee_count=len(employees),
        total_gross=totals["gross"],
        total_paye=totals["paye"],
        total_pension_employee=totals["pension_employee"],
        total_pension_employer=totals["pension_employer"],
        total_nhf=totals["nhf"],
        total_nhis_employee=totals["nhis_employee"],
        total_nhis_employer=totals["nhis_employer"],
        total_nsitf=totals["nsitf"],
        total_itf=totals["itf"],
        total_employee_deductions=totals["employee_deductions"],
        total_employer_contributions=totals["employer_contributions"],
        total_net_pay=totals["net_pay"],
        employees=employees,
    )


@router.get("/rates", response_model=TaxRatesResponse)
def get_current_tax_rates(
    as_of_date: Optional[date] = None,
):
    """
    Get current statutory tax rates.

    Returns all applicable rates for display in HR settings or payroll UI.
    Automatically selects PITA or NTA 2025 based on date.
    """
    from app.api.tax.helpers import (
        PAYE_BANDS_PITA,
        PAYE_BANDS_NTA_2025,
        PENSION_EMPLOYEE_RATE,
        PENSION_EMPLOYER_RATE,
        NHF_RATE,
        NHIS_EMPLOYEE_RATE,
        NHIS_EMPLOYER_RATE,
        NSITF_EMPLOYER_RATE,
        ITF_RATE,
        PAYE_EXEMPTION_THRESHOLD,
    )

    tax_law = get_applicable_tax_law(as_of_date)

    if tax_law == "NTA_2025":
        bands = PAYE_BANDS_NTA_2025
        effective_date = "2026-01-01"
    else:
        bands = PAYE_BANDS_PITA
        effective_date = "Current (PITA)"

    bands_display = [
        {
            "lower": str(lower),
            "upper": str(upper) if upper else "unlimited",
            "rate_percent": float(rate * 100),
        }
        for lower, upper, rate in bands
    ]

    return TaxRatesResponse(
        tax_law=tax_law,
        effective_date=effective_date,
        minimum_wage_monthly=MINIMUM_WAGE_MONTHLY,
        minimum_wage_annual=MINIMUM_WAGE_ANNUAL,
        paye_exempt_threshold=PAYE_EXEMPTION_THRESHOLD,
        paye_bands=bands_display,
        pension_employee_rate=PENSION_EMPLOYEE_RATE,
        pension_employer_rate=PENSION_EMPLOYER_RATE,
        nhf_rate=NHF_RATE,
        nhis_employee_rate=NHIS_EMPLOYEE_RATE,
        nhis_employer_rate=NHIS_EMPLOYER_RATE,
        nsitf_rate=NSITF_EMPLOYER_RATE,
        itf_rate=ITF_RATE,
    )


@router.get("/check-exemption")
def check_paye_exemption(
    monthly_gross: Decimal,
):
    """
    Quick check if salary is PAYE exempt.

    Employees earning <= N70,000/month (N840,000/year) are exempt.
    """
    annual_gross = monthly_gross * 12
    exempt = is_paye_exempt(annual_gross)

    return {
        "monthly_gross": monthly_gross,
        "annual_gross": annual_gross,
        "is_exempt": exempt,
        "exemption_threshold_monthly": MINIMUM_WAGE_MONTHLY,
        "exemption_threshold_annual": MINIMUM_WAGE_ANNUAL,
    }


# ============= HR INTEGRATION UTILITIES =============

def calculate_slip_deductions(
    basic_salary: Decimal,
    housing_allowance: Decimal = Decimal("0"),
    transport_allowance: Decimal = Decimal("0"),
    other_allowances: Decimal = Decimal("0"),
    employment_type: Optional[str] = None,
    months_of_service: Optional[int] = None,
    db: Optional[Any] = None,  # Optional SQLAlchemy session
    include_paye: Optional[bool] = None,
    include_pension: Optional[bool] = None,
    include_nhf: Optional[bool] = None,
    include_nhis: Optional[bool] = None,
    include_nsitf: Optional[bool] = None,
    include_itf: Optional[bool] = None,
    payroll_date: Optional[date] = None,
) -> dict:
    """
    Utility function for HR payroll to calculate statutory deductions.
    Respects employment type eligibility when db session is provided.

    Call this during salary slip generation to get computed deductions.

    Usage in HR payroll:
    ```python
    from app.api.tax.payroll_integration import calculate_slip_deductions

    # During slip generation - with employment type awareness
    deductions = calculate_slip_deductions(
        basic_salary=assignment.base or Decimal("0"),
        housing_allowance=get_component_amount(structure, "Housing Allowance"),
        transport_allowance=get_component_amount(structure, "Transport Allowance"),
        other_allowances=other_earnings,
        employment_type=employee.employment_type,  # e.g., "CONTRACT", "INTERN"
        months_of_service=months_since_joining,
        db=db,  # Pass session for config lookup
        payroll_date=entry.posting_date,
    )

    # Only add deductions that are applicable for this employment type
    if deductions["paye"] > 0:
        slip_deduction = SalarySlipDeduction(
            salary_slip_id=slip.id,
            salary_component="PAYE",
            amount=deductions["paye"],
        )
        db.add(slip_deduction)
    ```

    Returns:
        Dict with deduction amounts ready for salary slip, including eligibility info
    """
    # Get employment type config if db is provided
    if db is not None and employment_type:
        emp_config = get_employment_type_config(db, employment_type)
    else:
        emp_config = {
            "paye_applicable": True,
            "pension_applicable": True,
            "nhf_applicable": True,
            "nhis_applicable": True,
            "nsitf_applicable": True,
            "itf_applicable": True,
            "pension_min_service_months": 0,
        }

    # Determine eligibility (explicit override > config > default True)
    paye_eligible = include_paye if include_paye is not None else emp_config["paye_applicable"]
    pension_eligible = include_pension if include_pension is not None else emp_config["pension_applicable"]
    nhf_eligible = include_nhf if include_nhf is not None else emp_config["nhf_applicable"]
    nhis_eligible = include_nhis if include_nhis is not None else emp_config["nhis_applicable"]
    nsitf_eligible = include_nsitf if include_nsitf is not None else emp_config["nsitf_applicable"]
    itf_eligible = include_itf if include_itf is not None else emp_config["itf_applicable"]

    # Check pension minimum service requirement
    if pension_eligible and emp_config["pension_min_service_months"] > 0:
        if months_of_service is not None and months_of_service < emp_config["pension_min_service_months"]:
            pension_eligible = False

    result = calculate_all_statutory_deductions(
        basic_salary=basic_salary,
        housing_allowance=housing_allowance,
        transport_allowance=transport_allowance,
        other_allowances=other_allowances,
        include_paye=paye_eligible,
        include_pension=pension_eligible,
        include_nhf=nhf_eligible,
        include_nhis=nhis_eligible,
        include_nsitf=nsitf_eligible,
        include_itf=itf_eligible,
        tax_date=payroll_date,
    )

    return {
        "paye": result["paye"]["monthly"],
        "pension_employee": result["pension"]["employee_contribution"],
        "pension_employer": result["pension"]["employer_contribution"],
        "nhf": result["nhf"]["contribution"] if result["nhf"] else Decimal("0"),
        "nhis_employee": result["nhis"]["employee_contribution"] if result["nhis"] else Decimal("0"),
        "nhis_employer": result["nhis"]["employer_contribution"] if result["nhis"] else Decimal("0"),
        "nsitf_employer": result["nsitf"]["employer_contribution"],
        "itf_provision": result["itf"]["monthly_provision"],
        "total_employee_deductions": result["totals"]["employee_deductions"],
        "total_employer_contributions": result["totals"]["employer_contributions"],
        "net_pay": result["totals"]["net_pay"],
        "gross_monthly": result["gross_monthly"],
        "is_paye_exempt": result["is_paye_exempt"],
        # Eligibility info for debugging/display
        "employment_type": employment_type,
        "eligibility": {
            "paye": paye_eligible,
            "pension": pension_eligible,
            "nhf": nhf_eligible,
            "nhis": nhis_eligible,
            "nsitf": nsitf_eligible,
            "itf": itf_eligible,
        },
    }


# Standard salary component names for integration
STATUTORY_COMPONENTS = {
    "PAYE": {
        "name": "PAYE",
        "abbr": "PAYE",
        "type": "DEDUCTION",
        "description": "Pay As You Earn - Nigerian income tax",
        "is_tax_applicable": False,  # It IS the tax
    },
    "PENSION_EMPLOYEE": {
        "name": "Pension - Employee",
        "abbr": "PEN-E",
        "type": "DEDUCTION",
        "description": "Employee pension contribution (8%)",
        "is_tax_applicable": False,  # Pension is tax-exempt
    },
    "PENSION_EMPLOYER": {
        "name": "Pension - Employer",
        "abbr": "PEN-R",
        "type": "EMPLOYER_CONTRIBUTION",
        "description": "Employer pension contribution (10%)",
    },
    "NHF": {
        "name": "NHF",
        "abbr": "NHF",
        "type": "DEDUCTION",
        "description": "National Housing Fund (2.5%)",
        "is_tax_applicable": False,
    },
    "NHIS_EMPLOYEE": {
        "name": "NHIS - Employee",
        "abbr": "NHIS-E",
        "type": "DEDUCTION",
        "description": "National Health Insurance - Employee (5%)",
    },
    "NHIS_EMPLOYER": {
        "name": "NHIS - Employer",
        "abbr": "NHIS-R",
        "type": "EMPLOYER_CONTRIBUTION",
        "description": "National Health Insurance - Employer (10%)",
    },
    "NSITF": {
        "name": "NSITF",
        "abbr": "NSITF",
        "type": "EMPLOYER_CONTRIBUTION",
        "description": "Nigeria Social Insurance Trust Fund (1%)",
    },
    "ITF": {
        "name": "ITF",
        "abbr": "ITF",
        "type": "EMPLOYER_CONTRIBUTION",
        "description": "Industrial Training Fund (1%)",
    },
}
