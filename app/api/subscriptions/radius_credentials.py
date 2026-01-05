"""RADIUS Credentials API

Endpoints for managing RADIUS credential generation configuration
and regenerating credentials for subscriptions.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional, Self

from app.database import get_db
from app.auth import Require, get_current_principal, Principal
from app.services.subscriptions import (
    RADIUSCredentialService,
    RADIUSCredentialConfigService,
)
from app.services.subscriptions.radius_credentials_types import (
    CredentialGenerationContext,
    RADIUS_CREDENTIAL_CONFIG_SCHEMA,
)
from app.services.errors import NotFoundError, ValidationError

router = APIRouter()


# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class UsernameConfigUpdate(BaseModel):
    """Schema for updating username configuration."""

    format_type: Optional[str] = Field(
        None,
        pattern="^(template|sequential|email|phone|subscription_id)$",
        description="Username format type",
    )
    template: Optional[str] = Field(None, max_length=256)
    domain: Optional[str] = Field(None, max_length=100)
    lowercase: Optional[bool] = None
    strip_special: Optional[bool] = None
    max_length: Optional[int] = Field(None, ge=8, le=128)


class SequentialConfigUpdate(BaseModel):
    """Schema for updating sequential configuration."""

    prefix: Optional[str] = Field(None, max_length=20)
    padding_length: Optional[int] = Field(None, ge=1, le=10)
    start_from: Optional[int] = Field(None, ge=1)


class PasswordConfigUpdate(BaseModel):
    """Schema for updating password configuration."""

    min_length: Optional[int] = Field(None, ge=8, le=32)
    max_length: Optional[int] = Field(None, ge=8, le=64)
    include_lowercase: Optional[bool] = None
    include_uppercase: Optional[bool] = None
    include_digits: Optional[bool] = None
    include_special: Optional[bool] = None
    special_chars: Optional[str] = Field(None, max_length=20)
    exclude_ambiguous: Optional[bool] = None

    @model_validator(mode="after")
    def validate_lengths(self) -> Self:
        """Validate min_length <= max_length when both provided."""
        if self.min_length is not None and self.max_length is not None:
            if self.min_length > self.max_length:
                raise ValueError("min_length cannot exceed max_length")
        return self


class ConfigUpdateSchema(BaseModel):
    """Schema for updating credential configuration."""

    enabled: Optional[bool] = None
    auto_generate_on_create: Optional[bool] = None
    notify_on_regenerate: Optional[bool] = None
    username: Optional[UsernameConfigUpdate] = None
    sequential: Optional[SequentialConfigUpdate] = None
    password: Optional[PasswordConfigUpdate] = None


class RegenerateSchema(BaseModel):
    """Schema for regenerating credentials."""

    regenerate_username: bool = Field(True, description="Regenerate username")
    regenerate_password: bool = Field(True, description="Regenerate password")


class BulkRegenerateSchema(BaseModel):
    """Schema for bulk credential regeneration."""

    subscription_ids: List[int] = Field(
        ..., min_length=1, max_length=100, description="Subscription IDs"
    )
    regenerate_username: bool = Field(True, description="Regenerate usernames")
    regenerate_password: bool = Field(True, description="Regenerate passwords")


class PreviewSchema(BaseModel):
    """Schema for previewing credential generation."""

    party_id: int = Field(..., description="Party ID")
    subscription_id: int = Field(0, description="Subscription ID (use 0 for new)")
    tariff_id: Optional[int] = Field(None, description="Tariff ID")


class SequenceResetSchema(BaseModel):
    """Schema for resetting sequential counter."""

    new_value: int = Field(0, ge=0, description="New counter value")
    new_prefix: Optional[str] = Field(None, max_length=20, description="New prefix")
    new_padding_length: Optional[int] = Field(
        None, ge=1, le=10, description="New padding length"
    )


# =============================================================================
# CONFIGURATION ENDPOINTS
# =============================================================================

@router.get("/config", dependencies=[Depends(Require("subscriptions:read"))])
async def get_config(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get RADIUS credential generation configuration.
    """
    service = RADIUSCredentialConfigService(db, principal)
    config = service.get_config()
    return config.to_dict()


@router.put("/config", dependencies=[Depends(Require("subscriptions:admin"))])
async def update_config(
    data: ConfigUpdateSchema,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Update RADIUS credential generation configuration.
    """
    service = RADIUSCredentialConfigService(db, principal)
    updates = data.model_dump(exclude_unset=True)
    config = service.update_config(updates)
    db.commit()
    return config.to_dict()


@router.post("/config/reset", dependencies=[Depends(Require("subscriptions:admin"))])
async def reset_config(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Reset configuration to default values.
    """
    service = RADIUSCredentialConfigService(db, principal)
    config = service.reset_to_defaults()
    db.commit()
    return config.to_dict()


@router.get("/config/schema", dependencies=[Depends(Require("subscriptions:read"))])
async def get_config_schema(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get configuration schema for UI rendering.
    """
    return RADIUS_CREDENTIAL_CONFIG_SCHEMA


# =============================================================================
# CREDENTIAL GENERATION ENDPOINTS
# =============================================================================

@router.post("/preview", dependencies=[Depends(Require("subscriptions:read"))])
async def preview_generation(
    data: PreviewSchema,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Preview what credentials would be generated for a party.
    """
    service = RADIUSCredentialService(db, principal)

    context = service.build_context(
        subscription_id=data.subscription_id,
        party_id=data.party_id,
        tariff_id=data.tariff_id,
    )

    return service.preview_generation(context)


@router.post("/{subscription_id}/regenerate", dependencies=[Depends(Require("subscriptions:update"))])
async def regenerate_credentials(
    subscription_id: int = Path(..., description="Subscription ID"),
    data: RegenerateSchema = RegenerateSchema(),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Regenerate RADIUS credentials for a subscription.
    """
    service = RADIUSCredentialService(db, principal)

    try:
        credentials = service.regenerate_credentials(
            subscription_id,
            regenerate_username=data.regenerate_username,
            regenerate_password=data.regenerate_password,
        )
        db.commit()

        return {
            "subscription_id": subscription_id,
            "username": credentials.username if data.regenerate_username else None,
            "password": credentials.password if data.regenerate_password else None,
            "generated_at": credentials.generated_at.isoformat(),
            "format_used": credentials.format_used,
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bulk/regenerate", dependencies=[Depends(Require("subscriptions:update"))])
async def bulk_regenerate(
    data: BulkRegenerateSchema,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Bulk regenerate credentials for multiple subscriptions.
    """
    service = RADIUSCredentialService(db, principal)

    results = service.regenerate_bulk(
        data.subscription_ids,
        regenerate_username=data.regenerate_username,
        regenerate_password=data.regenerate_password,
    )
    db.commit()

    return results


@router.get("/validate-username", dependencies=[Depends(Require("subscriptions:read"))])
async def validate_username(
    username: str = Query(..., min_length=1, max_length=100, description="Username to check"),
    exclude_subscription_id: Optional[int] = Query(None, description="Exclude subscription"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Check if a username is available (unique).
    """
    service = RADIUSCredentialService(db, principal)

    is_unique = service.validate_username_unique(
        username,
        exclude_subscription_id=exclude_subscription_id,
    )

    return {
        "username": username,
        "is_available": is_unique,
    }


@router.get("/format-types", dependencies=[Depends(Require("subscriptions:read"))])
async def get_format_types(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> List[Dict[str, str]]:
    """
    Get available username format types.
    """
    service = RADIUSCredentialService(db, principal)
    return service.get_format_types()


# =============================================================================
# SEQUENCE MANAGEMENT ENDPOINTS
# =============================================================================

@router.get("/sequence/current", dependencies=[Depends(Require("subscriptions:read"))])
async def get_current_sequence(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Get current sequential counter state.
    """
    service = RADIUSCredentialService(db, principal)
    return service.get_current_sequence()


@router.post("/sequence/reset", dependencies=[Depends(Require("subscriptions:admin"))])
async def reset_sequence(
    data: SequenceResetSchema,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Reset the sequential username counter.

    WARNING: This may cause username collisions if not used carefully.
    """
    service = RADIUSCredentialService(db, principal)

    result = service.reset_sequence(
        new_value=data.new_value,
        new_prefix=data.new_prefix,
        new_padding_length=data.new_padding_length,
    )
    db.commit()

    return result
