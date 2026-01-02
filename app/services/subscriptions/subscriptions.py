"""Subscription service - business logic for service subscriptions.

This service encapsulates subscription-related business logic:
- Core CRUD for subscriptions
- Status management with state machine
- Network assignment
- Provisioning triggers
- Party integration

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionType
from app.models.tariff import Tariff
from app.models.router import Router
from app.models.party import Party, PartyRole
from app.services.base import paginate, scoped_query, safe_filter
from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.types import PaginatedResult, PaginationParams

from .subscription_types import (
    SubscriptionFilters,
    SubscriptionCreateData,
    SubscriptionUpdateData,
    NetworkAssignmentData,
    ProvisioningConfigData,
    StatusTransition,
    SubscriptionStats,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["SubscriptionService"]


# Valid status transitions (state machine)
STATUS_TRANSITIONS = {
    SubscriptionStatus.PENDING: [
        StatusTransition("active", "Activate", "emerald"),
        StatusTransition("cancelled", "Cancel", "red"),
    ],
    SubscriptionStatus.ACTIVE: [
        StatusTransition("suspended", "Suspend", "amber"),
        StatusTransition("cancelled", "Cancel", "red"),
    ],
    SubscriptionStatus.SUSPENDED: [
        StatusTransition("active", "Reactivate", "emerald"),
        StatusTransition("cancelled", "Cancel", "red"),
    ],
    SubscriptionStatus.CANCELLED: [],
}


class SubscriptionService:
    """Service for subscription management."""

    ALLOWED_FILTERS = {"party_id", "router_id", "tariff_id"}

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Subscription CRUD
    # -------------------------------------------------------------------------

    def list_subscriptions(
        self,
        filters: Optional[SubscriptionFilters] = None,
        pagination: Optional[PaginationParams] = None,
        include_relations: bool = True,
    ) -> PaginatedResult[Subscription]:
        """List subscriptions with optional filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.
            include_relations: Whether to eagerly load relations.

        Returns:
            PaginatedResult containing subscriptions and total count.
        """
        query = scoped_query(self.db.query(Subscription), self.principal)

        if include_relations:
            query = query.options(
                joinedload(Subscription.tariff),
                joinedload(Subscription.router),
            )

        if filters:
            # Text search
            if filters.search:
                like = f"%{filters.search}%"
                query = query.filter(
                    or_(
                        Subscription.plan_name.ilike(like),
                        Subscription.ipv4_address.ilike(like),
                        Subscription.mac_address.ilike(like),
                        Subscription.ppp_username.ilike(like),
                    )
                )

            # Status filter
            if filters.status:
                try:
                    status_enum = SubscriptionStatus(filters.status)
                    query = query.filter(Subscription.status == status_enum)
                except ValueError:
                    pass

            # Service type filter
            if filters.service_type:
                try:
                    type_enum = SubscriptionType(filters.service_type)
                    query = query.filter(Subscription.service_type == type_enum)
                except ValueError:
                    pass

            # Direct filters
            if filters.party_id:
                query = query.filter(Subscription.party_id == filters.party_id)

            if filters.router_id:
                query = query.filter(Subscription.router_id == filters.router_id)

            if filters.tariff_id:
                query = query.filter(Subscription.tariff_id == filters.tariff_id)

            if filters.billing_cycle:
                query = query.filter(Subscription.billing_cycle == filters.billing_cycle)

            # Has router filter
            if filters.has_router is not None:
                if filters.has_router:
                    query = query.filter(Subscription.router_id.isnot(None))
                else:
                    query = query.filter(Subscription.router_id.is_(None))

            # Is provisioned filter
            if filters.is_provisioned is not None:
                if filters.is_provisioned:
                    query = query.filter(Subscription.provisioned_at.isnot(None))
                else:
                    query = query.filter(Subscription.provisioned_at.is_(None))

        query = query.order_by(Subscription.created_at.desc())
        return paginate(query, pagination)

    def get_subscription(
        self, subscription_id: int, include_relations: bool = True
    ) -> Subscription:
        """Get a subscription by ID.

        Args:
            subscription_id: The subscription ID.
            include_relations: Whether to eagerly load relations.

        Returns:
            The Subscription.

        Raises:
            NotFoundError: If subscription not found.
        """
        query = scoped_query(self.db.query(Subscription), self.principal)

        if include_relations:
            query = query.options(
                joinedload(Subscription.tariff),
                joinedload(Subscription.router),
            )

        sub = query.filter(Subscription.id == subscription_id).first()
        if not sub:
            raise NotFoundError(f"Subscription {subscription_id} not found")

        return sub

    def create_subscription(self, data: SubscriptionCreateData) -> Subscription:
        """Create a new subscription.

        Args:
            data: Subscription creation data.

        Returns:
            The created Subscription (not yet committed).

        Raises:
            ValidationError: If validation fails.
        """
        # Validate party exists
        party = self.db.query(Party).filter(Party.id == data.party_id).first()
        if not party:
            raise ValidationError(f"Party {data.party_id} not found")

        # Validate tariff if provided
        if data.tariff_id:
            tariff = self.db.query(Tariff).filter(Tariff.id == data.tariff_id).first()
            if not tariff:
                raise ValidationError(f"Tariff {data.tariff_id} not found")

        # Validate router if provided
        if data.router_id:
            router = self.db.query(Router).filter(Router.id == data.router_id).first()
            if not router:
                raise ValidationError(f"Router {data.router_id} not found")

        # Parse status
        try:
            status = SubscriptionStatus(data.status)
        except ValueError:
            status = SubscriptionStatus.PENDING

        # Parse service type
        try:
            service_type = SubscriptionType(data.service_type)
        except ValueError:
            service_type = SubscriptionType.INTERNET

        sub = Subscription(
            party_id=data.party_id,
            tariff_id=data.tariff_id,
            splynx_tariff_id=data.splynx_tariff_id,
            splynx_id=data.splynx_id,
            service_type=service_type,
            plan_name=data.plan_name,
            plan_code=data.plan_code,
            description=data.description,
            price=data.price,
            currency=data.currency,
            billing_cycle=data.billing_cycle,
            download_speed=data.download_speed,
            upload_speed=data.upload_speed,
            data_cap=data.data_cap,
            router_id=data.router_id,
            ipv4_address=data.ipv4_address,
            ipv6_address=data.ipv6_address,
            mac_address=data.mac_address,
            access_method=data.access_method,
            ppp_username=data.ppp_username,
            ppp_password=data.ppp_password,
            status=status,
            start_date=data.start_date,
            end_date=data.end_date,
        )

        self.db.add(sub)
        self.db.flush()

        return sub

    def update_subscription(
        self, subscription_id: int, data: SubscriptionUpdateData
    ) -> Subscription:
        """Update a subscription.

        Args:
            subscription_id: The subscription ID.
            data: Fields to update.

        Returns:
            The updated Subscription (not yet committed).

        Raises:
            NotFoundError: If subscription not found.
        """
        sub = self.get_subscription(subscription_id, include_relations=False)

        # Update simple fields
        simple_fields = [
            "plan_name", "plan_code", "description", "price", "currency",
            "billing_cycle", "download_speed", "upload_speed", "data_cap",
            "tariff_id", "start_date", "end_date",
        ]
        for field_name in simple_fields:
            value = getattr(data, field_name, None)
            if value is not None:
                setattr(sub, field_name, value)

        # Handle service type
        if data.service_type:
            try:
                sub.service_type = SubscriptionType(data.service_type)
            except ValueError:
                pass

        return sub

    def delete_subscription(self, subscription_id: int) -> None:
        """Delete a subscription (soft delete via cancel).

        Args:
            subscription_id: The subscription ID.

        Raises:
            NotFoundError: If subscription not found.
        """
        sub = self.get_subscription(subscription_id, include_relations=False)
        sub.status = SubscriptionStatus.CANCELLED
        sub.cancelled_date = datetime.now(timezone.utc)

    # -------------------------------------------------------------------------
    # Status Management
    # -------------------------------------------------------------------------

    def get_available_transitions(self, subscription_id: int) -> List[StatusTransition]:
        """Get available status transitions for a subscription.

        Args:
            subscription_id: The subscription ID.

        Returns:
            List of available transitions.
        """
        sub = self.get_subscription(subscription_id, include_relations=False)
        return STATUS_TRANSITIONS.get(sub.status, [])

    def change_status(
        self,
        subscription_id: int,
        new_status: str,
        reason: Optional[str] = None,
    ) -> Subscription:
        """Change subscription status with validation.

        Args:
            subscription_id: The subscription ID.
            new_status: The target status.
            reason: Optional reason for the change.

        Returns:
            The updated Subscription.

        Raises:
            NotFoundError: If subscription not found.
            ValidationError: If invalid status.
            ConflictError: If transition not allowed.
        """
        sub = self.get_subscription(subscription_id, include_relations=False)

        try:
            target = SubscriptionStatus(new_status)
        except ValueError:
            raise ValidationError(f"Invalid status: {new_status}")

        # Validate transition
        allowed = STATUS_TRANSITIONS.get(sub.status, [])
        if not any(t.target_status == new_status for t in allowed):
            raise ConflictError(
                f"Cannot transition from {sub.status.value} to {new_status}"
            )

        sub.status = target

        if target == SubscriptionStatus.CANCELLED:
            sub.cancelled_date = datetime.now(timezone.utc)

        return sub

    def activate(self, subscription_id: int) -> Subscription:
        """Activate a subscription and create subscriber role.

        Args:
            subscription_id: The subscription ID.

        Returns:
            The activated Subscription.
        """
        sub = self.change_status(subscription_id, "active")

        # Create subscriber PartyRole if party linked
        if sub.party_id:
            self._ensure_subscriber_role(sub.party_id)

        return sub

    def suspend(
        self, subscription_id: int, reason: Optional[str] = None
    ) -> Subscription:
        """Suspend a subscription.

        Args:
            subscription_id: The subscription ID.
            reason: Optional reason for suspension.

        Returns:
            The suspended Subscription.
        """
        return self.change_status(subscription_id, "suspended", reason)

    def cancel(
        self, subscription_id: int, reason: Optional[str] = None
    ) -> Subscription:
        """Cancel a subscription.

        Args:
            subscription_id: The subscription ID.
            reason: Optional reason for cancellation.

        Returns:
            The cancelled Subscription.
        """
        return self.change_status(subscription_id, "cancelled", reason)

    def reactivate(self, subscription_id: int) -> Subscription:
        """Reactivate a suspended subscription.

        Args:
            subscription_id: The subscription ID.

        Returns:
            The reactivated Subscription.
        """
        sub = self.change_status(subscription_id, "active")

        if sub.party_id:
            self._ensure_subscriber_role(sub.party_id)

        return sub

    # -------------------------------------------------------------------------
    # Network Assignment
    # -------------------------------------------------------------------------

    def assign_network(
        self, subscription_id: int, data: NetworkAssignmentData
    ) -> Subscription:
        """Assign network resources to a subscription.

        Args:
            subscription_id: The subscription ID.
            data: Network assignment data.

        Returns:
            The updated Subscription.

        Raises:
            NotFoundError: If subscription not found.
            ValidationError: If router not found.
        """
        sub = self.get_subscription(subscription_id, include_relations=False)

        if data.router_id is not None:
            if data.router_id:
                router = self.db.query(Router).filter(
                    Router.id == data.router_id
                ).first()
                if not router:
                    raise ValidationError(f"Router {data.router_id} not found")
            sub.router_id = data.router_id if data.router_id else None

        if data.ipv4_address is not None:
            sub.ipv4_address = data.ipv4_address or None

        if data.ipv6_address is not None:
            sub.ipv6_address = data.ipv6_address or None

        if data.mac_address is not None:
            sub.mac_address = data.mac_address or None

        return sub

    def configure_provisioning(
        self, subscription_id: int, data: ProvisioningConfigData
    ) -> Subscription:
        """Configure provisioning settings.

        Args:
            subscription_id: The subscription ID.
            data: Provisioning configuration data.

        Returns:
            The updated Subscription.
        """
        sub = self.get_subscription(subscription_id, include_relations=False)

        if data.router_id is not None:
            sub.router_id = data.router_id if data.router_id else None

        if data.access_method is not None:
            sub.access_method = data.access_method or None

        if data.ppp_username is not None:
            sub.ppp_username = data.ppp_username or None

        if data.ppp_password is not None:
            sub.ppp_password = data.ppp_password or None

        return sub

    def mark_provisioned(
        self, subscription_id: int, error: Optional[str] = None
    ) -> Subscription:
        """Mark subscription as provisioned (or failed).

        Args:
            subscription_id: The subscription ID.
            error: Optional error message if provisioning failed.

        Returns:
            The updated Subscription.
        """
        sub = self.get_subscription(subscription_id, include_relations=False)

        if error:
            sub.provisioning_error = error
        else:
            sub.provisioned_at = datetime.now(timezone.utc)
            sub.provisioning_error = None

        return sub

    # -------------------------------------------------------------------------
    # Party Integration
    # -------------------------------------------------------------------------

    def _ensure_subscriber_role(self, party_id: int) -> None:
        """Ensure party has 'subscriber' role.

        Args:
            party_id: The party ID.
        """
        existing = self.db.query(PartyRole).filter(
            PartyRole.party_id == party_id,
            PartyRole.role == "subscriber",
            PartyRole.until.is_(None),
        ).first()

        if not existing:
            role = PartyRole(
                party_id=party_id,
                role="subscriber",
                status="active",
            )
            self.db.add(role)
            self.db.flush()

    def get_party_subscriptions(
        self,
        party_id: int,
        active_only: bool = False,
    ) -> List[Subscription]:
        """Get all subscriptions for a party.

        Args:
            party_id: The party ID.
            active_only: Only return active subscriptions.

        Returns:
            List of Subscription.
        """
        query = self.db.query(Subscription).filter(
            Subscription.party_id == party_id
        )
        if active_only:
            query = query.filter(Subscription.status == SubscriptionStatus.ACTIVE)
        return query.order_by(Subscription.created_at.desc()).all()

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_stats(self) -> SubscriptionStats:
        """Get subscription statistics.

        Returns:
            SubscriptionStats with aggregate counts.
        """
        base = self.db.query(Subscription)

        active = base.filter(Subscription.status == SubscriptionStatus.ACTIVE).count()
        suspended = base.filter(Subscription.status == SubscriptionStatus.SUSPENDED).count()
        pending = base.filter(Subscription.status == SubscriptionStatus.PENDING).count()
        cancelled = base.filter(Subscription.status == SubscriptionStatus.CANCELLED).count()
        total = base.count()

        # MRR calculation
        mrr_monthly = self.db.query(func.sum(Subscription.price)).filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.billing_cycle == "monthly"
        ).scalar() or Decimal("0")

        mrr_quarterly = self.db.query(func.sum(Subscription.price / 3)).filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.billing_cycle == "quarterly"
        ).scalar() or Decimal("0")

        mrr_yearly = self.db.query(func.sum(Subscription.price / 12)).filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.billing_cycle == "yearly"
        ).scalar() or Decimal("0")

        mrr = mrr_monthly + mrr_quarterly + mrr_yearly

        # New this month
        start_of_month = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        new_this_month = base.filter(
            Subscription.created_at >= start_of_month
        ).count()

        return SubscriptionStats(
            active=active,
            suspended=suspended,
            pending=pending,
            cancelled=cancelled,
            total=total,
            mrr=mrr,
            new_this_month=new_this_month,
        )

    # -------------------------------------------------------------------------
    # Lifecycle Management (Upgrade, Downgrade, Renew)
    # -------------------------------------------------------------------------

    def upgrade(
        self,
        subscription_id: int,
        new_tariff_id: int,
        effective: str = "immediate",
        prorate: bool = True,
    ) -> "UpgradeResult":
        """Upgrade subscription to a higher-tier plan.

        Args:
            subscription_id: The subscription to upgrade.
            new_tariff_id: Target tariff/plan.
            effective: When change takes effect ("immediate" or "next_cycle").
            prorate: Whether to prorate charges.

        Returns:
            UpgradeResult with details.

        Raises:
            NotFoundError: If subscription or tariff not found.
            ValidationError: If upgrade not allowed.
        """
        from .service_type_config import ServiceTypeConfigService
        from .service_transactions import ServiceTransactionService

        sub = self.get_subscription(subscription_id, include_relations=False)

        if sub.status != SubscriptionStatus.ACTIVE:
            raise ValidationError("Can only upgrade active subscriptions")

        # Get new tariff
        new_tariff = self.db.query(Tariff).filter(Tariff.id == new_tariff_id).first()
        if not new_tariff:
            raise ValidationError(f"Tariff {new_tariff_id} not found")

        # Check if actually an upgrade (new price > old price)
        if new_tariff.price <= sub.price:
            raise ValidationError(
                "New plan must have higher price for upgrade. Use downgrade instead."
            )

        # Check config allows upgrades
        config_service = ServiceTypeConfigService(self.db, self.principal)
        if not config_service.can_upgrade():
            raise ValidationError("Upgrades are not allowed")

        old_plan = sub.plan_name
        old_price = sub.price
        old_tariff_id = sub.tariff_id

        # Calculate proration if applicable
        proration_amount = Decimal("0")
        if prorate and effective == "immediate":
            proration_amount = self._calculate_proration(sub, new_tariff.price, is_upgrade=True)

        # Update subscription
        sub.tariff_id = new_tariff_id
        sub.plan_name = new_tariff.title
        sub.price = new_tariff.price
        if new_tariff.download_speed:
            sub.download_speed = new_tariff.download_speed
        if new_tariff.upload_speed:
            sub.upload_speed = new_tariff.upload_speed

        # Record transaction
        txn_service = ServiceTransactionService(self.db, self.principal)
        txn_service.record_plan_change(
            subscription_id=subscription_id,
            party_id=sub.party_id,
            old_plan=old_plan,
            new_plan=new_tariff.title,
            old_price=old_price,
            new_price=new_tariff.price,
            is_upgrade=True,
            proration_amount=proration_amount,
            change_fee=config_service.get_upgrade_fee(),
        )

        return UpgradeResult(
            subscription_id=subscription_id,
            old_tariff_id=old_tariff_id,
            new_tariff_id=new_tariff_id,
            old_plan=old_plan,
            new_plan=new_tariff.title,
            old_price=old_price,
            new_price=new_tariff.price,
            proration_amount=proration_amount,
            effective=effective,
        )

    def downgrade(
        self,
        subscription_id: int,
        new_tariff_id: int,
        effective: str = "next_cycle",
        prorate: bool = False,
    ) -> "DowngradeResult":
        """Downgrade subscription to a lower-tier plan.

        Args:
            subscription_id: The subscription to downgrade.
            new_tariff_id: Target tariff/plan.
            effective: When change takes effect ("immediate" or "next_cycle").
            prorate: Whether to prorate credits.

        Returns:
            DowngradeResult with details.

        Raises:
            NotFoundError: If subscription or tariff not found.
            ValidationError: If downgrade not allowed.
        """
        from .service_type_config import ServiceTypeConfigService
        from .service_transactions import ServiceTransactionService

        sub = self.get_subscription(subscription_id, include_relations=False)

        if sub.status != SubscriptionStatus.ACTIVE:
            raise ValidationError("Can only downgrade active subscriptions")

        # Get new tariff
        new_tariff = self.db.query(Tariff).filter(Tariff.id == new_tariff_id).first()
        if not new_tariff:
            raise ValidationError(f"Tariff {new_tariff_id} not found")

        # Check if actually a downgrade
        if new_tariff.price >= sub.price:
            raise ValidationError(
                "New plan must have lower price for downgrade. Use upgrade instead."
            )

        # Check config allows downgrades
        config_service = ServiceTypeConfigService(self.db, self.principal)
        if not config_service.can_downgrade():
            raise ValidationError("Downgrades are not allowed")

        # Check minimum days restriction
        config = config_service.get_config()
        if config.plan_changes.min_days_before_downgrade > 0:
            if sub.start_date:
                days_active = (datetime.now(timezone.utc).date() - sub.start_date.date()).days
                if days_active < config.plan_changes.min_days_before_downgrade:
                    raise ValidationError(
                        f"Must wait {config.plan_changes.min_days_before_downgrade} days before downgrading"
                    )

        old_plan = sub.plan_name
        old_price = sub.price
        old_tariff_id = sub.tariff_id

        # Calculate proration credit if applicable
        proration_credit = Decimal("0")
        if prorate and effective == "immediate":
            proration_credit = self._calculate_proration(sub, new_tariff.price, is_upgrade=False)

        # If next_cycle, schedule the change instead of immediate
        if effective == "next_cycle":
            # Store pending change in metadata or separate table
            # For now, we'll apply immediately but note the intent
            pass

        # Update subscription
        sub.tariff_id = new_tariff_id
        sub.plan_name = new_tariff.title
        sub.price = new_tariff.price
        if new_tariff.download_speed:
            sub.download_speed = new_tariff.download_speed
        if new_tariff.upload_speed:
            sub.upload_speed = new_tariff.upload_speed

        # Record transaction
        txn_service = ServiceTransactionService(self.db, self.principal)
        txn_service.record_plan_change(
            subscription_id=subscription_id,
            party_id=sub.party_id,
            old_plan=old_plan,
            new_plan=new_tariff.title,
            old_price=old_price,
            new_price=new_tariff.price,
            is_upgrade=False,
            proration_amount=-proration_credit if proration_credit else None,
            change_fee=config_service.get_downgrade_fee(),
        )

        return DowngradeResult(
            subscription_id=subscription_id,
            old_tariff_id=old_tariff_id,
            new_tariff_id=new_tariff_id,
            old_plan=old_plan,
            new_plan=new_tariff.title,
            old_price=old_price,
            new_price=new_tariff.price,
            proration_credit=proration_credit,
            effective=effective,
        )

    def renew(
        self,
        subscription_id: int,
        periods: int = 1,
        new_end_date: Optional[datetime] = None,
    ) -> "RenewalResult":
        """Renew a subscription for additional periods.

        Args:
            subscription_id: The subscription to renew.
            periods: Number of billing periods to extend.
            new_end_date: Explicit new end date (overrides periods).

        Returns:
            RenewalResult with details.
        """
        from .service_transactions import ServiceTransactionService
        from dateutil.relativedelta import relativedelta

        sub = self.get_subscription(subscription_id, include_relations=False)

        if sub.status == SubscriptionStatus.CANCELLED:
            raise ValidationError("Cannot renew cancelled subscription")

        old_end_date = sub.end_date

        # Calculate new end date
        if new_end_date:
            sub.end_date = new_end_date
        elif sub.end_date:
            # Extend from current end date
            delta = self._get_billing_cycle_delta(sub.billing_cycle) * periods
            sub.end_date = sub.end_date + delta
        else:
            # No end date set, calculate from now
            delta = self._get_billing_cycle_delta(sub.billing_cycle) * periods
            sub.end_date = datetime.now(timezone.utc) + delta

        # Record transaction
        txn_service = ServiceTransactionService(self.db, self.principal)
        from .service_transactions import ServiceTransactionCreateData, ServiceTransactionType

        txn_service.create_transaction(ServiceTransactionCreateData(
            subscription_id=subscription_id,
            party_id=sub.party_id,
            transaction_type=ServiceTransactionType.RENEWAL.value,
            description=f"Subscription renewed for {periods} period(s)",
            amount=Decimal("0"),  # Charge handled separately via billing
            old_value=str(old_end_date) if old_end_date else None,
            new_value=str(sub.end_date) if sub.end_date else None,
            metadata={"periods": periods},
        ))

        return RenewalResult(
            subscription_id=subscription_id,
            old_end_date=old_end_date,
            new_end_date=sub.end_date,
            periods=periods,
        )

    def extend_grace_period(
        self,
        subscription_id: int,
        days: int,
        reason: str,
    ) -> Subscription:
        """Extend grace period for a suspended subscription.

        Args:
            subscription_id: The subscription.
            days: Days to extend.
            reason: Reason for extension.

        Returns:
            Updated subscription.
        """
        sub = self.get_subscription(subscription_id, include_relations=False)

        if sub.status != SubscriptionStatus.SUSPENDED:
            raise ValidationError("Can only extend grace period for suspended subscriptions")

        # Update end date to extend grace
        if sub.end_date:
            from datetime import timedelta
            sub.end_date = sub.end_date + timedelta(days=days)

        return sub

    def calculate_early_termination_fee(
        self,
        subscription_id: int,
    ) -> Decimal:
        """Calculate early termination fee for a subscription.

        Args:
            subscription_id: The subscription.

        Returns:
            Early termination fee amount.
        """
        from .service_type_config import ServiceTypeConfigService

        sub = self.get_subscription(subscription_id, include_relations=False)

        config_service = ServiceTypeConfigService(self.db, self.principal)

        # Calculate remaining months if on contract
        remaining_months = 0
        if sub.end_date and sub.start_date:
            from dateutil.relativedelta import relativedelta
            remaining = relativedelta(sub.end_date, datetime.now(timezone.utc))
            remaining_months = remaining.months + (remaining.years * 12)

        return config_service.calculate_early_termination_fee(
            monthly_price=sub.price,
            remaining_months=remaining_months,
        )

    def _calculate_proration(
        self,
        subscription: Subscription,
        new_price: Decimal,
        is_upgrade: bool,
    ) -> Decimal:
        """Calculate proration amount for plan change.

        Args:
            subscription: Current subscription.
            new_price: New plan price.
            is_upgrade: Whether this is an upgrade.

        Returns:
            Proration amount (positive for charge, negative for credit).
        """
        from datetime import timedelta

        # Get billing cycle days
        cycle_days = self._get_billing_cycle_days(subscription.billing_cycle)

        # Calculate days remaining in current period
        today = datetime.now(timezone.utc).date()

        if subscription.start_date:
            # Find current period start
            start = subscription.start_date.date() if isinstance(subscription.start_date, datetime) else subscription.start_date
            # Approximate period end
            period_end = start + timedelta(days=cycle_days)
            while period_end < today:
                period_end += timedelta(days=cycle_days)
            period_start = period_end - timedelta(days=cycle_days)

            days_remaining = (period_end - today).days
            days_used = (today - period_start).days
        else:
            # No start date, assume full period
            days_remaining = cycle_days
            days_used = 0

        if is_upgrade:
            # Charge difference for remaining days
            daily_diff = (new_price - subscription.price) / cycle_days
            return daily_diff * days_remaining
        else:
            # Credit difference for remaining days
            daily_diff = (subscription.price - new_price) / cycle_days
            return daily_diff * days_remaining

    def _get_billing_cycle_days(self, billing_cycle: str) -> int:
        """Get approximate days in billing cycle."""
        return {
            "daily": 1,
            "weekly": 7,
            "monthly": 30,
            "quarterly": 90,
            "yearly": 365,
        }.get(billing_cycle, 30)

    def _get_billing_cycle_delta(self, billing_cycle: str):
        """Get relativedelta for billing cycle."""
        from dateutil.relativedelta import relativedelta

        deltas = {
            "daily": relativedelta(days=1),
            "weekly": relativedelta(weeks=1),
            "monthly": relativedelta(months=1),
            "quarterly": relativedelta(months=3),
            "yearly": relativedelta(years=1),
        }
        return deltas.get(billing_cycle, relativedelta(months=1))


# =============================================================================
# Result DTOs for Lifecycle Operations
# =============================================================================

@dataclass
class UpgradeResult:
    """Result of an upgrade operation."""

    subscription_id: int
    old_tariff_id: Optional[int]
    new_tariff_id: int
    old_plan: str
    new_plan: str
    old_price: Decimal
    new_price: Decimal
    proration_amount: Decimal
    effective: str


@dataclass
class DowngradeResult:
    """Result of a downgrade operation."""

    subscription_id: int
    old_tariff_id: Optional[int]
    new_tariff_id: int
    old_plan: str
    new_plan: str
    old_price: Decimal
    new_price: Decimal
    proration_credit: Decimal
    effective: str


@dataclass
class RenewalResult:
    """Result of a renewal operation."""

    subscription_id: int
    old_end_date: Optional[datetime]
    new_end_date: Optional[datetime]
    periods: int


