"""
Expense Claims Routes.

Handles SSR pages for expense claims, cash advances, and categories.
Business logic is delegated to services in app/services/expenses/.
"""
from __future__ import annotations

from typing import Optional, Any
from datetime import date
from fastapi import APIRouter, Request, Response, Depends, Query, Form, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.web.dependencies import SessionUser, CSRFToken, require_scope
from app.web.context import get_base_context, get_navigation_context
from app.templates.environment import get_template_env
from app.auth import Principal
from app.models.expense_management import (
    ExpenseClaimStatus,
    CashAdvanceStatus,
)
from app.models.employee import Employee
from app.core.security import set_flash
from app.services.expenses import (
    ExpenseService,
    CashAdvanceService,
    ExpenseCategoryService,
    ExpenseClaimFilters,
    CashAdvanceFilters,
)
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError, ConflictError

router = APIRouter(prefix="/expenses", tags=["expenses"])
templates = get_template_env()

RequireExpensesRead = Depends(require_scope("expenses:read"))
RequireExpensesWrite = Depends(require_scope("expenses:write"))

TEMPLATE_PATH = "modules/expenses/templates"


# ============= SERVICE DEPENDENCY PROVIDERS =============

def get_expense_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_scope("expenses:read")),
) -> ExpenseService:
    return ExpenseService(db)


def get_cash_advance_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_scope("expenses:read")),
) -> CashAdvanceService:
    return CashAdvanceService(db)


def get_category_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_scope("expenses:read")),
) -> ExpenseCategoryService:
    return ExpenseCategoryService(db, principal)


def _form_str(form: Any, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile) or value is None:
        return default
    return str(value).strip()


# ============= EXPENSE CLAIMS LIST =============

@router.get("", response_class=HTMLResponse, dependencies=[RequireExpensesRead])
async def claims_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    service: ExpenseService = Depends(get_expense_service),
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("claim_date"),
    dir: str = Query("desc"),
):
    """Expense claims list page."""
    # Parse status if provided
    status_enum = None
    if status:
        try:
            status_enum = ExpenseClaimStatus(status)
        except ValueError:
            pass

    # Build filters
    filters = ExpenseClaimFilters(
        search=q,
        status=status_enum,
        sort_by=sort,
        sort_dir=dir,
    )
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    # Get claims via service
    result = service.list_claims(filters, pagination)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Expense Claims"
    context["claims"] = result.items
    context["q"] = q
    context["status"] = status
    context["sort"] = sort
    context["dir"] = dir
    context["pagination"] = {
        "page": page,
        "per_page": per_page,
        "total": result.total,
        "total_pages": (result.total + per_page - 1) // per_page,
    }

    # HTMX partial response
    if request.headers.get("HX-Request"):
        template = templates.get_template(f"{TEMPLATE_PATH}/partials/claims_table.html")
        return HTMLResponse(template.render(context))

    template = templates.get_template(f"{TEMPLATE_PATH}/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireExpensesRead])
async def claims_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    service: ExpenseService = Depends(get_expense_service),
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("claim_date"),
    dir: str = Query("desc"),
):
    """Claims table partial for HTMX."""
    return await claims_list(
        request, response, user, csrf_token, service,
        q, status, page, per_page, sort, dir
    )


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireExpensesWrite])
async def new_claim(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: Session = Depends(get_db),
):
    """New expense claim form."""
    employees = db.query(Employee).filter(Employee.status == "Active").order_by(Employee.name).all()
    categories = db.query(ExpenseCategory).filter(ExpenseCategory.is_active == True).order_by(ExpenseCategory.name).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Expense Claim"
    context["claim"] = None
    context["employee_options"] = [{"value": e.id, "label": e.name} for e in employees]
    context["category_options"] = [{"value": c.id, "label": c.name} for c in categories]
    context["errors"] = {}
    context["form_data"] = {}

    template = templates.get_template(f"{TEMPLATE_PATH}/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireExpensesWrite])
async def create_claim(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: Session = Depends(get_db),
    employee_id: int = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    claim_date: date = Form(...),
):
    """Create new expense claim."""
    from app.core.security import validate_csrf
    await validate_csrf(request)

    errors = {}
    if not employee_id:
        errors["employee_id"] = "Employee is required"
    if not title:
        errors["title"] = "Title is required"

    if errors:
        employees = db.query(Employee).filter(Employee.status == "Active").order_by(Employee.name).all()
        categories = db.query(ExpenseCategory).filter(ExpenseCategory.is_active == True).order_by(ExpenseCategory.name).all()

        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Expense Claim"
        context["claim"] = None
        context["employee_options"] = [{"value": e.id, "label": e.name} for e in employees]
        context["category_options"] = [{"value": c.id, "label": c.name} for c in categories]
        context["errors"] = errors
        context["form_data"] = {"employee_id": employee_id, "title": title, "description": description, "claim_date": claim_date}

        template = templates.get_template(f"{TEMPLATE_PATH}/pages/form.html")
        return HTMLResponse(template.render(context))

    # Get employee department
    employee = db.query(Employee).filter(Employee.id == employee_id).first()

    claim = ExpenseClaim(
        employee_id=employee_id,
        department_id=employee.department_id if employee else None,
        title=title,
        description=description,
        claim_date=claim_date,
        status=ExpenseClaimStatus.DRAFT,
        created_by_id=user.id,
    )
    db.add(claim)
    db.commit()

    set_flash(response, "Expense claim created successfully.", "success")
    return RedirectResponse(url=f"/expenses/{claim.id}", status_code=303)


@router.get("/advances", response_class=HTMLResponse, dependencies=[RequireExpensesRead])
async def advances_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    service: CashAdvanceService = Depends(get_cash_advance_service),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=100),
):
    """Cash advances list page."""
    # Parse status if provided
    status_enum = None
    if status:
        try:
            status_enum = CashAdvanceStatus(status)
        except ValueError:
            pass

    # Build filters
    filters = CashAdvanceFilters(
        status=status_enum,
        sort_by="request_date",
        sort_dir="desc",
    )
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    # Get advances via service
    result = service.list_advances(filters, pagination)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Cash Advances"
    context["advances"] = result.items
    context["status"] = status

    template = templates.get_template(f"{TEMPLATE_PATH}/pages/advances_list.html")
    return HTMLResponse(template.render(context))


@router.get("/categories", response_class=HTMLResponse, dependencies=[RequireExpensesRead])
async def categories_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    service: ExpenseCategoryService = Depends(get_category_service),
):
    """Expense categories list page."""
    result = service.list_categories(pagination=PaginationParams(offset=0, limit=1000))

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Expense Categories"
    context["categories"] = result.items

    template = templates.get_template(f"{TEMPLATE_PATH}/pages/categories_list.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# CASH ADVANCES CRUD
# =============================================================================

def get_advance_status_options():
    """Get advance status options for select dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in CashAdvanceStatus
    ]


@router.get("/advances/new", response_class=HTMLResponse, dependencies=[RequireExpensesWrite])
async def advance_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: Session = Depends(get_db),
):
    """New cash advance form."""
    employees = db.query(Employee).filter(Employee.status == "Active").order_by(Employee.name).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Cash Advance"
    context["advance"] = None
    context["employee_options"] = [{"value": e.id, "label": e.name} for e in employees]
    context["status_options"] = get_advance_status_options()
    context["errors"] = {}

    template = templates.get_template(f"{TEMPLATE_PATH}/pages/advance_form.html")
    return HTMLResponse(template.render(context))


@router.post("/advances", response_class=HTMLResponse, dependencies=[RequireExpensesWrite])
async def advance_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: Session = Depends(get_db),
):
    """Create new cash advance."""
    from app.core.security import validate_csrf
    from datetime import date as date_type
    from decimal import Decimal
    await validate_csrf(request)

    form = await request.form()

    errors = {}
    employee_id = _form_str(form, "employee_id")
    purpose = _form_str(form, "purpose")
    requested_amount = _form_str(form, "requested_amount")

    if not employee_id:
        errors["employee_id"] = "Employee is required"
    if not purpose:
        errors["purpose"] = "Purpose is required"
    if not requested_amount:
        errors["requested_amount"] = "Amount is required"

    if errors:
        employees = db.query(Employee).filter(Employee.status == "Active").order_by(Employee.name).all()

        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Cash Advance"
        context["advance"] = None
        context["employee_options"] = [{"value": e.id, "label": e.name} for e in employees]
        context["status_options"] = get_advance_status_options()
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template(f"{TEMPLATE_PATH}/pages/advance_form.html")
        return HTMLResponse(template.render(context), status_code=422)

    advance = CashAdvance(
        employee_id=int(employee_id),
        purpose=purpose,
        description=_form_str(form, "description") or None,
        requested_amount=Decimal(requested_amount),
        currency=_form_str(form, "currency", "USD"),
        status=CashAdvanceStatus.DRAFT,
    )
    db.add(advance)
    db.commit()
    db.refresh(advance)

    set_flash(response, "Cash advance request created successfully.", "success")
    return RedirectResponse(url=f"/expenses/advances/{advance.id}", status_code=303)


@router.get("/advances/{advance_id:int}", response_class=HTMLResponse, dependencies=[RequireExpensesRead])
async def advance_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    advance_id: int,
    service: CashAdvanceService = Depends(get_cash_advance_service),
):
    """Cash advance detail page."""
    try:
        advance = service.get_advance(advance_id)
    except NotFoundError:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Cash advance not found"
        return HTMLResponse(template.render(context), status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Cash Advance - {advance.purpose[:50]}"
    context["advance"] = advance

    template = templates.get_template(f"{TEMPLATE_PATH}/pages/advance_detail.html")
    return HTMLResponse(template.render(context))


@router.get("/advances/{advance_id:int}/edit", response_class=HTMLResponse, dependencies=[RequireExpensesWrite])
async def advance_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    advance_id: int,
    service: CashAdvanceService = Depends(get_cash_advance_service),
    db: Session = Depends(get_db),
):
    """Edit cash advance form."""
    try:
        advance = service.get_advance(advance_id)
    except NotFoundError:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Cash advance not found"
        return HTMLResponse(template.render(context), status_code=404)

    employees = db.query(Employee).filter(Employee.status == "Active").order_by(Employee.name).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Edit Cash Advance"
    context["advance"] = advance
    context["employee_options"] = [{"value": e.id, "label": e.name} for e in employees]
    context["status_options"] = get_advance_status_options()
    context["errors"] = {}

    template = templates.get_template(f"{TEMPLATE_PATH}/pages/advance_form.html")
    return HTMLResponse(template.render(context))


@router.post("/advances/{advance_id:int}", response_class=HTMLResponse, dependencies=[RequireExpensesWrite])
async def advance_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    advance_id: int,
    db: Session = Depends(get_db),
):
    """Update cash advance."""
    from app.core.security import validate_csrf
    from decimal import Decimal
    await validate_csrf(request)

    advance = db.query(CashAdvance).filter(CashAdvance.id == advance_id).first()
    if not advance:
        set_flash(response, "Cash advance not found.", "error")
        return RedirectResponse(url="/expenses/advances", status_code=303)

    form = await request.form()

    errors = {}
    purpose = _form_str(form, "purpose")
    requested_amount = _form_str(form, "requested_amount")

    if not purpose:
        errors["purpose"] = "Purpose is required"
    if not requested_amount:
        errors["requested_amount"] = "Amount is required"

    if errors:
        employees = db.query(Employee).filter(Employee.status == "Active").order_by(Employee.name).all()

        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit Cash Advance"
        context["advance"] = advance
        context["employee_options"] = [{"value": e.id, "label": e.name} for e in employees]
        context["status_options"] = get_advance_status_options()
        context["errors"] = errors

        template = templates.get_template(f"{TEMPLATE_PATH}/pages/advance_form.html")
        return HTMLResponse(template.render(context), status_code=422)

    advance.purpose = purpose
    advance.description = _form_str(form, "description") or None
    advance.requested_amount = Decimal(requested_amount)
    advance.currency = _form_str(form, "currency", advance.currency)
    db.commit()

    set_flash(response, "Cash advance updated successfully.", "success")
    return RedirectResponse(url=f"/expenses/advances/{advance.id}", status_code=303)


@router.post("/advances/{advance_id:int}/submit", dependencies=[RequireExpensesWrite])
async def advance_submit(
    request: Request,
    response: Response,
    user: SessionUser,
    advance_id: int,
    service: CashAdvanceService = Depends(get_cash_advance_service),
    db: Session = Depends(get_db),
):
    """Submit cash advance for approval."""
    from app.core.security import validate_csrf
    await validate_csrf(request)

    try:
        advance = service.get_advance(advance_id)
        service.submit(advance, user_id=user.id, company_code=None)
        db.commit()
        set_flash(response, "Cash advance submitted for approval.", "success")
    except NotFoundError:
        set_flash(response, "Cash advance not found.", "error")
        return RedirectResponse(url="/expenses/advances", status_code=303)
    except ValidationError as e:
        set_flash(response, str(e), "error")

    return RedirectResponse(url=f"/expenses/advances/{advance_id}", status_code=303)


# =============================================================================
# EXPENSE CATEGORIES CRUD
# =============================================================================

@router.get("/categories/new", response_class=HTMLResponse, dependencies=[RequireExpensesWrite])
async def category_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
):
    """New expense category form."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Expense Category"
    context["category"] = None
    context["errors"] = {}

    template = templates.get_template(f"{TEMPLATE_PATH}/pages/category_form.html")
    return HTMLResponse(template.render(context))


@router.post("/categories", response_class=HTMLResponse, dependencies=[RequireExpensesWrite])
async def category_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: Session = Depends(get_db),
):
    """Create new expense category."""
    from app.core.security import validate_csrf
    await validate_csrf(request)

    form = await request.form()

    errors = {}
    name = _form_str(form, "name")

    if not name:
        errors["name"] = "Category name is required"

    # Check for duplicate
    existing = db.query(ExpenseCategory).filter(ExpenseCategory.name == name).first()
    if existing:
        errors["name"] = "A category with this name already exists"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Expense Category"
        context["category"] = None
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template(f"{TEMPLATE_PATH}/pages/category_form.html")
        return HTMLResponse(template.render(context), status_code=422)

    category = ExpenseCategory(
        name=name,
        description=_form_str(form, "description") or None,
        is_active=form.get("is_active") == "on",
    )
    db.add(category)
    db.commit()

    set_flash(response, f"Category '{name}' created successfully.", "success")
    return RedirectResponse(url="/expenses/categories", status_code=303)


@router.get("/categories/{category_id:int}/edit", response_class=HTMLResponse, dependencies=[RequireExpensesWrite])
async def category_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    category_id: int,
    service: ExpenseCategoryService = Depends(get_category_service),
):
    """Edit expense category form."""
    try:
        category = service.get_category(category_id)
    except NotFoundError:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Category not found"
        return HTMLResponse(template.render(context), status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit Category: {category.name}"
    context["category"] = category
    context["errors"] = {}

    template = templates.get_template(f"{TEMPLATE_PATH}/pages/category_form.html")
    return HTMLResponse(template.render(context))


@router.post("/categories/{category_id:int}", response_class=HTMLResponse, dependencies=[RequireExpensesWrite])
async def category_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    category_id: int,
    db: Session = Depends(get_db),
):
    """Update expense category."""
    from app.core.security import validate_csrf
    await validate_csrf(request)

    category = db.query(ExpenseCategory).filter(ExpenseCategory.id == category_id).first()
    if not category:
        set_flash(response, "Category not found.", "error")
        return RedirectResponse(url="/expenses/categories", status_code=303)

    form = await request.form()

    errors = {}
    name = _form_str(form, "name")

    if not name:
        errors["name"] = "Category name is required"

    # Check for duplicate (excluding current)
    existing = db.query(ExpenseCategory).filter(
        ExpenseCategory.name == name,
        ExpenseCategory.id != category_id
    ).first()
    if existing:
        errors["name"] = "A category with this name already exists"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit Category: {category.name}"
        context["category"] = category
        context["errors"] = errors

        template = templates.get_template(f"{TEMPLATE_PATH}/pages/category_form.html")
        return HTMLResponse(template.render(context), status_code=422)

    category.name = name
    category.description = _form_str(form, "description") or None
    category.is_active = form.get("is_active") == "on"
    db.commit()

    set_flash(response, f"Category '{name}' updated successfully.", "success")
    return RedirectResponse(url="/expenses/categories", status_code=303)


@router.get("/{claim_id:int}", response_class=HTMLResponse, dependencies=[RequireExpensesRead])
async def claim_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    claim_id: int,
    service: ExpenseService = Depends(get_expense_service),
):
    """Expense claim detail page."""
    try:
        claim = service.get_claim(claim_id, include_lines=True)
    except NotFoundError:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Expense claim not found"
        return HTMLResponse(template.render(context), status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = claim.title
    context["claim"] = claim

    template = templates.get_template(f"{TEMPLATE_PATH}/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.post("/{claim_id:int}/submit", dependencies=[RequireExpensesWrite])
async def submit_claim(
    request: Request,
    response: Response,
    user: SessionUser,
    claim_id: int,
    service: ExpenseService = Depends(get_expense_service),
    db: Session = Depends(get_db),
):
    """Submit expense claim for approval."""
    from app.core.security import validate_csrf
    await validate_csrf(request)

    try:
        claim = service.get_claim(claim_id)
        service.submit_claim(claim, user_id=user.id, company_code=None)
        db.commit()
        set_flash(response, "Claim submitted for approval.", "success")
    except NotFoundError:
        set_flash(response, "Claim not found.", "error")
        return RedirectResponse(url="/expenses", status_code=303)
    except ValidationError as e:
        set_flash(response, str(e), "error")

    return RedirectResponse(url=f"/expenses/{claim_id}", status_code=303)


@router.post("/{claim_id:int}/approve", dependencies=[RequireExpensesWrite])
async def approve_claim(
    request: Request,
    response: Response,
    user: SessionUser,
    claim_id: int,
    service: ExpenseService = Depends(get_expense_service),
    db: Session = Depends(get_db),
):
    """Approve expense claim."""
    from app.core.security import validate_csrf
    await validate_csrf(request)

    try:
        claim = service.get_claim(claim_id)
        service.approve_claim(claim, user_id=user.id)
        db.commit()
        set_flash(response, "Claim approved.", "success")
    except NotFoundError:
        set_flash(response, "Claim not found.", "error")
        return RedirectResponse(url="/expenses", status_code=303)
    except ValidationError as e:
        set_flash(response, str(e), "error")

    return RedirectResponse(url=f"/expenses/{claim_id}", status_code=303)


@router.post("/{claim_id:int}/reject", dependencies=[RequireExpensesWrite])
async def reject_claim(
    request: Request,
    response: Response,
    user: SessionUser,
    claim_id: int,
    service: ExpenseService = Depends(get_expense_service),
    db: Session = Depends(get_db),
    reason: str = Form(...),
):
    """Reject expense claim."""
    from app.core.security import validate_csrf
    await validate_csrf(request)

    try:
        claim = service.get_claim(claim_id)
        service.reject_claim(claim, user_id=user.id, reason=reason)
        db.commit()
        set_flash(response, "Claim rejected.", "info")
    except NotFoundError:
        set_flash(response, "Claim not found.", "error")
        return RedirectResponse(url="/expenses", status_code=303)
    except ValidationError as e:
        set_flash(response, str(e), "error")

    return RedirectResponse(url=f"/expenses/{claim_id}", status_code=303)
