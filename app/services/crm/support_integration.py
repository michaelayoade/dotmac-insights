"""Support-CRM integration service - bridges Support and CRM modules.

This service provides integration between Support and CRM:
- Ticket ↔ Opportunity linking
- Lead creation from conversations/tickets (Party-based, NOT ERPNextLead)
- Opportunity creation from tickets
- Party enrichment from support history
- Cross-module search

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional, Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.party import Party, PartyRole
from app.models.crm import Opportunity, OpportunityStatus
from app.models.omni import OmniConversation
from app.models.ticket import Ticket, TicketStatus
from app.services.errors import NotFoundError, ValidationError
from app.utils.datetime_utils import utc_now

from .support_integration_types import (
    LeadFromConversationData,
    LeadFromTicketData,
    OpportunityFromTicketData,
    TicketOpportunityLink,
    PartyEnrichment,
    SupportSummary,
    RelatedEntities,
)

if TYPE_CHECKING:
    from app.auth import Principal


# Lead role code - must exist in ref_party_role_types
LEAD_ROLE = "lead"


class SupportCRMBridgeService:
    """Service for bridging Support and CRM modules.

    All methods that mutate data do NOT commit.
    The caller is responsible for db.commit().
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Ticket ↔ Opportunity Linking
    # -------------------------------------------------------------------------

    def link_ticket_to_opportunity(
        self,
        ticket_id: int,
        opportunity_id: int,
    ) -> TicketOpportunityLink:
        """Link a ticket to an opportunity.

        Args:
            ticket_id: The ticket ID.
            opportunity_id: The opportunity ID.

        Returns:
            TicketOpportunityLink record.

        Raises:
            NotFoundError: If ticket or opportunity not found.
        """
        ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")

        opportunity = self.db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
        if not opportunity:
            raise NotFoundError(f"Opportunity {opportunity_id} not found")

        # Store link in ticket's metadata or a dedicated field
        # For now, using party_id to ensure both reference same party
        if ticket.party_id and opportunity.party_id:
            if ticket.party_id != opportunity.party_id:
                raise ValidationError("Ticket and opportunity must belong to same party")

        # Store opportunity reference in ticket metadata
        metadata = ticket.metadata_ if hasattr(ticket, 'metadata_') else {}
        if not metadata:
            metadata = {}
        linked_opps = metadata.get("linked_opportunities", [])
        if opportunity_id not in linked_opps:
            linked_opps.append(opportunity_id)
            metadata["linked_opportunities"] = linked_opps
            if hasattr(ticket, 'metadata_'):
                ticket.metadata_ = metadata

        return TicketOpportunityLink(
            ticket_id=ticket_id,
            opportunity_id=opportunity_id,
            created_at=utc_now(),
            created_by=self.principal.user_id if self.principal else None,
        )

    def unlink_ticket_from_opportunity(
        self,
        ticket_id: int,
        opportunity_id: int,
    ) -> None:
        """Remove link between ticket and opportunity.

        Args:
            ticket_id: The ticket ID.
            opportunity_id: The opportunity ID.
        """
        ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")

        if hasattr(ticket, 'metadata_') and ticket.metadata_:
            metadata = ticket.metadata_
            linked_opps = metadata.get("linked_opportunities", [])
            if opportunity_id in linked_opps:
                linked_opps.remove(opportunity_id)
                metadata["linked_opportunities"] = linked_opps
                ticket.metadata_ = metadata

    def get_tickets_for_opportunity(self, opportunity_id: int) -> List[Ticket]:
        """Get all tickets linked to an opportunity.

        Args:
            opportunity_id: The opportunity ID.

        Returns:
            List of linked tickets.
        """
        opportunity = self.db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
        if not opportunity:
            raise NotFoundError(f"Opportunity {opportunity_id} not found")

        # Find tickets with same party_id
        if opportunity.party_id:
            return (
                self.db.query(Ticket)
                .filter(Ticket.party_id == opportunity.party_id)
                .order_by(Ticket.created_at.desc())
                .all()
            )

        return []

    def get_opportunities_for_ticket(self, ticket_id: int) -> List[Opportunity]:
        """Get all opportunities linked to a ticket.

        Args:
            ticket_id: The ticket ID.

        Returns:
            List of linked opportunities.
        """
        ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")

        # Find opportunities with same party_id
        if ticket.party_id:
            return (
                self.db.query(Opportunity)
                .filter(Opportunity.party_id == ticket.party_id)
                .order_by(Opportunity.created_at.desc())
                .all()
            )

        return []

    # -------------------------------------------------------------------------
    # Lead Creation from Support (Party-based)
    # -------------------------------------------------------------------------

    def create_lead_from_conversation(
        self,
        conversation_id: int,
        data: LeadFromConversationData,
    ) -> Party:
        """Create a lead (Party + PartyRole) from a conversation.

        Uses the Party system, NOT ERPNextLead (deprecated).

        Args:
            conversation_id: The conversation ID.
            data: Lead creation data.

        Returns:
            Created Party with lead role.

        Raises:
            NotFoundError: If conversation not found.
            ValidationError: If conversation already has a lead.
        """
        conv = self.db.query(OmniConversation).filter(
            OmniConversation.id == conversation_id
        ).first()

        if not conv:
            raise NotFoundError(f"Conversation {conversation_id} not found")

        # Check if already has a party/lead
        if conv.party_id:
            # Check if party already has lead role
            existing_lead = (
                self.db.query(PartyRole)
                .filter(PartyRole.party_id == conv.party_id)
                .filter(PartyRole.role == LEAD_ROLE)
                .filter(PartyRole.until.is_(None))
                .first()
            )
            if existing_lead:
                raise ValidationError("Conversation party is already a lead")

        # Create Party
        lead_name = data.lead_name or conv.contact_name or "Unknown"
        party = Party(
            type="person",
            status="active",
            name=lead_name,
            primary_email=conv.contact_email,
            primary_phone=conv.contact_phone,
            notes=data.notes or f"Created from inbox conversation #{conv.id}",
        )

        self.db.add(party)
        self.db.flush()

        # Create PartyRole with role='lead'
        role = PartyRole(
            party_id=party.id,
            role=LEAD_ROLE,
            status="active",
            source=data.source,
            source_campaign=f"conversation_{conv.id}",
            qualification=data.qualification,
            owner_party_id=data.owner_party_id,
        )

        self.db.add(role)
        self.db.flush()

        # Link conversation to party
        conv.party_id = party.id
        conv.updated_at = utc_now()

        return party

    def create_lead_from_ticket(
        self,
        ticket_id: int,
        data: LeadFromTicketData,
    ) -> Party:
        """Create a lead (Party + PartyRole) from a ticket.

        Uses the Party system, NOT ERPNextLead (deprecated).

        Args:
            ticket_id: The ticket ID.
            data: Lead creation data.

        Returns:
            Created Party with lead role.

        Raises:
            NotFoundError: If ticket not found.
            ValidationError: If ticket already has a lead.
        """
        ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()

        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")

        # Check if already has a party
        if ticket.party_id:
            # Check if party already has lead role
            existing_lead = (
                self.db.query(PartyRole)
                .filter(PartyRole.party_id == ticket.party_id)
                .filter(PartyRole.role == LEAD_ROLE)
                .filter(PartyRole.until.is_(None))
                .first()
            )
            if existing_lead:
                raise ValidationError("Ticket party is already a lead")

        # Create Party
        lead_name = data.lead_name or ticket.contact_name or "Unknown"
        party = Party(
            type="person",
            status="active",
            name=lead_name,
            primary_email=ticket.contact_email,
            notes=data.notes or f"Created from support ticket #{ticket.id}",
        )

        self.db.add(party)
        self.db.flush()

        # Create PartyRole with role='lead'
        role = PartyRole(
            party_id=party.id,
            role=LEAD_ROLE,
            status="active",
            source=data.source,
            source_campaign=f"ticket_{ticket.id}",
            qualification=data.qualification,
            owner_party_id=data.owner_party_id,
        )

        self.db.add(role)
        self.db.flush()

        # Link ticket to party
        ticket.party_id = party.id

        return party

    # -------------------------------------------------------------------------
    # Opportunity Creation from Support
    # -------------------------------------------------------------------------

    def create_opportunity_from_ticket(
        self,
        ticket_id: int,
        data: OpportunityFromTicketData,
    ) -> Opportunity:
        """Create an opportunity from a ticket.

        Args:
            ticket_id: The ticket ID.
            data: Opportunity creation data.

        Returns:
            Created Opportunity.

        Raises:
            NotFoundError: If ticket not found.
        """
        ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()

        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")

        # Create opportunity
        opp = Opportunity(
            name=data.opportunity_name or f"Opportunity from ticket #{ticket.id}: {ticket.subject}",
            party_id=ticket.party_id,
            status=OpportunityStatus.OPEN,
            stage_id=data.stage_id,
            deal_value=data.deal_value,
            expected_close_date=data.expected_close_date,
            source=data.source,
            owner_id=data.owner_id,
        )

        self.db.add(opp)
        self.db.flush()

        # Link ticket to opportunity via metadata
        if hasattr(ticket, 'metadata_'):
            metadata = ticket.metadata_ or {}
            linked_opps = metadata.get("linked_opportunities", [])
            linked_opps.append(opp.id)
            metadata["linked_opportunities"] = linked_opps
            ticket.metadata_ = metadata

        return opp

    # -------------------------------------------------------------------------
    # Party Enrichment
    # -------------------------------------------------------------------------

    def enrich_party_from_support_history(self, party_id: int) -> PartyEnrichment:
        """Enrich party data with support history.

        Args:
            party_id: The party ID.

        Returns:
            PartyEnrichment with support stats.

        Raises:
            NotFoundError: If party not found.
        """
        party = self.db.query(Party).filter(Party.id == party_id).first()
        if not party:
            raise NotFoundError(f"Party {party_id} not found")

        # Get ticket stats
        tickets = (
            self.db.query(Ticket)
            .filter(Ticket.party_id == party_id)
            .all()
        )

        total_tickets = len(tickets)
        open_tickets = len([t for t in tickets if t.status in (TicketStatus.OPEN, TicketStatus.PENDING)])
        resolved_tickets = len([t for t in tickets if t.status == TicketStatus.RESOLVED])

        # Get conversation count
        conv_count = (
            self.db.query(func.count(OmniConversation.id))
            .filter(OmniConversation.party_id == party_id)
            .scalar() or 0
        )

        # First and last contact
        first_ticket = min(tickets, key=lambda t: t.created_at, default=None) if tickets else None
        last_ticket = max(tickets, key=lambda t: t.created_at, default=None) if tickets else None

        # Collect tags
        all_tags = set()
        for t in tickets:
            if t.tags:
                all_tags.update(t.tags)

        return PartyEnrichment(
            party_id=party_id,
            ticket_count=total_tickets,
            open_ticket_count=open_tickets,
            resolved_ticket_count=resolved_tickets,
            avg_response_time_hours=None,  # Would need SLA data
            avg_resolution_time_hours=None,  # Would need SLA data
            satisfaction_score=None,  # Would need CSAT data
            first_contact_date=first_ticket.created_at if first_ticket else None,
            last_contact_date=last_ticket.created_at if last_ticket else None,
            total_conversations=conv_count,
            tags=list(all_tags),
        )

    def get_support_summary_for_party(self, party_id: int) -> SupportSummary:
        """Get support summary for a party.

        Args:
            party_id: The party ID.

        Returns:
            SupportSummary with stats.
        """
        tickets = (
            self.db.query(Ticket)
            .filter(Ticket.party_id == party_id)
            .order_by(Ticket.created_at.desc())
            .all()
        )

        open_count = len([t for t in tickets if t.status in (TicketStatus.OPEN, TicketStatus.PENDING)])
        resolved_count = len([t for t in tickets if t.status == TicketStatus.RESOLVED])

        recent = [
            {
                "id": t.id,
                "subject": t.subject,
                "status": t.status.value if hasattr(t.status, 'value') else str(t.status),
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tickets[:5]
        ]

        return SupportSummary(
            entity_type="party",
            entity_id=party_id,
            open_tickets=open_count,
            resolved_tickets=resolved_count,
            total_tickets=len(tickets),
            csat_avg=None,  # Would need CSAT service
            avg_response_time_hours=None,  # Would need SLA service
            recent_tickets=recent,
        )

    # -------------------------------------------------------------------------
    # Cross-module Search
    # -------------------------------------------------------------------------

    def search_related_entities(self, query: str, limit: int = 10) -> RelatedEntities:
        """Search across CRM and Support entities.

        Args:
            query: Search query.
            limit: Max results per entity type.

        Returns:
            RelatedEntities with search results.
        """
        like = f"%{query}%"

        # Search leads (Party with lead role)
        leads = (
            self.db.query(Party, PartyRole)
            .join(PartyRole, Party.id == PartyRole.party_id)
            .filter(PartyRole.role == LEAD_ROLE)
            .filter(PartyRole.until.is_(None))
            .filter(
                or_(
                    Party.name.ilike(like),
                    Party.primary_email.ilike(like),
                )
            )
            .limit(limit)
            .all()
        )

        lead_results = [
            {
                "id": p.id,
                "name": p.name,
                "email": p.primary_email,
                "status": r.status,
                "qualification": r.qualification,
            }
            for p, r in leads
        ]

        # Search opportunities
        opportunities = (
            self.db.query(Opportunity)
            .filter(Opportunity.name.ilike(like))
            .limit(limit)
            .all()
        )

        opp_results = [
            {
                "id": o.id,
                "name": o.name,
                "status": o.status.value,
                "deal_value": str(o.deal_value),
            }
            for o in opportunities
        ]

        # Search tickets
        tickets = (
            self.db.query(Ticket)
            .filter(
                or_(
                    Ticket.subject.ilike(like),
                    Ticket.contact_email.ilike(like),
                )
            )
            .limit(limit)
            .all()
        )

        ticket_results = [
            {
                "id": t.id,
                "subject": t.subject,
                "status": t.status.value if hasattr(t.status, 'value') else str(t.status),
            }
            for t in tickets
        ]

        # Search conversations
        conversations = (
            self.db.query(OmniConversation)
            .filter(
                or_(
                    OmniConversation.contact_name.ilike(like),
                    OmniConversation.contact_email.ilike(like),
                )
            )
            .limit(limit)
            .all()
        )

        conv_results = [
            {
                "id": c.id,
                "contact_name": c.contact_name,
                "contact_email": c.contact_email,
            }
            for c in conversations
        ]

        total = len(lead_results) + len(opp_results) + len(ticket_results) + len(conv_results)

        return RelatedEntities(
            query=query,
            leads=lead_results,
            opportunities=opp_results,
            tickets=ticket_results,
            conversations=conv_results,
            total_results=total,
        )
