"""
Marketing API Integration Tests

Covers CRUD + RBAC for marketing campaigns, journeys, social, email, audiences,
integrations, and consent endpoints.
"""
from __future__ import annotations

import pytest

from app.config import settings
from app.models.marketing import ConsentChannel
from app.services.marketing.consent_service import create_unsubscribe_token

from app.database import Base
from app.models.party import Party, PartyType, PartyStatus


pytestmark = [pytest.mark.integration, pytest.mark.marketing]


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def marketing_client(auth_client):
    return auth_client(["marketing:read", "marketing:write"])


@pytest.fixture
def marketing_read_client(auth_client):
    return auth_client(["marketing:read"])


@pytest.fixture
def no_scope_client(auth_client):
    return auth_client(["accounting:read"])


@pytest.fixture
def public_client(unauthenticated_client):
    return unauthenticated_client


@pytest.fixture
def ensure_marketing_tables(integration_db):
    Base.metadata.create_all(bind=integration_db.get_bind())
    return integration_db


@pytest.fixture
def create_party(ensure_marketing_tables):
    def _create_party(name: str = "Test Party") -> Party:
        party = Party(
            type=PartyType.PERSON.value,
            status=PartyStatus.ACTIVE.value,
            name=name,
            primary_email="test@example.com",
        )
        ensure_marketing_tables.add(party)
        ensure_marketing_tables.commit()
        ensure_marketing_tables.refresh(party)
        return party

    return _create_party


# =============================================================================
# DASHBOARD + RBAC
# =============================================================================


def test_dashboard_requires_scope(no_scope_client, ensure_marketing_tables):
    response = no_scope_client.get("/api/v1/marketing/dashboard")
    assert response.status_code in [401, 403]


def test_dashboard_returns_payload(marketing_read_client, ensure_marketing_tables):
    response = marketing_read_client.get("/api/v1/marketing/dashboard")
    assert response.status_code == 200
    payload = response.json()
    assert "stats" in payload
    assert "upcoming_sends" in payload
    assert "journeys" in payload


def test_write_requires_scope(marketing_read_client, ensure_marketing_tables):
    response = marketing_read_client.post(
        "/api/v1/marketing/campaigns",
        json={
            "name": "Launch",
            "campaign_type": "multi_channel",
        },
    )
    assert response.status_code in [401, 403]


# =============================================================================
# CAMPAIGNS
# =============================================================================


def test_campaign_crud(marketing_client, ensure_marketing_tables):
    create_resp = marketing_client.post(
        "/api/v1/marketing/campaigns",
        json={
            "name": "Launch Campaign",
            "campaign_type": "multi_channel",
            "status": "draft",
            "budget": "1500.00",
            "currency": "NGN",
        },
    )
    assert create_resp.status_code == 200
    campaign = create_resp.json()

    get_resp = marketing_client.get(f"/api/v1/marketing/campaigns/{campaign['id']}")
    assert get_resp.status_code == 200

    update_resp = marketing_client.patch(
        f"/api/v1/marketing/campaigns/{campaign['id']}",
        json={"status": "active"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "active"

    delete_resp = marketing_client.delete(f"/api/v1/marketing/campaigns/{campaign['id']}")
    assert delete_resp.status_code == 200


# =============================================================================
# JOURNEYS + TEMPLATES + STEPS
# =============================================================================


def test_journey_template_and_journey_crud(marketing_client, ensure_marketing_tables):
    template_resp = marketing_client.post(
        "/api/v1/marketing/journeys/templates",
        json={"name": "Onboarding", "category": "onboarding"},
    )
    assert template_resp.status_code == 200
    template = template_resp.json()

    journey_resp = marketing_client.post(
        "/api/v1/marketing/journeys",
        json={
            "name": "Welcome Journey",
            "template_id": template["id"],
            "status": "draft",
        },
    )
    assert journey_resp.status_code == 200
    journey = journey_resp.json()

    update_resp = marketing_client.patch(
        f"/api/v1/marketing/journeys/{journey['id']}",
        json={"status": "active"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "active"

    delete_resp = marketing_client.delete(f"/api/v1/marketing/journeys/{journey['id']}")
    assert delete_resp.status_code == 200


def test_journey_step_crud(marketing_client, ensure_marketing_tables):
    journey_resp = marketing_client.post(
        "/api/v1/marketing/journeys",
        json={"name": "Step Journey", "status": "draft"},
    )
    assert journey_resp.status_code == 200
    journey_id = journey_resp.json()["id"]

    step_resp = marketing_client.post(
        "/api/v1/marketing/journeys/steps",
        json={
            "journey_id": journey_id,
            "step_order": 1,
            "step_type": "email",
            "name": "Welcome Email",
        },
    )
    assert step_resp.status_code == 200
    step_id = step_resp.json()["id"]

    update_resp = marketing_client.patch(
        f"/api/v1/marketing/journeys/steps/{step_id}",
        json={"name": "Updated Email"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Updated Email"

    delete_resp = marketing_client.delete(f"/api/v1/marketing/journeys/steps/{step_id}")
    assert delete_resp.status_code == 200


# =============================================================================
# SOCIAL
# =============================================================================


def test_social_account_and_post_crud(marketing_client, ensure_marketing_tables):
    account_resp = marketing_client.post(
        "/api/v1/marketing/social/accounts",
        json={"platform": "facebook", "account_id": "fb-123"},
    )
    assert account_resp.status_code == 200
    account_id = account_resp.json()["id"]

    post_resp = marketing_client.post(
        "/api/v1/marketing/social/posts",
        json={
            "account_id": account_id,
            "content": "Hello world",
            "status": "draft",
        },
    )
    assert post_resp.status_code == 200
    post_id = post_resp.json()["id"]

    update_resp = marketing_client.patch(
        f"/api/v1/marketing/social/posts/{post_id}",
        json={"status": "scheduled"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "scheduled"

    delete_resp = marketing_client.delete(f"/api/v1/marketing/social/posts/{post_id}")
    assert delete_resp.status_code == 200

    account_delete = marketing_client.delete(f"/api/v1/marketing/social/accounts/{account_id}")
    assert account_delete.status_code == 200


# =============================================================================
# EMAIL
# =============================================================================


def test_email_template_and_campaign_crud(marketing_client, ensure_marketing_tables):
    template_resp = marketing_client.post(
        "/api/v1/marketing/email/templates",
        json={"name": "Welcome Template", "subject": "Hello"},
    )
    assert template_resp.status_code == 200
    template_id = template_resp.json()["id"]

    campaign_resp = marketing_client.post(
        "/api/v1/marketing/email/campaigns",
        json={
            "name": "Welcome Campaign",
            "template_id": template_id,
            "status": "draft",
        },
    )
    assert campaign_resp.status_code == 200
    campaign_id = campaign_resp.json()["id"]

    update_resp = marketing_client.patch(
        f"/api/v1/marketing/email/campaigns/{campaign_id}",
        json={"status": "scheduled"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "scheduled"

    delete_campaign = marketing_client.delete(f"/api/v1/marketing/email/campaigns/{campaign_id}")
    assert delete_campaign.status_code == 200

    delete_template = marketing_client.delete(f"/api/v1/marketing/email/templates/{template_id}")
    assert delete_template.status_code == 200


# =============================================================================
# AUDIENCES + INTEGRATIONS
# =============================================================================


def test_audience_crud(marketing_client, ensure_marketing_tables):
    create_resp = marketing_client.post(
        "/api/v1/marketing/audiences",
        json={"name": "New Leads", "member_count": 10},
    )
    assert create_resp.status_code == 200
    audience_id = create_resp.json()["id"]

    update_resp = marketing_client.patch(
        f"/api/v1/marketing/audiences/{audience_id}",
        json={"member_count": 15},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["member_count"] == 15

    delete_resp = marketing_client.delete(f"/api/v1/marketing/audiences/{audience_id}")
    assert delete_resp.status_code == 200


def test_integration_crud(marketing_client, ensure_marketing_tables):
    create_resp = marketing_client.post(
        "/api/v1/marketing/integrations",
        json={"integration_type": "meta", "status": "connected"},
    )
    assert create_resp.status_code == 200
    integration_id = create_resp.json()["id"]

    update_resp = marketing_client.patch(
        f"/api/v1/marketing/integrations/{integration_id}",
        json={"status": "error"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "error"

    delete_resp = marketing_client.delete(f"/api/v1/marketing/integrations/{integration_id}")
    assert delete_resp.status_code == 200


# =============================================================================
# CONSENT + SUPPRESSIONS
# =============================================================================


def test_consent_and_suppression_crud(marketing_client, create_party):
    party = create_party("Consent Party")

    create_resp = marketing_client.post(
        "/api/v1/marketing/consent",
        json={"party_id": party.id, "channel": "email", "status": "granted"},
    )
    assert create_resp.status_code == 200
    consent_id = create_resp.json()["id"]

    update_resp = marketing_client.patch(
        f"/api/v1/marketing/consent/{consent_id}",
        json={"status": "revoked"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "revoked"

    suppression_resp = marketing_client.post(
        "/api/v1/marketing/suppressions",
        json={"party_id": party.id, "channel": "email", "reason": "bounce"},
    )
    assert suppression_resp.status_code == 200
    suppression_id = suppression_resp.json()["id"]

    delete_suppression = marketing_client.delete(f"/api/v1/marketing/suppressions/{suppression_id}")
    assert delete_suppression.status_code == 200

    delete_consent = marketing_client.delete(f"/api/v1/marketing/consent/{consent_id}")
    assert delete_consent.status_code == 200


# =============================================================================
# PUBLIC ENDPOINTS + VALIDATION
# =============================================================================


def test_unsubscribe_with_token(public_client, create_party, monkeypatch):
    party = create_party("Unsubscribe Party")
    monkeypatch.setattr(settings, "email_unsubscribe_secret", "test-secret")
    token = create_unsubscribe_token(party.id, ConsentChannel.EMAIL)

    response = public_client.post(
        "/api/marketing/consent/unsubscribe",
        json={"token": token},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_campaign_validation_rejects_blank_name(marketing_client, ensure_marketing_tables):
    response = marketing_client.post(
        "/api/v1/marketing/campaigns",
        json={"name": "   ", "campaign_type": "email"},
    )
    assert response.status_code == 422


def test_social_post_validation_rejects_blank_content(marketing_client, ensure_marketing_tables):
    account_resp = marketing_client.post(
        "/api/v1/marketing/social/accounts",
        json={"platform": "facebook", "account_id": "fb-234"},
    )
    assert account_resp.status_code == 200
    account_id = account_resp.json()["id"]

    response = marketing_client.post(
        "/api/v1/marketing/social/posts",
        json={"account_id": account_id, "content": "   "},
    )
    assert response.status_code == 422


def test_email_campaign_validation_rejects_invalid_send_window(marketing_client, ensure_marketing_tables):
    template_resp = marketing_client.post(
        "/api/v1/marketing/email/templates",
        json={"name": "Send Window Template", "subject": "Test"},
    )
    assert template_resp.status_code == 200
    template_id = template_resp.json()["id"]

    response = marketing_client.post(
        "/api/v1/marketing/email/campaigns",
        json={
            "name": "Invalid Window",
            "template_id": template_id,
            "send_window_start": 9,
            "send_window_end": 9,
        },
    )
    assert response.status_code == 422


def test_audience_validation_rejects_negative_member_count(marketing_client, ensure_marketing_tables):
    response = marketing_client.post(
        "/api/v1/marketing/audiences",
        json={"name": "Invalid Audience", "member_count": -1},
    )
    assert response.status_code == 422
