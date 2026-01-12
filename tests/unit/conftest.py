"""
Shared fixtures for unit tests.

Provides mock database sessions, service stubs, and test data factories
for isolated unit testing of service layer components.
"""
from __future__ import annotations

from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from typing import Optional, List, Any, Dict
from unittest.mock import MagicMock, patch
from contextlib import contextmanager
from dataclasses import dataclass, field
import enum

import pytest


# =============================================================================
# MOCK ENUMS (to avoid importing real models)
# =============================================================================


class MockInvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    CANCELLED = "cancelled"


class MockPurchaseInvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    UNPAID = "unpaid"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    CANCELLED = "cancelled"


class MockTicketStatus(str, enum.Enum):
    OPEN = "open"
    REPLIED = "replied"
    ON_HOLD = "on_hold"
    RESOLVED = "resolved"
    CLOSED = "closed"


class MockTicketPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class MockSLATargetType(str, enum.Enum):
    FIRST_RESPONSE = "first_response"
    RESOLUTION = "resolution"


class MockBusinessHourType(str, enum.Enum):
    TWENTY_FOUR_SEVEN = "24x7"
    BUSINESS_HOURS = "business_hours"


class MockRoutingStrategy(str, enum.Enum):
    MANUAL = "manual"
    ROUND_ROBIN = "round_robin"
    LEAST_BUSY = "least_busy"
    SKILL_BASED = "skill_based"
    LOAD_BALANCED = "load_balanced"


# =============================================================================
# MOCK DATA CLASSES
# =============================================================================


@dataclass
class MockInvoice:
    """Mock Invoice for testing."""
    id: int
    invoice_number: str = "INV-001"
    customer_id: int = 1
    customer_account_id: Optional[int] = None
    contact_id: Optional[int] = None
    total_amount: Decimal = Decimal("1000.00")
    amount: Decimal = Decimal("900.00")  # Net amount
    tax_amount: Decimal = Decimal("100.00")
    amount_paid: Decimal = Decimal("0.00")
    balance: Optional[Decimal] = None
    status: MockInvoiceStatus = MockInvoiceStatus.PENDING
    invoice_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    due_date: Optional[datetime] = None
    currency: str = "NGN"
    company: Optional[str] = "Default Company"
    conversion_rate: Decimal = Decimal("1")
    docstatus: int = 0
    journal_entry_id: Optional[int] = None
    workflow_status: Optional[str] = None

    def __post_init__(self):
        if self.balance is None:
            self.balance = self.total_amount - self.amount_paid
        if self.customer_account_id is None:
            self.customer_account_id = self.customer_id


@dataclass
class MockPurchaseInvoice:
    """Mock Purchase Invoice (Bill) for testing."""
    id: int
    erpnext_id: Optional[str] = None
    bill_number: str = "BILL-001"
    supplier: str = "1"
    supplier_name: str = "Test Supplier"
    grand_total: Decimal = Decimal("1000.00")
    tax_amount: Decimal = Decimal("0.00")
    paid_amount: Decimal = Decimal("0.00")
    outstanding_amount: Optional[Decimal] = None
    status: MockPurchaseInvoiceStatus = MockPurchaseInvoiceStatus.UNPAID
    posting_date: date | datetime = field(default_factory=date.today)
    due_date: Optional[date] = None
    currency: str = "NGN"
    company: Optional[str] = "Default Company"
    conversion_rate: Decimal = Decimal("1")
    docstatus: int = 0
    journal_entry_id: Optional[int] = None
    workflow_status: Optional[str] = None

    def __post_init__(self):
        if self.outstanding_amount is None:
            self.outstanding_amount = self.grand_total - self.paid_amount
        if isinstance(self.posting_date, date) and not isinstance(self.posting_date, datetime):
            self.posting_date = datetime.combine(
                self.posting_date,
                datetime.min.time(),
                tzinfo=timezone.utc,
            )


@dataclass
class MockPayment:
    """Mock Payment for testing."""
    id: int
    customer_id: int = 1
    customer_account_id: Optional[int] = None
    receipt_number: str = "REC-001"
    amount: Decimal = Decimal("500.00")
    total_allocated: Decimal = Decimal("0.00")
    unallocated_amount: Optional[Decimal] = None
    payment_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    currency: str = "NGN"
    conversion_rate: Decimal = Decimal("1")
    invoice: Optional[MockInvoice] = None
    docstatus: int = 0
    journal_entry_id: Optional[int] = None
    workflow_status: Optional[str] = None

    def __post_init__(self):
        if self.unallocated_amount is None:
            self.unallocated_amount = self.amount - self.total_allocated
        if self.customer_account_id is None:
            self.customer_account_id = self.customer_id


@dataclass
class MockSupplierPayment:
    """Mock Supplier Payment for testing."""
    id: int
    supplier_id: int = 1
    payment_number: str = "PAY-001"
    paid_amount: Decimal = Decimal("500.00")
    total_allocated: Decimal = Decimal("0.00")
    unallocated_amount: Optional[Decimal] = None
    posting_date: date | datetime = field(default_factory=date.today)
    currency: str = "NGN"
    conversion_rate: Decimal = Decimal("1")
    company: Optional[str] = "Default Company"
    docstatus: int = 0
    journal_entry_id: Optional[int] = None
    workflow_status: Optional[str] = None

    def __post_init__(self):
        if self.unallocated_amount is None:
            self.unallocated_amount = self.paid_amount - self.total_allocated
        if isinstance(self.posting_date, date) and not isinstance(self.posting_date, datetime):
            self.posting_date = datetime.combine(
                self.posting_date,
                datetime.min.time(),
                tzinfo=timezone.utc,
            )


@dataclass
class MockPaymentAllocation:
    """Mock Payment Allocation for testing."""
    id: int
    payment_id: Optional[int] = None
    supplier_payment_id: Optional[int] = None
    allocation_type: str = "invoice"
    document_id: int = 1
    allocated_amount: Decimal = Decimal("500.00")
    discount_amount: Decimal = Decimal("0.00")
    write_off_amount: Decimal = Decimal("0.00")
    conversion_rate: Decimal = Decimal("1")
    base_allocated_amount: Decimal = Decimal("500.00")
    base_discount_amount: Decimal = Decimal("0.00")
    base_write_off_amount: Decimal = Decimal("0.00")
    exchange_gain_loss: Decimal = Decimal("0.00")
    discount_type: Optional[str] = None
    discount_account: Optional[str] = None
    write_off_account: Optional[str] = None
    write_off_reason: Optional[str] = None
    created_by_id: Optional[int] = None


@dataclass
class MockTicket:
    """Mock Ticket for testing."""
    id: int
    subject: str = "Test Ticket"
    status: MockTicketStatus = MockTicketStatus.OPEN
    priority: MockTicketPriority = MockTicketPriority.MEDIUM
    ticket_type: Optional[str] = None
    issue_type: Optional[str] = None
    region: Optional[str] = None
    assigned_to: Optional[str] = None
    resolution_team: Optional[str] = None
    opening_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    response_by: Optional[datetime] = None
    resolution_by: Optional[datetime] = None
    first_responded_on: Optional[datetime] = None
    resolution_date: Optional[datetime] = None


@dataclass
class MockSLAPolicy:
    """Mock SLA Policy for testing."""
    id: int
    name: str = "Default SLA"
    is_active: bool = True
    is_default: bool = False
    priority: int = 100
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    targets: List["MockSLATarget"] = field(default_factory=list)
    calendar: Optional["MockBusinessCalendar"] = None


@dataclass
class MockSLATarget:
    """Mock SLA Target for testing."""
    id: int
    policy_id: int
    target_type: str = "first_response"
    priority: Optional[str] = None
    target_hours: Decimal = Decimal("4")


@dataclass
class MockBusinessCalendar:
    """Mock Business Calendar for testing."""
    id: int
    name: str = "Default Calendar"
    calendar_type: str = "24x7"
    schedule: Optional[Dict[str, Any]] = None


@dataclass
class MockRoutingRule:
    """Mock Routing Rule for testing."""
    id: int
    name: str = "Default Rule"
    is_active: bool = True
    priority: int = 100
    strategy: str = "round_robin"
    conditions: Optional[List[Dict[str, Any]]] = None
    team_id: Optional[int] = None
    fallback_team_id: Optional[int] = None


@dataclass
class MockAgent:
    """Mock Agent for testing."""
    id: int
    email: str = "agent@example.com"
    display_name: str = "Test Agent"
    name: Optional[str] = None
    primary_email: Optional[str] = None
    is_active: bool = True
    capacity: int = 10
    routing_weight: int = 1
    skills: Dict[str, Any] = field(default_factory=dict)
    domains: Dict[str, Any] = field(default_factory=dict)
    agent_capacity: Optional[int] = None
    agent_routing_weight: Optional[int] = None
    agent_skills: Optional[Dict[str, Any]] = None
    agent_domains: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.name is None:
            self.name = self.display_name
        if self.primary_email is None:
            self.primary_email = self.email
        if self.agent_capacity is None:
            self.agent_capacity = self.capacity
        if self.agent_routing_weight is None:
            self.agent_routing_weight = self.routing_weight
        if self.agent_skills is None or (not self.agent_skills and self.skills):
            self.agent_skills = self.skills
        if self.agent_domains is None or (not self.agent_domains and self.domains):
            self.agent_domains = self.domains


@dataclass
class MockTeam:
    """Mock Team for testing."""
    id: int
    name: str = "Support Team"


@dataclass
class MockTeamMember:
    """Mock Team Member for testing."""
    id: int
    team_id: int
    agent_id: int
    is_active: bool = True


@dataclass
class MockContact:
    """Mock Contact for testing."""
    id: int
    display_name: str = "Test Contact"
    email: str = "contact@example.com"


# =============================================================================
# MOCK DATABASE SESSION
# =============================================================================


class MockQuery:
    """Mock SQLAlchemy query object."""

    def __init__(self, results: List[Any] = None):
        self._results = results or []
        self._filters = []

    def filter(self, *args, **kwargs):
        return self

    def filter_by(self, **kwargs):
        return self

    def options(self, *args, **kwargs):
        return self

    def order_by(self, *args):
        return self

    def limit(self, n: int):
        self._results = self._results[:n]
        return self

    def offset(self, n: int):
        self._results = self._results[n:]
        return self

    def with_for_update(self):
        return self

    def first(self):
        return self._results[0] if self._results else None

    def all(self):
        return self._results

    def one(self):
        if len(self._results) != 1:
            raise Exception("Expected exactly one result")
        return self._results[0]

    def one_or_none(self):
        if len(self._results) > 1:
            raise Exception("Expected at most one result")
        return self._results[0] if self._results else None

    def scalar(self):
        return len(self._results)

    def count(self):
        return len(self._results)


class MockSession:
    """Mock SQLAlchemy session for unit testing."""

    def __init__(self):
        self._data: Dict[type, List[Any]] = {}
        self._added: List[Any] = []
        self._deleted: List[Any] = []
        self._committed = False
        self._in_transaction = False

    def query(self, model_class):
        """Return mock query with registered data."""
        data = self._data.get(model_class, [])
        return MockQuery(data)

    def add(self, obj):
        """Track added objects."""
        self._added.append(obj)

    def delete(self, obj):
        """Track deleted objects."""
        self._deleted.append(obj)

    def commit(self):
        """Mark as committed."""
        self._committed = True

    def flush(self):
        """No-op for mock."""
        pass

    def rollback(self):
        """Reset transaction state."""
        self._added.clear()
        self._deleted.clear()
        self._committed = False

    def begin_nested(self):
        """Return context manager for nested transaction."""
        return _MockNestedTransaction(self)

    def begin(self):
        """Return context manager for transaction."""
        self._in_transaction = True
        return _MockTransaction(self)

    def in_transaction(self):
        """Check if in transaction."""
        return self._in_transaction

    def register_data(self, model_class, data: List[Any]):
        """Register mock data for a model class."""
        self._data[model_class] = data

    def get_added(self):
        """Get all added objects."""
        return self._added

    def get_deleted(self):
        """Get all deleted objects."""
        return self._deleted


class _MockTransaction:
    """Mock transaction context manager."""

    def __init__(self, session: MockSession):
        self.session = session

    def __enter__(self):
        self.session._in_transaction = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session._in_transaction = False
        if exc_type is None:
            self.session.commit()
        else:
            self.session.rollback()
        return False


class _MockNestedTransaction:
    """Mock nested transaction context manager."""

    def __init__(self, session: MockSession):
        self.session = session

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.session.rollback()
        return False


# =============================================================================
# PYTEST FIXTURES
# =============================================================================


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MockSession()


@pytest.fixture
def sample_invoice():
    """Create a sample invoice."""
    return MockInvoice(
        id=1,
        invoice_number="INV-001",
        customer_id=1,
        total_amount=Decimal("1000.00"),
        amount=Decimal("900.00"),
        tax_amount=Decimal("100.00"),
        amount_paid=Decimal("0.00"),
        status=MockInvoiceStatus.PENDING,
    )


@pytest.fixture
def sample_invoice_partially_paid():
    """Create a partially paid invoice."""
    return MockInvoice(
        id=2,
        invoice_number="INV-002",
        customer_id=1,
        total_amount=Decimal("1000.00"),
        amount=Decimal("900.00"),
        tax_amount=Decimal("100.00"),
        amount_paid=Decimal("500.00"),
        balance=Decimal("500.00"),
        status=MockInvoiceStatus.PARTIALLY_PAID,
    )


@pytest.fixture
def sample_payment():
    """Create a sample payment."""
    return MockPayment(
        id=1,
        customer_id=1,
        receipt_number="REC-001",
        amount=Decimal("500.00"),
        total_allocated=Decimal("0.00"),
    )


@pytest.fixture
def sample_payment_full():
    """Create a payment for full invoice amount."""
    return MockPayment(
        id=2,
        customer_id=1,
        receipt_number="REC-002",
        amount=Decimal("1000.00"),
        total_allocated=Decimal("0.00"),
    )


@pytest.fixture
def sample_bill():
    """Create a sample bill (purchase invoice)."""
    return MockPurchaseInvoice(
        id=1,
        bill_number="BILL-001",
        supplier="1",
        supplier_name="Test Supplier",
        grand_total=Decimal("500.00"),
        paid_amount=Decimal("0.00"),
        status=MockPurchaseInvoiceStatus.UNPAID,
    )


@pytest.fixture
def sample_supplier_payment():
    """Create a sample supplier payment."""
    return MockSupplierPayment(
        id=1,
        supplier_id=1,
        payment_number="PAY-001",
        paid_amount=Decimal("500.00"),
        total_allocated=Decimal("0.00"),
    )


@pytest.fixture
def sample_ticket():
    """Create a sample ticket."""
    return MockTicket(
        id=1,
        subject="Test Support Ticket",
        status=MockTicketStatus.OPEN,
        priority=MockTicketPriority.MEDIUM,
    )


@pytest.fixture
def sample_urgent_ticket():
    """Create an urgent ticket."""
    return MockTicket(
        id=2,
        subject="Urgent Issue",
        status=MockTicketStatus.OPEN,
        priority=MockTicketPriority.URGENT,
        ticket_type="technical",
        issue_type="outage",
    )


@pytest.fixture
def sample_sla_policy():
    """Create a sample SLA policy."""
    policy = MockSLAPolicy(
        id=1,
        name="Standard SLA",
        is_active=True,
        is_default=False,
        priority=100,
        conditions=[
            {"field": "priority", "operator": "equals", "value": "medium"}
        ],
    )
    policy.targets = [
        MockSLATarget(id=1, policy_id=1, target_type="first_response", target_hours=Decimal("4")),
        MockSLATarget(id=2, policy_id=1, target_type="resolution", target_hours=Decimal("24")),
    ]
    return policy


@pytest.fixture
def sample_default_sla_policy():
    """Create a default SLA policy."""
    policy = MockSLAPolicy(
        id=2,
        name="Default SLA",
        is_active=True,
        is_default=True,
        priority=999,
        conditions=[],
    )
    policy.targets = [
        MockSLATarget(id=3, policy_id=2, target_type="first_response", target_hours=Decimal("8")),
        MockSLATarget(id=4, policy_id=2, target_type="resolution", target_hours=Decimal("48")),
    ]
    return policy


@pytest.fixture
def sample_business_calendar():
    """Create a sample business calendar with business hours."""
    return MockBusinessCalendar(
        id=1,
        name="Business Hours",
        calendar_type="business_hours",
        schedule={
            "mon": {"start": "09:00", "end": "17:00"},
            "tue": {"start": "09:00", "end": "17:00"},
            "wed": {"start": "09:00", "end": "17:00"},
            "thu": {"start": "09:00", "end": "17:00"},
            "fri": {"start": "09:00", "end": "17:00"},
        },
    )


@pytest.fixture
def sample_24x7_calendar():
    """Create a 24x7 calendar."""
    return MockBusinessCalendar(
        id=2,
        name="24x7",
        calendar_type="24x7",
        schedule=None,
    )


@pytest.fixture
def sample_routing_rule():
    """Create a sample routing rule."""
    return MockRoutingRule(
        id=1,
        name="Support Routing",
        is_active=True,
        priority=100,
        strategy="round_robin",
        conditions=[
            {"field": "priority", "operator": "equals", "value": "medium"}
        ],
        team_id=1,
    )


@pytest.fixture
def sample_agents():
    """Create a list of sample agents."""
    return [
        MockAgent(id=1, email="agent1@example.com", display_name="Agent 1", capacity=10),
        MockAgent(id=2, email="agent2@example.com", display_name="Agent 2", capacity=10),
        MockAgent(id=3, email="agent3@example.com", display_name="Agent 3", capacity=10),
    ]


@pytest.fixture
def sample_team():
    """Create a sample team."""
    return MockTeam(id=1, name="Support Team")


@pytest.fixture
def sample_team_members(sample_agents):
    """Create team members for sample agents."""
    return [
        MockTeamMember(id=i + 1, team_id=1, agent_id=agent.id, is_active=True)
        for i, agent in enumerate(sample_agents)
    ]
