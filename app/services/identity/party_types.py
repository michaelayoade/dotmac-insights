"""Type definitions for party service.

These dataclasses define the contract for party operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional


__all__ = [
    "PartyFilters",
    "PartyCreateData",
    "PartyUpdateData",
    "PartyRoleCreateData",
    "PartyRoleUpdateData",
    "PartyRelationCreateData",
    "PartyRelationUpdateData",
    "EmailData",
    "PhoneData",
    "AddressData",
]


@dataclass
class EmailData:
    """Email contact information."""

    address: str
    label: Optional[str] = None
    is_primary: bool = False
    verified: bool = False


@dataclass
class PhoneData:
    """Phone contact information."""

    number: str
    label: Optional[str] = None
    is_primary: bool = False
    can_sms: bool = False
    can_whatsapp: bool = False


@dataclass
class AddressData:
    """Physical address information."""

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


@dataclass
class PartyFilters:
    """Filters for listing parties."""

    party_type: Optional[str] = None  # person, organization
    status: Optional[str] = None  # active, inactive, blocked
    search: Optional[str] = None
    role: Optional[str] = None  # Filter by role type
    has_role: Optional[str] = None  # Must have this role
    tag: Optional[str] = None


@dataclass
class PartyCreateData:
    """Data for creating a party."""

    type: str  # person, organization
    name: str
    status: str = "active"

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    legal_name: Optional[str] = None
    trading_name: Optional[str] = None

    emails: List[Dict[str, Any]] = field(default_factory=list)
    phones: List[Dict[str, Any]] = field(default_factory=list)
    addresses: List[Dict[str, Any]] = field(default_factory=list)

    external_ids: Dict[str, Any] = field(default_factory=dict)

    avatar_url: Optional[str] = None
    timezone: Optional[str] = None
    locale: Optional[str] = "en"
    tax_id: Optional[str] = None

    tags: List[str] = field(default_factory=list)
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    notes: Optional[str] = None


@dataclass
class PartyUpdateData:
    """Data for updating a party (all fields optional)."""

    status: Optional[str] = None
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    legal_name: Optional[str] = None
    trading_name: Optional[str] = None

    emails: Optional[List[Dict[str, Any]]] = None
    phones: Optional[List[Dict[str, Any]]] = None
    addresses: Optional[List[Dict[str, Any]]] = None

    external_ids: Optional[Dict[str, Any]] = None

    avatar_url: Optional[str] = None
    timezone: Optional[str] = None
    locale: Optional[str] = None
    tax_id: Optional[str] = None

    tags: Optional[List[str]] = None
    custom_fields: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


@dataclass
class PartyRoleCreateData:
    """Data for creating a party role."""

    role: str
    status: str = "active"
    scope_party_id: Optional[int] = None
    owner_party_id: Optional[int] = None

    source: Optional[str] = None
    source_campaign: Optional[str] = None
    qualification: Optional[str] = None
    lead_score: Optional[int] = None

    payment_terms: Optional[str] = None
    credit_limit: Optional[Decimal] = None

    notes: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PartyRoleUpdateData:
    """Data for updating a party role."""

    status: Optional[str] = None
    scope_party_id: Optional[int] = None
    owner_party_id: Optional[int] = None
    until: Optional[datetime] = None

    source: Optional[str] = None
    source_campaign: Optional[str] = None
    qualification: Optional[str] = None
    lead_score: Optional[int] = None

    payment_terms: Optional[str] = None
    credit_limit: Optional[Decimal] = None

    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PartyRelationCreateData:
    """Data for creating a party relation."""

    from_party_id: int
    to_party_id: int
    relation_type: str

    title: Optional[str] = None
    department: Optional[str] = None
    since: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PartyRelationUpdateData:
    """Data for updating a party relation."""

    title: Optional[str] = None
    department: Optional[str] = None
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    is_active: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None
