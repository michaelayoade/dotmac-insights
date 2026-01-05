"""Legacy conversation service for Chatwoot-backed conversations.

This service wraps database access for Conversation (legacy) records used in
the support web routes.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.conversation import Conversation, ConversationStatus
from app.models.party import CustomerAccount, Party
from app.models.unified_ticket import UnifiedTicket


class LegacyConversationService:
    """Service for legacy conversation listing and detail access."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_conversations(
        self,
        status: Optional[str] = None,
        channel: Optional[str] = None,
        search: Optional[str] = None,
        offset: int = 0,
        limit: int = 25,
    ) -> Tuple[List[Conversation], int]:
        """List conversations with filtering and pagination."""
        query = self.db.query(Conversation)

        if status:
            try:
                status_enum = ConversationStatus(status)
                query = query.filter(Conversation.status == status_enum)
            except ValueError:
                pass

        if channel:
            query = query.filter(Conversation.channel == channel)

        if search:
            search_term = f"%{search}%"
            query = query.filter(Conversation.subject.ilike(search_term))

        total = query.count()
        items = (
            query.order_by(Conversation.last_activity_at.desc().nullslast())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    def get_status_counts(self) -> Dict[str, int]:
        """Get conversation counts by status."""
        counts = {}
        for status in ConversationStatus:
            count = self.db.query(func.count(Conversation.id)).filter(
                Conversation.status == status
            ).scalar() or 0
            counts[status.value] = count
        return counts

    def list_channels(self) -> List[str]:
        """List distinct conversation channels."""
        channels = (
            self.db.query(Conversation.channel)
            .distinct()
            .filter(Conversation.channel.isnot(None))
            .all()
        )
        return [c[0] for c in channels if c[0]]

    def get_conversation(self, conversation_id: int) -> Optional[Conversation]:
        """Get a conversation by ID."""
        return self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()

    def get_ticket_map(self, ticket_ids: List[int]) -> Dict[int, UnifiedTicket]:
        """Get UnifiedTicket map for conversation ticket IDs."""
        if not ticket_ids:
            return {}
        tickets = self.db.query(UnifiedTicket).filter(
            UnifiedTicket.id.in_(ticket_ids)
        ).all()
        return {t.id: t for t in tickets}

    def get_customer_for_conversation(
        self,
        customer_account_id: Optional[int],
    ) -> Optional[CustomerAccount]:
        """Get customer account with party for a conversation."""
        if not customer_account_id:
            return None
        return (
            self.db.query(CustomerAccount)
            .join(Party, CustomerAccount.party_id == Party.id)
            .filter(CustomerAccount.id == customer_account_id)
            .first()
        )
