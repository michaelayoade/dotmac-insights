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
    {"id": "tokens", "label": "Service Tokens", "href": "/settings/admin/tokens"},
    {"id": "webhooks", "label": "Webhooks", "href": "/settings/admin/webhooks"},
    {"id": "audit", "label": "Audit Log", "href": "/settings/admin/audit"},
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
    from sqlalchemy import or_
    from app.models.auth import User

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "users"

    # Build query
    query = db.query(User)

    if q:
        search_filter = or_(
            User.email.ilike(f"%{q}%"),
            User.name.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    if status:
        query = query.filter(User.is_active == (status == "active"))

    # Count and paginate
    total = query.count()
    users = query.order_by(User.email).offset((page - 1) * per_page).limit(per_page).all()

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
    from app.models.auth import User
    from app.models.rbac import Role

    target_user = db.query(User).filter(User.id == user_id).first()
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
    roles = db.query(Role).order_by(Role.name).all()

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
    from app.models.auth import User
    from app.models.rbac import Role

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    form = await request.form()

    # Update status
    if "is_active" in form:
        target_user.is_active = _form_str(form, "is_active") in ("true", "on", "1")

    # Update roles
    role_ids = _form_list(form, "roles")
    if role_ids:
        roles = db.query(Role).filter(Role.id.in_(role_ids)).all()
        target_user.roles = roles

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
    from app.models.auth import User

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    target_user.is_active = not target_user.is_active
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
    from app.models.rbac import Role

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "roles"

    roles = db.query(Role).order_by(Role.is_system.desc(), Role.name).all()

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
    from app.models.rbac import Permission

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "roles"

    permissions = db.query(Permission).order_by(Permission.category, Permission.name).all()

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
    from app.models.rbac import Role, Permission

    form = await request.form()
    name = _form_str(form, "name")
    description = _form_str(form, "description")
    permission_ids = _form_list(form, "permissions")

    if not name:
        set_flash(response, "Role name is required.", "error")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/settings/admin/roles/new", status_code=303)

    # Check for duplicate
    existing = db.query(Role).filter(Role.name == name).first()
    if existing:
        set_flash(response, f"Role '{name}' already exists.", "error")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/settings/admin/roles/new", status_code=303)

    # Get permissions
    permissions = []
    if permission_ids:
        permissions = db.query(Permission).filter(Permission.id.in_(permission_ids)).all()

    role = Role(
        name=name,
        description=description,
        is_system=False,
        permissions=permissions,
    )
    db.add(role)
    db.commit()

    set_flash(response, f"Role '{name}' created successfully.", "success")

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
    from app.models.rbac import Role, Permission

    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "roles"

    permissions = db.query(Permission).order_by(Permission.category, Permission.name).all()

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
    from app.models.rbac import Role, Permission

    role = db.query(Role).filter(Role.id == role_id).first()
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
    if permission_ids:
        permissions = db.query(Permission).filter(Permission.id.in_(permission_ids)).all()
        role.permissions = permissions
    else:
        role.permissions = []

    db.commit()

    set_flash(response, f"Role '{role.name}' updated successfully.", "success")

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
    from app.models.rbac import Role

    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if role.is_system:
        raise HTTPException(status_code=400, detail="System roles cannot be deleted")

    role_name = role.name
    db.delete(role)
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
    from app.models.rbac import ServiceToken

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "tokens"

    tokens = db.query(ServiceToken).order_by(ServiceToken.created_at.desc()).all()

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
    from app.models.rbac import ServiceToken
    import secrets
    from datetime import datetime, timedelta

    form = await request.form()
    name = _form_str(form, "name")
    scopes = _form_str(form, "scopes")
    expires_days = _form_int(form, "expires_days", 365)

    if not name:
        set_flash(response, "Token name is required.", "error")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/settings/admin/tokens", status_code=303)

    # Generate token
    token_value = secrets.token_urlsafe(32)
    token_prefix = token_value[:8]

    token = ServiceToken(
        name=name,
        token_prefix=token_prefix,
        token_hash=token_value,  # In production, this should be hashed
        scopes=scopes.split(",") if scopes else [],
        expires_at=datetime.utcnow() + timedelta(days=expires_days),
        created_by_id=user.id,
    )
    db.add(token)
    db.commit()

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
    from app.models.rbac import ServiceToken

    token = db.query(ServiceToken).filter(ServiceToken.id == token_id).first()
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")

    token_name = token.name
    db.delete(token)
    db.commit()

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
    from app.models.settings import SettingsAuditLog

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "audit"

    # Build query
    query = db.query(SettingsAuditLog)

    if q:
        query = query.filter(SettingsAuditLog.user_email.ilike(f"%{q}%"))
    if group:
        query = query.filter(SettingsAuditLog.group_name == group)
    if action:
        query = query.filter(SettingsAuditLog.action == action)

    # Count and paginate
    total = query.count()
    entries = query.order_by(SettingsAuditLog.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

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
    from app.models.notification import WebhookConfig

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "admin")
    context["admin_tabs"] = ADMIN_TABS
    context["current_tab"] = "webhooks"

    # Build query
    query = db.query(WebhookConfig).filter(WebhookConfig.is_deleted == False)

    if q:
        from sqlalchemy import or_
        search_filter = or_(
            WebhookConfig.name.ilike(f"%{q}%"),
            WebhookConfig.url.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    if status == "active":
        query = query.filter(WebhookConfig.is_active == True)
    elif status == "inactive":
        query = query.filter(WebhookConfig.is_active == False)

    # Count and paginate
    total = query.count()
    webhooks = query.order_by(WebhookConfig.name).offset((page - 1) * per_page).limit(per_page).all()

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
    from app.models.notification import WebhookConfig
    import secrets as py_secrets

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

    # Generate signing secret
    signing_secret = py_secrets.token_urlsafe(32)

    webhook = WebhookConfig(
        name=name,
        description=description,
        url=url,
        method=method,
        auth_type=auth_type,
        auth_header=auth_header,
        event_types=event_types,
        max_retries=max_retries,
        signing_secret=signing_secret,
        created_by_id=user.id,
    )
    db.add(webhook)
    db.commit()

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
    from app.models.notification import WebhookConfig, WebhookDelivery, NotificationEventType

    webhook = db.query(WebhookConfig).filter(
        WebhookConfig.id == webhook_id,
        WebhookConfig.is_deleted == False
    ).first()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    # Get recent deliveries
    deliveries = db.query(WebhookDelivery).filter(
        WebhookDelivery.webhook_id == webhook_id
    ).order_by(WebhookDelivery.created_at.desc()).limit(20).all()

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
    from app.models.notification import WebhookConfig

    webhook = db.query(WebhookConfig).filter(
        WebhookConfig.id == webhook_id,
        WebhookConfig.is_deleted == False
    ).first()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    form = await request.form()
    webhook.name = _form_str(form, "name", webhook.name) or webhook.name
    webhook.url = _form_str(form, "url", webhook.url) or webhook.url
    webhook.method = _form_str(form, "method", webhook.method) or webhook.method
    webhook.auth_type = _form_str(form, "auth_type", webhook.auth_type)
    webhook.auth_header = _form_str(form, "auth_header") or None
    webhook.description = _form_str(form, "description") or None
    webhook.event_types = _form_list(form, "event_types")
    webhook.max_retries = _form_int(form, "max_retries", webhook.max_retries)
    webhook.is_active = _form_str(form, "is_active") in ("true", "on", "1")

    db.commit()

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
    from app.models.notification import WebhookConfig

    webhook = db.query(WebhookConfig).filter(
        WebhookConfig.id == webhook_id,
        WebhookConfig.is_deleted == False
    ).first()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    webhook.is_active = not webhook.is_active
    db.commit()

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
    from app.models.notification import WebhookConfig

    webhook = db.query(WebhookConfig).filter(
        WebhookConfig.id == webhook_id,
        WebhookConfig.is_deleted == False
    ).first()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    webhook_name = webhook.name
    webhook.is_deleted = True
    db.commit()

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
    from app.models.notification import WebhookConfig
    import httpx
    from datetime import datetime

    webhook = db.query(WebhookConfig).filter(
        WebhookConfig.id == webhook_id,
        WebhookConfig.is_deleted == False
    ).first()

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
