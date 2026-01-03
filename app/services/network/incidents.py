"""Network Incident Service - Outage and incident management."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass

from sqlalchemy import and_, func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.network_incident import (
    NetworkIncident,
    IncidentUpdate,
    IncidentAffectedSubscription,
    IncidentSeverity,
    IncidentStatus,
)
from app.models.router import Router
from app.models.pop import Pop
from app.models.subscription import Subscription, SubscriptionStatus
from app.utils.datetime_utils import utc_now
from app.services.event_bus import EventBus

logger = logging.getLogger(__name__)


@dataclass
class IncidentCreateInput:
    """Input for creating an incident."""
    title: str
    description: Optional[str] = None
    severity: str = IncidentSeverity.MINOR.value
    incident_type: Optional[str] = None
    started_at: Optional[datetime] = None
    affected_pop_ids: Optional[List[int]] = None
    affected_router_ids: Optional[List[int]] = None
    is_public: bool = False
    public_title: Optional[str] = None
    public_description: Optional[str] = None
    assigned_to_id: Optional[int] = None


@dataclass
class IncidentStats:
    """Incident statistics for dashboard."""
    active_incidents: int
    critical_count: int
    major_count: int
    minor_count: int
    maintenance_count: int
    mttr_hours: float  # Mean time to resolve
    incidents_today: int
    incidents_this_week: int
    total_affected_customers: int


class IncidentService:
    """Service for network incident management."""

    def __init__(self, session: AsyncSession, event_bus: Optional[EventBus] = None):
        self.session = session
        self.event_bus = event_bus

    # =========================================================================
    # Incident CRUD
    # =========================================================================

    async def create_incident(
        self,
        input_data: IncidentCreateInput,
        created_by_id: Optional[int] = None,
        auto_detected: bool = False,
    ) -> NetworkIncident:
        """Create a new network incident."""
        now = utc_now()

        incident = NetworkIncident(
            title=input_data.title,
            description=input_data.description,
            severity=input_data.severity,
            status=IncidentStatus.INVESTIGATING.value,
            incident_type=input_data.incident_type,
            started_at=input_data.started_at or now,
            detected_at=now,
            affected_pop_ids=input_data.affected_pop_ids,
            affected_router_ids=input_data.affected_router_ids,
            is_public=input_data.is_public,
            public_title=input_data.public_title,
            public_description=input_data.public_description,
            assigned_to_id=input_data.assigned_to_id,
            auto_detected=auto_detected,
            created_by_id=created_by_id,
        )

        self.session.add(incident)
        await self.session.flush()

        # Calculate affected subscriptions
        await self._calculate_affected_subscriptions(incident)

        # Create initial update
        await self.add_update(
            incident.id,
            IncidentStatus.INVESTIGATING.value,
            f"Incident created: {input_data.title}",
            is_public=input_data.is_public,
            created_by_id=created_by_id,
        )

        # Emit event
        if self.event_bus:
            await self.event_bus.emit(
                "incident.created",
                {
                    "incident_id": incident.id,
                    "severity": incident.severity,
                    "affected_customers": incident.affected_subscription_count,
                },
            )

        logger.info(
            "Incident created",
            extra={
                "incident_id": incident.id,
                "severity": incident.severity,
                "auto_detected": auto_detected,
            },
        )

        return incident

    async def get_incident(
        self,
        incident_id: int,
        include_updates: bool = True,
    ) -> Optional[NetworkIncident]:
        """Get incident by ID."""
        q = select(NetworkIncident).where(NetworkIncident.id == incident_id)

        if include_updates:
            q = q.options(selectinload(NetworkIncident.updates))

        result = await self.session.execute(q)
        return result.scalar()

    async def list_incidents(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_public: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[NetworkIncident], int]:
        """List incidents with filters."""
        q = select(NetworkIncident)
        count_q = select(func.count(NetworkIncident.id))

        filters = []
        if status:
            filters.append(NetworkIncident.status == status)
        if severity:
            filters.append(NetworkIncident.severity == severity)
        if is_active is not None:
            if is_active:
                filters.append(NetworkIncident.status != IncidentStatus.RESOLVED.value)
            else:
                filters.append(NetworkIncident.status == IncidentStatus.RESOLVED.value)
        if is_public is not None:
            filters.append(NetworkIncident.is_public == is_public)

        if filters:
            q = q.where(and_(*filters))
            count_q = count_q.where(and_(*filters))

        # Get total count
        count_result = await self.session.execute(count_q)
        total = count_result.scalar() or 0

        # Get paginated results
        q = q.order_by(NetworkIncident.started_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(q)
        incidents = list(result.scalars().all())

        return incidents, total

    async def update_incident(
        self,
        incident_id: int,
        **kwargs,
    ) -> Optional[NetworkIncident]:
        """Update incident fields."""
        incident = await self.session.get(NetworkIncident, incident_id)
        if not incident:
            return None

        for key, value in kwargs.items():
            if hasattr(incident, key):
                setattr(incident, key, value)

        # Recalculate affected subscriptions if infrastructure changed
        if "affected_pop_ids" in kwargs or "affected_router_ids" in kwargs:
            await self._calculate_affected_subscriptions(incident)

        await self.session.flush()
        return incident

    # =========================================================================
    # Status Updates
    # =========================================================================

    async def add_update(
        self,
        incident_id: int,
        status: str,
        message: str,
        is_public: bool = False,
        public_message: Optional[str] = None,
        created_by_id: Optional[int] = None,
    ) -> IncidentUpdate:
        """Add a status update to an incident."""
        incident = await self.session.get(NetworkIncident, incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")

        # Update incident status
        old_status = incident.status
        incident.status = status

        # Handle resolution
        if status == IncidentStatus.RESOLVED.value and not incident.resolved_at:
            incident.resolved_at = utc_now()
            if incident.started_at:
                delta = incident.resolved_at - incident.started_at
                incident.resolution_time_minutes = int(delta.total_seconds() / 60)

        update = IncidentUpdate(
            incident_id=incident_id,
            status=status,
            message=message,
            is_public=is_public,
            public_message=public_message,
            created_by_id=created_by_id,
        )

        self.session.add(update)
        await self.session.flush()

        # Emit event
        if self.event_bus and old_status != status:
            await self.event_bus.emit(
                "incident.status_changed",
                {
                    "incident_id": incident_id,
                    "old_status": old_status,
                    "new_status": status,
                },
            )

        return update

    async def resolve_incident(
        self,
        incident_id: int,
        resolution: str,
        root_cause: Optional[str] = None,
        root_cause_category: Optional[str] = None,
        created_by_id: Optional[int] = None,
    ) -> NetworkIncident:
        """Resolve an incident."""
        incident = await self.session.get(NetworkIncident, incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")

        incident.resolution = resolution
        incident.root_cause = root_cause
        incident.root_cause_category = root_cause_category

        await self.add_update(
            incident_id,
            IncidentStatus.RESOLVED.value,
            f"Incident resolved: {resolution}",
            is_public=incident.is_public,
            public_message=f"The issue has been resolved. {resolution}" if incident.is_public else None,
            created_by_id=created_by_id,
        )

        # Update affected subscriptions
        await self._mark_subscriptions_recovered(incident_id)

        # Emit event
        if self.event_bus:
            await self.event_bus.emit(
                "incident.resolved",
                {
                    "incident_id": incident_id,
                    "duration_minutes": incident.resolution_time_minutes,
                    "affected_customers": incident.affected_subscription_count,
                },
            )

        return incident

    # =========================================================================
    # Affected Subscriptions
    # =========================================================================

    async def _calculate_affected_subscriptions(
        self,
        incident: NetworkIncident,
    ) -> int:
        """Calculate and record affected subscriptions."""
        now = utc_now()

        # Find subscriptions linked to affected routers/POPs
        filters = [Subscription.status == SubscriptionStatus.ACTIVE]

        if incident.affected_router_ids:
            filters.append(Subscription.router_id.in_(incident.affected_router_ids))
        elif incident.affected_pop_ids:
            # Get routers in affected POPs
            router_q = select(Router.id).where(Router.pop_id.in_(incident.affected_pop_ids))
            router_result = await self.session.execute(router_q)
            router_ids = [r[0] for r in router_result.all()]
            if router_ids:
                filters.append(Subscription.router_id.in_(router_ids))
            else:
                # No routers found, no subscriptions affected
                incident.affected_subscription_count = 0
                return 0

        q = select(Subscription).where(and_(*filters))
        result = await self.session.execute(q)
        subscriptions = list(result.scalars().all())

        # Create affected subscription records
        for sub in subscriptions:
            affected = IncidentAffectedSubscription(
                incident_id=incident.id,
                subscription_id=sub.id,
                impact_start=incident.started_at,
            )
            self.session.add(affected)

        incident.affected_subscription_count = len(subscriptions)
        incident.estimated_customer_count = len(subscriptions)

        await self.session.flush()

        return len(subscriptions)

    async def _mark_subscriptions_recovered(self, incident_id: int) -> None:
        """Mark affected subscriptions as recovered."""
        now = utc_now()

        q = select(IncidentAffectedSubscription).where(
            and_(
                IncidentAffectedSubscription.incident_id == incident_id,
                IncidentAffectedSubscription.impact_end.is_(None),
            )
        )
        result = await self.session.execute(q)
        affected = result.scalars().all()

        for record in affected:
            record.impact_end = now
            if record.impact_start:
                delta = now - record.impact_start
                record.downtime_minutes = int(delta.total_seconds() / 60)

        await self.session.flush()

    async def get_affected_subscriptions(
        self,
        incident_id: int,
    ) -> List[IncidentAffectedSubscription]:
        """Get affected subscriptions for an incident."""
        q = select(IncidentAffectedSubscription).where(
            IncidentAffectedSubscription.incident_id == incident_id
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())

    # =========================================================================
    # Auto-Detection
    # =========================================================================

    async def detect_from_alert(
        self,
        router_id: int,
        interface: str,
        alert_type: str,
        severity: str = IncidentSeverity.MINOR.value,
    ) -> Optional[NetworkIncident]:
        """Auto-create incident from monitoring alert.

        Checks for existing active incidents on the same infrastructure
        to avoid duplicates.
        """
        # Check for existing active incident on this router
        existing_q = select(NetworkIncident).where(
            and_(
                NetworkIncident.status != IncidentStatus.RESOLVED.value,
                NetworkIncident.affected_router_ids.contains([router_id]),
            )
        )
        result = await self.session.execute(existing_q)
        existing = result.scalar()

        if existing:
            # Add update to existing incident
            await self.add_update(
                existing.id,
                existing.status,
                f"Additional alert detected on {interface}: {alert_type}",
            )
            return existing

        # Get router info
        router = await self.session.get(Router, router_id)
        router_name = router.title if router else f"Router {router_id}"

        # Create new incident
        return await self.create_incident(
            IncidentCreateInput(
                title=f"{alert_type} on {router_name} - {interface}",
                description=f"Auto-detected {alert_type} on interface {interface}",
                severity=severity,
                incident_type="network",
                affected_router_ids=[router_id],
            ),
            auto_detected=True,
        )

    async def auto_resolve_if_recovered(
        self,
        router_id: int,
        interface: str,
    ) -> Optional[NetworkIncident]:
        """Auto-resolve incident if monitoring shows recovery."""
        # Find active auto-detected incident for this router
        q = select(NetworkIncident).where(
            and_(
                NetworkIncident.status != IncidentStatus.RESOLVED.value,
                NetworkIncident.auto_detected == True,
                NetworkIncident.affected_router_ids.contains([router_id]),
            )
        )
        result = await self.session.execute(q)
        incident = result.scalar()

        if incident:
            incident.auto_resolved = True
            await self.add_update(
                incident.id,
                IncidentStatus.RESOLVED.value,
                f"Auto-resolved: {interface} recovered",
            )
            incident.resolved_at = utc_now()

            await self._mark_subscriptions_recovered(incident.id)

            return incident

        return None

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_stats(self) -> IncidentStats:
        """Get incident statistics for dashboard."""
        now = utc_now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())

        # Active incidents by severity
        active_q = select(
            NetworkIncident.severity,
            func.count(NetworkIncident.id),
        ).where(
            NetworkIncident.status != IncidentStatus.RESOLVED.value
        ).group_by(NetworkIncident.severity)

        result = await self.session.execute(active_q)
        severity_counts = {row[0]: row[1] for row in result.all()}

        # MTTR for resolved incidents in last 30 days
        mttr_q = select(
            func.avg(NetworkIncident.resolution_time_minutes)
        ).where(
            and_(
                NetworkIncident.status == IncidentStatus.RESOLVED.value,
                NetworkIncident.resolved_at >= now - timedelta(days=30),
                NetworkIncident.resolution_time_minutes.isnot(None),
            )
        )
        mttr_result = await self.session.execute(mttr_q)
        mttr_minutes = mttr_result.scalar() or 0

        # Incidents today/this week
        today_q = select(func.count(NetworkIncident.id)).where(
            NetworkIncident.created_at >= today_start
        )
        today_result = await self.session.execute(today_q)
        incidents_today = today_result.scalar() or 0

        week_q = select(func.count(NetworkIncident.id)).where(
            NetworkIncident.created_at >= week_start
        )
        week_result = await self.session.execute(week_q)
        incidents_week = week_result.scalar() or 0

        # Total affected customers from active incidents
        affected_q = select(
            func.sum(NetworkIncident.affected_subscription_count)
        ).where(
            NetworkIncident.status != IncidentStatus.RESOLVED.value
        )
        affected_result = await self.session.execute(affected_q)
        total_affected = affected_result.scalar() or 0

        active_count = sum(severity_counts.values())

        return IncidentStats(
            active_incidents=active_count,
            critical_count=severity_counts.get(IncidentSeverity.CRITICAL.value, 0),
            major_count=severity_counts.get(IncidentSeverity.MAJOR.value, 0),
            minor_count=severity_counts.get(IncidentSeverity.MINOR.value, 0),
            maintenance_count=severity_counts.get(IncidentSeverity.MAINTENANCE.value, 0),
            mttr_hours=mttr_minutes / 60,
            incidents_today=incidents_today,
            incidents_this_week=incidents_week,
            total_affected_customers=total_affected,
        )
