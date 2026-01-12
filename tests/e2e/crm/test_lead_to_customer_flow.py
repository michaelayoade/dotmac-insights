"""
E2E Tests: CRM Lead-to-Customer Flow

Tests the complete sales cycle from lead creation through conversion to customer.

Flow:
1. Create Lead
2. Qualify Lead
3. Convert Lead to Customer
4. Create Opportunity
5. Progress Opportunity through pipeline
6. Win/Lose Opportunity
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta

from tests.e2e.conftest import assert_http_ok, assert_http_error, get_json, assert_response_schema

# Apply module marker
pytestmark = pytest.mark.crm


class TestLeadLifecycle:
    """Test lead lifecycle from creation to qualification."""

    def test_create_lead(self, e2e_superuser_client, e2e_db):
        """Test lead creation via API."""
        payload = {
            "name": "E2E Test Lead",
            "type": "organization",
            "primary_email": "lead@testcompany.com",
            "primary_phone": "+2348012345678",
            "source": "Website",
        }

        response = e2e_superuser_client.post("/api/v1/crm/leads", json=payload)
        assert_http_ok(response, "Create lead")

        data = get_json(response)
        assert data["name"] == "E2E Test Lead"
        assert data["status"] == "active"

        # Store for cleanup
        self._lead_id = data["party_id"]

    def test_lead_listing(self, e2e_superuser_client, e2e_db):
        """Test lead listing and filtering."""
        # Create a lead first
        payload = {
            "name": "List Test Lead",
            "primary_email": "listtest@example.com",
        }
        create_resp = e2e_superuser_client.post("/api/v1/crm/leads", json=payload)
        assert_http_ok(create_resp, "Create lead for listing")

        # List all leads
        response = e2e_superuser_client.get("/api/v1/crm/leads")
        assert_http_ok(response, "List leads")

        data = get_json(response)
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_qualify_lead(self, e2e_superuser_client, e2e_db):
        """Test lead qualification workflow."""
        # Create lead
        payload = {"name": "Qualify Test Lead", "primary_email": "qualify@test.com"}
        create_resp = e2e_superuser_client.post("/api/v1/crm/leads", json=payload)
        lead = get_json(create_resp)
        lead_id = lead["party_id"]

        # Qualify the lead
        response = e2e_superuser_client.post(
            f"/api/v1/crm/leads/{lead_id}/qualify",
            json={"qualification": "qualified"},
        )
        assert_http_ok(response, "Qualify lead")

        result = get_json(response)
        assert result["qualification"] == "qualified"

        # Verify status changed
        verify_resp = e2e_superuser_client.get(f"/api/v1/crm/leads/{lead_id}")
        verified = get_json(verify_resp)
        assert verified["qualification"] == "qualified"
        assert verified["status"] == "active"

    def test_disqualify_lead(self, e2e_superuser_client, e2e_db):
        """Test lead disqualification."""
        # Create lead
        payload = {"name": "Disqualify Test Lead", "primary_email": "disqual@test.com"}
        create_resp = e2e_superuser_client.post("/api/v1/crm/leads", json=payload)
        lead = get_json(create_resp)
        lead_id = lead["party_id"]

        # Disqualify with reason
        response = e2e_superuser_client.post(
            f"/api/v1/crm/leads/{lead_id}/disqualify",
            json={"reason": "No budget"},
        )
        assert_http_ok(response, "Disqualify lead")

        result = get_json(response)
        assert result["qualification"] == "disqualified"
        assert result["status"] == "inactive"

        # Verify status changed
        verify_resp = e2e_superuser_client.get(f"/api/v1/crm/leads/{lead_id}")
        verified = get_json(verify_resp)
        assert verified["qualification"] == "disqualified"
        assert verified["status"] == "inactive"


class TestLeadConversion:
    """Test lead to customer conversion."""

    def test_convert_lead_to_customer(self, e2e_superuser_client, e2e_db):
        """Test full lead conversion to customer."""
        # Create lead
        payload = {
            "name": "Convert Test Lead",
            "type": "organization",
            "primary_email": "convert@test.com",
            "primary_phone": "+2348099999999",
        }
        create_resp = e2e_superuser_client.post("/api/v1/crm/leads", json=payload)
        lead = get_json(create_resp)
        lead_id = lead["party_id"]

        # Convert lead to customer
        response = e2e_superuser_client.post(
            f"/api/v1/crm/leads/{lead_id}/convert/customer",
            json={},
        )
        assert_http_ok(response, "Convert lead")

        result = get_json(response)
        assert result["id"] is not None

        # Verify lead marked as converted
        verify_resp = e2e_superuser_client.get(f"/api/v1/crm/leads/{lead_id}")
        verified = get_json(verify_resp)
        assert verified["qualification"] == "converted"

        # Verify customer exists
        customer_party_id = result["id"]
        customer_resp = e2e_superuser_client.get(
            f"/api/v1/crm/parties/{customer_party_id}",
            params={"include_roles": True},
        )
        assert_http_ok(customer_resp, "Get created customer")
        customer_data = get_json(customer_resp)
        assert customer_data["id"] == customer_party_id
        assert any(role["role"] == "customer" for role in (customer_data.get("roles") or []))

    def test_convert_lead_with_opportunity(self, e2e_superuser_client, e2e_db):
        """Test lead conversion with opportunity creation."""
        # Create lead
        payload = {
            "name": "Opp Convert Lead",
            "type": "organization",
            "primary_email": "bigdeal@test.com",
        }
        create_resp = e2e_superuser_client.post("/api/v1/crm/leads", json=payload)
        lead = get_json(create_resp)
        lead_id = lead["party_id"]

        # Convert to opportunity
        convert_payload = {
            "opportunity_name": "Big Enterprise Deal",
            "deal_value": 5000000.0,
        }
        response = e2e_superuser_client.post(
            f"/api/v1/crm/leads/{lead_id}/convert/opportunity",
            json=convert_payload,
        )
        assert_http_ok(response, "Convert lead with opportunity")

        result = get_json(response)
        assert result["id"] is not None

        # Verify opportunity exists
        opp_id = result["id"]
        opp_resp = e2e_superuser_client.get(f"/api/v1/crm/opportunities/{opp_id}")
        assert_http_ok(opp_resp, "Get created opportunity")

        opp_data = get_json(opp_resp)
        assert opp_data["name"] == "Big Enterprise Deal"
        assert float(opp_data["deal_value"]) == 5000000.0

    def test_cannot_convert_already_converted(self, e2e_superuser_client, e2e_db):
        """Test that already converted leads cannot be converted again."""
        # Create and convert lead
        payload = {"name": "Double Convert Lead", "primary_email": "double@test.com"}
        create_resp = e2e_superuser_client.post("/api/v1/crm/leads", json=payload)
        lead = get_json(create_resp)
        lead_id = lead["party_id"]

        # First conversion
        e2e_superuser_client.post(
            f"/api/v1/crm/leads/{lead_id}/convert/customer",
            json={},
        )

        # Second conversion should fail
        response = e2e_superuser_client.post(
            f"/api/v1/crm/leads/{lead_id}/convert/customer",
            json={},
        )
        assert_http_error(response, 400, "Double conversion should fail")


class TestOpportunityPipeline:
    """Test opportunity pipeline progression."""

    def test_create_opportunity(self, e2e_superuser_client, e2e_db):
        """Test opportunity creation."""
        from tests.e2e.fixtures.factories import create_customer, get_or_create_opportunity_stage
        customer = create_customer(e2e_db, name="Opp Test Customer")
        stage = get_or_create_opportunity_stage(e2e_db, name="New", sequence=1, probability=10)

        payload = {
            "name": "Test Opportunity",
            "party_id": customer.party_id,
            "stage_id": stage.id,
            "deal_value": 100000.0,
            "probability": 20,
            "expected_close_date": (date.today() + timedelta(days=30)).isoformat(),
        }

        response = e2e_superuser_client.post("/api/v1/crm/opportunities/", json=payload)
        assert_http_ok(response, "Create opportunity")

        data = get_json(response)
        assert data["name"] == "Test Opportunity"
        assert data["stage"]["name"] == "New"

    def test_opportunity_pipeline_stages(self, e2e_superuser_client, e2e_db):
        """Test opportunity progression through pipeline stages."""
        from tests.e2e.fixtures.factories import create_customer, get_or_create_opportunity_stage
        customer = create_customer(e2e_db, name="Pipeline Test Customer")

        # Get or create stages (shared resources)
        new_stage = get_or_create_opportunity_stage(e2e_db, name="New", sequence=1, probability=10)
        qual_stage = get_or_create_opportunity_stage(e2e_db, name="Qualification", sequence=2, probability=30)

        # Create opportunity
        payload = {
            "name": "Pipeline Test Opp",
            "party_id": customer.party_id,
            "stage_id": new_stage.id,
            "deal_value": 250000.0,
            "expected_close_date": (date.today() + timedelta(days=60)).isoformat(),
        }
        create_resp = e2e_superuser_client.post("/api/v1/crm/opportunities/", json=payload)
        opp = get_json(create_resp)
        opp_id = opp["id"]

        # Progress to Qualification stage
        update_resp = e2e_superuser_client.patch(
            f"/api/v1/crm/opportunities/{opp_id}",
            json={"stage_id": qual_stage.id},
        )
        assert_http_ok(update_resp, "Update to Qualification")

        verify_resp = e2e_superuser_client.get(f"/api/v1/crm/opportunities/{opp_id}")
        verified = get_json(verify_resp)
        assert verified["stage"]["name"] == "Qualification"

    def test_win_opportunity(self, e2e_superuser_client, e2e_db):
        """Test winning an opportunity."""
        from tests.e2e.fixtures.factories import create_customer, get_or_create_opportunity_stage
        customer = create_customer(e2e_db, name="Win Test Customer")
        neg_stage = get_or_create_opportunity_stage(e2e_db, name="Negotiation", sequence=4, probability=70)
        won_stage = get_or_create_opportunity_stage(e2e_db, name="Won", sequence=10, probability=100, is_won=True)

        # Create opportunity
        payload = {
            "name": "Win Test Opp",
            "party_id": customer.party_id,
            "stage_id": neg_stage.id,
            "deal_value": 500000.0,
            "expected_close_date": date.today().isoformat(),
        }
        create_resp = e2e_superuser_client.post("/api/v1/crm/opportunities/", json=payload)
        opp = get_json(create_resp)
        opp_id = opp["id"]

        # Mark as won
        response = e2e_superuser_client.patch(
            f"/api/v1/crm/opportunities/{opp_id}",
            json={"stage_id": won_stage.id, "status": "won"},
        )
        assert_http_ok(response, "Win opportunity")

        data = get_json(response)
        assert data["stage"]["name"] == "Won"

    def test_lose_opportunity(self, e2e_superuser_client, e2e_db):
        """Test losing an opportunity."""
        from tests.e2e.fixtures.factories import create_customer, get_or_create_opportunity_stage
        customer = create_customer(e2e_db, name="Lose Test Customer")
        proposal_stage = get_or_create_opportunity_stage(e2e_db, name="Proposal", sequence=3, probability=50)
        lost_stage = get_or_create_opportunity_stage(e2e_db, name="Lost", sequence=11, probability=0, is_lost=True)

        # Create opportunity
        payload = {
            "name": "Lose Test Opp",
            "party_id": customer.party_id,
            "stage_id": proposal_stage.id,
            "deal_value": 300000.0,
            "expected_close_date": date.today().isoformat(),
        }
        create_resp = e2e_superuser_client.post("/api/v1/crm/opportunities/", json=payload)
        opp = get_json(create_resp)
        opp_id = opp["id"]

        # Mark as lost
        response = e2e_superuser_client.patch(
            f"/api/v1/crm/opportunities/{opp_id}",
            json={"stage_id": lost_stage.id, "status": "lost"},
        )
        assert_http_ok(response, "Lose opportunity")

        data = get_json(response)
        assert data["stage"]["name"] == "Lost"


class TestLeadSummary:
    """Test lead analytics and summary endpoints."""

    def test_leads_summary(self, e2e_superuser_client, e2e_db):
        """Test lead summary statistics."""
        # Create some leads in different states
        leads_data = [
            {"name": "Summary Lead 1", "primary_email": "summary1@test.com"},
            {"name": "Summary Lead 2", "primary_email": "summary2@test.com"},
            {"name": "Summary Lead 3", "primary_email": "summary3@test.com"},
        ]

        lead_ids = []
        for payload in leads_data:
            resp = e2e_superuser_client.post("/api/v1/crm/leads", json=payload)
            lead = get_json(resp)
            lead_ids.append(lead["party_id"])

        # Qualify one lead
        e2e_superuser_client.post(
            f"/api/v1/crm/leads/{lead_ids[1]}/qualify",
            json={"qualification": "qualified"},
        )

        # Get summary
        response = e2e_superuser_client.get("/api/v1/crm/leads/summary")
        assert_http_ok(response, "Get leads summary")

        data = get_json(response)
        assert "total_leads" in data
        assert "active_leads" in data
        assert "qualified_leads" in data
        assert "by_source" in data
        assert data["total_leads"] >= 3


class TestFullSalesCycle:
    """Test complete sales cycle end-to-end."""

    def test_complete_sales_cycle(self, e2e_superuser_client, e2e_db):
        """
        Test complete flow:
        1. Create lead
        2. Qualify lead
        3. Convert to customer with opportunity
        4. Progress opportunity
        5. Win opportunity
        """
        from tests.e2e.fixtures.factories import get_or_create_opportunity_stage

        # Get or create pipeline stages (shared resources)
        qual_stage = get_or_create_opportunity_stage(e2e_db, name="Qualification", sequence=2, probability=30)
        proposal_stage = get_or_create_opportunity_stage(e2e_db, name="Proposal", sequence=3, probability=50)
        neg_stage = get_or_create_opportunity_stage(e2e_db, name="Negotiation", sequence=4, probability=70)
        won_stage = get_or_create_opportunity_stage(e2e_db, name="Won", sequence=10, probability=100, is_won=True)

        # Step 1: Create Lead
        lead_payload = {
            "name": "Full Cycle Lead",
            "type": "organization",
            "primary_email": "fullcycle@test.com",
            "primary_phone": "+2348011111111",
            "source": "Referral",
        }
        lead_resp = e2e_superuser_client.post("/api/v1/crm/leads", json=lead_payload)
        assert_http_ok(lead_resp, "Step 1: Create lead")
        lead = get_json(lead_resp)
        lead_id = lead["party_id"]

        # Step 2: Qualify Lead
        qual_resp = e2e_superuser_client.post(
            f"/api/v1/crm/leads/{lead_id}/qualify",
            json={"qualification": "qualified"},
        )
        assert_http_ok(qual_resp, "Step 2: Qualify lead")

        # Step 3: Convert to Opportunity and Customer
        convert_payload = {
            "opportunity_name": "Full Cycle Enterprise Deal",
            "deal_value": 10000000.0,
        }
        convert_resp = e2e_superuser_client.post(
            f"/api/v1/crm/leads/{lead_id}/convert/opportunity",
            json=convert_payload,
        )
        assert_http_ok(convert_resp, "Step 3: Convert lead to opportunity")
        convert_result = get_json(convert_resp)
        opp_id = convert_result["id"]

        customer_resp = e2e_superuser_client.post(
            f"/api/v1/crm/leads/{lead_id}/convert/customer",
            json={},
        )
        assert_http_ok(customer_resp, "Step 3: Convert lead to customer")
        customer_id = get_json(customer_resp)["id"]

        # Step 4: Progress Opportunity through stages
        stage_ids = [qual_stage.id, proposal_stage.id, neg_stage.id]
        stage_names = ["Qualification", "Proposal", "Negotiation"]
        for stage_id, stage_name in zip(stage_ids, stage_names):
            stage_resp = e2e_superuser_client.patch(
                f"/api/v1/crm/opportunities/{opp_id}",
                json={"stage_id": stage_id},
            )
            assert_http_ok(stage_resp, f"Step 4: Progress to {stage_name}")

        # Step 5: Win Opportunity
        win_resp = e2e_superuser_client.patch(
            f"/api/v1/crm/opportunities/{opp_id}",
            json={"stage_id": won_stage.id, "status": "won"},
        )
        assert_http_ok(win_resp, "Step 5: Win opportunity")

        # Final Verification
        # - Lead should be converted
        lead_check = e2e_superuser_client.get(f"/api/v1/crm/leads/{lead_id}")
        lead_final = get_json(lead_check)
        assert lead_final["qualification"] == "converted"

        # - Customer should exist
        customer_check = e2e_superuser_client.get(f"/api/v1/crm/parties/{customer_id}")
        assert_http_ok(customer_check, "Customer exists")

        # - Opportunity should be won
        opp_check = e2e_superuser_client.get(f"/api/v1/crm/opportunities/{opp_id}")
        opp_final = get_json(opp_check)
        assert opp_final["stage"]["name"] == "Won"
