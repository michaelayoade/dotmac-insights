"""
Hierarchy Validation Module

Provides circular reference detection for hierarchical data structures
(parent-child relationships) using recursive CTE queries.

Usage:
    from app.validators.hierarchy import validate_no_circular_reference, HierarchyTable

    if not validate_no_circular_reference(db, HierarchyTable.UNIFIED_CONTACTS, contact.id, new_parent_id):
        raise HTTPException(400, "Cannot set parent: would create circular reference")

Security:
    Uses enum/whitelist to prevent SQL injection - no dynamic table/field names
    are interpolated from user input.
"""
from enum import Enum
from typing import Optional
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


class HierarchyTable(Enum):
    """
    Whitelist of tables with parent references - prevents SQL injection.

    Format: (table_name, parent_field, has_deleted_at)
    """
    UNIFIED_CONTACTS = ("unified_contacts", "parent_id", False)
    TASKS = ("tasks", "parent_task_id", False)
    TICKETS = ("tickets", "parent_ticket_id", True)   # has deleted_at
    EMPLOYEES = ("employees", "reports_to_id", True)  # has deleted_at


def _build_cycle_query(table_name: str, parent_field: str, has_deleted_at: bool) -> str:
    """
    Build table-specific CTE query with conditional deleted_at filter.

    The query uses a recursive CTE to traverse the ancestor chain from the
    proposed parent and check if it would eventually reach the record being
    updated (which would indicate a cycle).

    IMPORTANT: Uses UNION (not UNION ALL) to ensure termination even if a
    cycle already exists in the data. UNION eliminates duplicates, so if
    we encounter an ID we've already seen, the recursion stops.

    Args:
        table_name: Name of the database table
        parent_field: Name of the parent foreign key column
        has_deleted_at: Whether the table has a deleted_at column for soft deletes

    Returns:
        SQL query string
    """
    # Filter out soft-deleted rows in both base and recursive parts
    deleted_filter_base = "AND deleted_at IS NULL" if has_deleted_at else ""
    deleted_filter_recursive = "WHERE t.deleted_at IS NULL" if has_deleted_at else ""

    # Use UNION (not UNION ALL) to guarantee termination if cycle exists
    return f"""
        WITH RECURSIVE ancestors AS (
            SELECT id, {parent_field}
            FROM {table_name}
            WHERE id = :parent_id {deleted_filter_base}
            UNION
            SELECT t.id, t.{parent_field}
            FROM {table_name} t
            JOIN ancestors a ON t.id = a.{parent_field}
            {deleted_filter_recursive}
        )
        SELECT EXISTS (SELECT 1 FROM ancestors WHERE id = :record_id)
    """


# Pre-built queries for each table (safe - no runtime interpolation)
_CYCLE_CHECK_QUERIES = {
    table: text(_build_cycle_query(*table.value))
    for table in HierarchyTable
}


def validate_no_circular_reference(
    db: Session,
    table: HierarchyTable,
    record_id: int,
    parent_id: Optional[int],
    *,
    company_id: Optional[int] = None,  # future: add tenant scoping
) -> bool:
    """
    Validate that setting parent_id won't create a cycle.

    Uses recursive CTE to detect cycles by traversing the ancestor chain
    from the proposed parent and checking if it would reach the record
    being updated.

    Args:
        db: SQLAlchemy database session
        table: Which hierarchy table to check (from HierarchyTable enum)
        record_id: The ID of the record being updated
        parent_id: The proposed new parent ID (or None to clear parent)
        company_id: Optional tenant ID for future multi-tenant scoping

    Returns:
        True if safe (no cycle would be created), False if cycle would be created

    Example:
        if not validate_no_circular_reference(db, HierarchyTable.EMPLOYEES, employee.id, new_manager_id):
            raise HTTPException(400, "Cannot set manager: would create circular reference")
    """
    # Clearing parent is always safe
    if parent_id is None:
        return True

    # Direct self-reference is never allowed
    if parent_id == record_id:
        logger.warning(
            f"Direct self-reference attempted: {table.value[0]}.id={record_id} -> parent_id={parent_id}"
        )
        return False

    # Check for indirect cycles using recursive CTE
    query = _CYCLE_CHECK_QUERIES[table]
    result = db.execute(query, {"parent_id": parent_id, "record_id": record_id})
    has_cycle = result.scalar()

    if has_cycle:
        logger.warning(
            f"Circular reference detected: {table.value[0]}.id={record_id} -> parent_id={parent_id}"
        )

    return not has_cycle
