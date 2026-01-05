"""Campaign service stubs for the Marketing module."""
from __future__ import annotations

from decimal import Decimal
from typing import List, Dict, Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.marketing import MarketingCampaign, MarketingCampaignStatus, MarketingCampaignType
from app.services.errors import NotFoundError
from app.services.validation.soft_validation_service import SoftValidationService


def _format_currency(currency: str, amount: Decimal | None) -> str:
    if amount is None:
        return f"{currency} 0.00"
    return f"{currency} {amount:,.2f}"


class CampaignService:
    """Provide marketing campaign data."""

    def __init__(self, db: Session):
        self.db = db

    def list_campaigns(self) -> List[Dict[str, Any]]:
        campaigns = (
            self.db.query(MarketingCampaign)
            .order_by(MarketingCampaign.created_at.desc())
            .all()
        )
        results: List[Dict[str, Any]] = []
        for campaign in campaigns:
            metrics = campaign.metrics or {}
            results.append(
                {
                    "name": campaign.name,
                    "type": campaign.campaign_type.value.replace("_", " ").title(),
                    "status": campaign.status.value,
                    "budget": _format_currency(campaign.currency, campaign.budget),
                    "reach": metrics.get("reach", "--"),
                    "owner": metrics.get("owner", "--"),
                }
            )
        return results

    def get_highlights(self) -> List[Dict[str, Any]]:
        total_campaigns = self.db.query(func.count(MarketingCampaign.id)).scalar() or 0
        active_campaigns = (
            self.db.query(func.count(MarketingCampaign.id))
            .filter(MarketingCampaign.status == MarketingCampaignStatus.ACTIVE)
            .scalar()
            or 0
        )
        total_budget = (
            self.db.query(func.coalesce(func.sum(MarketingCampaign.budget), 0))
            .scalar()
            or 0
        )
        scheduled = (
            self.db.query(func.count(MarketingCampaign.id))
            .filter(MarketingCampaign.status == MarketingCampaignStatus.PAUSED)
            .scalar()
            or 0
        )

        return [
            {"label": "Total Campaigns", "value": total_campaigns, "icon": "target", "color": "text-primary-600"},
            {"label": "Active", "value": active_campaigns, "icon": "trending-up", "color": "text-emerald-600"},
            {"label": "Paused", "value": scheduled, "icon": "clock", "color": "text-amber-600"},
            {"label": "Budget", "value": _format_currency(settings.default_currency, Decimal(total_budget)), "icon": "dollar-sign", "color": "text-indigo-600"},
        ]

    def get_campaign(self, campaign_id: int) -> MarketingCampaign:
        campaign = (
            self.db.query(MarketingCampaign)
            .filter(MarketingCampaign.id == campaign_id)
            .first()
        )
        if not campaign:
            raise NotFoundError("Marketing campaign not found")
        return campaign

    def create_campaign(self, data: Dict[str, Any]) -> MarketingCampaign:
        campaign = MarketingCampaign(
            name=data["name"],
            description=data.get("description"),
            campaign_type=data.get("campaign_type", MarketingCampaignType.MULTI_CHANNEL),
            status=data.get("status", MarketingCampaignStatus.DRAFT),
            budget=data.get("budget", Decimal("0")),
            currency=data.get("currency", "NGN"),
            utm_params=data.get("utm_params") or {},
            metrics=data.get("metrics") or {},
            starts_at=data.get("starts_at"),
            ends_at=data.get("ends_at"),
        )
        self.db.add(campaign)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(campaign)
        return campaign

    def update_campaign(self, campaign_id: int, data: Dict[str, Any]) -> MarketingCampaign:
        campaign = self.get_campaign(campaign_id)
        for field in [
            "name",
            "description",
            "campaign_type",
            "status",
            "budget",
            "currency",
            "utm_params",
            "metrics",
            "starts_at",
            "ends_at",
        ]:
            if field in data:
                setattr(campaign, field, data[field])
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(campaign)
        return campaign

    def delete_campaign(self, campaign_id: int) -> None:
        campaign = self.get_campaign(campaign_id)
        self.db.delete(campaign)
