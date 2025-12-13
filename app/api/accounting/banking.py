"""Banking: Bank accounts, bank transactions."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.auth import Require
from app.database import get_db
from app.models.accounting import (
    BankAccount,
    BankTransaction,
    BankTransactionStatus,
    GLEntry,
)

from .helpers import parse_date, paginate

router = APIRouter()


# =============================================================================
# BANK ACCOUNTS
# =============================================================================

@router.get("/bank-accounts", dependencies=[Depends(Require("accounting:read"))])
def get_bank_accounts(
    as_of_date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get bank accounts list with current balances.

    Args:
        as_of_date: Calculate balances as of this date (default: today)

    Returns:
        List of bank accounts with GL-derived balances
    """
    accounts = db.query(BankAccount).filter(BankAccount.disabled == False).all()

    # Calculate balances from GL entries for each bank's GL account
    cutoff = parse_date(as_of_date, "as_of_date") or date.today()
    gl_accounts = [acc.account for acc in accounts if acc.account]

    account_balances: Dict[str, float] = {}
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


# =============================================================================
# BANK TRANSACTIONS
# =============================================================================

@router.get("/bank-transactions", dependencies=[Depends(Require("accounting:read"))])
def list_bank_transactions(
    bank_account: Optional[str] = None,
    status: Optional[str] = None,
    transaction_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    unallocated_only: bool = False,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query(default="date", description="date,deposit,withdrawal,unallocated_amount"),
    sort_dir: Optional[str] = Query(default="desc"),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List bank transactions with filtering.

    Args:
        bank_account: Filter by bank account name
        status: Filter by status
        transaction_type: Filter by transaction type
        start_date: Filter from date
        end_date: Filter to date
        min_amount: Minimum amount filter
        max_amount: Maximum amount filter
        unallocated_only: Only show unallocated transactions
        search: Search description, reference, party name
        sort_by: Sort field
        sort_dir: Sort direction
        limit: Max results
        offset: Pagination offset

    Returns:
        Paginated bank transactions
    """
    query = db.query(BankTransaction)

    if bank_account:
        query = query.filter(BankTransaction.bank_account.ilike(f"%{bank_account}%"))

    if status:
        try:
            status_enum = BankTransactionStatus(status.lower())
            query = query.filter(BankTransaction.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if transaction_type:
        query = query.filter(BankTransaction.transaction_type == transaction_type)

    if start_date:
        start_dt = parse_date(start_date, "start_date")
        if start_dt:
            query = query.filter(BankTransaction.date >= start_dt)

    if end_date:
        end_dt = parse_date(end_date, "end_date")
        if end_dt:
            query = query.filter(BankTransaction.date <= end_dt)

    if min_amount:
        query = query.filter(
            or_(
                BankTransaction.deposit >= min_amount,
                BankTransaction.withdrawal >= min_amount,
            )
        )

    if max_amount:
        query = query.filter(
            and_(
                or_(BankTransaction.deposit <= max_amount, BankTransaction.deposit == 0),
                or_(BankTransaction.withdrawal <= max_amount, BankTransaction.withdrawal == 0),
            )
        )

    if unallocated_only:
        query = query.filter(BankTransaction.unallocated_amount > 0)

    if search:
        query = query.filter(
            or_(
                BankTransaction.description.ilike(f"%{search}%"),
                BankTransaction.reference_number.ilike(f"%{search}%"),
                BankTransaction.bank_party_name.ilike(f"%{search}%"),
            )
        )

    # Sorting
    sort_column = getattr(BankTransaction, sort_by, BankTransaction.date)
    if sort_dir == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    total, transactions = paginate(query, offset, limit)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": t.id,
                "date": t.date.isoformat() if t.date else None,
                "bank_account": t.bank_account,
                "deposit": float(t.deposit) if t.deposit else 0,
                "withdrawal": float(t.withdrawal) if t.withdrawal else 0,
                "currency": t.currency,
                "description": t.description,
                "reference_number": t.reference_number,
                "transaction_type": t.transaction_type,
                "status": t.status.value if t.status else None,
                "allocated_amount": float(t.allocated_amount) if t.allocated_amount else 0,
                "unallocated_amount": float(t.unallocated_amount) if t.unallocated_amount else 0,
                "party": t.party,
                "party_type": t.party_type,
            }
            for t in transactions
        ],
    }


@router.get("/bank-transactions/{transaction_id}", dependencies=[Depends(Require("accounting:read"))])
def get_bank_transaction_detail(
    transaction_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get bank transaction detail.

    Args:
        transaction_id: Bank transaction ID

    Returns:
        Full bank transaction details
    """
    txn = db.query(BankTransaction).filter(BankTransaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Bank transaction not found")

    return {
        "id": txn.id,
        "erpnext_id": txn.erpnext_id,
        "date": txn.date.isoformat() if txn.date else None,
        "bank_account": txn.bank_account,
        "deposit": float(txn.deposit) if txn.deposit else 0,
        "withdrawal": float(txn.withdrawal) if txn.withdrawal else 0,
        "currency": txn.currency,
        "description": txn.description,
        "reference_number": txn.reference_number,
        "transaction_id": txn.transaction_id,
        "transaction_type": txn.transaction_type,
        "status": txn.status.value if txn.status else None,
        "allocation": {
            "allocated_amount": float(txn.allocated_amount) if txn.allocated_amount else 0,
            "unallocated_amount": float(txn.unallocated_amount) if txn.unallocated_amount else 0,
        },
        "party": {
            "party_type": txn.party_type,
            "party": txn.party,
            "bank_party_name": txn.bank_party_name,
            "bank_party_account_number": txn.bank_party_account_number,
            "bank_party_iban": txn.bank_party_iban,
        },
        "docstatus": txn.docstatus,
    }
