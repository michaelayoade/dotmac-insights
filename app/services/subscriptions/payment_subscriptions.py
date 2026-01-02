"""Payment subscription service - business logic for recurring billing.

This service encapsulates payment subscription-related business logic:
- Core CRUD for payment subscriptions
- Billing actions (pause, resume, cancel, retry)
- Link to service subscriptions
- Statistics

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.payment_subscription import (
    PaymentSubscription,
    PaymentSubscriptionStatus,
    PaymentSubscriptionInterval,
)
from app.models.gateway_transaction import GatewayProvider
from app.models.party import Party
from app.models.subscription import Subscription
from app.services.base import paginate, scoped_query
from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.types import PaginatedResult, PaginationParams

from .payment_subscription_types import (
    PaymentSubscriptionFilters,
    PaymentSubscriptionCreateData,
    PaymentSubscriptionUpdateData,
    BillingActionResult,
    PaymentSubscriptionStats,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["PaymentSubscriptionService"]


class PaymentSubscriptionService:
    """Service for payment subscription management."""

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Payment Subscription CRUD
    # -------------------------------------------------------------------------

    def list_payment_subscriptions(
        self,
        filters: Optional[PaymentSubscriptionFilters] = None,
        pagination: Optional[PaginationParams] = None,
        include_relations: bool = True,
    ) -> PaginatedResult[PaymentSubscription]:
        """List payment subscriptions with optional filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.
            include_relations: Whether to eagerly load relations.

        Returns:
            PaginatedResult containing payment subscriptions and total count.
        """
        query = scoped_query(self.db.query(PaymentSubscription), self.principal)

        if filters:
            # Text search
            if filters.search:
                like = f"%{filters.search}%"
                query = query.filter(
                    or_(
                        PaymentSubscription.plan_name.ilike(like),
                        PaymentSubscription.customer_email.ilike(like),
                        PaymentSubscription.plan_code.ilike(like),
                    )
                )

            # Status filter
            if filters.status:
                try:
                    status_enum = PaymentSubscriptionStatus(filters.status)
                    query = query.filter(PaymentSubscription.status == status_enum)
                except ValueError:
                    pass

            # Party filter
            if filters.party_id:
                query = query.filter(PaymentSubscription.party_id == filters.party_id)

            # Provider filter
            if filters.provider:
                try:
                    provider_enum = GatewayProvider(filters.provider)
                    query = query.filter(PaymentSubscription.provider == provider_enum)
                except ValueError:
                    pass

            # Service subscription filter
            if filters.service_subscription_id:
                query = query.filter(
                    PaymentSubscription.service_subscription_id == filters.service_subscription_id
                )

            # Due before filter
            if filters.due_before:
                query = query.filter(PaymentSubscription.next_billing_date <= filters.due_before)

            # Interval filter
            if filters.interval:
                try:
                    interval_enum = PaymentSubscriptionInterval(filters.interval)
                    query = query.filter(PaymentSubscription.interval == interval_enum)
                except ValueError:
                    pass

        query = query.order_by(PaymentSubscription.created_at.desc())
        return paginate(query, pagination)

    def get_payment_subscription(
        self, subscription_id: int
    ) -> PaymentSubscription:
        """Get a payment subscription by ID.

        Args:
            subscription_id: The payment subscription ID.

        Returns:
            The PaymentSubscription.

        Raises:
            NotFoundError: If payment subscription not found.
        """
        query = scoped_query(self.db.query(PaymentSubscription), self.principal)
        sub = query.filter(PaymentSubscription.id == subscription_id).first()
        if not sub:
            raise NotFoundError(f"PaymentSubscription {subscription_id} not found")
        return sub

    def create_payment_subscription(
        self, data: PaymentSubscriptionCreateData
    ) -> PaymentSubscription:
        """Create a new payment subscription.

        Args:
            data: Payment subscription creation data.

        Returns:
            The created PaymentSubscription (not yet committed).

        Raises:
            ValidationError: If validation fails.
        """
        # Validate party exists
        party = self.db.query(Party).filter(Party.id == data.party_id).first()
        if not party:
            raise ValidationError(f"Party {data.party_id} not found")

        # Parse provider
        try:
            provider = GatewayProvider(data.provider)
        except ValueError:
            raise ValidationError(f"Invalid provider: {data.provider}")

        # Parse interval
        try:
            interval = PaymentSubscriptionInterval(data.interval)
        except ValueError:
            raise ValidationError(f"Invalid interval: {data.interval}")

        # Validate service subscription if provided
        if data.service_subscription_id:
            svc_sub = self.db.query(Subscription).filter(
                Subscription.id == data.service_subscription_id
            ).first()
            if not svc_sub:
                raise ValidationError(
                    f"Service subscription {data.service_subscription_id} not found"
                )

        sub = PaymentSubscription(
            party_id=data.party_id,
            customer_email=data.customer_email,
            provider=provider,
            authorization_code=data.authorization_code,
            plan_name=data.plan_name,
            plan_code=data.plan_code,
            description=data.description,
            amount=data.amount,
            currency=data.currency,
            interval=interval,
            interval_count=data.interval_count,
            current_period_start=data.current_period_start,
            current_period_end=data.current_period_end,
            next_billing_date=data.next_billing_date,
            max_charges=data.max_charges,
            service_subscription_id=data.service_subscription_id,
            invoice_template_id=data.invoice_template_id,
            product_id=data.product_id,
            extra_data=data.extra_data,
            company=data.company,
            status=PaymentSubscriptionStatus.ACTIVE,
        )

        self.db.add(sub)
        self.db.flush()

        return sub

    def update_payment_subscription(
        self, subscription_id: int, data: PaymentSubscriptionUpdateData
    ) -> PaymentSubscription:
        """Update a payment subscription.

        Args:
            subscription_id: The payment subscription ID.
            data: Fields to update.

        Returns:
            The updated PaymentSubscription (not yet committed).

        Raises:
            NotFoundError: If payment subscription not found.
        """
        sub = self.get_payment_subscription(subscription_id)

        # Update simple fields
        simple_fields = [
            "plan_name", "description", "amount", "max_charges",
            "next_billing_date", "extra_data",
        ]
        for field_name in simple_fields:
            value = getattr(data, field_name, None)
            if value is not None:
                setattr(sub, field_name, value)

        # Handle service subscription link
        if data.service_subscription_id is not None:
            if data.service_subscription_id:
                svc_sub = self.db.query(Subscription).filter(
                    Subscription.id == data.service_subscription_id
                ).first()
                if not svc_sub:
                    raise ValidationError(
                        f"Service subscription {data.service_subscription_id} not found"
                    )
            sub.service_subscription_id = data.service_subscription_id or None

        return sub

    # -------------------------------------------------------------------------
    # Billing Actions
    # -------------------------------------------------------------------------

    def pause(self, subscription_id: int) -> BillingActionResult:
        """Pause a payment subscription.

        Args:
            subscription_id: The payment subscription ID.

        Returns:
            BillingActionResult with outcome.

        Raises:
            NotFoundError: If payment subscription not found.
            ConflictError: If subscription cannot be paused.
        """
        sub = self.get_payment_subscription(subscription_id)

        if sub.status != PaymentSubscriptionStatus.ACTIVE:
            raise ConflictError(
                f"Cannot pause subscription in {sub.status.value} status"
            )

        sub.status = PaymentSubscriptionStatus.PAUSED
        sub.paused_at = datetime.now(timezone.utc)

        return BillingActionResult(
            success=True,
            action="pause",
            message="Subscription paused",
            new_status="paused",
        )

    def resume(self, subscription_id: int) -> BillingActionResult:
        """Resume a paused payment subscription.

        Args:
            subscription_id: The payment subscription ID.

        Returns:
            BillingActionResult with outcome.

        Raises:
            NotFoundError: If payment subscription not found.
            ConflictError: If subscription cannot be resumed.
        """
        sub = self.get_payment_subscription(subscription_id)

        if sub.status != PaymentSubscriptionStatus.PAUSED:
            raise ConflictError(
                f"Cannot resume subscription in {sub.status.value} status"
            )

        sub.status = PaymentSubscriptionStatus.ACTIVE
        sub.paused_at = None

        return BillingActionResult(
            success=True,
            action="resume",
            message="Subscription resumed",
            new_status="active",
            next_billing_date=sub.next_billing_date,
        )

    def cancel(
        self, subscription_id: int, reason: Optional[str] = None
    ) -> BillingActionResult:
        """Cancel a payment subscription.

        Args:
            subscription_id: The payment subscription ID.
            reason: Optional cancellation reason.

        Returns:
            BillingActionResult with outcome.

        Raises:
            NotFoundError: If payment subscription not found.
            ConflictError: If subscription already cancelled.
        """
        sub = self.get_payment_subscription(subscription_id)

        if sub.status == PaymentSubscriptionStatus.CANCELLED:
            raise ConflictError("Subscription is already cancelled")

        sub.status = PaymentSubscriptionStatus.CANCELLED
        sub.cancelled_at = datetime.now(timezone.utc)
        sub.cancellation_reason = reason
        sub.ended_at = datetime.now(timezone.utc)

        return BillingActionResult(
            success=True,
            action="cancel",
            message="Subscription cancelled",
            new_status="cancelled",
        )

    def mark_past_due(self, subscription_id: int) -> BillingActionResult:
        """Mark a payment subscription as past due.

        Args:
            subscription_id: The payment subscription ID.

        Returns:
            BillingActionResult with outcome.
        """
        sub = self.get_payment_subscription(subscription_id)

        if sub.status != PaymentSubscriptionStatus.ACTIVE:
            raise ConflictError(
                f"Cannot mark past_due for subscription in {sub.status.value} status"
            )

        sub.status = PaymentSubscriptionStatus.PAST_DUE

        return BillingActionResult(
            success=True,
            action="mark_past_due",
            message="Subscription marked as past due",
            new_status="past_due",
        )

    def record_charge_attempt(
        self,
        subscription_id: int,
        success: bool,
        reference: Optional[str] = None,
        amount: Optional[Decimal] = None,
    ) -> PaymentSubscription:
        """Record a charge attempt result.

        Args:
            subscription_id: The payment subscription ID.
            success: Whether the charge succeeded.
            reference: Optional transaction reference.
            amount: Optional charged amount (defaults to subscription amount).

        Returns:
            The updated PaymentSubscription.
        """
        sub = self.get_payment_subscription(subscription_id)

        sub.total_charges += 1
        sub.last_charge_date = datetime.now(timezone.utc)
        sub.last_charge_reference = reference

        if success:
            sub.successful_charges += 1
            sub.last_charge_status = "success"
            sub.retry_count = 0
            charged_amount = amount or sub.amount
            sub.total_collected += charged_amount

            # Check if completed
            if sub.max_charges and sub.successful_charges >= sub.max_charges:
                sub.status = PaymentSubscriptionStatus.COMPLETED
                sub.ended_at = datetime.now(timezone.utc)
        else:
            sub.failed_charges += 1
            sub.last_charge_status = "failed"
            sub.retry_count += 1

            # Mark as past due if max retries exceeded
            if sub.retry_count >= sub.max_retries:
                sub.status = PaymentSubscriptionStatus.PAST_DUE

        return sub

    # -------------------------------------------------------------------------
    # Service Subscription Link
    # -------------------------------------------------------------------------

    def link_to_service_subscription(
        self, subscription_id: int, service_subscription_id: int
    ) -> PaymentSubscription:
        """Link payment subscription to a service subscription.

        Args:
            subscription_id: The payment subscription ID.
            service_subscription_id: The service subscription ID to link.

        Returns:
            The updated PaymentSubscription.

        Raises:
            NotFoundError: If either subscription not found.
        """
        sub = self.get_payment_subscription(subscription_id)

        svc_sub = self.db.query(Subscription).filter(
            Subscription.id == service_subscription_id
        ).first()
        if not svc_sub:
            raise NotFoundError(
                f"Service subscription {service_subscription_id} not found"
            )

        sub.service_subscription_id = service_subscription_id
        return sub

    def unlink_service_subscription(
        self, subscription_id: int
    ) -> PaymentSubscription:
        """Unlink payment subscription from service subscription.

        Args:
            subscription_id: The payment subscription ID.

        Returns:
            The updated PaymentSubscription.
        """
        sub = self.get_payment_subscription(subscription_id)
        sub.service_subscription_id = None
        return sub

    # -------------------------------------------------------------------------
    # Party Integration
    # -------------------------------------------------------------------------

    def get_party_payment_subscriptions(
        self,
        party_id: int,
        active_only: bool = False,
    ) -> List[PaymentSubscription]:
        """Get all payment subscriptions for a party.

        Args:
            party_id: The party ID.
            active_only: Only return active subscriptions.

        Returns:
            List of PaymentSubscription.
        """
        query = self.db.query(PaymentSubscription).filter(
            PaymentSubscription.party_id == party_id
        )
        if active_only:
            query = query.filter(
                PaymentSubscription.status == PaymentSubscriptionStatus.ACTIVE
            )
        return query.order_by(PaymentSubscription.created_at.desc()).all()

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_stats(self) -> PaymentSubscriptionStats:
        """Get payment subscription statistics.

        Returns:
            PaymentSubscriptionStats with aggregate counts.
        """
        base = self.db.query(PaymentSubscription)

        active = base.filter(
            PaymentSubscription.status == PaymentSubscriptionStatus.ACTIVE
        ).count()
        paused = base.filter(
            PaymentSubscription.status == PaymentSubscriptionStatus.PAUSED
        ).count()
        cancelled = base.filter(
            PaymentSubscription.status == PaymentSubscriptionStatus.CANCELLED
        ).count()
        past_due = base.filter(
            PaymentSubscription.status == PaymentSubscriptionStatus.PAST_DUE
        ).count()
        total = base.count()

        # Monthly revenue (only active monthly subscriptions)
        monthly_revenue = self.db.query(func.sum(PaymentSubscription.amount)).filter(
            PaymentSubscription.status == PaymentSubscriptionStatus.ACTIVE,
            PaymentSubscription.interval == PaymentSubscriptionInterval.MONTHLY,
        ).scalar() or Decimal("0")

        # Total collected
        total_collected = self.db.query(
            func.sum(PaymentSubscription.total_collected)
        ).scalar() or Decimal("0")

        return PaymentSubscriptionStats(
            active=active,
            paused=paused,
            cancelled=cancelled,
            past_due=past_due,
            total=total,
            monthly_revenue=monthly_revenue,
            total_collected=total_collected,
        )
