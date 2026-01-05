"""Service layer for assets settings routes."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.asset_settings import AssetSettings
from app.services.validation.soft_validation_service import SoftValidationService


class SettingsAssetsService:
    """Assets settings coordinator for read/write operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_settings(self) -> AssetSettings:
        settings = self.db.query(AssetSettings).filter(AssetSettings.company == None).first()
        if not settings:
            settings = AssetSettings()
        return settings

    def save_settings(self, values: dict[str, Any]) -> None:
        settings = self.db.query(AssetSettings).filter(AssetSettings.company == None).first()
        if not settings:
            settings = AssetSettings()
            self.db.add(settings)

        for key, value in values.items():
            setattr(settings, key, value)

        SoftValidationService(self.db).validate_and_store(settings)
        self.db.commit()
