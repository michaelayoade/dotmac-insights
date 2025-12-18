"""
Shared test fixtures for DotMAC Insights tests.

Provides authentication fixtures for testing RBAC scopes:
- auth_client_with_scope: Factory for authenticated client with specific scopes
- service_token_client: Factory for service token authenticated client
- unauthenticated_client: Client with no auth for testing 401s
"""
import os
import pytest
from fastapi.testclient import TestClient

# Force SQLite for tests
os.environ.setdefault("TEST_DATABASE_URL", "sqlite:///./test.db")

from app.main import app as fastapi_app
from app.auth import get_current_principal, Principal


# =============================================================================
# MOCK PRINCIPALS
# =============================================================================


def create_mock_principal(
    scopes: set[str],
    principal_type: str = "user",
    is_superuser: bool = False,
    user_id: int = 1,
) -> Principal:
    """Create a mock Principal for testing."""
    return Principal(
        type=principal_type,
        id=user_id,
        external_id=f"test_{principal_type}_{user_id}",
        email="test@example.com" if principal_type == "user" else None,
        name=f"Test {principal_type.title()}",
        is_superuser=is_superuser,
        scopes=scopes,
    )


# =============================================================================
# BASE CLIENT FIXTURE
# =============================================================================


@pytest.fixture
def base_client():
    """Base TestClient without any auth overrides."""
    with TestClient(fastapi_app) as client:
        yield client


# =============================================================================
# AUTHENTICATED CLIENT FIXTURES
# =============================================================================


@pytest.fixture
def auth_client_with_scope(base_client):
    """
    Returns factory for authenticated client with specific scopes.

    Usage:
        def test_something(auth_client_with_scope):
            client = auth_client_with_scope(["contacts:read"])
            resp = client.get("/api/contacts")
            assert resp.status_code == 200
    """
    def _make_client(scopes: list[str], is_superuser: bool = False, user_id: int = 1):
        mock_principal = create_mock_principal(
            scopes=set(scopes),
            principal_type="user",
            is_superuser=is_superuser,
            user_id=user_id,
        )

        async def override_principal():
            return mock_principal

        fastapi_app.dependency_overrides[get_current_principal] = override_principal
        return base_client

    yield _make_client

    # Cleanup
    fastapi_app.dependency_overrides.pop(get_current_principal, None)


@pytest.fixture
def service_token_client(base_client):
    """
    Returns factory for service token authenticated client.

    Usage:
        def test_service_token(service_token_client):
            client = service_token_client(["contacts:read"])
            resp = client.get("/api/contacts")
            assert resp.status_code == 200
    """
    def _make_client(scopes: list[str], token_id: int = 1):
        mock_principal = create_mock_principal(
            scopes=set(scopes),
            principal_type="service_token",
            is_superuser=False,
            user_id=token_id,
        )

        async def override_principal():
            return mock_principal

        fastapi_app.dependency_overrides[get_current_principal] = override_principal
        return base_client

    yield _make_client

    # Cleanup
    fastapi_app.dependency_overrides.pop(get_current_principal, None)


@pytest.fixture
def unauthenticated_client():
    """
    Client with no auth - for testing 401s.

    Usage:
        def test_unauthenticated_rejected(unauthenticated_client):
            resp = unauthenticated_client.get("/api/contacts")
            assert resp.status_code == 401
    """
    # Don't override get_current_principal - let it raise 401
    fastapi_app.dependency_overrides.pop(get_current_principal, None)

    with TestClient(fastapi_app) as client:
        yield client


@pytest.fixture
def superuser_client(base_client):
    """
    Client authenticated as superuser (has all permissions).

    Usage:
        def test_superuser_access(superuser_client):
            resp = superuser_client.get("/api/admin/users")
            assert resp.status_code == 200
    """
    mock_principal = create_mock_principal(
        scopes={"*"},
        principal_type="user",
        is_superuser=True,
        user_id=1,
    )

    async def override_principal():
        return mock_principal

    fastapi_app.dependency_overrides[get_current_principal] = override_principal

    yield base_client

    # Cleanup
    fastapi_app.dependency_overrides.pop(get_current_principal, None)


# =============================================================================
# LEGACY COMPATIBILITY FIXTURE
# =============================================================================


@pytest.fixture
def client():
    """
    Legacy client fixture with superuser access.
    Use for existing tests that don't need scope testing.

    New tests should use auth_client_with_scope for proper RBAC testing.
    """
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

    fastapi_app.dependency_overrides[get_current_principal] = override_get_current_principal

    with TestClient(fastapi_app) as c:
        yield c

    fastapi_app.dependency_overrides = {}
