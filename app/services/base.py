"""Shared query helpers for the service layer.

This module provides common database query utilities:
- scoped_query(): Apply tenant/user scoping (single-tenant no-op for now)
- paginate(): Execute paginated query with count optimization
- safe_filter(): Whitelist-based filter application

Supports both SQLAlchemy 1.x Query style and 2.0 select() style.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional, Set, Type, TypeVar, Union, overload

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Query, Session

from app.services.types import PaginatedResult, PaginationParams, SortParams

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = [
    "scoped_query",
    "paginate",
    "safe_filter",
    "apply_sort",
    "Pagination",
    "SortParam",
]

T = TypeVar("T")
ModelT = TypeVar("ModelT")


# Aliases for common patterns
Pagination = PaginationParams
SortParam = SortParams


def scoped_query(
    query: Query[T],
    principal: Optional["Principal"] = None,
) -> Query[T]:
    """Apply tenant/user scoping to a query.

    In single-tenant mode, this is a no-op that returns the query unchanged.
    When multi-tenancy is implemented, this will filter by tenant_id based
    on the principal's context.

    Args:
        query: The SQLAlchemy query to scope.
        principal: The authenticated principal (user or service token).

    Returns:
        The scoped query.

    Example:
        query = scoped_query(db.query(Invoice), principal)
        query = apply_invoice_filters(query, filters)
        return paginate(query, pagination)
    """
    # Single-tenant: no scoping required
    # Future: filter by principal.tenant_id when multi-tenant
    return query


@overload
def paginate(
    db_or_query: Session,
    stmt_or_params: Select[tuple[T]],
    params: Optional[PaginationParams] = None,
    *,
    use_window: bool = True,
) -> PaginatedResult[T]:
    """SQLAlchemy 2.0 style: paginate(db, select(Model), params)"""
    ...


@overload
def paginate(
    db_or_query: Query[T],
    stmt_or_params: Optional[PaginationParams] = None,
    params: None = None,
    *,
    use_window: bool = True,
) -> PaginatedResult[T]:
    """Legacy style: paginate(query, params)"""
    ...


def paginate(
    db_or_query: Union[Session, Query[T]],
    stmt_or_params: Union[Select[tuple[T]], PaginationParams, None] = None,
    params: Optional[PaginationParams] = None,
    *,
    use_window: bool = True,
) -> PaginatedResult[T]:
    """Execute a paginated query with count optimization.

    Supports two call patterns:

    **Modern (SQLAlchemy 2.0 style):**
        result = paginate(db, select(Model).where(...), pagination)

    **Legacy (SQLAlchemy 1.x style):**
        result = paginate(query, pagination)

    Uses a window function to get total count in a single query when possible,
    avoiding the N+1 pattern of query.count() + query.limit().all().

    Args:
        db_or_query: Either a Session (modern) or Query (legacy).
        stmt_or_params: Either a Select statement (modern) or PaginationParams (legacy).
        params: PaginationParams when using modern style.
        use_window: Use window function for count (single query). Set False for
                    complex queries where window functions may not work.

    Returns:
        PaginatedResult containing items, total count, offset, and limit.

    Examples:
        # Modern style (recommended)
        stmt = select(Employee).where(Employee.status == "active")
        result = paginate(db, stmt, PaginationParams(offset=0, limit=25))

        # Legacy style (for backwards compatibility)
        query = db.query(Employee).filter(Employee.status == "active")
        result = paginate(query, PaginationParams(offset=0, limit=25))
    """
    # Detect which pattern based on argument types
    if isinstance(db_or_query, Session):
        # Modern: paginate(db, select(...), params)
        db = db_or_query
        stmt = stmt_or_params
        pagination = params or PaginationParams()
        return _paginate_select(db, stmt, pagination, use_window=use_window)
    else:
        # Legacy: paginate(query, params)
        query = db_or_query
        pagination = stmt_or_params if isinstance(stmt_or_params, PaginationParams) else PaginationParams()
        return _paginate_query(query, pagination, use_window=use_window)


def _paginate_query(
    query: Query[T],
    params: PaginationParams,
    *,
    use_window: bool = True,
) -> PaginatedResult[T]:
    """Paginate a legacy Query object."""
    offset = params.offset
    limit = params.limit

    if use_window:
        try:
            # Single-query approach with window function
            counted = query.add_columns(func.count().over().label("_total"))
            rows = counted.offset(offset).limit(limit).all()

            if not rows:
                return PaginatedResult(items=[], total=0, offset=offset, limit=limit)

            # Extract total from first row (all rows have same total)
            total = rows[0]._total
            # Strip the count column from results
            items = [row[0] for row in rows]
            return PaginatedResult(items=items, total=total, offset=offset, limit=limit)
        except Exception:
            # Fall back to two-query approach if window function fails
            pass

    # Fallback: two separate queries
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return PaginatedResult(items=items, total=total, offset=offset, limit=limit)


def _paginate_select(
    db: Session,
    stmt: Select[tuple[T]],
    params: PaginationParams,
    *,
    use_window: bool = True,
) -> PaginatedResult[T]:
    """Paginate a SQLAlchemy 2.0 Select statement."""
    offset = params.offset
    limit = params.limit

    if use_window:
        try:
            # Single-query approach with window function
            # Add count as a window function column
            counted_stmt = stmt.add_columns(func.count().over().label("_total"))
            counted_stmt = counted_stmt.offset(offset).limit(limit)
            rows = db.execute(counted_stmt).all()

            if not rows:
                return PaginatedResult(items=[], total=0, offset=offset, limit=limit)

            # Extract total from first row (all rows have same total)
            total = rows[0]._total
            # Strip the count column from results (first element is the model)
            items = [row[0] for row in rows]
            return PaginatedResult(items=items, total=total, offset=offset, limit=limit)
        except Exception:
            # Fall back to two-query approach if window function fails
            pass

    # Fallback: two separate queries
    # Get count using subquery
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    # Get paginated items
    paginated_stmt = stmt.offset(offset).limit(limit)
    items = list(db.scalars(paginated_stmt).all())

    return PaginatedResult(items=items, total=total, offset=offset, limit=limit)


def safe_filter(
    query: Query[T],
    model: Type[ModelT],
    filters: dict[str, Any],
    allowed: Set[str],
) -> Query[T]:
    """Apply only whitelisted filters to a query.

    Prevents SQL injection by only allowing explicitly whitelisted field names.
    Unknown filter keys are silently ignored.

    Args:
        query: The SQLAlchemy query to filter.
        model: The model class to get attributes from.
        filters: Dict of filter field -> value pairs.
        allowed: Set of allowed filter field names.

    Returns:
        The filtered query.

    Example:
        ALLOWED = {"status", "customer_account_id", "currency"}
        query = safe_filter(query, Invoice, {"status": "draft", "hack": "drop"}, ALLOWED)
        # Only "status" is applied; "hack" is ignored
    """
    for key, value in filters.items():
        if key not in allowed:
            continue
        if value is None:
            continue

        column = getattr(model, key, None)
        if column is None:
            continue

        query = query.filter(column == value)

    return query


@overload
def apply_sort(
    query: Query[T],
    model: Type[ModelT],
    sort: Optional[SortParams] = None,
    *,
    allowed: Optional[Set[str]] = None,
    default_field: str = "id",
) -> Query[T]:
    """Legacy style: apply_sort(query, Model, sort_params)"""
    ...


@overload
def apply_sort(
    query: Select[tuple[T]],
    model: Type[ModelT],
    sort: Optional[SortParams] = None,
    *,
    allowed: Optional[Set[str]] = None,
    default_field: str = "id",
) -> Select[tuple[T]]:
    """Modern style: apply_sort(select_stmt, Model, sort_params)"""
    ...


def apply_sort(
    query: Union[Query[T], Select[tuple[T]]],
    model: Type[ModelT],
    sort: Optional[SortParams] = None,
    *,
    allowed: Optional[Set[str]] = None,
    default_field: str = "id",
) -> Union[Query[T], Select[tuple[T]]]:
    """Apply sorting to a query with field validation.

    Supports both SQLAlchemy 1.x Query and 2.0 Select styles.

    Args:
        query: The SQLAlchemy query or select statement to sort.
        model: The model class to get the sort column from.
        sort: SortParams with field and descending. If None, no sorting applied.
        allowed: Optional set of allowed sort fields. If None, any valid field is allowed.
        default_field: Field to use if requested field is invalid.

    Returns:
        The sorted query/statement.

    Examples:
        # Modern style
        stmt = apply_sort(select(Employee), Employee, SortParams("name", False))

        # Legacy style
        query = apply_sort(db.query(Employee), Employee, SortParams("name", False))
    """
    if sort is None:
        return query

    field = sort.field
    descending = sort.descending

    # Validate field against whitelist if provided
    if allowed is not None and field not in allowed:
        field = default_field

    column = getattr(model, field, None)
    if column is None:
        column = getattr(model, default_field, None)
        if column is None:
            return query

    if descending:
        return query.order_by(column.desc())
    return query.order_by(column.asc())
