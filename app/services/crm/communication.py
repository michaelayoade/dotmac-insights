"""CRM Communication Service.

Provides business logic for proactive communications:
- Outreach scheduling and tracking
- Multi-channel communication (email, SMS, WhatsApp, calls)
- Contact preference management
- Communication analytics
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any

from sqlalchemy import select, func, and_, or_, case, update
from sqlalchemy.orm import Session

from app.models.crm_engagement import ProactiveCommunication
from app.models.party import Party

from .communication_types import (
    CommunicationFilters,
    CommunicationCreateData,
    CommunicationUpdateData,
    CommunicationScheduleData,
    CommunicationMetrics,
    CommunicationSummary,
    ChannelPerformance,
    ContactPreferences,
    BulkCommunicationResult,
)


class CRMCommunicationService:
    """Service for CRM communication operations."""

    def __init__(self, session: Session, company_id: int, user_id: int):
        self.session = session
        self.company_id = company_id
        self.user_id = user_id

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------

    def list_communications(
        self,
        filters: Optional[CommunicationFilters] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[ProactiveCommunication], int]:
        """List communications with optional filters."""
        query = select(ProactiveCommunication).where(
            ProactiveCommunication.company_id == self.company_id
        )

        if filters:
            if filters.search:
                search_term = f"%{filters.search}%"
                query = query.where(
                    or_(
                        ProactiveCommunication.subject.ilike(search_term),
                        ProactiveCommunication.content.ilike(search_term),
                    )
                )

            if filters.channel:
                query = query.where(ProactiveCommunication.channel == filters.channel)

            if filters.status:
                query = query.where(ProactiveCommunication.status == filters.status)

            if filters.party_id:
                query = query.where(
                    ProactiveCommunication.party_id == filters.party_id
                )

            if filters.campaign_id:
                query = query.where(
                    ProactiveCommunication.campaign_id == filters.campaign_id
                )

            if filters.sequence_id:
                query = query.where(
                    ProactiveCommunication.sequence_id == filters.sequence_id
                )

            if filters.created_after:
                query = query.where(
                    ProactiveCommunication.created_at >= filters.created_after
                )

            if filters.created_before:
                query = query.where(
                    ProactiveCommunication.created_at <= filters.created_before
                )

            if filters.sent_after:
                query = query.where(
                    ProactiveCommunication.sent_at >= filters.sent_after
                )

            if filters.sent_before:
                query = query.where(
                    ProactiveCommunication.sent_at <= filters.sent_before
                )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = self.session.execute(count_query).scalar() or 0

        # Fetch with pagination
        query = (
            query.order_by(ProactiveCommunication.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        communications = list(self.session.execute(query).scalars().all())

        return communications, total

    def get_communication(
        self, communication_id: int
    ) -> Optional[ProactiveCommunication]:
        """Get a communication by ID."""
        query = select(ProactiveCommunication).where(
            ProactiveCommunication.id == communication_id,
            ProactiveCommunication.company_id == self.company_id,
        )
        return self.session.execute(query).scalar_one_or_none()

    def create_communication(
        self, data: CommunicationCreateData
    ) -> ProactiveCommunication:
        """Create a new communication."""
        # Check contact preferences
        party = self._get_party(data.party_id)
        if party and party.do_not_contact:
            raise ValueError("Contact has opted out of communications")

        communication = ProactiveCommunication(
            company_id=self.company_id,
            party_id=data.party_id,
            channel=data.channel,
            communication_type=data.communication_type,
            subject=data.subject,
            content=data.content,
            template_id=data.template_id,
            scheduled_at=data.scheduled_at,
            campaign_id=data.campaign_id,
            sequence_id=data.sequence_id,
            opportunity_id=data.opportunity_id,
            personalization_data=data.personalization_data,
            priority=data.priority,
            track_opens=data.track_opens,
            track_clicks=data.track_clicks,
            status="pending" if data.scheduled_at else "ready",
            created_by=self.user_id,
        )
        self.session.add(communication)
        self.session.flush()

        return communication

    def update_communication(
        self, communication_id: int, data: CommunicationUpdateData
    ) -> Optional[ProactiveCommunication]:
        """Update a communication (only if not yet sent)."""
        communication = self.get_communication(communication_id)
        if not communication:
            return None

        if communication.status in ("sent", "delivered", "opened", "clicked"):
            raise ValueError("Cannot update communication that has already been sent")

        if data.subject is not None:
            communication.subject = data.subject
        if data.content is not None:
            communication.content = data.content
        if data.scheduled_at is not None:
            communication.scheduled_at = data.scheduled_at
        if data.priority is not None:
            communication.priority = data.priority
        if data.status is not None:
            communication.status = data.status

        communication.updated_at = datetime.utcnow()
        self.session.flush()

        return communication

    def delete_communication(self, communication_id: int) -> bool:
        """Delete a communication (only if not yet sent)."""
        communication = self.get_communication(communication_id)
        if not communication:
            return False

        if communication.status in ("sent", "delivered", "opened", "clicked"):
            raise ValueError("Cannot delete communication that has already been sent")

        self.session.delete(communication)
        self.session.flush()
        return True

    # -------------------------------------------------------------------------
    # Sending Operations
    # -------------------------------------------------------------------------

    def schedule_bulk(
        self, data: CommunicationScheduleData
    ) -> BulkCommunicationResult:
        """Schedule communications for multiple contacts."""
        scheduled_ids: List[int] = []
        skipped_do_not_contact: List[int] = []
        skipped_frequency_limit: List[int] = []
        skipped_no_contact: List[int] = []
        failures: List[Dict[str, Any]] = []

        for party_id in data.party_ids:
            party = self._get_party(party_id)
            if not party:
                skipped_no_contact.append(party_id)
                continue

            # Check do_not_contact
            if data.respect_preferences and party.do_not_contact:
                skipped_do_not_contact.append(party_id)
                continue

            # Check frequency limit
            if data.respect_frequency_limits and party.contact_frequency_limit:
                if self._exceeds_frequency_limit(party_id, party.contact_frequency_limit):
                    skipped_frequency_limit.append(party_id)
                    continue

            # Check contact info for channel
            if not self._has_contact_for_channel(party, data.channel):
                skipped_no_contact.append(party_id)
                continue

            try:
                comm = ProactiveCommunication(
                    company_id=self.company_id,
                    party_id=party_id,
                    channel=data.channel,
                    communication_type="outreach",
                    subject=data.subject,
                    content=data.content,
                    template_id=data.template_id,
                    scheduled_at=data.scheduled_at,
                    campaign_id=data.campaign_id,
                    status="pending" if data.scheduled_at else "ready",
                    created_by=self.user_id,
                )
                self.session.add(comm)
                self.session.flush()
                scheduled_ids.append(comm.id)
            except Exception as e:
                failures.append({"party_id": party_id, "error": str(e)})

        return BulkCommunicationResult(
            total_requested=len(data.party_ids),
            scheduled_count=len(scheduled_ids),
            skipped_do_not_contact=len(skipped_do_not_contact),
            skipped_frequency_limit=len(skipped_frequency_limit),
            skipped_no_contact_info=len(skipped_no_contact),
            failed_count=len(failures),
            scheduled_ids=scheduled_ids,
            skipped_party_ids=(
                skipped_do_not_contact + skipped_frequency_limit + skipped_no_contact
            ),
            failure_details=failures,
        )

    def mark_sent(self, communication_id: int) -> Optional[ProactiveCommunication]:
        """Mark a communication as sent."""
        communication = self.get_communication(communication_id)
        if not communication:
            return None

        communication.status = "sent"
        communication.sent_at = datetime.utcnow()

        # Update party's last_contacted_at
        self._update_last_contacted(communication.party_id)

        self.session.flush()
        return communication

    def mark_delivered(
        self, communication_id: int
    ) -> Optional[ProactiveCommunication]:
        """Mark a communication as delivered."""
        communication = self.get_communication(communication_id)
        if not communication:
            return None

        communication.status = "delivered"
        communication.delivered_at = datetime.utcnow()
        self.session.flush()
        return communication

    def record_open(self, communication_id: int) -> Optional[ProactiveCommunication]:
        """Record an open event."""
        communication = self.get_communication(communication_id)
        if not communication:
            return None

        if not communication.opened_at:
            communication.opened_at = datetime.utcnow()
            communication.status = "opened"

        communication.open_count = (communication.open_count or 0) + 1

        # Update party's last_engagement_at
        self._update_last_engagement(communication.party_id)

        self.session.flush()
        return communication

    def record_click(
        self, communication_id: int, link_url: Optional[str] = None
    ) -> Optional[ProactiveCommunication]:
        """Record a click event."""
        communication = self.get_communication(communication_id)
        if not communication:
            return None

        if not communication.clicked_at:
            communication.clicked_at = datetime.utcnow()
            communication.status = "clicked"

        communication.click_count = (communication.click_count or 0) + 1

        if link_url:
            links = communication.links_clicked or []
            if link_url not in links:
                links.append(link_url)
            communication.links_clicked = links

        # Update party's last_engagement_at
        self._update_last_engagement(communication.party_id)

        self.session.flush()
        return communication

    def record_reply(
        self, communication_id: int
    ) -> Optional[ProactiveCommunication]:
        """Record a reply to a communication."""
        communication = self.get_communication(communication_id)
        if not communication:
            return None

        communication.replied = True
        communication.reply_at = datetime.utcnow()

        # Update party's last_engagement_at
        self._update_last_engagement(communication.party_id)

        self.session.flush()
        return communication

    def mark_failed(
        self, communication_id: int, error: str
    ) -> Optional[ProactiveCommunication]:
        """Mark a communication as failed."""
        communication = self.get_communication(communication_id)
        if not communication:
            return None

        communication.status = "failed"
        communication.failure_reason = error
        self.session.flush()
        return communication

    # -------------------------------------------------------------------------
    # Analytics
    # -------------------------------------------------------------------------

    def get_summary(
        self, days: int = 30
    ) -> CommunicationSummary:
        """Get summary of communications."""
        since = datetime.utcnow() - timedelta(days=days)

        # Count by status
        status_query = (
            select(
                func.count(ProactiveCommunication.id).label("total"),
                func.sum(
                    case((ProactiveCommunication.status == "pending", 1), else_=0)
                ).label("pending"),
                func.sum(
                    case((ProactiveCommunication.status == "sent", 1), else_=0)
                ).label("sent"),
                func.sum(
                    case((ProactiveCommunication.status == "delivered", 1), else_=0)
                ).label("delivered"),
                func.sum(
                    case((ProactiveCommunication.status == "opened", 1), else_=0)
                ).label("opened"),
                func.sum(
                    case((ProactiveCommunication.status == "clicked", 1), else_=0)
                ).label("clicked"),
                func.sum(
                    case((ProactiveCommunication.status == "failed", 1), else_=0)
                ).label("failed"),
                func.sum(
                    case((ProactiveCommunication.replied == True, 1), else_=0)
                ).label("replied"),
            )
            .where(
                ProactiveCommunication.company_id == self.company_id,
                ProactiveCommunication.created_at >= since,
            )
        )
        result = self.session.execute(status_query).one()

        total = result.total or 0
        sent = (result.sent or 0) + (result.delivered or 0) + (result.opened or 0) + (result.clicked or 0)
        delivered = (result.delivered or 0) + (result.opened or 0) + (result.clicked or 0)

        # Calculate rates
        delivery_rate = (delivered / sent * 100) if sent > 0 else 0.0
        open_rate = ((result.opened or 0) + (result.clicked or 0)) / delivered * 100 if delivered > 0 else 0.0
        click_rate = (result.clicked or 0) / delivered * 100 if delivered > 0 else 0.0
        reply_rate = (result.replied or 0) / sent * 100 if sent > 0 else 0.0

        # Count by channel
        channel_query = (
            select(
                ProactiveCommunication.channel,
                ProactiveCommunication.status,
                func.count(ProactiveCommunication.id).label("count"),
            )
            .where(
                ProactiveCommunication.company_id == self.company_id,
                ProactiveCommunication.created_at >= since,
            )
            .group_by(ProactiveCommunication.channel, ProactiveCommunication.status)
        )
        channel_results = self.session.execute(channel_query).all()

        by_channel: Dict[str, Dict[str, int]] = {}
        for row in channel_results:
            if row.channel not in by_channel:
                by_channel[row.channel] = {}
            by_channel[row.channel][row.status] = row.count

        # Time-based counts
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        time_query = select(
            func.sum(
                case(
                    (ProactiveCommunication.sent_at >= today, 1),
                    else_=0,
                )
            ).label("today"),
            func.sum(
                case(
                    (ProactiveCommunication.sent_at >= week_ago, 1),
                    else_=0,
                )
            ).label("week"),
            func.sum(
                case(
                    (ProactiveCommunication.sent_at >= month_ago, 1),
                    else_=0,
                )
            ).label("month"),
        ).where(
            ProactiveCommunication.company_id == self.company_id,
            ProactiveCommunication.sent_at.isnot(None),
        )
        time_result = self.session.execute(time_query).one()

        return CommunicationSummary(
            total_communications=total,
            pending_count=result.pending or 0,
            sent_count=sent,
            delivered_count=delivered,
            opened_count=(result.opened or 0) + (result.clicked or 0),
            clicked_count=result.clicked or 0,
            failed_count=result.failed or 0,
            delivery_rate=delivery_rate,
            open_rate=open_rate,
            click_rate=click_rate,
            reply_rate=reply_rate,
            by_channel=by_channel,
            sent_today=time_result.today or 0,
            sent_this_week=time_result.week or 0,
            sent_this_month=time_result.month or 0,
            top_templates=[],  # Would need template join
            best_sending_times=[],  # Would need time analysis
        )

    def get_channel_performance(self, channel: str) -> ChannelPerformance:
        """Get performance metrics for a channel."""
        query = select(
            func.count(ProactiveCommunication.id).label("total"),
            func.sum(
                case(
                    (
                        ProactiveCommunication.status.in_(
                            ["delivered", "opened", "clicked"]
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("delivered"),
            func.sum(
                case(
                    (ProactiveCommunication.status.in_(["opened", "clicked"]), 1),
                    else_=0,
                )
            ).label("opened"),
            func.sum(
                case((ProactiveCommunication.status == "clicked", 1), else_=0)
            ).label("clicked"),
            func.sum(
                case((ProactiveCommunication.replied == True, 1), else_=0)
            ).label("replied"),
            func.sum(
                case((ProactiveCommunication.status == "failed", 1), else_=0)
            ).label("failed"),
        ).where(
            ProactiveCommunication.company_id == self.company_id,
            ProactiveCommunication.channel == channel,
            ProactiveCommunication.sent_at.isnot(None),
        )

        result = self.session.execute(query).one()

        total = result.total or 0
        delivered = result.delivered or 0
        opened = result.opened or 0
        clicked = result.clicked or 0
        replied = result.replied or 0
        failed = result.failed or 0

        return ChannelPerformance(
            channel=channel,
            total_sent=total,
            delivered=delivered,
            opened=opened,
            clicked=clicked,
            replied=replied,
            failed=failed,
            delivery_rate=(delivered / total * 100) if total > 0 else 0.0,
            open_rate=(opened / delivered * 100) if delivered > 0 else 0.0,
            click_rate=(clicked / delivered * 100) if delivered > 0 else 0.0,
            reply_rate=(replied / total * 100) if total > 0 else 0.0,
            failure_rate=(failed / total * 100) if total > 0 else 0.0,
            avg_time_to_open_minutes=None,  # Would need timestamp calculation
            best_day_of_week=None,
            best_hour_of_day=None,
            trend_vs_last_period=0.0,
        )

    def get_contact_preferences(self, party_id: int) -> Optional[ContactPreferences]:
        """Get communication preferences for a contact."""
        party = self._get_party(party_id)
        if not party:
            return None

        # Get communication history
        history_query = select(
            func.count(ProactiveCommunication.id).label("total"),
            func.sum(
                case(
                    (ProactiveCommunication.status.in_(["opened", "clicked"]), 1),
                    else_=0,
                )
            ).label("opened"),
            func.sum(
                case((ProactiveCommunication.status == "clicked", 1), else_=0)
            ).label("clicked"),
            func.sum(
                case((ProactiveCommunication.replied == True, 1), else_=0)
            ).label("replied"),
        ).where(
            ProactiveCommunication.party_id == party_id,
            ProactiveCommunication.sent_at.isnot(None),
        )
        history = self.session.execute(history_query).one()

        total = history.total or 0
        opened = history.opened or 0
        clicked = history.clicked or 0
        replied = history.replied or 0

        # Calculate days since contact
        days_since = None
        if party.last_contacted_at:
            delta = datetime.utcnow() - party.last_contacted_at
            days_since = delta.days

        return ContactPreferences(
            party_id=party_id,
            party_name=party.display_name or party.name or str(party_id),
            preferred_channel=party.preferred_channel,
            do_not_contact=party.do_not_contact,
            contact_frequency_limit=party.contact_frequency_limit,
            best_contact_time=None,
            responsive_channels=[],
            avg_response_time_hours=None,
            total_communications=total,
            last_contacted_at=party.last_contacted_at,
            last_response_at=party.last_engagement_at,
            days_since_contact=days_since,
            overall_open_rate=(opened / total * 100) if total > 0 else 0.0,
            overall_click_rate=(clicked / total * 100) if total > 0 else 0.0,
            overall_reply_rate=(replied / total * 100) if total > 0 else 0.0,
        )

    def get_communication_metrics(
        self, communication_id: int
    ) -> Optional[CommunicationMetrics]:
        """Get detailed metrics for a communication."""
        communication = self.get_communication(communication_id)
        if not communication:
            return None

        party = self._get_party(communication.party_id)
        party_name = ""
        if party:
            party_name = party.display_name or party.name or str(party.id)

        # Calculate time to open
        time_to_open = None
        if communication.sent_at and communication.opened_at:
            delta = communication.opened_at - communication.sent_at
            time_to_open = int(delta.total_seconds())

        return CommunicationMetrics(
            communication_id=communication_id,
            party_id=communication.party_id,
            party_name=party_name,
            channel=communication.channel,
            status=communication.status,
            created_at=communication.created_at,
            scheduled_at=communication.scheduled_at,
            sent_at=communication.sent_at,
            delivered_at=communication.delivered_at,
            opened_at=communication.opened_at,
            clicked_at=communication.clicked_at,
            open_count=communication.open_count or 0,
            click_count=communication.click_count or 0,
            links_clicked=communication.links_clicked or [],
            time_to_open_seconds=time_to_open,
            replied=communication.replied or False,
            reply_at=communication.reply_at,
            converted=communication.converted or False,
        )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_party(self, party_id: int) -> Optional[Party]:
        """Get a party by ID."""
        return self.session.execute(
            select(Party).where(
                Party.id == party_id,
                Party.company_id == self.company_id,
            )
        ).scalar_one_or_none()

    def _has_contact_for_channel(self, party: Party, channel: str) -> bool:
        """Check if party has contact info for channel."""
        if channel == "email":
            return bool(party.email)
        elif channel in ("sms", "whatsapp", "call"):
            return bool(party.phone)
        return True

    def _exceeds_frequency_limit(self, party_id: int, limit: int) -> bool:
        """Check if we've exceeded the contact frequency limit."""
        # Count communications in the last 30 days
        since = datetime.utcnow() - timedelta(days=30)
        count = self.session.execute(
            select(func.count(ProactiveCommunication.id)).where(
                ProactiveCommunication.party_id == party_id,
                ProactiveCommunication.sent_at >= since,
            )
        ).scalar() or 0

        return count >= limit

    def _update_last_contacted(self, party_id: int) -> None:
        """Update party's last_contacted_at."""
        self.session.execute(
            update(Party)
            .where(Party.id == party_id)
            .values(last_contacted_at=datetime.utcnow())
        )

    def _update_last_engagement(self, party_id: int) -> None:
        """Update party's last_engagement_at."""
        self.session.execute(
            update(Party)
            .where(Party.id == party_id)
            .values(last_engagement_at=datetime.utcnow())
        )
