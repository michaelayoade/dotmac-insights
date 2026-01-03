"""Expense claim endpoints."""
from __future__ import annotations

from typing import Dict, List, Optional, Any, cast
from datetime import datetime, timezone
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
from app.api.expenses.access import apply_employee_scope, assert_employee_access

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


def _serialize_claim_line(line: Any) -> Dict[str, Any]:
    """Serialize an expense claim line to dict."""
    return {
        "id": line.id,
        "category_id": line.category_id,
        "expense_date": line.expense_date.isoformat() if line.expense_date else None,
        "description": line.description,
        "claimed_amount": float(line.claimed_amount) if line.claimed_amount else 0,
        "sanctioned_amount": float(line.sanctioned_amount) if line.sanctioned_amount else 0,
        "currency": line.currency,
        "funding_method": line.funding_method.value if line.funding_method else None,
        "has_receipt": line.has_receipt,
        "tax_amount": float(line.tax_amount) if line.tax_amount else 0,
        "conversion_rate": float(line.conversion_rate) if line.conversion_rate else 1,
        "base_claimed_amount": float(line.base_claimed_amount) if line.base_claimed_amount else 0,
    }


def _serialize_claim(claim: ExpenseClaim, transfer: Optional[Transfer] = None) -> Dict[str, Any]:
    """Serialize an expense claim to dict following coding standards."""
    result = {
        "id": claim.id,
        "claim_number": claim.claim_number,
        "title": claim.title,
        "employee_id": claim.employee_id,
        "claim_date": claim.claim_date.isoformat() if claim.claim_date else None,
        "status": claim.status.value if claim.status else None,
        "total_claimed_amount": float(claim.total_claimed_amount) if claim.total_claimed_amount else 0,
        "total_taxes": float(claim.total_taxes) if claim.total_taxes else 0,
        "currency": claim.currency,
        "base_currency": claim.base_currency,
        "conversion_rate": float(claim.conversion_rate) if claim.conversion_rate else 1,
        "payment_status": claim.payment_status,
        "amount_paid": float(claim.amount_paid) if claim.amount_paid else 0,
        "payment_date": claim.payment_date.isoformat() if claim.payment_date else None,
        "payment_reference": claim.payment_reference,
        "mode_of_payment": claim.mode_of_payment,
        "lines": [_serialize_claim_line(line) for line in (claim.lines or [])],
    }
    # Add transfer details if available
    if transfer:
        result["transfer_reference"] = transfer.reference
        result["transfer_status"] = transfer.status.value if transfer.status else None
        result["transfer_provider"] = transfer.provider.value if transfer.provider else None
        result["transfer_amount"] = float(transfer.amount) if transfer.amount else None
        result["transfer_fee"] = float(transfer.fee) if transfer.fee else None
        result["transfer_created_at"] = transfer.created_at.isoformat() if transfer.created_at else None
    else:
        # Check if transfer details were attached dynamically
        claim_any = cast(Any, claim)
        if hasattr(claim_any, "transfer_reference"):
            result["transfer_reference"] = claim_any.transfer_reference
            result["transfer_status"] = claim_any.transfer_status
            result["transfer_provider"] = claim_any.transfer_provider
            result["transfer_amount"] = float(claim_any.transfer_amount) if claim_any.transfer_amount else None
            result["transfer_fee"] = float(claim_any.transfer_fee) if claim_any.transfer_fee else None
            result["transfer_created_at"] = claim_any.transfer_created_at.isoformat() if claim_any.transfer_created_at else None
    return result


@router.get("/", dependencies=[Depends(Require("expenses:read"))])
def list_claims(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """List expense claims with pagination."""
    query = db.query(ExpenseClaim).options(selectinload(ExpenseClaim.lines)).order_by(ExpenseClaim.created_at.desc())
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=ExpenseClaim.employee_id,
        created_by_field=ExpenseClaim.created_by_id,
    )
    if status:
        try:
            query = query.filter(ExpenseClaim.status == ExpenseClaimStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    total = query.count()
    claims = query.offset(offset).limit(limit).all()

    # Fetch transfer details for claims with payment references
    refs = [c.payment_reference for c in claims if c.payment_reference]
    transfers: Dict[str, Transfer] = {}
    if refs:
        for t in db.query(Transfer).filter(Transfer.reference.in_(refs)).all():
            transfers[t.reference] = t

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            _serialize_claim(claim, transfers.get(claim.payment_reference) if claim.payment_reference else None)
            for claim in claims
        ],
    }


@router.get("/{claim_id}", dependencies=[Depends(Require("expenses:read"))])
def get_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get expense claim detail."""
    query = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
    )
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=ExpenseClaim.employee_id,
        created_by_field=ExpenseClaim.created_by_id,
    )
    claim = query.first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    transfer = None
    if claim.payment_reference:
        transfer = db.query(Transfer).filter(Transfer.reference == claim.payment_reference).first()
    return _serialize_claim(claim, transfer)


@router.post("/", status_code=201, dependencies=[Depends(Require("expenses:write"))])
async def create_claim(
    payload: ExpenseClaimCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new expense claim."""
    service = ExpenseService(db)
    try:
        assert_employee_access(principal, db, payload.employee_id)
        claim = service.create_claim(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if principal.type == "user":
        claim.created_by_id = principal.id
    db.commit()
    db.refresh(claim)
    claim_with_lines = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim.id)
        .first()
    )
    if claim_with_lines is None:
        raise HTTPException(status_code=404, detail="Expense claim not found")
    return _serialize_claim(claim_with_lines)


@router.post("/{claim_id}/submit", dependencies=[Depends(Require("expenses:write"))])
async def submit_claim(
    claim_id: int,
    company_code: Optional[str] = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Submit an expense claim for approval."""
    query = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
    )
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=ExpenseClaim.employee_id,
        created_by_field=ExpenseClaim.created_by_id,
    )
    claim = query.first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    service = ExpenseService(db)
    try:
        claim = service.submit_claim(claim, user_id=principal.id, company_code=company_code)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(claim)
    return _serialize_claim(claim)


@router.post("/{claim_id}/approve", dependencies=[Depends(Require("expenses:write"))])
async def approve_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Approve an expense claim."""
    query = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
    )
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=ExpenseClaim.employee_id,
        created_by_field=ExpenseClaim.created_by_id,
    )
    claim = query.first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    service = ExpenseService(db)
    try:
        claim = service.approve_claim(claim, user_id=principal.id)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(claim)
    return _serialize_claim(claim)


@router.post("/{claim_id}/reject", dependencies=[Depends(Require("expenses:write"))])
async def reject_claim(
    claim_id: int,
    reason: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Reject an expense claim."""
    query = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
    )
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=ExpenseClaim.employee_id,
        created_by_field=ExpenseClaim.created_by_id,
    )
    claim = query.first()
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
    return _serialize_claim(claim)


@router.post("/{claim_id}/return", dependencies=[Depends(Require("expenses:write"))])
async def return_claim(
    claim_id: int,
    reason: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Return an expense claim for revision."""
    query = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
    )
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=ExpenseClaim.employee_id,
        created_by_field=ExpenseClaim.created_by_id,
    )
    claim = query.first()
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
    return _serialize_claim(claim)


@router.post("/{claim_id}/recall", dependencies=[Depends(Require("expenses:write"))])
async def recall_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Recall a submitted expense claim."""
    query = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
    )
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=ExpenseClaim.employee_id,
        created_by_field=ExpenseClaim.created_by_id,
    )
    claim = query.first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    service = ExpenseService(db)
    try:
        claim = service.recall_claim(claim, user_id=principal.id)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(claim)
    return _serialize_claim(claim)


@router.post("/{claim_id}/post", dependencies=[Depends(Require("expenses:write"))])
async def post_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Post an expense claim to accounting."""
    query = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
    )
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=ExpenseClaim.employee_id,
        created_by_field=ExpenseClaim.created_by_id,
    )
    claim = query.first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    posting_service = ExpensePostingService(db)
    try:
        posting_service.post_claim(claim, user_id=principal.id)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(claim)
    return _serialize_claim(claim)


@router.post("/{claim_id}/reverse", dependencies=[Depends(Require("expenses:write"))])
async def reverse_claim(
    claim_id: int,
    reason: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Reverse a posted expense claim."""
    query = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
    )
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=ExpenseClaim.employee_id,
        created_by_field=ExpenseClaim.created_by_id,
    )
    claim = query.first()
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
    return _serialize_claim(claim)


@router.post("/{claim_id}/pay-now", dependencies=[Depends(Require("expenses:write"))])
async def pay_claim_now(
    claim_id: int,
    payload: ExpenseClaimPayNow,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Pay an approved or posted expense claim via transfer provider."""
    query = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
    )
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=ExpenseClaim.employee_id,
        created_by_field=ExpenseClaim.created_by_id,
    )
    claim = query.first()
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

        reference = f"EXP-{claim.id}-{int(datetime.now(timezone.utc).timestamp())}"
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
        return _serialize_claim(claim, transfer)
    finally:
        await client.close()


@router.post("/{claim_id}/verify-transfer", dependencies=[Depends(Require("expenses:write"))])
async def verify_claim_transfer(
    claim_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Verify transfer status for an expense claim payout."""
    query = (
        db.query(ExpenseClaim)
        .options(selectinload(ExpenseClaim.lines))
        .filter(ExpenseClaim.id == claim_id)
        .with_for_update()
    )
    query = apply_employee_scope(
        query,
        principal,
        db,
        employee_field=ExpenseClaim.employee_id,
        created_by_field=ExpenseClaim.created_by_id,
    )
    claim = query.first()
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
        claim.payment_date = datetime.now(timezone.utc)
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
    return _serialize_claim(claim, transfer)
