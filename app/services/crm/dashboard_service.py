"""Service layer for CRM dashboard analytics."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.crm import Activity, ActivityStatus, Opportunity, OpportunityStatus
from app.models.party import PartyRole


class CRMDashboardService:
    """Encapsulate CRM dashboard data queries."""

    def __init__(self, db: Session):
        self.db = db

    def get_active_lead_count(self) -> int:
        return (
            self.db.query(func.count(PartyRole.id))
            .filter(PartyRole.role == "lead", PartyRole.status == "active")
            .scalar()
            or 0
        )

    def get_open_opportunity_count(self) -> int:
        return (
            self.db.query(func.count(Opportunity.id))
            .filter(Opportunity.status == OpportunityStatus.OPEN)
            .scalar()
            or 0
        )

    def get_pipeline_value(self) -> Decimal:
        return (
            self.db.query(func.sum(Opportunity.deal_value))
            .filter(Opportunity.status == OpportunityStatus.OPEN)
            .scalar()
            or Decimal("0")
        )

    def get_today_activity_count(self, today: date) -> int:
        return (
            self.db.query(func.count(Activity.id))
            .filter(
                func.date(Activity.scheduled_at) == today,
            )
            .scalar()
            or 0
        )

    def get_won_stats(self, month_start: date) -> tuple[int, Decimal]:
        won_count = (
            self.db.query(func.count(Opportunity.id))
            .filter(
                Opportunity.status == OpportunityStatus.WON,
                Opportunity.actual_close_date >= month_start,
            )
            .scalar()
            or 0
        )
        won_value = (
            self.db.query(func.sum(Opportunity.deal_value))
            .filter(
                Opportunity.status == OpportunityStatus.WON,
                Opportunity.actual_close_date >= month_start,
            )
            .scalar()
            or Decimal("0")
        )
        return won_count, won_value

    def list_recent_activities(self, limit: int = 5) -> list[Activity]:
        return (
            self.db.query(Activity)
            .order_by(Activity.created_at.desc())
            .limit(limit)
            .all()
        )

    def list_upcoming_activities(self, since: datetime, limit: int = 5) -> list[Activity]:
        return (
            self.db.query(Activity)
            .filter(
                Activity.scheduled_at >= since,
                Activity.status == ActivityStatus.PLANNED,
            )
            .order_by(Activity.scheduled_at)
            .limit(limit)
            .all()
        )
