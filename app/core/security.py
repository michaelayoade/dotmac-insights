"""
Enhanced session security for SSR frontend.

Provides:
- CSRF token generation and validation
- Session flash messages
- Secure cookie utilities
- Login redirect handling
"""
from __future__ import annotations

import json
import secrets
from typing import Optional, Dict, Any

from fastapi import Request, Response, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import settings


# ============================================================================
# CSRF Protection
# ============================================================================

CSRF_TOKEN_NAME = "dotmac_csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_FORM_FIELD = "csrf_token"
CSRF_TOKEN_LENGTH = 32


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token."""
    return secrets.token_urlsafe(CSRF_TOKEN_LENGTH)


def set_csrf_cookie(response: Response, token: str) -> None:
    """Set CSRF token as a readable cookie (not httpOnly so JS can read it)."""
    response.set_cookie(
        key=CSRF_TOKEN_NAME,
        value=token,
        httponly=False,  # JS needs to read this for HTMX headers
        secure=settings.is_production,
        samesite="lax",
        path="/",
        max_age=86400,  # 24 hours
    )


def get_csrf_token(request: Request) -> Optional[str]:
    """Get CSRF token from cookie."""
    return request.cookies.get(CSRF_TOKEN_NAME)


async def validate_csrf(request: Request) -> None:
    """Validate CSRF token for state-changing requests.

    HTMX automatically includes the token via hx-headers configuration.

    Raises:
        HTTPException: If CSRF validation fails
    """
    # Skip safe methods
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    cookie_token = request.cookies.get(CSRF_TOKEN_NAME)

    # Check header first (HTMX requests)
    header_token = request.headers.get(CSRF_HEADER_NAME)

    # Fall back to form field (standard form submissions)
    form_token = None
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/x-www-form-urlencoded") or \
       content_type.startswith("multipart/form-data"):
        try:
            form_data = await request.form()
            form_token = form_data.get(CSRF_FORM_FIELD)
        except Exception:
            pass

    submitted_token_raw = header_token or form_token
    submitted_token: Optional[str] = None
    if isinstance(submitted_token_raw, str):
        submitted_token = submitted_token_raw

    if not cookie_token:
        raise HTTPException(status_code=403, detail="CSRF token cookie missing")

    if not submitted_token:
        raise HTTPException(status_code=403, detail="CSRF token not provided")

    if not secrets.compare_digest(cookie_token, submitted_token):
        raise HTTPException(status_code=403, detail="CSRF token invalid")


# ============================================================================
# Flash Messages
# ============================================================================

FLASH_COOKIE_NAME = "dotmac_flash"


class FlashMessage(BaseModel):
    """A flash message to display on the next page load."""
    category: str  # success, error, warning, info
    message: str


def set_flash(response: Response, message: str, category: str = "info") -> None:
    """Set a flash message to be displayed on the next request."""
    flash_data = json.dumps({"category": category, "message": message})
    response.set_cookie(
        key=FLASH_COOKIE_NAME,
        value=flash_data,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/",
        max_age=60,  # Short-lived
    )


def get_flash(request: Request, response: Response) -> Optional[FlashMessage]:
    """Get and clear flash message from cookie.

    Returns the flash message and deletes the cookie so it only shows once.
    """
    flash_data = request.cookies.get(FLASH_COOKIE_NAME)
    if not flash_data:
        return None

    # Clear the cookie
    response.delete_cookie(FLASH_COOKIE_NAME, path="/")

    try:
        data = json.loads(flash_data)
        return FlashMessage(**data)
    except (json.JSONDecodeError, ValueError):
        return None


# ============================================================================
# Session Utilities
# ============================================================================

def get_login_redirect_url(request: Request) -> str:
    """Get URL to redirect to after successful login.

    Checks for 'next' query parameter, defaults to dashboard.
    Implements strict validation to prevent open redirect attacks.
    """
    from urllib.parse import unquote

    next_url = request.query_params.get("next")
    if not next_url:
        return "/"

    # Must start with single forward slash (relative path)
    if not next_url.startswith("/"):
        return "/"

    # Block protocol-relative URLs (//evil.com)
    if next_url.startswith("//"):
        return "/"

    # Block backslash variants (/\evil.com - some browsers interpret as //)
    if next_url.startswith("/\\"):
        return "/"

    # Block null bytes and newlines (header injection)
    if "\x00" in next_url or "\n" in next_url or "\r" in next_url:
        return "/"

    # URL decode and re-check for bypass attempts
    decoded = unquote(next_url)
    if decoded.startswith("//") or decoded.startswith("/\\"):
        return "/"

    # Block URLs with embedded credentials or authority
    if "@" in next_url or ":" in next_url.split("/")[1] if len(next_url.split("/")) > 1 else False:
        return "/"

    return next_url


def build_login_url(request: Request) -> str:
    """Build login URL with return path.

    Used when redirecting unauthenticated users to login.
    """
    current_path = request.url.path
    if request.url.query:
        current_path += f"?{request.url.query}"

    # URL encode the path
    from urllib.parse import quote
    return f"/login?next={quote(current_path, safe='')}"


def is_htmx_request(request: Request) -> bool:
    """Check if the request is from HTMX."""
    return request.headers.get("HX-Request") == "true"


def is_boosted_request(request: Request) -> bool:
    """Check if the request is a boosted navigation (hx-boost)."""
    return request.headers.get("HX-Boosted") == "true"


# ============================================================================
# HTMX Response Helpers
# ============================================================================

def htmx_redirect(response: Response, url: str) -> None:
    """Set HX-Redirect header for client-side navigation."""
    response.headers["HX-Redirect"] = url


def htmx_refresh(response: Response) -> None:
    """Trigger a full page refresh."""
    response.headers["HX-Refresh"] = "true"


def htmx_trigger(response: Response, event: str, data: Optional[Dict[str, Any]] = None) -> None:
    """Trigger a client-side event.

    Args:
        response: FastAPI response object
        event: Event name to trigger
        data: Optional data to pass with the event
    """
    if data:
        trigger_value = json.dumps({event: data})
    else:
        trigger_value = event
    response.headers["HX-Trigger"] = trigger_value


def htmx_toast(response: Response, message: str, toast_type: str = "info") -> None:
    """Trigger a toast notification on the client.

    Uses custom headers that the frontend JavaScript reads after HTMX swaps.

    Args:
        response: FastAPI response object
        message: Message to display
        toast_type: Toast type (success, error, warning, info)
    """
    from urllib.parse import quote
    response.headers["HX-Toast"] = quote(message)
    response.headers["HX-Toast-Type"] = toast_type


def htmx_close_modal(response: Response) -> None:
    """Trigger modal close on the client."""
    htmx_trigger(response, "closeModal", {})
