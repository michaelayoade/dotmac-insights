"""
Shared dependencies for subscriber routes.

This module contains common imports, helpers, and permission dependencies
used across all subscriber route modules.
"""
from __future__ import annotations

from typing import Optional, Any, List, Dict
from datetime import datetime, timedelta, date
from decimal import Decimal

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile, Path
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import joinedload, Session

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.core.security import is_htmx_request, htmx_toast, set_flash

# =============================================================================
# MODELS
# =============================================================================

from app.models.party import Party, PartyRole, PartyStatus, CustomerAccount
from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionType
from app.models.payment_subscription import PaymentSubscription, PaymentSubscriptionStatus
from app.models.invoice import Invoice
from app.models.ticket import Ticket

# =============================================================================
# SERVICES
# =============================================================================

from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.types import PaginationParams
from app.services.subscribers import (
    SubscriberService,
    SubscriberFilters,
    SubscriberCreateData,
    SubscriberUpdateData,
    Subscriber360Data,
    SubscriberStats,
)

# =============================================================================
# PERMISSION DEPENDENCIES
# =============================================================================

RequireSubscribersRead = Depends(require_scope("crm:read"))
RequireSubscribersWrite = Depends(require_scope("crm:write"))

# =============================================================================
# TEMPLATE ENVIRONMENT
# =============================================================================

templates = get_template_env()

# =============================================================================
# FORM HELPERS
# =============================================================================


def _form_str(form: Any, key: str, default: str = "") -> str:
    """Extract string from form data."""
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


def _form_int(form: Any, key: str, default: int = 0) -> int:
    """Extract integer from form data."""
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    try:
        return int(value) if value not in ("", None) else default
    except (TypeError, ValueError):
        return default


def _form_decimal(form: Any, key: str) -> Optional[Decimal]:
    """Extract decimal from form data."""
    value = form.get(key)
    if isinstance(value, UploadFile):
        return None
    if value in ("", None):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _form_bool(form: Any, key: str) -> bool:
    """Extract boolean from form data."""
    value = form.get(key)
    if isinstance(value, UploadFile):
        return False
    return value in ("true", "on", "1", True)


def _form_date(form: Any, key: str) -> Optional[date]:
    """Extract date from form data."""
    value = form.get(key)
    if isinstance(value, UploadFile):
        return None
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def _form_list(form: Any, key: str) -> List[str]:
    """Extract list from form data (multiple values with same key)."""
    values = form.getlist(key) if hasattr(form, 'getlist') else []
    return [str(v).strip() for v in values if v]


# =============================================================================
# OPTION HELPERS
# =============================================================================


def get_status_options() -> List[Dict[str, str]]:
    """Get status options for dropdown."""
    return [
        {"value": "active", "label": "Active"},
        {"value": "inactive", "label": "Inactive"},
        {"value": "blocked", "label": "Blocked"},
    ]


def get_party_type_options() -> List[Dict[str, str]]:
    """Get party type options for dropdown."""
    return [
        {"value": "person", "label": "Person"},
        {"value": "organization", "label": "Organization"},
    ]


def get_account_tier_options() -> List[Dict[str, str]]:
    """Get account tier options for dropdown."""
    return [
        {"value": "standard", "label": "Standard"},
        {"value": "premium", "label": "Premium"},
        {"value": "enterprise", "label": "Enterprise"},
    ]


def get_billing_cycle_options() -> List[Dict[str, str]]:
    """Get billing cycle options for dropdown."""
    return [
        {"value": "monthly", "label": "Monthly"},
        {"value": "quarterly", "label": "Quarterly"},
        {"value": "yearly", "label": "Yearly"},
    ]


# =============================================================================
# STATUS HELPERS
# =============================================================================


def get_status_style(status: str) -> Dict[str, str]:
    """Get status badge styling."""
    styles = {
        "active": {"bg": "bg-green-100", "text": "text-green-800", "dot": "bg-green-500"},
        "inactive": {"bg": "bg-gray-100", "text": "text-gray-800", "dot": "bg-gray-500"},
        "blocked": {"bg": "bg-red-100", "text": "text-red-800", "dot": "bg-red-500"},
    }
    return styles.get(status, {"bg": "bg-gray-100", "text": "text-gray-800", "dot": "bg-gray-500"})


def get_subscription_status_style(status: str) -> Dict[str, str]:
    """Get subscription status badge styling."""
    styles = {
        "active": {"bg": "bg-green-100", "text": "text-green-800"},
        "pending": {"bg": "bg-yellow-100", "text": "text-yellow-800"},
        "suspended": {"bg": "bg-orange-100", "text": "text-orange-800"},
        "cancelled": {"bg": "bg-red-100", "text": "text-red-800"},
        "expired": {"bg": "bg-gray-100", "text": "text-gray-800"},
    }
    return styles.get(status, {"bg": "bg-gray-100", "text": "text-gray-800"})


# =============================================================================
# FORMATTING HELPERS
# =============================================================================


def format_currency(amount: Optional[Decimal], currency: str = "NGN") -> str:
    """Format amount as currency."""
    if amount is None:
        return "-"
    return f"{currency} {amount:,.2f}"


def format_phone(phone: Optional[str]) -> str:
    """Format phone number for display."""
    if not phone:
        return "-"
    return phone


def format_date(dt: Optional[datetime]) -> str:
    """Format datetime for display."""
    if not dt:
        return "-"
    return dt.strftime("%b %d, %Y")


def format_datetime(dt: Optional[datetime]) -> str:
    """Format datetime with time for display."""
    if not dt:
        return "-"
    return dt.strftime("%b %d, %Y %H:%M")
