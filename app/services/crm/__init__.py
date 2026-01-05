"""CRM domain services.

This module contains business logic for:
- Opportunities (deal pipeline)
- Leads (Party-based lead management)
- Activities (calls, meetings, tasks, notes)
- Campaigns (marketing campaigns)
- CRM Analytics and Dashboard
- Support-CRM Integration
- Nurture Sequences (drip campaigns)
- Contact Segmentation
- Lead Scoring
- Proactive Communications
- Customer Health Analytics (CRM-Support integration)
"""
from .opportunities import OpportunityService
from .leads import LeadService
from .activities import ActivityService
from .campaigns import CampaignService
from .analytics import CRMAnalyticsService
from .dashboard import CRMDashboardService
from .support_integration import SupportCRMBridgeService
from .nurture import NurtureSequenceService
from .segments import SegmentService
from .scoring import LeadScoringService
from .communication import CRMCommunicationService
from .customer_health import CustomerHealthService
from .health_web import CustomerHealthWebService

__all__ = [
    "OpportunityService",
    "LeadService",
    "ActivityService",
    "CampaignService",
    "CRMAnalyticsService",
    "CRMDashboardService",
    "SupportCRMBridgeService",
    "NurtureSequenceService",
    "SegmentService",
    "LeadScoringService",
    "CRMCommunicationService",
    "CustomerHealthService",
    "CustomerHealthWebService",
]
