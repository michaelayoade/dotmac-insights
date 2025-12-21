"""Support API Package - Router aggregation.

This package provides comprehensive helpdesk support functionality:
- Ticket management and CRUD
- Agent and team management
- Conversations (Chatwoot)
- Analytics and insights
- SLA policies and business calendars
- Automation rules
- Routing configuration
- Knowledge base
- Canned responses (macros)
"""
from fastapi import APIRouter

from .tickets import router as tickets_router
from .agents import router as agents_router
from .conversations import router as conversations_router
from .analytics import router as analytics_router
from .sla import router as sla_router
from .automation import router as automation_router
from .routing import router as routing_router
from .knowledge_base import router as kb_router
from .canned_responses import router as canned_router
from .csat import router as csat_router

router = APIRouter()

# Core ticket management
router.include_router(tickets_router, tags=["Support - Tickets"])

# Agent and team management
router.include_router(agents_router, tags=["Support - Agents"])

# Conversations
router.include_router(conversations_router, tags=["Support - Conversations"])

# Analytics and insights
router.include_router(analytics_router, tags=["Support - Analytics"])

# SLA policies and business calendars
router.include_router(sla_router, prefix="/sla", tags=["Support - SLA"])

# Automation rules
router.include_router(automation_router, prefix="/automation", tags=["Support - Automation"])

# Routing configuration
router.include_router(routing_router, prefix="/routing", tags=["Support - Routing"])

# Knowledge base (includes public endpoints)
router.include_router(kb_router, tags=["Support - Knowledge Base"])

# Canned responses / macros
router.include_router(canned_router, tags=["Support - Canned Responses"])

# CSAT surveys
router.include_router(csat_router, tags=["Support - CSAT"])

__all__ = ["router"]
