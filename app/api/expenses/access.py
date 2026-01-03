"""Expense access helpers for owner/organization scoping."""
from __future__ import annotations

from typing import Optional, cast

from fastapi import HTTPException
from sqlalchemy import false, func, or_
from sqlalchemy.orm import Session

from app.auth import Principal
from app.models.employee import Employee


def _normalize_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    return email.strip().lower()


def _can_manage_all(principal: Principal) -> bool:
    return (
        principal.is_superuser
        or principal.has_scope("expenses:admin")
        or principal.has_scope("expenses:read:all")
        or principal.has_scope("expenses:write:all")
    )


def resolve_employee_id(principal: Principal, db: Session) -> Optional[int]:
    """Resolve the Employee.id for the current principal via email mapping."""
    if principal.type != "user":
        return None
    normalized = _normalize_email(principal.email)
    if not normalized:
        return None
    employee_id = (
        db.query(Employee.id)
        .filter(func.lower(Employee.email) == normalized)
        .scalar()
    )
    return cast(Optional[int], employee_id)


def apply_employee_scope(
    query,
    principal: Principal,
    db: Session,
    *,
    employee_field,
    created_by_field=None,
):
    """Apply ownership scoping for expense resources."""
    if _can_manage_all(principal):
        return query

    filters = []
    employee_id = resolve_employee_id(principal, db)
    if employee_id is not None:
        filters.append(employee_field == employee_id)
    if created_by_field is not None and principal.type == "user":
        filters.append(created_by_field == principal.id)

    if not filters:
        return query.filter(false())
    return query.filter(or_(*filters))


def assert_employee_access(principal: Principal, db: Session, employee_id: int) -> None:
    """Ensure the principal can act on resources owned by the given employee."""
    if _can_manage_all(principal):
        return
    resolved_employee_id = resolve_employee_id(principal, db)
    if resolved_employee_id != employee_id:
        raise HTTPException(status_code=403, detail="Permission denied for this employee")
