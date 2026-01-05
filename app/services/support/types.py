"""Type definitions for support services.

These dataclasses define the contract for support operations including:
- Conversations (OmniConversation)
- Messages (OmniMessage)
- Channels (OmniChannel)
- Contacts (InboxContact, Party resolution)
- Webhooks (ingest, delivery)
- Routing and automation

They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.omni import ConversationPriority, ConversationStatus, OmniChannelType

__all__ = [
    # Conversation types
    "ConversationFilters",
    "ConversationCreate",
    "ConversationUpdate",
    "ConversationWithMessages",
    # Message types
    "MessageFilters",
    "InboundMessageData",
    "OutboundMessageData",
    "InternalNoteData",
    "AttachmentData",
    # Channel types
    "ChannelCreate",
    "ChannelUpdate",
    "DeliveryResult",
    "ConnectionTestResult",
    # Webhook types
    "WebhookResult",
    "WebhookEventData",
    # Routing types
    "RoutingRuleCreate",
    "RoutingRuleUpdate",
    "RoutingMatch",
    "TicketRoutingRuleCreate",
    "TicketRoutingRuleUpdate",
    "AgentWorkload",
    "QueueHealth",
    # SLA types
    "SLADueDates",
    "SLABreachInfo",
    "BusinessCalendarCreate",
    "BusinessCalendarUpdate",
    "HolidayCreate",
    "SLAPolicyCreate",
    "SLAPolicyUpdate",
    "SLATargetCreate",
    "SLATargetUpdate",
    "SLABreachFilters",
    "SLABreachSummary",
    # Stats types
    "InboxStats",
    "ConversationStats",
    # Bulk operations
    "ConversationBulkUpdate",
    "BulkOperationResult",
    # Agent types
    "AgentFilters",
    "AgentCreate",
    "AgentUpdate",
    "TeamCreate",
    "TeamUpdate",
    "AgentWorkload",
    "TeamWorkload",
    "AgentDetailStats",
    "AgentDetailResult",
    # Canned response types
    "CannedResponseCreate",
    "CannedResponseUpdate",
    "CannedResponseFilters",
    "CannedResponseStats",
    "CannedListResult",
    # Knowledge base types
    "KBCategoryCreate",
    "KBCategoryUpdate",
    "KBArticleCreate",
    "KBArticleUpdate",
    "KBAttachmentData",
    "KBHelpfulnessStats",
    # CSAT types
    "CSATSurveyCreate",
    "CSATSurveyUpdate",
    "CSATMetrics",
    # Tag types
    "TagCreate",
    "TagUpdate",
    # Escalation types
    "EscalationPolicyCreate",
    "EscalationPolicyUpdate",
    "EscalationLevelCreate",
    "EscalationLevelUpdate",
    "EscalationResult",
    # Queue types
    "QueueCreate",
    "QueueUpdate",
    # Settings types
    "SupportSettingsUpdate",
    # Custom field types
    "CustomFieldCreate",
    "CustomFieldUpdate",
    # Email template types
    "EmailTemplateCreate",
    "EmailTemplateUpdate",
    # Tag analytics types
    "TagStats",
    "TagTrend",
    # Enhanced SLA analytics types
    "AgentSLAStats",
    "TeamSLAStats",
    "NearMissTicket",
    "SLATrendPoint",
    "CategorySLAStats",
    "PrioritySLAStats",
    "SLAAnalyticsSummary",
]


# ==============================================================================
# Conversation Types
# ==============================================================================


@dataclass
class ConversationFilters:
    """Filters for listing conversations."""

    status: Optional[ConversationStatus] = None
    statuses: List[str] = field(default_factory=list)
    priority: Optional[ConversationPriority] = None
    channel_id: Optional[int] = None
    channel_type: Optional[str] = None
    assigned_agent_id: Optional[int] = None
    assigned_team_id: Optional[int] = None
    unassigned_only: bool = False
    starred_only: bool = False
    has_unread: bool = False
    party_id: Optional[int] = None
    ticket_id: Optional[int] = None
    search: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


@dataclass
class ConversationCreate:
    """Data for creating a conversation."""

    channel_id: int
    subject: Optional[str] = None
    external_thread_id: Optional[str] = None
    status: str = "open"
    priority: str = "medium"
    party_id: Optional[int] = None
    ticket_id: Optional[int] = None
    lead_id: Optional[int] = None
    assigned_agent_id: Optional[int] = None
    assigned_team_id: Optional[int] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_company: Optional[str] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class ConversationUpdate:
    """Data for updating a conversation (all fields optional)."""

    subject: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_agent_id: Optional[int] = None
    assigned_team_id: Optional[int] = None
    is_starred: Optional[bool] = None
    tags: Optional[List[str]] = None
    party_id: Optional[int] = None
    ticket_id: Optional[int] = None
    lead_id: Optional[int] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_company: Optional[str] = None
    snoozed_until: Optional[datetime] = None


@dataclass
class ConversationWithMessages:
    """Conversation with preloaded messages."""

    conversation: Any  # OmniConversation
    messages: List[Any] = field(default_factory=list)  # List[OmniMessage]
    total_messages: int = 0
    has_more: bool = False


# ==============================================================================
# Message Types
# ==============================================================================


@dataclass
class MessageFilters:
    """Filters for listing messages."""

    conversation_id: Optional[int] = None
    direction: Optional[str] = None  # inbound, outbound
    message_type: Optional[str] = None
    before: Optional[datetime] = None
    after: Optional[datetime] = None
    limit: int = 50


@dataclass
class InboundMessageData:
    """Data for creating an inbound message (from customer)."""

    conversation_id: int
    body: str
    participant_id: Optional[int] = None
    channel_id: Optional[int] = None
    subject: Optional[str] = None
    message_type: Optional[str] = None
    provider_message_id: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    attachments: List["AttachmentData"] = field(default_factory=list)
    sent_at: Optional[datetime] = None


@dataclass
class OutboundMessageData:
    """Data for creating an outbound message (from agent)."""

    conversation_id: int
    body: str
    agent_id: Optional[int] = None
    channel_id: Optional[int] = None
    subject: Optional[str] = None
    message_type: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    attachments: List["AttachmentData"] = field(default_factory=list)


@dataclass
class InternalNoteData:
    """Data for creating an internal note (not visible to customer)."""

    conversation_id: int
    body: str
    agent_id: int
    mentioned_agent_ids: List[int] = field(default_factory=list)


@dataclass
class AttachmentData:
    """Data for creating/referencing an attachment."""

    filename: Optional[str] = None
    url: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    meta: Dict[str, Any] = field(default_factory=dict)


# ==============================================================================
# Channel Types
# ==============================================================================


@dataclass
class ChannelCreate:
    """Data for creating a channel."""

    name: str
    type: str  # OmniChannelType value
    config: Dict[str, Any] = field(default_factory=dict)
    webhook_secret: Optional[str] = None
    is_active: bool = True
    chatwoot_inbox_id: Optional[int] = None


@dataclass
class ChannelUpdate:
    """Data for updating a channel (all fields optional)."""

    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    webhook_secret: Optional[str] = None
    is_active: Optional[bool] = None
    chatwoot_inbox_id: Optional[int] = None


@dataclass
class DeliveryResult:
    """Result of attempting to deliver a message via a channel."""

    success: bool
    provider_message_id: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    delivered_at: Optional[datetime] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectionTestResult:
    """Result of testing channel connection."""

    success: bool
    message: str = ""
    latency_ms: Optional[int] = None
    details: Dict[str, Any] = field(default_factory=dict)


# ==============================================================================
# Webhook Types
# ==============================================================================


@dataclass
class WebhookResult:
    """Result of processing a webhook."""

    success: bool
    event_id: Optional[int] = None  # OmniWebhookEvent.id
    conversation_id: Optional[int] = None
    message_id: Optional[int] = None
    error: Optional[str] = None
    is_duplicate: bool = False
    action_taken: Optional[str] = None  # created_message, updated_status, etc.


@dataclass
class WebhookEventData:
    """Data for recording a webhook event."""

    channel_id: int
    provider_event_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, Any] = field(default_factory=dict)
    processed: bool = False
    error: Optional[str] = None


# ==============================================================================
# Routing Types
# ==============================================================================


@dataclass
class RoutingRuleCreate:
    """Data for creating a routing rule."""

    name: str
    conditions: List[Dict[str, Any]]  # [{"type": "channel", "value": "email"}, ...]
    action_type: str  # assign_agent, assign_team, add_tag, create_ticket
    action_value: Optional[str] = None
    action_config: Dict[str, Any] = field(default_factory=dict)
    description: Optional[str] = None
    priority: int = 0
    is_active: bool = True


@dataclass
class RoutingRuleUpdate:
    """Data for updating a routing rule (all fields optional)."""

    name: Optional[str] = None
    description: Optional[str] = None
    conditions: Optional[List[Dict[str, Any]]] = None
    action_type: Optional[str] = None
    action_value: Optional[str] = None
    action_config: Optional[Dict[str, Any]] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


@dataclass
class RoutingMatch:
    """Result of matching a routing rule."""

    rule_id: int
    rule_name: str
    action_type: str
    action_value: Optional[str] = None
    action_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TicketRoutingRuleCreate:
    """Data for creating a ticket routing rule (RoutingRule model)."""

    name: str
    team_id: Optional[int] = None
    strategy: str = "round_robin"
    conditions: Optional[List[Dict[str, Any]]] = None
    description: Optional[str] = None
    priority: int = 100
    is_active: bool = True
    fallback_team_id: Optional[int] = None


@dataclass
class TicketRoutingRuleUpdate:
    """Data for updating a ticket routing rule (all fields optional)."""

    name: Optional[str] = None
    description: Optional[str] = None
    team_id: Optional[int] = None
    strategy: Optional[str] = None
    conditions: Optional[List[Dict[str, Any]]] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    fallback_team_id: Optional[int] = None


@dataclass
class AgentWorkload:
    """Agent workload statistics."""

    agent_id: int
    agent_name: str
    open_tickets: int
    capacity: int
    utilization_pct: float


@dataclass
class QueueHealth:
    """Queue health metrics."""

    total_open: int
    by_status: Dict[str, int]
    avg_wait_minutes: float
    agents_active: int
    agents_at_capacity: int


# ==============================================================================
# Automation Types
# ==============================================================================


@dataclass
class AutomationRuleCreate:
    """Data for creating an automation rule (database-backed)."""

    name: str
    trigger: str
    actions: List[Dict[str, Any]]
    description: Optional[str] = None
    conditions: Optional[List[Dict[str, Any]]] = None
    is_active: bool = True
    priority: int = 100
    stop_processing: bool = False
    max_executions_per_hour: Optional[int] = None


@dataclass
class AutomationRuleUpdate:
    """Data for updating an automation rule (all fields optional)."""

    name: Optional[str] = None
    description: Optional[str] = None
    trigger: Optional[str] = None
    conditions: Optional[List[Dict[str, Any]]] = None
    actions: Optional[List[Dict[str, Any]]] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None
    stop_processing: Optional[bool] = None
    max_executions_per_hour: Optional[int] = None


@dataclass
class AutomationLogFilters:
    """Filters for listing automation logs."""

    rule_id: Optional[int] = None
    ticket_id: Optional[int] = None
    trigger: Optional[str] = None
    success: Optional[bool] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


@dataclass
class AutomationLogSummary:
    """Summary statistics for automation logs."""

    total_executions: int
    successful: int
    failed: int
    by_trigger: Dict[str, int]
    by_rule: Dict[str, int]


# ==============================================================================
# SLA Types
# ==============================================================================


@dataclass
class SLADueDates:
    """Calculated SLA due dates."""

    first_response_due: Optional[datetime] = None
    resolution_due: Optional[datetime] = None
    next_response_due: Optional[datetime] = None


@dataclass
class SLABreachInfo:
    """Information about an SLA breach."""

    breached: bool = False
    breach_type: Optional[str] = None  # first_response, resolution, next_response
    breached_at: Optional[datetime] = None
    overdue_by_minutes: Optional[int] = None


@dataclass
class BusinessCalendarCreate:
    """Data for creating a business calendar."""

    name: str
    calendar_type: str = "standard"  # standard, 24x7, custom
    timezone: str = "UTC"
    schedule: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    is_default: bool = False


@dataclass
class BusinessCalendarUpdate:
    """Data for updating a business calendar."""

    name: Optional[str] = None
    description: Optional[str] = None
    calendar_type: Optional[str] = None
    timezone: Optional[str] = None
    schedule: Optional[Dict[str, Any]] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


@dataclass
class HolidayCreate:
    """Data for creating a holiday."""

    name: str
    holiday_date: datetime  # Date of the holiday
    is_recurring: bool = False


@dataclass
class SLAPolicyCreate:
    """Data for creating an SLA policy."""

    name: str
    calendar_id: Optional[int] = None
    description: Optional[str] = None
    conditions: Optional[List[Dict[str, Any]]] = None
    is_default: bool = False
    priority: int = 100


@dataclass
class SLAPolicyUpdate:
    """Data for updating an SLA policy."""

    name: Optional[str] = None
    description: Optional[str] = None
    calendar_id: Optional[int] = None
    conditions: Optional[List[Dict[str, Any]]] = None
    is_default: Optional[bool] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


@dataclass
class SLATargetCreate:
    """Data for creating an SLA target."""

    target_type: str  # first_response, resolution, next_response
    target_hours: float
    priority: Optional[str] = None  # low, medium, high, urgent (None = all)
    warning_threshold_pct: int = 80


@dataclass
class SLATargetUpdate:
    """Data for updating an SLA target."""

    target_type: Optional[str] = None
    priority: Optional[str] = None
    target_hours: Optional[float] = None
    warning_threshold_pct: Optional[int] = None


@dataclass
class SLABreachFilters:
    """Filters for listing SLA breaches."""

    ticket_id: Optional[int] = None
    policy_id: Optional[int] = None
    target_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


@dataclass
class SLABreachSummary:
    """Summary statistics for SLA breaches."""

    total_breaches: int
    by_target_type: Dict[str, int]
    by_policy: Dict[str, int]
    avg_overdue_hours: float


# ==============================================================================
# Stats Types
# ==============================================================================


@dataclass
class InboxStats:
    """Overall inbox statistics."""

    total_conversations: int = 0
    open_conversations: int = 0
    pending_conversations: int = 0
    resolved_conversations: int = 0
    unassigned_conversations: int = 0
    my_conversations: int = 0
    unread_conversations: int = 0
    snoozed_conversations: int = 0
    avg_first_response_time_minutes: Optional[float] = None
    avg_resolution_time_minutes: Optional[float] = None


@dataclass
class ConversationStats:
    """Stats for a single conversation."""

    message_count: int = 0
    inbound_count: int = 0
    outbound_count: int = 0
    unread_count: int = 0
    first_response_time_minutes: Optional[float] = None
    time_to_resolution_minutes: Optional[float] = None


# ==============================================================================
# Bulk Operations
# ==============================================================================


@dataclass
class ConversationBulkUpdate:
    """Data for bulk updating conversations."""

    ids: List[int] = field(default_factory=list)
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_agent_id: Optional[int] = None
    assigned_team_id: Optional[int] = None
    add_tags: List[str] = field(default_factory=list)
    remove_tags: List[str] = field(default_factory=list)


@dataclass
class BulkOperationResult:
    """Result of a bulk operation."""

    updated_count: int = 0
    failed_count: int = 0
    failed_ids: List[int] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# ==============================================================================
# Agent Types
# ==============================================================================


@dataclass
class AgentFilters:
    """Filters for listing agents."""

    is_active: Optional[bool] = None
    domain: Optional[str] = None
    team_id: Optional[int] = None
    skill: Optional[str] = None
    search: Optional[str] = None


@dataclass
class AgentCreate:
    """Data for creating an agent."""

    email: str
    display_name: str
    employee_id: Optional[int] = None
    domains: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    capacity: int = 10
    routing_weight: int = 1
    channel_caps: Dict[str, bool] = field(default_factory=dict)


@dataclass
class AgentUpdate:
    """Data for updating an agent (all fields optional)."""

    display_name: Optional[str] = None
    domains: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    capacity: Optional[int] = None
    routing_weight: Optional[int] = None
    channel_caps: Optional[Dict[str, bool]] = None
    is_active: Optional[bool] = None


@dataclass
class TeamCreate:
    """Data for creating a team."""

    name: str
    description: Optional[str] = None
    domain: str = "support"
    assignment_rule: str = "round_robin"


@dataclass
class TeamUpdate:
    """Data for updating a team (all fields optional)."""

    name: Optional[str] = None
    description: Optional[str] = None
    domain: Optional[str] = None
    assignment_rule: Optional[str] = None
    is_active: Optional[bool] = None


@dataclass
class AgentWorkload:
    """Agent workload information."""

    agent_id: int
    open_tickets: int = 0
    open_conversations: int = 0
    total_active: int = 0
    capacity: int = 10
    utilization_pct: float = 0.0


@dataclass
class TeamWorkload:
    """Team workload information."""

    team_id: int
    total_open: int = 0
    total_agents: int = 0
    available_agents: int = 0
    avg_utilization_pct: float = 0.0


@dataclass
class AgentDetailStats:
    """Statistics for agent detail page."""

    open_tickets: int = 0
    resolved_today: int = 0
    team_count: int = 0
    avg_resolution_hours: Optional[float] = None
    csat_score: Optional[float] = None


@dataclass
class AgentDetailResult:
    """Combined result for agent detail page.

    After Agent → Party unification, 'agent' is now a Party instance
    with PartyRole(role="support_agent").
    """

    agent: Any  # Party model (with support_agent role)
    employee: Optional[Any] = None  # Employee model if linked via party_id
    stats: AgentDetailStats = field(default_factory=AgentDetailStats)
    team_memberships: List[Any] = field(default_factory=list)  # List of TeamMember
    recent_tickets: List[Any] = field(default_factory=list)  # List of UnifiedTicket


# ==============================================================================
# Canned Response Types
# ==============================================================================


@dataclass
class CannedResponseCreate:
    """Data for creating a canned response."""

    name: str
    content: str
    shortcode: Optional[str] = None
    scope: str = "personal"  # personal, team, global
    team_id: Optional[int] = None
    agent_id: Optional[int] = None
    category: Optional[str] = None


@dataclass
class CannedResponseUpdate:
    """Data for updating a canned response (all fields optional)."""

    name: Optional[str] = None
    content: Optional[str] = None
    shortcode: Optional[str] = None
    scope: Optional[str] = None
    team_id: Optional[int] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None


@dataclass
class CannedResponseFilters:
    """Filters for canned response list queries."""

    search: Optional[str] = None
    scope: Optional[str] = None  # personal, team, global
    team_id: Optional[int] = None
    category: Optional[str] = None
    active_only: bool = True


@dataclass
class CannedResponseStats:
    """Statistics for canned responses."""

    total: int = 0
    personal_count: int = 0
    team_count: int = 0
    global_count: int = 0


@dataclass
class CannedListResult:
    """Combined result for canned response list page."""

    items: List[Any]  # List of CannedResponse
    total: int
    stats: CannedResponseStats


# ==============================================================================
# Knowledge Base Types
# ==============================================================================


@dataclass
class KBCategoryCreate:
    """Data for creating a KB category."""

    name: str
    slug: Optional[str] = None  # Auto-generated if not provided
    description: Optional[str] = None
    icon: Optional[str] = None
    parent_id: Optional[int] = None
    visibility: str = "public"  # public, internal, restricted


@dataclass
class KBCategoryUpdate:
    """Data for updating a KB category (all fields optional)."""

    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    parent_id: Optional[int] = None
    visibility: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


@dataclass
class KBArticleCreate:
    """Data for creating a KB article."""

    title: str
    content: str
    category_id: Optional[int] = None
    slug: Optional[str] = None
    excerpt: Optional[str] = None
    visibility: str = "public"
    search_keywords: Optional[str] = None
    related_article_ids: List[int] = field(default_factory=list)
    team_ids: List[int] = field(default_factory=list)


@dataclass
class KBArticleUpdate:
    """Data for updating a KB article (all fields optional)."""

    title: Optional[str] = None
    content: Optional[str] = None
    category_id: Optional[int] = None
    slug: Optional[str] = None
    excerpt: Optional[str] = None
    visibility: Optional[str] = None
    search_keywords: Optional[str] = None
    related_article_ids: Optional[List[int]] = None
    team_ids: Optional[List[int]] = None


@dataclass
class KBAttachmentData:
    """Data for creating a KB article attachment."""

    filename: str
    url: str
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None


@dataclass
class KBHelpfulnessStats:
    """Helpfulness stats for a KB article."""

    article_id: int
    helpful_count: int = 0
    not_helpful_count: int = 0
    total_count: int = 0
    helpful_pct: float = 0.0


@dataclass
class KBArticleFilters:
    """Filters for listing KB articles."""

    search: Optional[str] = None
    status: Optional[str] = None  # draft, published, archived
    category_id: Optional[int] = None
    visibility: Optional[str] = None  # public, internal, restricted


@dataclass
class KBArticleStats:
    """Aggregate statistics for KB articles."""

    published_count: int = 0
    draft_count: int = 0
    archived_count: int = 0
    total_views: int = 0


@dataclass
class KBCategoryWithCount:
    """Category with article count."""

    category: Any  # KBCategory
    article_count: int = 0


@dataclass
class KBListResult:
    """Result of listing KB articles with stats."""

    items: List[Any]  # List[KBArticle]
    total: int
    stats: KBArticleStats
    categories: List[Any] = field(default_factory=list)  # List[KBCategory]
    category_counts: Dict[int, int] = field(default_factory=dict)


# ==============================================================================
# CSAT Types
# ==============================================================================


@dataclass
class CSATSurveyCreate:
    """Data for creating a CSAT survey."""

    name: str
    survey_type: str = "csat"  # csat, nps, ces
    trigger: str = "ticket_resolved"  # ticket_resolved, ticket_closed, manual
    questions: List[Dict[str, Any]] = field(default_factory=list)
    delay_hours: int = 0
    send_via: str = "email"  # email, in_app, both
    conditions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CSATSurveyUpdate:
    """Data for updating a CSAT survey (all fields optional)."""

    name: Optional[str] = None
    questions: Optional[List[Dict[str, Any]]] = None
    delay_hours: Optional[int] = None
    send_via: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


@dataclass
class CSATMetrics:
    """CSAT survey metrics."""

    survey_id: int
    total_sent: int = 0
    total_responded: int = 0
    response_rate: float = 0.0
    avg_rating: float = 0.0
    score: float = 0.0  # CSAT % or NPS or CES avg
    rating_distribution: Dict[int, int] = field(default_factory=dict)


# ==============================================================================
# Tag Types
# ==============================================================================


@dataclass
class TagCreate:
    """Data for creating a ticket tag."""

    name: str
    color: Optional[str] = None
    description: Optional[str] = None


@dataclass
class TagUpdate:
    """Data for updating a ticket tag (all fields optional)."""

    name: Optional[str] = None
    color: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


# ==============================================================================
# Escalation Types
# ==============================================================================


@dataclass
class EscalationPolicyCreate:
    """Data for creating an escalation policy."""

    name: str
    description: Optional[str] = None
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    priority: int = 100  # Lower = higher priority


@dataclass
class EscalationPolicyUpdate:
    """Data for updating an escalation policy (all fields optional)."""

    name: Optional[str] = None
    description: Optional[str] = None
    conditions: Optional[List[Dict[str, Any]]] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


@dataclass
class EscalationLevelCreate:
    """Data for creating an escalation level."""

    level: int
    trigger: str = "sla_breach"  # sla_breach, sla_warning, idle_time, customer_escalation, reopen_count
    trigger_hours: int = 0
    escalate_to_team_id: Optional[int] = None
    escalate_to_user_id: Optional[int] = None
    notify_current_assignee: bool = True
    notify_team_lead: bool = True
    reassign_ticket: bool = False
    change_priority: bool = False
    new_priority: Optional[str] = None
    notification_template: Optional[str] = None


@dataclass
class EscalationLevelUpdate:
    """Data for updating an escalation level (all fields optional)."""

    trigger: Optional[str] = None
    trigger_hours: Optional[int] = None
    escalate_to_team_id: Optional[int] = None
    escalate_to_user_id: Optional[int] = None
    notify_current_assignee: Optional[bool] = None
    notify_team_lead: Optional[bool] = None
    reassign_ticket: Optional[bool] = None
    change_priority: Optional[bool] = None
    new_priority: Optional[str] = None
    notification_template: Optional[str] = None


@dataclass
class EscalationResult:
    """Result of an escalation execution."""

    escalated: bool = False
    policy_id: Optional[int] = None
    level: int = 0
    actions_taken: List[str] = field(default_factory=list)
    notifications_sent: List[str] = field(default_factory=list)
    error: Optional[str] = None


# ==============================================================================
# Queue Types
# ==============================================================================


@dataclass
class QueueCreate:
    """Data for creating a support queue."""

    name: str
    description: Optional[str] = None
    queue_type: str = "custom"  # system, custom
    filters: List[Dict[str, Any]] = field(default_factory=list)
    sort_by: str = "created_at"
    sort_direction: str = "desc"
    is_public: bool = True
    owner_id: Optional[int] = None
    icon: Optional[str] = None
    color: Optional[str] = None


@dataclass
class QueueUpdate:
    """Data for updating a support queue (all fields optional)."""

    name: Optional[str] = None
    description: Optional[str] = None
    filters: Optional[List[Dict[str, Any]]] = None
    sort_by: Optional[str] = None
    sort_direction: Optional[str] = None
    is_public: Optional[bool] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


# ==============================================================================
# Settings Types
# ==============================================================================


@dataclass
class SupportSettingsUpdate:
    """Data for updating support settings (all fields optional).

    This dataclass covers ALL configurable settings in the SupportSettings model.
    """

    # -------------------------------------------------------------------------
    # Business Hours
    # -------------------------------------------------------------------------
    working_hours_type: Optional[str] = None  # STANDARD, EXTENDED, ROUND_THE_CLOCK, CUSTOM
    timezone: Optional[str] = None
    weekly_schedule: Optional[Dict[str, Any]] = None  # {"MONDAY": {"start": "09:00", "end": "17:00", "closed": false}, ...}
    holiday_calendar_id: Optional[int] = None

    # -------------------------------------------------------------------------
    # SLA Defaults
    # -------------------------------------------------------------------------
    default_sla_policy_id: Optional[int] = None
    sla_warning_threshold_percent: Optional[int] = None  # Warn at X% of target (default 80)
    sla_include_holidays: Optional[bool] = None
    sla_include_weekends: Optional[bool] = None
    default_first_response_hours: Optional[float] = None
    default_resolution_hours: Optional[float] = None

    # -------------------------------------------------------------------------
    # Ticket Routing
    # -------------------------------------------------------------------------
    default_routing_strategy: Optional[str] = None  # ROUND_ROBIN, LEAST_BUSY, SKILL_BASED, LOAD_BALANCED, MANUAL
    default_team_id: Optional[int] = None
    fallback_team_id: Optional[int] = None
    auto_assign_enabled: Optional[bool] = None
    max_tickets_per_agent: Optional[int] = None
    rebalance_threshold_percent: Optional[int] = None  # Rebalance if agent exceeds avg by X%

    # -------------------------------------------------------------------------
    # Ticket Defaults
    # -------------------------------------------------------------------------
    default_priority: Optional[str] = None  # LOW, MEDIUM, HIGH, URGENT
    default_ticket_type: Optional[str] = None
    allow_customer_priority_selection: Optional[bool] = None
    allow_customer_team_selection: Optional[bool] = None

    # -------------------------------------------------------------------------
    # Auto-Close Settings
    # -------------------------------------------------------------------------
    auto_close_enabled: Optional[bool] = None
    auto_close_resolved_days: Optional[int] = None  # Days after resolved
    auto_close_action: Optional[str] = None  # CLOSE, ARCHIVE, NOTIFY_ONLY
    auto_close_notify_customer: Optional[bool] = None
    allow_customer_reopen: Optional[bool] = None
    reopen_window_days: Optional[int] = None  # Days after close customer can reopen
    max_reopens_allowed: Optional[int] = None

    # -------------------------------------------------------------------------
    # Escalation Defaults
    # -------------------------------------------------------------------------
    escalation_enabled: Optional[bool] = None
    default_escalation_team_id: Optional[int] = None
    escalation_notify_manager: Optional[bool] = None
    idle_escalation_enabled: Optional[bool] = None
    idle_hours_before_escalation: Optional[int] = None
    reopen_escalation_enabled: Optional[bool] = None
    reopen_count_for_escalation: Optional[int] = None

    # -------------------------------------------------------------------------
    # CSAT / Customer Feedback
    # -------------------------------------------------------------------------
    csat_enabled: Optional[bool] = None
    csat_survey_trigger: Optional[str] = None  # ON_RESOLVE, ON_CLOSE, MANUAL, DISABLED
    csat_delay_hours: Optional[int] = None  # Hours after trigger before sending
    csat_reminder_enabled: Optional[bool] = None
    csat_reminder_days: Optional[int] = None
    csat_survey_expiry_days: Optional[int] = None
    default_csat_survey_id: Optional[int] = None

    # -------------------------------------------------------------------------
    # Customer Portal
    # -------------------------------------------------------------------------
    portal_enabled: Optional[bool] = None
    portal_ticket_creation_enabled: Optional[bool] = None
    portal_show_ticket_history: Optional[bool] = None
    portal_show_knowledge_base: Optional[bool] = None
    portal_show_faq: Optional[bool] = None
    portal_require_login: Optional[bool] = None

    # -------------------------------------------------------------------------
    # Knowledge Base
    # -------------------------------------------------------------------------
    kb_enabled: Optional[bool] = None
    kb_public_access: Optional[bool] = None
    kb_suggest_articles_on_create: Optional[bool] = None
    kb_track_article_helpfulness: Optional[bool] = None

    # -------------------------------------------------------------------------
    # Notifications
    # -------------------------------------------------------------------------
    notification_channels: Optional[List[str]] = None  # ["EMAIL", "IN_APP", "SMS", "SLACK", "WEBHOOK"]
    notification_events: Optional[Dict[str, bool]] = None  # {"ticket_created": true, ...}
    notify_assigned_agent: Optional[bool] = None
    notify_team_on_unassigned: Optional[bool] = None
    notify_customer_on_status_change: Optional[bool] = None
    notify_customer_on_reply: Optional[bool] = None

    # -------------------------------------------------------------------------
    # Queue Management
    # -------------------------------------------------------------------------
    unassigned_warning_minutes: Optional[int] = None  # Warn if unassigned > X mins
    overdue_highlight_enabled: Optional[bool] = None
    queue_refresh_seconds: Optional[int] = None  # Auto-refresh interval

    # -------------------------------------------------------------------------
    # Integrations
    # -------------------------------------------------------------------------
    email_to_ticket_enabled: Optional[bool] = None
    email_reply_to_address: Optional[str] = None
    sync_to_erpnext: Optional[bool] = None
    sync_to_splynx: Optional[bool] = None
    sync_to_chatwoot: Optional[bool] = None

    # -------------------------------------------------------------------------
    # Data Retention
    # -------------------------------------------------------------------------
    archive_closed_tickets_days: Optional[int] = None  # Archive after X days
    delete_archived_tickets_days: Optional[int] = None  # 0 = never delete

    # -------------------------------------------------------------------------
    # Display & Formatting
    # -------------------------------------------------------------------------
    ticket_id_prefix: Optional[str] = None
    ticket_id_min_digits: Optional[int] = None
    date_format: Optional[str] = None
    time_format: Optional[str] = None


# ==============================================================================
# Custom Field Types
# ==============================================================================


@dataclass
class CustomFieldCreate:
    """Data for creating a custom ticket field."""

    name: str
    field_key: str
    field_type: str = "text"  # text, number, dropdown, multi_select, date, datetime, checkbox, url, email
    description: Optional[str] = None
    options: Optional[List[Dict[str, str]]] = None  # For dropdown/multi_select
    default_value: Optional[str] = None
    is_required: bool = False
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    validation_regex: Optional[str] = None
    display_order: int = 100
    show_in_list: bool = False
    show_in_create_form: bool = True
    show_in_customer_portal: bool = False
    applies_to_types: Optional[List[str]] = None


@dataclass
class CustomFieldUpdate:
    """Data for updating a custom ticket field (all fields optional)."""

    name: Optional[str] = None
    description: Optional[str] = None
    options: Optional[List[Dict[str, str]]] = None
    default_value: Optional[str] = None
    is_required: Optional[bool] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    validation_regex: Optional[str] = None
    display_order: Optional[int] = None
    show_in_list: Optional[bool] = None
    show_in_create_form: Optional[bool] = None
    show_in_customer_portal: Optional[bool] = None
    applies_to_types: Optional[List[str]] = None
    is_active: Optional[bool] = None


# ==============================================================================
# Email Template Types
# ==============================================================================


@dataclass
class EmailTemplateCreate:
    """Data for creating an email template."""

    name: str
    template_type: str  # ticket_created, ticket_replied, sla_warning, etc.
    subject: str
    body_html: str
    body_text: Optional[str] = None


@dataclass
class EmailTemplateUpdate:
    """Data for updating an email template (all fields optional)."""

    name: Optional[str] = None
    subject: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    is_active: Optional[bool] = None


# ==============================================================================
# Analytics Types
# ==============================================================================


@dataclass
class AnalyticsFilters:
    """Filters for analytics queries."""

    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    days: int = 30
    team_id: Optional[int] = None
    agent_id: Optional[int] = None
    channel: Optional[str] = None
    priority: Optional[str] = None
    ticket_type: Optional[str] = None


@dataclass
class OverviewStats:
    """High-level support overview statistics."""

    total_tickets: int
    open_tickets: int
    resolved_tickets: int
    closed_tickets: int
    pending_tickets: int
    avg_resolution_hours: float
    avg_first_response_hours: float
    sla_attainment_pct: float
    csat_score: Optional[float]
    period_days: int


@dataclass
class VolumeDataPoint:
    """Single data point for volume trends."""

    period: str  # YYYY-MM or YYYY-MM-DD
    year: int
    month: int
    day: Optional[int] = None
    total: int = 0
    opened: int = 0
    resolved: int = 0
    closed: int = 0
    reopened: int = 0


@dataclass
class VolumeTrend:
    """Volume trend over time."""

    data: List[VolumeDataPoint]
    total_opened: int
    total_resolved: int
    avg_daily_volume: float
    peak_day: Optional[str]
    peak_volume: int


@dataclass
class ResolutionTimeStats:
    """Resolution time statistics."""

    avg_hours: float
    median_hours: float
    p90_hours: float
    p95_hours: float
    min_hours: float
    max_hours: float
    sample_size: int


@dataclass
class FirstResponseStats:
    """First response time statistics."""

    avg_hours: float
    median_hours: float
    p90_hours: float
    within_sla_pct: float
    sample_size: int


@dataclass
class AgentPerformance:
    """Individual agent performance metrics."""

    agent_id: int
    agent_name: str
    team_id: Optional[int]
    team_name: Optional[str]
    total_tickets: int
    resolved_tickets: int
    resolution_rate: float
    avg_resolution_hours: float
    avg_first_response_hours: float
    sla_attainment_pct: float
    csat_score: Optional[float]
    csat_responses: int
    current_open: int
    capacity: int
    utilization_pct: float


@dataclass
class TeamPerformance:
    """Team performance metrics."""

    team_id: int
    team_name: str
    total_agents: int
    active_agents: int
    total_tickets: int
    resolved_tickets: int
    resolution_rate: float
    avg_resolution_hours: float
    avg_first_response_hours: float
    sla_attainment_pct: float
    csat_score: Optional[float]
    current_open: int
    total_capacity: int
    utilization_pct: float
    top_performers: List[str]


@dataclass
class ChannelStats:
    """Statistics by support channel."""

    channel: str
    total_tickets: int
    resolved_tickets: int
    resolution_rate: float
    avg_resolution_hours: float
    avg_first_response_hours: float
    sla_attainment_pct: float
    pct_of_total: float


@dataclass
class CategoryStats:
    """Statistics by ticket category/type."""

    category: str
    category_type: str  # ticket_type, issue_type, priority
    total_tickets: int
    resolved_tickets: int
    resolution_rate: float
    avg_resolution_hours: float
    pct_of_total: float


@dataclass
class SLAPerformance:
    """SLA performance metrics."""

    period: str
    response_met: int
    response_breached: int
    response_attainment_pct: float
    resolution_met: int
    resolution_breached: int
    resolution_attainment_pct: float
    total_tracked: int


@dataclass
class BacklogAging:
    """Backlog aging analysis."""

    age_bucket: str  # "0-24h", "1-3d", "3-7d", "1-2w", "2-4w", ">1m"
    count: int
    pct_of_backlog: float
    avg_priority: float
    sla_at_risk: int


@dataclass
class ReopenAnalysis:
    """Ticket reopen/rework analysis."""

    total_reopened: int
    reopen_rate: float
    avg_reopens_per_ticket: float
    top_reopen_reasons: List[Dict[str, Any]]
    by_agent: List[Dict[str, Any]]
    by_category: List[Dict[str, Any]]


@dataclass
class PatternInsights:
    """Support pattern insights."""

    peak_hours: List[Dict[str, Any]]  # hour, count
    peak_days: List[Dict[str, Any]]  # day_name, count
    busiest_period: str
    quietest_period: str
    by_region: List[Dict[str, Any]]
    seasonal_factors: List[Dict[str, Any]]


@dataclass
class AutomationEffectiveness:
    """Automation rule effectiveness metrics."""

    total_executions: int
    successful_executions: int
    success_rate: float
    tickets_auto_assigned: int
    tickets_auto_categorized: int
    tickets_auto_responded: int
    avg_time_saved_hours: float
    top_rules: List[Dict[str, Any]]


@dataclass
class KBDeflection:
    """Knowledge base deflection metrics."""

    total_article_views: int
    helpful_votes: int
    not_helpful_votes: int
    helpfulness_rate: float
    estimated_deflections: int
    deflection_rate: float
    top_articles: List[Dict[str, Any]]
    search_no_results: int


@dataclass
class E2EReport:
    """End-to-end comprehensive support report."""

    report_period: str
    generated_at: datetime
    overview: OverviewStats
    volume_trend: VolumeTrend
    resolution_stats: ResolutionTimeStats
    first_response_stats: FirstResponseStats
    sla_performance: List[SLAPerformance]
    agent_performance: List[AgentPerformance]
    team_performance: List[TeamPerformance]
    channel_breakdown: List[ChannelStats]
    category_breakdown: List[CategoryStats]
    backlog_aging: List[BacklogAging]
    reopen_analysis: ReopenAnalysis
    patterns: PatternInsights
    automation: AutomationEffectiveness
    kb_deflection: KBDeflection


# ==============================================================================
# Tag Analytics Types
# ==============================================================================


@dataclass
class TagStats:
    """Tag usage statistics for dashboard."""

    tag_id: int
    tag_name: str
    color: str
    ticket_count: int
    pct_of_total: float
    growth_pct: float  # Growth vs prior period (positive = trending up)
    prior_period_count: int


@dataclass
class TagTrend:
    """Tag usage trend over time for sparklines."""

    tag_id: int
    tag_name: str
    color: str
    daily_counts: List[Dict[str, Any]]  # [{"date": "2026-01-01", "count": 5}, ...]


# ==============================================================================
# Enhanced SLA Analytics Types
# ==============================================================================


@dataclass
class AgentSLAStats:
    """SLA attainment statistics per agent."""

    agent_id: int
    agent_name: str
    team_name: Optional[str]
    total_tickets: int
    response_met: int
    response_breached: int
    response_attainment_pct: float
    resolution_met: int
    resolution_breached: int
    resolution_attainment_pct: float
    overall_attainment_pct: float
    avg_response_hours: Optional[float]
    avg_resolution_hours: Optional[float]


@dataclass
class TeamSLAStats:
    """SLA attainment statistics per team."""

    team_id: int
    team_name: str
    total_tickets: int
    response_met: int
    response_breached: int
    response_attainment_pct: float
    resolution_met: int
    resolution_breached: int
    resolution_attainment_pct: float
    overall_attainment_pct: float
    agent_count: int


@dataclass
class NearMissTicket:
    """Ticket that came close to breaching SLA."""

    ticket_id: int
    ticket_number: str
    subject: str
    sla_type: str  # 'response' or 'resolution'
    target_time: datetime
    actual_time: datetime
    margin_minutes: int  # Minutes remaining before breach
    margin_pct: float  # e.g., 0.95 means 5% margin
    assigned_to: Optional[str]
    priority: str


@dataclass
class SLATrendPoint:
    """SLA attainment for a single time period."""

    period: str  # Date or period label
    response_attainment_pct: float
    resolution_attainment_pct: float
    overall_attainment_pct: float
    total_tracked: int
    breaches: int


@dataclass
class CategorySLAStats:
    """SLA performance by ticket category."""

    category: str
    total_tickets: int
    response_attainment_pct: float
    resolution_attainment_pct: float
    overall_attainment_pct: float
    avg_resolution_hours: float
    breaches: int


@dataclass
class PrioritySLAStats:
    """SLA performance by priority level."""

    priority: str
    total_tickets: int
    response_attainment_pct: float
    resolution_attainment_pct: float
    overall_attainment_pct: float
    avg_response_hours: float
    avg_resolution_hours: float
    breaches: int


@dataclass
class SLAAnalyticsSummary:
    """Summary statistics for SLA analytics dashboard."""

    overall_attainment_pct: float
    response_attainment_pct: float
    resolution_attainment_pct: float
    total_tracked: int
    total_breaches: int
    response_breaches: int
    resolution_breaches: int
    near_miss_count: int
    period_days: int
