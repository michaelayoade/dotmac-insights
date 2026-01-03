"""
Chart of Accounts routes for accounting module.
"""
from fastapi import APIRouter, Query

from ._deps import (
    Request, Response, HTMLResponse, RedirectResponse, Optional,
    SessionUser, CSRFToken, CSRFProtect, DB,
    RequireAccountingRead, RequireAccountingWrite,
    templates,
    get_base_context, get_navigation_context, build_breadcrumbs, build_pagination_context,
    is_htmx_request, HTTPException, set_flash, form_str,
    Account, AccountType,
)
from app.services.accounting import LedgerService
from app.services.accounting.ledger_types import AccountCreateData, AccountFilters, AccountUpdateData, GLEntryFilters
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginationParams

router = APIRouter()


def get_root_type_options():
    """Get root type options for account filter dropdown."""
    return [
        {"value": t.value, "label": t.value.title()}
        for t in AccountType
    ]


def get_account_type_options():
    """Get common account type options."""
    return [
        {"value": "Accumulated Depreciation", "label": "Accumulated Depreciation"},
        {"value": "Bank", "label": "Bank"},
        {"value": "Cash", "label": "Cash"},
        {"value": "Chargeable", "label": "Chargeable"},
        {"value": "Cost of Goods Sold", "label": "Cost of Goods Sold"},
        {"value": "Depreciation", "label": "Depreciation"},
        {"value": "Direct Expense", "label": "Direct Expense"},
        {"value": "Direct Income", "label": "Direct Income"},
        {"value": "Equity", "label": "Equity"},
        {"value": "Expense Account", "label": "Expense Account"},
        {"value": "Expenses Included In Asset Valuation", "label": "Expenses Included In Asset Valuation"},
        {"value": "Expenses Included In Valuation", "label": "Expenses Included In Valuation"},
        {"value": "Fixed Asset", "label": "Fixed Asset"},
        {"value": "Income Account", "label": "Income Account"},
        {"value": "Indirect Expense", "label": "Indirect Expense"},
        {"value": "Indirect Income", "label": "Indirect Income"},
        {"value": "Payable", "label": "Payable"},
        {"value": "Receivable", "label": "Receivable"},
        {"value": "Round Off", "label": "Round Off"},
        {"value": "Stock", "label": "Stock"},
        {"value": "Stock Adjustment", "label": "Stock Adjustment"},
        {"value": "Stock Received But Not Billed", "label": "Stock Received But Not Billed"},
        {"value": "Tax", "label": "Tax"},
        {"value": "Temporary", "label": "Temporary"},
    ]


def _get_ledger_service(db: DB, user: SessionUser) -> LedgerService:
    return LedgerService(db, user)


def get_parent_account_options(service: LedgerService, exclude_id: Optional[int] = None):
    """Get parent account options (groups only)."""
    filters = AccountFilters(
        is_group=True,
        include_disabled=False,
        sort_by="account_name",
        sort_dir="asc",
    )
    pagination = PaginationParams(limit=1000, offset=0)
    result = service.list_accounts(filters, pagination)
    accounts = result.items
    if exclude_id:
        accounts = [acc for acc in accounts if acc.id != exclude_id]
    return [
        {"value": str(a.id), "label": f"{a.account_name} ({a.root_type.value.title() if a.root_type else 'Unknown'})"}
        for a in accounts
    ]


def build_account_tree(accounts: list, parent: Optional[str] = None) -> list:
    """Build hierarchical account tree structure."""
    tree = []
    for account in accounts:
        if account.parent_account == parent:
            children = build_account_tree(accounts, account.account_name)
            node = {
                "account": account,
                "children": children,
                "has_children": len(children) > 0,
            }
            tree.append(node)
    return tree


def get_account_balance(service: LedgerService, account: Account):
    """Calculate account balance from GL entries."""
    info = service.get_account_balance(account)
    return info.balance


@router.get("/accounts", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def accounts_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    root_type: Optional[str] = Query(None, description="Filter by root type"),
    show_disabled: bool = Query(False, description="Show disabled accounts"),
    view: str = Query("tree", description="View mode: tree or flat"),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=10, le=500),
):
    """Chart of Accounts list page."""
    service = _get_ledger_service(db, user)
    root_type_enum = None
    if root_type:
        try:
            root_type_enum = AccountType(root_type)
        except ValueError:
            root_type_enum = None

    filters = AccountFilters(
        search=q,
        root_type=root_type_enum,
        include_disabled=show_disabled,
        sort_by="root_type",
        sort_dir="asc",
    )
    pagination = PaginationParams(
        limit=per_page,
        offset=(page - 1) * per_page,
    )
    if view == "tree" and not q:
        pagination = PaginationParams(limit=10000, offset=0)

    try:
        result = service.list_accounts(filters, pagination)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    accounts = result.items
    total = result.total
    account_tree = build_account_tree(accounts) if view == "tree" and not q else None

    stats = service.get_account_stats()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["accounts"] = accounts
    context["account_tree"] = account_tree
    context["search_query"] = q or ""
    context["current_root_type"] = root_type
    context["show_disabled"] = show_disabled
    context["view_mode"] = view
    context["root_type_options"] = get_root_type_options()
    context["stats"] = stats
    context["pagination"] = build_pagination_context(page, per_page, total)

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/accounting/templates/accounts/partials/accounts_tree.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Chart of Accounts"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/accounts"},
        {"label": "Chart of Accounts"},
    ])

    template = templates.get_template("modules/accounting/templates/accounts/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/accounts/table", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def accounts_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    root_type: Optional[str] = Query(None),
    show_disabled: bool = Query(False),
    view: str = Query("tree"),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=10, le=500),
):
    """Accounts table partial for HTMX updates."""
    return await accounts_list(
        request, response, user, csrf_token, db,
        q, root_type, show_disabled, view, page, per_page
    )


@router.get("/accounts/new", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def account_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New account form page."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Account"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/accounts"},
        {"label": "Chart of Accounts", "href": "/accounting/accounts"},
        {"label": "New Account"},
    ])
    context["account"] = None
    context["root_type_options"] = get_root_type_options()
    context["account_type_options"] = get_account_type_options()
    service = _get_ledger_service(db, user)
    context["parent_options"] = get_parent_account_options(service)
    context["errors"] = {}

    template = templates.get_template("modules/accounting/templates/accounts/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/accounts", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def account_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new account."""
    form = await request.form()

    # Validate
    errors = {}
    account_name = form_str(form, "account_name")
    account_number = form_str(form, "account_number") or None
    root_type_value = form_str(form, "root_type")
    account_type = form_str(form, "account_type") or None
    parent_id = form_str(form, "parent_account") or None
    is_group = form.get("is_group") == "on"

    if not account_name:
        errors["account_name"] = "Account name is required"

    if not root_type_value:
        errors["root_type"] = "Root type is required"

    # Check for duplicate name
    service = _get_ledger_service(db, user)
    existing = service.get_account_by_name(account_name)
    if existing:
        errors["account_name"] = "An account with this name already exists"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Account"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Accounting", "href": "/accounting/accounts"},
            {"label": "Chart of Accounts", "href": "/accounting/accounts"},
            {"label": "New Account"},
        ])
        context["account"] = None
        context["root_type_options"] = get_root_type_options()
        context["account_type_options"] = get_account_type_options()
        context["parent_options"] = get_parent_account_options(service)
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/accounting/templates/accounts/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Get parent account name if parent_id provided
    parent_account_name = None
    if parent_id:
        try:
            parent = service.get_account(int(parent_id))
            parent_account_name = parent.account_name
        except NotFoundError:
            parent_account_name = None

    # Create account
    account = service.create_account(
        AccountCreateData(
            account_name=account_name,
            account_number=account_number,
            root_type=AccountType(root_type_value),
            account_type=account_type,
            parent_account=parent_account_name,
            is_group=is_group,
            disabled=False,
        )
    )
    db.commit()

    set_flash(response, f"Account '{account_name}' created successfully.", "success")
    return RedirectResponse(url=f"/accounting/accounts/{account.id}", status_code=303)


@router.get("/accounts/{account_id}", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def account_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    account_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Account detail page with ledger entries."""
    service = _get_ledger_service(db, user)
    try:
        account = service.get_account(account_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Account not found") from exc

    pagination = PaginationParams(limit=per_page, offset=(page - 1) * per_page)
    gl_filters = GLEntryFilters(
        account=account.account_name,
        is_cancelled=False,
        sort_by="posting_date",
        sort_dir="desc",
    )
    gl_entries_result = service.list_gl_entries(gl_filters, pagination)
    gl_entries = gl_entries_result.items
    total_entries = gl_entries_result.total

    balance = get_account_balance(service, account)

    children = service.list_child_accounts(account.account_name) if account.is_group else []

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = account.account_name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/accounts"},
        {"label": "Chart of Accounts", "href": "/accounting/accounts"},
        {"label": account.account_name},
    ])
    context["account"] = account
    context["gl_entries"] = gl_entries
    context["balance"] = balance
    context["children"] = children
    context["pagination"] = build_pagination_context(page, per_page, total_entries)

    template = templates.get_template("modules/accounting/templates/accounts/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/accounts/{account_id}/edit", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def account_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    account_id: int,
):
    """Account edit form page."""
    service = _get_ledger_service(db, user)
    try:
        account = service.get_account(account_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Account not found") from exc

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit {account.account_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/accounts"},
        {"label": "Chart of Accounts", "href": "/accounting/accounts"},
        {"label": account.account_name, "href": f"/accounting/accounts/{account.id}"},
        {"label": "Edit"},
    ])
    context["account"] = account
    context["root_type_options"] = get_root_type_options()
    context["account_type_options"] = get_account_type_options()
    context["parent_options"] = get_parent_account_options(service, exclude_id=account.id)
    context["errors"] = {}

    template = templates.get_template("modules/accounting/templates/accounts/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/accounts/{account_id}", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def account_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    account_id: int,
):
    """Update an existing account."""
    service = _get_ledger_service(db, user)
    try:
        account = service.get_account(account_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Account not found") from exc

    form = await request.form()

    # Validate
    errors = {}
    account_name = form_str(form, "account_name")
    account_number = form_str(form, "account_number") or None
    root_type_value = form_str(form, "root_type")
    account_type = form_str(form, "account_type") or None
    parent_id = form_str(form, "parent_account") or None
    is_group = form.get("is_group") == "on"
    disabled = form.get("disabled") == "on"

    if not account_name:
        errors["account_name"] = "Account name is required"

    if not root_type_value:
        errors["root_type"] = "Root type is required"

    # Check for duplicate name (excluding this account)
    existing = service.get_account_by_name(account_name)
    if existing and existing.id != account_id:
        errors["account_name"] = "An account with this name already exists"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit {account.account_name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Accounting", "href": "/accounting/accounts"},
            {"label": "Chart of Accounts", "href": "/accounting/accounts"},
            {"label": account.account_name, "href": f"/accounting/accounts/{account.id}"},
            {"label": "Edit"},
        ])
        context["account"] = account
        context["root_type_options"] = get_root_type_options()
        context["account_type_options"] = get_account_type_options()
        context["parent_options"] = get_parent_account_options(service, exclude_id=account.id)
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/accounting/templates/accounts/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Get parent account name if parent_id provided
    parent_account_name = None
    if parent_id:
        try:
            parent = service.get_account(int(parent_id))
            parent_account_name = parent.account_name
        except NotFoundError:
            parent_account_name = None

    # Update account
    service.update_account(
        account_id,
        AccountUpdateData(
            account_name=account_name,
            account_number=account_number,
            root_type=AccountType(root_type_value),
            account_type=account_type,
            parent_account=parent_account_name,
            is_group=is_group,
            disabled=disabled,
        ),
    )
    db.commit()

    set_flash(response, f"Account '{account_name}' updated successfully.", "success")
    return RedirectResponse(url=f"/accounting/accounts/{account.id}", status_code=303)
