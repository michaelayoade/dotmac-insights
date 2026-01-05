"""Dispatch service for field service dispatch operations.

This service handles:
- Dispatch board views
- Bulk assignment operations
- Route optimization suggestions
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.field_service import (
    ServiceOrder,
    ServiceOrderStatus,
    FieldTeam,
    FieldTeamMember,
)
from app.models.employee import Employee
from app.services.customer_notifications import get_notification_service

from .dispatch_types import (
    DispatchBoardOrder,
    DispatchBoardView,
    DispatchBoardSummary,
    TechnicianWorkload,
    BulkAssignData,
    BulkAssignResult,
    BulkAssignError,
    RouteSuggestion,
    RouteOptimizationResult,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["DispatchService"]


class DispatchService:
    """Service for managing field service dispatch.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for audit fields).
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Dispatch Board
    # -------------------------------------------------------------------------

    def get_dispatch_board(
        self,
        board_date: Optional[date] = None,
        company: Optional[str] = None,
    ) -> DispatchBoardView:
        """Get dispatch board view for a given date.

        Args:
            board_date: Date for dispatch board (defaults to today)
            company: Optional company filter

        Returns:
            DispatchBoardView with orders grouped by status
        """
        check_date = board_date or date.today()

        # Get all orders for this date
        query = self.db.query(ServiceOrder).filter(
            ServiceOrder.scheduled_date == check_date
        )
        if company:
            query = query.filter(ServiceOrder.company == company)

        orders = query.order_by(
            ServiceOrder.priority.desc(),
            ServiceOrder.scheduled_start_time,
        ).all()

        # Group by status
        by_status: Dict[str, List[DispatchBoardOrder]] = {
            "unassigned": [],
            "assigned": [],
            "en_route": [],
            "on_site": [],
            "in_progress": [],
            "completed": [],
        }

        for order in orders:
            order_data = DispatchBoardOrder(
                id=order.id,
                order_number=order.order_number,
                title=order.title,
                order_type=order.order_type.value,
                status=order.status.value,
                priority=order.priority.value,
                scheduled_start_time=(
                    order.scheduled_start_time.isoformat()
                    if order.scheduled_start_time
                    else None
                ),
                estimated_duration_hours=float(order.estimated_duration_hours),
                customer_name=order.customer.name if order.customer else None,
                service_address=order.service_address,
                city=order.city,
                technician_id=order.assigned_technician_id,
                technician_name=order.technician.name if order.technician else None,
                team_id=order.assigned_team_id,
                is_overdue=order.is_overdue,
            )

            if (
                order.status
                in [ServiceOrderStatus.DRAFT, ServiceOrderStatus.SCHEDULED]
                and not order.assigned_technician_id
            ):
                by_status["unassigned"].append(order_data)
            elif order.status == ServiceOrderStatus.DISPATCHED:
                by_status["assigned"].append(order_data)
            elif order.status == ServiceOrderStatus.EN_ROUTE:
                by_status["en_route"].append(order_data)
            elif order.status == ServiceOrderStatus.ON_SITE:
                by_status["on_site"].append(order_data)
            elif order.status == ServiceOrderStatus.IN_PROGRESS:
                by_status["in_progress"].append(order_data)
            elif order.status == ServiceOrderStatus.COMPLETED:
                by_status["completed"].append(order_data)

        # Get technicians with their workload
        tech_query = (
            self.db.query(Employee)
            .join(
                FieldTeamMember,
                and_(
                    FieldTeamMember.party_id == Employee.party_id,
                    FieldTeamMember.is_active == True,
                ),
            )
            .distinct()
        )
        if company:
            tech_query = tech_query.filter(Employee.company == company)

        technicians = tech_query.all()

        tech_workload = []
        for tech in technicians:
            tech_orders = [o for o in orders if o.assigned_technician_id == tech.id]
            tech_workload.append(
                TechnicianWorkload(
                    technician_id=tech.id,
                    technician_name=tech.name,
                    total_orders=len(tech_orders),
                    completed=sum(
                        1
                        for o in tech_orders
                        if o.status == ServiceOrderStatus.COMPLETED
                    ),
                    in_progress=sum(
                        1
                        for o in tech_orders
                        if o.status == ServiceOrderStatus.IN_PROGRESS
                    ),
                    pending=sum(
                        1
                        for o in tech_orders
                        if o.status
                        in [
                            ServiceOrderStatus.DISPATCHED,
                            ServiceOrderStatus.EN_ROUTE,
                            ServiceOrderStatus.ON_SITE,
                        ]
                    ),
                )
            )

        summary = DispatchBoardSummary(
            total=len(orders),
            unassigned=len(by_status["unassigned"]),
            assigned=len(by_status["assigned"]),
            in_field=(
                len(by_status["en_route"])
                + len(by_status["on_site"])
                + len(by_status["in_progress"])
            ),
            completed=len(by_status["completed"]),
        )

        return DispatchBoardView(
            date=check_date.isoformat(),
            orders={k: v for k, v in by_status.items()},
            summary=summary,
            technician_workload=tech_workload,
        )

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def bulk_assign(self, data: BulkAssignData) -> BulkAssignResult:
        """Bulk assign orders to a technician.

        Args:
            data: Bulk assign data

        Returns:
            BulkAssignResult with assigned IDs and errors

        Raises:
            NotFoundError: If technician not found
            ValidationError: If no valid orders found
        """
        from app.services.errors import NotFoundError, ValidationError

        # Validate technician
        technician = (
            self.db.query(Employee).filter(Employee.id == data.technician_id).first()
        )
        if not technician:
            raise NotFoundError(f"Technician with ID {data.technician_id} not found")

        # Get orders
        orders = (
            self.db.query(ServiceOrder)
            .filter(ServiceOrder.id.in_(data.order_ids))
            .all()
        )

        if not orders:
            raise ValidationError("No valid orders found")

        notification_service = get_notification_service(self.db)
        assigned = []
        errors = []

        for order in orders:
            if order.status not in [
                ServiceOrderStatus.DRAFT,
                ServiceOrderStatus.SCHEDULED,
            ]:
                errors.append(
                    BulkAssignError(
                        order_id=order.id,
                        error=f"Cannot assign order in {order.status.value} status",
                    )
                )
                continue

            order.assigned_technician_id = data.technician_id
            if data.team_id:
                order.assigned_team_id = data.team_id

            order.status = ServiceOrderStatus.DISPATCHED

            # Notify customer if requested
            if data.notify_customers:
                try:
                    notification_service.notify_technician_assigned(order)
                    order.customer_notified = True
                    order.last_notification_at = datetime.now(timezone.utc)
                except Exception as e:
                    errors.append(
                        BulkAssignError(
                            order_id=order.id,
                            error=f"Notification failed: {str(e)}",
                        )
                    )

            assigned.append(order.id)

        return BulkAssignResult(
            assigned=assigned,
            assigned_count=len(assigned),
            technician_name=technician.name,
            errors=errors,
        )

    # -------------------------------------------------------------------------
    # Route Optimization
    # -------------------------------------------------------------------------

    def get_route_suggestions(
        self,
        suggestion_date: date,
        company: Optional[str] = None,
    ) -> RouteOptimizationResult:
        """Get route optimization suggestions for unassigned orders.

        Args:
            suggestion_date: Date to optimize
            company: Optional company filter

        Returns:
            RouteOptimizationResult with suggestions
        """
        # Get unassigned orders
        unassigned_query = self.db.query(ServiceOrder).filter(
            ServiceOrder.scheduled_date == suggestion_date,
            ServiceOrder.assigned_technician_id.is_(None),
            ServiceOrder.status.in_(
                [ServiceOrderStatus.DRAFT, ServiceOrderStatus.SCHEDULED]
            ),
        )
        if company:
            unassigned_query = unassigned_query.filter(
                ServiceOrder.company == company
            )

        unassigned = unassigned_query.all()

        # Get technicians with availability
        tech_query = (
            self.db.query(Employee)
            .join(
                FieldTeamMember,
                and_(
                    FieldTeamMember.party_id == Employee.party_id,
                    FieldTeamMember.is_active == True,
                ),
            )
            .distinct()
        )
        if company:
            tech_query = tech_query.filter(Employee.company == company)

        technicians = tech_query.all()

        suggestions = []

        for order in unassigned:
            # Find best technician based on:
            # 1. Zone coverage
            # 2. Current workload
            # 3. Skills (if applicable)

            best_match = None
            best_score = -1

            for tech in technicians:
                score = 0

                # Check workload
                tech_orders = (
                    self.db.query(func.count(ServiceOrder.id))
                    .filter(
                        ServiceOrder.assigned_technician_id == tech.id,
                        ServiceOrder.scheduled_date == suggestion_date,
                        ServiceOrder.status.notin_([ServiceOrderStatus.CANCELLED]),
                    )
                    .scalar()
                    or 0
                )

                if tech_orders >= 10:  # Max orders reached
                    continue

                # Lower workload = higher score
                score += (10 - tech_orders) * 10

                # Zone matching
                membership = (
                    self.db.query(FieldTeamMember)
                    .filter(
                        FieldTeamMember.party_id == tech.party_id,
                        FieldTeamMember.is_active == True,
                    )
                    .first()
                )

                if membership and membership.team and order.zone_id:
                    if (
                        membership.team.coverage_zone_ids
                        and order.zone_id in membership.team.coverage_zone_ids
                    ):
                        score += 50  # Zone match bonus

                if score > best_score:
                    best_score = score
                    best_match = tech

            if best_match:
                suggestions.append(
                    RouteSuggestion(
                        order_id=order.id,
                        order_number=order.order_number,
                        title=order.title,
                        customer_name=order.customer.name if order.customer else None,
                        service_address=order.service_address,
                        city=order.city,
                        priority=order.priority.value,
                        suggested_technician_id=best_match.id,
                        suggested_technician_name=best_match.name,
                        confidence_score=min(100, best_score),
                    )
                )

        return RouteOptimizationResult(
            date=suggestion_date.isoformat(),
            unassigned_count=len(unassigned),
            suggestions=suggestions,
        )
