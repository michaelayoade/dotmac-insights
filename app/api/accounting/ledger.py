"""Ledger endpoints: Chart of Accounts, Account Details, GL Entries."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth import Require
from app.database import get_db
from app.models.accounting import Account, AccountType, GLEntry

from .helpers import parse_date, paginate, serialize_account

router = APIRouter()


class AccountCreateRequest(BaseModel):
    account_name: str
    account_number: Optional[str] = None
    parent_account: Optional[str] = None
    root_type: Optional[str] = None
    account_type: Optional[str] = None
    company: Optional[str] = None
    is_group: bool = False
    disabled: bool = False
    balance_must_be: Optional[str] = None


class AccountUpdateRequest(BaseModel):
    account_name: Optional[str] = None
    account_number: Optional[str] = None
    parent_account: Optional[str] = None
    root_type: Optional[str] = None
    account_type: Optional[str] = None
    company: Optional[str] = None
    is_group: Optional[bool] = None
    disabled: Optional[bool] = None
    balance_must_be: Optional[str] = None


class GLEntryCreateRequest(BaseModel):
    posting_date: Optional[date] = None
    account: Optional[str] = None
    party_type: Optional[str] = None
    party: Optional[str] = None
    debit: Optional[Decimal] = Decimal("0")
    credit: Optional[Decimal] = Decimal("0")
    debit_in_account_currency: Optional[Decimal] = None
    credit_in_account_currency: Optional[Decimal] = None
    voucher_type: Optional[str] = None
    voucher_no: Optional[str] = None
    cost_center: Optional[str] = None
    company: Optional[str] = None
    fiscal_year: Optional[str] = None
    is_cancelled: bool = False

    @validator(
        "debit",
        "credit",
        "debit_in_account_currency",
        "credit_in_account_currency",
        pre=True,
    )
    def _to_decimal(cls, value):
        if value is None:
            return None
        return Decimal(str(value))


class GLEntryUpdateRequest(BaseModel):
    posting_date: Optional[date] = None
    account: Optional[str] = None
    party_type: Optional[str] = None
    party: Optional[str] = None
    debit: Optional[Decimal] = None
    credit: Optional[Decimal] = None
    debit_in_account_currency: Optional[Decimal] = None
    credit_in_account_currency: Optional[Decimal] = None
    voucher_type: Optional[str] = None
    voucher_no: Optional[str] = None
    cost_center: Optional[str] = None
    company: Optional[str] = None
    fiscal_year: Optional[str] = None
    is_cancelled: Optional[bool] = None

    @validator(
        "debit",
        "credit",
        "debit_in_account_currency",
        "credit_in_account_currency",
        pre=True,
    )
    def _to_decimal(cls, value):
        if value is None:
            return None
        return Decimal(str(value))


# =============================================================================
# ACCOUNTS LIST
# =============================================================================

@router.get("/accounts", dependencies=[Depends(Require("accounting:read"))])
def list_accounts(
    root_type: Optional[str] = None,
    account_type: Optional[str] = None,
    is_group: Optional[bool] = None,
    include_disabled: bool = False,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List all accounts with filtering and pagination.

    Args:
        root_type: Filter by root type (asset, liability, equity, income, expense)
        account_type: Filter by account type (Bank, Cash, Receivable, Payable, etc.)
        is_group: Filter group vs leaf accounts
        include_disabled: Include disabled accounts
        search: Search by account name

    Returns:
        Paginated list of accounts
    """
    query = db.query(Account)

    if root_type:
        try:
            root_type_enum = AccountType(root_type.lower())
            query = query.filter(Account.root_type == root_type_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid root_type: {root_type}")

    if account_type:
        query = query.filter(Account.account_type == account_type)

    if is_group is not None:
        query = query.filter(Account.is_group == is_group)

    if not include_disabled:
        query = query.filter(Account.disabled == False)

    if search:
        query = query.filter(Account.account_name.ilike(f"%{search}%"))

    query = query.order_by(Account.account_name)
    total, accounts = paginate(query, offset, limit)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "accounts": [serialize_account(acc) for acc in accounts],
    }


# =============================================================================
# ACCOUNT DETAIL
# =============================================================================

@router.get("/accounts/{account_id}", dependencies=[Depends(Require("accounting:read"))])
def get_account_detail(
    account_id: int,
    include_ledger: bool = True,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed account information with optional transaction ledger.

    Args:
        account_id: Account ID
        include_ledger: Include recent GL entries for this account
        start_date: Filter ledger from date
        end_date: Filter ledger to date
        limit: Max ledger entries to return

    Returns:
        Account details with optional ledger entries
    """
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Calculate current balance
    balance_result = db.query(
        func.sum(GLEntry.debit).label("total_debit"),
        func.sum(GLEntry.credit).label("total_credit"),
    ).filter(
        GLEntry.account == account.erpnext_id,
        GLEntry.is_cancelled == False,
    ).first()

    totals = balance_result._mapping if balance_result else {}
    total_debit = totals.get("total_debit") or Decimal("0")
    total_credit = totals.get("total_credit") or Decimal("0")
    balance = total_debit - total_credit

    # Determine normal balance type
    if account.root_type in [AccountType.ASSET, AccountType.EXPENSE]:
        normal_balance = "debit"
    else:
        normal_balance = "credit"

    result: Dict[str, Any] = {
        "id": account.id,
        "erpnext_id": account.erpnext_id,
        "name": account.account_name,
        "account_number": account.account_number,
        "parent_account": account.parent_account,
        "root_type": account.root_type.value if account.root_type else None,
        "account_type": account.account_type,
        "is_group": account.is_group,
        "disabled": account.disabled,
        "normal_balance": normal_balance,
        "total_debit": float(total_debit),
        "total_credit": float(total_credit),
        "balance": float(balance),
        "balance_type": "Dr" if balance >= 0 else "Cr",
    }

    if include_ledger:
        ledger_query = db.query(GLEntry).filter(
            GLEntry.account == account.erpnext_id,
            GLEntry.is_cancelled == False,
        )

        if start_date:
            ledger_query = ledger_query.filter(GLEntry.posting_date >= parse_date(start_date, "start_date"))
        if end_date:
            ledger_query = ledger_query.filter(GLEntry.posting_date <= parse_date(end_date, "end_date"))

        entries = ledger_query.order_by(GLEntry.posting_date.desc(), GLEntry.id.desc()).limit(limit).all()

        ledger_entries = [
            {
                "id": e.id,
                "posting_date": e.posting_date.isoformat() if e.posting_date else None,
                "party_type": e.party_type,
                "party": e.party,
                "debit": float(e.debit),
                "credit": float(e.credit),
                "voucher_type": e.voucher_type,
                "voucher_no": e.voucher_no,
                "cost_center": e.cost_center,
            }
            for e in entries
        ]
        result["ledger"] = ledger_entries
        result["ledger_count"] = len(entries)

    return result


# =============================================================================
# ACCOUNT CRUD
# =============================================================================

@router.post("/accounts", dependencies=[Depends(Require("accounting:write"))])
def create_account(
    payload: AccountCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a chart of accounts entry locally."""
    root_type_enum = None
    if payload.root_type:
        try:
            root_type_enum = AccountType(payload.root_type.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid root_type: {payload.root_type}")

    account = Account(
        account_name=payload.account_name,
        account_number=payload.account_number,
        parent_account=payload.parent_account,
        root_type=root_type_enum,
        account_type=payload.account_type,
        company=payload.company,
        is_group=payload.is_group,
        disabled=payload.disabled,
        balance_must_be=payload.balance_must_be,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return {"id": account.id}


@router.patch("/accounts/{account_id}", dependencies=[Depends(Require("accounting:write"))])
def update_account(
    account_id: int,
    payload: AccountUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a chart of accounts entry locally."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "root_type" in update_data and update_data["root_type"]:
        try:
            update_data["root_type"] = AccountType(update_data["root_type"].lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid root_type: {update_data['root_type']}")

    for key, value in update_data.items():
        setattr(account, key, value)

    db.commit()
    db.refresh(account)
    return {"id": account.id}


@router.delete("/accounts/{account_id}", dependencies=[Depends(Require("accounting:write"))])
def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Disable a chart of accounts entry."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account.disabled = True
    db.commit()
    return {"status": "disabled", "account_id": account_id}


# =============================================================================
# ACCOUNT LEDGER (with running balance)
# =============================================================================

@router.get("/accounts/{account_id}/ledger", dependencies=[Depends(Require("accounting:read"))])
def get_account_ledger(
    account_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    party_type: Optional[str] = None,
    party: Optional[str] = None,
    voucher_type: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get ledger (GL entries) for a specific account with running balance.

    Args:
        account_id: Account ID
        start_date: Filter from date
        end_date: Filter to date
        party_type: Filter by party type
        party: Filter by party name
        voucher_type: Filter by voucher type
        limit: Max entries per page
        offset: Pagination offset

    Returns:
        Ledger entries with running balance
    """
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Base query
    query = db.query(GLEntry).filter(
        GLEntry.account == account.erpnext_id,
        GLEntry.is_cancelled == False,
    )

    # Calculate opening balance (before start_date)
    opening_balance = Decimal("0")
    start_dt = parse_date(start_date, "start_date")
    end_dt = parse_date(end_date, "end_date")

    if start_dt:
        opening_result = db.query(
            func.sum(GLEntry.debit - GLEntry.credit)
        ).filter(
            GLEntry.account == account.erpnext_id,
            GLEntry.is_cancelled == False,
            GLEntry.posting_date < start_dt,
        ).scalar()
        opening_balance = opening_result or Decimal("0")
        query = query.filter(GLEntry.posting_date >= start_dt)

    if end_dt:
        query = query.filter(GLEntry.posting_date <= end_dt)

    if party_type:
        query = query.filter(GLEntry.party_type == party_type)
    if party:
        query = query.filter(GLEntry.party.ilike(f"%{party}%"))
    if voucher_type:
        query = query.filter(GLEntry.voucher_type == voucher_type)

    total = query.count()
    entries = query.order_by(GLEntry.posting_date.asc(), GLEntry.id.asc()).offset(offset).limit(limit).all()

    # Calculate running balance
    ledger = []
    running_balance = opening_balance
    for e in entries:
        running_balance += e.debit - e.credit
        ledger.append({
            "id": e.id,
            "posting_date": e.posting_date.isoformat() if e.posting_date else None,
            "party_type": e.party_type,
            "party": e.party,
            "debit": float(e.debit),
            "credit": float(e.credit),
            "balance": float(running_balance),
            "voucher_type": e.voucher_type,
            "voucher_no": e.voucher_no,
            "cost_center": e.cost_center,
        })

    return {
        "account": {
            "id": account.id,
            "name": account.account_name,
            "root_type": account.root_type.value if account.root_type else None,
        },
        "period": {
            "start_date": start_dt.isoformat() if start_dt else None,
            "end_date": end_dt.isoformat() if end_dt else None,
        },
        "opening_balance": float(opening_balance),
        "closing_balance": float(running_balance) if ledger else float(opening_balance),
        "total": total,
        "limit": limit,
        "offset": offset,
        "entries": ledger,
    }


# =============================================================================
# CHART OF ACCOUNTS
# =============================================================================

@router.get("/chart-of-accounts", dependencies=[Depends(Require("accounting:read"))])
def get_chart_of_accounts(
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

    Returns:
        Chart of accounts in both flat and tree formats
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
    account_balances: Dict[str, float] = {}
    if include_balances:
        cutoff = parse_date(as_of_date, "as_of_date") or date.today()
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
    def build_tree(accs: List[Account], parent: Optional[str] = None) -> List[Dict]:
        tree = []
        for acc in accs:
            if acc.parent_account == parent:
                balance = account_balances.get(acc.erpnext_id or "", 0.0)
                node = {
                    "id": acc.id,
                    "name": acc.account_name,
                    "account_number": acc.account_number,
                    "root_type": acc.root_type.value if acc.root_type else None,
                    "account_type": acc.account_type,
                    "is_group": acc.is_group,
                    "disabled": acc.disabled,
                    "balance": balance,
                    "children": build_tree(accs, acc.erpnext_id) if acc.is_group else [],
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
            "balance": account_balances.get(acc.erpnext_id or "", 0.0),
        }
        for acc in accounts
    ]

    # Group by root type
    by_root_type: Dict[str, List[str]] = {}
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


# =============================================================================
# GENERAL LEDGER
# =============================================================================

@router.get("/general-ledger", dependencies=[Depends(Require("accounting:read"))])
def get_general_ledger(
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
    """Get general ledger transactions with filtering and pagination.

    Args:
        account: Filter by account
        start_date: Filter from date
        end_date: Filter to date
        party_type: Filter by party type (Customer, Supplier)
        party: Filter by party name
        voucher_type: Filter by voucher type
        currency: Currency filter (reserved for future use)
        limit: Max records to return
        offset: Pagination offset

    Returns:
        Paginated GL entries
    """
    query = db.query(GLEntry).filter(GLEntry.is_cancelled == False)

    if account:
        query = query.filter(GLEntry.account.ilike(f"%{account}%"))

    if start_date:
        query = query.filter(GLEntry.posting_date >= parse_date(start_date, "start_date"))

    if end_date:
        query = query.filter(GLEntry.posting_date <= parse_date(end_date, "end_date"))

    if party_type:
        query = query.filter(GLEntry.party_type == party_type)

    if party:
        query = query.filter(GLEntry.party.ilike(f"%{party}%"))

    if voucher_type:
        query = query.filter(GLEntry.voucher_type == voucher_type)

    query = query.order_by(GLEntry.posting_date.desc(), GLEntry.id.desc())
    total, entries = paginate(query, offset, limit)

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


# =============================================================================
# GL ENTRIES LIST
# =============================================================================

@router.get("/gl-entries", dependencies=[Depends(Require("accounting:read"))])
def list_gl_entries(
    account: Optional[str] = None,
    voucher_type: Optional[str] = None,
    voucher_no: Optional[str] = None,
    party_type: Optional[str] = None,
    party: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    is_cancelled: Optional[bool] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query(default="posting_date", description="posting_date,account,debit,credit"),
    sort_dir: Optional[str] = Query(default="desc"),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List GL entries with filtering and sorting.

    Args:
        account: Filter by account name
        voucher_type: Filter by voucher type
        voucher_no: Filter by voucher number
        party_type: Filter by party type
        party: Filter by party name
        start_date: Filter from date
        end_date: Filter to date
        is_cancelled: Filter by cancelled status
        search: Search across account, voucher_no, party
        sort_by: Field to sort by
        sort_dir: Sort direction (asc/desc)
        limit: Max entries per page
        offset: Pagination offset

    Returns:
        Paginated GL entries
    """
    query = db.query(GLEntry)

    if account:
        query = query.filter(GLEntry.account.ilike(f"%{account}%"))

    if voucher_type:
        query = query.filter(GLEntry.voucher_type == voucher_type)

    if voucher_no:
        query = query.filter(GLEntry.voucher_no.ilike(f"%{voucher_no}%"))

    if party_type:
        query = query.filter(GLEntry.party_type == party_type)

    if party:
        query = query.filter(GLEntry.party.ilike(f"%{party}%"))

    if start_date:
        start_dt = parse_date(start_date, "start_date")
        if start_dt:
            query = query.filter(GLEntry.posting_date >= start_dt)

    if end_date:
        end_dt = parse_date(end_date, "end_date")
        if end_dt:
            query = query.filter(GLEntry.posting_date <= end_dt)

    if is_cancelled is not None:
        query = query.filter(GLEntry.is_cancelled == is_cancelled)

    if search:
        query = query.filter(
            or_(
                GLEntry.account.ilike(f"%{search}%"),
                GLEntry.voucher_no.ilike(f"%{search}%"),
                GLEntry.party.ilike(f"%{search}%"),
            )
        )

    # Sorting
    sort_key = sort_by or "posting_date"
    sort_column = getattr(GLEntry, sort_key, GLEntry.posting_date)
    if sort_dir == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    total, entries = paginate(query, offset, limit)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
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
                "is_cancelled": e.is_cancelled,
            }
            for e in entries
        ],
    }


# =============================================================================
# GL ENTRY DETAIL
# =============================================================================

@router.get("/gl-entries/{entry_id}", dependencies=[Depends(Require("accounting:read"))])
def get_gl_entry_detail(
    entry_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get single GL entry detail.

    Args:
        entry_id: GL entry ID

    Returns:
        GL entry with account details
    """
    entry = db.query(GLEntry).filter(GLEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="GL entry not found")

    # Get account details
    account = db.query(Account).filter(Account.erpnext_id == entry.account).first()

    return {
        "id": entry.id,
        "erpnext_id": entry.erpnext_id,
        "posting_date": entry.posting_date.isoformat() if entry.posting_date else None,
        "account": entry.account,
        "account_name": account.account_name if account else None,
        "root_type": account.root_type.value if account and account.root_type else None,
        "party_type": entry.party_type,
        "party": entry.party,
        "debit": float(entry.debit),
        "credit": float(entry.credit),
        "voucher_type": entry.voucher_type,
        "voucher_no": entry.voucher_no,
        "cost_center": entry.cost_center,
        "fiscal_year": entry.fiscal_year,
        "is_cancelled": entry.is_cancelled,
        "company": entry.company,
    }


# =============================================================================
# GL ENTRY CRUD
# =============================================================================

@router.post("/gl-entries", dependencies=[Depends(Require("accounting:write"))])
def create_gl_entry(
    payload: GLEntryCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a GL entry locally."""
    entry = GLEntry(
        posting_date=payload.posting_date,
        account=payload.account,
        party_type=payload.party_type,
        party=payload.party,
        debit=payload.debit or Decimal("0"),
        credit=payload.credit or Decimal("0"),
        debit_in_account_currency=payload.debit_in_account_currency
        if payload.debit_in_account_currency is not None
        else payload.debit or Decimal("0"),
        credit_in_account_currency=payload.credit_in_account_currency
        if payload.credit_in_account_currency is not None
        else payload.credit or Decimal("0"),
        voucher_type=payload.voucher_type,
        voucher_no=payload.voucher_no,
        cost_center=payload.cost_center,
        company=payload.company,
        fiscal_year=payload.fiscal_year,
        is_cancelled=payload.is_cancelled,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"id": entry.id}


@router.patch("/gl-entries/{entry_id}", dependencies=[Depends(Require("accounting:write"))])
def update_gl_entry(
    entry_id: int,
    payload: GLEntryUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a GL entry locally."""
    entry = db.query(GLEntry).filter(GLEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="GL entry not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(entry, key, value)

    db.commit()
    db.refresh(entry)
    return {"id": entry.id}


@router.delete("/gl-entries/{entry_id}", dependencies=[Depends(Require("accounting:write"))])
def delete_gl_entry(
    entry_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a GL entry."""
    entry = db.query(GLEntry).filter(GLEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="GL entry not found")

    db.delete(entry)
    db.commit()
    return {"status": "deleted", "gl_entry_id": entry_id}


# =============================================================================
# ACCOUNT TYPES
# =============================================================================

@router.get("/account-types", dependencies=[Depends(Require("accounting:read"))])
def get_account_types(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get summary of accounts grouped by account type.

    Returns:
        Account types with counts
    """
    # Query distinct account types with counts
    type_counts = db.query(
        Account.account_type,
        Account.root_type,
        func.count(Account.id).label("count"),
    ).filter(
        Account.disabled == False,
    ).group_by(Account.account_type, Account.root_type).all()

    by_type: Dict[str, Dict] = {}
    for row in type_counts:
        acc_type = row.account_type or "Unspecified"
        if acc_type not in by_type:
            by_type[acc_type] = {
                "count": 0,
                "root_types": [],
            }
        by_type[acc_type]["count"] += row.count
        rt = row.root_type.value if row.root_type else "unknown"
        if rt not in by_type[acc_type]["root_types"]:
            by_type[acc_type]["root_types"].append(rt)

    # Standard root types
    root_types = [rt.value for rt in AccountType]

    return {
        "root_types": root_types,
        "account_types": by_type,
        "total_types": len(by_type),
    }
