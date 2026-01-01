"""
HR Module Router

Combines all HR sub-modules into a single router.
"""

from fastapi import APIRouter

from .leave import router as leave_router
from .attendance import router as attendance_router
from .recruitment import router as recruitment_router
from .payroll import router as payroll_router
from .training import router as training_router
from .appraisal import router as appraisal_router
from .lifecycle import router as lifecycle_router
from .analytics import router as analytics_router
from .masters import router as masters_router

router = APIRouter()

# Include all sub-routers
router.include_router(leave_router, tags=["HR - Leave Management"])
router.include_router(attendance_router, tags=["HR - Attendance"])
router.include_router(recruitment_router, tags=["HR - Recruitment"])
router.include_router(payroll_router, tags=["HR - Payroll"])
router.include_router(training_router, tags=["HR - Training"])
router.include_router(appraisal_router, tags=["HR - Appraisal"])
router.include_router(lifecycle_router, tags=["HR - Lifecycle"])
router.include_router(analytics_router, prefix="/analytics", tags=["HR - Analytics"])
router.include_router(masters_router, tags=["HR - Masters"])
