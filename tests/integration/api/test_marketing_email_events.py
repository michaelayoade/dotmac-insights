"""
Marketing email event webhook tests.
"""
from __future__ import annotations

import pytest

from app.database import Base
from app.models.marketing import EmailCampaign, EmailCampaignStatus, EmailSend, EmailSendStatus, EmailTemplate
from app.models.party import Party, PartyType, PartyStatus


pytestmark = [pytest.mark.integration, pytest.mark.marketing]


@pytest.fixture
def ensure_marketing_tables(integration_db):
    Base.metadata.create_all(bind=integration_db.get_bind())
    return integration_db


def test_email_events_list_payload_updates_send(unauthenticated_client, ensure_marketing_tables):
    template = EmailTemplate(
        name="Test Template",
        subject="Hello",
        body_text="Hi",
        variables=[],
    )
    party = Party(
        type=PartyType.PERSON.value,
        status=PartyStatus.ACTIVE.value,
        name="Email Recipient",
        primary_email="recipient@example.com",
    )
    ensure_marketing_tables.add_all([template, party])
    ensure_marketing_tables.commit()
    ensure_marketing_tables.refresh(template)
    ensure_marketing_tables.refresh(party)

    campaign = EmailCampaign(
        name="Test Campaign",
        template_id=template.id,
        status=EmailCampaignStatus.DRAFT,
    )
    ensure_marketing_tables.add(campaign)
    ensure_marketing_tables.commit()
    ensure_marketing_tables.refresh(campaign)

    send = EmailSend(
        campaign_id=campaign.id,
        party_id=party.id,
        status=EmailSendStatus.SENT,
        provider_message_id="msg-123",
    )
    ensure_marketing_tables.add(send)
    ensure_marketing_tables.commit()
    ensure_marketing_tables.refresh(send)

    response = unauthenticated_client.post(
        "/api/marketing/email/events",
        json=[{"event": "delivered", "provider_message_id": "msg-123"}],
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["updated"] == 1

    updated = ensure_marketing_tables.query(EmailSend).filter(EmailSend.id == send.id).first()
    assert updated.status == EmailSendStatus.DELIVERED
    assert updated.delivered_at is not None


def test_email_events_mailgun_payload_updates_send(unauthenticated_client, ensure_marketing_tables):
    template = EmailTemplate(
        name="Mailgun Template",
        subject="Hello",
        body_text="Hi",
        variables=[],
    )
    party = Party(
        type=PartyType.PERSON.value,
        status=PartyStatus.ACTIVE.value,
        name="Mailgun Recipient",
        primary_email="mailgun@example.com",
    )
    ensure_marketing_tables.add_all([template, party])
    ensure_marketing_tables.commit()
    ensure_marketing_tables.refresh(template)
    ensure_marketing_tables.refresh(party)

    campaign = EmailCampaign(
        name="Mailgun Campaign",
        template_id=template.id,
        status=EmailCampaignStatus.DRAFT,
    )
    ensure_marketing_tables.add(campaign)
    ensure_marketing_tables.commit()
    ensure_marketing_tables.refresh(campaign)

    send = EmailSend(
        campaign_id=campaign.id,
        party_id=party.id,
        status=EmailSendStatus.SENT,
        provider_message_id="mailgun-id",
    )
    ensure_marketing_tables.add(send)
    ensure_marketing_tables.commit()
    ensure_marketing_tables.refresh(send)

    payload = {
        "event-data": {
            "event": "opened",
            "message": {"headers": {"message-id": "<mailgun-id>"}},
        }
    }
    response = unauthenticated_client.post(
        "/api/marketing/email/events",
        json=payload,
    )
    assert response.status_code == 200

    updated = ensure_marketing_tables.query(EmailSend).filter(EmailSend.id == send.id).first()
    assert updated.status == EmailSendStatus.OPENED
    assert updated.opened_at is not None
