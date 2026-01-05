"""Customer Health Web Service - Sync service for web routes.

This service provides customer health analytics for the CRM web module.
Uses synchronous SQLAlchemy Session (matching other CRM services).

All methods are read-only queries. No commits needed.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.models.party import Party
from app.models.crm import Opportunity, OpportunityStatus

from .health_web_types import (
    HealthFilters,
    HealthGrade,
    ChurnRiskLevel,
    CustomerHealthSummary,
    HealthDistribution,
    ChurnRiskDistribution,
    CustomerHealthDashboard,
)

if TYPE_CHECKING:
    from app.auth import Principal


class CustomerHealthWebService:
    """Service for customer health analytics in web routes.

    Uses sync Session, matching other CRM services pattern.
    All methods are read-only queries. No commits needed.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    def get_customer_health_dashboard(
        self,
        filters: Optional[HealthFilters] = None,
    ) -> CustomerHealthDashboard:
        """Get complete customer health dashboard data.

        Args:
            filters: Optional filters for grade, risk level, etc.

        Returns:
            CustomerHealthDashboard with distribution and customer list.
        """
        filters = filters or HealthFilters()

        # Get all customers with health summaries
        customers = self._get_customer_health_summaries(filters)

        # Calculate distributions from full customer set (before filtering)
        all_customers = self._get_customer_health_summaries(HealthFilters(limit=1000))

        health_dist = self._calculate_health_distribution(all_customers)
        churn_dist = self._calculate_churn_distribution(all_customers)

        # Calculate average health score
        if customers:
            avg_score = sum(c.health_score for c in customers) / len(customers)
        else:
            avg_score = 0.0

        # Calculate revenue at risk (from high/critical churn risk customers)
        revenue_at_risk = sum(
            c.total_value
            for c in all_customers
            if c.churn_risk in (ChurnRiskLevel.HIGH, ChurnRiskLevel.CRITICAL)
        )

        return CustomerHealthDashboard(
            health_distribution=health_dist,
            churn_distribution=churn_dist,
            customers=customers,
            avg_health_score=avg_score,
            total_revenue_at_risk=revenue_at_risk,
        )

    def _get_customer_health_summaries(
        self,
        filters: HealthFilters,
    ) -> list[CustomerHealthSummary]:
        """Get customer health summaries with calculated scores.

        Args:
            filters: Filters to apply.

        Returns:
            List of CustomerHealthSummary sorted by health score (worst first).
        """
        # Get parties with opportunities
        parties_with_opps = (
            self.db.query(Party)
            .join(Opportunity, Opportunity.party_id == Party.id)
            .filter(Party.status != "deleted")
            .distinct()
            .limit(filters.limit)
            .all()
        )

        customers = []

        for party in parties_with_opps:
            summary = self._calculate_customer_health(party)

            # Apply grade filter
            if filters.grade and summary.health_grade != filters.grade:
                continue

            # Apply risk filter
            if filters.risk and summary.churn_risk != filters.risk:
                continue

            # Apply value filter
            if filters.min_value and summary.total_value < filters.min_value:
                continue

            customers.append(summary)

        # Sort by health score (worst first for intervention prioritization)
        customers.sort(key=lambda x: x.health_score)

        return customers

    def _calculate_customer_health(self, party: Party) -> CustomerHealthSummary:
        """Calculate health metrics for a single customer.

        Args:
            party: The Party model to calculate health for.

        Returns:
            CustomerHealthSummary with calculated metrics.
        """
        # Get opportunity stats
        total_opps = (
            self.db.query(func.count(Opportunity.id))
            .filter(Opportunity.party_id == party.id)
            .scalar() or 0
        )

        won_opps = (
            self.db.query(func.count(Opportunity.id))
            .filter(
                Opportunity.party_id == party.id,
                Opportunity.status == OpportunityStatus.WON
            )
            .scalar() or 0
        )

        lost_opps = (
            self.db.query(func.count(Opportunity.id))
            .filter(
                Opportunity.party_id == party.id,
                Opportunity.status == OpportunityStatus.LOST
            )
            .scalar() or 0
        )

        total_value = (
            self.db.query(func.sum(Opportunity.deal_value))
            .filter(
                Opportunity.party_id == party.id,
                Opportunity.status == OpportunityStatus.WON
            )
            .scalar() or Decimal("0")
        )

        # Get last activity date
        last_opp = (
            self.db.query(Opportunity.updated_at)
            .filter(Opportunity.party_id == party.id)
            .order_by(Opportunity.updated_at.desc())
            .first()
        )
        last_activity = last_opp[0] if last_opp else None

        # Calculate win rate
        win_rate = (won_opps / total_opps * 100) if total_opps > 0 else 0

        # Calculate health score and grade
        health_score, health_grade = self._calculate_health_score(
            total_opps=total_opps,
            won_opps=won_opps,
            lost_opps=lost_opps,
            win_rate=win_rate,
        )

        # Calculate churn risk
        churn_risk = self._calculate_churn_risk(
            won_opps=won_opps,
            lost_opps=lost_opps,
            win_rate=win_rate,
            last_activity=last_activity,
        )

        # Get display name from Party - use name, or construct from first/last, or fallback
        party_name = party.name or party.trading_name or party.legal_name
        if not party_name and (party.first_name or party.last_name):
            party_name = f"{party.first_name or ''} {party.last_name or ''}".strip()
        if not party_name:
            party_name = f"Customer {party.id}"

        return CustomerHealthSummary(
            party_id=party.id,
            party_name=party_name,
            health_score=health_score,
            health_grade=health_grade,
            churn_risk=churn_risk,
            total_opportunities=total_opps,
            won_opportunities=won_opps,
            lost_opportunities=lost_opps,
            win_rate=win_rate,
            total_value=total_value,
            last_activity_date=last_activity,
        )

    def _calculate_health_score(
        self,
        total_opps: int,
        won_opps: int,
        lost_opps: int,
        win_rate: float,
    ) -> tuple[int, HealthGrade]:
        """Calculate health score and grade.

        Health is based on:
        - Win rate (primary factor)
        - Total engagement (secondary factor)

        Args:
            total_opps: Total opportunities.
            won_opps: Won opportunities.
            lost_opps: Lost opportunities.
            win_rate: Win rate percentage.

        Returns:
            Tuple of (score, grade).
        """
        # Excellent: High win rate with multiple wins
        if win_rate >= 70 and won_opps >= 2:
            return 85, HealthGrade.EXCELLENT

        # Good: Decent win rate or high engagement
        if win_rate >= 50 or (total_opps >= 3 and won_opps > 0):
            return 65, HealthGrade.GOOD

        # At Risk: Has wins but not great
        if won_opps > 0:
            return 45, HealthGrade.AT_RISK

        # Critical: No wins or all lost
        return 25, HealthGrade.CRITICAL

    def _calculate_churn_risk(
        self,
        won_opps: int,
        lost_opps: int,
        win_rate: float,
        last_activity: Optional[datetime],
    ) -> ChurnRiskLevel:
        """Calculate churn risk level.

        Risk factors:
        - Multiple lost opportunities
        - Low win rate
        - Long inactivity

        Args:
            won_opps: Won opportunities.
            lost_opps: Lost opportunities.
            win_rate: Win rate percentage.
            last_activity: Last activity datetime.

        Returns:
            ChurnRiskLevel.
        """
        # Critical: Multiple losses, no wins
        if lost_opps >= 2 and won_opps == 0:
            return ChurnRiskLevel.CRITICAL

        # High: Losses with low win rate
        if lost_opps >= 1 and win_rate < 30:
            return ChurnRiskLevel.HIGH

        # Medium: Has losses but also wins
        if lost_opps > 0:
            return ChurnRiskLevel.MEDIUM

        # Low: No losses or good activity
        return ChurnRiskLevel.LOW

    def _calculate_health_distribution(
        self,
        customers: list[CustomerHealthSummary],
    ) -> HealthDistribution:
        """Calculate health grade distribution.

        Args:
            customers: List of customer summaries.

        Returns:
            HealthDistribution.
        """
        excellent = sum(1 for c in customers if c.health_grade == HealthGrade.EXCELLENT)
        good = sum(1 for c in customers if c.health_grade == HealthGrade.GOOD)
        at_risk = sum(1 for c in customers if c.health_grade == HealthGrade.AT_RISK)
        critical = sum(1 for c in customers if c.health_grade == HealthGrade.CRITICAL)

        return HealthDistribution(
            total=len(customers),
            excellent=excellent,
            good=good,
            at_risk=at_risk,
            critical=critical,
        )

    def _calculate_churn_distribution(
        self,
        customers: list[CustomerHealthSummary],
    ) -> ChurnRiskDistribution:
        """Calculate churn risk distribution.

        Args:
            customers: List of customer summaries.

        Returns:
            ChurnRiskDistribution.
        """
        low = sum(1 for c in customers if c.churn_risk == ChurnRiskLevel.LOW)
        medium = sum(1 for c in customers if c.churn_risk == ChurnRiskLevel.MEDIUM)
        high = sum(1 for c in customers if c.churn_risk == ChurnRiskLevel.HIGH)
        critical = sum(1 for c in customers if c.churn_risk == ChurnRiskLevel.CRITICAL)

        return ChurnRiskDistribution(
            low=low,
            medium=medium,
            high=high,
            critical=critical,
        )

    def get_customers_by_grade(
        self,
        grade: HealthGrade,
        limit: int = 50,
    ) -> list[CustomerHealthSummary]:
        """Get customers filtered by health grade.

        Args:
            grade: Health grade to filter by.
            limit: Maximum results.

        Returns:
            List of CustomerHealthSummary.
        """
        filters = HealthFilters(grade=grade, limit=limit)
        return self._get_customer_health_summaries(filters)

    def get_customers_by_risk(
        self,
        risk: ChurnRiskLevel,
        limit: int = 50,
    ) -> list[CustomerHealthSummary]:
        """Get customers filtered by churn risk level.

        Args:
            risk: Risk level to filter by.
            limit: Maximum results.

        Returns:
            List of CustomerHealthSummary.
        """
        filters = HealthFilters(risk=risk, limit=limit)
        return self._get_customer_health_summaries(filters)
