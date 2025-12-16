"""Inbox API - Unified omnichannel inbox management."""

from fastapi import APIRouter

from .conversations import router as conversations_router
from .routing import router as routing_router
from .contacts import router as contacts_router
from .analytics import router as analytics_router

router = APIRouter(prefix="/inbox", tags=["inbox"])

router.include_router(conversations_router)
router.include_router(routing_router)
router.include_router(contacts_router)
router.include_router(analytics_router)
