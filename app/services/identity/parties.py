"""Party service - business logic for party (identity) management.

This service encapsulates party-related business logic:
- Core CRUD for parties (person/organization)
- Party roles (customer, lead, vendor, etc.)
- Party relations (employment, contact-of, etc.)

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional, Sequence, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.party import Party, PartyRole, PartyRelation
from app.services.base import paginate, scoped_query
from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.types import PaginatedResult, PaginationParams

from .party_types import (
    PartyFilters,
    PartyCreateData,
    PartyUpdateData,
    PartyRoleCreateData,
    PartyRoleUpdateData,
    PartyRelationCreateData,
    PartyRelationUpdateData,
)

if TYPE_CHECKING:
    from app.auth import Principal


class PartyService:
    """Service for party (identity) management."""

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Party CRUD
    # -------------------------------------------------------------------------

    def list_parties(
        self,
        filters: Optional[PartyFilters] = None,
        pagination: Optional[PaginationParams] = None,
        include_roles: bool = False,
    ) -> PaginatedResult[Party]:
        """List parties with optional filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.
            include_roles: Whether to eagerly load roles.

        Returns:
            PaginatedResult containing parties and total count.
        """
        query = scoped_query(self.db.query(Party), self.principal)

        if include_roles:
            query = query.options(joinedload(Party.roles))

        if filters:
            if filters.party_type:
                query = query.filter(Party.type == filters.party_type)
            if filters.status:
                query = query.filter(Party.status == filters.status)
            if filters.search:
                like = f"%{filters.search}%"
                query = query.filter(
                    or_(
                        Party.name.ilike(like),
                        Party.primary_email.ilike(like),
                        Party.primary_phone.ilike(like),
                        Party.first_name.ilike(like),
                        Party.last_name.ilike(like),
                    )
                )
            if filters.has_role:
                query = query.join(PartyRole).filter(
                    PartyRole.role == filters.has_role,
                    PartyRole.until.is_(None),
                )

        query = query.order_by(Party.name.asc())
        return paginate(query, pagination)

    def get_party(
        self, party_id: int, include_roles: bool = False
    ) -> Party:
        """Get a party by ID.

        Args:
            party_id: The party ID.
            include_roles: Whether to eagerly load roles.

        Returns:
            The Party.

        Raises:
            NotFoundError: If party not found.
        """
        query = scoped_query(self.db.query(Party), self.principal)

        if include_roles:
            query = query.options(joinedload(Party.roles))

        party = query.filter(Party.id == party_id).first()
        if not party:
            raise NotFoundError(f"Party {party_id} not found")

        return party

    def get_party_by_email(self, email: str) -> Optional[Party]:
        """Get a party by primary email.

        Args:
            email: The email address.

        Returns:
            The Party or None if not found.
        """
        query = scoped_query(self.db.query(Party), self.principal)
        return query.filter(Party.primary_email == email).first()

    def create_party(self, data: PartyCreateData) -> Party:
        """Create a new party.

        Args:
            data: Party creation data.

        Returns:
            The created Party (not yet committed).

        Raises:
            ConflictError: If email/phone already exists.
        """
        # Derive primary_email and primary_phone from emails/phones list
        primary_email = None
        primary_phone = None

        if data.emails:
            for email in data.emails:
                if email.get("is_primary") or not primary_email:
                    primary_email = email.get("address")

        if data.phones:
            for phone in data.phones:
                if phone.get("is_primary") or not primary_phone:
                    primary_phone = phone.get("number")

        # Check for email uniqueness
        if primary_email:
            existing = self.get_party_by_email(primary_email)
            if existing:
                raise ConflictError(f"Party with email {primary_email} already exists")

        party = Party(
            type=data.type,
            status=data.status,
            name=data.name,
            first_name=data.first_name,
            last_name=data.last_name,
            legal_name=data.legal_name,
            trading_name=data.trading_name,
            primary_email=primary_email,
            primary_phone=primary_phone,
            emails=data.emails,
            phones=data.phones,
            addresses=data.addresses,
            external_ids=data.external_ids,
            avatar_url=data.avatar_url,
            timezone=data.timezone,
            locale=data.locale,
            tax_id=data.tax_id,
            tags=data.tags,
            custom_fields=data.custom_fields,
            notes=data.notes,
        )

        self.db.add(party)
        self.db.flush()

        return party

    def update_party(self, party_id: int, data: PartyUpdateData) -> Party:
        """Update a party.

        Args:
            party_id: The party ID.
            data: Fields to update.

        Returns:
            The updated Party (not yet committed).

        Raises:
            NotFoundError: If party not found.
            ConflictError: If email already exists on another party.
        """
        party = self.get_party(party_id)

        # Update simple fields
        simple_fields = [
            "status", "name", "first_name", "last_name", "legal_name",
            "trading_name", "avatar_url", "timezone", "locale", "tax_id",
            "tags", "custom_fields", "notes", "external_ids",
        ]
        for field_name in simple_fields:
            value = getattr(data, field_name, None)
            if value is not None:
                setattr(party, field_name, value)

        # Handle emails - update primary_email
        if data.emails is not None:
            party.emails = data.emails
            primary_email = None
            for email in data.emails:
                if email.get("is_primary") or not primary_email:
                    primary_email = email.get("address")

            if primary_email and primary_email != party.primary_email:
                existing = self.get_party_by_email(primary_email)
                if existing and existing.id != party_id:
                    raise ConflictError(f"Party with email {primary_email} already exists")
                party.primary_email = primary_email

        # Handle phones - update primary_phone
        if data.phones is not None:
            party.phones = data.phones
            primary_phone = None
            for phone in data.phones:
                if phone.get("is_primary") or not primary_phone:
                    primary_phone = phone.get("number")
            party.primary_phone = primary_phone

        # Handle addresses
        if data.addresses is not None:
            party.addresses = data.addresses

        return party

    def delete_party(self, party_id: int) -> None:
        """Delete a party (soft delete by setting status to inactive).

        Args:
            party_id: The party ID.

        Raises:
            NotFoundError: If party not found.
        """
        party = self.get_party(party_id)
        party.status = "inactive"

    # -------------------------------------------------------------------------
    # Party Roles
    # -------------------------------------------------------------------------

    def list_roles(self, party_id: int, active_only: bool = True) -> List[PartyRole]:
        """List roles for a party.

        Args:
            party_id: The party ID.
            active_only: Only return active roles (until is NULL).

        Returns:
            List of PartyRole.

        Raises:
            NotFoundError: If party not found.
        """
        # Verify party exists
        self.get_party(party_id)

        query = self.db.query(PartyRole).filter(PartyRole.party_id == party_id)
        if active_only:
            query = query.filter(PartyRole.until.is_(None))

        return query.order_by(PartyRole.role.asc()).all()

    def get_role(self, party_id: int, role_id: int) -> PartyRole:
        """Get a specific role.

        Args:
            party_id: The party ID.
            role_id: The role ID.

        Returns:
            The PartyRole.

        Raises:
            NotFoundError: If party or role not found.
        """
        # Verify party exists
        self.get_party(party_id)

        role = (
            self.db.query(PartyRole)
            .filter(PartyRole.id == role_id, PartyRole.party_id == party_id)
            .first()
        )
        if not role:
            raise NotFoundError(f"Role {role_id} not found")

        return role

    def add_role(self, party_id: int, data: PartyRoleCreateData) -> PartyRole:
        """Add a role to a party.

        Args:
            party_id: The party ID.
            data: Role creation data.

        Returns:
            The created PartyRole (not yet committed).

        Raises:
            NotFoundError: If party not found.
            ConflictError: If party already has this active role.
        """
        party = self.get_party(party_id)

        # Check for existing active role
        existing = (
            self.db.query(PartyRole)
            .filter(
                PartyRole.party_id == party_id,
                PartyRole.role == data.role,
                PartyRole.until.is_(None),
            )
            .first()
        )
        if existing:
            if data.scope_party_id == existing.scope_party_id:
                raise ConflictError(f"Party already has active role '{data.role}'")

        role = PartyRole(
            party_id=party.id,
            role=data.role,
            status=data.status,
            scope_party_id=data.scope_party_id,
            owner_party_id=data.owner_party_id,
            source=data.source,
            source_campaign=data.source_campaign,
            qualification=data.qualification,
            lead_score=data.lead_score,
            payment_terms=data.payment_terms,
            credit_limit=data.credit_limit,
            notes=data.notes,
            metadata_=data.metadata,
        )

        self.db.add(role)
        self.db.flush()

        return role

    def update_role(
        self, party_id: int, role_id: int, data: PartyRoleUpdateData
    ) -> PartyRole:
        """Update a party role.

        Args:
            party_id: The party ID.
            role_id: The role ID.
            data: Fields to update.

        Returns:
            The updated PartyRole.

        Raises:
            NotFoundError: If party or role not found.
        """
        role = self.get_role(party_id, role_id)

        fields = [
            "status", "scope_party_id", "owner_party_id", "until",
            "source", "source_campaign", "qualification", "lead_score",
            "payment_terms", "credit_limit", "notes",
        ]
        for field_name in fields:
            value = getattr(data, field_name, None)
            if value is not None:
                setattr(role, field_name, value)

        if data.metadata is not None:
            role.metadata_ = data.metadata

        return role

    def remove_role(self, party_id: int, role_id: int) -> None:
        """Remove a role (set until to now).

        Args:
            party_id: The party ID.
            role_id: The role ID.

        Raises:
            NotFoundError: If party or role not found.
        """
        role = self.get_role(party_id, role_id)
        role.until = datetime.now(timezone.utc)

    # -------------------------------------------------------------------------
    # Party Relations
    # -------------------------------------------------------------------------

    def list_relations(
        self, party_id: int, direction: str = "from", active_only: bool = True
    ) -> List[PartyRelation]:
        """List relations for a party.

        Args:
            party_id: The party ID.
            direction: 'from' or 'to' - which side of the relation to filter.
            active_only: Only return active relations.

        Returns:
            List of PartyRelation.

        Raises:
            NotFoundError: If party not found.
        """
        # Verify party exists
        self.get_party(party_id)

        query = self.db.query(PartyRelation)
        if direction == "from":
            query = query.filter(PartyRelation.from_party_id == party_id)
        else:
            query = query.filter(PartyRelation.to_party_id == party_id)

        if active_only:
            query = query.filter(PartyRelation.is_active == True)

        return query.all()

    def add_relation(self, data: PartyRelationCreateData) -> PartyRelation:
        """Add a relation between parties.

        Args:
            data: Relation creation data.

        Returns:
            The created PartyRelation (not yet committed).

        Raises:
            NotFoundError: If either party not found.
            ConflictError: If relation already exists.
        """
        # Verify both parties exist
        self.get_party(data.from_party_id)
        self.get_party(data.to_party_id)

        # Check for existing active relation
        existing = (
            self.db.query(PartyRelation)
            .filter(
                PartyRelation.from_party_id == data.from_party_id,
                PartyRelation.to_party_id == data.to_party_id,
                PartyRelation.relation_type == data.relation_type,
                PartyRelation.until.is_(None),
            )
            .first()
        )
        if existing:
            raise ConflictError(
                f"Relation '{data.relation_type}' already exists between parties"
            )

        relation = PartyRelation(
            from_party_id=data.from_party_id,
            to_party_id=data.to_party_id,
            relation_type=data.relation_type,
            title=data.title,
            department=data.department,
            since=data.since or datetime.now(timezone.utc),
            metadata_=data.metadata,
        )

        self.db.add(relation)
        self.db.flush()

        return relation

    def update_relation(
        self, relation_id: int, data: PartyRelationUpdateData
    ) -> PartyRelation:
        """Update a party relation.

        Args:
            relation_id: The relation ID.
            data: Fields to update.

        Returns:
            The updated PartyRelation.

        Raises:
            NotFoundError: If relation not found.
        """
        relation = self.db.query(PartyRelation).filter(PartyRelation.id == relation_id).first()
        if not relation:
            raise NotFoundError(f"Relation {relation_id} not found")

        fields = ["title", "department", "since", "until", "is_active"]
        for field_name in fields:
            value = getattr(data, field_name, None)
            if value is not None:
                setattr(relation, field_name, value)

        if data.metadata is not None:
            relation.metadata_ = data.metadata

        return relation

    def remove_relation(self, relation_id: int) -> None:
        """Remove a relation (set until to now and is_active to false).

        Args:
            relation_id: The relation ID.

        Raises:
            NotFoundError: If relation not found.
        """
        relation = self.db.query(PartyRelation).filter(PartyRelation.id == relation_id).first()
        if not relation:
            raise NotFoundError(f"Relation {relation_id} not found")

        relation.until = datetime.now(timezone.utc)
        relation.is_active = False

    # -------------------------------------------------------------------------
    # Utility methods
    # -------------------------------------------------------------------------

    def find_by_external_id(self, system: str, external_id: str) -> Optional[Party]:
        """Find a party by external ID.

        Args:
            system: The external system name.
            external_id: The ID in the external system.

        Returns:
            The Party or None if not found.
        """
        from app.models.party import PartyExternalId

        mapping = (
            self.db.query(PartyExternalId)
            .filter(
                PartyExternalId.system == system,
                PartyExternalId.external_id == external_id,
            )
            .first()
        )
        if mapping:
            return self.db.query(Party).filter(Party.id == mapping.party_id).first()
        return None
