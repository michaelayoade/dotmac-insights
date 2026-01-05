"""Finance service - integrates subscriptions with accounting.

This service handles the integration between subscription billing and
the accounting module:
- Invoice generation via InvoiceService (with proper tax/VAT)
- Payment recording via ARPaymentService (with allocations)
- GL posting via DocumentPostingService
- Revenue recognition and deferred revenue
- MRR/ARR/churn metrics

All operations respect double-entry bookkeeping and integrate with:
- Accounts Receivable (AR)
- Revenue accounts
- Tax/VAT accounts
- Bank accounts
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session, joinedload

from app.models.subscription import Subscription, SubscriptionStatus
from app.models.payment_subscription import (
    PaymentSubscription,
    PaymentSubscriptionStatus,
)
from app.models.invoice import Invoice, InvoiceStatus, InvoiceSource
from app.models.document_lines import InvoiceLine
from app.models.party import CustomerAccount, Party
from app.services.errors import NotFoundError, ValidationError

from .subscription_types import (
    SubscriptionInvoiceData,
    SubscriptionBillingInfo,
)
from .billing_config import BillingConfigService, BillingConfig

if TYPE_CHECKING:
    from app.auth import Principal
    from app.models.payment import Payment
    from app.models.accounting import JournalEntry

__all__ = ["SubscriptionFinanceService"]


class SubscriptionFinanceService:
    """Service for subscription financial operations.

    Integrates with accounting services for proper double-entry bookkeeping:
    - Invoices: Created via InvoiceService with tax handling
    - Payments: Recorded via ARPaymentService with allocations
    - GL: Posted via DocumentPostingService

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for audit fields).
    """

    # Default GL accounts for subscription revenue
    DEFAULT_REVENUE_ACCOUNT = "4100"  # Subscription Revenue
    DEFAULT_AR_ACCOUNT = "1200"  # Accounts Receivable
    DEFAULT_TAX_ACCOUNT = "2100"  # VAT/Tax Payable

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal
        self._billing_config: Optional[BillingConfig] = None

    @property
    def billing_config(self) -> BillingConfig:
        """Get billing configuration (lazy loaded)."""
        if self._billing_config is None:
            config_service = BillingConfigService(self.db, self.principal)
            self._billing_config = config_service.get_config()
        return self._billing_config

    # -------------------------------------------------------------------------
    # Invoice Operations (via InvoiceService)
    # -------------------------------------------------------------------------

    def create_subscription_invoice(
        self,
        data: SubscriptionInvoiceData,
        auto_post: bool = False,
    ) -> Invoice:
        """Create an invoice for a subscription using InvoiceService.

        Creates a proper accounting invoice with:
        - Tax/VAT calculated per billing config
        - Proper line items
        - GL account assignments
        - Optional auto-posting to GL

        Args:
            data: Invoice data including subscription, period, and amounts.
            auto_post: If True, post invoice to GL immediately.

        Returns:
            Created Invoice.

        Raises:
            ValidationError: If data is invalid.
            NotFoundError: If subscription/customer not found.
        """
        from app.services.accounting import InvoiceService
        from app.services.accounting.invoice_types import (
            InvoiceCreateData,
            InvoiceLineData,
        )

        sub = self._get_subscription(data.subscription_id)
        config = self.billing_config

        # Validate party/customer account exists
        customer_account = self._get_or_create_customer_account(sub.party_id)

        # Calculate tax
        tax_rate = config.tax_rate
        base_amount = data.amount
        tax_amount = Decimal("0")

        if tax_rate > 0:
            tax_amount = base_amount * (tax_rate / 100)

        total_amount = base_amount + tax_amount

        # Build description
        description = data.description
        if data.prorated:
            description = f"{description} (Prorated: {data.proration_days} days)"

        # Determine due date
        due_date = data.due_date
        if not due_date:
            config_service = BillingConfigService(self.db, self.principal)
            due_date = config_service.get_invoice_due_date(
                data.billing_period_start
            )

        # Create line item data
        line = InvoiceLineData(
            item_code=f"SUB-{sub.id}",
            item_name=sub.plan_name,
            description=(
                f"{sub.plan_name} - "
                f"{data.billing_period_start} to {data.billing_period_end}"
            ),
            quantity=Decimal("1"),
            rate=base_amount,
            amount=base_amount,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            account=self.DEFAULT_REVENUE_ACCOUNT,
        )

        # Create invoice via InvoiceService
        invoice_data = InvoiceCreateData(
            customer_account_id=customer_account.id,
            invoice_date=datetime.now(timezone.utc),
            due_date=datetime.combine(due_date, datetime.min.time()),
            currency=data.currency or config.default_currency,
            description=description,
            lines=[line],
            category="subscription",
        )

        invoice_service = InvoiceService(self.db, self.principal)
        invoice = invoice_service.create_invoice(invoice_data)

        # Store subscription reference in metadata
        invoice.metadata = invoice.metadata or {}
        invoice.metadata["subscription_id"] = data.subscription_id
        invoice.metadata["billing_period_start"] = data.billing_period_start.isoformat()
        invoice.metadata["billing_period_end"] = data.billing_period_end.isoformat()

        # Auto-post if requested
        if auto_post:
            invoice, _ = invoice_service.post_invoice(invoice.id)

        return invoice

    def create_prorated_invoice(
        self,
        subscription_id: int,
        proration_start: date,
        proration_end: date,
        reason: str = "plan_change",
    ) -> Invoice:
        """Create a prorated invoice for partial period billing.

        Used for:
        - Mid-cycle plan upgrades/downgrades
        - Mid-cycle activations
        - Mid-cycle cancellations (credit)

        Args:
            subscription_id: The subscription ID.
            proration_start: Start of prorated period.
            proration_end: End of prorated period.
            reason: Proration reason (plan_change, activation, cancellation).

        Returns:
            Created Invoice.
        """
        sub = self._get_subscription(subscription_id)
        config = self.billing_config

        # Calculate prorated amount
        if sub.billing_cycle == "daily":
            full_period_days = 1
            daily_rate = sub.price
        elif sub.billing_cycle == "weekly":
            full_period_days = 7
            daily_rate = sub.price / 7
        elif sub.billing_cycle == "monthly":
            full_period_days = 30
            daily_rate = sub.price / 30
        elif sub.billing_cycle == "quarterly":
            full_period_days = 90
            daily_rate = sub.price / 90
        elif sub.billing_cycle == "yearly":
            full_period_days = 365
            daily_rate = sub.price / 365
        else:
            full_period_days = 30
            daily_rate = sub.price / 30

        proration_days = (proration_end - proration_start).days + 1
        prorated_amount = daily_rate * proration_days

        # Create invoice
        invoice_data = SubscriptionInvoiceData(
            subscription_id=subscription_id,
            party_id=sub.party_id,
            billing_period_start=proration_start,
            billing_period_end=proration_end,
            amount=prorated_amount.quantize(Decimal("0.01")),
            currency=sub.currency or config.default_currency,
            description=f"Prorated charge ({reason}): {sub.plan_name}",
            prorated=True,
            proration_days=proration_days,
        )

        return self.create_subscription_invoice(invoice_data, auto_post=True)

    def get_subscription_invoices(
        self,
        subscription_id: int,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Invoice]:
        """Get invoices for a subscription.

        Args:
            subscription_id: The subscription ID.
            status: Optional status filter.
            limit: Maximum invoices to return.

        Returns:
            List of invoices.
        """
        sub = self._get_subscription(subscription_id)

        customer_account_id = self._get_customer_account_id(sub.party_id)
        if not customer_account_id:
            return []

        query = self.db.query(Invoice).filter(
            Invoice.customer_account_id == customer_account_id,
            Invoice.is_deleted == False,
        )

        if status:
            try:
                status_enum = InvoiceStatus(status)
                query = query.filter(Invoice.status == status_enum)
            except ValueError:
                pass

        return (
            query.order_by(Invoice.invoice_date.desc())
            .limit(limit)
            .all()
        )

    def get_outstanding_invoices(self, party_id: int) -> List[Invoice]:
        """Get outstanding (unpaid) invoices for a party.

        Args:
            party_id: The party ID.

        Returns:
            List of outstanding invoices ordered by due date.
        """
        customer_account_id = self._get_customer_account_id(party_id)
        if not customer_account_id:
            return []

        return (
            self.db.query(Invoice)
            .filter(
                Invoice.customer_account_id == customer_account_id,
                Invoice.status.in_([
                    InvoiceStatus.PENDING,
                    InvoiceStatus.PARTIALLY_PAID,
                    InvoiceStatus.OVERDUE,
                ]),
                Invoice.is_deleted == False,
            )
            .order_by(Invoice.due_date.asc())
            .all()
        )

    # -------------------------------------------------------------------------
    # Payment Operations (via ARPaymentService)
    # -------------------------------------------------------------------------

    def record_subscription_payment(
        self,
        subscription_id: int,
        amount: Decimal,
        payment_date: date,
        reference: Optional[str] = None,
        gateway: Optional[str] = None,
        bank_account_id: Optional[int] = None,
        auto_allocate: bool = True,
    ) -> dict:
        """Record a payment against a subscription via ARPaymentService.

        Creates a proper AR payment with:
        - Bank account linkage (if provided)
        - Automatic allocation to oldest invoices
        - Proper audit trail

        Args:
            subscription_id: The subscription ID.
            amount: Payment amount.
            payment_date: Date of payment.
            reference: Payment reference/transaction ID.
            gateway: Payment gateway used (paystack, flutterwave, etc.).
            bank_account_id: Bank account to credit.
            auto_allocate: If True, allocate to oldest outstanding invoices.

        Returns:
            Dictionary with payment details and allocations.
        """
        from app.services.accounting import ARPaymentService
        from app.services.accounting.ar_payment_types import (
            PaymentCreateData,
            AllocationData,
        )

        sub = self._get_subscription(subscription_id)
        config = self.billing_config

        # Get outstanding invoices for allocation
        outstanding = self.get_outstanding_invoices(sub.party_id)
        allocations = []

        if auto_allocate and outstanding:
            remaining = amount
            for invoice in outstanding:
                if remaining <= 0:
                    break

                invoice_balance = invoice.total_amount - (invoice.amount_paid or Decimal("0"))
                allocation_amount = min(remaining, invoice_balance)

                if allocation_amount > 0:
                    allocations.append(AllocationData(
                        document_type="Invoice",
                        document_id=invoice.id,
                        allocated_amount=allocation_amount,
                    ))
                    remaining -= allocation_amount

        # Get or create customer account
        customer_account = self._get_or_create_customer_account(sub.party_id)

        # Create payment via ARPaymentService
        payment_data = PaymentCreateData(
            customer_account_id=customer_account.id,
            payment_date=datetime.combine(payment_date, datetime.min.time()),
            amount=amount,
            currency=sub.currency or config.default_currency,
            transaction_reference=reference,
            bank_account_id=bank_account_id,
            notes=f"Subscription payment - {sub.plan_name}" + (
                f" via {gateway}" if gateway else ""
            ),
            allocations=allocations,
        )

        ar_service = ARPaymentService(self.db, self.principal)
        payment = ar_service.create_payment(payment_data)

        # Calculate allocation summary
        total_allocated = sum(a.allocated_amount for a in allocations)

        return {
            "success": True,
            "payment_id": payment.id,
            "subscription_id": subscription_id,
            "amount": float(amount),
            "currency": payment_data.currency,
            "allocated": float(total_allocated),
            "remaining": float(amount - total_allocated),
            "invoices_updated": [
                {
                    "invoice_id": a.document_id,
                    "amount_allocated": float(a.allocated_amount),
                }
                for a in allocations
            ],
            "reference": reference,
            "gateway": gateway,
            "bank_account_id": bank_account_id,
        }

    def process_gateway_payment(
        self,
        subscription_id: int,
        gateway_response: dict,
        gateway: str = "paystack",
    ) -> dict:
        """Process a payment gateway webhook/callback.

        Validates and records a payment from payment gateways like
        Paystack, Flutterwave, etc.

        Args:
            subscription_id: The subscription ID.
            gateway_response: Response/webhook data from gateway.
            gateway: Payment gateway name.

        Returns:
            Payment result dictionary.
        """
        # Extract common fields from gateway response
        if gateway == "paystack":
            amount = Decimal(str(gateway_response.get("amount", 0))) / 100
            reference = gateway_response.get("reference")
            status = gateway_response.get("status")
            currency = gateway_response.get("currency", "NGN")
        elif gateway == "flutterwave":
            amount = Decimal(str(gateway_response.get("amount", 0)))
            reference = gateway_response.get("tx_ref")
            status = gateway_response.get("status")
            currency = gateway_response.get("currency", "NGN")
        else:
            # Generic format
            amount = Decimal(str(gateway_response.get("amount", 0)))
            reference = gateway_response.get("reference")
            status = gateway_response.get("status", "success")
            currency = gateway_response.get("currency", "NGN")

        if status not in ("success", "successful"):
            return {
                "success": False,
                "error": f"Payment status: {status}",
                "gateway_response": gateway_response,
            }

        # Record the payment
        return self.record_subscription_payment(
            subscription_id=subscription_id,
            amount=amount,
            payment_date=date.today(),
            reference=reference,
            gateway=gateway,
            auto_allocate=True,
        )

    def get_payment_history(
        self,
        subscription_id: int,
        limit: int = 50,
    ) -> List[dict]:
        """Get payment history for a subscription.

        Args:
            subscription_id: The subscription ID.
            limit: Maximum records to return.

        Returns:
            List of payment records.
        """
        from app.models.payment import Payment

        sub = self._get_subscription(subscription_id)
        customer_account_id = self._get_customer_account_id(sub.party_id)
        if not customer_account_id:
            return []

        payments = (
            self.db.query(Payment)
            .filter(
                Payment.customer_account_id == customer_account_id,
                Payment.is_deleted == False,
            )
            .order_by(Payment.payment_date.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "payment_id": p.id,
                "date": p.payment_date.isoformat() if p.payment_date else None,
                "amount": float(p.amount),
                "currency": p.currency,
                "status": p.status.value if p.status else None,
                "reference": p.transaction_reference,
                "allocated": float(p.total_allocated or 0),
                "unallocated": float(p.unallocated_amount or 0),
            }
            for p in payments
        ]

    # -------------------------------------------------------------------------
    # Financial Summary
    # -------------------------------------------------------------------------

    def get_subscription_financial_summary(
        self,
        subscription_id: int,
    ) -> dict:
        """Get comprehensive financial summary for a subscription.

        Args:
            subscription_id: The subscription ID.

        Returns:
            Dictionary with financial summary including AR balance.
        """
        sub = self._get_subscription(subscription_id)
        config = self.billing_config
        customer_account_id = self._get_customer_account_id(sub.party_id)

        # Get all invoices
        invoices = []
        if customer_account_id:
            invoices = (
                self.db.query(Invoice)
                .filter(
                    Invoice.customer_account_id == customer_account_id,
                    Invoice.is_deleted == False,
                )
                .all()
            )

        total_invoiced = sum(inv.total_amount for inv in invoices)
        total_paid = sum(inv.amount_paid or Decimal("0") for inv in invoices)
        total_tax = sum(inv.tax_amount or Decimal("0") for inv in invoices)
        outstanding = total_invoiced - total_paid

        # Calculate lifetime value
        active_days = 0
        if sub.start_date:
            start = sub.start_date.date() if isinstance(
                sub.start_date, datetime
            ) else sub.start_date
            end = date.today()
            if sub.cancelled_date:
                end = sub.cancelled_date.date() if isinstance(
                    sub.cancelled_date, datetime
                ) else sub.cancelled_date
            active_days = (end - start).days

        # Get payment subscription info
        payment_sub = (
            self.db.query(PaymentSubscription)
            .filter(
                PaymentSubscription.service_subscription_id == subscription_id,
            )
            .first()
        )

        # Count invoice statuses
        status_counts = {}
        for inv in invoices:
            status_key = inv.status.value if inv.status else "unknown"
            status_counts[status_key] = status_counts.get(status_key, 0) + 1

        return {
            "subscription_id": subscription_id,
            "party_id": sub.party_id,
            "plan_name": sub.plan_name,
            "price": float(sub.price),
            "currency": sub.currency or config.default_currency,
            "billing_cycle": sub.billing_cycle,
            "status": sub.status.value,
            "financials": {
                "total_invoiced": float(total_invoiced),
                "total_paid": float(total_paid),
                "total_tax": float(total_tax),
                "outstanding_balance": float(outstanding),
                "invoice_count": len(invoices),
                "invoice_status_breakdown": status_counts,
            },
            "lifetime": {
                "active_days": active_days,
                "lifetime_value": float(total_paid),
                "monthly_average": float(
                    total_paid / max(1, active_days / 30)
                ),
            },
            "payment_subscription": {
                "linked": payment_sub is not None,
                "id": payment_sub.id if payment_sub else None,
                "status": payment_sub.status.value if payment_sub else None,
                "provider": payment_sub.provider if payment_sub else None,
                "total_collected": float(payment_sub.total_collected)
                if payment_sub
                else 0,
                "successful_charges": payment_sub.successful_charges
                if payment_sub
                else 0,
                "failed_charges": payment_sub.failed_charges
                if payment_sub
                else 0,
            }
            if payment_sub
            else None,
            "config": {
                "tax_rate": float(config.tax_rate),
                "invoice_due_days": config.invoice_due_days,
                "auto_charge_enabled": config.auto_charge_enabled,
            },
        }

    def get_party_ar_balance(self, party_id: int) -> dict:
        """Get AR (Accounts Receivable) balance for a party.

        Args:
            party_id: The party ID.

        Returns:
            AR balance breakdown.
        """
        invoices = self.get_outstanding_invoices(party_id)

        total_outstanding = Decimal("0")
        overdue_amount = Decimal("0")
        current_amount = Decimal("0")
        today = date.today()

        aging = {
            "current": Decimal("0"),
            "1_30_days": Decimal("0"),
            "31_60_days": Decimal("0"),
            "61_90_days": Decimal("0"),
            "over_90_days": Decimal("0"),
        }

        for inv in invoices:
            balance = inv.total_amount - (inv.amount_paid or Decimal("0"))
            total_outstanding += balance

            due = inv.due_date.date() if isinstance(
                inv.due_date, datetime
            ) else inv.due_date

            if due:
                days_overdue = (today - due).days

                if days_overdue <= 0:
                    aging["current"] += balance
                    current_amount += balance
                elif days_overdue <= 30:
                    aging["1_30_days"] += balance
                    overdue_amount += balance
                elif days_overdue <= 60:
                    aging["31_60_days"] += balance
                    overdue_amount += balance
                elif days_overdue <= 90:
                    aging["61_90_days"] += balance
                    overdue_amount += balance
                else:
                    aging["over_90_days"] += balance
                    overdue_amount += balance
            else:
                aging["current"] += balance
                current_amount += balance

        return {
            "party_id": party_id,
            "total_outstanding": float(total_outstanding),
            "current": float(current_amount),
            "overdue": float(overdue_amount),
            "invoice_count": len(invoices),
            "aging": {k: float(v) for k, v in aging.items()},
        }

    # -------------------------------------------------------------------------
    # Revenue Recognition & Metrics
    # -------------------------------------------------------------------------

    def get_revenue_by_period(
        self,
        period_start: date,
        period_end: date,
        group_by: str = "day",  # day, week, month
    ) -> List[dict]:
        """Get subscription revenue grouped by time period.

        Args:
            period_start: Start of reporting period.
            period_end: End of reporting period.
            group_by: Grouping granularity.

        Returns:
            List of revenue by period.
        """
        invoices = (
            self.db.query(Invoice)
            .filter(
                Invoice.invoice_date >= datetime.combine(
                    period_start, datetime.min.time()
                ),
                Invoice.invoice_date <= datetime.combine(
                    period_end, datetime.max.time()
                ),
                Invoice.category == "subscription",
                Invoice.status == InvoiceStatus.PAID,
                Invoice.is_deleted == False,
            )
            .all()
        )

        # Group by period
        revenue_map: Dict[str, Dict[str, Decimal]] = {}

        for inv in invoices:
            inv_date = inv.invoice_date.date() if isinstance(
                inv.invoice_date, datetime
            ) else inv.invoice_date

            if group_by == "day":
                key = inv_date.isoformat()
            elif group_by == "week":
                key = f"{inv_date.isocalendar()[0]}-W{inv_date.isocalendar()[1]:02d}"
            elif group_by == "month":
                key = f"{inv_date.year}-{inv_date.month:02d}"
            else:
                key = inv_date.isoformat()

            if key not in revenue_map:
                revenue_map[key] = {
                    "revenue": Decimal("0"),
                    "tax": Decimal("0"),
                    "count": 0,
                }

            revenue_map[key]["revenue"] += inv.amount or Decimal("0")
            revenue_map[key]["tax"] += inv.tax_amount or Decimal("0")
            revenue_map[key]["count"] += 1

        return [
            {
                "period": k,
                "revenue": float(v["revenue"]),
                "tax": float(v["tax"]),
                "total": float(v["revenue"] + v["tax"]),
                "invoice_count": v["count"],
            }
            for k, v in sorted(revenue_map.items())
        ]

    def calculate_mrr(
        self,
        currency: Optional[str] = None,
        as_of_date: Optional[date] = None,
    ) -> dict:
        """Calculate Monthly Recurring Revenue.

        Args:
            currency: Currency to calculate for (defaults to config).
            as_of_date: Date to calculate as of (defaults to today).

        Returns:
            Dictionary with MRR breakdown.
        """
        config = self.billing_config
        if currency is None:
            currency = config.default_currency
        if as_of_date is None:
            as_of_date = date.today()

        # Get active subscriptions
        subs = (
            self.db.query(Subscription)
            .filter(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.currency == currency,
            )
            .all()
        )

        mrr_total = Decimal("0")
        mrr_by_cycle = {
            "daily": Decimal("0"),
            "weekly": Decimal("0"),
            "monthly": Decimal("0"),
            "quarterly": Decimal("0"),
            "yearly": Decimal("0"),
        }
        mrr_by_plan: Dict[str, Decimal] = {}

        for sub in subs:
            monthly_value = self._normalize_to_monthly(sub.price, sub.billing_cycle)
            mrr_total += monthly_value

            cycle = sub.billing_cycle or "monthly"
            if cycle in mrr_by_cycle:
                mrr_by_cycle[cycle] += monthly_value

            plan = sub.plan_name or "Unknown"
            mrr_by_plan[plan] = mrr_by_plan.get(plan, Decimal("0")) + monthly_value

        return {
            "currency": currency,
            "as_of_date": as_of_date.isoformat(),
            "mrr": float(mrr_total),
            "arr": float(mrr_total * 12),
            "subscription_count": len(subs),
            "breakdown_by_cycle": {k: float(v) for k, v in mrr_by_cycle.items()},
            "breakdown_by_plan": {k: float(v) for k, v in mrr_by_plan.items()},
            "average_revenue_per_subscription": float(
                mrr_total / len(subs) if subs else 0
            ),
        }

    def calculate_churn(
        self,
        period_start: date,
        period_end: date,
        currency: Optional[str] = None,
    ) -> dict:
        """Calculate subscription churn metrics.

        Args:
            period_start: Start of period.
            period_end: End of period.
            currency: Currency to calculate for (defaults to config).

        Returns:
            Dictionary with churn metrics.
        """
        config = self.billing_config
        if currency is None:
            currency = config.default_currency

        # Subscriptions active at period start
        start_subs = (
            self.db.query(Subscription)
            .filter(
                Subscription.currency == currency,
                Subscription.created_at <= datetime.combine(
                    period_start, datetime.max.time()
                ),
                or_(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    and_(
                        Subscription.status == SubscriptionStatus.CANCELLED,
                        Subscription.cancelled_date >= datetime.combine(
                            period_start, datetime.min.time()
                        ),
                    ),
                ),
            )
            .all()
        )

        start_count = len(start_subs)
        start_mrr = sum(
            self._normalize_to_monthly(s.price, s.billing_cycle)
            for s in start_subs
        )

        # Cancelled during period
        cancelled = (
            self.db.query(Subscription)
            .filter(
                Subscription.currency == currency,
                Subscription.status == SubscriptionStatus.CANCELLED,
                Subscription.cancelled_date >= datetime.combine(
                    period_start, datetime.min.time()
                ),
                Subscription.cancelled_date <= datetime.combine(
                    period_end, datetime.max.time()
                ),
            )
            .all()
        )

        churned_count = len(cancelled)
        churned_mrr = sum(
            self._normalize_to_monthly(s.price, s.billing_cycle)
            for s in cancelled
        )

        # New subscriptions during period
        new_subs = (
            self.db.query(Subscription)
            .filter(
                Subscription.currency == currency,
                Subscription.created_at >= datetime.combine(
                    period_start, datetime.min.time()
                ),
                Subscription.created_at <= datetime.combine(
                    period_end, datetime.max.time()
                ),
            )
            .all()
        )

        new_count = len(new_subs)
        new_mrr = sum(
            self._normalize_to_monthly(s.price, s.billing_cycle)
            for s in new_subs
        )

        # Churn rates
        churn_rate = (churned_count / start_count * 100) if start_count > 0 else 0
        revenue_churn_rate = (churned_mrr / start_mrr * 100) if start_mrr > 0 else 0
        net_mrr_change = new_mrr - churned_mrr

        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "currency": currency,
            "starting_subscriptions": start_count,
            "starting_mrr": float(start_mrr),
            "churned_subscriptions": churned_count,
            "churned_mrr": float(churned_mrr),
            "new_subscriptions": new_count,
            "new_mrr": float(new_mrr),
            "net_mrr_change": float(net_mrr_change),
            "churn_rate_percent": round(churn_rate, 2),
            "revenue_churn_rate_percent": round(revenue_churn_rate, 2),
        }

    def calculate_deferred_revenue(
        self,
        as_of_date: Optional[date] = None,
        currency: Optional[str] = None,
    ) -> dict:
        """Calculate deferred revenue from prepaid subscriptions.

        Args:
            as_of_date: Date to calculate as of.
            currency: Currency to calculate for (defaults to config).

        Returns:
            Dictionary with deferred revenue breakdown.
        """
        config = self.billing_config
        if as_of_date is None:
            as_of_date = date.today()
        if currency is None:
            currency = config.default_currency

        # Get active subscriptions with prepaid amounts
        subs = (
            self.db.query(Subscription)
            .filter(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.currency == currency,
                Subscription.billing_cycle.in_(["quarterly", "yearly"]),
            )
            .all()
        )

        total_deferred = Decimal("0")
        breakdown = []

        for sub in subs:
            if sub.start_date:
                start = sub.start_date.date() if isinstance(
                    sub.start_date, datetime
                ) else sub.start_date

                if sub.billing_cycle == "quarterly":
                    period_days = 90
                elif sub.billing_cycle == "yearly":
                    period_days = 365
                else:
                    continue

                days_elapsed = (as_of_date - start).days % period_days
                days_remaining = period_days - days_elapsed

                daily_rate = sub.price / period_days
                deferred = daily_rate * days_remaining

                total_deferred += deferred
                breakdown.append({
                    "subscription_id": sub.id,
                    "plan_name": sub.plan_name,
                    "billing_cycle": sub.billing_cycle,
                    "total_prepaid": float(sub.price),
                    "days_elapsed": days_elapsed,
                    "days_remaining": days_remaining,
                    "recognized": float(daily_rate * days_elapsed),
                    "deferred_amount": float(deferred),
                })

        return {
            "as_of_date": as_of_date.isoformat(),
            "currency": currency,
            "total_deferred_revenue": float(total_deferred),
            "subscription_count": len(breakdown),
            "breakdown": breakdown,
        }

    # -------------------------------------------------------------------------
    # Helper Methods
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

    def _get_customer_account_id(self, party_id: int) -> Optional[int]:
        account = (
            self.db.query(CustomerAccount)
            .filter(CustomerAccount.party_id == party_id)
            .first()
        )
        return account.id if account else None

    def _get_or_create_customer_account(self, party_id: int) -> CustomerAccount:
        """Get or create a customer account record for a party."""
        account = (
            self.db.query(CustomerAccount)
            .filter(CustomerAccount.party_id == party_id)
            .first()
        )
        if account:
            return account

        party = self.db.query(Party).filter(Party.id == party_id).first()
        if not party:
            raise NotFoundError(f"Party {party_id} not found")

        account = CustomerAccount(
            party_id=party_id,
            account_number=f"ACCT-{party_id}",
        )
        self.db.add(account)
        self.db.flush()
        return account

    def _normalize_to_monthly(
        self, price: Decimal, billing_cycle: Optional[str]
    ) -> Decimal:
        """Normalize subscription price to monthly value."""
        cycle = billing_cycle or "monthly"

        if cycle == "daily":
            return price * 30
        elif cycle == "weekly":
            return price * Decimal("4.33")
        elif cycle == "monthly":
            return price
        elif cycle == "quarterly":
            return price / 3
        elif cycle == "yearly":
            return price / 12
        else:
            return price
