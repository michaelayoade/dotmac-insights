"""Banking: Bank accounts, bank transactions, CRUD, splits, import, reconciliation."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, field_validator, ValidationInfo
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.auth import Require, Principal, get_current_principal
from app.database import get_db
from app.config import settings
from app.models.accounting import (
    BankAccount,
    BankTransaction,
    BankTransactionStatus,
    PurchaseInvoice,
)
from app.models.invoice import Invoice
from app.services.accounting.banking import BankingService
from app.services.accounting.banking_types import (
    BankAccountCreateData,
    BankAccountUpdateData,
    BankTransactionCreateData,
    BankTransactionFilters,
    BankTransactionSplitData,
    BankTransactionUpdateData,
    ImportColumnMapping,
)
from app.services.errors import NotFoundError, ValidationError as ServiceValidationError
from app.services.types import PaginationParams

from .helpers import parse_date

router = APIRouter()


def get_banking_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> BankingService:
    """Dependency to get BankingService instance."""
    return BankingService(db, principal)


# PYDANTIC SCHEMAS

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

    @field_validator("deposit", "withdrawal")
    def _validate_amounts(cls, value: float, info: ValidationInfo) -> float:
        other_key = "withdrawal" if info.field_name == "deposit" else "deposit"
        other_value = info.data.get(other_key)
        if other_value is None:
            return value
        if value < 0 or other_value < 0:
            raise ValueError("Deposit and withdrawal must be non-negative.")
        if value > 0 and other_value > 0:
            raise ValueError("Provide either a deposit or a withdrawal, not both.")
        if value == 0 and other_value == 0:
            raise ValueError("Provide a positive deposit or withdrawal amount.")
        return value


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

    @field_validator("deposit", "withdrawal")
    def _validate_amounts(cls, value: Optional[float], info: ValidationInfo) -> Optional[float]:
        other_key = "withdrawal" if info.field_name == "deposit" else "deposit"
        other_value = info.data.get(other_key)
        if value is None or other_value is None:
            return value
        if value < 0 or other_value < 0:
            raise ValueError("Deposit and withdrawal must be non-negative.")
        if value > 0 and other_value > 0:
            raise ValueError("Provide either a deposit or a withdrawal, not both.")
        if value == 0 and other_value == 0:
            raise ValueError("Provide a positive deposit or withdrawal amount.")
        return value


class BankAccountCreate(BaseModel):
    """Schema for creating a bank account."""
    account_name: str
    bank: Optional[str] = None
    bank_account_no: Optional[str] = None
    account: Optional[str] = None
    company: Optional[str] = None
    currency: str = "NGN"
    is_company_account: bool = True
    is_default: bool = False
    disabled: bool = False


class BankAccountUpdate(BaseModel):
    """Schema for updating a bank account."""
    account_name: Optional[str] = None
    bank: Optional[str] = None
    bank_account_no: Optional[str] = None
    account: Optional[str] = None
    company: Optional[str] = None
    currency: Optional[str] = None
    is_company_account: Optional[bool] = None
    is_default: Optional[bool] = None
    disabled: Optional[bool] = None


class ReconciliationAllocation(BaseModel):
    """Schema for a single reconciliation allocation."""
    document_type: str  # "Sales Invoice" or "Purchase Invoice"
    document_id: int
    allocated_amount: float


class ReconcileRequest(BaseModel):
    """Schema for reconciling a bank transaction with documents."""
    allocations: List[ReconciliationAllocation]
    create_payment_entry: bool = False


# BANK ACCOUNTS

@router.get("/bank-accounts", dependencies=[Depends(Require("accounting:read"))])
def get_bank_accounts(
    as_of_date: Optional[str] = None,
    service: BankingService = Depends(get_banking_service),
) -> Dict[str, Any]:
    """Get bank accounts list with current balances.

    Args:
        as_of_date: Calculate balances as of this date (default: today)

    Returns:
        List of bank accounts with GL-derived balances
    """
    cutoff = parse_date(as_of_date, "as_of_date")
    result = service.list_bank_accounts(as_of_date=cutoff)
    return {
        "total": result["total"],
        "total_balance": result["total_balance"],
        "as_of_date": result["as_of_date"],
        "accounts": [
            {
                "id": acc.id,
                "erpnext_id": acc.erpnext_id,
                "name": acc.name,
                "bank": acc.bank,
                "account_no": acc.account_no,
                "gl_account": acc.gl_account,
                "company": acc.company,
                "currency": acc.currency,
                "is_default": acc.is_default,
                "balance": acc.balance,
            }
            for acc in result["accounts"]
        ],
    }


# BANK ACCOUNT CRUD

@router.post("/bank-accounts", dependencies=[Depends(Require("accounting:write"))])
def create_bank_account(
    payload: BankAccountCreate,
    db: Session = Depends(get_db),
    service: BankingService = Depends(get_banking_service),
) -> Dict[str, Any]:
    """Create a bank account locally."""
    create_data = BankAccountCreateData(
        account_name=payload.account_name,
        bank=payload.bank,
        bank_account_no=payload.bank_account_no,
        account=payload.account,
        company=payload.company,
        currency=payload.currency,
        is_company_account=payload.is_company_account,
        is_default=payload.is_default,
        disabled=payload.disabled,
    )
    account = service.create_bank_account(create_data)
    db.commit()
    return {"id": account.id}


@router.patch("/bank-accounts/{bank_account_id}", dependencies=[Depends(Require("accounting:write"))])
def update_bank_account(
    bank_account_id: int,
    payload: BankAccountUpdate,
    db: Session = Depends(get_db),
    service: BankingService = Depends(get_banking_service),
) -> Dict[str, Any]:
    """Update a bank account locally."""
    update_data = BankAccountUpdateData(
        account_name=payload.account_name,
        bank=payload.bank,
        bank_account_no=payload.bank_account_no,
        account=payload.account,
        company=payload.company,
        currency=payload.currency,
        is_company_account=payload.is_company_account,
        is_default=payload.is_default,
        disabled=payload.disabled,
    )
    try:
        account = service.update_bank_account(bank_account_id, update_data)
        db.commit()
        return {"id": account.id}
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


@router.delete("/bank-accounts/{bank_account_id}", dependencies=[Depends(Require("accounting:write"))])
def delete_bank_account(
    bank_account_id: int,
    db: Session = Depends(get_db),
    service: BankingService = Depends(get_banking_service),
) -> Dict[str, Any]:
    """Disable a bank account."""
    try:
        service.disable_bank_account(bank_account_id)
        db.commit()
        return {"status": "disabled", "bank_account_id": bank_account_id}
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


# BANK RECONCILIATION


@router.get("/bank-accounts/{bank_account_id}/reconciliation-status", dependencies=[Depends(Require("accounting:read"))])
async def get_bank_reconciliation_status(
    bank_account_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get current reconciliation status for a bank account."""
    from app.services.bank_reconciliation import BankReconciliationService, ReconciliationError

    service = BankReconciliationService(db)

    try:
        return service.get_reconciliation_status(bank_account_id)
    except ReconciliationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/bank-accounts/{bank_account_id}/reconciliation/start", dependencies=[Depends(Require("books:write"))])
async def start_bank_reconciliation(
    bank_account_id: int,
    from_date: str = Query(..., description="Statement start date (YYYY-MM-DD)"),
    to_date: str = Query(..., description="Statement end date (YYYY-MM-DD)"),
    statement_opening_balance: str = Query(..., description="Opening balance from bank statement"),
    statement_closing_balance: str = Query(..., description="Closing balance from bank statement"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Start a new bank reconciliation."""
    from app.services.bank_reconciliation import BankReconciliationService, ReconciliationError

    service = BankReconciliationService(db)

    try:
        parsed_from_date = parse_date(from_date, "from_date")
        parsed_to_date = parse_date(to_date, "to_date")
        if not parsed_from_date or not parsed_to_date:
            raise HTTPException(status_code=400, detail="Invalid date range")
        reconciliation = service.start_reconciliation(
            bank_account_id=bank_account_id,
            from_date=parsed_from_date,
            to_date=parsed_to_date,
            statement_opening_balance=Decimal(statement_opening_balance),
            statement_closing_balance=Decimal(statement_closing_balance),
            user_id=principal.id,
        )
        db.commit()

        return {
            "message": "Reconciliation started",
            "reconciliation_id": reconciliation.id,
            "bank_account": reconciliation.bank_account,
            "from_date": reconciliation.from_date.isoformat() if reconciliation.from_date else None,
            "to_date": reconciliation.to_date.isoformat() if reconciliation.to_date else None,
            "statement_opening": float(reconciliation.bank_statement_opening_balance),
            "statement_closing": float(reconciliation.bank_statement_closing_balance),
            "gl_opening": float(reconciliation.account_opening_balance),
        }
    except (ReconciliationError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/bank-reconciliations/{reconciliation_id}/outstanding", dependencies=[Depends(Require("accounting:read"))])
async def get_reconciliation_outstanding(
    reconciliation_id: int,
    bank_limit: int | None = Query(default=None, ge=1, le=500),
    bank_offset: int = Query(default=0, ge=0),
    gl_limit: int | None = Query(default=None, ge=1, le=500),
    gl_offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get outstanding (unmatched) items for a reconciliation."""
    from app.services.bank_reconciliation import BankReconciliationService, ReconciliationError

    service = BankReconciliationService(db)

    try:
        return service.get_outstanding_items(
            reconciliation_id,
            bank_limit=bank_limit,
            bank_offset=bank_offset,
            gl_limit=gl_limit,
            gl_offset=gl_offset,
        )
    except ReconciliationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/bank-reconciliations/{reconciliation_id}/match", dependencies=[Depends(Require("books:write"))])
async def match_bank_transaction(
    reconciliation_id: int,
    bank_transaction_id: int = Query(..., description="Bank transaction ID to match"),
    gl_entry_ids: str = Query(..., description="Comma-separated GL entry IDs to match"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Match a bank transaction to GL entries."""
    from app.services.bank_reconciliation import BankReconciliationService, ReconciliationError

    service = BankReconciliationService(db)

    try:
        entry_ids = [int(x.strip()) for x in gl_entry_ids.split(",")]
        result = service.match_transaction(
            bank_transaction_id=bank_transaction_id,
            gl_entry_ids=entry_ids,
            user_id=principal.id,
            reconciliation_id=reconciliation_id,
        )
        db.commit()
        return result
    except (ReconciliationError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/bank-reconciliations/{reconciliation_id}/auto-match", dependencies=[Depends(Require("books:write"))])
async def auto_match_transactions(
    reconciliation_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Automatically match bank transactions to GL entries based on amount."""
    from app.services.bank_reconciliation import BankReconciliationService, ReconciliationError

    service = BankReconciliationService(db)

    try:
        result = service.auto_match(reconciliation_id, principal.id)
        db.commit()
        return result
    except ReconciliationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/bank-reconciliations/{reconciliation_id}/complete", dependencies=[Depends(Require("books:write"))])
async def complete_bank_reconciliation(
    reconciliation_id: int,
    adjustment_account: Optional[str] = Query(None, description="Account for difference adjustment"),
    adjustment_remarks: Optional[str] = Query(None, description="Remarks for adjustment"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Complete the bank reconciliation."""
    from app.services.bank_reconciliation import BankReconciliationService, ReconciliationError

    service = BankReconciliationService(db)

    try:
        result = service.complete_reconciliation(
            reconciliation_id=reconciliation_id,
            user_id=principal.id,
            adjustment_account=adjustment_account,
            adjustment_remarks=adjustment_remarks,
        )
        db.commit()
        return result
    except ReconciliationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# BANK TRANSACTIONS

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
    offset: int = Query(default=0, ge=0),
    service: BankingService = Depends(get_banking_service),
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
    filters = BankTransactionFilters(
        bank_account=bank_account,
        status=status,
        transaction_type=transaction_type,
        start_date=parse_date(start_date, "start_date"),
        end_date=parse_date(end_date, "end_date"),
        min_amount=min_amount,
        max_amount=max_amount,
        unallocated_only=unallocated_only,
        search=search,
        sort_by=sort_by or "date",
        sort_dir=sort_dir or "desc",
    )
    pagination = PaginationParams(limit=limit, offset=offset)

    try:
        result = service.list_transactions(filters, pagination)
    except ServiceValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message) from exc

    return {
        "total": result.total,
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
            for t in result.items
        ],
    }


@router.get("/bank-transactions/{transaction_id}", dependencies=[Depends(Require("accounting:read"))])
def get_bank_transaction_detail(
    transaction_id: int,
    service: BankingService = Depends(get_banking_service),
) -> Dict[str, Any]:
    """Get bank transaction detail.

    Args:
        transaction_id: Bank transaction ID

    Returns:
        Full bank transaction details
    """
    try:
        txn = service.get_transaction(transaction_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc

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


# BANK TRANSACTIONS CRUD

@router.post("/bank-transactions", dependencies=[Depends(Require("books:write"))])
def create_bank_transaction(
    data: BankTransactionCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
    service: BankingService = Depends(get_banking_service),
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

    # Convert splits
    splits = [
        BankTransactionSplitData(
            amount=Decimal(str(s.amount)),
            account=s.account,
            cost_center=s.cost_center,
            tax_code_id=s.tax_code_id,
            tax_rate=Decimal(str(s.tax_rate)),
            tax_amount=Decimal(str(s.tax_amount)),
            memo=s.memo,
            party_type=s.party_type,
            party=s.party,
        )
        for s in data.splits
    ]

    create_data = BankTransactionCreateData(
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
        splits=splits,
    )

    try:
        txn = service.create_transaction(
            create_data,
            user_id=principal.id,
            auto_create_bank_account=settings.e2e_auth_enabled,
        )
        db.commit()
    except ServiceValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message) from exc

    amount = txn.deposit if txn.deposit > 0 else txn.withdrawal
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
    service: BankingService = Depends(get_banking_service),
) -> Dict[str, Any]:
    """Update a bank transaction.

    Only unreconciled transactions can be updated.

    Args:
        transaction_id: Bank transaction ID
        data: Update data

    Returns:
        Updated transaction info
    """
    # Parse date if provided
    txn_date = None
    if data.date is not None:
        try:
            txn_date = datetime.fromisoformat(data.date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")

    update_data = BankTransactionUpdateData(
        date=txn_date,
        bank_account=data.bank_account,
        deposit=Decimal(str(data.deposit)) if data.deposit is not None else None,
        withdrawal=Decimal(str(data.withdrawal)) if data.withdrawal is not None else None,
        description=data.description,
        reference_number=data.reference_number,
        transaction_type=data.transaction_type,
        payee_name=data.payee_name,
        payee_account=data.payee_account,
        party_type=data.party_type,
        party=data.party,
    )

    try:
        txn = service.update_transaction(transaction_id, update_data)
        db.commit()
        return {"message": "Bank transaction updated", "id": txn.id}
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except ServiceValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message) from exc


@router.delete("/bank-transactions/{transaction_id}", dependencies=[Depends(Require("books:write"))])
def delete_bank_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    service: BankingService = Depends(get_banking_service),
) -> Dict[str, Any]:
    """Delete a bank transaction.

    Only unreconciled manual entries can be deleted.

    Args:
        transaction_id: Bank transaction ID

    Returns:
        Deletion confirmation
    """
    try:
        service.delete_transaction(transaction_id)
        db.commit()
        return {"message": "Bank transaction deleted"}
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except ServiceValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message) from exc


# BANK TRANSACTION SPLITS

@router.post("/bank-transactions/{transaction_id}/splits", dependencies=[Depends(Require("books:write"))])
def add_transaction_splits(
    transaction_id: int,
    splits: List[BankTransactionSplitCreate],
    db: Session = Depends(get_db),
    service: BankingService = Depends(get_banking_service),
) -> Dict[str, Any]:
    """Add splits to a bank transaction.

    Args:
        transaction_id: Bank transaction ID
        splits: List of splits to add

    Returns:
        Created splits info
    """
    split_data_list = [
        BankTransactionSplitData(
            amount=Decimal(str(s.amount)),
            account=s.account,
            cost_center=s.cost_center,
            tax_code_id=s.tax_code_id,
            tax_rate=Decimal(str(s.tax_rate)),
            tax_amount=Decimal(str(s.tax_amount)),
            memo=s.memo,
            party_type=s.party_type,
            party=s.party,
        )
        for s in splits
    ]

    try:
        created_ids = service.add_splits(transaction_id, split_data_list)
        db.commit()
        return {
            "message": f"Added {len(created_ids)} splits",
            "split_ids": created_ids,
        }
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except ServiceValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message) from exc


@router.delete("/bank-transactions/{transaction_id}/splits/{split_id}", dependencies=[Depends(Require("books:write"))])
def delete_transaction_split(
    transaction_id: int,
    split_id: int,
    db: Session = Depends(get_db),
    service: BankingService = Depends(get_banking_service),
) -> Dict[str, Any]:
    """Delete a split from a bank transaction.

    Args:
        transaction_id: Bank transaction ID
        split_id: Split ID

    Returns:
        Deletion confirmation
    """
    try:
        service.delete_split(transaction_id, split_id)
        db.commit()
        return {"message": "Split deleted"}
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except ServiceValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message) from exc


# RECONCILIATION

@router.post("/bank-transactions/{transaction_id}/reconcile", dependencies=[Depends(Require("books:write"))])
def reconcile_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    service: BankingService = Depends(get_banking_service),
) -> Dict[str, Any]:
    """Mark a bank transaction as reconciled.

    Args:
        transaction_id: Bank transaction ID

    Returns:
        Reconciliation status
    """
    try:
        txn = service.reconcile_transaction(transaction_id)
        db.commit()
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except ServiceValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message) from exc

    return {
        "message": "Transaction reconciled",
        "id": txn.id,
        "status": txn.status.value,
    }


@router.post("/bank-transactions/{transaction_id}/unreconcile", dependencies=[Depends(Require("books:write"))])
def unreconcile_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    service: BankingService = Depends(get_banking_service),
) -> Dict[str, Any]:
    """Unreconcile a bank transaction.

    Args:
        transaction_id: Bank transaction ID

    Returns:
        Updated status
    """
    try:
        txn = service.unreconcile_transaction(transaction_id)
        db.commit()
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except ServiceValidationError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message) from exc

    return {
        "message": "Transaction unreconciled",
        "id": txn.id,
        "status": txn.status.value,
    }


# BANK TRANSACTION IMPORT

@router.post("/bank-transactions/import", dependencies=[Depends(Require("books:write"))])
async def import_bank_transactions(
    file: UploadFile = File(...),
    account: str = Form(...),
    format: str = Form(...),  # "csv" or "ofx"
    column_mapping: Optional[str] = Form(None),  # JSON string for CSV
    skip_duplicates: bool = Form(True),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
    service: BankingService = Depends(get_banking_service),
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
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to read file. Please ensure it is a valid CSV or OFX file.")

    # Parse transactions based on format using service
    if format == "csv":
        if not column_mapping:
            raise HTTPException(status_code=400, detail="column_mapping is required for CSV import")
        try:
            mapping_dict = json.loads(column_mapping)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid column_mapping JSON")

        if not mapping_dict.get("date_column"):
            raise HTTPException(status_code=400, detail="date_column is required in column_mapping")

        mapping = ImportColumnMapping(
            date_column=mapping_dict.get("date_column", ""),
            amount_column=mapping_dict.get("amount_column"),
            deposit_column=mapping_dict.get("deposit_column"),
            withdrawal_column=mapping_dict.get("withdrawal_column"),
            description_column=mapping_dict.get("description_column"),
            reference_column=mapping_dict.get("reference_column"),
        )
        parsed = service.parse_csv(content, mapping)
    else:
        parsed = service.parse_ofx(content)

    if not parsed:
        return {
            "imported_count": 0,
            "skipped_count": 0,
            "errors": [{"row": 0, "error": "No valid transactions found in file"}],
            "transaction_ids": [],
        }

    # Import transactions using service
    result = service.import_transactions(
        bank_account=account,
        transactions=parsed,
        skip_duplicates=skip_duplicates,
        user_id=principal.id,
    )
    db.commit()

    return {
        "imported_count": result.imported_count,
        "skipped_count": result.skipped_count,
        "errors": result.errors,
        "transaction_ids": result.transaction_ids,
    }


# RECONCILIATION SUGGESTIONS

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
            if txn.reference_number and bill.bill_number:
                if txn.reference_number.lower() in bill.bill_number.lower():
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
                    "document_name": bill.bill_number or f"BILL-{bill.id}",
                    "party": bill.supplier or "",
                    "party_name": bill.supplier_name or "",
                    "outstanding_amount": bill_outstanding,
                    "due_date": bill.due_date.isoformat() if bill.due_date else None,
                    "posting_date": bill.posting_date.isoformat() if bill.posting_date else None,
                    "match_score": min(score, 100),
                    "match_reasons": reasons,
                })

    def _match_score(item: Dict[str, Any]) -> float:
        score = item.get("match_score")
        return float(score) if score is not None else 0.0

    # Sort by score descending
    suggestions.sort(key=_match_score, reverse=True)

    return {
        "transaction_amount": txn_amount,
        "unallocated_amount": float(txn.unallocated_amount) if txn.unallocated_amount else txn_amount,
        "suggestions": suggestions[:limit],
    }


# ENHANCED RECONCILIATION WITH ALLOCATIONS

@router.post("/bank-transactions/{transaction_id}/allocate", dependencies=[Depends(Require("books:write"))])
def allocate_bank_transaction(
    transaction_id: int,
    data: ReconcileRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
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
    # Use SELECT FOR UPDATE to prevent race conditions on concurrent allocations
    txn = db.query(BankTransaction).filter(BankTransaction.id == transaction_id).with_for_update().first()
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
            # Lock invoice row to prevent concurrent allocation updates
            invoice = db.query(Invoice).filter(Invoice.id == alloc.document_id).with_for_update().first()
            if not invoice:
                raise HTTPException(status_code=404, detail=f"Invoice {alloc.document_id} not found")

            # Update invoice paid amount
            invoice.amount_paid = (invoice.amount_paid or Decimal("0")) + Decimal(str(alloc.allocated_amount))
            invoice.balance = invoice.total_amount - invoice.amount_paid

            allocated_results.append({
                "document_type": alloc.document_type,
                "document_id": str(alloc.document_id),
                "allocated_amount": alloc.allocated_amount,
            })

        elif alloc.document_type == "Purchase Invoice":
            # Lock bill row to prevent concurrent allocation updates
            bill = db.query(PurchaseInvoice).filter(PurchaseInvoice.id == alloc.document_id).with_for_update().first()
            if not bill:
                raise HTTPException(status_code=404, detail=f"Bill {alloc.document_id} not found")

            # Update bill paid amount
            bill.paid_amount = (bill.paid_amount or Decimal("0")) + Decimal(str(alloc.allocated_amount))
            bill.outstanding_amount = bill.grand_total - bill.paid_amount

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
