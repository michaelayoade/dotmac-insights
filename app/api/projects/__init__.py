"""
Projects API Package

Provides all project management endpoints:
- Dashboard, CRUD, Tasks, Milestones
- Gantt charts, Analytics, Comments
- Attachments, Workflows, Templates
"""

from fastapi import APIRouter

from app.api.projects.schemas import router as schemas_router
from app.api.projects.dashboard import router as dashboard_router
from app.api.projects.projects import router as projects_router
from app.api.projects.crud import router as crud_router
from app.api.projects.tasks import router as tasks_router
from app.api.projects.milestones import router as milestones_router
from app.api.projects.gantt import router as gantt_router
from app.api.projects.analytics import router as analytics_router
from app.api.projects.comments import router as comments_router
from app.api.projects.activity import router as activity_router
from app.api.projects.attachments import router as attachments_router
from app.api.projects.workflows import router as workflows_router
from app.api.projects.history import router as history_router
from app.api.projects.templates import router as templates_router

router = APIRouter()

router.include_router(schemas_router)
router.include_router(dashboard_router)
router.include_router(projects_router)
router.include_router(crud_router)
router.include_router(tasks_router)
router.include_router(milestones_router)
router.include_router(gantt_router)
router.include_router(analytics_router)
router.include_router(comments_router)
router.include_router(activity_router)
router.include_router(attachments_router)
router.include_router(workflows_router)
router.include_router(history_router)
router.include_router(templates_router)

__all__ = ["router"]
