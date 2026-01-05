"""
Marketing webhook public endpoint tests.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest

from app.config import settings
from app.database import Base
from app.models.marketing import MarketingWebhookEvent
from app.models.party import Party, PartyType, PartyStatus, PartyExternalId, PartyRole
from app.models.marketing import MarketingConsent, ConsentChannel, ConsentStatus, SuppressionEntry


pytestmark = [pytest.mark.integration, pytest.mark.marketing]


@pytest.fixture
def ensure_marketing_tables(integration_db):
    Base.metadata.create_all(bind=integration_db.get_bind())
    return integration_db


def _sign_payload(secret: str, payload: bytes) -> str:
    signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={signature}"


def test_signed_webhook_accepted(unauthenticated_client, ensure_marketing_tables, monkeypatch):
    monkeypatch.setattr(settings, "meta_webhook_secret", "webhook-secret")

    payload = {"event_id": "evt-001", "type": "test"}
    payload_bytes = json.dumps(payload).encode("utf-8")
    signature = _sign_payload(settings.meta_webhook_secret, payload_bytes)

    response = unauthenticated_client.post(
        "/api/marketing/webhooks/meta",
        data=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "x-hub-signature-256": signature,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    stored = (
        ensure_marketing_tables.query(MarketingWebhookEvent)
        .filter(MarketingWebhookEvent.event_id == "evt-001")
        .first()
    )
    assert stored is not None


def test_duplicate_webhook_rejected(unauthenticated_client, ensure_marketing_tables, monkeypatch):
    monkeypatch.setattr(settings, "meta_webhook_secret", "webhook-secret")

    payload = {"event_id": "evt-dup"}
    payload_bytes = json.dumps(payload).encode("utf-8")
    signature = _sign_payload(settings.meta_webhook_secret, payload_bytes)

    first = unauthenticated_client.post(
        "/api/marketing/webhooks/meta",
        data=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "x-hub-signature-256": signature,
        },
    )
    assert first.status_code == 200

    second = unauthenticated_client.post(
        "/api/marketing/webhooks/meta",
        data=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "x-hub-signature-256": signature,
        },
    )
    assert second.status_code == 409


def test_webhook_rejects_invalid_signature(unauthenticated_client, ensure_marketing_tables, monkeypatch):
    monkeypatch.setattr(settings, "meta_webhook_secret", "webhook-secret")

    payload = {"event_id": "evt-bad"}
    payload_bytes = json.dumps(payload).encode("utf-8")

    response = unauthenticated_client.post(
        "/api/marketing/webhooks/meta",
        data=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "x-hub-signature-256": "sha256=bad",
        },
    )
    assert response.status_code == 401


def test_webhook_rejects_stale_timestamp(unauthenticated_client, ensure_marketing_tables, monkeypatch):
    monkeypatch.setattr(settings, "meta_webhook_secret", "webhook-secret")

    payload = {"event_id": "evt-stale"}
    payload_bytes = json.dumps(payload).encode("utf-8")
    signature = _sign_payload(settings.meta_webhook_secret, payload_bytes)
    stale_timestamp = str(int(time.time()) - 1000)

    response = unauthenticated_client.post(
        "/api/marketing/webhooks/meta",
        data=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "x-hub-signature-256": signature,
            "x-request-timestamp": stale_timestamp,
        },
    )
    assert response.status_code == 400


def test_webhook_rejects_duplicate_payload_hash(unauthenticated_client, ensure_marketing_tables, monkeypatch):
    monkeypatch.setattr(settings, "meta_webhook_secret", "webhook-secret")

    payload = {"event_id": "evt-hash"}
    payload_bytes = json.dumps(payload).encode("utf-8")
    signature = _sign_payload(settings.meta_webhook_secret, payload_bytes)

    first = unauthenticated_client.post(
        "/api/marketing/webhooks/meta",
        data=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "x-hub-signature-256": signature,
        },
    )
    assert first.status_code == 200

    second = unauthenticated_client.post(
        "/api/marketing/webhooks/meta",
        data=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "x-hub-signature-256": signature,
        },
    )
    assert second.status_code == 409


def test_whatsapp_webhook_opt_out_sets_consent(unauthenticated_client, ensure_marketing_tables, monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_webhook_secret", "webhook-secret")

    party = Party(
        type=PartyType.PERSON.value,
        status=PartyStatus.ACTIVE.value,
        name="WhatsApp Party",
        primary_phone="+2348012345678",
    )
    ensure_marketing_tables.add(party)
    ensure_marketing_tables.commit()
    ensure_marketing_tables.refresh(party)

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"from": "2348012345678", "type": "text", "text": {"body": "STOP"}}
                            ]
                        }
                    }
                ]
            }
        ]
    }
    payload_bytes = json.dumps(payload).encode("utf-8")
    signature = _sign_payload(settings.whatsapp_webhook_secret, payload_bytes)

    response = unauthenticated_client.post(
        "/api/marketing/webhooks/whatsapp",
        data=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "x-hub-signature-256": signature,
        },
    )
    assert response.status_code == 200

    consent = (
        ensure_marketing_tables.query(MarketingConsent)
        .filter(
            MarketingConsent.party_id == party.id,
            MarketingConsent.channel == ConsentChannel.WHATSAPP,
        )
        .first()
    )
    assert consent is not None
    assert consent.status == ConsentStatus.REVOKED

    suppression = (
        ensure_marketing_tables.query(SuppressionEntry)
        .filter(
            SuppressionEntry.party_id == party.id,
            SuppressionEntry.channel == ConsentChannel.WHATSAPP,
        )
        .first()
    )
    assert suppression is not None


def test_whatsapp_webhook_creates_lead_party(unauthenticated_client, ensure_marketing_tables, monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_webhook_secret", "webhook-secret")

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"from": "2348011112222", "type": "text", "text": {"body": "Hello"}}
                            ]
                        }
                    }
                ]
            }
        ]
    }
    payload_bytes = json.dumps(payload).encode("utf-8")
    signature = _sign_payload(settings.whatsapp_webhook_secret, payload_bytes)

    response = unauthenticated_client.post(
        "/api/marketing/webhooks/whatsapp",
        data=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "x-hub-signature-256": signature,
        },
    )
    assert response.status_code == 200

    mapping = (
        ensure_marketing_tables.query(PartyExternalId)
        .filter(
            PartyExternalId.system == "marketing:whatsapp",
            PartyExternalId.external_id == "2348011112222",
        )
        .first()
    )
    assert mapping is not None
    lead_role = (
        ensure_marketing_tables.query(PartyRole)
        .filter(
            PartyRole.party_id == mapping.party_id,
            PartyRole.role == "lead",
        )
        .first()
    )
    assert lead_role is not None
