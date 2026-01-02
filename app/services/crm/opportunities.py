"""Opportunity service - business logic for deal pipeline management.

This service encapsulates opportunity-related business logic:
- Core CRUD for opportunities
- Pipeline stage management
- Win/loss tracking
- Pipeline analytics

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.crm import Opportunity, OpportunityStage, OpportunityStatus
from app.services.base import paginate, scoped_query
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams

from .opportunity_types import (
    OpportunityFilters,
    OpportunityCreateData,
    OpportunityUpdateData,
    PipelineSummary,
    StageSummary,
)

if TYPE_CHECKING:
    from app.auth import Principal


class OpportunityService:
    """Service for opportunity (deal pipeline) management."""

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Opportunity CRUD
    # -------------------------------------------------------------------------

    def list_opportunities(
        self,
        filters: Optional[OpportunityFilters] = None,
        pagination: Optional[PaginationParams] = None,
        include_relations: bool = True,
    ) -> PaginatedResult[Opportunity]:
        """List opportunities with optional filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.
            include_relations: Whether to eagerly load stage and party.

        Returns:
            PaginatedResult containing opportunities and total count.
        """
        query = scoped_query(self.db.query(Opportunity), self.principal)

        if include_relations:
            query = query.options(
                joinedload(Opportunity.stage_rel),
                joinedload(Opportunity.party),
            )

        if filters:
            if filters.search:
                like = f"%{filters.search}%"
                query = query.filter(Opportunity.name.ilike(like))

            if filters.status:
                try:
                    status_enum = OpportunityStatus(filters.status.lower())
                    query = query.filter(Opportunity.status == status_enum)
                except ValueError:
                    pass

            if filters.stage_id:
                query = query.filter(Opportunity.stage_id == filters.stage_id)

            if filters.party_id:
                query = query.filter(Opportunity.party_id == filters.party_id)

            if filters.customer_id:
                query = query.filter(Opportunity.customer_id == filters.customer_id)

            if filters.owner_id:
                query = query.filter(Opportunity.owner_id == filters.owner_id)

            if filters.sales_person_id:
                query = query.filter(Opportunity.sales_person_id == filters.sales_person_id)

            if filters.min_value is not None:
                query = query.filter(Opportunity.deal_value >= filters.min_value)

            if filters.max_value is not None:
                query = query.filter(Opportunity.deal_value <= filters.max_value)

            if filters.expected_close_before:
                query = query.filter(Opportunity.expected_close_date <= filters.expected_close_before)

            if filters.expected_close_after:
                query = query.filter(Opportunity.expected_close_date >= filters.expected_close_after)

            if filters.campaign_id:
                query = query.filter(Opportunity.campaign_id == filters.campaign_id)

            if filters.source:
                query = query.filter(Opportunity.source == filters.source)

        query = query.order_by(Opportunity.created_at.desc())
        return paginate(query, pagination)

    def get_opportunity(self, opportunity_id: int, include_relations: bool = True) -> Opportunity:
        """Get an opportunity by ID.

        Args:
            opportunity_id: The opportunity ID.
            include_relations: Whether to eagerly load stage and party.

        Returns:
            The Opportunity.

        Raises:
            NotFoundError: If opportunity not found.
        """
        query = scoped_query(self.db.query(Opportunity), self.principal)

        if include_relations:
            query = query.options(
                joinedload(Opportunity.stage_rel),
                joinedload(Opportunity.party),
            )

        opp = query.filter(Opportunity.id == opportunity_id).first()
        if not opp:
            raise NotFoundError(f"Opportunity {opportunity_id} not found")

        return opp

    def create_opportunity(self, data: OpportunityCreateData) -> Opportunity:
        """Create a new opportunity.

        Args:
            data: Opportunity creation data.

        Returns:
            The created Opportunity (not yet committed).
        """
        opp = Opportunity(
            name=data.name,
            description=data.description,
            party_id=data.party_id,
            stage_id=data.stage_id,
            deal_value=data.deal_value,
            probability=data.probability,
            currency=data.currency,
            expected_close_date=data.expected_close_date,
            owner_id=data.owner_id,
            sales_person_id=data.sales_person_id,
            source=data.source,
            campaign=data.campaign,
            campaign_id=data.campaign_id,
            lead_id=data.lead_id,
            customer_id=data.customer_id,
            status=OpportunityStatus.OPEN,
        )

        # If stage has probability and none set, use stage probability
        if data.stage_id and not data.probability:
            stage = self.db.query(OpportunityStage).filter(
                OpportunityStage.id == data.stage_id
            ).first()
            if stage:
                opp.probability = stage.probability

        opp.update_weighted_value()
        self.db.add(opp)
        self.db.flush()

        return opp

    def update_opportunity(self, opportunity_id: int, data: OpportunityUpdateData) -> Opportunity:
        """Update an opportunity.

        Args:
            opportunity_id: The opportunity ID.
            data: Fields to update.

        Returns:
            The updated Opportunity (not yet committed).

        Raises:
            NotFoundError: If opportunity not found.
        """
        opp = self.get_opportunity(opportunity_id, include_relations=False)

        # Update simple fields
        simple_fields = [
            "name", "description", "party_id", "currency",
            "expected_close_date", "owner_id", "sales_person_id",
            "source", "campaign", "campaign_id", "lost_reason", "competitor",
        ]
        for field_name in simple_fields:
            value = getattr(data, field_name, None)
            if value is not None:
                setattr(opp, field_name, value)

        # Handle deal_value
        if data.deal_value is not None:
            opp.deal_value = data.deal_value

        # Handle probability - if stage changes without explicit probability, use stage probability
        if data.stage_id is not None and data.probability is None:
            stage = self.db.query(OpportunityStage).filter(
                OpportunityStage.id == data.stage_id
            ).first()
            if stage:
                opp.probability = stage.probability
            opp.stage_id = data.stage_id
        elif data.stage_id is not None:
            opp.stage_id = data.stage_id

        if data.probability is not None:
            opp.probability = data.probability

        opp.update_weighted_value()
        return opp

    def delete_opportunity(self, opportunity_id: int) -> None:
        """Delete an opportunity.

        Args:
            opportunity_id: The opportunity ID.

        Raises:
            NotFoundError: If opportunity not found.
        """
        opp = self.get_opportunity(opportunity_id, include_relations=False)
        self.db.delete(opp)

    # -------------------------------------------------------------------------
    # Pipeline Stage Operations
    # -------------------------------------------------------------------------

    def move_to_stage(self, opportunity_id: int, stage_id: int) -> Opportunity:
        """Move an opportunity to a different pipeline stage.

        Args:
            opportunity_id: The opportunity ID.
            stage_id: The target stage ID.

        Returns:
            The updated Opportunity (not yet committed).

        Raises:
            NotFoundError: If opportunity or stage not found.
        """
        opp = self.get_opportunity(opportunity_id, include_relations=False)

        stage = self.db.query(OpportunityStage).filter(
            OpportunityStage.id == stage_id
        ).first()
        if not stage:
            raise NotFoundError(f"Stage {stage_id} not found")

        opp.stage_id = stage_id
        opp.probability = stage.probability

        # If moving to won/lost stage, update status
        if stage.is_won:
            opp.status = OpportunityStatus.WON
            opp.actual_close_date = date.today()
        elif stage.is_lost:
            opp.status = OpportunityStatus.LOST
            opp.actual_close_date = date.today()

        opp.update_weighted_value()
        return opp

    def mark_won(self, opportunity_id: int) -> Opportunity:
        """Mark an opportunity as won.

        Args:
            opportunity_id: The opportunity ID.

        Returns:
            The updated Opportunity (not yet committed).

        Raises:
            NotFoundError: If opportunity not found.
        """
        opp = self.get_opportunity(opportunity_id, include_relations=False)

        opp.status = OpportunityStatus.WON
        opp.probability = 100
        opp.actual_close_date = date.today()
        opp.update_weighted_value()

        return opp

    def mark_lost(
        self,
        opportunity_id: int,
        reason: Optional[str] = None,
        competitor: Optional[str] = None,
    ) -> Opportunity:
        """Mark an opportunity as lost.

        Args:
            opportunity_id: The opportunity ID.
            reason: Optional lost reason.
            competitor: Optional competitor name.

        Returns:
            The updated Opportunity (not yet committed).

        Raises:
            NotFoundError: If opportunity not found.
        """
        opp = self.get_opportunity(opportunity_id, include_relations=False)

        opp.status = OpportunityStatus.LOST
        opp.probability = 0
        opp.actual_close_date = date.today()
        opp.lost_reason = reason
        opp.competitor = competitor
        opp.update_weighted_value()

        return opp

    # -------------------------------------------------------------------------
    # Pipeline Analytics
    # -------------------------------------------------------------------------

    def get_pipeline_summary(self) -> PipelineSummary:
        """Get pipeline summary with stage breakdown.

        Returns:
            PipelineSummary with stats and stage breakdown.
        """
        # Overall stats for open opportunities
        total = (
            self.db.query(func.count(Opportunity.id))
            .filter(Opportunity.status == OpportunityStatus.OPEN)
            .scalar() or 0
        )
        total_value = (
            self.db.query(func.sum(Opportunity.deal_value))
            .filter(Opportunity.status == OpportunityStatus.OPEN)
            .scalar() or Decimal("0")
        )
        weighted = (
            self.db.query(func.sum(Opportunity.weighted_value))
            .filter(Opportunity.status == OpportunityStatus.OPEN)
            .scalar() or Decimal("0")
        )

        # Won stats
        won_count = (
            self.db.query(func.count(Opportunity.id))
            .filter(Opportunity.status == OpportunityStatus.WON)
            .scalar() or 0
        )
        won_value = (
            self.db.query(func.sum(Opportunity.deal_value))
            .filter(Opportunity.status == OpportunityStatus.WON)
            .scalar() or Decimal("0")
        )

        # Lost stats
        lost_count = (
            self.db.query(func.count(Opportunity.id))
            .filter(Opportunity.status == OpportunityStatus.LOST)
            .scalar() or 0
        )

        # By stage breakdown
        stages = (
            self.db.query(OpportunityStage)
            .filter(OpportunityStage.is_active == True)
            .order_by(OpportunityStage.sequence)
            .all()
        )

        by_stage = []
        for stage in stages:
            count = (
                self.db.query(func.count(Opportunity.id))
                .filter(
                    Opportunity.stage_id == stage.id,
                    Opportunity.status == OpportunityStatus.OPEN,
                )
                .scalar() or 0
            )
            value = (
                self.db.query(func.sum(Opportunity.deal_value))
                .filter(
                    Opportunity.stage_id == stage.id,
                    Opportunity.status == OpportunityStatus.OPEN,
                )
                .scalar() or Decimal("0")
            )
            by_stage.append(StageSummary(
                stage_id=stage.id,
                stage_name=stage.name,
                color=stage.color,
                probability=stage.probability,
                count=count,
                value=value,
            ))

        # Calculate metrics
        closed_total = won_count + lost_count
        win_rate = (won_count / closed_total * 100) if closed_total > 0 else 0.0
        avg_deal = total_value / total if total > 0 else Decimal("0")

        return PipelineSummary(
            total_opportunities=total,
            total_value=total_value,
            weighted_value=weighted,
            won_count=won_count,
            won_value=won_value,
            lost_count=lost_count,
            by_stage=by_stage,
            avg_deal_size=avg_deal,
            win_rate=win_rate,
        )

    # -------------------------------------------------------------------------
    # Stage Management
    # -------------------------------------------------------------------------

    def list_stages(self, active_only: bool = True) -> List[OpportunityStage]:
        """List pipeline stages.

        Args:
            active_only: Only return active stages.

        Returns:
            List of OpportunityStage.
        """
        query = self.db.query(OpportunityStage)
        if active_only:
            query = query.filter(OpportunityStage.is_active == True)
        return query.order_by(OpportunityStage.sequence).all()

    def get_stage(self, stage_id: int) -> OpportunityStage:
        """Get a pipeline stage by ID.

        Args:
            stage_id: The stage ID.

        Returns:
            The OpportunityStage.

        Raises:
            NotFoundError: If stage not found.
        """
        stage = self.db.query(OpportunityStage).filter(
            OpportunityStage.id == stage_id
        ).first()
        if not stage:
            raise NotFoundError(f"Stage {stage_id} not found")
        return stage
