"""
Shared dependencies for support routes.

This module contains common imports, helpers, and permission dependencies
used across all support route modules.
"""
from __future__ import annotations

from typing import Optional, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import joinedload

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_any_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.core.security import is_htmx_request, htmx_toast, set_flash

# Models - Tickets
from app.models.unified_ticket import (
    UnifiedTicket,
    TicketStatus,
    TicketPriority,
    TicketType,
    TicketChannel,
    TicketSource,
)

# Models - Teams (Agent model deprecated - use Party with support_agent role)
from app.models.agent import Team, TeamMember
from app.models.party import PartyRole

# Models - Support Config
from app.models.support_canned import CannedResponse, CannedResponseScope
from app.models.support_sla import SLAPolicy, SLATarget, BusinessCalendar

# Models - Related
from app.models.employee import Employee, EmploymentStatus
from app.models.party import Party

# Permission dependencies
RequireSupportRead = Depends(require_any_scope("support:read", "tickets:read"))
RequireSupportWrite = Depends(require_any_scope("support:write", "tickets:write"))

# Template environment
templates = get_template_env()


# =============================================================================
# COMMON HELPER FUNCTIONS
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


# =============================================================================
# ENUM OPTIONS FOR DROPDOWNS
# =============================================================================

def get_status_options():
    """Get status options for select dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in TicketStatus
    ]


def get_priority_options():
    """Get priority options for select dropdown."""
    return [
        {"value": p.value, "label": p.value.title()}
        for p in TicketPriority
    ]


def get_type_options():
    """Get type options for select dropdown."""
    return [
        {"value": t.value, "label": t.value.replace("_", " ").title()}
        for t in TicketType
    ]


def get_channel_options():
    """Get channel options for select dropdown."""
    return [
        {"value": c.value, "label": c.value.replace("_", " ").title()}
        for c in TicketChannel
    ]


def get_source_options():
    """Get source options for select dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in TicketSource
    ]


# =============================================================================
# DYNAMIC OPTIONS FROM DATABASE (using services)
# =============================================================================

def get_agent_options(db):
    """Get active support agents for assignment dropdown.

    After Agent → Party unification, agents are Party records
    with PartyRole(role="support_agent").
    """
    from app.services.support import AgentService
    service = AgentService(db)
    from app.services.support.types import AgentFilters
    agents = service.list_agents(filters=AgentFilters(is_active=True))
    return [
        {"value": str(a.id), "label": a.display_name or f"Agent {a.id}"}
        for a in agents
    ]


def get_team_options(db):
    """Get active teams for assignment dropdown."""
    from app.services.support import AgentService
    service = AgentService(db)
    teams = service.list_teams(active_only=True)
    return [
        {"value": str(t.id), "label": t.name}
        for t in teams
    ]


def get_sla_policy_options(db):
    """Get active SLA policies for dropdown."""
    from app.services.support import SLAService
    service = SLAService(db)
    policies = service.list_policies(active_only=True)
    return [
        {"value": str(p.id), "label": p.name}
        for p in policies
    ]


def get_canned_response_options(db):
    """Get canned responses for quick reply dropdown."""
    from app.services.support import CannedResponseService
    service = CannedResponseService(db)
    responses = service.list(active_only=True)
    return [
        {"value": str(r.id), "label": r.name, "content": r.content}
        for r in responses
    ]


# =============================================================================
# ENTITY LISTS FOR FORMS (returns full model objects)
# =============================================================================

def get_agents(db):
    """Get list of active employees who can be assigned tickets."""
    from app.services.hr import EmployeeService
    from app.models.employee import EmploymentStatus
    service = EmployeeService(db)
    from app.services.hr.employee_types import EmployeeFilters
    result = service.list_employees(filters=EmployeeFilters(status=EmploymentStatus.ACTIVE))
    return result.items


def get_teams(db):
    """Get list of support teams for assignment."""
    from app.services.support import AgentService
    service = AgentService(db)
    return service.list_teams(active_only=True)


# =============================================================================
# PARTY RESOLUTION FOR TICKETS
# =============================================================================

def resolve_party_for_ticket(db, email: str, phone: str = None, name: str = None) -> Optional[Party]:
    """Resolve or create a Party record for ticket contact."""
    if not email and not phone:
        return None

    from app.services.identity import PartyService
    from app.services.identity.party_types import PartyCreateData

    service = PartyService(db)
    party = None
    if email:
        party = service.get_party_by_email(email)
    if not party and phone:
        party = service.get_party_by_phone(phone)

    if party:
        return party

    create_data = PartyCreateData(
        type="person",
        status="active",
        name=name or email or phone,
        emails=[{"address": email, "is_primary": True}] if email else [],
        phones=[{"number": phone, "is_primary": True}] if phone else [],
    )
    return service.create_party(create_data)
