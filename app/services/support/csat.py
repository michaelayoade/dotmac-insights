"""CSAT service - business logic for customer satisfaction surveys.

This service handles customer satisfaction management:
- Survey CRUD operations
- Response collection and tracking
- CSAT/NPS/CES metrics calculation

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import case, extract, func
from sqlalchemy.orm import Session

from app.models.support_csat import CSATResponse, CSATSurvey, SurveyTrigger, SurveyType

from .types import (
    CSATMetrics,
    CSATSurveyCreate,
    CSATSurveyUpdate,
)
from .errors import (
    CSATResponseNotFoundError,
    CSATSurveyNotFoundError,
    InvalidSurveyTokenError,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["CSATService"]


class CSATService:
    """Service for customer satisfaction survey management.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Survey Queries
    # -------------------------------------------------------------------------

    def list_surveys(
        self,
        survey_type: Optional[str] = None,
        active_only: bool = True,
    ) -> List[CSATSurvey]:
        """List CSAT surveys with optional filtering.

        Args:
            survey_type: Filter by survey type (csat, nps, ces).
            active_only: Only return active surveys.

        Returns:
            List of CSATSurvey instances.
        """
        query = self.db.query(CSATSurvey)

        if active_only:
            query = query.filter(CSATSurvey.is_active == True)

        if survey_type:
            query = query.filter(CSATSurvey.survey_type == survey_type)

        return query.order_by(CSATSurvey.name.asc()).all()

    def get_survey(self, survey_id: int) -> CSATSurvey:
        """Get a survey by ID.

        Args:
            survey_id: The survey ID.

        Returns:
            CSATSurvey instance.

        Raises:
            CSATSurveyNotFoundError: If not found.
        """
        survey = (
            self.db.query(CSATSurvey)
            .filter(CSATSurvey.id == survey_id)
            .first()
        )
        if not survey:
            raise CSATSurveyNotFoundError(survey_id)
        return survey

    def get_active_survey_for_trigger(
        self,
        trigger: str,
    ) -> Optional[CSATSurvey]:
        """Get the active survey for a specific trigger.

        Args:
            trigger: The trigger type (ticket_resolved, ticket_closed, manual).

        Returns:
            CSATSurvey instance or None.
        """
        return (
            self.db.query(CSATSurvey)
            .filter(
                CSATSurvey.trigger == trigger,
                CSATSurvey.is_active == True,
            )
            .first()
        )

    # -------------------------------------------------------------------------
    # Survey Mutations
    # -------------------------------------------------------------------------

    def create_survey(self, data: CSATSurveyCreate) -> CSATSurvey:
        """Create a new CSAT survey.

        Args:
            data: Survey creation data.

        Returns:
            Created CSATSurvey instance.
        """
        survey = CSATSurvey(
            name=data.name,
            survey_type=data.survey_type,
            trigger=data.trigger,
            questions=data.questions if data.questions else None,
            delay_hours=data.delay_hours,
            send_via=data.send_via,
            conditions=data.conditions if data.conditions else None,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        if self.principal:
            survey.created_by_id = getattr(self.principal, "id", None)

        self.db.add(survey)
        self.db.flush()
        return survey

    def update_survey(
        self,
        survey_id: int,
        data: CSATSurveyUpdate,
    ) -> CSATSurvey:
        """Update a CSAT survey.

        Args:
            survey_id: The survey ID.
            data: Update data.

        Returns:
            Updated CSATSurvey instance.

        Raises:
            CSATSurveyNotFoundError: If not found.
        """
        survey = self.get_survey(survey_id)

        if data.name is not None:
            survey.name = data.name

        if data.questions is not None:
            survey.questions = data.questions if data.questions else None

        if data.delay_hours is not None:
            survey.delay_hours = data.delay_hours

        if data.send_via is not None:
            survey.send_via = data.send_via

        if data.conditions is not None:
            survey.conditions = data.conditions if data.conditions else None

        if data.is_active is not None:
            survey.is_active = data.is_active

        survey.updated_at = datetime.now(timezone.utc)

        if self.principal:
            survey.updated_by_id = getattr(self.principal, "id", None)

        self.db.flush()
        return survey

    def activate_survey(self, survey_id: int) -> CSATSurvey:
        """Activate a survey.

        Args:
            survey_id: The survey ID.

        Returns:
            Updated CSATSurvey instance.
        """
        survey = self.get_survey(survey_id)
        survey.is_active = True
        survey.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return survey

    def deactivate_survey(self, survey_id: int) -> CSATSurvey:
        """Deactivate a survey.

        Args:
            survey_id: The survey ID.

        Returns:
            Updated CSATSurvey instance.
        """
        survey = self.get_survey(survey_id)
        survey.is_active = False
        survey.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return survey

    def delete_survey(self, survey_id: int) -> bool:
        """Delete a survey.

        Args:
            survey_id: The survey ID.

        Returns:
            True if deleted.

        Raises:
            CSATSurveyNotFoundError: If not found.
        """
        survey = self.get_survey(survey_id)
        self.db.delete(survey)
        self.db.flush()
        return True

    # -------------------------------------------------------------------------
    # Response Collection
    # -------------------------------------------------------------------------

    def send_survey(
        self,
        survey_id: int,
        ticket_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
        party_id: Optional[int] = None,
        agent_id: Optional[int] = None,
    ) -> str:
        """Create a pending survey response and return token.

        Args:
            survey_id: The survey ID.
            ticket_id: Optional ticket ID.
            conversation_id: Optional conversation ID.
            party_id: Optional party ID.
            agent_id: Optional agent ID who handled the ticket.

        Returns:
            Response token for the survey link.
        """
        # Verify survey exists
        self.get_survey(survey_id)

        # Generate unique token
        token = secrets.token_urlsafe(32)

        response = CSATResponse(
            survey_id=survey_id,
            ticket_id=ticket_id,
            chatwoot_conversation_id=conversation_id,
            party_id=party_id,
            agent_id=agent_id,
            response_token=token,
            sent_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(response)
        self.db.flush()

        return token

    def record_response(
        self,
        token: str,
        rating: int,
        answers: Optional[Dict] = None,
        feedback_text: Optional[str] = None,
        response_channel: Optional[str] = None,
    ) -> CSATResponse:
        """Record a customer's response to a survey.

        Args:
            token: The response token.
            rating: The rating value.
            answers: Optional answers to questions (keyed by question ID).
            feedback_text: Optional free-form feedback.
            response_channel: Channel used to respond (email, web, etc.).

        Returns:
            Updated CSATResponse instance.

        Raises:
            InvalidSurveyTokenError: If token is invalid or expired.
        """
        response = (
            self.db.query(CSATResponse)
            .filter(CSATResponse.response_token == token)
            .first()
        )
        if not response:
            raise InvalidSurveyTokenError(token)

        # Check if already responded
        if response.responded_at:
            raise InvalidSurveyTokenError(
                token,
                message="Survey has already been submitted",
            )

        response.rating = rating
        response.answers = answers if answers else None
        response.feedback_text = feedback_text
        response.response_channel = response_channel
        response.responded_at = datetime.now(timezone.utc)

        self.db.flush()
        return response

    def get_pending_responses(
        self,
        party_id: Optional[int] = None,
    ) -> List[CSATResponse]:
        """Get pending (not yet responded) survey responses.

        Args:
            party_id: Optional filter by party.

        Returns:
            List of CSATResponse instances.
        """
        query = self.db.query(CSATResponse).filter(
            CSATResponse.responded_at.is_(None),
        )

        if party_id:
            query = query.filter(CSATResponse.party_id == party_id)

        return query.order_by(CSATResponse.sent_at.desc()).all()

    # -------------------------------------------------------------------------
    # Response Queries
    # -------------------------------------------------------------------------

    def list_responses(
        self,
        survey_id: Optional[int] = None,
        agent_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        responded_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CSATResponse]:
        """List survey responses with optional filtering.

        Args:
            survey_id: Filter by survey.
            agent_id: Filter by agent.
            start_date: Filter by start date.
            end_date: Filter by end date.
            responded_only: Only include completed responses.
            limit: Maximum number of results.
            offset: Offset for pagination.

        Returns:
            List of CSATResponse instances.
        """
        query = self.db.query(CSATResponse)

        if responded_only:
            query = query.filter(CSATResponse.responded_at.isnot(None))

        if survey_id:
            query = query.filter(CSATResponse.survey_id == survey_id)

        if agent_id:
            query = query.filter(CSATResponse.agent_party_id == agent_id)

        if start_date:
            query = query.filter(CSATResponse.responded_at >= start_date)

        if end_date:
            query = query.filter(CSATResponse.responded_at <= end_date)

        query = query.order_by(CSATResponse.responded_at.desc())
        return query.offset(offset).limit(limit).all()

    def get_response(self, response_id: int) -> CSATResponse:
        """Get a response by ID.

        Args:
            response_id: The response ID.

        Returns:
            CSATResponse instance.

        Raises:
            CSATResponseNotFoundError: If not found.
        """
        response = (
            self.db.query(CSATResponse)
            .filter(CSATResponse.id == response_id)
            .first()
        )
        if not response:
            raise CSATResponseNotFoundError(response_id)
        return response

    def get_response_by_token(self, token: str) -> Optional[CSATResponse]:
        """Get a response by token.

        Args:
            token: The response token.

        Returns:
            CSATResponse instance or None.
        """
        return (
            self.db.query(CSATResponse)
            .filter(CSATResponse.response_token == token)
            .first()
        )

    def get_responses_for_ticket(self, ticket_id: int) -> List[CSATResponse]:
        """Get all responses for a ticket.

        Args:
            ticket_id: The ticket ID.

        Returns:
            List of CSATResponse instances.
        """
        return (
            self.db.query(CSATResponse)
            .filter(CSATResponse.ticket_id == ticket_id)
            .order_by(CSATResponse.created_at.desc())
            .all()
        )

    def get_responses_for_agent(
        self,
        agent_id: int,
        responded_only: bool = True,
    ) -> List[CSATResponse]:
        """Get all responses for an agent.

        Args:
            agent_id: The agent ID.
            responded_only: Only include completed responses.

        Returns:
            List of CSATResponse instances.
        """
        query = self.db.query(CSATResponse).filter(
            CSATResponse.agent_party_id == agent_id,
        )

        if responded_only:
            query = query.filter(CSATResponse.responded_at.isnot(None))

        return query.order_by(CSATResponse.responded_at.desc()).all()

    # -------------------------------------------------------------------------
    # Metrics
    # -------------------------------------------------------------------------

    def get_csat_score(
        self,
        agent_id: Optional[int] = None,
        team_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Optional[float]:
        """Calculate CSAT score (% of 4-5 ratings out of 5).

        Args:
            agent_id: Filter by agent.
            team_id: Filter by team (requires join with tickets).
            start_date: Filter by start date.
            end_date: Filter by end date.

        Returns:
            CSAT score as percentage (0-100) or None if no data.
        """
        query = (
            self.db.query(CSATResponse)
            .join(CSATSurvey)
            .filter(
                CSATSurvey.survey_type == SurveyType.CSAT.value,
                CSATResponse.rating.isnot(None),
            )
        )

        if agent_id:
            query = query.filter(CSATResponse.agent_party_id == agent_id)

        if start_date:
            query = query.filter(CSATResponse.responded_at >= start_date)

        if end_date:
            query = query.filter(CSATResponse.responded_at <= end_date)

        responses = query.all()

        if not responses:
            return None

        # CSAT: % of responses with rating 4 or 5 (out of 5-point scale)
        satisfied = sum(1 for r in responses if r.rating and r.rating >= 4)
        total = len(responses)

        return round((satisfied / total) * 100, 1) if total > 0 else None

    def get_nps_score(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Optional[float]:
        """Calculate NPS score (% promoters - % detractors).

        NPS scale is 0-10:
        - Promoters: 9-10
        - Passives: 7-8
        - Detractors: 0-6

        Args:
            start_date: Filter by start date.
            end_date: Filter by end date.

        Returns:
            NPS score (-100 to 100) or None if no data.
        """
        query = (
            self.db.query(CSATResponse)
            .join(CSATSurvey)
            .filter(
                CSATSurvey.survey_type == SurveyType.NPS.value,
                CSATResponse.rating.isnot(None),
            )
        )

        if start_date:
            query = query.filter(CSATResponse.responded_at >= start_date)

        if end_date:
            query = query.filter(CSATResponse.responded_at <= end_date)

        responses = query.all()

        if not responses:
            return None

        promoters = sum(1 for r in responses if r.rating and r.rating >= 9)
        detractors = sum(1 for r in responses if r.rating is not None and r.rating <= 6)
        total = len(responses)

        promoter_pct = (promoters / total) * 100 if total > 0 else 0
        detractor_pct = (detractors / total) * 100 if total > 0 else 0

        return round(promoter_pct - detractor_pct, 1)

    def get_ces_score(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Optional[float]:
        """Calculate average CES score (1-7 scale).

        Args:
            start_date: Filter by start date.
            end_date: Filter by end date.

        Returns:
            Average CES score (1-7) or None if no data.
        """
        query = (
            self.db.query(func.avg(CSATResponse.rating))
            .join(CSATSurvey)
            .filter(
                CSATSurvey.survey_type == SurveyType.CES.value,
                CSATResponse.rating.isnot(None),
            )
        )

        if start_date:
            query = query.filter(CSATResponse.responded_at >= start_date)

        if end_date:
            query = query.filter(CSATResponse.responded_at <= end_date)

        avg_score = query.scalar()
        return round(avg_score, 2) if avg_score else None

    def get_survey_metrics(self, survey_id: int) -> CSATMetrics:
        """Get comprehensive metrics for a survey.

        Args:
            survey_id: The survey ID.

        Returns:
            CSATMetrics instance.
        """
        survey = self.get_survey(survey_id)

        # Count total sent
        total_sent = (
            self.db.query(func.count(CSATResponse.id))
            .filter(CSATResponse.survey_id == survey_id)
            .scalar()
            or 0
        )

        # Count responded
        total_responded = (
            self.db.query(func.count(CSATResponse.id))
            .filter(
                CSATResponse.survey_id == survey_id,
                CSATResponse.responded_at.isnot(None),
            )
            .scalar()
            or 0
        )

        # Calculate response rate
        response_rate = (total_responded / total_sent * 100) if total_sent > 0 else 0.0

        # Calculate average rating
        avg_rating = (
            self.db.query(func.avg(CSATResponse.rating))
            .filter(
                CSATResponse.survey_id == survey_id,
                CSATResponse.rating.isnot(None),
            )
            .scalar()
        )
        avg_rating = round(avg_rating, 2) if avg_rating else 0.0

        # Calculate score based on survey type
        score = 0.0
        if survey.survey_type == SurveyType.CSAT.value:
            # CSAT: % of 4-5 ratings
            satisfied = (
                self.db.query(func.count(CSATResponse.id))
                .filter(
                    CSATResponse.survey_id == survey_id,
                    CSATResponse.rating >= 4,
                )
                .scalar()
                or 0
            )
            score = (satisfied / total_responded * 100) if total_responded > 0 else 0.0
        elif survey.survey_type == SurveyType.NPS.value:
            # NPS: promoters - detractors
            promoters = (
                self.db.query(func.count(CSATResponse.id))
                .filter(
                    CSATResponse.survey_id == survey_id,
                    CSATResponse.rating >= 9,
                )
                .scalar()
                or 0
            )
            detractors = (
                self.db.query(func.count(CSATResponse.id))
                .filter(
                    CSATResponse.survey_id == survey_id,
                    CSATResponse.rating <= 6,
                )
                .scalar()
                or 0
            )
            promoter_pct = (promoters / total_responded * 100) if total_responded > 0 else 0
            detractor_pct = (detractors / total_responded * 100) if total_responded > 0 else 0
            score = promoter_pct - detractor_pct
        elif survey.survey_type == SurveyType.CES.value:
            # CES: average score
            score = avg_rating

        # Get rating distribution
        rating_distribution: Dict[int, int] = {}
        ratings = (
            self.db.query(CSATResponse.rating, func.count(CSATResponse.id))
            .filter(
                CSATResponse.survey_id == survey_id,
                CSATResponse.rating.isnot(None),
            )
            .group_by(CSATResponse.rating)
            .all()
        )
        for rating, count in ratings:
            if rating is not None:
                rating_distribution[rating] = count

        return CSATMetrics(
            survey_id=survey_id,
            total_sent=total_sent,
            total_responded=total_responded,
            response_rate=round(response_rate, 1),
            avg_rating=avg_rating,
            score=round(score, 1),
            rating_distribution=rating_distribution,
        )

    def get_agent_csat_score(
        self,
        agent_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Optional[float]:
        """Get CSAT score for a specific agent.

        Args:
            agent_id: The agent ID.
            start_date: Filter by start date.
            end_date: Filter by end date.

        Returns:
            CSAT score as percentage or None.
        """
        return self.get_csat_score(
            agent_id=agent_id,
            start_date=start_date,
            end_date=end_date,
        )

    # -------------------------------------------------------------------------
    # Reporting Helpers
    # -------------------------------------------------------------------------

    def get_survey_stats(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
    ) -> Dict[int, Dict[str, float]]:
        """Get per-survey stats for a date range."""
        query = self.db.query(
            CSATResponse.survey_id.label("survey_id"),
            func.count(CSATResponse.id).label("total"),
            func.avg(CSATResponse.rating).label("avg_rating"),
            func.sum(case((CSATResponse.rating >= 4, 1), else_=0)).label("positive"),
        ).filter(
            CSATResponse.responded_at >= start_date,
            CSATResponse.rating.isnot(None),
        )

        if end_date:
            query = query.filter(CSATResponse.responded_at <= end_date)

        rows = query.group_by(CSATResponse.survey_id).all()
        return {
            row.survey_id: {
                "total": row.total or 0,
                "avg_rating": round(float(row.avg_rating or 0), 2),
                "positive": row.positive or 0,
            }
            for row in rows
        }

    def get_overall_stats(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, float]:
        """Get overall response stats for a date range."""
        query = self.db.query(
            func.count(CSATResponse.id).label("total"),
            func.avg(CSATResponse.rating).label("avg_rating"),
            func.sum(case((CSATResponse.rating >= 4, 1), else_=0)).label("positive"),
            func.sum(case((CSATResponse.rating <= 2, 1), else_=0)).label("negative"),
        ).filter(
            CSATResponse.responded_at >= start_date,
            CSATResponse.rating.isnot(None),
        )

        if end_date:
            query = query.filter(CSATResponse.responded_at <= end_date)

        stats = query.first()
        return {
            "total": stats.total if stats else 0,
            "avg_rating": round(float(stats.avg_rating or 0), 2) if stats else 0,
            "positive": stats.positive or 0 if stats else 0,
            "negative": stats.negative or 0 if stats else 0,
        }

    def get_response_counts(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """Get sent vs responded counts for a date range."""
        sent_query = self.db.query(func.count(CSATResponse.id)).filter(
            CSATResponse.sent_at >= start_date
        )
        responded_query = self.db.query(func.count(CSATResponse.id)).filter(
            CSATResponse.responded_at >= start_date
        )

        if end_date:
            sent_query = sent_query.filter(CSATResponse.sent_at <= end_date)
            responded_query = responded_query.filter(CSATResponse.responded_at <= end_date)

        return {
            "sent": sent_query.scalar() or 0,
            "responded": responded_query.scalar() or 0,
        }

    def get_survey_period_stats(
        self,
        survey_id: int,
        start_date: datetime,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get per-survey stats and rating distribution for a date range."""
        stats_query = self.db.query(
            func.count(CSATResponse.id).label("total"),
            func.avg(CSATResponse.rating).label("avg_rating"),
            func.sum(case((CSATResponse.rating >= 4, 1), else_=0)).label("positive"),
            func.sum(case((CSATResponse.rating <= 2, 1), else_=0)).label("negative"),
        ).filter(
            CSATResponse.survey_id == survey_id,
            CSATResponse.responded_at >= start_date,
            CSATResponse.rating.isnot(None),
        )

        if end_date:
            stats_query = stats_query.filter(CSATResponse.responded_at <= end_date)

        stats = stats_query.first()

        rating_query = self.db.query(
            CSATResponse.rating,
            func.count(CSATResponse.id).label("count"),
        ).filter(
            CSATResponse.survey_id == survey_id,
            CSATResponse.responded_at >= start_date,
            CSATResponse.rating.isnot(None),
        )
        if end_date:
            rating_query = rating_query.filter(CSATResponse.responded_at <= end_date)

        rating_dist_rows = rating_query.group_by(CSATResponse.rating).all()
        rating_distribution = {row.rating: row.count for row in rating_dist_rows}

        return {
            "total": stats.total if stats else 0,
            "avg_rating": round(float(stats.avg_rating or 0), 2) if stats else 0,
            "positive": stats.positive or 0 if stats else 0,
            "negative": stats.negative or 0 if stats else 0,
            "rating_distribution": rating_distribution,
        }

    def list_recent_feedback(
        self,
        start_date: datetime,
        limit: int = 20,
    ) -> List[CSATResponse]:
        """List recent feedback comments within a date range."""
        return (
            self.db.query(CSATResponse)
            .filter(
                CSATResponse.responded_at >= start_date,
                CSATResponse.feedback_text.isnot(None),
                CSATResponse.feedback_text != "",
            )
            .order_by(CSATResponse.responded_at.desc())
            .limit(limit)
            .all()
        )

    def get_trends(
        self,
        start_date: datetime,
    ) -> List[Dict[str, Any]]:
        """Get monthly CSAT trends since a start date."""
        rows = (
            self.db.query(
                extract("year", CSATResponse.responded_at).label("year"),
                extract("month", CSATResponse.responded_at).label("month"),
                func.count(CSATResponse.id).label("count"),
                func.avg(CSATResponse.rating).label("avg_rating"),
            )
            .filter(
                CSATResponse.responded_at >= start_date,
                CSATResponse.rating.isnot(None),
            )
            .group_by(
                extract("year", CSATResponse.responded_at),
                extract("month", CSATResponse.responded_at),
            )
            .order_by(
                extract("year", CSATResponse.responded_at),
                extract("month", CSATResponse.responded_at),
            )
            .all()
        )

        return [
            {
                "year": int(r.year),
                "month": int(r.month),
                "count": r.count,
                "avg_rating": round(float(r.avg_rating or 0), 2),
            }
            for r in rows
        ]

    def get_agent_stats(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get CSAT stats grouped by agent."""
        from app.models.party import Party, PartyRole

        query = (
            self.db.query(
                CSATResponse.agent_party_id,
                Party.name.label("display_name"),
                func.count(CSATResponse.id).label("count"),
                func.avg(CSATResponse.rating).label("avg_rating"),
                func.sum(case((CSATResponse.rating >= 4, 1), else_=0)).label("positive"),
            )
            .join(Party, Party.id == CSATResponse.agent_party_id, isouter=True)
            .join(PartyRole, Party.id == PartyRole.party_id, isouter=True)
            .filter(
                CSATResponse.responded_at >= start_date,
                CSATResponse.rating.isnot(None),
                CSATResponse.agent_party_id.isnot(None),
            )
            .group_by(CSATResponse.agent_party_id, Party.name)
            .order_by(func.avg(CSATResponse.rating).desc())
        )

        if end_date:
            query = query.filter(CSATResponse.responded_at <= end_date)

        rows = query.all()
        return [
            {
                "agent_id": r.agent_party_id,
                "agent_name": r.display_name or "Unknown",
                "count": r.count,
                "avg_rating": round(float(r.avg_rating or 0), 2),
                "positive": r.positive or 0,
            }
            for r in rows
        ]

    def get_type_stats(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get CSAT stats grouped by survey type."""
        query = (
            self.db.query(
                CSATSurvey.survey_type,
                func.count(CSATResponse.id).label("count"),
                func.avg(CSATResponse.rating).label("avg_rating"),
            )
            .join(CSATSurvey, CSATSurvey.id == CSATResponse.survey_id)
            .filter(
                CSATResponse.responded_at >= start_date,
                CSATResponse.rating.isnot(None),
            )
            .group_by(CSATSurvey.survey_type)
        )

        if end_date:
            query = query.filter(CSATResponse.responded_at <= end_date)

        rows = query.all()
        return [
            {
                "type": r.survey_type,
                "count": r.count,
                "avg_rating": round(float(r.avg_rating or 0), 2),
            }
            for r in rows
        ]
