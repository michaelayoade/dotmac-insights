"""
Field Service API Router

Provides endpoints for:
- Service orders management
- Teams and technicians
- Scheduling and dispatch
- Customer notifications
- Real-time WebSocket updates
"""
from fastapi import APIRouter

from app.api.field_service import orders, teams, scheduling, analytics, websocket

router = APIRouter(prefix="/field-service", tags=["field-service"])

# Include sub-routers
router.include_router(orders.router)
router.include_router(teams.router)
router.include_router(scheduling.router)
router.include_router(analytics.router)
router.include_router(websocket.router)
