"""Email campaign service stubs for the Marketing module."""
from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Any

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.marketing import (
    EmailCampaign,
    EmailCampaignStatus,
    EmailSend,
    EmailSendStatus,
    EmailTemplate,
    MarketingAudience,
)
from app.services.errors import NotFoundError
from app.services.validation.soft_validation_service import SoftValidationService


def _format_datetime(value: datetime | None) -> str:
    if not value:
        return "--"
    return value.strftime("%b %d, %Y")


def _format_percent(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0%"
    return f"{round((numerator / denominator) * 100)}%"


def _truncate(text: str | None, limit: int = 120) -> str:
    if not text:
        return ""
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return f"{clean[:limit - 3]}..."


class EmailCampaignService:
    """Provide email campaigns, templates, and analytics."""

    def __init__(self, db: Session):
        self.db = db

    def list_campaigns(self) -> List[Dict[str, Any]]:
        campaigns = (
            self.db.query(EmailCampaign, MarketingAudience)
            .outerjoin(MarketingAudience, EmailCampaign.audience_id == MarketingAudience.id)
            .order_by(EmailCampaign.created_at.desc())
            .all()
        )
        results: List[Dict[str, Any]] = []
        for campaign, audience in campaigns:
            metrics = campaign.metrics or {}
            opens = metrics.get("open_rate")
            clicks = metrics.get("click_rate")
            results.append(
                {
                    "name": campaign.name,
                    "segment": audience.name if audience else "All",
                    "status": campaign.status.value,
                    "send_date": _format_datetime(campaign.scheduled_at),
                    "opens": opens if opens is not None else "0%",
                    "clicks": clicks if clicks is not None else "0%",
                }
            )
        return results

    def list_templates(self) -> List[Dict[str, Any]]:
        templates = (
            self.db.query(EmailTemplate)
            .order_by(EmailTemplate.updated_at.desc())
            .all()
        )
        results: List[Dict[str, Any]] = []
        for template in templates:
            preview_source = template.body_text or template.body_html or ""
            results.append(
                {
                    "name": template.name,
                    "status": "active" if template.is_system_template else "draft",
                    "preview": _truncate(preview_source, 140),
                    "last_updated": _format_datetime(template.updated_at),
                }
            )
        return results

    def get_kpis(self) -> List[Dict[str, Any]]:
        total_sent = (
            self.db.query(func.count(EmailSend.id))
            .filter(EmailSend.status == EmailSendStatus.SENT)
            .scalar()
            or 0
        )
        total_opened = (
            self.db.query(func.count(EmailSend.id))
            .filter(EmailSend.status == EmailSendStatus.OPENED)
            .scalar()
            or 0
        )
        total_clicked = (
            self.db.query(func.count(EmailSend.id))
            .filter(EmailSend.status == EmailSendStatus.CLICKED)
            .scalar()
            or 0
        )
        total_bounced = (
            self.db.query(func.count(EmailSend.id))
            .filter(EmailSend.status == EmailSendStatus.BOUNCED)
            .scalar()
            or 0
        )

        return [
            {"label": "Sent", "value": total_sent, "icon": "check-circle", "color": "text-primary-600"},
            {"label": "Open Rate", "value": _format_percent(total_opened, total_sent), "icon": "trending-up", "color": "text-emerald-600"},
            {"label": "Click Rate", "value": _format_percent(total_clicked, total_sent), "icon": "activity", "color": "text-indigo-600"},
            {"label": "Bounced", "value": total_bounced, "icon": "clock", "color": "text-amber-600"},
        ]

    def get_metrics(self) -> List[Dict[str, Any]]:
        total_sent = (
            self.db.query(func.count(EmailSend.id))
            .filter(EmailSend.status == EmailSendStatus.SENT)
            .scalar()
            or 0
        )
        total_opened = (
            self.db.query(func.count(EmailSend.id))
            .filter(EmailSend.status == EmailSendStatus.OPENED)
            .scalar()
            or 0
        )
        total_clicked = (
            self.db.query(func.count(EmailSend.id))
            .filter(EmailSend.status == EmailSendStatus.CLICKED)
            .scalar()
            or 0
        )
        total_bounced = (
            self.db.query(func.count(EmailSend.id))
            .filter(EmailSend.status == EmailSendStatus.BOUNCED)
            .scalar()
            or 0
        )

        return [
            {"label": "Sent", "value": total_sent, "delta": "0%"},
            {"label": "Open Rate", "value": _format_percent(total_opened, total_sent), "delta": "0%"},
            {"label": "Click Rate", "value": _format_percent(total_clicked, total_sent), "delta": "0%"},
            {"label": "Bounce Rate", "value": _format_percent(total_bounced, total_sent), "delta": "0%"},
        ]

    def get_top_campaigns(self) -> List[Dict[str, Any]]:
        rows = (
            self.db.query(
                EmailCampaign.id,
                EmailCampaign.name,
                func.count(EmailSend.id).label("sent"),
                func.sum(case((EmailSend.status == EmailSendStatus.OPENED, 1), else_=0)).label("opened"),
                func.sum(case((EmailSend.status == EmailSendStatus.CLICKED, 1), else_=0)).label("clicked"),
            )
            .join(EmailSend, EmailSend.campaign_id == EmailCampaign.id)
            .group_by(EmailCampaign.id)
            .order_by(func.count(EmailSend.id).desc())
            .limit(5)
            .all()
        )
        results: List[Dict[str, Any]] = []
        for row in rows:
            sent = row.sent or 0
            results.append(
                {
                    "name": row.name,
                    "open_rate": _format_percent(row.opened or 0, sent),
                    "click_rate": _format_percent(row.clicked or 0, sent),
                }
            )
        return results

    def get_campaign(self, campaign_id: int) -> EmailCampaign:
        campaign = (
            self.db.query(EmailCampaign)
            .filter(EmailCampaign.id == campaign_id)
            .first()
        )
        if not campaign:
            raise NotFoundError("Email campaign not found")
        return campaign

    def create_campaign(self, data: Dict[str, Any]) -> EmailCampaign:
        campaign = EmailCampaign(
            name=data["name"],
            template_id=data["template_id"],
            audience_id=data.get("audience_id"),
            campaign_id=data.get("campaign_id"),
            status=data.get("status", EmailCampaignStatus.DRAFT),
            scheduled_at=data.get("scheduled_at"),
            timezone=data.get("timezone", "UTC"),
            send_window_start=data.get("send_window_start"),
            send_window_end=data.get("send_window_end"),
            metrics=data.get("metrics") or {},
        )
        self.db.add(campaign)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(campaign)
        return campaign

    def update_campaign(self, campaign_id: int, data: Dict[str, Any]) -> EmailCampaign:
        campaign = self.get_campaign(campaign_id)
        for field in [
            "name",
            "template_id",
            "audience_id",
            "campaign_id",
            "status",
            "scheduled_at",
            "timezone",
            "send_window_start",
            "send_window_end",
            "metrics",
        ]:
            if field in data:
                setattr(campaign, field, data[field])
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(campaign)
        return campaign

    def delete_campaign(self, campaign_id: int) -> None:
        campaign = self.get_campaign(campaign_id)
        self.db.delete(campaign)

    def get_template(self, template_id: int) -> EmailTemplate:
        template = (
            self.db.query(EmailTemplate)
            .filter(EmailTemplate.id == template_id)
            .first()
        )
        if not template:
            raise NotFoundError("Email template not found")
        return template

    def create_template(self, data: Dict[str, Any]) -> EmailTemplate:
        template = EmailTemplate(
            name=data["name"],
            subject=data.get("subject"),
            body_html=data.get("body_html"),
            body_text=data.get("body_text"),
            variables=data.get("variables") or [],
            is_system_template=bool(data.get("is_system_template", False)),
        )
        self.db.add(template)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(template)
        return template

    def update_template(self, template_id: int, data: Dict[str, Any]) -> EmailTemplate:
        template = self.get_template(template_id)
        for field in [
            "name",
            "subject",
            "body_html",
            "body_text",
            "variables",
            "is_system_template",
        ]:
            if field in data:
                setattr(template, field, data[field])
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(template)
        return template

    def delete_template(self, template_id: int) -> None:
        template = self.get_template(template_id)
        self.db.delete(template)
