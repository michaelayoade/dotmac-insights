"""
Admin Settings Routes - User, Role, Token, and Audit management.

Provides web UI for admin operations.
"""
from __future__ import annotations

from typing import Optional, Any

from fastapi import APIRouter, Request, Response, Query, Depends, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.core.security import is_htmx_request, set_flash
from app.services.admin_settings_service import AdminSettingsService
from app.services.activity_logger import ActivityLogger

# Permission dependencies
RequireAdminRead = Depends(require_scope("admin:read"))
RequireAdminWrite = Depends(require_scope("admin:write"))

router = APIRouter(prefix="/admin", tags=["settings-admin"])
templates = get_template_env()


def _form_str(form: Any, key: str, default: Optional[str] = "") -> Optional[str]:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


def _form_int(form: Any, key: str, default: int) -> int:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    try:
        return int(value) if value not in ("", None) else default
    except (TypeError, ValueError):
        return default


def _form_list(form: Any, key: str) -> list[str]:
    values = form.getlist(key)
    result: list[str] = []
    for value in values:
        if isinstance(value, UploadFile):
            continue
        if value is None:
            continue
        text = str(value).strip()
        if text:
            result.append(text)
    return result


def get_settings_nav(user, current_section: str = "admin") -> list[dict]:
    """Get settings navigation."""
    from app.modules.settings.routes import SETTINGS_CATEGORIES
    nav_items = []
    for cat in SETTINGS_CATEGORIES:
        if cat["scope"] is None or user.has_scope(cat["scope"]):
            nav_items.append({
                **cat,
                "is_current": current_section == cat["id"],
            })
    return nav_items


# Admin sub-navigation
ADMIN_TABS = [
    {"id": "users", "label": "Users", "href": "/settings/admin/users"},
    {"id": "roles", "label": "Roles", "href": "/settings/admin/roles"},
    {"id": "groups", "label": "Groups", "href": "/settings/admin/groups"},
    {"id": "permissions", "label": "Permissions", "href": "/settings/admin/permissions"},
    {"id": "sessions", "label": "Sessions", "href": "/settings/admin/sessions"},
    {"id": "tokens", "label": "Service Tokens", "href": "/settings/admin/tokens"},
    {"id": "webhooks", "label": "Webhooks", "href": "/settings/admin/webhooks"},
    {"id": "audit", "label": "Audit Log", "href": "/settings/admin/audit"},
    {"id": "activity", "label": "Activity Log", "href": "/settings/admin/activity"},
]


@router.get("", response_class=HTMLResponse, dependencies=[RequireAdminRead])
async def admin_index(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
):
    """Admin settings landing - redirects to users."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/settings/admin/users", status_code=303)


# ============================================================================
# USER MANAGEMENT
# ============================================================================

@router.get("/users", response_class=HTMLResponse, dependencies=[RequireAdminRead])
async def users_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """User management list."""
    service = AdminSettingsService(db)
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "users"

    users, total = service.list_users(q=q, status=status, page=page, per_page=per_page)

    context["page_title"] = "Users"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Admin", "href": "/settings/admin"},
        {"label": "Users"},
    ])
    context["users"] = users
    context["search_query"] = q or ""
    context["current_status"] = status
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/settings/templates/partials/users_table.html")
    else:
        template = templates.get_template("modules/settings/templates/pages/admin/users_list.html")

    return HTMLResponse(template.render(context))


@router.get("/users/{user_id}", response_class=HTMLResponse, dependencies=[RequireAdminRead])
async def user_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    user_id: str,
):
    """User detail/edit page."""
    service = AdminSettingsService(db)
    target_user = service.get_user(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "users"

    context["page_title"] = f"User: {target_user.name or target_user.email}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Admin", "href": "/settings/admin"},
        {"label": "Users", "href": "/settings/admin/users"},
        {"label": target_user.name or target_user.email},
    ])

    # Get all roles for assignment
    roles = service.list_roles()

    context["target_user"] = target_user
    context["all_roles"] = roles
    context["can_edit"] = user.has_scope("admin:write")

    template = templates.get_template("modules/settings/templates/pages/admin/user_detail.html")
    return HTMLResponse(template.render(context))


@router.post("/users/{user_id}", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def update_user(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    user_id: str,
    _csrf: CSRFProtect,
):
    """Update user (activate/deactivate, assign roles)."""
    service = AdminSettingsService(db)
    target_user = service.get_user(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    form = await request.form()
    change_meta = {}
    did_update = False

    # Update status
    if "is_active" in form:
        target_user = service.update_user(
            target_user,
            is_active=_form_str(form, "is_active") in ("true", "on", "1"),
        )
        change_meta["is_active"] = target_user.is_active
        did_update = True

    # Update roles
    role_ids = _form_list(form, "roles")
    if role_ids:
        target_user = service.update_user(
            target_user,
            role_ids=role_ids,
            update_roles=True,
        )
        change_meta["role_ids"] = role_ids
        did_update = True

    if did_update:
        activity_logger = ActivityLogger(db)
        activity_logger.log(
            action="rbac.user.update",
            user_id=user.id,
            entity_type="user",
            entity_id=str(target_user.id),
            summary=f"Updated user {target_user.email}",
            metadata=change_meta,
            request=request,
        )
        db.commit()

    set_flash(response, f"User {target_user.email} updated successfully.", "success")

    if is_htmx_request(request):
        response.headers["HX-Redirect"] = f"/settings/admin/users/{user_id}"
        return HTMLResponse("")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/settings/admin/users/{user_id}", status_code=303)


@router.post("/users/{user_id}/toggle-status", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def toggle_user_status(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    user_id: str,
):
    """Toggle user active status via HTMX."""
    service = AdminSettingsService(db)
    target_user = service.get_user(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    target_user = service.toggle_user_status(target_user)

    activity_logger = ActivityLogger(db)
    activity_logger.log(
        action="rbac.user.update",
        user_id=user.id,
        entity_type="user",
        entity_id=str(target_user.id),
        summary=f"Toggled user status for {target_user.email}",
        metadata={"is_active": target_user.is_active, "toggle": True},
        request=request,
    )
    db.commit()

    # Return updated row
    context = {"user": target_user, "can_edit": True}
    template = templates.get_template("modules/settings/templates/partials/user_row.html")
    return HTMLResponse(template.render(context))


# ============================================================================
# ROLE MANAGEMENT
# ============================================================================

@router.get("/roles", response_class=HTMLResponse, dependencies=[RequireAdminRead])
async def roles_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Role management list."""
    service = AdminSettingsService(db)
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "roles"

    roles = service.list_roles(system_first=True)

    context["page_title"] = "Roles"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Admin", "href": "/settings/admin"},
        {"label": "Roles"},
    ])
    context["roles"] = roles
    context["can_create"] = user.has_scope("admin:write")

    template = templates.get_template("modules/settings/templates/pages/admin/roles_list.html")
    return HTMLResponse(template.render(context))


@router.get("/roles/new", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def new_role_form(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New role creation form."""
    service = AdminSettingsService(db)
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "roles"

    permissions = service.list_permissions()

    # Group permissions by category
    permission_groups: dict[str, list[Permission]] = {}
    for perm in permissions:
        cat = perm.category or "Other"
        if cat not in permission_groups:
            permission_groups[cat] = []
        permission_groups[cat].append(perm)

    context["page_title"] = "New Role"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Admin", "href": "/settings/admin"},
        {"label": "Roles", "href": "/settings/admin/roles"},
        {"label": "New Role"},
    ])
    context["role"] = None
    context["permission_groups"] = permission_groups
    context["is_new"] = True

    template = templates.get_template("modules/settings/templates/pages/admin/role_form.html")
    return HTMLResponse(template.render(context))


@router.post("/roles", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def create_role(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _csrf: CSRFProtect,
):
    """Create new role."""
    form = await request.form()
    name = _form_str(form, "name")
    description = _form_str(form, "description")
    permission_ids = _form_list(form, "permissions")

    if not name:
        set_flash(response, "Role name is required.", "error")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/settings/admin/roles/new", status_code=303)

    service = AdminSettingsService(db)
    role = service.create_role(
        name=name,
        description=description,
        permission_ids=permission_ids,
    )
    if not role:
        set_flash(response, f"Role '{name}' already exists.", "error")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/settings/admin/roles/new", status_code=303)

    set_flash(response, f"Role '{name}' created successfully.", "success")

    activity_logger = ActivityLogger(db)
    activity_logger.log(
        action="rbac.role.create",
        user_id=user.id,
        entity_type="role",
        entity_id=str(role.id),
        summary=f"Created role '{role.name}'",
        metadata={"permission_ids": permission_ids},
        request=request,
    )
    db.commit()

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/settings/admin/roles", status_code=303)


@router.get("/roles/{role_id}", response_class=HTMLResponse, dependencies=[RequireAdminRead])
async def role_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    role_id: str,
):
    """Role detail/edit form."""
    service = AdminSettingsService(db)
    role = service.get_role(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "roles"

    permissions = service.list_permissions()

    # Group permissions by category
    permission_groups: dict[str, list[Permission]] = {}
    for perm in permissions:
        cat = perm.category or "Other"
        if cat not in permission_groups:
            permission_groups[cat] = []
        permission_groups[cat].append(perm)

    # Get role's current permission IDs
    role_permission_ids = {str(p.id) for p in role.permissions}

    context["page_title"] = f"Role: {role.name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Admin", "href": "/settings/admin"},
        {"label": "Roles", "href": "/settings/admin/roles"},
        {"label": role.name},
    ])
    context["role"] = role
    context["permission_groups"] = permission_groups
    context["role_permission_ids"] = role_permission_ids
    context["is_new"] = False
    context["can_edit"] = user.has_scope("admin:write") and not role.is_system

    template = templates.get_template("modules/settings/templates/pages/admin/role_form.html")
    return HTMLResponse(template.render(context))


@router.post("/roles/{role_id}", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def update_role(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    role_id: str,
    _csrf: CSRFProtect,
):
    """Update role."""
    service = AdminSettingsService(db)
    role = service.get_role(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if role.is_system:
        set_flash(response, "System roles cannot be modified.", "error")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"/settings/admin/roles/{role_id}", status_code=303)

    form = await request.form()
    role.name = _form_str(form, "name", role.name)
    role.description = _form_str(form, "description")

    permission_ids = _form_list(form, "permissions")
    service.update_role(
        role,
        name=role.name,
        description=role.description,
        permission_ids=permission_ids,
    )

    set_flash(response, f"Role '{role.name}' updated successfully.", "success")

    activity_logger = ActivityLogger(db)
    activity_logger.log(
        action="rbac.role.update",
        user_id=user.id,
        entity_type="role",
        entity_id=str(role.id),
        summary=f"Updated role '{role.name}'",
        metadata={"permission_ids": permission_ids},
        request=request,
    )
    db.commit()

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/settings/admin/roles", status_code=303)


@router.delete("/roles/{role_id}", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def delete_role(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    role_id: str,
):
    """Delete role."""
    service = AdminSettingsService(db)
    role = service.get_role(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if role.is_system:
        raise HTTPException(status_code=400, detail="System roles cannot be deleted")

    role_name = role.name
    service.delete_role(role)

    activity_logger = ActivityLogger(db)
    activity_logger.log(
        action="rbac.role.delete",
        user_id=user.id,
        entity_type="role",
        entity_id=str(role_id),
        summary=f"Deleted role '{role_name}'",
        request=request,
    )
    db.commit()

    if is_htmx_request(request):
        response.headers["HX-Trigger"] = "roleDeleted"
        return HTMLResponse("")

    set_flash(response, f"Role '{role_name}' deleted.", "success")
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/settings/admin/roles", status_code=303)


# ============================================================================
# SERVICE TOKENS
# ============================================================================

@router.get("/tokens", response_class=HTMLResponse, dependencies=[RequireAdminRead])
async def tokens_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Service tokens list."""
    service = AdminSettingsService(db)
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "tokens"

    tokens = service.list_tokens()

    context["page_title"] = "Service Tokens"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Admin", "href": "/settings/admin"},
        {"label": "Service Tokens"},
    ])
    context["tokens"] = tokens
    context["can_create"] = user.has_scope("admin:write")

    template = templates.get_template("modules/settings/templates/pages/admin/tokens_list.html")
    return HTMLResponse(template.render(context))


@router.post("/tokens", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def create_token(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _csrf: CSRFProtect,
):
    """Create service token."""
    form = await request.form()
    name = _form_str(form, "name")
    scopes = _form_str(form, "scopes")
    expires_days = _form_int(form, "expires_days", 365)

    if not name:
        set_flash(response, "Token name is required.", "error")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/settings/admin/tokens", status_code=303)

    service = AdminSettingsService(db)
    _, token_value = service.create_token(
        name=name,
        scopes=scopes.split(",") if scopes else [],
        expires_days=expires_days,
        created_by_id=user.id,
    )

    # Show the token once
    set_flash(
        response,
        f"Token created. Copy it now, it won't be shown again: {token_value}",
        "success"
    )

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/settings/admin/tokens", status_code=303)


@router.delete("/tokens/{token_id}", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def revoke_token(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    token_id: str,
):
    """Revoke service token."""
    service = AdminSettingsService(db)
    token = service.revoke_token(token_id)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")

    token_name = token.name

    if is_htmx_request(request):
        response.headers["HX-Trigger"] = "tokenRevoked"
        return HTMLResponse("")

    set_flash(response, f"Token '{token_name}' revoked.", "success")
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/settings/admin/tokens", status_code=303)


# ============================================================================
# AUDIT LOG
# ============================================================================

@router.get("/audit", response_class=HTMLResponse, dependencies=[RequireAdminRead])
async def audit_log(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search by user email"),
    group: Optional[str] = Query(None, description="Filter by settings group"),
    action: Optional[str] = Query(None, description="Filter by action"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=100),
):
    """Audit log viewer."""
    service = AdminSettingsService(db)
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "audit"

    entries, total = service.list_audit_log(
        q=q,
        group=group,
        action=action,
        page=page,
        per_page=per_page,
    )

    context["page_title"] = "Audit Log"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Admin", "href": "/settings/admin"},
        {"label": "Audit Log"},
    ])
    context["entries"] = entries
    context["search_query"] = q or ""
    context["current_group"] = group
    context["current_action"] = action
    context["pagination"] = build_pagination_context(page, per_page, total)

    # Filter options
    context["group_options"] = ["email", "payments", "webhooks", "sms", "notifications", "branding", "localization"]
    context["action_options"] = ["create", "update", "delete", "test"]

    if is_htmx_request(request):
        template = templates.get_template("modules/settings/templates/partials/audit_table.html")
    else:
        template = templates.get_template("modules/settings/templates/pages/admin/audit_log.html")

    return HTMLResponse(template.render(context))


# ============================================================================
# ACTIVITY LOG
# ============================================================================

@router.get("/activity", response_class=HTMLResponse, dependencies=[RequireAdminRead])
async def activity_log(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search by user email or summary"),
    action: Optional[str] = Query(None, description="Filter by action"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=100),
):
    """Activity log viewer."""
    service = AdminSettingsService(db)
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "activity"

    entries, total = service.list_activity_log(
        q=q,
        action=action,
        entity_type=entity_type,
        page=page,
        per_page=per_page,
    )

    context["page_title"] = "Activity Log"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Admin", "href": "/settings/admin"},
        {"label": "Activity Log"},
    ])
    context["entries"] = entries
    context["search_query"] = q or ""
    context["current_action"] = action
    context["current_entity_type"] = entity_type
    context["pagination"] = build_pagination_context(page, per_page, total)

    context["action_options"] = [
        "login",
        "logout",
        "session.revoke",
        "session.revoke_all",
        "rbac.user.create",
        "rbac.user.update",
        "rbac.role.create",
        "rbac.role.update",
        "rbac.role.delete",
        "rbac.group.create",
        "rbac.group.update",
        "rbac.group.delete",
        "rbac.group.member.add",
        "rbac.group.member.remove",
        "rbac.permission.assign",
        "rbac.permission.revoke",
        "settings.create",
        "settings.update",
        "settings.delete",
        "settings.test",
        "approval.submit",
        "approval.approve",
        "approval.reject",
        "approval.post",
        "approval.cancel",
        "finance.invoice.create",
        "finance.invoice.update",
        "finance.invoice.delete",
        "finance.invoice.submit",
        "finance.invoice.post",
        "finance.invoice.cancel",
        "finance.payment.create",
        "finance.payment.update",
        "finance.payment.delete",
        "finance.payment.approve",
        "finance.payment.post",
        "finance.payment.allocate",
        "finance.supplier_payment.create",
        "finance.supplier_payment.update",
        "finance.supplier_payment.delete",
        "finance.supplier_payment.allocate",
        "finance.supplier_payment.approve",
        "finance.supplier_payment.reject",
        "finance.supplier_payment.post",
        "finance.journal_entry.create",
        "finance.journal_entry.update",
        "finance.journal_entry.delete",
        "finance.journal_entry.post",
        "finance.bank_reconciliation.start",
        "finance.bank_reconciliation.match",
        "finance.bank_reconciliation.auto_match",
        "finance.bank_reconciliation.complete",
        "finance.bank_reconciliation.import",
        "finance.expense_claim.create",
        "finance.expense_claim.submit",
        "finance.expense_claim.approve",
        "finance.expense_claim.reject",
        "finance.expense_claim.return",
        "finance.expense_claim.recall",
        "crm.party.create",
        "crm.party.update",
        "crm.party.delete",
        "support.ticket.create",
        "support.ticket.update",
        "support.ticket.delete",
        "support.message.inbound",
        "support.message.outbound",
        "support.message.note",
        "subscriptions.create",
        "subscriptions.update",
        "subscriptions.delete",
        "subscriptions.status.change",
        "subscriptions.provisioning.configure",
        "subscriptions.provisioning.mark",
        "subscriptions.plan.upgrade",
        "subscriptions.plan.downgrade",
        "inventory.stock_entry.create",
        "inventory.stock_entry.update",
        "inventory.stock_entry.submit",
        "inventory.stock_entry.cancel",
        "inventory.stock_entry.delete",
        "hr.employee.create",
        "hr.employee.update",
        "hr.employee.delete",
        "hr.employee.status.activate",
        "hr.employee.status.deactivate",
        "hr.employee.status.terminate",
        "hr.payroll.entry.create",
        "hr.payroll.entry.update",
        "hr.payroll.entry.delete",
        "hr.payroll.slips.generate",
        "hr.payroll.slips.submit",
        "projects.project.create",
        "projects.project.update",
        "projects.project.delete",
        "projects.task.create",
        "projects.task.update",
        "projects.task.delete",
        "ops.import.csv",
        "ops.import.rows",
        "ops.data_cleanup.bulk_update",
        "ops.data_cleanup.normalize_phones",
        "ops.data_cleanup.normalize_emails",
        "ops.data_cleanup.merge_duplicates",
        "ops.data_cleanup.link_orphans",
    ]
    context["entity_type_options"] = [
        "auth",
        "session",
        "user",
        "role",
        "group",
        "permission",
        "settings",
        "approval",
        "invoice",
        "payment",
        "supplier_payment",
        "journal_entry",
        "bank_reconciliation",
        "bank_transaction",
        "expense_claim",
        "party",
        "ticket",
        "message",
        "subscription",
        "stock_entry",
        "employee",
        "payroll_entry",
        "project",
        "task",
        "import",
        "data_cleanup",
    ]

    if is_htmx_request(request):
        template = templates.get_template("modules/settings/templates/partials/activity_log_table.html")
    else:
        template = templates.get_template("modules/settings/templates/pages/admin/activity_log.html")

    return HTMLResponse(template.render(context))


# ============================================================================
# WEBHOOK MANAGEMENT
# ============================================================================

@router.get("/webhooks", response_class=HTMLResponse, dependencies=[RequireAdminRead])
async def webhooks_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Webhook configurations list."""
    service = AdminSettingsService(db)
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "webhooks"

    webhooks, total = service.list_webhooks(
        q=q,
        status=status,
        page=page,
        per_page=per_page,
    )

    context["page_title"] = "Webhooks"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Admin", "href": "/settings/admin"},
        {"label": "Webhooks"},
    ])
    context["webhooks"] = webhooks
    context["search_query"] = q or ""
    context["current_status"] = status
    context["pagination"] = build_pagination_context(page, per_page, total)
    context["can_create"] = user.has_scope("admin:write")

    if is_htmx_request(request):
        template = templates.get_template("modules/settings/templates/partials/webhooks_table.html")
    else:
        template = templates.get_template("modules/settings/templates/pages/admin/webhooks_list.html")

    return HTMLResponse(template.render(context))


@router.get("/webhooks/new", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def new_webhook_form(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
):
    """New webhook creation form."""
    from app.models.notification import NotificationEventType

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "webhooks"

    context["page_title"] = "New Webhook"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Admin", "href": "/settings/admin"},
        {"label": "Webhooks", "href": "/settings/admin/webhooks"},
        {"label": "New Webhook"},
    ])
    context["webhook"] = None
    context["is_new"] = True
    context["event_types"] = [e.value for e in NotificationEventType]
    context["auth_types"] = ["none", "bearer", "basic", "api_key", "hmac"]
    context["http_methods"] = ["POST", "PUT", "PATCH"]

    template = templates.get_template("modules/settings/templates/pages/admin/webhook_form.html")
    return HTMLResponse(template.render(context))


@router.post("/webhooks", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def create_webhook(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _csrf: CSRFProtect,
):
    """Create new webhook."""
    form = await request.form()
    name = _form_str(form, "name")
    url = _form_str(form, "url")
    method = _form_str(form, "method", "POST")
    auth_type = _form_str(form, "auth_type", "none")
    auth_header = _form_str(form, "auth_header") or None
    auth_value = _form_str(form, "auth_value") or None
    description = _form_str(form, "description") or None
    event_types = _form_list(form, "event_types")
    max_retries = _form_int(form, "max_retries", 3)

    if not name or not url:
        set_flash(response, "Name and URL are required.", "error")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/settings/admin/webhooks/new", status_code=303)

    service = AdminSettingsService(db)
    _, signing_secret = service.create_webhook(
        name=name,
        url=url,
        method=method,
        auth_type=auth_type,
        auth_header=auth_header,
        description=description,
        event_types=event_types,
        max_retries=max_retries,
        created_by_id=user.id,
    )

    set_flash(
        response,
        f"Webhook '{name}' created. Signing secret: {signing_secret} (save this, it won't be shown again)",
        "success"
    )

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/settings/admin/webhooks", status_code=303)


@router.get("/webhooks/{webhook_id}", response_class=HTMLResponse, dependencies=[RequireAdminRead])
async def webhook_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    webhook_id: int,
):
    """Webhook detail/edit form."""
    from app.models.notification import NotificationEventType

    service = AdminSettingsService(db)
    webhook = service.get_webhook(webhook_id)

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    deliveries = service.list_webhook_deliveries(webhook_id, limit=20)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "webhooks"

    context["page_title"] = f"Webhook: {webhook.name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Admin", "href": "/settings/admin"},
        {"label": "Webhooks", "href": "/settings/admin/webhooks"},
        {"label": webhook.name},
    ])
    context["webhook"] = webhook
    context["deliveries"] = deliveries
    context["is_new"] = False
    context["event_types"] = [e.value for e in NotificationEventType]
    context["auth_types"] = ["none", "bearer", "basic", "api_key", "hmac"]
    context["http_methods"] = ["POST", "PUT", "PATCH"]
    context["can_edit"] = user.has_scope("admin:write")

    template = templates.get_template("modules/settings/templates/pages/admin/webhook_form.html")
    return HTMLResponse(template.render(context))


@router.post("/webhooks/{webhook_id}", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def update_webhook(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    webhook_id: int,
    _csrf: CSRFProtect,
):
    """Update webhook."""
    service = AdminSettingsService(db)
    webhook = service.get_webhook(webhook_id)

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    form = await request.form()
    service.update_webhook(
        webhook,
        name=_form_str(form, "name", webhook.name) or webhook.name,
        url=_form_str(form, "url", webhook.url) or webhook.url,
        method=_form_str(form, "method", webhook.method) or webhook.method,
        auth_type=_form_str(form, "auth_type", webhook.auth_type),
        auth_header=_form_str(form, "auth_header") or None,
        description=_form_str(form, "description") or None,
        event_types=_form_list(form, "event_types"),
        max_retries=_form_int(form, "max_retries", webhook.max_retries),
        is_active=_form_str(form, "is_active") in ("true", "on", "1"),
        updated_by_id=user.id,
    )

    set_flash(response, f"Webhook '{webhook.name}' updated successfully.", "success")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/settings/admin/webhooks/{webhook_id}", status_code=303)


@router.post("/webhooks/{webhook_id}/toggle", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def toggle_webhook(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    webhook_id: int,
):
    """Toggle webhook active status."""
    service = AdminSettingsService(db)
    webhook = service.get_webhook(webhook_id)

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    webhook = service.toggle_webhook(webhook)

    if is_htmx_request(request):
        context = {"webhook": webhook, "can_edit": True}
        template = templates.get_template("modules/settings/templates/partials/webhook_row.html")
        return HTMLResponse(template.render(context))

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/settings/admin/webhooks", status_code=303)


@router.delete("/webhooks/{webhook_id}", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def delete_webhook(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    webhook_id: int,
):
    """Delete (soft) webhook."""
    service = AdminSettingsService(db)
    webhook = service.get_webhook(webhook_id)

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    webhook_name = webhook.name
    service.delete_webhook(webhook, deleted_by_id=user.id)

    if is_htmx_request(request):
        response.headers["HX-Trigger"] = "webhookDeleted"
        return HTMLResponse("")

    set_flash(response, f"Webhook '{webhook_name}' deleted.", "success")
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/settings/admin/webhooks", status_code=303)


@router.post("/webhooks/{webhook_id}/test", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def test_webhook(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    webhook_id: int,
):
    """Send test webhook."""
    import httpx
    from datetime import datetime

    service = AdminSettingsService(db)
    webhook = service.get_webhook(webhook_id)

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    # Prepare test payload
    test_payload = {
        "event": "test.ping",
        "timestamp": datetime.utcnow().isoformat(),
        "webhook_id": webhook.id,
        "webhook_name": webhook.name,
        "data": {"message": "This is a test webhook delivery"},
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Content-Type": "application/json"}

            # Add auth header if configured
            if webhook.auth_type == "bearer" and webhook.auth_header:
                headers["Authorization"] = f"Bearer {webhook.auth_header}"
            elif webhook.auth_type == "api_key" and webhook.auth_header:
                headers[webhook.auth_header or "X-API-Key"] = "***"

            resp = await client.request(
                method=webhook.method,
                url=webhook.url,
                json=test_payload,
                headers=headers,
            )

            if resp.status_code < 400:
                set_flash(response, f"Test webhook sent successfully. Status: {resp.status_code}", "success")
            else:
                set_flash(response, f"Webhook returned error status: {resp.status_code}", "warning")

    except Exception as e:
        set_flash(response, f"Webhook test failed: {str(e)}", "error")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/settings/admin/webhooks/{webhook_id}", status_code=303)


# ============================================================================
# GROUP MANAGEMENT
# ============================================================================

@router.get("/groups", response_class=HTMLResponse, dependencies=[RequireAdminRead])
async def groups_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Group management list."""
    service = AdminSettingsService(db)
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "groups"

    groups, total = service.list_groups(q=q, page=page, per_page=per_page)

    context["page_title"] = "Groups"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Admin", "href": "/settings/admin"},
        {"label": "Groups"},
    ])
    context["groups"] = groups
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)
    context["can_create"] = user.has_scope("admin:write")

    if is_htmx_request(request):
        template = templates.get_template("modules/settings/templates/partials/groups_table.html")
    else:
        template = templates.get_template("modules/settings/templates/pages/admin/groups_list.html")

    return HTMLResponse(template.render(context))


@router.get("/groups/new", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def new_group_form(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New group creation form."""
    service = AdminSettingsService(db)
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "groups"

    roles = service.list_roles()

    context["page_title"] = "New Group"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Admin", "href": "/settings/admin"},
        {"label": "Groups", "href": "/settings/admin/groups"},
        {"label": "New Group"},
    ])
    context["group"] = None
    context["all_roles"] = roles
    context["is_new"] = True

    template = templates.get_template("modules/settings/templates/pages/admin/group_form.html")
    return HTMLResponse(template.render(context))


@router.post("/groups", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def create_group(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _csrf: CSRFProtect,
):
    """Create new group."""
    form = await request.form()
    name = _form_str(form, "name")
    description = _form_str(form, "description")
    role_ids = _form_list(form, "roles")

    if not name:
        set_flash(response, "Group name is required.", "error")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/settings/admin/groups/new", status_code=303)

    service = AdminSettingsService(db)
    group = service.create_group(
        name=name,
        description=description,
        role_ids=role_ids,
        created_by_id=user.id,
    )
    if not group:
        set_flash(response, f"Group '{name}' already exists.", "error")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/settings/admin/groups/new", status_code=303)

    set_flash(response, f"Group '{name}' created successfully.", "success")

    activity_logger = ActivityLogger(db)
    activity_logger.log(
        action="rbac.group.create",
        user_id=user.id,
        entity_type="group",
        entity_id=str(group.id),
        summary=f"Created group '{group.name}'",
        metadata={"role_ids": role_ids},
        request=request,
    )
    db.commit()

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/settings/admin/groups", status_code=303)


@router.get("/groups/{group_id}", response_class=HTMLResponse, dependencies=[RequireAdminRead])
async def group_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    group_id: int,
):
    """Group detail/edit page."""
    service = AdminSettingsService(db)
    group = service.get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "groups"

    # Get all roles for assignment
    roles = service.list_roles()

    # Get current role IDs
    group_role_ids = {str(gr.role_id) for gr in group.group_roles}

    # Get available users (not already in group)
    available_users = service.list_available_group_users(group)

    context["page_title"] = f"Group: {group.name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Admin", "href": "/settings/admin"},
        {"label": "Groups", "href": "/settings/admin/groups"},
        {"label": group.name},
    ])
    context["group"] = group
    context["all_roles"] = roles
    context["group_role_ids"] = group_role_ids
    context["available_users"] = available_users
    context["is_new"] = False
    context["can_edit"] = user.has_scope("admin:write")

    template = templates.get_template("modules/settings/templates/pages/admin/group_detail.html")
    return HTMLResponse(template.render(context))


@router.post("/groups/{group_id}", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def update_group(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    group_id: int,
    _csrf: CSRFProtect,
):
    """Update group."""
    service = AdminSettingsService(db)
    group = service.get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    form = await request.form()
    is_active = _form_str(form, "is_active") in ("true", "on", "1")
    role_ids = _form_list(form, "roles")
    service.update_group(
        group,
        name=_form_str(form, "name", group.name) or group.name,
        description=_form_str(form, "description"),
        is_active=is_active,
        role_ids=role_ids,
        updated_by_id=user.id,
    )

    set_flash(response, f"Group '{group.name}' updated successfully.", "success")

    activity_logger = ActivityLogger(db)
    activity_logger.log(
        action="rbac.group.update",
        user_id=user.id,
        entity_type="group",
        entity_id=str(group.id),
        summary=f"Updated group '{group.name}'",
        metadata={"role_ids": role_ids, "is_active": is_active},
        request=request,
    )
    db.commit()

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/settings/admin/groups/{group_id}", status_code=303)


@router.post("/groups/{group_id}/members", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def add_group_member(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    group_id: int,
    _csrf: CSRFProtect,
):
    """Add member to group."""
    service = AdminSettingsService(db)
    group = service.get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    form = await request.form()
    user_id = _form_int(form, "user_id", 0)

    if not user_id:
        set_flash(response, "User is required.", "error")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"/settings/admin/groups/{group_id}", status_code=303)

    added = service.add_group_member(
        group_id=group_id,
        user_id=user_id,
        added_by_id=user.id,
    )
    if not added:
        set_flash(response, "User is already a member of this group.", "warning")
    else:
        set_flash(response, "Member added successfully.", "success")
        activity_logger = ActivityLogger(db)
        activity_logger.log(
            action="rbac.group.member.add",
            user_id=user.id,
            entity_type="group",
            entity_id=str(group_id),
            summary=f"Added member to group '{group.name}'",
            metadata={"member_user_id": user_id},
            request=request,
        )
        db.commit()

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/settings/admin/groups/{group_id}", status_code=303)


@router.delete("/groups/{group_id}/members/{member_user_id}", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def remove_group_member(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    group_id: int,
    member_user_id: int,
):
    """Remove member from group."""
    service = AdminSettingsService(db)
    service.remove_group_member(group_id=group_id, user_id=member_user_id)

    if is_htmx_request(request):
        activity_logger = ActivityLogger(db)
        activity_logger.log(
            action="rbac.group.member.remove",
            user_id=user.id,
            entity_type="group",
            entity_id=str(group_id),
            summary="Removed member from group",
            metadata={"member_user_id": member_user_id},
            request=request,
        )
        db.commit()
        response.headers["HX-Trigger"] = "memberRemoved"
        return HTMLResponse("")

    set_flash(response, "Member removed.", "success")
    activity_logger = ActivityLogger(db)
    activity_logger.log(
        action="rbac.group.member.remove",
        user_id=user.id,
        entity_type="group",
        entity_id=str(group_id),
        summary="Removed member from group",
        metadata={"member_user_id": member_user_id},
        request=request,
    )
    db.commit()
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/settings/admin/groups/{group_id}", status_code=303)


@router.delete("/groups/{group_id}", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def delete_group(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    group_id: int,
):
    """Delete group."""
    service = AdminSettingsService(db)
    group = service.get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    group_name = group.name
    service.delete_group(group)

    if is_htmx_request(request):
        activity_logger = ActivityLogger(db)
        activity_logger.log(
            action="rbac.group.delete",
            user_id=user.id,
            entity_type="group",
            entity_id=str(group_id),
            summary=f"Deleted group '{group_name}'",
            request=request,
        )
        db.commit()
        response.headers["HX-Trigger"] = "groupDeleted"
        return HTMLResponse("")

    set_flash(response, f"Group '{group_name}' deleted.", "success")
    activity_logger = ActivityLogger(db)
    activity_logger.log(
        action="rbac.group.delete",
        user_id=user.id,
        entity_type="group",
        entity_id=str(group_id),
        summary=f"Deleted group '{group_name}'",
        request=request,
    )
    db.commit()
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/settings/admin/groups", status_code=303)


# ============================================================================
# PERMISSIONS BROWSER
# ============================================================================

@router.get("/permissions", response_class=HTMLResponse, dependencies=[RequireAdminRead])
async def permissions_browser(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    category: Optional[str] = Query(None, description="Filter by category"),
):
    """Browse all permissions organized by category."""
    service = AdminSettingsService(db)
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "permissions"

    # Get all categories
    categories = service.list_permission_categories()
    permissions = service.list_permissions_for_category(category)

    # Group permissions by category (fallback to string category if no category_id)
    permission_groups: dict[str, list] = {}
    for perm in permissions:
        if perm.permission_category:
            cat_name = perm.permission_category.display_name
        else:
            cat_name = perm.category or "Other"
        if cat_name not in permission_groups:
            permission_groups[cat_name] = []
        permission_groups[cat_name].append(perm)

    context["page_title"] = "Permissions Browser"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Admin", "href": "/settings/admin"},
        {"label": "Permissions"},
    ])
    context["categories"] = categories
    context["current_category"] = category
    context["permission_groups"] = permission_groups
    context["total_permissions"] = len(permissions)

    template = templates.get_template("modules/settings/templates/pages/admin/permissions_browser.html")
    return HTMLResponse(template.render(context))


# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

@router.get("/sessions", response_class=HTMLResponse, dependencies=[RequireAdminRead])
async def sessions_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search by user email"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=100),
):
    """List all active sessions."""
    service = AdminSettingsService(db)
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "sessions"

    sessions, total = service.list_active_sessions(q=q, page=page, per_page=per_page)

    context["page_title"] = "Active Sessions"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Admin", "href": "/settings/admin"},
        {"label": "Sessions"},
    ])
    context["sessions"] = sessions
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)
    context["can_revoke"] = user.has_scope("admin:write")

    if is_htmx_request(request):
        template = templates.get_template("modules/settings/templates/partials/sessions_table.html")
    else:
        template = templates.get_template("modules/settings/templates/pages/admin/sessions_list.html")

    return HTMLResponse(template.render(context))


@router.post("/sessions/{session_id}/revoke", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def revoke_session(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    session_id: str,
):
    """Revoke a user session."""
    service = AdminSettingsService(db)
    success = service.revoke_session(
        session_id=session_id,
        revoked_by_id=user.id,
        reason="Revoked by administrator"
    )

    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    activity_logger = ActivityLogger(db)
    activity_logger.log(
        action="session.revoke",
        user_id=user.id,
        entity_type="session",
        entity_id=session_id,
        summary="Revoked a user session",
        request=request,
    )
    db.commit()

    if is_htmx_request(request):
        response.headers["HX-Trigger"] = "sessionRevoked"
        return HTMLResponse("")

    set_flash(response, "Session revoked successfully.", "success")
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/settings/admin/sessions", status_code=303)


@router.get("/users/{user_id}/sessions", response_class=HTMLResponse, dependencies=[RequireAdminRead])
async def user_sessions(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    user_id: int,
):
    """List sessions for a specific user."""
    from app.services.session_service import SessionService

    service = AdminSettingsService(db)
    target_user = service.get_user(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    session_service = SessionService(db)
    sessions = session_service.get_active_sessions(user_id)
    summary = session_service.get_sessions_summary(user_id)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "sessions"

    context["page_title"] = f"Sessions: {target_user.name or target_user.email}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Admin", "href": "/settings/admin"},
        {"label": "Sessions", "href": "/settings/admin/sessions"},
        {"label": target_user.name or target_user.email},
    ])
    context["target_user"] = target_user
    context["sessions"] = sessions
    context["summary"] = summary
    context["can_revoke"] = user.has_scope("admin:write")

    template = templates.get_template("modules/settings/templates/pages/admin/user_sessions.html")
    return HTMLResponse(template.render(context))


@router.post("/users/{user_id}/sessions/revoke-all", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def revoke_all_user_sessions(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    user_id: int,
):
    """Revoke all sessions for a user."""
    service = AdminSettingsService(db)
    target_user = service.get_user(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    count = service.revoke_all_sessions(
        user_id=user_id,
        revoked_by_id=user.id,
        reason="All sessions revoked by administrator"
    )

    activity_logger = ActivityLogger(db)
    activity_logger.log(
        action="session.revoke_all",
        user_id=user.id,
        entity_type="session",
        entity_id=str(user_id),
        summary=f"Revoked all sessions for {target_user.email}",
        metadata={"revoked_count": count, "target_user_id": user_id},
        request=request,
    )
    db.commit()

    set_flash(response, f"Revoked {count} session(s) for {target_user.email}.", "success")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/settings/admin/users/{user_id}/sessions", status_code=303)


# ============================================================================
# USER DIRECT PERMISSIONS
# ============================================================================

@router.get("/users/{user_id}/permissions", response_class=HTMLResponse, dependencies=[RequireAdminRead])
async def user_permissions(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    user_id: int,
):
    """View and manage direct permissions for a user."""
    from app.services.rbac_service import RBACService
    from app.feature_flags import feature_flags

    service = AdminSettingsService(db)
    target_user = service.get_user(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "users"

    # Get effective permissions if granular RBAC is enabled
    effective_permissions = None
    if feature_flags.RBAC_GRANULAR_ENABLED:
        rbac_service = RBACService(db)
        effective_permissions = await rbac_service.get_effective_permissions(user_id)

    # Get direct permissions
    direct_permissions = service.list_user_permissions(user_id)

    # Get all available permissions
    all_permissions = service.list_permissions()

    # Group permissions by category
    permission_groups: dict[str, list] = {}
    for perm in all_permissions:
        cat = perm.category or "Other"
        if cat not in permission_groups:
            permission_groups[cat] = []
        permission_groups[cat].append(perm)

    context["page_title"] = f"Permissions: {target_user.name or target_user.email}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Admin", "href": "/settings/admin"},
        {"label": "Users", "href": "/settings/admin/users"},
        {"label": target_user.name or target_user.email, "href": f"/settings/admin/users/{user_id}"},
        {"label": "Permissions"},
    ])
    context["target_user"] = target_user
    context["effective_permissions"] = effective_permissions
    context["direct_permissions"] = direct_permissions
    context["permission_groups"] = permission_groups
    context["can_edit"] = user.has_scope("admin:write")
    context["rbac_enabled"] = feature_flags.RBAC_GRANULAR_ENABLED

    template = templates.get_template("modules/settings/templates/pages/admin/user_permissions.html")
    return HTMLResponse(template.render(context))


@router.post("/users/{user_id}/permissions", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def add_user_permission(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    user_id: int,
    _csrf: CSRFProtect,
):
    """Add direct permission to user."""
    service = AdminSettingsService(db)
    target_user = service.get_user(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    form = await request.form()
    permission_id = _form_int(form, "permission_id", 0)
    grant_type = _form_str(form, "grant_type", "allow")
    reason = _form_str(form, "reason")

    if not permission_id:
        set_flash(response, "Permission is required.", "error")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"/settings/admin/users/{user_id}/permissions", status_code=303)

    created = service.add_user_permission(
        user_id=user_id,
        permission_id=permission_id,
        grant_type=grant_type,
        reason=reason,
        created_by_id=user.id,
    )
    if created:
        set_flash(response, "Permission added.", "success")
    else:
        set_flash(response, "Permission updated.", "success")

    activity_logger = ActivityLogger(db)
    activity_logger.log(
        action="rbac.permission.assign",
        user_id=user.id,
        entity_type="permission",
        entity_id=str(permission_id),
        summary=f"Assigned permission to {target_user.email}",
        metadata={"target_user_id": user_id, "grant_type": grant_type, "reason": reason},
        request=request,
    )
    db.commit()

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/settings/admin/users/{user_id}/permissions", status_code=303)


@router.delete("/users/{user_id}/permissions/{permission_id}", response_class=HTMLResponse, dependencies=[RequireAdminWrite])
async def remove_user_permission(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    user_id: int,
    permission_id: int,
):
    """Remove direct permission from user."""
    service = AdminSettingsService(db)
    service.remove_user_permission(user_id=user_id, permission_id=permission_id)

    if is_htmx_request(request):
        activity_logger = ActivityLogger(db)
        activity_logger.log(
            action="rbac.permission.revoke",
            user_id=user.id,
            entity_type="permission",
            entity_id=str(permission_id),
            summary=f"Removed permission from user {user_id}",
            metadata={"target_user_id": user_id},
            request=request,
        )
        db.commit()
        response.headers["HX-Trigger"] = "permissionRemoved"
        return HTMLResponse("")

    set_flash(response, "Permission removed.", "success")
    activity_logger = ActivityLogger(db)
    activity_logger.log(
        action="rbac.permission.revoke",
        user_id=user.id,
        entity_type="permission",
        entity_id=str(permission_id),
        summary=f"Removed permission from user {user_id}",
        metadata={"target_user_id": user_id},
        request=request,
    )
    db.commit()
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/settings/admin/users/{user_id}/permissions", status_code=303)
