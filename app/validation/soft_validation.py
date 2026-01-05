"""Soft validation utilities for all modules."""
from __future__ import annotations

import base64
import json
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, Iterable, List, Optional

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session
from sqlalchemy import event

from app.models.validation import SoftValidationMixin


@dataclass
class ValidationWarning:
    severity: str
    code: str
    field: Optional[str]
    message: str
    model: str
    record_id: Optional[Any] = None


_warnings: ContextVar[List[ValidationWarning]] = ContextVar("soft_validation_warnings", default=[])

FINANCE_MODULE_PREFIXES = (
    "app.models.accounting",
    "app.models.accounting_ext",
    "app.models.asset",
    "app.models.asset_settings",
    "app.models.bank_transaction",
    "app.models.books_settings",
    "app.models.credit_note",
    "app.models.document_lines",
    "app.models.invoice",
    "app.models.payment",
    "app.models.tax",
    "app.models.tax_ng",
)


def clear_warnings() -> None:
    _warnings.set([])


def add_warning(warning: ValidationWarning) -> None:
    current = list(_warnings.get())
    current.append(warning)
    _warnings.set(current)


def get_warnings() -> List[ValidationWarning]:
    return list(_warnings.get())


def validate_instance(session: Session, instance: Any) -> List[ValidationWarning]:
    clear_warnings()
    _validate_instance(session, instance)
    return get_warnings()


def serialize_warnings(limit: int = 100) -> tuple[str, int]:
    warnings = get_warnings()
    total = len(warnings)
    if total > limit:
        warnings = warnings[:limit]
        warnings.append(
            ValidationWarning(
                severity="info",
                code="truncated",
                field=None,
                message=f"{total - limit} warnings truncated",
                model="validation",
                record_id=None,
            )
        )
    payload = json.dumps([asdict(w) for w in warnings], ensure_ascii=True)
    encoded = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")
    return encoded, total


def register_soft_validation() -> None:
    event.listen(Session, "before_flush", _before_flush)


def _before_flush(session: Session, flush_context, instances) -> None:
    for instance in list(session.new) + list(session.dirty):
        if not _should_validate(instance):
            continue
        if instance in session.dirty and not session.is_modified(instance, include_collections=False):
            continue
        before_len = len(get_warnings())
        _validate_instance(session, instance)
        if _should_persist_issues(instance):
            warnings = get_warnings()[before_len:]
            _store_issues(session, instance, warnings)


def _should_validate(instance: Any) -> bool:
    if getattr(instance, "__skip_soft_validation__", False):
        return False
    if not hasattr(instance, "__table__"):
        return False
    if isinstance(instance, SoftValidationMixin):
        return True
    if instance.__class__.__name__ in _RULES:
        return True
    return _is_finance_model(instance)


def _should_persist_issues(instance: Any) -> bool:
    if isinstance(instance, SoftValidationMixin):
        return True
    return _is_finance_model(instance)


def _is_finance_model(instance: Any) -> bool:
    module_name = getattr(instance.__class__, "__module__", "")
    return module_name.startswith(FINANCE_MODULE_PREFIXES)


def _store_issues(session: Session, instance: Any, warnings: List[ValidationWarning]) -> None:
    from app.models.validation import FinanceValidationIssue

    record_id = getattr(instance, "id", None)
    if record_id is None:
        return

    detected_at = datetime.now(timezone.utc)
    issues_payload = [
        {
            "severity": warning.severity,
            "code": warning.code,
            "message": warning.message,
            "field": warning.field,
            "detected_at": detected_at.isoformat(),
        }
        for warning in warnings
    ]

    existing = (
        session.query(FinanceValidationIssue)
        .filter(
            FinanceValidationIssue.model_name == instance.__class__.__name__,
            FinanceValidationIssue.record_id == record_id,
        )
        .first()
    )
    if existing:
        existing.issues = issues_payload
        existing.detected_at = detected_at
        existing.scope = _scope_for_instance(instance)
    else:
        session.add(
            FinanceValidationIssue(
                model_name=instance.__class__.__name__,
                record_id=record_id,
                scope=_scope_for_instance(instance),
                issues=issues_payload,
                detected_at=detected_at,
            )
        )


def _scope_for_instance(instance: Any) -> str:
    if isinstance(instance, SoftValidationMixin):
        return instance.validation_scope
    return "finance"


def _validate_instance(session: Session, instance: Any) -> None:
    mapper = inspect(instance).mapper
    model_name = mapper.class_.__name__
    record_id = getattr(instance, "id", None)

    for column in mapper.columns:
        name = column.key
        value = getattr(instance, name, None)

        if not column.nullable and value is None:
            if column.default is None and column.server_default is None:
                add_warning(
                    ValidationWarning(
                        severity="warning",
                        code="missing_required",
                        field=name,
                        message=f"{name} is required",
                        model=model_name,
                        record_id=record_id,
                    )
                )

        if isinstance(column.type, String) and value is not None:
            max_len = column.type.length
            if max_len and isinstance(value, str) and len(value) > max_len:
                add_warning(
                    ValidationWarning(
                        severity="warning",
                        code="max_length",
                        field=name,
                        message=f"{name} exceeds max length {max_len}",
                        model=model_name,
                        record_id=record_id,
                    )
                )

        if isinstance(column.type, SAEnum) and value is not None:
            enum_values = [str(item.value) if hasattr(item, "value") else str(item) for item in column.type.enums]
            if _enum_value(value) not in enum_values:
                add_warning(
                    ValidationWarning(
                        severity="warning",
                        code="invalid_enum",
                        field=name,
                        message=f"{name} has invalid value",
                        model=model_name,
                        record_id=record_id,
                    )
                )

    _check_date_ranges(instance, model_name, record_id)
    _apply_module_rules(session, instance, model_name, record_id)


RuleFn = Callable[[Session, Any, str, Any], None]
_RULES: Dict[str, List[RuleFn]] = {}


def register_rule(model_name: str, rule: RuleFn) -> None:
    rules = _RULES.setdefault(model_name, [])
    rules.append(rule)


def _apply_module_rules(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    for rule in _RULES.get(model_name, []):
        rule(session, instance, model_name, record_id)


def _check_date_ranges(instance: Any, model_name: str, record_id: Any) -> None:
    candidates = [
        ("starts_at", "ends_at"),
        ("start_at", "end_at"),
        ("start_date", "end_date"),
        ("from_date", "to_date"),
        ("scheduled_at", "published_at"),
    ]
    for start_field, end_field in candidates:
        if hasattr(instance, start_field) and hasattr(instance, end_field):
            start_value = getattr(instance, start_field, None)
            end_value = getattr(instance, end_field, None)
            if isinstance(start_value, datetime) and isinstance(end_value, datetime):
                if start_value > end_value:
                    add_warning(
                        ValidationWarning(
                            severity="warning",
                            code="invalid_range",
                            field=f"{start_field},{end_field}",
                            message=f"{start_field} is after {end_field}",
                            model=model_name,
                            record_id=record_id,
                        )
                    )


def _warn(model: str, field: Optional[str], message: str, record_id: Any, code: str = "rule") -> None:
    add_warning(
        ValidationWarning(
            severity="warning",
            code=code,
            field=field,
            message=message,
            model=model,
            record_id=record_id,
        )
    )


def _is_close(left: Decimal, right: Decimal, tolerance: Decimal = Decimal("0.01")) -> bool:
    return abs(left - right) <= tolerance


def _enum_value(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    if value is None:
        return ""
    return str(value)


def _rule_social_post(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    from app.models.marketing import SocialPostStatus, SocialAccount, SocialPlatform, MarketingIntegration

    status = getattr(instance, "status", None)
    if status == SocialPostStatus.SCHEDULED and getattr(instance, "scheduled_at", None) is None:
        _warn(model_name, "scheduled_at", "scheduled_at is required when status=scheduled", record_id, "missing_required")
    if status == SocialPostStatus.PUBLISHED and getattr(instance, "published_at", None) is None:
        _warn(model_name, "published_at", "published_at is required when status=published", record_id, "missing_required")

    account_id = getattr(instance, "account_id", None)
    account = None
    if account_id:
        account = session.query(SocialAccount).filter(SocialAccount.id == account_id).first()
    if account_id and not account:
        _warn(model_name, "account_id", "account_id does not resolve to a social account", record_id, "missing_reference")

    if account and account.platform == SocialPlatform.WHATSAPP:
        metrics = getattr(instance, "metrics", {}) or {}
        recipients = metrics.get("recipients") or metrics.get("to")
        has_recipients = bool(recipients)
        default_recipient = None
        if isinstance(account.stats, dict):
            default_recipient = account.stats.get("default_recipient")
        if not default_recipient:
            integration = (
                session.query(MarketingIntegration)
                .filter(MarketingIntegration.integration_type == "whatsapp")
                .first()
            )
            if integration and isinstance(integration.settings, dict):
                default_recipient = integration.settings.get("default_recipient")
        if not has_recipients and not default_recipient:
            _warn(model_name, "metrics.recipients", "WhatsApp posts need recipients or a default_recipient", record_id, "missing_required")


def _rule_email_send(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    from app.models.marketing import EmailSendStatus

    status = getattr(instance, "status", None)
    if status == EmailSendStatus.DELIVERED and getattr(instance, "delivered_at", None) is None:
        _warn(model_name, "delivered_at", "delivered_at is required when status=delivered", record_id, "missing_required")
    if status == EmailSendStatus.OPENED and getattr(instance, "opened_at", None) is None:
        _warn(model_name, "opened_at", "opened_at is required when status=opened", record_id, "missing_required")
    if status == EmailSendStatus.CLICKED and getattr(instance, "clicked_at", None) is None:
        _warn(model_name, "clicked_at", "clicked_at is required when status=clicked", record_id, "missing_required")
    if status == EmailSendStatus.BOUNCED and getattr(instance, "bounced_at", None) is None:
        _warn(model_name, "bounced_at", "bounced_at is required when status=bounced", record_id, "missing_required")
    if status == EmailSendStatus.FAILED and not getattr(instance, "error", None):
        _warn(model_name, "error", "error is required when status=failed", record_id, "missing_required")


def _rule_omni_message(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    direction = getattr(instance, "direction", None)
    if direction not in {"inbound", "outbound"}:
        _warn(model_name, "direction", "direction should be inbound or outbound", record_id, "invalid_enum")
    if direction == "inbound" and not getattr(instance, "participant_id", None):
        _warn(model_name, "participant_id", "participant_id is required for inbound messages", record_id, "missing_required")
    if direction == "outbound" and not getattr(instance, "party_id", None):
        _warn(model_name, "party_id", "party_id is required for outbound messages", record_id, "missing_required")

    if not getattr(instance, "channel_id", None):
        _warn(model_name, "channel_id", "channel_id is required for messages", record_id, "missing_required")

    body = getattr(instance, "body", None)
    subject = getattr(instance, "subject", None)
    if not body and not subject:
        _warn(model_name, "body,subject", "message body or subject should be set", record_id, "missing_required")

    delivery_status = getattr(instance, "delivery_status", None)
    if delivery_status == "sent" and getattr(instance, "sent_at", None) is None:
        _warn(model_name, "sent_at", "sent_at is required when delivery_status=sent", record_id, "missing_required")
    if delivery_status == "delivered" and getattr(instance, "delivered_at", None) is None:
        _warn(model_name, "delivered_at", "delivered_at is required when delivery_status=delivered", record_id, "missing_required")
    if delivery_status == "read" and getattr(instance, "read_at", None) is None:
        _warn(model_name, "read_at", "read_at is required when delivery_status=read", record_id, "missing_required")


def _rule_omni_conversation(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    from app.models.omni import OmniChannel, ConversationStatus, ConversationPriority

    channel_id = getattr(instance, "channel_id", None)
    if channel_id:
        channel = session.query(OmniChannel.id).filter(OmniChannel.id == channel_id).first()
        if not channel:
            _warn(model_name, "channel_id", "channel_id does not resolve to a channel", record_id, "missing_reference")
    else:
        _warn(model_name, "channel_id", "channel_id is required", record_id, "missing_required")

    status = getattr(instance, "status", None)
    if status and _enum_value(status) not in {item.value for item in ConversationStatus}:
        _warn(model_name, "status", "status is not a valid conversation status", record_id, "invalid_enum")
    if status in {"resolved", "closed"} and getattr(instance, "resolved_at", None) is None:
        _warn(model_name, "resolved_at", "resolved_at is required when conversation is resolved", record_id, "missing_required")
    if status == "snoozed" and getattr(instance, "snoozed_until", None) is None:
        _warn(model_name, "snoozed_until", "snoozed_until is required when conversation is snoozed", record_id, "missing_required")
    if status == "open" and getattr(instance, "resolved_at", None) is not None:
        _warn(model_name, "resolved_at", "resolved_at should be empty for open conversations", record_id, "inconsistent_state")

    priority = getattr(instance, "priority", None)
    if priority and _enum_value(priority) not in {item.value for item in ConversationPriority}:
        _warn(model_name, "priority", "priority is not a valid value", record_id, "invalid_enum")

    unread_count = getattr(instance, "unread_count", None)
    if unread_count is not None and unread_count < 0:
        _warn(model_name, "unread_count", "unread_count should not be negative", record_id, "invalid_amount")

    message_count = getattr(instance, "message_count", None)
    if message_count is not None and message_count < 0:
        _warn(model_name, "message_count", "message_count should not be negative", record_id, "invalid_amount")

    contact_email = getattr(instance, "contact_email", None)
    if contact_email and "@" not in contact_email:
        _warn(model_name, "contact_email", "contact_email does not look valid", record_id, "invalid_format")


def _rule_omni_channel(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    from app.models.omni import OmniChannelType

    channel_type = _enum_value(getattr(instance, "type", None))
    if channel_type not in {item.value for item in OmniChannelType}:
        _warn(model_name, "type", "type is not a supported channel", record_id, "invalid_enum")

    if channel_type == "sms":
        _warn(model_name, "type", "sms channels are not supported", record_id, "unsupported_channel")

    if channel_type == "chatwoot" and not getattr(instance, "chatwoot_inbox_id", None):
        _warn(model_name, "chatwoot_inbox_id", "chatwoot_inbox_id is required for chatwoot channels", record_id, "missing_required")

    if getattr(instance, "is_active", True) and not getattr(instance, "config", None):
        _warn(model_name, "config", "active channels should have configuration", record_id, "missing_required")


def _rule_omni_participant(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    from app.models.omni import OmniChannelType

    channel_type = _enum_value(getattr(instance, "channel_type", None))
    if channel_type not in {item.value for item in OmniChannelType}:
        _warn(model_name, "channel_type", "channel_type is not supported", record_id, "invalid_enum")

    handle = getattr(instance, "handle", None)
    if channel_type == "email" and handle and "@" not in handle:
        _warn(model_name, "handle", "email handle does not look valid", record_id, "invalid_format")
    if channel_type in {"whatsapp", "sms"} and handle:
        if len(handle) < 7:
            _warn(model_name, "handle", "phone handle looks too short", record_id, "invalid_format")


def _rule_omni_attachment(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    filename = getattr(instance, "filename", None)
    url = getattr(instance, "url", None)
    if not filename and not url:
        _warn(model_name, "filename,url", "attachments should include a filename or url", record_id, "missing_required")

    size_bytes = getattr(instance, "size_bytes", None)
    if size_bytes is not None and size_bytes < 0:
        _warn(model_name, "size_bytes", "size_bytes should not be negative", record_id, "invalid_amount")

    if url and not getattr(instance, "mime_type", None):
        _warn(model_name, "mime_type", "mime_type is recommended for attachment urls", record_id, "missing_required")


def _rule_omni_webhook_event(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    processed = getattr(instance, "processed", False)
    error = getattr(instance, "error", None)
    if processed and error:
        _warn(model_name, "error", "processed events should not carry error", record_id, "inconsistent_state")

    retry_count = getattr(instance, "retry_count", None) or 0
    last_retry_at = getattr(instance, "last_retry_at", None)
    if retry_count > 0 and last_retry_at is None:
        _warn(model_name, "last_retry_at", "last_retry_at is required when retry_count > 0", record_id, "missing_required")

    if not getattr(instance, "provider_event_id", None):
        _warn(model_name, "provider_event_id", "provider_event_id is recommended for idempotency", record_id, "missing_required")


def _rule_inbox_routing_rule(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    conditions = getattr(instance, "conditions", None) or []
    if not conditions:
        _warn(model_name, "conditions", "routing rule conditions should not be empty", record_id, "missing_required")

    action_type = getattr(instance, "action_type", None)
    allowed_actions = {"assign_agent", "assign_team", "add_tag", "create_ticket"}
    if action_type and action_type not in allowed_actions:
        _warn(model_name, "action_type", "action_type is not supported", record_id, "invalid_enum")

    if action_type in {"assign_agent", "assign_team", "add_tag"} and not getattr(instance, "action_value", None):
        _warn(model_name, "action_value", "action_value is required for assignment/tag actions", record_id, "missing_required")

    priority = getattr(instance, "priority", None)
    if priority is not None and priority < 0:
        _warn(model_name, "priority", "priority should not be negative", record_id, "invalid_amount")


def _rule_inbox_contact(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    email = getattr(instance, "email", None)
    phone = getattr(instance, "phone", None)
    if not email and not phone:
        _warn(model_name, "email,phone", "contact should have an email or phone", record_id, "missing_required")

    if email and "@" not in email:
        _warn(model_name, "email", "email does not look valid", record_id, "invalid_format")

    if phone and len(phone) < 7:
        _warn(model_name, "phone", "phone number looks too short", record_id, "invalid_format")

    total_conversations = getattr(instance, "total_conversations", None)
    if total_conversations is not None and total_conversations < 0:
        _warn(model_name, "total_conversations", "total_conversations should not be negative", record_id, "invalid_amount")


def _rule_marketing_campaign(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    status = _enum_value(getattr(instance, "status", None))
    starts_at = getattr(instance, "starts_at", None)
    ends_at = getattr(instance, "ends_at", None)
    if status in {"active", "completed"} and starts_at is None:
        _warn(model_name, "starts_at", "starts_at is recommended for active campaigns", record_id, "missing_required")
    if status == "completed" and ends_at is None:
        _warn(model_name, "ends_at", "ends_at is recommended for completed campaigns", record_id, "missing_required")

    budget = getattr(instance, "budget", None)
    if budget is not None and budget < 0:
        _warn(model_name, "budget", "budget should not be negative", record_id, "invalid_amount")


def _rule_journey_template(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    template_config = getattr(instance, "template_config", None) or {}
    if not template_config:
        _warn(model_name, "template_config", "template_config should not be empty", record_id, "missing_required")


def _rule_customer_journey(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    status = _enum_value(getattr(instance, "status", None))
    entry_trigger = getattr(instance, "entry_trigger", None)
    if status == "active" and not entry_trigger:
        _warn(model_name, "entry_trigger", "entry_trigger is recommended for active journeys", record_id, "missing_required")


def _rule_journey_step(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    step_order = getattr(instance, "step_order", None)
    if step_order is not None and step_order < 0:
        _warn(model_name, "step_order", "step_order should not be negative", record_id, "invalid_amount")

    step_type = _enum_value(getattr(instance, "step_type", None))
    delay_days = getattr(instance, "delay_days", None) or 0
    delay_hours = getattr(instance, "delay_hours", None) or 0
    delay_minutes = getattr(instance, "delay_minutes", None) or 0

    if step_type == "wait" and (delay_days + delay_hours + delay_minutes) <= 0:
        _warn(model_name, "delay_days,delay_hours,delay_minutes", "wait steps should have a delay configured", record_id, "missing_required")

    if step_type == "email" and not getattr(instance, "email_template_id", None):
        _warn(model_name, "email_template_id", "email_template_id is required for email steps", record_id, "missing_required")

    if step_type == "webhook" and not getattr(instance, "webhook_url", None):
        _warn(model_name, "webhook_url", "webhook_url is required for webhook steps", record_id, "missing_required")

    if step_type == "condition":
        condition_config = getattr(instance, "condition_config", None) or {}
        if not condition_config:
            _warn(model_name, "condition_config", "condition_config is required for condition steps", record_id, "missing_required")


def _rule_journey_enrollment(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    status = _enum_value(getattr(instance, "status", None))
    if status in {"active", "paused"} and not getattr(instance, "current_step_id", None):
        _warn(model_name, "current_step_id", "current_step_id is recommended for active enrollments", record_id, "missing_required")

    if status == "active" and getattr(instance, "next_action_at", None) is None:
        _warn(model_name, "next_action_at", "next_action_at is recommended for active enrollments", record_id, "missing_required")


def _rule_social_account(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    token = getattr(instance, "access_token_encrypted", None)
    if not token:
        _warn(model_name, "access_token_encrypted", "access_token_encrypted is required to publish posts", record_id, "missing_required")


def _rule_email_template(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    subject = getattr(instance, "subject", None)
    body_html = getattr(instance, "body_html", None)
    body_text = getattr(instance, "body_text", None)
    if not subject and not body_html and not body_text:
        _warn(model_name, "subject,body_html,body_text", "email template should include subject or body content", record_id, "missing_required")


def _rule_email_campaign(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    status = _enum_value(getattr(instance, "status", None))
    if status in {"scheduled", "sending", "sent"} and getattr(instance, "scheduled_at", None) is None:
        _warn(model_name, "scheduled_at", "scheduled_at is required for scheduled/sent campaigns", record_id, "missing_required")

    send_window_start = getattr(instance, "send_window_start", None)
    send_window_end = getattr(instance, "send_window_end", None)
    if send_window_start is not None and (send_window_start < 0 or send_window_start > 23):
        _warn(model_name, "send_window_start", "send_window_start must be 0-23", record_id, "invalid_range")
    if send_window_end is not None and (send_window_end < 0 or send_window_end > 23):
        _warn(model_name, "send_window_end", "send_window_end must be 0-23", record_id, "invalid_range")
    if send_window_start is not None and send_window_end is not None and send_window_start > send_window_end:
        _warn(model_name, "send_window_start,send_window_end", "send_window_start is after send_window_end", record_id, "invalid_range")


def _rule_marketing_audience(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    filter_criteria = getattr(instance, "filter_criteria", None) or {}
    if not filter_criteria:
        _warn(model_name, "filter_criteria", "filter_criteria should not be empty", record_id, "missing_required")

    member_count = getattr(instance, "member_count", None)
    if member_count is not None and member_count < 0:
        _warn(model_name, "member_count", "member_count should not be negative", record_id, "invalid_amount")


def _rule_marketing_integration(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    status = _enum_value(getattr(instance, "status", None))
    if status == "connected" and not getattr(instance, "credentials_encrypted", None):
        _warn(model_name, "credentials_encrypted", "credentials_encrypted is required for connected integrations", record_id, "missing_required")


def _rule_marketing_consent(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    status = _enum_value(getattr(instance, "status", None))
    if status == "revoked" and not getattr(instance, "source", None):
        _warn(model_name, "source", "source is recommended when consent is revoked", record_id, "missing_required")


def _rule_suppression_entry(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    if not getattr(instance, "reason", None):
        _warn(model_name, "reason", "reason is recommended for suppressions", record_id, "missing_required")


def _rule_marketing_webhook_event(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    if not getattr(instance, "payload_hash", None):
        _warn(model_name, "payload_hash", "payload_hash is recommended for idempotency", record_id, "missing_required")


def _rule_journal_entry(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    total_debit = getattr(instance, "total_debit", None) or 0
    total_credit = getattr(instance, "total_credit", None) or 0
    if abs(total_debit - total_credit) > 0.0001:
        _warn(model_name, "total_debit,total_credit", "total_debit does not match total_credit", record_id, "unbalanced")

    items = getattr(instance, "items", None)
    if items:
        debit_sum = sum((item.debit or 0) for item in items)
        credit_sum = sum((item.credit or 0) for item in items)
    elif record_id:
        from app.models.accounting import JournalEntryItem
        rows = session.query(JournalEntryItem).filter(JournalEntryItem.journal_entry_id == record_id).all()
        debit_sum = sum((item.debit or 0) for item in rows)
        credit_sum = sum((item.credit or 0) for item in rows)
    else:
        return

    if abs(debit_sum - total_debit) > 0.0001 or abs(credit_sum - total_credit) > 0.0001:
        _warn(model_name, "items", "journal entry totals do not match item sums", record_id, "inconsistent_total")


def _rule_journal_entry_item(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    debit = getattr(instance, "debit", None) or 0
    credit = getattr(instance, "credit", None) or 0
    if debit > 0 and credit > 0:
        _warn(model_name, "debit,credit", "both debit and credit are set on the same line", record_id, "invalid_amount")
    if debit == 0 and credit == 0:
        _warn(model_name, "debit,credit", "line has no debit or credit amount", record_id, "invalid_amount")


def _rule_invoice(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    from app.models.invoice import InvoiceStatus

    amount = getattr(instance, "amount", None) or Decimal("0")
    tax_amount = getattr(instance, "tax_amount", None) or Decimal("0")
    total_amount = getattr(instance, "total_amount", None) or Decimal("0")
    amount_paid = getattr(instance, "amount_paid", None) or Decimal("0")
    balance = getattr(instance, "balance", None)
    conversion_rate = getattr(instance, "conversion_rate", None) or Decimal("0")
    base_amount = getattr(instance, "base_amount", None)
    base_tax_amount = getattr(instance, "base_tax_amount", None)
    base_total_amount = getattr(instance, "base_total_amount", None)

    if total_amount < amount:
        _warn(model_name, "total_amount", "total_amount is less than amount", record_id, "invalid_amount")
    if amount_paid > total_amount:
        _warn(model_name, "amount_paid", "amount_paid exceeds total_amount", record_id, "invalid_amount")
    if balance is not None and abs((total_amount - amount_paid) - balance) > Decimal("0.01"):
        _warn(model_name, "balance", "balance does not match total_amount minus amount_paid", record_id, "inconsistent_total")

    status = getattr(instance, "status", None)
    if status == InvoiceStatus.PAID:
        if getattr(instance, "paid_date", None) is None:
            _warn(model_name, "paid_date", "paid_date is required when status=paid", record_id, "missing_required")
        if amount_paid + Decimal("0.01") < total_amount:
            _warn(model_name, "amount_paid", "amount_paid is less than total_amount for paid invoice", record_id, "inconsistent_total")

    invoice_date = getattr(instance, "invoice_date", None)
    due_date = getattr(instance, "due_date", None)
    if invoice_date and due_date and invoice_date > due_date:
        _warn(model_name, "due_date", "due_date is before invoice_date", record_id, "invalid_range")

    if conversion_rate <= 0:
        _warn(model_name, "conversion_rate", "conversion_rate should be positive", record_id, "invalid_amount")
    if base_amount is not None and conversion_rate > 0:
        expected = amount * conversion_rate
        if not _is_close(expected, base_amount):
            _warn(model_name, "base_amount", "base_amount does not match amount * conversion_rate", record_id, "inconsistent_total")
    if base_tax_amount is not None and conversion_rate > 0:
        expected = tax_amount * conversion_rate
        if not _is_close(expected, base_tax_amount):
            _warn(model_name, "base_tax_amount", "base_tax_amount does not match tax_amount * conversion_rate", record_id, "inconsistent_total")
    if base_total_amount is not None and conversion_rate > 0:
        expected = total_amount * conversion_rate
        if not _is_close(expected, base_total_amount):
            _warn(model_name, "base_total_amount", "base_total_amount does not match total_amount * conversion_rate", record_id, "inconsistent_total")

    lines = getattr(instance, "lines", None)
    if not lines and record_id:
        from app.models.document_lines import InvoiceLine

        lines = session.query(InvoiceLine).filter(InvoiceLine.invoice_id == record_id).all()
    if lines:
        line_subtotal = Decimal("0")
        line_tax = Decimal("0")
        use_net = any((getattr(line, "net_amount", None) or Decimal("0")) for line in lines)
        for line in lines:
            line_tax += getattr(line, "tax_amount", None) or Decimal("0")
            if use_net:
                line_subtotal += getattr(line, "net_amount", None) or Decimal("0")
            else:
                line_subtotal += getattr(line, "amount", None) or Decimal("0")
        expected_total = line_subtotal + line_tax
        if not _is_close(line_subtotal, amount):
            _warn(model_name, "amount", "amount does not match invoice line subtotal", record_id, "inconsistent_total")
        if not _is_close(line_tax, tax_amount):
            _warn(model_name, "tax_amount", "tax_amount does not match invoice line tax total", record_id, "inconsistent_total")
        if not _is_close(expected_total, total_amount):
            _warn(model_name, "total_amount", "total_amount does not match line subtotal + tax", record_id, "inconsistent_total")


def _rule_invoice_line(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    quantity = getattr(instance, "quantity", None) or Decimal("0")
    rate = getattr(instance, "rate", None) or Decimal("0")
    amount = getattr(instance, "amount", None) or Decimal("0")
    if quantity <= 0:
        _warn(model_name, "quantity", "quantity should be greater than zero", record_id, "invalid_amount")
    if rate < 0:
        _warn(model_name, "rate", "rate should not be negative", record_id, "invalid_amount")
    if amount < 0:
        _warn(model_name, "amount", "amount should not be negative", record_id, "invalid_amount")


def _rule_purchase_invoice(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    from app.models.accounting import PurchaseInvoiceStatus

    grand_total = getattr(instance, "grand_total", None) or Decimal("0")
    paid_amount = getattr(instance, "paid_amount", None) or Decimal("0")
    outstanding = getattr(instance, "outstanding_amount", None) or Decimal("0")
    base_grand_total = getattr(instance, "base_grand_total", None)
    base_tax_amount = getattr(instance, "base_tax_amount", None)
    tax_amount = getattr(instance, "tax_amount", None) or Decimal("0")
    conversion_rate = getattr(instance, "conversion_rate", None) or Decimal("0")

    if paid_amount + outstanding > grand_total + Decimal("0.01"):
        _warn(model_name, "paid_amount,outstanding_amount", "paid_amount + outstanding_amount exceeds grand_total", record_id, "inconsistent_total")
    if conversion_rate <= 0:
        _warn(model_name, "conversion_rate", "conversion_rate should be positive", record_id, "invalid_amount")
    if base_grand_total is not None and conversion_rate > 0:
        expected = (grand_total * conversion_rate)
        if abs(expected - base_grand_total) > Decimal("0.01"):
            _warn(model_name, "base_grand_total", "base_grand_total does not match grand_total * conversion_rate", record_id, "inconsistent_total")
    if base_tax_amount is not None and conversion_rate > 0:
        expected = tax_amount * conversion_rate
        if not _is_close(expected, base_tax_amount):
            _warn(model_name, "base_tax_amount", "base_tax_amount does not match tax_amount * conversion_rate", record_id, "inconsistent_total")

    status = getattr(instance, "status", None)
    if status == PurchaseInvoiceStatus.PAID and outstanding > Decimal("0.01"):
        _warn(model_name, "outstanding_amount", "outstanding_amount should be zero when status=paid", record_id, "inconsistent_total")

    posting_date = getattr(instance, "posting_date", None)
    due_date = getattr(instance, "due_date", None)
    if posting_date and due_date and posting_date > due_date:
        _warn(model_name, "due_date", "due_date is before posting_date", record_id, "invalid_range")

    lines = getattr(instance, "lines", None)
    if not lines and record_id:
        from app.models.document_lines import BillLine

        lines = session.query(BillLine).filter(BillLine.purchase_invoice_id == record_id).all()
    if lines:
        line_subtotal = Decimal("0")
        line_tax = Decimal("0")
        use_net = any((getattr(line, "net_amount", None) or Decimal("0")) for line in lines)
        for line in lines:
            line_tax += getattr(line, "tax_amount", None) or Decimal("0")
            if use_net:
                line_subtotal += getattr(line, "net_amount", None) or Decimal("0")
            else:
                line_subtotal += getattr(line, "amount", None) or Decimal("0")
        expected_total = line_subtotal + line_tax
        if not _is_close(line_tax, tax_amount):
            _warn(model_name, "tax_amount", "tax_amount does not match bill line tax total", record_id, "inconsistent_total")
        if not _is_close(expected_total, grand_total):
            _warn(model_name, "grand_total", "grand_total does not match line subtotal + tax", record_id, "inconsistent_total")


def _rule_bill_line(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    _rule_invoice_line(session, instance, model_name, record_id)


def _rule_credit_note(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    from app.models.credit_note import CreditNoteStatus

    total_amount = getattr(instance, "total_amount", None) or Decimal("0")
    amount = getattr(instance, "amount", None) or Decimal("0")
    if total_amount < amount:
        _warn(model_name, "total_amount", "total_amount is less than amount", record_id, "invalid_amount")

    status = getattr(instance, "status", None)
    if status == CreditNoteStatus.ISSUED and getattr(instance, "issue_date", None) is None:
        _warn(model_name, "issue_date", "issue_date is required when status=issued", record_id, "missing_required")
    if status == CreditNoteStatus.APPLIED and getattr(instance, "applied_date", None) is None:
        _warn(model_name, "applied_date", "applied_date is required when status=applied", record_id, "missing_required")


def _rule_debit_note(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    from app.models.books_settings import DebitNoteStatus

    total_amount = getattr(instance, "total_amount", None) or Decimal("0")
    outstanding = getattr(instance, "outstanding_amount", None) or Decimal("0")
    if outstanding > total_amount + Decimal("0.01"):
        _warn(model_name, "outstanding_amount", "outstanding_amount exceeds total_amount", record_id, "inconsistent_total")

    status = getattr(instance, "status", None)
    if status == DebitNoteStatus.ISSUED and getattr(instance, "posting_date", None) is None:
        _warn(model_name, "posting_date", "posting_date is required when status=issued", record_id, "missing_required")
    if status == DebitNoteStatus.APPLIED and getattr(instance, "posting_date", None) is None:
        _warn(model_name, "posting_date", "posting_date is required when status=applied", record_id, "missing_required")


def _rule_payment(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    amount = getattr(instance, "amount", None) or Decimal("0")
    total_allocated = getattr(instance, "total_allocated", None) or Decimal("0")
    unallocated = getattr(instance, "unallocated_amount", None) or Decimal("0")
    conversion_rate = getattr(instance, "conversion_rate", None) or Decimal("0")
    base_amount = getattr(instance, "base_amount", None)
    if amount <= 0:
        _warn(model_name, "amount", "amount should be greater than zero", record_id, "invalid_amount")
    if total_allocated + unallocated > amount + Decimal("0.01"):
        _warn(model_name, "total_allocated,unallocated_amount", "allocation exceeds payment amount", record_id, "inconsistent_total")
    if conversion_rate <= 0:
        _warn(model_name, "conversion_rate", "conversion_rate should be positive", record_id, "invalid_amount")
    if base_amount is not None and conversion_rate > 0:
        expected = amount * conversion_rate
        if not _is_close(expected, base_amount):
            _warn(model_name, "base_amount", "base_amount does not match amount * conversion_rate", record_id, "inconsistent_total")

    status = _enum_value(getattr(instance, "status", None))
    if status in {"completed", "posted"} and getattr(instance, "payment_date", None) is None:
        _warn(model_name, "payment_date", "payment_date is required when payment is completed", record_id, "missing_required")


def _rule_supplier_payment(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    paid_amount = getattr(instance, "paid_amount", None) or Decimal("0")
    total_allocated = getattr(instance, "total_allocated", None) or Decimal("0")
    unallocated = getattr(instance, "unallocated_amount", None) or Decimal("0")
    conversion_rate = getattr(instance, "conversion_rate", None) or Decimal("0")
    base_paid_amount = getattr(instance, "base_paid_amount", None)
    if paid_amount <= 0:
        _warn(model_name, "paid_amount", "paid_amount should be greater than zero", record_id, "invalid_amount")
    if total_allocated + unallocated > paid_amount + Decimal("0.01"):
        _warn(model_name, "total_allocated,unallocated_amount", "allocation exceeds paid_amount", record_id, "inconsistent_total")
    if conversion_rate <= 0:
        _warn(model_name, "conversion_rate", "conversion_rate should be positive", record_id, "invalid_amount")
    if base_paid_amount is not None and conversion_rate > 0:
        expected = paid_amount * conversion_rate
        if not _is_close(expected, base_paid_amount):
            _warn(model_name, "base_paid_amount", "base_paid_amount does not match paid_amount * conversion_rate", record_id, "inconsistent_total")


def _rule_payment_allocation(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    payment_id = getattr(instance, "payment_id", None)
    supplier_payment_id = getattr(instance, "supplier_payment_id", None)
    if bool(payment_id) == bool(supplier_payment_id):
        _warn(model_name, "payment_id,supplier_payment_id", "exactly one of payment_id or supplier_payment_id is required", record_id, "missing_required")

    allocated = getattr(instance, "allocated_amount", None) or Decimal("0")
    discount_amount = getattr(instance, "discount_amount", None) or Decimal("0")
    write_off_amount = getattr(instance, "write_off_amount", None) or Decimal("0")
    conversion_rate = getattr(instance, "conversion_rate", None) or Decimal("0")
    base_allocated_amount = getattr(instance, "base_allocated_amount", None)
    base_discount_amount = getattr(instance, "base_discount_amount", None)
    base_write_off_amount = getattr(instance, "base_write_off_amount", None)
    if allocated <= 0:
        _warn(model_name, "allocated_amount", "allocated_amount should be greater than zero", record_id, "invalid_amount")
    if discount_amount < 0:
        _warn(model_name, "discount_amount", "discount_amount should not be negative", record_id, "invalid_amount")
    if write_off_amount < 0:
        _warn(model_name, "write_off_amount", "write_off_amount should not be negative", record_id, "invalid_amount")
    if conversion_rate <= 0:
        _warn(model_name, "conversion_rate", "conversion_rate should be positive", record_id, "invalid_amount")
    if base_allocated_amount is not None and conversion_rate > 0:
        expected = allocated * conversion_rate
        if not _is_close(expected, base_allocated_amount):
            _warn(model_name, "base_allocated_amount", "base_allocated_amount does not match allocated_amount * conversion_rate", record_id, "inconsistent_total")
    if base_discount_amount is not None and conversion_rate > 0:
        expected = discount_amount * conversion_rate
        if not _is_close(expected, base_discount_amount):
            _warn(model_name, "base_discount_amount", "base_discount_amount does not match discount_amount * conversion_rate", record_id, "inconsistent_total")
    if base_write_off_amount is not None and conversion_rate > 0:
        expected = write_off_amount * conversion_rate
        if not _is_close(expected, base_write_off_amount):
            _warn(model_name, "base_write_off_amount", "base_write_off_amount does not match write_off_amount * conversion_rate", record_id, "inconsistent_total")

    allocation_type = _enum_value(getattr(instance, "allocation_type", None)).lower()
    document_id = getattr(instance, "document_id", None)
    if document_id:
        document = None
        if allocation_type == "invoice":
            from app.models.invoice import Invoice

            document = session.query(Invoice).filter(Invoice.id == document_id).first()
        elif allocation_type == "bill":
            from app.models.accounting import PurchaseInvoice

            document = session.query(PurchaseInvoice).filter(PurchaseInvoice.id == document_id).first()
        elif allocation_type == "credit_note":
            from app.models.credit_note import CreditNote

            document = session.query(CreditNote).filter(CreditNote.id == document_id).first()
        elif allocation_type == "debit_note":
            from app.models.books_settings import DebitNote

            document = session.query(DebitNote).filter(DebitNote.id == document_id).first()
        if not document:
            _warn(model_name, "document_id", "document_id does not resolve for allocation_type", record_id, "missing_reference")
        else:
            outstanding = None
            if hasattr(document, "balance") and getattr(document, "balance", None) is not None:
                outstanding = getattr(document, "balance")
            elif hasattr(document, "outstanding_amount") and getattr(document, "outstanding_amount", None) is not None:
                outstanding = getattr(document, "outstanding_amount")
            if outstanding is not None and instance.total_settled > outstanding + Decimal("0.01"):
                _warn(model_name, "allocated_amount", "allocation exceeds document outstanding balance", record_id, "inconsistent_total")


def _rule_bank_transaction(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    deposit = getattr(instance, "deposit", None) or Decimal("0")
    withdrawal = getattr(instance, "withdrawal", None) or Decimal("0")
    allocated = getattr(instance, "allocated_amount", None) or Decimal("0")
    unallocated = getattr(instance, "unallocated_amount", None) or Decimal("0")
    conversion_rate = getattr(instance, "conversion_rate", None) or Decimal("0")
    base_amount = getattr(instance, "base_amount", None)

    if deposit > 0 and withdrawal > 0:
        _warn(model_name, "deposit,withdrawal", "both deposit and withdrawal are set", record_id, "invalid_amount")
    if deposit == 0 and withdrawal == 0:
        _warn(model_name, "deposit,withdrawal", "transaction has no amount", record_id, "invalid_amount")

    total_amount = deposit if deposit > 0 else withdrawal
    if allocated + unallocated > total_amount + Decimal("0.01"):
        _warn(model_name, "allocated_amount,unallocated_amount", "allocated + unallocated exceeds transaction amount", record_id, "inconsistent_total")

    status = _enum_value(getattr(instance, "status", None)).lower()
    if status == "reconciled" and unallocated > Decimal("0.01"):
        _warn(model_name, "unallocated_amount", "unallocated_amount should be zero when reconciled", record_id, "inconsistent_total")

    if conversion_rate <= 0:
        _warn(model_name, "conversion_rate", "conversion_rate should be positive", record_id, "invalid_amount")
    if base_amount is not None and conversion_rate > 0:
        expected = total_amount * conversion_rate
        if not _is_close(expected, base_amount):
            _warn(model_name, "base_amount", "base_amount does not match transaction amount * conversion_rate", record_id, "inconsistent_total")

    splits = getattr(instance, "splits", None)
    if not splits and record_id:
        from app.models.bank_transaction_split import BankTransactionSplit

        splits = session.query(BankTransactionSplit).filter(BankTransactionSplit.bank_transaction_id == record_id).all()
    if splits:
        splits_total = sum((split.amount or Decimal("0")) for split in splits)
        if not _is_close(splits_total, total_amount):
            _warn(model_name, "splits", "split totals do not match transaction amount", record_id, "inconsistent_total")


def _rule_bank_transaction_payment(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    allocated = getattr(instance, "allocated_amount", None) or Decimal("0")
    if allocated <= 0:
        _warn(model_name, "allocated_amount", "allocated_amount should be greater than zero", record_id, "invalid_amount")
    if not getattr(instance, "payment_entry", None):
        _warn(model_name, "payment_entry", "payment_entry is required", record_id, "missing_required")


def _rule_bank_reconciliation(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    status = _enum_value(getattr(instance, "status", None)).upper()
    total_amount = getattr(instance, "total_amount", None) or Decimal("0")
    if status == "COMPLETED" and total_amount == 0:
        _warn(model_name, "total_amount", "total_amount should be set when reconciliation is completed", record_id, "missing_required")


def _rule_gl_entry(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    debit = getattr(instance, "debit", None) or Decimal("0")
    credit = getattr(instance, "credit", None) or Decimal("0")
    if debit > 0 and credit > 0:
        _warn(model_name, "debit,credit", "both debit and credit are set", record_id, "invalid_amount")
    if debit == 0 and credit == 0:
        _warn(model_name, "debit,credit", "entry has no debit or credit amount", record_id, "invalid_amount")
    if not getattr(instance, "account_id", None) and getattr(instance, "account", None):
        _warn(model_name, "account_id", "account_id missing for entry with account name", record_id, "missing_required")


def _rule_account(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    if not getattr(instance, "root_type", None) and not getattr(instance, "is_group", False):
        _warn(model_name, "root_type", "root_type is recommended for non-group accounts", record_id, "missing_required")


def _rule_exchange_rate(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    rate = getattr(instance, "rate", None) or Decimal("0")
    if rate <= 0:
        _warn(model_name, "rate", "exchange rate should be positive", record_id, "invalid_amount")
    from_currency = getattr(instance, "from_currency", None)
    to_currency = getattr(instance, "to_currency", None)
    if from_currency and to_currency and from_currency == to_currency:
        _warn(model_name, "from_currency,to_currency", "from_currency and to_currency should differ", record_id, "invalid_value")


def _rule_fiscal_period(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    status = _enum_value(getattr(instance, "status", None)).lower()
    if status == "hard_closed" and getattr(instance, "closed_at", None) is None:
        _warn(model_name, "closed_at", "closed_at is required when status=hard_closed", record_id, "missing_required")


def _rule_gateway_transaction(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    amount = getattr(instance, "amount", None) or Decimal("0")
    fees = getattr(instance, "fees", None) or Decimal("0")
    net_amount = getattr(instance, "net_amount", None) or Decimal("0")
    if amount <= 0:
        _warn(model_name, "amount", "amount should be greater than zero", record_id, "invalid_amount")
    if net_amount and abs((amount - fees) - net_amount) > Decimal("0.01"):
        _warn(model_name, "net_amount", "net_amount does not match amount minus fees", record_id, "inconsistent_total")

    status = _enum_value(getattr(instance, "status", None)).lower()
    if status == "success" and getattr(instance, "completed_at", None) is None:
        _warn(model_name, "completed_at", "completed_at is required when status=success", record_id, "missing_required")
    if status == "failed" and not getattr(instance, "failure_reason", None):
        _warn(model_name, "failure_reason", "failure_reason is required when status=failed", record_id, "missing_required")


def _rule_payment_subscription(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    amount = getattr(instance, "amount", None) or Decimal("0")
    if amount <= 0:
        _warn(model_name, "amount", "amount should be greater than zero", record_id, "invalid_amount")

    start = getattr(instance, "current_period_start", None)
    end = getattr(instance, "current_period_end", None)
    if start and end and start > end:
        _warn(model_name, "current_period_start,current_period_end", "current_period_start is after current_period_end", record_id, "invalid_range")

    status = _enum_value(getattr(instance, "status", None)).lower()
    if status in {"cancelled", "expired"} and getattr(instance, "cancelled_at", None) is None:
        _warn(model_name, "cancelled_at", "cancelled_at is recommended when subscription is cancelled", record_id, "missing_required")


def _rule_tax_code(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    rate = getattr(instance, "rate", None)
    if rate is not None:
        try:
            rate_value = Decimal(str(rate))
        except Exception:
            rate_value = None
        if rate_value is not None and (rate_value < 0 or rate_value > 100):
            _warn(model_name, "rate", "rate should be between 0 and 100", record_id, "invalid_amount")

    rounding_precision = getattr(instance, "rounding_precision", None)
    if rounding_precision is not None and (rounding_precision < 0 or rounding_precision > 6):
        _warn(model_name, "rounding_precision", "rounding_precision should be between 0 and 6", record_id, "invalid_value")

    if getattr(instance, "is_tax_inclusive", False) and (rate is None or Decimal(str(rate)) == 0):
        _warn(model_name, "rate", "tax-inclusive codes should have a positive rate", record_id, "missing_required")

    valid_from = getattr(instance, "valid_from", None)
    valid_to = getattr(instance, "valid_to", None)
    if valid_from and valid_to and valid_from > valid_to:
        _warn(model_name, "valid_from,valid_to", "valid_from is after valid_to", record_id, "invalid_range")

    if getattr(instance, "is_active", True) and valid_to and valid_to < datetime.utcnow().date():
        _warn(model_name, "valid_to", "tax code is active but validity has expired", record_id, "invalid_range")


def _rule_sales_tax_template_detail(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    rate = getattr(instance, "rate", None) or Decimal("0")
    if rate < 0 or rate > 100:
        _warn(model_name, "rate", "rate should be between 0 and 100", record_id, "invalid_amount")
    tax_amount = getattr(instance, "tax_amount", None) or Decimal("0")
    if tax_amount < 0:
        _warn(model_name, "tax_amount", "tax_amount should not be negative", record_id, "invalid_amount")
    if rate > 0 and not getattr(instance, "account_head", None):
        _warn(model_name, "account_head", "account_head is required for non-zero tax rate", record_id, "missing_required")


def _rule_purchase_tax_template_detail(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    rate = getattr(instance, "rate", None) or Decimal("0")
    if rate < 0 or rate > 100:
        _warn(model_name, "rate", "rate should be between 0 and 100", record_id, "invalid_amount")
    tax_amount = getattr(instance, "tax_amount", None) or Decimal("0")
    if tax_amount < 0:
        _warn(model_name, "tax_amount", "tax_amount should not be negative", record_id, "invalid_amount")
    if rate > 0 and not getattr(instance, "account_head", None):
        _warn(model_name, "account_head", "account_head is required for non-zero tax rate", record_id, "missing_required")


def _rule_item_tax_template_detail(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    tax_rate = getattr(instance, "tax_rate", None) or Decimal("0")
    if tax_rate < 0 or tax_rate > 100:
        _warn(model_name, "tax_rate", "tax_rate should be between 0 and 100", record_id, "invalid_amount")
    if tax_rate > 0 and not getattr(instance, "tax_type", None):
        _warn(model_name, "tax_type", "tax_type is required for non-zero tax_rate", record_id, "missing_required")


def _rule_tax_filing_period(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    period_start = getattr(instance, "period_start", None)
    period_end = getattr(instance, "period_end", None)
    due_date = getattr(instance, "due_date", None)
    if period_start and period_end and period_start > period_end:
        _warn(model_name, "period_start,period_end", "period_start is after period_end", record_id, "invalid_range")
    if due_date and period_end and due_date < period_end:
        _warn(model_name, "due_date", "due_date is before period_end", record_id, "invalid_range")

    tax_base = getattr(instance, "tax_base", None) or Decimal("0")
    tax_amount = getattr(instance, "tax_amount", None) or Decimal("0")
    amount_paid = getattr(instance, "amount_paid", None) or Decimal("0")
    if tax_base < 0:
        _warn(model_name, "tax_base", "tax_base should not be negative", record_id, "invalid_amount")
    if tax_amount < 0:
        _warn(model_name, "tax_amount", "tax_amount should not be negative", record_id, "invalid_amount")
    if amount_paid > tax_amount + Decimal("0.01"):
        _warn(model_name, "amount_paid", "amount_paid exceeds tax_amount", record_id, "inconsistent_total")

    status = _enum_value(getattr(instance, "status", None)).lower()
    if status == "filed" and getattr(instance, "filed_at", None) is None:
        _warn(model_name, "filed_at", "filed_at is required when status=filed", record_id, "missing_required")
    if status == "paid" and amount_paid + Decimal("0.01") < tax_amount:
        _warn(model_name, "amount_paid", "amount_paid should cover tax_amount when status=paid", record_id, "inconsistent_total")


def _rule_tax_payment(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    amount = getattr(instance, "amount", None) or Decimal("0")
    if amount <= 0:
        _warn(model_name, "amount", "amount should be greater than zero", record_id, "invalid_amount")

    period_id = getattr(instance, "filing_period_id", None)
    if period_id:
        from app.models.tax import TaxFilingPeriod

        period = session.query(TaxFilingPeriod).filter(TaxFilingPeriod.id == period_id).first()
        if period:
            payment_date = getattr(instance, "payment_date", None)
            if payment_date and payment_date < period.period_start:
                _warn(model_name, "payment_date", "payment_date is before period_start", record_id, "invalid_range")
            if payment_date and period.due_date and payment_date > period.due_date:
                _warn(model_name, "payment_date", "payment_date is after due_date", record_id, "invalid_range")


def _rule_tax_category(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    if getattr(instance, "disabled", False) and getattr(instance, "last_synced_at", None) is None:
        _warn(model_name, "disabled", "disabled tax category has no last_synced_at", record_id, "invalid_state")


def _rule_sales_tax_template(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    if getattr(instance, "is_default", False) and not getattr(instance, "company", None):
        _warn(model_name, "company", "company is required for default sales tax template", record_id, "missing_required")

    taxes = getattr(instance, "taxes", None)
    if not taxes and record_id:
        from app.models.tax import SalesTaxTemplateDetail

        taxes = session.query(SalesTaxTemplateDetail).filter(SalesTaxTemplateDetail.template_id == record_id).all()
    if taxes is not None and len(taxes) == 0:
        _warn(model_name, "taxes", "sales tax template has no tax lines", record_id, "missing_required")


def _rule_purchase_tax_template(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    if getattr(instance, "is_default", False) and not getattr(instance, "company", None):
        _warn(model_name, "company", "company is required for default purchase tax template", record_id, "missing_required")

    taxes = getattr(instance, "taxes", None)
    if not taxes and record_id:
        from app.models.tax import PurchaseTaxTemplateDetail

        taxes = session.query(PurchaseTaxTemplateDetail).filter(PurchaseTaxTemplateDetail.template_id == record_id).all()
    if taxes is not None and len(taxes) == 0:
        _warn(model_name, "taxes", "purchase tax template has no tax lines", record_id, "missing_required")


def _rule_item_tax_template(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    taxes = getattr(instance, "taxes", None)
    if not taxes and record_id:
        from app.models.tax import ItemTaxTemplateDetail

        taxes = session.query(ItemTaxTemplateDetail).filter(ItemTaxTemplateDetail.template_id == record_id).all()
    if taxes is not None and len(taxes) == 0:
        _warn(model_name, "taxes", "item tax template has no tax lines", record_id, "missing_required")


def _rule_tax_withholding_category(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    if not getattr(instance, "account", None):
        _warn(model_name, "account", "account is required for tax withholding category", record_id, "missing_required")


def _rule_tax_rule(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    tax_type = (getattr(instance, "tax_type", None) or "").lower()
    sales_template = getattr(instance, "sales_tax_template", None)
    purchase_template = getattr(instance, "purchase_tax_template", None)
    if tax_type == "sales" and not sales_template:
        _warn(model_name, "sales_tax_template", "sales_tax_template is required for Sales tax rules", record_id, "missing_required")
    if tax_type == "purchase" and not purchase_template:
        _warn(model_name, "purchase_tax_template", "purchase_tax_template is required for Purchase tax rules", record_id, "missing_required")
    if tax_type and not sales_template and not purchase_template:
        _warn(model_name, "sales_tax_template,purchase_tax_template", "tax rule is missing a tax template", record_id, "missing_required")

    priority = getattr(instance, "priority", None)
    if priority is not None and priority < 1:
        _warn(model_name, "priority", "priority should be at least 1", record_id, "invalid_value")


def _rule_bank_transaction_split(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    amount = getattr(instance, "amount", None) or Decimal("0")
    base_amount = getattr(instance, "base_amount", None)
    tax_rate = getattr(instance, "tax_rate", None) or Decimal("0")
    tax_amount = getattr(instance, "tax_amount", None) or Decimal("0")

    if amount == 0:
        _warn(model_name, "amount", "split amount should not be zero", record_id, "invalid_amount")
    if base_amount is not None and base_amount < 0:
        _warn(model_name, "base_amount", "base_amount should not be negative", record_id, "invalid_amount")
    if tax_rate < 0 or tax_rate > 100:
        _warn(model_name, "tax_rate", "tax_rate should be between 0 and 100", record_id, "invalid_amount")
    if tax_amount < 0:
        _warn(model_name, "tax_amount", "tax_amount should not be negative", record_id, "invalid_amount")
    if tax_rate > 0 and not getattr(instance, "tax_code_id", None):
        _warn(model_name, "tax_code_id", "tax_code_id is required for non-zero tax_rate", record_id, "missing_required")


def _rule_credit_note_line(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    _rule_invoice_line(session, instance, model_name, record_id)


def _rule_debit_note_line(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    _rule_invoice_line(session, instance, model_name, record_id)


def _rule_tax_settings(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    annual_turnover = getattr(instance, "annual_turnover", None) or Decimal("0")
    vat_rate = getattr(instance, "vat_rate", None) or Decimal("0")
    einvoice_threshold = getattr(instance, "einvoice_threshold", None) or Decimal("0")
    fiscal_month = getattr(instance, "fiscal_year_start_month", None)

    if annual_turnover < 0:
        _warn(model_name, "annual_turnover", "annual_turnover should not be negative", record_id, "invalid_amount")
    if vat_rate < 0 or vat_rate > 1:
        _warn(model_name, "vat_rate", "vat_rate should be between 0 and 1", record_id, "invalid_amount")
    if einvoice_threshold < 0:
        _warn(model_name, "einvoice_threshold", "einvoice_threshold should not be negative", record_id, "invalid_amount")
    if fiscal_month is not None and not 1 <= fiscal_month <= 12:
        _warn(model_name, "fiscal_year_start_month", "fiscal_year_start_month should be 1-12", record_id, "invalid_value")


def _rule_nigerian_tax_rate(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    rate = getattr(instance, "rate", None) or Decimal("0")
    if rate < 0 or rate > 1:
        _warn(model_name, "rate", "rate should be between 0 and 1", record_id, "invalid_amount")

    min_threshold = getattr(instance, "min_threshold", None)
    max_threshold = getattr(instance, "max_threshold", None)
    if min_threshold is not None and max_threshold is not None and min_threshold > max_threshold:
        _warn(model_name, "min_threshold,max_threshold", "min_threshold is greater than max_threshold", record_id, "invalid_range")

    effective_from = getattr(instance, "effective_from", None)
    effective_to = getattr(instance, "effective_to", None)
    if effective_from and effective_to and effective_from > effective_to:
        _warn(model_name, "effective_from,effective_to", "effective_from is after effective_to", record_id, "invalid_range")

    tax_type = _enum_value(getattr(instance, "tax_type", None)).lower()
    wht_payment_type = getattr(instance, "wht_payment_type", None)
    if tax_type == "wht" and wht_payment_type is None:
        _warn(model_name, "wht_payment_type", "wht_payment_type is required for WHT rates", record_id, "missing_required")
    if tax_type != "wht" and wht_payment_type is not None:
        _warn(model_name, "wht_payment_type", "wht_payment_type should be empty unless tax_type is WHT", record_id, "invalid_value")


def _rule_vat_transaction(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    taxable_amount = getattr(instance, "taxable_amount", None) or Decimal("0")
    vat_rate = getattr(instance, "vat_rate", None) or Decimal("0")
    vat_amount = getattr(instance, "vat_amount", None) or Decimal("0")
    total_amount = getattr(instance, "total_amount", None) or Decimal("0")
    exchange_rate = getattr(instance, "exchange_rate", None) or Decimal("0")

    if taxable_amount < 0:
        _warn(model_name, "taxable_amount", "taxable_amount should not be negative", record_id, "invalid_amount")
    if vat_rate < 0 or vat_rate > 1:
        _warn(model_name, "vat_rate", "vat_rate should be between 0 and 1", record_id, "invalid_amount")
    if vat_amount < 0:
        _warn(model_name, "vat_amount", "vat_amount should not be negative", record_id, "invalid_amount")
    if total_amount < 0:
        _warn(model_name, "total_amount", "total_amount should not be negative", record_id, "invalid_amount")
    if exchange_rate <= 0:
        _warn(model_name, "exchange_rate", "exchange_rate should be positive", record_id, "invalid_amount")
    if not _is_close(taxable_amount + vat_amount, total_amount):
        _warn(model_name, "total_amount", "total_amount does not match taxable_amount + vat_amount", record_id, "inconsistent_total")

    is_exempt = getattr(instance, "is_exempt", False)
    is_zero_rated = getattr(instance, "is_zero_rated", False)
    if (is_exempt or is_zero_rated) and vat_amount > 0:
        _warn(model_name, "vat_amount", "vat_amount should be zero for exempt/zero-rated transactions", record_id, "invalid_amount")
    if is_exempt and not getattr(instance, "exemption_reason", None):
        _warn(model_name, "exemption_reason", "exemption_reason is required for exempt transactions", record_id, "missing_required")


def _rule_wht_transaction(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    gross_amount = getattr(instance, "gross_amount", None) or Decimal("0")
    wht_rate = getattr(instance, "wht_rate", None) or Decimal("0")
    standard_rate = getattr(instance, "standard_rate", None) or Decimal("0")
    wht_amount = getattr(instance, "wht_amount", None) or Decimal("0")
    net_amount = getattr(instance, "net_amount", None) or Decimal("0")
    exchange_rate = getattr(instance, "exchange_rate", None) or Decimal("0")

    if gross_amount < 0:
        _warn(model_name, "gross_amount", "gross_amount should not be negative", record_id, "invalid_amount")
    if wht_rate < 0 or wht_rate > 1:
        _warn(model_name, "wht_rate", "wht_rate should be between 0 and 1", record_id, "invalid_amount")
    if standard_rate < 0 or standard_rate > 1:
        _warn(model_name, "standard_rate", "standard_rate should be between 0 and 1", record_id, "invalid_amount")
    if wht_amount < 0:
        _warn(model_name, "wht_amount", "wht_amount should not be negative", record_id, "invalid_amount")
    if net_amount < 0:
        _warn(model_name, "net_amount", "net_amount should not be negative", record_id, "invalid_amount")
    if exchange_rate <= 0:
        _warn(model_name, "exchange_rate", "exchange_rate should be positive", record_id, "invalid_amount")
    if not _is_close(gross_amount - wht_amount, net_amount):
        _warn(model_name, "net_amount", "net_amount does not match gross_amount minus wht_amount", record_id, "inconsistent_total")

    if not getattr(instance, "has_valid_tin", True) and wht_rate <= standard_rate:
        _warn(model_name, "wht_rate", "wht_rate should exceed standard_rate when supplier has no valid TIN", record_id, "invalid_amount")

    remittance_due_date = getattr(instance, "remittance_due_date", None)
    transaction_date = getattr(instance, "transaction_date", None)
    if remittance_due_date and transaction_date and remittance_due_date < transaction_date:
        _warn(model_name, "remittance_due_date", "remittance_due_date is before transaction_date", record_id, "invalid_range")
    if getattr(instance, "is_remitted", False) and getattr(instance, "remitted_at", None) is None:
        _warn(model_name, "remitted_at", "remitted_at is required when is_remitted is true", record_id, "missing_required")


def _rule_wht_certificate(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    period_start = getattr(instance, "period_start", None)
    period_end = getattr(instance, "period_end", None)
    if period_start and period_end and period_start > period_end:
        _warn(model_name, "period_start,period_end", "period_start is after period_end", record_id, "invalid_range")

    total_gross = getattr(instance, "total_gross_amount", None) or Decimal("0")
    total_wht = getattr(instance, "total_wht_amount", None) or Decimal("0")
    if total_gross < 0:
        _warn(model_name, "total_gross_amount", "total_gross_amount should not be negative", record_id, "invalid_amount")
    if total_wht < 0:
        _warn(model_name, "total_wht_amount", "total_wht_amount should not be negative", record_id, "invalid_amount")
    if total_wht > total_gross + Decimal("0.01"):
        _warn(model_name, "total_wht_amount", "total_wht_amount exceeds total_gross_amount", record_id, "inconsistent_total")

    issue_date = getattr(instance, "issue_date", None)
    valid_until = getattr(instance, "valid_until", None)
    if issue_date and valid_until and issue_date > valid_until:
        _warn(model_name, "valid_until", "valid_until is before issue_date", record_id, "invalid_range")
    if getattr(instance, "is_issued", False) and getattr(instance, "issued_at", None) is None:
        _warn(model_name, "issued_at", "issued_at is required when is_issued is true", record_id, "missing_required")
    if getattr(instance, "is_cancelled", False) and not getattr(instance, "cancellation_reason", None):
        _warn(model_name, "cancellation_reason", "cancellation_reason is required when certificate is cancelled", record_id, "missing_required")


def _rule_paye_calculation(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    gross_income = getattr(instance, "gross_income", None) or Decimal("0")
    annual_gross_income = getattr(instance, "annual_gross_income", None) or Decimal("0")
    total_reliefs = getattr(instance, "total_reliefs", None) or Decimal("0")
    annual_taxable_income = getattr(instance, "annual_taxable_income", None) or Decimal("0")
    annual_tax = getattr(instance, "annual_tax", None) or Decimal("0")
    monthly_tax = getattr(instance, "monthly_tax", None) or Decimal("0")
    effective_rate = getattr(instance, "effective_rate", None) or Decimal("0")

    components = [
        getattr(instance, "basic_salary", None) or Decimal("0"),
        getattr(instance, "housing_allowance", None) or Decimal("0"),
        getattr(instance, "transport_allowance", None) or Decimal("0"),
        getattr(instance, "other_allowances", None) or Decimal("0"),
        getattr(instance, "bonus", None) or Decimal("0"),
    ]
    components_sum = sum(components)
    if not _is_close(components_sum, gross_income):
        _warn(model_name, "gross_income", "gross_income does not match sum of income components", record_id, "inconsistent_total")
    if total_reliefs < 0:
        _warn(model_name, "total_reliefs", "total_reliefs should not be negative", record_id, "invalid_amount")
    if total_reliefs > annual_gross_income + Decimal("0.01"):
        _warn(model_name, "total_reliefs", "total_reliefs exceeds annual_gross_income", record_id, "invalid_amount")
    if annual_gross_income < gross_income:
        _warn(model_name, "annual_gross_income", "annual_gross_income is less than gross_income", record_id, "invalid_amount")
    if annual_taxable_income < 0:
        _warn(model_name, "annual_taxable_income", "annual_taxable_income should not be negative", record_id, "invalid_amount")
    if annual_tax < 0 or monthly_tax < 0:
        _warn(model_name, "annual_tax,monthly_tax", "tax amounts should not be negative", record_id, "invalid_amount")
    if effective_rate < 0 or effective_rate > 1:
        _warn(model_name, "effective_rate", "effective_rate should be between 0 and 1", record_id, "invalid_amount")
    if annual_tax > 0 and monthly_tax > 0:
        expected_monthly = (annual_tax / Decimal("12"))
        if not _is_close(expected_monthly, monthly_tax):
            _warn(model_name, "monthly_tax", "monthly_tax does not match annual_tax / 12", record_id, "inconsistent_total")


def _rule_cit_assessment(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    gross_turnover = getattr(instance, "gross_turnover", None) or Decimal("0")
    gross_profit = getattr(instance, "gross_profit", None) or Decimal("0")
    adjusted_profit = getattr(instance, "adjusted_profit", None) or Decimal("0")
    assessable_profit = getattr(instance, "assessable_profit", None) or Decimal("0")
    cit_rate = getattr(instance, "cit_rate", None) or Decimal("0")
    tet_rate = getattr(instance, "tet_rate", None) or Decimal("0")
    cit_amount = getattr(instance, "cit_amount", None) or Decimal("0")
    tet_amount = getattr(instance, "tet_amount", None) or Decimal("0")
    total_tax_liability = getattr(instance, "total_tax_liability", None) or Decimal("0")
    amount_paid = getattr(instance, "amount_paid", None) or Decimal("0")
    balance_due = getattr(instance, "balance_due", None) or Decimal("0")

    for field_name, value in (
        ("gross_turnover", gross_turnover),
        ("gross_profit", gross_profit),
        ("adjusted_profit", adjusted_profit),
        ("assessable_profit", assessable_profit),
        ("cit_amount", cit_amount),
        ("tet_amount", tet_amount),
        ("total_tax_liability", total_tax_liability),
        ("amount_paid", amount_paid),
        ("balance_due", balance_due),
    ):
        if value < 0:
            _warn(model_name, field_name, f"{field_name} should not be negative", record_id, "invalid_amount")

    if cit_rate < 0 or cit_rate > 1:
        _warn(model_name, "cit_rate", "cit_rate should be between 0 and 1", record_id, "invalid_amount")
    if tet_rate < 0 or tet_rate > 1:
        _warn(model_name, "tet_rate", "tet_rate should be between 0 and 1", record_id, "invalid_amount")
    if amount_paid > total_tax_liability + Decimal("0.01"):
        _warn(model_name, "amount_paid", "amount_paid exceeds total_tax_liability", record_id, "invalid_amount")
    if not _is_close(total_tax_liability - amount_paid, balance_due):
        _warn(model_name, "balance_due", "balance_due does not match total_tax_liability minus amount_paid", record_id, "inconsistent_total")

    period_start = getattr(instance, "period_start", None)
    period_end = getattr(instance, "period_end", None)
    if period_start and period_end and period_start > period_end:
        _warn(model_name, "period_start,period_end", "period_start is after period_end", record_id, "invalid_range")
    due_date = getattr(instance, "due_date", None)
    if due_date and period_end and due_date < period_end:
        _warn(model_name, "due_date", "due_date is before period_end", record_id, "invalid_range")
    if getattr(instance, "is_filed", False) and getattr(instance, "filed_at", None) is None:
        _warn(model_name, "filed_at", "filed_at is required when is_filed is true", record_id, "missing_required")


def _rule_einvoice(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    issue_date = getattr(instance, "issue_date", None)
    due_date = getattr(instance, "due_date", None)
    if issue_date and due_date and issue_date > due_date:
        _warn(model_name, "due_date", "due_date is before issue_date", record_id, "invalid_range")

    line_extension_amount = getattr(instance, "line_extension_amount", None) or Decimal("0")
    tax_exclusive_amount = getattr(instance, "tax_exclusive_amount", None) or Decimal("0")
    tax_inclusive_amount = getattr(instance, "tax_inclusive_amount", None) or Decimal("0")
    allowance_total_amount = getattr(instance, "allowance_total_amount", None) or Decimal("0")
    charge_total_amount = getattr(instance, "charge_total_amount", None) or Decimal("0")
    tax_amount = getattr(instance, "tax_amount", None) or Decimal("0")
    payable_amount = getattr(instance, "payable_amount", None) or Decimal("0")

    if not _is_close(line_extension_amount, tax_exclusive_amount):
        _warn(model_name, "tax_exclusive_amount", "tax_exclusive_amount does not match line_extension_amount", record_id, "inconsistent_total")
    expected_inclusive = tax_exclusive_amount + tax_amount
    if not _is_close(expected_inclusive, tax_inclusive_amount):
        _warn(model_name, "tax_inclusive_amount", "tax_inclusive_amount does not match tax_exclusive_amount + tax_amount", record_id, "inconsistent_total")
    expected_payable = tax_inclusive_amount + charge_total_amount - allowance_total_amount
    if not _is_close(expected_payable, payable_amount):
        _warn(model_name, "payable_amount", "payable_amount does not match totals with charges/allowances", record_id, "inconsistent_total")

    status = _enum_value(getattr(instance, "status", None)).lower()
    if status in {"validated", "submitted", "accepted"} and getattr(instance, "validated_at", None) is None:
        _warn(model_name, "validated_at", "validated_at is required once e-invoice is validated/submitted", record_id, "missing_required")

    lines = getattr(instance, "lines", None)
    if not lines and record_id:
        from app.models.tax_ng import EInvoiceLine

        lines = session.query(EInvoiceLine).filter(EInvoiceLine.einvoice_id == record_id).all()
    if lines:
        lines_total = sum((line.line_extension_amount or Decimal("0")) for line in lines)
        lines_tax = sum((line.tax_amount or Decimal("0")) for line in lines)
        if not _is_close(lines_total, line_extension_amount):
            _warn(model_name, "line_extension_amount", "line_extension_amount does not match sum of line items", record_id, "inconsistent_total")
        if not _is_close(lines_tax, tax_amount):
            _warn(model_name, "tax_amount", "tax_amount does not match sum of line item taxes", record_id, "inconsistent_total")


def _rule_einvoice_line(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    quantity = getattr(instance, "quantity", None) or Decimal("0")
    unit_price = getattr(instance, "unit_price", None) or Decimal("0")
    line_extension_amount = getattr(instance, "line_extension_amount", None) or Decimal("0")
    allowance_amount = getattr(instance, "allowance_amount", None) or Decimal("0")
    charge_amount = getattr(instance, "charge_amount", None) or Decimal("0")
    tax_amount = getattr(instance, "tax_amount", None) or Decimal("0")
    total_amount = getattr(instance, "total_amount", None) or Decimal("0")

    if quantity <= 0:
        _warn(model_name, "quantity", "quantity should be greater than zero", record_id, "invalid_amount")
    if unit_price < 0:
        _warn(model_name, "unit_price", "unit_price should not be negative", record_id, "invalid_amount")
    if allowance_amount < 0:
        _warn(model_name, "allowance_amount", "allowance_amount should not be negative", record_id, "invalid_amount")
    if charge_amount < 0:
        _warn(model_name, "charge_amount", "charge_amount should not be negative", record_id, "invalid_amount")
    if tax_amount < 0:
        _warn(model_name, "tax_amount", "tax_amount should not be negative", record_id, "invalid_amount")

    expected_extension = quantity * unit_price
    if not _is_close(expected_extension, line_extension_amount):
        _warn(model_name, "line_extension_amount", "line_extension_amount does not match quantity * unit_price", record_id, "inconsistent_total")
    expected_total = line_extension_amount - allowance_amount + charge_amount + tax_amount
    if not _is_close(expected_total, total_amount):
        _warn(model_name, "total_amount", "total_amount does not match line amounts + tax", record_id, "inconsistent_total")

def _rule_asset_category(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    if getattr(instance, "enable_cwip_accounting", False):
        has_cwip = False
        finance_books = getattr(instance, "finance_books", None)
        if finance_books:
            has_cwip = any(getattr(fb, "capital_work_in_progress_account", None) for fb in finance_books)
        elif record_id:
            from app.models.asset import AssetCategoryFinanceBook
            rows = (
                session.query(AssetCategoryFinanceBook)
                .filter(AssetCategoryFinanceBook.asset_category_id == record_id)
                .all()
            )
            has_cwip = any(row.capital_work_in_progress_account for row in rows)
        if not has_cwip:
            _warn(model_name, "capital_work_in_progress_account", "CWIP accounting enabled but no CWIP account configured", record_id, "missing_required")


def _rule_asset_category_finance_book(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    total_depr = getattr(instance, "total_number_of_depreciations", None) or 0
    if total_depr <= 0:
        _warn(model_name, "total_number_of_depreciations", "total_number_of_depreciations should be positive", record_id, "invalid_amount")

    freq = getattr(instance, "frequency_of_depreciation", None) or 0
    if freq <= 0:
        _warn(model_name, "frequency_of_depreciation", "frequency_of_depreciation should be positive", record_id, "invalid_amount")


def _rule_asset(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    gross_purchase_amount = getattr(instance, "gross_purchase_amount", None) or Decimal("0")
    asset_value = getattr(instance, "asset_value", None) or Decimal("0")
    asset_quantity = getattr(instance, "asset_quantity", None) or 0

    if gross_purchase_amount < 0:
        _warn(model_name, "gross_purchase_amount", "gross_purchase_amount should not be negative", record_id, "invalid_amount")
    if asset_value < 0:
        _warn(model_name, "asset_value", "asset_value should not be negative", record_id, "invalid_amount")
    if asset_quantity <= 0:
        _warn(model_name, "asset_quantity", "asset_quantity should be greater than zero", record_id, "invalid_amount")

    purchase_date = getattr(instance, "purchase_date", None)
    available_for_use_date = getattr(instance, "available_for_use_date", None)
    if purchase_date and available_for_use_date and available_for_use_date < purchase_date:
        _warn(model_name, "available_for_use_date", "available_for_use_date is before purchase_date", record_id, "invalid_range")

    status = _enum_value(getattr(instance, "status", None)).lower()
    if status in {"sold", "scrapped"} and getattr(instance, "disposal_date", None) is None:
        _warn(model_name, "disposal_date", "disposal_date is required for disposed assets", record_id, "missing_required")

    if getattr(instance, "maintenance_required", False) and status in {"sold", "scrapped"}:
        _warn(model_name, "maintenance_required", "maintenance_required should be false for disposed assets", record_id, "invalid_value")

    insurance_start = getattr(instance, "insurance_start_date", None)
    insurance_end = getattr(instance, "insurance_end_date", None)
    if insurance_start and insurance_end and insurance_start > insurance_end:
        _warn(model_name, "insurance_start_date,insurance_end_date", "insurance_start_date is after insurance_end_date", record_id, "invalid_range")

    insured_value = getattr(instance, "insured_value", None) or Decimal("0")
    if insured_value > 0 and not insurance_start:
        _warn(model_name, "insurance_start_date", "insurance_start_date is required when insured_value is set", record_id, "missing_required")

    warranty_expiry = getattr(instance, "warranty_expiry_date", None)
    if warranty_expiry and purchase_date and warranty_expiry < purchase_date:
        _warn(model_name, "warranty_expiry_date", "warranty_expiry_date is before purchase_date", record_id, "invalid_range")

    if getattr(instance, "calculate_depreciation", False):
        finance_books = getattr(instance, "finance_books", None)
        if finance_books is not None and not finance_books:
            _warn(model_name, "finance_books", "calculate_depreciation is enabled but no finance books exist", record_id, "missing_required")


def _rule_asset_finance_book(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    total_depr = getattr(instance, "total_number_of_depreciations", None) or 0
    if total_depr <= 0:
        _warn(model_name, "total_number_of_depreciations", "total_number_of_depreciations should be positive", record_id, "invalid_amount")

    freq = getattr(instance, "frequency_of_depreciation", None) or 0
    if freq <= 0:
        _warn(model_name, "frequency_of_depreciation", "frequency_of_depreciation should be positive", record_id, "invalid_amount")

    depreciation_start = getattr(instance, "depreciation_start_date", None)
    if getattr(instance, "depreciation_method", None) and not depreciation_start:
        _warn(model_name, "depreciation_start_date", "depreciation_start_date is required when depreciation_method is set", record_id, "missing_required")

    rate = getattr(instance, "rate_of_depreciation", None)
    if rate is not None:
        try:
            rate_value = Decimal(str(rate))
        except Exception:
            rate_value = None
        if rate_value is not None and (rate_value < 0 or rate_value > 100):
            _warn(model_name, "rate_of_depreciation", "rate_of_depreciation should be between 0 and 100", record_id, "invalid_amount")

    expected_value = getattr(instance, "expected_value_after_useful_life", None) or Decimal("0")
    if expected_value < 0:
        _warn(model_name, "expected_value_after_useful_life", "expected_value_after_useful_life should not be negative", record_id, "invalid_amount")

    value_after_depr = getattr(instance, "value_after_depreciation", None) or Decimal("0")
    if value_after_depr < 0:
        _warn(model_name, "value_after_depreciation", "value_after_depreciation should not be negative", record_id, "invalid_amount")


def _rule_asset_depreciation_schedule(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    depreciation_amount = getattr(instance, "depreciation_amount", None) or Decimal("0")
    accumulated_amount = getattr(instance, "accumulated_depreciation_amount", None) or Decimal("0")
    if depreciation_amount < 0:
        _warn(model_name, "depreciation_amount", "depreciation_amount should not be negative", record_id, "invalid_amount")
    if accumulated_amount < 0:
        _warn(model_name, "accumulated_depreciation_amount", "accumulated_depreciation_amount should not be negative", record_id, "invalid_amount")
    if depreciation_amount > 0 and getattr(instance, "schedule_date", None) is None:
        _warn(model_name, "schedule_date", "schedule_date is required when depreciation_amount is set", record_id, "missing_required")
    if getattr(instance, "depreciation_booked", False) and not getattr(instance, "journal_entry", None):
        _warn(model_name, "journal_entry", "journal_entry is required when depreciation is booked", record_id, "missing_required")


def _rule_asset_settings(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    for field in ("maintenance_alert_days", "warranty_alert_days", "insurance_alert_days"):
        value = getattr(instance, field, None)
        if value is not None and value < 0:
            _warn(model_name, field, f"{field} should not be negative", record_id, "invalid_amount")


def _rule_item(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    if getattr(instance, "is_stock_item", False) and not getattr(instance, "stock_uom", None):
        _warn(model_name, "stock_uom", "stock_uom is required for stock items", record_id, "missing_required")

    if getattr(instance, "has_serial_no", False) and not getattr(instance, "is_stock_item", False):
        _warn(model_name, "has_serial_no", "serial tracking should be enabled only for stock items", record_id, "invalid_value")

    if getattr(instance, "has_batch_no", False) and not getattr(instance, "is_stock_item", False):
        _warn(model_name, "has_batch_no", "batch tracking should be enabled only for stock items", record_id, "invalid_value")

    valuation_rate = getattr(instance, "valuation_rate", None)
    if valuation_rate is not None and valuation_rate < 0:
        _warn(model_name, "valuation_rate", "valuation_rate should not be negative", record_id, "invalid_amount")

    standard_rate = getattr(instance, "standard_rate", None)
    if standard_rate is not None and standard_rate < 0:
        _warn(model_name, "standard_rate", "standard_rate should not be negative", record_id, "invalid_amount")

    reorder_level = getattr(instance, "reorder_level", None)
    if reorder_level is not None and reorder_level < 0:
        _warn(model_name, "reorder_level", "reorder_level should not be negative", record_id, "invalid_amount")

    reorder_qty = getattr(instance, "reorder_qty", None)
    if reorder_qty is not None and reorder_qty < 0:
        _warn(model_name, "reorder_qty", "reorder_qty should not be negative", record_id, "invalid_amount")


def _rule_item_group(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    if getattr(instance, "is_group", False) and getattr(instance, "parent_item_group", None) == getattr(instance, "item_group_name", None):
        _warn(model_name, "parent_item_group", "item group cannot be its own parent", record_id, "invalid_value")


def _rule_warehouse(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    if not getattr(instance, "is_group", False) and not getattr(instance, "account", None):
        _warn(model_name, "account", "account is recommended for non-group warehouses", record_id, "missing_required")


def _rule_stock_entry(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    entry_type = (getattr(instance, "stock_entry_type", None) or "").lower()
    from_wh = getattr(instance, "from_warehouse", None)
    to_wh = getattr(instance, "to_warehouse", None)
    if "transfer" in entry_type and (not from_wh or not to_wh):
        _warn(model_name, "from_warehouse,to_warehouse", "transfer entries require from_warehouse and to_warehouse", record_id, "missing_required")
    if from_wh and to_wh and from_wh == to_wh:
        _warn(model_name, "to_warehouse", "from_warehouse and to_warehouse should differ", record_id, "invalid_value")

    if getattr(instance, "docstatus", None) == 1 and getattr(instance, "posting_date", None) is None:
        _warn(model_name, "posting_date", "posting_date is required for submitted entries", record_id, "missing_required")

    total_amount = getattr(instance, "total_amount", None)
    if total_amount is not None and total_amount < 0:
        _warn(model_name, "total_amount", "total_amount should not be negative", record_id, "invalid_amount")


def _rule_stock_entry_detail(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    qty = getattr(instance, "qty", None) or Decimal("0")
    if qty <= 0:
        _warn(model_name, "qty", "qty should be greater than zero", record_id, "invalid_amount")

    if not getattr(instance, "s_warehouse", None) and not getattr(instance, "t_warehouse", None):
        _warn(model_name, "s_warehouse,t_warehouse", "either s_warehouse or t_warehouse is required", record_id, "missing_required")

    conversion_factor = getattr(instance, "conversion_factor", None) or Decimal("0")
    if conversion_factor <= 0:
        _warn(model_name, "conversion_factor", "conversion_factor should be positive", record_id, "invalid_amount")

    amount = getattr(instance, "amount", None) or Decimal("0")
    if amount < 0:
        _warn(model_name, "amount", "amount should not be negative", record_id, "invalid_amount")


def _rule_stock_ledger_entry(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    actual_qty = getattr(instance, "actual_qty", None) or Decimal("0")
    if actual_qty == 0:
        _warn(model_name, "actual_qty", "actual_qty is zero for ledger entry", record_id, "invalid_amount")
    if not getattr(instance, "warehouse", None):
        _warn(model_name, "warehouse", "warehouse is required for ledger entry", record_id, "missing_required")
    qty_after = getattr(instance, "qty_after_transaction", None)
    if qty_after is not None and qty_after < 0:
        _warn(model_name, "qty_after_transaction", "qty_after_transaction should not be negative", record_id, "invalid_amount")


def _rule_landed_cost_voucher(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    total_charges = getattr(instance, "total_taxes_and_charges", None) or Decimal("0")
    if total_charges < 0:
        _warn(model_name, "total_taxes_and_charges", "total_taxes_and_charges should not be negative", record_id, "invalid_amount")
    if record_id:
        from app.models.inventory import LandedCostTax
        tax_count = session.query(LandedCostTax).filter(LandedCostTax.voucher_id == record_id).count()
        if tax_count == 0:
            _warn(model_name, "taxes", "landed cost voucher has no taxes/charges", record_id, "missing_required")


def _rule_landed_cost_item(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    qty = getattr(instance, "qty", None) or Decimal("0")
    if qty <= 0:
        _warn(model_name, "qty", "qty should be greater than zero", record_id, "invalid_amount")
    amount = getattr(instance, "amount", None) or Decimal("0")
    if amount < 0:
        _warn(model_name, "amount", "amount should not be negative", record_id, "invalid_amount")
    charges = getattr(instance, "applicable_charges", None) or Decimal("0")
    if charges < 0:
        _warn(model_name, "applicable_charges", "applicable_charges should not be negative", record_id, "invalid_amount")


def _rule_landed_cost_tax(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    amount = getattr(instance, "amount", None) or Decimal("0")
    if amount < 0:
        _warn(model_name, "amount", "amount should not be negative", record_id, "invalid_amount")
    if amount > 0 and not getattr(instance, "expense_account", None):
        _warn(model_name, "expense_account", "expense_account is required for non-zero charges", record_id, "missing_required")


def _rule_stock_receipt(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    total_qty = getattr(instance, "total_qty", None) or Decimal("0")
    if total_qty <= 0:
        _warn(model_name, "total_qty", "total_qty should be greater than zero", record_id, "invalid_amount")
    status = _enum_value(getattr(instance, "status", None)).lower()
    if status in {"approved", "posted"} and getattr(instance, "approved_at", None) is None:
        _warn(model_name, "approved_at", "approved_at is required when receipt is approved", record_id, "missing_required")
    if status != "draft" and getattr(instance, "posting_date", None) is None:
        _warn(model_name, "posting_date", "posting_date is required for non-draft receipts", record_id, "missing_required")


def _rule_stock_receipt_item(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    qty = getattr(instance, "qty", None) or Decimal("0")
    if qty <= 0:
        _warn(model_name, "qty", "qty should be greater than zero", record_id, "invalid_amount")
    rate = getattr(instance, "rate", None) or Decimal("0")
    if rate < 0:
        _warn(model_name, "rate", "rate should not be negative", record_id, "invalid_amount")
    amount = getattr(instance, "amount", None) or Decimal("0")
    if amount < 0:
        _warn(model_name, "amount", "amount should not be negative", record_id, "invalid_amount")


def _rule_stock_issue(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    total_qty = getattr(instance, "total_qty", None) or Decimal("0")
    if total_qty <= 0:
        _warn(model_name, "total_qty", "total_qty should be greater than zero", record_id, "invalid_amount")
    total_cost = getattr(instance, "total_cost", None) or Decimal("0")
    if total_cost < 0:
        _warn(model_name, "total_cost", "total_cost should not be negative", record_id, "invalid_amount")
    status = _enum_value(getattr(instance, "status", None)).lower()
    if status in {"approved", "posted"} and getattr(instance, "approved_at", None) is None:
        _warn(model_name, "approved_at", "approved_at is required when issue is approved", record_id, "missing_required")
    if status != "draft" and getattr(instance, "posting_date", None) is None:
        _warn(model_name, "posting_date", "posting_date is required for non-draft issues", record_id, "missing_required")


def _rule_stock_issue_item(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    qty = getattr(instance, "qty", None) or Decimal("0")
    if qty <= 0:
        _warn(model_name, "qty", "qty should be greater than zero", record_id, "invalid_amount")
    valuation_rate = getattr(instance, "valuation_rate", None) or Decimal("0")
    if valuation_rate < 0:
        _warn(model_name, "valuation_rate", "valuation_rate should not be negative", record_id, "invalid_amount")
    cost_amount = getattr(instance, "cost_amount", None) or Decimal("0")
    if cost_amount < 0:
        _warn(model_name, "cost_amount", "cost_amount should not be negative", record_id, "invalid_amount")


def _rule_transfer_request(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    from_wh = getattr(instance, "from_warehouse", None)
    to_wh = getattr(instance, "to_warehouse", None)
    if not from_wh or not to_wh:
        _warn(model_name, "from_warehouse,to_warehouse", "from_warehouse and to_warehouse are required", record_id, "missing_required")
    if from_wh and to_wh and from_wh == to_wh:
        _warn(model_name, "to_warehouse", "from_warehouse and to_warehouse should differ", record_id, "invalid_value")

    total_qty = getattr(instance, "total_qty", None) or Decimal("0")
    if total_qty <= 0:
        _warn(model_name, "total_qty", "total_qty should be greater than zero", record_id, "invalid_amount")

    status = _enum_value(getattr(instance, "status", None)).lower()
    if status in {"approved", "in_transit", "completed"} and getattr(instance, "approved_at", None) is None:
        _warn(model_name, "approved_at", "approved_at is required when transfer is approved", record_id, "missing_required")
    if status == "rejected" and not getattr(instance, "rejection_reason", None):
        _warn(model_name, "rejection_reason", "rejection_reason is required for rejected transfers", record_id, "missing_required")


def _rule_transfer_request_item(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    qty = getattr(instance, "qty", None) or Decimal("0")
    if qty <= 0:
        _warn(model_name, "qty", "qty should be greater than zero", record_id, "invalid_amount")
    amount = getattr(instance, "amount", None) or Decimal("0")
    if amount < 0:
        _warn(model_name, "amount", "amount should not be negative", record_id, "invalid_amount")


def _rule_batch(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    batch_qty = getattr(instance, "batch_qty", None) or Decimal("0")
    if batch_qty < 0:
        _warn(model_name, "batch_qty", "batch_qty should not be negative", record_id, "invalid_amount")

    manufacturing_date = getattr(instance, "manufacturing_date", None)
    expiry_date = getattr(instance, "expiry_date", None)
    if manufacturing_date and expiry_date and manufacturing_date > expiry_date:
        _warn(model_name, "expiry_date", "expiry_date is before manufacturing_date", record_id, "invalid_range")
    if expiry_date and not getattr(instance, "disabled", False) and expiry_date < datetime.utcnow():
        _warn(model_name, "expiry_date", "batch has expired but is not disabled", record_id, "invalid_range")


def _rule_serial_number(session: Session, instance: Any, model_name: str, record_id: Any) -> None:
    status = _enum_value(getattr(instance, "status", None)).lower()
    if status == "delivered":
        if getattr(instance, "delivery_date", None) is None:
            _warn(model_name, "delivery_date", "delivery_date is required when status=delivered", record_id, "missing_required")
        if not getattr(instance, "customer", None):
            _warn(model_name, "customer", "customer is required when status=delivered", record_id, "missing_required")
    if status == "issued" and getattr(instance, "issued_at", None) is None:
        _warn(model_name, "issued_at", "issued_at is required when status=issued", record_id, "missing_required")
    if status == "reserved" and getattr(instance, "reserved_at", None) is None:
        _warn(model_name, "reserved_at", "reserved_at is required when status=reserved", record_id, "missing_required")
    if status == "returned" and getattr(instance, "returned_at", None) is None:
        _warn(model_name, "returned_at", "returned_at is required when status=returned", record_id, "missing_required")
    if status in {"delivered", "issued"} and getattr(instance, "warehouse", None):
        _warn(model_name, "warehouse", "warehouse should be cleared for delivered/issued serials", record_id, "invalid_value")


register_rule("SocialPost", _rule_social_post)
register_rule("EmailSend", _rule_email_send)
register_rule("OmniChannel", _rule_omni_channel)
register_rule("OmniMessage", _rule_omni_message)
register_rule("OmniConversation", _rule_omni_conversation)
register_rule("OmniParticipant", _rule_omni_participant)
register_rule("OmniAttachment", _rule_omni_attachment)
register_rule("OmniWebhookEvent", _rule_omni_webhook_event)
register_rule("InboxRoutingRule", _rule_inbox_routing_rule)
register_rule("InboxContact", _rule_inbox_contact)
register_rule("MarketingCampaign", _rule_marketing_campaign)
register_rule("JourneyTemplate", _rule_journey_template)
register_rule("CustomerJourney", _rule_customer_journey)
register_rule("JourneyStep", _rule_journey_step)
register_rule("JourneyEnrollment", _rule_journey_enrollment)
register_rule("SocialAccount", _rule_social_account)
register_rule("EmailTemplate", _rule_email_template)
register_rule("EmailCampaign", _rule_email_campaign)
register_rule("MarketingAudience", _rule_marketing_audience)
register_rule("MarketingIntegration", _rule_marketing_integration)
register_rule("MarketingConsent", _rule_marketing_consent)
register_rule("SuppressionEntry", _rule_suppression_entry)
register_rule("MarketingWebhookEvent", _rule_marketing_webhook_event)
register_rule("JournalEntry", _rule_journal_entry)
register_rule("JournalEntryItem", _rule_journal_entry_item)
register_rule("Invoice", _rule_invoice)
register_rule("InvoiceLine", _rule_invoice_line)
register_rule("PurchaseInvoice", _rule_purchase_invoice)
register_rule("BillLine", _rule_bill_line)
register_rule("CreditNote", _rule_credit_note)
register_rule("DebitNote", _rule_debit_note)
register_rule("Payment", _rule_payment)
register_rule("SupplierPayment", _rule_supplier_payment)
register_rule("PaymentAllocation", _rule_payment_allocation)
register_rule("BankTransaction", _rule_bank_transaction)
register_rule("BankTransactionPayment", _rule_bank_transaction_payment)
register_rule("BankReconciliation", _rule_bank_reconciliation)
register_rule("GLEntry", _rule_gl_entry)
register_rule("Account", _rule_account)
register_rule("ExchangeRate", _rule_exchange_rate)
register_rule("FiscalPeriod", _rule_fiscal_period)
register_rule("GatewayTransaction", _rule_gateway_transaction)
register_rule("PaymentSubscription", _rule_payment_subscription)
register_rule("TaxCode", _rule_tax_code)
register_rule("TaxCategory", _rule_tax_category)
register_rule("SalesTaxTemplate", _rule_sales_tax_template)
register_rule("SalesTaxTemplateDetail", _rule_sales_tax_template_detail)
register_rule("PurchaseTaxTemplate", _rule_purchase_tax_template)
register_rule("PurchaseTaxTemplateDetail", _rule_purchase_tax_template_detail)
register_rule("ItemTaxTemplate", _rule_item_tax_template)
register_rule("ItemTaxTemplateDetail", _rule_item_tax_template_detail)
register_rule("TaxWithholdingCategory", _rule_tax_withholding_category)
register_rule("TaxRule", _rule_tax_rule)
register_rule("TaxFilingPeriod", _rule_tax_filing_period)
register_rule("TaxPayment", _rule_tax_payment)
register_rule("AssetCategory", _rule_asset_category)
register_rule("AssetCategoryFinanceBook", _rule_asset_category_finance_book)
register_rule("Asset", _rule_asset)
register_rule("AssetFinanceBook", _rule_asset_finance_book)
register_rule("AssetDepreciationSchedule", _rule_asset_depreciation_schedule)
register_rule("AssetSettings", _rule_asset_settings)
register_rule("Item", _rule_item)
register_rule("ItemGroup", _rule_item_group)
register_rule("Warehouse", _rule_warehouse)
register_rule("StockEntry", _rule_stock_entry)
register_rule("StockEntryDetail", _rule_stock_entry_detail)
register_rule("StockLedgerEntry", _rule_stock_ledger_entry)
register_rule("LandedCostVoucher", _rule_landed_cost_voucher)
register_rule("LandedCostItem", _rule_landed_cost_item)
register_rule("LandedCostTax", _rule_landed_cost_tax)
register_rule("StockReceipt", _rule_stock_receipt)
register_rule("StockReceiptItem", _rule_stock_receipt_item)
register_rule("StockIssue", _rule_stock_issue)
register_rule("StockIssueItem", _rule_stock_issue_item)
register_rule("TransferRequest", _rule_transfer_request)
register_rule("TransferRequestItem", _rule_transfer_request_item)
register_rule("Batch", _rule_batch)
register_rule("SerialNumber", _rule_serial_number)
register_rule("BankTransactionSplit", _rule_bank_transaction_split)
register_rule("CreditNoteLine", _rule_credit_note_line)
register_rule("DebitNoteLine", _rule_debit_note_line)
register_rule("TaxSettings", _rule_tax_settings)
register_rule("NigerianTaxRate", _rule_nigerian_tax_rate)
register_rule("VATTransaction", _rule_vat_transaction)
register_rule("WHTTransaction", _rule_wht_transaction)
register_rule("WHTCertificate", _rule_wht_certificate)
register_rule("PAYECalculation", _rule_paye_calculation)
register_rule("CITAssessment", _rule_cit_assessment)
register_rule("EInvoice", _rule_einvoice)
register_rule("EInvoiceLine", _rule_einvoice_line)
