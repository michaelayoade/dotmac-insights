"""
HR Module - Human Resources Management with SSR + HTMX.

This module provides web interfaces for HR functions:
- Employees: Employee directory and profile management
- Departments: Department hierarchy
- Leave: Leave types, allocations, and applications
- Attendance: Shift types and attendance records
- Payroll: Salary structures, slips, and payroll runs
- Training: Programs, events, and results
- Appraisal: Performance reviews and templates
- Recruitment: Job openings, applicants, offers, and interviews
- Lifecycle: Onboarding, separations, promotions, transfers

Permission Requirements:
- hr:read - View HR data
- hr:write - Create, update, delete HR data
"""
from __future__ import annotations

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="hr",
    name="Human Resources",
    description="Employee management, payroll, leave, and recruitment",
    icon="users",
    prefix="/hr",
    group="People Ops",
    order=30,
    scopes=["hr:read"],
    prefixes=["/hr"],
)

NAVIGATION = [
    {
        "section": "HR",
        "module": "hr",
        "href": "/hr",
        "icon": "users",
        "scope": "hr:read",
        "order": 30,
        "links": [
            {"label": "Dashboard", "href": "/hr", "icon": "home"},
            {"label": "Employees", "href": "/hr/employees", "icon": "users"},
            {"label": "Departments", "href": "/hr/departments", "icon": "building"},
            {"label": "Designations", "href": "/hr/designations", "icon": "award"},
            {"label": "Leave Applications", "href": "/hr/leave", "icon": "calendar"},
            {"label": "Leave Types", "href": "/hr/leave/types", "icon": "list"},
            {"label": "Leave Allocations", "href": "/hr/leave/allocations", "icon": "check-square"},
            {"label": "Attendance", "href": "/hr/attendance", "icon": "clock"},
            {"label": "Shifts", "href": "/hr/attendance/shifts", "icon": "clock"},
            {"label": "Payroll Slips", "href": "/hr/payroll", "icon": "dollar-sign"},
            {"label": "Payroll Runs", "href": "/hr/payroll/runs", "icon": "repeat"},
            {"label": "Salary Structures", "href": "/hr/payroll/structures", "icon": "list"},
            {"label": "Training Events", "href": "/hr/training", "icon": "book"},
            {"label": "Training Programs", "href": "/hr/training/programs", "icon": "book-open"},
            {"label": "Appraisals", "href": "/hr/appraisal", "icon": "award"},
            {"label": "Appraisal Templates", "href": "/hr/appraisal/templates", "icon": "file-text"},
            {"label": "Job Openings", "href": "/hr/recruitment", "icon": "user-plus"},
            {"label": "Applicants", "href": "/hr/recruitment/applicants", "icon": "users"},
            {"label": "Interviews", "href": "/hr/recruitment/interviews", "icon": "calendar"},
            {"label": "Job Offers", "href": "/hr/recruitment/offers", "icon": "file-text"},
            {"label": "Onboarding", "href": "/hr/lifecycle/onboarding", "icon": "user-plus"},
            {"label": "Separations", "href": "/hr/lifecycle/separation", "icon": "user-minus"},
            {"label": "Promotions", "href": "/hr/lifecycle/promotions", "icon": "trending-up"},
            {"label": "Transfers", "href": "/hr/lifecycle/transfers", "icon": "repeat"},
            {"label": "Holidays", "href": "/hr/holidays", "icon": "calendar"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]
