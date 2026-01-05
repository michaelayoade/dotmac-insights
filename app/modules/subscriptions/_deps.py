"""
Shared dependencies for subscription routes.

This module contains common imports, helpers, and permission dependencies
used across all subscription route modules.
"""
from __future__ import annotations

from dataclasses import dataclass
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

# Subscription models
from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionType

# Tariff models
from app.models.tariff import Tariff, TariffType

# Payment subscription models
from app.models.payment_subscription import PaymentSubscription, PaymentSubscriptionStatus

# Party/Customer models
from app.models.party import Party, PartyRole, PartyStatus

# Network models
from app.models.router import Router
from app.models.pop import Pop

# Usage tracking
from app.models.customer_usage import CustomerUsage

# Provisioning
from app.models.provisioning_log import ProvisioningLog, ProvisioningAction, ProvisioningStatus

# =============================================================================
# SERVICES
# =============================================================================

from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.types import PaginationParams
from app.services.subscriptions import (
    SubscriptionService,
    SubscriptionFilters,
    SubscriptionCreateData,
    SubscriptionUpdateData,
    NetworkAssignmentData,
    ProvisioningConfigData,
)
from app.services.subscriptions import (
    TariffService,
)
from app.services.subscriptions import (
    PaymentSubscriptionService,
    PaymentSubscriptionFilters,
)
from app.services.subscriptions import (
    UsageService,
    UsageFilters,
)
from app.services.subscriptions import (
    SessionService,
    SessionFilters,
)
from app.services.subscriptions import (
    ProvisioningService,
    ProvisioningLogFilters,
)
from app.services.subscriptions import (
    BillingService,
)
from app.services.subscriptions import (
    ServiceTypeConfigService,
)
from app.services.subscriptions import (
    UpgradeResult,
    DowngradeResult,
    RenewalResult,
)
from app.services.identity.parties import PartyService

# Access method configuration
from app.integrations.mikrotik.access_methods import ACCESS_METHODS, get_access_method_options

# =============================================================================
# PERMISSION DEPENDENCIES
# =============================================================================

RequireSubscriptionsRead = Depends(require_scope("subscriptions:read"))
RequireSubscriptionsWrite = Depends(require_scope("subscriptions:write"))
RequireNetworkRead = Depends(require_scope("network:read"))
RequireNetworkWrite = Depends(require_scope("network:write"))
RequireBillingRead = Depends(require_scope("billing:read"))
RequireBillingWrite = Depends(require_scope("billing:write"))

# =============================================================================
# TEMPLATE ENVIRONMENT
# =============================================================================

templates = get_template_env()

# =============================================================================
# BREADCRUMBS / CONTEXT HELPERS
# =============================================================================


@dataclass(frozen=True)
class BreadcrumbItem:
    label: str
    url: Optional[str] = None


def get_context(
    request: Request,
    title: str,
    breadcrumbs: Optional[List[BreadcrumbItem]] = None,
    user: Optional[SessionUser] = None,
    csrf_token: str = "",
    response: Optional[Response] = None,
) -> Dict[str, Any]:
    """Build template context for subscription bundle pages."""
    response = response or Response()
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = title
    if breadcrumbs:
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": item.label, "href": item.url} for item in breadcrumbs
        ])
    else:
        context["breadcrumbs"] = []
    return context


# =============================================================================
# FORM HELPERS
# =============================================================================

def _form_str(form: Any, key: str, default: str = "") -> str:
    """Extract string value from form data."""
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


def _form_int(form: Any, key: str, default: Optional[int] = None) -> Optional[int]:
    """Extract integer value from form data."""
    value = _form_str(form, key, "")
    if not value:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _form_decimal(form: Any, key: str, default: Optional[Decimal] = None) -> Optional[Decimal]:
    """Extract decimal value from form data."""
    value = _form_str(form, key, "")
    if not value:
        return default
    try:
        return Decimal(value)
    except Exception:
        return default


def _form_bool(form: Any, key: str, default: bool = False) -> bool:
    """Extract boolean value from form data."""
    value = _form_str(form, key, "").lower()
    if value in ("true", "1", "yes", "on"):
        return True
    if value in ("false", "0", "no", "off", ""):
        return False
    return default


def _form_date(form: Any, key: str, default: Optional[date] = None) -> Optional[date]:
    """Extract date value from form data."""
    value = _form_str(form, key, "")
    if not value:
        return default
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return default


# =============================================================================
# ENUM OPTIONS FOR DROPDOWNS
# =============================================================================

def get_status_options() -> List[Dict[str, str]]:
    """Get subscription status options for dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in SubscriptionStatus
    ]


def get_service_type_options() -> List[Dict[str, str]]:
    """Get service type options for dropdown."""
    return [
        {"value": t.value, "label": t.value.replace("_", " ").title()}
        for t in SubscriptionType
    ]


def get_billing_cycle_options() -> List[Dict[str, str]]:
    """Get billing cycle options for dropdown."""
    return [
        {"value": "daily", "label": "Daily"},
        {"value": "weekly", "label": "Weekly"},
        {"value": "monthly", "label": "Monthly"},
        {"value": "quarterly", "label": "Quarterly"},
        {"value": "yearly", "label": "Yearly"},
    ]


def get_tariff_type_options() -> List[Dict[str, str]]:
    """Get tariff type options for dropdown."""
    return [
        {"value": t.value, "label": t.value.replace("_", " ").title()}
        for t in TariffType
    ]


def get_payment_status_options() -> List[Dict[str, str]]:
    """Get payment subscription status options for dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in PaymentSubscriptionStatus
    ]


def get_provisioning_status_options() -> List[Dict[str, str]]:
    """Get provisioning status options for dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in ProvisioningStatus
    ]


def get_provisioning_action_options() -> List[Dict[str, str]]:
    """Get provisioning action options for dropdown."""
    return [
        {"value": a.value, "label": a.value.replace("_", " ").title()}
        for a in ProvisioningAction
    ]


# =============================================================================
# STATUS STYLES FOR BADGES
# =============================================================================

STATUS_STYLES = {
    # Subscription statuses
    "active": {"bg": "bg-green-100", "text": "text-green-800", "dot": "bg-green-500"},
    "pending": {"bg": "bg-yellow-100", "text": "text-yellow-800", "dot": "bg-yellow-500"},
    "suspended": {"bg": "bg-orange-100", "text": "text-orange-800", "dot": "bg-orange-500"},
    "cancelled": {"bg": "bg-red-100", "text": "text-red-800", "dot": "bg-red-500"},
    # Payment subscription statuses
    "paused": {"bg": "bg-gray-100", "text": "text-gray-800", "dot": "bg-gray-500"},
    "past_due": {"bg": "bg-red-100", "text": "text-red-800", "dot": "bg-red-500"},
    "completed": {"bg": "bg-blue-100", "text": "text-blue-800", "dot": "bg-blue-500"},
    "expired": {"bg": "bg-gray-100", "text": "text-gray-600", "dot": "bg-gray-400"},
    # Provisioning statuses
    "success": {"bg": "bg-green-100", "text": "text-green-800", "dot": "bg-green-500"},
    "failed": {"bg": "bg-red-100", "text": "text-red-800", "dot": "bg-red-500"},
    "retrying": {"bg": "bg-yellow-100", "text": "text-yellow-800", "dot": "bg-yellow-500"},
}


def get_status_style(status: str) -> Dict[str, str]:
    """Get badge style for a status value."""
    return STATUS_STYLES.get(status.lower(), STATUS_STYLES["pending"])


# =============================================================================
# DYNAMIC OPTIONS FROM DATABASE
# =============================================================================

def get_router_options(db: Session) -> List[Dict[str, str]]:
    """Get active routers for dropdown."""
    from app.services.subscriptions.web_helpers import SubscriptionWebHelpers
    return SubscriptionWebHelpers(db).get_router_options()


def get_pop_options(db: Session) -> List[Dict[str, str]]:
    """Get POPs for dropdown."""
    from app.services.subscriptions.web_helpers import SubscriptionWebHelpers
    return SubscriptionWebHelpers(db).get_pop_options()


def get_tariff_options(db: Session, tariff_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get active tariffs for dropdown."""
    from app.services.subscriptions.web_helpers import SubscriptionWebHelpers
    return SubscriptionWebHelpers(db).get_tariff_options(tariff_type)


def get_party_options(db: Session, search: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """Get parties for dropdown with optional search."""
    from app.services.subscriptions.web_helpers import SubscriptionWebHelpers
    return SubscriptionWebHelpers(db).get_party_options(search=search, limit=limit)


# =============================================================================
# FORMATTING HELPERS
# =============================================================================

def format_speed(speed: Optional[int]) -> str:
    """Format speed in Mbps or Gbps."""
    if not speed:
        return "-"
    if speed >= 1000:
        return f"{speed / 1000:.1f} Gbps"
    return f"{speed} Mbps"


def format_bytes(bytes_value: Optional[int]) -> str:
    """Format bytes to human-readable string."""
    if not bytes_value:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_index = 0
    size = float(bytes_value)

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.2f} {units[unit_index]}"


def format_duration(seconds: Optional[int]) -> str:
    """Format duration in seconds to human-readable string."""
    if not seconds:
        return "0s"

    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)


def format_currency(amount: Optional[Decimal], currency: str = "NGN") -> str:
    """Format currency amount."""
    if amount is None:
        return "-"
    return f"{currency} {amount:,.2f}"


# =============================================================================
# STATS COMPUTATION
# =============================================================================

def compute_subscription_stats(db: Session) -> Dict[str, Any]:
    """Compute subscription stats for dashboard cards."""
    from app.services.subscriptions.web_helpers import SubscriptionWebHelpers
    return SubscriptionWebHelpers(db).compute_subscription_stats()


# =============================================================================
# STATE TRANSITION HELPERS
# =============================================================================

VALID_TRANSITIONS = {
    SubscriptionStatus.PENDING: [SubscriptionStatus.ACTIVE, SubscriptionStatus.CANCELLED],
    SubscriptionStatus.ACTIVE: [SubscriptionStatus.SUSPENDED, SubscriptionStatus.CANCELLED],
    SubscriptionStatus.SUSPENDED: [SubscriptionStatus.ACTIVE, SubscriptionStatus.CANCELLED],
    SubscriptionStatus.CANCELLED: [],  # Terminal state
}


def get_available_transitions(current_status: SubscriptionStatus) -> List[Dict[str, str]]:
    """Get available status transitions for a subscription."""
    valid_statuses = VALID_TRANSITIONS.get(current_status, [])
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in valid_statuses
    ]


def can_transition(from_status: SubscriptionStatus, to_status: SubscriptionStatus) -> bool:
    """Check if a status transition is valid."""
    valid_statuses = VALID_TRANSITIONS.get(from_status, [])
    return to_status in valid_statuses
