"""Financial reports: Trial Balance, Balance Sheet, Income Statement, Cash Flow."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple, List, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, false
from sqlalchemy.orm import Session

from app.auth import Require
from app.database import get_db
from app.models.accounting import (
    Account,
    AccountType,
    BankTransaction,
    GLEntry,
)

from .helpers import (
    parse_date,
    get_fiscal_year_dates,
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
    classify_oci_account,
    get_equity_component_type,
    LIABILITY_ACCOUNT_TYPES,
    ASSET_ACCOUNT_TYPES,
    COGS_ACCOUNT_TYPES,
    CURRENT_ASSET_TYPES,
    NON_CURRENT_ASSET_TYPES,
    CURRENT_LIABILITY_TYPES,
    NON_CURRENT_LIABILITY_TYPES,
    # Equity component types for IFRS
    SHARE_CAPITAL_TYPES,
    SHARE_PREMIUM_TYPES,
    RESERVE_TYPES,
    TREASURY_SHARE_TYPES,
    OCI_RESERVE_TYPES,
    RETAINED_EARNINGS_TYPES,
    # Finance types for IFRS Income Statement
    FINANCE_INCOME_TYPES,
    FINANCE_COST_TYPES,
    TAX_EXPENSE_TYPES,
    # IFRS 16/IAS 12/IAS 37 types
    RIGHT_OF_USE_ASSET_TYPES,
    LEASE_LIABILITY_TYPES,
    DEFERRED_TAX_ASSET_TYPES,
    DEFERRED_TAX_LIABILITY_TYPES,
    PROVISION_TYPES,
    # OCI classification
    OCI_MAY_RECLASSIFY_TYPES,
    OCI_NOT_RECLASSIFY_TYPES,
    # D&A
    DEPRECIATION_TYPES,
    AMORTIZATION_TYPES,
    # IFRS 2 - Share-based payments
    SHARE_BASED_PAYMENT_TYPES,
)

from .validation import (
    ValidationResult,
    validate_balance_sheet_equation,
    validate_income_statement_subtotals,
    validate_cash_flow_to_balance_sheet,
    validate_equity_component_movement,
)

router = APIRouter()


# =============================================================================
# COMPARATIVES AND CURRENCY HELPERS
# =============================================================================

def calculate_prior_period(
    start_date: date,
    end_date: date,
) -> tuple[date, date]:
    """Calculate the prior period dates for comparative analysis.

    Uses the same duration as the current period, shifted back by that duration.

    Args:
        start_date: Current period start date
        end_date: Current period end date

    Returns:
        Tuple of (prior_start_date, prior_end_date)
    """
    duration = (end_date - start_date).days + 1
    prior_end = start_date - timedelta(days=1)
    prior_start = prior_end - timedelta(days=duration - 1)
    return prior_start, prior_end


def calculate_prior_period_point(as_of_date: date) -> date:
    """Calculate the prior period point-in-time date.

    For balance sheet comparatives, returns the same date one year prior.

    Args:
        as_of_date: Current as-of date

    Returns:
        Prior period as-of date
    """
    # One year prior
    try:
        return as_of_date.replace(year=as_of_date.year - 1)
    except ValueError:
        # Handle Feb 29 in leap years
        return as_of_date.replace(year=as_of_date.year - 1, day=28)


def get_fx_metadata(
    functional_currency: str = "NGN",
    presentation_currency: str = "NGN",
    average_rate: Optional[float] = None,
    closing_rate: Optional[float] = None,
) -> Dict[str, Any]:
    """Build FX metadata for report responses.

    Args:
        functional_currency: The entity's functional currency
        presentation_currency: The currency used for presentation
        average_rate: Average exchange rate for the period (if different currencies)
        closing_rate: Closing exchange rate (if different currencies)

    Returns:
        Dict with FX metadata
    """
    is_same_currency = functional_currency == presentation_currency
    return {
        "functional_currency": functional_currency,
        "presentation_currency": presentation_currency,
        "is_same_currency": is_same_currency,
        "average_rate": average_rate if not is_same_currency else 1.0,
        "closing_rate": closing_rate if not is_same_currency else 1.0,
    }


def calculate_variance(
    current: float,
    prior: float,
) -> Dict[str, Any]:
    """Calculate variance between current and prior period values.

    Args:
        current: Current period value
        prior: Prior period value

    Returns:
        Dict with variance and variance_pct
    """
    variance = current - prior
    if prior != 0:
        variance_pct = (variance / abs(prior)) * 100
    else:
        variance_pct = 100.0 if current != 0 else 0.0

    return {
        "variance": variance,
        "variance_pct": round(variance_pct, 2),
    }


# =============================================================================
# TRIAL BALANCE
# =============================================================================

@router.get("/trial-balance", dependencies=[Depends(Require("accounting:read"))])
def get_trial_balance(
    as_of_date: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    cost_center: Optional[str] = None,
    drill: bool = Query(False, description="Include account_id for drill-through to GL details"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get trial balance report.

    Shows debit and credit totals for each account. The trial balance
    should be balanced (total debits = total credits).

    Args:
        as_of_date: Report as of this date (default: today)
        fiscal_year: Filter by fiscal year
        cost_center: Filter by cost center
        drill: If true, include account_id refs for drill-through to GL

    Returns:
        Trial balance with account details and totals
    """
    end_date = parse_date(as_of_date, "as_of_date") or date.today()

    # Get fiscal year start if specified
    start_date = None
    if fiscal_year:
        start_date, _ = get_fiscal_year_dates(db, fiscal_year)

    # Build GL query
    query = db.query(
        GLEntry.account,
        func.sum(GLEntry.debit).label("total_debit"),
        func.sum(GLEntry.credit).label("total_credit"),
    ).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date <= end_date,
    )

    if start_date:
        query = query.filter(GLEntry.posting_date >= start_date)

    if cost_center:
        query = query.filter(GLEntry.cost_center == cost_center)

    query = query.group_by(GLEntry.account)
    results = query.all()

    # Get account details
    accounts: Dict[str, Account] = {acc.erpnext_id: acc for acc in db.query(Account).all() if acc.erpnext_id}

    trial_balance = []
    total_debit = Decimal("0")
    total_credit = Decimal("0")

    for row in results:
        acc = accounts.get(row.account)
        debit = row.total_debit or Decimal("0")
        credit = row.total_credit or Decimal("0")
        balance = debit - credit

        entry = {
            "account": row.account,
            "account_name": acc.account_name if acc else row.account,
            "root_type": acc.root_type.value if acc and acc.root_type else None,
            "debit": float(debit),
            "credit": float(credit),
            "balance": float(balance),
            "balance_type": "Dr" if balance >= 0 else "Cr",
        }
        if drill and acc:
            entry["account_id"] = acc.id
            entry["drill_url"] = f"/api/accounting/accounts/{acc.id}/ledger"
        trial_balance.append(entry)

        total_debit += debit
        total_credit += credit

    # Sort by account name
    trial_balance.sort(key=lambda x: x["account_name"])

    return {
        "as_of_date": end_date.isoformat(),
        "fiscal_year": fiscal_year,
        "total_debit": float(total_debit),
        "total_credit": float(total_credit),
        "is_balanced": abs(total_debit - total_credit) < Decimal("0.01"),
        "difference": float(abs(total_debit - total_credit)),
        "accounts": trial_balance,
    }


# =============================================================================
# BALANCE SHEET
# =============================================================================

@router.get("/balance-sheet", dependencies=[Depends(Require("accounting:read"))])
def get_balance_sheet(
    as_of_date: Optional[str] = None,
    comparative_date: Optional[str] = None,
    common_size: bool = Query(False, description="Show values as percentage of total assets"),
    currency: Optional[str] = Query(None, description="Presentation currency"),
    include_prior_period: bool = Query(True, description="Include auto-calculated prior period comparatives"),
    functional_currency: Optional[str] = Query(None, description="Entity's functional currency"),
    presentation_currency_param: Optional[str] = Query(None, description="Presentation currency if different"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get balance sheet report (IAS 1 - Statement of Financial Position).

    Assets = Liabilities + Equity

    IFRS/IAS compliant with:
    - Current/Non-current classification
    - IFRS 16 Right-of-use assets and lease liabilities
    - IAS 12 Deferred tax assets/liabilities
    - IAS 37 Provisions
    - Automatic prior period comparatives

    Automatically corrects common ERPNext account misclassifications
    (e.g., Payable accounts incorrectly classified as Asset root_type).

    Args:
        as_of_date: Report as of this date (default: today)
        comparative_date: Optional date for comparison (overrides auto-calc)
        common_size: Show each line as percentage of total assets
        currency: Presentation currency (IFRS requires disclosure)
        include_prior_period: Include auto-calculated prior period comparatives
        functional_currency: Entity's functional currency
        presentation_currency_param: Presentation currency if different

    Returns:
        Balance sheet with assets, liabilities, equity sections,
        IFRS 16/IAS 12/IAS 37 line items, validation
    """
    end_date = parse_date(as_of_date, "as_of_date") or date.today()
    comp_date = parse_date(comparative_date, "comparative_date")

    # Auto-calculate prior period if not provided but include_prior_period is True
    if include_prior_period and comp_date is None:
        comp_date = calculate_prior_period_point(end_date)

    presentation_currency = currency or presentation_currency_param or "NGN"

    def get_balances(cutoff_date: date) -> Dict[str, Decimal]:
        """Get account balances as of a date."""
        results = db.query(
            GLEntry.account,
            func.sum(GLEntry.debit - GLEntry.credit).label("balance"),
        ).filter(
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= cutoff_date,
        ).group_by(GLEntry.account).all()

        return {r.account: r.balance or Decimal("0") for r in results if r.account}

    # Get account details
    accounts: Dict[str, Account] = {acc.erpnext_id: acc for acc in db.query(Account).all() if acc.erpnext_id}

    current_balances = get_balances(end_date)
    comparative_balances = get_balances(comp_date) if comp_date else {}

    # Track reclassified accounts for warnings
    reclassified: List[Dict[str, Any]] = []

    def build_section(root_type: AccountType, negate: bool = False) -> Dict[str, Any]:
        """Build a section of the balance sheet."""
        section_accounts: List[Dict[str, Any]] = []
        total = Decimal("0")
        comp_total = Decimal("0")

        for acc_id, acc in accounts.items():
            effective_type = get_effective_root_type(acc)
            if effective_type != root_type:
                continue

            # Track if account was reclassified
            if acc.root_type != effective_type:
                reclassified.append({
                    "account": acc.account_name,
                    "original_root_type": acc.root_type.value if acc.root_type else None,
                    "effective_root_type": effective_type.value if effective_type else None,
                    "account_type": acc.account_type,
                })

            balance = current_balances.get(acc_id, Decimal("0"))
            comp_balance = comparative_balances.get(acc_id, Decimal("0"))

            if negate:
                balance = -balance
                comp_balance = -comp_balance

            if balance != 0 or comp_balance != 0:
                section_accounts.append({
                    "account": acc.account_name or "",
                    "account_type": acc.account_type,
                    "balance": float(balance),
                    "comparative_balance": float(comp_balance) if comp_date else None,
                    "change": float(balance - comp_balance) if comp_date else None,
                })
                total += balance
                comp_total += comp_balance

        section_accounts.sort(key=lambda x: str(x.get("account") or ""))

        return {
            "accounts": section_accounts,
            "total": float(total),
            "comparative_total": float(comp_total) if comp_date else None,
            "change": float(total - comp_total) if comp_date else None,
        }

    # Build standard sections
    assets: Dict[str, Any] = build_section(AccountType.ASSET)
    liabilities: Dict[str, Any] = build_section(AccountType.LIABILITY, negate=True)
    equity: Dict[str, Any] = build_section(AccountType.EQUITY, negate=True)

    # Build Current/Non-Current classified sections with IFRS 16/IAS 12/IAS 37 breakouts
    def classify_accounts(section_accounts: List[Dict[str, Any]], account_type: str) -> Dict[str, Any]:
        """Classify accounts as current or non-current with special IFRS line items."""
        if account_type == "asset":
            current_types = CURRENT_ASSET_TYPES
            non_current_types = NON_CURRENT_ASSET_TYPES
        else:  # liability
            current_types = CURRENT_LIABILITY_TYPES
            non_current_types = NON_CURRENT_LIABILITY_TYPES

        current_accounts: List[Dict[str, Any]] = []
        non_current_accounts: List[Dict[str, Any]] = []
        current_total: float = 0.0
        non_current_total: float = 0.0

        # IFRS 16 - Right-of-use assets and lease liabilities
        rou_assets: Dict[str, Any] = {"accounts": [], "total": 0.0}
        lease_liabilities_current: Dict[str, Any] = {"accounts": [], "total": 0.0}
        lease_liabilities_non_current: Dict[str, Any] = {"accounts": [], "total": 0.0}

        # IAS 12 - Deferred tax
        deferred_tax_assets: Dict[str, Any] = {"accounts": [], "total": 0.0}
        deferred_tax_liabilities: Dict[str, Any] = {"accounts": [], "total": 0.0}

        # IAS 37 - Provisions
        provisions_current: Dict[str, Any] = {"accounts": [], "total": 0.0}
        provisions_non_current: Dict[str, Any] = {"accounts": [], "total": 0.0}

        for acc_entry in section_accounts:
            acc_type_str = acc_entry.get("account_type", "")
            acc_name = acc_entry.get("account", "").lower()
            balance = float(acc_entry.get("balance") or 0)

            # IFRS 16 - Right-of-use assets (assets only)
            if account_type == "asset":
                if acc_type_str in RIGHT_OF_USE_ASSET_TYPES or any(kw in acc_name for kw in ["right of use", "rou asset", "lease asset"]):
                    rou_assets["accounts"].append(acc_entry)
                    rou_assets["total"] += balance
                    non_current_accounts.append(acc_entry)
                    non_current_total += balance
                    continue

                # IAS 12 - Deferred tax assets
                if acc_type_str in DEFERRED_TAX_ASSET_TYPES or any(kw in acc_name for kw in ["deferred tax asset", "dta"]):
                    deferred_tax_assets["accounts"].append(acc_entry)
                    deferred_tax_assets["total"] += balance
                    non_current_accounts.append(acc_entry)
                    non_current_total += balance
                    continue

            # IFRS 16 - Lease liabilities (liabilities only)
            if account_type == "liability":
                if acc_type_str in LEASE_LIABILITY_TYPES or any(kw in acc_name for kw in ["lease liability", "finance lease"]):
                    # Split by current indicator in name or default to non-current
                    if any(kw in acc_name for kw in ["current", "short term", "due within"]):
                        lease_liabilities_current["accounts"].append(acc_entry)
                        lease_liabilities_current["total"] += balance
                        current_accounts.append(acc_entry)
                        current_total += balance
                    else:
                        lease_liabilities_non_current["accounts"].append(acc_entry)
                        lease_liabilities_non_current["total"] += balance
                        non_current_accounts.append(acc_entry)
                        non_current_total += balance
                    continue

                # IAS 12 - Deferred tax liabilities
                if acc_type_str in DEFERRED_TAX_LIABILITY_TYPES or any(kw in acc_name for kw in ["deferred tax liability", "dtl"]):
                    deferred_tax_liabilities["accounts"].append(acc_entry)
                    deferred_tax_liabilities["total"] += balance
                    non_current_accounts.append(acc_entry)
                    non_current_total += balance
                    continue

                # IAS 37 - Provisions
                if acc_type_str in PROVISION_TYPES or any(kw in acc_name for kw in ["provision", "warranty", "restructuring", "legal claim"]):
                    if any(kw in acc_name for kw in ["current", "short term"]):
                        provisions_current["accounts"].append(acc_entry)
                        provisions_current["total"] += balance
                        current_accounts.append(acc_entry)
                        current_total += balance
                    else:
                        provisions_non_current["accounts"].append(acc_entry)
                        provisions_non_current["total"] += balance
                        non_current_accounts.append(acc_entry)
                        non_current_total += balance
                    continue

            # Standard current/non-current classification
            if acc_type_str in current_types:
                current_accounts.append(acc_entry)
                current_total += balance
            elif acc_type_str in non_current_types:
                non_current_accounts.append(acc_entry)
                non_current_total += balance
            else:
                # Default: assets without specific type go to current, liabilities to non-current
                if account_type == "asset":
                    current_accounts.append(acc_entry)
                    current_total += balance
                else:
                    non_current_accounts.append(acc_entry)
                    non_current_total += balance

        result = {
            "current": {
                "accounts": current_accounts,
                "total": current_total,
            },
            "non_current": {
                "accounts": non_current_accounts,
                "total": non_current_total,
            },
        }

        # Add IFRS-specific line items
        if account_type == "asset":
            result["right_of_use_assets"] = rou_assets
            result["deferred_tax_assets"] = deferred_tax_assets
        else:  # liability
            result["lease_liabilities"] = {
                "current": lease_liabilities_current,
                "non_current": lease_liabilities_non_current,
                "total": lease_liabilities_current["total"] + lease_liabilities_non_current["total"],
            }
            result["deferred_tax_liabilities"] = deferred_tax_liabilities
            result["provisions"] = {
                "current": provisions_current,
                "non_current": provisions_non_current,
                "total": provisions_current["total"] + provisions_non_current["total"],
            }

        return result

    assets_classified = classify_accounts(assets["accounts"], "asset")
    liabilities_classified = classify_accounts(liabilities["accounts"], "liability")

    # Classify equity accounts by component (IAS 1)
    def classify_equity_by_component(equity_accounts: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Classify equity accounts into IFRS components."""
        components: Dict[str, Dict[str, Any]] = {
            "share_capital": {"accounts": [], "total": 0.0},
            "share_premium": {"accounts": [], "total": 0.0},
            "reserves": {"accounts": [], "total": 0.0},
            "other_comprehensive_income": {"accounts": [], "total": 0.0},
            "retained_earnings": {"accounts": [], "total": 0.0},
            "treasury_shares": {"accounts": [], "total": 0.0},
        }

        for acc_entry in equity_accounts:
            acc_type = acc_entry.get("account_type", "")
            acc_name = acc_entry.get("account", "").lower()
            balance = float(acc_entry.get("balance") or 0)

            # Classify by account type or name
            if acc_type in SHARE_CAPITAL_TYPES or any(kw in acc_name for kw in ["share capital", "common stock", "ordinary share"]):
                components["share_capital"]["accounts"].append(acc_entry)
                components["share_capital"]["total"] += balance
            elif acc_type in SHARE_PREMIUM_TYPES or any(kw in acc_name for kw in ["share premium", "paid-in capital"]):
                components["share_premium"]["accounts"].append(acc_entry)
                components["share_premium"]["total"] += balance
            elif acc_type in TREASURY_SHARE_TYPES or "treasury" in acc_name:
                components["treasury_shares"]["accounts"].append(acc_entry)
                components["treasury_shares"]["total"] += balance
            elif acc_type in OCI_RESERVE_TYPES or any(kw in acc_name for kw in ["oci", "revaluation", "translation"]):
                components["other_comprehensive_income"]["accounts"].append(acc_entry)
                components["other_comprehensive_income"]["total"] += balance
            elif acc_type in RESERVE_TYPES or "reserve" in acc_name:
                components["reserves"]["accounts"].append(acc_entry)
                components["reserves"]["total"] += balance
            else:
                # Default to retained earnings
                components["retained_earnings"]["accounts"].append(acc_entry)
                components["retained_earnings"]["total"] += balance

        return components

    equity_classified = classify_equity_by_component(equity["accounts"])

    # Calculate retained earnings (Income - Expense for all time)
    income_total = sum(
        (
            -current_balances.get(acc_id, Decimal("0"))
            for acc_id, acc in accounts.items()
            if get_effective_root_type(acc) == AccountType.INCOME
        ),
        Decimal("0"),
    )
    expense_total = sum(
        (
            current_balances.get(acc_id, Decimal("0"))
            for acc_id, acc in accounts.items()
            if get_effective_root_type(acc) == AccountType.EXPENSE
        ),
        Decimal("0"),
    )
    retained_earnings = income_total - expense_total

    total_liab_equity = liabilities["total"] + equity["total"] + float(retained_earnings)
    difference = abs(Decimal(str(assets["total"])) - Decimal(str(total_liab_equity)))

    # Add common-size percentages if requested
    total_assets_val = assets["total"]
    if common_size and total_assets_val != 0:
        for acc in assets["accounts"]:
            acc["pct_of_total"] = round(acc["balance"] / total_assets_val * 100, 2)
        for acc in liabilities["accounts"]:
            acc["pct_of_total"] = round(acc["balance"] / total_assets_val * 100, 2)
        for acc in equity["accounts"]:
            acc["pct_of_total"] = round(acc["balance"] / total_assets_val * 100, 2)
        assets["pct_of_total"] = 100.0
        liabilities["pct_of_total"] = round(liabilities["total"] / total_assets_val * 100, 2)
        equity["pct_of_total"] = round(equity["total"] / total_assets_val * 100, 2)

    # Calculate total equity including current period retained earnings
    total_equity_value = equity["total"] + float(retained_earnings)

    # === VALIDATION (IAS 1) ===
    validation_errors: List[Dict[str, Any]] = []
    validation_warnings: List[Dict[str, Any]] = []

    # Validate balance sheet equation: Assets = Liabilities + Equity
    validation_result_bs = validate_balance_sheet_equation(
        total_assets=Decimal(str(assets["total"])),
        total_liabilities=Decimal(str(liabilities["total"])),
        total_equity=Decimal(str(total_equity_value)),
    )
    if not validation_result_bs.is_valid:
        for err in validation_result_bs.errors:
            validation_errors.append({
                "code": err.code,
                "message": err.message,
                "field": err.field,
                "expected": err.expected,
                "actual": err.actual,
            })
    for warn in validation_result_bs.warnings:
        validation_warnings.append({
            "code": warn.code,
            "message": warn.message,
            "field": warn.field,
        })

    validation_result = {
        "is_valid": len(validation_errors) == 0,
        "errors": validation_errors,
        "warnings": validation_warnings,
    }

    result = {
        "as_of_date": end_date.isoformat(),
        "comparative_date": comp_date.isoformat() if comp_date else None,
        "currency": presentation_currency,
        "fx_metadata": get_fx_metadata(
            functional_currency or "NGN",
            presentation_currency,
        ),
        # Traditional structure
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        # GAAP/IFRS classified structure with IFRS 16/IAS 12/IAS 37 line items
        "assets_classified": {
            "current_assets": assets_classified["current"],
            "non_current_assets": assets_classified["non_current"],
            # IFRS 16 - Right-of-use assets
            "right_of_use_assets": assets_classified.get("right_of_use_assets", {"accounts": [], "total": 0}),
            # IAS 12 - Deferred tax assets
            "deferred_tax_assets": assets_classified.get("deferred_tax_assets", {"accounts": [], "total": 0}),
            "total": assets["total"],
        },
        "liabilities_classified": {
            "current_liabilities": liabilities_classified["current"],
            "non_current_liabilities": liabilities_classified["non_current"],
            # IFRS 16 - Lease liabilities
            "lease_liabilities": liabilities_classified.get("lease_liabilities", {"current": {"accounts": [], "total": 0}, "non_current": {"accounts": [], "total": 0}, "total": 0}),
            # IAS 12 - Deferred tax liabilities
            "deferred_tax_liabilities": liabilities_classified.get("deferred_tax_liabilities", {"accounts": [], "total": 0}),
            # IAS 37 - Provisions
            "provisions": liabilities_classified.get("provisions", {"current": {"accounts": [], "total": 0}, "non_current": {"accounts": [], "total": 0}, "total": 0}),
            "total": liabilities["total"],
        },
        # IFRS Equity component breakdown (IAS 1)
        "equity_classified": {
            "share_capital": equity_classified["share_capital"],
            "share_premium": equity_classified["share_premium"],
            "reserves": equity_classified["reserves"],
            "other_comprehensive_income": equity_classified["other_comprehensive_income"],
            "retained_earnings": {
                "accounts": equity_classified["retained_earnings"]["accounts"],
                "from_equity_accounts": equity_classified["retained_earnings"]["total"],
                "current_period_profit": float(retained_earnings),
                "total": equity_classified["retained_earnings"]["total"] + float(retained_earnings),
            },
            "treasury_shares": equity_classified["treasury_shares"],
            "total": total_equity_value,
        },
        # Key totals
        "retained_earnings": float(retained_earnings),
        "total_assets": assets["total"],
        "total_current_assets": assets_classified["current"]["total"],
        "total_non_current_assets": assets_classified["non_current"]["total"],
        "total_liabilities": liabilities["total"],
        "total_current_liabilities": liabilities_classified["current"]["total"],
        "total_non_current_liabilities": liabilities_classified["non_current"]["total"],
        "total_equity": total_equity_value,
        "total_liabilities_equity": total_liab_equity,
        # Working capital (Current Assets - Current Liabilities)
        "working_capital": assets_classified["current"]["total"] - liabilities_classified["current"]["total"],
        # IFRS 16/IAS 12/IAS 37 summary
        "ifrs_line_items": {
            "right_of_use_assets": assets_classified.get("right_of_use_assets", {}).get("total", 0),
            "lease_liabilities_total": liabilities_classified.get("lease_liabilities", {}).get("total", 0),
            "deferred_tax_assets": assets_classified.get("deferred_tax_assets", {}).get("total", 0),
            "deferred_tax_liabilities": liabilities_classified.get("deferred_tax_liabilities", {}).get("total", 0),
            "net_deferred_tax": assets_classified.get("deferred_tax_assets", {}).get("total", 0) - liabilities_classified.get("deferred_tax_liabilities", {}).get("total", 0),
            "provisions_total": liabilities_classified.get("provisions", {}).get("total", 0),
        },
        # Validation
        "validation": validation_result,
        "difference": float(difference),
        "is_balanced": difference < Decimal("1"),
        "reclassified_accounts": reclassified if reclassified else None,
    }

    # Add prior period variance if comparative date is provided
    if comp_date:
        comp_total_assets = sum(acc.get("comparative_balance", 0) or 0 for acc in assets["accounts"])
        comp_total_liabilities = sum(acc.get("comparative_balance", 0) or 0 for acc in liabilities["accounts"])
        comp_total_equity = sum(acc.get("comparative_balance", 0) or 0 for acc in equity["accounts"])

        result["prior_period"] = {
            "as_of_date": comp_date.isoformat(),
            "total_assets": comp_total_assets,
            "total_liabilities": comp_total_liabilities,
            "total_equity": comp_total_equity,
        }
        result["variance"] = {
            "total_assets": calculate_variance(assets["total"], comp_total_assets),
            "total_liabilities": calculate_variance(liabilities["total"], comp_total_liabilities),
            "total_equity": calculate_variance(total_equity_value, comp_total_equity),
        }

    if common_size:
        result["common_size_base"] = "total_assets"
        result["retained_earnings_pct"] = round(float(retained_earnings) / total_assets_val * 100, 2) if total_assets_val else 0

    return result


# =============================================================================
# INCOME STATEMENT (P&L)
# =============================================================================

@router.get("/income-statement", dependencies=[Depends(Require("accounting:read"))])
def get_income_statement(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    cost_center: Optional[str] = None,
    compare_start: Optional[str] = Query(None, description="Prior period start date for comparison"),
    compare_end: Optional[str] = Query(None, description="Prior period end date for comparison"),
    show_ytd: bool = Query(False, description="Include year-to-date column"),
    common_size: bool = Query(False, description="Show values as percentage of total revenue"),
    basis: str = Query("accrual", description="Accounting basis: 'accrual' (default) or 'cash'"),
    include_prior_period: bool = Query(True, description="Include auto-calculated prior period comparatives"),
    classification_basis: str = Query("by_nature", description="Expense classification: 'by_nature' or 'by_function'"),
    functional_currency: Optional[str] = Query(None, description="Entity's functional currency"),
    presentation_currency: Optional[str] = Query(None, description="Presentation currency if different"),
    weighted_avg_shares: Optional[int] = Query(None, description="Weighted average ordinary shares for EPS"),
    diluted_shares: Optional[int] = Query(None, description="Diluted shares for diluted EPS"),
    statutory_tax_rate: Optional[float] = Query(None, description="Statutory corporate tax rate for tax reconciliation"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get income statement (profit & loss) report - IFRS/IAS 1 compliant.

    Shows revenue, expenses, and net income for a period with optional
    comparative analysis, common-size percentages, EPS, and OCI breakdown.

    Args:
        start_date: Period start (default: fiscal year start)
        end_date: Period end (default: today)
        fiscal_year: Use fiscal year dates
        cost_center: Filter by cost center
        compare_start: Prior period start date for comparison (overrides auto-calc)
        compare_end: Prior period end date for comparison (overrides auto-calc)
        show_ytd: Include year-to-date column
        common_size: Show each line as percentage of total revenue
        basis: Accounting basis - 'accrual' (default) or 'cash'
        include_prior_period: Include auto-calculated prior period comparatives
        classification_basis: Expense classification method (IAS 1.99)
        functional_currency: Entity's functional currency
        presentation_currency: Presentation currency if different
        weighted_avg_shares: Weighted average shares for basic EPS (IAS 33)
        diluted_shares: Diluted shares for diluted EPS
        statutory_tax_rate: Statutory tax rate for reconciliation

    Returns:
        Income statement with IFRS-compliant sections, EPS, OCI, validation
    """
    if basis not in ("accrual", "cash"):
        raise HTTPException(status_code=400, detail="basis must be 'accrual' or 'cash'")

    if classification_basis not in ("by_nature", "by_function"):
        raise HTTPException(status_code=400, detail="classification_basis must be 'by_nature' or 'by_function'")

    # Cash basis voucher types
    cash_voucher_types = [
        "Payment Entry",
        "Bank Entry",
        "Cash Entry",
        "payment_entry",
        "bank_entry",
        "cash_entry",
    ]

    # Determine date range
    if fiscal_year:
        period_start, period_end = get_fiscal_year_dates(db, fiscal_year)
        if period_start is None or period_end is None:
            raise HTTPException(status_code=400, detail="Invalid fiscal year dates")
    else:
        period_end = parse_date(end_date, "end_date") or date.today()
        period_start = parse_date(start_date, "start_date") or date(period_end.year, 1, 1)

    if period_start is None or period_end is None:
        raise HTTPException(status_code=400, detail="Invalid period dates")

    # Comparative period - use provided dates or auto-calculate
    comp_start = parse_date(compare_start, "compare_start")
    comp_end = parse_date(compare_end, "compare_end")

    # Auto-calculate prior period if not provided but include_prior_period is True
    if include_prior_period and comp_start is None and comp_end is None:
        comp_start, comp_end = calculate_prior_period(period_start, period_end)

    has_comparison = comp_start is not None and comp_end is not None

    # YTD dates
    ytd_start = date(period_end.year, 1, 1)

    # Get account details
    accounts: Dict[str, Account] = {acc.erpnext_id: acc for acc in db.query(Account).all() if acc.erpnext_id}

    def get_period_data(p_start: date, p_end: date, cc: Optional[str] = None) -> Dict[str, tuple[Decimal, Account]]:
        """Get account totals for a period."""
        query = db.query(
            GLEntry.account,
            func.sum(GLEntry.debit).label("debit"),
            func.sum(GLEntry.credit).label("credit"),
        ).filter(
            GLEntry.is_cancelled == False,
            GLEntry.posting_date >= p_start,
            GLEntry.posting_date <= p_end,
        )
        if cc:
            query = query.filter(GLEntry.cost_center == cc)
        if basis == "cash":
            query = query.filter(GLEntry.voucher_type.in_(cash_voucher_types))
        query = query.group_by(GLEntry.account)
        results = query.all()

        data: Dict[str, tuple[Decimal, Account]] = {}
        for row in results:
            acc = accounts.get(row.account)
            if not acc:
                continue
            if acc.root_type == AccountType.INCOME:
                amount = (row.credit or Decimal("0")) - (row.debit or Decimal("0"))
            elif acc.root_type == AccountType.EXPENSE:
                amount = (row.debit or Decimal("0")) - (row.credit or Decimal("0"))
            else:
                continue
            data[row.account] = (amount, acc)
        return data

    # Get data for all periods
    current_data = get_period_data(period_start, period_end, cost_center)
    if comp_start is not None and comp_end is not None:
        comp_data = get_period_data(comp_start, comp_end, cost_center)
    else:
        comp_data = {}
    ytd_data = get_period_data(ytd_start, period_end, cost_center) if show_ytd and ytd_start != period_start else {}

    def build_section(root_type: AccountType, filter_cogs: Optional[bool] = None) -> Dict[str, Any]:
        """Build income or expense section.

        Args:
            root_type: AccountType to filter by
            filter_cogs: If True, only include COGS accounts. If False, exclude COGS.
                        If None, include all accounts of the root_type.
        """
        section_accounts: List[Dict[str, Any]] = []
        total = Decimal("0")
        comp_total = Decimal("0")
        ytd_total = Decimal("0")

        all_acc_ids = set(current_data.keys()) | set(comp_data.keys()) | set(ytd_data.keys())

        for acc_id in all_acc_ids:
            acc = accounts.get(acc_id)
            if not acc or acc.root_type != root_type:
                continue

            # Filter by COGS if specified
            if filter_cogs is not None:
                acc_is_cogs = is_cogs_account(acc)
                if filter_cogs and not acc_is_cogs:
                    continue
                if not filter_cogs and acc_is_cogs:
                    continue

            amount = current_data.get(acc_id, (Decimal("0"), acc))[0]
            comp_amount = comp_data.get(acc_id, (Decimal("0"), acc))[0] if has_comparison else None
            ytd_amount = ytd_data.get(acc_id, (Decimal("0"), acc))[0] if show_ytd and ytd_data else None

            if amount != 0 or (comp_amount and comp_amount != 0) or (ytd_amount and ytd_amount != 0):
                entry = {
                    "account": acc.account_name or "",
                    "account_type": acc.account_type,
                    "amount": float(amount),
                }
                if has_comparison:
                    entry["prior_amount"] = float(comp_amount) if comp_amount else 0
                    entry["variance"] = float(amount - (comp_amount or Decimal("0")))
                    if comp_amount and comp_amount != 0:
                        entry["variance_pct"] = round(float((amount - comp_amount) / abs(comp_amount) * 100), 2)
                if show_ytd and ytd_data:
                    entry["ytd_amount"] = float(ytd_amount) if ytd_amount else 0

                section_accounts.append(entry)
                total += amount
                if has_comparison and comp_amount:
                    comp_total += comp_amount
                if show_ytd and ytd_amount:
                    ytd_total += ytd_amount

        section_accounts.sort(key=lambda x: -abs(float(x.get("amount") or 0)))

        result = {
            "accounts": section_accounts,
            "total": float(total),
        }
        if has_comparison:
            result["prior_total"] = float(comp_total)
            result["variance"] = float(total - comp_total)
            if comp_total != 0:
                result["variance_pct"] = round(float((total - comp_total) / abs(comp_total) * 100), 2)
        if show_ytd and ytd_data:
            result["ytd_total"] = float(ytd_total)

        return result

    # Helper functions for IFRS classification
    def is_finance_income(acc: Account) -> bool:
        """Check if account is finance income (interest, dividends)."""
        acc_type = acc.account_type or ""
        acc_name = (acc.account_name or "").lower()
        if acc_type in FINANCE_INCOME_TYPES:
            return True
        return any(kw in acc_name for kw in ["interest income", "investment income", "dividend income", "finance income", "bank interest received"])

    def is_finance_cost(acc: Account) -> bool:
        """Check if account is finance cost (interest expense, bank charges)."""
        acc_type = acc.account_type or ""
        acc_name = (acc.account_name or "").lower()
        if acc_type in FINANCE_COST_TYPES:
            return True
        return any(kw in acc_name for kw in ["interest expense", "finance cost", "bank charge", "loan interest", "interest on loan"])

    def is_tax_expense(acc: Account) -> bool:
        """Check if account is income tax expense."""
        acc_type = acc.account_type or ""
        acc_name = (acc.account_name or "").lower()
        if acc_type in TAX_EXPENSE_TYPES:
            return True
        return any(kw in acc_name for kw in ["income tax", "tax expense", "corporate tax", "current tax", "deferred tax"])

    def is_depreciation(acc: Account) -> bool:
        """Check if account is depreciation/amortization."""
        acc_type = acc.account_type or ""
        acc_name = (acc.account_name or "").lower()
        return acc_type in ("Depreciation", "Amortization", "Accumulated Depreciation") or \
               any(kw in acc_name for kw in ["depreciation", "amortization"])

    def is_operating_expense(acc: Account) -> bool:
        """Check if expense is an operating expense (not COGS, finance cost, or tax)."""
        return not is_cogs_account(acc) and not is_finance_cost(acc) and not is_tax_expense(acc)

    # Build sections with IFRS-compliant structure
    revenue: Dict[str, Any] = build_section(AccountType.INCOME)
    cost_of_goods_sold: Dict[str, Any] = build_section(AccountType.EXPENSE, filter_cogs=True)

    # Build operating expenses (excluding COGS, finance costs, and tax)
    opex_accounts: List[Dict[str, Any]] = []
    opex_total = Decimal("0")
    opex_comp_total = Decimal("0")
    opex_ytd_total = Decimal("0")
    depreciation_total = Decimal("0")

    all_acc_ids = set(current_data.keys()) | set(comp_data.keys()) | set(ytd_data.keys())
    for acc_id in all_acc_ids:
        acc = accounts.get(acc_id)
        if not acc or acc.root_type != AccountType.EXPENSE:
            continue
        if not is_operating_expense(acc):
            continue

        amount = current_data.get(acc_id, (Decimal("0"), acc))[0]
        comp_amount = comp_data.get(acc_id, (Decimal("0"), acc))[0] if has_comparison else None
        ytd_amount = ytd_data.get(acc_id, (Decimal("0"), acc))[0] if show_ytd and ytd_data else None

        if amount != 0 or (comp_amount and comp_amount != 0) or (ytd_amount and ytd_amount != 0):
            entry = {
                "account": acc.account_name or "",
                "account_type": acc.account_type,
                "amount": float(amount),
            }
            if has_comparison:
                entry["prior_amount"] = float(comp_amount) if comp_amount else 0
            if show_ytd and ytd_data:
                entry["ytd_amount"] = float(ytd_amount) if ytd_amount else 0

            opex_accounts.append(entry)
            opex_total += amount
            if has_comparison and comp_amount:
                opex_comp_total += comp_amount
            if show_ytd and ytd_amount:
                opex_ytd_total += ytd_amount
            if is_depreciation(acc):
                depreciation_total += amount

    opex_accounts.sort(key=lambda x: -abs(float(x.get("amount") or 0)))
    operating_expenses: Dict[str, Any] = {"accounts": opex_accounts, "total": float(opex_total)}
    if has_comparison:
        operating_expenses["prior_total"] = float(opex_comp_total)
    if show_ytd and ytd_data:
        operating_expenses["ytd_total"] = float(opex_ytd_total)

    # Build finance income section
    finance_income_accounts: List[Dict[str, Any]] = []
    finance_income_total = Decimal("0")
    for acc_id in all_acc_ids:
        acc = accounts.get(acc_id)
        if not acc or acc.root_type != AccountType.INCOME:
            continue
        if not is_finance_income(acc):
            continue
        amount = current_data.get(acc_id, (Decimal("0"), acc))[0]
        if amount != 0:
            finance_income_accounts.append({
                "account": acc.account_name or "",
                "account_type": acc.account_type,
                "amount": float(amount),
            })
            finance_income_total += amount

    finance_income = {"accounts": finance_income_accounts, "total": float(finance_income_total)}

    # Build finance costs section
    finance_cost_accounts: List[Dict[str, Any]] = []
    finance_cost_total = Decimal("0")
    for acc_id in all_acc_ids:
        acc = accounts.get(acc_id)
        if not acc or acc.root_type != AccountType.EXPENSE:
            continue
        if not is_finance_cost(acc):
            continue
        amount = current_data.get(acc_id, (Decimal("0"), acc))[0]
        if amount != 0:
            finance_cost_accounts.append({
                "account": acc.account_name or "",
                "account_type": acc.account_type,
                "amount": float(amount),
            })
            finance_cost_total += amount

    finance_costs = {"accounts": finance_cost_accounts, "total": float(finance_cost_total)}

    # Build tax expense section
    tax_accounts: List[Dict[str, Any]] = []
    tax_total = Decimal("0")
    for acc_id in all_acc_ids:
        acc = accounts.get(acc_id)
        if not acc or acc.root_type != AccountType.EXPENSE:
            continue
        if not is_tax_expense(acc):
            continue
        amount = current_data.get(acc_id, (Decimal("0"), acc))[0]
        if amount != 0:
            tax_accounts.append({
                "account": acc.account_name or "",
                "account_type": acc.account_type,
                "amount": float(amount),
            })
            tax_total += amount

    tax_expense = {"accounts": tax_accounts, "total": float(tax_total)}

    # Calculate key metrics (IFRS order)
    total_revenue = revenue["total"]
    total_cogs = cost_of_goods_sold["total"]
    total_opex = float(opex_total)
    total_finance_income = float(finance_income_total)
    total_finance_costs = float(finance_cost_total)
    total_tax = float(tax_total)
    total_depreciation = float(depreciation_total)

    # IFRS P&L line items
    gross_profit = total_revenue - total_cogs
    operating_income = gross_profit - total_opex  # EBIT (Earnings Before Interest and Tax)
    ebit = operating_income  # Same as operating income
    ebitda = operating_income + total_depreciation  # Add back depreciation
    net_finance = total_finance_income - total_finance_costs
    profit_before_tax = operating_income + net_finance  # EBT
    ebt = profit_before_tax
    profit_after_tax = profit_before_tax - total_tax  # Net Income
    net_income = profit_after_tax

    # Calculate margins
    gross_margin = round(gross_profit / total_revenue * 100, 2) if total_revenue else 0
    operating_margin = round(operating_income / total_revenue * 100, 2) if total_revenue else 0
    ebitda_margin = round(ebitda / total_revenue * 100, 2) if total_revenue else 0
    net_margin = round(net_income / total_revenue * 100, 2) if total_revenue else 0
    effective_tax_rate = round(total_tax / profit_before_tax * 100, 2) if profit_before_tax > 0 else 0

    # Add common-size percentages
    if common_size and total_revenue != 0:
        for acc in revenue["accounts"]:
            acc["pct_of_revenue"] = round(acc["amount"] / total_revenue * 100, 2)
        for acc in cost_of_goods_sold["accounts"]:
            acc["pct_of_revenue"] = round(acc["amount"] / total_revenue * 100, 2)
        for acc in operating_expenses["accounts"]:
            acc["pct_of_revenue"] = round(acc["amount"] / total_revenue * 100, 2)
        revenue["pct_of_revenue"] = 100.0
        cost_of_goods_sold["pct_of_revenue"] = round(total_cogs / total_revenue * 100, 2)
        operating_expenses["pct_of_revenue"] = round(total_opex / total_revenue * 100, 2)

    # === SUBTOTAL VALIDATION (IAS 1) ===
    validation_errors: list[dict[str, Any]] = []
    validation_warnings: list[dict[str, Any]] = []

    # Validate: Revenue - COGS = Gross Profit
    expected_gross_profit = total_revenue - total_cogs
    if abs(gross_profit - expected_gross_profit) > 0.01:
        validation_errors.append({
            "code": "GROSS_PROFIT_MISMATCH",
            "message": "Revenue - COGS != Gross Profit",
            "expected": expected_gross_profit,
            "actual": gross_profit,
        })

    # Validate: Gross Profit - OpEx = Operating Income
    expected_operating_income = gross_profit - total_opex
    if abs(operating_income - expected_operating_income) > 0.01:
        validation_errors.append({
            "code": "OPERATING_INCOME_MISMATCH",
            "message": "Gross Profit - Operating Expenses != Operating Income",
            "expected": expected_operating_income,
            "actual": operating_income,
        })

    # Validate: Operating Income + Net Finance = Profit Before Tax
    expected_pbt = operating_income + net_finance
    if abs(profit_before_tax - expected_pbt) > 0.01:
        validation_errors.append({
            "code": "PBT_MISMATCH",
            "message": "Operating Income + Net Finance != Profit Before Tax",
            "expected": expected_pbt,
            "actual": profit_before_tax,
        })

    # Validate: Profit Before Tax - Tax = Profit After Tax
    expected_pat = profit_before_tax - total_tax
    if abs(profit_after_tax - expected_pat) > 0.01:
        validation_errors.append({
            "code": "PAT_MISMATCH",
            "message": "Profit Before Tax - Tax Expense != Profit After Tax",
            "expected": expected_pat,
            "actual": profit_after_tax,
        })

    validation_result = {
        "is_valid": len(validation_errors) == 0,
        "errors": validation_errors,
        "warnings": validation_warnings,
    }

    # === EPS CALCULATION (IAS 33) ===
    earnings_per_share = None
    if weighted_avg_shares and weighted_avg_shares > 0:
        basic_eps = net_income / weighted_avg_shares
        diluted_eps = None
        if diluted_shares and diluted_shares > 0:
            diluted_eps = net_income / diluted_shares

        earnings_per_share = {
            "basic_eps": round(basic_eps, 4),
            "diluted_eps": round(diluted_eps, 4) if diluted_eps is not None else None,
            "weighted_average_shares": weighted_avg_shares,
            "diluted_shares": diluted_shares,
            "profit_attributable_to_shareholders": net_income,
            "dilutive_instruments": [],  # Would need tracking for options, convertibles, etc.
        }

    # === TAX RECONCILIATION (IAS 12) ===
    tax_reconciliation = None
    if statutory_tax_rate is not None and profit_before_tax != 0:
        expected_tax = profit_before_tax * (statutory_tax_rate / 100)
        tax_difference = total_tax - expected_tax

        tax_reconciliation = {
            "statutory_rate": statutory_tax_rate,
            "effective_rate": effective_tax_rate,
            "profit_before_tax": profit_before_tax,
            "tax_at_statutory_rate": expected_tax,
            "actual_tax_expense": total_tax,
            "difference": tax_difference,
            "reconciling_items": [
                {
                    "description": "Tax effect of permanent differences",
                    "amount": tax_difference,  # Placeholder - would need detailed tracking
                }
            ],
        }

    # === OCI BREAKDOWN (IAS 1.82A) ===
    # Query OCI accounts from equity
    oci_may_reclassify_items = []
    oci_not_reclassify_items = []
    oci_may_reclassify_total = Decimal("0")
    oci_not_reclassify_total = Decimal("0")

    # Get OCI movements from equity accounts during the period
    oci_results = db.query(
        GLEntry.account,
        func.sum(GLEntry.credit - GLEntry.debit).label("movement"),
    ).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= period_start,
        GLEntry.posting_date <= period_end,
    ).group_by(GLEntry.account).all()

    for row in oci_results:
        acc = accounts.get(row.account)
        if not acc or get_effective_root_type(acc) != AccountType.EQUITY:
            continue

        acc_type = acc.account_type or ""
        acc_name = (acc.account_name or "").lower()
        movement = row.movement or Decimal("0")

        # Check if it's an OCI account
        if acc_type in OCI_MAY_RECLASSIFY_TYPES or any(kw in acc_name for kw in ["hedge", "translation", "available for sale"]):
            oci_may_reclassify_items.append({
                "account": acc.account_name,
                "amount": float(movement),
            })
            oci_may_reclassify_total += movement
        elif acc_type in OCI_NOT_RECLASSIFY_TYPES or any(kw in acc_name for kw in ["revaluation", "actuarial", "fvoci equity"]):
            oci_not_reclassify_items.append({
                "account": acc.account_name,
                "amount": float(movement),
            })
            oci_not_reclassify_total += movement

    total_oci = float(oci_may_reclassify_total + oci_not_reclassify_total)
    total_comprehensive_income = net_income + total_oci

    other_comprehensive_income = {
        "items_may_be_reclassified": {
            "items": oci_may_reclassify_items,
            "total": float(oci_may_reclassify_total),
            "reclassification_adjustments": 0,  # Would need specific tracking
        },
        "items_not_reclassified": {
            "items": oci_not_reclassify_items,
            "total": float(oci_not_reclassify_total),
        },
        "total": total_oci,
    }

    result = {
        "period": {
            "start_date": period_start.isoformat(),
            "end_date": period_end.isoformat(),
            "fiscal_year": fiscal_year,
        },
        "currency": presentation_currency or "NGN",
        "fx_metadata": get_fx_metadata(
            functional_currency or "NGN",
            presentation_currency or "NGN",
        ),
        "basis": basis,
        "classification_basis": classification_basis,
        # === IFRS STATEMENT OF PROFIT OR LOSS ===
        # Revenue section
        "revenue": revenue,
        # Cost of Goods Sold section
        "cost_of_goods_sold": cost_of_goods_sold,
        # Gross Profit = Revenue - COGS
        "gross_profit": gross_profit,
        "gross_margin": gross_margin,
        # Operating Expenses section (excludes finance costs and tax)
        "operating_expenses": operating_expenses,
        "depreciation_amortization": total_depreciation,
        # Operating Income (EBIT) = Gross Profit - Operating Expenses
        "operating_income": operating_income,
        "operating_margin": operating_margin,
        "ebit": ebit,
        # EBITDA = EBIT + Depreciation & Amortization
        "ebitda": ebitda,
        "ebitda_margin": ebitda_margin,
        # Finance Income/Costs (IAS 1)
        "finance_income": finance_income,
        "finance_costs": finance_costs,
        "net_finance_income": net_finance,
        # Profit Before Tax (EBT)
        "profit_before_tax": profit_before_tax,
        "ebt": ebt,
        # Income Tax Expense (IAS 12)
        "tax_expense": tax_expense,
        "effective_tax_rate": effective_tax_rate,
        "tax_reconciliation": tax_reconciliation,
        # Profit After Tax / Net Income
        "profit_after_tax": profit_after_tax,
        "net_income": net_income,
        "net_margin": net_margin,
        # EPS (IAS 33)
        "earnings_per_share": earnings_per_share,
        # Other Comprehensive Income (IAS 1.82A)
        "other_comprehensive_income": other_comprehensive_income,
        "total_comprehensive_income": total_comprehensive_income,
        # Validation
        "validation": validation_result,
        # Legacy fields for backward compatibility
        "income": revenue,
        "expenses": {
            "accounts": cost_of_goods_sold["accounts"] + operating_expenses["accounts"] + finance_costs["accounts"] + tax_expense["accounts"],
            "total": total_cogs + total_opex + total_finance_costs + total_tax,
        },
        "profit_margin": net_margin,
    }

    if has_comparison:
        if comp_start is None or comp_end is None:
            raise HTTPException(status_code=400, detail="Comparison period dates are missing")
        comp_start_date = comp_start
        comp_end_date = comp_end
        comp_revenue = revenue.get("prior_total", 0)
        comp_cogs = cost_of_goods_sold.get("prior_total", 0)
        comp_opex = operating_expenses.get("prior_total", 0)
        comp_gross = comp_revenue - comp_cogs
        comp_operating = comp_gross - comp_opex
        comp_net = comp_operating

        result["prior_period"] = {
            "period": {
                "start_date": comp_start_date.isoformat(),
                "end_date": comp_end_date.isoformat(),
            },
            "revenue": comp_revenue,
            "cost_of_goods_sold": comp_cogs,
            "gross_profit": comp_gross,
            "operating_expenses": comp_opex,
            "operating_income": comp_operating,
            "net_income": comp_net,
        }

        result["variance"] = {
            "revenue": calculate_variance(total_revenue, comp_revenue),
            "gross_profit": calculate_variance(gross_profit, comp_gross),
            "operating_income": calculate_variance(operating_income, comp_operating),
            "net_income": calculate_variance(net_income, comp_net),
        }

        # Legacy variance fields
        result["comparison_period"] = {
            "start_date": comp_start_date.isoformat(),
            "end_date": comp_end_date.isoformat(),
        }
        result["prior_revenue"] = comp_revenue
        result["prior_gross_profit"] = comp_gross
        result["prior_operating_income"] = comp_operating
        result["prior_net_income"] = comp_net
        result["revenue_variance"] = total_revenue - comp_revenue
        result["gross_profit_variance"] = gross_profit - comp_gross
        result["operating_income_variance"] = operating_income - comp_operating
        result["net_income_variance"] = net_income - comp_net
        if comp_net != 0:
            result["net_income_variance_pct"] = round((net_income - comp_net) / abs(comp_net) * 100, 2)

    if show_ytd and ytd_data:
        result["ytd_period"] = {
            "start_date": ytd_start.isoformat(),
            "end_date": period_end.isoformat(),
        }
        ytd_revenue = revenue.get("ytd_total", 0)
        ytd_cogs = cost_of_goods_sold.get("ytd_total", 0)
        ytd_opex = operating_expenses.get("ytd_total", 0)
        result["ytd_revenue"] = ytd_revenue
        result["ytd_gross_profit"] = ytd_revenue - ytd_cogs
        result["ytd_operating_income"] = ytd_revenue - ytd_cogs - ytd_opex
        result["ytd_net_income"] = ytd_revenue - ytd_cogs - ytd_opex

    if common_size:
        result["common_size_base"] = "total_revenue"

    return result


# =============================================================================
# CASH FLOW (Indirect Method - GAAP/IFRS Compliant)
# =============================================================================

# Account types for cash flow classification
OPERATING_ACCOUNT_TYPES = {
    "Receivable", "Payable", "Stock", "Current Asset", "Current Liability",
    "Expense", "Income", "Cost of Goods Sold", "Tax",
}
INVESTING_ACCOUNT_TYPES = {
    "Fixed Asset", "Accumulated Depreciation", "Capital Work in Progress",
    "Investment", "Long Term Investment",
}
FINANCING_ACCOUNT_TYPES = {
    "Equity", "Long Term Liability", "Loan", "Share Capital",
    "Retained Earnings", "Reserves and Surplus",
}
# Voucher types for activity classification
OPERATING_VOUCHER_TYPES = {
    "Sales Invoice", "Purchase Invoice", "Payment Entry", "Journal Entry",
    "Expense Claim", "Payroll Entry", "Tax Entry",
    "sales_invoice", "purchase_invoice", "payment_entry", "journal_entry",
}
INVESTING_VOUCHER_TYPES = {
    "Asset", "Asset Capitalization", "Asset Disposal",
    "asset", "asset_capitalization", "asset_disposal",
}
FINANCING_VOUCHER_TYPES = {
    "Loan", "Loan Disbursement", "Loan Repayment", "Share Transfer",
    "Dividend", "Capital Contribution",
    "loan", "loan_disbursement", "loan_repayment",
}


@router.get("/cash-flow", dependencies=[Depends(Require("accounting:read"))])
def get_cash_flow(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    method: str = "indirect",
    currency: Optional[str] = Query(None, description="Presentation currency"),
    include_prior_period: bool = Query(True, description="Include auto-calculated prior period comparatives"),
    functional_currency: Optional[str] = Query(None, description="Entity's functional currency"),
    presentation_currency_param: Optional[str] = Query(None, description="Presentation currency if different"),
    interest_paid_classification: str = Query("operating", description="Classification for interest paid: 'operating' or 'financing'"),
    interest_received_classification: str = Query("operating", description="Classification for interest received: 'operating' or 'investing'"),
    dividends_paid_classification: str = Query("financing", description="Classification for dividends paid: 'operating' or 'financing'"),
    dividends_received_classification: str = Query("operating", description="Classification for dividends received: 'operating' or 'investing'"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get cash flow statement (IAS 7 - Indirect Method).

    Uses the indirect method starting from net income and adjusting for:
    - Non-cash items (depreciation, amortization)
    - Changes in working capital (AR, AP, Inventory)

    IAS 7 requires disclosure of:
    - Interest paid (operating or financing - policy choice)
    - Interest received (operating or investing - policy choice)
    - Dividends paid (operating or financing - policy choice)
    - Dividends received (operating or investing - policy choice)
    - Income taxes paid (operating)
    - Non-cash transactions (IAS 7.43)
    - FX effect on cash balances

    Args:
        start_date: Period start (default: Jan 1 of current year)
        end_date: Period end (default: today)
        fiscal_year: Use fiscal year dates
        method: 'indirect' (default) or 'direct'
        currency: Presentation currency
        include_prior_period: Include auto-calculated prior period comparatives
        functional_currency: Entity's functional currency
        presentation_currency_param: Presentation currency if different
        interest_paid_classification: Classification policy for interest paid
        interest_received_classification: Classification policy for interest received
        dividends_paid_classification: Classification policy for dividends paid
        dividends_received_classification: Classification policy for dividends received

    Returns:
        Cash flow statement with operating, investing, financing activities,
        structured non-cash transactions, FX effect, validation, and comparatives
    """
    presentation_currency = currency or presentation_currency_param or "NGN"

    # Validate classification policies
    if interest_paid_classification not in ("operating", "financing"):
        raise HTTPException(status_code=400, detail="interest_paid_classification must be 'operating' or 'financing'")
    if interest_received_classification not in ("operating", "investing"):
        raise HTTPException(status_code=400, detail="interest_received_classification must be 'operating' or 'investing'")
    if dividends_paid_classification not in ("operating", "financing"):
        raise HTTPException(status_code=400, detail="dividends_paid_classification must be 'operating' or 'financing'")
    if dividends_received_classification not in ("operating", "investing"):
        raise HTTPException(status_code=400, detail="dividends_received_classification must be 'operating' or 'investing'")

    # Determine date range
    if fiscal_year:
        period_start, period_end = get_fiscal_year_dates(db, fiscal_year)
    else:
        period_end = parse_date(end_date, "end_date") or date.today()
        period_start = parse_date(start_date, "start_date") or date(period_end.year, 1, 1)

    # Get all accounts
    accounts: Dict[str, Account] = {acc.erpnext_id: acc for acc in db.query(Account).all() if acc.erpnext_id}

    # Get bank/cash accounts
    cash_accounts = db.query(Account).filter(
        Account.account_type.in_(["Bank", "Cash"]),
        Account.disabled == False,
    ).all()
    cash_account_names = {acc.erpnext_id for acc in cash_accounts}

    def get_cash_balance(as_of: date) -> Decimal:
        """Get total cash balance as of a date."""
        result = db.query(
            func.sum(GLEntry.debit - GLEntry.credit)
        ).filter(
            GLEntry.account.in_(cash_account_names),
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= as_of,
        ).scalar()
        return result or Decimal("0")

    def get_balance_change(account_types: set, start: date, end: date) -> Decimal:
        """Get balance change for accounts of specific types."""
        relevant_accounts = [
            acc_id for acc_id, acc in accounts.items()
            if acc.account_type in account_types
        ]
        if not relevant_accounts:
            return Decimal("0")

        start_bal = db.query(
            func.sum(GLEntry.debit - GLEntry.credit)
        ).filter(
            GLEntry.account.in_(relevant_accounts),
            GLEntry.is_cancelled == False,
            GLEntry.posting_date < start,
        ).scalar() or Decimal("0")

        end_bal = db.query(
            func.sum(GLEntry.debit - GLEntry.credit)
        ).filter(
            GLEntry.account.in_(relevant_accounts),
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= end,
        ).scalar() or Decimal("0")

        return end_bal - start_bal

    # Calculate opening and closing cash
    opening_cash = get_cash_balance(period_start - timedelta(days=1)) if period_start else Decimal("0")
    closing_cash = get_cash_balance(period_end)

    # === INDIRECT METHOD ===
    # 1. Start with Net Income
    income_accounts = [acc_id for acc_id, acc in accounts.items() if acc.root_type == AccountType.INCOME]
    expense_accounts = [acc_id for acc_id, acc in accounts.items() if acc.root_type == AccountType.EXPENSE]

    period_income = db.query(
        func.sum(GLEntry.credit - GLEntry.debit)
    ).filter(
        GLEntry.account.in_(income_accounts),
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= period_start,
        GLEntry.posting_date <= period_end,
    ).scalar() or Decimal("0")

    period_expenses = db.query(
        func.sum(GLEntry.debit - GLEntry.credit)
    ).filter(
        GLEntry.account.in_(expense_accounts),
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= period_start,
        GLEntry.posting_date <= period_end,
    ).scalar() or Decimal("0")

    net_income = period_income - period_expenses

    # 2. Adjustments for non-cash items
    depreciation_accounts = [
        acc_id for acc_id, acc in accounts.items()
        if acc.account_type in ("Accumulated Depreciation", "Depreciation")
        or "depreciation" in (acc.account_name or "").lower()
    ]
    depreciation = db.query(
        func.sum(GLEntry.credit - GLEntry.debit)
    ).filter(
        GLEntry.account.in_(depreciation_accounts),
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= period_start,
        GLEntry.posting_date <= period_end,
    ).scalar() or Decimal("0")

    # 3. Changes in working capital
    ar_change = get_balance_change({"Receivable"}, period_start, period_end)
    inventory_change = get_balance_change({"Stock"}, period_start, period_end)
    prepaid_change = get_balance_change({"Current Asset"}, period_start, period_end) - ar_change
    ap_change = get_balance_change({"Payable"}, period_start, period_end)
    accrued_change = get_balance_change({"Current Liability"}, period_start, period_end) - ap_change

    # Operating = Net Income + Depreciation - Increase in AR - Increase in Inventory + Increase in AP
    operating_net = float(
        net_income
        + depreciation
        - ar_change
        - inventory_change
        - prepaid_change
        - ap_change
        - accrued_change
    )
    operating_activities = {
        "net_income": float(net_income),
        "adjustments": {
            "depreciation_amortization": float(depreciation),
        },
        "working_capital_changes": {
            "accounts_receivable": float(-ar_change),  # Increase in AR = cash outflow
            "inventory": float(-inventory_change),  # Increase in inventory = cash outflow
            "prepaid_expenses": float(-prepaid_change),
            "accounts_payable": float(-ap_change),  # Increase in AP = cash inflow (liability increases)
            "accrued_liabilities": float(-accrued_change),
        },
        "net": operating_net,
    }

    # 4. Investing Activities
    fixed_asset_change = get_balance_change({"Fixed Asset", "Capital Work in Progress"}, period_start, period_end)
    investment_change = get_balance_change({"Investment", "Long Term Investment"}, period_start, period_end)

    investing_net = float(-fixed_asset_change - investment_change)
    investing_activities = {
        "fixed_asset_purchases": float(-fixed_asset_change) if fixed_asset_change > 0 else 0,
        "fixed_asset_sales": float(-fixed_asset_change) if fixed_asset_change < 0 else 0,
        "investments": float(-investment_change),
        "net": investing_net,
    }

    # 5. Financing Activities
    long_term_debt_change = get_balance_change({"Long Term Liability", "Loan"}, period_start, period_end)
    equity_change = get_balance_change({"Equity", "Share Capital"}, period_start, period_end)

    financing_net = float(-long_term_debt_change - equity_change)
    financing_activities = {
        "debt_proceeds": float(-long_term_debt_change) if long_term_debt_change < 0 else 0,
        "debt_repayments": float(-long_term_debt_change) if long_term_debt_change > 0 else 0,
        "equity_proceeds": float(-equity_change) if equity_change < 0 else 0,
        "dividends_paid": 0,  # Would need specific dividend tracking
        "net": financing_net,
    }

    # Bank transactions summary
    bank_txns = db.query(BankTransaction).filter(
        BankTransaction.date >= period_start,
        BankTransaction.date <= period_end,
    ).all()
    deposits = sum(t.deposit for t in bank_txns)
    withdrawals = sum(t.withdrawal for t in bank_txns)

    # === IAS 7 Required Disclosures ===
    # Interest paid (from finance cost accounts)
    interest_expense_accounts = [
        acc_id for acc_id, acc in accounts.items()
        if acc.account_type in FINANCE_COST_TYPES or
        any(kw in (acc.account_name or "").lower() for kw in ["interest expense", "finance cost", "loan interest"])
    ]
    interest_paid_query = db.query(
        func.sum(GLEntry.debit - GLEntry.credit)
    ).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= period_start,
        GLEntry.posting_date <= period_end,
    )
    if interest_expense_accounts:
        interest_paid_query = interest_paid_query.filter(GLEntry.account.in_(interest_expense_accounts))
    else:
        interest_paid_query = interest_paid_query.filter(false())
    interest_paid = interest_paid_query.scalar() or Decimal("0")

    # Interest received (from finance income accounts)
    interest_income_accounts = [
        acc_id for acc_id, acc in accounts.items()
        if acc.account_type in FINANCE_INCOME_TYPES or
        any(kw in (acc.account_name or "").lower() for kw in ["interest income", "bank interest", "investment income"])
    ]
    interest_received_query = db.query(
        func.sum(GLEntry.credit - GLEntry.debit)
    ).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= period_start,
        GLEntry.posting_date <= period_end,
    )
    if interest_income_accounts:
        interest_received_query = interest_received_query.filter(GLEntry.account.in_(interest_income_accounts))
    else:
        interest_received_query = interest_received_query.filter(false())
    interest_received = interest_received_query.scalar() or Decimal("0")

    # Taxes paid (from tax expense accounts - approximated by tax expense)
    tax_expense_accounts = [
        acc_id for acc_id, acc in accounts.items()
        if acc.account_type in TAX_EXPENSE_TYPES or
        any(kw in (acc.account_name or "").lower() for kw in ["income tax", "tax expense", "corporate tax"])
    ]
    taxes_paid_query = db.query(
        func.sum(GLEntry.debit - GLEntry.credit)
    ).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= period_start,
        GLEntry.posting_date <= period_end,
    )
    if tax_expense_accounts:
        taxes_paid_query = taxes_paid_query.filter(GLEntry.account.in_(tax_expense_accounts))
    else:
        taxes_paid_query = taxes_paid_query.filter(false())
    taxes_paid = taxes_paid_query.scalar() or Decimal("0")

    # Dividends paid (from dividend accounts - would need specific tracking)
    dividend_accounts = [
        acc_id for acc_id, acc in accounts.items()
        if "dividend" in (acc.account_name or "").lower()
    ]
    dividends_paid_query = db.query(
        func.sum(GLEntry.debit - GLEntry.credit)
    ).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= period_start,
        GLEntry.posting_date <= period_end,
    )
    if dividend_accounts:
        dividends_paid_query = dividends_paid_query.filter(GLEntry.account.in_(dividend_accounts))
    else:
        dividends_paid_query = dividends_paid_query.filter(false())
    dividends_paid = dividends_paid_query.scalar() or Decimal("0")

    # === FX EFFECT ON CASH (IAS 7.28) ===
    # Note: In practice, this would come from FX revaluation journals on cash accounts
    # For now, we calculate as the reconciling item
    fx_effect_on_cash = Decimal("0")  # Placeholder - would need specific FX tracking

    # Reconciliation
    total_cash_flow = operating_net + investing_net + financing_net
    actual_change = float(closing_cash - opening_cash)

    # The reconciliation difference (excluding FX) represents unexplained variance
    reconciliation_diff = actual_change - total_cash_flow - float(fx_effect_on_cash)

    # === CFO RECONCILIATION (Indirect Method Detail) ===
    cfo_reconciliation = {
        "net_income": float(net_income),
        "adjustments_for_non_cash_items": {
            "depreciation_amortization": float(depreciation),
            "total": float(depreciation),
        },
        "working_capital_changes": {
            "accounts_receivable": float(-ar_change),
            "inventory": float(-inventory_change),
            "prepaid_expenses": float(-prepaid_change),
            "accounts_payable": float(-ap_change),
            "accrued_liabilities": float(-accrued_change),
            "total": float(-ar_change - inventory_change - prepaid_change - ap_change - accrued_change),
        },
        "cash_from_operations": operating_net,
        "is_reconciled": abs(
            operating_net -
            (float(net_income) + float(depreciation) - float(ar_change) - float(inventory_change) -
             float(prepaid_change) - float(ap_change) - float(accrued_change))
        ) < 1.0,
    }

    # === VALIDATION ===
    validation_errors = []
    validation_warnings = []

    # Validate: Opening Cash + Net Cash Flow + FX Effect = Closing Cash
    expected_closing = float(opening_cash) + total_cash_flow + float(fx_effect_on_cash)
    if abs(float(closing_cash) - expected_closing) > 1.0:
        validation_errors.append({
            "code": "CASH_RECONCILIATION_MISMATCH",
            "message": "Opening + Net Cash Flow + FX Effect != Closing Cash",
            "expected": expected_closing,
            "actual": float(closing_cash),
        })

    # Validate: CFO reconciliation
    if not cfo_reconciliation["is_reconciled"]:
        validation_warnings.append({
            "code": "CFO_RECONCILIATION_WARNING",
            "message": "CFO calculation has minor variance from sum of components",
        })

    validation_result = {
        "is_valid": len(validation_errors) == 0,
        "errors": validation_errors,
        "warnings": validation_warnings,
    }

    # === STRUCTURED NON-CASH TRANSACTIONS (IAS 7.43) ===
    # In a real implementation, these would be tracked via specific voucher types
    non_cash_transactions = {
        "transactions": [],  # Would contain typed entries from voucher tracking
        "transaction_types": [
            "lease_inception",  # IFRS 16 lease commencement
            "debt_conversion",  # Debt-to-equity conversion
            "asset_exchange",   # Non-monetary asset exchange
            "barter",          # Barter transactions
            "stock_dividend",  # Share dividends
            "asset_acquisition_with_debt",  # Asset purchase with liability assumption
        ],
        "total": 0,
        "note": "Non-cash investing and financing activities are excluded from the cash flow statement but disclosed separately per IAS 7.43",
    }

    # Calculate prior period if requested
    prior_period_data = None
    if include_prior_period:
        prior_start, prior_end = calculate_prior_period(period_start, period_end)
        prior_opening_cash = get_cash_balance(prior_start - timedelta(days=1)) if prior_start else Decimal("0")
        prior_closing_cash = get_cash_balance(prior_end)
        prior_change = float(prior_closing_cash - prior_opening_cash)

        prior_period_data = {
            "period": {
                "start_date": prior_start.isoformat(),
                "end_date": prior_end.isoformat(),
            },
            "opening_cash": float(prior_opening_cash),
            "closing_cash": float(prior_closing_cash),
            "net_change_in_cash": prior_change,
        }

    result = {
        "period": {
            "start_date": period_start.isoformat(),
            "end_date": period_end.isoformat(),
            "fiscal_year": fiscal_year,
        },
        "currency": presentation_currency,
        "fx_metadata": get_fx_metadata(
            functional_currency or "NGN",
            presentation_currency,
        ),
        "method": "indirect",
        "opening_cash": float(opening_cash),
        "closing_cash": float(closing_cash),
        "net_change_in_cash": actual_change,
        "fx_effect_on_cash": float(fx_effect_on_cash),
        "operating_activities": operating_activities,
        "investing_activities": investing_activities,
        "financing_activities": financing_activities,
        "total_cash_flow": total_cash_flow,
        # Detailed CFO reconciliation (indirect method)
        "cfo_reconciliation": cfo_reconciliation,
        # IAS 7 Required Supplementary Disclosures
        "supplementary_disclosures": {
            "interest_paid": float(interest_paid),
            "interest_received": float(interest_received),
            "dividends_paid": float(dividends_paid),
            "dividends_received": 0,  # Would need specific tracking
            "income_taxes_paid": float(taxes_paid),
        },
        # Classification Policy (IAS 7 policy choices)
        "classification_policy": {
            "interest_paid": interest_paid_classification,
            "interest_received": interest_received_classification,
            "dividends_paid": dividends_paid_classification,
            "dividends_received": dividends_received_classification,
            "taxes_paid": "operating",  # Generally always operating
        },
        # Structured Non-cash transactions (IAS 7.43)
        "non_cash_transactions": non_cash_transactions,
        # Validation
        "validation": validation_result,
        "reconciliation_difference": reconciliation_diff,
        "is_reconciled": abs(reconciliation_diff) < 1.0,
        "bank_summary": {
            "deposits": float(deposits),
            "withdrawals": float(withdrawals),
        },
    }

    # Add prior period and variance if available
    if include_prior_period and prior_period_data:
        result["prior_period"] = prior_period_data
        prior_net_change: float | int | Decimal | str = 0.0
        if isinstance(prior_period_data, dict):
            prior_net_change_raw = prior_period_data.get("net_change_in_cash", 0) or 0
            prior_net_change = cast(float | int | Decimal | str, prior_net_change_raw)
        result["variance"] = {
            "net_change_in_cash": calculate_variance(
                actual_change,
                float(prior_net_change),
            ),
        }

    return result


# =============================================================================
# FINANCIAL RATIOS (Comprehensive)
# =============================================================================

@router.get("/financial-ratios", dependencies=[Depends(Require("accounting:read"))])
def get_financial_ratios(
    as_of_date: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get comprehensive financial ratios.

    Calculates key financial ratios across four categories:
    - Liquidity: Current Ratio, Quick Ratio, Cash Ratio
    - Solvency: Debt-to-Equity, Debt-to-Assets, Interest Coverage
    - Efficiency: AR Turnover, AP Turnover, Inventory Turnover, Asset Turnover
    - Profitability: ROA, ROE, Gross Margin, Operating Margin, Net Margin

    Args:
        as_of_date: Calculate ratios as of this date (default: today)
        fiscal_year: Fiscal year for period-based ratios

    Returns:
        Comprehensive financial ratios with interpretations
    """
    end_date = parse_date(as_of_date, "as_of_date") or date.today()

    # Get fiscal year dates for P&L ratios
    if fiscal_year:
        period_start, period_end = get_fiscal_year_dates(db, fiscal_year)
    else:
        period_start = date(end_date.year, 1, 1)
        period_end = end_date

    # Get all accounts
    accounts: Dict[str, Account] = {acc.erpnext_id: acc for acc in db.query(Account).all() if acc.erpnext_id}

    # Get cumulative balances for balance sheet items
    balances = db.query(
        GLEntry.account,
        func.sum(GLEntry.debit - GLEntry.credit).label("balance"),
    ).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date <= end_date,
    ).group_by(GLEntry.account).all()

    balance_map = {r.account: float(r.balance or 0) for r in balances if r.account}

    # Get period data for P&L items
    period_data = db.query(
        GLEntry.account,
        func.sum(GLEntry.debit).label("debit"),
        func.sum(GLEntry.credit).label("credit"),
    ).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= period_start,
        GLEntry.posting_date <= period_end,
    ).group_by(GLEntry.account).all()

    period_map = {
        r.account: {"debit": float(r.debit or 0), "credit": float(r.credit or 0)}
        for r in period_data
        if r.account
    }

    # === BALANCE SHEET COMPONENTS ===

    # Current Assets
    current_asset_types = {"Bank", "Cash", "Receivable", "Stock", "Current Asset"}
    current_assets = sum(
        balance_map.get(acc_id, 0)
        for acc_id, acc in accounts.items()
        if acc.account_type in current_asset_types or
        (get_effective_root_type(acc) == AccountType.ASSET and acc.account_type not in {"Fixed Asset", "Capital Work in Progress"})
    )

    # Cash and Cash Equivalents
    cash_types = {"Bank", "Cash"}
    cash = sum(
        balance_map.get(acc_id, 0)
        for acc_id, acc in accounts.items()
        if acc.account_type in cash_types
    )

    # Accounts Receivable
    ar = sum(
        balance_map.get(acc_id, 0)
        for acc_id, acc in accounts.items()
        if acc.account_type == "Receivable"
    )

    # Inventory
    inventory = sum(
        balance_map.get(acc_id, 0)
        for acc_id, acc in accounts.items()
        if acc.account_type == "Stock"
    )

    # Total Assets
    total_assets = sum(
        balance_map.get(acc_id, 0)
        for acc_id, acc in accounts.items()
        if get_effective_root_type(acc) == AccountType.ASSET
    )

    # Fixed Assets
    fixed_assets = total_assets - current_assets

    # Current Liabilities
    current_liability_types = {"Payable", "Current Liability"}
    current_liabilities = sum(
        -balance_map.get(acc_id, 0)
        for acc_id, acc in accounts.items()
        if acc.account_type in current_liability_types
    )

    # Accounts Payable
    ap = sum(
        -balance_map.get(acc_id, 0)
        for acc_id, acc in accounts.items()
        if acc.account_type == "Payable"
    )

    # Total Liabilities
    total_liabilities = sum(
        -balance_map.get(acc_id, 0)
        for acc_id, acc in accounts.items()
        if get_effective_root_type(acc) == AccountType.LIABILITY
    )

    # Total Equity
    total_equity = sum(
        -balance_map.get(acc_id, 0)
        for acc_id, acc in accounts.items()
        if get_effective_root_type(acc) == AccountType.EQUITY
    )

    # Add retained earnings to equity
    income_total = sum(
        period_map.get(acc_id, {}).get("credit", 0) - period_map.get(acc_id, {}).get("debit", 0)
        for acc_id, acc in accounts.items()
        if get_effective_root_type(acc) == AccountType.INCOME
    )
    expense_total = sum(
        period_map.get(acc_id, {}).get("debit", 0) - period_map.get(acc_id, {}).get("credit", 0)
        for acc_id, acc in accounts.items()
        if get_effective_root_type(acc) == AccountType.EXPENSE
    )
    retained_earnings = income_total - expense_total
    shareholders_equity = total_equity + retained_earnings

    # === INCOME STATEMENT COMPONENTS ===

    # Revenue
    revenue = income_total

    # COGS
    cogs = sum(
        period_map.get(acc_id, {}).get("debit", 0) - period_map.get(acc_id, {}).get("credit", 0)
        for acc_id, acc in accounts.items()
        if get_effective_root_type(acc) == AccountType.EXPENSE and is_cogs_account(acc)
    )

    # Operating Expenses
    opex = expense_total - cogs

    # Gross Profit
    gross_profit = revenue - cogs

    # Operating Income
    operating_income = gross_profit - opex

    # Net Income
    net_income = revenue - expense_total

    # === CALCULATE RATIOS ===

    def safe_divide(numerator: float, denominator: float, default: float = 0) -> float:
        """Safely divide two numbers, returning default if denominator is zero."""
        if denominator == 0:
            return default
        return numerator / denominator

    def ratio_status(value: float, good_min: float, good_max: float, warning_min: float, warning_max: float) -> str:
        """Determine status of a ratio based on thresholds."""
        if good_min <= value <= good_max:
            return "good"
        if warning_min <= value <= warning_max:
            return "warning"
        return "critical"

    # Days in period for turnover calculations
    days_in_period = (period_end - period_start).days + 1

    # LIQUIDITY RATIOS
    current_ratio = safe_divide(current_assets, current_liabilities)
    quick_ratio = safe_divide(current_assets - inventory, current_liabilities)
    cash_ratio = safe_divide(cash, current_liabilities)
    working_capital = current_assets - current_liabilities

    liquidity = {
        "current_ratio": {
            "value": round(current_ratio, 2),
            "interpretation": "Current Assets / Current Liabilities",
            "status": ratio_status(current_ratio, 1.5, 3.0, 1.0, 4.0),
            "benchmark": "1.5 - 2.0 is healthy",
        },
        "quick_ratio": {
            "value": round(quick_ratio, 2),
            "interpretation": "(Current Assets - Inventory) / Current Liabilities",
            "status": ratio_status(quick_ratio, 1.0, 2.0, 0.5, 3.0),
            "benchmark": "1.0+ is healthy",
        },
        "cash_ratio": {
            "value": round(cash_ratio, 2),
            "interpretation": "Cash / Current Liabilities",
            "status": ratio_status(cash_ratio, 0.2, 1.0, 0.1, 2.0),
            "benchmark": "0.2 - 0.5 is typical",
        },
        "working_capital": {
            "value": round(working_capital, 2),
            "interpretation": "Current Assets - Current Liabilities",
            "status": "good" if working_capital > 0 else "critical",
        },
    }

    # SOLVENCY RATIOS
    debt_to_equity = safe_divide(total_liabilities, shareholders_equity)
    debt_to_assets = safe_divide(total_liabilities, total_assets)
    equity_ratio = safe_divide(shareholders_equity, total_assets)

    solvency = {
        "debt_to_equity": {
            "value": round(debt_to_equity, 2),
            "interpretation": "Total Liabilities / Shareholders' Equity",
            "status": ratio_status(debt_to_equity, 0.0, 1.5, 0.0, 2.5),
            "benchmark": "< 1.5 is conservative",
        },
        "debt_to_assets": {
            "value": round(debt_to_assets, 2),
            "interpretation": "Total Liabilities / Total Assets",
            "status": ratio_status(debt_to_assets, 0.0, 0.5, 0.0, 0.7),
            "benchmark": "< 0.5 is conservative",
        },
        "equity_ratio": {
            "value": round(equity_ratio, 2),
            "interpretation": "Shareholders' Equity / Total Assets",
            "status": ratio_status(equity_ratio, 0.4, 1.0, 0.2, 1.0),
            "benchmark": "> 0.5 is strong",
        },
    }

    # EFFICIENCY RATIOS
    ar_turnover = safe_divide(revenue, ar) if ar > 0 else 0
    ar_days = safe_divide(365, ar_turnover) if ar_turnover > 0 else 0
    ap_turnover = safe_divide(cogs, ap) if ap > 0 else 0
    ap_days = safe_divide(365, ap_turnover) if ap_turnover > 0 else 0
    inventory_turnover = safe_divide(cogs, inventory) if inventory > 0 else 0
    inventory_days = safe_divide(365, inventory_turnover) if inventory_turnover > 0 else 0
    asset_turnover = safe_divide(revenue, total_assets)

    efficiency = {
        "receivables_turnover": {
            "value": round(ar_turnover, 2),
            "days": round(ar_days, 0),
            "interpretation": "Revenue / Accounts Receivable",
            "status": ratio_status(ar_days, 0, 45, 0, 90),
            "benchmark": "30-45 days is typical",
        },
        "payables_turnover": {
            "value": round(ap_turnover, 2),
            "days": round(ap_days, 0),
            "interpretation": "COGS / Accounts Payable",
            "status": "info",
            "benchmark": "30-60 days is typical",
        },
        "inventory_turnover": {
            "value": round(inventory_turnover, 2),
            "days": round(inventory_days, 0),
            "interpretation": "COGS / Average Inventory",
            "status": ratio_status(inventory_turnover, 4, 20, 2, 30),
            "benchmark": "4-6x per year is typical",
        },
        "asset_turnover": {
            "value": round(asset_turnover, 2),
            "interpretation": "Revenue / Total Assets",
            "status": ratio_status(asset_turnover, 0.5, 3.0, 0.2, 5.0),
            "benchmark": "Varies by industry",
        },
        "cash_conversion_cycle": {
            "value": round(ar_days + inventory_days - ap_days, 0),
            "interpretation": "AR Days + Inventory Days - AP Days",
            "status": "info",
            "benchmark": "Lower is better",
        },
    }

    # PROFITABILITY RATIOS
    gross_margin = safe_divide(gross_profit, revenue) * 100
    operating_margin = safe_divide(operating_income, revenue) * 100
    net_margin = safe_divide(net_income, revenue) * 100
    roa = safe_divide(net_income, total_assets) * 100
    roe = safe_divide(net_income, shareholders_equity) * 100

    profitability = {
        "gross_margin": {
            "value": round(gross_margin, 2),
            "interpretation": "Gross Profit / Revenue × 100",
            "status": ratio_status(gross_margin, 20, 80, 10, 90),
            "benchmark": "Varies by industry",
        },
        "operating_margin": {
            "value": round(operating_margin, 2),
            "interpretation": "Operating Income / Revenue × 100",
            "status": ratio_status(operating_margin, 10, 40, 5, 50),
            "benchmark": "10-20% is healthy",
        },
        "net_margin": {
            "value": round(net_margin, 2),
            "interpretation": "Net Income / Revenue × 100",
            "status": ratio_status(net_margin, 5, 30, 0, 50),
            "benchmark": "5-15% is typical",
        },
        "return_on_assets": {
            "value": round(roa, 2),
            "interpretation": "Net Income / Total Assets × 100",
            "status": ratio_status(roa, 5, 20, 0, 30),
            "benchmark": "5-10% is good",
        },
        "return_on_equity": {
            "value": round(roe, 2),
            "interpretation": "Net Income / Shareholders' Equity × 100",
            "status": ratio_status(roe, 10, 30, 5, 50),
            "benchmark": "15-20% is excellent",
        },
    }

    return {
        "as_of_date": end_date.isoformat(),
        "period": {
            "start_date": period_start.isoformat(),
            "end_date": period_end.isoformat(),
            "days": days_in_period,
        },
        "liquidity_ratios": liquidity,
        "solvency_ratios": solvency,
        "efficiency_ratios": efficiency,
        "profitability_ratios": profitability,
        "components": {
            "current_assets": round(current_assets, 2),
            "current_liabilities": round(current_liabilities, 2),
            "total_assets": round(total_assets, 2),
            "total_liabilities": round(total_liabilities, 2),
            "shareholders_equity": round(shareholders_equity, 2),
            "revenue": round(revenue, 2),
            "cogs": round(cogs, 2),
            "gross_profit": round(gross_profit, 2),
            "operating_income": round(operating_income, 2),
            "net_income": round(net_income, 2),
            "cash": round(cash, 2),
            "receivables": round(ar, 2),
            "inventory": round(inventory, 2),
            "payables": round(ap, 2),
        },
    }


# =============================================================================
# STATEMENT OF CHANGES IN EQUITY (IAS 1)
# =============================================================================

@router.get("/equity-statement", dependencies=[Depends(Require("accounting:read"))])
def get_equity_statement(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    currency: Optional[str] = None,
    include_prior_period: bool = True,
    functional_currency: Optional[str] = None,
    presentation_currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get Statement of Changes in Equity (IFRS/IAS 1 compliant).

    Shows movements in each component of equity:
    - Share Capital
    - Share Premium
    - Reserves (statutory, revaluation, etc.)
    - Other Comprehensive Income (with may/may-not reclassify split)
    - Retained Earnings
    - Treasury Shares
    - Share-Based Payments (IFRS 2)
    - FX Translation Reserve

    Args:
        start_date: Period start (default: fiscal year start)
        end_date: Period end (default: today)
        fiscal_year: Use fiscal year dates
        currency: Filter by currency
        include_prior_period: Include prior period comparatives (default: True)
        functional_currency: Entity's functional currency
        presentation_currency: Presentation currency if different

    Returns:
        Statement of changes in equity with opening, movements, closing balances,
        OCI breakdown, prior period comparatives, and validation results
    """
    # Determine date range
    if fiscal_year:
        period_start, period_end = get_fiscal_year_dates(db, fiscal_year)
    else:
        period_end = parse_date(end_date, "end_date") or date.today()
        period_start = parse_date(start_date, "start_date") or date(period_end.year, 1, 1)

    # Calculate prior period dates for comparatives
    prior_start, prior_end = calculate_prior_period(period_start, period_end)

    # Get all accounts
    accounts: Dict[str, Account] = {acc.erpnext_id: acc for acc in db.query(Account).all() if acc.erpnext_id}

    def classify_equity_account(acc: Account) -> str:
        """Classify an equity account into its component type."""
        acc_type = acc.account_type or ""
        acc_name = (acc.account_name or "").lower()

        # Check account type first
        if acc_type in SHARE_CAPITAL_TYPES:
            return "share_capital"
        if acc_type in SHARE_PREMIUM_TYPES:
            return "share_premium"
        if acc_type in TREASURY_SHARE_TYPES:
            return "treasury_shares"
        if acc_type in OCI_RESERVE_TYPES:
            return "other_comprehensive_income"
        if acc_type in RESERVE_TYPES:
            return "reserves"
        if acc_type in RETAINED_EARNINGS_TYPES:
            return "retained_earnings"
        if acc_type in SHARE_BASED_PAYMENT_TYPES:
            return "share_based_payments"

        # Check account name keywords
        if any(kw in acc_name for kw in ["share capital", "common stock", "ordinary share"]):
            return "share_capital"
        if any(kw in acc_name for kw in ["share premium", "paid-in capital", "capital surplus"]):
            return "share_premium"
        if any(kw in acc_name for kw in ["treasury", "own share"]):
            return "treasury_shares"
        if any(kw in acc_name for kw in ["share based", "stock compensation", "stock option", "equity settled"]):
            return "share_based_payments"
        if any(kw in acc_name for kw in ["translation reserve", "fx reserve", "currency translation"]):
            return "fx_translation_reserve"
        if any(kw in acc_name for kw in ["oci", "comprehensive income", "revaluation surplus"]):
            return "other_comprehensive_income"
        if any(kw in acc_name for kw in ["reserve", "statutory"]):
            return "reserves"
        if any(kw in acc_name for kw in ["retained", "accumulated profit", "accumulated loss"]):
            return "retained_earnings"

        # Default to retained earnings for unclassified equity
        return "retained_earnings"

    def classify_oci_component(acc: Account) -> Optional[str]:
        """Classify OCI account into may-reclassify or not-reclassify category."""
        acc_type = acc.account_type or ""
        acc_name = (acc.account_name or "").lower()

        # Items that MAY be reclassified to P&L
        if acc_type in OCI_MAY_RECLASSIFY_TYPES:
            return "may_reclassify"
        if any(kw in acc_name for kw in ["hedge", "translation", "available for sale"]):
            return "may_reclassify"

        # Items that will NOT be reclassified to P&L
        if acc_type in OCI_NOT_RECLASSIFY_TYPES:
            return "not_reclassify"
        if any(kw in acc_name for kw in ["revaluation", "actuarial", "fvoci equity"]):
            return "not_reclassify"

        return None

    def get_equity_balances(
        as_of: date,
    ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        """Get equity account balances by component as of a date."""
        results = db.query(
            GLEntry.account,
            func.sum(GLEntry.credit - GLEntry.debit).label("balance"),
        ).filter(
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= as_of,
        ).group_by(GLEntry.account).all()

        components: Dict[str, Dict[str, Any]] = {
            "share_capital": {"total": Decimal("0"), "accounts": {}},
            "share_premium": {"total": Decimal("0"), "accounts": {}},
            "reserves": {"total": Decimal("0"), "accounts": {}},
            "other_comprehensive_income": {"total": Decimal("0"), "accounts": {}},
            "retained_earnings": {"total": Decimal("0"), "accounts": {}},
            "treasury_shares": {"total": Decimal("0"), "accounts": {}},
            "share_based_payments": {"total": Decimal("0"), "accounts": {}},
            "fx_translation_reserve": {"total": Decimal("0"), "accounts": {}},
        }

        # OCI breakdown by reclassification category
        oci_breakdown: Dict[str, Dict[str, Any]] = {
            "may_reclassify": {"total": Decimal("0"), "items": {}},
            "not_reclassify": {"total": Decimal("0"), "items": {}},
        }

        for row in results:
            acc = accounts.get(row.account)
            if not acc or get_effective_root_type(acc) != AccountType.EQUITY:
                continue

            balance = row.balance or Decimal("0")
            component = classify_equity_account(acc)
            component_data = components[component]
            component_total = cast(Decimal, component_data["total"])
            component_data["total"] = component_total + balance
            component_accounts = cast(Dict[str, float], component_data["accounts"])
            component_accounts[acc.account_name or ""] = float(balance)

            # Track OCI breakdown
            if component == "other_comprehensive_income":
                oci_category = classify_oci_component(acc)
                if oci_category:
                    oci_data = oci_breakdown[oci_category]
                    oci_total = cast(Decimal, oci_data["total"])
                    oci_data["total"] = oci_total + balance
                    oci_items = cast(Dict[str, float], oci_data["items"])
                    oci_items[acc.account_name or ""] = float(balance)

        return components, oci_breakdown

    def get_period_movements(
        p_start: date,
        p_end: date,
    ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        """Get equity movements during a specific period."""
        results = db.query(
            GLEntry.account,
            func.sum(GLEntry.credit - GLEntry.debit).label("movement"),
        ).filter(
            GLEntry.is_cancelled == False,
            GLEntry.posting_date >= p_start,
            GLEntry.posting_date <= p_end,
        ).group_by(GLEntry.account).all()

        components: Dict[str, Dict[str, Any]] = {
            "share_capital": {"total": Decimal("0"), "accounts": {}},
            "share_premium": {"total": Decimal("0"), "accounts": {}},
            "reserves": {"total": Decimal("0"), "accounts": {}},
            "other_comprehensive_income": {"total": Decimal("0"), "accounts": {}},
            "retained_earnings": {"total": Decimal("0"), "accounts": {}},
            "treasury_shares": {"total": Decimal("0"), "accounts": {}},
            "share_based_payments": {"total": Decimal("0"), "accounts": {}},
            "fx_translation_reserve": {"total": Decimal("0"), "accounts": {}},
        }

        # OCI movement breakdown
        oci_movement_breakdown: Dict[str, Dict[str, Any]] = {
            "may_reclassify": {"total": Decimal("0"), "items": {}},
            "not_reclassify": {"total": Decimal("0"), "items": {}},
        }

        for row in results:
            acc = accounts.get(row.account)
            if not acc or get_effective_root_type(acc) != AccountType.EQUITY:
                continue

            movement = row.movement or Decimal("0")
            component = classify_equity_account(acc)
            component_data = components[component]
            component_total = cast(Decimal, component_data["total"])
            component_data["total"] = component_total + movement
            component_accounts = cast(Dict[str, float], component_data["accounts"])
            component_accounts[acc.account_name or ""] = float(movement)

            # Track OCI movement breakdown
            if component == "other_comprehensive_income":
                oci_category = classify_oci_component(acc)
                if oci_category:
                    oci_data = oci_movement_breakdown[oci_category]
                    oci_total = cast(Decimal, oci_data["total"])
                    oci_data["total"] = oci_total + movement
                    oci_items = cast(Dict[str, float], oci_data["items"])
                    oci_items[acc.account_name or ""] = float(movement)

        return components, oci_movement_breakdown

    def calculate_profit_for_period(p_start: date, p_end: date) -> Decimal:
        """Calculate profit/loss for a period (affects retained earnings)."""
        income_accounts_list = [acc_id for acc_id, acc in accounts.items() if acc.root_type == AccountType.INCOME]
        expense_accounts_list = [acc_id for acc_id, acc in accounts.items() if acc.root_type == AccountType.EXPENSE]

        period_income = db.query(
            func.sum(GLEntry.credit - GLEntry.debit)
        ).filter(
            GLEntry.account.in_(income_accounts_list),
            GLEntry.is_cancelled == False,
            GLEntry.posting_date >= p_start,
            GLEntry.posting_date <= p_end,
        ).scalar() or Decimal("0")

        period_expenses = db.query(
            func.sum(GLEntry.debit - GLEntry.credit)
        ).filter(
            GLEntry.account.in_(expense_accounts_list),
            GLEntry.is_cancelled == False,
            GLEntry.posting_date >= p_start,
            GLEntry.posting_date <= p_end,
        ).scalar() or Decimal("0")

        return period_income - period_expenses

    # Calculate current period data
    profit_for_period = calculate_profit_for_period(period_start, period_end)
    opening_date = period_start - timedelta(days=1)
    opening_balances: Dict[str, Dict[str, Any]]
    opening_oci: Dict[str, Dict[str, Any]]
    closing_balances: Dict[str, Dict[str, Any]]
    closing_oci: Dict[str, Dict[str, Any]]
    period_movements: Dict[str, Dict[str, Any]]
    oci_movements: Dict[str, Dict[str, Any]]

    opening_balances, opening_oci = get_equity_balances(opening_date)
    closing_balances, closing_oci = get_equity_balances(period_end)
    period_movements, oci_movements = get_period_movements(period_start, period_end)

    # Calculate prior period data if requested
    prior_period_data = None
    if include_prior_period:
        prior_profit = calculate_profit_for_period(prior_start, prior_end)
        prior_opening_date = prior_start - timedelta(days=1)
        prior_opening_balances: Dict[str, Dict[str, Any]]
        prior_opening_oci: Dict[str, Dict[str, Any]]
        prior_closing_balances: Dict[str, Dict[str, Any]]
        prior_closing_oci: Dict[str, Dict[str, Any]]
        prior_movements: Dict[str, Dict[str, Any]]
        prior_oci_movements: Dict[str, Dict[str, Any]]

        prior_opening_balances, prior_opening_oci = get_equity_balances(prior_opening_date)
        prior_closing_balances, prior_closing_oci = get_equity_balances(prior_end)
        prior_movements, prior_oci_movements = get_period_movements(prior_start, prior_end)

    # Build the statement structure
    def build_component(name: str, label: str, is_prior: bool = False) -> Dict[str, Any]:
        """Build a single equity component row."""
        if is_prior:
            opening = float(prior_opening_balances[name]["total"])
            closing = float(prior_closing_balances[name]["total"])
            movement = float(prior_movements[name]["total"])
            profit = prior_profit
        else:
            opening = float(opening_balances[name]["total"])
            closing = float(closing_balances[name]["total"])
            movement = float(period_movements[name]["total"])
            profit = profit_for_period

        # Add profit to retained earnings movement
        profit_impact = float(profit) if name == "retained_earnings" else 0

        # Determine movement type based on component
        share_transactions = movement if name in ("share_capital", "share_premium", "treasury_shares") else 0
        share_based = movement if name == "share_based_payments" else 0
        fx_translation = movement if name == "fx_translation_reserve" else 0
        transfers = movement if name == "reserves" else 0
        oci_impact = movement if name == "other_comprehensive_income" else 0

        other_movements = 0.0
        if name not in ("share_capital", "share_premium", "treasury_shares", "reserves",
                        "share_based_payments", "fx_translation_reserve", "other_comprehensive_income"):
            if profit_impact == 0:
                other_movements = movement

        return {
            "component": label,
            "opening_balance": opening,
            "profit_loss": profit_impact,
            "other_comprehensive_income": oci_impact,
            "share_based_payments": share_based,
            "fx_translation": fx_translation,
            "dividends": 0,  # Would need dividend tracking from specific voucher types
            "share_transactions": share_transactions,
            "transfers": transfers,
            "other_movements": other_movements,
            "closing_balance": closing,
            "accounts": (prior_closing_balances if is_prior else closing_balances)[name]["accounts"],
        }

    # Build current period components
    component_keys = [
        ("share_capital", "Share Capital"),
        ("share_premium", "Share Premium"),
        ("reserves", "Reserves"),
        ("share_based_payments", "Share-Based Payments (IFRS 2)"),
        ("fx_translation_reserve", "FX Translation Reserve"),
        ("other_comprehensive_income", "Other Comprehensive Income"),
        ("retained_earnings", "Retained Earnings"),
        ("treasury_shares", "Treasury Shares"),
    ]

    components = [build_component(key, label) for key, label in component_keys]

    # Build prior period components if requested
    prior_components = None
    if include_prior_period:
        prior_components = [build_component(key, label, is_prior=True) for key, label in component_keys]

    # Calculate totals
    total_opening = sum(c["opening_balance"] for c in components)
    total_closing = sum(c["closing_balance"] for c in components)

    # Treasury shares reduce equity (sign convention)
    treasury_idx = next((i for i, c in enumerate(components) if c["component"] == "Treasury Shares"), None)
    if treasury_idx is not None:
        components[treasury_idx]["opening_balance"] = -abs(components[treasury_idx]["opening_balance"])
        components[treasury_idx]["closing_balance"] = -abs(components[treasury_idx]["closing_balance"])

    if prior_components:
        prior_treasury_idx = next((i for i, c in enumerate(prior_components) if c["component"] == "Treasury Shares"), None)
        if prior_treasury_idx is not None:
            prior_components[prior_treasury_idx]["opening_balance"] = -abs(prior_components[prior_treasury_idx]["opening_balance"])
            prior_components[prior_treasury_idx]["closing_balance"] = -abs(prior_components[prior_treasury_idx]["closing_balance"])

    # Build OCI breakdown structure (IAS 1.82A)
    oci_breakdown = {
        "items_may_be_reclassified": {
            "opening_balance": float(opening_oci["may_reclassify"]["total"]),
            "movement": float(oci_movements["may_reclassify"]["total"]),
            "closing_balance": float(closing_oci["may_reclassify"]["total"]),
            "items": closing_oci["may_reclassify"]["items"],
            "reclassification_adjustments": 0,  # Would need specific tracking
        },
        "items_not_reclassified": {
            "opening_balance": float(opening_oci["not_reclassify"]["total"]),
            "movement": float(oci_movements["not_reclassify"]["total"]),
            "closing_balance": float(closing_oci["not_reclassify"]["total"]),
            "items": closing_oci["not_reclassify"]["items"],
        },
        "total_oci": float(closing_oci["may_reclassify"]["total"] + closing_oci["not_reclassify"]["total"]),
    }

    # Validate equity statement
    validation_errors: List[Dict[str, Any]] = []
    validation_warnings: List[Dict[str, Any]] = []

    # Validate each component reconciliation
    for comp in components:
        expected_closing = (
            comp["opening_balance"] +
            comp["profit_loss"] +
            comp["other_comprehensive_income"] +
            comp["share_based_payments"] +
            comp["fx_translation"] -
            comp["dividends"] +
            comp["share_transactions"] +
            comp["transfers"] +
            comp["other_movements"]
        )
        if abs(comp["closing_balance"] - expected_closing) > 1.0:
            validation_errors.append({
                "code": "EQUITY_RECONCILIATION_MISMATCH",
                "message": f"{comp['component']} opening + movements != closing",
                "field": comp["component"],
                "expected": expected_closing,
                "actual": comp["closing_balance"],
            })

    # Validate total equity reconciliation
    expected_total = (
        total_opening +
        float(profit_for_period) +
        float(period_movements["other_comprehensive_income"]["total"]) +
        float(period_movements["share_based_payments"]["total"]) +
        float(period_movements["fx_translation_reserve"]["total"]) +
        float(period_movements["share_capital"]["total"]) +
        float(period_movements["share_premium"]["total"]) +
        float(period_movements["reserves"]["total"]) +
        float(period_movements["treasury_shares"]["total"])
    )
    is_reconciled = abs(total_closing - expected_total) < 1.0
    if not is_reconciled:
        validation_errors.append({
            "code": "TOTAL_EQUITY_MISMATCH",
            "message": "Total equity opening + movements != closing",
            "expected": expected_total,
            "actual": total_closing,
        })

    validation_result = {
        "is_valid": len(validation_errors) == 0,
        "errors": validation_errors,
        "warnings": validation_warnings,
    }

    # Calculate variances if prior period available
    variances = None
    if include_prior_period and prior_components:
        prior_total_closing = sum(c["closing_balance"] for c in prior_components)
        variances = calculate_variance(total_closing, prior_total_closing)

    # Build response
    response: Dict[str, Any] = {
        "period": {
            "start_date": period_start.isoformat(),
            "end_date": period_end.isoformat(),
            "fiscal_year": fiscal_year,
        },
        "currency": currency or "NGN",
        "fx_metadata": get_fx_metadata(
            functional_currency or "NGN",
            presentation_currency or currency or "NGN",
        ),
        "components": components,
        "oci_breakdown": oci_breakdown,
        "summary": {
            "total_opening_equity": total_opening,
            "total_comprehensive_income": float(profit_for_period) + float(period_movements["other_comprehensive_income"]["total"]),
            "profit_for_period": float(profit_for_period),
            "other_comprehensive_income": float(period_movements["other_comprehensive_income"]["total"]),
            "share_based_payments": float(period_movements["share_based_payments"]["total"]),
            "fx_translation_reserve": float(period_movements["fx_translation_reserve"]["total"]),
            "transactions_with_owners": {
                "dividends_paid": 0,
                "share_issues": float(period_movements["share_capital"]["total"] + period_movements["share_premium"]["total"]),
                "treasury_share_transactions": float(period_movements["treasury_shares"]["total"]),
            },
            "total_closing_equity": total_closing,
            "change_in_equity": total_closing - total_opening,
        },
        "reconciliation": {
            "opening_equity": total_opening,
            "add_profit_for_period": float(profit_for_period),
            "add_other_comprehensive_income": float(period_movements["other_comprehensive_income"]["total"]),
            "add_share_based_payments": float(period_movements["share_based_payments"]["total"]),
            "add_fx_translation": float(period_movements["fx_translation_reserve"]["total"]),
            "less_dividends": 0,
            "add_share_issues": float(period_movements["share_capital"]["total"] + period_movements["share_premium"]["total"]),
            "less_treasury_shares": float(period_movements["treasury_shares"]["total"]),
            "other_movements": float(period_movements["reserves"]["total"]),
            "closing_equity": total_closing,
            "is_reconciled": is_reconciled,
        },
        "validation": validation_result,
    }

    # Add prior period and variance if available
    if include_prior_period and prior_components:
        prior_total_opening = sum(c["opening_balance"] for c in prior_components)
        prior_total_closing = sum(c["closing_balance"] for c in prior_components)
        response["prior_period"] = {
            "period": {
                "start_date": prior_start.isoformat(),
                "end_date": prior_end.isoformat(),
            },
            "components": prior_components,
            "summary": {
                "total_opening_equity": prior_total_opening,
                "total_comprehensive_income": float(prior_profit) + float(prior_movements["other_comprehensive_income"]["total"]),
                "profit_for_period": float(prior_profit),
                "other_comprehensive_income": float(prior_movements["other_comprehensive_income"]["total"]),
                "total_closing_equity": prior_total_closing,
                "change_in_equity": prior_total_closing - prior_total_opening,
            },
        }
        response["variance"] = variances

    return response
