"""Support domain services.

This module contains business logic for:
- Tickets (help desk)
- Conversations (omnichannel inbox)
- Messages (inbound/outbound)
- Channels (email, WhatsApp, etc.)
- Webhooks (ingest, delivery)
- Routing and automation
- SLA management
- Agents and teams
- Canned responses
- Knowledge base
- CSAT surveys
- Tags
- Escalation policies
- Ticket queues
- Support settings
- Custom fields
- Email templates
"""
# Core services
from .tickets import TicketService
from .conversations import ConversationService
from .legacy_conversations import LegacyConversationService
from .messages import MessageService
from .channels import ChannelService
from .webhooks import WebhookService
from .sla import SLAService
from .routing import RoutingService
from .automation import AutomationService

# Extended services
from .agents import AgentService
from .canned_responses import CannedResponseService
from .knowledge_base import KnowledgeBaseService
from .csat import CSATService
from .tags import TagService

# Additional services
from .escalation import EscalationService
from .queues import QueueService
from .settings import SettingsService
from .custom_fields import CustomFieldService
from .email_templates import EmailTemplateService
from .analytics import SupportAnalyticsService

# Type definitions
from .types import (
    # Conversation types
    AttachmentData,
    BulkOperationResult,
    ConversationBulkUpdate,
    ConversationCreate,
    ConversationFilters,
    ConversationStats,
    ConversationUpdate,
    ConversationWithMessages,
    # Message types
    InboundMessageData,
    InboxStats,
    InternalNoteData,
    MessageFilters,
    OutboundMessageData,
    # Channel types
    ChannelCreate,
    ChannelUpdate,
    ConnectionTestResult,
    DeliveryResult,
    # Webhook types
    WebhookEventData,
    WebhookResult,
    # Routing types
    RoutingMatch,
    RoutingRuleCreate,
    RoutingRuleUpdate,
    TicketRoutingRuleCreate,
    TicketRoutingRuleUpdate,
    # SLA types
    BusinessCalendarCreate,
    BusinessCalendarUpdate,
    HolidayCreate,
    SLABreachFilters,
    SLABreachInfo,
    SLABreachSummary,
    SLADueDates,
    SLAPolicyCreate,
    SLAPolicyUpdate,
    SLATargetCreate,
    SLATargetUpdate,
    # Agent types
    AgentCreate,
    AgentFilters,
    AgentUpdate,
    AgentWorkload,
    AgentDetailStats,
    AgentDetailResult,
    TeamCreate,
    TeamUpdate,
    TeamWorkload,
    # Canned response types
    CannedResponseCreate,
    CannedResponseUpdate,
    CannedResponseFilters,
    CannedResponseStats,
    CannedListResult,
    # Knowledge base types
    KBArticleCreate,
    KBArticleFilters,
    KBArticleStats,
    KBArticleUpdate,
    KBAttachmentData,
    KBCategoryCreate,
    KBCategoryUpdate,
    KBHelpfulnessStats,
    KBListResult,
    # CSAT types
    CSATMetrics,
    CSATSurveyCreate,
    CSATSurveyUpdate,
    # Tag types
    TagCreate,
    TagUpdate,
    # Escalation types
    EscalationPolicyCreate,
    EscalationPolicyUpdate,
    EscalationLevelCreate,
    EscalationLevelUpdate,
    EscalationResult,
    # Queue types
    QueueCreate,
    QueueUpdate,
    # Settings types
    SupportSettingsUpdate,
    # Custom field types
    CustomFieldCreate,
    CustomFieldUpdate,
    # Email template types
    EmailTemplateCreate,
    EmailTemplateUpdate,
    # Analytics types
    AnalyticsFilters,
    OverviewStats,
    VolumeDataPoint,
    VolumeTrend,
    ResolutionTimeStats,
    FirstResponseStats,
    AgentPerformance,
    TeamPerformance,
    ChannelStats,
    CategoryStats,
    SLAPerformance,
    BacklogAging,
    ReopenAnalysis,
    PatternInsights,
    AutomationEffectiveness,
    KBDeflection,
    E2EReport,
)

# Errors
from .errors import (
    # Base errors (re-exported)
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceError,
    ValidationError,
    # Conversation errors
    ConversationAssignmentError,
    ConversationClosedError,
    ConversationNotFoundError,
    # Message errors
    DuplicateMessageError,
    MessageDeliveryError,
    MessageNotFoundError,
    # Channel errors
    ChannelConfigError,
    ChannelInactiveError,
    ChannelNotFoundError,
    # Webhook errors
    DuplicateWebhookError,
    WebhookProcessingError,
    WebhookValidationError,
    # Routing errors
    NoMatchingRuleError,
    RoutingRuleNotFoundError,
    # SLA errors
    SLAConfigError,
    # Agent errors
    AgentNotFoundError,
    DuplicateAgentError,
    # Team errors
    DuplicateTeamError,
    TeamMembershipError,
    TeamNotFoundError,
    # Canned response errors
    CannedResponseNotFoundError,
    DuplicateShortcodeError,
    # Knowledge base errors
    DuplicateSlugError,
    KBArticleNotFoundError,
    KBCategoryNotFoundError,
    # CSAT errors
    CSATResponseNotFoundError,
    CSATSurveyNotFoundError,
    InvalidSurveyTokenError,
    # Tag errors
    DuplicateTagError,
    TagNotFoundError,
    # Escalation errors
    EscalationPolicyNotFoundError,
    EscalationLevelNotFoundError,
    DuplicatePolicyError,
    # Queue errors
    QueueNotFoundError,
    DuplicateQueueError,
    # Settings errors
    SettingsNotFoundError,
    # Custom field errors
    CustomFieldNotFoundError,
    DuplicateFieldKeyError,
    # Email template errors
    EmailTemplateNotFoundError,
    DuplicateTemplateTypeError,
)

__all__ = [
    # Core Services
    "TicketService",
    "ConversationService",
    "LegacyConversationService",
    "MessageService",
    "ChannelService",
    "WebhookService",
    "SLAService",
    "RoutingService",
    "AutomationService",
    # Extended Services
    "AgentService",
    "CannedResponseService",
    "KnowledgeBaseService",
    "CSATService",
    "TagService",
    # Additional Services
    "EscalationService",
    "QueueService",
    "SettingsService",
    "CustomFieldService",
    "EmailTemplateService",
    "SupportAnalyticsService",
    # Types - Conversation
    "ConversationFilters",
    "ConversationCreate",
    "ConversationUpdate",
    "ConversationWithMessages",
    "ConversationStats",
    "ConversationBulkUpdate",
    # Types - Message
    "MessageFilters",
    "InboundMessageData",
    "OutboundMessageData",
    "InternalNoteData",
    "AttachmentData",
    # Types - Channel
    "ChannelCreate",
    "ChannelUpdate",
    "DeliveryResult",
    "ConnectionTestResult",
    # Types - Webhook
    "WebhookResult",
    "WebhookEventData",
    # Types - Routing
    "RoutingRuleCreate",
    "RoutingRuleUpdate",
    "RoutingMatch",
    "TicketRoutingRuleCreate",
    "TicketRoutingRuleUpdate",
    # Types - SLA
    "BusinessCalendarCreate",
    "BusinessCalendarUpdate",
    "HolidayCreate",
    "SLABreachFilters",
    "SLABreachInfo",
    "SLABreachSummary",
    "SLADueDates",
    "SLAPolicyCreate",
    "SLAPolicyUpdate",
    "SLATargetCreate",
    "SLATargetUpdate",
    # Types - Stats
    "InboxStats",
    # Types - Bulk
    "BulkOperationResult",
    # Types - Agent
    "AgentFilters",
    "AgentCreate",
    "AgentUpdate",
    "TeamCreate",
    "TeamUpdate",
    "AgentWorkload",
    "AgentDetailStats",
    "AgentDetailResult",
    "TeamWorkload",
    # Types - Canned Response
    "CannedResponseCreate",
    "CannedResponseUpdate",
    "CannedResponseFilters",
    "CannedResponseStats",
    "CannedListResult",
    # Types - Knowledge Base
    "KBArticleFilters",
    "KBArticleStats",
    "KBCategoryCreate",
    "KBCategoryUpdate",
    "KBArticleCreate",
    "KBArticleUpdate",
    "KBAttachmentData",
    "KBHelpfulnessStats",
    "KBListResult",
    # Types - CSAT
    "CSATSurveyCreate",
    "CSATSurveyUpdate",
    "CSATMetrics",
    # Types - Tag
    "TagCreate",
    "TagUpdate",
    # Types - Escalation
    "EscalationPolicyCreate",
    "EscalationPolicyUpdate",
    "EscalationLevelCreate",
    "EscalationLevelUpdate",
    "EscalationResult",
    # Types - Queue
    "QueueCreate",
    "QueueUpdate",
    # Types - Settings
    "SupportSettingsUpdate",
    # Types - Custom Field
    "CustomFieldCreate",
    "CustomFieldUpdate",
    # Types - Email Template
    "EmailTemplateCreate",
    "EmailTemplateUpdate",
    # Types - Analytics
    "AnalyticsFilters",
    "OverviewStats",
    "VolumeDataPoint",
    "VolumeTrend",
    "ResolutionTimeStats",
    "FirstResponseStats",
    "AgentPerformance",
    "TeamPerformance",
    "ChannelStats",
    "CategoryStats",
    "SLAPerformance",
    "BacklogAging",
    "ReopenAnalysis",
    "PatternInsights",
    "AutomationEffectiveness",
    "KBDeflection",
    "E2EReport",
    # Errors - Base
    "ServiceError",
    "NotFoundError",
    "ValidationError",
    "ConflictError",
    "ForbiddenError",
    # Errors - Conversation
    "ConversationNotFoundError",
    "ConversationClosedError",
    "ConversationAssignmentError",
    # Errors - Message
    "MessageNotFoundError",
    "MessageDeliveryError",
    "DuplicateMessageError",
    # Errors - Channel
    "ChannelNotFoundError",
    "ChannelInactiveError",
    "ChannelConfigError",
    # Errors - Webhook
    "WebhookValidationError",
    "WebhookProcessingError",
    "DuplicateWebhookError",
    # Errors - Routing
    "RoutingRuleNotFoundError",
    "NoMatchingRuleError",
    # Errors - SLA
    "SLAConfigError",
    # Errors - Agent
    "AgentNotFoundError",
    "DuplicateAgentError",
    # Errors - Team
    "TeamNotFoundError",
    "DuplicateTeamError",
    "TeamMembershipError",
    # Errors - Canned Response
    "CannedResponseNotFoundError",
    "DuplicateShortcodeError",
    # Errors - Knowledge Base
    "KBCategoryNotFoundError",
    "KBArticleNotFoundError",
    "DuplicateSlugError",
    # Errors - CSAT
    "CSATSurveyNotFoundError",
    "CSATResponseNotFoundError",
    "InvalidSurveyTokenError",
    # Errors - Tag
    "TagNotFoundError",
    "DuplicateTagError",
    # Errors - Escalation
    "EscalationPolicyNotFoundError",
    "EscalationLevelNotFoundError",
    "DuplicatePolicyError",
    # Errors - Queue
    "QueueNotFoundError",
    "DuplicateQueueError",
    # Errors - Settings
    "SettingsNotFoundError",
    # Errors - Custom Field
    "CustomFieldNotFoundError",
    "DuplicateFieldKeyError",
    # Errors - Email Template
    "EmailTemplateNotFoundError",
    "DuplicateTemplateTypeError",
]
