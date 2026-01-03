"""
Recruitment Management Router

Aggregates all recruitment sub-modules:
- Job Openings
- Job Applicants
- Job Offers
- Interviews
"""

from fastapi import APIRouter

from .recruitment_job_openings import router as job_openings_router
from .recruitment_job_applicants import router as job_applicants_router
from .recruitment_job_offers import router as job_offers_router
from .recruitment_interviews import router as interviews_router

router = APIRouter()

# Include all recruitment sub-routers
router.include_router(job_openings_router)
router.include_router(job_applicants_router)
router.include_router(job_offers_router)
router.include_router(interviews_router)
