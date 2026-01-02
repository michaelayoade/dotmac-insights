"""
Subscription Configuration API

Service type configuration and billing settings endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional
from decimal import Decimal

from app.database import get_db
from app.auth import Require, get_current_principal, Principal
from app.services.subscriptions import (
    ServiceTypeConfigService,
    BillingConfigService,
)

router = APIRouter()


# ============================================================================
# Service Type Configuration
# ============================================================================

@router.get("/service-types", dependencies=[Depends(Require("subscriptions:read"))])
async def list_service_types(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    List all service type configurations.
    """
    service = ServiceTypeConfigService(db, principal)
    types = service.list_service_types()

    return {
        "items": [
            {
                "type_code": t.type_code,
                "label": t.label,
                "description": t.description,
                "icon": t.icon,
                "default_billing_cycle": t.default_billing_cycle,
                "requires_provisioning": t.requires_provisioning,
                "requires_network_assignment": t.requires_network_assignment,
                "is_active": t.is_active,
            }
            for t in types
        ],
        "total": len(types),
    }


@router.get("/service-types/{type_code}", dependencies=[Depends(Require("subscriptions:read"))])
async def get_service_type(
    type_code: str = Path(..., description="Service type code"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get full service type configuration including SLA, fees, and lifecycle settings.
    """
    service = ServiceTypeConfigService(db, principal)

    config = service.get_service_type(type_code)
    if not config:
        raise HTTPException(status_code=404, detail=f"Service type '{type_code}' not found")

    return {
        "type_code": config.type_code,
        "label": config.label,
        "description": config.description,
        "icon": config.icon,
        "default_billing_cycle": config.default_billing_cycle,
        "requires_provisioning": config.requires_provisioning,
        "requires_network_assignment": config.requires_network_assignment,
        "is_active": config.is_active,
        "sla_settings": {
            "uptime_sla_percent": config.sla_settings.uptime_sla_percent,
            "support_response_hours": config.sla_settings.support_response_hours,
            "issue_resolution_hours": config.sla_settings.issue_resolution_hours,
        } if config.sla_settings else None,
        "grace_period_days": config.grace_period_days,
        "suspension_grace_days": config.suspension_grace_days,
        "fees": {
            "installation_fee": float(config.fees.installation_fee) if config.fees else 0,
            "activation_fee": float(config.fees.activation_fee) if config.fees else 0,
            "reconnection_fee": float(config.fees.reconnection_fee) if config.fees else 0,
            "early_termination_fee": float(config.fees.early_termination_fee) if config.fees else 0,
        } if config.fees else None,
        "lifecycle_settings": config.lifecycle_settings,
        "plan_change_settings": config.plan_change_settings,
        "contract_settings": config.contract_settings,
    }


@router.get("/service-types/{type_code}/fees", dependencies=[Depends(Require("subscriptions:read"))])
async def get_service_type_fees(
    type_code: str = Path(..., description="Service type code"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get fee structure for a service type.
    """
    service = ServiceTypeConfigService(db, principal)

    fees = service.get_fees(type_code)
    if not fees:
        raise HTTPException(status_code=404, detail=f"Service type '{type_code}' not found")

    return {
        "type_code": type_code,
        "installation_fee": float(fees.installation_fee),
        "activation_fee": float(fees.activation_fee),
        "reconnection_fee": float(fees.reconnection_fee),
        "early_termination_fee": float(fees.early_termination_fee),
        "currency": fees.currency,
    }


@router.get("/service-types/{type_code}/sla", dependencies=[Depends(Require("subscriptions:read"))])
async def get_service_type_sla(
    type_code: str = Path(..., description="Service type code"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get SLA settings for a service type.
    """
    service = ServiceTypeConfigService(db, principal)

    sla = service.get_sla_settings(type_code)
    if not sla:
        raise HTTPException(status_code=404, detail=f"Service type '{type_code}' not found")

    return {
        "type_code": type_code,
        "uptime_sla_percent": sla.uptime_sla_percent,
        "support_response_hours": sla.support_response_hours,
        "issue_resolution_hours": sla.issue_resolution_hours,
    }


# ============================================================================
# Billing Configuration
# ============================================================================

@router.get("/billing", dependencies=[Depends(Require("subscriptions:read"))])
async def get_billing_config(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get billing configuration settings.
    """
    service = BillingConfigService(db, principal)
    config = service.get_billing_config()

    return {
        "default_currency": config.default_currency,
        "billing_cycles": config.billing_cycles,
        "proration_method": config.proration_method,
        "invoice_due_days": config.invoice_due_days,
        "late_fee_percent": float(config.late_fee_percent),
        "late_fee_grace_days": config.late_fee_grace_days,
        "auto_suspend_days": config.auto_suspend_days,
        "auto_cancel_days": config.auto_cancel_days,
        "tax_settings": config.tax_settings,
    }


@router.get("/billing/cycles", dependencies=[Depends(Require("subscriptions:read"))])
async def get_billing_cycles(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get available billing cycles.
    """
    service = BillingConfigService(db, principal)
    cycles = service.get_billing_cycles()

    return {
        "cycles": [
            {
                "code": c.code,
                "label": c.label,
                "months": c.months,
                "discount_percent": float(c.discount_percent) if c.discount_percent else 0,
            }
            for c in cycles
        ]
    }


@router.get("/billing/proration-methods", dependencies=[Depends(Require("subscriptions:read"))])
async def get_proration_methods() -> Dict[str, Any]:
    """
    Get available proration methods.
    """
    return {
        "methods": [
            {"code": "daily", "label": "Daily Proration", "description": "Calculate based on exact days used"},
            {"code": "half_month", "label": "Half Month", "description": "Charge half if less than 15 days"},
            {"code": "full_month", "label": "Full Month", "description": "Always charge full month"},
            {"code": "none", "label": "No Proration", "description": "No proration on plan changes"},
        ]
    }


# ============================================================================
# Status Configuration
# ============================================================================

@router.get("/statuses", dependencies=[Depends(Require("subscriptions:read"))])
async def get_subscription_statuses() -> Dict[str, Any]:
    """
    Get subscription status definitions and transitions.
    """
    return {
        "statuses": [
            {
                "code": "pending",
                "label": "Pending",
                "description": "Awaiting activation",
                "color": "yellow",
                "allowed_transitions": ["active", "cancelled"],
            },
            {
                "code": "active",
                "label": "Active",
                "description": "Service is active",
                "color": "green",
                "allowed_transitions": ["suspended", "cancelled"],
            },
            {
                "code": "suspended",
                "label": "Suspended",
                "description": "Service temporarily suspended",
                "color": "orange",
                "allowed_transitions": ["active", "cancelled"],
            },
            {
                "code": "cancelled",
                "label": "Cancelled",
                "description": "Service terminated",
                "color": "red",
                "allowed_transitions": [],
            },
        ]
    }


@router.get("/provisioning-statuses", dependencies=[Depends(Require("subscriptions:read"))])
async def get_provisioning_statuses() -> Dict[str, Any]:
    """
    Get provisioning status definitions.
    """
    return {
        "statuses": [
            {"code": "pending", "label": "Pending", "color": "yellow"},
            {"code": "in_progress", "label": "In Progress", "color": "blue"},
            {"code": "completed", "label": "Completed", "color": "green"},
            {"code": "failed", "label": "Failed", "color": "red"},
            {"code": "rollback", "label": "Rolled Back", "color": "orange"},
        ]
    }


@router.get("/access-methods", dependencies=[Depends(Require("subscriptions:read"))])
async def get_access_methods() -> Dict[str, Any]:
    """
    Get available access methods for provisioning.
    """
    return {
        "methods": [
            {"code": "pppoe", "label": "PPPoE", "description": "Point-to-Point Protocol over Ethernet"},
            {"code": "static", "label": "Static IP", "description": "Static IP assignment"},
            {"code": "dhcp", "label": "DHCP", "description": "Dynamic IP via DHCP"},
            {"code": "hotspot", "label": "Hotspot", "description": "Captive portal authentication"},
        ]
    }
