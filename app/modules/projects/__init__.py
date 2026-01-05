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
from .routes import router as projects_router
from .gantt_routes import router as gantt_router

# Create combined router
router = APIRouter(tags=["projects"])
router.include_router(projects_router)
router.include_router(gantt_router)

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]
