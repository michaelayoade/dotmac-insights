"""Audience service stubs for the Marketing module."""
from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Any

from sqlalchemy.orm import Session

from app.models.marketing import MarketingAudience
from app.services.errors import NotFoundError
from app.services.validation.soft_validation_service import SoftValidationService


def _format_datetime(value: datetime | None) -> str:
    if not value:
        return "--"
    return value.strftime("%b %d, %Y")


def _criteria_summary(criteria: dict) -> str:
    if not criteria:
        return "All contacts"
    parts = []
    for key, value in criteria.items():
        parts.append(f"{key}: {value}")
    return ", ".join(parts)


class AudienceService:
    """Provide audience segment data."""

    def __init__(self, db: Session):
        self.db = db

    def list_audiences(self) -> List[Dict[str, Any]]:
        audiences = (
            self.db.query(MarketingAudience)
            .order_by(MarketingAudience.updated_at.desc())
            .all()
        )
        results: List[Dict[str, Any]] = []
        for audience in audiences:
            results.append(
                {
                    "name": audience.name,
                    "criteria": _criteria_summary(audience.filter_criteria or {}),
                    "members": audience.member_count,
                    "updated": _format_datetime(audience.updated_at),
                }
            )
        return results

    def get_audience(self, audience_id: int) -> MarketingAudience:
        audience = (
            self.db.query(MarketingAudience)
            .filter(MarketingAudience.id == audience_id)
            .first()
        )
        if not audience:
            raise NotFoundError("Audience not found")
        return audience

    def create_audience(self, data: Dict[str, Any]) -> MarketingAudience:
        audience = MarketingAudience(
            name=data["name"],
            description=data.get("description"),
            filter_criteria=data.get("filter_criteria") or {},
            member_count=data.get("member_count", 0),
        )
        self.db.add(audience)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(audience)
        return audience

    def update_audience(self, audience_id: int, data: Dict[str, Any]) -> MarketingAudience:
        audience = self.get_audience(audience_id)
        for field in ["name", "description", "filter_criteria", "member_count"]:
            if field in data:
                setattr(audience, field, data[field])
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(audience)
        return audience

    def delete_audience(self, audience_id: int) -> None:
        audience = self.get_audience(audience_id)
        self.db.delete(audience)
