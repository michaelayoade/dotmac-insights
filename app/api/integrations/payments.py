"""
Payment API endpoints.

Handles payment initialization, verification, and management.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import Require
from app.models.gateway_transaction import (
    GatewayTransaction,
    GatewayProvider,
    GatewayTransactionType,
    GatewayTransactionStatus,
)
from app.integrations.payments.providers.paystack import PaystackClient
from app.integrations.payments.providers.flutterwave import FlutterwaveClient
from app.integrations.payments.base import InitializePaymentRequest
from app.integrations.payments.enums import PaymentProvider
from app.integrations.payments.config import get_payment_settings

router = APIRouter(prefix="/payments", tags=["payments"])


# =============================================================================
# Schemas
# =============================================================================

class InitializePaymentSchema(BaseModel):
    """Request to initialize a payment."""
    amount: Decimal = Field(..., gt=0, description="Amount in Naira")
    email: str = Field(..., description="Customer email address")
    currency: str = "NGN"
    callback_url: Optional[str] = None
    reference: Optional[str] = None  # Auto-generated if not provided
    channels: Optional[List[str]] = None
    invoice_id: Optional[int] = None
    customer_id: Optional[int] = None
    metadata: Optional[dict] = None
    provider: Optional[str] = None  # paystack or flutterwave


class InitializePaymentResponse(BaseModel):
    """Response from payment initialization."""
    authorization_url: str
    access_code: str
    reference: str
    provider: str


class VerifyPaymentResponse(BaseModel):
    """Payment verification response."""
    reference: str
    provider_reference: str
    status: str
    amount: Decimal
    currency: str
    paid_at: Optional[str] = None
    channel: Optional[str] = None
    fees: Decimal = Decimal("0")
    customer_email: Optional[str] = None


class PaymentListItem(BaseModel):
    """Payment list item."""
    id: int
    reference: str
    provider: str
    amount: Decimal
    currency: str
    status: str
    customer_email: Optional[str] = None
    created_at: str

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Helper Functions
# =============================================================================

def get_payment_client(provider: Optional[str] = None):
    """Get appropriate payment gateway client."""
    settings = get_payment_settings()
    provider = provider or settings.default_payment_provider

    if provider == "flutterwave":
        return FlutterwaveClient()
    return PaystackClient()  # Default


def generate_reference() -> str:
    """Generate unique payment reference."""
    return f"PAY-{uuid.uuid4().hex[:12].upper()}"


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/initialize", response_model=InitializePaymentResponse, dependencies=[Depends(Require("payments:write"))])
async def initialize_payment(
    request: InitializePaymentSchema,
    db: AsyncSession = Depends(get_db),
):
    """
    Initialize a payment transaction.

    Returns an authorization URL to redirect the customer to complete payment.
    """
    reference = request.reference or generate_reference()

    # Check for duplicate reference
    existing = await db.execute(
        select(GatewayTransaction).where(GatewayTransaction.reference == reference)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payment reference already exists",
        )

    # Get payment client
    client = get_payment_client(request.provider)

    try:
        # Initialize with provider
        payment_request = InitializePaymentRequest(
            amount=request.amount,
            currency=request.currency,
            email=request.email,
            reference=reference,
            callback_url=request.callback_url,
            metadata=request.metadata,
            channels=request.channels,
            invoice_id=request.invoice_id,
            customer_id=request.customer_id,
        )

        result = await client.initialize_payment(payment_request)

        # Create transaction record
        provider_enum = (
            GatewayProvider.FLUTTERWAVE
            if request.provider == "flutterwave"
            else GatewayProvider.PAYSTACK
        )

        transaction = GatewayTransaction(
            reference=reference,
            provider=provider_enum,
            transaction_type=GatewayTransactionType.PAYMENT,
            amount=request.amount,
            currency=request.currency,
            status=GatewayTransactionStatus.PENDING,
            customer_email=request.email,
            customer_id=request.customer_id,
            invoice_id=request.invoice_id,
            authorization_url=result.authorization_url,
            access_code=result.access_code,
            callback_url=request.callback_url,
            extra_data=request.metadata,
        )
        db.add(transaction)
        await db.commit()

        return InitializePaymentResponse(
            authorization_url=result.authorization_url,
            access_code=result.access_code,
            reference=result.reference,
            provider=result.provider.value,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    finally:
        await client.close()


@router.get("/verify/{reference}", response_model=VerifyPaymentResponse, dependencies=[Depends(Require("payments:read"))])
async def verify_payment(
    reference: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify a payment by reference.

    Checks the payment status with the provider and updates local record.
    """
    # Get transaction
    result = await db.execute(
        select(GatewayTransaction).where(GatewayTransaction.reference == reference)
    )
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    # Get appropriate client
    provider = "flutterwave" if transaction.provider == GatewayProvider.FLUTTERWAVE else "paystack"
    client = get_payment_client(provider)

    try:
        verification = await client.verify_payment(reference)

        # Update transaction
        status_map = {
            "success": GatewayTransactionStatus.SUCCESS,
            "failed": GatewayTransactionStatus.FAILED,
            "pending": GatewayTransactionStatus.PENDING,
            "abandoned": GatewayTransactionStatus.ABANDONED,
        }
        transaction.status = status_map.get(
            verification.status.value, GatewayTransactionStatus.PENDING
        )
        transaction.provider_reference = verification.provider_reference
        transaction.fees = verification.fees
        transaction.completed_at = verification.paid_at

        if verification.authorization:
            transaction.extra_data = transaction.extra_data or {}
            transaction.extra_data["authorization"] = verification.authorization

        await db.commit()

        return VerifyPaymentResponse(
            reference=verification.reference,
            provider_reference=verification.provider_reference,
            status=verification.status.value,
            amount=verification.amount,
            currency=verification.currency,
            paid_at=verification.paid_at.isoformat() if verification.paid_at else None,
            channel=verification.channel,
            fees=verification.fees,
            customer_email=verification.customer_email,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    finally:
        await client.close()


@router.get("/{reference}", dependencies=[Depends(Require("payments:read"))])
async def get_payment(
    reference: str,
    db: AsyncSession = Depends(get_db),
):
    """Get payment details by reference."""
    result = await db.execute(
        select(GatewayTransaction).where(GatewayTransaction.reference == reference)
    )
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    return {
        "id": transaction.id,
        "reference": transaction.reference,
        "provider": transaction.provider.value,
        "provider_reference": transaction.provider_reference,
        "amount": transaction.amount,
        "currency": transaction.currency,
        "status": transaction.status.value,
        "customer_email": transaction.customer_email,
        "fees": transaction.fees,
        "paid_at": transaction.completed_at.isoformat() if transaction.completed_at else None,
        "created_at": transaction.created_at.isoformat(),
        "extra_data": transaction.extra_data,
    }


@router.get("/", dependencies=[Depends(Require("payments:read"))])
async def list_payments(
    status_filter: Optional[str] = Query(None, alias="status"),
    provider_filter: Optional[str] = Query(None, alias="provider"),
    customer_id: Optional[int] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List payment transactions with optional filters."""
    query = select(GatewayTransaction).where(
        GatewayTransaction.transaction_type == GatewayTransactionType.PAYMENT
    )

    if status_filter:
        try:
            status_enum = GatewayTransactionStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status filter",
            )
        query = query.where(GatewayTransaction.status == status_enum)
    if provider_filter:
        try:
            provider_enum = GatewayProvider(provider_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid provider filter",
            )
        query = query.where(GatewayTransaction.provider == provider_enum)
    if customer_id:
        query = query.where(GatewayTransaction.customer_id == customer_id)

    query = query.order_by(GatewayTransaction.created_at.desc())
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    transactions = result.scalars().all()

    return {
        "items": [
            {
                "id": t.id,
                "reference": t.reference,
                "provider": t.provider.value,
                "amount": t.amount,
                "currency": t.currency,
                "status": t.status.value,
                "customer_email": t.customer_email,
                "created_at": t.created_at.isoformat(),
            }
            for t in transactions
        ],
        "limit": limit,
        "offset": offset,
    }


@router.post("/{reference}/refund", dependencies=[Depends(Require("payments:write"))])
async def refund_payment(
    reference: str,
    amount: Optional[Decimal] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Refund a payment (full or partial).

    If amount is not provided, full refund is processed.
    """
    result = await db.execute(
        select(GatewayTransaction).where(GatewayTransaction.reference == reference)
    )
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    if transaction.status != GatewayTransactionStatus.SUCCESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only successful payments can be refunded",
        )

    provider = "flutterwave" if transaction.provider == GatewayProvider.FLUTTERWAVE else "paystack"
    client = get_payment_client(provider)

    try:
        refund_result = await client.refund_payment(reference, amount)

        transaction.status = GatewayTransactionStatus.REFUNDED
        transaction.extra_data = transaction.extra_data or {}
        transaction.extra_data["refund"] = refund_result

        await db.commit()

        return {
            "status": "success",
            "message": "Refund processed",
            "refund": refund_result,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    finally:
        await client.close()
