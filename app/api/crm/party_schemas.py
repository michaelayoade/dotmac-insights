from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict

from pydantic import BaseModel, ConfigDict, Field


class PartyEmail(BaseModel):
    address: str
    label: Optional[str] = None
    is_primary: bool = False
    verified: bool = False


class PartyPhone(BaseModel):
    number: str
    label: Optional[str] = None
    is_primary: bool = False
    can_sms: bool = False
    can_whatsapp: bool = False


class PartyAddress(BaseModel):
    type: Optional[str] = None
    line1: Optional[str] = None
    line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    is_primary: bool = False


class PartyBase(BaseModel):
    type: str = Field(..., pattern="^(person|organization)$")
    status: str = Field("active", pattern="^(active|inactive|blocked)$")
    name: str

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    legal_name: Optional[str] = None
    trading_name: Optional[str] = None

    emails: List[PartyEmail] = Field(default_factory=list)
    phones: List[PartyPhone] = Field(default_factory=list)
    addresses: List[PartyAddress] = Field(default_factory=list)

    external_ids: Dict[str, object] = Field(default_factory=dict)

    avatar_url: Optional[str] = None
    timezone: Optional[str] = None
    locale: Optional[str] = "en"
    tax_id: Optional[str] = None

    tags: List[str] = Field(default_factory=list)
    custom_fields: Dict[str, object] = Field(default_factory=dict)
    notes: Optional[str] = None


class PartyCreate(PartyBase):
    pass


class PartyUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(active|inactive|blocked)$")
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    legal_name: Optional[str] = None
    trading_name: Optional[str] = None
    emails: Optional[List[PartyEmail]] = None
    phones: Optional[List[PartyPhone]] = None
    addresses: Optional[List[PartyAddress]] = None
    external_ids: Optional[Dict[str, object]] = None
    avatar_url: Optional[str] = None
    timezone: Optional[str] = None
    locale: Optional[str] = None
    tax_id: Optional[str] = None
    tags: Optional[List[str]] = None
    custom_fields: Optional[Dict[str, object]] = None
    notes: Optional[str] = None


class PartyRoleCreate(BaseModel):
    role: str
    status: str = Field("active", pattern="^(active|inactive|suspended)$")
    scope_party_id: Optional[int] = None
    owner_party_id: Optional[int] = None


class PartyRoleResponse(BaseModel):
    id: int
    party_id: int
    role: str
    status: str
    scope_party_id: Optional[int] = None
    owner_party_id: Optional[int] = None
    since: Optional[datetime] = None
    until: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PartyMergeRequest(BaseModel):
    duplicate_party_id: int
    reason: str = Field(..., min_length=3, max_length=500)
    deactivate_duplicate: bool = True
    auto_select_primary: bool = True


class PartyMergePreviewRequest(BaseModel):
    duplicate_party_id: int
    auto_select_primary: bool = True


class PartyMergePreviewResponse(BaseModel):
    primary_id: int
    duplicate_id: int
    selected_primary_id: int
    selected_duplicate_id: int
    auto_swapped: bool
    primary_score: int
    duplicate_score: int
    audit_issues: List[str] = Field(default_factory=list)


class PartyResponse(PartyBase):
    id: int
    primary_email: Optional[str] = None
    primary_phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    roles: Optional[List[PartyRoleResponse]] = None

    model_config = ConfigDict(from_attributes=True)


class PartyListResponse(BaseModel):
    data: List[PartyResponse]
    total: int
    limit: int
    offset: int
