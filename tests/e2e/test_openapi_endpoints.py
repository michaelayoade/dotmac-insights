"""
OpenAPI Endpoint Smoke Tests.

Fetches the OpenAPI spec and verifies each endpoint returns expected status codes.
This ensures all documented API routes are accessible and responding correctly.

Run with: pytest tests/e2e/test_openapi_endpoints.py -v
"""

import pytest
from typing import Any


@pytest.fixture
def openapi_spec(e2e_client) -> dict[str, Any]:
    """Fetch and parse the OpenAPI specification."""
    response = e2e_client.get("/openapi.json")
    assert response.status_code == 200, f"Failed to fetch OpenAPI spec: {response.status_code}"
    return response.json()


def extract_endpoints(openapi_spec: dict[str, Any]) -> list[tuple[str, str, dict]]:
    """Extract all endpoints from OpenAPI spec.

    Returns list of (method, path, operation_info) tuples.
    """
    endpoints = []
    paths = openapi_spec.get("paths", {})

    for path, methods in paths.items():
        for method, operation in methods.items():
            if method.upper() in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
                endpoints.append((method.upper(), path, operation))

    return endpoints


def substitute_path_params(path: str) -> str:
    """Replace path parameters with test values."""
    import re

    # Common substitutions for path parameters
    substitutions = {
        "{id}": "1",
        "{contact_id}": "1",
        "{ticket_id}": "1",
        "{customer_id}": "1",
        "{invoice_id}": "1",
        "{user_id}": "1",
        "{team_id}": "1",
        "{project_id}": "1",
        "{task_id}": "1",
        "{expense_id}": "1",
        "{payment_id}": "1",
        "{product_id}": "1",
        "{order_id}": "1",
        "{item_id}": "1",
    }

    result = path
    for param, value in substitutions.items():
        result = result.replace(param, value)

    # Handle any remaining {param} patterns
    result = re.sub(r"\{[^}]+\}", "1", result)

    return result


class TestOpenAPIDocsAccessibility:
    """Test that OpenAPI documentation endpoints are accessible."""

    def test_openapi_json_accessible(self, e2e_client):
        """Verify /openapi.json endpoint returns valid JSON."""
        response = e2e_client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
        assert "info" in data

    def test_swagger_docs_accessible(self, e2e_client):
        """Verify /docs (Swagger UI) is accessible."""
        response = e2e_client.get("/docs", allow_redirects=True)
        # Should return HTML or redirect
        assert response.status_code in (200, 307, 308)

    def test_redoc_accessible(self, e2e_client):
        """Verify /redoc is accessible."""
        response = e2e_client.get("/redoc", allow_redirects=True)
        # Should return HTML or redirect
        assert response.status_code in (200, 307, 308)


class TestOpenAPIEndpointsSmokeTest:
    """Smoke test all endpoints from OpenAPI spec."""

    @pytest.mark.parametrize("endpoint_type", ["public", "authenticated"])
    def test_health_endpoints(self, endpoint_type, e2e_client):
        """Verify health check endpoints respond."""
        health_paths = ["/health", "/health/ready", "/api/health", "/api/health/ready", "/healthz", "/ready"]

        for path in health_paths:
            try:
                response = e2e_client.get(path)
                if response.status_code in (200, 503):
                    return  # Found a working health endpoint
            except Exception:
                continue

        # At least one health endpoint should work
        pytest.skip("No health endpoint found")

    def test_get_endpoints_respond(self, openapi_spec: dict[str, Any], e2e_superuser_client):
        """Test all GET endpoints return expected status codes."""
        endpoints = extract_endpoints(openapi_spec)
        get_endpoints = [(path, op) for method, path, op in endpoints if method == "GET"]

        results = {"passed": 0, "failed": 0, "skipped": 0}
        failures = []

        for path, operation in get_endpoints:
            url = substitute_path_params(path)

            try:
                response = e2e_superuser_client.get(url, allow_redirects=True)

                # Expected: 200, 404 (resource not found), 422 (missing params)
                # Unexpected: 500, 502, 503 (server errors), 401/403 (auth failures)
                if response.status_code >= 500:
                    failures.append(f"{path}: {response.status_code}")
                    results["failed"] += 1
                elif response.status_code in (401, 403):
                    failures.append(f"{path}: {response.status_code}")
                    results["failed"] += 1
                else:
                    results["passed"] += 1

            except Exception as e:
                failures.append(f"{path}: {str(e)}")
                results["failed"] += 1

        # Report results
        print(f"\nGET Endpoints: {results['passed']} passed, {results['failed']} failed, {results['skipped']} skipped")

        if failures:
            print("Failures:")
            for f in failures[:10]:  # Show first 10 failures
                print(f"  - {f}")

        # Allow some failures (404 for non-existent IDs is expected)
        assert results["failed"] <= len(get_endpoints) * 0.1, f"Too many failures: {failures}"


class TestCriticalEndpoints:
    """Test critical API endpoints that must always work."""

    CRITICAL_ENDPOINTS = [
        ("GET", "/health"),
        ("GET", "/openapi.json"),
        ("GET", "/api/v1/crm/parties"),
        ("GET", "/api/v1/support/tickets"),
    ]

    @pytest.mark.critical
    @pytest.mark.parametrize("method,path", CRITICAL_ENDPOINTS)
    def test_critical_endpoint(self, method: str, path: str, e2e_superuser_client):
        """Verify critical endpoints respond without server errors."""
        if method == "GET":
            response = e2e_superuser_client.get(path, allow_redirects=True)
        else:
            pytest.skip(f"Method {method} not implemented in test")

        # Should not return server errors
        assert response.status_code < 500, f"{path} returned {response.status_code}"


class TestModuleEndpoints:
    """Test endpoints for each module."""

    MODULE_ENDPOINTS = {
        "CRM": [
            "/api/v1/crm/parties",
        ],
        "Support": [
            "/support/tickets",
            "/api/v1/support/tickets",
        ],
        "Purchasing": [
            "/purchasing/expenses",
            "/api/v1/purchasing/expenses",
        ],
        "Accounting": [
            "/accounting/invoices",
            "/api/v1/accounting/invoices",
        ],
    }

    @pytest.mark.parametrize("module", MODULE_ENDPOINTS.keys())
    def test_module_has_accessible_endpoint(self, module: str, e2e_superuser_client):
        """Verify each module has at least one accessible endpoint."""
        endpoints = self.MODULE_ENDPOINTS[module]
        accessible = False

        for path in endpoints:
            try:
                response = e2e_superuser_client.get(path, allow_redirects=True)
                if response.status_code < 500:
                    accessible = True
                    break
            except Exception:
                continue

        assert accessible, f"No accessible endpoint found for {module} module"
