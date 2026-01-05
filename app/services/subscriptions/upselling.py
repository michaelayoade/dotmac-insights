"""Upselling Service - Usage analysis and opportunity detection."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import and_, func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.subscription import Subscription, SubscriptionStatus
from app.models.upselling import (
    UpsellOpportunity,
    UpsellAnalysisRun,
    UpsellConversionEvent,
    UpsellTriggerType,
    UpsellStatus,
)
from app.models.data_bundle import CustomerBundle, BundleUsageLog
from app.models.tariff import Tariff
from app.models.party import Party
from app.utils.datetime_utils import utc_now
from app.services.event_bus import EventBus
from app.services.settings_service import SettingsService

from .upselling_types import (
    TriggerType,
    UsageMetrics,
    TriggerEvidence,
    UpgradeRecommendation,
    AnalysisResult,
    BatchAnalysisInput,
    BatchAnalysisResult,
    ConversionStats,
    SalesLeaderboardEntry,
    OpportunityListFilters,
    UpsellingSettings,
    RevenueForecast,
)

logger = logging.getLogger(__name__)


class UpsellingService:
    """Service for upselling opportunity detection and management."""

    def __init__(
        self,
        session: AsyncSession,
        company_id: int,
        event_bus: Optional[EventBus] = None,
        settings_service: Optional[SettingsService] = None,
    ):
        self.session = session
        self.company_id = company_id
        self.event_bus = event_bus
        self.settings_service = settings_service
        self._settings: Optional[UpsellingSettings] = None

    async def _get_settings(self) -> UpsellingSettings:
        """Get upselling settings from settings service."""
        if self._settings:
            return self._settings

        # Load from settings service or use defaults
        self._settings = UpsellingSettings()
        return self._settings

    # =========================================================================
    # Analysis Methods
    # =========================================================================

    async def analyze_subscription(
        self,
        subscription_id: int,
    ) -> AnalysisResult:
        """Analyze a single subscription for upselling opportunities."""
        subscription = await self.session.get(Subscription, subscription_id)
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        settings = await self._get_settings()

        # Get usage metrics
        usage_metrics = await self._get_usage_metrics(subscription)

        # Check each trigger type
        triggers: List[TriggerEvidence] = []

        # High usage check
        high_usage = await self._check_high_usage(subscription, usage_metrics, settings)
        if high_usage:
            triggers.append(high_usage)

        # Bundle exhaustion check
        bundle_exhaustion = await self._check_bundle_exhaustion(subscription, settings)
        if bundle_exhaustion:
            triggers.append(bundle_exhaustion)

        # Speed upgrade check
        speed_upgrade = await self._check_speed_limits(subscription, usage_metrics, settings)
        if speed_upgrade:
            triggers.append(speed_upgrade)

        # Loyalty upgrade check
        loyalty = await self._check_loyalty_upgrade(subscription, settings)
        if loyalty:
            triggers.append(loyalty)

        # Contract renewal check
        renewal = await self._check_contract_renewal(subscription, settings)
        if renewal:
            triggers.append(renewal)

        # Get upgrade recommendations
        recommendations = await self._find_upgrade_recommendations(subscription, triggers)

        # Calculate best recommendation
        best = recommendations[0] if recommendations else None

        # Calculate priority
        max_score = max((t.confidence_score for t in triggers), default=0)
        if max_score >= 80:
            priority = "urgent"
        elif max_score >= 60:
            priority = "high"
        elif max_score >= 40:
            priority = "medium"
        else:
            priority = "low"

        potential_increase = best.price_increase if best else Decimal("0")

        return AnalysisResult(
            subscription_id=subscription_id,
            party_id=subscription.party_id,
            current_plan=subscription.plan_name,
            current_mrr=Decimal(str(subscription.mrr)),
            triggers_found=triggers,
            recommendations=recommendations,
            best_recommendation=best,
            potential_mrr_increase=potential_increase,
            priority=priority,
        )

    async def run_batch_analysis(
        self,
        input_data: BatchAnalysisInput,
    ) -> BatchAnalysisResult:
        """Run batch analysis on multiple subscriptions."""
        import time
        start_time = time.time()

        settings = await self._get_settings()

        # Create analysis run record
        run = UpsellAnalysisRun(
            started_at=utc_now(),
            status="running",
        )
        self.session.add(run)
        await self.session.flush()

        try:
            # Get subscriptions to analyze
            q = select(Subscription).where(
                Subscription.status == SubscriptionStatus.ACTIVE
            )

            if input_data.subscription_ids:
                q = q.where(Subscription.id.in_(input_data.subscription_ids))

            if input_data.min_months_active > 0:
                cutoff = utc_now() - timedelta(days=input_data.min_months_active * 30)
                q = q.where(Subscription.start_date <= cutoff)

            if input_data.exclude_recently_analyzed:
                recent_cutoff = utc_now() - timedelta(days=input_data.recently_analyzed_days)
                # Exclude subscriptions with recent opportunities
                subq = select(UpsellOpportunity.subscription_id).where(
                    UpsellOpportunity.created_at >= recent_cutoff
                )
                q = q.where(Subscription.id.notin_(subq))

            result = await self.session.execute(q)
            subscriptions = list(result.scalars().all())

            # Track results
            opportunities_found = 0
            by_trigger: Dict[str, int] = {}
            total_potential_mrr = Decimal("0")

            # Analyze in batches
            for subscription in subscriptions:
                try:
                    analysis = await self.analyze_subscription(subscription.id)

                    if analysis.triggers_found:
                        # Create opportunity
                        opp = await self._create_opportunity_from_analysis(analysis, settings)
                        if opp:
                            opportunities_found += 1
                            total_potential_mrr += analysis.potential_mrr_increase

                            # Track by trigger
                            for trigger in analysis.triggers_found:
                                by_trigger[trigger.trigger_type.value] = by_trigger.get(
                                    trigger.trigger_type.value, 0
                                ) + 1

                except Exception as e:
                    logger.warning(
                        f"Failed to analyze subscription {subscription.id}: {e}"
                    )

            # Update run record
            run.completed_at = utc_now()
            run.status = "completed"
            run.subscriptions_analyzed = len(subscriptions)
            run.opportunities_found = opportunities_found
            run.high_usage_found = by_trigger.get(TriggerType.HIGH_USAGE.value, 0)
            run.bundle_exhaustion_found = by_trigger.get(TriggerType.BUNDLE_EXHAUSTION.value, 0)
            run.speed_upgrade_found = by_trigger.get(TriggerType.SPEED_UPGRADE.value, 0)
            run.loyalty_upgrade_found = by_trigger.get(TriggerType.LOYALTY_UPGRADE.value, 0)
            run.contract_renewal_found = by_trigger.get(TriggerType.CONTRACT_RENEWAL.value, 0)
            run.total_potential_mrr_increase = total_potential_mrr

            await self.session.flush()

            duration = time.time() - start_time

            return BatchAnalysisResult(
                run_id=run.id,
                subscriptions_analyzed=len(subscriptions),
                opportunities_found=opportunities_found,
                opportunities_by_trigger=by_trigger,
                total_potential_mrr=total_potential_mrr,
                duration_seconds=duration,
            )

        except Exception as e:
            run.status = "failed"
            run.error_message = str(e)
            run.completed_at = utc_now()
            await self.session.flush()
            raise

    # =========================================================================
    # Trigger Detection Methods
    # =========================================================================

    async def _get_usage_metrics(
        self,
        subscription: Subscription,
    ) -> UsageMetrics:
        """Get usage metrics for a subscription."""
        # Get bundle usage if applicable
        cutoff_90d = utc_now() - timedelta(days=90)

        q = select(CustomerBundle).where(
            and_(
                CustomerBundle.subscription_id == subscription.id,
                CustomerBundle.activated_at >= cutoff_90d,
            )
        )
        result = await self.session.execute(q)
        bundles = list(result.scalars().all())

        total_data = 0
        total_allocated = 0
        exhaustion_count = 0

        for bundle in bundles:
            total_data += bundle.data_used_mb
            total_allocated += bundle.data_allocated_mb
            if bundle.status == "exhausted":
                exhaustion_count += 1

        avg_usage_pct = (total_data / total_allocated * 100) if total_allocated > 0 else 0

        # Calculate months with high usage
        months_high = 0
        for i in range(3):
            month_start = utc_now() - timedelta(days=30 * (i + 1))
            month_end = utc_now() - timedelta(days=30 * i)

            month_q = select(CustomerBundle).where(
                and_(
                    CustomerBundle.subscription_id == subscription.id,
                    CustomerBundle.activated_at >= month_start,
                    CustomerBundle.activated_at < month_end,
                )
            )
            month_result = await self.session.execute(month_q)
            month_bundles = list(month_result.scalars().all())

            month_usage = sum(b.data_used_mb for b in month_bundles)
            month_alloc = sum(b.data_allocated_mb for b in month_bundles)

            if month_alloc > 0 and (month_usage / month_alloc) > 0.8:
                months_high += 1

        return UsageMetrics(
            subscription_id=subscription.id,
            avg_usage_percent=avg_usage_pct,
            peak_usage_percent=100 if exhaustion_count > 0 else avg_usage_pct,
            usage_trend="stable",
            months_high_usage=months_high,
            bundle_exhaustion_count=exhaustion_count,
            avg_session_duration_hours=0,
            total_data_gb=total_data / 1024,
            peak_throughput_mbps=0,
            plan_speed_mbps=subscription.download_speed or 0,
        )

    async def _check_high_usage(
        self,
        subscription: Subscription,
        metrics: UsageMetrics,
        settings: UpsellingSettings,
    ) -> Optional[TriggerEvidence]:
        """Check for high usage trigger."""
        if metrics.avg_usage_percent >= settings.high_usage_threshold_percent:
            if metrics.months_high_usage >= settings.high_usage_months_required:
                score = min(100, int(50 + metrics.avg_usage_percent / 2))
                return TriggerEvidence(
                    trigger_type=TriggerType.HIGH_USAGE,
                    confidence_score=score,
                    metrics={
                        "avg_usage_percent": metrics.avg_usage_percent,
                        "months_high_usage": metrics.months_high_usage,
                        "threshold": settings.high_usage_threshold_percent,
                    },
                    explanation=(
                        f"Customer has used >{settings.high_usage_threshold_percent}% "
                        f"of their data cap for {metrics.months_high_usage} consecutive months"
                    ),
                    detected_at=utc_now(),
                )
        return None

    async def _check_bundle_exhaustion(
        self,
        subscription: Subscription,
        settings: UpsellingSettings,
    ) -> Optional[TriggerEvidence]:
        """Check for bundle exhaustion trigger."""
        cutoff = utc_now() - timedelta(days=settings.bundle_exhaustion_months * 30)

        q = select(func.count(CustomerBundle.id)).where(
            and_(
                CustomerBundle.subscription_id == subscription.id,
                CustomerBundle.status == "exhausted",
                CustomerBundle.exhausted_at >= cutoff,
            )
        )
        result = await self.session.execute(q)
        exhaustion_count = result.scalar() or 0

        if exhaustion_count >= settings.bundle_exhaustion_count:
            score = min(100, 60 + exhaustion_count * 10)
            return TriggerEvidence(
                trigger_type=TriggerType.BUNDLE_EXHAUSTION,
                confidence_score=score,
                metrics={
                    "exhaustion_count": exhaustion_count,
                    "period_months": settings.bundle_exhaustion_months,
                    "threshold": settings.bundle_exhaustion_count,
                },
                explanation=(
                    f"Customer exhausted their data bundle {exhaustion_count} times "
                    f"in the last {settings.bundle_exhaustion_months} months"
                ),
                detected_at=utc_now(),
            )
        return None

    async def _check_speed_limits(
        self,
        subscription: Subscription,
        metrics: UsageMetrics,
        settings: UpsellingSettings,
    ) -> Optional[TriggerEvidence]:
        """Check if customer is hitting speed limits."""
        # This would require traffic metrics data
        # For now, check if they're on a lower tier plan
        if subscription.download_speed and subscription.download_speed <= 10:
            return TriggerEvidence(
                trigger_type=TriggerType.SPEED_UPGRADE,
                confidence_score=50,
                metrics={
                    "current_speed": subscription.download_speed,
                    "usage_percent": metrics.avg_usage_percent,
                },
                explanation=(
                    f"Customer is on a {subscription.download_speed}Mbps plan "
                    "and may benefit from faster speeds"
                ),
                detected_at=utc_now(),
            )
        return None

    async def _check_loyalty_upgrade(
        self,
        subscription: Subscription,
        settings: UpsellingSettings,
    ) -> Optional[TriggerEvidence]:
        """Check for loyalty upgrade opportunity."""
        if not subscription.start_date:
            return None

        months_active = (utc_now() - subscription.start_date).days // 30

        if months_active >= settings.loyalty_months_threshold:
            # Check if they've never upgraded
            # (simplified - would check subscription history)
            score = min(100, 40 + months_active)
            return TriggerEvidence(
                trigger_type=TriggerType.LOYALTY_UPGRADE,
                confidence_score=score,
                metrics={
                    "months_active": months_active,
                    "threshold": settings.loyalty_months_threshold,
                },
                explanation=(
                    f"Customer has been active for {months_active} months "
                    "and may be eligible for a loyalty upgrade"
                ),
                detected_at=utc_now(),
            )
        return None

    async def _check_contract_renewal(
        self,
        subscription: Subscription,
        settings: UpsellingSettings,
    ) -> Optional[TriggerEvidence]:
        """Check for contract renewal opportunity."""
        if not subscription.end_date:
            return None

        days_until_end = (subscription.end_date - utc_now()).days

        if 0 < days_until_end <= settings.contract_renewal_days_before:
            score = min(100, 90 - days_until_end)  # Higher score as expiry approaches
            return TriggerEvidence(
                trigger_type=TriggerType.CONTRACT_RENEWAL,
                confidence_score=score,
                metrics={
                    "days_until_end": days_until_end,
                    "end_date": subscription.end_date.isoformat(),
                },
                explanation=(
                    f"Customer's contract ends in {days_until_end} days - "
                    "opportunity to discuss upgrade during renewal"
                ),
                detected_at=utc_now(),
            )
        return None

    # =========================================================================
    # Recommendation Engine
    # =========================================================================

    async def _find_upgrade_recommendations(
        self,
        subscription: Subscription,
        triggers: List[TriggerEvidence],
    ) -> List[UpgradeRecommendation]:
        """Find suitable upgrade recommendations."""
        recommendations = []

        # Get available tariffs that are upgrades
        q = select(Tariff).where(
            and_(
                Tariff.is_active == True,
                Tariff.price > subscription.price,
            )
        ).order_by(Tariff.price)

        result = await self.session.execute(q)
        tariffs = list(result.scalars().all())

        for tariff in tariffs[:5]:  # Limit to top 5 recommendations
            speed_increase = 0
            if tariff.download_speed and subscription.download_speed:
                speed_increase = tariff.download_speed - subscription.download_speed

            match_score = 50  # Base score

            # Boost score based on triggers
            for trigger in triggers:
                if trigger.trigger_type == TriggerType.HIGH_USAGE:
                    if tariff.data_cap and subscription.data_cap:
                        if tariff.data_cap > subscription.data_cap:
                            match_score += 20
                elif trigger.trigger_type == TriggerType.SPEED_UPGRADE:
                    if speed_increase > 0:
                        match_score += 15
                elif trigger.trigger_type == TriggerType.BUNDLE_EXHAUSTION:
                    if tariff.data_cap and subscription.data_cap:
                        if tariff.data_cap > subscription.data_cap * 1.5:
                            match_score += 25

            recommendations.append(UpgradeRecommendation(
                tariff_id=tariff.id,
                tariff_name=tariff.name,
                current_price=subscription.price,
                new_price=tariff.price,
                price_increase=tariff.price - subscription.price,
                speed_increase_mbps=speed_increase,
                data_increase_gb=None,  # Would calculate from tariff data cap
                features_added=[],
                match_score=min(100, match_score),
            ))

        # Sort by match score
        recommendations.sort(key=lambda r: r.match_score, reverse=True)
        return recommendations

    async def _create_opportunity_from_analysis(
        self,
        analysis: AnalysisResult,
        settings: UpsellingSettings,
    ) -> Optional[UpsellOpportunity]:
        """Create an opportunity from analysis result."""
        if not analysis.triggers_found:
            return None

        # Use the highest-scoring trigger
        best_trigger = max(analysis.triggers_found, key=lambda t: t.confidence_score)

        # Set expiry
        expires_at = utc_now() + timedelta(days=settings.opportunity_expiry_days)

        opportunity = UpsellOpportunity(
            subscription_id=analysis.subscription_id,
            party_id=analysis.party_id,
            trigger_type=best_trigger.trigger_type.value,
            trigger_score=best_trigger.confidence_score,
            trigger_data=best_trigger.metrics,
            current_plan_name=analysis.current_plan,
            current_mrr=analysis.current_mrr,
            recommended_tariff_id=analysis.best_recommendation.tariff_id if analysis.best_recommendation else None,
            recommended_plan_name=analysis.best_recommendation.tariff_name if analysis.best_recommendation else None,
            recommended_mrr=analysis.best_recommendation.new_price if analysis.best_recommendation else None,
            monthly_revenue_increase=analysis.potential_mrr_increase,
            annual_revenue_increase=analysis.potential_mrr_increase * 12,
            status=UpsellStatus.NEW.value,
            priority=analysis.priority,
            expires_at=expires_at,
        )

        self.session.add(opportunity)
        await self.session.flush()

        # Emit event
        if self.event_bus:
            await self.event_bus.emit(
                "upsell.opportunity_created",
                {
                    "opportunity_id": opportunity.id,
                    "subscription_id": analysis.subscription_id,
                    "trigger_type": best_trigger.trigger_type.value,
                    "score": best_trigger.confidence_score,
                    "potential_mrr": float(analysis.potential_mrr_increase),
                },
            )

        # Create CRM opportunity if configured
        if settings.auto_create_crm_opportunity:
            await self._create_crm_opportunity(opportunity)

        return opportunity

    async def _create_crm_opportunity(
        self,
        upsell: UpsellOpportunity,
    ) -> None:
        """Create a linked CRM opportunity."""
        # This would integrate with the CRM opportunity service
        # For now, just log it
        logger.info(
            "Would create CRM opportunity",
            extra={
                "upsell_id": upsell.id,
                "subscription_id": upsell.subscription_id,
            },
        )

    # =========================================================================
    # Opportunity Management
    # =========================================================================

    async def list_opportunities(
        self,
        filters: OpportunityListFilters,
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[List[UpsellOpportunity], int]:
        """List opportunities with filters."""
        q = select(UpsellOpportunity)
        count_q = select(func.count(UpsellOpportunity.id))

        conditions = []
        if filters.status:
            conditions.append(UpsellOpportunity.status == filters.status)
        if filters.trigger_type:
            conditions.append(UpsellOpportunity.trigger_type == filters.trigger_type)
        if filters.priority:
            conditions.append(UpsellOpportunity.priority == filters.priority)
        if filters.assigned_to_id:
            conditions.append(UpsellOpportunity.assigned_to_id == filters.assigned_to_id)
        if filters.min_revenue_increase:
            conditions.append(UpsellOpportunity.monthly_revenue_increase >= filters.min_revenue_increase)
        if filters.min_score:
            conditions.append(UpsellOpportunity.trigger_score >= filters.min_score)
        if filters.created_after:
            conditions.append(UpsellOpportunity.created_at >= filters.created_after)
        if filters.expires_before:
            conditions.append(UpsellOpportunity.expires_at <= filters.expires_before)

        if conditions:
            q = q.where(and_(*conditions))
            count_q = count_q.where(and_(*conditions))

        # Get total
        count_result = await self.session.execute(count_q)
        total = count_result.scalar() or 0

        # Paginate
        q = q.order_by(
            UpsellOpportunity.trigger_score.desc(),
            UpsellOpportunity.created_at.desc(),
        ).limit(per_page).offset((page - 1) * per_page)

        result = await self.session.execute(q)
        opportunities = list(result.scalars().all())

        return opportunities, total

    async def get_opportunity(self, opportunity_id: int) -> Optional[UpsellOpportunity]:
        """Get opportunity by ID."""
        return await self.session.get(UpsellOpportunity, opportunity_id)

    async def assign_opportunity(
        self,
        opportunity_id: int,
        employee_id: int,
    ) -> UpsellOpportunity:
        """Assign opportunity to a sales rep."""
        opportunity = await self.session.get(UpsellOpportunity, opportunity_id)
        if not opportunity:
            raise ValueError(f"Opportunity {opportunity_id} not found")

        opportunity.assigned_to_id = employee_id
        await self.session.flush()

        return opportunity

    async def mark_contacted(
        self,
        opportunity_id: int,
        method: str,
        notes: Optional[str] = None,
    ) -> UpsellOpportunity:
        """Mark opportunity as contacted."""
        opportunity = await self.session.get(UpsellOpportunity, opportunity_id)
        if not opportunity:
            raise ValueError(f"Opportunity {opportunity_id} not found")

        opportunity.status = UpsellStatus.CONTACTED.value
        opportunity.contacted_at = utc_now()
        opportunity.contact_method = method
        opportunity.contact_notes = notes

        await self.session.flush()
        return opportunity

    async def mark_converted(
        self,
        opportunity_id: int,
        new_subscription_id: int,
        converted_by_id: Optional[int] = None,
    ) -> UpsellOpportunity:
        """Mark opportunity as converted."""
        opportunity = await self.session.get(UpsellOpportunity, opportunity_id)
        if not opportunity:
            raise ValueError(f"Opportunity {opportunity_id} not found")

        opportunity.status = UpsellStatus.CONVERTED.value
        opportunity.converted_at = utc_now()
        opportunity.new_subscription_id = new_subscription_id

        # Create conversion event
        new_sub = await self.session.get(Subscription, new_subscription_id)
        if new_sub:
            days_to_convert = (utc_now() - opportunity.created_at).days

            event = UpsellConversionEvent(
                opportunity_id=opportunity_id,
                subscription_id=new_subscription_id,
                party_id=opportunity.party_id,
                trigger_type=opportunity.trigger_type,
                previous_plan=opportunity.current_plan_name,
                new_plan=new_sub.plan_name,
                previous_mrr=opportunity.current_mrr,
                new_mrr=Decimal(str(new_sub.mrr)),
                mrr_increase=Decimal(str(new_sub.mrr)) - opportunity.current_mrr,
                converted_by_id=converted_by_id,
                days_to_convert=days_to_convert,
            )
            self.session.add(event)

        await self.session.flush()

        # Emit event
        if self.event_bus:
            await self.event_bus.emit(
                "upsell.opportunity_converted",
                {
                    "opportunity_id": opportunity_id,
                    "subscription_id": new_subscription_id,
                    "mrr_increase": float(opportunity.monthly_revenue_increase),
                },
            )

        return opportunity

    async def mark_declined(
        self,
        opportunity_id: int,
        reason: str,
    ) -> UpsellOpportunity:
        """Mark opportunity as declined."""
        opportunity = await self.session.get(UpsellOpportunity, opportunity_id)
        if not opportunity:
            raise ValueError(f"Opportunity {opportunity_id} not found")

        opportunity.status = UpsellStatus.DECLINED.value
        opportunity.declined_at = utc_now()
        opportunity.declined_reason = reason

        await self.session.flush()
        return opportunity

    async def expire_old_opportunities(self) -> int:
        """Expire opportunities past their expiry date."""
        now = utc_now()

        q = select(UpsellOpportunity).where(
            and_(
                UpsellOpportunity.status.in_([
                    UpsellStatus.NEW.value,
                    UpsellStatus.CONTACTED.value,
                    UpsellStatus.QUALIFIED.value,
                ]),
                UpsellOpportunity.expires_at < now,
            )
        )

        result = await self.session.execute(q)
        opportunities = list(result.scalars().all())

        for opp in opportunities:
            opp.status = UpsellStatus.EXPIRED.value
            opp.expired_at = now

        await self.session.flush()
        return len(opportunities)

    # =========================================================================
    # Analytics
    # =========================================================================

    async def get_conversion_stats(
        self,
        period_days: int = 30,
    ) -> ConversionStats:
        """Get conversion statistics for the period."""
        cutoff = utc_now() - timedelta(days=period_days)

        # Total opportunities
        total_q = select(func.count(UpsellOpportunity.id)).where(
            UpsellOpportunity.created_at >= cutoff
        )
        total_result = await self.session.execute(total_q)
        total = total_result.scalar() or 0

        # By status
        status_q = select(
            UpsellOpportunity.status,
            func.count(UpsellOpportunity.id),
        ).where(
            UpsellOpportunity.created_at >= cutoff
        ).group_by(UpsellOpportunity.status)

        status_result = await self.session.execute(status_q)
        status_counts = {row[0]: row[1] for row in status_result.all()}

        converted = status_counts.get(UpsellStatus.CONVERTED.value, 0)
        declined = status_counts.get(UpsellStatus.DECLINED.value, 0)
        expired = status_counts.get(UpsellStatus.EXPIRED.value, 0)

        conversion_rate = (converted / total * 100) if total > 0 else 0

        # MRR gained
        mrr_q = select(func.sum(UpsellConversionEvent.mrr_increase)).where(
            UpsellConversionEvent.converted_at >= cutoff
        )
        mrr_result = await self.session.execute(mrr_q)
        total_mrr = mrr_result.scalar() or Decimal("0")

        avg_mrr = total_mrr / converted if converted > 0 else Decimal("0")

        # Avg days to convert
        days_q = select(func.avg(UpsellConversionEvent.days_to_convert)).where(
            UpsellConversionEvent.converted_at >= cutoff
        )
        days_result = await self.session.execute(days_q)
        avg_days = days_result.scalar() or 0

        # Top triggers
        trigger_q = select(
            UpsellOpportunity.trigger_type,
            func.count(UpsellOpportunity.id).label("count"),
        ).where(
            UpsellOpportunity.created_at >= cutoff
        ).group_by(UpsellOpportunity.trigger_type)

        trigger_result = await self.session.execute(trigger_q)
        top_triggers = [
            (row[0], row[1], 0.0)  # Would calculate conversion rate per trigger
            for row in trigger_result.all()
        ]

        return ConversionStats(
            period=f"{period_days}d",
            total_opportunities=total,
            converted_count=converted,
            declined_count=declined,
            expired_count=expired,
            conversion_rate=conversion_rate,
            total_mrr_gained=total_mrr,
            avg_mrr_per_conversion=avg_mrr,
            avg_days_to_convert=avg_days,
            top_trigger_types=top_triggers,
        )

    async def get_revenue_forecast(self) -> RevenueForecast:
        """Get revenue forecast from active opportunities."""
        q = select(UpsellOpportunity).where(
            UpsellOpportunity.status.in_([
                UpsellStatus.NEW.value,
                UpsellStatus.CONTACTED.value,
                UpsellStatus.QUALIFIED.value,
                UpsellStatus.PROPOSAL_SENT.value,
            ])
        )

        result = await self.session.execute(q)
        opportunities = list(result.scalars().all())

        total = len(opportunities)
        active = len([o for o in opportunities if o.is_active])

        potential_monthly = sum(o.monthly_revenue_increase for o in opportunities)
        potential_annual = potential_monthly * 12

        # Assume 25% conversion rate for forecasting
        expected_rate = 0.25
        expected_monthly = potential_monthly * Decimal(str(expected_rate))
        expected_annual = expected_monthly * 12

        # By trigger type
        by_trigger: Dict[str, Decimal] = {}
        for opp in opportunities:
            by_trigger[opp.trigger_type] = by_trigger.get(
                opp.trigger_type, Decimal("0")
            ) + opp.monthly_revenue_increase

        # By priority
        by_priority: Dict[str, Decimal] = {}
        for opp in opportunities:
            by_priority[opp.priority] = by_priority.get(
                opp.priority, Decimal("0")
            ) + opp.monthly_revenue_increase

        return RevenueForecast(
            total_opportunities=total,
            active_opportunities=active,
            potential_monthly_revenue=potential_monthly,
            potential_annual_revenue=potential_annual,
            expected_conversion_rate=expected_rate,
            expected_monthly_revenue=expected_monthly,
            expected_annual_revenue=expected_annual,
            by_trigger_type=by_trigger,
            by_priority=by_priority,
        )
