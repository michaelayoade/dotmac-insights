"""Provisioning service - business logic for MikroTik/RADIUS provisioning.

This service encapsulates provisioning-related business logic:
- Provisioning log management
- Task orchestration (queueing provisioning tasks)
- Router connection testing
- RADIUS user management coordination
- Failed provisioning retry logic

Routes should call this service and control the transaction boundary.
The actual provisioning is executed by Celery tasks calling the
SubscriptionProvisioner from app/integrations/mikrotik/provisioner.py.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session, joinedload

from app.models.provisioning_log import (
    ProvisioningLog,
    ProvisioningAction,
    ProvisioningStatus,
)
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.router import Router
from app.services.base import paginate, scoped_query
from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.types import PaginatedResult, PaginationParams

from .subscription_types import (
    ProvisioningRequest,
    ProvisioningResult,
    ProvisioningLogFilters,
    ProvisioningLogEntry,
    RouterConnectionTest,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["ProvisioningService"]


class ProvisioningService:
    """Service for provisioning management and orchestration."""

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Provisioning Orchestration
    # -------------------------------------------------------------------------

    def queue_provision(self, request: ProvisioningRequest) -> ProvisioningResult:
        """Queue a subscription for provisioning.

        This method validates the subscription is ready for provisioning
        and queues a Celery task. The actual provisioning happens async.

        Args:
            request: Provisioning request data.

        Returns:
            ProvisioningResult with task queuing status.
        """
        sub = self._get_subscription(request.subscription_id)

        # Validation
        if not sub.router_id:
            return ProvisioningResult(
                success=False,
                action="provision",
                message="Subscription has no router assigned",
                error_type="validation_error",
            )

        if not sub.access_method:
            return ProvisioningResult(
                success=False,
                action="provision",
                message="Subscription has no access method configured",
                error_type="validation_error",
            )

        # Check if already provisioned (unless force)
        if sub.provisioned_at and not request.force:
            return ProvisioningResult(
                success=False,
                action="provision",
                message="Subscription is already provisioned. Use force=True to re-provision.",
                error_type="already_provisioned",
            )

        # Queue the Celery task
        from app.tasks.provisioning_tasks import provision_subscription
        task = provision_subscription.delay(
            subscription_id=request.subscription_id,
            force=request.force,
            triggered_by=request.triggered_by,
        )

        return ProvisioningResult(
            success=True,
            action="provision",
            message=f"Provisioning task queued (task_id={task.id})",
        )

    def queue_deprovision(
        self, subscription_id: int, triggered_by: str = "system"
    ) -> ProvisioningResult:
        """Queue a subscription for deprovisioning.

        Args:
            subscription_id: The subscription ID.
            triggered_by: Who triggered this action.

        Returns:
            ProvisioningResult with task queuing status.
        """
        sub = self._get_subscription(subscription_id)

        if not sub.provisioned_at:
            return ProvisioningResult(
                success=False,
                action="deprovision",
                message="Subscription is not provisioned",
                error_type="not_provisioned",
            )

        from app.tasks.provisioning_tasks import deprovision_subscription
        task = deprovision_subscription.delay(
            subscription_id=subscription_id,
            triggered_by=triggered_by,
        )

        return ProvisioningResult(
            success=True,
            action="deprovision",
            message=f"Deprovisioning task queued (task_id={task.id})",
        )

    def queue_disconnect(
        self, subscription_id: int, triggered_by: str = "system"
    ) -> ProvisioningResult:
        """Queue a session disconnect for a subscription.

        Args:
            subscription_id: The subscription ID.
            triggered_by: Who triggered this action.

        Returns:
            ProvisioningResult with task queuing status.
        """
        sub = self._get_subscription(subscription_id)

        if not sub.provisioned_at:
            return ProvisioningResult(
                success=False,
                action="disconnect",
                message="Subscription is not provisioned",
                error_type="not_provisioned",
            )

        from app.tasks.provisioning_tasks import disconnect_subscription_session
        task = disconnect_subscription_session.delay(
            subscription_id=subscription_id,
            triggered_by=triggered_by,
        )

        return ProvisioningResult(
            success=True,
            action="disconnect",
            message=f"Disconnect task queued (task_id={task.id})",
        )

    def queue_update(
        self, subscription_id: int, triggered_by: str = "system"
    ) -> ProvisioningResult:
        """Queue a provisioning update (for speed/IP changes).

        Args:
            subscription_id: The subscription ID.
            triggered_by: Who triggered this action.

        Returns:
            ProvisioningResult with task queuing status.
        """
        sub = self._get_subscription(subscription_id)

        if not sub.provisioned_at:
            return ProvisioningResult(
                success=False,
                action="update",
                message="Subscription is not provisioned",
                error_type="not_provisioned",
            )

        from app.tasks.provisioning_tasks import update_subscription_provisioning
        task = update_subscription_provisioning.delay(
            subscription_id=subscription_id,
            triggered_by=triggered_by,
        )

        return ProvisioningResult(
            success=True,
            action="update",
            message=f"Update task queued (task_id={task.id})",
        )

    def retry_failed(self, log_id: int) -> ProvisioningResult:
        """Retry a failed provisioning operation.

        Args:
            log_id: The provisioning log ID to retry.

        Returns:
            ProvisioningResult with retry status.
        """
        log = self.get_log(log_id)

        if not log.can_retry:
            return ProvisioningResult(
                success=False,
                action=log.action.value,
                message=f"Cannot retry: status={log.status.value}, retries={log.retry_count}/{log.max_retries}",
                error_type="cannot_retry",
            )

        from app.tasks.provisioning_tasks import retry_failed_provisioning
        task = retry_failed_provisioning.delay(log_id=log_id)

        return ProvisioningResult(
            success=True,
            action=log.action.value,
            message=f"Retry task queued (task_id={task.id})",
            log_id=log_id,
        )

    # -------------------------------------------------------------------------
    # Router Connection Testing
    # -------------------------------------------------------------------------

    def test_router_connection(self, router_id: int) -> RouterConnectionTest:
        """Test connection to a router.

        Args:
            router_id: The router ID.

        Returns:
            RouterConnectionTest with connection status.
        """
        router = self.db.query(Router).filter(Router.id == router_id).first()
        if not router:
            raise NotFoundError(f"Router {router_id} not found")

        from app.tasks.provisioning_tasks import test_router_connection
        task = test_router_connection.delay(router_id=router_id)

        # Wait for result (with timeout)
        try:
            result = task.get(timeout=30)
            return RouterConnectionTest(
                router_id=router_id,
                router_title=router.title,
                success=result.get("success", False),
                message=result.get("message", "Unknown result"),
                routeros_version=result.get("routeros_version"),
                uptime=result.get("uptime"),
                response_time_ms=result.get("response_time_ms"),
            )
        except Exception as e:
            return RouterConnectionTest(
                router_id=router_id,
                router_title=router.title,
                success=False,
                message=f"Connection test failed: {str(e)}",
            )

    # -------------------------------------------------------------------------
    # Provisioning Logs
    # -------------------------------------------------------------------------

    def list_logs(
        self,
        filters: Optional[ProvisioningLogFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[ProvisioningLog]:
        """List provisioning logs with optional filters.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.

        Returns:
            PaginatedResult containing logs and total count.
        """
        query = self.db.query(ProvisioningLog).options(
            joinedload(ProvisioningLog.subscription),
            joinedload(ProvisioningLog.router),
        )

        if filters:
            if filters.subscription_id:
                query = query.filter(
                    ProvisioningLog.subscription_id == filters.subscription_id
                )

            if filters.router_id:
                query = query.filter(ProvisioningLog.router_id == filters.router_id)

            if filters.action:
                try:
                    action = ProvisioningAction(filters.action)
                    query = query.filter(ProvisioningLog.action == action)
                except ValueError:
                    pass

            if filters.status:
                try:
                    status = ProvisioningStatus(filters.status)
                    query = query.filter(ProvisioningLog.status == status)
                except ValueError:
                    pass

            if filters.access_method:
                query = query.filter(
                    ProvisioningLog.access_method == filters.access_method
                )

            if filters.triggered_by:
                query = query.filter(
                    ProvisioningLog.triggered_by == filters.triggered_by
                )

            if filters.date_from:
                query = query.filter(ProvisioningLog.started_at >= filters.date_from)

            if filters.date_to:
                query = query.filter(ProvisioningLog.started_at <= filters.date_to)

            if filters.failed_only:
                query = query.filter(
                    ProvisioningLog.status == ProvisioningStatus.FAILED
                )

        query = query.order_by(ProvisioningLog.started_at.desc())
        return paginate(query, pagination)

    def get_log(self, log_id: int) -> ProvisioningLog:
        """Get a provisioning log by ID.

        Args:
            log_id: The log ID.

        Returns:
            The ProvisioningLog.

        Raises:
            NotFoundError: If log not found.
        """
        log = self.db.query(ProvisioningLog).filter(
            ProvisioningLog.id == log_id
        ).first()
        if not log:
            raise NotFoundError(f"ProvisioningLog {log_id} not found")
        return log

    def get_subscription_logs(
        self, subscription_id: int, limit: int = 10
    ) -> List[ProvisioningLog]:
        """Get recent provisioning logs for a subscription.

        Args:
            subscription_id: The subscription ID.
            limit: Maximum number of logs to return.

        Returns:
            List of ProvisioningLog.
        """
        return (
            self.db.query(ProvisioningLog)
            .filter(ProvisioningLog.subscription_id == subscription_id)
            .order_by(ProvisioningLog.started_at.desc())
            .limit(limit)
            .all()
        )

    def get_failed_logs(self, limit: int = 50) -> List[ProvisioningLog]:
        """Get recent failed provisioning logs that can be retried.

        Args:
            limit: Maximum number of logs to return.

        Returns:
            List of ProvisioningLog that can be retried.
        """
        return (
            self.db.query(ProvisioningLog)
            .filter(
                ProvisioningLog.status == ProvisioningStatus.FAILED,
                ProvisioningLog.retry_count < ProvisioningLog.max_retries,
            )
            .order_by(ProvisioningLog.started_at.desc())
            .limit(limit)
            .all()
        )

    def create_log(
        self,
        subscription_id: int,
        router_id: int,
        action: str,
        access_method: str,
        triggered_by: str = "system",
        request_data: Optional[dict] = None,
    ) -> ProvisioningLog:
        """Create a new provisioning log entry.

        Args:
            subscription_id: The subscription ID.
            router_id: The router ID.
            action: The action being performed.
            access_method: The access method.
            triggered_by: Who triggered this action.
            request_data: Optional request data dict.

        Returns:
            The created ProvisioningLog.
        """
        try:
            action_enum = ProvisioningAction(action)
        except ValueError:
            raise ValidationError(f"Invalid action: {action}")

        log = ProvisioningLog(
            subscription_id=subscription_id,
            router_id=router_id,
            action=action_enum,
            access_method=access_method,
            status=ProvisioningStatus.PENDING,
            triggered_by=triggered_by,
            request_data=json.dumps(request_data) if request_data else None,
        )

        self.db.add(log)
        self.db.flush()
        return log

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Get provisioning statistics.

        Returns:
            Dictionary with provisioning statistics.
        """
        base = self.db.query(ProvisioningLog)

        # Recent stats (last 24 hours)
        yesterday = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        total_today = base.filter(ProvisioningLog.started_at >= yesterday).count()

        success_today = base.filter(
            ProvisioningLog.started_at >= yesterday,
            ProvisioningLog.status == ProvisioningStatus.SUCCESS,
        ).count()

        failed_today = base.filter(
            ProvisioningLog.started_at >= yesterday,
            ProvisioningLog.status == ProvisioningStatus.FAILED,
        ).count()

        pending = base.filter(
            ProvisioningLog.status == ProvisioningStatus.PENDING
        ).count()

        retryable = base.filter(
            ProvisioningLog.status == ProvisioningStatus.FAILED,
            ProvisioningLog.retry_count < ProvisioningLog.max_retries,
        ).count()

        # Action breakdown
        action_counts = {}
        for action in ProvisioningAction:
            count = base.filter(
                ProvisioningLog.action == action,
                ProvisioningLog.started_at >= yesterday,
            ).count()
            action_counts[action.value] = count

        # Average duration (successful ops)
        avg_duration = self.db.query(func.avg(ProvisioningLog.duration_ms)).filter(
            ProvisioningLog.status == ProvisioningStatus.SUCCESS,
            ProvisioningLog.duration_ms.isnot(None),
        ).scalar() or 0

        return {
            "total_today": total_today,
            "success_today": success_today,
            "failed_today": failed_today,
            "success_rate": round(success_today / total_today * 100, 1) if total_today > 0 else 0,
            "pending": pending,
            "retryable": retryable,
            "action_counts": action_counts,
            "avg_duration_ms": round(avg_duration),
        }

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _get_subscription(self, subscription_id: int) -> Subscription:
        """Get a subscription with validation."""
        sub = self.db.query(Subscription).filter(
            Subscription.id == subscription_id
        ).first()
        if not sub:
            raise NotFoundError(f"Subscription {subscription_id} not found")
        return sub

    def is_ready_for_provisioning(self, subscription_id: int) -> tuple[bool, str]:
        """Check if a subscription is ready for provisioning.

        Args:
            subscription_id: The subscription ID.

        Returns:
            Tuple of (is_ready, reason).
        """
        sub = self._get_subscription(subscription_id)

        if not sub.router_id:
            return False, "No router assigned"

        if not sub.access_method:
            return False, "No access method configured"

        # Check access method requirements
        if sub.access_method in ("pppoe", "hotspot"):
            if not sub.ppp_username or not sub.ppp_password:
                return False, f"{sub.access_method} requires PPP credentials"

        if sub.access_method in ("dhcp", "static"):
            if not sub.mac_address:
                return False, f"{sub.access_method} requires MAC address"

        if not sub.download_speed or not sub.upload_speed:
            return False, "Speed limits not configured"

        return True, "Ready for provisioning"
