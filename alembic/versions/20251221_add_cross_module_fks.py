"""Add cross-module foreign keys for better data integrity.

This migration adds FK columns to enable proper cross-module queries:
- Task: assigned_to_id, completed_by_id → employees
- Expense: vehicle_id → vehicles, asset_id → assets
- Asset: custodian_id → employees
- ServiceOrder: asset_id → assets, vehicle_id → vehicles
- Ticket: resolution_team_id → teams
- UnifiedTicket: assigned_team_id → teams

These FKs complement existing TEXT fields (kept for ERPNext sync compatibility)
and enable efficient local queries and referential integrity.

Revision ID: 20251221_add_cross_module_fks
Revises: 20251221_add_asset_settings
Create Date: 2025-12-21
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "20251221_add_cross_module_fks"
down_revision: Union[str, None] = "20251221_add_asset_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add cross-module FK columns and indexes."""

    # ==========================================================================
    # Task: assigned_to_id, completed_by_id → employees
    # ==========================================================================
    op.add_column(
        "tasks",
        sa.Column("assigned_to_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("completed_by_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_tasks_assigned_to_id", "tasks", ["assigned_to_id"])
    op.create_index("ix_tasks_completed_by_id", "tasks", ["completed_by_id"])
    op.create_foreign_key(
        "fk_tasks_assigned_to_id_employees",
        "tasks",
        "employees",
        ["assigned_to_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_tasks_completed_by_id_employees",
        "tasks",
        "employees",
        ["completed_by_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ==========================================================================
    # Expense: vehicle_id → vehicles, asset_id → assets
    # ==========================================================================
    op.add_column(
        "expenses",
        sa.Column("vehicle_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "expenses",
        sa.Column("asset_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_expenses_vehicle_id", "expenses", ["vehicle_id"])
    op.create_index("ix_expenses_asset_id", "expenses", ["asset_id"])
    op.create_foreign_key(
        "fk_expenses_vehicle_id_vehicles",
        "expenses",
        "vehicles",
        ["vehicle_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_expenses_asset_id_assets",
        "expenses",
        "assets",
        ["asset_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ==========================================================================
    # Asset: custodian_id → employees
    # ==========================================================================
    op.add_column(
        "assets",
        sa.Column("custodian_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_assets_custodian_id", "assets", ["custodian_id"])
    op.create_foreign_key(
        "fk_assets_custodian_id_employees",
        "assets",
        "employees",
        ["custodian_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ==========================================================================
    # ServiceOrder: asset_id → assets, vehicle_id → vehicles
    # ==========================================================================
    op.add_column(
        "service_orders",
        sa.Column("asset_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "service_orders",
        sa.Column("vehicle_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_service_orders_asset_id", "service_orders", ["asset_id"])
    op.create_index("ix_service_orders_vehicle_id", "service_orders", ["vehicle_id"])
    op.create_foreign_key(
        "fk_service_orders_asset_id_assets",
        "service_orders",
        "assets",
        ["asset_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_service_orders_vehicle_id_vehicles",
        "service_orders",
        "vehicles",
        ["vehicle_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ==========================================================================
    # Ticket: resolution_team_id → teams
    # ==========================================================================
    op.add_column(
        "tickets",
        sa.Column("resolution_team_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_tickets_resolution_team_id", "tickets", ["resolution_team_id"])
    op.create_foreign_key(
        "fk_tickets_resolution_team_id_teams",
        "tickets",
        "teams",
        ["resolution_team_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ==========================================================================
    # UnifiedTicket: assigned_team_id → teams
    # ==========================================================================
    op.add_column(
        "unified_tickets",
        sa.Column("assigned_team_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_unified_tickets_assigned_team_id", "unified_tickets", ["assigned_team_id"]
    )
    op.create_foreign_key(
        "fk_unified_tickets_assigned_team_id_teams",
        "unified_tickets",
        "teams",
        ["assigned_team_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Remove cross-module FK columns."""

    # UnifiedTicket
    op.drop_constraint(
        "fk_unified_tickets_assigned_team_id_teams", "unified_tickets", type_="foreignkey"
    )
    op.drop_index("ix_unified_tickets_assigned_team_id", table_name="unified_tickets")
    op.drop_column("unified_tickets", "assigned_team_id")

    # Ticket
    op.drop_constraint(
        "fk_tickets_resolution_team_id_teams", "tickets", type_="foreignkey"
    )
    op.drop_index("ix_tickets_resolution_team_id", table_name="tickets")
    op.drop_column("tickets", "resolution_team_id")

    # ServiceOrder
    op.drop_constraint(
        "fk_service_orders_vehicle_id_vehicles", "service_orders", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_service_orders_asset_id_assets", "service_orders", type_="foreignkey"
    )
    op.drop_index("ix_service_orders_vehicle_id", table_name="service_orders")
    op.drop_index("ix_service_orders_asset_id", table_name="service_orders")
    op.drop_column("service_orders", "vehicle_id")
    op.drop_column("service_orders", "asset_id")

    # Asset
    op.drop_constraint(
        "fk_assets_custodian_id_employees", "assets", type_="foreignkey"
    )
    op.drop_index("ix_assets_custodian_id", table_name="assets")
    op.drop_column("assets", "custodian_id")

    # Expense
    op.drop_constraint(
        "fk_expenses_asset_id_assets", "expenses", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_expenses_vehicle_id_vehicles", "expenses", type_="foreignkey"
    )
    op.drop_index("ix_expenses_asset_id", table_name="expenses")
    op.drop_index("ix_expenses_vehicle_id", table_name="expenses")
    op.drop_column("expenses", "asset_id")
    op.drop_column("expenses", "vehicle_id")

    # Task
    op.drop_constraint(
        "fk_tasks_completed_by_id_employees", "tasks", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_tasks_assigned_to_id_employees", "tasks", type_="foreignkey"
    )
    op.drop_index("ix_tasks_completed_by_id", table_name="tasks")
    op.drop_index("ix_tasks_assigned_to_id", table_name="tasks")
    op.drop_column("tasks", "completed_by_id")
    op.drop_column("tasks", "assigned_to_id")
