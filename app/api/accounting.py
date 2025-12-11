"""Accounting API endpoints for financial statements and reports."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case, and_, or_
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal

from app.database import get_db
from app.auth import Require
from app.models.customer import Customer
from app.models.accounting import (
    Account,
    AccountType,
    GLEntry,
    JournalEntry,
    JournalEntryType,
    PurchaseInvoice,
    PurchaseInvoiceStatus,
    BankAccount,
    BankTransaction,
    BankTransactionStatus,
    CostCenter,
    FiscalYear,
    Supplier,
    ModeOfPayment,
)
from app.models.invoice import Invoice, InvoiceStatus

router = APIRouter()


def _parse_date(value: Optional[str], field_name: str) -> Optional[date]:
    """Parse date string to date object."""
    if not value:
        return None
    try:
        # Handle ISO format with time
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format for {field_name}")


def _resolve_currency_or_raise(db: Session, column, requested: Optional[str]) -> Optional[str]:
    """Ensure we do not mix currencies. If none requested and multiple exist, raise 400."""
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


def _get_fiscal_year_dates(db: Session, fiscal_year: Optional[str] = None) -> tuple[date, date]:
    """Get start and end dates for a fiscal year."""
    if fiscal_year:
        fy = db.query(FiscalYear).filter(FiscalYear.year == fiscal_year).first()
        if not fy:
            raise HTTPException(status_code=404, detail=f"Fiscal year {fiscal_year} not found")
        return fy.year_start_date, fy.year_end_date

    # Default to current year
    today = date.today()
    return date(today.year, 1, 1), date(today.year, 12, 31)


# ============= CHART OF ACCOUNTS =============

@router.get("/chart-of-accounts", dependencies=[Depends(Require("accounting:read"))])
async def get_chart_of_accounts(
    root_type: Optional[str] = None,
    include_disabled: bool = False,
    include_balances: bool = True,
    as_of_date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get chart of accounts as hierarchical tree with balances.

    Args:
        root_type: Filter by root type (asset, liability, equity, income, expense)
        include_disabled: Include disabled accounts
        include_balances: Include account balances from GL entries (default: True)
        as_of_date: Calculate balances as of this date (default: today)
    """
    query = db.query(Account)

    if root_type:
        try:
            root_type_enum = AccountType(root_type.lower())
            query = query.filter(Account.root_type == root_type_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid root_type: {root_type}")

    if not include_disabled:
        query = query.filter(Account.disabled == False)

    accounts = query.order_by(Account.account_name).all()

    # Calculate balances from GL entries if requested
    account_balances = {}
    if include_balances:
        cutoff = _parse_date(as_of_date, "as_of_date") or date.today()
        balance_query = db.query(
            GLEntry.account,
            func.sum(GLEntry.debit).label("total_debit"),
            func.sum(GLEntry.credit).label("total_credit"),
        ).filter(
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= cutoff,
        ).group_by(GLEntry.account)

        for row in balance_query.all():
            debit = row.total_debit or Decimal("0")
            credit = row.total_credit or Decimal("0")
            account_balances[row.account] = float(debit - credit)

    # Build tree structure
    def build_tree(accounts: List[Account], parent: Optional[str] = None) -> List[Dict]:
        tree = []
        for acc in accounts:
            if acc.parent_account == parent:
                balance = account_balances.get(acc.erpnext_id, 0.0)
                node = {
                    "id": acc.id,
                    "name": acc.account_name,
                    "account_number": acc.account_number,
                    "root_type": acc.root_type.value if acc.root_type else None,
                    "account_type": acc.account_type,
                    "is_group": acc.is_group,
                    "disabled": acc.disabled,
                    "balance": balance,
                    "children": build_tree(accounts, acc.erpnext_id) if acc.is_group else [],
                }
                tree.append(node)
        return tree

    # Also return flat list for easier processing
    flat_list = [
        {
            "id": acc.id,
            "erpnext_id": acc.erpnext_id,
            "name": acc.account_name,
            "account_number": acc.account_number,
            "parent_account": acc.parent_account,
            "root_type": acc.root_type.value if acc.root_type else None,
            "account_type": acc.account_type,
            "is_group": acc.is_group,
            "disabled": acc.disabled,
            "balance": account_balances.get(acc.erpnext_id, 0.0),
        }
        for acc in accounts
    ]

    # Group by root type
    by_root_type = {}
    for acc in accounts:
        rt = acc.root_type.value if acc.root_type else "unknown"
        if rt not in by_root_type:
            by_root_type[rt] = []
        by_root_type[rt].append(acc.account_name)

    return {
        "total": len(accounts),
        "by_root_type": {k: len(v) for k, v in by_root_type.items()},
        "accounts": flat_list,
        "tree": build_tree(accounts, None),
    }


# ============= TRIAL BALANCE =============

@router.get("/trial-balance", dependencies=[Depends(Require("accounting:read"))])
async def get_trial_balance(
    as_of_date: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    cost_center: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get trial balance report (optional fiscal year/cost center).

    Shows debit and credit totals for each account.

    Args:
        as_of_date: Report as of this date (default: today)
        fiscal_year: Filter by fiscal year
        cost_center: Filter by cost center
    """
    end_date = _parse_date(as_of_date, "as_of_date") or date.today()


    # Get fiscal year start if specified
    start_date = None
    if fiscal_year:
        start_date, _ = _get_fiscal_year_dates(db, fiscal_year)

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
    accounts = {acc.erpnext_id: acc for acc in db.query(Account).all()}

    trial_balance = []
    total_debit = Decimal("0")
    total_credit = Decimal("0")

    for row in results:
        acc = accounts.get(row.account)
        debit = row.total_debit or Decimal("0")
        credit = row.total_credit or Decimal("0")
        balance = debit - credit

        trial_balance.append({
            "account": row.account,
            "account_name": acc.account_name if acc else row.account,
            "root_type": acc.root_type.value if acc and acc.root_type else None,
            "debit": float(debit),
            "credit": float(credit),
            "balance": float(balance),
            "balance_type": "Dr" if balance >= 0 else "Cr",
        })

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


# ============= BALANCE SHEET =============

# Account types that indicate liability regardless of root_type
LIABILITY_ACCOUNT_TYPES = {"Payable", "Current Liability"}
# Account types that indicate asset regardless of root_type
ASSET_ACCOUNT_TYPES = {"Receivable", "Bank", "Cash", "Fixed Asset", "Stock", "Current Asset"}


def _get_effective_root_type(acc) -> Optional[AccountType]:
    """Determine effective root type, correcting common ERPNext misclassifications.

    Some accounts in ERPNext have wrong root_type (e.g., Payable accounts classified as Asset).
    This function uses account_type to correct obvious misclassifications.
    """
    # If account_type indicates liability but root_type says asset, treat as liability
    if acc.account_type in LIABILITY_ACCOUNT_TYPES and acc.root_type == AccountType.ASSET:
        return AccountType.LIABILITY
    # If account_type indicates asset but root_type says liability, treat as asset
    if acc.account_type in ASSET_ACCOUNT_TYPES and acc.root_type == AccountType.LIABILITY:
        return AccountType.ASSET
    return acc.root_type


@router.get("/balance-sheet", dependencies=[Depends(Require("accounting:read"))])
async def get_balance_sheet(
    as_of_date: Optional[str] = None,
    comparative_date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get balance sheet report (optional comparative date).

    Assets = Liabilities + Equity

    Note: Automatically corrects common ERPNext account misclassifications
    (e.g., Payable accounts incorrectly classified as Asset root_type).

    Args:
        as_of_date: Report as of this date (default: today)
        comparative_date: Optional date for comparison
    """
    end_date = _parse_date(as_of_date, "as_of_date") or date.today()
    comp_date = _parse_date(comparative_date, "comparative_date")

    def get_balances(cutoff_date: date) -> Dict[str, Decimal]:
        """Get account balances as of a date."""
        results = db.query(
            GLEntry.account,
            func.sum(GLEntry.debit - GLEntry.credit).label("balance"),
        ).filter(
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= cutoff_date,
        )
        results = results.group_by(GLEntry.account).all()

        return {r.account: r.balance or Decimal("0") for r in results}

    # Get account details
    accounts = {acc.erpnext_id: acc for acc in db.query(Account).all()}

    current_balances = get_balances(end_date)
    comparative_balances = get_balances(comp_date) if comp_date else {}

    # Track reclassified accounts for warnings
    reclassified = []

    def build_section(root_type: AccountType, negate: bool = False) -> Dict:
        """Build a section of the balance sheet."""
        section_accounts = []
        total = Decimal("0")
        comp_total = Decimal("0")

        for acc_id, acc in accounts.items():
            effective_type = _get_effective_root_type(acc)
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
                    "account": acc.account_name,
                    "account_type": acc.account_type,
                    "balance": float(balance),
                    "comparative_balance": float(comp_balance) if comp_date else None,
                    "change": float(balance - comp_balance) if comp_date else None,
                })
                total += balance
                comp_total += comp_balance

        section_accounts.sort(key=lambda x: x["account"])

        return {
            "accounts": section_accounts,
            "total": float(total),
            "comparative_total": float(comp_total) if comp_date else None,
            "change": float(total - comp_total) if comp_date else None,
        }

    assets = build_section(AccountType.ASSET)
    liabilities = build_section(AccountType.LIABILITY, negate=True)
    equity = build_section(AccountType.EQUITY, negate=True)

    # Calculate retained earnings (Income - Expense for all time)
    income_total = sum(
        -current_balances.get(acc_id, Decimal("0"))
        for acc_id, acc in accounts.items()
        if _get_effective_root_type(acc) == AccountType.INCOME
    )
    expense_total = sum(
        current_balances.get(acc_id, Decimal("0"))
        for acc_id, acc in accounts.items()
        if _get_effective_root_type(acc) == AccountType.EXPENSE
    )
    retained_earnings = income_total - expense_total

    total_liab_equity = liabilities["total"] + equity["total"] + float(retained_earnings)
    difference = abs(Decimal(str(assets["total"])) - Decimal(str(total_liab_equity)))

    return {
        "as_of_date": end_date.isoformat(),
        "comparative_date": comp_date.isoformat() if comp_date else None,
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "retained_earnings": float(retained_earnings),
        "total_assets": assets["total"],
        "total_liabilities_equity": total_liab_equity,
        "difference": float(difference),
        "is_balanced": difference < Decimal("1"),
        "reclassified_accounts": reclassified if reclassified else None,
    }


# ============= INCOME STATEMENT (P&L) =============

@router.get("/income-statement", dependencies=[Depends(Require("accounting:read"))])
async def get_income_statement(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    cost_center: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get income statement (profit & loss) report.

    Shows revenue, expenses, and net income for a period.

    Args:
        start_date: Period start (default: fiscal year start)
        end_date: Period end (default: today)
        fiscal_year: Use fiscal year dates
        cost_center: Filter by cost center
    """
    # Determine date range
    if fiscal_year:
        period_start, period_end = _get_fiscal_year_dates(db, fiscal_year)
    else:
        period_end = _parse_date(end_date, "end_date") or date.today()
        period_start = _parse_date(start_date, "start_date") or date(period_end.year, 1, 1)

    # Get account details
    accounts = {acc.erpnext_id: acc for acc in db.query(Account).all()}

    # Query GL entries for the period
    query = db.query(
        GLEntry.account,
        func.sum(GLEntry.debit).label("debit"),
        func.sum(GLEntry.credit).label("credit"),
    ).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= period_start,
        GLEntry.posting_date <= period_end,
    )

    if cost_center:
        query = query.filter(GLEntry.cost_center == cost_center)

    query = query.group_by(GLEntry.account)
    results = query.all()

    def build_section(root_type: AccountType) -> Dict:
        """Build income or expense section."""
        section_accounts = []
        total = Decimal("0")

        for row in results:
            acc = accounts.get(row.account)
            if not acc or acc.root_type != root_type:
                continue

            # Income: credit - debit; Expense: debit - credit
            if root_type == AccountType.INCOME:
                amount = (row.credit or Decimal("0")) - (row.debit or Decimal("0"))
            else:
                amount = (row.debit or Decimal("0")) - (row.credit or Decimal("0"))

            if amount != 0:
                section_accounts.append({
                    "account": acc.account_name,
                    "account_type": acc.account_type,
                    "amount": float(amount),
                })
                total += amount

        section_accounts.sort(key=lambda x: -abs(x["amount"]))

        return {
            "accounts": section_accounts,
            "total": float(total),
        }

    income = build_section(AccountType.INCOME)
    expenses = build_section(AccountType.EXPENSE)

    gross_profit = income["total"]
    net_income = income["total"] - expenses["total"]

    return {
        "period": {
            "start_date": period_start.isoformat(),
            "end_date": period_end.isoformat(),
            "fiscal_year": fiscal_year,
        },
        "income": income,
        "expenses": expenses,
        "gross_profit": gross_profit,
        "net_income": net_income,
        "profit_margin": round(net_income / gross_profit * 100, 2) if gross_profit else 0,
    }


# ============= GENERAL LEDGER =============

@router.get("/general-ledger", dependencies=[Depends(Require("accounting:read"))])
async def get_general_ledger(
    account: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    party_type: Optional[str] = None,
    party: Optional[str] = None,
    voucher_type: Optional[str] = None,
    currency: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get general ledger transactions (single-currency, filterable/paginated).

    Args:
        account: Filter by account
        start_date: Filter from date
        end_date: Filter to date
        party_type: Filter by party type (Customer, Supplier)
        party: Filter by party name
        voucher_type: Filter by voucher type
        currency: Require single currency if dataset has more than one
        limit: Max records to return
        offset: Pagination offset
    """
    query = db.query(GLEntry).filter(GLEntry.is_cancelled == False)

    if account:
        query = query.filter(GLEntry.account.ilike(f"%{account}%"))

    if start_date:
        query = query.filter(GLEntry.posting_date >= _parse_date(start_date, "start_date"))

    if end_date:
        query = query.filter(GLEntry.posting_date <= _parse_date(end_date, "end_date"))

    if party_type:
        query = query.filter(GLEntry.party_type == party_type)

    if party:
        query = query.filter(GLEntry.party.ilike(f"%{party}%"))

    if voucher_type:
        query = query.filter(GLEntry.voucher_type == voucher_type)

    total = query.count()
    entries = query.order_by(GLEntry.posting_date.desc(), GLEntry.id.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "entries": [
            {
                "id": e.id,
                "posting_date": e.posting_date.isoformat() if e.posting_date else None,
                "account": e.account,
                "party_type": e.party_type,
                "party": e.party,
                "debit": float(e.debit),
                "credit": float(e.credit),
                "voucher_type": e.voucher_type,
                "voucher_no": e.voucher_no,
                "cost_center": e.cost_center,
                "fiscal_year": e.fiscal_year,
            }
            for e in entries
        ],
    }


# ============= ACCOUNTS PAYABLE =============

@router.get("/accounts-payable", dependencies=[Depends(Require("accounting:read"))])
async def get_accounts_payable(
    as_of_date: Optional[str] = None,
    supplier: Optional[str] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get accounts payable aging report.

    Shows outstanding purchase invoices by age bucket.
    """
    cutoff = _parse_date(as_of_date, "as_of_date") or date.today()
    currency = _resolve_currency_or_raise(db, PurchaseInvoice.currency, currency)

    query = db.query(PurchaseInvoice).filter(
        PurchaseInvoice.outstanding_amount > 0,
        PurchaseInvoice.status.in_([
            PurchaseInvoiceStatus.SUBMITTED,
            PurchaseInvoiceStatus.UNPAID,
            PurchaseInvoiceStatus.OVERDUE,
        ]),
    )

    if supplier:
        query = query.filter(PurchaseInvoice.supplier.ilike(f"%{supplier}%"))

    if currency:
        query = query.filter(PurchaseInvoice.currency == currency)

    invoices = query.all()

    # Age buckets
    buckets = {
        "current": {"count": 0, "total": Decimal("0"), "invoices": []},
        "1_30": {"count": 0, "total": Decimal("0"), "invoices": []},
        "31_60": {"count": 0, "total": Decimal("0"), "invoices": []},
        "61_90": {"count": 0, "total": Decimal("0"), "invoices": []},
        "over_90": {"count": 0, "total": Decimal("0"), "invoices": []},
    }

    for inv in invoices:
        due = inv.due_date.date() if inv.due_date else (inv.posting_date.date() if inv.posting_date else cutoff)
        days_overdue = (cutoff - due).days if cutoff > due else 0

        if days_overdue <= 0:
            bucket = "current"
        elif days_overdue <= 30:
            bucket = "1_30"
        elif days_overdue <= 60:
            bucket = "31_60"
        elif days_overdue <= 90:
            bucket = "61_90"
        else:
            bucket = "over_90"

        buckets[bucket]["count"] += 1
        buckets[bucket]["total"] += inv.outstanding_amount
        buckets[bucket]["invoices"].append({
            "id": inv.id,
            "invoice_no": inv.erpnext_id,
            "supplier": inv.supplier_name or inv.supplier,
            "posting_date": inv.posting_date.isoformat() if inv.posting_date else None,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "grand_total": float(inv.grand_total),
            "outstanding": float(inv.outstanding_amount),
            "days_overdue": days_overdue,
        })

    # Convert totals to float
    for bucket in buckets.values():
        bucket["total"] = float(bucket["total"])

    total_payable = sum(b["total"] for b in buckets.values())

    return {
        "as_of_date": cutoff.isoformat(),
        "total_payable": total_payable,
        "total_invoices": sum(b["count"] for b in buckets.values()),
        "aging": buckets,
    }


# ============= ACCOUNTS RECEIVABLE =============

@router.get("/accounts-receivable", dependencies=[Depends(Require("accounting:read"))])
async def get_accounts_receivable(
    as_of_date: Optional[str] = None,
    customer_id: Optional[int] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get accounts receivable aging report (single-currency).

    Shows outstanding customer invoices by age bucket.
    """
    cutoff = _parse_date(as_of_date, "as_of_date") or date.today()
    currency = _resolve_currency_or_raise(db, Invoice.currency, currency)

    query = db.query(Invoice).options(
        joinedload(Invoice.customer)
    ).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]),
    )

    if customer_id:
        query = query.filter(Invoice.customer_id == customer_id)

    if currency:
        query = query.filter(Invoice.currency == currency)

    invoices = query.all()

    # Age buckets
    buckets = {
        "current": {"count": 0, "total": Decimal("0"), "invoices": []},
        "1_30": {"count": 0, "total": Decimal("0"), "invoices": []},
        "31_60": {"count": 0, "total": Decimal("0"), "invoices": []},
        "61_90": {"count": 0, "total": Decimal("0"), "invoices": []},
        "over_90": {"count": 0, "total": Decimal("0"), "invoices": []},
    }

    for inv in invoices:
        due = inv.due_date.date() if inv.due_date else inv.invoice_date.date()
        days_overdue = (cutoff - due).days if cutoff > due else 0
        outstanding = inv.total_amount - inv.amount_paid

        if outstanding <= 0:
            continue

        if days_overdue <= 0:
            bucket = "current"
        elif days_overdue <= 30:
            bucket = "1_30"
        elif days_overdue <= 60:
            bucket = "31_60"
        elif days_overdue <= 90:
            bucket = "61_90"
        else:
            bucket = "over_90"

        buckets[bucket]["count"] += 1
        buckets[bucket]["total"] += outstanding
        buckets[bucket]["invoices"].append({
            "id": inv.id,
            "invoice_no": inv.invoice_number,
            "customer_id": inv.customer_id,
            "customer_name": inv.customer.name if inv.customer else None,
            "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "total_amount": float(inv.total_amount),
            "amount_paid": float(inv.amount_paid),
            "outstanding": float(outstanding),
            "days_overdue": days_overdue,
        })

    # Convert totals to float
    for bucket in buckets.values():
        bucket["total"] = float(bucket["total"])

    total_receivable = sum(b["total"] for b in buckets.values())

    return {
        "as_of_date": cutoff.isoformat(),
        "total_receivable": total_receivable,
        "total_invoices": sum(b["count"] for b in buckets.values()),
        "aging": buckets,
    }


# ============= CASH FLOW =============

@router.get("/cash-flow", dependencies=[Depends(Require("accounting:read"))])
async def get_cash_flow(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get cash flow statement.

    Shows cash inflows and outflows from operating, investing, and financing activities.
    """
    # Determine date range
    if fiscal_year:
        period_start, period_end = _get_fiscal_year_dates(db, fiscal_year)
    else:
        period_end = _parse_date(end_date, "end_date") or date.today()
        period_start = _parse_date(start_date, "start_date") or date(period_end.year, 1, 1)

    # Get bank/cash accounts
    cash_accounts = db.query(Account).filter(
        Account.account_type.in_(["Bank", "Cash"]),
        Account.disabled == False,
    ).all()
    cash_account_names = [acc.erpnext_id for acc in cash_accounts]

    # Get opening and closing cash balances
    def get_cash_balance(as_of: date) -> Decimal:
        result = db.query(
            func.sum(GLEntry.debit - GLEntry.credit)
        ).filter(
            GLEntry.account.in_(cash_account_names),
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= as_of,
        )
        result = result.scalar()
        return result or Decimal("0")

    opening_cash = get_cash_balance(period_start - timedelta(days=1)) if period_start else Decimal("0")
    closing_cash = get_cash_balance(period_end)

    # Get cash movements by category
    # This is a simplified version - proper cash flow requires account classification

    # Bank transactions for the period
    bank_txns_query = db.query(BankTransaction).filter(
        BankTransaction.date >= period_start,
        BankTransaction.date <= period_end,
    )
    bank_txns = bank_txns_query.all()

    deposits = sum(t.deposit for t in bank_txns)
    withdrawals = sum(t.withdrawal for t in bank_txns)

    # Journal entries affecting cash accounts
    cash_entries = db.query(
        GLEntry.voucher_type,
        func.sum(GLEntry.debit).label("inflow"),
        func.sum(GLEntry.credit).label("outflow"),
    ).filter(
        GLEntry.account.in_(cash_account_names),
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= period_start,
        GLEntry.posting_date <= period_end,
    )
    cash_entries = cash_entries.group_by(GLEntry.voucher_type).all()

    by_voucher_type = {
        row.voucher_type: {
            "inflow": float(row.inflow or 0),
            "outflow": float(row.outflow or 0),
            "net": float((row.inflow or 0) - (row.outflow or 0)),
        }
        for row in cash_entries
    }

    # Categorize (simplified)
    operating = Decimal("0")
    investing = Decimal("0")
    financing = Decimal("0")

    for vtype, flows in by_voucher_type.items():
        net = Decimal(str(flows["net"]))
        if vtype in ["Sales Invoice", "Payment Entry", "Journal Entry"]:
            operating += net
        elif vtype in ["Purchase Invoice", "Asset"]:
            investing += net
        else:
            financing += net

    net_change = closing_cash - opening_cash

    return {
        "period": {
            "start_date": period_start.isoformat(),
            "end_date": period_end.isoformat(),
            "fiscal_year": fiscal_year,
        },
        "opening_cash": float(opening_cash),
        "closing_cash": float(closing_cash),
        "net_change": float(net_change),
        "operating_activities": float(operating),
        "investing_activities": float(investing),
        "financing_activities": float(financing),
        "bank_deposits": float(deposits),
        "bank_withdrawals": float(withdrawals),
        "by_voucher_type": by_voucher_type,
    }


# ============= JOURNAL ENTRIES =============

@router.get("/journal-entries", dependencies=[Depends(Require("accounting:read"))])
async def get_journal_entries(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    voucher_type: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get journal entries list."""
    query = db.query(JournalEntry)

    if start_date:
        query = query.filter(JournalEntry.posting_date >= _parse_date(start_date, "start_date"))

    if end_date:
        query = query.filter(JournalEntry.posting_date <= _parse_date(end_date, "end_date"))

    if voucher_type:
        try:
            vtype = JournalEntryType(voucher_type.lower())
            query = query.filter(JournalEntry.voucher_type == vtype)
        except ValueError:
            pass

    total = query.count()
    entries = query.order_by(JournalEntry.posting_date.desc(), JournalEntry.id.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "entries": [
            {
                "id": e.id,
                "erpnext_id": e.erpnext_id,
                "voucher_type": e.voucher_type.value if e.voucher_type else None,
                "posting_date": e.posting_date.isoformat() if e.posting_date else None,
                "company": e.company,
                "total_debit": float(e.total_debit),
                "total_credit": float(e.total_credit),
                "user_remark": e.user_remark,
                "is_opening": e.is_opening,
            }
            for e in entries
        ],
    }


# ============= SUPPLIERS =============

@router.get("/suppliers", dependencies=[Depends(Require("accounting:read"))])
async def get_suppliers(
    search: Optional[str] = None,
    supplier_group: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get suppliers list."""
    query = db.query(Supplier).filter(Supplier.disabled == False)

    if search:
        query = query.filter(Supplier.supplier_name.ilike(f"%{search}%"))

    if supplier_group:
        query = query.filter(Supplier.supplier_group == supplier_group)

    total = query.count()
    suppliers = query.order_by(Supplier.supplier_name).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "suppliers": [
            {
                "id": s.id,
                "erpnext_id": s.erpnext_id,
                "name": s.supplier_name,
                "group": s.supplier_group,
                "type": s.supplier_type,
                "country": s.country,
                "currency": s.default_currency,
                "email": s.email_id,
                "mobile": s.mobile_no,
            }
            for s in suppliers
        ],
    }


# ============= BANK ACCOUNTS =============

@router.get("/bank-accounts", dependencies=[Depends(Require("accounting:read"))])
async def get_bank_accounts(
    as_of_date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get bank accounts list with current balances.

    Args:
        as_of_date: Calculate balances as of this date (default: today)
    """
    accounts = db.query(BankAccount).filter(BankAccount.disabled == False).all()

    # Calculate balances from GL entries for each bank's GL account
    cutoff = _parse_date(as_of_date, "as_of_date") or date.today()
    gl_accounts = [acc.account for acc in accounts if acc.account]

    account_balances = {}
    if gl_accounts:
        balance_query = db.query(
            GLEntry.account,
            func.sum(GLEntry.debit).label("total_debit"),
            func.sum(GLEntry.credit).label("total_credit"),
        ).filter(
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= cutoff,
            GLEntry.account.in_(gl_accounts),
        ).group_by(GLEntry.account)

        for row in balance_query.all():
            debit = row.total_debit or Decimal("0")
            credit = row.total_credit or Decimal("0")
            account_balances[row.account] = float(debit - credit)

    total_balance = sum(account_balances.values())

    return {
        "total": len(accounts),
        "total_balance": total_balance,
        "as_of_date": cutoff.isoformat(),
        "accounts": [
            {
                "id": acc.id,
                "erpnext_id": acc.erpnext_id,
                "name": acc.account_name,
                "bank": acc.bank,
                "account_no": acc.bank_account_no,
                "gl_account": acc.account,
                "company": acc.company,
                "currency": acc.currency,
                "is_default": acc.is_default,
                "balance": account_balances.get(acc.account, 0.0),
            }
            for acc in accounts
        ],
    }


# ============= FISCAL YEARS =============

@router.get("/fiscal-years", dependencies=[Depends(Require("accounting:read"))])
async def get_fiscal_years(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get fiscal years list."""
    years = db.query(FiscalYear).filter(FiscalYear.disabled == False).order_by(FiscalYear.year.desc()).all()

    return {
        "total": len(years),
        "fiscal_years": [
            {
                "id": fy.id,
                "year": fy.year,
                "start_date": fy.year_start_date.isoformat() if fy.year_start_date else None,
                "end_date": fy.year_end_date.isoformat() if fy.year_end_date else None,
                "is_short_year": fy.is_short_year,
            }
            for fy in years
        ],
    }


# ============= COST CENTERS =============

@router.get("/cost-centers", dependencies=[Depends(Require("accounting:read"))])
async def get_cost_centers(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get cost centers list."""
    centers = db.query(CostCenter).filter(CostCenter.disabled == False).all()

    return {
        "total": len(centers),
        "cost_centers": [
            {
                "id": cc.id,
                "erpnext_id": cc.erpnext_id,
                "name": cc.cost_center_name,
                "number": cc.cost_center_number,
                "parent": cc.parent_cost_center,
                "company": cc.company,
                "is_group": cc.is_group,
            }
            for cc in centers
        ],
    }
