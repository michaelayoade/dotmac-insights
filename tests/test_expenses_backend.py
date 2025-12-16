import os
import pytest
from fastapi.testclient import TestClient

# Use SQLite for tests
os.environ.setdefault("TEST_DATABASE_URL", "sqlite:///./test.db")

from app.main import app as fastapi_app
from app.auth import get_current_principal, Principal
import app.models  # noqa: F401

# Permit all scopes during tests
mock_principal = Principal(
    type="user",
    id=1,
    external_id="test_user",
    email="test@example.com",
    name="Test User",
    is_superuser=True,
    scopes={"*"},
)


async def override_get_current_principal():
    return mock_principal


@pytest.fixture
def client():
    fastapi_app.dependency_overrides[get_current_principal] = override_get_current_principal
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides = {}


# ---------------------------------------------------------------------------
# Expenses frontend page smoke coverage
# ---------------------------------------------------------------------------

EXPENSE_PAGE_ENDPOINTS = [
    ("/api/expenses/categories/", list, None),
    ("/api/expenses/policies/", list, None),
    ("/api/expenses/claims/", list, None),
    ("/api/expenses/cash-advances/", list, None),
    ("/api/analytics/expenses/by-category", dict, ["by_category", "total_expenses"]),
    ("/api/analytics/expenses/by-cost-center", dict, ["by_cost_center", "total_expenses"]),
    ("/api/analytics/expenses/trend", list, None),
    ("/api/analytics/expenses/vendor-spend", dict, ["vendors"]),
]


@pytest.mark.parametrize(
    "endpoint,expected_type,required_keys",
    EXPENSE_PAGE_ENDPOINTS,
    ids=[path for path, _, _ in EXPENSE_PAGE_ENDPOINTS],
)
def test_expense_frontend_pages_have_data_sources(client, endpoint, expected_type, required_keys):
    """Smoke test: Expense pages' backing APIs respond with JSON."""
    response = client.get(endpoint)
    assert response.status_code == 200, f"{endpoint} failed: {response.text}"

    payload = response.json()
    assert isinstance(payload, expected_type), f"{endpoint} returned {type(payload)} instead of {expected_type}"

    if required_keys:
        for key in required_keys:
            assert key in payload, f"{endpoint} missing expected key '{key}'"


@pytest.mark.parametrize(
    "detail_endpoint",
    [
        "/api/expenses/claims/999999",
        "/api/expenses/cash-advances/999999",
    ],
)
def test_expense_detail_endpoints_404_for_missing_records(client, detail_endpoint):
    """Detail routes should return 404 for nonexistent records."""
    resp = client.get(detail_endpoint)
    assert resp.status_code == 404, f"{detail_endpoint} should 404 for missing records, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Corporate Card API smoke tests
# ---------------------------------------------------------------------------

CORPORATE_CARD_ENDPOINTS = [
    ("/api/expenses/cards/", list, None),
    ("/api/expenses/transactions/", list, None),
    ("/api/expenses/statements/", list, None),
]


@pytest.mark.parametrize(
    "endpoint,expected_type,required_keys",
    CORPORATE_CARD_ENDPOINTS,
    ids=[path for path, _, _ in CORPORATE_CARD_ENDPOINTS],
)
def test_corporate_card_list_endpoints(client, endpoint, expected_type, required_keys):
    """Smoke test: Corporate card list APIs respond with JSON."""
    response = client.get(endpoint)
    assert response.status_code == 200, f"{endpoint} failed: {response.text}"

    payload = response.json()
    assert isinstance(payload, expected_type), f"{endpoint} returned {type(payload)} instead of {expected_type}"

    if required_keys:
        for key in required_keys:
            assert key in payload, f"{endpoint} missing expected key '{key}'"


@pytest.mark.parametrize(
    "detail_endpoint",
    [
        "/api/expenses/cards/999999",
        "/api/expenses/transactions/999999",
        "/api/expenses/statements/999999",
    ],
)
def test_corporate_card_detail_endpoints_404_for_missing_records(client, detail_endpoint):
    """Corporate card detail routes should return 404 for nonexistent records."""
    resp = client.get(detail_endpoint)
    assert resp.status_code == 404, f"{detail_endpoint} should 404 for missing records, got {resp.status_code}"


def test_cards_filter_by_employee(client):
    """Cards endpoint should accept employee_id filter."""
    response = client.get("/api/expenses/cards/?employee_id=1")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_cards_filter_by_status(client):
    """Cards endpoint should accept status filter."""
    response = client.get("/api/expenses/cards/?status=active")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_transactions_filter_by_card(client):
    """Transactions endpoint should accept card_id filter."""
    response = client.get("/api/expenses/transactions/?card_id=1")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_transactions_unmatched_filter(client):
    """Transactions endpoint should accept unmatched_only filter."""
    response = client.get("/api/expenses/transactions/?unmatched_only=true")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_statements_filter_by_card(client):
    """Statements endpoint should accept card_id filter."""
    response = client.get("/api/expenses/statements/?card_id=1")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
