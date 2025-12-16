"""Add CRM/Sales and Projects/Tasks KPI definitions

Revision ID: 20251217_add_crm_project_kpis
Revises: 20251217_add_projects_rbac_scopes
Create Date: 2025-12-17

Adds KPI definitions for:
- CRM/Sales module (opportunities, activities, pipeline)
- Projects/Tasks module (project completion, tasks, budget)

Also adds:
- KRA_SALES_PERFORMANCE: Sales Performance KRA for sales teams

CRM KPIs:
- CRM_OPP_WON: Opportunities Won (count)
- CRM_WIN_RATE: Win Rate (percent)
- CRM_PIPELINE_VALUE: Pipeline Value (sum)
- CRM_ACTIVITIES_COMPLETED: Activities Completed (count)
- CRM_AVG_DEAL_SIZE: Average Deal Size (avg)
- CRM_AVG_SALES_CYCLE: Average Sales Cycle Days (avg)

Projects KPIs:
- PROJ_COMPLETED: Projects Completed (count)
- PROJ_ON_TIME: Project On-Time Delivery Rate (percent)
- PROJ_BUDGET_ADHERENCE: Budget Adherence Rate (percent)
- TASK_COMPLETED: Tasks Completed (count)
- TASK_ON_TIME: On-Time Task Completion Rate (percent)
- TASK_TIME_VARIANCE: Average Task Time Variance (avg)
"""
from typing import Sequence, Union
import json

from alembic import op, context
import sqlalchemy as sa
from datetime import datetime


revision: str = "20251217_add_crm_project_kpis"
down_revision: Union[str, None] = "20251217_add_projects_rbac_scopes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Sales-specific KRA definition
SALES_KRA = {
    "code": "KRA_SALES_PERFORMANCE",
    "name": "Sales Performance",
    "description": "Measures sales outcomes including deals won, pipeline value, and revenue generation",
    "category": "Sales",
    "is_active": True,
}

# Projects-specific KRA definition
PROJECTS_KRA = {
    "code": "KRA_PROJECT_DELIVERY",
    "name": "Project Delivery",
    "description": "Measures project completion, on-time delivery, and budget adherence",
    "category": "Projects",
    "is_active": True,
}


# CRM/Sales KPI definitions
CRM_KPIS = [
    {
        "code": "CRM_OPP_WON",
        "name": "Opportunities Won",
        "description": "Total number of opportunities closed as won in the period",
        "data_source": "crm",
        "aggregation": "count",
        "query_config": {
            "table": "opportunities",
            "filter": {"status": "won"},
            "employee_field": "owner_id",
        },
        "scoring_method": "linear",
        "min_value": 0,
        "target_value": 10,
        "max_value": 25,
        "higher_is_better": True,
    },
    {
        "code": "CRM_WIN_RATE",
        "name": "Win Rate",
        "description": "Percentage of closed opportunities that were won",
        "data_source": "crm",
        "aggregation": "percent",
        "query_config": {
            "table": "opportunities",
            "numerator": {"status": "won"},
            "denominator": {"status_in": ["won", "lost"]},
            "employee_field": "owner_id",
        },
        "scoring_method": "threshold",
        "min_value": 0,
        "target_value": 40,
        "max_value": 100,
        "higher_is_better": True,
    },
    {
        "code": "CRM_PIPELINE_VALUE",
        "name": "Pipeline Value",
        "description": "Total value of open opportunities in pipeline",
        "data_source": "crm",
        "aggregation": "sum",
        "query_config": {
            "table": "opportunities",
            "field": "deal_value",
            "filter": {"status": "open"},
            "employee_field": "owner_id",
        },
        "scoring_method": "linear",
        "min_value": 0,
        "target_value": 5000000,
        "max_value": 15000000,
        "higher_is_better": True,
    },
    {
        "code": "CRM_ACTIVITIES_COMPLETED",
        "name": "Activities Completed",
        "description": "Total number of activities (calls, meetings, demos) completed",
        "data_source": "crm",
        "aggregation": "count",
        "query_config": {
            "table": "activities",
            "filter": {"status": "completed"},
            "employee_field": "assigned_to_id",
        },
        "scoring_method": "linear",
        "min_value": 0,
        "target_value": 50,
        "max_value": 100,
        "higher_is_better": True,
    },
    {
        "code": "CRM_AVG_DEAL_SIZE",
        "name": "Average Deal Size",
        "description": "Average value of won opportunities",
        "data_source": "crm",
        "aggregation": "avg",
        "query_config": {
            "table": "opportunities",
            "field": "deal_value",
            "filter": {"status": "won"},
            "employee_field": "owner_id",
        },
        "scoring_method": "linear",
        "min_value": 50000,
        "target_value": 500000,
        "max_value": 2000000,
        "higher_is_better": True,
    },
    {
        "code": "CRM_AVG_SALES_CYCLE",
        "name": "Average Sales Cycle (Days)",
        "description": "Average days from opportunity creation to close",
        "data_source": "crm",
        "aggregation": "avg",
        "query_config": {
            "table": "opportunities",
            "field": "sales_cycle_days",
            "filter": {"status_in": ["won", "lost"]},
            "employee_field": "owner_id",
        },
        "scoring_method": "linear",
        "min_value": 120,
        "target_value": 45,
        "max_value": 15,
        "higher_is_better": False,
    },
]


# Projects/Tasks KPI definitions
PROJECT_KPIS = [
    {
        "code": "PROJ_COMPLETED",
        "name": "Projects Completed",
        "description": "Total number of projects marked as completed",
        "data_source": "project",
        "aggregation": "count",
        "query_config": {
            "table": "projects",
            "filter": {"status": "completed"},
            "employee_field": "project_manager_id",
        },
        "scoring_method": "linear",
        "min_value": 0,
        "target_value": 5,
        "max_value": 15,
        "higher_is_better": True,
    },
    {
        "code": "PROJ_ON_TIME",
        "name": "Project On-Time Delivery Rate",
        "description": "Percentage of projects delivered on or before expected end date",
        "data_source": "project",
        "aggregation": "percent",
        "query_config": {
            "table": "projects",
            "filter": {"status": "completed"},
            "numerator": {"on_time": True},
            "denominator": {},
            "employee_field": "project_manager_id",
        },
        "scoring_method": "threshold",
        "min_value": 0,
        "target_value": 85,
        "max_value": 100,
        "higher_is_better": True,
    },
    {
        "code": "PROJ_BUDGET_ADHERENCE",
        "name": "Budget Adherence Rate",
        "description": "Percentage of projects completed within budget (actual <= estimated)",
        "data_source": "project",
        "aggregation": "percent",
        "query_config": {
            "table": "projects",
            "filter": {"status": "completed"},
            "numerator": {"within_budget": True},
            "denominator": {},
            "employee_field": "project_manager_id",
        },
        "scoring_method": "threshold",
        "min_value": 0,
        "target_value": 90,
        "max_value": 100,
        "higher_is_better": True,
    },
    {
        "code": "TASK_COMPLETED",
        "name": "Tasks Completed",
        "description": "Total number of tasks marked as completed",
        "data_source": "project",
        "aggregation": "count",
        "query_config": {
            "table": "tasks",
            "filter": {"status": "completed"},
            "employee_field": "assigned_to",
        },
        "scoring_method": "linear",
        "min_value": 0,
        "target_value": 30,
        "max_value": 80,
        "higher_is_better": True,
    },
    {
        "code": "TASK_ON_TIME",
        "name": "On-Time Task Completion Rate",
        "description": "Percentage of tasks completed on or before expected end date",
        "data_source": "project",
        "aggregation": "percent",
        "query_config": {
            "table": "tasks",
            "filter": {"status": "completed"},
            "numerator": {"on_time": True},
            "denominator": {},
            "employee_field": "assigned_to",
        },
        "scoring_method": "threshold",
        "min_value": 0,
        "target_value": 80,
        "max_value": 100,
        "higher_is_better": True,
    },
    {
        "code": "TASK_TIME_VARIANCE",
        "name": "Average Task Time Variance (%)",
        "description": "Average percentage variance between expected and actual time spent",
        "data_source": "project",
        "aggregation": "avg",
        "query_config": {
            "table": "tasks",
            "field": "time_variance_percent",
            "filter": {"status": "completed"},
            "employee_field": "assigned_to",
        },
        "scoring_method": "linear",
        "min_value": 50,
        "target_value": 10,
        "max_value": 0,
        "higher_is_better": False,
    },
]


def upgrade() -> None:
    """Add CRM/Sales and Projects/Tasks KPI definitions."""
    if context.is_offline_mode():
        return

    connection = op.get_bind()
    if connection is None:
        return

    now = datetime.utcnow()

    # =========================================================================
    # STEP 1: Add Sales KRA
    # =========================================================================
    connection.execute(
        sa.text("""
            INSERT INTO kra_definitions (code, name, description, category, is_active, created_at, updated_at)
            VALUES (:code, :name, :description, :category, :is_active, :created_at, :updated_at)
            ON CONFLICT (code) DO NOTHING
        """),
        {
            "code": SALES_KRA["code"],
            "name": SALES_KRA["name"],
            "description": SALES_KRA["description"],
            "category": SALES_KRA["category"],
            "is_active": SALES_KRA["is_active"],
            "created_at": now,
            "updated_at": now,
        }
    )

    # =========================================================================
    # STEP 2: Add Project Delivery KRA
    # =========================================================================
    connection.execute(
        sa.text("""
            INSERT INTO kra_definitions (code, name, description, category, is_active, created_at, updated_at)
            VALUES (:code, :name, :description, :category, :is_active, :created_at, :updated_at)
            ON CONFLICT (code) DO NOTHING
        """),
        {
            "code": PROJECTS_KRA["code"],
            "name": PROJECTS_KRA["name"],
            "description": PROJECTS_KRA["description"],
            "category": PROJECTS_KRA["category"],
            "is_active": PROJECTS_KRA["is_active"],
            "created_at": now,
            "updated_at": now,
        }
    )

    # =========================================================================
    # STEP 3: Add CRM/Sales KPI definitions
    # =========================================================================
    for kpi in CRM_KPIS:
        connection.execute(
            sa.text("""
                INSERT INTO kpi_definitions (
                    code, name, description, data_source, aggregation, query_config,
                    scoring_method, min_value, target_value, max_value, higher_is_better,
                    created_at, updated_at
                )
                VALUES (
                    :code, :name, :description, :data_source, :aggregation, :query_config::jsonb,
                    :scoring_method, :min_value, :target_value, :max_value, :higher_is_better,
                    :created_at, :updated_at
                )
                ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    query_config = EXCLUDED.query_config,
                    updated_at = EXCLUDED.updated_at
            """),
            {
                "code": kpi["code"],
                "name": kpi["name"],
                "description": kpi["description"],
                "data_source": kpi["data_source"],
                "aggregation": kpi["aggregation"],
                "query_config": json.dumps(kpi["query_config"]),
                "scoring_method": kpi["scoring_method"],
                "min_value": kpi["min_value"],
                "target_value": kpi["target_value"],
                "max_value": kpi["max_value"],
                "higher_is_better": kpi["higher_is_better"],
                "created_at": now,
                "updated_at": now,
            }
        )

    # =========================================================================
    # STEP 4: Add Projects/Tasks KPI definitions
    # =========================================================================
    for kpi in PROJECT_KPIS:
        connection.execute(
            sa.text("""
                INSERT INTO kpi_definitions (
                    code, name, description, data_source, aggregation, query_config,
                    scoring_method, min_value, target_value, max_value, higher_is_better,
                    created_at, updated_at
                )
                VALUES (
                    :code, :name, :description, :data_source, :aggregation, :query_config::jsonb,
                    :scoring_method, :min_value, :target_value, :max_value, :higher_is_better,
                    :created_at, :updated_at
                )
                ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    query_config = EXCLUDED.query_config,
                    updated_at = EXCLUDED.updated_at
            """),
            {
                "code": kpi["code"],
                "name": kpi["name"],
                "description": kpi["description"],
                "data_source": kpi["data_source"],
                "aggregation": kpi["aggregation"],
                "query_config": json.dumps(kpi["query_config"]),
                "scoring_method": kpi["scoring_method"],
                "min_value": kpi["min_value"],
                "target_value": kpi["target_value"],
                "max_value": kpi["max_value"],
                "higher_is_better": kpi["higher_is_better"],
                "created_at": now,
                "updated_at": now,
            }
        )


def downgrade() -> None:
    """Remove CRM/Sales and Projects/Tasks KPI definitions."""
    if context.is_offline_mode():
        return

    connection = op.get_bind()
    if connection is None:
        return

    # Delete CRM KPIs
    crm_kpi_codes = [kpi["code"] for kpi in CRM_KPIS]
    for code in crm_kpi_codes:
        connection.execute(
            sa.text("DELETE FROM kpi_definitions WHERE code = :code"),
            {"code": code}
        )

    # Delete Project KPIs
    project_kpi_codes = [kpi["code"] for kpi in PROJECT_KPIS]
    for code in project_kpi_codes:
        connection.execute(
            sa.text("DELETE FROM kpi_definitions WHERE code = :code"),
            {"code": code}
        )

    # Delete Sales KRA
    connection.execute(
        sa.text("DELETE FROM kra_definitions WHERE code = :code"),
        {"code": SALES_KRA["code"]}
    )

    # Delete Project Delivery KRA
    connection.execute(
        sa.text("DELETE FROM kra_definitions WHERE code = :code"),
        {"code": PROJECTS_KRA["code"]}
    )
