"""Corporate card statement endpoints."""
from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from app.api.expenses.schemas import (
    CorporateCardStatementCreate,
    CorporateCardStatementRead,
    StatementImportPayload,
)
from app.database import get_db
from app.models.expense_management import (
    CorporateCard,
    CorporateCardStatement,
    CorporateCardTransaction,
    CardTransactionStatus,
    StatementStatus,
)
from app.auth import get_current_principal, Principal, Require
from app.api.expenses.access import apply_employee_scope

router = APIRouter()


def compute_import_hash(card_id: int, transaction_date: datetime, amount: Decimal, reference: Optional[str]) -> str:
    """Compute a hash for deduplication during import."""
    data = f"{card_id}:{transaction_date.isoformat()}:{amount}:{reference or ''}"
    return hashlib.sha256(data.encode()).hexdigest()


@router.get("/", response_model=List[CorporateCardStatementRead], dependencies=[Depends(Require("expenses:read"))])
async def list_statements(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    card_id: Optional[int] = Query(default=None, description="Filter by card"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """List corporate card statements with optional filters."""
    query = db.query(CorporateCardStatement).join(CorporateCard).order_by(
        CorporateCardStatement.period_start.desc()
    )
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=CorporateCard.employee_id,
        created_by_field=CorporateCardStatement.created_by_id,
    )

    if card_id:
        query = query.filter(CorporateCardStatement.card_id == card_id)

    if status:
        try:
            query = query.filter(CorporateCardStatement.status == StatementStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status filter")

    statements = query.offset(offset).limit(limit).all()
    return statements


@router.get("/{statement_id}", response_model=CorporateCardStatementRead, dependencies=[Depends(Require("expenses:read"))])
async def get_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Get a single statement by ID."""
    query = (
        db.query(CorporateCardStatement)
        .join(CorporateCard)
        .filter(CorporateCardStatement.id == statement_id)
    )
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=CorporateCard.employee_id,
        created_by_field=CorporateCardStatement.created_by_id,
    )
    statement = query.first()
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")
    return statement


@router.post("/", response_model=CorporateCardStatementRead, status_code=201, dependencies=[Depends(Require("expenses:write"))])
async def create_statement(
    payload: CorporateCardStatementCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Create a new statement period (without transactions)."""
    # Validate card exists
    card_query = db.query(CorporateCard).filter(CorporateCard.id == payload.card_id)
    card_query = apply_employee_scope(
        card_query,
        principal,
        db,
        employee_field=CorporateCard.employee_id,
        created_by_field=CorporateCard.created_by_id,
    )
    card = card_query.first()
    if not card:
        raise HTTPException(status_code=400, detail="Corporate card not found")

    # Check for overlapping period
    existing = (
        db.query(CorporateCardStatement)
        .filter(
            CorporateCardStatement.card_id == payload.card_id,
            CorporateCardStatement.period_start <= payload.period_end,
            CorporateCardStatement.period_end >= payload.period_start,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Statement period overlaps with existing statement",
        )

    statement = CorporateCardStatement(
        card_id=payload.card_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        statement_date=payload.statement_date,
        import_date=datetime.utcnow(),
        import_source=payload.import_source,
        original_filename=payload.original_filename,
        status=StatementStatus.OPEN,
        created_by_id=principal.id,
    )

    db.add(statement)
    db.commit()
    db.refresh(statement)
    return statement


@router.post("/import", response_model=CorporateCardStatementRead, status_code=201, dependencies=[Depends(Require("expenses:write"))])
async def import_statement(
    payload: StatementImportPayload,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Import a statement with transactions."""
    # Validate card exists
    card_query = db.query(CorporateCard).filter(CorporateCard.id == payload.card_id)
    card_query = apply_employee_scope(
        card_query,
        principal,
        db,
        employee_field=CorporateCard.employee_id,
        created_by_field=CorporateCard.created_by_id,
    )
    card = card_query.first()
    if not card:
        raise HTTPException(status_code=400, detail="Corporate card not found")

    # Check for overlapping period
    existing = (
        db.query(CorporateCardStatement)
        .filter(
            CorporateCardStatement.card_id == payload.card_id,
            CorporateCardStatement.period_start <= payload.period_end,
            CorporateCardStatement.period_end >= payload.period_start,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Statement period overlaps with existing statement",
        )

    # Create statement
    statement = CorporateCardStatement(
        card_id=payload.card_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        statement_date=payload.statement_date,
        import_date=datetime.utcnow(),
        import_source=payload.import_source,
        original_filename=payload.original_filename,
        status=StatementStatus.OPEN,
        created_by_id=principal.id,
    )
    db.add(statement)
    db.flush()  # Get statement ID

    # Import transactions
    total_amount = Decimal("0")
    imported_count = 0
    skipped_count = 0

    for txn_data in payload.transactions:
        # Ensure card_id matches statement
        if txn_data.card_id != payload.card_id:
            txn_data.card_id = payload.card_id

        # Compute import hash
        transaction_datetime = datetime.combine(txn_data.transaction_date, datetime.min.time())
        import_hash = compute_import_hash(
            txn_data.card_id,
            transaction_datetime,
            txn_data.amount,
            txn_data.transaction_reference,
        )

        # Check for duplicate
        existing_txn = (
            db.query(CorporateCardTransaction)
            .filter(CorporateCardTransaction.import_hash == import_hash)
            .first()
        )
        if existing_txn:
            skipped_count += 1
            continue

        transaction = CorporateCardTransaction(
            card_id=txn_data.card_id,
            statement_id=statement.id,
            transaction_date=transaction_datetime,
            posting_date=datetime.combine(txn_data.posting_date, datetime.min.time()) if txn_data.posting_date else None,
            merchant_name=txn_data.merchant_name,
            merchant_category_code=txn_data.merchant_category_code,
            description=txn_data.description,
            amount=txn_data.amount,
            currency=txn_data.currency,
            original_amount=txn_data.original_amount,
            original_currency=txn_data.original_currency,
            conversion_rate=txn_data.conversion_rate,
            transaction_reference=txn_data.transaction_reference,
            authorization_code=txn_data.authorization_code,
            status=CardTransactionStatus.IMPORTED,
            import_hash=import_hash,
            imported_at=datetime.utcnow(),
        )
        db.add(transaction)
        total_amount += txn_data.amount
        imported_count += 1

    # Update statement totals
    statement.total_amount = total_amount
    statement.transaction_count = imported_count
    statement.unmatched_count = imported_count

    db.commit()
    db.refresh(statement)
    return statement


@router.post("/{statement_id}/reconcile", response_model=CorporateCardStatementRead, dependencies=[Depends(Require("expenses:write"))])
async def reconcile_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Mark a statement as reconciled after reviewing all transactions."""
    query = (
        db.query(CorporateCardStatement)
        .join(CorporateCard)
        .filter(CorporateCardStatement.id == statement_id)
        .with_for_update()
    )
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=CorporateCard.employee_id,
        created_by_field=CorporateCardStatement.created_by_id,
    )
    statement = query.first()
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")

    if statement.status == StatementStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Statement is already closed")

    # Calculate reconciliation stats
    transactions = (
        db.query(CorporateCardTransaction)
        .filter(CorporateCardTransaction.statement_id == statement_id)
        .all()
    )

    matched_count = 0
    matched_amount = Decimal("0")
    unmatched_count = 0

    for txn in transactions:
        if txn.status == CardTransactionStatus.MATCHED:
            matched_count += 1
            matched_amount += txn.amount
        elif txn.status in [CardTransactionStatus.IMPORTED, CardTransactionStatus.UNMATCHED]:
            unmatched_count += 1

    statement.matched_count = matched_count
    statement.matched_amount = matched_amount
    statement.unmatched_count = unmatched_count
    statement.status = StatementStatus.RECONCILED
    statement.reconciled_at = datetime.utcnow()
    statement.reconciled_by_id = principal.id

    db.commit()
    db.refresh(statement)
    return statement


@router.post("/{statement_id}/close", response_model=CorporateCardStatementRead, dependencies=[Depends(Require("expenses:write"))])
async def close_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Close a statement (final, prevents further changes)."""
    query = (
        db.query(CorporateCardStatement)
        .join(CorporateCard)
        .filter(CorporateCardStatement.id == statement_id)
        .with_for_update()
    )
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=CorporateCard.employee_id,
        created_by_field=CorporateCardStatement.created_by_id,
    )
    statement = query.first()
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")

    if statement.status == StatementStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Statement is already closed")

    if statement.status != StatementStatus.RECONCILED:
        raise HTTPException(status_code=400, detail="Statement must be reconciled before closing")

    statement.status = StatementStatus.CLOSED
    statement.closed_at = datetime.utcnow()
    statement.closed_by_id = principal.id

    db.commit()
    db.refresh(statement)
    return statement


@router.post("/{statement_id}/reopen", response_model=CorporateCardStatementRead, dependencies=[Depends(Require("expenses:write"))])
async def reopen_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Reopen a reconciled statement for adjustments."""
    query = (
        db.query(CorporateCardStatement)
        .join(CorporateCard)
        .filter(CorporateCardStatement.id == statement_id)
        .with_for_update()
    )
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=CorporateCard.employee_id,
        created_by_field=CorporateCardStatement.created_by_id,
    )
    statement = query.first()
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")

    if statement.status == StatementStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Cannot reopen a closed statement")

    if statement.status != StatementStatus.RECONCILED:
        raise HTTPException(status_code=400, detail="Statement is not reconciled")

    statement.status = StatementStatus.OPEN
    statement.reconciled_at = None
    statement.reconciled_by_id = None

    db.commit()
    db.refresh(statement)
    return statement


@router.get("/{statement_id}/transactions", response_model=List, dependencies=[Depends(Require("expenses:read"))])
async def get_statement_transactions(
    statement_id: int,
    status: Optional[str] = Query(default=None, description="Filter by status"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Get all transactions for a statement."""
    statement_query = (
        db.query(CorporateCardStatement)
        .join(CorporateCard)
        .filter(CorporateCardStatement.id == statement_id)
    )
    statement_query = apply_employee_scope(
        statement_query,
        principal,
        db,
        employee_field=CorporateCard.employee_id,
        created_by_field=CorporateCardStatement.created_by_id,
    )
    statement = statement_query.first()
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")

    query = (
        db.query(CorporateCardTransaction)
        .filter(CorporateCardTransaction.statement_id == statement_id)
        .order_by(CorporateCardTransaction.transaction_date.desc())
    )

    if status:
        try:
            query = query.filter(CorporateCardTransaction.status == CardTransactionStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status filter")

    return query.all()


@router.delete("/{statement_id}", status_code=204, dependencies=[Depends(Require("expenses:write"))])
async def delete_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Delete a statement and its transactions (only if open)."""
    query = (
        db.query(CorporateCardStatement)
        .join(CorporateCard)
        .options(selectinload(CorporateCardStatement.transactions))
        .filter(CorporateCardStatement.id == statement_id)
    )
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=CorporateCard.employee_id,
        created_by_field=CorporateCardStatement.created_by_id,
    )
    statement = query.first()
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")

    if statement.status != StatementStatus.OPEN:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete reconciled or closed statements",
        )

    # Check if any transactions are matched
    matched = any(
        txn.status == CardTransactionStatus.MATCHED
        for txn in statement.transactions
    )
    if matched:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete statement with matched transactions",
        )

    # Delete transactions first
    for txn in statement.transactions:
        db.delete(txn)

    db.delete(statement)
    db.commit()
