"""
HR Routes Aggregation.

Combines all HR sub-module routers into a single router.
Also provides redirects to expenses and performance modules.
"""
from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from .dashboard import router as dashboard_router
from .employees import router as employees_router
from .departments import router as departments_router
from .designations import router as designations_router
from .leave import router as leave_router
from .attendance import router as attendance_router
from .payroll import router as payroll_router
from .training import router as training_router
from .appraisal import router as appraisal_router
from .recruitment import router as recruitment_router
from .lifecycle import router as lifecycle_router
from .holidays import router as holidays_router

router = APIRouter(prefix="/hr", tags=["hr"])

# Dashboard first (matches /hr path)
router.include_router(dashboard_router)
router.include_router(employees_router)
router.include_router(departments_router)
router.include_router(designations_router)
router.include_router(leave_router)
router.include_router(attendance_router)
router.include_router(payroll_router)
router.include_router(training_router)
router.include_router(appraisal_router)
router.include_router(recruitment_router)
router.include_router(lifecycle_router)
router.include_router(holidays_router)


# Redirects for consolidated modules
@router.get("/expenses")
async def hr_expenses_redirect():
    """Redirect to expenses module."""
    return RedirectResponse(url="/expenses", status_code=302)


@router.get("/expenses/{path:path}")
async def hr_expenses_path_redirect(path: str):
    """Redirect expense sub-paths."""
    return RedirectResponse(url=f"/expenses/{path}", status_code=302)


@router.get("/performance")
async def hr_performance_redirect():
    """Redirect to performance module."""
    return RedirectResponse(url="/performance", status_code=302)


@router.get("/performance/{path:path}")
async def hr_performance_path_redirect(path: str):
    """Redirect performance sub-paths."""
    return RedirectResponse(url=f"/performance/{path}", status_code=302)
