"""Integration service stubs for the Marketing module."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import re
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

from app.models.marketing import MarketingIntegration, MarketingIntegrationStatus
from app.models.omni import OmniChannel, OmniChannelType
from app.services.errors import NotFoundError
from app.services.secrets_service import get_secrets
from app.services.support.channels import ChannelService
from app.services.support.errors import ValidationError as ChannelValidationError
from app.services.support.types import ChannelCreate
from app.services.validation.soft_validation_service import SoftValidationService


def _format_datetime(value: datetime | None) -> str:
    if not value:
        return "--"
    return value.strftime("%b %d, %Y")


def _integration_label(name: str) -> str:
    return name.replace("_", " ").title()


def _integration_description(name: str) -> str:
    mapping = {
        "meta": "Facebook & Instagram ads + pages",
        "twitter": "X (Twitter) publishing and analytics",
        "linkedin": "LinkedIn pages and ads",
        "whatsapp": "WhatsApp Business messaging",
    }
    return mapping.get(name, "Marketing platform connection")


class IntegrationService:
    """Provide integration connection data."""

    def __init__(self, db: Session):
        self.db = db
        self._secrets = get_secrets()

    def list_default_providers(self) -> List[Dict[str, str]]:
        return [
            {"id": "meta", "label": "Meta Business", "description": _integration_description("meta")},
            {"id": "twitter", "label": "X (Twitter)", "description": _integration_description("twitter")},
            {"id": "linkedin", "label": "LinkedIn", "description": _integration_description("linkedin")},
            {"id": "whatsapp", "label": "WhatsApp", "description": _integration_description("whatsapp")},
        ]

    def list_integrations(self) -> List[Dict[str, Any]]:
        integrations = (
            self.db.query(MarketingIntegration)
            .order_by(MarketingIntegration.created_at.desc())
            .all()
        )
        results: List[Dict[str, Any]] = []
        for integration in integrations:
            name = integration.integration_type
            settings = integration.settings or {}
            display_name = settings.get("name") or _integration_label(name)
            description = settings.get("description") or _integration_description(name)
            results.append(
                {
                    "name": display_name,
                    "description": description,
                    "status": integration.status.value,
                    "last_synced": _format_datetime(integration.last_synced_at),
                    "href": "/marketing/integrations",
                }
            )
        return results

    def get_callback_base_url(self, default_base_url: str) -> str:
        for provider in self.list_default_providers():
            integration = (
                self.db.query(MarketingIntegration)
                .filter(MarketingIntegration.integration_type == provider["id"])
                .first()
            )
            if integration and integration.settings:
                base_url = integration.settings.get("callback_base_url")
                if base_url:
                    return base_url
        return default_base_url.rstrip("/")

    def get_integration(self, integration_id: int) -> MarketingIntegration:
        integration = (
            self.db.query(MarketingIntegration)
            .filter(MarketingIntegration.id == integration_id)
            .first()
        )
        if not integration:
            raise NotFoundError("Integration not found")
        return integration

    def get_or_create_by_type(self, integration_type: str) -> MarketingIntegration:
        integration = (
            self.db.query(MarketingIntegration)
            .filter(MarketingIntegration.integration_type == integration_type)
            .first()
        )
        if not integration:
            integration = MarketingIntegration(
                integration_type=integration_type,
                status=MarketingIntegrationStatus.DISCONNECTED,
                settings={},
            )
            self.db.add(integration)
            self.db.flush()
            SoftValidationService(self.db).validate_and_store(integration)
        return integration

    def create_integration(self, data: Dict[str, Any]) -> MarketingIntegration:
        integration = MarketingIntegration(
            integration_type=data["integration_type"],
            credentials_encrypted=data.get("credentials_encrypted"),
            status=data.get("status", MarketingIntegrationStatus.DISCONNECTED),
            settings=data.get("settings") or {},
            last_synced_at=data.get("last_synced_at"),
        )
        self.db.add(integration)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(integration)
        self.ensure_omni_channel(integration)
        return integration

    def create_custom_integration(self, data: Dict[str, Any]) -> MarketingIntegration:
        integration_type = _slugify(data["integration_type"])
        integration = self.get_or_create_by_type(integration_type)
        integration.status = data.get("status", MarketingIntegrationStatus.DISCONNECTED)
        settings = integration.settings or {}
        settings.update(
            {
                "name": data.get("name") or integration_type,
                "description": data.get("description"),
                "webhook_url": data.get("webhook_url"),
            }
        )
        integration.settings = settings
        credentials = data.get("credentials")
        if credentials:
            integration.credentials_encrypted = self._secrets.encrypt(json.dumps({"credentials": credentials}))
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(integration)
        self.ensure_omni_channel(integration)
        return integration

    def update_integration(self, integration_id: int, data: Dict[str, Any]) -> MarketingIntegration:
        integration = self.get_integration(integration_id)
        for field in [
            "integration_type",
            "credentials_encrypted",
            "status",
            "settings",
            "last_synced_at",
        ]:
            if field in data:
                setattr(integration, field, data[field])
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(integration)
        self.ensure_omni_channel(integration)
        return integration

    def update_settings_by_type(self, integration_type: str, updates: Dict[str, Any]) -> MarketingIntegration:
        integration = self.get_or_create_by_type(integration_type)
        settings = integration.settings or {}
        settings.update(updates)
        integration.settings = settings
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(integration)
        self.ensure_omni_channel(integration)
        return integration

    def set_oauth_state(self, integration: MarketingIntegration, state: str, expires_in: int = 600) -> None:
        settings = integration.settings or {}
        settings["oauth_state"] = state
        settings["oauth_state_expires_at"] = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
        integration.settings = settings
        self.db.flush()

    def validate_oauth_state(self, integration: MarketingIntegration, state: str) -> bool:
        settings = integration.settings or {}
        stored_state = settings.get("oauth_state")
        expires_at = settings.get("oauth_state_expires_at")
        if not stored_state or stored_state != state:
            return False
        if expires_at:
            try:
                expires_at_dt = datetime.fromisoformat(expires_at)
            except ValueError:
                return False
            if datetime.now(timezone.utc) > expires_at_dt:
                return False
        return True

    def store_credentials(self, integration: MarketingIntegration, payload: Dict[str, Any]) -> None:
        integration.credentials_encrypted = self._secrets.encrypt(json.dumps(payload))
        integration.status = MarketingIntegrationStatus.CONNECTED
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(integration)
        self.ensure_omni_channel(integration)

    def get_credentials(self, integration: MarketingIntegration) -> Dict[str, Any]:
        if not integration.credentials_encrypted:
            return {}
        return json.loads(self._secrets.decrypt(integration.credentials_encrypted))

    def delete_integration(self, integration_id: int) -> None:
        integration = self.get_integration(integration_id)
        channel = self._get_existing_channel(integration)
        if channel:
            channel.is_active = False
            channel.updated_at = datetime.now(timezone.utc)
        self.db.delete(integration)

    def ensure_omni_channel(self, integration: MarketingIntegration) -> OmniChannel:
        channel = self._get_existing_channel(integration)
        channel_type = _marketing_channel_type(integration.integration_type)
        settings = integration.settings or {}
        channel_name = _marketing_channel_name(integration)

        if channel:
            if channel.type != channel_type:
                channel.type = channel_type
            if channel.name != channel_name:
                channel.name = channel_name
            channel.config = _marketing_channel_config(integration)
            channel.is_active = True
            channel.updated_at = datetime.now(timezone.utc)
        else:
            channel = self._create_channel(channel_name, channel_type, integration)

        settings["omni_channel_id"] = channel.id
        settings["omni_channel_name"] = channel.name
        integration.settings = settings
        return channel

    def _get_existing_channel(self, integration: MarketingIntegration) -> Optional[OmniChannel]:
        settings = integration.settings or {}
        channel_id = settings.get("omni_channel_id")
        if channel_id:
            channel = self.db.query(OmniChannel).filter(OmniChannel.id == channel_id).first()
            if channel:
                return channel

        if integration.id:
            return (
                self.db.query(OmniChannel)
                .filter(
                    OmniChannel.config["source"].astext == "marketing",
                    OmniChannel.config["integration_id"].astext == str(integration.id),
                )
                .first()
            )
        return None

    def _create_channel(
        self,
        name: str,
        channel_type: str,
        integration: MarketingIntegration,
    ) -> OmniChannel:
        channel_service = ChannelService(self.db)
        config = _marketing_channel_config(integration)
        try:
            channel = channel_service.create(
                ChannelCreate(
                    name=name,
                    type=channel_type,
                    config=config,
                    is_active=True,
                )
            )
        except ChannelValidationError:
            channel = channel_service.create(
                ChannelCreate(
                    name=f"{name} ({integration.id})",
                    type=channel_type,
                    config=config,
                    is_active=True,
                )
            )
        return channel


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\\-\\s]+", "", value)
    value = re.sub(r"\\s+", "-", value)
    return value or "custom"


def _marketing_channel_type(integration_type: str) -> str:
    if integration_type == "whatsapp":
        return OmniChannelType.WHATSAPP.value
    return OmniChannelType.CUSTOM.value


def _marketing_channel_name(integration: MarketingIntegration) -> str:
    settings = integration.settings or {}
    name = settings.get("name") or _integration_label(integration.integration_type)
    return f"Marketing: {name}"


def _marketing_channel_config(integration: MarketingIntegration) -> Dict[str, Any]:
    return {
        "source": "marketing",
        "integration_id": integration.id,
        "integration_type": integration.integration_type,
    }
