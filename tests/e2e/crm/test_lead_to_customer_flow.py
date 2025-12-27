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

from tests.e2e.conftest import assert_http_ok, assert_http_error, get_json


class TestLeadLifecycle:
    """Test lead lifecycle from creation to qualification."""

    def test_create_lead(self, e2e_superuser_client, e2e_db):
        """Test lead creation via API."""
        payload = {
            "lead_name": "E2E Test Lead",
            "company_name": "Test Company Ltd",
            "email_id": "lead@testcompany.com",
            "phone": "+2348012345678",
            "source": "Website",
            "territory": "Lagos",
            "industry": "Technology",
        }

        response = e2e_superuser_client.post("/api/crm/leads", json=payload)
        assert_http_ok(response, "Create lead")

        data = get_json(response)
        assert data["lead_name"] == "E2E Test Lead"
        assert data["status"] == "lead"
        assert data["converted"] is False

        # Store for cleanup
        self._lead_id = data["id"]

    def test_lead_listing(self, e2e_superuser_client, e2e_db):
        """Test lead listing and filtering."""
        # Create a lead first
        payload = {
            "lead_name": "List Test Lead",
            "email_id": "listtest@example.com",
        }
        create_resp = e2e_superuser_client.post("/api/crm/leads", json=payload)
        assert_http_ok(create_resp, "Create lead for listing")

        # List all leads
        response = e2e_superuser_client.get("/api/crm/leads")
        assert_http_ok(response, "List leads")

        data = get_json(response)
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_qualify_lead(self, e2e_superuser_client, e2e_db):
        """Test lead qualification workflow."""
        # Create lead
        payload = {"lead_name": "Qualify Test Lead", "email_id": "qualify@test.com"}
        create_resp = e2e_superuser_client.post("/api/crm/leads", json=payload)
        lead = get_json(create_resp)
        lead_id = lead["id"]

        # Qualify the lead
        response = e2e_superuser_client.post(f"/api/crm/leads/{lead_id}/qualify")
        assert_http_ok(response, "Qualify lead")

        result = get_json(response)
        assert result["success"] is True

        # Verify status changed
        verify_resp = e2e_superuser_client.get(f"/api/crm/leads/{lead_id}")
        verified = get_json(verify_resp)
        assert verified["status"] == "opportunity"
        assert verified["qualification_status"] == "qualified"

    def test_disqualify_lead(self, e2e_superuser_client, e2e_db):
        """Test lead disqualification."""
        # Create lead
        payload = {"lead_name": "Disqualify Test Lead", "email_id": "disqual@test.com"}
        create_resp = e2e_superuser_client.post("/api/crm/leads", json=payload)
        lead = get_json(create_resp)
        lead_id = lead["id"]

        # Disqualify with reason
        response = e2e_superuser_client.post(
            f"/api/crm/leads/{lead_id}/disqualify",
            params={"reason": "No budget"},
        )
        assert_http_ok(response, "Disqualify lead")

        result = get_json(response)
        assert result["success"] is True

        # Verify status changed
        verify_resp = e2e_superuser_client.get(f"/api/crm/leads/{lead_id}")
        verified = get_json(verify_resp)
        assert verified["status"] == "do_not_contact"


class TestLeadConversion:
    """Test lead to customer conversion."""

    def test_convert_lead_to_customer(self, e2e_superuser_client, e2e_db):
        """Test full lead conversion to customer."""
        # Create lead
        payload = {
            "lead_name": "Convert Test Lead",
            "company_name": "Convertible Ltd",
            "email_id": "convert@test.com",
            "phone": "+2348099999999",
            "city": "Lagos",
        }
        create_resp = e2e_superuser_client.post("/api/crm/leads", json=payload)
        lead = get_json(create_resp)
        lead_id = lead["id"]

        # Convert lead to customer
        convert_payload = {
            "customer_name": "Converted Customer Ltd",
            "customer_type": "business",
            "create_opportunity": False,
        }
        response = e2e_superuser_client.post(
            f"/api/crm/leads/{lead_id}/convert",
            json=convert_payload,
        )
        assert_http_ok(response, "Convert lead")

        result = get_json(response)
        assert result["success"] is True
        assert result["customer_id"] is not None
        assert result["contact_id"] is not None

        # Verify lead marked as converted
        verify_resp = e2e_superuser_client.get(f"/api/crm/leads/{lead_id}")
        verified = get_json(verify_resp)
        assert verified["converted"] is True
        assert verified["status"] == "converted"

        # Verify customer exists
        customer_id = result["customer_id"]
        customer_resp = e2e_superuser_client.get(f"/api/customers/{customer_id}")
        assert_http_ok(customer_resp, "Get created customer")

    def test_convert_lead_with_opportunity(self, e2e_superuser_client, e2e_db):
        """Test lead conversion with opportunity creation."""
        # Create lead
        payload = {
            "lead_name": "Opp Convert Lead",
            "company_name": "Big Deal Ltd",
            "email_id": "bigdeal@test.com",
        }
        create_resp = e2e_superuser_client.post("/api/crm/leads", json=payload)
        lead = get_json(create_resp)
        lead_id = lead["id"]

        # Convert with opportunity
        convert_payload = {
            "customer_name": "Big Deal Customer",
            "customer_type": "enterprise",
            "create_opportunity": True,
            "opportunity_name": "Big Enterprise Deal",
            "deal_value": 5000000.0,
        }
        response = e2e_superuser_client.post(
            f"/api/crm/leads/{lead_id}/convert",
            json=convert_payload,
        )
        assert_http_ok(response, "Convert lead with opportunity")

        result = get_json(response)
        assert result["success"] is True
        assert result["opportunity_id"] is not None

        # Verify opportunity exists
        opp_id = result["opportunity_id"]
        opp_resp = e2e_superuser_client.get(f"/api/crm/opportunities/{opp_id}")
        assert_http_ok(opp_resp, "Get created opportunity")

        opp_data = get_json(opp_resp)
        assert opp_data["name"] == "Big Enterprise Deal"
        assert float(opp_data["deal_value"]) == 5000000.0

    def test_cannot_convert_already_converted(self, e2e_superuser_client, e2e_db):
        """Test that already converted leads cannot be converted again."""
        # Create and convert lead
        payload = {"lead_name": "Double Convert Lead", "email_id": "double@test.com"}
        create_resp = e2e_superuser_client.post("/api/crm/leads", json=payload)
        lead = get_json(create_resp)
        lead_id = lead["id"]

        # First conversion
        e2e_superuser_client.post(
            f"/api/crm/leads/{lead_id}/convert",
            json={"customer_type": "business"},
        )

        # Second conversion should fail
        response = e2e_superuser_client.post(
            f"/api/crm/leads/{lead_id}/convert",
            json={"customer_type": "business"},
        )
        assert_http_error(response, 400, "Double conversion should fail")


class TestOpportunityPipeline:
    """Test opportunity pipeline progression."""

    def test_create_opportunity(self, e2e_superuser_client, e2e_db):
        """Test opportunity creation."""
        # First create a customer
        from tests.e2e.fixtures.factories import create_customer
        customer = create_customer(e2e_db, name="Opp Test Customer")

        payload = {
            "name": "Test Opportunity",
            "customer_id": customer.id,
            "stage": "New",
            "deal_value": 100000.0,
            "probability": 20,
            "expected_close_date": (date.today() + timedelta(days=30)).isoformat(),
        }

        response = e2e_superuser_client.post("/api/crm/opportunities/", json=payload)
        assert_http_ok(response, "Create opportunity")

        data = get_json(response)
        assert data["name"] == "Test Opportunity"
        assert data["stage"] == "New"

    def test_opportunity_pipeline_stages(self, e2e_superuser_client, e2e_db):
        """Test opportunity progression through pipeline stages."""
        from tests.e2e.fixtures.factories import create_customer
        customer = create_customer(e2e_db, name="Pipeline Test Customer")

        # Create opportunity
        payload = {
            "name": "Pipeline Test Opp",
            "customer_id": customer.id,
            "stage": "New",
            "deal_value": 250000.0,
            "expected_close_date": (date.today() + timedelta(days=60)).isoformat(),
        }
        create_resp = e2e_superuser_client.post("/api/crm/opportunities/", json=payload)
        opp = get_json(create_resp)
        opp_id = opp["id"]

        # Progress through stages
        stages = ["Qualification", "Proposal", "Negotiation"]

        for stage in stages:
            update_resp = e2e_superuser_client.patch(
                f"/api/crm/opportunities/{opp_id}",
                json={"stage": stage},
            )
            assert_http_ok(update_resp, f"Update to {stage}")

            verify_resp = e2e_superuser_client.get(f"/api/crm/opportunities/{opp_id}")
            verified = get_json(verify_resp)
            assert verified["stage"] == stage

    def test_win_opportunity(self, e2e_superuser_client, e2e_db):
        """Test winning an opportunity."""
        from tests.e2e.fixtures.factories import create_customer
        customer = create_customer(e2e_db, name="Win Test Customer")

        # Create opportunity
        payload = {
            "name": "Win Test Opp",
            "customer_id": customer.id,
            "stage": "Negotiation",
            "deal_value": 500000.0,
            "expected_close_date": date.today().isoformat(),
        }
        create_resp = e2e_superuser_client.post("/api/crm/opportunities/", json=payload)
        opp = get_json(create_resp)
        opp_id = opp["id"]

        # Mark as won
        response = e2e_superuser_client.patch(
            f"/api/crm/opportunities/{opp_id}",
            json={"stage": "Won", "status": "won"},
        )
        assert_http_ok(response, "Win opportunity")

        data = get_json(response)
        assert data["stage"] == "Won"

    def test_lose_opportunity(self, e2e_superuser_client, e2e_db):
        """Test losing an opportunity."""
        from tests.e2e.fixtures.factories import create_customer
        customer = create_customer(e2e_db, name="Lose Test Customer")

        # Create opportunity
        payload = {
            "name": "Lose Test Opp",
            "customer_id": customer.id,
            "stage": "Proposal",
            "deal_value": 300000.0,
            "expected_close_date": date.today().isoformat(),
        }
        create_resp = e2e_superuser_client.post("/api/crm/opportunities/", json=payload)
        opp = get_json(create_resp)
        opp_id = opp["id"]

        # Mark as lost
        response = e2e_superuser_client.patch(
            f"/api/crm/opportunities/{opp_id}",
            json={"stage": "Lost", "status": "lost"},
        )
        assert_http_ok(response, "Lose opportunity")

        data = get_json(response)
        assert data["stage"] == "Lost"


class TestLeadSummary:
    """Test lead analytics and summary endpoints."""

    def test_leads_summary(self, e2e_superuser_client, e2e_db):
        """Test lead summary statistics."""
        # Create some leads in different states
        leads_data = [
            {"lead_name": "Summary Lead 1", "email_id": "summary1@test.com"},
            {"lead_name": "Summary Lead 2", "email_id": "summary2@test.com"},
            {"lead_name": "Summary Lead 3", "email_id": "summary3@test.com"},
        ]

        lead_ids = []
        for payload in leads_data:
            resp = e2e_superuser_client.post("/api/crm/leads", json=payload)
            lead = get_json(resp)
            lead_ids.append(lead["id"])

        # Qualify one lead
        e2e_superuser_client.post(f"/api/crm/leads/{lead_ids[1]}/qualify")

        # Get summary
        response = e2e_superuser_client.get("/api/crm/leads/summary")
        assert_http_ok(response, "Get leads summary")

        data = get_json(response)
        assert "total_leads" in data
        assert "new_leads" in data
        assert "qualified_leads" in data
        assert "by_status" in data
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
        # Step 1: Create Lead
        lead_payload = {
            "lead_name": "Full Cycle Lead",
            "company_name": "Full Cycle Corp",
            "email_id": "fullcycle@test.com",
            "phone": "+2348011111111",
            "source": "Referral",
            "industry": "Finance",
        }
        lead_resp = e2e_superuser_client.post("/api/crm/leads", json=lead_payload)
        assert_http_ok(lead_resp, "Step 1: Create lead")
        lead = get_json(lead_resp)
        lead_id = lead["id"]

        # Step 2: Qualify Lead
        qual_resp = e2e_superuser_client.post(f"/api/crm/leads/{lead_id}/qualify")
        assert_http_ok(qual_resp, "Step 2: Qualify lead")

        # Step 3: Convert to Customer with Opportunity
        convert_payload = {
            "customer_name": "Full Cycle Customer Corp",
            "customer_type": "enterprise",
            "create_opportunity": True,
            "opportunity_name": "Full Cycle Enterprise Deal",
            "deal_value": 10000000.0,
        }
        convert_resp = e2e_superuser_client.post(
            f"/api/crm/leads/{lead_id}/convert",
            json=convert_payload,
        )
        assert_http_ok(convert_resp, "Step 3: Convert lead")
        convert_result = get_json(convert_resp)
        customer_id = convert_result["customer_id"]
        opp_id = convert_result["opportunity_id"]

        # Step 4: Progress Opportunity through stages
        stages = ["Qualification", "Proposal", "Negotiation"]
        for stage in stages:
            stage_resp = e2e_superuser_client.patch(
                f"/api/crm/opportunities/{opp_id}",
                json={"stage": stage},
            )
            assert_http_ok(stage_resp, f"Step 4: Progress to {stage}")

        # Step 5: Win Opportunity
        win_resp = e2e_superuser_client.patch(
            f"/api/crm/opportunities/{opp_id}",
            json={"stage": "Won", "status": "won"},
        )
        assert_http_ok(win_resp, "Step 5: Win opportunity")

        # Final Verification
        # - Lead should be converted
        lead_check = e2e_superuser_client.get(f"/api/crm/leads/{lead_id}")
        lead_final = get_json(lead_check)
        assert lead_final["converted"] is True

        # - Customer should exist
        customer_check = e2e_superuser_client.get(f"/api/customers/{customer_id}")
        assert_http_ok(customer_check, "Customer exists")

        # - Opportunity should be won
        opp_check = e2e_superuser_client.get(f"/api/crm/opportunities/{opp_id}")
        opp_final = get_json(opp_check)
        assert opp_final["stage"] == "Won"
