"""
Journal Entry routes for accounting module.
"""
from fastapi import APIRouter, Query

from ._deps import (
    Request, Response, HTMLResponse, RedirectResponse, Optional,
    SessionUser, CSRFToken, CSRFProtect, DB,
    RequireAccountingRead, RequireAccountingWrite,
    templates,
    get_base_context, get_navigation_context, build_breadcrumbs, build_pagination_context,
    is_htmx_request, HTTPException, set_flash, form_str,
    Account, GLEntry, JournalEntry, JournalEntryItem, JournalEntryType,
    func, or_, datetime, Decimal, selectinload,
)

router = APIRouter()


def get_voucher_type_options():
    """Get voucher type options for JE filter dropdown."""
    return [
        {"value": t.value, "label": t.value.replace("_", " ").title()}
        for t in JournalEntryType
    ]


def get_docstatus_options():
    """Get document status options."""
    return [
        {"value": "0", "label": "Draft"},
        {"value": "1", "label": "Posted"},
        {"value": "2", "label": "Cancelled"},
    ]


def get_je_stats(db) -> dict:
    """Calculate journal entry statistics."""
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_count = db.query(func.count(JournalEntry.id)).scalar() or 0

    draft_count = db.query(func.count(JournalEntry.id)).filter(
        JournalEntry.docstatus == 0
    ).scalar() or 0

    posted_count = db.query(func.count(JournalEntry.id)).filter(
        JournalEntry.docstatus == 1
    ).scalar() or 0

    this_month = db.query(func.count(JournalEntry.id)).filter(
        JournalEntry.posting_date >= month_start,
        JournalEntry.docstatus == 1,
    ).scalar() or 0

    return {
        "total_count": total_count,
        "draft_count": draft_count,
        "posted_count": posted_count,
        "this_month": this_month,
    }


@router.get("/journal-entries", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def journal_entries_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    voucher_type: Optional[str] = Query(None, description="Filter by voucher type"),
    docstatus: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("posting_date", description="Sort field"),
    dir: str = Query("desc", description="Sort direction"),
):
    """Journal Entries list page."""
    # Build query with eager loading
    query = db.query(JournalEntry).options(selectinload(JournalEntry.items))

    # Search
    if q:
        search_filter = or_(
            JournalEntry.erpnext_id.ilike(f"%{q}%"),
            JournalEntry.user_remark.ilike(f"%{q}%"),
            JournalEntry.cheque_no.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    # Filters
    if voucher_type:
        query = query.filter(JournalEntry.voucher_type == voucher_type)

    if docstatus:
        query = query.filter(JournalEntry.docstatus == int(docstatus))

    # Count total
    total = query.count()

    # Sort
    sort_column = getattr(JournalEntry, sort, JournalEntry.posting_date)
    if dir == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    # Paginate
    offset = (page - 1) * per_page
    entries = query.offset(offset).limit(per_page).all()

    # Get stats
    stats = get_je_stats(db)

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["entries"] = entries
    context["search_query"] = q or ""
    context["current_voucher_type"] = voucher_type
    context["current_docstatus"] = docstatus
    context["voucher_type_options"] = get_voucher_type_options()
    context["docstatus_options"] = get_docstatus_options()
    context["stats"] = stats
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, total)

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/accounting/templates/journal_entries/partials/journal_entries_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Journal Entries"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/accounts"},
        {"label": "Journal Entries"},
    ])

    template = templates.get_template("modules/accounting/templates/journal_entries/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/journal-entries/table", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def journal_entries_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    voucher_type: Optional[str] = Query(None),
    docstatus: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("posting_date"),
    dir: str = Query("desc"),
):
    """Journal entries table partial for HTMX updates."""
    return await journal_entries_list(
        request, response, user, csrf_token, db,
        q, voucher_type, docstatus, page, per_page, sort, dir
    )


@router.get("/journal-entries/new", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def journal_entry_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    account: Optional[str] = Query(None, description="Pre-fill account"),
):
    """New journal entry form page."""
    # Get accounts for dropdown
    accounts = db.query(Account).filter(
        Account.disabled == False,
        Account.is_group == False,
    ).order_by(Account.account_name).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Journal Entry"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/accounts"},
        {"label": "Journal Entries", "href": "/accounting/journal-entries"},
        {"label": "New Entry"},
    ])
    context["entry"] = None
    context["voucher_type_options"] = get_voucher_type_options()
    context["accounts"] = accounts
    context["prefill_account"] = account
    context["errors"] = {}

    template = templates.get_template("modules/accounting/templates/journal_entries/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/journal-entries", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def journal_entry_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new journal entry."""
    form = await request.form()

    # Get accounts for error re-render
    accounts = db.query(Account).filter(
        Account.disabled == False,
        Account.is_group == False,
    ).order_by(Account.account_name).all()

    # Validate
    errors = {}
    posting_date = form_str(form, "posting_date")
    voucher_type_value = form_str(form, "voucher_type")
    user_remark = form_str(form, "user_remark") or None
    cheque_no = form_str(form, "cheque_no") or None

    if not posting_date:
        errors["posting_date"] = "Posting date is required"

    if not voucher_type_value:
        errors["voucher_type"] = "Voucher type is required"

    # Parse line items
    line_items = []
    total_debit = Decimal("0")
    total_credit = Decimal("0")

    # Get all account/debit/credit fields
    i = 0
    while True:
        account_field = form.get(f"items[{i}][account]")
        if account_field is None:
            break

        if not isinstance(account_field, str):
            i += 1
            continue
        account_val = account_field.strip()
        debit_val = form_str(form, f"items[{i}][debit]", "0") or "0"
        credit_val = form_str(form, f"items[{i}][credit]", "0") or "0"
        description = form_str(form, f"items[{i}][description]") or None

        if account_val:
            try:
                debit = Decimal(debit_val)
                credit = Decimal(credit_val)
                line_items.append({
                    "account": account_val,
                    "debit": debit,
                    "credit": credit,
                    "description": description,
                    "idx": i,
                })
                total_debit += debit
                total_credit += credit
            except (ValueError, TypeError):
                errors[f"items[{i}]"] = "Invalid debit/credit amount"

        i += 1

    # Validate line items
    if len(line_items) < 2:
        errors["items"] = "At least two line items are required"

    # Check debit = credit
    if abs(total_debit - total_credit) > Decimal("0.01"):
        errors["balance"] = f"Debits ({total_debit}) must equal credits ({total_credit})"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Journal Entry"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Accounting", "href": "/accounting/accounts"},
            {"label": "Journal Entries", "href": "/accounting/journal-entries"},
            {"label": "New Entry"},
        ])
        context["entry"] = None
        context["voucher_type_options"] = get_voucher_type_options()
        context["accounts"] = accounts
        context["errors"] = errors
        context["form_data"] = dict(form)
        context["line_items"] = line_items

        template = templates.get_template("modules/accounting/templates/journal_entries/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Create journal entry
    entry = JournalEntry(
        voucher_type=JournalEntryType(voucher_type_value),
        posting_date=datetime.strptime(posting_date, "%Y-%m-%d"),
        user_remark=user_remark,
        cheque_no=cheque_no,
        total_debit=total_debit,
        total_credit=total_credit,
        docstatus=0,  # Draft
    )
    db.add(entry)
    db.flush()

    # Add line items
    for item_data in line_items:
        # Find account ID
        acct = db.query(Account).filter(Account.account_name == item_data["account"]).first()
        if acct:
            je_item = JournalEntryItem(
                journal_entry_id=entry.id,
                account=item_data["account"],
                account_id=acct.id,
                debit=item_data["debit"],
                credit=item_data["credit"],
                idx=item_data["idx"],
            )
            db.add(je_item)

    db.commit()
    db.refresh(entry)

    set_flash(response, "Journal entry created successfully.", "success")
    return RedirectResponse(url=f"/accounting/journal-entries/{entry.id}", status_code=303)


@router.get("/journal-entries/{entry_id}", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def journal_entry_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    entry_id: int,
):
    """Journal entry detail page."""
    entry = db.query(JournalEntry).options(
        selectinload(JournalEntry.items)
    ).filter(JournalEntry.id == entry_id).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"JE-{entry.id}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/accounts"},
        {"label": "Journal Entries", "href": "/accounting/journal-entries"},
        {"label": f"JE-{entry.id}"},
    ])
    context["entry"] = entry

    template = templates.get_template("modules/accounting/templates/journal_entries/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/journal-entries/{entry_id}/edit", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def journal_entry_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    entry_id: int,
):
    """Journal entry edit form page."""
    entry = db.query(JournalEntry).options(
        selectinload(JournalEntry.items)
    ).filter(JournalEntry.id == entry_id).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    if entry.docstatus != 0:
        set_flash(response, "Only draft entries can be edited.", "error")
        return RedirectResponse(url=f"/accounting/journal-entries/{entry.id}", status_code=303)

    # Get accounts for dropdown
    accounts = db.query(Account).filter(
        Account.disabled == False,
        Account.is_group == False,
    ).order_by(Account.account_name).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit JE-{entry.id}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/accounts"},
        {"label": "Journal Entries", "href": "/accounting/journal-entries"},
        {"label": f"JE-{entry.id}", "href": f"/accounting/journal-entries/{entry.id}"},
        {"label": "Edit"},
    ])
    context["entry"] = entry
    context["voucher_type_options"] = get_voucher_type_options()
    context["accounts"] = accounts
    context["errors"] = {}

    template = templates.get_template("modules/accounting/templates/journal_entries/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/journal-entries/{entry_id}", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def journal_entry_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    entry_id: int,
):
    """Update a journal entry."""
    entry = db.query(JournalEntry).options(
        selectinload(JournalEntry.items)
    ).filter(JournalEntry.id == entry_id).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    if entry.docstatus != 0:
        set_flash(response, "Only draft entries can be edited.", "error")
        return RedirectResponse(url=f"/accounting/journal-entries/{entry.id}", status_code=303)

    form = await request.form()

    # Get accounts for error re-render
    accounts = db.query(Account).filter(
        Account.disabled == False,
        Account.is_group == False,
    ).order_by(Account.account_name).all()

    # Validate (similar to create)
    errors = {}
    posting_date = form_str(form, "posting_date")
    voucher_type_value = form_str(form, "voucher_type")
    user_remark = form_str(form, "user_remark") or None
    cheque_no = form_str(form, "cheque_no") or None

    if not posting_date:
        errors["posting_date"] = "Posting date is required"

    if not voucher_type_value:
        errors["voucher_type"] = "Voucher type is required"

    # Parse line items
    line_items = []
    total_debit = Decimal("0")
    total_credit = Decimal("0")

    i = 0
    while True:
        account_field = form.get(f"items[{i}][account]")
        if account_field is None:
            break

        if not isinstance(account_field, str):
            i += 1
            continue
        account_val = account_field.strip()
        debit_val = form_str(form, f"items[{i}][debit]", "0") or "0"
        credit_val = form_str(form, f"items[{i}][credit]", "0") or "0"
        description = form_str(form, f"items[{i}][description]") or None

        if account_val:
            try:
                debit = Decimal(debit_val)
                credit = Decimal(credit_val)
                line_items.append({
                    "account": account_val,
                    "debit": debit,
                    "credit": credit,
                    "description": description,
                    "idx": i,
                })
                total_debit += debit
                total_credit += credit
            except (ValueError, TypeError):
                errors[f"items[{i}]"] = "Invalid debit/credit amount"

        i += 1

    if len(line_items) < 2:
        errors["items"] = "At least two line items are required"

    if abs(total_debit - total_credit) > Decimal("0.01"):
        errors["balance"] = f"Debits ({total_debit}) must equal credits ({total_credit})"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit JE-{entry.id}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Accounting", "href": "/accounting/accounts"},
            {"label": "Journal Entries", "href": "/accounting/journal-entries"},
            {"label": f"JE-{entry.id}", "href": f"/accounting/journal-entries/{entry.id}"},
            {"label": "Edit"},
        ])
        context["entry"] = entry
        context["voucher_type_options"] = get_voucher_type_options()
        context["accounts"] = accounts
        context["errors"] = errors
        context["form_data"] = dict(form)
        context["line_items"] = line_items

        template = templates.get_template("modules/accounting/templates/journal_entries/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Update entry
    entry.voucher_type = JournalEntryType(voucher_type_value)
    entry.posting_date = datetime.strptime(posting_date, "%Y-%m-%d")
    entry.user_remark = user_remark
    entry.cheque_no = cheque_no
    entry.total_debit = total_debit
    entry.total_credit = total_credit

    # Delete old items and add new ones
    for item in entry.items:
        db.delete(item)

    for item_data in line_items:
        acct = db.query(Account).filter(Account.account_name == item_data["account"]).first()
        if acct:
            je_item = JournalEntryItem(
                journal_entry_id=entry.id,
                account=item_data["account"],
                account_id=acct.id,
                debit=item_data["debit"],
                credit=item_data["credit"],
                idx=item_data["idx"],
            )
            db.add(je_item)

    db.commit()

    set_flash(response, "Journal entry updated successfully.", "success")
    return RedirectResponse(url=f"/accounting/journal-entries/{entry.id}", status_code=303)


@router.post("/journal-entries/{entry_id}/post", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def journal_entry_post(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    entry_id: int,
):
    """Post a journal entry to the general ledger."""
    entry = db.query(JournalEntry).options(
        selectinload(JournalEntry.items)
    ).filter(JournalEntry.id == entry_id).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    if entry.docstatus != 0:
        set_flash(response, "Only draft entries can be posted.", "error")
        return RedirectResponse(url=f"/accounting/journal-entries/{entry.id}", status_code=303)

    # Create GL entries
    for item in entry.items:
        gl_entry = GLEntry(
            posting_date=entry.posting_date,
            account=item.account,
            debit=item.debit,
            credit=item.credit,
            voucher_type="Journal Entry",
            voucher_no=f"JE-{entry.id}",
            is_cancelled=False,
        )
        db.add(gl_entry)

    # Update entry status
    entry.docstatus = 1
    db.commit()

    set_flash(response, "Journal entry posted to GL successfully.", "success")
    return RedirectResponse(url=f"/accounting/journal-entries/{entry.id}", status_code=303)
