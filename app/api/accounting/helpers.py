"""Shared helpers for the accounting API module.

This module contains API-specific helpers that depend on FastAPI (HTTPException,
StreamingResponse, etc.) and async operations.

For account classification, caching, and business logic, see:
    app.services.accounting.account_utils
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple, TypeVar, cast

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, Query

from app.models.accounting import FiscalYear
from app.cache import get_redis_client, invalidate_pattern

# Re-export all account utilities from services layer for backward compatibility
from app.services.accounting.account_utils import (
    # Constants
    ASSET_ACCOUNT_TYPES,
    LIABILITY_ACCOUNT_TYPES,
    COGS_ACCOUNT_TYPES,
    COGS_ACCOUNT_KEYWORDS,
    FINANCE_INCOME_TYPES,
    FINANCE_COST_TYPES,
    TAX_EXPENSE_TYPES,
    OPERATING_EXPENSE_TYPES,
    CURRENT_ASSET_TYPES,
    NON_CURRENT_ASSET_TYPES,
    CURRENT_LIABILITY_TYPES,
    NON_CURRENT_LIABILITY_TYPES,
    SHARE_CAPITAL_TYPES,
    SHARE_PREMIUM_TYPES,
    RESERVE_TYPES,
    TREASURY_SHARE_TYPES,
    OCI_RESERVE_TYPES,
    RETAINED_EARNINGS_TYPES,
    OCI_MAY_RECLASSIFY_TYPES,
    OCI_NOT_RECLASSIFY_TYPES,
    RIGHT_OF_USE_ASSET_TYPES,
    LEASE_LIABILITY_TYPES,
    DEFERRED_TAX_ASSET_TYPES,
    DEFERRED_TAX_LIABILITY_TYPES,
    PROVISION_TYPES,
    SHARE_BASED_PAYMENT_TYPES,
    DEPRECIATION_TYPES,
    AMORTIZATION_TYPES,
    # Functions
    get_accounts_by_erpnext_id,
    invalidate_accounts_cache,
    get_effective_root_type,
    is_cogs_account,
    is_finance_income_account,
    is_finance_cost_account,
    is_tax_expense_account,
    is_depreciation_account,
    is_lease_asset_account,
    is_lease_liability_account,
    is_deferred_tax_asset_account,
    is_deferred_tax_liability_account,
    is_provision_account,
    is_share_based_payment_account,
    classify_oci_account,
    get_equity_component_type,
    get_account_balances,
    gl_ar_ap_balances,
    serialize_account,
    serialize_gl_entry,
    decimal_to_float,
)

T = TypeVar("T")

# Report cache key prefixes for invalidation
REPORT_CACHE_KEYS = [
    "accounting-dashboard",
    "accounting-dashboard-bundle",
    "trial-balance",
    "balance-sheet",
    "income-statement",
    "accounts-payable",
    "accounts-receivable",
    "cash-flow",
    "tax-dashboard",
    "receivables-aging-enhanced",
    "payables-aging",
    "financial-ratios",
    "equity-statement",
    "period-summary",
]


# =============================================================================
# Date Parsing (API-specific - uses HTTPException)
# =============================================================================

def parse_date(value: Optional[str], field_name: str) -> Optional[date]:
    """Parse date string to date object.

    Handles both ISO format with time and simple YYYY-MM-DD format.

    Args:
        value: Date string to parse
        field_name: Name of field for error messages

    Returns:
        Parsed date or None if value is empty

    Raises:
        HTTPException: If date format is invalid
    """
    if not value:
        return None
    try:
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format for {field_name}")


def get_fiscal_year_dates(db: Session, fiscal_year: Optional[str] = None) -> Tuple[date, date]:
    """Get start and end dates for a fiscal year.

    Args:
        db: Database session
        fiscal_year: Optional fiscal year identifier

    Returns:
        Tuple of (start_date, end_date)

    Raises:
        HTTPException: If specified fiscal year not found
    """
    if fiscal_year:
        fy = db.query(FiscalYear).filter(FiscalYear.year == fiscal_year).first()
        if not fy:
            raise HTTPException(status_code=404, detail=f"Fiscal year {fiscal_year} not found")
        if fy.year_start_date is None or fy.year_end_date is None:
            raise HTTPException(
                status_code=400,
                detail=f"Fiscal year {fiscal_year} is missing start or end date",
            )
        return fy.year_start_date, fy.year_end_date

    # Default to current calendar year
    today = date.today()
    return date(today.year, 1, 1), date(today.year, 12, 31)


# =============================================================================
# Currency Resolution (API-specific - uses HTTPException)
# =============================================================================

def resolve_currency_or_raise(db: Session, column, requested: Optional[str]) -> Optional[str]:
    """Ensure we do not mix currencies.

    If none requested and multiple exist in the data, raises HTTP 400.

    Args:
        db: Database session
        column: SQLAlchemy column to check for distinct currencies
        requested: Explicitly requested currency

    Returns:
        The currency to use

    Raises:
        HTTPException: If multiple currencies detected without explicit selection
    """
    if requested:
        return requested
    currencies = [row[0] for row in db.query(func.distinct(column)).filter(column.isnot(None)).all()]
    if not currencies:
        return None
    if len(set(currencies)) > 1:
        raise HTTPException(
            status_code=400,
            detail="Multiple currencies detected; please provide the 'currency' query parameter to avoid mixed-currency aggregates.",
        )
    return cast(str, currencies[0])


# =============================================================================
# Pagination (API-specific)
# =============================================================================

def paginate(
    query: Query,
    offset: int = 0,
    limit: int = 100,
    use_window: bool = True,
) -> Tuple[int, List[Any]]:
    """Execute paginated query with count optimization.

    Uses a window function to get total count in a single query when possible,
    avoiding the common antipattern of query.count() + query.limit().all().

    Args:
        query: SQLAlchemy query to paginate
        offset: Starting position
        limit: Maximum results to return
        use_window: Use window function for count (single query). Set False for
                    complex queries where window functions may not work.

    Returns:
        Tuple of (total_count, results)
    """
    if use_window:
        # Single-query approach with window function
        try:
            counted = query.add_columns(func.count().over().label('_total'))
            rows = counted.offset(offset).limit(limit).all()
            if not rows:
                return 0, []
            # Extract total from first row (all rows have same total)
            total = rows[0]._total
            # Strip the count column from results - return original entities
            return total, [row[0] for row in rows]
        except Exception:
            # Fall back to two-query approach if window function fails
            pass

    # Fallback: two separate queries
    total = query.count()
    results = query.offset(offset).limit(limit).all()
    return total, results


# =============================================================================
# Export Helpers (API-specific - uses StreamingResponse)
# =============================================================================

def export_headers(base_filename: str, extension: str) -> Dict[str, str]:
    """Generate HTTP headers for file download.

    Args:
        base_filename: Base name for the file (without extension)
        extension: File extension (csv, pdf, etc.)

    Returns:
        Dict of HTTP headers
    """
    filename = f"{base_filename}_{date.today().isoformat()}.{extension}"
    return {
        "Content-Disposition": f'attachment; filename="{filename}"',
    }


def stream_export(
    content: Any,
    media_type: str,
    base_filename: str,
    extension: str,
) -> StreamingResponse:
    """Create a streaming response for file export.

    Args:
        content: Content to stream (string or bytes)
        media_type: MIME type
        base_filename: Base name for the file
        extension: File extension

    Returns:
        StreamingResponse configured for download
    """
    headers = export_headers(base_filename, extension)

    if isinstance(content, str):
        content = content.encode("utf-8")

    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers=headers,
    )


# =============================================================================
# Cache Invalidation (API-specific - async)
# =============================================================================

async def invalidate_report_cache(keys: Optional[List[str]] = None) -> int:
    """Invalidate accounting report caches after mutations.

    Call this after operations that modify financial data (JE post,
    invoice write-off, period close, etc.) to ensure reports show fresh data.

    Args:
        keys: Specific cache key prefixes to invalidate. If None, invalidates
              all report caches.

    Returns:
        Number of cache keys deleted
    """
    client = await get_redis_client()
    if client is None:
        return 0

    keys_to_delete = keys or REPORT_CACHE_KEYS
    deleted = 0

    for key_prefix in keys_to_delete:
        count = await invalidate_pattern(f"analytics:{key_prefix}:*")
        deleted += count

    return deleted
