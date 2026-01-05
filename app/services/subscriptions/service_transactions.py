"""Service Transaction Management.

Tracks all service-level transactions for subscriptions:
- Activations, suspensions, cancellations
- Plan upgrades and downgrades
- Credits, adjustments, refunds
- Fee charges (installation, reconnection)
- Usage-based charges

These transactions provide an audit trail and integrate with
accounting for financial reconciliation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session, joinedload

from app.models.subscription import Subscription
from app.services.base import paginate, scoped_query
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = [
    # Enums
    "ServiceTransactionType",
    "ServiceTransactionStatus",
    # DTOs
    "ServiceTransactionFilters",
    "ServiceTransactionCreateData",
    "ServiceTransactionSummary",
    "PartyTransactionHistory",
    # Service
    "ServiceTransactionService",
]


# =============================================================================
# ENUMS
# =============================================================================

class ServiceTransactionType(str, Enum):
    """Types of service transactions."""

    # Lifecycle events
    ACTIVATION = "activation"
    SUSPENSION = "suspension"
    REACTIVATION = "reactivation"
    CANCELLATION = "cancellation"

    # Plan changes
    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"
    RENEWAL = "renewal"

    # Charges
    SUBSCRIPTION_CHARGE = "subscription_charge"
    USAGE_CHARGE = "usage_charge"
    INSTALLATION_FEE = "installation_fee"
    ACTIVATION_FEE = "activation_fee"
    RECONNECTION_FEE = "reconnection_fee"
    EARLY_TERMINATION_FEE = "early_termination_fee"
    OTHER_FEE = "other_fee"

    # Credits
    CREDIT = "credit"
    ADJUSTMENT = "adjustment"
    REFUND = "refund"
    PRORATION_CREDIT = "proration_credit"
    PRORATION_CHARGE = "proration_charge"

    # Service events
    PROVISIONING = "provisioning"
    DEPROVISIONING = "deprovisioning"
    IP_CHANGE = "ip_change"
    SPEED_CHANGE = "speed_change"


class ServiceTransactionStatus(str, Enum):
    """Status of a service transaction."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"
    CANCELLED = "cancelled"


# =============================================================================
# DTOs
# =============================================================================

@dataclass
class ServiceTransactionFilters:
    """Filters for listing service transactions."""

    subscription_id: Optional[int] = None
    party_id: Optional[int] = None
    transaction_type: Optional[str] = None
    status: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    amount_min: Optional[Decimal] = None
    amount_max: Optional[Decimal] = None
    has_invoice: Optional[bool] = None
    search: Optional[str] = None


@dataclass
class ServiceTransactionCreateData:
    """Data for creating a service transaction."""

    subscription_id: int
    party_id: int
    transaction_type: str
    description: str

    # Financial
    amount: Decimal = Decimal("0")
    currency: str = "NGN"

    # Reference to other entities
    invoice_id: Optional[int] = None
    payment_id: Optional[int] = None
    credit_note_id: Optional[int] = None

    # Context
    old_value: Optional[str] = None  # For changes (e.g., old plan name)
    new_value: Optional[str] = None  # For changes (e.g., new plan name)
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Processing
    effective_date: Optional[date] = None
    status: str = "completed"


@dataclass
class ServiceTransactionSummary:
    """Summary of service transactions for a period."""

    period_start: date
    period_end: date
    currency: str = "NGN"

    # Counts
    total_transactions: int = 0
    activations: int = 0
    cancellations: int = 0
    upgrades: int = 0
    downgrades: int = 0

    # Amounts
    total_charges: Decimal = Decimal("0")
    total_credits: Decimal = Decimal("0")
    net_amount: Decimal = Decimal("0")

    # Breakdown
    subscription_charges: Decimal = Decimal("0")
    usage_charges: Decimal = Decimal("0")
    fee_charges: Decimal = Decimal("0")
    credits_issued: Decimal = Decimal("0")
    refunds_issued: Decimal = Decimal("0")

    # By type
    by_type: Dict[str, int] = field(default_factory=dict)


@dataclass
class PartyTransactionHistory:
    """Transaction history for a party."""

    party_id: int
    party_name: str

    # Lifetime
    total_transactions: int = 0
    total_charges: Decimal = Decimal("0")
    total_credits: Decimal = Decimal("0")
    total_refunds: Decimal = Decimal("0")
    net_lifetime_value: Decimal = Decimal("0")

    # Current period
    current_month_charges: Decimal = Decimal("0")
    current_month_credits: Decimal = Decimal("0")

    # Subscription stats
    active_subscriptions: int = 0
    total_subscriptions: int = 0
    upgrades_count: int = 0
    downgrades_count: int = 0

    # Recent transactions (last 10)
    recent_transactions: List[Dict[str, Any]] = field(default_factory=list)


# =============================================================================
# SERVICE TRANSACTION MODEL (if not exists, define inline)
# =============================================================================

# Note: This assumes a ServiceTransaction model exists or will be created.
# For now, we'll work with a dict-based approach that can be persisted.

@dataclass
class ServiceTransaction:
    """Service transaction record (in-memory representation)."""

    id: Optional[int] = None
    subscription_id: int = 0
    party_id: int = 0
    transaction_type: str = ""
    status: str = "completed"
    description: str = ""

    amount: Decimal = Decimal("0")
    currency: str = "NGN"

    invoice_id: Optional[int] = None
    payment_id: Optional[int] = None
    credit_note_id: Optional[int] = None

    old_value: Optional[str] = None
    new_value: Optional[str] = None
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    effective_date: Optional[date] = None
    created_at: Optional[datetime] = None
    created_by_id: Optional[int] = None


# =============================================================================
# SERVICE
# =============================================================================

class ServiceTransactionService:
    """Service for managing subscription service transactions.

    Provides transaction tracking and audit trail for all subscription
    lifecycle events and financial transactions.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None):
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Transaction CRUD
    # -------------------------------------------------------------------------

    def create_transaction(self, data: ServiceTransactionCreateData) -> Dict[str, Any]:
        """Create a service transaction record.

        Args:
            data: Transaction creation data.

        Returns:
            Created transaction as dict.
        """
        from app.models.service_transaction import ServiceTransaction as ServiceTransactionModel

        # Validate subscription exists
        sub = self.db.query(Subscription).filter(
            Subscription.id == data.subscription_id
        ).first()
        if not sub:
            raise ValidationError(f"Subscription {data.subscription_id} not found")

        # Validate transaction type
        try:
            txn_type = ServiceTransactionType(data.transaction_type)
        except ValueError:
            raise ValidationError(f"Invalid transaction type: {data.transaction_type}")

        # Validate status
        try:
            status = ServiceTransactionStatus(data.status)
        except ValueError:
            status = ServiceTransactionStatus.COMPLETED

        txn = ServiceTransactionModel(
            subscription_id=data.subscription_id,
            party_id=data.party_id,
            transaction_type=txn_type.value,
            status=status.value,
            description=data.description,
            amount=data.amount,
            currency=data.currency,
            invoice_id=data.invoice_id,
            payment_id=data.payment_id,
            credit_note_id=data.credit_note_id,
            old_value=data.old_value,
            new_value=data.new_value,
            reason=data.reason,
            metadata_json=data.metadata or {},
            effective_date=data.effective_date or date.today(),
            created_by_id=self.principal.id if self.principal else None,
        )

        self.db.add(txn)
        self.db.flush()

        return self._to_dict(txn)

    def get_transaction(self, transaction_id: int) -> Dict[str, Any]:
        """Get a transaction by ID."""
        from app.models.service_transaction import ServiceTransaction as ServiceTransactionModel

        txn = self.db.query(ServiceTransactionModel).filter(
            ServiceTransactionModel.id == transaction_id
        ).first()

        if not txn:
            raise NotFoundError(f"Transaction {transaction_id} not found")

        return self._to_dict(txn)

    def list_transactions(
        self,
        filters: Optional[ServiceTransactionFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Dict[str, Any]]:
        """List service transactions with filters."""
        from app.models.service_transaction import ServiceTransaction as ServiceTransactionModel

        query = self.db.query(ServiceTransactionModel)

        if filters:
            if filters.subscription_id:
                query = query.filter(
                    ServiceTransactionModel.subscription_id == filters.subscription_id
                )
            if filters.party_id:
                query = query.filter(
                    ServiceTransactionModel.party_id == filters.party_id
                )
            if filters.transaction_type:
                query = query.filter(
                    ServiceTransactionModel.transaction_type == filters.transaction_type
                )
            if filters.status:
                query = query.filter(
                    ServiceTransactionModel.status == filters.status
                )
            if filters.date_from:
                query = query.filter(
                    ServiceTransactionModel.effective_date >= filters.date_from
                )
            if filters.date_to:
                query = query.filter(
                    ServiceTransactionModel.effective_date <= filters.date_to
                )
            if filters.amount_min is not None:
                query = query.filter(
                    ServiceTransactionModel.amount >= filters.amount_min
                )
            if filters.amount_max is not None:
                query = query.filter(
                    ServiceTransactionModel.amount <= filters.amount_max
                )
            if filters.has_invoice is not None:
                if filters.has_invoice:
                    query = query.filter(
                        ServiceTransactionModel.invoice_id.isnot(None)
                    )
                else:
                    query = query.filter(
                        ServiceTransactionModel.invoice_id.is_(None)
                    )
            if filters.search:
                like = f"%{filters.search}%"
                query = query.filter(
                    or_(
                        ServiceTransactionModel.description.ilike(like),
                        ServiceTransactionModel.reason.ilike(like),
                    )
                )

        query = query.order_by(ServiceTransactionModel.created_at.desc())

        result = paginate(query, pagination)
        return PaginatedResult(
            items=[self._to_dict(t) for t in result.items],
            total=result.total,
            offset=result.offset,
            limit=result.limit,
        )

    def reverse_transaction(
        self,
        transaction_id: int,
        reason: str,
    ) -> Dict[str, Any]:
        """Reverse a transaction (create offsetting entry)."""
        from app.models.service_transaction import ServiceTransaction as ServiceTransactionModel

        original = self.db.query(ServiceTransactionModel).filter(
            ServiceTransactionModel.id == transaction_id
        ).first()

        if not original:
            raise NotFoundError(f"Transaction {transaction_id} not found")

        if original.status == ServiceTransactionStatus.REVERSED.value:
            raise ValidationError("Transaction already reversed")

        # Mark original as reversed
        original.status = ServiceTransactionStatus.REVERSED.value

        # Create reversal transaction
        reversal = ServiceTransactionModel(
            subscription_id=original.subscription_id,
            party_id=original.party_id,
            transaction_type=original.transaction_type,
            status=ServiceTransactionStatus.COMPLETED.value,
            description=f"Reversal: {original.description}",
            amount=-original.amount,  # Negate amount
            currency=original.currency,
            reason=reason,
            metadata={"reversed_transaction_id": original.id},
            effective_date=date.today(),
            created_by_id=self.principal.id if self.principal else None,
        )

        self.db.add(reversal)
        self.db.flush()

        return self._to_dict(reversal)

    # -------------------------------------------------------------------------
    # Lifecycle Transaction Helpers
    # -------------------------------------------------------------------------

    def record_activation(
        self,
        subscription_id: int,
        party_id: int,
        amount: Decimal = Decimal("0"),
        activation_fee: Decimal = Decimal("0"),
        notes: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Record activation transaction(s)."""
        transactions = []

        # Activation event
        txn = self.create_transaction(ServiceTransactionCreateData(
            subscription_id=subscription_id,
            party_id=party_id,
            transaction_type=ServiceTransactionType.ACTIVATION.value,
            description="Service activated",
            amount=Decimal("0"),  # Event, not charge
            reason=notes,
        ))
        transactions.append(txn)

        # Activation fee if applicable
        if activation_fee > 0:
            fee_txn = self.create_transaction(ServiceTransactionCreateData(
                subscription_id=subscription_id,
                party_id=party_id,
                transaction_type=ServiceTransactionType.ACTIVATION_FEE.value,
                description="Activation fee",
                amount=activation_fee,
            ))
            transactions.append(fee_txn)

        return transactions

    def record_suspension(
        self,
        subscription_id: int,
        party_id: int,
        reason: str,
    ) -> Dict[str, Any]:
        """Record suspension transaction."""
        return self.create_transaction(ServiceTransactionCreateData(
            subscription_id=subscription_id,
            party_id=party_id,
            transaction_type=ServiceTransactionType.SUSPENSION.value,
            description="Service suspended",
            amount=Decimal("0"),
            reason=reason,
        ))

    def record_reactivation(
        self,
        subscription_id: int,
        party_id: int,
        reconnection_fee: Decimal = Decimal("0"),
    ) -> List[Dict[str, Any]]:
        """Record reactivation transaction(s)."""
        transactions = []

        txn = self.create_transaction(ServiceTransactionCreateData(
            subscription_id=subscription_id,
            party_id=party_id,
            transaction_type=ServiceTransactionType.REACTIVATION.value,
            description="Service reactivated",
            amount=Decimal("0"),
        ))
        transactions.append(txn)

        if reconnection_fee > 0:
            fee_txn = self.create_transaction(ServiceTransactionCreateData(
                subscription_id=subscription_id,
                party_id=party_id,
                transaction_type=ServiceTransactionType.RECONNECTION_FEE.value,
                description="Reconnection fee",
                amount=reconnection_fee,
            ))
            transactions.append(fee_txn)

        return transactions

    def record_cancellation(
        self,
        subscription_id: int,
        party_id: int,
        reason: str,
        early_termination_fee: Decimal = Decimal("0"),
        proration_credit: Decimal = Decimal("0"),
    ) -> List[Dict[str, Any]]:
        """Record cancellation transaction(s)."""
        transactions = []

        txn = self.create_transaction(ServiceTransactionCreateData(
            subscription_id=subscription_id,
            party_id=party_id,
            transaction_type=ServiceTransactionType.CANCELLATION.value,
            description="Service cancelled",
            amount=Decimal("0"),
            reason=reason,
        ))
        transactions.append(txn)

        if early_termination_fee > 0:
            fee_txn = self.create_transaction(ServiceTransactionCreateData(
                subscription_id=subscription_id,
                party_id=party_id,
                transaction_type=ServiceTransactionType.EARLY_TERMINATION_FEE.value,
                description="Early termination fee",
                amount=early_termination_fee,
            ))
            transactions.append(fee_txn)

        if proration_credit > 0:
            credit_txn = self.create_transaction(ServiceTransactionCreateData(
                subscription_id=subscription_id,
                party_id=party_id,
                transaction_type=ServiceTransactionType.PRORATION_CREDIT.value,
                description="Unused service credit",
                amount=-proration_credit,  # Negative = credit
            ))
            transactions.append(credit_txn)

        return transactions

    def record_plan_change(
        self,
        subscription_id: int,
        party_id: int,
        old_plan: str,
        new_plan: str,
        old_price: Decimal,
        new_price: Decimal,
        is_upgrade: bool,
        proration_amount: Optional[Decimal] = None,
        change_fee: Decimal = Decimal("0"),
    ) -> List[Dict[str, Any]]:
        """Record plan change (upgrade/downgrade) transactions."""
        transactions = []

        txn_type = ServiceTransactionType.UPGRADE if is_upgrade else ServiceTransactionType.DOWNGRADE
        txn = self.create_transaction(ServiceTransactionCreateData(
            subscription_id=subscription_id,
            party_id=party_id,
            transaction_type=txn_type.value,
            description=f"Plan changed from {old_plan} to {new_plan}",
            amount=Decimal("0"),
            old_value=f"{old_plan} ({old_price})",
            new_value=f"{new_plan} ({new_price})",
            metadata={
                "old_plan": old_plan,
                "new_plan": new_plan,
                "old_price": float(old_price),
                "new_price": float(new_price),
            },
        ))
        transactions.append(txn)

        # Proration
        if proration_amount and proration_amount != 0:
            if proration_amount > 0:
                # Charge for upgrade proration
                prorate_txn = self.create_transaction(ServiceTransactionCreateData(
                    subscription_id=subscription_id,
                    party_id=party_id,
                    transaction_type=ServiceTransactionType.PRORATION_CHARGE.value,
                    description=f"Proration charge for upgrade to {new_plan}",
                    amount=proration_amount,
                ))
            else:
                # Credit for downgrade proration
                prorate_txn = self.create_transaction(ServiceTransactionCreateData(
                    subscription_id=subscription_id,
                    party_id=party_id,
                    transaction_type=ServiceTransactionType.PRORATION_CREDIT.value,
                    description=f"Proration credit for downgrade from {old_plan}",
                    amount=proration_amount,  # Already negative
                ))
            transactions.append(prorate_txn)

        # Change fee
        if change_fee > 0:
            fee_type = "Upgrade" if is_upgrade else "Downgrade"
            fee_txn = self.create_transaction(ServiceTransactionCreateData(
                subscription_id=subscription_id,
                party_id=party_id,
                transaction_type=ServiceTransactionType.OTHER_FEE.value,
                description=f"{fee_type} processing fee",
                amount=change_fee,
            ))
            transactions.append(fee_txn)

        return transactions

    def record_subscription_charge(
        self,
        subscription_id: int,
        party_id: int,
        amount: Decimal,
        description: str,
        invoice_id: Optional[int] = None,
        billing_period_start: Optional[date] = None,
        billing_period_end: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Record a subscription charge."""
        return self.create_transaction(ServiceTransactionCreateData(
            subscription_id=subscription_id,
            party_id=party_id,
            transaction_type=ServiceTransactionType.SUBSCRIPTION_CHARGE.value,
            description=description,
            amount=amount,
            invoice_id=invoice_id,
            metadata={
                "billing_period_start": str(billing_period_start) if billing_period_start else None,
                "billing_period_end": str(billing_period_end) if billing_period_end else None,
            },
        ))

    def record_usage_charge(
        self,
        subscription_id: int,
        party_id: int,
        amount: Decimal,
        description: str,
        usage_gb: Optional[float] = None,
        invoice_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Record a usage-based charge."""
        return self.create_transaction(ServiceTransactionCreateData(
            subscription_id=subscription_id,
            party_id=party_id,
            transaction_type=ServiceTransactionType.USAGE_CHARGE.value,
            description=description,
            amount=amount,
            invoice_id=invoice_id,
            metadata={"usage_gb": usage_gb} if usage_gb else {},
        ))

    def record_credit(
        self,
        subscription_id: int,
        party_id: int,
        amount: Decimal,
        description: str,
        reason: str,
        credit_note_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Record a credit (negative amount)."""
        return self.create_transaction(ServiceTransactionCreateData(
            subscription_id=subscription_id,
            party_id=party_id,
            transaction_type=ServiceTransactionType.CREDIT.value,
            description=description,
            amount=-abs(amount),  # Ensure negative
            reason=reason,
            credit_note_id=credit_note_id,
        ))

    def record_refund(
        self,
        subscription_id: int,
        party_id: int,
        amount: Decimal,
        description: str,
        reason: str,
        payment_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Record a refund."""
        return self.create_transaction(ServiceTransactionCreateData(
            subscription_id=subscription_id,
            party_id=party_id,
            transaction_type=ServiceTransactionType.REFUND.value,
            description=description,
            amount=-abs(amount),  # Negative
            reason=reason,
            payment_id=payment_id,
        ))

    # -------------------------------------------------------------------------
    # Reports and Summaries
    # -------------------------------------------------------------------------

    def get_summary(
        self,
        period_start: date,
        period_end: date,
        currency: str = "NGN",
    ) -> ServiceTransactionSummary:
        """Get transaction summary for a period."""
        from app.models.service_transaction import ServiceTransaction as ServiceTransactionModel

        base_query = self.db.query(ServiceTransactionModel).filter(
            ServiceTransactionModel.effective_date >= period_start,
            ServiceTransactionModel.effective_date <= period_end,
            ServiceTransactionModel.currency == currency,
            ServiceTransactionModel.status == ServiceTransactionStatus.COMPLETED.value,
        )

        # Counts
        total = base_query.count()
        activations = base_query.filter(
            ServiceTransactionModel.transaction_type == ServiceTransactionType.ACTIVATION.value
        ).count()
        cancellations = base_query.filter(
            ServiceTransactionModel.transaction_type == ServiceTransactionType.CANCELLATION.value
        ).count()
        upgrades = base_query.filter(
            ServiceTransactionModel.transaction_type == ServiceTransactionType.UPGRADE.value
        ).count()
        downgrades = base_query.filter(
            ServiceTransactionModel.transaction_type == ServiceTransactionType.DOWNGRADE.value
        ).count()

        # Amounts
        total_charges = self.db.query(func.sum(ServiceTransactionModel.amount)).filter(
            ServiceTransactionModel.effective_date >= period_start,
            ServiceTransactionModel.effective_date <= period_end,
            ServiceTransactionModel.currency == currency,
            ServiceTransactionModel.status == ServiceTransactionStatus.COMPLETED.value,
            ServiceTransactionModel.amount > 0,
        ).scalar() or Decimal("0")

        total_credits = self.db.query(func.sum(ServiceTransactionModel.amount)).filter(
            ServiceTransactionModel.effective_date >= period_start,
            ServiceTransactionModel.effective_date <= period_end,
            ServiceTransactionModel.currency == currency,
            ServiceTransactionModel.status == ServiceTransactionStatus.COMPLETED.value,
            ServiceTransactionModel.amount < 0,
        ).scalar() or Decimal("0")

        # Breakdown by type
        charge_types = [
            ServiceTransactionType.SUBSCRIPTION_CHARGE.value,
        ]
        subscription_charges = self.db.query(func.sum(ServiceTransactionModel.amount)).filter(
            ServiceTransactionModel.effective_date >= period_start,
            ServiceTransactionModel.effective_date <= period_end,
            ServiceTransactionModel.currency == currency,
            ServiceTransactionModel.transaction_type.in_(charge_types),
        ).scalar() or Decimal("0")

        usage_charges = self.db.query(func.sum(ServiceTransactionModel.amount)).filter(
            ServiceTransactionModel.effective_date >= period_start,
            ServiceTransactionModel.effective_date <= period_end,
            ServiceTransactionModel.currency == currency,
            ServiceTransactionModel.transaction_type == ServiceTransactionType.USAGE_CHARGE.value,
        ).scalar() or Decimal("0")

        fee_types = [
            ServiceTransactionType.INSTALLATION_FEE.value,
            ServiceTransactionType.ACTIVATION_FEE.value,
            ServiceTransactionType.RECONNECTION_FEE.value,
            ServiceTransactionType.EARLY_TERMINATION_FEE.value,
            ServiceTransactionType.OTHER_FEE.value,
        ]
        fee_charges = self.db.query(func.sum(ServiceTransactionModel.amount)).filter(
            ServiceTransactionModel.effective_date >= period_start,
            ServiceTransactionModel.effective_date <= period_end,
            ServiceTransactionModel.currency == currency,
            ServiceTransactionModel.transaction_type.in_(fee_types),
        ).scalar() or Decimal("0")

        credits_issued = self.db.query(func.sum(ServiceTransactionModel.amount)).filter(
            ServiceTransactionModel.effective_date >= period_start,
            ServiceTransactionModel.effective_date <= period_end,
            ServiceTransactionModel.currency == currency,
            ServiceTransactionModel.transaction_type == ServiceTransactionType.CREDIT.value,
        ).scalar() or Decimal("0")

        refunds_issued = self.db.query(func.sum(ServiceTransactionModel.amount)).filter(
            ServiceTransactionModel.effective_date >= period_start,
            ServiceTransactionModel.effective_date <= period_end,
            ServiceTransactionModel.currency == currency,
            ServiceTransactionModel.transaction_type == ServiceTransactionType.REFUND.value,
        ).scalar() or Decimal("0")

        # Count by type
        by_type_rows = self.db.query(
            ServiceTransactionModel.transaction_type,
            func.count(ServiceTransactionModel.id)
        ).filter(
            ServiceTransactionModel.effective_date >= period_start,
            ServiceTransactionModel.effective_date <= period_end,
        ).group_by(ServiceTransactionModel.transaction_type).all()

        by_type = {row[0]: row[1] for row in by_type_rows}

        return ServiceTransactionSummary(
            period_start=period_start,
            period_end=period_end,
            currency=currency,
            total_transactions=total,
            activations=activations,
            cancellations=cancellations,
            upgrades=upgrades,
            downgrades=downgrades,
            total_charges=total_charges,
            total_credits=abs(total_credits),
            net_amount=total_charges + total_credits,
            subscription_charges=subscription_charges,
            usage_charges=usage_charges,
            fee_charges=fee_charges,
            credits_issued=abs(credits_issued),
            refunds_issued=abs(refunds_issued),
            by_type=by_type,
        )

    def get_party_history(self, party_id: int) -> PartyTransactionHistory:
        """Get transaction history for a party."""
        from app.models.service_transaction import ServiceTransaction as ServiceTransactionModel
        from app.models.party import Party

        party = self.db.query(Party).filter(Party.id == party_id).first()
        if not party:
            raise NotFoundError(f"Party {party_id} not found")

        base_query = self.db.query(ServiceTransactionModel).filter(
            ServiceTransactionModel.party_id == party_id,
            ServiceTransactionModel.status == ServiceTransactionStatus.COMPLETED.value,
        )

        # Counts
        total_transactions = base_query.count()

        # Amounts
        total_charges = self.db.query(func.sum(ServiceTransactionModel.amount)).filter(
            ServiceTransactionModel.party_id == party_id,
            ServiceTransactionModel.status == ServiceTransactionStatus.COMPLETED.value,
            ServiceTransactionModel.amount > 0,
        ).scalar() or Decimal("0")

        total_credits = self.db.query(func.sum(ServiceTransactionModel.amount)).filter(
            ServiceTransactionModel.party_id == party_id,
            ServiceTransactionModel.status == ServiceTransactionStatus.COMPLETED.value,
            ServiceTransactionModel.transaction_type == ServiceTransactionType.CREDIT.value,
        ).scalar() or Decimal("0")

        total_refunds = self.db.query(func.sum(ServiceTransactionModel.amount)).filter(
            ServiceTransactionModel.party_id == party_id,
            ServiceTransactionModel.status == ServiceTransactionStatus.COMPLETED.value,
            ServiceTransactionModel.transaction_type == ServiceTransactionType.REFUND.value,
        ).scalar() or Decimal("0")

        # Current month
        today = date.today()
        month_start = today.replace(day=1)

        current_month_charges = self.db.query(func.sum(ServiceTransactionModel.amount)).filter(
            ServiceTransactionModel.party_id == party_id,
            ServiceTransactionModel.effective_date >= month_start,
            ServiceTransactionModel.status == ServiceTransactionStatus.COMPLETED.value,
            ServiceTransactionModel.amount > 0,
        ).scalar() or Decimal("0")

        current_month_credits = self.db.query(func.sum(ServiceTransactionModel.amount)).filter(
            ServiceTransactionModel.party_id == party_id,
            ServiceTransactionModel.effective_date >= month_start,
            ServiceTransactionModel.status == ServiceTransactionStatus.COMPLETED.value,
            ServiceTransactionModel.amount < 0,
        ).scalar() or Decimal("0")

        # Subscription stats
        from app.models.subscription import SubscriptionStatus

        active_subs = self.db.query(Subscription).filter(
            Subscription.party_id == party_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        ).count()

        total_subs = self.db.query(Subscription).filter(
            Subscription.party_id == party_id,
        ).count()

        upgrades = base_query.filter(
            ServiceTransactionModel.transaction_type == ServiceTransactionType.UPGRADE.value
        ).count()

        downgrades = base_query.filter(
            ServiceTransactionModel.transaction_type == ServiceTransactionType.DOWNGRADE.value
        ).count()

        # Recent transactions
        recent = base_query.order_by(
            ServiceTransactionModel.created_at.desc()
        ).limit(10).all()

        return PartyTransactionHistory(
            party_id=party_id,
            party_name=party.display_name or f"Party #{party_id}",
            total_transactions=total_transactions,
            total_charges=total_charges,
            total_credits=abs(total_credits),
            total_refunds=abs(total_refunds),
            net_lifetime_value=total_charges + total_credits + total_refunds,
            current_month_charges=current_month_charges,
            current_month_credits=abs(current_month_credits),
            active_subscriptions=active_subs,
            total_subscriptions=total_subs,
            upgrades_count=upgrades,
            downgrades_count=downgrades,
            recent_transactions=[self._to_dict(t) for t in recent],
        )

    def get_subscription_transactions(
        self,
        subscription_id: int,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get all transactions for a subscription."""
        from app.models.service_transaction import ServiceTransaction as ServiceTransactionModel

        txns = self.db.query(ServiceTransactionModel).filter(
            ServiceTransactionModel.subscription_id == subscription_id
        ).order_by(
            ServiceTransactionModel.created_at.desc()
        ).limit(limit).all()

        return [self._to_dict(t) for t in txns]

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _to_dict(self, txn) -> Dict[str, Any]:
        """Convert transaction model to dict."""
        return {
            "id": txn.id,
            "subscription_id": txn.subscription_id,
            "party_id": txn.party_id,
            "transaction_type": txn.transaction_type,
            "status": txn.status,
            "description": txn.description,
            "amount": float(txn.amount),
            "currency": txn.currency,
            "invoice_id": txn.invoice_id,
            "payment_id": txn.payment_id,
            "credit_note_id": txn.credit_note_id,
            "old_value": txn.old_value,
            "new_value": txn.new_value,
            "reason": txn.reason,
            "metadata": txn.metadata_json or {},
            "effective_date": str(txn.effective_date) if txn.effective_date else None,
            "created_at": txn.created_at.isoformat() if txn.created_at else None,
            "created_by_id": txn.created_by_id,
        }
