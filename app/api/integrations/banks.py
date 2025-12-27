"""
Bank API endpoints.

Provides bank listing and account resolution (NUBAN validation).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field

from app.integrations.payments.providers.paystack import PaystackClient
from app.integrations.payments.providers.flutterwave import FlutterwaveClient
from app.integrations.payments.config import get_payment_settings

router = APIRouter(prefix="/banks", tags=["banks"])


# =============================================================================
# Schemas
# =============================================================================

class BankSchema(BaseModel):
    """Bank information."""
    code: str
    name: str
    slug: str
    is_active: bool
    country: str
    currency: str


class ResolveAccountRequest(BaseModel):
    """Request to resolve a bank account."""
    account_number: str = Field(..., min_length=10, max_length=10)
    bank_code: str


class ResolveAccountResponse(BaseModel):
    """Resolved account information."""
    account_number: str
    account_name: str
    bank_code: str
    bank_name: Optional[str] = None


# =============================================================================
# Helper Functions
# =============================================================================

def get_client(provider: Optional[str] = None):
    """Get payment client.

    Raises:
        HTTPException: If the payment provider is not configured.
    """
    settings = get_payment_settings()
    provider = provider or settings.default_payment_provider

    try:
        if provider == "flutterwave":
            return FlutterwaveClient()
        return PaystackClient()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Payment provider not configured: {str(e)}"
        )


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/", response_model=list[BankSchema])
async def list_banks(
    country: str = Query("NG", description="Country code (e.g., NG, GH, KE)"),
    provider: Optional[str] = Query(None, description="Provider to use (paystack/flutterwave)"),
):
    """
    Get list of supported banks.

    Returns all banks supported for transfers in the specified country.
    Defaults to Nigerian banks (NG).
    """
    client = get_client(provider)

    try:
        banks = await client.get_banks(country)

        return [
            BankSchema(
                code=bank.code,
                name=bank.name,
                slug=bank.slug,
                is_active=bank.is_active,
                country=bank.country,
                currency=bank.currency,
            )
            for bank in banks
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch banks: {str(e)}",
        )
    finally:
        await client.close()


@router.post("/resolve", response_model=ResolveAccountResponse)
async def resolve_account(
    request: ResolveAccountRequest,
    provider: Optional[str] = Query(None, description="Provider to use"),
):
    """
    Resolve/verify a bank account (NUBAN validation).

    Validates the account number against the bank and returns
    the account holder's name. Use this before initiating transfers
    to ensure the account details are correct.
    """
    client = get_client(provider)

    try:
        result = await client.resolve_account(
            account_number=request.account_number,
            bank_code=request.bank_code,
        )

        return ResolveAccountResponse(
            account_number=result.account_number,
            account_name=result.account_name,
            bank_code=result.bank_code,
            bank_name=result.bank_name,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    finally:
        await client.close()


@router.get("/search")
async def search_banks(
    q: str = Query(..., min_length=2, description="Search query"),
    country: str = Query("NG", description="Country code"),
    provider: Optional[str] = Query(None, description="Provider to use"),
):
    """
    Search banks by name.

    Useful for autocomplete in bank selection dropdowns.
    """
    client = get_client(provider)

    try:
        banks = await client.get_banks(country)

        # Filter by search query (case-insensitive)
        query = q.lower()
        matches = [
            BankSchema(
                code=bank.code,
                name=bank.name,
                slug=bank.slug,
                is_active=bank.is_active,
                country=bank.country,
                currency=bank.currency,
            )
            for bank in banks
            if query in bank.name.lower() or query in bank.slug.lower()
        ]

        return {"results": matches, "count": len(matches)}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search banks: {str(e)}",
        )
    finally:
        await client.close()


@router.get("/{bank_code}")
async def get_bank(
    bank_code: str,
    country: str = Query("NG", description="Country code"),
    provider: Optional[str] = Query(None, description="Provider to use"),
):
    """
    Get bank details by code.
    """
    client = get_client(provider)

    try:
        banks = await client.get_banks(country)

        for bank in banks:
            if bank.code == bank_code:
                return BankSchema(
                    code=bank.code,
                    name=bank.name,
                    slug=bank.slug,
                    is_active=bank.is_active,
                    country=bank.country,
                    currency=bank.currency,
                )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bank not found",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch bank: {str(e)}",
        )
    finally:
        await client.close()
