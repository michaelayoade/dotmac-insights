import os
import pytest
from fastapi.testclient import TestClient

# Force SQLite for tests
os.environ.setdefault("TEST_DATABASE_URL", "sqlite:///./test.db")

from app.main import app as fastapi_app
from app.auth import get_current_principal, Principal
import app.models  # noqa: F401

# Mock Principal with wide scopes so HR endpoints authorize
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
# HR frontend page smoke coverage
# ---------------------------------------------------------------------------

HR_PAGE_ENDPOINTS = [
    ("/api/hr/analytics/overview", dict, ["leave_by_status", "attendance_status_30d", "payroll_30d"]),
    ("/api/hr/analytics/leave-trend", list, None),
    ("/api/hr/analytics/attendance-trend", list, None),
    ("/api/hr/analytics/payroll-summary", dict, ["net_total"]),
    ("/api/hr/analytics/payroll-trend", list, None),
    ("/api/hr/analytics/payroll-components", list, None),
    ("/api/hr/analytics/recruitment-funnel", dict, ["openings", "applicants"]),
    ("/api/hr/analytics/appraisal-status", dict, ["status_counts"]),
    ("/api/hr/analytics/lifecycle-events", dict, ["onboarding", "separation", "promotion", "transfer"]),
    ("/api/hr/leave-types", dict, ["data"]),
    ("/api/hr/holiday-lists", dict, ["data"]),
    ("/api/hr/leave-policies", dict, ["data"]),
    ("/api/hr/leave-allocations", dict, ["data"]),
    ("/api/hr/leave-applications", dict, ["data"]),
    ("/api/hr/shift-types", dict, ["data"]),
    ("/api/hr/shift-assignments", dict, ["data"]),
    ("/api/hr/attendances", dict, ["data"]),
    ("/api/hr/attendance-requests", dict, ["data"]),
    ("/api/hr/job-openings", dict, ["data"]),
    ("/api/hr/job-applicants", dict, ["data"]),
    ("/api/hr/job-offers", dict, ["data"]),
    ("/api/hr/interviews", dict, ["data"]),
    ("/api/hr/salary-components", dict, ["data"]),
    ("/api/hr/salary-structures", dict, ["data"]),
    ("/api/hr/salary-structure-assignments", dict, ["data"]),
    ("/api/hr/payroll-entries", dict, ["data"]),
    ("/api/hr/salary-slips", dict, ["data"]),
    ("/api/hr/training-programs", dict, ["data"]),
    ("/api/hr/training-events", dict, ["data"]),
    ("/api/hr/training-results", dict, ["data"]),
    ("/api/hr/employee-onboardings", dict, ["data"]),
    ("/api/hr/employee-separations", dict, ["data"]),
    ("/api/hr/employee-promotions", dict, ["data"]),
    ("/api/hr/employee-transfers", dict, ["data"]),
    ("/api/hr/settings", dict, ["settings"]),
]


@pytest.mark.parametrize(
    "endpoint,expected_type,required_keys",
    HR_PAGE_ENDPOINTS,
    ids=[path for path, _, _ in HR_PAGE_ENDPOINTS],
)
def test_hr_frontend_pages_have_data_sources(client, endpoint, expected_type, required_keys):
    """Smoke test: HR pages' backing APIs respond and shape matches expectations."""
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
        "/api/hr/leave-types/999999",
        "/api/hr/attendances/999999",
        "/api/hr/job-openings/999999",
        "/api/hr/salary-slips/999999",
    ],
)
def test_hr_detail_endpoints_404_for_missing_records(client, detail_endpoint):
    """Detail routes should return clean 404s for nonexistent records."""
    resp = client.get(detail_endpoint)
    assert resp.status_code == 404, f"{detail_endpoint} should 404 for missing records, got {resp.status_code}"
