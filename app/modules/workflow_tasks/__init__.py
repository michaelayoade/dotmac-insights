"""
Workflow Tasks Module - Unified Task Management.

Routes:
- /tasks - Task list and management
"""
from __future__ import annotations

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="workflow_tasks",
    name="Tasks",
    description="Workflow tasks and approvals",
    icon="check-square",
    prefix="/tasks",
    group="Main",
    order=2,
    scopes=["tasks:read"],
    prefixes=["/tasks"],
)

NAVIGATION = [
    {
        "section": "Tasks",
        "module": "workflow_tasks",
        "href": "/tasks",
        "icon": "check-square",
        "scope": "tasks:read",
        "order": 2,
        "links": [
            {"label": "All Tasks", "href": "/tasks", "icon": "check-square"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]
