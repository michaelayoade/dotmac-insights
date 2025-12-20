"""
HR Module Helpers

Common utilities shared across HR sub-modules.
"""

import io
import csv
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

if TYPE_CHECKING:
    from app.models.hr_leave import LeaveAllocation, LeaveApplication, LeaveType


def decimal_or_default(val: Optional[Decimal], default: Decimal = Decimal("0")) -> Decimal:
    """Convert value to Decimal or return default."""
    if val is None:
        return default
    return Decimal(str(val))


def now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


def csv_response(rows: List[List[Any]], filename: str) -> StreamingResponse:
    """Utility to return a CSV string response."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def validate_date_order(start, end, field: str = "start_date/end_date"):
    """Validate that start date is on or before end date."""
    if start and end and start > end:
        raise HTTPException(status_code=400, detail=f"{field} must have start on or before end")


def status_counts(records) -> Dict[str, int]:
    """Convert status query results to a dict of status -> count."""
    return {row[0].value if row[0] else "unknown": int(row[1] or 0) for row in records}


def get_leave_balance(
    db: Session,
    employee_id: int,
    leave_type_id: int,
    as_of_date: date,
) -> Decimal:
    """
    Calculate available leave balance for an employee/leave type as of a given date.

    Returns the sum of unused_leaves from all active allocations for the period,
    aligned with allocation balances updated during approvals/cancellations.
    """
    from app.models.hr_leave import LeaveAllocation, LeaveAllocationStatus

    # Find active allocations covering the date
    allocations = db.query(LeaveAllocation).filter(
        LeaveAllocation.employee_id == employee_id,
        LeaveAllocation.leave_type_id == leave_type_id,
        LeaveAllocation.from_date <= as_of_date,
        LeaveAllocation.to_date >= as_of_date,
        LeaveAllocation.status.in_([LeaveAllocationStatus.SUBMITTED, LeaveAllocationStatus.DRAFT]),
    ).all()

    if not allocations:
        return Decimal("0")

    # Use the tracked unused_leaves to align with prior approvals/cancellations
    remaining = sum([a.unused_leaves or Decimal("0") for a in allocations], Decimal("0"))
    return remaining


def check_leave_overlap(
    db: Session,
    employee_id: int,
    from_date: date,
    to_date: date,
    exclude_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Check if there's an overlapping leave application for the employee.

    Returns the overlapping application info if found, None otherwise.
    """
    from app.models.hr_leave import LeaveApplication, LeaveApplicationStatus

    query = db.query(LeaveApplication).filter(
        LeaveApplication.employee_id == employee_id,
        LeaveApplication.status.in_([LeaveApplicationStatus.APPROVED, LeaveApplicationStatus.OPEN]),
        # Overlap condition: existing.from <= new.to AND existing.to >= new.from
        LeaveApplication.from_date <= to_date,
        LeaveApplication.to_date >= from_date,
    )

    if exclude_id:
        query = query.filter(LeaveApplication.id != exclude_id)

    existing = query.first()
    if existing:
        return {
            "id": existing.id,
            "from_date": existing.from_date.isoformat() if existing.from_date else None,
            "to_date": existing.to_date.isoformat() if existing.to_date else None,
            "leave_type": existing.leave_type,
            "status": existing.status.value if existing.status else None,
        }
    return None


def check_allocation_overlap(
    db: Session,
    employee_id: int,
    leave_type_id: int,
    from_date: date,
    to_date: date,
    exclude_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Check if there's an overlapping leave allocation for the employee/leave type.

    Returns the overlapping allocation info if found, None otherwise.
    """
    from app.models.hr_leave import LeaveAllocation, LeaveAllocationStatus

    query = db.query(LeaveAllocation).filter(
        LeaveAllocation.employee_id == employee_id,
        LeaveAllocation.leave_type_id == leave_type_id,
        LeaveAllocation.status.in_([LeaveAllocationStatus.SUBMITTED, LeaveAllocationStatus.DRAFT]),
        # Overlap condition
        LeaveAllocation.from_date <= to_date,
        LeaveAllocation.to_date >= from_date,
    )

    if exclude_id:
        query = query.filter(LeaveAllocation.id != exclude_id)

    existing = query.first()
    if existing:
        return {
            "id": existing.id,
            "from_date": existing.from_date.isoformat() if existing.from_date else None,
            "to_date": existing.to_date.isoformat() if existing.to_date else None,
            "total_leaves_allocated": float(existing.total_leaves_allocated) if existing.total_leaves_allocated else 0,
        }
    return None


def get_leave_type_constraints(db: Session, leave_type_id: int) -> Optional[Dict[str, Any]]:
    """
    Get leave type constraints for validation.

    Returns dict with max_leaves_allowed, max_continuous_days_allowed, is_carry_forward.
    """
    from app.models.hr_leave import LeaveType

    lt = db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()
    if not lt:
        return None

    return {
        "id": lt.id,
        "leave_type_name": lt.leave_type_name,
        "max_leaves_allowed": lt.max_leaves_allowed or 0,
        "max_continuous_days_allowed": lt.max_continuous_days_allowed or 0,
        "is_carry_forward": lt.is_carry_forward or False,
        "is_lwp": lt.is_lwp or False,
    }


def update_allocation_balance(
    db: Session,
    employee_id: int,
    leave_type_id: int,
    application_from_date: date,
    days_delta: Decimal,
) -> bool:
    """
    Update the unused_leaves in the allocation covering the application period.

    days_delta: positive to restore balance (cancel), negative to deduct (approve)
    Returns True if allocation found and updated, False otherwise.
    """
    from app.models.hr_leave import LeaveAllocation, LeaveAllocationStatus

    allocation = db.query(LeaveAllocation).filter(
        LeaveAllocation.employee_id == employee_id,
        LeaveAllocation.leave_type_id == leave_type_id,
        LeaveAllocation.from_date <= application_from_date,
        LeaveAllocation.to_date >= application_from_date,
        LeaveAllocation.status.in_([LeaveAllocationStatus.SUBMITTED, LeaveAllocationStatus.DRAFT]),
    ).first()

    if not allocation:
        return False

    current_unused = allocation.unused_leaves or Decimal("0")
    allocation.unused_leaves = current_unused + days_delta
    return True
