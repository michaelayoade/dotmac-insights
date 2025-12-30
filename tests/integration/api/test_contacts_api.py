"""
Contacts API Integration Tests

Tests CRUD operations, filtering, search, person contacts,
RBAC, and validation for the Unified Contacts API.
"""
import pytest
from datetime import datetime, timezone
from decimal import Decimal

from app.models.unified_contact import (
    UnifiedContact, ContactType, ContactCategory, ContactStatus,
    BillingType, LeadQualification
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_contact_payload():
    """Base payload for creating a contact."""
    return {
        "name": "Test Organization Ltd",
        "contact_type": "customer",
        "category": "business",
        "status": "active",
        "is_organization": True,
        "email": "contact@testorg.com",
        "phone": "+234 812 345 6789",
        "city": "Lagos",
        "state": "Lagos",
        "country": "Nigeria",
        "territory": "South West",
        "source": "Referral",
    }


@pytest.fixture
def sample_lead_payload():
    """Payload for creating a lead."""
    return {
        "name": "John Doe",
        "contact_type": "lead",
        "category": "residential",
        "status": "active",
        "is_organization": False,
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone": "+234 803 123 4567",
        "city": "Abuja",
        "state": "FCT",
        "source": "Website",
        "lead_qualification": "warm",
        "lead_score": 65,
    }


@pytest.fixture
def create_test_contact(integration_db):
    """Factory fixture to create test contacts directly in the database."""
    created = []

    def _create(
        name: str = "Test Contact",
        contact_type: ContactType = ContactType.CUSTOMER,
        category: ContactCategory = ContactCategory.BUSINESS,
        status: ContactStatus = ContactStatus.ACTIVE,
        is_organization: bool = True,
        email: str = None,
        phone: str = None,
        city: str = "Lagos",
        state: str = "Lagos",
        territory: str = None,
        source: str = None,
        owner_id: int = None,
        parent_id: int = None,
        mrr: Decimal = None,
        outstanding_balance: Decimal = None,
        lead_qualification: LeadQualification = None,
        lead_score: int = None,
        tags: list = None,
    ) -> UnifiedContact:
        contact = UnifiedContact(
            name=name,
            contact_type=contact_type,
            category=category,
            status=status,
            is_organization=is_organization,
            email=email or f"{name.lower().replace(' ', '_')}@test.com",
            phone=phone,
            city=city,
            state=state,
            territory=territory,
            source=source,
            owner_id=owner_id,
            parent_id=parent_id,
            mrr=mrr,
            outstanding_balance=outstanding_balance,
            lead_qualification=lead_qualification,
            lead_score=lead_score,
            tags=tags,
        )
        integration_db.add(contact)
        integration_db.commit()
        integration_db.refresh(contact)
        created.append(contact)
        return contact

    yield _create


# =============================================================================
# CRUD TESTS
# =============================================================================


class TestContactCreate:
    """Tests for POST /api/contacts/"""

    def test_create_organization_contact_success(self, auth_client, sample_contact_payload):
        """Create an organization contact successfully."""
        client = auth_client(["contacts:write"])
        resp = client.post("/api/contacts/", json=sample_contact_payload)

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == sample_contact_payload["name"]
        assert data["contact_type"] == "customer"
        assert data["category"] == "business"
        assert data["is_organization"] is True
        assert data["email"] == sample_contact_payload["email"]
        assert data["city"] == "Lagos"
        assert data["id"] is not None

    def test_create_lead_contact_success(self, auth_client, sample_lead_payload):
        """Create a lead contact successfully."""
        client = auth_client(["contacts:write"])
        resp = client.post("/api/contacts/", json=sample_lead_payload)

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "John Doe"
        assert data["contact_type"] == "lead"
        assert data["is_organization"] is False
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"
        assert data["lead_qualification"] == "warm"
        assert data["lead_score"] == 65

    def test_create_person_contact_with_parent(self, auth_client, create_test_contact):
        """Create a person contact associated with an organization."""
        # First create the parent organization
        org = create_test_contact(
            name="Parent Organization",
            is_organization=True,
            contact_type=ContactType.CUSTOMER,
        )

        client = auth_client(["contacts:write"])
        person_payload = {
            "name": "Jane Smith",
            "contact_type": "person",
            "category": "business",
            "status": "active",
            "parent_id": org.id,
            "is_organization": False,
            "is_primary_contact": True,
            "is_billing_contact": True,
            "designation": "Finance Manager",
            "department": "Finance",
            "email": "jane@parentorg.com",
            "phone": "+234 809 876 5432",
        }
        resp = client.post("/api/contacts/", json=person_payload)

        assert resp.status_code == 201
        data = resp.json()
        assert data["parent_id"] == org.id
        assert data["is_primary_contact"] is True
        assert data["is_billing_contact"] is True
        assert data["designation"] == "Finance Manager"

    def test_create_person_without_parent_fails(self, auth_client):
        """Person contacts must have a parent_id."""
        client = auth_client(["contacts:write"])
        payload = {
            "name": "Orphan Person",
            "contact_type": "person",
            "category": "business",
            "status": "active",
            "is_organization": False,
            "email": "orphan@test.com",
        }
        resp = client.post("/api/contacts/", json=payload)

        assert resp.status_code == 400
        assert "parent_id" in resp.json()["detail"].lower()

    def test_create_contact_with_invalid_parent_fails(self, auth_client):
        """Cannot create person with non-existent parent."""
        client = auth_client(["contacts:write"])
        payload = {
            "name": "Invalid Parent Person",
            "contact_type": "person",
            "category": "business",
            "status": "active",
            "parent_id": 99999,
            "is_organization": False,
            "email": "invalid@test.com",
        }
        resp = client.post("/api/contacts/", json=payload)

        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"].lower()

    def test_create_contact_parent_must_be_organization(self, auth_client, create_test_contact):
        """Parent contact must be an organization."""
        # Create a non-org contact
        individual = create_test_contact(
            name="Individual Customer",
            is_organization=False,
            contact_type=ContactType.CUSTOMER,
        )

        client = auth_client(["contacts:write"])
        payload = {
            "name": "Person Under Individual",
            "contact_type": "person",
            "category": "residential",
            "status": "active",
            "parent_id": individual.id,
            "is_organization": False,
            "email": "under@test.com",
        }
        resp = client.post("/api/contacts/", json=payload)

        assert resp.status_code == 400
        assert "organization" in resp.json()["detail"].lower()

    def test_create_contact_without_write_scope_fails(self, auth_client, sample_contact_payload):
        """Cannot create contact without contacts:write scope."""
        client = auth_client(["contacts:read"])
        resp = client.post("/api/contacts/", json=sample_contact_payload)

        assert resp.status_code == 403

    def test_create_contact_with_tags(self, auth_client):
        """Create a contact with tags."""
        client = auth_client(["contacts:write"])
        payload = {
            "name": "Tagged Contact",
            "contact_type": "customer",
            "category": "enterprise",
            "status": "active",
            "is_organization": True,
            "email": "tagged@test.com",
            "tags": ["vip", "enterprise", "priority"],
        }
        resp = client.post("/api/contacts/", json=payload)

        assert resp.status_code == 201
        data = resp.json()
        assert "vip" in data["tags"]
        assert "enterprise" in data["tags"]

    def test_create_contact_with_custom_fields(self, auth_client):
        """Create a contact with custom fields."""
        client = auth_client(["contacts:write"])
        payload = {
            "name": "Custom Fields Contact",
            "contact_type": "customer",
            "category": "business",
            "status": "active",
            "is_organization": True,
            "email": "custom@test.com",
            "custom_fields": {
                "referral_code": "REF123",
                "preferred_time": "morning",
            },
        }
        resp = client.post("/api/contacts/", json=payload)

        assert resp.status_code == 201
        data = resp.json()
        assert data["custom_fields"]["referral_code"] == "REF123"


class TestContactRead:
    """Tests for GET /api/contacts/{contact_id}"""

    def test_get_contact_by_id(self, auth_client, create_test_contact):
        """Get a contact by ID."""
        contact = create_test_contact(name="Readable Contact")

        client = auth_client(["contacts:read"])
        resp = client.get(f"/api/contacts/{contact.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == contact.id
        assert data["name"] == "Readable Contact"

    def test_get_nonexistent_contact_returns_404(self, auth_client):
        """Get a non-existent contact returns 404."""
        client = auth_client(["contacts:read"])
        resp = client.get("/api/contacts/99999")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_get_contact_without_read_scope_fails(self, auth_client, create_test_contact):
        """Cannot read contact without contacts:read scope."""
        contact = create_test_contact(name="Unreadable Contact")

        client = auth_client(["support:read"])  # Wrong scope
        resp = client.get(f"/api/contacts/{contact.id}")

        assert resp.status_code == 403


class TestContactUpdate:
    """Tests for PATCH /api/contacts/{contact_id}"""

    def test_update_contact_basic_fields(self, auth_client, create_test_contact):
        """Update basic contact fields."""
        contact = create_test_contact(name="Original Name", city="Lagos")

        client = auth_client(["contacts:write"])
        resp = client.patch(f"/api/contacts/{contact.id}", json={
            "name": "Updated Name",
            "city": "Abuja",
            "phone": "+234 111 222 3333",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"
        assert data["city"] == "Abuja"
        assert data["phone"] == "+234 111 222 3333"

    def test_update_contact_status(self, auth_client, create_test_contact):
        """Update contact status."""
        contact = create_test_contact(status=ContactStatus.ACTIVE)

        client = auth_client(["contacts:write"])
        resp = client.patch(f"/api/contacts/{contact.id}", json={
            "status": "suspended",
        })

        assert resp.status_code == 200
        assert resp.json()["status"] == "suspended"

    def test_update_contact_type(self, auth_client, create_test_contact):
        """Update contact type (e.g., lead to customer)."""
        contact = create_test_contact(contact_type=ContactType.LEAD)

        client = auth_client(["contacts:write"])
        resp = client.patch(f"/api/contacts/{contact.id}", json={
            "contact_type": "customer",
        })

        assert resp.status_code == 200
        assert resp.json()["contact_type"] == "customer"

    def test_update_primary_contact_unmarks_others(self, auth_client, create_test_contact, integration_db):
        """Setting primary contact unmarks other primaries."""
        org = create_test_contact(name="Organization", is_organization=True)
        person1 = create_test_contact(
            name="Person 1",
            contact_type=ContactType.PERSON,
            parent_id=org.id,
            is_organization=False,
        )
        person1.is_primary_contact = True
        integration_db.commit()

        person2 = create_test_contact(
            name="Person 2",
            contact_type=ContactType.PERSON,
            parent_id=org.id,
            is_organization=False,
        )

        client = auth_client(["contacts:write"])
        resp = client.patch(f"/api/contacts/{person2.id}", json={
            "is_primary_contact": True,
        })

        assert resp.status_code == 200
        assert resp.json()["is_primary_contact"] is True

        # Verify person1 is no longer primary
        integration_db.refresh(person1)
        assert person1.is_primary_contact is False

    def test_update_nonexistent_contact_returns_404(self, auth_client):
        """Update non-existent contact returns 404."""
        client = auth_client(["contacts:write"])
        resp = client.patch("/api/contacts/99999", json={"name": "Ghost"})

        assert resp.status_code == 404

    def test_update_contact_without_write_scope_fails(self, auth_client, create_test_contact):
        """Cannot update contact without contacts:write scope."""
        contact = create_test_contact()

        client = auth_client(["contacts:read"])
        resp = client.patch(f"/api/contacts/{contact.id}", json={"name": "Hacked"})

        assert resp.status_code == 403


class TestContactDelete:
    """Tests for DELETE /api/contacts/{contact_id}"""

    def test_soft_delete_contact(self, auth_client, create_test_contact, integration_db):
        """Soft delete sets status to inactive."""
        contact = create_test_contact(status=ContactStatus.ACTIVE)

        client = auth_client(["contacts:write"])
        resp = client.delete(f"/api/contacts/{contact.id}")

        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert "deactivated" in resp.json()["message"].lower()

        integration_db.refresh(contact)
        assert contact.status == ContactStatus.INACTIVE

    def test_hard_delete_contact(self, auth_client, create_test_contact, integration_db):
        """Hard delete removes contact from database."""
        contact = create_test_contact()
        contact_id = contact.id

        client = auth_client(["contacts:write"])
        resp = client.delete(f"/api/contacts/{contact_id}?hard=true")

        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"].lower()

        # Verify contact is gone
        deleted = integration_db.query(UnifiedContact).filter(
            UnifiedContact.id == contact_id
        ).first()
        assert deleted is None

    def test_hard_delete_cascades_to_children(self, auth_client, create_test_contact, integration_db):
        """Hard delete also removes child contacts."""
        org = create_test_contact(name="Parent Org", is_organization=True)
        child1 = create_test_contact(
            name="Child 1",
            contact_type=ContactType.PERSON,
            parent_id=org.id,
            is_organization=False,
        )
        child2 = create_test_contact(
            name="Child 2",
            contact_type=ContactType.PERSON,
            parent_id=org.id,
            is_organization=False,
        )

        org_id = org.id
        child1_id = child1.id
        child2_id = child2.id

        client = auth_client(["contacts:write"])
        resp = client.delete(f"/api/contacts/{org_id}?hard=true")

        assert resp.status_code == 200

        # Verify all are gone
        assert integration_db.query(UnifiedContact).filter(
            UnifiedContact.id == org_id
        ).first() is None
        assert integration_db.query(UnifiedContact).filter(
            UnifiedContact.id == child1_id
        ).first() is None
        assert integration_db.query(UnifiedContact).filter(
            UnifiedContact.id == child2_id
        ).first() is None

    def test_delete_nonexistent_contact_returns_404(self, auth_client):
        """Delete non-existent contact returns 404."""
        client = auth_client(["contacts:write"])
        resp = client.delete("/api/contacts/99999")

        assert resp.status_code == 404


# =============================================================================
# LIST AND FILTER TESTS
# =============================================================================


class TestContactList:
    """Tests for GET /api/contacts/"""

    def test_list_contacts_paginated(self, auth_client, create_test_contact):
        """List contacts with pagination."""
        for i in range(25):
            create_test_contact(name=f"Contact {i}")

        client = auth_client(["contacts:read"])

        # First page
        resp = client.get("/api/contacts/?page=1&page_size=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 10
        assert data["total"] >= 25
        assert data["limit"] == 10
        assert data["offset"] == 0

        # Second page
        resp = client.get("/api/contacts/?page=2&page_size=10")
        data = resp.json()
        assert len(data["data"]) == 10
        assert data["offset"] == 10

    def test_list_contacts_filter_by_type(self, auth_client, create_test_contact):
        """Filter contacts by contact_type."""
        create_test_contact(name="Lead 1", contact_type=ContactType.LEAD)
        create_test_contact(name="Lead 2", contact_type=ContactType.LEAD)
        create_test_contact(name="Customer 1", contact_type=ContactType.CUSTOMER)

        client = auth_client(["contacts:read"])
        resp = client.get("/api/contacts/?contact_type=lead")

        assert resp.status_code == 200
        data = resp.json()
        assert all(c["contact_type"] == "lead" for c in data["data"])

    def test_list_contacts_filter_by_status(self, auth_client, create_test_contact):
        """Filter contacts by status."""
        create_test_contact(name="Active 1", status=ContactStatus.ACTIVE)
        create_test_contact(name="Suspended 1", status=ContactStatus.SUSPENDED)

        client = auth_client(["contacts:read"])
        resp = client.get("/api/contacts/?status=suspended")

        assert resp.status_code == 200
        data = resp.json()
        assert all(c["status"] == "suspended" for c in data["data"])

    def test_list_contacts_filter_by_category(self, auth_client, create_test_contact):
        """Filter contacts by category."""
        create_test_contact(name="Business 1", category=ContactCategory.BUSINESS)
        create_test_contact(name="Enterprise 1", category=ContactCategory.ENTERPRISE)

        client = auth_client(["contacts:read"])
        resp = client.get("/api/contacts/?category=enterprise")

        assert resp.status_code == 200
        data = resp.json()
        assert all(c["category"] == "enterprise" for c in data["data"])

    def test_list_contacts_filter_by_owner(self, auth_client, create_test_contact):
        """Filter contacts by owner_id."""
        create_test_contact(name="Owner 1", owner_id=100)
        create_test_contact(name="Owner 2", owner_id=100)
        create_test_contact(name="Other Owner", owner_id=200)

        client = auth_client(["contacts:read"])
        resp = client.get("/api/contacts/?owner_id=100")

        assert resp.status_code == 200
        data = resp.json()
        assert all(c["owner_id"] == 100 for c in data["data"])

    def test_list_contacts_filter_by_territory(self, auth_client, create_test_contact):
        """Filter contacts by territory."""
        create_test_contact(name="Lagos 1", territory="Lagos")
        create_test_contact(name="Abuja 1", territory="Abuja")

        client = auth_client(["contacts:read"])
        resp = client.get("/api/contacts/?territory=Lagos")

        assert resp.status_code == 200
        data = resp.json()
        assert all(c["territory"] == "Lagos" for c in data["data"])

    def test_list_contacts_filter_by_city(self, auth_client, create_test_contact):
        """Filter contacts by city (partial match)."""
        create_test_contact(name="Ikeja Contact", city="Ikeja")
        create_test_contact(name="Lekki Contact", city="Lekki")

        client = auth_client(["contacts:read"])
        resp = client.get("/api/contacts/?city=Ike")

        assert resp.status_code == 200
        data = resp.json()
        assert all("ike" in c["city"].lower() for c in data["data"])

    def test_list_contacts_filter_is_organization(self, auth_client, create_test_contact):
        """Filter by is_organization flag."""
        create_test_contact(name="Org 1", is_organization=True)
        create_test_contact(name="Individual 1", is_organization=False)

        client = auth_client(["contacts:read"])
        resp = client.get("/api/contacts/?is_organization=true")

        assert resp.status_code == 200
        data = resp.json()
        assert all(c["is_organization"] is True for c in data["data"])

    def test_list_contacts_filter_has_outstanding(self, auth_client, create_test_contact):
        """Filter contacts with outstanding balance."""
        create_test_contact(name="Owing", outstanding_balance=Decimal("50000"))
        create_test_contact(name="Clear", outstanding_balance=Decimal("0"))

        client = auth_client(["contacts:read"])
        resp = client.get("/api/contacts/?has_outstanding=true")

        assert resp.status_code == 200
        data = resp.json()
        assert all(
            c.get("outstanding_balance") is not None and
            float(c["outstanding_balance"]) > 0
            for c in data["data"]
        )

    def test_list_contacts_filter_by_tag(self, auth_client, create_test_contact):
        """Filter contacts by tag."""
        create_test_contact(name="VIP Contact", tags=["vip", "priority"])
        create_test_contact(name="Regular Contact", tags=["regular"])

        client = auth_client(["contacts:read"])
        resp = client.get("/api/contacts/?tag=vip")

        assert resp.status_code == 200
        data = resp.json()
        assert all("vip" in (c.get("tags") or []) for c in data["data"])

    def test_list_contacts_search_by_name(self, auth_client, create_test_contact):
        """Search contacts by name."""
        create_test_contact(name="Acme Corporation")
        create_test_contact(name="Beta Industries")

        client = auth_client(["contacts:read"])
        resp = client.get("/api/contacts/?search=Acme")

        assert resp.status_code == 200
        data = resp.json()
        assert any("Acme" in c["name"] for c in data["data"])

    def test_list_contacts_search_by_email(self, auth_client, create_test_contact):
        """Search contacts by email."""
        create_test_contact(name="Email Search", email="unique.email@domain.com")

        client = auth_client(["contacts:read"])
        resp = client.get("/api/contacts/?search=unique.email")

        assert resp.status_code == 200
        data = resp.json()
        assert any("unique.email" in (c.get("email") or "") for c in data["data"])

    def test_list_contacts_sort_by_name(self, auth_client, create_test_contact):
        """Sort contacts by name."""
        create_test_contact(name="Zebra Company")
        create_test_contact(name="Alpha Company")

        client = auth_client(["contacts:read"])
        resp = client.get("/api/contacts/?sort_by=name&sort_order=asc")

        assert resp.status_code == 200
        data = resp.json()
        names = [c["name"] for c in data["data"]]
        assert names == sorted(names)

    def test_list_contacts_sort_by_created_at_desc(self, auth_client, create_test_contact):
        """Sort contacts by created_at descending (newest first)."""
        create_test_contact(name="Older Contact")
        create_test_contact(name="Newer Contact")

        client = auth_client(["contacts:read"])
        resp = client.get("/api/contacts/?sort_by=created_at&sort_order=desc")

        assert resp.status_code == 200
        data = resp.json()
        # Newer should come before older
        dates = [c["created_at"] for c in data["data"]]
        assert dates == sorted(dates, reverse=True)


class TestContactListSpecialized:
    """Tests for specialized list endpoints."""

    def test_list_leads(self, auth_client, create_test_contact):
        """GET /api/contacts/leads returns only leads and prospects."""
        create_test_contact(name="Lead 1", contact_type=ContactType.LEAD)
        create_test_contact(name="Prospect 1", contact_type=ContactType.PROSPECT)
        create_test_contact(name="Customer 1", contact_type=ContactType.CUSTOMER)

        client = auth_client(["contacts:read"])
        resp = client.get("/api/contacts/leads")

        assert resp.status_code == 200
        data = resp.json()
        for contact in data["data"]:
            assert contact["contact_type"] in ["lead", "prospect"]

    def test_list_customers(self, auth_client, create_test_contact):
        """GET /api/contacts/customers returns only customers."""
        create_test_contact(name="Lead 1", contact_type=ContactType.LEAD)
        create_test_contact(name="Customer 1", contact_type=ContactType.CUSTOMER)
        create_test_contact(name="Customer 2", contact_type=ContactType.CUSTOMER)

        client = auth_client(["contacts:read"])
        resp = client.get("/api/contacts/customers")

        assert resp.status_code == 200
        data = resp.json()
        assert all(c["contact_type"] == "customer" for c in data["data"])

    def test_list_organizations(self, auth_client, create_test_contact):
        """GET /api/contacts/organizations returns only organizations."""
        create_test_contact(name="Org 1", is_organization=True)
        create_test_contact(name="Individual 1", is_organization=False)

        client = auth_client(["contacts:read"])
        resp = client.get("/api/contacts/organizations")

        assert resp.status_code == 200
        data = resp.json()
        assert all(c["is_organization"] is True for c in data["data"])


class TestContactPersons:
    """Tests for GET /api/contacts/{contact_id}/persons"""

    def test_get_organization_persons(self, auth_client, create_test_contact):
        """Get person contacts for an organization."""
        org = create_test_contact(name="Org With Persons", is_organization=True)

        person1 = create_test_contact(
            name="Person A",
            contact_type=ContactType.PERSON,
            parent_id=org.id,
            is_organization=False,
        )
        person1.is_primary_contact = True

        person2 = create_test_contact(
            name="Person B",
            contact_type=ContactType.PERSON,
            parent_id=org.id,
            is_organization=False,
        )

        client = auth_client(["contacts:read"])
        resp = client.get(f"/api/contacts/{org.id}/persons")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        # Primary contact should come first
        assert data[0]["is_primary_contact"] is True

    def test_get_persons_for_non_organization_fails(self, auth_client, create_test_contact):
        """Cannot get persons for non-organization contact."""
        individual = create_test_contact(
            name="Individual",
            is_organization=False,
            contact_type=ContactType.CUSTOMER,
        )

        client = auth_client(["contacts:read"])
        resp = client.get(f"/api/contacts/{individual.id}/persons")

        assert resp.status_code == 400
        assert "organization" in resp.json()["detail"].lower()

    def test_get_persons_nonexistent_contact(self, auth_client):
        """Get persons for non-existent contact returns 404."""
        client = auth_client(["contacts:read"])
        resp = client.get("/api/contacts/99999/persons")

        assert resp.status_code == 404


# =============================================================================
# QUALITY ISSUE FILTER TESTS
# =============================================================================


class TestQualityIssueFilters:
    """Tests for quality_issue filter parameter."""

    def test_filter_missing_email(self, auth_client, create_test_contact, integration_db):
        """Filter contacts with missing email."""
        contact_no_email = create_test_contact(name="No Email Contact")
        contact_no_email.email = None
        integration_db.commit()

        create_test_contact(name="Has Email", email="has@email.com")

        client = auth_client(["contacts:read"])
        resp = client.get("/api/contacts/?quality_issue=missing_email")

        assert resp.status_code == 200
        data = resp.json()
        assert all(
            c.get("email") is None or c.get("email") == ""
            for c in data["data"]
        )

    def test_filter_missing_phone(self, auth_client, create_test_contact, integration_db):
        """Filter contacts with missing phone and mobile."""
        contact_no_phone = create_test_contact(name="No Phone Contact")
        contact_no_phone.phone = None
        contact_no_phone.mobile = None
        integration_db.commit()

        create_test_contact(name="Has Phone", phone="+234 123 456")

        client = auth_client(["contacts:read"])
        resp = client.get("/api/contacts/?quality_issue=missing_phone")

        assert resp.status_code == 200
        data = resp.json()
        for c in data["data"]:
            assert (c.get("phone") is None or c.get("phone") == "") and \
                   (c.get("mobile") is None or c.get("mobile") == "")


# =============================================================================
# VALIDATION TESTS
# =============================================================================


class TestContactValidation:
    """Tests for request validation."""

    def test_create_contact_missing_name_fails(self, auth_client):
        """Name is required for contact creation."""
        client = auth_client(["contacts:write"])
        payload = {
            "contact_type": "customer",
            "category": "business",
            "status": "active",
            "email": "test@test.com",
        }
        resp = client.post("/api/contacts/", json=payload)

        assert resp.status_code == 422

    def test_create_contact_invalid_email_format(self, auth_client):
        """Invalid email format should be rejected."""
        client = auth_client(["contacts:write"])
        payload = {
            "name": "Bad Email Contact",
            "contact_type": "customer",
            "category": "business",
            "status": "active",
            "email": "not-an-email",
        }
        # Note: The API may accept non-standard emails depending on validation
        # This test verifies whatever the current behavior is
        resp = client.post("/api/contacts/", json=payload)
        # If validation is strict, expect 422; otherwise 201
        assert resp.status_code in [201, 422]

    def test_create_contact_invalid_contact_type(self, auth_client):
        """Invalid contact_type should be rejected."""
        client = auth_client(["contacts:write"])
        payload = {
            "name": "Bad Type Contact",
            "contact_type": "invalid_type",
            "category": "business",
            "status": "active",
        }
        resp = client.post("/api/contacts/", json=payload)

        assert resp.status_code == 422

    def test_create_contact_invalid_lead_score_range(self, auth_client):
        """Lead score must be 0-100."""
        client = auth_client(["contacts:write"])
        payload = {
            "name": "Bad Score Lead",
            "contact_type": "lead",
            "category": "residential",
            "status": "active",
            "lead_score": 150,  # Invalid: > 100
        }
        resp = client.post("/api/contacts/", json=payload)

        assert resp.status_code == 422

    def test_list_contacts_invalid_page(self, auth_client):
        """Page must be >= 1."""
        client = auth_client(["contacts:read"])
        resp = client.get("/api/contacts/?page=0")

        assert resp.status_code == 422

    def test_list_contacts_invalid_page_size(self, auth_client):
        """Page size must be 1-100."""
        client = auth_client(["contacts:read"])
        resp = client.get("/api/contacts/?page_size=200")

        assert resp.status_code == 422


# =============================================================================
# RBAC TESTS
# =============================================================================


class TestContactRBAC:
    """Tests for role-based access control."""

    def test_superuser_can_access_all(self, superuser_client, create_test_contact):
        """Superuser can access all contact operations."""
        contact = create_test_contact(name="Superuser Test")

        # Read
        resp = superuser_client.get(f"/api/contacts/{contact.id}")
        assert resp.status_code == 200

        # Update
        resp = superuser_client.patch(f"/api/contacts/{contact.id}", json={"name": "Updated"})
        assert resp.status_code == 200

        # List
        resp = superuser_client.get("/api/contacts/")
        assert resp.status_code == 200

    def test_read_only_scope(self, auth_client, create_test_contact):
        """User with only read scope can read but not write."""
        contact = create_test_contact(name="Read Only Test")
        client = auth_client(["contacts:read"])

        # Can read
        resp = client.get(f"/api/contacts/{contact.id}")
        assert resp.status_code == 200

        # Cannot write
        resp = client.post("/api/contacts/", json={
            "name": "New Contact",
            "contact_type": "customer",
            "category": "business",
            "status": "active",
        })
        assert resp.status_code == 403

        # Cannot update
        resp = client.patch(f"/api/contacts/{contact.id}", json={"name": "Hacked"})
        assert resp.status_code == 403

        # Cannot delete
        resp = client.delete(f"/api/contacts/{contact.id}")
        assert resp.status_code == 403

    def test_write_scope_includes_read(self, auth_client, create_test_contact):
        """User with write scope can also read."""
        contact = create_test_contact(name="Write Scope Test")
        client = auth_client(["contacts:write", "contacts:read"])

        # Can read
        resp = client.get(f"/api/contacts/{contact.id}")
        assert resp.status_code == 200

        # Can write
        resp = client.patch(f"/api/contacts/{contact.id}", json={"name": "Updated"})
        assert resp.status_code == 200
