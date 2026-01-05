"""
E2E Test Configuration and Fixtures.

Provides fixtures for comprehensive end-to-end testing including:
- Database session management with transaction rollback
- Authenticated clients with full permissions
- Factory functions for creating test data
- State verification utilities
"""
import os
import logging

import pytest
from decimal import Decimal
from datetime import datetime, date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON

# Configure E2E test logging
logging.basicConfig(level=logging.INFO)
e2e_logger = logging.getLogger("e2e")

# Get database URL from environment - fail fast if not configured
_DEFAULT_DB_URL = "postgresql+psycopg://dotmac:dotmac_dev_password@localhost:5432/dotmac_insights"
E2E_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL") or _DEFAULT_DB_URL

# Set for app import
if "TEST_DATABASE_URL" not in os.environ:
    os.environ["TEST_DATABASE_URL"] = E2E_DATABASE_URL

# For SQLite compatibility, we need to compile JSONB as JSON
from sqlalchemy.ext.compiler import compiles

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    """Compile PostgreSQL JSONB to SQLite JSON."""
    return "JSON"

from app.main import app as fastapi_app
from app.database import Base, get_db
from app.auth import get_current_principal, Principal


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

def pytest_configure(config):
    """Register custom markers for E2E tests."""
    config.addinivalue_line("markers", "accounting: Accounting module tests")
    config.addinivalue_line("markers", "crm: CRM module tests")
    config.addinivalue_line("markers", "hr: HR module tests")
    config.addinivalue_line("markers", "projects: Projects module tests")
    config.addinivalue_line("markers", "support: Support module tests")
    config.addinivalue_line("markers", "marketing: Marketing module tests")


# =============================================================================
# DATABASE FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def e2e_engine():
    """Create test database engine."""
    db_url = E2E_DATABASE_URL

    # Force PostgreSQL for E2E tests - SQLite lacks needed features
    if db_url.startswith("sqlite"):
        db_url = _DEFAULT_DB_URL
        e2e_logger.warning(f"SQLite not supported for E2E tests, using PostgreSQL: {db_url}")

    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        connect_args={},
    )

    # Validate database connectivity at session start
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        e2e_logger.info(f"E2E database connection established: {db_url.split('@')[-1]}")
    except Exception as e:
        pytest.fail(f"E2E database connection failed: {e}")

    yield engine

    # Cleanup
    engine.dispose()


@pytest.fixture(scope="function")
def e2e_db(e2e_engine):
    """
    Provide a database session with transaction rollback.

    Each test runs in its own transaction that is rolled back after.
    """
    connection = e2e_engine.connect()

    # Validate connectivity before starting transaction
    try:
        connection.execute(text("SELECT 1"))
    except Exception as e:
        connection.close()
        pytest.fail(f"Database connection failed at test start: {e}")

    transaction = connection.begin()

    TestSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=connection,
    )
    db = TestSessionLocal()

    yield db

    # Rollback and cleanup
    db.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def e2e_client(e2e_db):
    """
    FastAPI TestClient with database dependency override.

    Uses the same database session as e2e_db for state verification.
    """
    def override_get_db():
        try:
            yield e2e_db
        finally:
            pass  # Don't close - handled by e2e_db fixture

    # Use direct override assignment for cleaner fixture chain
    fastapi_app.dependency_overrides[get_db] = override_get_db

    with TestClient(fastapi_app) as client:
        yield client

    fastapi_app.dependency_overrides.pop(get_db, None)


# =============================================================================
# AUTHENTICATION FIXTURES
# =============================================================================

def create_e2e_principal(
    scopes: set[str] = None,
    is_superuser: bool = True,
    user_id: int = 1,
    company_id: int = 1,
) -> Principal:
    """Create a Principal for E2E testing."""
    return Principal(
        type="user",
        id=user_id,
        external_id=f"e2e_user_{user_id}",
        email="e2e@example.com",
        name="E2E Test User",
        is_superuser=is_superuser,
        scopes=scopes or {"*"},
        company_id=company_id,
    )


@pytest.fixture(scope="function")
def e2e_superuser_client(e2e_db, e2e_client):
    """
    E2E client authenticated as superuser.

    Has full permissions and shares database session with e2e_db.
    """
    mock_principal = create_e2e_principal(
        scopes={"*"},
        is_superuser=True,
    )

    async def override_principal():
        return mock_principal

    # Use direct override assignment for cleaner fixture chain
    fastapi_app.dependency_overrides[get_current_principal] = override_principal

    yield e2e_client

    fastapi_app.dependency_overrides.pop(get_current_principal, None)


@pytest.fixture(scope="function")
def e2e_scoped_client(e2e_db, e2e_client):
    """
    Factory for E2E client with specific scopes.

    Usage:
        def test_limited_access(e2e_scoped_client):
            client = e2e_scoped_client(["contacts:read", "contacts:write"])
            # Test with limited permissions
    """
    def _make_client(scopes: list[str], is_superuser: bool = False):
        mock_principal = create_e2e_principal(
            scopes=set(scopes),
            is_superuser=is_superuser,
        )

        async def override_principal():
            return mock_principal

        fastapi_app.dependency_overrides[get_current_principal] = override_principal
        return e2e_client

    yield _make_client

    fastapi_app.dependency_overrides.pop(get_current_principal, None)


# =============================================================================
# SETUP DATA FIXTURES
# =============================================================================

@pytest.fixture(scope="function")
def e2e_fiscal_year(e2e_db):
    """Create or get a fiscal year for accounting tests."""
    from app.models.accounting import FiscalYear

    current_year = datetime.now().year
    current_year_str = str(current_year)

    # Check if already exists (get_or_create pattern for shared resources)
    existing = e2e_db.query(FiscalYear).filter(
        FiscalYear.year == current_year_str
    ).first()

    if existing:
        return existing

    fiscal_year = FiscalYear(
        year=current_year_str,
        year_start_date=date(current_year, 1, 1),
        year_end_date=date(current_year, 12, 31),
    )
    e2e_db.add(fiscal_year)
    e2e_db.commit()
    e2e_db.refresh(fiscal_year)

    return fiscal_year


@pytest.fixture(scope="function")
def e2e_chart_of_accounts(e2e_db, e2e_fiscal_year):
    """Create basic chart of accounts for accounting tests."""
    from app.models.accounting import Account, AccountType
    from app.models.accounting_ext import FiscalPeriod
    from app.services.period_manager import PeriodManager

    accounts = []
    account_defs = [
        ("1000", "Cash", AccountType.ASSET),
        ("1100", "Accounts Receivable", AccountType.ASSET),
        ("2000", "Accounts Payable", AccountType.LIABILITY),
        ("3000", "Retained Earnings", AccountType.EQUITY),
        ("4000", "Revenue", AccountType.INCOME),
        ("5000", "Cost of Sales", AccountType.EXPENSE),
        ("6000", "Operating Expenses", AccountType.EXPENSE),
    ]

    for code, name, acc_type in account_defs:
        existing = e2e_db.query(Account).filter(
            Account.account_number == code
        ).first()

        if existing:
            accounts.append(existing)
            continue

        account = Account(
            account_number=code,
            account_name=name,
            root_type=acc_type,
            company="Test Company",
            is_group=False,
            disabled=False,
        )
        e2e_db.add(account)
        accounts.append(account)

    e2e_db.commit()

    # Refresh all accounts
    for acc in accounts:
        e2e_db.refresh(acc)

    # Ensure fiscal periods exist for the fiscal year (needed for JE validation)
    existing_period = e2e_db.query(FiscalPeriod).filter(
        FiscalPeriod.fiscal_year_id == e2e_fiscal_year.id
    ).first()
    if not existing_period:
        PeriodManager(e2e_db).create_fiscal_periods_for_year(
            fiscal_year_id=e2e_fiscal_year.id
        )
        e2e_db.commit()

    return {acc.account_number: acc for acc in accounts}


@pytest.fixture(scope="function")
def e2e_payment_terms(e2e_db):
    """Create or get payment terms for invoicing tests."""
    from app.models.payment_terms import PaymentTerms

    # Check if already exists (get_or_create pattern for shared resources)
    existing = e2e_db.query(PaymentTerms).filter(
        PaymentTerms.code == "NET30"
    ).first()

    if existing:
        return existing

    terms = PaymentTerms(
        code="NET30",
        name="Net 30 Days",
        days_until_due=30,
        is_active=True,
    )
    e2e_db.add(terms)
    e2e_db.commit()
    e2e_db.refresh(terms)

    return terms


# =============================================================================
# CLEANUP UTILITIES
# =============================================================================

@pytest.fixture(autouse=True)
def e2e_cleanup():
    """Clean up dependency overrides after each test."""
    yield

    # Transaction rollback in e2e_db handles data cleanup
    # Clear any remaining dependency overrides as safety measure
    fastapi_app.dependency_overrides.clear()


# =============================================================================
# HELPER FUNCTIONS (available to all tests)
# =============================================================================

def assert_http_ok(response, message: str = ""):
    """Assert response is successful (2xx status)."""
    assert 200 <= response.status_code < 300, (
        f"{message}: Expected 2xx, got {response.status_code}: {response.text}"
    )


def assert_http_error(response, expected_status: int, message: str = ""):
    """Assert response has expected error status."""
    assert response.status_code == expected_status, (
        f"{message}: Expected {expected_status}, got {response.status_code}: {response.text}"
    )


def get_json(response):
    """Get JSON from response, with helpful error message."""
    assert response.status_code < 500, f"Server error: {response.text}"
    return response.json()


# =============================================================================
# RESPONSE VALIDATION HELPERS
# =============================================================================

def assert_response_schema(data: dict, required_fields: list[str], message: str = ""):
    """Validate response contains required fields."""
    missing = [f for f in required_fields if f not in data]
    assert not missing, f"{message}: Missing required fields: {missing}"


def assert_field_exists(data: dict, *path: str, message: str = ""):
    """
    Assert nested field exists in response.

    Usage:
        assert_field_exists(data, "resolution", "resolution", message="Ticket resolution")
    """
    current = data
    for key in path:
        assert key in current, f"{message}: Missing field '{key}' in {list(current.keys())}"
        current = current[key]
    return current


def assert_invoice_response(data: dict):
    """Validate invoice response schema."""
    assert_response_schema(data, ["id", "invoice_number", "status"], "Invoice response")


def assert_payment_response(data: dict):
    """Validate payment response schema."""
    assert_response_schema(data, ["id", "amount"], "Payment response")


def assert_ticket_response(data: dict):
    """Validate ticket response schema."""
    assert_response_schema(data, ["id", "subject", "status", "priority"], "Ticket response")


def assert_project_response(data: dict):
    """Validate project response schema."""
    assert_response_schema(data, ["id", "project_name", "status"], "Project response")


def assert_lead_response(data: dict):
    """Validate lead response schema."""
    assert_response_schema(data, ["id", "lead_name", "status"], "Lead response")
