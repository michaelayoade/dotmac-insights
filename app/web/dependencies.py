"""
FastAPI dependencies for SSR web routes.

Provides typed dependencies for:
- Session-based authentication (with granular RBAC support)
- CSRF protection
- Database access
- Template context
"""
from __future__ import annotations

from typing import Optional, Annotated, Callable

from fastapi import Depends, Request, Response, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import (
    AUTH_COOKIE_NAME,
    verify_jwt,
    get_or_create_user,
    is_token_denylisted,
    Principal,
)
from app.config import settings
from app.core.security import (
    validate_csrf,
    get_csrf_token,
    generate_csrf_token,
    set_csrf_cookie,
    build_login_url,
    is_htmx_request,
)
from app.feature_flags import feature_flags


async def get_session_user(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Optional[Principal]:
    """Get authenticated user from session cookie.

    Returns None if not authenticated (for optional auth routes).
    Does not raise - use require_session_user for protected routes.

    When RBAC_GRANULAR_ENABLED is True, loads effective permissions
    including group memberships and direct permission grants.
    """
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        return None

    try:
        claims = await verify_jwt(token)

        # Check token denylist if jti is present
        if claims.jti and await is_token_denylisted(claims.jti, db):
            return None

        user = await get_or_create_user(claims, db)
        if not user or not user.is_active:
            return None

        # Load effective permissions if granular RBAC is enabled
        effective_permissions = None
        groups = []

        if feature_flags.RBAC_GRANULAR_ENABLED:
            try:
                from app.services.rbac_service import RBACService
                rbac_service = RBACService(db)
                effective_permissions = await rbac_service.get_effective_permissions(user.id)

                # Get group IDs
                groups = [gm.group_id for gm in user.group_memberships]
            except Exception:
                # Fall back to legacy permissions on error
                pass

        return Principal(
            type="user",
            id=user.id,
            external_id=user.external_id,
            email=user.email,
            name=user.name,
            is_superuser=user.is_superuser,
            scopes=user.all_permissions,
            raw_claims=claims.model_dump(),
            effective_permissions=effective_permissions,
            groups=groups,
        )
    except HTTPException:
        return None
    except Exception:
        return None


async def require_session_user(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Principal:
    """Require authenticated user, redirect to login if not.

    For HTMX requests, returns 401 so client can handle redirect.
    For regular requests, returns 303 redirect to login page.

    If AUTH_DISABLED is true, returns a mock superuser principal.
    """
    # Development bypass - return mock superuser
    if settings.auth_disabled:
        return Principal(
            type="user",
            id=1,
            external_id="dev-user",
            email="dev@localhost",
            name="Dev User",
            is_superuser=True,
            scopes={"*"},  # All permissions
            raw_claims={},
        )

    user = await get_session_user(request, response, db)
    if not user:
        login_url = build_login_url(request)

        if is_htmx_request(request):
            # HTMX: Return 401 with redirect header
            raise HTTPException(
                status_code=401,
                headers={"HX-Redirect": login_url},
            )
        else:
            # Regular: HTTP redirect
            raise HTTPException(
                status_code=303,
                headers={"Location": login_url},
            )

    return user


async def csrf_protect(request: Request) -> None:
    """CSRF validation dependency for state-changing routes.

    Add to route dependencies for POST/PUT/DELETE endpoints.
    """
    await validate_csrf(request)


def ensure_csrf_token(request: Request, response: Response) -> str:
    """Ensure CSRF token exists in cookie, generate if needed.

    Returns the token value for use in templates.
    """
    token = get_csrf_token(request)
    if not token:
        token = generate_csrf_token()
        set_csrf_cookie(response, token)
    # Store on request for middleware to attach to outgoing responses.
    request.state.csrf_token = token
    return token


def require_scope(scope: str):
    """Create a dependency that requires a specific permission scope.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_scope("admin:read"))])
        async def admin_page(...): ...
    """
    async def check_scope(
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ) -> Principal:
        user = await require_session_user(request, response, db)
        if not user.has_scope(scope):
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: requires {scope}",
            )
        return user

    return check_scope


def require_scope_with_context(
    scope: str,
    context_builder: Optional[Callable[[Request], dict]] = None,
):
    """Create a dependency that requires a permission scope with context.

    This allows conditional permissions to be evaluated using request context.

    Usage:
        def build_context(request: Request) -> dict:
            return {
                "client_ip": request.client.host,
                "request_path": str(request.url.path),
            }

        @router.get(
            "/resource/{id}",
            dependencies=[Depends(require_scope_with_context("resource:read", build_context))]
        )
        async def get_resource(...): ...
    """
    async def check_scope(
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ) -> Principal:
        user = await require_session_user(request, response, db)

        # Build context if builder is provided
        context = None
        if context_builder:
            try:
                context = context_builder(request)
            except Exception:
                pass

        if not user.has_scope(scope, context):
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: requires {scope}",
            )
        return user

    return check_scope


def require_any_scope(*scopes: str):
    """Create a dependency that requires at least one of the specified scopes.

    Usage:
        @router.get(
            "/dashboard",
            dependencies=[Depends(require_any_scope("admin:read", "analytics:read"))]
        )
        async def dashboard(...): ...
    """
    async def check_scope(
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ) -> Principal:
        user = await require_session_user(request, response, db)

        if not any(user.has_scope(scope) for scope in scopes):
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: requires one of {', '.join(scopes)}",
            )
        return user

    return check_scope


def require_all_scopes(*scopes: str):
    """Create a dependency that requires all of the specified scopes.

    Usage:
        @router.post(
            "/dangerous-action",
            dependencies=[Depends(require_all_scopes("admin:write", "audit:write"))]
        )
        async def dangerous_action(...): ...
    """
    async def check_scope(
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ) -> Principal:
        user = await require_session_user(request, response, db)

        missing = [scope for scope in scopes if not user.has_scope(scope)]
        if missing:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: requires {', '.join(missing)}",
            )
        return user

    return check_scope


# ============================================================================
# Type Aliases for Clean Route Signatures
# ============================================================================

# Session user (required - redirects to login if not authenticated)
SessionUser = Annotated[Principal, Depends(require_session_user)]

# Optional user (for pages that work with or without auth)
OptionalUser = Annotated[Optional[Principal], Depends(get_session_user)]

# CSRF token value for templates
CSRFToken = Annotated[str, Depends(ensure_csrf_token)]

# CSRF protection (validates token on POST/PUT/DELETE)
CSRFProtect = Annotated[None, Depends(csrf_protect)]

# Database session
DB = Annotated[Session, Depends(get_db)]
