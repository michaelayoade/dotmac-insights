"""Lead service - business logic for lead management.

Leads are Party + PartyRole(role="lead") - NOT ERPNextLead (deprecated).

This service encapsulates lead-related business logic:
- Core CRUD for leads (Party + PartyRole)
- Lead scoring
- Qualification workflow
- Conversion to opportunity or customer
- Bulk operations

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional, Tuple

from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session, joinedload

from app.models.party import Party, PartyRole
from app.models.crm import Opportunity, OpportunityStatus
from app.services.base import paginate, scoped_query
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams
from app.utils.datetime_utils import utc_now

from .lead_types import (
    LeadFilters,
    LeadCreateData,
    LeadUpdateData,
    LeadScoreUpdate,
    LeadConversionData,
    LeadSummary,
    LeadFunnel,
    Lead,
)

if TYPE_CHECKING:
    from app.auth import Principal


# Lead role code - must exist in ref_party_role_types
LEAD_ROLE = "lead"


class LeadService:
    """Service for lead management using Party + PartyRole.

    All methods that mutate data do NOT commit.
    The caller is responsible for db.commit().
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Lead CRUD
    # -------------------------------------------------------------------------

    def list_leads(
        self,
        filters: Optional[LeadFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Lead]:
        """List leads with optional filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.

        Returns:
            PaginatedResult containing Lead objects and total count.
        """
        # Join Party with PartyRole where role = 'lead'
        query = (
            self.db.query(Party, PartyRole)
            .join(PartyRole, Party.id == PartyRole.party_id)
            .filter(PartyRole.role == LEAD_ROLE)
            .filter(PartyRole.until.is_(None))  # Active role
        )

        if filters:
            if filters.search:
                like = f"%{filters.search}%"
                query = query.filter(
                    or_(
                        Party.name.ilike(like),
                        Party.primary_email.ilike(like),
                        Party.primary_phone.ilike(like),
                    )
                )

            if filters.status:
                query = query.filter(PartyRole.status == filters.status)

            if filters.qualification:
                query = query.filter(PartyRole.qualification == filters.qualification)

            if filters.source:
                query = query.filter(PartyRole.source == filters.source)

            if filters.source_campaign:
                query = query.filter(PartyRole.source_campaign == filters.source_campaign)

            if filters.owner_id:
                query = query.filter(PartyRole.owner_party_id == filters.owner_id)

            if filters.min_score is not None:
                query = query.filter(PartyRole.lead_score >= filters.min_score)

            if filters.max_score is not None:
                query = query.filter(PartyRole.lead_score <= filters.max_score)

            if filters.created_after:
                query = query.filter(PartyRole.since >= filters.created_after)

            if filters.created_before:
                query = query.filter(PartyRole.since <= filters.created_before)

        query = query.order_by(PartyRole.since.desc())

        # Manual pagination since we're returning Lead objects
        if pagination:
            total = query.count()
            offset = pagination.offset or 0
            limit = pagination.limit or 50
            results = query.offset(offset).limit(limit).all()
        else:
            results = query.all()
            total = len(results)

        leads = [self._to_lead(party, role) for party, role in results]

        return PaginatedResult(
            data=leads,
            total=total,
            page=pagination.page if pagination else 1,
            page_size=pagination.limit if pagination else total,
        )

    def get_lead(self, lead_id: int) -> Lead:
        """Get a lead by Party ID.

        Args:
            lead_id: The Party ID of the lead.

        Returns:
            The Lead object.

        Raises:
            NotFoundError: If lead not found.
        """
        result = (
            self.db.query(Party, PartyRole)
            .join(PartyRole, Party.id == PartyRole.party_id)
            .filter(Party.id == lead_id)
            .filter(PartyRole.role == LEAD_ROLE)
            .filter(PartyRole.until.is_(None))
            .first()
        )

        if not result:
            raise NotFoundError(f"Lead {lead_id} not found")

        party, role = result
        return self._to_lead(party, role)

    def get_lead_by_email(self, email: str) -> Optional[Lead]:
        """Get a lead by email.

        Args:
            email: Email address.

        Returns:
            Lead if found, None otherwise.
        """
        result = (
            self.db.query(Party, PartyRole)
            .join(PartyRole, Party.id == PartyRole.party_id)
            .filter(Party.primary_email == email)
            .filter(PartyRole.role == LEAD_ROLE)
            .filter(PartyRole.until.is_(None))
            .first()
        )

        if not result:
            return None

        party, role = result
        return self._to_lead(party, role)

    def create_lead(self, data: LeadCreateData) -> Lead:
        """Create a new lead (Party + PartyRole).

        Args:
            data: Lead creation data.

        Returns:
            The created Lead (not yet committed).
        """
        # Check for existing lead with same email
        if data.primary_email:
            existing = self.get_lead_by_email(data.primary_email)
            if existing:
                raise ValidationError(f"Lead with email {data.primary_email} already exists")

        # Create Party
        party = Party(
            type=data.type,
            status="active",
            name=data.name,
            first_name=data.first_name,
            last_name=data.last_name,
            legal_name=data.legal_name,
            trading_name=data.trading_name,
            primary_email=data.primary_email,
            primary_phone=data.primary_phone,
            notes=data.notes,
            tags=data.tags or [],
            custom_fields=data.custom_fields or {},
        )

        self.db.add(party)
        self.db.flush()

        # Create PartyRole with role='lead'
        role = PartyRole(
            party_id=party.id,
            role=LEAD_ROLE,
            status="active",
            source=data.source,
            source_campaign=data.source_campaign,
            qualification=data.qualification,
            lead_score=data.lead_score,
            owner_party_id=data.owner_party_id,
        )

        self.db.add(role)
        self.db.flush()

        return self._to_lead(party, role)

    def update_lead(self, lead_id: int, data: LeadUpdateData) -> Lead:
        """Update a lead.

        Args:
            lead_id: The Party ID of the lead.
            data: Fields to update.

        Returns:
            The updated Lead (not yet committed).

        Raises:
            NotFoundError: If lead not found.
        """
        result = (
            self.db.query(Party, PartyRole)
            .join(PartyRole, Party.id == PartyRole.party_id)
            .filter(Party.id == lead_id)
            .filter(PartyRole.role == LEAD_ROLE)
            .filter(PartyRole.until.is_(None))
            .first()
        )

        if not result:
            raise NotFoundError(f"Lead {lead_id} not found")

        party, role = result

        # Update Party fields
        party_fields = ["name", "primary_email", "primary_phone", "first_name", "last_name", "notes"]
        for field_name in party_fields:
            value = getattr(data, field_name, None)
            if value is not None:
                setattr(party, field_name, value)

        if data.tags is not None:
            party.tags = data.tags
        if data.custom_fields is not None:
            party.custom_fields = data.custom_fields

        # Update PartyRole fields
        role_fields = ["status", "source", "source_campaign", "qualification", "lead_score", "owner_party_id"]
        for field_name in role_fields:
            value = getattr(data, field_name, None)
            if value is not None:
                setattr(role, field_name, value)

        return self._to_lead(party, role)

    def delete_lead(self, lead_id: int) -> None:
        """Delete a lead (end the lead role, keep Party).

        Args:
            lead_id: The Party ID of the lead.

        Raises:
            NotFoundError: If lead not found.
        """
        role = (
            self.db.query(PartyRole)
            .filter(PartyRole.party_id == lead_id)
            .filter(PartyRole.role == LEAD_ROLE)
            .filter(PartyRole.until.is_(None))
            .first()
        )

        if not role:
            raise NotFoundError(f"Lead {lead_id} not found")

        # End the role instead of deleting
        role.until = utc_now()
        role.status = "inactive"

    # -------------------------------------------------------------------------
    # Lead Scoring
    # -------------------------------------------------------------------------

    def calculate_score(self, lead_id: int) -> int:
        """Calculate lead score based on various factors.

        Args:
            lead_id: The Party ID of the lead.

        Returns:
            Calculated score (0-100).
        """
        lead = self.get_lead(lead_id)
        score = 0

        # Email provided (+20)
        if lead.primary_email:
            score += 20

        # Phone provided (+15)
        if lead.primary_phone:
            score += 15

        # Source attribution (+10)
        if lead.source:
            score += 10

        # Campaign attribution (+10)
        if lead.source_campaign:
            score += 10

        # Qualification level
        if lead.qualification:
            qual_scores = {
                "hot": 30,
                "warm": 20,
                "cold": 5,
            }
            score += qual_scores.get(lead.qualification.lower(), 0)

        # Activity count (would need to query activities)
        # For now, cap at 100
        return min(score, 100)

    def update_score(self, lead_id: int, score_update: LeadScoreUpdate) -> Lead:
        """Update lead score.

        Args:
            lead_id: The Party ID of the lead.
            score_update: Score and optional reason.

        Returns:
            Updated Lead.
        """
        role = (
            self.db.query(PartyRole)
            .filter(PartyRole.party_id == lead_id)
            .filter(PartyRole.role == LEAD_ROLE)
            .filter(PartyRole.until.is_(None))
            .first()
        )

        if not role:
            raise NotFoundError(f"Lead {lead_id} not found")

        role.lead_score = score_update.score

        # Store reason in metadata
        if score_update.reason:
            metadata = role.metadata_ or {}
            metadata["score_history"] = metadata.get("score_history", [])
            metadata["score_history"].append({
                "score": score_update.score,
                "reason": score_update.reason,
                "timestamp": utc_now().isoformat(),
            })
            role.metadata_ = metadata

        return self.get_lead(lead_id)

    # -------------------------------------------------------------------------
    # Qualification Workflow
    # -------------------------------------------------------------------------

    def qualify_lead(self, lead_id: int, qualification: str) -> Lead:
        """Qualify a lead.

        Args:
            lead_id: The Party ID of the lead.
            qualification: Qualification level (hot, warm, cold, etc.)

        Returns:
            Updated Lead.
        """
        return self.update_lead(lead_id, LeadUpdateData(qualification=qualification))

    def disqualify_lead(self, lead_id: int, reason: str) -> Lead:
        """Disqualify a lead.

        Args:
            lead_id: The Party ID of the lead.
            reason: Disqualification reason.

        Returns:
            Updated Lead.
        """
        role = (
            self.db.query(PartyRole)
            .filter(PartyRole.party_id == lead_id)
            .filter(PartyRole.role == LEAD_ROLE)
            .filter(PartyRole.until.is_(None))
            .first()
        )

        if not role:
            raise NotFoundError(f"Lead {lead_id} not found")

        role.qualification = "disqualified"
        role.status = "inactive"

        # Store reason
        metadata = role.metadata_ or {}
        metadata["disqualification_reason"] = reason
        metadata["disqualified_at"] = utc_now().isoformat()
        role.metadata_ = metadata

        return self.get_lead(lead_id)

    # -------------------------------------------------------------------------
    # Conversion
    # -------------------------------------------------------------------------

    def convert_to_opportunity(
        self,
        lead_id: int,
        conversion_data: LeadConversionData,
    ) -> Opportunity:
        """Convert lead to opportunity.

        Args:
            lead_id: The Party ID of the lead.
            conversion_data: Opportunity details.

        Returns:
            Created Opportunity.
        """
        lead = self.get_lead(lead_id)

        # Create opportunity linked to the Party
        opp = Opportunity(
            name=conversion_data.opportunity_name or f"Opportunity from {lead.name}",
            party_id=lead.party_id,
            status=OpportunityStatus.OPEN,
            deal_value=conversion_data.deal_value or 0,
            stage_id=conversion_data.stage_id,
            expected_close_date=conversion_data.expected_close_date,
            source=lead.source,
            campaign=lead.source_campaign,
        )

        self.db.add(opp)
        self.db.flush()

        # Update lead role to mark as converted
        role = (
            self.db.query(PartyRole)
            .filter(PartyRole.party_id == lead_id)
            .filter(PartyRole.role == LEAD_ROLE)
            .filter(PartyRole.until.is_(None))
            .first()
        )

        if role:
            role.qualification = "converted"
            metadata = role.metadata_ or {}
            metadata["converted_to"] = "opportunity"
            metadata["opportunity_id"] = opp.id
            metadata["converted_at"] = utc_now().isoformat()
            role.metadata_ = metadata

        return opp

    def convert_to_customer(self, lead_id: int) -> Party:
        """Convert lead to customer (add customer role).

        Args:
            lead_id: The Party ID of the lead.

        Returns:
            The Party with customer role added.
        """
        lead = self.get_lead(lead_id)

        # Check if customer role already exists
        existing_role = (
            self.db.query(PartyRole)
            .filter(PartyRole.party_id == lead_id)
            .filter(PartyRole.role == "customer")
            .filter(PartyRole.until.is_(None))
            .first()
        )

        if existing_role:
            raise ValidationError(f"Party {lead_id} is already a customer")

        # Add customer role
        customer_role = PartyRole(
            party_id=lead_id,
            role="customer",
            status="active",
            source=lead.source,
            source_campaign=lead.source_campaign,
        )

        self.db.add(customer_role)

        # Update lead role to mark as converted
        lead_role = (
            self.db.query(PartyRole)
            .filter(PartyRole.party_id == lead_id)
            .filter(PartyRole.role == LEAD_ROLE)
            .filter(PartyRole.until.is_(None))
            .first()
        )

        if lead_role:
            lead_role.qualification = "converted"
            metadata = lead_role.metadata_ or {}
            metadata["converted_to"] = "customer"
            metadata["converted_at"] = utc_now().isoformat()
            lead_role.metadata_ = metadata

        party = self.db.query(Party).filter(Party.id == lead_id).first()
        return party

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def bulk_assign(self, lead_ids: List[int], owner_id: int) -> int:
        """Bulk assign leads to an owner.

        Args:
            lead_ids: List of Party IDs.
            owner_id: Owner Party ID.

        Returns:
            Number of leads updated.
        """
        count = (
            self.db.query(PartyRole)
            .filter(PartyRole.party_id.in_(lead_ids))
            .filter(PartyRole.role == LEAD_ROLE)
            .filter(PartyRole.until.is_(None))
            .update({"owner_party_id": owner_id}, synchronize_session=False)
        )
        return count

    def bulk_update_status(self, lead_ids: List[int], status: str) -> int:
        """Bulk update lead status.

        Args:
            lead_ids: List of Party IDs.
            status: New status.

        Returns:
            Number of leads updated.
        """
        count = (
            self.db.query(PartyRole)
            .filter(PartyRole.party_id.in_(lead_ids))
            .filter(PartyRole.role == LEAD_ROLE)
            .filter(PartyRole.until.is_(None))
            .update({"status": status}, synchronize_session=False)
        )
        return count

    # -------------------------------------------------------------------------
    # Analytics
    # -------------------------------------------------------------------------

    def get_summary(self, filters: Optional[LeadFilters] = None) -> LeadSummary:
        """Get lead summary statistics.

        Args:
            filters: Optional filters.

        Returns:
            LeadSummary with aggregated stats.
        """
        base_query = (
            self.db.query(PartyRole)
            .filter(PartyRole.role == LEAD_ROLE)
            .filter(PartyRole.until.is_(None))
        )

        if filters:
            if filters.created_after:
                base_query = base_query.filter(PartyRole.since >= filters.created_after)
            if filters.created_before:
                base_query = base_query.filter(PartyRole.since <= filters.created_before)

        total = base_query.count()
        active = base_query.filter(PartyRole.status == "active").count()
        qualified = base_query.filter(PartyRole.qualification.in_(["hot", "warm"])).count()
        unqualified = base_query.filter(
            or_(PartyRole.qualification.is_(None), PartyRole.qualification == "cold")
        ).count()
        converted = base_query.filter(PartyRole.qualification == "converted").count()

        # Average score
        avg_score_result = base_query.with_entities(
            func.avg(PartyRole.lead_score)
        ).scalar()
        avg_score = float(avg_score_result) if avg_score_result else 0.0

        # By source
        source_counts = (
            base_query.with_entities(PartyRole.source, func.count(PartyRole.id))
            .group_by(PartyRole.source)
            .all()
        )
        by_source = {src or "Unknown": cnt for src, cnt in source_counts}

        # By qualification
        qual_counts = (
            base_query.with_entities(PartyRole.qualification, func.count(PartyRole.id))
            .group_by(PartyRole.qualification)
            .all()
        )
        by_qualification = {qual or "Unqualified": cnt for qual, cnt in qual_counts}

        return LeadSummary(
            total_leads=total,
            active_leads=active,
            qualified_leads=qualified,
            unqualified_leads=unqualified,
            converted_leads=converted,
            avg_score=avg_score,
            by_source=by_source,
            by_qualification=by_qualification,
        )

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _to_lead(self, party: Party, role: PartyRole) -> Lead:
        """Convert Party + PartyRole to Lead dataclass."""
        return Lead(
            party_id=party.id,
            name=party.name or "",
            type=party.type,
            primary_email=party.primary_email,
            primary_phone=party.primary_phone,
            first_name=party.first_name,
            last_name=party.last_name,
            notes=party.notes,
            tags=party.tags or [],
            custom_fields=party.custom_fields or {},
            created_at=party.created_at,
            role_id=role.id,
            status=role.status,
            source=role.source,
            source_campaign=role.source_campaign,
            qualification=role.qualification,
            lead_score=role.lead_score,
            owner_party_id=role.owner_party_id,
            role_since=role.since,
        )
