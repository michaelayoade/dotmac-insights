"""Corporate card transaction endpoints."""
from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.expenses.schemas import (
    CorporateCardTransactionCreate,
    CorporateCardTransactionRead,
    CorporateCardTransactionUpdate,
    TransactionMatchPayload,
    TransactionDisputePayload,
)
from app.database import get_db
from app.models.expense_management import (
    CorporateCard,
    CorporateCardTransaction,
    CorporateCardStatement,
    CardTransactionStatus,
    ExpenseClaimLine,
)
from app.auth import get_current_principal, Principal, Require

router = APIRouter()


def compute_import_hash(card_id: int, transaction_date: datetime, amount: Decimal, reference: Optional[str]) -> str:
    """Compute a hash for deduplication during import."""
    data = f"{card_id}:{transaction_date.isoformat()}:{amount}:{reference or ''}"
    return hashlib.sha256(data.encode()).hexdigest()


@router.get("/", response_model=List[CorporateCardTransactionRead], dependencies=[Depends(Require("expenses:read"))])
def list_transactions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    card_id: Optional[int] = Query(default=None, description="Filter by card"),
    statement_id: Optional[int] = Query(default=None, description="Filter by statement"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    unmatched_only: bool = Query(default=False, description="Only show unmatched transactions"),
    db: Session = Depends(get_db),
):
    """List corporate card transactions with optional filters."""
    query = db.query(CorporateCardTransaction).order_by(
        CorporateCardTransaction.transaction_date.desc()
    )

    if card_id:
        query = query.filter(CorporateCardTransaction.card_id == card_id)

    if statement_id:
        query = query.filter(CorporateCardTransaction.statement_id == statement_id)

    if status:
        try:
            query = query.filter(CorporateCardTransaction.status == CardTransactionStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status filter")

    if unmatched_only:
        query = query.filter(
            CorporateCardTransaction.status.in_([
                CardTransactionStatus.IMPORTED,
                CardTransactionStatus.UNMATCHED,
            ])
        )

    transactions = query.offset(offset).limit(limit).all()
    return transactions


@router.get("/{transaction_id}", response_model=CorporateCardTransactionRead, dependencies=[Depends(Require("expenses:read"))])
def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    """Get a single transaction by ID."""
    transaction = (
        db.query(CorporateCardTransaction)
        .filter(CorporateCardTransaction.id == transaction_id)
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.post("/", response_model=CorporateCardTransactionRead, status_code=201)
async def create_transaction(
    payload: CorporateCardTransactionCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Create a new corporate card transaction (manual entry)."""
    # Validate card exists
    card = db.query(CorporateCard).filter(CorporateCard.id == payload.card_id).first()
    if not card:
        raise HTTPException(status_code=400, detail="Corporate card not found")

    # Validate statement if provided
    if payload.statement_id:
        statement = (
            db.query(CorporateCardStatement)
            .filter(CorporateCardStatement.id == payload.statement_id)
            .first()
        )
        if not statement:
            raise HTTPException(status_code=400, detail="Statement not found")
        if statement.card_id != payload.card_id:
            raise HTTPException(status_code=400, detail="Statement does not belong to this card")

    # Compute import hash for deduplication
    transaction_datetime = datetime.combine(payload.transaction_date, datetime.min.time())
    import_hash = compute_import_hash(
        payload.card_id,
        transaction_datetime,
        payload.amount,
        payload.transaction_reference,
    )

    # Check for duplicate
    existing = (
        db.query(CorporateCardTransaction)
        .filter(CorporateCardTransaction.import_hash == import_hash)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Duplicate transaction detected",
        )

    transaction = CorporateCardTransaction(
        card_id=payload.card_id,
        statement_id=payload.statement_id,
        transaction_date=transaction_datetime,
        posting_date=datetime.combine(payload.posting_date, datetime.min.time()) if payload.posting_date else None,
        merchant_name=payload.merchant_name,
        merchant_category_code=payload.merchant_category_code,
        description=payload.description,
        amount=payload.amount,
        currency=payload.currency,
        original_amount=payload.original_amount,
        original_currency=payload.original_currency,
        conversion_rate=payload.conversion_rate,
        transaction_reference=payload.transaction_reference,
        authorization_code=payload.authorization_code,
        status=CardTransactionStatus.IMPORTED,
        import_hash=import_hash,
        imported_at=datetime.utcnow(),
    )

    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


@router.put("/{transaction_id}", response_model=CorporateCardTransactionRead)
async def update_transaction(
    transaction_id: int,
    payload: CorporateCardTransactionUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Update a transaction's status or matching."""
    transaction = (
        db.query(CorporateCardTransaction)
        .filter(CorporateCardTransaction.id == transaction_id)
        .with_for_update()
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(transaction, field, value)

    db.commit()
    db.refresh(transaction)
    return transaction


@router.post("/{transaction_id}/match", response_model=CorporateCardTransactionRead)
async def match_transaction(
    transaction_id: int,
    payload: TransactionMatchPayload,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Match a transaction to an expense claim line."""
    transaction = (
        db.query(CorporateCardTransaction)
        .filter(CorporateCardTransaction.id == transaction_id)
        .with_for_update()
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if transaction.status in [CardTransactionStatus.EXCLUDED, CardTransactionStatus.PERSONAL]:
        raise HTTPException(status_code=400, detail="Cannot match excluded or personal transactions")

    # Validate expense claim line exists
    line = (
        db.query(ExpenseClaimLine)
        .filter(ExpenseClaimLine.id == payload.expense_claim_line_id)
        .first()
    )
    if not line:
        raise HTTPException(status_code=400, detail="Expense claim line not found")

    transaction.expense_claim_line_id = payload.expense_claim_line_id
    transaction.match_confidence = payload.confidence
    transaction.status = CardTransactionStatus.MATCHED

    db.commit()
    db.refresh(transaction)
    return transaction


@router.post("/{transaction_id}/unmatch", response_model=CorporateCardTransactionRead)
async def unmatch_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Remove matching from a transaction."""
    transaction = (
        db.query(CorporateCardTransaction)
        .filter(CorporateCardTransaction.id == transaction_id)
        .with_for_update()
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    transaction.expense_claim_line_id = None
    transaction.match_confidence = None
    transaction.status = CardTransactionStatus.UNMATCHED

    db.commit()
    db.refresh(transaction)
    return transaction


@router.post("/{transaction_id}/dispute", response_model=CorporateCardTransactionRead)
async def dispute_transaction(
    transaction_id: int,
    payload: TransactionDisputePayload,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Mark a transaction as disputed."""
    transaction = (
        db.query(CorporateCardTransaction)
        .filter(CorporateCardTransaction.id == transaction_id)
        .with_for_update()
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if not payload.reason:
        raise HTTPException(status_code=400, detail="Dispute reason is required")

    transaction.status = CardTransactionStatus.DISPUTED
    transaction.dispute_reason = payload.reason
    transaction.disputed_at = datetime.utcnow()

    db.commit()
    db.refresh(transaction)
    return transaction


@router.post("/{transaction_id}/resolve", response_model=CorporateCardTransactionRead)
async def resolve_dispute(
    transaction_id: int,
    resolution_notes: str,
    new_status: str = Query(default="unmatched", description="Status after resolution"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Resolve a disputed transaction."""
    transaction = (
        db.query(CorporateCardTransaction)
        .filter(CorporateCardTransaction.id == transaction_id)
        .with_for_update()
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if transaction.status != CardTransactionStatus.DISPUTED:
        raise HTTPException(status_code=400, detail="Transaction is not disputed")

    try:
        resolved_status = CardTransactionStatus(new_status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid resolution status")

    transaction.status = resolved_status
    transaction.resolution_notes = resolution_notes

    db.commit()
    db.refresh(transaction)
    return transaction


@router.post("/{transaction_id}/exclude", response_model=CorporateCardTransactionRead)
async def exclude_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Exclude a transaction from reconciliation."""
    transaction = (
        db.query(CorporateCardTransaction)
        .filter(CorporateCardTransaction.id == transaction_id)
        .with_for_update()
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    transaction.status = CardTransactionStatus.EXCLUDED

    db.commit()
    db.refresh(transaction)
    return transaction


@router.post("/{transaction_id}/mark-personal", response_model=CorporateCardTransactionRead)
async def mark_personal(
    transaction_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Mark a transaction as personal (to be repaid by employee)."""
    transaction = (
        db.query(CorporateCardTransaction)
        .filter(CorporateCardTransaction.id == transaction_id)
        .with_for_update()
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    transaction.status = CardTransactionStatus.PERSONAL

    db.commit()
    db.refresh(transaction)
    return transaction


@router.delete("/{transaction_id}", status_code=204)
async def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Delete a transaction (only if not matched to an expense claim)."""
    transaction = (
        db.query(CorporateCardTransaction)
        .filter(CorporateCardTransaction.id == transaction_id)
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if transaction.expense_claim_line_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete transaction matched to an expense claim",
        )

    db.delete(transaction)
    db.commit()


# =============================================================================
# AUTO-MATCHING ENDPOINTS
# =============================================================================

@router.get("/matching/suggest")
async def suggest_matches(
    transaction_id: Optional[int] = Query(default=None, description="Suggest matches for specific transaction"),
    statement_id: Optional[int] = Query(default=None, description="Suggest matches for all transactions in statement"),
    card_id: Optional[int] = Query(default=None, description="Suggest matches for all transactions on card"),
    min_confidence: float = Query(default=0.5, ge=0.0, le=1.0, description="Minimum confidence score"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """
    Suggest potential expense claim line matches for unmatched transactions.

    Returns a list of candidates sorted by confidence score (highest first).
    Each candidate includes:
    - transaction_id: The card transaction
    - expense_claim_line_id: The matching expense line
    - confidence: Match confidence (0.0 to 1.0)
    - reasons: Why this match was suggested
    """
    from app.services.transaction_matching_service import suggest_matches_endpoint_helper

    return suggest_matches_endpoint_helper(
        db=db,
        transaction_id=transaction_id,
        statement_id=statement_id,
        card_id=card_id,
        min_confidence=min_confidence,
    )


@router.post("/matching/auto-match")
async def auto_match_transactions(
    statement_id: Optional[int] = Query(default=None, description="Auto-match transactions in statement"),
    card_id: Optional[int] = Query(default=None, description="Auto-match transactions on card"),
    threshold: float = Query(default=0.85, ge=0.5, le=1.0, description="Minimum confidence to auto-match"),
    dry_run: bool = Query(default=False, description="Preview matches without applying"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """
    Automatically match transactions to expense claim lines.

    Only matches above the confidence threshold are applied.
    Use dry_run=true to preview matches without actually updating records.

    Matching criteria:
    - Amount: Transaction amount matches expense line (within 1% tolerance)
    - Date: Transaction date within 7 days of expense date
    - Employee: Card holder matches expense claim submitter
    - Merchant: Fuzzy match of merchant names (bonus score)
    """
    from app.services.transaction_matching_service import TransactionMatchingService, MatchConfig

    config = MatchConfig(auto_match_threshold=threshold)
    service = TransactionMatchingService(db, config=config)

    result = service.auto_match(
        statement_id=statement_id,
        card_id=card_id,
        dry_run=dry_run,
    )

    if not dry_run:
        db.commit()

    return result


@router.post("/{transaction_id}/auto-match")
async def auto_match_single_transaction(
    transaction_id: int,
    min_confidence: float = Query(default=0.5, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """
    Find and apply the best match for a single transaction.

    If a match is found above the minimum confidence, it will be applied.
    """
    from app.services.transaction_matching_service import TransactionMatchingService

    service = TransactionMatchingService(db)
    candidates = service.find_matches_for_transaction(
        transaction_id, min_confidence
    )

    if not candidates:
        return {
            "matched": False,
            "message": "No suitable matches found",
            "candidates_found": 0,
        }

    # Take the best match
    best = candidates[0]

    # Apply the match
    txn = db.query(CorporateCardTransaction).filter(
        CorporateCardTransaction.id == transaction_id
    ).first()

    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    txn.expense_claim_line_id = best.expense_claim_line_id
    txn.match_confidence = best.confidence
    txn.status = CardTransactionStatus.MATCHED

    db.commit()
    db.refresh(txn)

    return {
        "matched": True,
        "transaction_id": txn.id,
        "expense_claim_line_id": best.expense_claim_line_id,
        "expense_claim_id": best.expense_claim_id,
        "confidence": round(best.confidence, 3),
        "reasons": best.match_reasons,
    }
