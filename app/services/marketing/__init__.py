"""Marketing services package."""
from .campaign_service import CampaignService
from .journey_service import JourneyService
from .social_service import SocialMediaService
from .email_campaign_service import EmailCampaignService
from .audience_service import AudienceService
from .integration_service import IntegrationService
from .analytics_service import MarketingAnalyticsService
from .consent_service import ConsentService
from .seed import seed_marketing_defaults

__all__ = [
    "CampaignService",
    "JourneyService",
    "SocialMediaService",
    "EmailCampaignService",
    "AudienceService",
    "IntegrationService",
    "MarketingAnalyticsService",
    "ConsentService",
    "seed_marketing_defaults",
]
