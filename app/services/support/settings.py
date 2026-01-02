"""Settings service - business logic for company-wide support settings.

This service handles support configuration management:
- Get/update company-wide support settings
- Business hours management
- SLA defaults
- Routing configuration
- Notification preferences

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.support_settings import (
    SupportSettings,
    WorkingHoursType,
    DefaultRoutingStrategy,
    TicketPriorityDefault,
    TicketAutoCloseAction,
    CSATSurveyTrigger,
)

from .types import SupportSettingsUpdate
from .errors import SettingsNotFoundError

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["SettingsService"]


class SettingsService:
    """Service for support settings management.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def get(self, company: Optional[str] = None) -> SupportSettings:
        """Get support settings for a company.

        Creates default settings if none exist.

        Args:
            company: The company identifier (None for default).

        Returns:
            SupportSettings instance.
        """
        settings = (
            self.db.query(SupportSettings)
            .filter(SupportSettings.company == company)
            .first()
        )

        if not settings:
            # Create default settings
            settings = self._create_default_settings(company)

        return settings

    def get_by_id(self, settings_id: int) -> SupportSettings:
        """Get settings by ID.

        Args:
            settings_id: The settings ID.

        Returns:
            SupportSettings instance.

        Raises:
            SettingsNotFoundError: If not found.
        """
        settings = (
            self.db.query(SupportSettings)
            .filter(SupportSettings.id == settings_id)
            .first()
        )
        if not settings:
            raise SettingsNotFoundError(settings_id)
        return settings

    def exists(self, company: Optional[str] = None) -> bool:
        """Check if settings exist for a company.

        Args:
            company: The company identifier.

        Returns:
            True if settings exist.
        """
        return (
            self.db.query(SupportSettings)
            .filter(SupportSettings.company == company)
            .count() > 0
        )

    def get_all(self, company: Optional[str] = None) -> Dict[str, Any]:
        """Get all support settings as a dictionary.

        This returns every configurable setting organized by category.

        Args:
            company: The company identifier.

        Returns:
            Dict with all settings grouped by category.
        """
        settings = self.get(company)
        return {
            "id": settings.id,
            "company": settings.company,
            "business_hours": {
                "working_hours_type": settings.working_hours_type.value,
                "timezone": settings.timezone,
                "weekly_schedule": settings.weekly_schedule,
                "holiday_calendar_id": settings.holiday_calendar_id,
            },
            "sla_defaults": {
                "default_sla_policy_id": settings.default_sla_policy_id,
                "sla_warning_threshold_percent": settings.sla_warning_threshold_percent,
                "sla_include_holidays": settings.sla_include_holidays,
                "sla_include_weekends": settings.sla_include_weekends,
                "default_first_response_hours": float(settings.default_first_response_hours),
                "default_resolution_hours": float(settings.default_resolution_hours),
            },
            "routing": {
                "default_routing_strategy": settings.default_routing_strategy.value,
                "default_team_id": settings.default_team_id,
                "fallback_team_id": settings.fallback_team_id,
                "auto_assign_enabled": settings.auto_assign_enabled,
                "max_tickets_per_agent": settings.max_tickets_per_agent,
                "rebalance_threshold_percent": settings.rebalance_threshold_percent,
            },
            "ticket_defaults": {
                "default_priority": settings.default_priority.value,
                "default_ticket_type": settings.default_ticket_type,
                "allow_customer_priority_selection": settings.allow_customer_priority_selection,
                "allow_customer_team_selection": settings.allow_customer_team_selection,
            },
            "auto_close": {
                "auto_close_enabled": settings.auto_close_enabled,
                "auto_close_resolved_days": settings.auto_close_resolved_days,
                "auto_close_action": settings.auto_close_action.value,
                "auto_close_notify_customer": settings.auto_close_notify_customer,
                "allow_customer_reopen": settings.allow_customer_reopen,
                "reopen_window_days": settings.reopen_window_days,
                "max_reopens_allowed": settings.max_reopens_allowed,
            },
            "escalation": {
                "escalation_enabled": settings.escalation_enabled,
                "default_escalation_team_id": settings.default_escalation_team_id,
                "escalation_notify_manager": settings.escalation_notify_manager,
                "idle_escalation_enabled": settings.idle_escalation_enabled,
                "idle_hours_before_escalation": settings.idle_hours_before_escalation,
                "reopen_escalation_enabled": settings.reopen_escalation_enabled,
                "reopen_count_for_escalation": settings.reopen_count_for_escalation,
            },
            "csat": {
                "csat_enabled": settings.csat_enabled,
                "csat_survey_trigger": settings.csat_survey_trigger.value,
                "csat_delay_hours": settings.csat_delay_hours,
                "csat_reminder_enabled": settings.csat_reminder_enabled,
                "csat_reminder_days": settings.csat_reminder_days,
                "csat_survey_expiry_days": settings.csat_survey_expiry_days,
                "default_csat_survey_id": settings.default_csat_survey_id,
            },
            "portal": {
                "portal_enabled": settings.portal_enabled,
                "portal_ticket_creation_enabled": settings.portal_ticket_creation_enabled,
                "portal_show_ticket_history": settings.portal_show_ticket_history,
                "portal_show_knowledge_base": settings.portal_show_knowledge_base,
                "portal_show_faq": settings.portal_show_faq,
                "portal_require_login": settings.portal_require_login,
            },
            "knowledge_base": {
                "kb_enabled": settings.kb_enabled,
                "kb_public_access": settings.kb_public_access,
                "kb_suggest_articles_on_create": settings.kb_suggest_articles_on_create,
                "kb_track_article_helpfulness": settings.kb_track_article_helpfulness,
            },
            "notifications": {
                "notification_channels": settings.notification_channels,
                "notification_events": settings.notification_events,
                "notify_assigned_agent": settings.notify_assigned_agent,
                "notify_team_on_unassigned": settings.notify_team_on_unassigned,
                "notify_customer_on_status_change": settings.notify_customer_on_status_change,
                "notify_customer_on_reply": settings.notify_customer_on_reply,
            },
            "queue_management": {
                "unassigned_warning_minutes": settings.unassigned_warning_minutes,
                "overdue_highlight_enabled": settings.overdue_highlight_enabled,
                "queue_refresh_seconds": settings.queue_refresh_seconds,
            },
            "integrations": {
                "email_to_ticket_enabled": settings.email_to_ticket_enabled,
                "email_reply_to_address": settings.email_reply_to_address,
                "sync_to_erpnext": settings.sync_to_erpnext,
                "sync_to_splynx": settings.sync_to_splynx,
                "sync_to_chatwoot": settings.sync_to_chatwoot,
            },
            "data_retention": {
                "archive_closed_tickets_days": settings.archive_closed_tickets_days,
                "delete_archived_tickets_days": settings.delete_archived_tickets_days,
            },
            "display": {
                "ticket_id_prefix": settings.ticket_id_prefix,
                "ticket_id_min_digits": settings.ticket_id_min_digits,
                "date_format": settings.date_format,
                "time_format": settings.time_format,
            },
            "updated_at": settings.updated_at.isoformat() if settings.updated_at else None,
            "updated_by_id": settings.updated_by_id,
        }

    # -------------------------------------------------------------------------
    # Mutations
    # -------------------------------------------------------------------------

    def update(
        self,
        data: SupportSettingsUpdate,
        company: Optional[str] = None,
    ) -> SupportSettings:
        """Update support settings.

        All fields are optional - only provided fields are updated.

        Args:
            data: Update data with any combination of settings fields.
            company: The company identifier.

        Returns:
            Updated SupportSettings instance.
        """
        settings = self.get(company)

        # -------------------------------------------------------------------------
        # Business Hours
        # -------------------------------------------------------------------------
        if data.working_hours_type is not None:
            settings.working_hours_type = WorkingHoursType(data.working_hours_type)

        if data.timezone is not None:
            settings.timezone = data.timezone

        if data.weekly_schedule is not None:
            settings.weekly_schedule = data.weekly_schedule

        if data.holiday_calendar_id is not None:
            settings.holiday_calendar_id = data.holiday_calendar_id

        # -------------------------------------------------------------------------
        # SLA Defaults
        # -------------------------------------------------------------------------
        if data.default_sla_policy_id is not None:
            settings.default_sla_policy_id = data.default_sla_policy_id

        if data.sla_warning_threshold_percent is not None:
            settings.sla_warning_threshold_percent = data.sla_warning_threshold_percent

        if data.sla_include_holidays is not None:
            settings.sla_include_holidays = data.sla_include_holidays

        if data.sla_include_weekends is not None:
            settings.sla_include_weekends = data.sla_include_weekends

        if data.default_first_response_hours is not None:
            settings.default_first_response_hours = Decimal(str(data.default_first_response_hours))

        if data.default_resolution_hours is not None:
            settings.default_resolution_hours = Decimal(str(data.default_resolution_hours))

        # -------------------------------------------------------------------------
        # Ticket Routing
        # -------------------------------------------------------------------------
        if data.default_routing_strategy is not None:
            settings.default_routing_strategy = DefaultRoutingStrategy(data.default_routing_strategy)

        if data.default_team_id is not None:
            settings.default_team_id = data.default_team_id

        if data.fallback_team_id is not None:
            settings.fallback_team_id = data.fallback_team_id

        if data.auto_assign_enabled is not None:
            settings.auto_assign_enabled = data.auto_assign_enabled

        if data.max_tickets_per_agent is not None:
            settings.max_tickets_per_agent = data.max_tickets_per_agent

        if data.rebalance_threshold_percent is not None:
            settings.rebalance_threshold_percent = data.rebalance_threshold_percent

        # -------------------------------------------------------------------------
        # Ticket Defaults
        # -------------------------------------------------------------------------
        if data.default_priority is not None:
            settings.default_priority = TicketPriorityDefault(data.default_priority)

        if data.default_ticket_type is not None:
            settings.default_ticket_type = data.default_ticket_type

        if data.allow_customer_priority_selection is not None:
            settings.allow_customer_priority_selection = data.allow_customer_priority_selection

        if data.allow_customer_team_selection is not None:
            settings.allow_customer_team_selection = data.allow_customer_team_selection

        # -------------------------------------------------------------------------
        # Auto-Close Settings
        # -------------------------------------------------------------------------
        if data.auto_close_enabled is not None:
            settings.auto_close_enabled = data.auto_close_enabled

        if data.auto_close_resolved_days is not None:
            settings.auto_close_resolved_days = data.auto_close_resolved_days

        if data.auto_close_action is not None:
            settings.auto_close_action = TicketAutoCloseAction(data.auto_close_action)

        if data.auto_close_notify_customer is not None:
            settings.auto_close_notify_customer = data.auto_close_notify_customer

        if data.allow_customer_reopen is not None:
            settings.allow_customer_reopen = data.allow_customer_reopen

        if data.reopen_window_days is not None:
            settings.reopen_window_days = data.reopen_window_days

        if data.max_reopens_allowed is not None:
            settings.max_reopens_allowed = data.max_reopens_allowed

        # -------------------------------------------------------------------------
        # Escalation Defaults
        # -------------------------------------------------------------------------
        if data.escalation_enabled is not None:
            settings.escalation_enabled = data.escalation_enabled

        if data.default_escalation_team_id is not None:
            settings.default_escalation_team_id = data.default_escalation_team_id

        if data.escalation_notify_manager is not None:
            settings.escalation_notify_manager = data.escalation_notify_manager

        if data.idle_escalation_enabled is not None:
            settings.idle_escalation_enabled = data.idle_escalation_enabled

        if data.idle_hours_before_escalation is not None:
            settings.idle_hours_before_escalation = data.idle_hours_before_escalation

        if data.reopen_escalation_enabled is not None:
            settings.reopen_escalation_enabled = data.reopen_escalation_enabled

        if data.reopen_count_for_escalation is not None:
            settings.reopen_count_for_escalation = data.reopen_count_for_escalation

        # -------------------------------------------------------------------------
        # CSAT / Customer Feedback
        # -------------------------------------------------------------------------
        if data.csat_enabled is not None:
            settings.csat_enabled = data.csat_enabled

        if data.csat_survey_trigger is not None:
            settings.csat_survey_trigger = CSATSurveyTrigger(data.csat_survey_trigger)

        if data.csat_delay_hours is not None:
            settings.csat_delay_hours = data.csat_delay_hours

        if data.csat_reminder_enabled is not None:
            settings.csat_reminder_enabled = data.csat_reminder_enabled

        if data.csat_reminder_days is not None:
            settings.csat_reminder_days = data.csat_reminder_days

        if data.csat_survey_expiry_days is not None:
            settings.csat_survey_expiry_days = data.csat_survey_expiry_days

        if data.default_csat_survey_id is not None:
            settings.default_csat_survey_id = data.default_csat_survey_id

        # -------------------------------------------------------------------------
        # Customer Portal
        # -------------------------------------------------------------------------
        if data.portal_enabled is not None:
            settings.portal_enabled = data.portal_enabled

        if data.portal_ticket_creation_enabled is not None:
            settings.portal_ticket_creation_enabled = data.portal_ticket_creation_enabled

        if data.portal_show_ticket_history is not None:
            settings.portal_show_ticket_history = data.portal_show_ticket_history

        if data.portal_show_knowledge_base is not None:
            settings.portal_show_knowledge_base = data.portal_show_knowledge_base

        if data.portal_show_faq is not None:
            settings.portal_show_faq = data.portal_show_faq

        if data.portal_require_login is not None:
            settings.portal_require_login = data.portal_require_login

        # -------------------------------------------------------------------------
        # Knowledge Base
        # -------------------------------------------------------------------------
        if data.kb_enabled is not None:
            settings.kb_enabled = data.kb_enabled

        if data.kb_public_access is not None:
            settings.kb_public_access = data.kb_public_access

        if data.kb_suggest_articles_on_create is not None:
            settings.kb_suggest_articles_on_create = data.kb_suggest_articles_on_create

        if data.kb_track_article_helpfulness is not None:
            settings.kb_track_article_helpfulness = data.kb_track_article_helpfulness

        # -------------------------------------------------------------------------
        # Notifications
        # -------------------------------------------------------------------------
        if data.notification_channels is not None:
            settings.notification_channels = data.notification_channels

        if data.notification_events is not None:
            settings.notification_events = data.notification_events

        if data.notify_assigned_agent is not None:
            settings.notify_assigned_agent = data.notify_assigned_agent

        if data.notify_team_on_unassigned is not None:
            settings.notify_team_on_unassigned = data.notify_team_on_unassigned

        if data.notify_customer_on_status_change is not None:
            settings.notify_customer_on_status_change = data.notify_customer_on_status_change

        if data.notify_customer_on_reply is not None:
            settings.notify_customer_on_reply = data.notify_customer_on_reply

        # -------------------------------------------------------------------------
        # Queue Management
        # -------------------------------------------------------------------------
        if data.unassigned_warning_minutes is not None:
            settings.unassigned_warning_minutes = data.unassigned_warning_minutes

        if data.overdue_highlight_enabled is not None:
            settings.overdue_highlight_enabled = data.overdue_highlight_enabled

        if data.queue_refresh_seconds is not None:
            settings.queue_refresh_seconds = data.queue_refresh_seconds

        # -------------------------------------------------------------------------
        # Integrations
        # -------------------------------------------------------------------------
        if data.email_to_ticket_enabled is not None:
            settings.email_to_ticket_enabled = data.email_to_ticket_enabled

        if data.email_reply_to_address is not None:
            settings.email_reply_to_address = data.email_reply_to_address

        if data.sync_to_erpnext is not None:
            settings.sync_to_erpnext = data.sync_to_erpnext

        if data.sync_to_splynx is not None:
            settings.sync_to_splynx = data.sync_to_splynx

        if data.sync_to_chatwoot is not None:
            settings.sync_to_chatwoot = data.sync_to_chatwoot

        # -------------------------------------------------------------------------
        # Data Retention
        # -------------------------------------------------------------------------
        if data.archive_closed_tickets_days is not None:
            settings.archive_closed_tickets_days = data.archive_closed_tickets_days

        if data.delete_archived_tickets_days is not None:
            settings.delete_archived_tickets_days = data.delete_archived_tickets_days

        # -------------------------------------------------------------------------
        # Display & Formatting
        # -------------------------------------------------------------------------
        if data.ticket_id_prefix is not None:
            settings.ticket_id_prefix = data.ticket_id_prefix

        if data.ticket_id_min_digits is not None:
            settings.ticket_id_min_digits = data.ticket_id_min_digits

        if data.date_format is not None:
            settings.date_format = data.date_format

        if data.time_format is not None:
            settings.time_format = data.time_format

        # -------------------------------------------------------------------------
        # Audit
        # -------------------------------------------------------------------------
        if self.principal:
            settings.updated_by_id = getattr(self.principal, "id", None)

        self.db.flush()
        return settings

    def _create_default_settings(self, company: Optional[str] = None) -> SupportSettings:
        """Create default settings for a company.

        Args:
            company: The company identifier.

        Returns:
            New SupportSettings instance.
        """
        settings = SupportSettings(company=company)
        self.db.add(settings)
        self.db.flush()
        return settings

    # -------------------------------------------------------------------------
    # Business Hours
    # -------------------------------------------------------------------------

    def get_business_hours(self, company: Optional[str] = None) -> Dict[str, Any]:
        """Get business hours configuration.

        Args:
            company: The company identifier.

        Returns:
            Dict with working_hours_type, timezone, and weekly_schedule.
        """
        settings = self.get(company)
        return {
            "working_hours_type": settings.working_hours_type.value,
            "timezone": settings.timezone,
            "weekly_schedule": settings.weekly_schedule,
            "holiday_calendar_id": settings.holiday_calendar_id,
        }

    def update_business_hours(
        self,
        working_hours_type: Optional[str] = None,
        timezone: Optional[str] = None,
        weekly_schedule: Optional[Dict[str, Any]] = None,
        holiday_calendar_id: Optional[int] = None,
        company: Optional[str] = None,
    ) -> SupportSettings:
        """Update business hours configuration.

        Args:
            working_hours_type: Type of working hours.
            timezone: Timezone string.
            weekly_schedule: Weekly schedule dict.
            holiday_calendar_id: Holiday calendar reference.
            company: The company identifier.

        Returns:
            Updated SupportSettings instance.
        """
        settings = self.get(company)

        if working_hours_type is not None:
            settings.working_hours_type = WorkingHoursType(working_hours_type)

        if timezone is not None:
            settings.timezone = timezone

        if weekly_schedule is not None:
            settings.weekly_schedule = weekly_schedule

        if holiday_calendar_id is not None:
            settings.holiday_calendar_id = holiday_calendar_id

        if self.principal:
            settings.updated_by_id = getattr(self.principal, "id", None)

        self.db.flush()
        return settings

    def is_within_business_hours(
        self,
        dt: Optional[datetime] = None,
        company: Optional[str] = None,
    ) -> bool:
        """Check if a datetime falls within business hours.

        Args:
            dt: The datetime to check (defaults to now).
            company: The company identifier.

        Returns:
            True if within business hours.
        """
        settings = self.get(company)

        if settings.working_hours_type == WorkingHoursType.ROUND_THE_CLOCK:
            return True

        if dt is None:
            dt = datetime.now(timezone.utc)

        # Get the day of week
        day_name = dt.strftime("%A").upper()
        schedule = settings.weekly_schedule.get(day_name, {})

        if schedule.get("closed", True):
            return False

        # Parse start and end times
        try:
            start_str = schedule.get("start", "00:00")
            end_str = schedule.get("end", "00:00")

            start_hour, start_min = map(int, start_str.split(":"))
            end_hour, end_min = map(int, end_str.split(":"))

            current_minutes = dt.hour * 60 + dt.minute
            start_minutes = start_hour * 60 + start_min
            end_minutes = end_hour * 60 + end_min

            return start_minutes <= current_minutes <= end_minutes
        except (ValueError, AttributeError):
            return False

    # -------------------------------------------------------------------------
    # SLA Defaults
    # -------------------------------------------------------------------------

    def get_sla_defaults(self, company: Optional[str] = None) -> Dict[str, Any]:
        """Get SLA default configuration.

        Args:
            company: The company identifier.

        Returns:
            Dict with SLA default settings.
        """
        settings = self.get(company)
        return {
            "default_sla_policy_id": settings.default_sla_policy_id,
            "sla_warning_threshold_percent": settings.sla_warning_threshold_percent,
            "sla_include_holidays": settings.sla_include_holidays,
            "sla_include_weekends": settings.sla_include_weekends,
            "default_first_response_hours": float(settings.default_first_response_hours),
            "default_resolution_hours": float(settings.default_resolution_hours),
        }

    # -------------------------------------------------------------------------
    # Routing Defaults
    # -------------------------------------------------------------------------

    def get_routing_config(self, company: Optional[str] = None) -> Dict[str, Any]:
        """Get routing configuration.

        Args:
            company: The company identifier.

        Returns:
            Dict with routing settings.
        """
        settings = self.get(company)
        return {
            "default_routing_strategy": settings.default_routing_strategy.value,
            "default_team_id": settings.default_team_id,
            "fallback_team_id": settings.fallback_team_id,
            "auto_assign_enabled": settings.auto_assign_enabled,
            "max_tickets_per_agent": settings.max_tickets_per_agent,
            "rebalance_threshold_percent": settings.rebalance_threshold_percent,
        }

    # -------------------------------------------------------------------------
    # Notification Config
    # -------------------------------------------------------------------------

    def get_notification_config(self, company: Optional[str] = None) -> Dict[str, Any]:
        """Get notification configuration.

        Args:
            company: The company identifier.

        Returns:
            Dict with notification settings.
        """
        settings = self.get(company)
        return {
            "notification_channels": settings.notification_channels,
            "notification_events": settings.notification_events,
            "notify_assigned_agent": settings.notify_assigned_agent,
            "notify_team_on_unassigned": settings.notify_team_on_unassigned,
            "notify_customer_on_status_change": settings.notify_customer_on_status_change,
            "notify_customer_on_reply": settings.notify_customer_on_reply,
        }

    def is_event_notification_enabled(
        self,
        event: str,
        company: Optional[str] = None,
    ) -> bool:
        """Check if notifications are enabled for an event.

        Args:
            event: The event name (e.g., 'ticket_created').
            company: The company identifier.

        Returns:
            True if notifications enabled for this event.
        """
        settings = self.get(company)
        events = settings.notification_events or {}
        return events.get(event, False)

    # -------------------------------------------------------------------------
    # Auto-Close Config
    # -------------------------------------------------------------------------

    def get_auto_close_config(self, company: Optional[str] = None) -> Dict[str, Any]:
        """Get auto-close configuration.

        Args:
            company: The company identifier.

        Returns:
            Dict with auto-close settings.
        """
        settings = self.get(company)
        return {
            "auto_close_enabled": settings.auto_close_enabled,
            "auto_close_resolved_days": settings.auto_close_resolved_days,
            "auto_close_action": settings.auto_close_action.value,
            "auto_close_notify_customer": settings.auto_close_notify_customer,
            "allow_customer_reopen": settings.allow_customer_reopen,
            "reopen_window_days": settings.reopen_window_days,
            "max_reopens_allowed": settings.max_reopens_allowed,
        }

    # -------------------------------------------------------------------------
    # CSAT Config
    # -------------------------------------------------------------------------

    def get_csat_config(self, company: Optional[str] = None) -> Dict[str, Any]:
        """Get CSAT configuration.

        Args:
            company: The company identifier.

        Returns:
            Dict with CSAT settings.
        """
        settings = self.get(company)
        return {
            "csat_enabled": settings.csat_enabled,
            "csat_survey_trigger": settings.csat_survey_trigger.value,
            "csat_delay_hours": settings.csat_delay_hours,
            "csat_reminder_enabled": settings.csat_reminder_enabled,
            "csat_reminder_days": settings.csat_reminder_days,
            "csat_survey_expiry_days": settings.csat_survey_expiry_days,
            "default_csat_survey_id": settings.default_csat_survey_id,
        }

    # -------------------------------------------------------------------------
    # Portal Config
    # -------------------------------------------------------------------------

    def get_portal_config(self, company: Optional[str] = None) -> Dict[str, Any]:
        """Get customer portal configuration.

        Args:
            company: The company identifier.

        Returns:
            Dict with portal settings.
        """
        settings = self.get(company)
        return {
            "portal_enabled": settings.portal_enabled,
            "portal_ticket_creation_enabled": settings.portal_ticket_creation_enabled,
            "portal_show_ticket_history": settings.portal_show_ticket_history,
            "portal_show_knowledge_base": settings.portal_show_knowledge_base,
            "portal_show_faq": settings.portal_show_faq,
            "portal_require_login": settings.portal_require_login,
        }

    # -------------------------------------------------------------------------
    # Integration Config
    # -------------------------------------------------------------------------

    def get_integration_config(self, company: Optional[str] = None) -> Dict[str, Any]:
        """Get integration configuration.

        Args:
            company: The company identifier.

        Returns:
            Dict with integration settings.
        """
        settings = self.get(company)
        return {
            "email_to_ticket_enabled": settings.email_to_ticket_enabled,
            "email_reply_to_address": settings.email_reply_to_address,
            "sync_to_erpnext": settings.sync_to_erpnext,
            "sync_to_splynx": settings.sync_to_splynx,
            "sync_to_chatwoot": settings.sync_to_chatwoot,
        }

    # -------------------------------------------------------------------------
    # Display Config
    # -------------------------------------------------------------------------

    def get_display_config(self, company: Optional[str] = None) -> Dict[str, Any]:
        """Get display/formatting configuration.

        Args:
            company: The company identifier.

        Returns:
            Dict with display settings.
        """
        settings = self.get(company)
        return {
            "ticket_id_prefix": settings.ticket_id_prefix,
            "ticket_id_min_digits": settings.ticket_id_min_digits,
            "date_format": settings.date_format,
            "time_format": settings.time_format,
        }

    def format_ticket_number(
        self,
        ticket_id: int,
        company: Optional[str] = None,
    ) -> str:
        """Format a ticket ID according to settings.

        Args:
            ticket_id: The ticket ID.
            company: The company identifier.

        Returns:
            Formatted ticket number string.
        """
        settings = self.get(company)
        prefix = settings.ticket_id_prefix or "TKT"
        min_digits = settings.ticket_id_min_digits or 6
        return f"{prefix}-{str(ticket_id).zfill(min_digits)}"
