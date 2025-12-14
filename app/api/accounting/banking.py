"""Banking: Bank accounts, bank transactions, CRUD, splits, import, reconciliation."""
from __future__ import annotations

import csv
import io
import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.auth import Require
from app.database import get_db
from app.models.accounting import (
    BankAccount,
    BankTransaction,
    BankTransactionStatus,
    GLEntry,
    PurchaseInvoice,
)
from app.models.bank_transaction_split import BankTransactionSplit
from app.models.invoice import Invoice

from .helpers import parse_date, paginate

router = APIRouter()


# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class BankTransactionSplitCreate(BaseModel):
    """Schema for creating a bank transaction split."""
    amount: float
    account: Optional[str] = None
    cost_center: Optional[str] = None
    tax_code_id: Optional[int] = None
    tax_rate: float = 0
    tax_amount: float = 0
    memo: Optional[str] = None
    party_type: Optional[str] = None
    party: Optional[str] = None


class BankTransactionCreate(BaseModel):
    """Schema for creating a manual bank transaction."""
    date: str
    bank_account: str
    deposit: float = 0
    withdrawal: float = 0
    currency: str = "NGN"
    description: Optional[str] = None
    reference_number: Optional[str] = None
    transaction_type: Optional[str] = None
    payee_name: Optional[str] = None
    payee_account: Optional[str] = None
    party_type: Optional[str] = None
    party: Optional[str] = None
    splits: List[BankTransactionSplitCreate] = []


class BankTransactionUpdate(BaseModel):
    """Schema for updating a bank transaction."""
    date: Optional[str] = None
    bank_account: Optional[str] = None
    deposit: Optional[float] = None
    withdrawal: Optional[float] = None
    description: Optional[str] = None
    reference_number: Optional[str] = None
    transaction_type: Optional[str] = None
    payee_name: Optional[str] = None
    payee_account: Optional[str] = None
    party_type: Optional[str] = None
    party: Optional[str] = None


class ReconciliationAllocation(BaseModel):
    """Schema for a single reconciliation allocation."""
    document_type: str  # "Sales Invoice" or "Purchase Invoice"
    document_id: int
    allocated_amount: float


class ReconcileRequest(BaseModel):
    """Schema for reconciling a bank transaction with documents."""
    allocations: List[ReconciliationAllocation]
    create_payment_entry: bool = False


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
        "is_manual_entry": txn.is_manual_entry,
        "payee_name": txn.payee_name,
        "payee_account": txn.payee_account,
        "base_currency": txn.base_currency,
        "conversion_rate": float(txn.conversion_rate) if txn.conversion_rate else 1,
        "base_amount": float(txn.base_amount) if txn.base_amount else 0,
        "splits": [
            {
                "id": s.id,
                "amount": float(s.amount),
                "account": s.account,
                "cost_center": s.cost_center,
                "tax_code_id": s.tax_code_id,
                "tax_rate": float(s.tax_rate) if s.tax_rate else 0,
                "tax_amount": float(s.tax_amount) if s.tax_amount else 0,
                "memo": s.memo,
                "party_type": s.party_type,
                "party": s.party,
            }
            for s in getattr(txn, "splits", [])
        ],
    }


# =============================================================================
# BANK TRANSACTIONS CRUD
# =============================================================================

@router.post("/bank-transactions", dependencies=[Depends(Require("books:write"))])
def create_bank_transaction(
    data: BankTransactionCreate,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Create a manual bank transaction.

    Args:
        data: Bank transaction data

    Returns:
        Created transaction details
    """
    # Validate date
    try:
        txn_date = datetime.fromisoformat(data.date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    # Create transaction
    txn = BankTransaction(
        date=txn_date,
        bank_account=data.bank_account,
        deposit=Decimal(str(data.deposit)),
        withdrawal=Decimal(str(data.withdrawal)),
        currency=data.currency,
        description=data.description,
        reference_number=data.reference_number,
        transaction_type=data.transaction_type,
        payee_name=data.payee_name,
        payee_account=data.payee_account,
        party_type=data.party_type,
        party=data.party,
        status=BankTransactionStatus.UNRECONCILED,
        is_manual_entry=True,
        created_by_id=user.id,
    )

    # Calculate unallocated amount
    amount = txn.deposit if txn.deposit > 0 else txn.withdrawal
    txn.unallocated_amount = amount
    txn.allocated_amount = Decimal("0")

    db.add(txn)
    db.flush()

    # Add splits if provided
    for idx, split_data in enumerate(data.splits):
        split = BankTransactionSplit(
            bank_transaction_id=txn.id,
            amount=Decimal(str(split_data.amount)),
            account=split_data.account,
            cost_center=split_data.cost_center,
            tax_code_id=split_data.tax_code_id,
            tax_rate=Decimal(str(split_data.tax_rate)),
            tax_amount=Decimal(str(split_data.tax_amount)),
            memo=split_data.memo,
            party_type=split_data.party_type,
            party=split_data.party,
            idx=idx,
        )
        db.add(split)

    db.commit()
    db.refresh(txn)

    return {
        "message": "Bank transaction created",
        "id": txn.id,
        "date": txn.date.isoformat() if txn.date else None,
        "amount": float(amount),
    }


@router.patch("/bank-transactions/{transaction_id}", dependencies=[Depends(Require("books:write"))])
def update_bank_transaction(
    transaction_id: int,
    data: BankTransactionUpdate,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Update a bank transaction.

    Only unreconciled transactions can be updated.

    Args:
        transaction_id: Bank transaction ID
        data: Update data

    Returns:
        Updated transaction info
    """
    txn = db.query(BankTransaction).filter(BankTransaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Bank transaction not found")

    if txn.status == BankTransactionStatus.RECONCILED:
        raise HTTPException(status_code=400, detail="Cannot update reconciled transaction")

    if data.date is not None:
        try:
            txn.date = datetime.fromisoformat(data.date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")

    if data.bank_account is not None:
        txn.bank_account = data.bank_account
    if data.deposit is not None:
        txn.deposit = Decimal(str(data.deposit))
    if data.withdrawal is not None:
        txn.withdrawal = Decimal(str(data.withdrawal))
    if data.description is not None:
        txn.description = data.description
    if data.reference_number is not None:
        txn.reference_number = data.reference_number
    if data.transaction_type is not None:
        txn.transaction_type = data.transaction_type
    if data.payee_name is not None:
        txn.payee_name = data.payee_name
    if data.payee_account is not None:
        txn.payee_account = data.payee_account
    if data.party_type is not None:
        txn.party_type = data.party_type
    if data.party is not None:
        txn.party = data.party

    # Recalculate unallocated
    amount = txn.deposit if txn.deposit > 0 else txn.withdrawal
    txn.unallocated_amount = amount - txn.allocated_amount

    db.commit()

    return {
        "message": "Bank transaction updated",
        "id": txn.id,
    }


@router.delete("/bank-transactions/{transaction_id}", dependencies=[Depends(Require("books:write"))])
def delete_bank_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Delete a bank transaction.

    Only unreconciled manual entries can be deleted.

    Args:
        transaction_id: Bank transaction ID

    Returns:
        Deletion confirmation
    """
    txn = db.query(BankTransaction).filter(BankTransaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Bank transaction not found")

    if txn.status == BankTransactionStatus.RECONCILED:
        raise HTTPException(status_code=400, detail="Cannot delete reconciled transaction")

    if not txn.is_manual_entry:
        raise HTTPException(status_code=400, detail="Cannot delete imported transaction")

    # Delete splits first
    db.query(BankTransactionSplit).filter(
        BankTransactionSplit.bank_transaction_id == transaction_id
    ).delete()

    db.delete(txn)
    db.commit()

    return {"message": "Bank transaction deleted"}


# =============================================================================
# BANK TRANSACTION SPLITS
# =============================================================================

@router.post("/bank-transactions/{transaction_id}/splits", dependencies=[Depends(Require("books:write"))])
def add_transaction_splits(
    transaction_id: int,
    splits: List[BankTransactionSplitCreate],
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Add splits to a bank transaction.

    Args:
        transaction_id: Bank transaction ID
        splits: List of splits to add

    Returns:
        Created splits info
    """
    txn = db.query(BankTransaction).filter(BankTransaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Bank transaction not found")

    if txn.status == BankTransactionStatus.RECONCILED:
        raise HTTPException(status_code=400, detail="Cannot modify reconciled transaction")

    # Get current max idx
    max_idx = db.query(func.max(BankTransactionSplit.idx)).filter(
        BankTransactionSplit.bank_transaction_id == transaction_id
    ).scalar() or -1

    created_ids = []
    for idx, split_data in enumerate(splits, start=max_idx + 1):
        split = BankTransactionSplit(
            bank_transaction_id=transaction_id,
            amount=Decimal(str(split_data.amount)),
            account=split_data.account,
            cost_center=split_data.cost_center,
            tax_code_id=split_data.tax_code_id,
            tax_rate=Decimal(str(split_data.tax_rate)),
            tax_amount=Decimal(str(split_data.tax_amount)),
            memo=split_data.memo,
            party_type=split_data.party_type,
            party=split_data.party,
            idx=idx,
        )
        db.add(split)
        db.flush()
        created_ids.append(split.id)

    db.commit()

    return {
        "message": f"Added {len(created_ids)} splits",
        "split_ids": created_ids,
    }


@router.delete("/bank-transactions/{transaction_id}/splits/{split_id}", dependencies=[Depends(Require("books:write"))])
def delete_transaction_split(
    transaction_id: int,
    split_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Delete a split from a bank transaction.

    Args:
        transaction_id: Bank transaction ID
        split_id: Split ID

    Returns:
        Deletion confirmation
    """
    txn = db.query(BankTransaction).filter(BankTransaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Bank transaction not found")

    if txn.status == BankTransactionStatus.RECONCILED:
        raise HTTPException(status_code=400, detail="Cannot modify reconciled transaction")

    split = db.query(BankTransactionSplit).filter(
        BankTransactionSplit.id == split_id,
        BankTransactionSplit.bank_transaction_id == transaction_id,
    ).first()
    if not split:
        raise HTTPException(status_code=404, detail="Split not found")

    db.delete(split)
    db.commit()

    return {"message": "Split deleted"}


# =============================================================================
# RECONCILIATION
# =============================================================================

@router.post("/bank-transactions/{transaction_id}/reconcile", dependencies=[Depends(Require("books:write"))])
def reconcile_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Mark a bank transaction as reconciled.

    Args:
        transaction_id: Bank transaction ID

    Returns:
        Reconciliation status
    """
    txn = db.query(BankTransaction).filter(BankTransaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Bank transaction not found")

    if txn.status == BankTransactionStatus.RECONCILED:
        raise HTTPException(status_code=400, detail="Transaction is already reconciled")

    txn.status = BankTransactionStatus.RECONCILED
    db.commit()

    return {
        "message": "Transaction reconciled",
        "id": txn.id,
        "status": txn.status.value,
    }


@router.post("/bank-transactions/{transaction_id}/unreconcile", dependencies=[Depends(Require("books:write"))])
def unreconcile_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Unreconcile a bank transaction.

    Args:
        transaction_id: Bank transaction ID

    Returns:
        Updated status
    """
    txn = db.query(BankTransaction).filter(BankTransaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Bank transaction not found")

    if txn.status != BankTransactionStatus.RECONCILED:
        raise HTTPException(status_code=400, detail="Transaction is not reconciled")

    txn.status = BankTransactionStatus.UNRECONCILED
    db.commit()

    return {
        "message": "Transaction unreconciled",
        "id": txn.id,
        "status": txn.status.value,
    }


# =============================================================================
# BANK TRANSACTION IMPORT
# =============================================================================

def _parse_csv_content(content: str, column_mapping: Dict[str, str]) -> List[Dict[str, Any]]:
    """Parse CSV content into transaction records.

    Args:
        content: CSV file content
        column_mapping: Mapping of standard fields to CSV column names

    Returns:
        List of parsed transaction dicts
    """
    transactions = []
    reader = csv.DictReader(io.StringIO(content))

    for row_num, row in enumerate(reader, start=2):  # Start at 2 (1-indexed, skip header)
        try:
            # Parse date
            date_col = column_mapping.get("date_column", "")
            date_str = row.get(date_col, "").strip()
            if not date_str:
                continue

            # Try multiple date formats
            txn_date = None
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]:
                try:
                    txn_date = datetime.strptime(date_str[:10], fmt)
                    break
                except ValueError:
                    continue

            if not txn_date:
                continue

            # Parse amount
            deposit = Decimal("0")
            withdrawal = Decimal("0")

            if column_mapping.get("amount_column"):
                amount_str = row.get(column_mapping["amount_column"], "0")
                amount_str = re.sub(r"[^\d.\-]", "", amount_str)
                amount = Decimal(amount_str) if amount_str else Decimal("0")
                if amount >= 0:
                    deposit = amount
                else:
                    withdrawal = abs(amount)
            else:
                if column_mapping.get("deposit_column"):
                    dep_str = row.get(column_mapping["deposit_column"], "0")
                    dep_str = re.sub(r"[^\d.]", "", dep_str)
                    deposit = Decimal(dep_str) if dep_str else Decimal("0")
                if column_mapping.get("withdrawal_column"):
                    with_str = row.get(column_mapping["withdrawal_column"], "0")
                    with_str = re.sub(r"[^\d.]", "", with_str)
                    withdrawal = Decimal(with_str) if with_str else Decimal("0")

            # Skip zero transactions
            if deposit == 0 and withdrawal == 0:
                continue

            transactions.append({
                "date": txn_date,
                "deposit": deposit,
                "withdrawal": withdrawal,
                "description": row.get(column_mapping.get("description_column", ""), ""),
                "reference_number": row.get(column_mapping.get("reference_column", ""), ""),
                "row_num": row_num,
            })

        except Exception as e:
            # Skip invalid rows, will be reported as errors
            continue

    return transactions


def _parse_ofx_content(content: str) -> List[Dict[str, Any]]:
    """Parse OFX/QFX content into transaction records.

    Args:
        content: OFX file content

    Returns:
        List of parsed transaction dicts
    """
    transactions = []

    # Extract STMTTRN blocks using regex
    trn_pattern = re.compile(r"<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|(?=</BANKTRANLIST>))", re.DOTALL | re.IGNORECASE)

    def extract_tag(block: str, tag: str) -> str:
        """Extract a tag value from OFX block."""
        # Try XML style first
        xml_match = re.search(rf"<{tag}>([^<]*)</{tag}>", block, re.IGNORECASE)
        if xml_match:
            return xml_match.group(1).strip()
        # Try SGML style
        sgml_match = re.search(rf"<{tag}>([^<\n\r]+)", block, re.IGNORECASE)
        if sgml_match:
            return sgml_match.group(1).strip()
        return ""

    for row_num, match in enumerate(trn_pattern.finditer(content), start=1):
        block = match.group(1)

        # Parse date (YYYYMMDD format)
        date_str = extract_tag(block, "DTPOSTED")
        if len(date_str) < 8:
            continue
        try:
            txn_date = datetime.strptime(date_str[:8], "%Y%m%d")
        except ValueError:
            continue

        # Parse amount
        amount_str = extract_tag(block, "TRNAMT")
        try:
            amount = Decimal(amount_str)
        except:
            continue

        deposit = amount if amount >= 0 else Decimal("0")
        withdrawal = abs(amount) if amount < 0 else Decimal("0")

        # Build description from NAME and MEMO
        name = extract_tag(block, "NAME")
        memo = extract_tag(block, "MEMO")
        description = f"{name} - {memo}".strip(" -") if name or memo else ""

        # Reference from FITID or CHECKNUM
        reference = extract_tag(block, "CHECKNUM") or extract_tag(block, "FITID")

        transactions.append({
            "date": txn_date,
            "deposit": deposit,
            "withdrawal": withdrawal,
            "description": description,
            "reference_number": reference,
            "row_num": row_num,
            "fitid": extract_tag(block, "FITID"),
        })

    return transactions


@router.post("/bank-transactions/import", dependencies=[Depends(Require("books:write"))])
async def import_bank_transactions(
    file: UploadFile = File(...),
    account: str = Form(...),
    format: str = Form(...),  # "csv" or "ofx"
    column_mapping: Optional[str] = Form(None),  # JSON string for CSV
    skip_duplicates: bool = Form(True),
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Import bank transactions from CSV or OFX file.

    Args:
        file: Uploaded file (CSV or OFX)
        account: Bank account name to import into
        format: File format ("csv" or "ofx")
        column_mapping: JSON string with column mapping for CSV
        skip_duplicates: Skip transactions that already exist

    Returns:
        Import results with counts and errors
    """
    import json

    # Validate file type
    if format not in ("csv", "ofx"):
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'ofx'")

    # Read file content
    try:
        content = (await file.read()).decode("utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    # Parse transactions based on format
    if format == "csv":
        if not column_mapping:
            raise HTTPException(status_code=400, detail="column_mapping is required for CSV import")
        try:
            mapping = json.loads(column_mapping)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid column_mapping JSON")

        if not mapping.get("date_column"):
            raise HTTPException(status_code=400, detail="date_column is required in column_mapping")

        parsed = _parse_csv_content(content, mapping)
    else:
        parsed = _parse_ofx_content(content)

    if not parsed:
        return {
            "imported_count": 0,
            "skipped_count": 0,
            "errors": [{"row": 0, "error": "No valid transactions found in file"}],
            "transaction_ids": [],
        }

    # Import transactions
    imported_count = 0
    skipped_count = 0
    errors = []
    transaction_ids = []

    for txn_data in parsed:
        try:
            # Check for duplicates
            if skip_duplicates:
                existing = db.query(BankTransaction).filter(
                    BankTransaction.bank_account == account,
                    BankTransaction.date == txn_data["date"],
                    or_(
                        and_(
                            BankTransaction.deposit == txn_data["deposit"],
                            BankTransaction.withdrawal == txn_data["withdrawal"],
                        ),
                    ),
                ).first()

                # Also check by reference if available
                if not existing and txn_data.get("reference_number"):
                    existing = db.query(BankTransaction).filter(
                        BankTransaction.bank_account == account,
                        BankTransaction.reference_number == txn_data["reference_number"],
                    ).first()

                # Check by FITID for OFX
                if not existing and txn_data.get("fitid"):
                    existing = db.query(BankTransaction).filter(
                        BankTransaction.bank_account == account,
                        BankTransaction.transaction_id == txn_data["fitid"],
                    ).first()

                if existing:
                    skipped_count += 1
                    continue

            # Create transaction
            amount = txn_data["deposit"] if txn_data["deposit"] > 0 else txn_data["withdrawal"]
            txn = BankTransaction(
                date=txn_data["date"],
                bank_account=account,
                deposit=txn_data["deposit"],
                withdrawal=txn_data["withdrawal"],
                currency="NGN",
                description=txn_data.get("description", ""),
                reference_number=txn_data.get("reference_number", ""),
                transaction_id=txn_data.get("fitid", ""),
                transaction_type="deposit" if txn_data["deposit"] > 0 else "withdrawal",
                status=BankTransactionStatus.UNRECONCILED,
                unallocated_amount=amount,
                allocated_amount=Decimal("0"),
                is_manual_entry=False,
                created_by_id=user.id,
            )

            db.add(txn)
            db.flush()

            imported_count += 1
            transaction_ids.append(txn.id)

        except Exception as e:
            errors.append({
                "row": txn_data.get("row_num", 0),
                "error": str(e),
            })

    db.commit()

    return {
        "imported_count": imported_count,
        "skipped_count": skipped_count,
        "errors": errors,
        "transaction_ids": transaction_ids,
    }


# =============================================================================
# RECONCILIATION SUGGESTIONS
# =============================================================================

@router.get("/bank-transactions/{transaction_id}/suggestions", dependencies=[Depends(Require("accounting:read"))])
def get_reconciliation_suggestions(
    transaction_id: int,
    party_type: Optional[str] = Query(None, description="Filter by party type: Customer or Supplier"),
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get reconciliation suggestions for a bank transaction.

    Finds open invoices/bills that might match this transaction based on:
    - Amount (exact match scores highest)
    - Party name matching
    - Reference number matching
    - Date proximity

    Args:
        transaction_id: Bank transaction ID
        party_type: Filter suggestions by Customer or Supplier
        limit: Max suggestions to return

    Returns:
        List of suggested documents with match scores
    """
    txn = db.query(BankTransaction).filter(BankTransaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Bank transaction not found")

    # Get transaction amount
    txn_amount = float(txn.deposit if txn.deposit > 0 else txn.withdrawal)
    is_deposit = txn.deposit > 0

    suggestions = []

    # For deposits, look for customer invoices; for withdrawals, look for supplier bills
    if is_deposit and (not party_type or party_type == "Customer"):
        # Query open invoices
        invoices = db.query(Invoice).filter(
            Invoice.balance > 0,
            Invoice.docstatus == 1,  # Submitted
        ).limit(limit * 2).all()

        for inv in invoices:
            score = 0
            reasons = []

            # Amount matching
            inv_balance = float(inv.balance) if inv.balance else 0
            amount_diff = abs(inv_balance - txn_amount)
            if amount_diff == 0:
                score += 50
                reasons.append("Exact amount match")
            elif amount_diff < txn_amount * 0.05:  # Within 5%
                score += 30
                reasons.append("Amount close match")
            elif amount_diff < txn_amount * 0.20:  # Within 20%
                score += 10

            # Reference matching
            if txn.reference_number and inv.invoice_number:
                if txn.reference_number.lower() in inv.invoice_number.lower():
                    score += 25
                    reasons.append("Reference match")
                elif inv.invoice_number.lower() in (txn.description or "").lower():
                    score += 15
                    reasons.append("Reference in description")

            # Party matching
            if txn.bank_party_name and hasattr(inv, 'customer') and inv.customer:
                if txn.bank_party_name.lower() in inv.customer.name.lower():
                    score += 20
                    reasons.append("Party name match")

            # Date proximity
            if txn.date and inv.due_date:
                days_diff = abs((txn.date.date() if hasattr(txn.date, 'date') else txn.date) -
                               (inv.due_date.date() if hasattr(inv.due_date, 'date') else inv.due_date)).days
                if days_diff <= 7:
                    score += 5
                    reasons.append("Near due date")

            if score > 0:
                suggestions.append({
                    "document_type": "Sales Invoice",
                    "document_id": inv.id,
                    "document_name": inv.invoice_number or f"INV-{inv.id}",
                    "party": str(inv.customer_id) if inv.customer_id else "",
                    "party_name": "",  # Would need join to get customer name
                    "outstanding_amount": inv_balance,
                    "due_date": inv.due_date.isoformat() if inv.due_date else None,
                    "posting_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                    "match_score": min(score, 100),
                    "match_reasons": reasons,
                })

    if not is_deposit and (not party_type or party_type == "Supplier"):
        # Query open purchase invoices/bills
        bills = db.query(PurchaseInvoice).filter(
            PurchaseInvoice.outstanding_amount > 0,
            PurchaseInvoice.docstatus == 1,  # Submitted
        ).limit(limit * 2).all()

        for bill in bills:
            score = 0
            reasons = []

            # Amount matching
            bill_outstanding = float(bill.outstanding_amount) if bill.outstanding_amount else 0
            amount_diff = abs(bill_outstanding - txn_amount)
            if amount_diff == 0:
                score += 50
                reasons.append("Exact amount match")
            elif amount_diff < txn_amount * 0.05:
                score += 30
                reasons.append("Amount close match")
            elif amount_diff < txn_amount * 0.20:
                score += 10

            # Reference matching
            if txn.reference_number and bill.bill_no:
                if txn.reference_number.lower() in bill.bill_no.lower():
                    score += 25
                    reasons.append("Reference match")

            # Supplier matching
            if txn.bank_party_name and bill.supplier_name:
                if txn.bank_party_name.lower() in bill.supplier_name.lower():
                    score += 20
                    reasons.append("Supplier name match")

            # Date proximity
            if txn.date and bill.due_date:
                days_diff = abs((txn.date.date() if hasattr(txn.date, 'date') else txn.date) -
                               (bill.due_date.date() if hasattr(bill.due_date, 'date') else bill.due_date)).days
                if days_diff <= 7:
                    score += 5
                    reasons.append("Near due date")

            if score > 0:
                suggestions.append({
                    "document_type": "Purchase Invoice",
                    "document_id": bill.id,
                    "document_name": bill.bill_no or f"BILL-{bill.id}",
                    "party": bill.supplier or "",
                    "party_name": bill.supplier_name or "",
                    "outstanding_amount": bill_outstanding,
                    "due_date": bill.due_date.isoformat() if bill.due_date else None,
                    "posting_date": bill.posting_date.isoformat() if bill.posting_date else None,
                    "match_score": min(score, 100),
                    "match_reasons": reasons,
                })

    # Sort by score descending
    suggestions.sort(key=lambda x: x["match_score"], reverse=True)

    return {
        "transaction_amount": txn_amount,
        "unallocated_amount": float(txn.unallocated_amount) if txn.unallocated_amount else txn_amount,
        "suggestions": suggestions[:limit],
    }


# =============================================================================
# ENHANCED RECONCILIATION WITH ALLOCATIONS
# =============================================================================

@router.post("/bank-transactions/{transaction_id}/allocate", dependencies=[Depends(Require("books:write"))])
def allocate_bank_transaction(
    transaction_id: int,
    data: ReconcileRequest,
    db: Session = Depends(get_db),
    user=Depends(Require("books:write")),
) -> Dict[str, Any]:
    """Allocate a bank transaction to one or more documents.

    This matches the bank transaction to invoices/bills and updates
    allocation amounts.

    Args:
        transaction_id: Bank transaction ID
        data: Allocation request with document references

    Returns:
        Allocation results
    """
    txn = db.query(BankTransaction).filter(BankTransaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Bank transaction not found")

    if txn.status == BankTransactionStatus.RECONCILED:
        raise HTTPException(status_code=400, detail="Transaction is already fully reconciled")

    unallocated = float(txn.unallocated_amount) if txn.unallocated_amount else 0
    total_allocation = sum(a.allocated_amount for a in data.allocations)

    if total_allocation > unallocated:
        raise HTTPException(
            status_code=400,
            detail=f"Total allocation ({total_allocation}) exceeds unallocated amount ({unallocated})"
        )

    allocated_results = []

    for alloc in data.allocations:
        if alloc.document_type == "Sales Invoice":
            doc = db.query(Invoice).filter(Invoice.id == alloc.document_id).first()
            if not doc:
                raise HTTPException(status_code=404, detail=f"Invoice {alloc.document_id} not found")

            # Update invoice paid amount
            doc.amount_paid = (doc.amount_paid or Decimal("0")) + Decimal(str(alloc.allocated_amount))
            doc.balance = doc.total_amount - doc.amount_paid

            allocated_results.append({
                "document_type": alloc.document_type,
                "document_id": str(alloc.document_id),
                "allocated_amount": alloc.allocated_amount,
            })

        elif alloc.document_type == "Purchase Invoice":
            doc = db.query(PurchaseInvoice).filter(PurchaseInvoice.id == alloc.document_id).first()
            if not doc:
                raise HTTPException(status_code=404, detail=f"Bill {alloc.document_id} not found")

            # Update bill paid amount
            doc.paid_amount = (doc.paid_amount or Decimal("0")) + Decimal(str(alloc.allocated_amount))
            doc.outstanding_amount = doc.grand_total - doc.paid_amount

            allocated_results.append({
                "document_type": alloc.document_type,
                "document_id": str(alloc.document_id),
                "allocated_amount": alloc.allocated_amount,
            })
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported document type: {alloc.document_type}")

    # Update transaction allocation
    txn.allocated_amount = (txn.allocated_amount or Decimal("0")) + Decimal(str(total_allocation))
    txn.unallocated_amount = (txn.unallocated_amount or Decimal("0")) - Decimal(str(total_allocation))

    # Mark as reconciled if fully allocated
    if txn.unallocated_amount <= 0:
        txn.status = BankTransactionStatus.RECONCILED

    db.commit()

    return {
        "success": True,
        "allocated_amount": total_allocation,
        "remaining_unallocated": float(txn.unallocated_amount),
        "allocations": allocated_results,
    }
