"""
Open Banking API endpoints.

Handles bank account linking, transaction syncing, and identity verification
via Mono and Okra.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import Require
from app.models.open_banking import (
    OpenBankingConnection,
    OpenBankingProvider as OBProvider,
    ConnectionStatus,
)
from app.integrations.payments.openbanking.mono import MonoClient
from app.integrations.payments.openbanking.okra import OkraClient
from app.integrations.payments.config import get_payment_settings

router = APIRouter(prefix="/openbanking", tags=["openbanking"])


# =============================================================================
# Schemas
# =============================================================================

class WidgetConfigRequest(BaseModel):
    """Request for widget configuration."""
    customer_id: str
    redirect_url: str
    provider: Optional[str] = None  # mono or okra
    metadata: Optional[dict] = None


class WidgetConfigResponse(BaseModel):
    """Widget configuration response."""
    public_key: str
    provider: str
    customer_id: str
    redirect_url: str
    widget_url: str
    metadata: Optional[dict] = None


class LinkAccountRequest(BaseModel):
    """Request to complete account linking."""
    code: str  # Authorization code from widget callback
    provider: str
    customer_id: int
    customer_email: Optional[str] = None


class LinkedAccountResponse(BaseModel):
    """Linked account details."""
    id: int
    provider: str
    provider_account_id: str
    account_number: str
    bank_name: str
    account_name: str
    account_type: str
    currency: str
    balance: Optional[Decimal] = None
    status: str


class TransactionSchema(BaseModel):
    """Bank transaction."""
    transaction_id: str
    date: datetime
    narration: str
    type: str
    amount: Decimal
    balance: Optional[Decimal] = None
    category: Optional[str] = None


class IdentityResponse(BaseModel):
    """Identity information."""
    bvn: Optional[str] = None
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None


# =============================================================================
# Helper Functions
# =============================================================================

def get_openbanking_client(provider: Optional[str] = None):
    """Get appropriate open banking client."""
    settings = get_payment_settings()
    provider = provider or settings.default_open_banking_provider

    if provider == "okra":
        return OkraClient()
    return MonoClient()


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/widget-config", response_model=WidgetConfigResponse, dependencies=[Depends(Require("openbanking:write"))])
async def get_widget_config(request: WidgetConfigRequest):
    """
    Get configuration for launching the account linking widget.

    Returns the public key and configuration needed to launch
    Mono Connect or Okra widget in the frontend.
    """
    client = get_openbanking_client(request.provider)

    try:
        config = await client.get_widget_token(
            customer_id=request.customer_id,
            redirect_url=request.redirect_url,
            metadata=request.metadata,
        )

        return WidgetConfigResponse(
            public_key=config["public_key"],
            provider=client.provider.value,
            customer_id=request.customer_id,
            redirect_url=request.redirect_url,
            widget_url=config["widget_url"],
            metadata=config.get("metadata"),
        )

    finally:
        await client.close()


@router.post("/link-account", response_model=LinkedAccountResponse, dependencies=[Depends(Require("openbanking:write"))])
async def link_account(
    request: LinkAccountRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Complete account linking after widget authorization.

    Exchange the authorization code from the widget callback
    for a permanent account connection.
    """
    client = get_openbanking_client(request.provider)

    try:
        # Exchange code for account ID
        provider_account_id = await client.exchange_code(request.code)

        # Get account details
        account = await client.get_account_details(provider_account_id)

        # Map provider enum
        provider_enum = (
            OBProvider.OKRA if request.provider == "okra" else OBProvider.MONO
        )

        # Check for existing connection
        existing = await db.execute(
            select(OpenBankingConnection).where(
                OpenBankingConnection.provider == provider_enum,
                OpenBankingConnection.account_id == provider_account_id,
            )
        )
        connection = existing.scalar_one_or_none()

        if connection:
            # Update existing connection
            connection.status = ConnectionStatus.CONNECTED
            connection.cached_balance = account.balance
            connection.balance_updated_at = datetime.utcnow()
        else:
            # Create new connection
            connection = OpenBankingConnection(
                provider=provider_enum,
                account_id=provider_account_id,
                customer_id=request.customer_id,
                email=request.customer_email,
                account_number=account.account_number,
                bank_code=account.bank_code,
                bank_name=account.bank_name,
                account_name=account.account_name,
                account_type=account.account_type,
                currency=account.currency,
                cached_balance=account.balance,
                balance_updated_at=datetime.utcnow() if account.balance else None,
                bvn=account.bvn,
                status=ConnectionStatus.CONNECTED,
            )
            db.add(connection)

        await db.commit()
        await db.refresh(connection)

        return LinkedAccountResponse(
            id=connection.id,
            provider=connection.provider.value,
            provider_account_id=connection.account_id,
            account_number=connection.account_number,
            bank_name=connection.bank_name,
            account_name=connection.account_name,
            account_type=connection.account_type or "",
            currency=connection.currency,
            balance=connection.cached_balance,
            status=connection.status.value,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    finally:
        await client.close()


@router.get("/accounts", response_model=List[LinkedAccountResponse], dependencies=[Depends(Require("openbanking:read"))])
async def list_linked_accounts(
    customer_id: Optional[int] = None,
    provider: Optional[str] = None,
    connection_status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List linked bank accounts."""
    query = select(OpenBankingConnection)

    if customer_id:
        query = query.where(OpenBankingConnection.customer_id == customer_id)
    if provider:
        try:
            provider_enum = OBProvider(provider)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid provider filter",
            )
        query = query.where(OpenBankingConnection.provider == provider_enum)
    if connection_status:
        try:
            status_enum = ConnectionStatus(connection_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status filter",
            )
        query = query.where(OpenBankingConnection.status == status_enum)

    query = query.order_by(OpenBankingConnection.created_at.desc())

    result = await db.execute(query)
    connections = result.scalars().all()

    return [
        LinkedAccountResponse(
            id=c.id,
            provider=c.provider.value,
            provider_account_id=c.account_id,
            account_number=c.account_number,
            bank_name=c.bank_name,
            account_name=c.account_name,
            account_type=c.account_type or "",
            currency=c.currency,
            balance=c.cached_balance,
            status=c.status.value,
        )
        for c in connections
    ]


@router.get("/accounts/{account_id}", dependencies=[Depends(Require("openbanking:read"))])
async def get_linked_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get linked account details."""
    result = await db.execute(
        select(OpenBankingConnection).where(OpenBankingConnection.id == account_id)
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked account not found",
        )

    return {
        "id": connection.id,
        "provider": connection.provider.value,
        "provider_account_id": connection.account_id,
        "customer_id": connection.customer_id,
        "account_number": connection.account_number,
        "bank_code": connection.bank_code,
        "bank_name": connection.bank_name,
        "account_name": connection.account_name,
        "account_type": connection.account_type,
        "currency": connection.currency,
        "balance": connection.cached_balance,
        "balance_updated_at": connection.balance_updated_at.isoformat() if connection.balance_updated_at else None,
        "status": connection.status.value,
        "created_at": connection.created_at.isoformat(),
        "last_synced_at": connection.last_synced_at.isoformat() if connection.last_synced_at else None,
    }


@router.get("/accounts/{account_id}/balance", dependencies=[Depends(Require("openbanking:read"))])
async def get_account_balance(
    account_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get current account balance (fetches from provider)."""
    result = await db.execute(
        select(OpenBankingConnection).where(OpenBankingConnection.id == account_id)
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked account not found",
        )

    client = get_openbanking_client(connection.provider.value)

    try:
        balance = await client.get_account_balance(connection.account_id)

        # Update stored balance
        connection.cached_balance = balance
        connection.balance_updated_at = datetime.utcnow()
        await db.commit()

        return {
            "account_id": account_id,
            "balance": balance,
            "currency": connection.currency,
            "updated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    finally:
        await client.close()


@router.get("/accounts/{account_id}/transactions", response_model=List[TransactionSchema], dependencies=[Depends(Require("openbanking:read"))])
async def get_account_transactions(
    account_id: int,
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get account transactions."""
    result = await db.execute(
        select(OpenBankingConnection).where(OpenBankingConnection.id == account_id)
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked account not found",
        )

    client = get_openbanking_client(connection.provider.value)

    try:
        transactions = await client.get_transactions(
            account_id=connection.account_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

        # Update last synced timestamp
        connection.last_synced_at = datetime.utcnow()
        await db.commit()

        return [
            TransactionSchema(
                transaction_id=t.transaction_id,
                date=t.date,
                narration=t.narration,
                type=t.type,
                amount=t.amount,
                balance=t.balance,
                category=t.category,
            )
            for t in transactions
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    finally:
        await client.close()


@router.get("/accounts/{account_id}/identity", response_model=IdentityResponse, dependencies=[Depends(Require("openbanking:read"))])
async def get_account_identity(
    account_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get customer identity from linked account."""
    result = await db.execute(
        select(OpenBankingConnection).where(OpenBankingConnection.id == account_id)
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked account not found",
        )

    client = get_openbanking_client(connection.provider.value)

    try:
        identity = await client.get_identity(connection.account_id)

        # Update BVN if available
        if identity.bvn and not connection.bvn:
            connection.bvn = identity.bvn
            await db.commit()

        return IdentityResponse(
            bvn=identity.bvn,
            full_name=identity.full_name,
            first_name=identity.first_name,
            last_name=identity.last_name,
            email=identity.email,
            phone=identity.phone,
            date_of_birth=identity.date_of_birth.isoformat() if identity.date_of_birth else None,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    finally:
        await client.close()


@router.post("/accounts/{account_id}/reauthorize", dependencies=[Depends(Require("openbanking:write"))])
async def reauthorize_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get reauthorization URL for expired connection."""
    result = await db.execute(
        select(OpenBankingConnection).where(OpenBankingConnection.id == account_id)
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked account not found",
        )

    client = get_openbanking_client(connection.provider.value)

    try:
        reauth_url = await client.reauthorize(connection.account_id)

        return {
            "account_id": account_id,
            "reauthorization_url": reauth_url,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    finally:
        await client.close()


@router.delete("/accounts/{account_id}", dependencies=[Depends(Require("openbanking:write"))])
async def unlink_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Unlink a connected bank account."""
    result = await db.execute(
        select(OpenBankingConnection).where(OpenBankingConnection.id == account_id)
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked account not found",
        )

    client = get_openbanking_client(connection.provider.value)

    try:
        # Unlink from provider
        await client.unlink_account(connection.account_id)

        # Update local status
        connection.status = ConnectionStatus.DISCONNECTED
        await db.commit()

        return {"status": "success", "message": "Account unlinked"}

    except Exception as e:
        # Even if provider fails, mark as disconnected locally
        connection.status = ConnectionStatus.DISCONNECTED
        await db.commit()

        return {"status": "success", "message": "Account unlinked locally"}
    finally:
        await client.close()
