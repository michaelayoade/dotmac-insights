"""
Transfer API endpoints.

Handles bank transfers (payouts) to Nigerian bank accounts.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.transfer import Transfer, TransferStatus, TransferType
from app.integrations.payments.providers.paystack import PaystackClient
from app.integrations.payments.providers.flutterwave import FlutterwaveClient
from app.integrations.payments.base import TransferRecipient, TransferRequest
from app.integrations.payments.config import get_payment_settings
from app.models.gateway_transaction import GatewayProvider

router = APIRouter(prefix="/transfers", tags=["transfers"])


# =============================================================================
# Schemas
# =============================================================================

class TransferListResponse(BaseModel):
    items: list[dict]
    limit: int
    offset: int
    total: int

class RecipientSchema(BaseModel):
    """Bank account recipient details."""
    account_number: str = Field(..., min_length=10, max_length=10)
    bank_code: str
    account_name: Optional[str] = None


class InitiateTransferSchema(BaseModel):
    """Request to initiate a bank transfer."""
    amount: Decimal = Field(..., gt=0, description="Amount in Naira")
    recipient: RecipientSchema
    currency: str = "NGN"
    reference: Optional[str] = None
    reason: Optional[str] = None
    narration: Optional[str] = None
    transfer_type: str = "single"  # single, payroll, vendor_payment
    metadata: Optional[dict] = None
    provider: Optional[str] = None


class BulkTransferItemSchema(BaseModel):
    """Single transfer in a bulk request."""
    amount: Decimal = Field(..., gt=0)
    recipient: RecipientSchema
    reference: Optional[str] = None
    reason: Optional[str] = None


class BulkTransferSchema(BaseModel):
    """Request to initiate bulk transfers."""
    transfers: List[BulkTransferItemSchema]
    currency: str = "NGN"
    provider: Optional[str] = None


class TransferResponse(BaseModel):
    """Transfer initiation response."""
    reference: str
    provider_reference: str
    status: str
    amount: Decimal
    currency: str
    recipient_code: str
    fee: Decimal = Decimal("0")


class PayrollPayoutRequest(BaseModel):
    """Batch payout request for payroll-related transfers."""
    transfer_ids: List[int]
    provider: Optional[str] = None


# =============================================================================
# Helper Functions
# =============================================================================

def get_transfer_client(provider: Optional[str] = None):
    """Get appropriate payment client for transfers."""
    settings = get_payment_settings()
    provider = (provider or settings.default_transfer_provider).lower()

    if provider == GatewayProvider.FLUTTERWAVE.value:
        return FlutterwaveClient()
    if provider == GatewayProvider.PAYSTACK.value:
        return PaystackClient()

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported transfer provider",
    )


def generate_transfer_reference() -> str:
    """Generate unique transfer reference."""
    return f"TRF-{uuid.uuid4().hex[:12].upper()}"


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/", response_model=TransferListResponse)
async def list_transfers(
    status: Optional[str] = None,
    provider: Optional[str] = None,
    transfer_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List transfers with optional filters."""
    query = select(Transfer)

    if status:
        try:
            status_enum = TransferStatus(status)
            query = query.where(Transfer.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status filter",
            )
    if provider:
        try:
            provider_enum = GatewayProvider(provider)
            query = query.where(Transfer.provider == provider_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid provider filter",
            )
    if transfer_type:
        try:
            type_enum = TransferType(transfer_type)
            query = query.where(Transfer.transfer_type == type_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid transfer type filter",
            )

    total_result = await db.execute(query)
    total = len(total_result.scalars().all())

    query = query.order_by(Transfer.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    transfers = result.scalars().all()

    return {
        "items": [
            {
                "id": t.id,
                "reference": t.reference,
                "provider": t.provider.value if t.provider else None,
                "provider_reference": t.provider_reference,
                "recipient_name": t.recipient_name,
                "recipient_account": t.recipient_account,
                "recipient_bank_code": t.recipient_bank_code,
                "amount": t.amount,
                "currency": t.currency,
                "status": t.status.value if t.status else None,
                "fees": t.fee,
                "transfer_type": t.transfer_type.value if t.transfer_type else None,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "company": t.company,
                "salary_slip_id": t.salary_slip_id,
                "payroll_run_id": t.payroll_run_id,
            }
            for t in transfers
        ],
        "limit": limit,
        "offset": offset,
        "total": total,
    }

@router.post("/initiate", response_model=TransferResponse)
async def initiate_transfer(
    request: InitiateTransferSchema,
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate a bank transfer (payout).

    Transfers funds from your balance to a Nigerian bank account.
    """
    settings = get_payment_settings()
    provider_value = (request.provider or settings.default_transfer_provider).lower()
    reference = request.reference or generate_transfer_reference()

    # Check for duplicate reference
    existing = await db.execute(
        select(Transfer).where(Transfer.reference == reference)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transfer reference already exists",
        )

    client = get_transfer_client(provider_value)

    try:
        # Resolve account first to get account name
        if not request.recipient.account_name:
            account_info = await client.resolve_account(
                request.recipient.account_number,
                request.recipient.bank_code,
            )
            account_name = account_info.account_name
        else:
            account_name = request.recipient.account_name

        # Create recipient
        recipient = TransferRecipient(
            account_number=request.recipient.account_number,
            bank_code=request.recipient.bank_code,
            account_name=account_name,
            currency=request.currency,
        )

        # Initiate transfer
        transfer_request = TransferRequest(
            amount=request.amount,
            currency=request.currency,
            recipient=recipient,
            reference=reference,
            reason=request.reason,
            narration=request.narration,
            metadata=request.metadata,
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

        provider_enum = (
            GatewayProvider.FLUTTERWAVE
            if provider_value == GatewayProvider.FLUTTERWAVE.value
            else GatewayProvider.PAYSTACK
        )

        # Map transfer type
        type_map = {
            "single": TransferType.SINGLE,
            "bulk": TransferType.BULK,
            "payroll": TransferType.PAYROLL,
            "vendor_payment": TransferType.VENDOR_PAYMENT,
        }

        # Save transfer record
        transfer = Transfer(
            reference=reference,
            provider=provider_enum,
            provider_reference=result.provider_reference,
            transfer_type=type_map.get(request.transfer_type, TransferType.SINGLE),
            amount=request.amount,
            currency=request.currency,
            status=status_map.get(result.status.value, TransferStatus.PENDING),
            recipient_account=request.recipient.account_number,
            recipient_bank_code=request.recipient.bank_code,
            recipient_name=account_name,
            recipient_code=result.recipient_code,
            reason=request.reason,
            narration=request.narration,
            fee=result.fee,
            metadata=request.metadata,
        )
        db.add(transfer)
        await db.commit()

        return TransferResponse(
            reference=result.reference,
            provider_reference=result.provider_reference,
            status=result.status.value,
            amount=result.amount,
            currency=result.currency,
            recipient_code=result.recipient_code,
            fee=result.fee,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    finally:
        await client.close()


@router.post("/payroll/payout")
async def pay_pending_payroll_transfers(
    request: PayrollPayoutRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate payouts for pending payroll transfers (created from HR handoff).
    """
    if not request.transfer_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No transfer IDs supplied",
        )

    transfers_result = await db.execute(
        select(Transfer).where(Transfer.id.in_(request.transfer_ids))
    )
    transfers = transfers_result.scalars().all()

    if not transfers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transfers not found",
        )

    provider_value = (request.provider or "").lower()
    provider_enum = (
        GatewayProvider.FLUTTERWAVE
        if provider_value == GatewayProvider.FLUTTERWAVE.value
        else GatewayProvider.PAYSTACK
    )

    client = get_transfer_client(request.provider)
    try:
        transfer_requests: List[TransferRequest] = []
        for t in transfers:
            if t.transfer_type != TransferType.PAYROLL:
                continue
            recipient = TransferRecipient(
                account_number=t.recipient_account,
                bank_code=t.recipient_bank_code,
                account_name=t.recipient_name,
                currency=t.currency,
                recipient_code=t.recipient_code,
            )
            transfer_requests.append(
                TransferRequest(
                    amount=t.amount,
                    currency=t.currency,
                    recipient=recipient,
                    reference=t.reference,
                    reason=t.reason,
                    metadata={"salary_slip_id": t.salary_slip_id, "payroll_run_id": t.payroll_run_id},
                )
            )

        if not transfer_requests:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No payroll transfers to pay",
            )

        # Use bulk when multiple
        if len(transfer_requests) > 1:
            results = await client.initiate_bulk_transfer(transfer_requests)
        else:
            results = [await client.initiate_transfer(transfer_requests[0])]

        status_map = {
            "success": TransferStatus.SUCCESS,
            "failed": TransferStatus.FAILED,
            "pending": TransferStatus.PENDING,
            "processing": TransferStatus.PROCESSING,
            "reversed": TransferStatus.REVERSED,
        }

        for req_item, result in zip(transfer_requests, results):
            t = next((x for x in transfers if x.reference == result.reference), None)
            if not t:
                continue
            t.provider = provider_enum
            t.provider_reference = result.provider_reference
            t.status = status_map.get(result.status.value, TransferStatus.PENDING)
            t.fee = result.fee
            t.raw_response = result.raw_response

        await db.commit()

        return {
            "count": len(results),
            "results": [
                {
                    "reference": r.reference,
                    "provider_reference": r.provider_reference,
                    "status": r.status.value,
                    "amount": r.amount,
                }
                for r in results
            ],
        }
    finally:
        await client.close()


@router.post("/bulk", response_model=list[TransferResponse])
async def initiate_bulk_transfers(
    request: BulkTransferSchema,
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate multiple transfers in one batch.
    """
    if not request.transfers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No transfers supplied",
        )

    settings = get_payment_settings()
    provider_value = (request.provider or settings.default_transfer_provider).lower()
    client = get_transfer_client(provider_value)

    try:
        # Prepare references and check for duplicates
        references = [
            transfer.reference or generate_transfer_reference()
            for transfer in request.transfers
        ]

        # Ensure references are unique within the payload
        if len(set(references)) != len(references):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate references in bulk payload",
            )

        existing_refs = await db.execute(
            select(Transfer.reference).where(Transfer.reference.in_(references))
        )
        if existing_refs.scalars().all():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="One or more transfer references already exist",
            )

        # Build transfer requests
        transfer_requests: List[TransferRequest] = []
        resolved_names: List[str] = []
        for ref, item in zip(references, request.transfers):
            # Resolve account name if missing
            if not item.recipient.account_name:
                account_info = await client.resolve_account(
                    item.recipient.account_number,
                    item.recipient.bank_code,
                )
                account_name = account_info.account_name
            else:
                account_name = item.recipient.account_name

            resolved_names.append(account_name)

            recipient = TransferRecipient(
                account_number=item.recipient.account_number,
                bank_code=item.recipient.bank_code,
                account_name=account_name,
                currency=request.currency,
            )

            transfer_requests.append(
                TransferRequest(
                    amount=item.amount,
                    currency=request.currency,
                    recipient=recipient,
                    reference=ref,
                    reason=item.reason,
                )
            )

        results = await client.initiate_bulk_transfer(transfer_requests)

        status_map = {
            "success": TransferStatus.SUCCESS,
            "failed": TransferStatus.FAILED,
            "pending": TransferStatus.PENDING,
            "processing": TransferStatus.PROCESSING,
            "reversed": TransferStatus.REVERSED,
        }
        provider_enum = (
            GatewayProvider.FLUTTERWAVE
            if provider_value == GatewayProvider.FLUTTERWAVE.value
            else GatewayProvider.PAYSTACK
        )

        transfer_records = []
        for transfer_request, result, account_name in zip(
            transfer_requests, results, resolved_names
        ):
            transfer_records.append(
                Transfer(
                    reference=transfer_request.reference,
                    provider=provider_enum,
                    provider_reference=result.provider_reference,
                    transfer_type=TransferType.BULK,
                    amount=transfer_request.amount,
                    currency=transfer_request.currency,
                    status=status_map.get(result.status.value, TransferStatus.PENDING),
                    recipient_account=transfer_request.recipient.account_number,
                    recipient_bank_code=transfer_request.recipient.bank_code,
                    recipient_name=account_name,
                    recipient_code=result.recipient_code,
                    reason=transfer_request.reason,
                    fee=result.fee,
                )
            )

        db.add_all(transfer_records)
        await db.commit()

        return [
            TransferResponse(
                reference=result.reference,
                provider_reference=result.provider_reference,
                status=result.status.value,
                amount=result.amount,
                currency=result.currency,
                recipient_code=result.recipient_code,
                fee=result.fee,
            )
            for result in results
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    finally:
        await client.close()


@router.get("/verify/{reference}")
async def verify_transfer(
    reference: str,
    db: AsyncSession = Depends(get_db),
):
    """Verify a transfer status."""
    result = await db.execute(
        select(Transfer).where(Transfer.reference == reference)
    )
    transfer = result.scalar_one_or_none()

    if not transfer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transfer not found",
        )

    client = get_transfer_client(transfer.provider)

    try:
        verification = await client.verify_transfer(reference)

        # Update transfer status
        status_map = {
            "success": TransferStatus.SUCCESS,
            "failed": TransferStatus.FAILED,
            "pending": TransferStatus.PENDING,
            "processing": TransferStatus.PROCESSING,
            "reversed": TransferStatus.REVERSED,
        }
        transfer.status = status_map.get(
            verification.status.value, TransferStatus.PENDING
        )
        transfer.provider_reference = verification.provider_reference

        await db.commit()

        return {
            "reference": verification.reference,
            "provider_reference": verification.provider_reference,
            "status": verification.status.value,
            "amount": verification.amount,
            "currency": verification.currency,
            "fee": verification.fee,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    finally:
        await client.close()


@router.get("/{reference}")
async def get_transfer(
    reference: str,
    db: AsyncSession = Depends(get_db),
):
    """Get transfer details by reference."""
    result = await db.execute(
        select(Transfer).where(Transfer.reference == reference)
    )
    transfer = result.scalar_one_or_none()

    if not transfer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transfer not found",
        )

    return {
        "id": transfer.id,
        "reference": transfer.reference,
        "provider": transfer.provider,
        "provider_reference": transfer.provider_reference,
        "transfer_type": transfer.transfer_type.value,
        "amount": transfer.amount,
        "currency": transfer.currency,
        "status": transfer.status.value,
        "recipient_account": transfer.recipient_account,
        "recipient_bank_code": transfer.recipient_bank_code,
        "recipient_name": transfer.recipient_name,
        "reason": transfer.reason,
        "fee": transfer.fee,
        "failure_reason": transfer.failure_reason,
        "created_at": transfer.created_at.isoformat(),
        "completed_at": transfer.completed_at.isoformat() if transfer.completed_at else None,
    }


@router.get("/")
async def list_transfers(
    status: Optional[str] = None,
    transfer_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List transfers with optional filters."""
    query = select(Transfer)

    if status:
        query = query.where(Transfer.status == status)
    if transfer_type:
        query = query.where(Transfer.transfer_type == transfer_type)

    query = query.order_by(Transfer.created_at.desc())
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    transfers = result.scalars().all()

    return {
        "items": [
            {
                "id": t.id,
                "reference": t.reference,
                "amount": t.amount,
                "currency": t.currency,
                "status": t.status.value,
                "recipient_name": t.recipient_name,
                "created_at": t.created_at.isoformat(),
            }
            for t in transfers
        ],
        "limit": limit,
        "offset": offset,
    }
