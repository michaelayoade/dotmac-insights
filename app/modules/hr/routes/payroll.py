"""
HR Payroll Routes - Payroll Management with SSR + HTMX.

Permission Requirements:
- hr:read - View salary slips, structures, payroll runs
- hr:write - Process payroll

Uses PayrollService for all business logic.
"""
from decimal import Decimal
from typing import Optional
from datetime import date

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.core.security import is_htmx_request
from sqlalchemy.exc import SQLAlchemyError
from app.services.hr.payroll import PayrollService
from app.services.hr.employees import EmployeeService
from app.services.hr.employee_types import EmployeeFilters
from app.services.hr.payroll_types import (
    SalarySlipFilters,
    SalaryStructureFilters,
    PayrollEntryFilters,
    SalaryStructureCreateData,
    SalaryStructureUpdateData,
    StructureEarningData,
    StructureDeductionData,
    SalarySlipCreateData,
)
from app.services.types import PaginationParams
from app.services.hr.errors import SalarySlipNotFoundError, SalaryStructureNotFoundError, EmployeeNotFoundError
from app.models.hr_payroll import SalaryComponentType

RequireHRRead = Depends(require_scope("hr:read"))
RequireHRWrite = Depends(require_scope("hr:write"))

router = APIRouter(prefix="/payroll", tags=["hr-payroll"])
templates = get_template_env()


@router.get("", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def payroll_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Salary slips list page."""
    service = PayrollService(db, user)
    offset = (page - 1) * per_page

    filters = SalarySlipFilters()
    pagination = PaginationParams(offset=offset, limit=per_page)
    try:
        result = service.list_salary_slips(filters, pagination)
    except SQLAlchemyError:
        result = None

    # Apply search filter post-query if needed (service handles employee_id filter)
    slips = result.items if result else []
    if q:
        q_lower = q.lower()
        slips = [
            s for s in slips
            if (s.employee_name and q_lower in s.employee_name.lower())
            or (s.employee and q_lower in s.employee.lower())
        ]
        total = len(slips)
    else:
        total = result.total if result else 0

    context = get_base_context(request, response, user, csrf_token)
    context["slips"] = slips
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/payroll/partials/slips_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Salary Slips"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Payroll"},
    ])

    template = templates.get_template("modules/hr/templates/payroll/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def payroll_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    return await payroll_list(request, response, user, csrf_token, db, q, page, per_page)


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def salary_slip_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New salary slip form."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Salary Slip"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Payroll", "href": "/hr/payroll"},
        {"label": "New Slip"},
    ])
    context["employees"] = get_employee_options(db)
    context["form_data"] = {
        "employee_id": "",
        "posting_date": "",
        "start_date": "",
        "end_date": "",
        "gross_pay": "",
        "total_deduction": "",
        "net_pay": "",
        "currency": "NGN",
        "company": "",
        "bank_name": "",
        "bank_account_no": "",
    }
    context["errors"] = {}
    template = templates.get_template("modules/hr/templates/payroll/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def salary_slip_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _: CSRFProtect,
):
    """Create a new salary slip."""
    form = await request.form()
    employee_id = _form_str(form.get("employee_id"))
    posting_date = _form_date(form.get("posting_date"))
    start_date = _form_date(form.get("start_date"))
    end_date = _form_date(form.get("end_date"))
    gross_pay = _form_decimal(form.get("gross_pay"))
    total_deduction = _form_decimal(form.get("total_deduction"))
    net_pay = _form_decimal(form.get("net_pay"))
    currency = _form_str(form.get("currency")) or "NGN"
    company = _form_str(form.get("company"))
    bank_name = _form_str(form.get("bank_name"))
    bank_account_no = _form_str(form.get("bank_account_no"))

    errors: dict[str, str] = {}
    if not employee_id or not employee_id.isdigit():
        errors["employee_id"] = "Employee is required."
    if not posting_date:
        errors["posting_date"] = "Posting date is required."
    if not start_date:
        errors["start_date"] = "Start date is required."
    if not end_date:
        errors["end_date"] = "End date is required."
    if start_date and end_date and end_date < start_date:
        errors["end_date"] = "End date must be after start date."

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Salary Slip"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Payroll", "href": "/hr/payroll"},
            {"label": "New Slip"},
        ])
        context["employees"] = get_employee_options(db)
        context["form_data"] = {
            "employee_id": employee_id or "",
            "posting_date": form.get("posting_date") or "",
            "start_date": form.get("start_date") or "",
            "end_date": form.get("end_date") or "",
            "gross_pay": form.get("gross_pay") or "",
            "total_deduction": form.get("total_deduction") or "",
            "net_pay": form.get("net_pay") or "",
            "currency": currency,
            "company": company or "",
            "bank_name": bank_name or "",
            "bank_account_no": bank_account_no or "",
        }
        context["errors"] = errors
        template = templates.get_template("modules/hr/templates/payroll/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    employee_service = EmployeeService(db)
    try:
        employee = employee_service.get_employee(int(employee_id))
    except EmployeeNotFoundError:
        errors["employee_id"] = "Employee not found."

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Salary Slip"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Payroll", "href": "/hr/payroll"},
            {"label": "New Slip"},
        ])
        context["employees"] = get_employee_options(db)
        context["form_data"] = {
            "employee_id": employee_id or "",
            "posting_date": form.get("posting_date") or "",
            "start_date": form.get("start_date") or "",
            "end_date": form.get("end_date") or "",
            "gross_pay": form.get("gross_pay") or "",
            "total_deduction": form.get("total_deduction") or "",
            "net_pay": form.get("net_pay") or "",
            "currency": currency,
            "company": company or "",
            "bank_name": bank_name or "",
            "bank_account_no": bank_account_no or "",
        }
        context["errors"] = errors
        template = templates.get_template("modules/hr/templates/payroll/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)
    employee_code = employee.employee_number or employee.name

    service = PayrollService(db, user)
    data = SalarySlipCreateData(
        employee_id=employee.id,
        employee=employee_code,
        employee_name=employee.name,
        department=employee.department,
        designation=employee.designation,
        posting_date=posting_date,
        start_date=start_date,
        end_date=end_date,
        company=company,
        currency=currency,
        gross_pay=gross_pay,
        total_deduction=total_deduction,
        net_pay=net_pay,
        bank_name=bank_name,
        bank_account_no=bank_account_no,
    )
    slip = service.create_salary_slip(data)
    db.commit()
    db.refresh(slip)
    return RedirectResponse(url="/hr/payroll", status_code=303)


@router.get("/structures", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def salary_structures_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Salary structures list page."""
    service = PayrollService(db, user)
    offset = (page - 1) * per_page

    filters = SalaryStructureFilters()
    pagination = PaginationParams(offset=offset, limit=per_page)
    result = service.list_salary_structures(filters, pagination)

    # Apply search filter post-query if needed
    structures = result.items
    if q:
        q_lower = q.lower()
        structures = [
            s for s in structures
            if s.salary_structure_name and q_lower in s.salary_structure_name.lower()
        ]
        total = len(structures)
    else:
        total = result.total

    context = get_base_context(request, response, user, csrf_token)
    context["structures"] = structures
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/payroll/partials/structures_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Salary Structures"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Salary Structures"},
    ])

    template = templates.get_template("modules/hr/templates/payroll/pages/structures_list.html")
    return HTMLResponse(template.render(context))


PAYROLL_FREQUENCIES = [
    ("Monthly", "Monthly"),
    ("Biweekly", "Biweekly"),
    ("Weekly", "Weekly"),
    ("Daily", "Daily"),
]


def _form_str(value: Optional[str]) -> Optional[str]:
    """Return None for empty strings."""
    return value.strip() if value and value.strip() else None


def _form_decimal(value: Optional[str]) -> Decimal:
    """Parse form decimal or return zero."""
    if not value or not value.strip():
        return Decimal("0")
    try:
        return Decimal(value.strip())
    except Exception:
        return Decimal("0")


def _form_date(value: Optional[str]) -> Optional[date]:
    if not value or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def get_employee_options(db: DB):
    """Get employees using EmployeeService."""
    service = EmployeeService(db)
    result = service.list_employees(
        filters=EmployeeFilters(),
        pagination=PaginationParams(offset=0, limit=500),
    )
    employees = sorted(result.items, key=lambda e: e.name or "")
    return employees


def _parse_structure_components(
    form_data: dict,
    service: PayrollService,
) -> tuple[list[StructureEarningData], list[StructureDeductionData]]:
    """Parse earnings and deductions from form data."""
    earnings: list[StructureEarningData] = []
    deductions: list[StructureDeductionData] = []

    # Parse earnings
    earning_ids = form_data.getlist("earning_component_id")
    earning_amounts = form_data.getlist("earning_amount")
    earning_formulas = form_data.getlist("earning_formula")

    for idx, comp_id in enumerate(earning_ids):
        if not comp_id:
            continue
        try:
            component = service.get_salary_component(int(comp_id))
            amount_str = earning_amounts[idx] if idx < len(earning_amounts) else "0"
            formula_str = earning_formulas[idx] if idx < len(earning_formulas) else ""
            use_formula = bool(formula_str and formula_str.strip())

            earnings.append(
                StructureEarningData(
                    salary_component=component.salary_component_name,
                    abbr=component.salary_component_abbr,
                    amount=_form_decimal(amount_str) if not use_formula else Decimal("0"),
                    amount_based_on_formula=use_formula,
                    formula=formula_str.strip() if use_formula else None,
                    idx=idx,
                )
            )
        except Exception:
            continue

    # Parse deductions
    deduction_ids = form_data.getlist("deduction_component_id")
    deduction_amounts = form_data.getlist("deduction_amount")
    deduction_formulas = form_data.getlist("deduction_formula")

    for idx, comp_id in enumerate(deduction_ids):
        if not comp_id:
            continue
        try:
            component = service.get_salary_component(int(comp_id))
            amount_str = deduction_amounts[idx] if idx < len(deduction_amounts) else "0"
            formula_str = deduction_formulas[idx] if idx < len(deduction_formulas) else ""
            use_formula = bool(formula_str and formula_str.strip())

            deductions.append(
                StructureDeductionData(
                    salary_component=component.salary_component_name,
                    abbr=component.salary_component_abbr,
                    amount=_form_decimal(amount_str) if not use_formula else Decimal("0"),
                    amount_based_on_formula=use_formula,
                    formula=formula_str.strip() if use_formula else None,
                    idx=idx,
                )
            )
        except Exception:
            continue

    return earnings, deductions


@router.get("/structures/new", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def salary_structure_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New salary structure form."""
    service = PayrollService(db, user)

    # Get salary components for selection
    earning_components = service.list_salary_components(
        component_type=SalaryComponentType.EARNING,
        include_disabled=False,
    ).items
    deduction_components = service.list_salary_components(
        component_type=SalaryComponentType.DEDUCTION,
        include_disabled=False,
    ).items

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Salary Structure"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Salary Structures", "href": "/hr/payroll/structures"},
        {"label": "New"},
    ])
    context["structure"] = None
    context["form_data"] = None
    context["errors"] = {}
    context["payroll_frequencies"] = PAYROLL_FREQUENCIES
    context["earning_components"] = earning_components
    context["deduction_components"] = deduction_components

    template = templates.get_template("modules/hr/templates/payroll/structures/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/structures", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def salary_structure_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _: CSRFProtect,
):
    """Create a new salary structure."""
    form_data = await request.form()
    service = PayrollService(db, user)

    errors: dict = {}
    name = _form_str(form_data.get("salary_structure_name"))
    if not name:
        errors["salary_structure_name"] = "Structure name is required"

    if errors:
        earning_components = service.list_salary_components(
            component_type=SalaryComponentType.EARNING,
            include_disabled=False,
        ).items
        deduction_components = service.list_salary_components(
            component_type=SalaryComponentType.DEDUCTION,
            include_disabled=False,
        ).items

        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Salary Structure"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Salary Structures", "href": "/hr/payroll/structures"},
            {"label": "New"},
        ])
        context["structure"] = None
        context["form_data"] = dict(form_data)
        context["errors"] = errors
        context["payroll_frequencies"] = PAYROLL_FREQUENCIES
        context["earning_components"] = earning_components
        context["deduction_components"] = deduction_components

        template = templates.get_template("modules/hr/templates/payroll/structures/pages/form.html")
        return HTMLResponse(template.render(context))

    earnings, deductions = _parse_structure_components(form_data, service)

    create_data = SalaryStructureCreateData(
        salary_structure_name=name,
        company=_form_str(form_data.get("company")),
        payroll_frequency=_form_str(form_data.get("payroll_frequency")),
        currency=_form_str(form_data.get("currency")) or "NGN",
        earnings=earnings,
        deductions=deductions,
    )

    structure = service.create_salary_structure(create_data)
    db.commit()

    return RedirectResponse(
        url=f"/hr/payroll/structures/{structure.id}",
        status_code=303,
    )


@router.get("/structures/{structure_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def salary_structure_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    structure_id: int,
):
    """Salary structure detail page."""
    service = PayrollService(db, user)

    try:
        structure = service.get_salary_structure(structure_id)
    except SalaryStructureNotFoundError:
        raise HTTPException(status_code=404, detail="Salary structure not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Structure - {structure.salary_structure_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Salary Structures", "href": "/hr/payroll/structures"},
        {"label": structure.salary_structure_name},
    ])
    context["structure"] = structure

    template = templates.get_template("modules/hr/templates/payroll/structures/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/structures/{structure_id}/edit", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def salary_structure_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    structure_id: int,
):
    """Edit salary structure form."""
    service = PayrollService(db, user)

    try:
        structure = service.get_salary_structure(structure_id)
    except SalaryStructureNotFoundError:
        raise HTTPException(status_code=404, detail="Salary structure not found")

    earning_components = service.list_salary_components(
        component_type=SalaryComponentType.EARNING,
        include_disabled=False,
    ).items
    deduction_components = service.list_salary_components(
        component_type=SalaryComponentType.DEDUCTION,
        include_disabled=False,
    ).items

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit - {structure.salary_structure_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Salary Structures", "href": "/hr/payroll/structures"},
        {"label": structure.salary_structure_name, "href": f"/hr/payroll/structures/{structure.id}"},
        {"label": "Edit"},
    ])
    context["structure"] = structure
    context["form_data"] = None
    context["errors"] = {}
    context["payroll_frequencies"] = PAYROLL_FREQUENCIES
    context["earning_components"] = earning_components
    context["deduction_components"] = deduction_components

    template = templates.get_template("modules/hr/templates/payroll/structures/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/structures/{structure_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def salary_structure_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    structure_id: int,
    _: CSRFProtect,
):
    """Update a salary structure."""
    form_data = await request.form()
    service = PayrollService(db, user)

    try:
        structure = service.get_salary_structure(structure_id)
    except SalaryStructureNotFoundError:
        raise HTTPException(status_code=404, detail="Salary structure not found")

    errors: dict = {}
    name = _form_str(form_data.get("salary_structure_name"))
    if not name:
        errors["salary_structure_name"] = "Structure name is required"

    if errors:
        earning_components = service.list_salary_components(
            component_type=SalaryComponentType.EARNING,
            include_disabled=False,
        ).items
        deduction_components = service.list_salary_components(
            component_type=SalaryComponentType.DEDUCTION,
            include_disabled=False,
        ).items

        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit - {structure.salary_structure_name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Salary Structures", "href": "/hr/payroll/structures"},
            {"label": structure.salary_structure_name, "href": f"/hr/payroll/structures/{structure.id}"},
            {"label": "Edit"},
        ])
        context["structure"] = structure
        context["form_data"] = dict(form_data)
        context["errors"] = errors
        context["payroll_frequencies"] = PAYROLL_FREQUENCIES
        context["earning_components"] = earning_components
        context["deduction_components"] = deduction_components

        template = templates.get_template("modules/hr/templates/payroll/structures/pages/form.html")
        return HTMLResponse(template.render(context))

    earnings, deductions = _parse_structure_components(form_data, service)

    update_data = SalaryStructureUpdateData(
        salary_structure_name=name,
        company=_form_str(form_data.get("company")),
        payroll_frequency=_form_str(form_data.get("payroll_frequency")),
        currency=_form_str(form_data.get("currency")) or "NGN",
        earnings=earnings,
        deductions=deductions,
    )

    service.update_salary_structure(structure_id, update_data)
    db.commit()

    return RedirectResponse(
        url=f"/hr/payroll/structures/{structure_id}",
        status_code=303,
    )


@router.delete("/structures/{structure_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def salary_structure_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    structure_id: int,
    _: CSRFProtect,
):
    """Deactivate a salary structure."""
    service = PayrollService(db, user)

    try:
        service.delete_salary_structure(structure_id)
        db.commit()
    except SalaryStructureNotFoundError:
        raise HTTPException(status_code=404, detail="Salary structure not found")

    response.headers["HX-Redirect"] = "/hr/payroll/structures"
    return HTMLResponse("")


@router.get("/runs", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def payroll_runs_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Payroll runs list page."""
    service = PayrollService(db, user)
    offset = (page - 1) * per_page

    filters = PayrollEntryFilters()
    pagination = PaginationParams(offset=offset, limit=per_page)
    result = service.list_payroll_entries(filters, pagination)
    runs = result.items
    total = result.total

    context = get_base_context(request, response, user, csrf_token)
    context["runs"] = runs
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/payroll/partials/runs_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Payroll Runs"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Payroll Runs"},
    ])

    template = templates.get_template("modules/hr/templates/payroll/pages/runs_list.html")
    return HTMLResponse(template.render(context))


@router.get("/{slip_id:int}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def salary_slip_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    slip_id: int,
):
    """Salary slip detail page."""
    service = PayrollService(db, user)

    try:
        slip = service.get_salary_slip(slip_id)
    except SalarySlipNotFoundError:
        raise HTTPException(status_code=404, detail="Salary slip not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Salary Slip - {slip.employee_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Payroll", "href": "/hr/payroll"},
        {"label": f"Slip #{slip.id}"},
    ])
    context["slip"] = slip

    template = templates.get_template("modules/hr/templates/payroll/pages/detail.html")
    return HTMLResponse(template.render(context))
