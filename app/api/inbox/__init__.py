"""Inbox API - Unified omnichannel inbox management."""

from fastapi import APIRouter

from .conversations import router as conversations_router
from .routing import router as routing_router
from .analytics import router as analytics_router
from .websocket import router as websocket_router
from .soft_validation import router as soft_validation_router

router = APIRouter(prefix="/inbox", tags=["inbox"])

router.include_router(conversations_router)
router.include_router(routing_router)
router.include_router(analytics_router)
router.include_router(websocket_router)
router.include_router(soft_validation_router, tags=["Inbox - Validation"])
