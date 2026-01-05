"""Service layer for support settings routes."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.support.custom_fields import CustomFieldService
from app.services.support.email_templates import EmailTemplateService
from app.services.support.escalation import EscalationService
from app.services.support.queues import QueueService
from app.services.support.settings import SettingsService
from app.services.support.types import SupportSettingsUpdate


class SettingsSupportService:
    """Support settings coordinator with DB lifecycle management."""

    def __init__(self, db: Session, principal: Any):
        self.db = db
        self.principal = principal

    def get_general_settings(self) -> dict:
        service = SettingsService(self.db, principal=self.principal)
        if not service.exists():
            settings = service.get()
            self.db.commit()
        else:
            settings = service.get()
        return settings

    def save_general_settings(self, update_data: SupportSettingsUpdate) -> None:
        service = SettingsService(self.db, principal=self.principal)
        service.update(update_data)
        self.db.commit()

    def list_escalation_policies(self) -> list:
        service = EscalationService(self.db, principal=self.principal)
        policies = service.list_policies(active_only=False)
        for policy in policies:
            _ = policy.levels
        return policies

    def list_queues(self) -> list:
        service = QueueService(self.db, principal=self.principal)
        return service.list(active_only=False, include_all=True)

    def list_custom_fields(self) -> list:
        service = CustomFieldService(self.db, principal=self.principal)
        return service.list(active_only=False)

    def list_email_templates(self) -> list:
        service = EmailTemplateService(self.db, principal=self.principal)
        service.ensure_default_templates()
        self.db.commit()
        return service.list(active_only=False)
