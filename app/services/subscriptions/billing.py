"""Billing service - orchestrates subscription billing including daily billing.

This service handles:
- Daily billing runs
- Weekly/monthly billing cycle processing
- Invoice generation for subscriptions
- Automatic charge processing via payment subscriptions
- Billing statistics and reporting
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.models.subscription import Subscription, SubscriptionStatus
from app.models.payment_subscription import (
    PaymentSubscription,
    PaymentSubscriptionStatus,
    PaymentSubscriptionInterval,
)
from app.models.invoice import Invoice, InvoiceStatus, InvoiceSource
from app.models.party import CustomerAccount
from app.services.errors import NotFoundError, ValidationError
from app.services.validation.soft_validation_service import SoftValidationService

from .subscription_types import (
    DailyBillingConfig,
    DailyBillingResult,
    BillingRunSummary,
    BillableSubscription,
    ChargeRequest,
    ChargeResult,
    SubscriptionBillingInfo,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["BillingService"]


class BillingService:
    """Service for subscription billing operations."""

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Daily Billing
    # -------------------------------------------------------------------------

    def run_daily_billing(
        self,
        billing_date: Optional[date] = None,
        dry_run: bool = False,
    ) -> BillingRunSummary:
        """Run daily billing for all eligible subscriptions.

        Processes subscriptions with daily billing cycle and generates
        invoices/charges.

        Args:
            billing_date: The date to bill for (defaults to yesterday).
            dry_run: If True, don't create invoices or charges.

        Returns:
            BillingRunSummary with results.
        """
        if billing_date is None:
            billing_date = date.today() - timedelta(days=1)

        run_id = f"daily-{billing_date.isoformat()}-{uuid.uuid4().hex[:8]}"
        started_at = datetime.now(timezone.utc)

        summary = BillingRunSummary(
            run_id=run_id,
            run_type="daily",
            run_date=billing_date,
            started_at=started_at,
        )

        # Get daily billing subscriptions
        billable = self._get_daily_billable_subscriptions(billing_date)
        summary.total_subscriptions = len(billable)

        for sub in billable:
            try:
                result = self._process_daily_subscription(
                    sub, billing_date, dry_run=dry_run
                )

                if result.success:
                    summary.successful += 1
                    summary.total_amount += result.total_amount
                else:
                    summary.failed += 1
                    summary.error_details.append({
                        "subscription_id": sub.subscription_id,
                        "error": result.error_message,
                    })

            except Exception as e:
                summary.failed += 1
                summary.error_details.append({
                    "subscription_id": sub.subscription_id,
                    "error": str(e),
                })

        summary.completed_at = datetime.now(timezone.utc)
        return summary

    def bill_subscription_daily(
        self,
        subscription_id: int,
        billing_date: date,
        billing_config: Optional[DailyBillingConfig] = None,
    ) -> DailyBillingResult:
        """Bill a specific subscription for a day.

        Args:
            subscription_id: The subscription ID.
            billing_date: The date to bill for.
            billing_config: Optional billing configuration.

        Returns:
            DailyBillingResult with billing details.
        """
        sub = self._get_subscription(subscription_id)

        if sub.status != SubscriptionStatus.ACTIVE:
            return DailyBillingResult(
                subscription_id=subscription_id,
                billing_date=billing_date,
                success=False,
                billing_type="skipped",
                fixed_amount=Decimal("0"),
                usage_amount=Decimal("0"),
                total_amount=Decimal("0"),
                currency=sub.currency,
                error_message="Subscription is not active",
            )

        # Determine billing type and amounts
        config = billing_config or self._get_default_daily_config(sub)
        fixed_amount = Decimal("0")
        usage_amount = Decimal("0")

        if config.billing_type in ("fixed", "hybrid"):
            # Calculate daily fixed amount from subscription price
            fixed_amount = config.fixed_daily_amount or self._calculate_daily_rate(sub)

        if config.billing_type in ("usage_based", "hybrid"):
            # Calculate usage-based amount
            usage_amount = self._calculate_usage_amount(
                subscription_id,
                billing_date,
                rate_per_gb=config.usage_rate_per_gb or Decimal("0"),
                included_gb=config.included_gb_per_day or Decimal("0"),
            )

        total_amount = fixed_amount + usage_amount

        if total_amount <= 0:
            return DailyBillingResult(
                subscription_id=subscription_id,
                billing_date=billing_date,
                success=True,
                billing_type=config.billing_type,
                fixed_amount=fixed_amount,
                usage_amount=usage_amount,
                total_amount=total_amount,
                currency=sub.currency,
            )

        # Generate invoice if configured
        invoice_id = None
        if config.generate_invoice:
            invoice = self._create_daily_invoice(
                sub, billing_date, total_amount, config.billing_type
            )
            invoice_id = invoice.id

        # Auto-charge if configured
        charge_reference = None
        if config.auto_charge:
            charge_result = self._auto_charge_subscription(
                sub, total_amount, billing_date, invoice_id
            )
            if charge_result.success:
                charge_reference = charge_result.reference
            else:
                return DailyBillingResult(
                    subscription_id=subscription_id,
                    billing_date=billing_date,
                    success=False,
                    billing_type=config.billing_type,
                    fixed_amount=fixed_amount,
                    usage_amount=usage_amount,
                    total_amount=total_amount,
                    currency=sub.currency,
                    invoice_id=invoice_id,
                    error_message=charge_result.error_message,
                )

        return DailyBillingResult(
            subscription_id=subscription_id,
            billing_date=billing_date,
            success=True,
            billing_type=config.billing_type,
            fixed_amount=fixed_amount,
            usage_amount=usage_amount,
            total_amount=total_amount,
            currency=sub.currency,
            invoice_id=invoice_id,
            charge_reference=charge_reference,
        )

    # -------------------------------------------------------------------------
    # Billable Subscriptions
    # -------------------------------------------------------------------------

    def get_billable_subscriptions(
        self,
        billing_cycle: str,
        as_of_date: Optional[date] = None,
    ) -> List[BillableSubscription]:
        """Get subscriptions due for billing.

        Args:
            billing_cycle: Billing cycle to filter (daily, weekly, monthly, etc.)
            as_of_date: The date to check against (defaults to today).

        Returns:
            List of BillableSubscription ready for billing.
        """
        if as_of_date is None:
            as_of_date = date.today()

        query = (
            self.db.query(Subscription)
            .filter(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.billing_cycle == billing_cycle,
            )
        )

        subs = query.all()
        results = []

        for sub in subs:
            # Check if billing is due
            next_billing = self._calculate_next_billing_date(sub)

            if next_billing and next_billing <= as_of_date:
                # Check for linked payment subscription
                payment_sub = self._get_linked_payment_subscription(sub.id)

                results.append(BillableSubscription(
                    subscription_id=sub.id,
                    party_id=sub.party_id,
                    plan_name=sub.plan_name,
                    billing_cycle=sub.billing_cycle,
                    price=sub.price,
                    currency=sub.currency,
                    next_billing_date=next_billing,
                    payment_subscription_id=payment_sub.id if payment_sub else None,
                    has_auto_charge=payment_sub is not None and payment_sub.is_active,
                ))

        return results

    def get_billing_info(self, subscription_id: int) -> SubscriptionBillingInfo:
        """Get billing information for a subscription.

        Args:
            subscription_id: The subscription ID.

        Returns:
            SubscriptionBillingInfo with billing details.
        """
        sub = self._get_subscription(subscription_id)

        # Get linked payment subscription
        payment_sub = self._get_linked_payment_subscription(subscription_id)

        # Get last invoice
        account_id = self._get_customer_account_id(sub.party_id)
        last_invoice = None
        if account_id:
            last_invoice = (
                self.db.query(Invoice)
                .filter(Invoice.customer_account_id == account_id)
                .order_by(Invoice.invoice_date.desc())
                .first()
            )

        # Calculate outstanding balance (simplified)
        outstanding = self._calculate_outstanding_balance(sub.party_id)

        # Calculate next billing date
        next_billing = self._calculate_next_billing_date(sub)

        return SubscriptionBillingInfo(
            subscription_id=subscription_id,
            party_id=sub.party_id,
            plan_name=sub.plan_name,
            price=sub.price,
            currency=sub.currency,
            billing_cycle=sub.billing_cycle,
            next_billing_date=next_billing,
            last_invoice_date=last_invoice.invoice_date.date() if last_invoice else None,
            last_invoice_id=last_invoice.id if last_invoice else None,
            outstanding_balance=outstanding,
            is_payment_subscription_linked=payment_sub is not None,
            payment_subscription_id=payment_sub.id if payment_sub else None,
        )

    # -------------------------------------------------------------------------
    # Invoice Generation
    # -------------------------------------------------------------------------

    def generate_subscription_invoice(
        self,
        subscription_id: int,
        billing_period_start: date,
        billing_period_end: date,
        amount: Optional[Decimal] = None,
    ) -> Invoice:
        """Generate an invoice for a subscription.

        Args:
            subscription_id: The subscription ID.
            billing_period_start: Start of billing period.
            billing_period_end: End of billing period.
            amount: Invoice amount (defaults to subscription price).

        Returns:
            Created Invoice.
        """
        sub = self._get_subscription(subscription_id)

        if amount is None:
            amount = self._calculate_period_amount(
                sub, billing_period_start, billing_period_end
            )

        # Generate invoice number
        invoice_number = self._generate_invoice_number()

        account_id = self._get_customer_account_id(sub.party_id)
        invoice = Invoice(
            source=InvoiceSource.INTERNAL,
            customer_account_id=account_id,
            invoice_number=invoice_number,
            description=f"{sub.plan_name} - {billing_period_start} to {billing_period_end}",
            amount=amount,
            tax_amount=Decimal("0"),
            total_amount=amount,
            currency=sub.currency,
            status=InvoiceStatus.PENDING,
            invoice_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=7),
        )

        self.db.add(invoice)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(invoice)
        return invoice

    # -------------------------------------------------------------------------
    # Billing Statistics
    # -------------------------------------------------------------------------

    def get_billing_stats(
        self,
        period_start: Optional[date] = None,
        period_end: Optional[date] = None,
    ) -> dict:
        """Get billing statistics.

        Args:
            period_start: Start of reporting period (defaults to start of month).
            period_end: End of reporting period (defaults to today).

        Returns:
            Dictionary with billing statistics.
        """
        if period_start is None:
            period_start = date.today().replace(day=1)
        if period_end is None:
            period_end = date.today()

        # Daily billing subscriptions
        daily_subs = (
            self.db.query(Subscription)
            .filter(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.billing_cycle == "daily",
            )
            .count()
        )

        # Weekly billing subscriptions
        weekly_subs = (
            self.db.query(Subscription)
            .filter(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.billing_cycle == "weekly",
            )
            .count()
        )

        # Monthly billing subscriptions
        monthly_subs = (
            self.db.query(Subscription)
            .filter(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.billing_cycle == "monthly",
            )
            .count()
        )

        # Invoices in period
        period_invoices = (
            self.db.query(Invoice)
            .filter(
                Invoice.invoice_date >= datetime.combine(period_start, datetime.min.time()),
                Invoice.invoice_date <= datetime.combine(period_end, datetime.max.time()),
                Invoice.source == InvoiceSource.INTERNAL,
            )
            .all()
        )

        total_invoiced = sum(inv.total_amount for inv in period_invoices)
        paid_invoices = [inv for inv in period_invoices if inv.status == InvoiceStatus.PAID]
        total_collected = sum(inv.total_amount for inv in paid_invoices)

        # Active payment subscriptions
        active_payment_subs = (
            self.db.query(PaymentSubscription)
            .filter(PaymentSubscription.status == PaymentSubscriptionStatus.ACTIVE)
            .count()
        )

        # Daily recurring revenue (from daily subscriptions)
        daily_revenue = (
            self.db.query(Subscription)
            .filter(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.billing_cycle == "daily",
            )
            .with_entities(Subscription.price)
            .all()
        )
        drr = sum(p[0] for p in daily_revenue) if daily_revenue else Decimal("0")

        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "subscriptions_by_cycle": {
                "daily": daily_subs,
                "weekly": weekly_subs,
                "monthly": monthly_subs,
            },
            "invoices": {
                "count": len(period_invoices),
                "total_amount": float(total_invoiced),
                "paid_count": len(paid_invoices),
                "collected_amount": float(total_collected),
            },
            "payment_subscriptions": {
                "active": active_payment_subs,
            },
            "daily_recurring_revenue": float(drr),
        }

    # -------------------------------------------------------------------------
    # Helper Methods - Subscription Lookup
    # -------------------------------------------------------------------------

    def _get_subscription(self, subscription_id: int) -> Subscription:
        """Get a subscription with validation."""
        sub = (
            self.db.query(Subscription)
            .filter(Subscription.id == subscription_id)
            .first()
        )
        if not sub:
            raise NotFoundError(f"Subscription {subscription_id} not found")
        return sub

    def _get_daily_billable_subscriptions(
        self, billing_date: date
    ) -> List[BillableSubscription]:
        """Get subscriptions due for daily billing."""
        return self.get_billable_subscriptions("daily", billing_date)

    def _get_linked_payment_subscription(
        self, subscription_id: int
    ) -> Optional[PaymentSubscription]:
        """Get payment subscription linked to a service subscription."""
        return (
            self.db.query(PaymentSubscription)
            .filter(
                PaymentSubscription.service_subscription_id == subscription_id,
                PaymentSubscription.status == PaymentSubscriptionStatus.ACTIVE,
            )
            .first()
        )

    # -------------------------------------------------------------------------
    # Helper Methods - Calculations
    # -------------------------------------------------------------------------

    def _calculate_daily_rate(self, subscription: Subscription) -> Decimal:
        """Calculate daily rate from subscription price."""
        cycle = subscription.billing_cycle or "monthly"
        price = subscription.price

        if cycle == "daily":
            return price
        elif cycle == "weekly":
            return price / 7
        elif cycle == "monthly":
            return price / 30  # Approximate
        elif cycle == "quarterly":
            return price / 90
        elif cycle == "yearly":
            return price / 365
        else:
            return price / 30  # Default to monthly

    def _calculate_usage_amount(
        self,
        subscription_id: int,
        billing_date: date,
        rate_per_gb: Decimal,
        included_gb: Decimal,
    ) -> Decimal:
        """Calculate usage-based billing amount."""
        from .usage import UsageService

        usage_service = UsageService(self.db, self.principal)
        charge_info = usage_service.calculate_usage_charge(
            subscription_id, billing_date, rate_per_gb, included_gb
        )
        return Decimal(str(charge_info["charge_amount"]))

    def _calculate_period_amount(
        self,
        subscription: Subscription,
        period_start: date,
        period_end: date,
    ) -> Decimal:
        """Calculate billing amount for a period."""
        cycle = subscription.billing_cycle or "monthly"
        price = subscription.price

        # For daily billing, calculate based on days
        if cycle == "daily":
            days = (period_end - period_start).days + 1
            return price * days

        # For other cycles, use full period price
        return price

    def _calculate_next_billing_date(
        self, subscription: Subscription
    ) -> Optional[date]:
        """Calculate next billing date for a subscription."""
        # Use start_date or created_at as anchor
        if subscription.start_date:
            anchor = subscription.start_date.date() if isinstance(
                subscription.start_date, datetime
            ) else subscription.start_date
        else:
            anchor = subscription.created_at.date() if isinstance(
                subscription.created_at, datetime
            ) else subscription.created_at

        today = date.today()
        cycle = subscription.billing_cycle or "monthly"

        if cycle == "daily":
            # Daily billing - next day after today
            return today + timedelta(days=1)

        elif cycle == "weekly":
            # Weekly - same day of week as anchor
            days_since_anchor = (today - anchor).days
            weeks = days_since_anchor // 7
            next_billing = anchor + timedelta(weeks=weeks + 1)
            return next_billing

        elif cycle == "monthly":
            # Monthly - same day of month as anchor
            anchor_day = min(anchor.day, 28)

            if today.day >= anchor_day:
                # Next billing is next month
                if today.month == 12:
                    return today.replace(year=today.year + 1, month=1, day=anchor_day)
                return today.replace(month=today.month + 1, day=anchor_day)
            else:
                # Next billing is this month
                return today.replace(day=anchor_day)

        elif cycle == "quarterly":
            # Quarterly - 3 months from anchor pattern
            months_since_anchor = (
                (today.year - anchor.year) * 12 + (today.month - anchor.month)
            )
            next_quarter = ((months_since_anchor // 3) + 1) * 3
            next_year = anchor.year + (anchor.month + next_quarter - 1) // 12
            next_month = ((anchor.month + next_quarter - 1) % 12) + 1
            return date(next_year, next_month, min(anchor.day, 28))

        elif cycle == "yearly":
            # Yearly - same date next year
            if today >= anchor.replace(year=today.year):
                return anchor.replace(year=today.year + 1)
            return anchor.replace(year=today.year)

        return None

    def _get_customer_account_id(self, party_id: int) -> Optional[int]:
        account = (
            self.db.query(CustomerAccount)
            .filter(CustomerAccount.party_id == party_id)
            .first()
        )
        return account.id if account else None

    def _calculate_outstanding_balance(self, party_id: int) -> Decimal:
        """Calculate outstanding balance for a party."""
        account_id = self._get_customer_account_id(party_id)
        if not account_id:
            return Decimal("0")

        outstanding_invoices = (
            self.db.query(Invoice)
            .filter(
                Invoice.customer_account_id == account_id,
                Invoice.status.in_([
                    InvoiceStatus.PENDING,
                    InvoiceStatus.PARTIALLY_PAID,
                    InvoiceStatus.OVERDUE,
                ]),
                Invoice.is_deleted == False,
            )
            .all()
        )

        return sum(
            (inv.balance or (inv.total_amount - (inv.amount_paid or Decimal("0"))))
            for inv in outstanding_invoices
        )

    # -------------------------------------------------------------------------
    # Helper Methods - Invoice/Charge Processing
    # -------------------------------------------------------------------------

    def _create_daily_invoice(
        self,
        subscription: Subscription,
        billing_date: date,
        amount: Decimal,
        billing_type: str,
    ) -> Invoice:
        """Create an invoice for daily billing."""
        invoice_number = self._generate_invoice_number()

        description = f"{subscription.plan_name} - Daily ({billing_type})"
        if billing_type == "usage_based":
            description = f"{subscription.plan_name} - Daily Usage"
        elif billing_type == "hybrid":
            description = f"{subscription.plan_name} - Daily (Fixed + Usage)"

        account_id = self._get_customer_account_id(subscription.party_id)
        invoice = Invoice(
            source=InvoiceSource.INTERNAL,
            customer_account_id=account_id,
            invoice_number=invoice_number,
            description=f"{description} - {billing_date}",
            amount=amount,
            tax_amount=Decimal("0"),
            total_amount=amount,
            currency=subscription.currency,
            status=InvoiceStatus.PENDING,
            invoice_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=1),  # Due next day
        )

        self.db.add(invoice)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(invoice)
        return invoice

    def _auto_charge_subscription(
        self,
        subscription: Subscription,
        amount: Decimal,
        billing_date: date,
        invoice_id: Optional[int] = None,
    ) -> ChargeResult:
        """Attempt automatic charge via payment subscription."""
        payment_sub = self._get_linked_payment_subscription(subscription.id)

        if not payment_sub:
            return ChargeResult(
                success=False,
                subscription_id=subscription.id,
                amount=amount,
                currency=subscription.currency,
                error_code="no_payment_method",
                error_message="No active payment subscription linked",
                retryable=False,
            )

        if not payment_sub.is_active:
            return ChargeResult(
                success=False,
                subscription_id=subscription.id,
                amount=amount,
                currency=subscription.currency,
                error_code="payment_sub_inactive",
                error_message="Payment subscription is not active",
                retryable=False,
            )

        # Queue charge via Celery task (actual charging is async)
        try:
            from app.tasks.billing_tasks import process_subscription_charge

            task = process_subscription_charge.delay(
                payment_subscription_id=payment_sub.id,
                amount=float(amount),
                currency=subscription.currency,
                description=f"Daily billing for {subscription.plan_name}",
                invoice_id=invoice_id,
                idempotency_key=f"daily-{subscription.id}-{billing_date.isoformat()}",
            )

            return ChargeResult(
                success=True,
                subscription_id=subscription.id,
                amount=amount,
                currency=subscription.currency,
                reference=task.id,
            )

        except Exception as e:
            return ChargeResult(
                success=False,
                subscription_id=subscription.id,
                amount=amount,
                currency=subscription.currency,
                error_code="charge_failed",
                error_message=str(e),
                retryable=True,
            )

    def _process_daily_subscription(
        self,
        billable: BillableSubscription,
        billing_date: date,
        dry_run: bool = False,
    ) -> DailyBillingResult:
        """Process daily billing for a single subscription."""
        sub = self._get_subscription(billable.subscription_id)
        config = self._get_default_daily_config(sub)

        if dry_run:
            # Return what would be billed without creating anything
            fixed_amount = config.fixed_daily_amount or self._calculate_daily_rate(sub)
            usage_amount = Decimal("0")

            if config.billing_type in ("usage_based", "hybrid"):
                usage_amount = self._calculate_usage_amount(
                    sub.id,
                    billing_date,
                    rate_per_gb=config.usage_rate_per_gb or Decimal("0"),
                    included_gb=config.included_gb_per_day or Decimal("0"),
                )

            return DailyBillingResult(
                subscription_id=sub.id,
                billing_date=billing_date,
                success=True,
                billing_type=config.billing_type,
                fixed_amount=fixed_amount,
                usage_amount=usage_amount,
                total_amount=fixed_amount + usage_amount,
                currency=sub.currency,
            )

        return self.bill_subscription_daily(sub.id, billing_date, config)

    def _get_default_daily_config(
        self, subscription: Subscription
    ) -> DailyBillingConfig:
        """Get default daily billing config for a subscription."""
        # Determine billing type based on subscription configuration
        has_usage_rate = getattr(subscription, "usage_rate_per_gb", None) is not None
        has_data_cap = subscription.data_cap is not None

        if has_usage_rate and not subscription.price:
            billing_type = "usage_based"
        elif has_usage_rate and subscription.price:
            billing_type = "hybrid"
        else:
            billing_type = "fixed"

        return DailyBillingConfig(
            subscription_id=subscription.id,
            enabled=True,
            billing_type=billing_type,
            fixed_daily_amount=self._calculate_daily_rate(subscription)
            if billing_type in ("fixed", "hybrid")
            else None,
            usage_rate_per_gb=getattr(subscription, "usage_rate_per_gb", None),
            included_gb_per_day=getattr(subscription, "included_gb_per_day", None),
            auto_charge=self._get_linked_payment_subscription(subscription.id)
            is not None,
            generate_invoice=True,
        )

    def _generate_invoice_number(self) -> str:
        """Generate unique invoice number."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        random_part = uuid.uuid4().hex[:6].upper()
        return f"INV-{timestamp}-{random_part}"
