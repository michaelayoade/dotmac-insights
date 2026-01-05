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
from sqlalchemy.orm import Session, joinedload, load_only

from app.models.party import Party, PartyExternalId, PartyRole, PartyRelation
from app.models.omni import OmniConversation, OmniMessage, OmniParticipant
from app.models.marketing import EmailSend, JourneyEnrollment, MarketingConsent, SuppressionEntry
from app.models.ticket import Ticket
from app.models.crm import Activity, ActivityType, ActivityStatus
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
        query = scoped_query(self.db.query(Party), self.principal).options(
            load_only(
                Party.id,
                Party.type,
                Party.status,
                Party.name,
                Party.first_name,
                Party.last_name,
                Party.legal_name,
                Party.trading_name,
                Party.primary_email,
                Party.primary_phone,
                Party.emails,
                Party.phones,
                Party.addresses,
                Party.external_ids,
                Party.avatar_url,
                Party.timezone,
                Party.locale,
                Party.tax_id,
                Party.tags,
                Party.custom_fields,
                Party.notes,
                Party.created_at,
                Party.updated_at,
            )
        )

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
        query = scoped_query(self.db.query(Party), self.principal).options(
            load_only(
                Party.id,
                Party.type,
                Party.status,
                Party.name,
                Party.first_name,
                Party.last_name,
                Party.legal_name,
                Party.trading_name,
                Party.primary_email,
                Party.primary_phone,
                Party.emails,
                Party.phones,
                Party.addresses,
                Party.external_ids,
                Party.avatar_url,
                Party.timezone,
                Party.locale,
                Party.tax_id,
                Party.tags,
                Party.custom_fields,
                Party.notes,
                Party.created_at,
                Party.updated_at,
            )
        )

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
        query = scoped_query(self.db.query(Party), self.principal).options(
            load_only(
                Party.id,
                Party.type,
                Party.status,
                Party.name,
                Party.first_name,
                Party.last_name,
                Party.legal_name,
                Party.trading_name,
                Party.primary_email,
                Party.primary_phone,
                Party.emails,
                Party.phones,
                Party.addresses,
                Party.external_ids,
                Party.avatar_url,
                Party.timezone,
                Party.locale,
                Party.tax_id,
                Party.tags,
                Party.custom_fields,
                Party.notes,
                Party.created_at,
                Party.updated_at,
            )
        )
        return query.filter(Party.primary_email == email).first()

    def get_party_by_phone(self, phone: str) -> Optional[Party]:
        """Get a party by primary phone number.

        Args:
            phone: The phone number.

        Returns:
            The Party or None if not found.
        """
        query = scoped_query(self.db.query(Party), self.principal).options(
            load_only(
                Party.id,
                Party.type,
                Party.status,
                Party.name,
                Party.first_name,
                Party.last_name,
                Party.legal_name,
                Party.trading_name,
                Party.primary_email,
                Party.primary_phone,
                Party.emails,
                Party.phones,
                Party.addresses,
                Party.external_ids,
                Party.avatar_url,
                Party.timezone,
                Party.locale,
                Party.tax_id,
                Party.tags,
                Party.custom_fields,
                Party.notes,
                Party.created_at,
                Party.updated_at,
            )
        )
        return query.filter(Party.primary_phone == phone).first()

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
    # Merge Parties
    # -------------------------------------------------------------------------

    def merge_parties(
        self,
        primary_id: int,
        duplicate_id: int,
        deactivate_duplicate: bool = True,
        reason: str | None = None,
        auto_select_primary: bool = True,
    ) -> Party:
        if primary_id == duplicate_id:
            raise ValidationError("Primary and duplicate parties must differ")

        primary = self.db.query(Party).filter(Party.id == primary_id).first()
        if not primary:
            raise NotFoundError(f"Party {primary_id} not found")

        duplicate = self.db.query(Party).filter(Party.id == duplicate_id).first()
        if not duplicate:
            raise NotFoundError(f"Party {duplicate_id} not found")

        now = datetime.now(timezone.utc)

        selection = self.preview_merge(primary_id, duplicate_id, auto_select_primary=auto_select_primary)
        if selection["selected_primary_id"] != primary_id:
            primary, duplicate = duplicate, primary
        primary_score = selection["primary_score"]
        duplicate_score = selection["duplicate_score"]
        audit_issues = selection["audit_issues"]

        if not primary.primary_email and duplicate.primary_email:
            primary.primary_email = duplicate.primary_email
        if not primary.primary_phone and duplicate.primary_phone:
            primary.primary_phone = duplicate.primary_phone
        if not primary.name and duplicate.name:
            primary.name = duplicate.name
        if not primary.first_name and duplicate.first_name:
            primary.first_name = duplicate.first_name
        if not primary.last_name and duplicate.last_name:
            primary.last_name = duplicate.last_name

        primary.external_ids = _merge_dict(primary.external_ids, duplicate.external_ids)
        primary.tags = _merge_list(primary.tags, duplicate.tags)

        mappings = (
            self.db.query(PartyExternalId)
            .filter(PartyExternalId.party_id == duplicate.id)
            .all()
        )
        for mapping in mappings:
            exists = (
                self.db.query(PartyExternalId)
                .filter(
                    PartyExternalId.system == mapping.system,
                    PartyExternalId.external_id == mapping.external_id,
                )
                .first()
            )
            if exists:
                self.db.delete(mapping)
                continue

            has_primary = (
                self.db.query(PartyExternalId)
                .filter(
                    PartyExternalId.party_id == primary.id,
                    PartyExternalId.system == mapping.system,
                    PartyExternalId.is_primary.is_(True),
                )
                .first()
            )
            mapping.party_id = primary.id
            if has_primary:
                mapping.is_primary = False

        self.db.query(OmniParticipant).filter(OmniParticipant.party_id == duplicate.id).update(
            {"party_id": primary.id, "updated_at": now},
            synchronize_session=False,
        )
        self.db.query(OmniConversation).filter(OmniConversation.party_id == duplicate.id).update(
            {"party_id": primary.id, "updated_at": now},
            synchronize_session=False,
        )
        self.db.query(OmniMessage).filter(OmniMessage.party_id == duplicate.id).update(
            {"party_id": primary.id, "updated_at": now},
            synchronize_session=False,
        )

        self._merge_marketing_records(primary.id, duplicate.id)
        self.db.query(JourneyEnrollment).filter(JourneyEnrollment.party_id == duplicate.id).update(
            {"party_id": primary.id},
            synchronize_session=False,
        )
        self.db.query(EmailSend).filter(EmailSend.party_id == duplicate.id).update(
            {"party_id": primary.id},
            synchronize_session=False,
        )
        self.db.query(Ticket).filter(Ticket.party_id == duplicate.id).update(
            {"party_id": primary.id},
            synchronize_session=False,
        )

        duplicate_roles = self.db.query(PartyRole).filter(PartyRole.party_id == duplicate.id).all()
        for role in duplicate_roles:
            if role.until is None:
                exists = (
                    self.db.query(PartyRole)
                    .filter(
                        PartyRole.party_id == primary.id,
                        PartyRole.role == role.role,
                        PartyRole.scope_party_id == role.scope_party_id,
                        PartyRole.until.is_(None),
                    )
                    .first()
                )
                if exists:
                    role.until = now
                    role.status = "inactive"
                    role.updated_at = now
                    continue
            role.party_id = primary.id
            role.updated_at = now

        if deactivate_duplicate:
            duplicate.status = "inactive"
            note = f"Merged into party {primary.id} on {now.date().isoformat()}"
            duplicate.notes = f"{duplicate.notes}\n{note}" if duplicate.notes else note
            duplicate.updated_at = now

        primary.updated_at = now
        self._log_merge_activity(
            primary_id=primary.id,
            duplicate_id=duplicate.id,
            reason=reason or "unspecified",
            occurred_at=now,
            primary_score=primary_score,
            duplicate_score=duplicate_score,
            swapped=selection["auto_swapped"],
            audit_issues=audit_issues,
        )
        return primary

    def _merge_marketing_records(self, primary_id: int, duplicate_id: int) -> None:
        duplicate_consents = (
            self.db.query(MarketingConsent)
            .filter(MarketingConsent.party_id == duplicate_id)
            .all()
        )
        for consent in duplicate_consents:
            existing = (
                self.db.query(MarketingConsent)
                .filter(
                    MarketingConsent.party_id == primary_id,
                    MarketingConsent.channel == consent.channel,
                )
                .first()
            )
            if existing:
                self.db.delete(consent)
            else:
                consent.party_id = primary_id

        duplicate_suppressions = (
            self.db.query(SuppressionEntry)
            .filter(SuppressionEntry.party_id == duplicate_id)
            .all()
        )
        for suppression in duplicate_suppressions:
            existing = (
                self.db.query(SuppressionEntry)
                .filter(
                    SuppressionEntry.party_id == primary_id,
                    SuppressionEntry.channel == suppression.channel,
                )
                .first()
            )
            if existing:
                self.db.delete(suppression)
            else:
                suppression.party_id = primary_id

    def preview_merge(self, primary_id: int, duplicate_id: int, auto_select_primary: bool = True) -> dict:
        if primary_id == duplicate_id:
            raise ValidationError("Primary and duplicate parties must differ")

        primary = self.db.query(Party).filter(Party.id == primary_id).first()
        if not primary:
            raise NotFoundError(f"Party {primary_id} not found")

        duplicate = self.db.query(Party).filter(Party.id == duplicate_id).first()
        if not duplicate:
            raise NotFoundError(f"Party {duplicate_id} not found")

        primary_score = self._party_history_score(primary.id)
        duplicate_score = self._party_history_score(duplicate.id)

        selected_primary_id = primary_id
        selected_duplicate_id = duplicate_id
        if auto_select_primary and duplicate_score > primary_score:
            selected_primary_id = duplicate_id
            selected_duplicate_id = primary_id

        audit_issues = self._identity_audit(selected_primary_id)
        return {
            "primary_id": primary_id,
            "duplicate_id": duplicate_id,
            "selected_primary_id": selected_primary_id,
            "selected_duplicate_id": selected_duplicate_id,
            "auto_swapped": selected_primary_id != primary_id,
            "primary_score": primary_score,
            "duplicate_score": duplicate_score,
            "audit_issues": audit_issues,
        }

    def _party_history_score(self, party_id: int) -> int:
        score = 0
        score += self.db.query(PartyRole).filter(PartyRole.party_id == party_id).count()
        score += self.db.query(OmniConversation).filter(OmniConversation.party_id == party_id).count()
        score += self.db.query(OmniMessage).filter(OmniMessage.party_id == party_id).count()
        score += self.db.query(EmailSend).filter(EmailSend.party_id == party_id).count()
        score += self.db.query(JourneyEnrollment).filter(JourneyEnrollment.party_id == party_id).count()
        score += self.db.query(PartyExternalId).filter(PartyExternalId.party_id == party_id).count()
        return score

    def _identity_audit(self, party_id: int) -> List[str]:
        issues: List[str] = []
        party = self.db.query(Party).filter(Party.id == party_id).first()
        if not party:
            return issues

        if party.primary_email:
            dup_email = (
                self.db.query(Party)
                .filter(Party.primary_email == party.primary_email, Party.id != party.id)
                .first()
            )
            if dup_email:
                issues.append(f"primary_email_duplicate:{party.primary_email}")

        if party.primary_phone:
            dup_phone = (
                self.db.query(Party)
                .filter(Party.primary_phone == party.primary_phone, Party.id != party.id)
                .first()
            )
            if dup_phone:
                issues.append(f"primary_phone_duplicate:{party.primary_phone}")

        participants = self.db.query(OmniParticipant).filter(OmniParticipant.party_id == party.id).all()
        for participant in participants:
            if not participant.handle:
                continue
            if participant.handle in {party.primary_email, party.primary_phone}:
                continue
            system = f"marketing:{participant.channel_type}"
            mapping = (
                self.db.query(PartyExternalId)
                .filter(
                    PartyExternalId.party_id == party.id,
                    PartyExternalId.system == system,
                    PartyExternalId.external_id == participant.handle,
                )
                .first()
            )
            if not mapping:
                issues.append(f"missing_mapping:{system}:{participant.handle}")

        return issues

    def _log_merge_activity(
        self,
        primary_id: int,
        duplicate_id: int,
        reason: str,
        occurred_at: datetime,
        primary_score: int,
        duplicate_score: int,
        swapped: bool,
        audit_issues: List[str],
    ) -> None:
        actor_label = "system"
        if self.principal:
            actor_label = self.principal.email or self.principal.name or f"{self.principal.type}:{self.principal.id}"
        details = [
            f"actor={actor_label}",
            f"reason={reason}",
            f"primary_id={primary_id}",
            f"duplicate_id={duplicate_id}",
            f"primary_score={primary_score}",
            f"duplicate_score={duplicate_score}",
            f"auto_swapped={str(swapped).lower()}",
            f"audit_issues={audit_issues if audit_issues else 'none'}",
        ]
        activity = Activity(
            activity_type=ActivityType.NOTE,
            subject="Party merge",
            description="\n".join(details),
            status=ActivityStatus.COMPLETED,
            party_id=primary_id,
            completed_at=occurred_at,
            created_at=occurred_at,
            updated_at=occurred_at,
        )
        self.db.add(activity)

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
            return (
                self.db.query(Party)
                .options(
                    load_only(
                        Party.id,
                        Party.type,
                        Party.status,
                        Party.name,
                        Party.first_name,
                        Party.last_name,
                        Party.legal_name,
                        Party.trading_name,
                        Party.primary_email,
                        Party.primary_phone,
                        Party.emails,
                        Party.phones,
                        Party.addresses,
                        Party.external_ids,
                        Party.avatar_url,
                        Party.timezone,
                        Party.locale,
                        Party.tax_id,
                        Party.tags,
                        Party.custom_fields,
                        Party.notes,
                        Party.created_at,
                        Party.updated_at,
                    )
                )
                .filter(Party.id == mapping.party_id)
                .first()
            )
        return None


def _merge_list(left: list, right: Optional[list]) -> list:
    merged = list(left or [])
    for item in right or []:
        if item not in merged:
            merged.append(item)
    return merged


def _merge_dict(left: dict, right: Optional[dict]) -> dict:
    merged = dict(left or {})
    for key, value in (right or {}).items():
        merged.setdefault(key, value)
    return merged
