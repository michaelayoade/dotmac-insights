"""Subscriber service - business logic for subscriber management.

This service provides:
- Subscriber CRUD (Party with subscriber role)
- 360-degree view aggregation
- Subscriber analytics and stats

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import func, or_, and_, case
from sqlalchemy.orm import Session, joinedload

from app.models.party import Party, PartyRole, CustomerAccount
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.payment_subscription import PaymentSubscription
from app.models.invoice import Invoice
from app.models.ticket import Ticket
from app.models.service_transaction import ServiceTransaction
from app.services.base import paginate, scoped_query
from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.types import PaginatedResult, PaginationParams
from app.services.activity_logger import ActivityLogger

from .subscriber_types import (
    SubscriberFilters,
    SubscriberCreateData,
    SubscriberUpdateData,
    Subscriber360Data,
    SubscriberStats,
    SubscriberServiceSummary,
    SubscriberFinancialSummary,
    SubscriberSupportSummary,
    SubscriberUsageSummary,
)

if TYPE_CHECKING:
    from app.auth import Principal


class SubscriberService:
    """Service for subscriber management and 360 view."""

    SUBSCRIBER_ROLE = "subscriber"
    CUSTOMER_ROLE = "customer"

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Subscriber List & Search
    # -------------------------------------------------------------------------

    def list_subscribers(
        self,
        filters: Optional[SubscriberFilters] = None,
        pagination: Optional[PaginationParams] = None,
        include_account: bool = True,
    ) -> PaginatedResult[Party]:
        """List subscribers with optional filters and pagination.

        Subscribers are Parties that have either:
        - A 'subscriber' role, OR
        - A 'customer' role, OR
        - Subscriptions linked to them

        Args:
            filters: Optional filter criteria.
            pagination: Optional pagination parameters.
            include_account: Whether to eagerly load CustomerAccount.

        Returns:
            PaginatedResult containing parties and total count.
        """
        query = scoped_query(self.db.query(Party), self.principal)

        # Eager load roles
        query = query.options(joinedload(Party.roles))

        if include_account:
            query = query.outerjoin(
                CustomerAccount, CustomerAccount.party_id == Party.id
            )

        # Filter to only parties with subscriber/customer roles or subscriptions
        subscriber_subq = (
            self.db.query(PartyRole.party_id)
            .filter(
                PartyRole.role.in_([self.SUBSCRIBER_ROLE, self.CUSTOMER_ROLE]),
                PartyRole.until.is_(None),
            )
            .subquery()
        )
        subscription_subq = (
            self.db.query(Subscription.party_id)
            .filter(Subscription.status != SubscriptionStatus.CANCELLED)
            .distinct()
            .subquery()
        )

        query = query.filter(
            or_(
                Party.id.in_(subscriber_subq),
                Party.id.in_(subscription_subq),
            )
        )

        if filters:
            if filters.search:
                like = f"%{filters.search}%"
                query = query.filter(
                    or_(
                        Party.name.ilike(like),
                        Party.primary_email.ilike(like),
                        Party.primary_phone.ilike(like),
                        Party.first_name.ilike(like),
                        Party.last_name.ilike(like),
                    )
                )

            if filters.status:
                query = query.filter(Party.status == filters.status)

            if filters.party_type:
                query = query.filter(Party.type == filters.party_type)

            if filters.has_active_subscription is not None:
                active_sub_subq = (
                    self.db.query(Subscription.party_id)
                    .filter(Subscription.status == SubscriptionStatus.ACTIVE)
                    .distinct()
                    .subquery()
                )
                if filters.has_active_subscription:
                    query = query.filter(Party.id.in_(active_sub_subq))
                else:
                    query = query.filter(~Party.id.in_(active_sub_subq))

            if filters.subscription_status:
                status_subq = (
                    self.db.query(Subscription.party_id)
                    .filter(Subscription.status == filters.subscription_status)
                    .distinct()
                    .subquery()
                )
                query = query.filter(Party.id.in_(status_subq))

            if filters.service_type:
                type_subq = (
                    self.db.query(Subscription.party_id)
                    .filter(Subscription.service_type == filters.service_type)
                    .distinct()
                    .subquery()
                )
                query = query.filter(Party.id.in_(type_subq))

            if filters.has_outstanding_balance is not None:
                if include_account:
                    if filters.has_outstanding_balance:
                        query = query.filter(
                            CustomerAccount.outstanding_balance > 0
                        )
                    else:
                        query = query.filter(
                            or_(
                                CustomerAccount.outstanding_balance.is_(None),
                                CustomerAccount.outstanding_balance <= 0,
                            )
                        )

            if filters.created_after:
                query = query.filter(Party.created_at >= filters.created_after)

            if filters.created_before:
                query = query.filter(Party.created_at <= filters.created_before)

        query = query.order_by(Party.name.asc())
        return paginate(query, pagination)

    def get_subscriber(
        self,
        party_id: int,
        include_roles: bool = True,
    ) -> Party:
        """Get a subscriber by party ID.

        Args:
            party_id: The party ID.
            include_roles: Whether to eagerly load roles.

        Returns:
            The Party.

        Raises:
            NotFoundError: If subscriber not found.
        """
        query = scoped_query(self.db.query(Party), self.principal)

        if include_roles:
            query = query.options(joinedload(Party.roles))

        party = query.filter(Party.id == party_id).first()
        if not party:
            raise NotFoundError(f"Subscriber {party_id} not found")

        return party

    def get_customer_account(self, party_id: int) -> Optional[CustomerAccount]:
        """Get the CustomerAccount for a party if it exists.

        Args:
            party_id: The party ID.

        Returns:
            CustomerAccount or None.
        """
        return (
            self.db.query(CustomerAccount)
            .filter(CustomerAccount.party_id == party_id)
            .first()
        )

    # -------------------------------------------------------------------------
    # Subscriber CRUD
    # -------------------------------------------------------------------------

    def create_subscriber(self, data: SubscriberCreateData) -> Party:
        """Create a new subscriber (Party + subscriber role + optional account).

        Args:
            data: Subscriber creation data.

        Returns:
            The created Party (not yet committed).

        Raises:
            ConflictError: If email already exists.
            ValidationError: If data is invalid.
        """
        # Derive primary email/phone
        primary_email = None
        primary_phone = None

        if data.emails:
            for email in data.emails:
                if email.get("is_primary") or not primary_email:
                    primary_email = email.get("address")

        if data.phones:
            for phone in data.phones:
                if phone.get("is_primary") or not primary_phone:
                    primary_phone = phone.get("number")

        # Check email uniqueness
        if primary_email:
            existing = (
                self.db.query(Party)
                .filter(Party.primary_email == primary_email)
                .first()
            )
            if existing:
                raise ConflictError(f"Party with email {primary_email} already exists")

        # Create Party
        party = Party(
            type=data.party_type,
            status="active",
            name=data.name,
            first_name=data.first_name,
            last_name=data.last_name,
            legal_name=data.legal_name,
            trading_name=data.trading_name,
            primary_email=primary_email,
            primary_phone=primary_phone,
            emails=data.emails,
            phones=data.phones,
            addresses=data.addresses,
            external_ids=data.external_ids or {},
            avatar_url=data.avatar_url,
            timezone=data.timezone,
            locale=data.locale,
            tax_id=data.tax_id,
            tags=data.tags or [],
            custom_fields=data.custom_fields or {},
            notes=data.notes,
        )
        self.db.add(party)
        self.db.flush()

        # Add subscriber role
        role = PartyRole(
            party_id=party.id,
            role=self.SUBSCRIBER_ROLE,
            status="active",
        )
        self.db.add(role)

        # Also add customer role if creating account
        if data.create_account or data.customer_account_id:
            customer_role = PartyRole(
                party_id=party.id,
                role=self.CUSTOMER_ROLE,
                status="active",
            )
            self.db.add(customer_role)

        # Create CustomerAccount if requested
        if data.create_account and not data.customer_account_id:
            account_number = self._generate_account_number()
            account = CustomerAccount(
                party_id=party.id,
                account_number=account_number,
                status="active",
                tier=data.account_tier,
                account_type="direct",
                billing_type=data.billing_type,
                billing_email=data.billing_email or primary_email,
                billing_cycle=data.billing_cycle,
                payment_terms=data.payment_terms,
                credit_limit=data.credit_limit,
                currency=data.currency,
            )
            self.db.add(account)

        self.db.flush()
        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="crm.party.create",
            user_id=self.principal.id if self.principal else None,
            user_email=getattr(self.principal, "email", None),
            entity_type="party",
            entity_id=str(party.id),
            summary=f"Created subscriber {party.name}",
            metadata={"customer_account": bool(data.create_account or data.customer_account_id)},
        )
        return party

    def update_subscriber(
        self,
        party_id: int,
        data: SubscriberUpdateData,
    ) -> Party:
        """Update a subscriber.

        Args:
            party_id: The party ID.
            data: Fields to update.

        Returns:
            The updated Party (not yet committed).

        Raises:
            NotFoundError: If subscriber not found.
            ConflictError: If email already exists on another party.
        """
        party = self.get_subscriber(party_id, include_roles=False)

        # Update simple fields
        simple_fields = [
            "status", "name", "first_name", "last_name", "legal_name",
            "trading_name", "avatar_url", "timezone", "locale", "tax_id",
            "tags", "custom_fields", "notes", "external_ids",
        ]
        for field_name in simple_fields:
            value = getattr(data, field_name, None)
            if value is not None:
                setattr(party, field_name, value)

        # Handle emails - update primary_email
        if data.emails is not None:
            party.emails = data.emails
            primary_email = None
            for email in data.emails:
                if email.get("is_primary") or not primary_email:
                    primary_email = email.get("address")

            if primary_email and primary_email != party.primary_email:
                existing = (
                    self.db.query(Party)
                    .filter(Party.primary_email == primary_email, Party.id != party_id)
                    .first()
                )
                if existing:
                    raise ConflictError(f"Party with email {primary_email} already exists")
                party.primary_email = primary_email

        # Handle phones - update primary_phone
        if data.phones is not None:
            party.phones = data.phones
            primary_phone = None
            for phone in data.phones:
                if phone.get("is_primary") or not primary_phone:
                    primary_phone = phone.get("number")
            party.primary_phone = primary_phone

        # Handle addresses
        if data.addresses is not None:
            party.addresses = data.addresses

        # Update CustomerAccount if exists
        account = self.get_customer_account(party_id)
        if account:
            account_fields = [
                "account_tier", "billing_type", "billing_email",
                "billing_cycle", "payment_terms", "credit_limit",
            ]
            for field_name in account_fields:
                value = getattr(data, field_name, None)
                if value is not None:
                    # Map account_tier to tier
                    db_field = "tier" if field_name == "account_tier" else field_name
                    setattr(account, db_field, value)

        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="crm.party.update",
            user_id=self.principal.id if self.principal else None,
            user_email=getattr(self.principal, "email", None),
            entity_type="party",
            entity_id=str(party.id),
            summary=f"Updated subscriber {party.name}",
        )
        return party

    def delete_subscriber(self, party_id: int) -> None:
        """Soft delete a subscriber (set status to inactive).

        Args:
            party_id: The party ID.

        Raises:
            NotFoundError: If subscriber not found.
            ValidationError: If subscriber has active subscriptions.
        """
        party = self.get_subscriber(party_id)

        # Check for active subscriptions
        active_count = (
            self.db.query(Subscription)
            .filter(
                Subscription.party_id == party_id,
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
            .count()
        )
        if active_count > 0:
            raise ValidationError(
                f"Cannot delete subscriber with {active_count} active subscription(s)"
            )

        party.status = "inactive"

        # End subscriber role
        for role in party.roles:
            if role.role in [self.SUBSCRIBER_ROLE, self.CUSTOMER_ROLE] and role.until is None:
                role.until = datetime.now(timezone.utc)

        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="crm.party.delete",
            user_id=self.principal.id if self.principal else None,
            user_email=getattr(self.principal, "email", None),
            entity_type="party",
            entity_id=str(party.id),
            summary=f"Deactivated subscriber {party.name}",
        )

    # -------------------------------------------------------------------------
    # 360 View
    # -------------------------------------------------------------------------

    def get_subscriber_360(
        self,
        party_id: int,
        include_invoices: bool = True,
        include_tickets: bool = True,
        include_usage: bool = True,
        invoice_limit: int = 10,
        ticket_limit: int = 10,
        transaction_limit: int = 20,
    ) -> Subscriber360Data:
        """Get comprehensive 360-degree view of a subscriber.

        Aggregates data from multiple sources into a single view.

        Args:
            party_id: The party ID.
            include_invoices: Whether to include invoice data.
            include_tickets: Whether to include ticket data.
            include_usage: Whether to include usage/session data.
            invoice_limit: Max invoices to return.
            ticket_limit: Max tickets to return.
            transaction_limit: Max transactions to return.

        Returns:
            Subscriber360Data with all aggregated information.

        Raises:
            NotFoundError: If subscriber not found.
        """
        party = self.get_subscriber(party_id, include_roles=True)
        account = self.get_customer_account(party_id)

        # Get subscriptions
        subscriptions = (
            self.db.query(Subscription)
            .filter(Subscription.party_id == party_id)
            .options(joinedload(Subscription.tariff))
            .order_by(Subscription.created_at.desc())
            .all()
        )

        # Get payment subscriptions
        payment_subscriptions = (
            self.db.query(PaymentSubscription)
            .filter(PaymentSubscription.party_id == party_id)
            .order_by(PaymentSubscription.created_at.desc())
            .all()
        )

        # Build service summary
        service_summary = self._build_service_summary(subscriptions, payment_subscriptions)

        # Get invoices
        invoices = []
        if include_invoices and account:
            invoices = (
                self.db.query(Invoice)
                .filter(
                    Invoice.customer_account_id == account.id,
                    Invoice.is_deleted == False,
                )
                .order_by(Invoice.invoice_date.desc())
                .limit(invoice_limit)
                .all()
            )

        # Build financial summary
        financial_summary = self._build_financial_summary(party_id, account, invoices)

        # Get tickets
        tickets = []
        if include_tickets:
            tickets = (
                self.db.query(Ticket)
                .filter(Ticket.party_id == party_id)
                .order_by(Ticket.created_at.desc())
                .limit(ticket_limit)
                .all()
            )

        # Build support summary
        support_summary = self._build_support_summary(party_id)

        # Get usage summary
        usage_summary = SubscriberUsageSummary()
        active_sessions = []
        if include_usage:
            usage_summary, active_sessions = self._build_usage_summary(party_id, subscriptions)

        # Get recent transactions
        recent_transactions = (
            self.db.query(ServiceTransaction)
            .filter(ServiceTransaction.party_id == party_id)
            .order_by(ServiceTransaction.created_at.desc())
            .limit(transaction_limit)
            .all()
        )

        # Build activity timeline
        recent_activity = self._build_activity_timeline(
            subscriptions, invoices, tickets, recent_transactions
        )

        return Subscriber360Data(
            party=party,
            roles=list(party.roles) if party.roles else [],
            customer_account=account,
            subscriptions=subscriptions,
            payment_subscriptions=payment_subscriptions,
            service_summary=service_summary,
            invoices=invoices,
            financial_summary=financial_summary,
            tickets=tickets,
            support_summary=support_summary,
            active_sessions=active_sessions,
            usage_summary=usage_summary,
            recent_transactions=[
                {
                    "id": t.id,
                    "type": t.transaction_type,
                    "status": t.status,
                    "amount": float(t.amount) if t.amount else 0,
                    "created_at": t.created_at,
                    "description": t.description,
                }
                for t in recent_transactions
            ],
            recent_activity=recent_activity,
        )

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_stats(self) -> SubscriberStats:
        """Get aggregate subscriber statistics.

        Returns:
            SubscriberStats with aggregate metrics.
        """
        # Count subscribers by status
        status_counts = (
            self.db.query(
                Party.status,
                func.count(Party.id),
            )
            .join(PartyRole, PartyRole.party_id == Party.id)
            .filter(
                PartyRole.role.in_([self.SUBSCRIBER_ROLE, self.CUSTOMER_ROLE]),
                PartyRole.until.is_(None),
            )
            .group_by(Party.status)
            .all()
        )

        stats = SubscriberStats()
        for status, count in status_counts:
            stats.total_subscribers += count
            if status == "active":
                stats.active_subscribers = count
            elif status == "inactive":
                stats.inactive_subscribers = count
            elif status == "blocked":
                stats.blocked_subscribers = count

        # Count by type
        type_counts = (
            self.db.query(
                Party.type,
                func.count(Party.id),
            )
            .join(PartyRole, PartyRole.party_id == Party.id)
            .filter(
                PartyRole.role.in_([self.SUBSCRIBER_ROLE, self.CUSTOMER_ROLE]),
                PartyRole.until.is_(None),
            )
            .group_by(Party.type)
            .all()
        )

        for ptype, count in type_counts:
            if ptype == "person":
                stats.person_count = count
            elif ptype == "organization":
                stats.organization_count = count

        # New/churned this month
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        stats.new_this_month = (
            self.db.query(func.count(Party.id))
            .join(PartyRole, PartyRole.party_id == Party.id)
            .filter(
                PartyRole.role.in_([self.SUBSCRIBER_ROLE, self.CUSTOMER_ROLE]),
                Party.created_at >= month_start,
            )
            .scalar() or 0
        )

        stats.churned_this_month = (
            self.db.query(func.count(PartyRole.id))
            .filter(
                PartyRole.role.in_([self.SUBSCRIBER_ROLE, self.CUSTOMER_ROLE]),
                PartyRole.until >= month_start,
                PartyRole.until <= now,
            )
            .scalar() or 0
        )

        stats.net_growth = stats.new_this_month - stats.churned_this_month

        # Financial aggregates from CustomerAccount
        financial_agg = (
            self.db.query(
                func.sum(CustomerAccount.mrr),
                func.sum(CustomerAccount.outstanding_balance),
            )
            .filter(CustomerAccount.status == "active")
            .first()
        )

        if financial_agg:
            stats.total_mrr = Decimal(str(financial_agg[0] or 0))
            stats.total_outstanding = Decimal(str(financial_agg[1] or 0))

        return stats

    # -------------------------------------------------------------------------
    # Private Helpers
    # -------------------------------------------------------------------------

    def _generate_account_number(self) -> str:
        """Generate a unique account number."""
        import random
        import string

        prefix = "ACC"
        while True:
            suffix = "".join(random.choices(string.digits, k=8))
            account_number = f"{prefix}{suffix}"
            exists = (
                self.db.query(CustomerAccount)
                .filter(CustomerAccount.account_number == account_number)
                .first()
            )
            if not exists:
                return account_number

    def _build_service_summary(
        self,
        subscriptions: List[Subscription],
        payment_subscriptions: List[PaymentSubscription],
    ) -> SubscriberServiceSummary:
        """Build service summary from subscriptions."""
        summary = SubscriberServiceSummary()
        summary.total_subscriptions = len(subscriptions)
        summary.payment_subscriptions = len(payment_subscriptions)

        for sub in subscriptions:
            if sub.status == SubscriptionStatus.ACTIVE:
                summary.active_subscriptions += 1
                summary.total_mrr += sub.price or Decimal("0")
                summary.total_speed_mbps += sub.download_speed or 0
            elif sub.status == SubscriptionStatus.SUSPENDED:
                summary.suspended_subscriptions += 1
            elif sub.status == SubscriptionStatus.CANCELLED:
                summary.cancelled_subscriptions += 1

            # Count by type
            stype = sub.service_type.value if hasattr(sub.service_type, 'value') else str(sub.service_type)
            if stype == "internet":
                summary.internet_count += 1
            elif stype == "voice":
                summary.voice_count += 1
            elif stype == "bundle":
                summary.bundle_count += 1

        for psub in payment_subscriptions:
            if psub.status == "active":
                summary.active_payment_subscriptions += 1

        return summary

    def _build_financial_summary(
        self,
        party_id: int,
        account: Optional[CustomerAccount],
        invoices: List[Invoice],
    ) -> SubscriberFinancialSummary:
        """Build financial summary."""
        summary = SubscriberFinancialSummary()

        if account:
            summary.outstanding_balance = account.outstanding_balance or Decimal("0")
            summary.mrr = account.mrr or Decimal("0")
            summary.total_revenue = account.total_revenue or Decimal("0")
            summary.credit_limit = account.credit_limit
            if account.credit_limit:
                summary.available_credit = account.credit_limit - summary.outstanding_balance

        summary.total_invoices = len(invoices)
        now = datetime.now(timezone.utc).date()

        for inv in invoices:
            if inv.status in ["draft", "submitted", "unpaid"]:
                summary.open_invoices += 1
            if inv.due_date and inv.due_date < now and inv.outstanding_amount > 0:
                summary.overdue_invoices += 1
                summary.overdue_amount += inv.outstanding_amount

        return summary

    def _build_support_summary(self, party_id: int) -> SubscriberSupportSummary:
        """Build support summary from tickets."""
        summary = SubscriberSupportSummary()

        # Count tickets by status
        ticket_counts = (
            self.db.query(
                Ticket.status,
                func.count(Ticket.id),
            )
            .filter(Ticket.party_id == party_id)
            .group_by(Ticket.status)
            .all()
        )

        for status, count in ticket_counts:
            summary.total_tickets += count
            status_val = status.value if hasattr(status, 'value') else str(status)
            if status_val in ["open", "in_progress", "waiting", "reopened"]:
                summary.open_tickets += count
            elif status_val in ["resolved", "closed"]:
                summary.resolved_tickets += count

        # Get latest ticket
        latest = (
            self.db.query(Ticket)
            .filter(Ticket.party_id == party_id)
            .order_by(Ticket.created_at.desc())
            .first()
        )
        if latest:
            summary.last_ticket_date = latest.created_at
            summary.last_ticket_subject = latest.subject

        return summary

    def _build_usage_summary(
        self,
        party_id: int,
        subscriptions: List[Subscription],
    ) -> tuple[SubscriberUsageSummary, List[dict]]:
        """Build usage summary. Returns (summary, active_sessions)."""
        summary = SubscriberUsageSummary()
        active_sessions = []

        # This would integrate with SessionService/UsageService
        # For now, return empty data - to be wired up
        subscription_ids = [s.id for s in subscriptions if s.status == SubscriptionStatus.ACTIVE]

        if subscription_ids:
            # Placeholder for session/usage integration
            # Would call SessionService.list_active_sessions() etc.
            pass

        return summary, active_sessions

    def _build_activity_timeline(
        self,
        subscriptions: List[Subscription],
        invoices: List[Invoice],
        tickets: List[Ticket],
        transactions: List[ServiceTransaction],
    ) -> List[dict]:
        """Build a unified activity timeline."""
        activities = []

        # Add subscription events
        for sub in subscriptions[:5]:
            activities.append({
                "type": "subscription",
                "date": sub.created_at,
                "title": f"Subscription: {sub.plan_name}",
                "description": f"Status: {sub.status.value if hasattr(sub.status, 'value') else sub.status}",
                "icon": "wifi",
            })

        # Add invoice events
        for inv in invoices[:5]:
            activities.append({
                "type": "invoice",
                "date": inv.created_at,
                "title": f"Invoice #{inv.invoice_number}",
                "description": f"Amount: {inv.total_amount} {inv.currency}",
                "icon": "receipt",
            })

        # Add ticket events
        for ticket in tickets[:5]:
            activities.append({
                "type": "ticket",
                "date": ticket.created_at,
                "title": f"Ticket: {ticket.subject}",
                "description": f"Status: {ticket.status.value if hasattr(ticket.status, 'value') else ticket.status}",
                "icon": "headset",
            })

        # Sort by date descending
        activities.sort(key=lambda x: x["date"] or datetime.min, reverse=True)

        return activities[:20]
