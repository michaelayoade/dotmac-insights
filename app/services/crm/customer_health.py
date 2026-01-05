"""Customer Health Service - CRM-Support Integration Analytics.

Provides customer health scoring, churn risk assessment, pattern detection,
and opportunity signals based on support ticket data.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func, case, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.support_csat import CSATResponse
from app.models.party import Party
from app.models.subscription import Subscription
from app.utils.datetime_utils import utc_now

from .customer_health_types import (
    CalculateHealthInput,
    BulkHealthCalculationInput,
    ListHealthScoresInput,
    DetectPatternsInput,
    CustomerHealthScore,
    CustomerHealthSummary,
    CustomerHealthTrend,
    HealthTrendPoint,
    HealthDashboardStats,
    HealthScoreBreakdown,
    TicketMetrics,
    CSATMetrics,
    ChurnRiskAssessment,
    ChurnRiskFactor,
    EscalationAlert,
    SLABreachWarning,
    OpportunitySignal,
    OpportunitySignalType,
    FeatureRequestAggregate,
    RecurringIssue,
    PatternDetectionResult,
    HealthGrade,
    RiskLevel,
)


class CustomerHealthService:
    """Service for calculating and analyzing customer health from support data."""

    def __init__(self, session: AsyncSession, company_id: UUID):
        self.session = session
        self.company_id = company_id

    # -------------------------------------------------------------------------
    # Health Score Calculation
    # -------------------------------------------------------------------------

    async def calculate_health_score(
        self,
        input_data: CalculateHealthInput,
    ) -> CustomerHealthScore:
        """Calculate health score for a single customer."""
        party_id = input_data.party_id
        lookback_days = input_data.lookback_days
        cutoff_date = utc_now() - timedelta(days=lookback_days)

        # Get ticket metrics
        ticket_metrics = await self._get_ticket_metrics(party_id, cutoff_date)

        # Get CSAT metrics
        csat_metrics = await self._get_csat_metrics(party_id, cutoff_date)

        # Calculate score breakdown
        breakdown = self._calculate_score_breakdown(ticket_metrics, csat_metrics)

        # Calculate overall score
        overall_score = self._calculate_overall_score(breakdown)

        # Determine grade
        grade = self._score_to_grade(overall_score)

        # Get previous score for trend
        previous_score = await self._get_previous_score(party_id)
        score_change = overall_score - previous_score if previous_score else 0.0
        trend = "improving" if score_change > 5 else "declining" if score_change < -5 else "stable"

        return CustomerHealthScore(
            party_id=party_id,
            company_id=self.company_id,
            overall_score=overall_score,
            grade=grade,
            breakdown=breakdown,
            ticket_metrics=ticket_metrics,
            csat_metrics=csat_metrics,
            calculated_at=utc_now(),
            previous_score=previous_score,
            score_change=score_change,
            trend_direction=trend,
        )

    async def bulk_calculate_health_scores(
        self,
        input_data: BulkHealthCalculationInput,
    ) -> list[CustomerHealthScore]:
        """Calculate health scores for multiple customers."""
        # Get party IDs to process
        if input_data.party_ids:
            party_ids = input_data.party_ids
        else:
            # Get all parties with tickets
            party_ids = await self._get_parties_with_tickets(
                min_ticket_count=input_data.min_ticket_count
            )

        results = []
        for party_id in party_ids:
            try:
                score = await self.calculate_health_score(
                    CalculateHealthInput(
                        party_id=party_id,
                        lookback_days=input_data.lookback_days,
                    )
                )
                # Apply grade filter if specified
                if input_data.health_grade_filter:
                    if score.grade == input_data.health_grade_filter:
                        results.append(score)
                else:
                    results.append(score)
            except Exception:
                # Skip parties that fail calculation
                continue

        return results

    async def list_health_scores(
        self,
        input_data: ListHealthScoresInput,
    ) -> tuple[list[CustomerHealthSummary], int]:
        """List customer health summaries with filtering and pagination."""
        # Get all parties with recent ticket activity
        parties = await self._get_parties_with_tickets(min_ticket_count=0)

        summaries = []
        for party_id in parties:
            try:
                score = await self.calculate_health_score(
                    CalculateHealthInput(party_id=party_id, lookback_days=90)
                )

                # Get party name
                party = await self.session.get(Party, party_id)
                party_name = party.display_name if party else "Unknown"

                # Get alert count
                alerts = await self.get_escalation_alerts(party_id)

                # Apply filters
                if input_data.grade_filter and score.grade != input_data.grade_filter:
                    continue
                if input_data.min_score and score.overall_score < input_data.min_score:
                    continue
                if input_data.max_score and score.overall_score > input_data.max_score:
                    continue

                # Get churn risk
                churn = await self.assess_churn_risk(party_id)

                if input_data.risk_level_filter and churn.risk_level != input_data.risk_level_filter:
                    continue
                if input_data.has_alerts is not None:
                    has = len(alerts) > 0
                    if input_data.has_alerts != has:
                        continue

                summaries.append(CustomerHealthSummary(
                    party_id=party_id,
                    party_name=party_name,
                    overall_score=score.overall_score,
                    grade=score.grade,
                    churn_risk=churn.risk_level,
                    open_tickets=score.ticket_metrics.open_tickets,
                    avg_csat=score.csat_metrics.average_score if score.csat_metrics.response_count > 0 else None,
                    last_ticket_date=await self._get_last_ticket_date(party_id),
                    has_alerts=len(alerts) > 0,
                    alert_count=len(alerts),
                ))
            except Exception:
                continue

        # Sort
        if input_data.sort_by == "score":
            summaries.sort(key=lambda x: x.overall_score, reverse=input_data.sort_desc)
        elif input_data.sort_by == "name":
            summaries.sort(key=lambda x: x.party_name, reverse=input_data.sort_desc)
        elif input_data.sort_by == "ticket_count":
            summaries.sort(key=lambda x: x.open_tickets, reverse=input_data.sort_desc)

        total = len(summaries)

        # Paginate
        start = (input_data.page - 1) * input_data.per_page
        end = start + input_data.per_page
        summaries = summaries[start:end]

        return summaries, total

    async def get_health_trend(
        self,
        party_id: UUID,
        period_days: int = 90,
    ) -> CustomerHealthTrend:
        """Get health score trend over time for a customer."""
        data_points = []
        current_date = utc_now()

        # Calculate weekly snapshots going back
        for week in range(0, period_days // 7):
            snapshot_date = current_date - timedelta(days=week * 7)
            lookback = 30  # Each point looks back 30 days

            ticket_metrics = await self._get_ticket_metrics(
                party_id,
                snapshot_date - timedelta(days=lookback),
                end_date=snapshot_date,
            )
            csat_metrics = await self._get_csat_metrics(
                party_id,
                snapshot_date - timedelta(days=lookback),
                end_date=snapshot_date,
            )

            breakdown = self._calculate_score_breakdown(ticket_metrics, csat_metrics)
            score = self._calculate_overall_score(breakdown)
            grade = self._score_to_grade(score)

            data_points.append(HealthTrendPoint(
                date=snapshot_date,
                score=score,
                grade=grade,
                ticket_count=ticket_metrics.total_tickets,
                csat_score=csat_metrics.average_score if csat_metrics.response_count > 0 else None,
            ))

        # Reverse to show oldest first
        data_points.reverse()

        # Determine overall trend
        if len(data_points) >= 2:
            first_score = data_points[0].score
            last_score = data_points[-1].score
            velocity = (last_score - first_score) / len(data_points)
            trend = "improving" if velocity > 1 else "declining" if velocity < -1 else "stable"
        else:
            velocity = 0.0
            trend = "stable"

        return CustomerHealthTrend(
            party_id=party_id,
            company_id=self.company_id,
            period_days=period_days,
            data_points=data_points,
            overall_trend=trend,
            trend_velocity=velocity,
        )

    async def get_dashboard_stats(self) -> HealthDashboardStats:
        """Get aggregate health statistics for the dashboard."""
        # Get all parties with tickets
        parties = await self._get_parties_with_tickets(min_ticket_count=0)

        excellent = good = at_risk = critical = 0
        total_score = 0.0
        churn_high = churn_critical = 0
        active_alerts = 0

        for party_id in parties:
            try:
                score = await self.calculate_health_score(
                    CalculateHealthInput(party_id=party_id, lookback_days=90)
                )
                total_score += score.overall_score

                if score.grade == HealthGrade.EXCELLENT:
                    excellent += 1
                elif score.grade == HealthGrade.GOOD:
                    good += 1
                elif score.grade == HealthGrade.AT_RISK:
                    at_risk += 1
                else:
                    critical += 1

                # Check churn risk
                churn = await self.assess_churn_risk(party_id)
                if churn.risk_level == RiskLevel.HIGH:
                    churn_high += 1
                elif churn.risk_level == RiskLevel.CRITICAL:
                    churn_critical += 1

                # Count alerts
                alerts = await self.get_escalation_alerts(party_id)
                active_alerts += len(alerts)
            except Exception:
                continue

        total_customers = len(parties)
        avg_score = total_score / total_customers if total_customers > 0 else 0.0

        # Get aggregate ticket stats
        from sqlalchemy import select
        open_tickets_q = select(func.count(Ticket.id)).where(
            and_(
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.WAITING]),
                Ticket.is_deleted == False,
            )
        )
        result = await self.session.execute(open_tickets_q)
        total_open = result.scalar() or 0

        # Avg resolution time
        resolved_q = select(func.avg(
            func.extract('epoch', Ticket.resolution_date - Ticket.opening_date) / 3600
        )).where(
            and_(
                Ticket.resolution_date.isnot(None),
                Ticket.opening_date.isnot(None),
                Ticket.is_deleted == False,
            )
        )
        result = await self.session.execute(resolved_q)
        avg_resolution = result.scalar() or 0.0

        # Avg CSAT
        csat_q = select(func.avg(CSATResponse.rating)).where(
            CSATResponse.rating.isnot(None)
        )
        result = await self.session.execute(csat_q)
        avg_csat = result.scalar() or 0.0

        return HealthDashboardStats(
            company_id=self.company_id,
            total_customers=total_customers,
            excellent_count=excellent,
            good_count=good,
            at_risk_count=at_risk,
            critical_count=critical,
            avg_health_score=avg_score,
            churn_risk_high=churn_high,
            churn_risk_critical=churn_critical,
            active_alerts=active_alerts,
            total_open_tickets=total_open,
            avg_resolution_hours=avg_resolution,
            avg_csat=avg_csat,
            calculated_at=utc_now(),
        )

    # -------------------------------------------------------------------------
    # Risk Assessment
    # -------------------------------------------------------------------------

    async def assess_churn_risk(
        self,
        party_id: UUID,
        lookback_days: int = 90,
    ) -> ChurnRiskAssessment:
        """Assess churn risk for a customer based on support patterns."""
        cutoff_date = utc_now() - timedelta(days=lookback_days)

        ticket_metrics = await self._get_ticket_metrics(party_id, cutoff_date)
        csat_metrics = await self._get_csat_metrics(party_id, cutoff_date)

        factors: list[ChurnRiskFactor] = []
        factor_details: dict = {}
        risk_score = 0.0

        # High ticket volume
        if ticket_metrics.tickets_last_30_days > 5:
            factors.append(ChurnRiskFactor.HIGH_TICKET_VOLUME)
            factor_details["ticket_volume"] = {
                "count": ticket_metrics.tickets_last_30_days,
                "threshold": 5,
            }
            risk_score += 15

        # Escalations
        if ticket_metrics.escalated_tickets > 2:
            factors.append(ChurnRiskFactor.ESCALATIONS)
            factor_details["escalations"] = {
                "count": ticket_metrics.escalated_tickets,
                "threshold": 2,
            }
            risk_score += 20

        # Low CSAT
        if csat_metrics.response_count > 0 and csat_metrics.average_score < 3.0:
            factors.append(ChurnRiskFactor.LOW_CSAT)
            factor_details["csat"] = {
                "score": csat_metrics.average_score,
                "threshold": 3.0,
            }
            risk_score += 25

        # SLA breaches
        if ticket_metrics.sla_breaches > 2:
            factors.append(ChurnRiskFactor.SLA_BREACHES)
            factor_details["sla_breaches"] = {
                "count": ticket_metrics.sla_breaches,
                "threshold": 2,
            }
            risk_score += 20

        # Long resolution times
        if ticket_metrics.avg_resolution_hours > 48:
            factors.append(ChurnRiskFactor.LONG_RESOLUTION_TIMES)
            factor_details["resolution_time"] = {
                "hours": ticket_metrics.avg_resolution_hours,
                "threshold": 48,
            }
            risk_score += 10

        # Recurring issues (check for same issue type tickets)
        recurring = await self._check_recurring_issues(party_id, cutoff_date)
        if recurring:
            factors.append(ChurnRiskFactor.RECURRING_ISSUES)
            factor_details["recurring_issues"] = {
                "categories": recurring,
            }
            risk_score += 15

        # Ticket trend
        if ticket_metrics.trend_direction == "increasing":
            risk_score += 10

        # Cap at 100
        risk_score = min(risk_score, 100)

        # Determine risk level
        if risk_score >= 70:
            risk_level = RiskLevel.CRITICAL
        elif risk_score >= 50:
            risk_level = RiskLevel.HIGH
        elif risk_score >= 30:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        # Get estimated revenue at risk
        revenue = await self._get_party_revenue(party_id)

        # Generate recommendations
        recommendations = self._generate_churn_recommendations(factors)

        return ChurnRiskAssessment(
            party_id=party_id,
            company_id=self.company_id,
            risk_level=risk_level,
            risk_score=risk_score,
            contributing_factors=factors,
            factor_details=factor_details,
            recommended_actions=recommendations,
            estimated_revenue_at_risk=revenue,
            assessed_at=utc_now(),
        )

    async def get_escalation_alerts(
        self,
        party_id: UUID,
        period_days: int = 30,
    ) -> list[EscalationAlert]:
        """Get escalation alerts for a customer."""
        from sqlalchemy import select

        cutoff = utc_now() - timedelta(days=period_days)

        # Find escalated tickets
        q = select(Ticket).where(
            and_(
                Ticket.party_id == party_id,
                Ticket.is_escalated == True,
                Ticket.created_at >= cutoff,
                Ticket.is_deleted == False,
            )
        )
        result = await self.session.execute(q)
        escalated = result.scalars().all()

        alerts = []

        if len(escalated) >= 3:
            alerts.append(EscalationAlert(
                party_id=party_id,
                company_id=self.company_id,
                alert_type="repeated_escalation",
                severity=RiskLevel.HIGH,
                ticket_ids=[t.id for t in escalated],
                escalation_count=len(escalated),
                period_days=period_days,
                message=f"Customer has {len(escalated)} escalated tickets in the last {period_days} days",
                created_at=utc_now(),
            ))

        # Check for critical priority escalations
        critical_escalated = [t for t in escalated if t.priority == TicketPriority.URGENT]
        if critical_escalated:
            alerts.append(EscalationAlert(
                party_id=party_id,
                company_id=self.company_id,
                alert_type="critical_escalation",
                severity=RiskLevel.CRITICAL,
                ticket_ids=[t.id for t in critical_escalated],
                escalation_count=len(critical_escalated),
                period_days=period_days,
                message=f"Customer has {len(critical_escalated)} critical/urgent escalated tickets",
                created_at=utc_now(),
            ))

        return alerts

    async def get_sla_breach_warnings(
        self,
        party_id: UUID,
        period_days: int = 30,
    ) -> SLABreachWarning:
        """Get SLA breach warnings for a customer."""
        from sqlalchemy import select

        cutoff = utc_now() - timedelta(days=period_days)

        # Total tickets in period
        total_q = select(func.count(Ticket.id)).where(
            and_(
                Ticket.party_id == party_id,
                Ticket.created_at >= cutoff,
                Ticket.is_deleted == False,
            )
        )
        total_result = await self.session.execute(total_q)
        total_tickets = total_result.scalar() or 0

        # Breached tickets (where resolution_date > resolution_by)
        breach_q = select(Ticket).where(
            and_(
                Ticket.party_id == party_id,
                Ticket.created_at >= cutoff,
                Ticket.resolution_by.isnot(None),
                Ticket.is_deleted == False,
            )
        )
        result = await self.session.execute(breach_q)
        tickets = result.scalars().all()

        breached = [t for t in tickets if t.is_overdue or (
            t.resolution_date and t.resolution_by and t.resolution_date > t.resolution_by
        )]

        breach_count = len(breached)
        breach_rate = (breach_count / total_tickets * 100) if total_tickets > 0 else 0.0

        # Calculate avg breach hours
        total_breach_hours = 0.0
        for t in breached:
            if t.resolution_date and t.resolution_by:
                delta = t.resolution_date - t.resolution_by
                total_breach_hours += delta.total_seconds() / 3600

        avg_breach_hours = total_breach_hours / breach_count if breach_count > 0 else 0.0

        # Determine severity
        if breach_rate >= 30:
            severity = RiskLevel.CRITICAL
        elif breach_rate >= 20:
            severity = RiskLevel.HIGH
        elif breach_rate >= 10:
            severity = RiskLevel.MEDIUM
        else:
            severity = RiskLevel.LOW

        # At-risk tickets (currently open with SLA approaching)
        at_risk_q = select(Ticket).where(
            and_(
                Ticket.party_id == party_id,
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]),
                Ticket.resolution_by.isnot(None),
                Ticket.is_deleted == False,
            )
        )
        result = await self.session.execute(at_risk_q)
        open_tickets = result.scalars().all()

        # Tickets where SLA is within 4 hours
        now = utc_now()
        at_risk = [t.id for t in open_tickets if t.resolution_by and (t.resolution_by - now).total_seconds() < 4 * 3600]

        return SLABreachWarning(
            party_id=party_id,
            company_id=self.company_id,
            breach_count=breach_count,
            breach_rate=breach_rate,
            at_risk_tickets=at_risk,
            avg_breach_hours=avg_breach_hours,
            severity=severity,
            created_at=utc_now(),
        )

    # -------------------------------------------------------------------------
    # Opportunity Signals
    # -------------------------------------------------------------------------

    async def detect_opportunity_signals(
        self,
        party_id: UUID,
        lookback_days: int = 180,
    ) -> list[OpportunitySignal]:
        """Detect sales/expansion opportunities from support data."""
        from sqlalchemy import select

        cutoff = utc_now() - timedelta(days=lookback_days)
        signals = []

        # Get tickets for analysis
        q = select(Ticket).where(
            and_(
                Ticket.party_id == party_id,
                Ticket.created_at >= cutoff,
                Ticket.is_deleted == False,
            )
        )
        result = await self.session.execute(q)
        tickets = result.scalars().all()

        # Analyze for feature requests
        feature_keywords = ["feature", "request", "would be nice", "wish", "suggestion", "enhance"]
        feature_tickets = []
        for t in tickets:
            text = f"{t.subject or ''} {t.description or ''}".lower()
            if any(kw in text for kw in feature_keywords):
                feature_tickets.append(t)

        if feature_tickets:
            signals.append(OpportunitySignal(
                party_id=party_id,
                company_id=self.company_id,
                signal_type=OpportunitySignalType.FEATURE_REQUEST,
                confidence=min(len(feature_tickets) * 0.2, 0.9),
                source_ticket_ids=[t.id for t in feature_tickets],
                description=f"Customer has submitted {len(feature_tickets)} feature requests",
                suggested_action="Schedule product feedback call to discuss roadmap alignment",
                detected_at=utc_now(),
            ))

        # High satisfaction = potential advocate
        csat_metrics = await self._get_csat_metrics(party_id, cutoff)
        if csat_metrics.average_score >= 4.5 and csat_metrics.response_count >= 3:
            signals.append(OpportunitySignal(
                party_id=party_id,
                company_id=self.company_id,
                signal_type=OpportunitySignalType.ADVOCACY,
                confidence=0.8,
                source_ticket_ids=[],
                description=f"Customer has consistently high satisfaction ({csat_metrics.average_score:.1f}/5 over {csat_metrics.response_count} surveys)",
                suggested_action="Consider for case study, referral program, or beta testing",
                detected_at=utc_now(),
            ))

        # Usage limit tickets might indicate upgrade readiness
        upgrade_keywords = ["limit", "quota", "capacity", "upgrade", "more users", "more storage", "scale"]
        upgrade_tickets = []
        for t in tickets:
            text = f"{t.subject or ''} {t.description or ''}".lower()
            if any(kw in text for kw in upgrade_keywords):
                upgrade_tickets.append(t)

        if upgrade_tickets:
            signals.append(OpportunitySignal(
                party_id=party_id,
                company_id=self.company_id,
                signal_type=OpportunitySignalType.UPGRADE_READINESS,
                confidence=min(len(upgrade_tickets) * 0.25, 0.85),
                source_ticket_ids=[t.id for t in upgrade_tickets],
                description=f"Customer has {len(upgrade_tickets)} tickets related to limits/capacity",
                suggested_action="Discuss plan upgrade or additional resources",
                detected_at=utc_now(),
            ))

        return signals

    async def aggregate_feature_requests(
        self,
        lookback_days: int = 180,
        min_requests: int = 2,
    ) -> list[FeatureRequestAggregate]:
        """Aggregate feature requests across all customers."""
        from sqlalchemy import select
        from collections import defaultdict

        cutoff = utc_now() - timedelta(days=lookback_days)

        # Get all tickets with feature-like content
        feature_keywords = ["feature", "request", "would be nice", "wish", "suggestion", "enhance", "add support for"]

        q = select(Ticket).where(
            and_(
                Ticket.created_at >= cutoff,
                Ticket.is_deleted == False,
            )
        )
        result = await self.session.execute(q)
        tickets = result.scalars().all()

        # Group by extracted keywords
        aggregates: dict = defaultdict(lambda: {
            "count": 0,
            "parties": set(),
            "tickets": [],
            "first": None,
            "last": None,
        })

        for t in tickets:
            text = f"{t.subject or ''} {t.description or ''}".lower()
            if any(kw in text for kw in feature_keywords):
                # Extract the most relevant keyword/phrase
                # Simplified: use the first matching keyword
                for kw in feature_keywords:
                    if kw in text:
                        key = kw
                        break
                else:
                    key = "general_request"

                aggregates[key]["count"] += 1
                if t.party_id:
                    aggregates[key]["parties"].add(t.party_id)
                aggregates[key]["tickets"].append(t.id)
                if not aggregates[key]["first"] or t.created_at < aggregates[key]["first"]:
                    aggregates[key]["first"] = t.created_at
                if not aggregates[key]["last"] or t.created_at > aggregates[key]["last"]:
                    aggregates[key]["last"] = t.created_at

        results = []
        for keyword, data in aggregates.items():
            if data["count"] >= min_requests:
                # Calculate priority score based on request count and customer value
                priority = data["count"] * 10
                results.append(FeatureRequestAggregate(
                    feature_keyword=keyword,
                    request_count=data["count"],
                    requesting_parties=list(data["parties"]),
                    source_ticket_ids=data["tickets"],
                    first_requested=data["first"],
                    last_requested=data["last"],
                    priority_score=priority,
                ))

        # Sort by priority
        results.sort(key=lambda x: x.priority_score, reverse=True)
        return results

    # -------------------------------------------------------------------------
    # Pattern Detection
    # -------------------------------------------------------------------------

    async def detect_patterns(
        self,
        input_data: DetectPatternsInput,
    ) -> PatternDetectionResult:
        """Detect recurring issue patterns across tickets."""
        from sqlalchemy import select
        from collections import Counter

        cutoff = utc_now() - timedelta(days=input_data.lookback_days)

        # Base query
        q = select(Ticket).where(
            and_(
                Ticket.created_at >= cutoff,
                Ticket.is_deleted == False,
            )
        )

        if not input_data.include_resolved:
            q = q.where(Ticket.status.notin_([TicketStatus.RESOLVED, TicketStatus.CLOSED]))

        if input_data.categories:
            q = q.where(Ticket.ticket_type.in_(input_data.categories))

        result = await self.session.execute(q)
        tickets = result.scalars().all()

        # Analyze categories
        category_counts = Counter(t.ticket_type for t in tickets if t.ticket_type)
        top_categories = category_counts.most_common(10)

        # Extract keywords from subjects/descriptions
        all_words: list[str] = []
        for t in tickets:
            text = f"{t.subject or ''} {t.description or ''}".lower()
            # Simple word extraction (skip common words)
            stopwords = {"the", "a", "an", "is", "are", "was", "were", "to", "for", "of", "and", "in", "on", "at", "with", "by"}
            words = [w.strip(".,!?") for w in text.split() if len(w) > 3 and w not in stopwords]
            all_words.extend(words)

        word_counts = Counter(all_words)
        common_keywords = word_counts.most_common(20)

        # Find peak hours
        hour_counts = Counter(t.created_at.hour for t in tickets if t.created_at)
        peak_hours = [h for h, _ in hour_counts.most_common(3)]

        # Find peak days (0=Monday)
        day_counts = Counter(t.created_at.weekday() for t in tickets if t.created_at)
        peak_days = [d for d, _ in day_counts.most_common(3)]

        # Detect recurring issues (same category/type from same party multiple times)
        party_category_counts: dict = {}
        for t in tickets:
            if t.party_id and t.ticket_type:
                key = (t.party_id, t.ticket_type)
                if key not in party_category_counts:
                    party_category_counts[key] = {
                        "count": 0,
                        "tickets": [],
                        "first": None,
                        "last": None,
                    }
                party_category_counts[key]["count"] += 1
                party_category_counts[key]["tickets"].append(t)
                if not party_category_counts[key]["first"] or t.created_at < party_category_counts[key]["first"]:
                    party_category_counts[key]["first"] = t.created_at
                if not party_category_counts[key]["last"] or t.created_at > party_category_counts[key]["last"]:
                    party_category_counts[key]["last"] = t.created_at

        recurring_issues = []
        for (party_id, category), data in party_category_counts.items():
            if data["count"] >= input_data.min_occurrence_count:
                tickets_list = data["tickets"]
                avg_res = sum(
                    t.time_to_resolution_hours or 0 for t in tickets_list
                ) / len(tickets_list) if tickets_list else 0

                recurring_issues.append(RecurringIssue(
                    issue_id=party_id,  # Using party_id as issue identifier
                    category=category,
                    description=f"Recurring {category} issues from this customer",
                    occurrence_count=data["count"],
                    first_occurrence=data["first"],
                    last_occurrence=data["last"],
                    affected_parties=[party_id],
                    avg_resolution_hours=avg_res,
                    is_product_issue=data["count"] >= 5,
                    suggested_action="Investigate root cause and consider proactive outreach",
                ))

        return PatternDetectionResult(
            company_id=self.company_id,
            recurring_issues=recurring_issues,
            top_issue_categories=top_categories,
            common_keywords=common_keywords,
            peak_ticket_hours=peak_hours,
            peak_ticket_days=peak_days,
            analyzed_at=utc_now(),
        )

    # -------------------------------------------------------------------------
    # Private Helper Methods
    # -------------------------------------------------------------------------

    async def _get_ticket_metrics(
        self,
        party_id: UUID,
        start_date: datetime,
        end_date: Optional[datetime] = None,
    ) -> TicketMetrics:
        """Get ticket metrics for a party within a date range."""
        from sqlalchemy import select

        end_date = end_date or utc_now()

        q = select(Ticket).where(
            and_(
                Ticket.party_id == party_id,
                Ticket.created_at >= start_date,
                Ticket.created_at <= end_date,
                Ticket.is_deleted == False,
            )
        )
        result = await self.session.execute(q)
        tickets = list(result.scalars().all())

        total = len(tickets)
        open_count = len([t for t in tickets if t.status in [TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.WAITING]])
        resolved = len([t for t in tickets if t.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]])
        escalated = len([t for t in tickets if t.is_escalated])
        high_priority = len([t for t in tickets if t.priority in [TicketPriority.HIGH, TicketPriority.URGENT]])
        critical = len([t for t in tickets if t.priority == TicketPriority.URGENT])

        # Resolution time
        resolution_times = [t.time_to_resolution_hours for t in tickets if t.time_to_resolution_hours]
        avg_resolution = sum(resolution_times) / len(resolution_times) if resolution_times else 0.0

        # First response time
        response_times = []
        for t in tickets:
            if t.first_responded_on and t.opening_date:
                delta = (t.first_responded_on - t.opening_date).total_seconds() / 3600
                response_times.append(delta)
        avg_first_response = sum(response_times) / len(response_times) if response_times else 0.0

        # SLA breaches
        sla_breaches = len([t for t in tickets if t.is_overdue or (
            t.resolution_date and t.resolution_by and t.resolution_date > t.resolution_by
        )])

        # Recent tickets
        now = utc_now()
        last_30 = len([t for t in tickets if (now - t.created_at).days <= 30])
        last_90 = len([t for t in tickets if (now - t.created_at).days <= 90])

        # Trend
        first_half = len([t for t in tickets if (now - t.created_at).days > 45])
        second_half = len([t for t in tickets if (now - t.created_at).days <= 45])
        if second_half > first_half * 1.5:
            trend = "increasing"
        elif first_half > second_half * 1.5:
            trend = "decreasing"
        else:
            trend = "stable"

        return TicketMetrics(
            total_tickets=total,
            open_tickets=open_count,
            resolved_tickets=resolved,
            escalated_tickets=escalated,
            high_priority_tickets=high_priority,
            critical_tickets=critical,
            avg_resolution_hours=avg_resolution,
            avg_first_response_hours=avg_first_response,
            sla_breaches=sla_breaches,
            tickets_last_30_days=last_30,
            tickets_last_90_days=last_90,
            trend_direction=trend,
        )

    async def _get_csat_metrics(
        self,
        party_id: UUID,
        start_date: datetime,
        end_date: Optional[datetime] = None,
    ) -> CSATMetrics:
        """Get CSAT metrics for a party within a date range."""
        from sqlalchemy import select

        end_date = end_date or utc_now()

        q = select(CSATResponse).where(
            and_(
                CSATResponse.party_id == party_id,
                CSATResponse.responded_at.isnot(None),
                CSATResponse.created_at >= start_date,
                CSATResponse.created_at <= end_date,
            )
        )
        result = await self.session.execute(q)
        responses = list(result.scalars().all())

        if not responses:
            return CSATMetrics()

        ratings = [r.rating for r in responses if r.rating is not None]
        if not ratings:
            return CSATMetrics(response_count=len(responses))

        avg_score = sum(ratings) / len(ratings)
        promoters = len([r for r in ratings if r >= 9])  # NPS style
        passives = len([r for r in ratings if 7 <= r < 9])
        detractors = len([r for r in ratings if r < 7])

        # For CSAT (1-5 scale), adjust thresholds
        if max(ratings) <= 5:
            promoters = len([r for r in ratings if r >= 4])
            passives = len([r for r in ratings if r == 3])
            detractors = len([r for r in ratings if r < 3])

        # NPS calculation
        nps = None
        if len(ratings) > 0:
            promoter_pct = promoters / len(ratings) * 100
            detractor_pct = detractors / len(ratings) * 100
            nps = promoter_pct - detractor_pct

        # Trend
        sorted_responses = sorted(responses, key=lambda x: x.created_at)
        if len(sorted_responses) >= 4:
            first_half_avg = sum(r.rating or 0 for r in sorted_responses[:len(sorted_responses)//2]) / (len(sorted_responses)//2)
            second_half_avg = sum(r.rating or 0 for r in sorted_responses[len(sorted_responses)//2:]) / (len(sorted_responses) - len(sorted_responses)//2)
            if second_half_avg > first_half_avg + 0.5:
                trend = "improving"
            elif first_half_avg > second_half_avg + 0.5:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        last_feedback = max(r.responded_at for r in responses if r.responded_at) if responses else None

        return CSATMetrics(
            average_score=avg_score,
            response_count=len(responses),
            promoters=promoters,
            passives=passives,
            detractors=detractors,
            nps_score=nps,
            trend_direction=trend,
            last_feedback_date=last_feedback,
        )

    def _calculate_score_breakdown(
        self,
        ticket_metrics: TicketMetrics,
        csat_metrics: CSATMetrics,
    ) -> HealthScoreBreakdown:
        """Calculate individual score components."""
        # Ticket frequency score (fewer tickets = higher score)
        # Baseline: 0 tickets = 100, 10+ tickets = 0
        ticket_score = max(0, 100 - (ticket_metrics.tickets_last_30_days * 10))

        # Resolution time score
        # Baseline: < 4 hours = 100, > 48 hours = 0
        if ticket_metrics.avg_resolution_hours <= 4:
            resolution_score = 100
        elif ticket_metrics.avg_resolution_hours >= 48:
            resolution_score = 0
        else:
            resolution_score = 100 - ((ticket_metrics.avg_resolution_hours - 4) / 44 * 100)

        # CSAT score (normalize to 0-100)
        if csat_metrics.response_count > 0:
            # Assuming 1-5 scale
            csat_score = (csat_metrics.average_score / 5) * 100
        else:
            csat_score = 70  # Neutral if no data

        # Escalation score (fewer = better)
        if ticket_metrics.total_tickets > 0:
            escalation_rate = ticket_metrics.escalated_tickets / ticket_metrics.total_tickets
            escalation_score = max(0, 100 - (escalation_rate * 200))
        else:
            escalation_score = 100

        # SLA compliance score
        if ticket_metrics.total_tickets > 0:
            breach_rate = ticket_metrics.sla_breaches / ticket_metrics.total_tickets
            sla_score = max(0, 100 - (breach_rate * 200))
        else:
            sla_score = 100

        # Engagement score (based on trend - stable or improving is good)
        if ticket_metrics.trend_direction == "decreasing":
            engagement_score = 80  # Fewer issues is good
        elif ticket_metrics.trend_direction == "increasing":
            engagement_score = 40  # More issues is concerning
        else:
            engagement_score = 60  # Stable

        return HealthScoreBreakdown(
            ticket_frequency_score=ticket_score,
            resolution_time_score=resolution_score,
            csat_score=csat_score,
            escalation_score=escalation_score,
            sla_compliance_score=sla_score,
            engagement_score=engagement_score,
        )

    def _calculate_overall_score(self, breakdown: HealthScoreBreakdown) -> float:
        """Calculate weighted overall health score."""
        score = (
            breakdown.ticket_frequency_score * breakdown.ticket_frequency_weight +
            breakdown.resolution_time_score * breakdown.resolution_time_weight +
            breakdown.csat_score * breakdown.csat_weight +
            breakdown.escalation_score * breakdown.escalation_weight +
            breakdown.sla_compliance_score * breakdown.sla_compliance_weight +
            breakdown.engagement_score * breakdown.engagement_weight
        )
        return round(score, 1)

    def _score_to_grade(self, score: float) -> HealthGrade:
        """Convert numeric score to grade."""
        if score >= 80:
            return HealthGrade.EXCELLENT
        elif score >= 60:
            return HealthGrade.GOOD
        elif score >= 40:
            return HealthGrade.AT_RISK
        else:
            return HealthGrade.CRITICAL

    async def _get_parties_with_tickets(
        self,
        min_ticket_count: int = 0,
    ) -> list[UUID]:
        """Get all party IDs that have tickets."""
        from sqlalchemy import select

        q = select(Ticket.party_id).where(
            and_(
                Ticket.party_id.isnot(None),
                Ticket.is_deleted == False,
            )
        ).group_by(Ticket.party_id).having(
            func.count(Ticket.id) >= min_ticket_count
        )

        result = await self.session.execute(q)
        return [row[0] for row in result.all()]

    async def _get_previous_score(self, party_id: UUID) -> Optional[float]:
        """Get previously calculated health score (would use cache/history table in production)."""
        # In production, this would fetch from a health_score_history table
        # For now, return None to indicate no previous score
        return None

    async def _get_last_ticket_date(self, party_id: UUID) -> Optional[datetime]:
        """Get the most recent ticket date for a party."""
        from sqlalchemy import select

        q = select(func.max(Ticket.created_at)).where(
            and_(
                Ticket.party_id == party_id,
                Ticket.is_deleted == False,
            )
        )
        result = await self.session.execute(q)
        return result.scalar()

    async def _check_recurring_issues(
        self,
        party_id: UUID,
        start_date: datetime,
    ) -> list[str]:
        """Check for recurring issue categories."""
        from sqlalchemy import select
        from collections import Counter

        q = select(Ticket.ticket_type).where(
            and_(
                Ticket.party_id == party_id,
                Ticket.created_at >= start_date,
                Ticket.ticket_type.isnot(None),
                Ticket.is_deleted == False,
            )
        )
        result = await self.session.execute(q)
        types = [row[0] for row in result.all()]

        counts = Counter(types)
        # Return categories that appear 3+ times
        return [cat for cat, count in counts.items() if count >= 3]

    async def _get_party_revenue(self, party_id: UUID) -> Optional[Decimal]:
        """Get estimated revenue for a party from subscriptions."""
        from sqlalchemy import select

        q = select(func.sum(Subscription.price)).where(
            and_(
                Subscription.party_id == party_id,
                Subscription.status == "active",
            )
        )
        result = await self.session.execute(q)
        return result.scalar()

    def _generate_churn_recommendations(
        self,
        factors: list[ChurnRiskFactor],
    ) -> list[str]:
        """Generate actionable recommendations based on churn factors."""
        recommendations = []

        if ChurnRiskFactor.HIGH_TICKET_VOLUME in factors:
            recommendations.append("Schedule a customer success check-in to address recurring concerns")

        if ChurnRiskFactor.RECURRING_ISSUES in factors:
            recommendations.append("Conduct root cause analysis for recurring issue patterns")

        if ChurnRiskFactor.LOW_CSAT in factors:
            recommendations.append("Initiate customer feedback session to understand satisfaction drivers")

        if ChurnRiskFactor.ESCALATIONS in factors:
            recommendations.append("Review escalation history and ensure senior support involvement")

        if ChurnRiskFactor.SLA_BREACHES in factors:
            recommendations.append("Prioritize this customer's tickets and consider dedicated support")

        if ChurnRiskFactor.LONG_RESOLUTION_TIMES in factors:
            recommendations.append("Investigate ticket routing and consider expedited handling")

        if not recommendations:
            recommendations.append("Continue monitoring customer health metrics")

        return recommendations
