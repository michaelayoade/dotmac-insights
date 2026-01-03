"""
Shared dependencies for subscription routes.

This module contains common imports, helpers, and permission dependencies
used across all subscription route modules.
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
    routers = db.query(Router).filter(
        Router.is_active == True
    ).order_by(Router.title).all()
    return [
        {"value": str(r.id), "label": f"{r.title} ({r.ip})"}
        for r in routers
    ]


def get_pop_options(db: Session) -> List[Dict[str, str]]:
    """Get POPs for dropdown."""
    pops = db.query(Pop).filter(
        Pop.is_active == True
    ).order_by(Pop.name).all()
    return [
        {"value": str(p.id), "label": p.name}
        for p in pops
    ]


def get_tariff_options(db: Session, tariff_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get active tariffs for dropdown."""
    query = db.query(Tariff).filter(Tariff.enabled == True)
    if tariff_type:
        query = query.filter(Tariff.tariff_type == TariffType(tariff_type))
    tariffs = query.order_by(Tariff.title).all()
    return [
        {
            "value": str(t.id),
            "label": f"{t.title} - {t.price:,.0f} {t.currency}",
            "price": float(t.price),
            "download_speed": t.download_speed,
            "upload_speed": t.upload_speed,
        }
        for t in tariffs
    ]


def get_party_options(db: Session, search: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """Get parties for dropdown with optional search."""
    query = db.query(Party).filter(Party.status == PartyStatus.ACTIVE)
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Party.name.ilike(search_term),
                Party.primary_email.ilike(search_term),
                Party.primary_phone.ilike(search_term),
            )
        )
    parties = query.order_by(Party.name).limit(limit).all()
    return [
        {
            "value": str(p.id),
            "label": p.name or p.primary_email or f"Party {p.id}",
            "email": p.primary_email,
            "phone": p.primary_phone,
            "type": p.type,
        }
        for p in parties
    ]


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
    active = db.query(func.count(Subscription.id)).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    ).scalar() or 0

    suspended = db.query(func.count(Subscription.id)).filter(
        Subscription.status == SubscriptionStatus.SUSPENDED
    ).scalar() or 0

    pending = db.query(func.count(Subscription.id)).filter(
        Subscription.status == SubscriptionStatus.PENDING
    ).scalar() or 0

    cancelled = db.query(func.count(Subscription.id)).filter(
        Subscription.status == SubscriptionStatus.CANCELLED
    ).scalar() or 0

    total = active + suspended + pending + cancelled

    # MRR calculation
    mrr_monthly = db.query(func.sum(Subscription.price)).filter(
        Subscription.status == SubscriptionStatus.ACTIVE,
        Subscription.billing_cycle == "monthly"
    ).scalar() or Decimal("0")

    mrr_quarterly = db.query(func.sum(Subscription.price / 3)).filter(
        Subscription.status == SubscriptionStatus.ACTIVE,
        Subscription.billing_cycle == "quarterly"
    ).scalar() or Decimal("0")

    mrr_yearly = db.query(func.sum(Subscription.price / 12)).filter(
        Subscription.status == SubscriptionStatus.ACTIVE,
        Subscription.billing_cycle == "yearly"
    ).scalar() or Decimal("0")

    total_mrr = float(mrr_monthly) + float(mrr_quarterly) + float(mrr_yearly)

    # New this month
    start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    new_this_month = db.query(func.count(Subscription.id)).filter(
        Subscription.created_at >= start_of_month
    ).scalar() or 0

    # Failed provisioning
    failed_provisioning = db.query(func.count(Subscription.id)).filter(
        Subscription.provisioning_error.isnot(None)
    ).scalar() or 0

    return {
        "active": active,
        "suspended": suspended,
        "pending": pending,
        "cancelled": cancelled,
        "total": total,
        "mrr": total_mrr,
        "new_this_month": new_this_month,
        "failed_provisioning": failed_provisioning,
    }


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
