"""
Parties API Integration Tests

Tests CRUD operations, filtering, RBAC, and validation for CRM parties.
"""
import pytest

from app.models.party import Party


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_org_payload():
    """Base payload for creating an organization party."""
    return {
        "type": "organization",
        "status": "active",
        "name": "Test Organization Ltd",
        "emails": [
            {"address": "contact@testorg.com", "label": "primary", "is_primary": True}
        ],
        "phones": [
            {"number": "+234 812 345 6789", "label": "primary", "is_primary": True}
        ],
        "addresses": [
            {
                "line1": "123 Test Street",
                "city": "Lagos",
                "state": "Lagos",
                "country": "Nigeria",
                "is_primary": True,
            }
        ],
        "tags": ["enterprise"],
    }


@pytest.fixture
def sample_person_payload():
    """Payload for creating a person party."""
    return {
        "type": "person",
        "status": "active",
        "name": "John Doe",
        "first_name": "John",
        "last_name": "Doe",
        "emails": [
            {"address": "john.doe@example.com", "label": "primary", "is_primary": True}
        ],
        "phones": [
            {"number": "+234 803 123 4567", "label": "primary", "is_primary": True}
        ],
    }


@pytest.fixture
def create_test_party(integration_db):
    """Factory fixture to create test parties directly in the database."""
    created = []

    def _create(
        name: str = "Test Party",
        party_type: str = "organization",
        status: str = "active",
        email: str | None = None,
        phone: str | None = None,
        tags: list | None = None,
        custom_fields: dict | None = None,
    ) -> Party:
        email = email or f"{name.lower().replace(' ', '_')}@test.com"
        phone = phone or "+234 800 000 0000"
        party = Party(
            type=party_type,
            status=status,
            name=name,
            primary_email=email,
            primary_phone=phone,
            emails=[{"address": email, "label": "primary", "is_primary": True}],
            phones=[{"number": phone, "label": "primary", "is_primary": True}],
            tags=tags or [],
            custom_fields=custom_fields or {},
        )
        integration_db.add(party)
        integration_db.commit()
        integration_db.refresh(party)
        created.append(party)
        return party

    yield _create


# =============================================================================
# CRUD TESTS
# =============================================================================


class TestPartyCreate:
    """Tests for POST /api/v1/crm/parties/"""

    def test_create_organization_party_success(self, auth_client, sample_org_payload):
        client = auth_client(["crm:write"])
        resp = client.post("/api/v1/crm/parties/", json=sample_org_payload)

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == sample_org_payload["name"]
        assert data["type"] == "organization"
        assert data["primary_email"] == "contact@testorg.com"

    def test_create_person_party_success(self, auth_client, sample_person_payload):
        client = auth_client(["crm:write"])
        resp = client.post("/api/v1/crm/parties/", json=sample_person_payload)

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "John Doe"
        assert data["type"] == "person"
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"

    def test_create_party_with_tags(self, auth_client):
        client = auth_client(["crm:write"])
        payload = {
            "type": "organization",
            "status": "active",
            "name": "Tagged Party",
            "emails": [{"address": "tagged@test.com", "is_primary": True}],
            "tags": ["vip", "priority"],
        }
        resp = client.post("/api/v1/crm/parties/", json=payload)

        assert resp.status_code == 201
        data = resp.json()
        assert "vip" in data["tags"]
        assert "priority" in data["tags"]

    def test_create_party_with_custom_fields(self, auth_client):
        client = auth_client(["crm:write"])
        payload = {
            "type": "organization",
            "status": "active",
            "name": "Custom Fields Party",
            "emails": [{"address": "custom@test.com", "is_primary": True}],
            "custom_fields": {
                "referral_code": "REF123",
                "preferred_time": "morning",
            },
        }
        resp = client.post("/api/v1/crm/parties/", json=payload)

        assert resp.status_code == 201
        data = resp.json()
        assert data["custom_fields"]["referral_code"] == "REF123"

    def test_create_party_without_write_scope_fails(self, auth_client, sample_org_payload):
        client = auth_client(["crm:read"])
        resp = client.post("/api/v1/crm/parties/", json=sample_org_payload)
        assert resp.status_code == 403


class TestPartyRead:
    """Tests for GET /api/v1/crm/parties/{party_id}"""

    def test_get_party_by_id(self, auth_client, create_test_party):
        party = create_test_party(name="Readable Party")

        client = auth_client(["crm:read"])
        resp = client.get(f"/api/v1/crm/parties/{party.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == party.id
        assert data["name"] == "Readable Party"

    def test_get_nonexistent_party_returns_404(self, auth_client):
        client = auth_client(["crm:read"])
        resp = client.get("/api/v1/crm/parties/99999")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_get_party_without_read_scope_fails(self, auth_client, create_test_party):
        party = create_test_party(name="Unreadable Party")

        client = auth_client(["support:read"])
        resp = client.get(f"/api/v1/crm/parties/{party.id}")

        assert resp.status_code == 403


class TestPartyUpdate:
    """Tests for PATCH /api/v1/crm/parties/{party_id}"""

    def test_update_party_basic_fields(self, auth_client, create_test_party):
        party = create_test_party(name="Original Name")

        client = auth_client(["crm:write"])
        resp = client.patch(
            f"/api/v1/crm/parties/{party.id}",
            json={
                "name": "Updated Name",
                "tags": ["updated"],
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"
        assert "updated" in data["tags"]

    def test_update_party_status(self, auth_client, create_test_party):
        party = create_test_party(status="active")

        client = auth_client(["crm:write"])
        resp = client.patch(
            f"/api/v1/crm/parties/{party.id}",
            json={"status": "inactive"},
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "inactive"

    def test_update_party_without_write_scope_fails(self, auth_client, create_test_party):
        party = create_test_party()

        client = auth_client(["crm:read"])
        resp = client.patch(f"/api/v1/crm/parties/{party.id}", json={"name": "Hacked"})

        assert resp.status_code == 403


class TestPartyDelete:
    """Tests for DELETE /api/v1/crm/parties/{party_id}"""

    def test_soft_delete_party(self, auth_client, create_test_party, integration_db):
        party = create_test_party(status="active")

        client = auth_client(["crm:write"])
        resp = client.delete(f"/api/v1/crm/parties/{party.id}")

        assert resp.status_code == 204

        integration_db.refresh(party)
        assert party.status == "inactive"

    def test_delete_nonexistent_party_returns_404(self, auth_client):
        client = auth_client(["crm:write"])
        resp = client.delete("/api/v1/crm/parties/99999")

        assert resp.status_code == 404


class TestPartyList:
    """Tests for GET /api/v1/crm/parties/"""

    def test_list_parties_paginated(self, auth_client, create_test_party):
        for i in range(25):
            create_test_party(name=f"Party {i}")

        client = auth_client(["crm:read"])
        resp = client.get("/api/v1/crm/parties/?limit=10&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 10
        assert data["total"] >= 25
        assert data["limit"] == 10
        assert data["offset"] == 0

    def test_list_parties_with_search(self, auth_client, create_test_party):
        create_test_party(name="Searchable Party")
        create_test_party(name="Other Party")

        client = auth_client(["crm:read"])
        resp = client.get("/api/v1/crm/parties/?search=Searchable")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()["data"]]
        assert "Searchable Party" in names
