"""Conversation service - business logic for omnichannel inbox conversations.

This service encapsulates conversation-related business logic:
- Core CRUD operations
- Status and priority management
- Assignment (agent/team)
- Tags and starring
- Integration (ticket, lead creation)

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence

from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.omni import (
    OmniChannel,
    OmniConversation,
    OmniMessage,
    OmniParticipant,
    InboxContact,
)
from app.models.agent import Team
from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.party import Party, PartyRole
from app.services.base import paginate
from app.services.types import PaginatedResult, PaginationParams
from app.services.validation.soft_validation_service import SoftValidationService

from .types import (
    ConversationFilters,
    ConversationCreate,
    ConversationUpdate,
    ConversationWithMessages,
    ConversationBulkUpdate,
    BulkOperationResult,
    InboxStats,
)
from .errors import (
    ConversationNotFoundError,
    ConversationClosedError,
    ConversationAssignmentError,
    ValidationError,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["ConversationService"]


class ConversationService:
    """Service for conversation business logic.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for audit fields).
    """

    # Allowed sort columns to prevent unintended column access
    ALLOWED_SORTS = {
        "last_message_at", "created_at", "updated_at", "subject",
        "priority", "status", "unread_count", "message_count",
    }

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def list(
        self,
        filters: Optional[ConversationFilters] = None,
        pagination: Optional[PaginationParams] = None,
        sort_by: str = "last_message_at",
        sort_order: str = "desc",
    ) -> PaginatedResult[OmniConversation]:
        """List conversations with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters (offset, limit).
            sort_by: Column to sort by.
            sort_order: Sort direction (asc/desc).

        Returns:
            PaginatedResult containing conversations and total count.
        """
        query = self.db.query(OmniConversation).options(
            joinedload(OmniConversation.channel),
            joinedload(OmniConversation.assigned_party),
            joinedload(OmniConversation.assigned_team),
        )

        if filters:
            query = self._apply_filters(query, filters)

        # Apply sorting - validate sort column against whitelist
        if sort_by not in self.ALLOWED_SORTS:
            sort_by = "last_message_at"
        if sort_order not in ("asc", "desc"):
            sort_order = "desc"

        sort_column = getattr(OmniConversation, sort_by, OmniConversation.last_message_at)
        if sort_order == "desc":
            query = query.order_by(sort_column.desc().nullslast())
        else:
            query = query.order_by(sort_column.asc().nullsfirst())

        return paginate(query, pagination)

    def _apply_filters(self, query, filters: ConversationFilters):
        """Apply filters to conversation query."""
        if filters.status:
            # Handle both enum and string values
            status_val = filters.status.value if hasattr(filters.status, 'value') else filters.status
            query = query.filter(OmniConversation.status == status_val)

        if filters.statuses:
            query = query.filter(OmniConversation.status.in_(filters.statuses))

        if filters.priority:
            # Handle both enum and string values
            priority_val = filters.priority.value if hasattr(filters.priority, 'value') else filters.priority
            query = query.filter(OmniConversation.priority == priority_val)

        if filters.channel_id:
            query = query.filter(OmniConversation.channel_id == filters.channel_id)

        if filters.channel_type:
            query = query.join(OmniChannel).filter(OmniChannel.type == filters.channel_type)

        if filters.assigned_agent_id:
            query = query.filter(OmniConversation.assigned_party_id == filters.assigned_agent_id)

        if filters.assigned_team_id:
            query = query.filter(OmniConversation.assigned_team_id == filters.assigned_team_id)

        if filters.unassigned_only:
            query = query.filter(
                OmniConversation.assigned_party_id.is_(None),
                OmniConversation.assigned_team_id.is_(None),
            )

        if filters.starred_only:
            query = query.filter(OmniConversation.is_starred == True)

        if filters.has_unread:
            query = query.filter(OmniConversation.unread_count > 0)

        if filters.party_id:
            query = query.filter(OmniConversation.party_id == filters.party_id)

        if filters.ticket_id:
            query = query.filter(OmniConversation.ticket_id == filters.ticket_id)

        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    OmniConversation.subject.ilike(search_term),
                    OmniConversation.contact_name.ilike(search_term),
                    OmniConversation.contact_email.ilike(search_term),
                )
            )

        if filters.tags:
            for tag in filters.tags:
                query = query.filter(OmniConversation.tags.contains([tag]))

        if filters.start_date:
            query = query.filter(OmniConversation.created_at >= filters.start_date)

        if filters.end_date:
            query = query.filter(OmniConversation.created_at <= filters.end_date)

        return query

    def get(self, conversation_id: int) -> OmniConversation:
        """Get a conversation by ID.

        Args:
            conversation_id: The conversation ID.

        Returns:
            OmniConversation instance.

        Raises:
            ConversationNotFoundError: If conversation not found.
        """
        conv = (
            self.db.query(OmniConversation)
            .options(
                joinedload(OmniConversation.channel),
                joinedload(OmniConversation.assigned_party),
                joinedload(OmniConversation.assigned_team),
            )
            .filter(OmniConversation.id == conversation_id)
            .first()
        )
        if not conv:
            raise ConversationNotFoundError(conversation_id)
        return conv

    def get_with_messages(
        self,
        conversation_id: int,
        message_limit: int = 50,
    ) -> ConversationWithMessages:
        """Get a conversation with its messages.

        Args:
            conversation_id: The conversation ID.
            message_limit: Maximum number of messages to include.

        Returns:
            ConversationWithMessages containing conversation and messages.

        Raises:
            ConversationNotFoundError: If conversation not found.
        """
        conv = self.get(conversation_id)

        messages = (
            self.db.query(OmniMessage)
            .options(selectinload(OmniMessage.attachments))
            .filter(OmniMessage.conversation_id == conversation_id)
            .order_by(OmniMessage.created_at.desc())
            .limit(message_limit + 1)
            .all()
        )

        has_more = len(messages) > message_limit
        if has_more:
            messages = messages[:message_limit]

        # Reverse to get chronological order
        messages = list(reversed(messages))

        total = (
            self.db.query(func.count(OmniMessage.id))
            .filter(OmniMessage.conversation_id == conversation_id)
            .scalar()
        ) or 0

        return ConversationWithMessages(
            conversation=conv,
            messages=messages,
            total_messages=total,
            has_more=has_more,
        )

    def get_stats(self, agent_id: Optional[int] = None) -> InboxStats:
        """Get inbox statistics.

        Args:
            agent_id: Optional agent ID for "my conversations" count.

        Returns:
            InboxStats with conversation counts.
        """
        base_query = self.db.query(func.count(OmniConversation.id))

        total = base_query.scalar() or 0

        open_count = (
            base_query.filter(OmniConversation.status == "open").scalar() or 0
        )

        pending_count = (
            base_query.filter(OmniConversation.status == "pending").scalar() or 0
        )

        resolved_count = (
            base_query.filter(OmniConversation.status == "resolved").scalar() or 0
        )

        unassigned_count = (
            base_query.filter(
                OmniConversation.assigned_party_id.is_(None),
                OmniConversation.assigned_team_id.is_(None),
                OmniConversation.status.in_(["open", "pending"]),
            ).scalar()
            or 0
        )

        unread_count = (
            base_query.filter(OmniConversation.unread_count > 0).scalar() or 0
        )

        snoozed_count = (
            base_query.filter(OmniConversation.status == "snoozed").scalar() or 0
        )

        my_conversations = 0
        if agent_id:
            my_conversations = (
                base_query.filter(
                    OmniConversation.assigned_party_id == agent_id,
                    OmniConversation.status.in_(["open", "pending"]),
                ).scalar()
                or 0
            )

        return InboxStats(
            total_conversations=total,
            open_conversations=open_count,
            pending_conversations=pending_count,
            resolved_conversations=resolved_count,
            unassigned_conversations=unassigned_count,
            my_conversations=my_conversations,
            unread_conversations=unread_count,
            snoozed_conversations=snoozed_count,
        )

    # -------------------------------------------------------------------------
    # Mutations
    # -------------------------------------------------------------------------

    def create(self, data: ConversationCreate) -> OmniConversation:
        """Create a new conversation.

        Args:
            data: Conversation creation data.

        Returns:
            Created OmniConversation instance.

        Raises:
            ValidationError: If channel_id is invalid.
        """
        # Validate channel exists
        channel = self.db.query(OmniChannel).filter(OmniChannel.id == data.channel_id).first()
        if not channel:
            raise ValidationError(f"Channel not found: {data.channel_id}")

        conv = OmniConversation(
            channel_id=data.channel_id,
            subject=data.subject,
            external_thread_id=data.external_thread_id,
            status=data.status,
            priority=data.priority,
            party_id=data.party_id,
            ticket_id=data.ticket_id,
            lead_id=data.lead_id,
            assigned_party_id=data.assigned_agent_id,
            assigned_team_id=data.assigned_team_id,
            contact_name=data.contact_name,
            contact_email=data.contact_email,
            contact_company=data.contact_company,
            tags=data.tags if data.tags else None,
            assigned_at=datetime.now(timezone.utc) if data.assigned_agent_id or data.assigned_team_id else None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(conv)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(conv)
        return conv

    def update(
        self,
        conversation_id: int,
        data: ConversationUpdate,
    ) -> OmniConversation:
        """Update a conversation.

        Args:
            conversation_id: The conversation ID.
            data: Update data.

        Returns:
            Updated OmniConversation instance.

        Raises:
            ConversationNotFoundError: If conversation not found.
        """
        conv = self.get(conversation_id)

        if data.subject is not None:
            conv.subject = data.subject

        if data.status is not None:
            conv.status = data.status
            if data.status == "resolved":
                conv.resolved_at = datetime.now(timezone.utc)
            elif data.status == "snoozed" and data.snoozed_until:
                conv.snoozed_until = data.snoozed_until

        if data.priority is not None:
            conv.priority = data.priority

        if data.is_starred is not None:
            conv.is_starred = data.is_starred

        if data.tags is not None:
            conv.tags = data.tags if data.tags else None

        if data.assigned_agent_id is not None:
            conv.assigned_party_id = data.assigned_agent_id if data.assigned_agent_id > 0 else None

        if data.assigned_team_id is not None:
            conv.assigned_team_id = data.assigned_team_id if data.assigned_team_id > 0 else None

        if data.party_id is not None:
            conv.party_id = data.party_id if data.party_id > 0 else None

        if data.ticket_id is not None:
            conv.ticket_id = data.ticket_id if data.ticket_id > 0 else None

        if data.lead_id is not None:
            conv.lead_id = data.lead_id if data.lead_id > 0 else None

        if data.contact_name is not None:
            conv.contact_name = data.contact_name

        if data.contact_email is not None:
            conv.contact_email = data.contact_email

        if data.contact_company is not None:
            conv.contact_company = data.contact_company

        if data.snoozed_until is not None:
            conv.snoozed_until = data.snoozed_until

        conv.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(conv)
        return conv

    def update_status(
        self,
        conversation_id: int,
        status: str,
        snoozed_until: Optional[datetime] = None,
    ) -> OmniConversation:
        """Update conversation status.

        Args:
            conversation_id: The conversation ID.
            status: New status value.
            snoozed_until: Snooze end time (required if status is 'snoozed').

        Returns:
            Updated OmniConversation instance.

        Raises:
            ConversationNotFoundError: If conversation not found.
        """
        conv = self.get(conversation_id)

        conv.status = status
        if status == "resolved":
            conv.resolved_at = datetime.now(timezone.utc)
        elif status == "snoozed" and snoozed_until:
            conv.snoozed_until = snoozed_until
        elif status == "open":
            # Reopening clears resolved/snoozed
            conv.resolved_at = None
            conv.snoozed_until = None

        conv.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(conv)
        return conv

    def star(self, conversation_id: int, starred: bool) -> OmniConversation:
        """Star or unstar a conversation.

        Args:
            conversation_id: The conversation ID.
            starred: Whether to star (True) or unstar (False).

        Returns:
            Updated OmniConversation instance.

        Raises:
            ConversationNotFoundError: If conversation not found.
        """
        conv = self.get(conversation_id)
        conv.is_starred = starred
        conv.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(conv)
        return conv

    def add_tag(self, conversation_id: int, tag: str) -> OmniConversation:
        """Add a tag to a conversation.

        Args:
            conversation_id: The conversation ID.
            tag: Tag to add.

        Returns:
            Updated OmniConversation instance.

        Raises:
            ConversationNotFoundError: If conversation not found.
        """
        conv = self.get(conversation_id)
        current_tags = list(conv.tags or [])
        if tag not in current_tags:
            current_tags.append(tag)
            conv.tags = current_tags
            conv.updated_at = datetime.now(timezone.utc)
            self.db.flush()
            SoftValidationService(self.db).validate_and_store(conv)
        return conv

    def remove_tag(self, conversation_id: int, tag: str) -> OmniConversation:
        """Remove a tag from a conversation.

        Args:
            conversation_id: The conversation ID.
            tag: Tag to remove.

        Returns:
            Updated OmniConversation instance.

        Raises:
            ConversationNotFoundError: If conversation not found.
        """
        conv = self.get(conversation_id)
        current_tags = list(conv.tags or [])
        if tag in current_tags:
            current_tags.remove(tag)
            conv.tags = current_tags if current_tags else None
            conv.updated_at = datetime.now(timezone.utc)
            self.db.flush()
            SoftValidationService(self.db).validate_and_store(conv)
        return conv

    # -------------------------------------------------------------------------
    # Assignment
    # -------------------------------------------------------------------------

    def assign(
        self,
        conversation_id: int,
        agent_id: Optional[int] = None,
        team_id: Optional[int] = None,
    ) -> OmniConversation:
        """Assign a conversation to an agent and/or team.

        Args:
            conversation_id: The conversation ID.
            agent_id: Agent ID to assign (None or 0 to unassign).
            team_id: Team ID to assign (None or 0 to unassign).

        Returns:
            Updated OmniConversation instance.

        Raises:
            ConversationNotFoundError: If conversation not found.
            ConversationAssignmentError: If agent or team not found.
        """
        conv = self.get(conversation_id)

        if agent_id is not None:
            if agent_id > 0:
                # agent_id is now party_id after Agent → Party unification
                agent = (
                    self.db.query(Party)
                    .join(PartyRole, PartyRole.party_id == Party.id)
                    .filter(
                        Party.id == agent_id,
                        PartyRole.role == "support_agent",
                    )
                    .first()
                )
                if not agent:
                    raise ConversationAssignmentError(f"Agent not found: {agent_id}")
                conv.assigned_party_id = agent_id
            else:
                conv.assigned_party_id = None

        if team_id is not None:
            if team_id > 0:
                team = self.db.query(Team).filter(Team.id == team_id).first()
                if not team:
                    raise ConversationAssignmentError(f"Team not found: {team_id}")
                conv.assigned_team_id = team_id
            else:
                conv.assigned_team_id = None

        if conv.assigned_party_id or conv.assigned_team_id:
            conv.assigned_at = datetime.now(timezone.utc)
        else:
            conv.assigned_at = None

        conv.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(conv)
        return conv

    def unassign(self, conversation_id: int) -> OmniConversation:
        """Remove all assignments from a conversation.

        Args:
            conversation_id: The conversation ID.

        Returns:
            Updated OmniConversation instance.

        Raises:
            ConversationNotFoundError: If conversation not found.
        """
        return self.assign(conversation_id, agent_id=0, team_id=0)

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def resolve(self, conversation_id: int) -> OmniConversation:
        """Mark a conversation as resolved.

        Args:
            conversation_id: The conversation ID.

        Returns:
            Updated OmniConversation instance.

        Raises:
            ConversationNotFoundError: If conversation not found.
        """
        return self.update_status(conversation_id, "resolved")

    def snooze(
        self,
        conversation_id: int,
        until: datetime,
    ) -> OmniConversation:
        """Snooze a conversation until a specific time.

        Args:
            conversation_id: The conversation ID.
            until: When the snooze should end.

        Returns:
            Updated OmniConversation instance.

        Raises:
            ConversationNotFoundError: If conversation not found.
        """
        return self.update_status(conversation_id, "snoozed", snoozed_until=until)

    def reopen(self, conversation_id: int) -> OmniConversation:
        """Reopen a resolved or snoozed conversation.

        Args:
            conversation_id: The conversation ID.

        Returns:
            Updated OmniConversation instance.

        Raises:
            ConversationNotFoundError: If conversation not found.
        """
        return self.update_status(conversation_id, "open")

    def archive(self, conversation_id: int) -> OmniConversation:
        """Archive (close) a conversation.

        Args:
            conversation_id: The conversation ID.

        Returns:
            Updated OmniConversation instance.

        Raises:
            ConversationNotFoundError: If conversation not found.
        """
        return self.update_status(conversation_id, "closed")

    # -------------------------------------------------------------------------
    # Integration
    # -------------------------------------------------------------------------

    def create_ticket(
        self,
        conversation_id: int,
        subject: Optional[str] = None,
        priority: str = "medium",
        category: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Ticket:
        """Create a support ticket from a conversation.

        Args:
            conversation_id: The conversation ID.
            subject: Ticket subject (defaults to conversation subject).
            priority: Ticket priority.
            category: Ticket category.
            description: Ticket description (defaults to conversation messages).

        Returns:
            Created Ticket instance.

        Raises:
            ConversationNotFoundError: If conversation not found.
            ValidationError: If conversation already has a ticket.
        """
        conv = self.get(conversation_id)

        if conv.ticket_id:
            raise ValidationError("Conversation already has a ticket")

        # Build description from messages if not provided
        if not description:
            messages_text = "\n\n".join([
                f"[{msg.direction}] {msg.body or ''}"
                for msg in sorted(conv.messages, key=lambda m: m.created_at)[:10]
            ])
            description = messages_text or "Created from inbox conversation"

        ticket = Ticket(
            subject=subject or conv.subject or "Support Request",
            description=description,
            status=TicketStatus.OPEN,
            priority=TicketPriority[priority.upper()],
            category=category,
            party_id=conv.party_id,
            contact_name=conv.contact_name,
            contact_email=conv.contact_email,
            source="inbox",
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(ticket)
        self.db.flush()

        # Link conversation to ticket
        conv.ticket_id = ticket.id
        conv.updated_at = datetime.now(timezone.utc)
        self.db.flush()

        return ticket

    def create_lead(
        self,
        conversation_id: int,
        lead_name: Optional[str] = None,
        company_name: Optional[str] = None,
        source: str = "inbox",
        notes: Optional[str] = None,
        qualification: Optional[str] = None,
        owner_party_id: Optional[int] = None,
    ) -> Party:
        """Create a sales lead from a conversation.

        Creates a Party entity with a PartyRole(role="lead"). This replaces
        the deprecated ERPNextLead approach - all leads are now Party entities.

        Args:
            conversation_id: The conversation ID.
            lead_name: Lead name (defaults to contact name).
            company_name: Company name (for organization-type parties).
            source: Lead source (e.g., "inbox", "website", "referral").
            notes: Lead notes.
            qualification: Lead qualification status.
            owner_party_id: Party ID of the sales rep owning this lead.

        Returns:
            Created Party instance with lead role.

        Raises:
            ConversationNotFoundError: If conversation not found.
            ValidationError: If conversation party is already a lead.
        """
        conv = self.get(conversation_id)

        # Check if party already exists and has lead role
        if conv.party_id:
            existing_lead_role = (
                self.db.query(PartyRole)
                .filter(PartyRole.party_id == conv.party_id)
                .filter(PartyRole.role == "lead")
                .filter(PartyRole.until.is_(None))
                .first()
            )
            if existing_lead_role:
                raise ValidationError("Conversation party is already a lead")

            # Party exists but no lead role - add lead role
            party = self.db.query(Party).filter(Party.id == conv.party_id).first()
            if party:
                role = PartyRole(
                    party_id=party.id,
                    role="lead",
                    status="active",
                    source=source,
                    source_campaign=f"conversation_{conv.id}",
                    qualification=qualification,
                    owner_party_id=owner_party_id,
                )
                self.db.add(role)
                self.db.flush()
                return party

        # Create new Party
        # Determine party type based on whether company_name is provided
        party_type = "organization" if company_name else "person"
        party_name = lead_name or conv.contact_name or "Unknown"

        party = Party(
            type=party_type,
            status="active",
            name=party_name if party_type == "person" else company_name,
            primary_email=conv.contact_email,
            primary_phone=conv.contact_phone if hasattr(conv, 'contact_phone') else None,
            notes=notes or f"Created from inbox conversation #{conv.id}",
        )
        self.db.add(party)
        self.db.flush()

        # Create PartyRole with role='lead'
        role = PartyRole(
            party_id=party.id,
            role="lead",
            status="active",
            source=source,
            source_campaign=f"conversation_{conv.id}",
            qualification=qualification,
            owner_party_id=owner_party_id,
        )
        self.db.add(role)
        self.db.flush()

        # Link conversation to party
        conv.party_id = party.id
        conv.updated_at = datetime.now(timezone.utc)
        self.db.flush()

        return party

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def bulk_update(self, data: ConversationBulkUpdate) -> BulkOperationResult:
        """Bulk update multiple conversations.

        Args:
            data: Bulk update data with IDs and fields to update.

        Returns:
            BulkOperationResult with counts and any failures.
        """
        result = BulkOperationResult()

        if not data.ids:
            return result

        for conv_id in data.ids:
            try:
                conv = self.db.query(OmniConversation).filter(OmniConversation.id == conv_id).first()
                if not conv:
                    result.failed_ids.append(conv_id)
                    result.errors.append(f"Conversation {conv_id} not found")
                    continue

                if data.status:
                    conv.status = data.status
                    if data.status == "resolved":
                        conv.resolved_at = datetime.now(timezone.utc)

                if data.priority:
                    conv.priority = data.priority

                if data.assigned_agent_id is not None:
                    conv.assigned_party_id = data.assigned_agent_id if data.assigned_agent_id > 0 else None

                if data.assigned_team_id is not None:
                    conv.assigned_team_id = data.assigned_team_id if data.assigned_team_id > 0 else None

                if data.add_tags:
                    current_tags = list(conv.tags or [])
                    for tag in data.add_tags:
                        if tag not in current_tags:
                            current_tags.append(tag)
                    conv.tags = current_tags

                if data.remove_tags:
                    current_tags = list(conv.tags or [])
                    for tag in data.remove_tags:
                        if tag in current_tags:
                            current_tags.remove(tag)
                    conv.tags = current_tags if current_tags else None

                conv.updated_at = datetime.now(timezone.utc)
                result.updated_count += 1

            except Exception as e:
                result.failed_ids.append(conv_id)
                result.errors.append(f"Error updating {conv_id}: {str(e)}")
                result.failed_count += 1

        self.db.flush()
        return result

    def bulk_assign(
        self,
        ids: List[int],
        agent_id: Optional[int] = None,
        team_id: Optional[int] = None,
    ) -> BulkOperationResult:
        """Bulk assign multiple conversations.

        Args:
            ids: List of conversation IDs.
            agent_id: Agent to assign to.
            team_id: Team to assign to.

        Returns:
            BulkOperationResult with counts.
        """
        data = ConversationBulkUpdate(
            ids=ids,
            assigned_agent_id=agent_id,
            assigned_team_id=team_id,
        )
        return self.bulk_update(data)

    def bulk_update_status(self, ids: List[int], status: str) -> BulkOperationResult:
        """Bulk update status for multiple conversations.

        Args:
            ids: List of conversation IDs.
            status: Status to set.

        Returns:
            BulkOperationResult with counts.
        """
        data = ConversationBulkUpdate(ids=ids, status=status)
        return self.bulk_update(data)

    # -------------------------------------------------------------------------
    # Read Tracking
    # -------------------------------------------------------------------------

    def mark_read(self, conversation_id: int) -> int:
        """Mark all messages in a conversation as read.

        Args:
            conversation_id: The conversation ID.

        Returns:
            Number of messages marked as read.

        Raises:
            ConversationNotFoundError: If conversation not found.
        """
        conv = self.get(conversation_id)

        # Reset unread count
        conv.unread_count = 0

        # Mark inbound messages as read
        now = datetime.now(timezone.utc)
        updated = (
            self.db.query(OmniMessage)
            .filter(
                OmniMessage.conversation_id == conversation_id,
                OmniMessage.direction == "inbound",
                OmniMessage.read_at.is_(None),
            )
            .update({"read_at": now})
        )

        conv.updated_at = now
        self.db.flush()
        return updated
