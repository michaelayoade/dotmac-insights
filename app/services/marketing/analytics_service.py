"""Analytics service stubs for the Marketing module."""
from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.marketing import (
    CustomerJourney,
    EmailCampaign,
    EmailCampaignStatus,
    EmailSend,
    JourneyStatus,
    MarketingAudience,
    MarketingCampaign,
    SocialAccount,
    SocialPost,
    SocialPostStatus,
)
from app.services.marketing.journey_service import _format_datetime as _format_journey_datetime
from app.services.marketing.social_service import _format_datetime as _format_social_datetime


class MarketingAnalyticsService:
    """Provide dashboard metrics and summary data."""

    def __init__(self, db: Session):
        self.db = db

    def get_dashboard_stats(self) -> List[Dict[str, Any]]:
        total_campaigns = self.db.query(func.count(MarketingCampaign.id)).scalar() or 0
        active_journeys = (
            self.db.query(func.count(CustomerJourney.id))
            .filter(CustomerJourney.status == JourneyStatus.ACTIVE)
            .scalar()
            or 0
        )
        scheduled_emails = (
            self.db.query(func.count(EmailCampaign.id))
            .filter(EmailCampaign.status == EmailCampaignStatus.SCHEDULED)
            .scalar()
            or 0
        )
        scheduled_posts = (
            self.db.query(func.count(SocialPost.id))
            .filter(SocialPost.status == SocialPostStatus.SCHEDULED)
            .scalar()
            or 0
        )
        total_audiences = self.db.query(func.count(MarketingAudience.id)).scalar() or 0
        total_sends = self.db.query(func.count(EmailSend.id)).scalar() or 0

        return [
            {
                "label": "Campaigns",
                "value": total_campaigns,
                "icon": "target",
                "icon_bg": "bg-emerald-50",
                "icon_color": "text-emerald-600",
            },
            {
                "label": "Active Journeys",
                "value": active_journeys,
                "icon": "repeat",
                "icon_bg": "bg-indigo-50",
                "icon_color": "text-indigo-600",
            },
            {
                "label": "Email Queued",
                "value": scheduled_emails,
                "icon": "inbox",
                "icon_bg": "bg-blue-50",
                "icon_color": "text-blue-600",
            },
            {
                "label": "Social Scheduled",
                "value": scheduled_posts,
                "icon": "calendar",
                "icon_bg": "bg-amber-50",
                "icon_color": "text-amber-600",
            },
            {
                "label": "Audiences",
                "value": total_audiences,
                "icon": "users",
                "icon_bg": "bg-slate-50",
                "icon_color": "text-slate-600",
            },
            {
                "label": "Email Sends",
                "value": total_sends,
                "icon": "activity",
                "icon_bg": "bg-emerald-50",
                "icon_color": "text-emerald-600",
            },
        ]

    def get_upcoming_sends(self) -> List[Dict[str, Any]]:
        now = datetime.utcnow()
        campaigns = (
            self.db.query(EmailCampaign, MarketingAudience)
            .outerjoin(MarketingAudience, EmailCampaign.audience_id == MarketingAudience.id)
            .filter(EmailCampaign.scheduled_at.isnot(None))
            .filter(EmailCampaign.scheduled_at >= now)
            .filter(EmailCampaign.status == EmailCampaignStatus.SCHEDULED)
            .order_by(EmailCampaign.scheduled_at.asc())
            .limit(5)
            .all()
        )
        results: List[Dict[str, Any]] = []
        for campaign, audience in campaigns:
            results.append(
                {
                    "name": campaign.name,
                    "channel": "Email",
                    "audience": audience.name if audience else "All",
                    "scheduled": _format_social_datetime(campaign.scheduled_at),
                }
            )
        return results

    def get_active_journeys(self) -> List[Dict[str, Any]]:
        journeys = (
            self.db.query(CustomerJourney)
            .filter(CustomerJourney.status == JourneyStatus.ACTIVE)
            .order_by(CustomerJourney.updated_at.desc())
            .limit(4)
            .all()
        )
        results: List[Dict[str, Any]] = []
        for journey in journeys:
            data = {
                "name": journey.name,
                "status": journey.status.value,
            }
            updated_at = _format_journey_datetime(journey.updated_at)
            if updated_at:
                data["updated_at"] = updated_at
            results.append(data)
        return results

    def get_scheduled_posts(self) -> List[Dict[str, Any]]:
        posts = (
            self.db.query(SocialPost, SocialAccount)
            .join(SocialAccount, SocialPost.account_id == SocialAccount.id)
            .filter(SocialPost.status == SocialPostStatus.SCHEDULED)
            .order_by(SocialPost.scheduled_at.asc().nullslast())
            .limit(3)
            .all()
        )
        results: List[Dict[str, Any]] = []
        for post, account in posts:
            content = (post.content or "").strip()
            title = content.split(".")[0][:60] if content else "Scheduled post"
            excerpt = content[:140] + "..." if len(content) > 140 else content
            results.append(
                {
                    "title": title,
                    "platforms": account.platform.value.replace("_", " ").title(),
                    "status": post.status.value,
                    "excerpt": excerpt,
                    "scheduled_at": _format_social_datetime(post.scheduled_at),
                    "owner": "Marketing Team",
                }
            )
        return results

    def get_top_audiences(self) -> List[Dict[str, Any]]:
        audiences = (
            self.db.query(MarketingAudience)
            .order_by(MarketingAudience.member_count.desc())
            .limit(5)
            .all()
        )
        return [
            {
                "name": audience.name,
                "count": audience.member_count,
                "growth": "0%",
            }
            for audience in audiences
        ]
