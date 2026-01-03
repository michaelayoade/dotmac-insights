"""
Leave Management Router

Aggregates all leave sub-modules:
- Leave Types
- Leave Allocations
- Leave Applications
- Holiday Lists
- Leave Policies
"""

from fastapi import APIRouter

from .leave_leave_types import router as leave_types_router
from .leave_leave_allocations import router as leave_allocations_router
from .leave_leave_applications import router as leave_applications_router
from .leave_holiday_lists import router as holiday_lists_router
from .leave_leave_policies import router as leave_policies_router

router = APIRouter()

# Include all leave sub-routers
router.include_router(leave_types_router)
router.include_router(leave_allocations_router)
router.include_router(leave_applications_router)
router.include_router(holiday_lists_router)
router.include_router(leave_policies_router)
