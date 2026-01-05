"""Contact Segmentation Service.

Provides business logic for managing contact segments:
- Static segments (manually curated)
- Dynamic segments (rule-based, auto-refreshing)
- Membership management
- Segment analytics
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Any

from sqlalchemy import select, func, and_, or_, case, text
from sqlalchemy.orm import Session, joinedload

from app.models.crm_engagement import ContactSegment, SegmentMembership
from app.models.party import Party

from .segment_types import (
    SegmentFilters,
    SegmentCreateData,
    SegmentUpdateData,
    SegmentRuleData,
    SegmentMembershipData,
    SegmentSummary,
    SegmentAnalytics,
    MembershipChange,
)


class SegmentService:
    """Service for contact segmentation operations."""

    def __init__(self, session: Session, company_id: int, user_id: int):
        self.session = session
        self.company_id = company_id
        self.user_id = user_id

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------

    def list_segments(
        self,
        filters: Optional[SegmentFilters] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[ContactSegment], int]:
        """List segments with optional filters."""
        query = select(ContactSegment).where(
            ContactSegment.company_id == self.company_id
        )

        if filters:
            if filters.search:
                search_term = f"%{filters.search}%"
                query = query.where(
                    or_(
                        ContactSegment.name.ilike(search_term),
                        ContactSegment.description.ilike(search_term),
                    )
                )

            if filters.segment_type:
                query = query.where(ContactSegment.segment_type == filters.segment_type)

            if filters.is_active is not None:
                query = query.where(ContactSegment.is_active == filters.is_active)

            if filters.created_by:
                query = query.where(ContactSegment.created_by == filters.created_by)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = self.session.execute(count_query).scalar() or 0

        # Fetch with pagination
        query = query.order_by(ContactSegment.name).offset(skip).limit(limit)
        segments = list(self.session.execute(query).scalars().all())

        # Filter by has_members if needed (post-filter since it requires count)
        if filters and filters.has_members is not None:
            filtered = []
            for seg in segments:
                count = self._get_member_count(seg.id)
                if filters.has_members and count > 0:
                    filtered.append(seg)
                elif not filters.has_members and count == 0:
                    filtered.append(seg)
            segments = filtered

        return segments, total

    def get_segment(self, segment_id: int) -> Optional[ContactSegment]:
        """Get a segment by ID."""
        query = select(ContactSegment).where(
            ContactSegment.id == segment_id,
            ContactSegment.company_id == self.company_id,
        )
        return self.session.execute(query).scalar_one_or_none()

    def create_segment(self, data: SegmentCreateData) -> ContactSegment:
        """Create a new segment."""
        segment = ContactSegment(
            company_id=self.company_id,
            name=data.name,
            description=data.description,
            segment_type=data.segment_type,
            rules=self._serialize_rules(data.rules) if data.rules else None,
            rule_conjunction=data.rule_conjunction,
            auto_refresh=data.auto_refresh,
            refresh_interval_hours=data.refresh_interval_hours,
            is_active=data.is_active,
            created_by=self.user_id,
        )
        self.session.add(segment)
        self.session.flush()

        # Add initial members for static segments
        if data.segment_type == "static" and data.party_ids:
            self._add_members(segment.id, data.party_ids, "creation")

        # For dynamic segments, run initial evaluation
        if data.segment_type == "dynamic" and data.rules:
            self.refresh_segment(segment.id)

        return segment

    def update_segment(
        self, segment_id: int, data: SegmentUpdateData
    ) -> Optional[ContactSegment]:
        """Update a segment."""
        segment = self.get_segment(segment_id)
        if not segment:
            return None

        if data.name is not None:
            segment.name = data.name
        if data.description is not None:
            segment.description = data.description
        if data.rules is not None:
            segment.rules = self._serialize_rules(data.rules)
        if data.rule_conjunction is not None:
            segment.rule_conjunction = data.rule_conjunction
        if data.auto_refresh is not None:
            segment.auto_refresh = data.auto_refresh
        if data.refresh_interval_hours is not None:
            segment.refresh_interval_hours = data.refresh_interval_hours
        if data.is_active is not None:
            segment.is_active = data.is_active

        segment.updated_at = datetime.utcnow()
        self.session.flush()

        # Re-evaluate dynamic segment if rules changed
        if data.rules is not None and segment.segment_type == "dynamic":
            self.refresh_segment(segment_id)

        return segment

    def delete_segment(self, segment_id: int) -> bool:
        """Delete a segment and its memberships."""
        segment = self.get_segment(segment_id)
        if not segment:
            return False

        # Delete memberships first
        self.session.execute(
            SegmentMembership.__table__.delete().where(
                SegmentMembership.segment_id == segment_id
            )
        )

        self.session.delete(segment)
        self.session.flush()
        return True

    # -------------------------------------------------------------------------
    # Membership Management
    # -------------------------------------------------------------------------

    def add_members(
        self, segment_id: int, data: SegmentMembershipData
    ) -> List[SegmentMembership]:
        """Add members to a segment."""
        segment = self.get_segment(segment_id)
        if not segment or segment.segment_type != "static":
            return []

        return self._add_members(segment_id, data.party_ids, data.source)

    def remove_members(
        self, segment_id: int, data: SegmentMembershipData
    ) -> int:
        """Remove members from a segment."""
        segment = self.get_segment(segment_id)
        if not segment or segment.segment_type != "static":
            return 0

        # Delete memberships
        result = self.session.execute(
            SegmentMembership.__table__.delete().where(
                SegmentMembership.segment_id == segment_id,
                SegmentMembership.party_id.in_(data.party_ids),
            )
        )
        self.session.flush()
        return result.rowcount

    def get_members(
        self,
        segment_id: int,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Party], int]:
        """Get members of a segment."""
        # Count total
        count_query = select(func.count(SegmentMembership.id)).where(
            SegmentMembership.segment_id == segment_id
        )
        total = self.session.execute(count_query).scalar() or 0

        # Get party IDs
        member_query = (
            select(SegmentMembership.party_id)
            .where(SegmentMembership.segment_id == segment_id)
            .order_by(SegmentMembership.added_at.desc())
            .offset(skip)
            .limit(limit)
        )
        party_ids = list(self.session.execute(member_query).scalars().all())

        if not party_ids:
            return [], total

        # Get parties
        parties_query = select(Party).where(Party.id.in_(party_ids))
        parties = list(self.session.execute(parties_query).scalars().all())

        return parties, total

    def is_member(self, segment_id: int, party_id: int) -> bool:
        """Check if a party is a member of a segment."""
        query = select(func.count(SegmentMembership.id)).where(
            SegmentMembership.segment_id == segment_id,
            SegmentMembership.party_id == party_id,
        )
        count = self.session.execute(query).scalar() or 0
        return count > 0

    def get_party_segments(self, party_id: int) -> List[ContactSegment]:
        """Get all segments a party belongs to."""
        query = (
            select(ContactSegment)
            .join(SegmentMembership)
            .where(
                SegmentMembership.party_id == party_id,
                ContactSegment.company_id == self.company_id,
            )
        )
        return list(self.session.execute(query).scalars().all())

    # -------------------------------------------------------------------------
    # Dynamic Segment Evaluation
    # -------------------------------------------------------------------------

    def refresh_segment(self, segment_id: int) -> int:
        """Refresh a dynamic segment by re-evaluating rules."""
        segment = self.get_segment(segment_id)
        if not segment or segment.segment_type != "dynamic":
            return 0

        rules = self._deserialize_rules(segment.rules)
        if not rules:
            return 0

        # Build query based on rules
        matching_party_ids = self._evaluate_rules(rules, segment.rule_conjunction)

        # Get current members
        current_query = select(SegmentMembership.party_id).where(
            SegmentMembership.segment_id == segment_id
        )
        current_ids = set(self.session.execute(current_query).scalars().all())

        new_ids = set(matching_party_ids)

        # Remove parties no longer matching
        to_remove = current_ids - new_ids
        if to_remove:
            self.session.execute(
                SegmentMembership.__table__.delete().where(
                    SegmentMembership.segment_id == segment_id,
                    SegmentMembership.party_id.in_(to_remove),
                )
            )

        # Add new matching parties
        to_add = new_ids - current_ids
        if to_add:
            self._add_members(segment_id, list(to_add), "dynamic_refresh")

        # Update segment refresh time
        segment.last_refreshed_at = datetime.utcnow()
        segment.next_refresh_at = datetime.utcnow() + timedelta(
            hours=segment.refresh_interval_hours
        )
        self.session.flush()

        return len(new_ids)

    def refresh_due_segments(self) -> int:
        """Refresh all dynamic segments that are due."""
        query = select(ContactSegment).where(
            ContactSegment.company_id == self.company_id,
            ContactSegment.segment_type == "dynamic",
            ContactSegment.auto_refresh == True,
            ContactSegment.is_active == True,
            or_(
                ContactSegment.next_refresh_at.is_(None),
                ContactSegment.next_refresh_at <= datetime.utcnow(),
            ),
        )
        segments = list(self.session.execute(query).scalars().all())

        refreshed = 0
        for segment in segments:
            self.refresh_segment(segment.id)
            refreshed += 1

        return refreshed

    def _evaluate_rules(
        self, rules: List[SegmentRuleData], conjunction: str
    ) -> List[int]:
        """Evaluate segment rules and return matching party IDs."""
        if not rules:
            return []

        conditions = []
        for rule in rules:
            condition = self._rule_to_condition(rule)
            if condition is not None:
                conditions.append(condition)

        if not conditions:
            return []

        # Combine conditions
        if conjunction == "OR":
            combined = or_(*conditions)
        else:
            combined = and_(*conditions)

        query = select(Party.id).where(
            Party.company_id == self.company_id,
            combined,
        )
        return list(self.session.execute(query).scalars().all())

    def _rule_to_condition(self, rule: SegmentRuleData) -> Any:
        """Convert a rule to a SQLAlchemy condition."""
        field_name = rule.field
        op = rule.operator
        value = rule.value

        # Get the column
        if not hasattr(Party, field_name):
            return None

        column = getattr(Party, field_name)

        # Apply operator
        if op == "equals":
            return column == value
        elif op == "not_equals":
            return column != value
        elif op == "contains":
            return column.ilike(f"%{value}%")
        elif op == "starts_with":
            return column.ilike(f"{value}%")
        elif op == "ends_with":
            return column.ilike(f"%{value}")
        elif op == "gt":
            return column > value
        elif op == "gte":
            return column >= value
        elif op == "lt":
            return column < value
        elif op == "lte":
            return column <= value
        elif op == "in":
            return column.in_(value if isinstance(value, list) else [value])
        elif op == "not_in":
            return ~column.in_(value if isinstance(value, list) else [value])
        elif op == "is_null":
            return column.is_(None)
        elif op == "is_not_null":
            return column.isnot(None)
        else:
            return None

    # -------------------------------------------------------------------------
    # Analytics
    # -------------------------------------------------------------------------

    def get_summary(self) -> SegmentSummary:
        """Get summary of all segments."""
        # Count segments by type
        query = select(
            func.count(ContactSegment.id).label("total"),
            func.sum(case((ContactSegment.is_active == True, 1), else_=0)).label(
                "active"
            ),
            func.sum(
                case((ContactSegment.segment_type == "static", 1), else_=0)
            ).label("static"),
            func.sum(
                case((ContactSegment.segment_type == "dynamic", 1), else_=0)
            ).label("dynamic"),
        ).where(ContactSegment.company_id == self.company_id)

        result = self.session.execute(query).one()

        # Count total members
        member_count_query = (
            select(func.count(SegmentMembership.id))
            .join(ContactSegment)
            .where(ContactSegment.company_id == self.company_id)
        )
        total_members = self.session.execute(member_count_query).scalar() or 0

        # Find largest segment
        largest_query = (
            select(
                ContactSegment.name,
                func.count(SegmentMembership.id).label("size"),
            )
            .join(SegmentMembership, isouter=True)
            .where(ContactSegment.company_id == self.company_id)
            .group_by(ContactSegment.id, ContactSegment.name)
            .order_by(func.count(SegmentMembership.id).desc())
            .limit(1)
        )
        largest = self.session.execute(largest_query).first()

        total = result.total or 0
        avg_size = total_members / total if total > 0 else 0.0

        return SegmentSummary(
            total_segments=total,
            active_segments=result.active or 0,
            static_segments=result.static or 0,
            dynamic_segments=result.dynamic or 0,
            total_members=total_members,
            avg_segment_size=avg_size,
            largest_segment_name=largest.name if largest else None,
            largest_segment_size=largest.size if largest else 0,
        )

    def get_segment_analytics(self, segment_id: int) -> Optional[SegmentAnalytics]:
        """Get analytics for a segment."""
        segment = self.get_segment(segment_id)
        if not segment:
            return None

        # Get member count
        member_count = self._get_member_count(segment_id)

        # Get member growth (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        growth_query = select(func.count(SegmentMembership.id)).where(
            SegmentMembership.segment_id == segment_id,
            SegmentMembership.added_at >= thirty_days_ago,
        )
        growth_30d = self.session.execute(growth_query).scalar() or 0

        # Get member parties for analysis
        member_query = (
            select(Party)
            .join(SegmentMembership)
            .where(SegmentMembership.segment_id == segment_id)
        )
        members = list(self.session.execute(member_query).scalars().all())

        # Calculate breakdowns
        party_type_breakdown: dict = {}
        channel_breakdown: dict = {}
        engagement_dist = {"low": 0, "medium": 0, "high": 0}
        total_engagement = 0
        with_email = 0
        with_phone = 0
        do_not_contact = 0

        for party in members:
            # Party type
            pt = party.party_type or "unknown"
            party_type_breakdown[pt] = party_type_breakdown.get(pt, 0) + 1

            # Preferred channel
            ch = party.preferred_channel or "none"
            channel_breakdown[ch] = channel_breakdown.get(ch, 0) + 1

            # Engagement score
            score = party.engagement_score or 0
            total_engagement += score
            if score < 30:
                engagement_dist["low"] += 1
            elif score < 70:
                engagement_dist["medium"] += 1
            else:
                engagement_dist["high"] += 1

            # Contact info
            if party.email:
                with_email += 1
            if party.phone:
                with_phone += 1
            if party.do_not_contact:
                do_not_contact += 1

        avg_engagement = total_engagement / len(members) if members else 0.0
        growth_rate = (growth_30d / member_count * 100) if member_count > 0 else 0.0

        return SegmentAnalytics(
            segment_id=segment_id,
            segment_name=segment.name,
            segment_type=segment.segment_type,
            member_count=member_count,
            member_growth_30d=growth_30d,
            member_growth_rate=growth_rate,
            party_type_breakdown=party_type_breakdown,
            engagement_score_distribution=engagement_dist,
            preferred_channel_breakdown=channel_breakdown,
            avg_engagement_score=avg_engagement,
            contacts_with_email=with_email,
            contacts_with_phone=with_phone,
            do_not_contact_count=do_not_contact,
            created_at=segment.created_at,
            last_refreshed_at=segment.last_refreshed_at,
            next_refresh_at=segment.next_refresh_at,
        )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_member_count(self, segment_id: int) -> int:
        """Get member count for a segment."""
        query = select(func.count(SegmentMembership.id)).where(
            SegmentMembership.segment_id == segment_id
        )
        return self.session.execute(query).scalar() or 0

    def _add_members(
        self, segment_id: int, party_ids: List[int], source: str
    ) -> List[SegmentMembership]:
        """Add members to a segment."""
        # Check which parties are already members
        existing_query = select(SegmentMembership.party_id).where(
            SegmentMembership.segment_id == segment_id,
            SegmentMembership.party_id.in_(party_ids),
        )
        existing = set(self.session.execute(existing_query).scalars().all())

        # Add new members
        new_members = []
        for party_id in party_ids:
            if party_id not in existing:
                membership = SegmentMembership(
                    segment_id=segment_id,
                    party_id=party_id,
                    added_by=self.user_id,
                    source=source,
                )
                self.session.add(membership)
                new_members.append(membership)

        self.session.flush()
        return new_members

    def _serialize_rules(self, rules: List[SegmentRuleData]) -> dict:
        """Serialize rules to JSON-compatible dict."""
        return {
            "rules": [
                {
                    "field": r.field,
                    "operator": r.operator,
                    "value": r.value,
                    "conjunction": r.conjunction,
                }
                for r in rules
            ]
        }

    def _deserialize_rules(self, data: Optional[dict]) -> List[SegmentRuleData]:
        """Deserialize rules from JSON."""
        if not data or "rules" not in data:
            return []

        return [
            SegmentRuleData(
                field=r["field"],
                operator=r["operator"],
                value=r["value"],
                conjunction=r.get("conjunction", "AND"),
            )
            for r in data["rules"]
        ]
