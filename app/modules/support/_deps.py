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

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
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

# Models - Agents and Teams
from app.models.agent import Agent, Team, TeamMember

# Models - Support Config
from app.models.support_canned import CannedResponse, CannedResponseScope
from app.models.support_sla import SLAPolicy, SLATarget, BusinessCalendar

# Models - Related
from app.models.employee import Employee, EmploymentStatus
from app.models.contact import Contact

# Permission dependencies
RequireSupportRead = Depends(require_scope("support:read"))
RequireSupportWrite = Depends(require_scope("support:write"))

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
# DYNAMIC OPTIONS FROM DATABASE
# =============================================================================

def get_agent_options(db):
    """Get active agents for assignment dropdown."""
    agents = db.query(Agent).filter(
        Agent.is_active == True
    ).order_by(Agent.display_name).all()
    return [
        {"value": str(a.id), "label": a.display_name or a.email or f"Agent {a.id}"}
        for a in agents
    ]


def get_team_options(db):
    """Get active teams for assignment dropdown."""
    teams = db.query(Team).filter(
        Team.is_active == True
    ).order_by(Team.name).all()
    return [
        {"value": str(t.id), "label": t.name}
        for t in teams
    ]


def get_sla_policy_options(db):
    """Get active SLA policies for dropdown."""
    policies = db.query(SLAPolicy).filter(
        SLAPolicy.is_active == True
    ).order_by(SLAPolicy.name).all()
    return [
        {"value": str(p.id), "label": p.name}
        for p in policies
    ]


def get_canned_response_options(db):
    """Get canned responses for quick reply dropdown."""
    responses = db.query(CannedResponse).filter(
        CannedResponse.is_active == True
    ).order_by(CannedResponse.title).all()
    return [
        {"value": str(r.id), "label": r.title, "content": r.content}
        for r in responses
    ]


# =============================================================================
# ENTITY LISTS FOR FORMS (returns full model objects)
# =============================================================================

def get_agents(db):
    """Get list of active employees who can be assigned tickets."""
    return db.query(Employee).filter(
        Employee.is_deleted == False,
        Employee.status == EmploymentStatus.ACTIVE
    ).order_by(Employee.name).all()


def get_teams(db):
    """Get list of support teams for assignment."""
    return db.query(Team).filter(
        Team.is_active == True
    ).order_by(Team.name).all()
