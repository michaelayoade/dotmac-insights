"""Campaign service - business logic for marketing campaign management.

This service encapsulates campaign-related business logic:
- Core CRUD for campaigns
- Lifecycle (activate, pause, complete)
- Attribution (leads and opportunities from campaign)
- ROI and performance analytics

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.crm import Campaign, Opportunity, OpportunityStatus
from app.models.party import PartyRole
from app.services.base import paginate, scoped_query
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams

from .campaign_types import (
    CampaignFilters,
    CampaignCreateData,
    CampaignUpdateData,
    CampaignROI,
    CampaignPerformance,
    CampaignSummary,
)

if TYPE_CHECKING:
    from app.auth import Principal


class CampaignService:
    """Service for marketing campaign management.

    All methods that mutate data do NOT commit.
    The caller is responsible for db.commit().
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Campaign CRUD
    # -------------------------------------------------------------------------

    def list_campaigns(
        self,
        filters: Optional[CampaignFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Campaign]:
        """List campaigns with optional filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.

        Returns:
            PaginatedResult containing campaigns and total count.
        """
        query = scoped_query(self.db.query(Campaign), self.principal)

        if filters:
            if filters.search:
                like = f"%{filters.search}%"
                query = query.filter(Campaign.name.ilike(like))

            if filters.campaign_type:
                query = query.filter(Campaign.campaign_type == filters.campaign_type)

            if filters.is_active is not None:
                query = query.filter(Campaign.is_active == filters.is_active)

            if filters.start_date_from:
                query = query.filter(Campaign.start_date >= filters.start_date_from)

            if filters.start_date_to:
                query = query.filter(Campaign.start_date <= filters.start_date_to)

            if filters.end_date_from:
                query = query.filter(Campaign.end_date >= filters.end_date_from)

            if filters.end_date_to:
                query = query.filter(Campaign.end_date <= filters.end_date_to)

            if filters.min_budget is not None:
                query = query.filter(Campaign.budget >= filters.min_budget)

            if filters.max_budget is not None:
                query = query.filter(Campaign.budget <= filters.max_budget)

        query = query.order_by(Campaign.created_at.desc())
        return paginate(query, pagination)

    def get_campaign(self, campaign_id: int) -> Campaign:
        """Get a campaign by ID.

        Args:
            campaign_id: The campaign ID.

        Returns:
            The Campaign.

        Raises:
            NotFoundError: If campaign not found.
        """
        campaign = (
            scoped_query(self.db.query(Campaign), self.principal)
            .filter(Campaign.id == campaign_id)
            .first()
        )

        if not campaign:
            raise NotFoundError(f"Campaign {campaign_id} not found")

        return campaign

    def create_campaign(self, data: CampaignCreateData) -> Campaign:
        """Create a new campaign.

        Args:
            data: Campaign creation data.

        Returns:
            The created Campaign (not yet committed).
        """
        campaign = Campaign(
            name=data.name,
            description=data.description,
            campaign_type=data.campaign_type,
            start_date=data.start_date,
            end_date=data.end_date,
            currency=data.currency,
            budget=data.budget,
            is_active=True,
        )

        self.db.add(campaign)
        self.db.flush()

        return campaign

    def update_campaign(self, campaign_id: int, data: CampaignUpdateData) -> Campaign:
        """Update a campaign.

        Args:
            campaign_id: The campaign ID.
            data: Fields to update.

        Returns:
            The updated Campaign (not yet committed).

        Raises:
            NotFoundError: If campaign not found.
        """
        campaign = self.get_campaign(campaign_id)

        # Update fields
        update_fields = [
            "name", "description", "campaign_type", "start_date",
            "end_date", "budget", "actual_cost", "is_active",
        ]
        for field_name in update_fields:
            value = getattr(data, field_name, None)
            if value is not None:
                setattr(campaign, field_name, value)

        return campaign

    def delete_campaign(self, campaign_id: int) -> None:
        """Delete a campaign.

        Args:
            campaign_id: The campaign ID.

        Raises:
            NotFoundError: If campaign not found.
        """
        campaign = self.get_campaign(campaign_id)
        self.db.delete(campaign)

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def activate_campaign(self, campaign_id: int) -> Campaign:
        """Activate a campaign.

        Args:
            campaign_id: The campaign ID.

        Returns:
            The updated Campaign.
        """
        campaign = self.get_campaign(campaign_id)
        campaign.is_active = True
        return campaign

    def pause_campaign(self, campaign_id: int) -> Campaign:
        """Pause/deactivate a campaign.

        Args:
            campaign_id: The campaign ID.

        Returns:
            The updated Campaign.
        """
        campaign = self.get_campaign(campaign_id)
        campaign.is_active = False
        return campaign

    def complete_campaign(self, campaign_id: int) -> Campaign:
        """Mark campaign as complete.

        Args:
            campaign_id: The campaign ID.

        Returns:
            The updated Campaign.
        """
        campaign = self.get_campaign(campaign_id)
        campaign.is_active = False
        if not campaign.end_date:
            campaign.end_date = date.today()

        # Update final metrics
        self._refresh_campaign_metrics(campaign)

        return campaign

    # -------------------------------------------------------------------------
    # Attribution
    # -------------------------------------------------------------------------

    def get_leads_by_campaign(self, campaign_id: int) -> List[PartyRole]:
        """Get leads attributed to a campaign.

        Args:
            campaign_id: The campaign ID.

        Returns:
            List of PartyRole (leads).
        """
        campaign = self.get_campaign(campaign_id)

        return (
            self.db.query(PartyRole)
            .filter(PartyRole.role == "lead")
            .filter(PartyRole.source_campaign == campaign.name)
            .filter(PartyRole.until.is_(None))
            .all()
        )

    def get_opportunities_by_campaign(self, campaign_id: int) -> List[Opportunity]:
        """Get opportunities attributed to a campaign.

        Args:
            campaign_id: The campaign ID.

        Returns:
            List of Opportunities.
        """
        return (
            self.db.query(Opportunity)
            .filter(Opportunity.campaign_id == campaign_id)
            .all()
        )

    # -------------------------------------------------------------------------
    # Analytics
    # -------------------------------------------------------------------------

    def get_campaign_roi(self, campaign_id: int) -> CampaignROI:
        """Calculate campaign ROI.

        Args:
            campaign_id: The campaign ID.

        Returns:
            CampaignROI with calculations.
        """
        campaign = self.get_campaign(campaign_id)

        # Refresh metrics first
        self._refresh_campaign_metrics(campaign)

        # Calculate ROI
        cost = campaign.actual_cost or campaign.budget
        revenue = campaign.revenue_generated or Decimal("0")

        if cost > 0:
            roi = float((revenue - cost) / cost * 100)
        else:
            roi = 0.0

        # Cost per lead
        leads = campaign.leads_generated or 0
        cost_per_lead = cost / leads if leads > 0 else Decimal("0")

        # Cost per opportunity
        opps = campaign.opportunities_generated or 0
        cost_per_opp = cost / opps if opps > 0 else Decimal("0")

        return CampaignROI(
            campaign_id=campaign_id,
            campaign_name=campaign.name,
            budget=campaign.budget,
            actual_cost=campaign.actual_cost or Decimal("0"),
            revenue_generated=revenue,
            roi_percentage=roi,
            cost_per_lead=cost_per_lead,
            cost_per_opportunity=cost_per_opp,
        )

    def get_campaign_performance(self, campaign_id: int) -> CampaignPerformance:
        """Get campaign performance metrics.

        Args:
            campaign_id: The campaign ID.

        Returns:
            CampaignPerformance with metrics.
        """
        campaign = self.get_campaign(campaign_id)

        # Get fresh counts
        leads = self.get_leads_by_campaign(campaign_id)
        opportunities = self.get_opportunities_by_campaign(campaign_id)

        leads_count = len(leads)
        opps_count = len(opportunities)
        won_opps = [o for o in opportunities if o.status == OpportunityStatus.WON]
        won_count = len(won_opps)
        revenue = sum(o.deal_value for o in won_opps)

        # Conversion rates
        conversion_rate = (opps_count / leads_count * 100) if leads_count > 0 else 0.0
        win_rate = (won_count / opps_count * 100) if opps_count > 0 else 0.0

        return CampaignPerformance(
            campaign_id=campaign_id,
            campaign_name=campaign.name,
            leads_generated=leads_count,
            opportunities_generated=opps_count,
            deals_won=won_count,
            revenue_generated=revenue,
            conversion_rate=conversion_rate,
            win_rate=win_rate,
        )

    def get_summary(self, filters: Optional[CampaignFilters] = None) -> CampaignSummary:
        """Get campaign summary statistics.

        Args:
            filters: Optional filters.

        Returns:
            CampaignSummary with aggregated stats.
        """
        base_query = scoped_query(self.db.query(Campaign), self.principal)

        if filters:
            if filters.start_date_from:
                base_query = base_query.filter(Campaign.start_date >= filters.start_date_from)
            if filters.start_date_to:
                base_query = base_query.filter(Campaign.start_date <= filters.start_date_to)

        total = base_query.count()
        active = base_query.filter(Campaign.is_active == True).count()

        # Totals
        totals = base_query.with_entities(
            func.sum(Campaign.budget),
            func.sum(Campaign.actual_cost),
            func.sum(Campaign.leads_generated),
            func.sum(Campaign.opportunities_generated),
            func.sum(Campaign.revenue_generated),
        ).first()

        total_budget = totals[0] or Decimal("0")
        total_spent = totals[1] or Decimal("0")
        total_leads = totals[2] or 0
        total_opportunities = totals[3] or 0
        total_revenue = totals[4] or Decimal("0")

        # Overall ROI
        if total_spent > 0:
            overall_roi = float((total_revenue - total_spent) / total_spent * 100)
        else:
            overall_roi = 0.0

        # By type
        type_counts = (
            base_query.with_entities(Campaign.campaign_type, func.count(Campaign.id))
            .group_by(Campaign.campaign_type)
            .all()
        )
        by_type = {t or "Unknown": cnt for t, cnt in type_counts}

        return CampaignSummary(
            total_campaigns=total,
            active_campaigns=active,
            total_budget=total_budget,
            total_spent=total_spent,
            total_leads=total_leads,
            total_opportunities=total_opportunities,
            total_revenue=total_revenue,
            overall_roi=overall_roi,
            by_type=by_type,
        )

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _refresh_campaign_metrics(self, campaign: Campaign) -> None:
        """Refresh campaign metrics from related entities.

        Args:
            campaign: The campaign to update.
        """
        # Count leads
        leads_count = (
            self.db.query(PartyRole)
            .filter(PartyRole.role == "lead")
            .filter(PartyRole.source_campaign == campaign.name)
            .count()
        )

        # Count opportunities and revenue
        opportunities = (
            self.db.query(Opportunity)
            .filter(Opportunity.campaign_id == campaign.id)
            .all()
        )

        opps_count = len(opportunities)
        won_opps = [o for o in opportunities if o.status == OpportunityStatus.WON]
        revenue = sum(o.deal_value for o in won_opps)

        # Update campaign
        campaign.leads_generated = leads_count
        campaign.opportunities_generated = opps_count
        campaign.revenue_generated = revenue
