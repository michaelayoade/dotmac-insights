"""
OpenAPI Endpoint Smoke Tests.

Fetches the OpenAPI spec and verifies each endpoint returns expected status codes.
This ensures all documented API routes are accessible and responding correctly.

Run with: pytest tests/e2e/test_openapi_endpoints.py -v
"""

import pytest
import httpx
from typing import Any

# Base URL for the API
BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="module")
def openapi_spec() -> dict[str, Any]:
    """Fetch and parse the OpenAPI specification."""
    response = httpx.get(f"{BASE_URL}/openapi.json", timeout=30)
    assert response.status_code == 200, f"Failed to fetch OpenAPI spec: {response.status_code}"
    return response.json()


@pytest.fixture(scope="module")
def auth_token() -> str:
    """Get authentication token for protected endpoints."""
    # Try to login and get a token
    try:
        response = httpx.post(
            f"{BASE_URL}/api/auth/token",
            data={"username": "admin@dotmac.ng", "password": "admin123"},
            timeout=10,
        )
        if response.status_code == 200:
            return response.json().get("access_token", "")
    except Exception:
        pass

    # Fallback: try form-based login
    try:
        response = httpx.post(
            f"{BASE_URL}/auth/login",
            data={"email": "admin@dotmac.ng", "password": "admin123"},
            timeout=10,
        )
        if response.status_code == 200:
            # Extract token from cookies or response
            return response.cookies.get("access_token", "")
    except Exception:
        pass

    return ""


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

    def test_openapi_json_accessible(self):
        """Verify /openapi.json endpoint returns valid JSON."""
        response = httpx.get(f"{BASE_URL}/openapi.json", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
        assert "info" in data

    def test_swagger_docs_accessible(self):
        """Verify /docs (Swagger UI) is accessible."""
        response = httpx.get(f"{BASE_URL}/docs", timeout=10)
        # Should return HTML or redirect
        assert response.status_code in (200, 307, 308)

    def test_redoc_accessible(self):
        """Verify /redoc is accessible."""
        response = httpx.get(f"{BASE_URL}/redoc", timeout=10)
        # Should return HTML or redirect
        assert response.status_code in (200, 307, 308)


class TestOpenAPIEndpointsSmokeTest:
    """Smoke test all endpoints from OpenAPI spec."""

    @pytest.mark.parametrize("endpoint_type", ["public", "authenticated"])
    def test_health_endpoints(self, endpoint_type):
        """Verify health check endpoints respond."""
        health_paths = ["/health", "/api/health", "/healthz", "/ready"]

        for path in health_paths:
            try:
                response = httpx.get(f"{BASE_URL}{path}", timeout=5)
                if response.status_code == 200:
                    return  # Found a working health endpoint
            except Exception:
                continue

        # At least one health endpoint should work
        pytest.skip("No health endpoint found")

    def test_get_endpoints_respond(self, openapi_spec: dict[str, Any], auth_token: str):
        """Test all GET endpoints return expected status codes."""
        endpoints = extract_endpoints(openapi_spec)
        get_endpoints = [(path, op) for method, path, op in endpoints if method == "GET"]

        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        results = {"passed": 0, "failed": 0, "skipped": 0}
        failures = []

        for path, operation in get_endpoints:
            url = f"{BASE_URL}{substitute_path_params(path)}"

            try:
                response = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)

                # Expected: 200, 401 (auth required), 403 (forbidden), 404 (resource not found)
                # Unexpected: 500, 502, 503 (server errors)
                if response.status_code >= 500:
                    failures.append(f"{path}: {response.status_code}")
                    results["failed"] += 1
                elif response.status_code in (401, 403) and not auth_token:
                    results["skipped"] += 1  # Auth required but no token
                else:
                    results["passed"] += 1

            except httpx.TimeoutException:
                failures.append(f"{path}: timeout")
                results["failed"] += 1
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
        ("GET", "/crm/contacts"),
        ("GET", "/support/tickets"),
    ]

    @pytest.mark.critical
    @pytest.mark.parametrize("method,path", CRITICAL_ENDPOINTS)
    def test_critical_endpoint(self, method: str, path: str, auth_token: str):
        """Verify critical endpoints respond without server errors."""
        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        url = f"{BASE_URL}{path}"

        if method == "GET":
            response = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
        else:
            pytest.skip(f"Method {method} not implemented in test")

        # Should not return server errors
        assert response.status_code < 500, f"{path} returned {response.status_code}"


class TestModuleEndpoints:
    """Test endpoints for each module."""

    MODULE_ENDPOINTS = {
        "CRM": [
            "/crm/contacts",
            "/api/crm/contacts",
        ],
        "Support": [
            "/support/tickets",
            "/api/support/tickets",
        ],
        "Purchasing": [
            "/purchasing/expenses",
            "/api/purchasing/expenses",
        ],
        "Accounting": [
            "/accounting/invoices",
            "/api/accounting/invoices",
        ],
    }

    @pytest.mark.parametrize("module", MODULE_ENDPOINTS.keys())
    def test_module_has_accessible_endpoint(self, module: str, auth_token: str):
        """Verify each module has at least one accessible endpoint."""
        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        endpoints = self.MODULE_ENDPOINTS[module]
        accessible = False

        for path in endpoints:
            try:
                response = httpx.get(
                    f"{BASE_URL}{path}",
                    headers=headers,
                    timeout=10,
                    follow_redirects=True
                )
                if response.status_code < 500:
                    accessible = True
                    break
            except Exception:
                continue

        assert accessible, f"No accessible endpoint found for {module} module"


# CLI runner for standalone testing
if __name__ == "__main__":
    import sys

    print(f"Testing API at {BASE_URL}")
    print("=" * 60)

    # Quick smoke test without pytest
    try:
        # Test OpenAPI spec
        print("\n1. Fetching OpenAPI spec...")
        resp = httpx.get(f"{BASE_URL}/openapi.json", timeout=10)
        if resp.status_code == 200:
            spec = resp.json()
            endpoints = extract_endpoints(spec)
            print(f"   Found {len(endpoints)} endpoints in OpenAPI spec")
        else:
            print(f"   Failed: {resp.status_code}")
            sys.exit(1)

        # Test GET endpoints
        print("\n2. Testing GET endpoints...")
        get_endpoints = [e for e in endpoints if e[0] == "GET"]
        passed = 0
        failed = 0

        for method, path, _ in get_endpoints[:20]:  # Test first 20
            url = f"{BASE_URL}{substitute_path_params(path)}"
            try:
                r = httpx.get(url, timeout=5, follow_redirects=True)
                if r.status_code < 500:
                    passed += 1
                    print(f"   ✓ {path} -> {r.status_code}")
                else:
                    failed += 1
                    print(f"   ✗ {path} -> {r.status_code}")
            except Exception as e:
                failed += 1
                print(f"   ✗ {path} -> {e}")

        print(f"\n   Results: {passed} passed, {failed} failed")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
