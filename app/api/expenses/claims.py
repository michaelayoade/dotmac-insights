"""Expense claim endpoints."""
from __future__ import annotations

from typing import List, Optional, Any, cast
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from app.api.expenses.schemas import ExpenseClaimCreate, ExpenseClaimRead, ExpenseClaimPayNow
from app.database import get_db
from app.models.expense_management import ExpenseClaim, ExpenseClaimStatus
from app.models.transfer import Transfer, TransferStatus, TransferType
from app.models.gateway_transaction import GatewayProvider
from app.integrations.payments.providers.paystack import PaystackClient
from app.integrations.payments.providers.flutterwave import FlutterwaveClient
from app.integrations.payments.base import TransferRecipient, TransferRequest
from app.integrations.payments.config import get_payment_settings
from app.services.errors import ValidationError
from app.services.expense_service import ExpenseService
from app.services.expense_posting_service import ExpensePostingService
from app.auth import get_current_principal, Principal, Require

router = APIRouter()


def _attach_transfer_details(claim: ExpenseClaim, transfer: Optional[Transfer]) -> ExpenseClaim:
    if not transfer:
        return claim
    claim_any = cast(Any, claim)
    claim_any.transfer_reference = transfer.reference
    claim_any.transfer_status = transfer.status.value if transfer.status else None
    claim_any.transfer_provider = transfer.provider.value if transfer.provider else None
    claim_any.transfer_amount = transfer.amount
    claim_any.transfer_fee = transfer.fee
    claim_any.transfer_created_at = transfer.created_at
    return claim


@router.get("/", response_model=List[ExpenseClaimRead], dependencies=[Depends(Require("expenses:read"))])
def list_claims(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    db: Session = Depends(get_db),
):
    query = db.query(ExpenseClaim).options(selectinload(ExpenseClaim.lines)).order_by(ExpenseClaim.created_at.desc())
    if status:
        try:
            from app.models.expense_management import ExpenseClaimStatus

            query = query.filter(ExpenseClaim.status == ExpenseClaimStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status filter")

    claims = query.offset(offset).limit(limit).all()
    refs = [c.payment_reference for c in claims if c.payment_reference]
    transfers = {}
    if refs:
        for t in db.query(Transfer).filter(Transfer.reference.in_(refs)).all():
            transfers[t.reference] = t
        for claim in claims:
            if claim.payment_reference:
                _attach_transfer_details(claim, transfers.get(claim.payment_reference))
    return claims


@router.get("/{claim_id}", response_model=ExpenseClaimRead, dependencies=[Depends(Require("expenses:read"))])
def get_claim(claim_id: int, db: Session = Depends(get_db)):
    claim = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    transfer = None
    if claim.payment_reference:
        transfer = db.query(Transfer).filter(Transfer.reference == claim.payment_reference).first()
    _attach_transfer_details(claim, transfer)
    return claim


@router.post("/", response_model=ExpenseClaimRead, status_code=201)
async def create_claim(
    payload: ExpenseClaimCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    service = ExpenseService(db)
    try:
        claim = service.create_claim(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(claim)
    return (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim.id)
        .first()
    )


@router.post("/{claim_id}/submit", response_model=ExpenseClaimRead)
async def submit_claim(
    claim_id: int,
    company_code: Optional[str] = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    claim = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    service = ExpenseService(db)
    try:
        claim = service.submit_claim(claim, user_id=principal.id, company_code=company_code)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(claim)
    return claim


@router.post("/{claim_id}/approve", response_model=ExpenseClaimRead)
async def approve_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    claim = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    service = ExpenseService(db)
    try:
        claim = service.approve_claim(claim, user_id=principal.id)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(claim)
    return claim


@router.post("/{claim_id}/reject", response_model=ExpenseClaimRead)
async def reject_claim(
    claim_id: int,
    reason: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    claim = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if not reason:
        raise HTTPException(status_code=400, detail="Rejection reason is required")

    service = ExpenseService(db)
    try:
        claim = service.reject_claim(claim, user_id=principal.id, reason=reason)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(claim)
    return claim


@router.post("/{claim_id}/return", response_model=ExpenseClaimRead)
async def return_claim(
    claim_id: int,
    reason: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    claim = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if not reason:
        raise HTTPException(status_code=400, detail="Return reason is required")

    service = ExpenseService(db)
    try:
        claim = service.return_claim(claim, reason=reason)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(claim)
    return claim


@router.post("/{claim_id}/recall", response_model=ExpenseClaimRead)
async def recall_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    claim = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    service = ExpenseService(db)
    try:
        claim = service.recall_claim(claim, user_id=principal.id)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(claim)
    return claim


@router.post("/{claim_id}/post", response_model=ExpenseClaimRead)
async def post_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    claim = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    posting_service = ExpensePostingService(db)
    try:
        posting_service.post_claim(claim, user_id=principal.id)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(claim)
    return claim


@router.post("/{claim_id}/reverse", response_model=ExpenseClaimRead)
async def reverse_claim(
    claim_id: int,
    reason: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    claim = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if not reason:
        raise HTTPException(status_code=400, detail="Reversal reason is required")

    posting_service = ExpensePostingService(db)
    try:
        posting_service.reverse_claim(claim, reason=reason, user_id=principal.id)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(claim)
    return claim


@router.post("/{claim_id}/pay-now", response_model=ExpenseClaimRead)
async def pay_claim_now(
    claim_id: int,
    payload: ExpenseClaimPayNow,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Pay an approved or posted expense claim via transfer provider."""
    claim = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if claim.status not in {ExpenseClaimStatus.APPROVED, ExpenseClaimStatus.POSTED}:
        raise HTTPException(status_code=400, detail="Only approved or posted claims can be paid")

    payable = claim.total_reimbursable or claim.total_sanctioned_amount or claim.total_claimed_amount
    payable = Decimal(str(payable or 0))
    already_paid = Decimal(str(claim.amount_paid or 0))
    outstanding = max(payable - already_paid, Decimal("0"))
    if outstanding <= 0:
        raise HTTPException(status_code=400, detail="Claim is already fully paid")

    amount = Decimal(str(payload.amount)) if payload.amount is not None else outstanding
    if amount > outstanding:
        raise HTTPException(status_code=400, detail="Amount exceeds outstanding balance")

    settings = get_payment_settings()
    provider_value = (payload.provider or settings.default_transfer_provider).lower()
    client: FlutterwaveClient | PaystackClient
    if provider_value == GatewayProvider.FLUTTERWAVE.value:
        client = FlutterwaveClient()
        provider_enum = GatewayProvider.FLUTTERWAVE
    else:
        client = PaystackClient()
        provider_enum = GatewayProvider.PAYSTACK

    try:
        account_name = payload.account_name
        if not account_name:
            account_info = await client.resolve_account(payload.account_number, payload.bank_code)
            account_name = account_info.account_name

        reference = f"EXP-{claim.id}-{int(datetime.utcnow().timestamp())}"
        recipient = TransferRecipient(
            account_number=payload.account_number,
            bank_code=payload.bank_code,
            account_name=account_name,
            currency=claim.currency or "NGN",
        )
        transfer_request = TransferRequest(
            amount=amount,
            currency=claim.currency or "NGN",
            recipient=recipient,
            reference=reference,
            reason=payload.reason or f"Expense claim {claim.claim_number or claim.id}",
            narration=payload.narration,
            metadata={"expense_claim_id": claim.id},
        )
        result = await client.initiate_transfer(transfer_request)

        status_map = {
            "success": TransferStatus.SUCCESS,
            "failed": TransferStatus.FAILED,
            "pending": TransferStatus.PENDING,
            "abandoned": TransferStatus.FAILED,
            "processing": TransferStatus.PROCESSING,
            "reversed": TransferStatus.REVERSED,
        }

        transfer = Transfer(
            reference=result.reference,
            provider=provider_enum,
            provider_reference=result.provider_reference,
            transfer_code=result.transfer_code,
            transfer_type=TransferType.SINGLE,
            amount=amount,
            currency=result.currency,
            status=status_map.get(result.status.value, TransferStatus.PENDING),
            recipient_account=payload.account_number,
            recipient_bank_code=payload.bank_code,
            recipient_bank_name=None,
            recipient_name=account_name or "Recipient",
            recipient_code=result.recipient_code,
            reason=payload.reason,
            narration=payload.narration,
            fee=result.fee,
            employee_id=claim.employee_id,
            company=claim.company,
            created_by_id=principal.id,
            extra_data={"expense_claim_id": claim.id},
            raw_response=result.raw_response,
        )
        db.add(transfer)

        claim.payment_status = "pending"
        claim.payment_reference = result.reference
        claim.mode_of_payment = provider_enum.value
        db.commit()
        db.refresh(claim)
        _attach_transfer_details(claim, transfer)
        return claim
    finally:
        await client.close()


@router.post("/{claim_id}/verify-transfer", response_model=ExpenseClaimRead)
async def verify_claim_transfer(
    claim_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    """Verify transfer status for an expense claim payout."""
    claim = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if not claim.payment_reference:
        raise HTTPException(status_code=400, detail="No payment reference on claim")

    transfer = db.query(Transfer).filter(Transfer.reference == claim.payment_reference).first()
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")

    client: FlutterwaveClient | PaystackClient
    if transfer.provider == GatewayProvider.FLUTTERWAVE:
        client = FlutterwaveClient()
        provider_enum = GatewayProvider.FLUTTERWAVE
    else:
        client = PaystackClient()
        provider_enum = GatewayProvider.PAYSTACK

    try:
        result = await client.verify_transfer(transfer.reference)
    finally:
        await client.close()

    status_map = {
        "success": TransferStatus.SUCCESS,
        "failed": TransferStatus.FAILED,
        "pending": TransferStatus.PENDING,
        "processing": TransferStatus.PROCESSING,
        "reversed": TransferStatus.REVERSED,
    }
    transfer.status = status_map.get(result.status.value, transfer.status)
    transfer.provider_reference = result.provider_reference
    transfer.transfer_code = result.transfer_code or transfer.transfer_code
    transfer.fee = result.fee

    if transfer.status == TransferStatus.SUCCESS:
        payable = claim.total_reimbursable or claim.total_sanctioned_amount or claim.total_claimed_amount
        payable = Decimal(str(payable or 0))
        already_paid = Decimal(str(claim.amount_paid or 0))
        new_paid = already_paid + transfer.amount
        claim.amount_paid = new_paid
        claim.payment_reference = transfer.reference
        claim.payment_date = datetime.utcnow()
        claim.mode_of_payment = provider_enum.value
        if new_paid >= payable and payable > 0:
            claim.payment_status = "paid"
            claim.status = ExpenseClaimStatus.PAID
        else:
            claim.payment_status = "partially_paid"
    elif transfer.status == TransferStatus.FAILED:
        claim.payment_status = "failed"
    elif transfer.status == TransferStatus.REVERSED:
        claim.payment_status = "reversed"

    db.commit()
    db.refresh(claim)
    _attach_transfer_details(claim, transfer)
    return claim
