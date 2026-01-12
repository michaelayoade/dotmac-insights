"""
Integration Test Configuration and Fixtures.

Provides fixtures for API integration testing with real database operations
but using transaction rollback for isolation.
"""
import os
import pytest
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional, Dict, Any, List

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

# Get database URL - prefer PostgreSQL for integration tests
_DEFAULT_DB_URL = "postgresql+psycopg://dotmac:dotmac_dev_password@localhost:5432/dotmac_insights"
INTEGRATION_DATABASE_URL = (
    os.environ.get("TEST_DATABASE_URL") or
    os.environ.get("DATABASE_URL") or
    _DEFAULT_DB_URL
)

# Set for app import
if "TEST_DATABASE_URL" not in os.environ:
    os.environ["TEST_DATABASE_URL"] = INTEGRATION_DATABASE_URL

# Handle SQLite JSONB compatibility
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

from app.main import app as fastapi_app
from app.database import Base, get_db
from app.auth import get_current_principal, Principal


# =============================================================================
# DATABASE FIXTURES
# =============================================================================


@pytest.fixture(scope="session")
def integration_engine():
    """Create database engine for integration tests."""
    db_url = INTEGRATION_DATABASE_URL

    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}

    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        connect_args=connect_args,
    )

    # Validate connectivity
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        pytest.fail(f"Integration database connection failed: {e}")

    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def integration_db(integration_engine):
    """
    Database session with transaction rollback for test isolation.
    """
    connection = integration_engine.connect()
    transaction = connection.begin()

    TestSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=connection,
    )
    db = TestSessionLocal()

    yield db

    db.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def integration_client(integration_db):
    """FastAPI TestClient with database dependency override."""
    def override_get_db():
        try:
            yield integration_db
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db

    with TestClient(fastapi_app) as client:
        yield client

    fastapi_app.dependency_overrides.pop(get_db, None)


# =============================================================================
# AUTHENTICATION FIXTURES
# =============================================================================


def create_integration_principal(
    scopes: set[str] = None,
    is_superuser: bool = False,
    user_id: int = 1,
) -> Principal:
    """Create a Principal for integration testing."""
    return Principal(
        type="user",
        id=user_id,
        external_id=f"integration_user_{user_id}",
        email="integration@example.com",
        name="Integration Test User",
        is_superuser=is_superuser,
        scopes=scopes or {"*"},
    )


@pytest.fixture(scope="function")
def auth_client(integration_db, integration_client):
    """
    Factory for authenticated integration client.

    Usage:
        def test_api(auth_client):
            client = auth_client(["crm:read", "crm:write"])
            resp = client.get("/api/v1/crm/parties")
    """
    def _make_client(scopes: list[str], is_superuser: bool = False, user_id: int = 1):
        mock_principal = create_integration_principal(
            scopes=set(scopes),
            is_superuser=is_superuser,
            user_id=user_id,
        )

        async def override_principal():
            return mock_principal

        fastapi_app.dependency_overrides[get_current_principal] = override_principal
        return integration_client

    yield _make_client
    fastapi_app.dependency_overrides.pop(get_current_principal, None)


@pytest.fixture(scope="function")
def superuser_client(integration_db, integration_client):
    """Superuser authenticated client."""
    mock_principal = create_integration_principal(
        scopes={"*"},
        is_superuser=True,
    )

    async def override_principal():
        return mock_principal

    fastapi_app.dependency_overrides[get_current_principal] = override_principal

    yield integration_client

    fastapi_app.dependency_overrides.pop(get_current_principal, None)


@pytest.fixture(scope="function")
def unauthenticated_client(integration_db, integration_client):
    """Client without authentication for 401 tests."""
    # Remove any auth override
    fastapi_app.dependency_overrides.pop(get_current_principal, None)
    return integration_client


@pytest.fixture(scope="function")
def test_client(integration_db, integration_client):
    """Unauthenticated test client (alias for unauthenticated_client)."""
    # Remove any auth override to test without auth
    fastapi_app.dependency_overrides.pop(get_current_principal, None)
    return integration_client


@pytest.fixture(scope="function")
def readonly_client(integration_db, integration_client):
    """Client with read-only permissions."""
    mock_principal = create_integration_principal(
        scopes={"crm:read", "invoices:read", "tickets:read"},
        is_superuser=False,
    )

    async def override_principal():
        return mock_principal

    fastapi_app.dependency_overrides[get_current_principal] = override_principal

    yield integration_client

    fastapi_app.dependency_overrides.pop(get_current_principal, None)


@pytest.fixture(scope="function")
def limited_scope_client(integration_db, integration_client):
    """Client with limited scopes and non-superuser."""
    mock_principal = create_integration_principal(
        scopes={"crm:read", "crm:write"},
        is_superuser=False,
        user_id=2,  # Different user ID for ownership tests
    )

    async def override_principal():
        return mock_principal

    fastapi_app.dependency_overrides[get_current_principal] = override_principal

    yield integration_client

    fastapi_app.dependency_overrides.pop(get_current_principal, None)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def assert_http_ok(response, message: str = ""):
    """Assert response is 2xx."""
    assert 200 <= response.status_code < 300, (
        f"{message}: Expected 2xx, got {response.status_code}: {response.text}"
    )


def assert_http_created(response, message: str = ""):
    """Assert response is 201 Created."""
    assert response.status_code == 201, (
        f"{message}: Expected 201, got {response.status_code}: {response.text}"
    )


def assert_http_error(response, expected_status: int, message: str = ""):
    """Assert response has expected error status."""
    assert response.status_code == expected_status, (
        f"{message}: Expected {expected_status}, got {response.status_code}: {response.text}"
    )


def assert_validation_error(response, field: str = None, message: str = ""):
    """Assert 422 validation error, optionally for specific field."""
    assert response.status_code == 422, (
        f"{message}: Expected 422, got {response.status_code}: {response.text}"
    )
    if field:
        detail = response.json().get("detail", [])
        field_errors = [e for e in detail if field in str(e.get("loc", []))]
        assert field_errors, f"{message}: No validation error for field '{field}'"


def get_json(response):
    """Get JSON from response with error handling."""
    assert response.status_code < 500, f"Server error: {response.text}"
    return response.json()


# =============================================================================
# DATA FACTORY HELPERS
# =============================================================================


class IntegrationDataFactory:
    """Factory for creating test data in integration tests."""

    def __init__(self, db: Session):
        self.db = db

    def create_contact(
        self,
        contact_name: str = "Test Contact",
        contact_type: str = "Customer",
        email: str = None,
        phone: str = None,
    ) -> Any:
        """Create a party record."""
        from app.models.party import Party

        email = email or f"contact_{datetime.now().timestamp()}@example.com"
        phone = phone or "+234 800 000 0000"
        party_type = "organization"
        if contact_type and contact_type.lower() in {"person", "individual"}:
            party_type = "person"

        party = Party(
            type=party_type,
            status="active",
            name=contact_name,
            primary_email=email,
            primary_phone=phone,
            emails=[{"address": email, "label": "primary", "is_primary": True}],
            phones=[{"number": phone, "label": "primary", "is_primary": True}],
        )
        self.db.add(party)
        self.db.commit()
        self.db.refresh(party)
        return party

    def create_customer(
        self,
        name: str = "Test Customer",
        email: str = None,
    ) -> Any:
        """Create a customer account."""
        from app.models.party import Party, CustomerAccount

        email = email or f"customer_{datetime.now().timestamp()}@example.com"
        party = Party(
            type="organization",
            status="active",
            name=name,
            primary_email=email,
            emails=[{"address": email, "label": "primary", "is_primary": True}],
        )
        self.db.add(party)
        self.db.commit()
        self.db.refresh(party)

        account = CustomerAccount(
            party_id=party.id,
            account_number=f"CA-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            status="active",
            tier="standard",
            account_type="direct",
        )
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def create_invoice(
        self,
        customer_account_id: int = None,
        total_amount: Decimal = Decimal("1000.00"),
        status: str = "unpaid",
    ) -> Any:
        """Create an invoice."""
        from app.models.invoice import Invoice, InvoiceStatus

        invoice = Invoice(
            customer_account_id=customer_account_id,
            invoice_number=f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            total_amount=total_amount,
            amount=total_amount,
            tax_amount=Decimal("0"),
            amount_paid=Decimal("0"),
            balance=total_amount,
            status=InvoiceStatus(status) if isinstance(status, str) else status,
            invoice_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc),
            currency="NGN",
        )
        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def create_payment(
        self,
        customer_account_id: int,
        amount: Decimal = Decimal("500.00"),
    ) -> Any:
        """Create a payment."""
        from app.models.payment import Payment

        payment = Payment(
            customer_account_id=customer_account_id,
            receipt_number=f"REC-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            amount=amount,
            total_allocated=Decimal("0"),
            unallocated_amount=amount,
            payment_date=datetime.now(timezone.utc),
            currency="NGN",
        )
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def create_ticket(
        self,
        subject: str = "Test Ticket",
        priority: str = "medium",
        status: str = "open",
        customer_account_id: int = None,
    ) -> Any:
        """Create a support ticket."""
        from app.models.ticket import Ticket, TicketStatus, TicketPriority

        ticket = Ticket(
            subject=subject,
            status=TicketStatus(status) if isinstance(status, str) else status,
            priority=TicketPriority(priority) if isinstance(priority, str) else priority,
            customer_account_id=customer_account_id,
            opening_date=datetime.now(timezone.utc),
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    def create_expense_claim(
        self,
        employee_id: int = 1,
        amount: Decimal = Decimal("500.00"),
        status: str = "draft",
    ) -> Any:
        """Create an expense claim."""
        from app.models.expenses import ExpenseClaim

        claim = ExpenseClaim(
            employee_id=employee_id,
            claim_number=f"EXP-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            total_amount=amount,
            status=status,
            claim_date=date.today(),
        )
        self.db.add(claim)
        self.db.commit()
        self.db.refresh(claim)
        return claim


@pytest.fixture
def data_factory(integration_db):
    """Provide data factory for creating test data."""
    return IntegrationDataFactory(integration_db)


# =============================================================================
# CLEANUP
# =============================================================================


@pytest.fixture(autouse=True)
def integration_cleanup():
    """Clean up after each integration test."""
    yield
    fastapi_app.dependency_overrides.clear()
