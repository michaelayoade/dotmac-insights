"""Consent and suppression service stubs for the Marketing module."""
from __future__ import annotations

from datetime import datetime
import hashlib
import hmac
from typing import List, Dict, Any, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.marketing import ConsentChannel, ConsentStatus, MarketingConsent, SuppressionEntry
from app.models.party import Party
from app.services.errors import NotFoundError, DuplicateError, ValidationError
from app.services.validation.soft_validation_service import SoftValidationService


def _format_datetime(value: datetime | None) -> str:
    if not value:
        return "--"
    return value.strftime("%b %d, %Y")


def _format_percent(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0%"
    return f"{round((numerator / denominator) * 100)}%"


def _party_name(party: Party | None) -> str:
    if not party:
        return "Unknown"
    if party.name:
        return party.name
    names = " ".join([part for part in [party.first_name, party.last_name] if part])
    return names or "Unknown"


def _require_unsubscribe_secret() -> str:
    secret = settings.email_unsubscribe_secret
    if not secret:
        raise ValidationError("Email unsubscribe secret is not configured")
    return secret


def _sign_unsubscribe_payload(payload: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def create_unsubscribe_token(party_id: int, channel: ConsentChannel | str) -> str:
    secret = _require_unsubscribe_secret()
    if isinstance(channel, str):
        channel = ConsentChannel(channel)
    payload = f"{party_id}:{channel.value}"
    signature = _sign_unsubscribe_payload(payload, secret)
    return f"{payload}:{signature}"


def parse_unsubscribe_token(token: str) -> Tuple[int, ConsentChannel]:
    try:
        party_id_str, channel_value, signature = token.split(":", 2)
        party_id = int(party_id_str)
    except (ValueError, AttributeError):
        raise ValidationError("Invalid unsubscribe token format")

    secret = _require_unsubscribe_secret()
    payload = f"{party_id}:{channel_value}"
    expected_signature = _sign_unsubscribe_payload(payload, secret)
    if not hmac.compare_digest(expected_signature, signature):
        raise ValidationError("Invalid unsubscribe token signature")

    try:
        channel = ConsentChannel(channel_value)
    except ValueError:
        raise ValidationError("Invalid unsubscribe channel")

    return party_id, channel


class ConsentService:
    """Provide consent and suppression data."""

    def __init__(self, db: Session):
        self.db = db

    def get_overview(self) -> Dict[str, Any]:
        email_total = (
            self.db.query(func.count(MarketingConsent.id))
            .filter(MarketingConsent.channel == ConsentChannel.EMAIL)
            .scalar()
            or 0
        )
        email_granted = (
            self.db.query(func.count(MarketingConsent.id))
            .filter(
                MarketingConsent.channel == ConsentChannel.EMAIL,
                MarketingConsent.status == ConsentStatus.GRANTED,
            )
            .scalar()
            or 0
        )
        whatsapp_total = (
            self.db.query(func.count(MarketingConsent.id))
            .filter(MarketingConsent.channel == ConsentChannel.WHATSAPP)
            .scalar()
            or 0
        )
        whatsapp_granted = (
            self.db.query(func.count(MarketingConsent.id))
            .filter(
                MarketingConsent.channel == ConsentChannel.WHATSAPP,
                MarketingConsent.status == ConsentStatus.GRANTED,
            )
            .scalar()
            or 0
        )
        suppressed = self.db.query(func.count(SuppressionEntry.id)).scalar() or 0

        return {
            "email_opt_in": _format_percent(email_granted, email_total),
            "whatsapp_opt_in": _format_percent(whatsapp_granted, whatsapp_total),
            "suppressed_count": suppressed,
        }

    def list_records(self) -> List[Dict[str, Any]]:
        records = (
            self.db.query(MarketingConsent, Party)
            .join(Party, MarketingConsent.party_id == Party.id)
            .order_by(MarketingConsent.updated_at.desc())
            .limit(10)
            .all()
        )
        results: List[Dict[str, Any]] = []
        for consent, party in records:
            results.append(
                {
                    "name": _party_name(party),
                    "email": party.primary_email or "--",
                    "channel": consent.channel.value,
                    "status": consent.status.value,
                    "updated": _format_datetime(consent.updated_at),
                }
            )
        return results

    def list_suppressions(self) -> List[Dict[str, Any]]:
        rows = (
            self.db.query(SuppressionEntry.channel, func.count(SuppressionEntry.id))
            .group_by(SuppressionEntry.channel)
            .all()
        )
        results = [
            {
                "label": (row[0].value.replace("_", " ").title() if row[0] else "Unknown"),
                "count": row[1],
            }
            for row in rows
        ]
        if not results:
            return []
        return results

    def get_consent(self, consent_id: int) -> MarketingConsent:
        consent = (
            self.db.query(MarketingConsent)
            .filter(MarketingConsent.id == consent_id)
            .first()
        )
        if not consent:
            raise NotFoundError("Consent record not found")
        return consent

    def create_consent(self, data: Dict[str, Any]) -> MarketingConsent:
        existing = (
            self.db.query(MarketingConsent)
            .filter(
                MarketingConsent.party_id == data["party_id"],
                MarketingConsent.channel == data["channel"],
            )
            .first()
        )
        if existing:
            raise DuplicateError("Consent record already exists for party/channel")
        consent = MarketingConsent(
            party_id=data["party_id"],
            channel=data.get("channel", ConsentChannel.EMAIL),
            status=data.get("status", ConsentStatus.UNKNOWN),
            source=data.get("source"),
        )
        self.db.add(consent)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(consent)
        return consent

    def update_consent(self, consent_id: int, data: Dict[str, Any]) -> MarketingConsent:
        consent = self.get_consent(consent_id)
        for field in ["status", "source"]:
            if field in data:
                setattr(consent, field, data[field])
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(consent)
        return consent

    def delete_consent(self, consent_id: int) -> None:
        consent = self.get_consent(consent_id)
        self.db.delete(consent)

    def get_suppression(self, suppression_id: int) -> SuppressionEntry:
        suppression = (
            self.db.query(SuppressionEntry)
            .filter(SuppressionEntry.id == suppression_id)
            .first()
        )
        if not suppression:
            raise NotFoundError("Suppression entry not found")
        return suppression

    def create_suppression(self, data: Dict[str, Any]) -> SuppressionEntry:
        existing = (
            self.db.query(SuppressionEntry)
            .filter(
                SuppressionEntry.party_id == data["party_id"],
                SuppressionEntry.channel == data["channel"],
            )
            .first()
        )
        if existing:
            raise DuplicateError("Suppression entry already exists for party/channel")
        suppression = SuppressionEntry(
            party_id=data["party_id"],
            channel=data.get("channel", ConsentChannel.EMAIL),
            reason=data.get("reason"),
            source=data.get("source"),
        )
        self.db.add(suppression)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(suppression)
        return suppression

    def delete_suppression(self, suppression_id: int) -> None:
        suppression = self.get_suppression(suppression_id)
        self.db.delete(suppression)

    def unsubscribe(self, party_id: int, channel: ConsentChannel, source: str | None = None) -> MarketingConsent:
        consent = (
            self.db.query(MarketingConsent)
            .filter(
                MarketingConsent.party_id == party_id,
                MarketingConsent.channel == channel,
            )
            .first()
        )
        if consent:
            consent.status = ConsentStatus.REVOKED
            if source:
                consent.source = source
        else:
            consent = MarketingConsent(
                party_id=party_id,
                channel=channel,
                status=ConsentStatus.REVOKED,
                source=source,
            )
            self.db.add(consent)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(consent)

        suppression = (
            self.db.query(SuppressionEntry)
            .filter(
                SuppressionEntry.party_id == party_id,
                SuppressionEntry.channel == channel,
            )
            .first()
        )
        if not suppression:
            suppression = SuppressionEntry(
                party_id=party_id,
                channel=channel,
                reason="unsubscribe",
                source=source,
            )
            self.db.add(suppression)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(suppression)

        return consent
