"""Account utility functions for accounting services.

These functions provide classification and lookup utilities for Account models.
They are used by reports and other services for consistent account handling.
"""
from __future__ import annotations

import threading
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import Account, AccountType, GLEntry

if TYPE_CHECKING:
    pass

__all__ = [
    # Core account type classifications
    "ASSET_ACCOUNT_TYPES",
    "LIABILITY_ACCOUNT_TYPES",
    "COGS_ACCOUNT_TYPES",
    "COGS_ACCOUNT_KEYWORDS",
    "FINANCE_INCOME_TYPES",
    "FINANCE_COST_TYPES",
    "TAX_EXPENSE_TYPES",
    # Operating expense classifications
    "OPERATING_EXPENSE_TYPES",
    # Current vs Non-Current classifications (GAAP/IFRS)
    "CURRENT_ASSET_TYPES",
    "NON_CURRENT_ASSET_TYPES",
    "CURRENT_LIABILITY_TYPES",
    "NON_CURRENT_LIABILITY_TYPES",
    # Equity component classifications (IFRS)
    "SHARE_CAPITAL_TYPES",
    "SHARE_PREMIUM_TYPES",
    "RESERVE_TYPES",
    "TREASURY_SHARE_TYPES",
    "OCI_RESERVE_TYPES",
    "RETAINED_EARNINGS_TYPES",
    # OCI reclassification (IAS 1)
    "OCI_MAY_RECLASSIFY_TYPES",
    "OCI_NOT_RECLASSIFY_TYPES",
    # IFRS 16 - Lease accounting
    "RIGHT_OF_USE_ASSET_TYPES",
    "LEASE_LIABILITY_TYPES",
    # IAS 12 - Deferred tax
    "DEFERRED_TAX_ASSET_TYPES",
    "DEFERRED_TAX_LIABILITY_TYPES",
    # IAS 37 - Provisions
    "PROVISION_TYPES",
    # IFRS 2 - Share-based payments
    "SHARE_BASED_PAYMENT_TYPES",
    # Depreciation/Amortization
    "DEPRECIATION_TYPES",
    "AMORTIZATION_TYPES",
    # Cache functions
    "get_accounts_by_erpnext_id",
    "invalidate_accounts_cache",
    # Account classification functions
    "get_effective_root_type",
    "is_cogs_account",
    "is_finance_income_account",
    "is_finance_cost_account",
    "is_tax_expense_account",
    "is_depreciation_account",
    "is_lease_asset_account",
    "is_lease_liability_account",
    "is_deferred_tax_asset_account",
    "is_deferred_tax_liability_account",
    "is_provision_account",
    "is_share_based_payment_account",
    "classify_oci_account",
    "get_equity_component_type",
    # Balance helpers
    "get_account_balances",
    "gl_ar_ap_balances",
    # Serialization
    "serialize_account",
    "serialize_gl_entry",
    "decimal_to_float",
]

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
# Account Type Classifications
# =============================================================================

# Core classifications
ASSET_ACCOUNT_TYPES = {"Receivable", "Bank", "Cash", "Fixed Asset", "Stock", "Current Asset"}
LIABILITY_ACCOUNT_TYPES = {"Payable", "Current Liability"}
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

# =============================================================================
# Account Cache
# =============================================================================

_accounts_cache: Optional[Dict[str, Account]] = None
_accounts_cache_time: Optional[datetime] = None
_accounts_cache_lock = threading.RLock()
_ACCOUNTS_CACHE_TTL_SECONDS = 300  # 5 minutes


def get_accounts_by_erpnext_id(db: Session, force_refresh: bool = False) -> Dict[str, Account]:
    """Get all accounts indexed by erpnext_id with caching.

    This function caches the Account table lookup to avoid repeated full table scans
    in report generation. The cache is module-level and refreshes every 5 minutes
    or when force_refresh is True.

    Thread-safe: Uses RLock to prevent race conditions during cache refresh.

    Args:
        db: Database session
        force_refresh: If True, bypass cache and reload from database

    Returns:
        Dict mapping erpnext_id to Account objects
    """
    global _accounts_cache, _accounts_cache_time

    now = datetime.now()

    # Quick check without lock (double-checked locking pattern)
    if (
        not force_refresh
        and _accounts_cache is not None
        and _accounts_cache_time is not None
        and (now - _accounts_cache_time).total_seconds() < _ACCOUNTS_CACHE_TTL_SECONDS
    ):
        return _accounts_cache

    # Acquire lock for cache refresh
    with _accounts_cache_lock:
        # Re-check after acquiring lock (another thread may have refreshed)
        if (
            not force_refresh
            and _accounts_cache is not None
            and _accounts_cache_time is not None
            and (now - _accounts_cache_time).total_seconds() < _ACCOUNTS_CACHE_TTL_SECONDS
        ):
            return _accounts_cache

        # Refresh cache
        _accounts_cache = {
            acc.erpnext_id: acc
            for acc in db.query(Account).all()
            if acc.erpnext_id
        }
        _accounts_cache_time = now
        return _accounts_cache


def invalidate_accounts_cache() -> None:
    """Invalidate the accounts cache.

    Call this after any Account write operations (create, update, delete).
    Thread-safe: Uses lock to prevent race conditions.
    """
    global _accounts_cache, _accounts_cache_time
    with _accounts_cache_lock:
        _accounts_cache = None
        _accounts_cache_time = None


# =============================================================================
# Account Classification Functions
# =============================================================================

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
    return any(kw in acc_name_lower for kw in ["income tax", "tax expense", "corporation tax"])


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


# =============================================================================
# Balance Helper Functions
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


def gl_ar_ap_balances(db: Session, as_of: date) -> Dict[str, float]:
    """Return GL balances for AR/AP control accounts.

    Credits minus debits for liabilities, debits minus credits for assets.

    Args:
        db: Database session
        as_of: Date to calculate balances as of

    Returns:
        Dict with 'ar' and 'ap' totals
    """
    accounts = get_accounts_by_erpnext_id(db)

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
        "remarks": getattr(entry, "remarks", None),
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
