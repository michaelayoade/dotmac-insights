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
# Sign Convention Documentation
# =============================================================================
"""
IFRS Sign Conventions (enforced throughout the system):

BALANCE SHEET (cumulative balances):
- Assets: Positive debit balance (debit - credit > 0)
- Liabilities: Positive credit balance (stored as positive in API responses)
- Equity: Positive credit balance (stored as positive in API responses)

INCOME STATEMENT (period flows):
- Revenue: Positive amounts (credit increases)
- Expenses: Positive amounts (debit increases)
- Net Income = Revenue - Expenses (positive = profit)

CASH FLOW STATEMENT:
- Inflows: Positive amounts
- Outflows: Negative amounts
- Net change = Opening + Net Flow = Closing

STATEMENT OF CHANGES IN EQUITY:
- Opening balances: Positive
- Increases (profit, issues): Positive
- Decreases (losses, dividends, buybacks): Negative
- Closing balance = Opening + all movements
"""


# =============================================================================
# Constants
# =============================================================================

LIABILITY_ACCOUNT_TYPES = {"Payable", "Current Liability"}
ASSET_ACCOUNT_TYPES = {"Receivable", "Bank", "Cash", "Fixed Asset", "Stock", "Current Asset"}

# Cost of Goods Sold account types for Income Statement classification
COGS_ACCOUNT_TYPES = {"Cost of Goods Sold", "Stock Adjustment", "Stock Received But Not Billed"}
COGS_ACCOUNT_KEYWORDS = {"cost of goods", "cogs", "cost of sales", "direct cost", "stock adjustment"}

# Operating expense categories for better P&L presentation
OPERATING_EXPENSE_TYPES = {
    "Expense Account", "Indirect Expense", "Administrative Expense",
    "Selling Expense", "Marketing Expense",
}

# Current vs Non-Current classification for Balance Sheet (GAAP/IFRS)
CURRENT_ASSET_TYPES = {
    "Bank", "Cash", "Receivable", "Stock", "Current Asset",
    "Temporary Asset", "Prepaid Expense",
}
NON_CURRENT_ASSET_TYPES = {
    "Fixed Asset", "Capital Work in Progress", "Accumulated Depreciation",
    "Investment", "Long Term Investment", "Intangible Asset",
}
CURRENT_LIABILITY_TYPES = {
    "Payable", "Current Liability", "Tax Liability", "Short Term Loan",
    "Accrued Liability",
}
NON_CURRENT_LIABILITY_TYPES = {
    "Long Term Liability", "Loan", "Deferred Tax", "Long Term Loan",
    "Provision",
}

# Equity component classification for IFRS Statement of Changes in Equity
SHARE_CAPITAL_TYPES = {
    "Share Capital", "Ordinary Share Capital", "Preference Share Capital",
    "Common Stock", "Preferred Stock", "Capital Stock",
}
SHARE_PREMIUM_TYPES = {
    "Share Premium", "Additional Paid-In Capital", "Capital Surplus",
    "Share Premium Account",
}
RESERVE_TYPES = {
    "Reserve", "Statutory Reserve", "General Reserve", "Legal Reserve",
    "Revaluation Reserve", "Capital Reserve", "Revenue Reserve",
}
TREASURY_SHARE_TYPES = {
    "Treasury Stock", "Treasury Shares", "Own Shares",
}
OCI_RESERVE_TYPES = {
    "Other Comprehensive Income", "OCI Reserve", "Revaluation Surplus",
    "Foreign Currency Translation Reserve", "Fair Value Reserve",
    "Cash Flow Hedge Reserve", "Available for Sale Reserve",
}
RETAINED_EARNINGS_TYPES = {
    "Retained Earnings", "Accumulated Profit", "Accumulated Loss",
    "Profit and Loss Account", "Undistributed Profits",
}

# Finance income/cost account types for IFRS Income Statement
FINANCE_INCOME_TYPES = {
    "Interest Income", "Investment Income", "Dividend Income",
    "Finance Income", "Bank Interest",
}
FINANCE_COST_TYPES = {
    "Interest Expense", "Finance Cost", "Bank Charges", "Interest on Loan",
    "Finance Charges", "Loan Interest",
}
TAX_EXPENSE_TYPES = {
    "Income Tax", "Tax Expense", "Corporate Tax", "Deferred Tax Expense",
    "Current Tax", "Tax Provision",
}

# IFRS 16 - Lease accounting classifications
RIGHT_OF_USE_ASSET_TYPES = {
    "Right of Use Asset", "ROU Asset", "Lease Asset",
    "Right-of-Use Asset", "Operating Lease Asset",
}
LEASE_LIABILITY_TYPES = {
    "Lease Liability", "Operating Lease Liability", "Finance Lease Liability",
    "Lease Obligation", "Right of Use Liability",
}

# IAS 12 - Deferred tax classifications
DEFERRED_TAX_ASSET_TYPES = {
    "Deferred Tax Asset", "DTA", "Deferred Tax Receivable",
}
DEFERRED_TAX_LIABILITY_TYPES = {
    "Deferred Tax Liability", "DTL", "Deferred Tax Payable",
}

# IAS 37 - Provisions and contingent liabilities
PROVISION_TYPES = {
    "Provision", "Provision for", "Warranty Provision",
    "Restructuring Provision", "Legal Provision", "Environmental Provision",
    "Contingency Reserve",
}

# IFRS 2 - Share-based payment classifications
SHARE_BASED_PAYMENT_TYPES = {
    "Share Based Payment", "Stock Compensation", "Share Option Reserve",
    "Employee Share Scheme", "ESOP Reserve", "Stock Based Compensation",
}

# OCI classifications for may/may-not reclassify split (IAS 1)
OCI_MAY_RECLASSIFY_TYPES = {
    "Cash Flow Hedge Reserve", "Foreign Currency Translation Reserve",
    "Available for Sale Reserve", "Hedging Reserve", "Translation Reserve",
}
OCI_NOT_RECLASSIFY_TYPES = {
    "Revaluation Surplus", "Actuarial Gains Losses", "FVOCI Equity Reserve",
    "Remeasurement Reserve", "Property Revaluation Reserve",
}

# Depreciation and amortization for D&A tracking
DEPRECIATION_TYPES = {
    "Depreciation", "Accumulated Depreciation", "Depreciation Expense",
}
AMORTIZATION_TYPES = {
    "Amortization", "Accumulated Amortization", "Amortization Expense",
}

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


def is_cogs_account(acc: Account) -> bool:
    """Determine if an expense account is Cost of Goods Sold.

    COGS accounts are identified by:
    1. Account type being in COGS_ACCOUNT_TYPES
    2. Account name containing COGS-related keywords

    Args:
        acc: Account model instance

    Returns:
        True if account is COGS, False otherwise
    """
    if not acc:
        return False

    # Check account type
    if acc.account_type in COGS_ACCOUNT_TYPES:
        return True

    # Check account name for COGS keywords
    acc_name_lower = (acc.account_name or "").lower()
    for keyword in COGS_ACCOUNT_KEYWORDS:
        if keyword in acc_name_lower:
            return True

    return False


def is_finance_income_account(acc: Account) -> bool:
    """Determine if an account is finance income (IAS 1)."""
    if not acc:
        return False
    if acc.account_type in FINANCE_INCOME_TYPES:
        return True
    acc_name_lower = (acc.account_name or "").lower()
    return any(kw in acc_name_lower for kw in ["interest income", "finance income", "investment income"])


def is_finance_cost_account(acc: Account) -> bool:
    """Determine if an account is finance cost (IAS 1)."""
    if not acc:
        return False
    if acc.account_type in FINANCE_COST_TYPES:
        return True
    acc_name_lower = (acc.account_name or "").lower()
    return any(kw in acc_name_lower for kw in ["interest expense", "finance cost", "bank charges"])


def is_tax_expense_account(acc: Account) -> bool:
    """Determine if an account is tax expense (IAS 12)."""
    if not acc:
        return False
    if acc.account_type in TAX_EXPENSE_TYPES:
        return True
    acc_name_lower = (acc.account_name or "").lower()
    return any(kw in acc_name_lower for kw in ["income tax", "tax expense", "corporate tax"])


def is_depreciation_account(acc: Account) -> bool:
    """Determine if an account is depreciation or amortization."""
    if not acc:
        return False
    if acc.account_type in DEPRECIATION_TYPES or acc.account_type in AMORTIZATION_TYPES:
        return True
    acc_name_lower = (acc.account_name or "").lower()
    return any(kw in acc_name_lower for kw in ["depreciation", "amortization"])


def is_lease_asset_account(acc: Account) -> bool:
    """Determine if an account is a right-of-use asset (IFRS 16)."""
    if not acc:
        return False
    if acc.account_type in RIGHT_OF_USE_ASSET_TYPES:
        return True
    acc_name_lower = (acc.account_name or "").lower()
    return any(kw in acc_name_lower for kw in ["right of use", "rou asset", "lease asset"])


def is_lease_liability_account(acc: Account) -> bool:
    """Determine if an account is a lease liability (IFRS 16)."""
    if not acc:
        return False
    if acc.account_type in LEASE_LIABILITY_TYPES:
        return True
    acc_name_lower = (acc.account_name or "").lower()
    return any(kw in acc_name_lower for kw in ["lease liability", "lease obligation"])


def is_deferred_tax_asset_account(acc: Account) -> bool:
    """Determine if an account is a deferred tax asset (IAS 12)."""
    if not acc:
        return False
    if acc.account_type in DEFERRED_TAX_ASSET_TYPES:
        return True
    acc_name_lower = (acc.account_name or "").lower()
    return "deferred tax asset" in acc_name_lower or "dta" in acc_name_lower


def is_deferred_tax_liability_account(acc: Account) -> bool:
    """Determine if an account is a deferred tax liability (IAS 12)."""
    if not acc:
        return False
    if acc.account_type in DEFERRED_TAX_LIABILITY_TYPES:
        return True
    acc_name_lower = (acc.account_name or "").lower()
    return "deferred tax liability" in acc_name_lower or "dtl" in acc_name_lower


def is_provision_account(acc: Account) -> bool:
    """Determine if an account is a provision (IAS 37)."""
    if not acc:
        return False
    if acc.account_type in PROVISION_TYPES:
        return True
    acc_name_lower = (acc.account_name or "").lower()
    return "provision" in acc_name_lower


def is_share_based_payment_account(acc: Account) -> bool:
    """Determine if an account is share-based payment related (IFRS 2)."""
    if not acc:
        return False
    if acc.account_type in SHARE_BASED_PAYMENT_TYPES:
        return True
    acc_name_lower = (acc.account_name or "").lower()
    return any(kw in acc_name_lower for kw in ["share based", "stock compensation", "esop", "share option"])


def classify_oci_account(acc: Account) -> Optional[str]:
    """Classify an OCI account as may-reclassify or not-reclassify.

    Args:
        acc: Account model instance

    Returns:
        "may_reclassify", "not_reclassify", or None if not OCI
    """
    if not acc:
        return None

    if acc.account_type in OCI_MAY_RECLASSIFY_TYPES:
        return "may_reclassify"
    if acc.account_type in OCI_NOT_RECLASSIFY_TYPES:
        return "not_reclassify"

    # Check by name
    acc_name_lower = (acc.account_name or "").lower()
    if any(kw in acc_name_lower for kw in ["hedge", "translation", "available for sale"]):
        return "may_reclassify"
    if any(kw in acc_name_lower for kw in ["revaluation", "actuarial", "remeasurement"]):
        return "not_reclassify"

    return None


def get_equity_component_type(acc: Account) -> Optional[str]:
    """Classify an equity account into its IFRS component type.

    Args:
        acc: Account model instance

    Returns:
        One of: "share_capital", "share_premium", "reserves", "oci",
        "retained_earnings", "treasury_shares", "share_based_payments", or None
    """
    if not acc or acc.root_type != AccountType.EQUITY:
        return None

    acc_type = acc.account_type
    acc_name_lower = (acc.account_name or "").lower()

    # Check account type first
    if acc_type in SHARE_CAPITAL_TYPES:
        return "share_capital"
    if acc_type in SHARE_PREMIUM_TYPES:
        return "share_premium"
    if acc_type in TREASURY_SHARE_TYPES:
        return "treasury_shares"
    if acc_type in OCI_RESERVE_TYPES or acc_type in OCI_MAY_RECLASSIFY_TYPES or acc_type in OCI_NOT_RECLASSIFY_TYPES:
        return "oci"
    if acc_type in RETAINED_EARNINGS_TYPES:
        return "retained_earnings"
    if acc_type in SHARE_BASED_PAYMENT_TYPES:
        return "share_based_payments"
    if acc_type in RESERVE_TYPES:
        return "reserves"

    # Fall back to name-based classification
    if any(kw in acc_name_lower for kw in ["share capital", "common stock", "capital stock"]):
        return "share_capital"
    if any(kw in acc_name_lower for kw in ["share premium", "additional paid"]):
        return "share_premium"
    if any(kw in acc_name_lower for kw in ["treasury", "own shares"]):
        return "treasury_shares"
    if any(kw in acc_name_lower for kw in ["oci", "comprehensive income", "hedge", "translation", "revaluation"]):
        return "oci"
    if any(kw in acc_name_lower for kw in ["retained", "accumulated profit", "accumulated loss"]):
        return "retained_earnings"
    if any(kw in acc_name_lower for kw in ["share based", "stock compensation", "esop"]):
        return "share_based_payments"
    if "reserve" in acc_name_lower:
        return "reserves"

    return "retained_earnings"  # Default for unclassified equity


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
