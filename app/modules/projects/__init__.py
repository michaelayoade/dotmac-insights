"""
Projects Module - Project Lifecycle Management.

Routes:
- /projects - Project list and dashboard
- /projects/tasks - Project task management
- /projects/milestones - Milestone tracking
- /projects/{id}/gantt - Gantt chart views
"""
from __future__ import annotations

from fastapi import APIRouter

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="projects",
    name="Projects",
    description="Project management, tasks, and milestones",
    icon="folder",
    prefix="/projects",
    group="Operations",
    order=50,
    scopes=["projects:read"],
    enabled=True,
    prefixes=["/projects"],
)

NAVIGATION = [
    {
        "section": "Projects",
        "module": "projects",
        "href": "/projects",
        "icon": "folder",
        "scope": "projects:read",
        "order": 50,
        "links": [
            {"label": "Projects", "href": "/projects", "icon": "folder"},
            {"label": "Tasks", "href": "/projects/tasks", "icon": "check-square"},
            {"label": "Milestones", "href": "/projects/milestones", "icon": "flag"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

# Import sub-routers
from .routes import router as projects_router, tasks_router, milestones_router, dashboard_router
from .gantt_routes import router as gantt_router

# Create combined router
# NOTE: Routers with specific paths (tasks, milestones, gantt, dashboard) must be
# included BEFORE projects_router because it has /{project_id} which would catch them.
# These routers have no prefix, so we add /projects here.
router = APIRouter(tags=["projects"])
router.include_router(dashboard_router, prefix="/projects")
router.include_router(tasks_router, prefix="/projects")
router.include_router(milestones_router, prefix="/projects")
router.include_router(gantt_router, prefix="/projects")
router.include_router(projects_router)  # Already has prefix="/projects"

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]
