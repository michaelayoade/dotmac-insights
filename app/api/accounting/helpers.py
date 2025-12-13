"""Shared helpers for the accounting module."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, TypeVar

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, Query

from app.models.accounting import Account, AccountType, FiscalYear, GLEntry
from app.cache import get_redis_client, invalidate_pattern

T = TypeVar("T")


# =============================================================================
# Constants
# =============================================================================

LIABILITY_ACCOUNT_TYPES = {"Payable", "Current Liability"}
ASSET_ACCOUNT_TYPES = {"Receivable", "Bank", "Cash", "Fixed Asset", "Stock", "Current Asset"}

REPORT_CACHE_KEYS = [
    "accounting-dashboard",
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
# Date Parsing
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
        return fy.year_start_date, fy.year_end_date

    # Default to current calendar year
    today = date.today()
    return date(today.year, 1, 1), date(today.year, 12, 31)


# =============================================================================
# Currency Resolution
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
    return currencies[0]


# =============================================================================
# Pagination
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
# Account Balance Helpers
# =============================================================================

def get_account_balances(
    db: Session,
    as_of: Optional[date] = None,
    account_ids: Optional[List[str]] = None,
) -> Dict[str, Decimal]:
    """Get GL account balances as of a date.

    Args:
        db: Database session
        as_of: Date to calculate balances as of (defaults to today)
        account_ids: Optional list of account IDs to filter

    Returns:
        Dict mapping account erpnext_id to balance (debit - credit)
    """
    if as_of is None:
        as_of = date.today()

    query = db.query(
        GLEntry.account,
        func.sum(GLEntry.debit - GLEntry.credit).label("balance"),
    ).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date <= as_of,
    )

    if account_ids:
        query = query.filter(GLEntry.account.in_(account_ids))

    query = query.group_by(GLEntry.account)

    return {row.account: Decimal(str(row.balance or 0)) for row in query.all()}


def get_effective_root_type(acc: Account) -> Optional[AccountType]:
    """Determine effective root type for an account.

    Handles special account types that may override root_type classification.

    Args:
        acc: Account model instance

    Returns:
        Effective AccountType or None
    """
    if not acc:
        return None

    # Check if account_type overrides root_type
    if acc.account_type in ASSET_ACCOUNT_TYPES:
        return AccountType.ASSET
    if acc.account_type in LIABILITY_ACCOUNT_TYPES:
        return AccountType.LIABILITY

    return acc.root_type


def gl_ar_ap_balances(db: Session, as_of: date) -> Dict[str, float]:
    """Return GL balances for AR/AP control accounts.

    Credits minus debits for liabilities, debits minus credits for assets.

    Args:
        db: Database session
        as_of: Date to calculate balances as of

    Returns:
        Dict with 'ar' and 'ap' totals
    """
    accounts = {acc.erpnext_id: acc for acc in db.query(Account).all()}

    entries = (
        db.query(
            GLEntry.account,
            func.sum(GLEntry.debit).label("debit"),
            func.sum(GLEntry.credit).label("credit"),
        )
        .filter(
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= as_of,
            GLEntry.account.isnot(None),
        )
        .group_by(GLEntry.account)
        .all()
    )

    ar_total = 0.0
    ap_total = 0.0
    for row in entries:
        acc = accounts.get(row.account)
        debit = float(row.debit or 0)
        credit = float(row.credit or 0)
        if acc and (acc.account_type == "Receivable" or acc.root_type == AccountType.ASSET):
            ar_total += (debit - credit)
        if acc and (acc.account_type == "Payable" or acc.root_type == AccountType.LIABILITY):
            ap_total += (credit - debit)
    return {"ar": ar_total, "ap": ap_total}


# =============================================================================
# Export Helpers
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
# Cache Invalidation
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


# =============================================================================
# Serialization Helpers
# =============================================================================

def serialize_account(acc: Account) -> Dict[str, Any]:
    """Serialize an Account to a dict for API response.

    Args:
        acc: Account model instance

    Returns:
        Dict representation
    """
    return {
        "id": acc.id,
        "erpnext_id": acc.erpnext_id,
        "name": acc.account_name,
        "account_number": acc.account_number,
        "parent_account": acc.parent_account,
        "root_type": acc.root_type.value if acc.root_type else None,
        "account_type": acc.account_type,
        "is_group": acc.is_group,
        "disabled": acc.disabled,
    }


def serialize_gl_entry(entry: GLEntry, include_account_name: bool = False) -> Dict[str, Any]:
    """Serialize a GLEntry to a dict for API response.

    Args:
        entry: GLEntry model instance
        include_account_name: Whether to include joined account name

    Returns:
        Dict representation
    """
    result = {
        "id": entry.id,
        "erpnext_id": entry.erpnext_id,
        "posting_date": entry.posting_date.isoformat() if entry.posting_date else None,
        "account": entry.account,
        "debit": float(entry.debit or 0),
        "credit": float(entry.credit or 0),
        "party_type": entry.party_type,
        "party": entry.party,
        "voucher_type": entry.voucher_type,
        "voucher_no": entry.voucher_no,
        "cost_center": entry.cost_center,
        "remarks": entry.remarks,
        "is_cancelled": entry.is_cancelled,
    }

    if include_account_name and hasattr(entry, "account_name"):
        result["account_name"] = entry.account_name

    return result


def decimal_to_float(value: Optional[Decimal]) -> float:
    """Safely convert Decimal to float for JSON serialization.

    Args:
        value: Decimal value or None

    Returns:
        Float value (0.0 if None)
    """
    if value is None:
        return 0.0
    return float(value)
