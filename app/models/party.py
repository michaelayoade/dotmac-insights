from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Identity,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from app.models.customer_usage import CustomerUsage  # pragma: no cover


class PartyType(enum.Enum):
    PERSON = "person"
    ORGANIZATION = "organization"


class PartyStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"


class PartyRoleStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class MembershipStatus(enum.Enum):
    ACTIVE = "active"
    INVITED = "invited"
    SUSPENDED = "suspended"
    REMOVED = "removed"


class AccessRole(enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    MEMBER = "member"
    SUPPORT = "support"
    VIEWER = "viewer"


class CredentialType(enum.Enum):
    PASSWORD = "password"
    OAUTH = "oauth"
    SSO = "sso"
    API_KEY = "api_key"
    MAGIC_LINK = "magic_link"


class CredentialStatus(enum.Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    EXPIRED = "expired"
    LOCKED = "locked"


class RefPartyRoleType(Base):
    __tablename__ = "ref_party_role_types"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class RefRelationType(Base):
    __tablename__ = "ref_relation_types"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    from_type: Mapped[str] = mapped_column(Text, nullable=False)
    to_type: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class Party(Base):
    __tablename__ = "parties"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")

    name: Mapped[Optional[str]] = mapped_column(Text)
    first_name: Mapped[Optional[str]] = mapped_column(Text)
    last_name: Mapped[Optional[str]] = mapped_column(Text)
    legal_name: Mapped[Optional[str]] = mapped_column(Text)
    trading_name: Mapped[Optional[str]] = mapped_column(Text)

    primary_email: Mapped[Optional[str]] = mapped_column(Text)
    primary_phone: Mapped[Optional[str]] = mapped_column(Text)
    emails: Mapped[List[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    phones: Mapped[List[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    addresses: Mapped[List[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    external_ids: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    avatar_url: Mapped[Optional[str]] = mapped_column(Text)
    timezone: Mapped[Optional[str]] = mapped_column(Text)
    locale: Mapped[Optional[str]] = mapped_column(Text, server_default="en")
    tax_id: Mapped[Optional[str]] = mapped_column(Text)

    # Social media profiles
    linkedin_url: Mapped[Optional[str]] = mapped_column(Text)
    twitter_handle: Mapped[Optional[str]] = mapped_column(Text)
    facebook_url: Mapped[Optional[str]] = mapped_column(Text)
    instagram_handle: Mapped[Optional[str]] = mapped_column(Text)
    website_url: Mapped[Optional[str]] = mapped_column(Text)

    # Communication preferences
    preferred_channel: Mapped[Optional[str]] = mapped_column(Text)  # email, sms, whatsapp, phone
    do_not_contact: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    contact_frequency_limit: Mapped[Optional[int]] = mapped_column()  # max contacts per week

    # Engagement tracking
    engagement_score: Mapped[Optional[int]] = mapped_column()  # 0-100 computed score
    last_engagement_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_contacted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    tags: Mapped[List[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    custom_fields: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        server_default=func.now(),
    )

    roles: Mapped[List["PartyRole"]] = relationship(
        back_populates="party",
        foreign_keys="[PartyRole.party_id]",
    )
    external_mappings: Mapped[List["PartyExternalId"]] = relationship(back_populates="party")
    credentials: Mapped[List["Credential"]] = relationship(back_populates="party")
    memberships: Mapped[List["Membership"]] = relationship(
        back_populates="person",
        foreign_keys="[Membership.person_party_id]",
    )
    usage_records: Mapped[List["CustomerUsage"]] = relationship(back_populates="party")

    __table_args__ = (
        Index(
            "uq_parties_primary_email",
            "primary_email",
            unique=True,
            postgresql_where=text("primary_email IS NOT NULL"),
        ),
        Index(
            "uq_parties_primary_phone",
            "primary_phone",
            unique=True,
            postgresql_where=text("primary_phone IS NOT NULL"),
        ),
        Index("ix_parties_type_status", "type", "status"),
        Index("ix_parties_name", "name"),
    )


class PartyRole(Base):
    __tablename__ = "party_roles"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parties.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        Text,
        ForeignKey("ref_party_role_types.code"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="active",
    )
    scope_party_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("parties.id", ondelete="SET NULL"),
    )

    since: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        server_default=func.now(),
    )
    until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    source: Mapped[Optional[str]] = mapped_column(Text)
    source_campaign: Mapped[Optional[str]] = mapped_column(Text)
    qualification: Mapped[Optional[str]] = mapped_column(Text)
    lead_score: Mapped[Optional[int]]

    owner_party_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("parties.id", ondelete="SET NULL"),
    )

    payment_terms: Mapped[Optional[str]] = mapped_column(Text)
    credit_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))

    notes: Mapped[Optional[str]] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        server_default=func.now(),
    )

    party: Mapped["Party"] = relationship(foreign_keys=[party_id], back_populates="roles")
    owner: Mapped[Optional["Party"]] = relationship(foreign_keys=[owner_party_id])

    __table_args__ = (
        Index(
            "uq_party_roles_active",
            "party_id",
            "role",
            "scope_party_id",
            unique=True,
            postgresql_where=text("until IS NULL"),
        ),
        Index("ix_party_roles_role_status", "role", "status"),
        Index("ix_party_roles_party", "party_id"),
    )



class PartyRelation(Base):
    __tablename__ = "party_relations"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    from_party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parties.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parties.id", ondelete="CASCADE"),
        nullable=False,
    )
    relation_type: Mapped[str] = mapped_column(
        Text,
        ForeignKey("ref_relation_types.code"),
        nullable=False,
    )

    title: Mapped[Optional[str]] = mapped_column(Text)
    department: Mapped[Optional[str]] = mapped_column(Text)
    since: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_party_relations_from_to", "from_party_id", "to_party_id"),
        Index(
            "uq_party_relations_active",
            "from_party_id",
            "to_party_id",
            "relation_type",
            unique=True,
            postgresql_where=text("until IS NULL"),
        ),
        Index("ix_party_relations_to", "to_party_id"),
    )


class CustomerAccount(Base):
    __tablename__ = "customer_accounts"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parties.id", ondelete="RESTRICT"),
        nullable=False,
    )

    account_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    tier: Mapped[str] = mapped_column(Text, nullable=False, server_default="standard")
    parent_account_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("customer_accounts.id", ondelete="SET NULL"),
    )
    account_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="direct")

    billing_type: Mapped[Optional[str]] = mapped_column(Text)
    billing_email: Mapped[Optional[str]] = mapped_column(Text)
    billing_cycle: Mapped[Optional[str]] = mapped_column(Text)
    payment_terms: Mapped[Optional[str]] = mapped_column(Text)
    credit_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default="NGN")

    mrr: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    total_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    outstanding_balance: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))

    external_ids: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        server_default=func.now(),
    )
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    suspended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    party: Mapped["Party"] = relationship()
    contacts: Mapped[List["CustomerAccountContact"]] = relationship(back_populates="account")
    team: Mapped[List["CustomerAccountTeam"]] = relationship(back_populates="account")
    resellers: Mapped[List["CustomerAccountReseller"]] = relationship(back_populates="account")

    __table_args__ = (
        Index("ix_customer_accounts_party", "party_id"),
        Index("ix_customer_accounts_status", "status"),
        Index("ix_customer_accounts_parent", "parent_account_id"),
    )


class CustomerAccountContact(Base):
    __tablename__ = "customer_account_contacts"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("customer_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    person_party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parties.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    receives_invoices: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    receives_notifications: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    can_manage: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    since: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        server_default=func.now(),
    )
    until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    account: Mapped["CustomerAccount"] = relationship(back_populates="contacts")
    person: Mapped["Party"] = relationship()

    __table_args__ = (
        Index("ix_customer_account_contacts_account_role", "account_id", "role"),
        Index("ix_customer_account_contacts_person", "person_party_id"),
        Index(
            "uq_customer_account_contacts_primary",
            "account_id",
            unique=True,
            postgresql_where=text("is_primary = true AND until IS NULL"),
        ),
    )


class CustomerAccountTeam(Base):
    __tablename__ = "customer_account_team"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("customer_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    person_party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parties.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    since: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        server_default=func.now(),
    )
    until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    account: Mapped["CustomerAccount"] = relationship(back_populates="team")
    person: Mapped["Party"] = relationship()

    __table_args__ = (
        Index("ix_customer_account_team_account_role", "account_id", "role"),
        Index("ix_customer_account_team_person", "person_party_id"),
    )


class CustomerAccountReseller(Base):
    __tablename__ = "customer_account_resellers"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("customer_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    reseller_party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parties.id", ondelete="RESTRICT"),
        nullable=False,
    )
    commission_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    since: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        server_default=func.now(),
    )
    until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    account: Mapped["CustomerAccount"] = relationship(back_populates="resellers")
    reseller: Mapped["Party"] = relationship()

    __table_args__ = (
        Index(
            "uq_customer_account_resellers_active",
            "account_id",
            "reseller_party_id",
            unique=True,
            postgresql_where=text("until IS NULL"),
        ),
        Index("ix_customer_account_resellers_reseller", "reseller_party_id"),
    )


class PartyExternalId(Base):
    __tablename__ = "party_external_ids"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parties.id", ondelete="CASCADE"),
        nullable=False,
    )
    system: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    external_key_type: Mapped[Optional[str]] = mapped_column(Text)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        server_default=func.now(),
    )

    party: Mapped["Party"] = relationship(back_populates="external_mappings")

    __table_args__ = (
        UniqueConstraint("system", "external_id", name="uq_party_external_ids_system_extid"),
        Index("ix_party_external_ids_party", "party_id"),
        Index("ix_party_external_ids_system", "system"),
        Index("ix_party_external_ids_lookup", "system", "external_id"),
    )


class Credential(Base):
    __tablename__ = "credentials"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parties.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    identifier: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[Optional[str]] = mapped_column(Text)
    secret_hash: Mapped[Optional[str]] = mapped_column(Text)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        server_default=func.now(),
    )

    party: Mapped["Party"] = relationship(back_populates="credentials")

    __table_args__ = (
        Index(
            "uq_credentials_type_provider_identifier",
            "type",
            text("COALESCE(provider, '')"),
            "identifier",
            unique=True,
        ),
        Index("ix_credentials_party", "party_id"),
        Index("ix_credentials_identifier", "identifier"),
    )


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    org_party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parties.id", ondelete="CASCADE"),
        nullable=False,
    )
    person_party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parties.id", ondelete="CASCADE"),
        nullable=False,
    )
    access_role: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    permissions: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    invited_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    suspended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        server_default=func.now(),
    )

    organization: Mapped["Party"] = relationship(foreign_keys=[org_party_id])
    person: Mapped["Party"] = relationship(foreign_keys=[person_party_id], back_populates="memberships")

    __table_args__ = (
        Index("uq_memberships_org_person", "org_party_id", "person_party_id", unique=True),
        Index("ix_memberships_person_status", "person_party_id", "status"),
    )


class SupplierAccount(Base):
    """Supplier account linking Party to AP context.

    Mirrors CustomerAccount pattern for accounts payable.
    Links to Party for identity, optionally to legacy Supplier for migration.
    """
    __tablename__ = "supplier_accounts"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parties.id", ondelete="RESTRICT"),
        nullable=False,
    )

    account_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")

    # Legacy link for migration from Supplier model
    supplier_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
    )

    # AP-specific fields
    payment_terms: Mapped[Optional[str]] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default="NGN")
    outstanding_balance: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))

    external_ids: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        server_default=func.now(),
    )

    party: Mapped["Party"] = relationship()

    __table_args__ = (
        Index("ix_supplier_accounts_party", "party_id"),
        Index("ix_supplier_accounts_status", "status"),
        Index("ix_supplier_accounts_supplier", "supplier_id"),
    )
