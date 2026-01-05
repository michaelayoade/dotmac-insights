"""Marketing API - dashboards, campaigns, journeys, social, and email."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import secrets
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import Require
from app.models.marketing import (
    ConsentChannel,
    ConsentStatus,
    CustomerJourney,
    EmailCampaign,
    EmailCampaignStatus,
    EmailTemplate,
    JourneyStatus,
    JourneyStep,
    JourneyStepType,
    JourneyTemplate,
    MarketingAudience,
    MarketingCampaign,
    MarketingCampaignStatus,
    MarketingCampaignType,
    MarketingConsent,
    MarketingIntegration,
    MarketingIntegrationStatus,
    MarketingWebhookEvent,
    EmailSend,
    EmailSendStatus,
    SocialAccount,
    SocialPlatform,
    SocialPost,
    SocialPostStatus,
    SuppressionEntry,
)
from app.models.party import Party
from app.services.errors import NotFoundError, ValidationError, ConflictError, DuplicateError
from app.services.marketing import (
    CampaignService,
    JourneyService,
    SocialMediaService,
    EmailCampaignService,
    AudienceService,
    IntegrationService,
    MarketingAnalyticsService,
    ConsentService,
    seed_marketing_defaults,
)
from app.services.marketing.omni_bridge import ingest_marketing_webhook
from app.services.marketing.consent_service import parse_unsubscribe_token
from app.integrations.marketing import (
    compute_payload_hash,
    extract_event_id,
    verify_platform_signature,
    MetaBusinessClient,
    TwitterClient,
    LinkedInClient,
    WhatsAppBusinessClient,
)
from app.api.marketing.soft_validation import router as soft_validation_router

router = APIRouter(prefix="/marketing", tags=["marketing"])
public_router = APIRouter(prefix="/marketing", tags=["marketing-public"])

marketing_read_dep = Depends(Require("marketing:read"))
marketing_write_dep = Depends(Require("marketing:write"))

router.include_router(soft_validation_router, tags=["Marketing - Validation"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def get_campaign_service(db: Session = Depends(get_db)) -> CampaignService:
    return CampaignService(db)


def get_journey_service(db: Session = Depends(get_db)) -> JourneyService:
    return JourneyService(db)


def get_social_service(db: Session = Depends(get_db)) -> SocialMediaService:
    return SocialMediaService(db)


def get_email_service(db: Session = Depends(get_db)) -> EmailCampaignService:
    return EmailCampaignService(db)


def get_audience_service(db: Session = Depends(get_db)) -> AudienceService:
    return AudienceService(db)


def get_integration_service(db: Session = Depends(get_db)) -> IntegrationService:
    return IntegrationService(db)


def get_analytics_service(db: Session = Depends(get_db)) -> MarketingAnalyticsService:
    return MarketingAnalyticsService(db)


def get_consent_service(db: Session = Depends(get_db)) -> ConsentService:
    return ConsentService(db)


def handle_service_error(exc: Exception) -> None:
    if isinstance(exc, (NotFoundError,)):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (ValidationError,)):
        raise HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, (ConflictError, DuplicateError)):
        raise HTTPException(status_code=409, detail=str(exc))
    raise HTTPException(status_code=500, detail=str(exc))


def get_oauth_client(integration_type: str, access_token: Optional[str] = None):
    if integration_type == "meta":
        return MetaBusinessClient(access_token=access_token)
    if integration_type == "twitter":
        return TwitterClient(access_token=access_token)
    if integration_type == "linkedin":
        return LinkedInClient(access_token=access_token)
    if integration_type == "whatsapp":
        return WhatsAppBusinessClient(access_token=access_token)
    raise HTTPException(status_code=400, detail="Unsupported integration type")


def _normalize_phone(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits or None


def _find_party_id_by_phone(db: Session, phone: Optional[str]) -> Optional[int]:
    if not phone:
        return None
    candidates = [
        phone,
        f"+{phone}",
    ]
    party = db.query(Party).filter(Party.primary_phone.in_(candidates)).first()
    if party:
        return party.id
    return None


def _extract_whatsapp_messages(payload: dict) -> list[dict]:
    events: list[dict] = []
    for entry in payload.get("entry", []) if isinstance(payload, dict) else []:
        for change in entry.get("changes", []) or []:
            value = change.get("value") or {}
            for message in value.get("messages", []) or []:
                sender = message.get("from")
                text = None
                if message.get("type") == "text":
                    text = (message.get("text") or {}).get("body")
                events.append({"from": sender, "text": text})
    return events


def _extract_whatsapp_statuses(payload: dict) -> list[dict]:
    events: list[dict] = []
    for entry in payload.get("entry", []) if isinstance(payload, dict) else []:
        for change in entry.get("changes", []) or []:
            value = change.get("value") or {}
            for status in value.get("statuses", []) or []:
                events.append(
                    {
                        "id": status.get("id"),
                        "status": status.get("status"),
                        "timestamp": status.get("timestamp"),
                        "errors": status.get("errors") or [],
                    }
                )
    return events


def _whatsapp_status_timestamp(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        timestamp = datetime.fromtimestamp(int(value), tz=timezone.utc)
    except ValueError:
        return None
    return timestamp.isoformat()


def _update_whatsapp_post_status(db: Session, status_event: dict) -> None:
    message_id = status_event.get("id")
    if not message_id:
        return
    posts = (
        db.query(SocialPost)
        .filter(SocialPost.metrics["whatsapp_message_ids"].contains([message_id]))
        .all()
    )
    if not posts:
        return
    status_value = (status_event.get("status") or "").lower()
    timestamp = _whatsapp_status_timestamp(status_event.get("timestamp"))
    errors = status_event.get("errors") or []
    for post in posts:
        metrics = post.metrics or {}
        status_map = metrics.get("whatsapp_statuses") or {}
        status_map[str(message_id)] = {"status": status_value or "unknown", "timestamp": timestamp}
        metrics["whatsapp_statuses"] = status_map
        metrics[f"whatsapp_{status_value}_count"] = metrics.get(f"whatsapp_{status_value}_count", 0) + 1
        if errors:
            metrics["whatsapp_error_count"] = metrics.get("whatsapp_error_count", 0) + len(errors)
            post.error = "; ".join(str(err.get("title") or err) for err in errors)[:1000]
            post.status = SocialPostStatus.FAILED
        post.metrics = metrics
        post.updated_at = datetime.now(timezone.utc)


def _apply_whatsapp_consent(
    db: Session,
    consent_service: ConsentService,
    party_id: int,
    action: str,
) -> None:
    if action == "opt_out":
        consent_service.unsubscribe(party_id, ConsentChannel.WHATSAPP, source="whatsapp_webhook")
        return

    consent = (
        db.query(MarketingConsent)
        .filter(
            MarketingConsent.party_id == party_id,
            MarketingConsent.channel == ConsentChannel.WHATSAPP,
        )
        .first()
    )
    if consent:
        consent.status = ConsentStatus.GRANTED
        consent.source = "whatsapp_webhook"
    else:
        consent = MarketingConsent(
            party_id=party_id,
            channel=ConsentChannel.WHATSAPP,
            status=ConsentStatus.GRANTED,
            source="whatsapp_webhook",
        )
        db.add(consent)

    suppression = (
        db.query(SuppressionEntry)
        .filter(
            SuppressionEntry.party_id == party_id,
            SuppressionEntry.channel == ConsentChannel.WHATSAPP,
        )
        .first()
    )
    if suppression and suppression.reason in {"unsubscribe", "opt_out"}:
        db.delete(suppression)


def _extract_email_event_payload(payload: dict) -> dict:
    send_id = payload.get("send_id") or payload.get("sendId")

    provider_message_id = (
        payload.get("provider_message_id")
        or payload.get("message_id")
        or payload.get("message-id")
        or payload.get("smtp-id")
        or payload.get("sg_message_id")
        or payload.get("MessageID")
        or payload.get("MessageId")
    )

    if not provider_message_id:
        event_data = payload.get("event-data") or payload.get("event_data")
        if isinstance(event_data, dict):
            provider_message_id = (
                (event_data.get("message") or {}).get("headers", {}).get("message-id")
                or event_data.get("message-id")
            )
        ses = payload.get("mail") or payload.get("ses")
        if isinstance(ses, dict):
            provider_message_id = provider_message_id or ses.get("messageId")

    provider_message_id = _normalize_message_id(provider_message_id)

    event_type = payload.get("event") or payload.get("type")
    if not event_type:
        event_data = payload.get("event-data") or payload.get("event_data")
        if isinstance(event_data, dict):
            event_type = event_data.get("event")
    if not event_type:
        event_type = payload.get("RecordType") or payload.get("recordType")
    if not event_type:
        event_type = payload.get("eventType") or payload.get("event_type")
    return {
        "send_id": send_id,
        "provider_message_id": provider_message_id,
        "event": event_type,
    }


def _normalize_message_id(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    if isinstance(value, str):
        return value.strip().strip("<>").strip()
    return str(value)


def _email_event_status(event_type: Optional[str]) -> Optional[EmailSendStatus]:
    if not event_type:
        return None
    normalized = str(event_type).lower()
    status_map = {
        "delivered": EmailSendStatus.DELIVERED,
        "delivery": EmailSendStatus.DELIVERED,
        "processed": EmailSendStatus.SENT,
        "sent": EmailSendStatus.SENT,
        "open": EmailSendStatus.OPENED,
        "opened": EmailSendStatus.OPENED,
        "click": EmailSendStatus.CLICKED,
        "clicked": EmailSendStatus.CLICKED,
        "clickthrough": EmailSendStatus.CLICKED,
        "bounce": EmailSendStatus.BOUNCED,
        "bounced": EmailSendStatus.BOUNCED,
        "soft_bounce": EmailSendStatus.BOUNCED,
        "hard_bounce": EmailSendStatus.BOUNCED,
        "dropped": EmailSendStatus.FAILED,
        "deferred": EmailSendStatus.FAILED,
        "failed": EmailSendStatus.FAILED,
        "failed": EmailSendStatus.FAILED,
        "unsubscribe": EmailSendStatus.UNSUBSCRIBED,
        "unsubscribed": EmailSendStatus.UNSUBSCRIBED,
        "spamreport": EmailSendStatus.UNSUBSCRIBED,
        "complaint": EmailSendStatus.UNSUBSCRIBED,
        "spam_complaint": EmailSendStatus.UNSUBSCRIBED,
    }
    return status_map.get(normalized)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class MarketingCampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    campaign_type: MarketingCampaignType = MarketingCampaignType.MULTI_CHANNEL
    status: MarketingCampaignStatus = MarketingCampaignStatus.DRAFT
    budget: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = Field(default="NGN", min_length=1, max_length=10)
    utm_params: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None

    @field_validator("name")
    @classmethod
    def _campaign_name_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("currency")
    @classmethod
    def _campaign_currency_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("currency must not be blank")
        return value


class MarketingCampaignUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    campaign_type: Optional[MarketingCampaignType] = None
    status: Optional[MarketingCampaignStatus] = None
    budget: Optional[Decimal] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=1, max_length=10)
    utm_params: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, Any]] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None

    @field_validator("name")
    @classmethod
    def _campaign_name_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("currency")
    @classmethod
    def _campaign_currency_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("currency must not be blank")
        return value


class MarketingCampaignResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    campaign_type: MarketingCampaignType
    status: MarketingCampaignStatus
    budget: Decimal
    currency: str
    utm_params: Dict[str, Any]
    metrics: Dict[str, Any]
    starts_at: Optional[datetime]
    ends_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JourneyTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    category: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    template_config: Dict[str, Any] = Field(default_factory=dict)
    is_system_template: bool = False

    @field_validator("name")
    @classmethod
    def _template_name_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class JourneyTemplateUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    category: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    template_config: Optional[Dict[str, Any]] = None
    is_system_template: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def _template_name_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class JourneyTemplateResponse(BaseModel):
    id: int
    name: str
    category: Optional[str]
    description: Optional[str]
    template_config: Dict[str, Any]
    is_system_template: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JourneyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    template_id: Optional[int] = Field(default=None, gt=0)
    campaign_id: Optional[int] = Field(default=None, gt=0)
    status: JourneyStatus = JourneyStatus.DRAFT
    entry_trigger: Optional[str] = Field(default=None, max_length=255)
    exit_conditions: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _journey_name_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class JourneyUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    template_id: Optional[int] = Field(default=None, gt=0)
    campaign_id: Optional[int] = Field(default=None, gt=0)
    status: Optional[JourneyStatus] = None
    entry_trigger: Optional[str] = Field(default=None, max_length=255)
    exit_conditions: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, Any]] = None

    @field_validator("name")
    @classmethod
    def _journey_name_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class JourneyResponse(BaseModel):
    id: int
    name: str
    template_id: Optional[int]
    campaign_id: Optional[int]
    status: JourneyStatus
    entry_trigger: Optional[str]
    exit_conditions: Dict[str, Any]
    metrics: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JourneyStepCreate(BaseModel):
    journey_id: int = Field(..., gt=0)
    step_order: int = Field(default=0, ge=0)
    step_type: JourneyStepType = JourneyStepType.EMAIL
    name: Optional[str] = Field(default=None, max_length=120)
    delay_days: int = Field(default=0, ge=0)
    delay_hours: int = Field(default=0, ge=0)
    delay_minutes: int = Field(default=0, ge=0)
    content: Dict[str, Any] = Field(default_factory=dict)
    email_template_id: Optional[int] = Field(default=None, gt=0)
    webhook_url: Optional[str] = Field(default=None, max_length=500)
    condition_config: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _step_name_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class JourneyStepUpdate(BaseModel):
    step_order: Optional[int] = Field(default=None, ge=0)
    step_type: Optional[JourneyStepType] = None
    name: Optional[str] = Field(default=None, max_length=120)
    delay_days: Optional[int] = Field(default=None, ge=0)
    delay_hours: Optional[int] = Field(default=None, ge=0)
    delay_minutes: Optional[int] = Field(default=None, ge=0)
    content: Optional[Dict[str, Any]] = None
    email_template_id: Optional[int] = Field(default=None, gt=0)
    webhook_url: Optional[str] = Field(default=None, max_length=500)
    condition_config: Optional[Dict[str, Any]] = None

    @field_validator("name")
    @classmethod
    def _step_name_not_blank_update(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class JourneyStepResponse(BaseModel):
    id: int
    journey_id: int
    step_order: int
    step_type: JourneyStepType
    name: Optional[str]
    delay_days: int
    delay_hours: int
    delay_minutes: int
    content: Dict[str, Any]
    email_template_id: Optional[int]
    webhook_url: Optional[str]
    condition_config: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SocialAccountCreate(BaseModel):
    platform: SocialPlatform = SocialPlatform.FACEBOOK
    account_id: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = Field(default=None, max_length=255)
    profile_url: Optional[str] = Field(default=None, max_length=500)
    access_token_encrypted: Optional[str] = None
    refresh_token_encrypted: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    stats: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("account_id")
    @classmethod
    def _account_id_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("account_id must not be blank")
        return value


class SocialAccountUpdate(BaseModel):
    platform: Optional[SocialPlatform] = None
    account_id: Optional[str] = Field(default=None, min_length=1, max_length=255)
    display_name: Optional[str] = Field(default=None, max_length=255)
    profile_url: Optional[str] = Field(default=None, max_length=500)
    access_token_encrypted: Optional[str] = None
    refresh_token_encrypted: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    stats: Optional[Dict[str, Any]] = None

    @field_validator("account_id")
    @classmethod
    def _account_id_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("account_id must not be blank")
        return value


class SocialAccountResponse(BaseModel):
    id: int
    platform: SocialPlatform
    account_id: str
    display_name: Optional[str]
    profile_url: Optional[str]
    access_token_encrypted: Optional[str]
    refresh_token_encrypted: Optional[str]
    token_expires_at: Optional[datetime]
    stats: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SocialPostCreate(BaseModel):
    account_id: int = Field(..., gt=0)
    content: str = Field(..., min_length=1, max_length=5000)
    media_urls: List[str] = Field(default_factory=list)
    scheduled_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    status: SocialPostStatus = SocialPostStatus.DRAFT
    platform_post_id: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None

    @field_validator("content")
    @classmethod
    def _post_content_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("content must not be blank")
        return value


class SocialPostUpdate(BaseModel):
    account_id: Optional[int] = Field(default=None, gt=0)
    content: Optional[str] = Field(default=None, min_length=1, max_length=5000)
    media_urls: Optional[List[str]] = None
    scheduled_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    status: Optional[SocialPostStatus] = None
    platform_post_id: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    @field_validator("content")
    @classmethod
    def _post_content_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("content must not be blank")
        return value


class SocialPostResponse(BaseModel):
    id: int
    account_id: int
    content: str
    media_urls: List[str]
    scheduled_at: Optional[datetime]
    published_at: Optional[datetime]
    status: SocialPostStatus
    platform_post_id: Optional[str]
    metrics: Dict[str, Any]
    error: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmailTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    subject: Optional[str] = Field(default=None, max_length=200)
    body_html: Optional[str] = Field(default=None, max_length=20000)
    body_text: Optional[str] = Field(default=None, max_length=20000)
    variables: List[str] = Field(default_factory=list)
    is_system_template: bool = False

    @field_validator("name")
    @classmethod
    def _template_name_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    subject: Optional[str] = Field(default=None, max_length=200)
    body_html: Optional[str] = Field(default=None, max_length=20000)
    body_text: Optional[str] = Field(default=None, max_length=20000)
    variables: Optional[List[str]] = None
    is_system_template: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def _template_name_not_blank_update(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class EmailTemplateResponse(BaseModel):
    id: int
    name: str
    subject: Optional[str]
    body_html: Optional[str]
    body_text: Optional[str]
    variables: List[str]
    is_system_template: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmailCampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    template_id: int = Field(..., gt=0)
    audience_id: Optional[int] = Field(default=None, gt=0)
    campaign_id: Optional[int] = Field(default=None, gt=0)
    status: EmailCampaignStatus = EmailCampaignStatus.DRAFT
    scheduled_at: Optional[datetime] = None
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    send_window_start: Optional[int] = Field(default=None, ge=0, le=23)
    send_window_end: Optional[int] = Field(default=None, ge=0, le=23)
    metrics: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _email_campaign_name_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @model_validator(mode="after")
    def _validate_send_window(self) -> "EmailCampaignCreate":
        if self.send_window_start is not None and self.send_window_end is not None:
            if self.send_window_start == self.send_window_end:
                raise ValueError("send_window_start and send_window_end must differ")
        return self


class EmailCampaignUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    template_id: Optional[int] = Field(default=None, gt=0)
    audience_id: Optional[int] = Field(default=None, gt=0)
    campaign_id: Optional[int] = Field(default=None, gt=0)
    status: Optional[EmailCampaignStatus] = None
    scheduled_at: Optional[datetime] = None
    timezone: Optional[str] = Field(default=None, min_length=1, max_length=64)
    send_window_start: Optional[int] = Field(default=None, ge=0, le=23)
    send_window_end: Optional[int] = Field(default=None, ge=0, le=23)
    metrics: Optional[Dict[str, Any]] = None

    @field_validator("name")
    @classmethod
    def _email_campaign_name_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @model_validator(mode="after")
    def _validate_send_window(self) -> "EmailCampaignUpdate":
        if self.send_window_start is not None and self.send_window_end is not None:
            if self.send_window_start == self.send_window_end:
                raise ValueError("send_window_start and send_window_end must differ")
        return self


class EmailCampaignResponse(BaseModel):
    id: int
    name: str
    template_id: int
    audience_id: Optional[int]
    campaign_id: Optional[int]
    status: EmailCampaignStatus
    scheduled_at: Optional[datetime]
    timezone: str
    send_window_start: Optional[int]
    send_window_end: Optional[int]
    metrics: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AudienceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    filter_criteria: Dict[str, Any] = Field(default_factory=dict)
    member_count: int = Field(default=0, ge=0)

    @field_validator("name")
    @classmethod
    def _audience_name_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class AudienceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    filter_criteria: Optional[Dict[str, Any]] = None
    member_count: Optional[int] = Field(default=None, ge=0)

    @field_validator("name")
    @classmethod
    def _audience_name_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class AudienceResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    filter_criteria: Dict[str, Any]
    member_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IntegrationCreate(BaseModel):
    integration_type: str = Field(..., min_length=1, max_length=120)
    credentials_encrypted: Optional[str] = Field(default=None, max_length=2000)
    status: MarketingIntegrationStatus = MarketingIntegrationStatus.DISCONNECTED
    settings: Dict[str, Any] = Field(default_factory=dict)
    last_synced_at: Optional[datetime] = None

    @field_validator("integration_type")
    @classmethod
    def _integration_type_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("integration_type must not be blank")
        return value


class IntegrationUpdate(BaseModel):
    integration_type: Optional[str] = Field(default=None, min_length=1, max_length=120)
    credentials_encrypted: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[MarketingIntegrationStatus] = None
    settings: Optional[Dict[str, Any]] = None
    last_synced_at: Optional[datetime] = None

    @field_validator("integration_type")
    @classmethod
    def _integration_type_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("integration_type must not be blank")
        return value


class IntegrationResponse(BaseModel):
    id: int
    integration_type: str
    credentials_encrypted: Optional[str]
    status: MarketingIntegrationStatus
    settings: Dict[str, Any]
    last_synced_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OAuthStartRequest(BaseModel):
    redirect_uri: Optional[str] = None
    scopes: Optional[List[str]] = None
    state: Optional[str] = None
    code_challenge: Optional[str] = None


class OAuthStartResponse(BaseModel):
    authorization_url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    code: str
    redirect_uri: Optional[str] = None
    state: Optional[str] = None
    code_verifier: Optional[str] = None


class OAuthRefreshRequest(BaseModel):
    refresh_token: Optional[str] = None
    access_token: Optional[str] = None


class ConsentCreate(BaseModel):
    party_id: int = Field(..., gt=0)
    channel: ConsentChannel = ConsentChannel.EMAIL
    status: ConsentStatus = ConsentStatus.UNKNOWN
    source: Optional[str] = Field(default=None, max_length=255)


class ConsentUpdate(BaseModel):
    status: Optional[ConsentStatus] = None
    source: Optional[str] = Field(default=None, max_length=255)


class ConsentResponse(BaseModel):
    id: int
    party_id: int
    channel: ConsentChannel
    status: ConsentStatus
    source: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SuppressionCreate(BaseModel):
    party_id: int = Field(..., gt=0)
    channel: ConsentChannel = ConsentChannel.EMAIL
    reason: Optional[str] = Field(default=None, max_length=255)
    source: Optional[str] = Field(default=None, max_length=255)


class SuppressionResponse(BaseModel):
    id: int
    party_id: int
    channel: ConsentChannel
    reason: Optional[str]
    source: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/dashboard", dependencies=[marketing_read_dep])
async def get_marketing_dashboard(
    analytics_service: MarketingAnalyticsService = Depends(get_analytics_service),
):
    return {
        "stats": analytics_service.get_dashboard_stats(),
        "upcoming_sends": analytics_service.get_upcoming_sends(),
        "journeys": analytics_service.get_active_journeys(),
        "social_posts": analytics_service.get_scheduled_posts(),
        "audiences": analytics_service.get_top_audiences(),
    }


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------

@router.get("/campaigns", dependencies=[marketing_read_dep])
async def list_campaigns(
    campaign_service: CampaignService = Depends(get_campaign_service),
):
    return {
        "highlights": campaign_service.get_highlights(),
        "campaigns": campaign_service.list_campaigns(),
    }


@router.post("/campaigns", response_model=MarketingCampaignResponse, dependencies=[marketing_write_dep])
async def create_campaign(
    payload: MarketingCampaignCreate,
    db: Session = Depends(get_db),
    campaign_service: CampaignService = Depends(get_campaign_service),
):
    try:
        campaign = campaign_service.create_campaign(payload.model_dump())
        db.commit()
        db.refresh(campaign)
        return campaign
    except Exception as exc:
        handle_service_error(exc)


@router.get("/campaigns/{campaign_id}", response_model=MarketingCampaignResponse, dependencies=[marketing_read_dep])
async def get_campaign(
    campaign_id: int,
    campaign_service: CampaignService = Depends(get_campaign_service),
):
    try:
        return campaign_service.get_campaign(campaign_id)
    except Exception as exc:
        handle_service_error(exc)


@router.patch("/campaigns/{campaign_id}", response_model=MarketingCampaignResponse, dependencies=[marketing_write_dep])
async def update_campaign(
    campaign_id: int,
    payload: MarketingCampaignUpdate,
    db: Session = Depends(get_db),
    campaign_service: CampaignService = Depends(get_campaign_service),
):
    try:
        campaign = campaign_service.update_campaign(campaign_id, payload.model_dump(exclude_unset=True))
        db.commit()
        db.refresh(campaign)
        return campaign
    except Exception as exc:
        handle_service_error(exc)


@router.delete("/campaigns/{campaign_id}", dependencies=[marketing_write_dep])
async def delete_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    campaign_service: CampaignService = Depends(get_campaign_service),
):
    try:
        campaign_service.delete_campaign(campaign_id)
        db.commit()
        return {"status": "deleted"}
    except Exception as exc:
        handle_service_error(exc)


# ---------------------------------------------------------------------------
# Journeys
# ---------------------------------------------------------------------------

@router.get("/journeys", dependencies=[marketing_read_dep])
async def list_journeys(
    journey_service: JourneyService = Depends(get_journey_service),
):
    return {"journeys": journey_service.list_journeys()}


@router.post("/journeys", response_model=JourneyResponse, dependencies=[marketing_write_dep])
async def create_journey(
    payload: JourneyCreate,
    db: Session = Depends(get_db),
    journey_service: JourneyService = Depends(get_journey_service),
):
    try:
        journey = journey_service.create_journey(payload.model_dump())
        db.commit()
        db.refresh(journey)
        return journey
    except Exception as exc:
        handle_service_error(exc)


@router.get("/journeys/{journey_id}", response_model=JourneyResponse, dependencies=[marketing_read_dep])
async def get_journey(
    journey_id: int,
    journey_service: JourneyService = Depends(get_journey_service),
):
    try:
        return journey_service.get_journey(journey_id)
    except Exception as exc:
        handle_service_error(exc)


@router.patch("/journeys/{journey_id}", response_model=JourneyResponse, dependencies=[marketing_write_dep])
async def update_journey(
    journey_id: int,
    payload: JourneyUpdate,
    db: Session = Depends(get_db),
    journey_service: JourneyService = Depends(get_journey_service),
):
    try:
        journey = journey_service.update_journey(journey_id, payload.model_dump(exclude_unset=True))
        db.commit()
        db.refresh(journey)
        return journey
    except Exception as exc:
        handle_service_error(exc)


@router.delete("/journeys/{journey_id}", dependencies=[marketing_write_dep])
async def delete_journey(
    journey_id: int,
    db: Session = Depends(get_db),
    journey_service: JourneyService = Depends(get_journey_service),
):
    try:
        journey_service.delete_journey(journey_id)
        db.commit()
        return {"status": "deleted"}
    except Exception as exc:
        handle_service_error(exc)


@router.get("/journeys/templates", dependencies=[marketing_read_dep])
async def list_journey_templates(
    journey_service: JourneyService = Depends(get_journey_service),
):
    return {"templates": journey_service.list_templates()}


@router.post("/journeys/templates", response_model=JourneyTemplateResponse, dependencies=[marketing_write_dep])
async def create_journey_template(
    payload: JourneyTemplateCreate,
    db: Session = Depends(get_db),
    journey_service: JourneyService = Depends(get_journey_service),
):
    try:
        template = journey_service.create_template(payload.model_dump())
        db.commit()
        db.refresh(template)
        return template
    except Exception as exc:
        handle_service_error(exc)


@router.get("/journeys/templates/{template_id}", response_model=JourneyTemplateResponse, dependencies=[marketing_read_dep])
async def get_journey_template(
    template_id: int,
    journey_service: JourneyService = Depends(get_journey_service),
):
    try:
        return journey_service.get_template(template_id)
    except Exception as exc:
        handle_service_error(exc)


@router.patch("/journeys/templates/{template_id}", response_model=JourneyTemplateResponse, dependencies=[marketing_write_dep])
async def update_journey_template(
    template_id: int,
    payload: JourneyTemplateUpdate,
    db: Session = Depends(get_db),
    journey_service: JourneyService = Depends(get_journey_service),
):
    try:
        template = journey_service.update_template(template_id, payload.model_dump(exclude_unset=True))
        db.commit()
        db.refresh(template)
        return template
    except Exception as exc:
        handle_service_error(exc)


@router.delete("/journeys/templates/{template_id}", dependencies=[marketing_write_dep])
async def delete_journey_template(
    template_id: int,
    db: Session = Depends(get_db),
    journey_service: JourneyService = Depends(get_journey_service),
):
    try:
        journey_service.delete_template(template_id)
        db.commit()
        return {"status": "deleted"}
    except Exception as exc:
        handle_service_error(exc)


@router.get("/journeys/{journey_id}/steps", dependencies=[marketing_read_dep])
async def list_journey_steps(
    journey_id: int,
    journey_service: JourneyService = Depends(get_journey_service),
):
    return {"steps": journey_service.get_journey_steps(journey_id)}


@router.post("/journeys/steps", response_model=JourneyStepResponse, dependencies=[marketing_write_dep])
async def create_journey_step(
    payload: JourneyStepCreate,
    db: Session = Depends(get_db),
    journey_service: JourneyService = Depends(get_journey_service),
):
    try:
        step = journey_service.create_step(payload.model_dump())
        db.commit()
        db.refresh(step)
        return step
    except Exception as exc:
        handle_service_error(exc)


@router.get("/journeys/steps/{step_id}", response_model=JourneyStepResponse, dependencies=[marketing_read_dep])
async def get_journey_step(
    step_id: int,
    journey_service: JourneyService = Depends(get_journey_service),
):
    try:
        return journey_service.get_step(step_id)
    except Exception as exc:
        handle_service_error(exc)


@router.patch("/journeys/steps/{step_id}", response_model=JourneyStepResponse, dependencies=[marketing_write_dep])
async def update_journey_step(
    step_id: int,
    payload: JourneyStepUpdate,
    db: Session = Depends(get_db),
    journey_service: JourneyService = Depends(get_journey_service),
):
    try:
        step = journey_service.update_step(step_id, payload.model_dump(exclude_unset=True))
        db.commit()
        db.refresh(step)
        return step
    except Exception as exc:
        handle_service_error(exc)


@router.delete("/journeys/steps/{step_id}", dependencies=[marketing_write_dep])
async def delete_journey_step(
    step_id: int,
    db: Session = Depends(get_db),
    journey_service: JourneyService = Depends(get_journey_service),
):
    try:
        journey_service.delete_step(step_id)
        db.commit()
        return {"status": "deleted"}
    except Exception as exc:
        handle_service_error(exc)


# ---------------------------------------------------------------------------
# Social
# ---------------------------------------------------------------------------

@router.get("/social/posts", dependencies=[marketing_read_dep])
async def list_social_posts(
    social_service: SocialMediaService = Depends(get_social_service),
):
    return {"posts": social_service.list_posts()}


@router.post("/social/posts", response_model=SocialPostResponse, dependencies=[marketing_write_dep])
async def create_social_post(
    payload: SocialPostCreate,
    db: Session = Depends(get_db),
    social_service: SocialMediaService = Depends(get_social_service),
):
    try:
        post = social_service.create_post(payload.model_dump())
        db.commit()
        db.refresh(post)
        return post
    except Exception as exc:
        handle_service_error(exc)


@router.get("/social/posts/{post_id}", response_model=SocialPostResponse, dependencies=[marketing_read_dep])
async def get_social_post(
    post_id: int,
    social_service: SocialMediaService = Depends(get_social_service),
):
    try:
        return social_service.get_post(post_id)
    except Exception as exc:
        handle_service_error(exc)


@router.patch("/social/posts/{post_id}", response_model=SocialPostResponse, dependencies=[marketing_write_dep])
async def update_social_post(
    post_id: int,
    payload: SocialPostUpdate,
    db: Session = Depends(get_db),
    social_service: SocialMediaService = Depends(get_social_service),
):
    try:
        post = social_service.update_post(post_id, payload.model_dump(exclude_unset=True))
        db.commit()
        db.refresh(post)
        return post
    except Exception as exc:
        handle_service_error(exc)


@router.delete("/social/posts/{post_id}", dependencies=[marketing_write_dep])
async def delete_social_post(
    post_id: int,
    db: Session = Depends(get_db),
    social_service: SocialMediaService = Depends(get_social_service),
):
    try:
        social_service.delete_post(post_id)
        db.commit()
        return {"status": "deleted"}
    except Exception as exc:
        handle_service_error(exc)


@router.get("/social/accounts", dependencies=[marketing_read_dep])
async def list_social_accounts(
    social_service: SocialMediaService = Depends(get_social_service),
):
    return {"accounts": social_service.list_accounts()}


@router.post("/social/accounts", response_model=SocialAccountResponse, dependencies=[marketing_write_dep])
async def create_social_account(
    payload: SocialAccountCreate,
    db: Session = Depends(get_db),
    social_service: SocialMediaService = Depends(get_social_service),
):
    try:
        account = social_service.create_account(payload.model_dump())
        db.commit()
        db.refresh(account)
        return account
    except Exception as exc:
        handle_service_error(exc)


@router.get("/social/accounts/{account_id}", response_model=SocialAccountResponse, dependencies=[marketing_read_dep])
async def get_social_account(
    account_id: int,
    social_service: SocialMediaService = Depends(get_social_service),
):
    try:
        return social_service.get_account(account_id)
    except Exception as exc:
        handle_service_error(exc)


@router.patch("/social/accounts/{account_id}", response_model=SocialAccountResponse, dependencies=[marketing_write_dep])
async def update_social_account(
    account_id: int,
    payload: SocialAccountUpdate,
    db: Session = Depends(get_db),
    social_service: SocialMediaService = Depends(get_social_service),
):
    try:
        account = social_service.update_account(account_id, payload.model_dump(exclude_unset=True))
        db.commit()
        db.refresh(account)
        return account
    except Exception as exc:
        handle_service_error(exc)


@router.delete("/social/accounts/{account_id}", dependencies=[marketing_write_dep])
async def delete_social_account(
    account_id: int,
    db: Session = Depends(get_db),
    social_service: SocialMediaService = Depends(get_social_service),
):
    try:
        social_service.delete_account(account_id)
        db.commit()
        return {"status": "deleted"}
    except Exception as exc:
        handle_service_error(exc)


@router.get("/social/calendar", dependencies=[marketing_read_dep])
async def get_social_calendar(
    social_service: SocialMediaService = Depends(get_social_service),
):
    return {
        "days": social_service.list_calendar_days(),
        "posts": social_service.list_calendar_posts(),
    }


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

@router.get("/email/campaigns", dependencies=[marketing_read_dep])
async def list_email_campaigns(
    email_service: EmailCampaignService = Depends(get_email_service),
):
    return {"campaigns": email_service.list_campaigns()}


@router.post("/email/campaigns", response_model=EmailCampaignResponse, dependencies=[marketing_write_dep])
async def create_email_campaign(
    payload: EmailCampaignCreate,
    db: Session = Depends(get_db),
    email_service: EmailCampaignService = Depends(get_email_service),
):
    try:
        campaign = email_service.create_campaign(payload.model_dump())
        db.commit()
        db.refresh(campaign)
        return campaign
    except Exception as exc:
        handle_service_error(exc)


@router.get("/email/campaigns/{campaign_id}", response_model=EmailCampaignResponse, dependencies=[marketing_read_dep])
async def get_email_campaign(
    campaign_id: int,
    email_service: EmailCampaignService = Depends(get_email_service),
):
    try:
        return email_service.get_campaign(campaign_id)
    except Exception as exc:
        handle_service_error(exc)


@router.patch("/email/campaigns/{campaign_id}", response_model=EmailCampaignResponse, dependencies=[marketing_write_dep])
async def update_email_campaign(
    campaign_id: int,
    payload: EmailCampaignUpdate,
    db: Session = Depends(get_db),
    email_service: EmailCampaignService = Depends(get_email_service),
):
    try:
        campaign = email_service.update_campaign(campaign_id, payload.model_dump(exclude_unset=True))
        db.commit()
        db.refresh(campaign)
        return campaign
    except Exception as exc:
        handle_service_error(exc)


@router.delete("/email/campaigns/{campaign_id}", dependencies=[marketing_write_dep])
async def delete_email_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    email_service: EmailCampaignService = Depends(get_email_service),
):
    try:
        email_service.delete_campaign(campaign_id)
        db.commit()
        return {"status": "deleted"}
    except Exception as exc:
        handle_service_error(exc)


@router.get("/email/templates", dependencies=[marketing_read_dep])
async def list_email_templates(
    email_service: EmailCampaignService = Depends(get_email_service),
):
    return {"templates": email_service.list_templates()}


@router.post("/email/templates", response_model=EmailTemplateResponse, dependencies=[marketing_write_dep])
async def create_email_template(
    payload: EmailTemplateCreate,
    db: Session = Depends(get_db),
    email_service: EmailCampaignService = Depends(get_email_service),
):
    try:
        template = email_service.create_template(payload.model_dump())
        db.commit()
        db.refresh(template)
        return template
    except Exception as exc:
        handle_service_error(exc)


@router.get("/email/templates/{template_id}", response_model=EmailTemplateResponse, dependencies=[marketing_read_dep])
async def get_email_template(
    template_id: int,
    email_service: EmailCampaignService = Depends(get_email_service),
):
    try:
        return email_service.get_template(template_id)
    except Exception as exc:
        handle_service_error(exc)


@router.patch("/email/templates/{template_id}", response_model=EmailTemplateResponse, dependencies=[marketing_write_dep])
async def update_email_template(
    template_id: int,
    payload: EmailTemplateUpdate,
    db: Session = Depends(get_db),
    email_service: EmailCampaignService = Depends(get_email_service),
):
    try:
        template = email_service.update_template(template_id, payload.model_dump(exclude_unset=True))
        db.commit()
        db.refresh(template)
        return template
    except Exception as exc:
        handle_service_error(exc)


@router.delete("/email/templates/{template_id}", dependencies=[marketing_write_dep])
async def delete_email_template(
    template_id: int,
    db: Session = Depends(get_db),
    email_service: EmailCampaignService = Depends(get_email_service),
):
    try:
        email_service.delete_template(template_id)
        db.commit()
        return {"status": "deleted"}
    except Exception as exc:
        handle_service_error(exc)


@router.get("/email/kpis", dependencies=[marketing_read_dep])
async def get_email_kpis(
    email_service: EmailCampaignService = Depends(get_email_service),
):
    return {"kpis": email_service.get_kpis()}


@router.get("/email/analytics", dependencies=[marketing_read_dep])
async def get_email_analytics(
    email_service: EmailCampaignService = Depends(get_email_service),
):
    return {
        "metrics": email_service.get_metrics(),
        "top_campaigns": email_service.get_top_campaigns(),
    }


# ---------------------------------------------------------------------------
# Audiences, Integrations, Consent
# ---------------------------------------------------------------------------

@router.get("/audiences", dependencies=[marketing_read_dep])
async def list_audiences(
    audience_service: AudienceService = Depends(get_audience_service),
):
    return {"audiences": audience_service.list_audiences()}


@router.post("/audiences", response_model=AudienceResponse, dependencies=[marketing_write_dep])
async def create_audience(
    payload: AudienceCreate,
    db: Session = Depends(get_db),
    audience_service: AudienceService = Depends(get_audience_service),
):
    try:
        audience = audience_service.create_audience(payload.model_dump())
        db.commit()
        db.refresh(audience)
        return audience
    except Exception as exc:
        handle_service_error(exc)


@router.get("/audiences/{audience_id}", response_model=AudienceResponse, dependencies=[marketing_read_dep])
async def get_audience(
    audience_id: int,
    audience_service: AudienceService = Depends(get_audience_service),
):
    try:
        return audience_service.get_audience(audience_id)
    except Exception as exc:
        handle_service_error(exc)


@router.patch("/audiences/{audience_id}", response_model=AudienceResponse, dependencies=[marketing_write_dep])
async def update_audience(
    audience_id: int,
    payload: AudienceUpdate,
    db: Session = Depends(get_db),
    audience_service: AudienceService = Depends(get_audience_service),
):
    try:
        audience = audience_service.update_audience(audience_id, payload.model_dump(exclude_unset=True))
        db.commit()
        db.refresh(audience)
        return audience
    except Exception as exc:
        handle_service_error(exc)


@router.delete("/audiences/{audience_id}", dependencies=[marketing_write_dep])
async def delete_audience(
    audience_id: int,
    db: Session = Depends(get_db),
    audience_service: AudienceService = Depends(get_audience_service),
):
    try:
        audience_service.delete_audience(audience_id)
        db.commit()
        return {"status": "deleted"}
    except Exception as exc:
        handle_service_error(exc)


@router.get("/integrations", dependencies=[marketing_read_dep])
async def list_integrations(
    integration_service: IntegrationService = Depends(get_integration_service),
):
    return {"integrations": integration_service.list_integrations()}


@router.post("/integrations", response_model=IntegrationResponse, dependencies=[marketing_write_dep])
async def create_integration(
    payload: IntegrationCreate,
    db: Session = Depends(get_db),
    integration_service: IntegrationService = Depends(get_integration_service),
):
    try:
        integration = integration_service.create_integration(payload.model_dump())
        db.commit()
        db.refresh(integration)
        return integration
    except Exception as exc:
        handle_service_error(exc)


@router.get("/integrations/{integration_id}", response_model=IntegrationResponse, dependencies=[marketing_read_dep])
async def get_integration(
    integration_id: int,
    integration_service: IntegrationService = Depends(get_integration_service),
):
    try:
        return integration_service.get_integration(integration_id)
    except Exception as exc:
        handle_service_error(exc)


@router.patch("/integrations/{integration_id}", response_model=IntegrationResponse, dependencies=[marketing_write_dep])
async def update_integration(
    integration_id: int,
    payload: IntegrationUpdate,
    db: Session = Depends(get_db),
    integration_service: IntegrationService = Depends(get_integration_service),
):
    try:
        integration = integration_service.update_integration(integration_id, payload.model_dump(exclude_unset=True))
        db.commit()
        db.refresh(integration)
        return integration
    except Exception as exc:
        handle_service_error(exc)


@router.delete("/integrations/{integration_id}", dependencies=[marketing_write_dep])
async def delete_integration(
    integration_id: int,
    db: Session = Depends(get_db),
    integration_service: IntegrationService = Depends(get_integration_service),
):
    try:
        integration_service.delete_integration(integration_id)
        db.commit()
        return {"status": "deleted"}
    except Exception as exc:
        handle_service_error(exc)


@router.post(
    "/integrations/{integration_type}/oauth/start",
    response_model=OAuthStartResponse,
    dependencies=[marketing_write_dep],
)
async def start_integration_oauth(
    integration_type: str,
    payload: OAuthStartRequest,
    db: Session = Depends(get_db),
    service: IntegrationService = Depends(get_integration_service),
):
    integration = service.get_or_create_by_type(integration_type)
    state = payload.state or f"mk-{secrets.token_urlsafe(16)}"
    service.set_oauth_state(integration, state)

    if integration_type == "whatsapp":
        raise HTTPException(status_code=400, detail="WhatsApp OAuth is not supported")

    client = get_oauth_client(integration_type)
    try:
        if integration_type == "twitter":
            if not payload.code_challenge:
                raise HTTPException(status_code=400, detail="code_challenge is required for Twitter OAuth")
            url = client.get_authorization_url(
                payload.redirect_uri,
                state=state,
                code_challenge=payload.code_challenge,
                scopes=payload.scopes,
            )
        else:
            url = client.get_authorization_url(
                payload.redirect_uri,
                state=state,
                scopes=payload.scopes,
            )
    finally:
        await client.close()

    db.commit()
    return OAuthStartResponse(authorization_url=url, state=state)


@router.post(
    "/integrations/{integration_type}/oauth/callback",
    dependencies=[marketing_write_dep],
)
async def complete_integration_oauth(
    integration_type: str,
    payload: OAuthCallbackRequest,
    db: Session = Depends(get_db),
    service: IntegrationService = Depends(get_integration_service),
):
    integration = service.get_or_create_by_type(integration_type)
    if payload.state and not service.validate_oauth_state(integration, payload.state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    if integration_type == "whatsapp":
        raise HTTPException(status_code=400, detail="WhatsApp OAuth is not supported")

    client = get_oauth_client(integration_type)
    try:
        if integration_type == "twitter":
            if not payload.code_verifier:
                raise HTTPException(status_code=400, detail="code_verifier is required for Twitter OAuth")
            token_payload = await client.exchange_code(
                payload.code,
                redirect_uri=payload.redirect_uri,
                code_verifier=payload.code_verifier,
            )
        else:
            token_payload = await client.exchange_code(payload.code, redirect_uri=payload.redirect_uri)
    finally:
        await client.close()

    service.store_credentials(integration, {**token_payload, "obtained_at": datetime.utcnow().isoformat()})
    integration.last_synced_at = datetime.utcnow()
    db.commit()
    return {"status": "connected"}


@router.post(
    "/integrations/{integration_type}/oauth/refresh",
    dependencies=[marketing_write_dep],
)
async def refresh_integration_oauth(
    integration_type: str,
    payload: OAuthRefreshRequest,
    db: Session = Depends(get_db),
    service: IntegrationService = Depends(get_integration_service),
):
    integration = service.get_or_create_by_type(integration_type)
    stored = service.get_credentials(integration)
    refresh_token = payload.refresh_token or stored.get("refresh_token")
    access_token = payload.access_token or stored.get("access_token")

    client = get_oauth_client(integration_type, access_token=access_token)
    try:
        if integration_type in {"meta", "whatsapp"}:
            if not access_token:
                raise HTTPException(status_code=400, detail="access_token is required for refresh")
            token_payload = await client.refresh_access_token(access_token)
        else:
            if not refresh_token:
                raise HTTPException(status_code=400, detail="refresh_token is required for refresh")
            token_payload = await client.refresh_access_token(refresh_token)
    finally:
        await client.close()

    service.store_credentials(integration, {**stored, **token_payload, "refreshed_at": datetime.utcnow().isoformat()})
    integration.last_synced_at = datetime.utcnow()
    db.commit()
    return {"status": "refreshed"}


@router.get("/consent", dependencies=[marketing_read_dep])
async def get_consent_overview(
    consent_service: ConsentService = Depends(get_consent_service),
):
    return {
        "overview": consent_service.get_overview(),
        "records": consent_service.list_records(),
        "suppressions": consent_service.list_suppressions(),
    }


@router.post("/consent", response_model=ConsentResponse, dependencies=[marketing_write_dep])
async def create_consent(
    payload: ConsentCreate,
    db: Session = Depends(get_db),
    consent_service: ConsentService = Depends(get_consent_service),
):
    try:
        consent = consent_service.create_consent(payload.model_dump())
        db.commit()
        db.refresh(consent)
        return consent
    except Exception as exc:
        handle_service_error(exc)


@router.get("/consent/{consent_id}", response_model=ConsentResponse, dependencies=[marketing_read_dep])
async def get_consent(
    consent_id: int,
    consent_service: ConsentService = Depends(get_consent_service),
):
    try:
        return consent_service.get_consent(consent_id)
    except Exception as exc:
        handle_service_error(exc)


@router.patch("/consent/{consent_id}", response_model=ConsentResponse, dependencies=[marketing_write_dep])
async def update_consent(
    consent_id: int,
    payload: ConsentUpdate,
    db: Session = Depends(get_db),
    consent_service: ConsentService = Depends(get_consent_service),
):
    try:
        consent = consent_service.update_consent(consent_id, payload.model_dump(exclude_unset=True))
        db.commit()
        db.refresh(consent)
        return consent
    except Exception as exc:
        handle_service_error(exc)


@router.delete("/consent/{consent_id}", dependencies=[marketing_write_dep])
async def delete_consent(
    consent_id: int,
    db: Session = Depends(get_db),
    consent_service: ConsentService = Depends(get_consent_service),
):
    try:
        consent_service.delete_consent(consent_id)
        db.commit()
        return {"status": "deleted"}
    except Exception as exc:
        handle_service_error(exc)


@router.post("/suppressions", response_model=SuppressionResponse, dependencies=[marketing_write_dep])
async def create_suppression(
    payload: SuppressionCreate,
    db: Session = Depends(get_db),
    consent_service: ConsentService = Depends(get_consent_service),
):
    try:
        suppression = consent_service.create_suppression(payload.model_dump())
        db.commit()
        db.refresh(suppression)
        return suppression
    except Exception as exc:
        handle_service_error(exc)


@router.delete("/suppressions/{suppression_id}", dependencies=[marketing_write_dep])
async def delete_suppression(
    suppression_id: int,
    db: Session = Depends(get_db),
    consent_service: ConsentService = Depends(get_consent_service),
):
    try:
        consent_service.delete_suppression(suppression_id)
        db.commit()
        return {"status": "deleted"}
    except Exception as exc:
        handle_service_error(exc)


@router.post("/seed-defaults", dependencies=[marketing_write_dep])
async def seed_marketing_defaults_endpoint(db: Session = Depends(get_db)):
    return seed_marketing_defaults(db)


@public_router.post("/consent/unsubscribe")
async def unsubscribe_contact(
    request: Request,
    db: Session = Depends(get_db),
    consent_service: ConsentService = Depends(get_consent_service),
):
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    token = (payload.get("token") if isinstance(payload, dict) else None) or request.query_params.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="token is required")

    try:
        party_id, consent_channel = parse_unsubscribe_token(token)
        consent_service.unsubscribe(party_id, consent_channel, source="unsubscribe")
        db.commit()
        return {"status": "ok"}
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@public_router.post("/webhooks/{platform}")
async def marketing_webhook(
    platform: str,
    request: Request,
    db: Session = Depends(get_db),
):
    if platform not in {"meta", "twitter", "linkedin", "whatsapp"}:
        raise HTTPException(status_code=400, detail="Unsupported platform")

    payload_bytes = await request.body()
    if not verify_platform_signature(platform, request.headers, payload_bytes):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    timestamp_header = request.headers.get("x-request-timestamp") or request.headers.get("x-timestamp")
    if timestamp_header:
        try:
            timestamp = datetime.fromtimestamp(int(timestamp_header), tz=timezone.utc)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid webhook timestamp") from exc
        now = datetime.now(timezone.utc)
        if abs((now - timestamp).total_seconds()) > 300:
            raise HTTPException(status_code=400, detail="Stale webhook event")

    payload_hash = compute_payload_hash(payload_bytes)
    event_id = extract_event_id(payload, request.headers) or payload_hash

    recent_cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    recent_payload = (
        db.query(MarketingWebhookEvent)
        .filter(
            MarketingWebhookEvent.platform == platform,
            MarketingWebhookEvent.payload_hash == payload_hash,
            MarketingWebhookEvent.received_at >= recent_cutoff,
        )
        .first()
    )
    if recent_payload:
        raise HTTPException(status_code=409, detail="Duplicate webhook payload")

    existing = (
        db.query(MarketingWebhookEvent)
        .filter(
            MarketingWebhookEvent.platform == platform,
            MarketingWebhookEvent.event_id == event_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Duplicate webhook event")

    db.add(
        MarketingWebhookEvent(
            platform=platform,
            event_id=event_id,
            payload_hash=payload_hash,
        )
    )

    if platform == "whatsapp" and isinstance(payload, dict):
        consent_service = ConsentService(db)
        status = payload.get("status")
        party_id = payload.get("party_id")
        if status in {"opt_in", "opt_out"} and party_id:
            action = "opt_out" if status == "opt_out" else "opt_in"
            _apply_whatsapp_consent(db, consent_service, party_id, action)
        else:
            for event in _extract_whatsapp_messages(payload):
                sender = _normalize_phone(event.get("from"))
                party_id = _find_party_id_by_phone(db, sender)
                if not party_id:
                    continue
                text = (event.get("text") or "").strip().lower()
                if text in {"stop", "unsubscribe", "opt out", "optout"}:
                    _apply_whatsapp_consent(db, consent_service, party_id, "opt_out")
                else:
                    _apply_whatsapp_consent(db, consent_service, party_id, "opt_in")
        for status_event in _extract_whatsapp_statuses(payload):
            _update_whatsapp_post_status(db, status_event)

    try:
        ingest_marketing_webhook(
            db=db,
            platform=platform,
            payload=payload if isinstance(payload, dict) else {},
            headers=dict(request.headers),
            provider_event_id=str(event_id),
        )
    except Exception:
        pass

    db.commit()
    return {"status": "ok"}


@public_router.post("/email/events")
async def email_tracking_event(
    request: Request,
    db: Session = Depends(get_db),
):
    payload = await request.json()
    events: List[dict] = []
    if isinstance(payload, list):
        events = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("events"), list):
            events = payload["events"]
        else:
            events = [payload]

    if not events:
        raise HTTPException(status_code=400, detail="No events supplied")

    updated = 0
    missing = 0
    for event in events:
        if not isinstance(event, dict):
            continue
        parsed = _extract_email_event_payload(event)
        send_id = parsed["send_id"]
        provider_message_id = parsed["provider_message_id"]
        event_type = parsed["event"]

        if not (send_id or provider_message_id):
            missing += 1
            continue

        query = db.query(EmailSend)
        if send_id:
            query = query.filter(EmailSend.id == send_id)
        else:
            query = query.filter(EmailSend.provider_message_id == provider_message_id)

        send = query.first()
        if not send:
            missing += 1
            continue

        new_status = _email_event_status(event_type)
        if new_status:
            send.status = new_status
            now = datetime.now(timezone.utc)
            if new_status == EmailSendStatus.DELIVERED:
                send.delivered_at = now
            elif new_status == EmailSendStatus.OPENED:
                send.opened_at = now
            elif new_status == EmailSendStatus.CLICKED:
                send.clicked_at = now
            elif new_status == EmailSendStatus.BOUNCED:
                send.bounced_at = now
            send.updated_at = now
            updated += 1

    if len(events) == 1 and updated == 0 and missing:
        raise HTTPException(status_code=404, detail="Email send not found")

    db.commit()
    return {"status": "ok", "updated": updated}


__all__ = ["router", "public_router"]
