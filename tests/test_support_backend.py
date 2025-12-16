import os
import pytest
from fastapi.testclient import TestClient

# Force SQLite for tests
os.environ.setdefault("TEST_DATABASE_URL", "sqlite:///./test.db")

from app.main import app as fastapi_app
from app.auth import get_current_principal, Principal
import app.models  # noqa: F401

# Mock principal with full access
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
        # Seed default support settings if missing to avoid 404s
        c.post("/api/support/settings/seed-defaults")
        yield c
    fastapi_app.dependency_overrides = {}


# ---------------------------------------------------------------------------
# Support frontend page smoke coverage
# ---------------------------------------------------------------------------

SUPPORT_PAGE_ENDPOINTS = [
    ("/api/support/dashboard", dict, ["tickets"]),
    ("/api/support/analytics/overview", dict, ["ticket_volume"]),
    ("/api/support/analytics/volume-trend", list, None),
    ("/api/support/analytics/resolution-time", list, None),
    ("/api/support/analytics/by-category", dict, ["by_ticket_type"]),
    ("/api/support/analytics/sla-performance", list, None),
    ("/api/support/insights/patterns", dict, ["peak_hours"]),
    ("/api/support/insights/agent-performance", dict, ["by_assignee"]),
    ("/api/support/routing/queue-health", dict, ["unassigned_tickets"]),
    ("/api/support/routing/rules", list, None),
    ("/api/support/routing/agent-workload", list, None),
    ("/api/support/teams", list, None),
    ("/api/support/agents", dict, ["total", "data"]),
    ("/api/support/tickets", dict, ["total", "data"]),
    ("/api/support/sla/calendars", list, None),
    ("/api/support/sla/policies", list, None),
    ("/api/support/sla/breaches/summary", dict, ["total_breaches"]),
    ("/api/support/automation/rules", list, None),
    ("/api/support/automation/logs", dict, ["data"]),
    ("/api/support/automation/logs/summary", dict, ["total_executions"]),
    ("/api/support/kb/categories", list, None),
    ("/api/support/kb/articles", dict, ["total", "data"]),
    ("/api/support/canned-responses", dict, ["total", "data"]),
    ("/api/support/canned-responses/categories", list, None),
    ("/api/support/csat/surveys", list, None),
    ("/api/support/csat/analytics/summary", dict, ["total_responses"]),
    ("/api/support/csat/analytics/by-agent", list, None),
    ("/api/support/csat/analytics/trends", list, None),
    ("/api/support/settings", dict, None),
    ("/api/support/settings/queues", list, None),
    ("/api/support/metrics", dict, ["total"]),
]


@pytest.mark.parametrize(
    "endpoint,expected_type,required_keys",
    SUPPORT_PAGE_ENDPOINTS,
    ids=[path for path, _, _ in SUPPORT_PAGE_ENDPOINTS],
)
def test_support_frontend_pages_have_data_sources(client, endpoint, expected_type, required_keys):
    """Smoke test: Support pages' backing APIs respond with JSON."""
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
        "/api/support/tickets/999999",
        "/api/support/agents/999999",
        "/api/support/kb/articles/999999",
    ],
)
def test_support_detail_endpoints_404_for_missing_records(client, detail_endpoint):
    """Detail routes should return 404 for nonexistent records rather than 500s."""
    resp = client.get(detail_endpoint)
    assert resp.status_code == 404, f"{detail_endpoint} should 404 for missing records, got {resp.status_code}"
