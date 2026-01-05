"""
Payroll Management Router

Aggregates all payroll sub-modules:
- Salary Components
- Salary Structures
- Salary Structure Assignments
- Payroll Entries
- Salary Slips
"""

from fastapi import APIRouter

from .payroll_salary_components import router as salary_components_router
from .payroll_salary_structures import router as salary_structures_router
from .payroll_salary_assignments import router as salary_assignments_router
from .payroll_payroll_entries import router as payroll_entries_router
from .payroll_salary_slips import router as salary_slips_router

router = APIRouter()

# Include all payroll sub-routers
router.include_router(salary_components_router)
router.include_router(salary_structures_router)
router.include_router(salary_assignments_router)
router.include_router(payroll_entries_router)
router.include_router(salary_slips_router)
