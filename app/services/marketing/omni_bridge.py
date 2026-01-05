"""Bridge marketing webhooks into omnichannel inbox."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.omni import OmniChannel, OmniConversation, OmniParticipant, OmniWebhookEvent
from app.models.party import Party, PartyExternalId, PartyRole, PartyStatus, PartyType
from app.services.marketing.integration_service import IntegrationService
from app.services.support.conversations import ConversationService
from app.services.support.messages import MessageService
from app.services.support.types import ConversationCreate, InboundMessageData
from app.services.validation.soft_validation_service import SoftValidationService

__all__ = ["ingest_marketing_webhook"]


def ingest_marketing_webhook(
    db: Session,
    platform: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    provider_event_id: str,
) -> Dict[str, Optional[int]]:
    integration_service = IntegrationService(db)
    integration = integration_service.get_or_create_by_type(platform)
    channel = integration_service.ensure_omni_channel(integration)

    existing_event = (
        db.query(OmniWebhookEvent)
        .filter(
            OmniWebhookEvent.channel_id == channel.id,
            OmniWebhookEvent.provider_event_id == provider_event_id,
        )
        .first()
    )
    if existing_event:
        return {"conversation_id": None, "message_id": None}

    webhook_event = OmniWebhookEvent(
        channel_id=channel.id,
        provider_event_id=provider_event_id,
        payload=payload,
        headers=headers,
        processed=False,
        received_at=datetime.utcnow(),
    )
    db.add(webhook_event)
    db.flush()
    SoftValidationService(db).validate_and_store(webhook_event)

    message_payload = _normalize_inbound_message(platform, payload)
    if not message_payload:
        webhook_event.error = "No inbound message detected"
        return {"conversation_id": None, "message_id": None}

    participant = _get_or_create_participant(
        db,
        channel,
        message_payload.get("handle"),
        message_payload.get("display_name"),
        message_payload.get("participant_meta"),
    )

    party = _resolve_or_create_party(
        db,
        platform=platform,
        handle=message_payload.get("handle"),
        contact_email=message_payload.get("contact_email"),
        display_name=message_payload.get("display_name"),
    )

    if participant and party and participant.party_id != party.id:
        participant.party_id = party.id
        participant.updated_at = datetime.utcnow()

    conversation = _get_or_create_conversation(
        db,
        channel,
        external_thread_id=message_payload.get("external_thread_id"),
        subject=message_payload.get("subject"),
        contact_name=message_payload.get("display_name"),
        contact_email=message_payload.get("contact_email"),
        party_id=party.id if party else None,
    )

    try:
        message_service = MessageService(db)
        message = message_service.create_inbound(
            InboundMessageData(
                conversation_id=conversation.id,
                body=message_payload.get("body") or _fallback_body(platform),
                participant_id=participant.id if participant else None,
                channel_id=channel.id,
                subject=message_payload.get("subject"),
                message_type=message_payload.get("message_type"),
                provider_message_id=message_payload.get("provider_message_id"),
                meta=message_payload.get("meta") or {},
                sent_at=message_payload.get("sent_at"),
            )
        )
        if party and message.party_id != party.id:
            message.party_id = party.id
            message.updated_at = datetime.utcnow()
    except Exception as exc:
        webhook_event.error = str(exc)
        return {"conversation_id": conversation.id, "message_id": None}

    webhook_event.processed = True
    webhook_event.error = None
    return {"conversation_id": conversation.id, "message_id": message.id}


def _normalize_inbound_message(platform: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if platform == "whatsapp":
        return _normalize_whatsapp(payload)
    if platform == "meta":
        return _normalize_meta(payload)
    if platform == "twitter":
        return _normalize_twitter(payload)
    if platform == "linkedin":
        return _normalize_linkedin(payload)
    return _normalize_generic(payload)


def _normalize_whatsapp(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    entry = _first(payload.get("entry"))
    change = _first((entry or {}).get("changes"))
    value = (change or {}).get("value") or {}
    message = _first(value.get("messages")) or {}
    contact = _first(value.get("contacts")) or {}

    body = (
        (message.get("text") or {}).get("body")
        or (message.get("button") or {}).get("text")
        or ((message.get("interactive") or {}).get("button_reply") or {}).get("title")
    )
    handle = message.get("from")
    message_id = message.get("id")
    external_thread_id = (message.get("context") or {}).get("id") or message_id
    display_name = ((contact.get("profile") or {}) or {}).get("name")
    sent_at = _parse_timestamp(message.get("timestamp"))

    if not (body or message_id or handle):
        return None

    meta = {"raw_type": message.get("type") or "whatsapp"}
    return {
        "body": body,
        "handle": handle,
        "display_name": display_name,
        "contact_email": _email_from_handle(handle) or (contact.get("email") if isinstance(contact, dict) else None),
        "provider_message_id": message_id,
        "external_thread_id": external_thread_id,
        "sent_at": sent_at,
        "message_type": "whatsapp",
        "meta": meta,
    }


def _normalize_meta(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    entry = _first(payload.get("entry"))
    messaging = _first((entry or {}).get("messaging")) or {}
    message = messaging.get("message") or {}
    body = message.get("text") or message.get("message")
    sender = messaging.get("sender") or {}
    handle = sender.get("id")
    message_id = message.get("mid") or message.get("id")
    external_thread_id = (
        (messaging.get("conversation") or {}).get("id")
        or messaging.get("thread_id")
        or message_id
    )
    sent_at = _parse_timestamp(messaging.get("timestamp"))

    if not (body or message_id or handle):
        return None

    return {
        "body": body,
        "handle": handle,
        "display_name": None,
        "contact_email": _email_from_handle(handle),
        "provider_message_id": message_id,
        "external_thread_id": external_thread_id,
        "sent_at": sent_at,
        "message_type": "social",
        "meta": {"raw_type": "meta"},
    }


def _normalize_twitter(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    data = payload.get("data") or payload.get("tweet") or payload
    body = data.get("text") or payload.get("text")
    message_id = data.get("id") or payload.get("id")
    handle = data.get("author_id") or payload.get("sender_id") or payload.get("user_id")
    external_thread_id = data.get("conversation_id") or data.get("thread_id") or message_id
    sent_at = _parse_timestamp(data.get("timestamp") or data.get("created_at"))

    if not (body or message_id or handle):
        return None

    return {
        "body": body,
        "handle": handle,
        "display_name": None,
        "contact_email": _email_from_handle(handle),
        "provider_message_id": message_id,
        "external_thread_id": external_thread_id,
        "sent_at": sent_at,
        "message_type": "social",
        "meta": {"raw_type": "twitter"},
    }


def _normalize_linkedin(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    event = payload.get("event") or payload
    body = event.get("message") or event.get("text") or payload.get("message")
    handle = event.get("from") or event.get("sender") or event.get("actor")
    message_id = event.get("id") or payload.get("id")
    external_thread_id = event.get("conversation_id") or event.get("thread_id") or message_id
    sent_at = _parse_timestamp(event.get("timestamp") or event.get("created_at"))

    if not (body or message_id or handle):
        return None

    return {
        "body": body,
        "handle": str(handle) if handle else None,
        "display_name": None,
        "contact_email": _email_from_handle(handle),
        "provider_message_id": message_id,
        "external_thread_id": external_thread_id,
        "sent_at": sent_at,
        "message_type": "social",
        "meta": {"raw_type": "linkedin"},
    }


def _normalize_generic(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    body = payload.get("message") or payload.get("text") or payload.get("body")
    message_id = payload.get("id") or payload.get("message_id")
    handle = payload.get("from") or payload.get("sender") or payload.get("handle")
    external_thread_id = payload.get("thread_id") or payload.get("conversation_id") or message_id
    sent_at = _parse_timestamp(payload.get("timestamp"))

    if not (body or message_id or handle):
        return None

    return {
        "body": body,
        "handle": str(handle) if handle else None,
        "display_name": payload.get("name"),
        "contact_email": payload.get("email") or _email_from_handle(handle),
        "provider_message_id": message_id,
        "external_thread_id": external_thread_id,
        "sent_at": sent_at,
        "message_type": "social",
        "meta": {"raw_type": "generic"},
    }


def _get_or_create_participant(
    db: Session,
    channel: OmniChannel,
    handle: Optional[str],
    display_name: Optional[str],
    meta: Optional[Dict[str, Any]],
) -> Optional[OmniParticipant]:
    if not handle:
        return None

    participant = (
        db.query(OmniParticipant)
        .filter(
            OmniParticipant.handle == handle,
            OmniParticipant.channel_type == channel.type,
        )
        .first()
    )
    if participant:
        return participant

    participant = OmniParticipant(
        handle=handle,
        channel_type=channel.type,
        display_name=display_name,
        meta=meta or None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(participant)
    db.flush()
    SoftValidationService(db).validate_and_store(participant)
    return participant


def _get_or_create_conversation(
    db: Session,
    channel: OmniChannel,
    external_thread_id: Optional[str],
    subject: Optional[str],
    contact_name: Optional[str],
    contact_email: Optional[str],
    party_id: Optional[int] = None,
) -> OmniConversation:
    if external_thread_id:
        existing = (
            db.query(OmniConversation)
            .filter(
                OmniConversation.channel_id == channel.id,
                OmniConversation.external_thread_id == external_thread_id,
            )
            .first()
        )
        if existing:
            if party_id and existing.party_id != party_id:
                existing.party_id = party_id
                existing.updated_at = datetime.utcnow()
            return existing

    conversation_service = ConversationService(db)
    conv = conversation_service.create(
        ConversationCreate(
            channel_id=channel.id,
            subject=subject or f"Inbound {channel.name}",
            external_thread_id=external_thread_id,
            contact_name=contact_name,
            contact_email=contact_email,
            party_id=party_id,
        )
    )
    return conv


def _resolve_or_create_party(
    db: Session,
    platform: str,
    handle: Optional[str],
    contact_email: Optional[str],
    display_name: Optional[str],
) -> Optional[Party]:
    identifier = handle or contact_email
    if not identifier:
        return None

    system = f"marketing:{platform}"
    if handle:
        mapping = (
            db.query(PartyExternalId)
            .filter(
                PartyExternalId.system == system,
                PartyExternalId.external_id == handle,
            )
            .first()
        )
        if mapping:
            return mapping.party

    party = None
    if contact_email:
        party = db.query(Party).filter(Party.primary_email == contact_email).first()

    normalized_phone = _normalize_phone(handle)
    if not party and normalized_phone:
        candidates = [normalized_phone, f"+{normalized_phone}"]
        party = db.query(Party).filter(Party.primary_phone.in_(candidates)).first()

    if not party and handle and "@" in handle:
        party = db.query(Party).filter(Party.primary_email == handle).first()

    if party:
        _ensure_party_mapping(db, party, system, handle, platform)
        return party

    party = Party(
        type=PartyType.PERSON.value,
        status=PartyStatus.ACTIVE.value,
        name=display_name or handle or "New Lead",
        primary_email=contact_email if contact_email and "@" in contact_email else None,
        primary_phone=f"+{normalized_phone}" if normalized_phone else None,
        notes=f"Auto-created from {platform} inbound message",
        tags=_merge_party_tags([], "lead"),
    )
    db.add(party)
    db.flush()

    role = PartyRole(
        party_id=party.id,
        role="lead",
        status="active",
        source="marketing_inbound",
        source_campaign=platform,
    )
    db.add(role)
    db.flush()

    _ensure_party_mapping(db, party, system, handle, platform, is_primary=True)
    return party


def _ensure_party_mapping(
    db: Session,
    party: Party,
    system: str,
    handle: Optional[str],
    platform: str,
    is_primary: bool = False,
) -> None:
    if not handle:
        return
    existing = (
        db.query(PartyExternalId)
        .filter(
            PartyExternalId.system == system,
            PartyExternalId.external_id == handle,
        )
        .first()
    )
    if existing:
        return
    mapping = PartyExternalId(
        party_id=party.id,
        system=system,
        external_id=handle,
        external_key_type="handle",
        is_primary=is_primary,
        metadata_={"source": "marketing_inbound", "platform": platform},
    )
    db.add(mapping)
    db.flush()


def _normalize_phone(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) < 7:
        return None
    return digits


def _merge_party_tags(existing: list, tag: str) -> list:
    tags = existing[:] if isinstance(existing, list) else []
    for item in tags:
        if isinstance(item, str) and item == tag:
            return tags
        if isinstance(item, dict) and item.get("name") == tag:
            return tags
    tags.append(tag)
    return tags


def _fallback_body(platform: str) -> str:
    return f"Inbound {platform} message received."


def _first(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, list) and value:
        item = value[0]
        if isinstance(item, dict):
            return item
    if isinstance(value, dict):
        return value
    return None


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    try:
        if isinstance(value, str) and value.isdigit():
            value = int(value)
        if isinstance(value, (int, float)):
            if value > 10_000_000_000:
                value = value / 1000.0
            return datetime.fromtimestamp(value, tz=timezone.utc)
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None
    return None


def _email_from_handle(handle: Any) -> Optional[str]:
    if not handle:
        return None
    if isinstance(handle, str) and "@" in handle:
        return handle
    return None
