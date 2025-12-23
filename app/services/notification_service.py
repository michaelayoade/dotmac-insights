"""Notification and webhook dispatch service."""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from decimal import Decimal

import httpx
import structlog
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.notification import (
    WebhookConfig,
    WebhookDelivery,
    Notification,
    NotificationPreference,
    EmailQueue,
    NotificationEventType,
    NotificationStatus,
    NotificationChannel,
)
from app.models.agent import Team, TeamMember, Agent
from app.models.field_service import FieldTeam, FieldTeamMember
from app.models.employee import Employee, EmploymentStatus
from app.models.auth import User
from app.services.secrets_service import get_secrets, SecretsServiceError
from app.services.notification_templates import (
    NotificationTemplateRegistry,
    render_template,
)

logger = structlog.get_logger()


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class NotificationService:
    """Service for dispatching notifications across channels."""

    def __init__(self, db: Session):
        self.db = db
        self.http_client = httpx.Client(timeout=30.0)
        self.template_registry = NotificationTemplateRegistry()

    def emit_event(
        self,
        event_type: NotificationEventType,
        payload: Dict[str, Any],
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        user_ids: Optional[List[int]] = None,
        company: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Emit a notification event to all configured channels.

        Args:
            event_type: Type of event
            payload: Event data payload
            entity_type: Type of related entity (invoice, payment, etc.)
            entity_id: ID of related entity
            user_ids: Specific users to notify (for in-app notifications)
            company: Company filter for webhooks

        Returns:
            Summary of dispatch results
        """
        event_id = str(uuid.uuid4())
        errors: List[str] = []
        results: Dict[str, Any] = {
            "event_id": event_id,
            "event_type": event_type.value,
            "webhooks_queued": 0,
            "notifications_created": 0,
            "emails_queued": 0,
            "errors": errors,
        }

        logger.info(
            "notification_event_emitted",
            event_type=event_type.value,
            event_id=event_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )

        # 1. Queue webhooks
        try:
            webhook_count = self._queue_webhooks(
                event_type, event_id, payload, company
            )
            results["webhooks_queued"] = webhook_count
        except Exception as e:
            logger.error("webhook_queue_error", error=str(e))
            errors.append(f"Webhook error: {str(e)}")

        # 2. Create in-app notifications for specified users
        if user_ids:
            try:
                notif_count = self._create_in_app_notifications(
                    event_type, payload, entity_type, entity_id, user_ids
                )
                results["notifications_created"] = notif_count
            except Exception as e:
                logger.error("notification_create_error", error=str(e))
                errors.append(f"Notification error: {str(e)}")

        # 3. Queue emails based on user preferences
        if user_ids:
            try:
                email_count = self._queue_emails(
                    event_type, payload, entity_type, entity_id, user_ids
                )
                results["emails_queued"] = email_count
            except Exception as e:
                logger.error("email_queue_error", error=str(e))
                errors.append(f"Email error: {str(e)}")

        self.db.commit()
        return results

    def _queue_webhooks(
        self,
        event_type: NotificationEventType,
        event_id: str,
        payload: Dict[str, Any],
        company: Optional[str] = None,
        immediate: bool = True,
    ) -> int:
        """Queue webhook deliveries for active webhooks subscribed to this event.

        Args:
            event_type: Type of event
            event_id: Unique event ID
            payload: Event payload data
            company: Optional company filter
            immediate: If True, trigger Celery task for immediate delivery

        Returns:
            Number of webhooks queued
        """
        query = self.db.query(WebhookConfig).filter(
            and_(
                WebhookConfig.is_active == True,
                WebhookConfig.is_deleted == False,
            )
        )

        if company:
            query = query.filter(
                (WebhookConfig.company == company) | (WebhookConfig.company.is_(None))
            )

        webhooks = query.all()
        queued = 0
        delivery_ids = []

        for webhook in webhooks:
            # Check if webhook is subscribed to this event type
            if webhook.event_types and event_type.value not in webhook.event_types:
                continue

            # Check filters if any
            if webhook.filters:
                if not self._check_filters(webhook.filters, payload):
                    continue

            # Create delivery record
            delivery = WebhookDelivery(
                webhook_id=webhook.id,
                event_type=event_type.value,
                event_id=event_id,
                payload=payload,
                status=NotificationStatus.PENDING,
            )
            self.db.add(delivery)
            self.db.flush()  # Get the ID
            delivery_ids.append(delivery.id)
            queued += 1

            logger.debug(
                "webhook_delivery_queued",
                webhook_id=webhook.id,
                webhook_name=webhook.name,
                event_type=event_type.value,
            )

        # Trigger immediate delivery via Celery if requested
        if immediate and delivery_ids:
            dispatched_async = False
            try:
                from app.tasks.notification_tasks import deliver_single_webhook
                for delivery_id in delivery_ids:
                    deliver_single_webhook.delay(delivery_id)
                dispatched_async = True
            except Exception as e:
                # Don't fail the queue operation if Celery dispatch fails
                # The periodic task will pick up pending deliveries
                logger.warning(
                    "immediate_dispatch_failed",
                    error=str(e),
                    delivery_count=len(delivery_ids),
                )

            # Synchronous fallback so webhooks still fire even if Celery isn't running
            if not dispatched_async:
                for delivery_id in delivery_ids:
                    try:
                        self.deliver_webhook(delivery_id)
                    except Exception as sync_error:
                        logger.error(
                            "webhook_delivery_sync_failed",
                            delivery_id=delivery_id,
                            error=str(sync_error),
                        )

        return queued

    def _check_filters(self, filters: Dict[str, Any], payload: Dict[str, Any]) -> bool:
        """Check if payload matches webhook filters."""
        for key, allowed_values in filters.items():
            if key in payload:
                payload_value = payload[key]
                if isinstance(allowed_values, list):
                    if payload_value not in allowed_values:
                        return False
                elif payload_value != allowed_values:
                    return False
        return True

    def _create_in_app_notifications(
        self,
        event_type: NotificationEventType,
        payload: Dict[str, Any],
        entity_type: Optional[str],
        entity_id: Optional[int],
        user_ids: List[int],
    ) -> int:
        """Create in-app notifications for users based on preferences."""
        created = 0

        # Get notification template
        title, message, icon, priority = self._get_notification_template(event_type, payload)

        for user_id in user_ids:
            # Check user preference
            pref = self.db.query(NotificationPreference).filter(
                and_(
                    NotificationPreference.user_id == user_id,
                    NotificationPreference.event_type == event_type,
                )
            ).first()

            # Default to enabled if no preference set
            if pref and not pref.in_app_enabled:
                continue

            notification = Notification(
                user_id=user_id,
                event_type=event_type,
                title=title,
                message=message,
                icon=icon,
                entity_type=entity_type,
                entity_id=entity_id,
                action_url=self._build_action_url(entity_type, entity_id),
                extra_data=payload,
                priority=priority,
            )
            self.db.add(notification)
            created += 1

        return created

    def _queue_emails(
        self,
        event_type: NotificationEventType,
        payload: Dict[str, Any],
        entity_type: Optional[str],
        entity_id: Optional[int],
        user_ids: List[int],
    ) -> int:
        """Queue emails for users with email notifications enabled."""
        from app.models.auth import User

        queued = 0

        for user_id in user_ids:
            # Check preference
            pref = self.db.query(NotificationPreference).filter(
                and_(
                    NotificationPreference.user_id == user_id,
                    NotificationPreference.event_type == event_type,
                )
            ).first()

            # Default to enabled for important events
            important_events = {
                NotificationEventType.APPROVAL_REQUESTED,
                NotificationEventType.INVOICE_OVERDUE,
                NotificationEventType.TAX_OVERDUE,
                NotificationEventType.CREDIT_HOLD_APPLIED,
            }
            default_enabled = event_type in important_events

            if pref and not pref.email_enabled:
                continue
            if not pref and not default_enabled:
                continue

            # Get user email
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user or not user.email:
                continue

            subject, body_html, body_text = self._get_email_template(event_type, payload)

            email = EmailQueue(
                to_email=user.email,
                to_name=user.name,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                event_type=event_type.value,
                entity_type=entity_type,
                entity_id=entity_id,
                priority=self._get_email_priority(event_type),
            )
            self.db.add(email)
            queued += 1

        return queued

    def _get_notification_template(
        self, event_type: NotificationEventType, payload: Dict[str, Any]
    ) -> tuple[str, str, str, str]:
        """Get notification title, message, icon, and priority for event type."""
        template = self.template_registry.get_template(event_type)
        context = {**template.context, **payload}
        title = render_template(template.title, context)
        message = render_template(template.message, context)
        return title, message, template.icon, template.priority

    def _get_email_template(
        self, event_type: NotificationEventType, payload: Dict[str, Any]
    ) -> tuple[str, str, str]:
        """Get email subject, HTML body, and text body for event type.

        Args:
            event_type: The notification event type
            payload: Event data payload

        Returns:
            Tuple of (subject, html_body, text_body)
        """
        from app.templates.environment import get_template_env

        template = self.template_registry.get_template(event_type, payload)
        title = template.title
        message = template.message

        env = get_template_env()
        email_context = {
            **template.context,
            **payload,
            "title": title,
            "message": message,
        }

        html_template = env.get_template("emails/notification.html.j2")
        text_template = env.get_template("emails/notification.txt.j2")

        body_html = html_template.render(email_context)
        body_text = text_template.render(email_context)

        return f"[DotMac] {title}", body_html, body_text

    def _build_action_url(self, entity_type: Optional[str], entity_id: Optional[int]) -> Optional[str]:
        """Build URL to view the related entity."""
        if not entity_type or not entity_id:
            return None

        url_map = {
            "invoice": f"/accounting/invoices/{entity_id}",
            "payment": f"/accounting/payments/{entity_id}",
            "journal_entry": f"/accounting/journal-entries/{entity_id}",
            "expense": f"/accounting/expenses/{entity_id}",
            "customer": f"/customers/{entity_id}",
            "approval": f"/accounting/approvals/{entity_id}",
            "scorecard": f"/performance/scorecards/{entity_id}",
            "evaluation_period": f"/performance/periods/{entity_id}",
            "performance_review": f"/performance/reviews/{entity_id}",
        }
        return url_map.get(entity_type)

    def _get_email_priority(self, event_type: NotificationEventType) -> int:
        """Get email priority (1=highest, 10=lowest)."""
        urgent_events = {
            NotificationEventType.CREDIT_HOLD_APPLIED,
            NotificationEventType.TAX_OVERDUE,
        }
        high_events = {
            NotificationEventType.APPROVAL_REQUESTED,
            NotificationEventType.INVOICE_OVERDUE,
            NotificationEventType.APPROVAL_REJECTED,
            NotificationEventType.PERF_REVIEW_REQUESTED,
            NotificationEventType.PERF_SCORECARD_FINALIZED,
            NotificationEventType.PERF_PERIOD_CLOSING,
            NotificationEventType.PERF_REVIEW_REMINDER,
        }

        if event_type in urgent_events:
            return 1
        if event_type in high_events:
            return 3
        return 5

    def deliver_webhook(self, delivery_id: int) -> bool:
        """
        Attempt to deliver a webhook.

        Returns True if successful, False otherwise.
        """
        delivery = self.db.query(WebhookDelivery).filter(
            WebhookDelivery.id == delivery_id
        ).first()

        if not delivery:
            return False

        webhook = delivery.webhook
        if not webhook or not webhook.is_active:
            delivery.status = NotificationStatus.FAILED
            delivery.error_message = "Webhook not found or inactive"
            self.db.commit()
            return False

        delivery.attempt_count += 1
        delivery.last_attempt_at = datetime.utcnow()

        try:
            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Event": delivery.event_type,
                "X-Webhook-ID": delivery.event_id,
                "X-Webhook-Timestamp": str(int(datetime.utcnow().timestamp())),
            }

            # Add custom headers
            if webhook.custom_headers:
                headers.update(webhook.custom_headers)

            # Add authentication (decrypt auth value)
            if webhook.auth_value_encrypted:
                try:
                    secrets_service = get_secrets()
                    decrypted_auth_value = secrets_service.decrypt(webhook.auth_value_encrypted)
                except SecretsServiceError as e:
                    logger.error(
                        "webhook_auth_decryption_failed",
                        webhook_id=webhook.id,
                        error=str(e),
                    )
                    raise ValueError(f"Failed to decrypt webhook credentials: {e}")

                if webhook.auth_type == "bearer":
                    headers["Authorization"] = f"Bearer {decrypted_auth_value}"
                elif webhook.auth_type == "api_key" and webhook.auth_header:
                    headers[webhook.auth_header] = decrypted_auth_value
                elif webhook.auth_type == "basic":
                    headers["Authorization"] = f"Basic {decrypted_auth_value}"

            # Add signature if secret configured
            payload_json = json.dumps(delivery.payload, cls=DecimalEncoder)
            if webhook.signing_secret:
                signature = hmac.new(
                    webhook.signing_secret.encode(),
                    payload_json.encode(),
                    hashlib.sha256
                ).hexdigest()
                headers["X-Webhook-Signature"] = f"sha256={signature}"

            # Make request
            start_time = datetime.utcnow()
            response = self.http_client.request(
                method=webhook.method,
                url=webhook.url,
                headers=headers,
                content=payload_json,
            )
            end_time = datetime.utcnow()

            delivery.response_status_code = response.status_code
            delivery.response_body = response.text[:2000] if response.text else None
            delivery.response_time_ms = int((end_time - start_time).total_seconds() * 1000)

            if 200 <= response.status_code < 300:
                delivery.status = NotificationStatus.DELIVERED
                delivery.delivered_at = datetime.utcnow()
                webhook.success_count += 1
                webhook.last_triggered_at = datetime.utcnow()

                logger.info(
                    "webhook_delivered",
                    webhook_id=webhook.id,
                    delivery_id=delivery.id,
                    status_code=response.status_code,
                )
                self.db.commit()
                return True
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")

        except Exception as e:
            delivery.error_message = str(e)[:1000]
            webhook.failure_count += 1

            # Schedule retry if attempts remaining
            if delivery.attempt_count < webhook.max_retries:
                delivery.status = NotificationStatus.PENDING
                delivery.next_retry_at = datetime.utcnow() + timedelta(
                    seconds=webhook.retry_delay_seconds * delivery.attempt_count
                )
            else:
                delivery.status = NotificationStatus.FAILED

            logger.warning(
                "webhook_delivery_failed",
                webhook_id=webhook.id,
                delivery_id=delivery.id,
                attempt=delivery.attempt_count,
                error=str(e),
            )

            self.db.commit()
            return False

    def get_pending_deliveries(self, limit: int = 100) -> List[WebhookDelivery]:
        """Get webhook deliveries ready for (re)delivery."""
        now = datetime.utcnow()
        return self.db.query(WebhookDelivery).filter(
            and_(
                WebhookDelivery.status == NotificationStatus.PENDING,
                (WebhookDelivery.next_retry_at.is_(None)) | (WebhookDelivery.next_retry_at <= now),
            )
        ).order_by(WebhookDelivery.created_at).limit(limit).all()

    def mark_notification_read(self, notification_id: int, user_id: int) -> bool:
        """Mark an in-app notification as read."""
        notification = self.db.query(Notification).filter(
            and_(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        ).first()

        if not notification:
            return False

        notification.is_read = True
        notification.read_at = datetime.utcnow()
        self.db.commit()
        return True

    def get_user_notifications(
        self,
        user_id: int,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Notification]:
        """Get notifications for a user."""
        query = self.db.query(Notification).filter(Notification.user_id == user_id)

        if unread_only:
            query = query.filter(Notification.is_read == False)

        return query.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()

    def get_unread_count(self, user_id: int) -> int:
        """Get count of unread notifications for a user."""
        return self.db.query(Notification).filter(
            and_(
                Notification.user_id == user_id,
                Notification.is_read == False,
            )
        ).count()

    # =========================================================================
    # TEAM NOTIFICATIONS
    # =========================================================================

    def _get_user_ids_from_emails(self, emails: List[str]) -> List[int]:
        """Get user IDs by matching email addresses."""
        normalized_emails = {
            email.strip().lower()
            for email in emails
            if email and email.strip()
        }
        if not normalized_emails:
            return []
        users = self.db.query(User).filter(
            func.lower(User.email).in_(normalized_emails),
            User.is_active == True,
        ).all()
        return [u.id for u in users]

    def get_team_user_ids(self, team_id: int) -> List[int]:
        """Get user IDs for all active members of an agent/support team.

        Resolves: Team → TeamMember → Agent → Employee → User (via email match)
        """
        emails = (
            self.db.query(Employee.email)
            .join(Agent, Agent.employee_id == Employee.id)
            .join(TeamMember, TeamMember.agent_id == Agent.id)
            .join(Team, Team.id == TeamMember.team_id)
            .filter(
                TeamMember.team_id == team_id,
                TeamMember.is_active == True,
                Agent.is_active == True,
                Team.is_active == True,
                Employee.status == EmploymentStatus.ACTIVE,
                Employee.is_deleted == False,
                Employee.email.isnot(None),
            )
            .distinct()
            .all()
        )

        return self._get_user_ids_from_emails([email for (email,) in emails])

    def get_field_team_user_ids(self, team_id: int) -> List[int]:
        """Get user IDs for all active members of a field service team.

        Resolves: FieldTeam → FieldTeamMember → Employee → User (via email match)
        """
        emails = (
            self.db.query(Employee.email)
            .join(FieldTeamMember, FieldTeamMember.employee_id == Employee.id)
            .join(FieldTeam, FieldTeam.id == FieldTeamMember.team_id)
            .filter(
                FieldTeamMember.team_id == team_id,
                FieldTeamMember.is_active == True,
                FieldTeam.is_active == True,
                Employee.status == EmploymentStatus.ACTIVE,
                Employee.is_deleted == False,
                Employee.email.isnot(None),
            )
            .distinct()
            .all()
        )

        return self._get_user_ids_from_emails([email for (email,) in emails])

    def notify_team(
        self,
        team_id: int,
        event_type: NotificationEventType,
        payload: Dict[str, Any],
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        company: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send notifications to all members of an agent/support team.

        Args:
            team_id: ID of the Team (agent teams from agent.py)
            event_type: Type of notification event
            payload: Event data payload
            entity_type: Type of related entity
            entity_id: ID of related entity
            company: Company filter for webhooks

        Returns:
            Summary of dispatch results with team info
        """
        team = self.db.query(Team).filter(Team.id == team_id).first()
        if not team:
            return {
                "error": "Team not found",
                "team_id": team_id,
            }
        if not team.is_active:
            return {
                "error": "Team is inactive",
                "team_id": team_id,
                "team_name": team.name,
            }

        user_ids = self.get_team_user_ids(team_id)

        logger.info(
            "notify_team",
            team_id=team_id,
            team_name=team.name,
            user_count=len(user_ids),
            event_type=event_type.value,
        )

        if not user_ids:
            return {
                "team_id": team_id,
                "team_name": team.name,
                "user_count": 0,
                "message": "No active users found for team",
            }

        result = self.emit_event(
            event_type=event_type,
            payload=payload,
            entity_type=entity_type,
            entity_id=entity_id,
            user_ids=user_ids,
            company=company,
        )

        result["team_id"] = team_id
        result["team_name"] = team.name
        result["user_count"] = len(user_ids)

        return result

    def notify_field_team(
        self,
        team_id: int,
        event_type: NotificationEventType,
        payload: Dict[str, Any],
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        company: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send notifications to all members of a field service team.

        Args:
            team_id: ID of the FieldTeam
            event_type: Type of notification event
            payload: Event data payload
            entity_type: Type of related entity
            entity_id: ID of related entity
            company: Company filter for webhooks

        Returns:
            Summary of dispatch results with team info
        """
        team = self.db.query(FieldTeam).filter(FieldTeam.id == team_id).first()
        if not team:
            return {
                "error": "Field team not found",
                "team_id": team_id,
            }
        if not team.is_active:
            return {
                "error": "Field team is inactive",
                "team_id": team_id,
                "team_name": team.name,
            }

        user_ids = self.get_field_team_user_ids(team_id)

        logger.info(
            "notify_field_team",
            team_id=team_id,
            team_name=team.name,
            user_count=len(user_ids),
            event_type=event_type.value,
        )

        if not user_ids:
            return {
                "team_id": team_id,
                "team_name": team.name,
                "user_count": 0,
                "message": "No active users found for field team",
            }

        result = self.emit_event(
            event_type=event_type,
            payload=payload,
            entity_type=entity_type,
            entity_id=entity_id,
            user_ids=user_ids,
            company=company,
        )

        result["team_id"] = team_id
        result["team_name"] = team.name
        result["user_count"] = len(user_ids)

        return result

    def notify_teams(
        self,
        team_ids: List[int],
        event_type: NotificationEventType,
        payload: Dict[str, Any],
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        company: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send notifications to multiple agent/support teams.

        Deduplicates users who are members of multiple teams.

        Args:
            team_ids: List of Team IDs
            event_type: Type of notification event
            payload: Event data payload
            entity_type: Type of related entity
            entity_id: ID of related entity
            company: Company filter for webhooks

        Returns:
            Summary of dispatch results
        """
        all_user_ids = set()
        team_names = []

        for team_id in team_ids:
            team = self.db.query(Team).filter(Team.id == team_id).first()
            if not team:
                logger.info("notify_teams_missing_team", team_id=team_id)
                continue
            if not team.is_active:
                logger.info("notify_teams_inactive_team", team_id=team_id, team_name=team.name)
                continue
            team_names.append(team.name)
            user_ids = self.get_team_user_ids(team_id)
            all_user_ids.update(user_ids)

        user_ids_list = list(all_user_ids)

        logger.info(
            "notify_teams",
            team_ids=team_ids,
            team_names=team_names,
            user_count=len(user_ids_list),
            event_type=event_type.value,
        )

        if not user_ids_list:
            return {
                "team_ids": team_ids,
                "team_names": team_names,
                "user_count": 0,
                "message": "No active users found for teams",
            }

        result = self.emit_event(
            event_type=event_type,
            payload=payload,
            entity_type=entity_type,
            entity_id=entity_id,
            user_ids=user_ids_list,
            company=company,
        )

        result["team_ids"] = team_ids
        result["team_names"] = team_names
        result["user_count"] = len(user_ids_list)

        return result
