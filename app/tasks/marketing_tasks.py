"""Celery tasks for marketing automation."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict, Iterable, List
from urllib.parse import urlparse

import httpx
import structlog
from zoneinfo import ZoneInfo

from app.config import settings
from app.worker import celery_app
from app.database import SessionLocal
from app.models.marketing import (
    ConsentChannel,
    ConsentStatus,
    CustomerJourney,
    EmailCampaign,
    EmailCampaignStatus,
    EmailTemplate,
    EmailSend,
    EmailSendStatus,
    JourneyEnrollment,
    JourneyEnrollmentStatus,
    JourneyStep,
    JourneyStepType,
    MarketingAudience,
    MarketingConsent,
    SocialAccount,
    SocialPost,
    SocialPostStatus,
    SocialPlatform,
    SuppressionEntry,
)
from app.integrations.marketing import MetaBusinessClient, TwitterClient, LinkedInClient, WhatsAppBusinessClient
from app.services.marketing.consent_service import create_unsubscribe_token
from app.services.marketing.integration_service import IntegrationService
from app.services.marketing.oauth_service import MarketingOAuthService
from app.services.secrets_service import get_secrets
from app.models.party import Party
from sqlalchemy import and_, or_

logger = structlog.get_logger()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get_timezone(name: Optional[str]) -> timezone:
    if not name:
        return timezone.utc
    try:
        return ZoneInfo(name)
    except Exception:
        return timezone.utc


def _is_within_send_window(
    now: datetime,
    tz_name: Optional[str],
    window_start: Optional[int],
    window_end: Optional[int],
) -> bool:
    if window_start is None or window_end is None:
        return True
    local = now.astimezone(_get_timezone(tz_name))
    hour = local.hour
    if window_start < window_end:
        return window_start <= hour < window_end
    return hour >= window_start or hour < window_end


def _step_delay(step: JourneyStep) -> timedelta:
    return timedelta(
        days=step.delay_days or 0,
        hours=step.delay_hours or 0,
        minutes=step.delay_minutes or 0,
    )


def _should_send_marketing(
    db,
    party_id: int,
    channel: ConsentChannel,
) -> bool:
    suppressed = (
        db.query(SuppressionEntry)
        .filter(
            SuppressionEntry.party_id == party_id,
            SuppressionEntry.channel == channel,
        )
        .first()
    )
    if suppressed:
        return False

    consent = (
        db.query(MarketingConsent)
        .filter(
            MarketingConsent.party_id == party_id,
            MarketingConsent.channel == channel,
        )
        .first()
    )
    if not consent:
        return False
    return consent.status == ConsentStatus.GRANTED


def _record_engagement(enrollment: JourneyEnrollment, key: str, value: str) -> None:
    engagement = enrollment.engagement or {}
    engagement[key] = value
    enrollment.engagement = engagement


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _decrypt_secret(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    secrets_service = get_secrets()
    try:
        return secrets_service.decrypt(value)
    except Exception:
        return value


def _resolve_whatsapp_settings(
    db,
    account: SocialAccount,
) -> Dict[str, Any]:
    integration_service = IntegrationService(db)
    integration = integration_service.get_or_create_by_type("whatsapp")
    credentials = integration_service.get_credentials(integration)
    settings = integration.settings or {}

    access_token = _decrypt_secret(account.access_token_encrypted) or credentials.get("access_token")
    phone_number_id = account.account_id or settings.get("phone_number_id") or settings.get("whatsapp_phone_number_id")

    default_recipient = None
    if isinstance(account.stats, dict):
        default_recipient = account.stats.get("default_recipient")
    if not default_recipient:
        default_recipient = settings.get("default_recipient") or settings.get("default_to")

    return {
        "access_token": access_token,
        "phone_number_id": phone_number_id,
        "default_recipient": default_recipient,
    }


def _resolve_whatsapp_recipients(
    post: SocialPost,
    default_recipient: Optional[str],
) -> List[str]:
    metrics = post.metrics or {}
    recipients = metrics.get("recipients") or metrics.get("to")
    if isinstance(recipients, str):
        return [recipients]
    if isinstance(recipients, list):
        return [str(item) for item in recipients if item]
    if default_recipient:
        return [default_recipient]
    return []


def _build_whatsapp_body(post: SocialPost) -> str:
    content = (post.content or "").strip()
    media_urls = [url for url in (post.media_urls or []) if url]
    if media_urls:
        media_text = "\n".join(media_urls)
        if content:
            return f"{content}\n\n{media_text}"
        return media_text
    return content or "Marketing update"


def _whatsapp_media_payload(url: str, caption: Optional[str]) -> Dict[str, Any]:
    media_type = _infer_whatsapp_media_type(url)
    payload = {
        "type": media_type,
        media_type: {"link": url},
    }
    if caption:
        payload[media_type]["caption"] = caption
    return payload


def _infer_whatsapp_media_type(url: str) -> str:
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    if path.endswith((".mp4", ".mov", ".m4v", ".webm")):
        return "video"
    if path.endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")):
        return "document"
    return "image"


def _infer_media_type(url: str) -> str:
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    if path.endswith((".mp4", ".mov", ".m4v", ".webm")):
        return "video"
    if path.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
        return "image"
    return "unknown"


def _resolve_social_credentials(
    db,
    account: SocialAccount,
    integration_type: str,
) -> Dict[str, Optional[str]]:
    integration_service = IntegrationService(db)
    integration = integration_service.get_or_create_by_type(integration_type)
    credentials = integration_service.get_credentials(integration)
    return {
        "access_token": _decrypt_secret(account.access_token_encrypted) or credentials.get("access_token"),
        "refresh_token": _decrypt_secret(account.refresh_token_encrypted) or credentials.get("refresh_token"),
    }


def _resolve_meta_page_id(account: SocialAccount) -> Optional[str]:
    if account.account_id:
        return account.account_id
    stats = account.stats or {}
    return stats.get("page_id") or stats.get("instagram_business_account_id") or stats.get("ig_user_id")


def _resolve_instagram_user_id(account: SocialAccount) -> Optional[str]:
    stats = account.stats or {}
    return stats.get("ig_user_id") or stats.get("instagram_user_id") or stats.get("instagram_business_account_id")


def _resolve_linkedin_author(account: SocialAccount) -> Optional[str]:
    if account.account_id:
        if account.account_id.startswith("urn:"):
            return account.account_id
        return f"urn:li:person:{account.account_id}"
    stats = account.stats or {}
    org_id = stats.get("organization_id")
    if org_id:
        return f"urn:li:organization:{org_id}"
    return None


def _append_unsubscribe_link(body: str, party_id: int, channel: ConsentChannel) -> str:
    base_url = settings.marketing_public_base_url
    if not base_url:
        return body
    token = create_unsubscribe_token(party_id, channel)
    url = f"{base_url.rstrip('/')}/marketing/consent/unsubscribe?token={token}"
    if any(tag in body.lower() for tag in ("<html", "<body", "<p", "<div", "<br")):
        return f"{body}\n\n<p style=\"font-size:12px;color:#6b7280\">To unsubscribe, <a href=\"{url}\">click here</a>.</p>"
    return f"{body}\n\nUnsubscribe: {url}"


def _evaluate_step_conditions(party: Party, config: dict) -> bool:
    if not config:
        return True
    if any(key in config for key in ("all", "any", "none")):
        all_conditions = _normalize_condition_list(config.get("all") or [])
        any_conditions = _normalize_condition_list(config.get("any") or [])
        none_conditions = _normalize_condition_list(config.get("none") or [])
    elif "conditions" in config:
        all_conditions = _normalize_condition_list(config.get("conditions") or [])
        any_conditions = []
        none_conditions = []
    else:
        all_conditions = _normalize_condition_list([config])
        any_conditions = []
        none_conditions = []

    if all_conditions and not all(_evaluate_condition(party, cond) for cond in all_conditions):
        return False
    if any_conditions and not any(_evaluate_condition(party, cond) for cond in any_conditions):
        return False
    if none_conditions and any(_evaluate_condition(party, cond) for cond in none_conditions):
        return False
    return True


def _select_branch_step(config: dict, outcome: bool) -> Dict[str, Optional[int]]:
    if not config:
        return {}
    if outcome:
        return {
            "next_step_id": config.get("true_step_id"),
            "next_step_order": config.get("true_step_order"),
        }
    return {
        "next_step_id": config.get("false_step_id"),
        "next_step_order": config.get("false_step_order"),
    }


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _normalize_filter_criteria(criteria: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    if not criteria:
        return {"all": [], "any": [], "none": []}

    if any(key in criteria for key in ("all", "any", "none")):
        return {
            "all": _normalize_condition_list(criteria.get("all", [])),
            "any": _normalize_condition_list(criteria.get("any", [])),
            "none": _normalize_condition_list(criteria.get("none", [])),
        }

    if isinstance(criteria.get("filters"), list):
        return {
            "all": _normalize_condition_list(criteria.get("filters", [])),
            "any": [],
            "none": [],
        }

    conditions: List[Dict[str, Any]] = []
    if "status" in criteria:
        conditions.append(_value_condition("status", criteria.get("status")))
    if "type" in criteria:
        conditions.append(_value_condition("type", criteria.get("type")))
    if "has_email" in criteria:
        conditions.append({"field": "has_email", "op": "is", "value": bool(criteria.get("has_email"))})
    if "has_phone" in criteria:
        conditions.append({"field": "has_phone", "op": "is", "value": bool(criteria.get("has_phone"))})
    if "do_not_contact" in criteria:
        conditions.append({"field": "do_not_contact", "op": "eq", "value": bool(criteria.get("do_not_contact"))})
    if "tag" in criteria:
        conditions.append(_value_condition("tag", criteria.get("tag")))

    return {"all": _normalize_condition_list(conditions), "any": [], "none": []}


def _normalize_condition_list(value: Iterable[Any]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for item in value or []:
        if not isinstance(item, dict):
            continue
        if "field" in item:
            condition = {
                "field": item.get("field"),
                "op": item.get("op", "eq"),
                "value": item.get("value"),
            }
        else:
            condition = _value_condition(next(iter(item.keys()), ""), next(iter(item.values()), None))
        normalized.append(condition)
    return normalized


def _value_condition(field: str, value: Any) -> Dict[str, Any]:
    if isinstance(value, list):
        return {"field": field, "op": "in", "value": value}
    return {"field": field, "op": "eq", "value": value}


def _sql_condition(condition: Dict[str, Any]) -> Optional[Any]:
    field = condition.get("field")
    op = condition.get("op", "eq")
    value = condition.get("value")

    field_map = {
        "status": Party.status,
        "type": Party.type,
        "preferred_channel": Party.preferred_channel,
        "locale": Party.locale,
        "timezone": Party.timezone,
        "do_not_contact": Party.do_not_contact,
        "engagement_score": Party.engagement_score,
        "last_engagement_at": Party.last_engagement_at,
        "last_contacted_at": Party.last_contacted_at,
        "created_at": Party.created_at,
        "updated_at": Party.updated_at,
        "primary_email": Party.primary_email,
        "primary_phone": Party.primary_phone,
    }

    if field in ("has_email", "has_phone"):
        column = Party.primary_email if field == "has_email" else Party.primary_phone
        should_exist = bool(value)
        if should_exist:
            return and_(column.isnot(None), column != "")
        return or_(column.is_(None), column == "")

    column = field_map.get(field)
    if column is None:
        return None

    if op == "eq":
        return column == value
    if op == "neq":
        return column != value
    if op == "in":
        return column.in_(value if isinstance(value, list) else [value])
    if op == "not_in":
        return column.notin_(value if isinstance(value, list) else [value])
    if op == "contains" and isinstance(value, str):
        return column.ilike(f"%{value}%")
    if op == "exists":
        if bool(value):
            return column.isnot(None)
        return column.is_(None)
    if op in {"gt", "gte", "lt", "lte", "between"}:
        if op == "between" and isinstance(value, list) and len(value) == 2:
            start_val = value[0]
            end_val = value[1]
            if isinstance(start_val, (int, float)) and isinstance(end_val, (int, float)):
                return column.between(start_val, end_val)
            start = _parse_datetime(start_val)
            end = _parse_datetime(end_val)
            if start and end:
                return column.between(start, end)
            return None

        if isinstance(value, (int, float)):
            dt_value = value
        else:
            dt_value = _parse_datetime(value)
            if dt_value is None:
                return None
        if op == "gt":
            return column > dt_value
        if op == "gte":
            return column >= dt_value
        if op == "lt":
            return column < dt_value
        if op == "lte":
            return column <= dt_value

    return None


def _evaluate_condition(party: Party, condition: Dict[str, Any]) -> bool:
    field = condition.get("field")
    op = condition.get("op", "eq")
    value = condition.get("value")

    if field == "has_email":
        return bool(party.primary_email) if value else not bool(party.primary_email)
    if field == "has_phone":
        return bool(party.primary_phone) if value else not bool(party.primary_phone)
    if field == "tag":
        tags = party.tags or []
        requested = set(value if isinstance(value, list) else [value])
        for tag in tags:
            if isinstance(tag, str) and tag in requested:
                return True
            if isinstance(tag, dict) and tag.get("name") in requested:
                return True
        return False

    if field and field.startswith("custom_fields."):
        key = field.split(".", 1)[1]
        current = (party.custom_fields or {}).get(key)
    elif field == "custom_field":
        key = condition.get("key")
        current = (party.custom_fields or {}).get(key) if key else None
    else:
        current = getattr(party, field, None) if field else None

    if op == "eq":
        return current == value
    if op == "neq":
        return current != value
    if op == "in":
        return current in (value if isinstance(value, list) else [value])
    if op == "not_in":
        return current not in (value if isinstance(value, list) else [value])
    if op == "contains" and isinstance(current, str) and isinstance(value, str):
        return value.lower() in current.lower()
    if op == "exists":
        return current is not None
    if op in {"gt", "gte", "lt", "lte", "between"}:
        if isinstance(current, str):
            current = _parse_datetime(current) or current
        if op == "between" and isinstance(value, list) and len(value) == 2:
            start = value[0]
            end = value[1]
            if isinstance(current, datetime):
                start = _parse_datetime(start) or start
                end = _parse_datetime(end) or end
            return current is not None and start <= current <= end
        if isinstance(current, datetime):
            compare_value = _parse_datetime(value) or value
        else:
            compare_value = value
        if op == "gt":
            return current is not None and current > compare_value
        if op == "gte":
            return current is not None and current >= compare_value
        if op == "lt":
            return current is not None and current < compare_value
        if op == "lte":
            return current is not None and current <= compare_value

    return False


def _get_or_create_email_campaign(db, journey: CustomerJourney, step: JourneyStep) -> EmailCampaign:
    name = f"Journey {journey.id} - {journey.name}"
    campaign = (
        db.query(EmailCampaign)
        .filter(
            EmailCampaign.name == name,
            EmailCampaign.template_id == step.email_template_id,
        )
        .first()
    )
    if campaign:
        return campaign

    campaign = EmailCampaign(
        name=name,
        template_id=step.email_template_id,
        campaign_id=journey.campaign_id,
        status=EmailCampaignStatus.SENDING,
    )
    db.add(campaign)
    return campaign


def _execute_step_action(
    db,
    journey: CustomerJourney,
    enrollment: JourneyEnrollment,
    step: JourneyStep,
    now: datetime,
) -> dict:
    party = db.query(Party).filter(Party.id == enrollment.party_id).first()
    if not party:
        return {"status": "failed", "error": "party_not_found"}

    if step.step_type == JourneyStepType.WEBHOOK:
        if not step.webhook_url:
            return {"status": "failed", "error": "missing_webhook_url"}
        payload = {
            "journey_id": journey.id,
            "journey_name": journey.name,
            "enrollment_id": enrollment.id,
            "party_id": enrollment.party_id,
            "step_id": step.id,
            "step_type": step.step_type.value,
            "content": step.content or {},
        }
        try:
            response = httpx.post(step.webhook_url, json=payload, timeout=10)
            if response.status_code >= 400:
                return {"status": "failed", "error": f"webhook_failed:{response.status_code}"}
        except Exception as exc:
            return {"status": "failed", "error": f"webhook_error:{exc}"}
        return {"status": "executed"}

    if step.step_type == JourneyStepType.EMAIL:
        if not step.email_template_id:
            return {"status": "skipped", "reason": "missing_template"}
        window_start = (step.content or {}).get("send_window_start")
        window_end = (step.content or {}).get("send_window_end")
        tz_name = (step.content or {}).get("timezone") or "UTC"
        if not _is_within_send_window(now, tz_name, window_start, window_end):
            return {"status": "skipped", "reason": "outside_send_window"}
        if not party.primary_email:
            return {"status": "skipped", "reason": "missing_email"}
        if not _should_send_marketing(db, party.id, ConsentChannel.EMAIL):
            return {"status": "skipped", "reason": "consent"}

        template = db.query(EmailTemplate).filter(EmailTemplate.id == step.email_template_id).first()
        if not template:
            return {"status": "failed", "error": "template_not_found"}

        subject = template.subject or (step.content or {}).get("subject") or "Marketing Update"
        body = template.body_text or template.body_html or (step.content or {}).get("body") or ""
        body = _append_unsubscribe_link(body, party.id, ConsentChannel.EMAIL)

        from app.services.notification_providers import get_email_provider
        provider = get_email_provider()
        try:
            result = _run_async(provider.send(to=party.primary_email, subject=subject, message=body))
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}

        campaign = _get_or_create_email_campaign(db, journey, step)
        send = EmailSend(
            campaign_id=campaign.id,
            party_id=party.id,
            status=EmailSendStatus.SENT if result.success else EmailSendStatus.FAILED,
            provider_message_id=result.external_id,
            sent_at=now if result.success else None,
            error=result.error_message if not result.success else None,
        )
        db.add(send)

        return {"status": "executed" if result.success else "failed", "error": result.error_message}

    if step.step_type == JourneyStepType.WHATSAPP:
        window_start = (step.content or {}).get("send_window_start")
        window_end = (step.content or {}).get("send_window_end")
        tz_name = (step.content or {}).get("timezone") or "UTC"
        if not _is_within_send_window(now, tz_name, window_start, window_end):
            return {"status": "skipped", "reason": "outside_send_window"}
        if not party.primary_phone:
            return {"status": "skipped", "reason": "missing_phone"}
        if not _should_send_marketing(db, party.id, ConsentChannel.WHATSAPP):
            return {"status": "skipped", "reason": "consent"}

        message = (step.content or {}).get("message") or (step.content or {}).get("body") or "Marketing update"
        from app.services.notification_providers import get_whatsapp_provider
        provider = get_whatsapp_provider()
        try:
            result = _run_async(provider.send(to=party.primary_phone, subject="", message=message))
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}

        return {"status": "executed" if result.success else "failed", "error": result.error_message}

    if step.step_type == JourneyStepType.SOCIAL_POST:
        account_id = (step.content or {}).get("account_id")
        if not account_id:
            return {"status": "skipped", "reason": "missing_social_account"}
        account = db.query(SocialAccount).filter(SocialAccount.id == account_id).first()
        if not account:
            return {"status": "failed", "error": "social_account_not_found"}
        content = (step.content or {}).get("content") or (step.content or {}).get("message") or step.name or ""
        if not content:
            return {"status": "skipped", "reason": "missing_content"}
        post = SocialPost(
            account_id=account.id,
            content=content,
            media_urls=(step.content or {}).get("media_urls") or [],
            scheduled_at=now,
            status=SocialPostStatus.SCHEDULED,
            metrics={"journey_id": journey.id, "step_id": step.id},
        )
        db.add(post)
        return {"status": "executed"}

    if step.step_type in {JourneyStepType.CONDITION, JourneyStepType.SPLIT}:
        config = step.condition_config or {}
        outcome = _evaluate_step_conditions(party, config)
        _record_engagement(enrollment, "last_condition", "true" if outcome else "false")
        return {"status": "executed", **_select_branch_step(config, outcome)}

    if step.step_type == JourneyStepType.TASK:
        payload = step.content or {}
        _record_engagement(enrollment, "last_task", str(payload.get("title") or step.name or "task"))
        return {"status": "executed"}

    if step.step_type in {JourneyStepType.EXIT}:
        return {"status": "exit"}

    # Condition/split/wait/social/task are currently no-ops but should advance.
    return {"status": "executed"}


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def process_journey_steps(self, batch_size: int = 100):
    """Advance journey enrollments that are due for their next action.

    This task executes the due step action and schedules the next action time.
    """
    task_name = "process_journey_steps"
    logger.info("task_started", task=task_name, batch_size=batch_size)

    db = SessionLocal()
    processed = 0

    try:
        now = _utc_now()
        enrollments = (
            db.query(JourneyEnrollment)
            .filter(
                JourneyEnrollment.status == JourneyEnrollmentStatus.ACTIVE,
                JourneyEnrollment.next_action_at.isnot(None),
                JourneyEnrollment.next_action_at <= now,
            )
            .order_by(JourneyEnrollment.next_action_at.asc())
            .limit(batch_size)
            .all()
        )

        for enrollment in enrollments:
            journey = db.query(CustomerJourney).filter(CustomerJourney.id == enrollment.journey_id).first()
            if not journey:
                continue

            steps = (
                db.query(JourneyStep)
                .filter(JourneyStep.journey_id == journey.id)
                .order_by(JourneyStep.step_order.asc())
                .all()
            )
            if not steps:
                continue

            current_index = 0
            if enrollment.current_step_id:
                for idx, step in enumerate(steps):
                    if step.id == enrollment.current_step_id:
                        current_index = idx + 1
                        break

            if current_index >= len(steps):
                enrollment.status = JourneyEnrollmentStatus.COMPLETED
                enrollment.next_action_at = None
            else:
                step = steps[current_index]
                result = _execute_step_action(db, journey, enrollment, step, now)

                if result["status"] == "failed":
                    enrollment.status = JourneyEnrollmentStatus.FAILED
                    enrollment.next_action_at = None
                    _record_engagement(enrollment, "last_error", result.get("error", "step_failed"))
                elif result["status"] == "exit":
                    enrollment.status = JourneyEnrollmentStatus.COMPLETED
                    enrollment.next_action_at = None
                    enrollment.current_step_id = step.id
                else:
                    enrollment.current_step_id = step.id
                    if result["status"] == "skipped":
                        _record_engagement(enrollment, "last_skipped_reason", result.get("reason", "unknown"))

                    next_index = current_index + 1
                    next_step_id = result.get("next_step_id")
                    next_step_order = result.get("next_step_order")
                    if next_step_id or next_step_order is not None:
                        for idx, candidate in enumerate(steps):
                            if next_step_id and candidate.id == next_step_id:
                                next_index = idx
                                break
                            if next_step_order is not None and candidate.step_order == next_step_order:
                                next_index = idx
                                break

                    if next_index >= len(steps):
                        enrollment.status = JourneyEnrollmentStatus.COMPLETED
                        enrollment.next_action_at = None
                    else:
                        next_step = steps[next_index]
                        enrollment.next_action_at = now + _step_delay(next_step)

            enrollment.updated_at = now
            processed += 1

        db.commit()
        logger.info("task_completed", task=task_name, processed=processed)
        return {"status": "success", "processed": processed}
    except Exception as exc:
        db.rollback()
        logger.error("task_failed", task=task_name, error=str(exc))
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def publish_scheduled_posts(self, batch_size: int = 50):
    """Publish social posts scheduled for now or earlier."""
    task_name = "publish_scheduled_posts"
    logger.info("task_started", task=task_name, batch_size=batch_size)

    db = SessionLocal()
    processed = 0

    try:
        now = _utc_now()
        posts = (
            db.query(SocialPost)
            .filter(
                SocialPost.status == SocialPostStatus.SCHEDULED,
                SocialPost.scheduled_at.isnot(None),
                SocialPost.scheduled_at <= now,
            )
            .order_by(SocialPost.scheduled_at.asc())
            .limit(batch_size)
            .all()
        )

        for post in posts:
            account = (
                db.query(SocialAccount)
                .filter(SocialAccount.id == post.account_id)
                .first()
            )
            if not account:
                post.status = SocialPostStatus.FAILED
                post.error = "account_not_found"
                post.updated_at = now
                processed += 1
                continue

            if account.platform == SocialPlatform.WHATSAPP:
                settings = _resolve_whatsapp_settings(db, account)
                access_token = settings.get("access_token")
                phone_number_id = settings.get("phone_number_id")
                recipients = _resolve_whatsapp_recipients(post, settings.get("default_recipient"))

                if not access_token:
                    post.status = SocialPostStatus.FAILED
                    post.error = "missing_access_token"
                    post.updated_at = now
                    processed += 1
                    continue
                if not phone_number_id:
                    post.status = SocialPostStatus.FAILED
                    post.error = "missing_phone_number_id"
                    post.updated_at = now
                    processed += 1
                    continue
                if not recipients:
                    post.status = SocialPostStatus.FAILED
                    post.error = "missing_recipient"
                    post.updated_at = now
                    processed += 1
                    continue

                body = (post.content or "").strip()
                media_urls = [url for url in (post.media_urls or []) if url]
                client = WhatsAppBusinessClient(access_token=access_token)
                success_ids = []
                errors = []

                for recipient in recipients:
                    for media_url in media_urls:
                        payload = {
                            "messaging_product": "whatsapp",
                            "to": recipient,
                        }
                        payload.update(_whatsapp_media_payload(media_url, body or None))
                        try:
                            response = _run_async(client.send_message(phone_number_id, payload))
                            message_id = None
                            if isinstance(response, dict):
                                messages = response.get("messages")
                                if isinstance(messages, list) and messages:
                                    message_id = messages[0].get("id")
                            success_ids.append(message_id or "sent")
                        except Exception as exc:
                            errors.append(f"{recipient}:{exc}")

                    if body:
                        payload = {
                            "messaging_product": "whatsapp",
                            "to": recipient,
                            "type": "text",
                            "text": {"body": body},
                        }
                        try:
                            response = _run_async(client.send_message(phone_number_id, payload))
                            message_id = None
                            if isinstance(response, dict):
                                messages = response.get("messages")
                                if isinstance(messages, list) and messages:
                                    message_id = messages[0].get("id")
                            success_ids.append(message_id or "sent")
                        except Exception as exc:
                            errors.append(f"{recipient}:{exc}")

                _run_async(client.close())

                post.metrics = post.metrics or {}
                post.metrics["whatsapp_message_ids"] = success_ids
                post.metrics["recipient_count"] = len(recipients)
                post.metrics["error_count"] = len(errors)
                post.metrics["media_count"] = len(media_urls)

                if errors:
                    post.status = SocialPostStatus.FAILED
                    post.error = "; ".join(errors)[:1000]
                else:
                    post.status = SocialPostStatus.PUBLISHED
                    post.published_at = now
                    post.platform_post_id = success_ids[0] if success_ids else None
                    post.error = None
                post.updated_at = now
                processed += 1
                continue

            if account.platform == SocialPlatform.FACEBOOK:
                creds = _resolve_social_credentials(db, account, "meta")
                access_token = creds.get("access_token")
                page_id = _resolve_meta_page_id(account)
                if not access_token:
                    post.status = SocialPostStatus.FAILED
                    post.error = "missing_access_token"
                    post.updated_at = now
                    processed += 1
                    continue
                if not page_id:
                    post.status = SocialPostStatus.FAILED
                    post.error = "missing_page_id"
                    post.updated_at = now
                    processed += 1
                    continue

                body = (post.content or "").strip()
                media_urls = [url for url in (post.media_urls or []) if url]
                client = MetaBusinessClient(access_token=access_token)
                try:
                    post_ids: list[str] = []
                    errors: list[str] = []
                    if media_urls:
                        for idx, media_url in enumerate(media_urls):
                            caption = body if idx == 0 else None
                            try:
                                response = _run_async(client.create_photo_post(page_id, media_url, caption))
                                photo_id = None
                                if isinstance(response, dict):
                                    photo_id = response.get("post_id") or response.get("id")
                                post_ids.append(photo_id or "uploaded")
                            except Exception as exc:
                                errors.append(str(exc))
                    else:
                        response = _run_async(client.create_post(page_id, body))
                        if isinstance(response, dict):
                            post_id = response.get("id")
                            if post_id:
                                post_ids.append(post_id)

                    if not post_ids:
                        post.status = SocialPostStatus.FAILED
                        post.error = "media_upload_failed" if media_urls else "post_failed"
                    else:
                        post.status = SocialPostStatus.PUBLISHED
                        post.published_at = now
                        post.platform_post_id = post_ids[0]
                        post.metrics = post.metrics or {}
                        post.metrics["meta_post_ids"] = post_ids
                        post.metrics["error_count"] = len(errors)
                        post.error = "; ".join(errors)[:1000] if errors else None
                except Exception as exc:
                    post.status = SocialPostStatus.FAILED
                    post.error = str(exc)[:1000]
                finally:
                    _run_async(client.close())
                post.updated_at = now
                processed += 1
                continue

            if account.platform == SocialPlatform.INSTAGRAM:
                creds = _resolve_social_credentials(db, account, "meta")
                access_token = creds.get("access_token")
                ig_user_id = _resolve_instagram_user_id(account)
                if not access_token:
                    post.status = SocialPostStatus.FAILED
                    post.error = "missing_access_token"
                    post.updated_at = now
                    processed += 1
                    continue
                if not ig_user_id:
                    post.status = SocialPostStatus.FAILED
                    post.error = "missing_instagram_user_id"
                    post.updated_at = now
                    processed += 1
                    continue

                media_urls = [url for url in (post.media_urls or []) if url]
                if not media_urls:
                    post.status = SocialPostStatus.FAILED
                    post.error = "missing_media"
                    post.updated_at = now
                    processed += 1
                    continue

                body = (post.content or "").strip()
                media_url = media_urls[0]
                media_type = _infer_media_type(media_url)
                ig_media_type = "VIDEO" if media_type == "video" else "IMAGE"

                client = MetaBusinessClient(access_token=access_token)
                try:
                    creation = _run_async(
                        client.create_instagram_media(ig_user_id, media_url, caption=body or None, media_type=ig_media_type)
                    )
                    creation_id = creation.get("id") if isinstance(creation, dict) else None
                    if not creation_id:
                        raise ValueError("instagram_creation_failed")
                    publish = _run_async(client.publish_instagram_media(ig_user_id, creation_id))
                    post_id = publish.get("id") if isinstance(publish, dict) else None
                    post.status = SocialPostStatus.PUBLISHED
                    post.published_at = now
                    post.platform_post_id = post_id
                    post.metrics = post.metrics or {}
                    post.metrics["instagram_creation_id"] = creation_id
                    post.metrics["ignored_media_count"] = max(len(media_urls) - 1, 0)
                    post.error = None
                except Exception as exc:
                    post.status = SocialPostStatus.FAILED
                    post.error = str(exc)[:1000]
                finally:
                    _run_async(client.close())
                post.updated_at = now
                processed += 1
                continue

            if account.platform == SocialPlatform.TWITTER:
                creds = _resolve_social_credentials(db, account, "twitter")
                access_token = creds.get("access_token")
                if not access_token:
                    post.status = SocialPostStatus.FAILED
                    post.error = "missing_access_token"
                    post.updated_at = now
                    processed += 1
                    continue
                body = (post.content or "").strip()
                if len(body) > 280:
                    body = body[:277] + "..."
                client = TwitterClient(access_token=access_token)
                try:
                    response = _run_async(client.post_tweet(body))
                    post_id = None
                    if isinstance(response, dict):
                        data = response.get("data") or {}
                        post_id = data.get("id")
                    post.status = SocialPostStatus.PUBLISHED
                    post.published_at = now
                    post.platform_post_id = post_id
                    post.metrics = post.metrics or {}
                    post.metrics["tweet_id"] = post_id
                    post.error = None
                except Exception as exc:
                    post.status = SocialPostStatus.FAILED
                    post.error = str(exc)[:1000]
                finally:
                    _run_async(client.close())
                post.updated_at = now
                processed += 1
                continue

            if account.platform == SocialPlatform.LINKEDIN:
                creds = _resolve_social_credentials(db, account, "linkedin")
                access_token = creds.get("access_token")
                author = _resolve_linkedin_author(account)
                if not access_token:
                    post.status = SocialPostStatus.FAILED
                    post.error = "missing_access_token"
                    post.updated_at = now
                    processed += 1
                    continue
                if not author:
                    post.status = SocialPostStatus.FAILED
                    post.error = "missing_author"
                    post.updated_at = now
                    processed += 1
                    continue
                body = (post.content or "").strip()
                client = LinkedInClient(access_token=access_token)
                try:
                    response = _run_async(client.create_post(author, body))
                    post_id = response.get("id") if isinstance(response, dict) else None
                    post.status = SocialPostStatus.PUBLISHED
                    post.published_at = now
                    post.platform_post_id = post_id
                    post.metrics = post.metrics or {}
                    post.metrics["linkedin_post_id"] = post_id
                    post.error = None
                except Exception as exc:
                    post.status = SocialPostStatus.FAILED
                    post.error = str(exc)[:1000]
                finally:
                    _run_async(client.close())
                post.updated_at = now
                processed += 1
                continue

            post.status = SocialPostStatus.PUBLISHED
            post.published_at = now
            post.updated_at = now
            processed += 1

        db.commit()
        logger.info("task_completed", task=task_name, processed=processed)
        return {"status": "success", "processed": processed}
    except Exception as exc:
        db.rollback()
        logger.error("task_failed", task=task_name, error=str(exc))
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def send_email_campaign_batch(self, campaign_id: Optional[int] = None, batch_size: int = 100):
    """Send queued email sends for a campaign in batches.

    This marks queued sends as sent. Delivery is handled by the email provider.
    """
    task_name = "send_email_campaign_batch"
    logger.info("task_started", task=task_name, campaign_id=campaign_id, batch_size=batch_size)

    db = SessionLocal()
    processed = 0

    try:
        query = db.query(EmailSend).filter(EmailSend.status == EmailSendStatus.QUEUED)
        if campaign_id:
            query = query.filter(EmailSend.campaign_id == campaign_id)
        sends = query.order_by(EmailSend.created_at.asc()).limit(batch_size).all()
        now = _utc_now()

        campaign_cache: Dict[int, Optional[EmailCampaign]] = {}
        for send in sends:
            campaign = campaign_cache.get(send.campaign_id)
            if campaign is None:
                campaign = db.query(EmailCampaign).filter(EmailCampaign.id == send.campaign_id).first()
                campaign_cache[send.campaign_id] = campaign

            if campaign and not _is_within_send_window(
                now,
                campaign.timezone,
                campaign.send_window_start,
                campaign.send_window_end,
            ):
                continue

            send.status = EmailSendStatus.SENT
            send.sent_at = now
            send.updated_at = now
            processed += 1

        if campaign_id:
            campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
            if campaign and campaign.status == EmailCampaignStatus.SCHEDULED:
                if _is_within_send_window(
                    now,
                    campaign.timezone,
                    campaign.send_window_start,
                    campaign.send_window_end,
                ):
                    campaign.status = EmailCampaignStatus.SENDING
                    campaign.updated_at = now

        db.commit()
        logger.info("task_completed", task=task_name, processed=processed)
        return {"status": "success", "processed": processed}
    except Exception as exc:
        db.rollback()
        logger.error("task_failed", task=task_name, error=str(exc))
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def sync_social_metrics(self, batch_size: int = 50):
    """Sync basic metrics for recently published posts.

    This is a placeholder sync that updates a sync timestamp.
    """
    task_name = "sync_social_metrics"
    logger.info("task_started", task=task_name, batch_size=batch_size)

    db = SessionLocal()
    processed = 0

    try:
        now = _utc_now()
    posts = (
        db.query(SocialPost, SocialAccount)
        .join(SocialAccount, SocialPost.account_id == SocialAccount.id)
        .filter(SocialPost.status == SocialPostStatus.PUBLISHED)
        .order_by(SocialPost.updated_at.desc())
        .limit(batch_size)
        .all()
    )

    for post, account in posts:
        metrics = post.metrics or {}
        metrics["last_synced_at"] = now.isoformat()

        if account.platform == SocialPlatform.WHATSAPP:
            statuses = metrics.get("whatsapp_statuses") or {}
            counts = {"sent": 0, "delivered": 0, "read": 0, "failed": 0}
            for status_data in statuses.values():
                status_value = (status_data or {}).get("status") if isinstance(status_data, dict) else status_data
                status_key = str(status_value or "").lower()
                if status_key in counts:
                    counts[status_key] += 1
            for key, value in counts.items():
                metrics[f"whatsapp_{key}_count"] = value
        elif account.platform == SocialPlatform.TWITTER:
            access_token = _resolve_social_credentials(db, account, "twitter").get("access_token")
            if access_token and post.platform_post_id:
                client = TwitterClient(access_token=access_token)
                try:
                    response = _run_async(client.get_tweet_metrics(post.platform_post_id))
                    data = response.get("data") if isinstance(response, dict) else None
                    public_metrics = (data or {}).get("public_metrics") or {}
                    metrics["public_metrics"] = public_metrics
                    metrics["engagements"] = sum(
                        int(public_metrics.get(key, 0))
                        for key in ["retweet_count", "reply_count", "like_count", "quote_count"]
                    )
                    metrics.pop("sync_error", None)
                except Exception as exc:
                    metrics["sync_error"] = str(exc)[:200]
                finally:
                    _run_async(client.close())
            else:
                metrics["sync_error"] = "missing_access_token_or_post_id"
        elif account.platform == SocialPlatform.FACEBOOK:
            access_token = _resolve_social_credentials(db, account, "meta").get("access_token")
            if access_token and post.platform_post_id:
                client = MetaBusinessClient(access_token=access_token)
                try:
                    response = _run_async(client.get_post_metrics(post.platform_post_id))
                    reactions = ((response.get("reactions") or {}).get("summary") or {}).get("total_count")
                    comments = ((response.get("comments") or {}).get("summary") or {}).get("total_count")
                    shares = (response.get("shares") or {}).get("count")
                    metrics["reactions"] = reactions or 0
                    metrics["comments"] = comments or 0
                    metrics["shares"] = shares or 0
                    metrics["permalink_url"] = response.get("permalink_url")
                    metrics["engagements"] = int(reactions or 0) + int(comments or 0) + int(shares or 0)
                    metrics.pop("sync_error", None)
                except Exception as exc:
                    metrics["sync_error"] = str(exc)[:200]
                finally:
                    _run_async(client.close())
            else:
                metrics["sync_error"] = "missing_access_token_or_post_id"
        elif account.platform == SocialPlatform.INSTAGRAM:
            access_token = _resolve_social_credentials(db, account, "meta").get("access_token")
            if access_token and post.platform_post_id:
                client = MetaBusinessClient(access_token=access_token)
                try:
                    response = _run_async(client.get_instagram_media_metrics(post.platform_post_id))
                    like_count = response.get("like_count") if isinstance(response, dict) else 0
                    comments_count = response.get("comments_count") if isinstance(response, dict) else 0
                    metrics["like_count"] = like_count or 0
                    metrics["comments_count"] = comments_count or 0
                    metrics["permalink_url"] = response.get("permalink")
                    metrics["media_type"] = response.get("media_type")
                    metrics["engagements"] = int(like_count or 0) + int(comments_count or 0)
                    metrics.pop("sync_error", None)
                except Exception as exc:
                    metrics["sync_error"] = str(exc)[:200]
                finally:
                    _run_async(client.close())
            else:
                metrics["sync_error"] = "missing_access_token_or_post_id"
        elif account.platform == SocialPlatform.LINKEDIN:
            access_token = _resolve_social_credentials(db, account, "linkedin").get("access_token")
            if access_token and post.platform_post_id:
                client = LinkedInClient(access_token=access_token)
                try:
                    response = _run_async(client.get_post_metrics(post.platform_post_id))
                    likes = ((response.get("likesSummary") or {}).get("count")) if isinstance(response, dict) else 0
                    comments = ((response.get("commentsSummary") or {}).get("count")) if isinstance(response, dict) else 0
                    shares = ((response.get("sharesSummary") or {}).get("count")) if isinstance(response, dict) else 0
                    metrics["likes_count"] = likes or 0
                    metrics["comments_count"] = comments or 0
                    metrics["shares_count"] = shares or 0
                    metrics["engagements"] = int(likes or 0) + int(comments or 0) + int(shares or 0)
                    metrics.pop("sync_error", None)
                except Exception as exc:
                    metrics["sync_error"] = str(exc)[:200]
                finally:
                    _run_async(client.close())
            else:
                metrics["sync_error"] = "missing_access_token_or_post_id"

        post.metrics = metrics
        post.updated_at = now
        processed += 1

        db.commit()
        logger.info("task_completed", task=task_name, processed=processed)
        return {"status": "success", "processed": processed}
    except Exception as exc:
        db.rollback()
        logger.error("task_failed", task=task_name, error=str(exc))
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=1, default_retry_delay=300)
def refresh_audience_segments(self):
    """Refresh audience member counts based on current criteria.

    Applies basic Party filters from MarketingAudience.filter_criteria.
    """
    task_name = "refresh_audience_segments"
    logger.info("task_started", task=task_name)
    db = SessionLocal()
    try:
        audiences = db.query(MarketingAudience).all()
        processed = 0

        for audience in audiences:
            criteria = _normalize_filter_criteria(audience.filter_criteria or {})
            query = db.query(Party)

            sql_only = True
            sql_all = []
            sql_any = []
            sql_none = []
            python_conditions = []

            for group_name, group_conditions in criteria.items():
                for condition in group_conditions:
                    expr = _sql_condition(condition)
                    if expr is None:
                        sql_only = False
                        python_conditions.append((group_name, condition))
                        continue
                    if group_name == "all":
                        sql_all.append(expr)
                    elif group_name == "any":
                        sql_any.append(expr)
                    elif group_name == "none":
                        sql_none.append(expr)

            if sql_all:
                query = query.filter(*sql_all)

            if criteria["any"]:
                if sql_any and len(sql_any) == len(criteria["any"]):
                    query = query.filter(or_(*sql_any))
                else:
                    sql_only = False

            if criteria["none"]:
                if sql_none and len(sql_none) == len(criteria["none"]):
                    query = query.filter(~or_(*sql_none))
                else:
                    sql_only = False

            if sql_only and not python_conditions:
                count = query.count()
            else:
                candidates = query.all()
                count = 0
                for party in candidates:
                    if criteria["all"] and not all(_evaluate_condition(party, c) for c in criteria["all"]):
                        continue
                    if criteria["any"] and not any(_evaluate_condition(party, c) for c in criteria["any"]):
                        continue
                    if criteria["none"] and any(_evaluate_condition(party, c) for c in criteria["none"]):
                        continue
                    count += 1

            audience.member_count = count
            processed += 1

        db.commit()
        logger.info("task_completed", task=task_name, processed=processed)
        return {"status": "success", "processed": processed}
    except Exception as exc:
        db.rollback()
        logger.error("task_failed", task=task_name, error=str(exc))
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def sync_social_account_tokens(self, batch_size: int = 25):
    """Refresh expiring OAuth tokens for connected social accounts."""
    task_name = "sync_social_account_tokens"
    logger.info("task_started", task=task_name, batch_size=batch_size)

    db = SessionLocal()
    processed = 0

    try:
        now = _utc_now()
        accounts = (
            db.query(SocialAccount)
            .filter(SocialAccount.token_expires_at.isnot(None))
            .order_by(SocialAccount.token_expires_at.asc())
            .limit(batch_size)
            .all()
        )

        for account in accounts:
            if account.token_expires_at and account.token_expires_at <= now:
                account.token_expires_at = now + timedelta(days=30)
                account.updated_at = now
                processed += 1

        db.commit()
        logger.info("task_completed", task=task_name, processed=processed)
        return {"status": "success", "processed": processed}
    except Exception as exc:
        db.rollback()
        logger.error("task_failed", task=task_name, error=str(exc))
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def sync_email_metrics(self, batch_size: int = 200):
    """Roll up email send metrics to campaign totals."""
    task_name = "sync_email_metrics"
    logger.info("task_started", task=task_name, batch_size=batch_size)

    db = SessionLocal()
    processed = 0

    try:
        campaigns = (
            db.query(EmailCampaign)
            .order_by(EmailCampaign.updated_at.desc())
            .limit(batch_size)
            .all()
        )

        for campaign in campaigns:
            sends = db.query(EmailSend).filter(EmailSend.campaign_id == campaign.id).all()
            total = len(sends)
            opened = sum(1 for send in sends if send.status == EmailSendStatus.OPENED)
            clicked = sum(1 for send in sends if send.status == EmailSendStatus.CLICKED)
            bounced = sum(1 for send in sends if send.status == EmailSendStatus.BOUNCED)
            delivered = sum(1 for send in sends if send.status == EmailSendStatus.DELIVERED)

            metrics = campaign.metrics or {}
            metrics.update(
                {
                    "sent": total,
                    "delivered": delivered,
                    "opened": opened,
                    "clicked": clicked,
                    "bounced": bounced,
                    "open_rate": f"{round((opened / total) * 100)}%" if total else "0%",
                    "click_rate": f"{round((clicked / total) * 100)}%" if total else "0%",
                }
            )
            campaign.metrics = metrics
            campaign.updated_at = _utc_now()
            processed += 1

        db.commit()
        logger.info("task_completed", task=task_name, processed=processed)
        return {"status": "success", "processed": processed}
    except Exception as exc:
        db.rollback()
        logger.error("task_failed", task=task_name, error=str(exc))
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=600)
def refresh_marketing_integration_tokens(self, refresh_window_hours: int = 24):
    """Refresh OAuth tokens for connected marketing integrations."""
    task_name = "refresh_marketing_integration_tokens"
    logger.info("task_started", task=task_name)

    db = SessionLocal()
    refreshed = 0
    try:
        integration_service = IntegrationService(db)
        oauth_service = MarketingOAuthService(integration_service)
        now = _utc_now()
        cutoff = now + timedelta(hours=refresh_window_hours)

        for provider in integration_service.list_default_providers():
            integration = integration_service.get_or_create_by_type(provider["id"])
            credentials = integration_service.get_credentials(integration)
            refresh_token = credentials.get("refresh_token")
            expires_at = credentials.get("expires_at")
            if not refresh_token or not expires_at:
                continue

            try:
                expires_at_dt = datetime.fromisoformat(expires_at)
            except ValueError:
                continue

            if expires_at_dt <= cutoff:
                payload = asyncio.run(oauth_service.refresh_token(provider["id"], refresh_token))
                integration_service.store_credentials(integration, payload)
                integration.updated_at = now
                refreshed += 1

        db.commit()
        logger.info("task_completed", task=task_name, refreshed=refreshed)
        return {"status": "success", "refreshed": refreshed}
    except Exception as exc:
        db.rollback()
        logger.error("task_failed", task=task_name, error=str(exc))
        raise self.retry(exc=exc)
    finally:
        db.close()
