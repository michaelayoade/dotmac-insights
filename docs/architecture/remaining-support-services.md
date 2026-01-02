# Remaining Support Services Architecture

## Overview

This document defines the service layer architecture for support system components that currently lack proper service abstraction. These services complement the existing core services (TicketService, ConversationService, MessageService, etc.).

## Current State Analysis

### Services Already Implemented
| Service | Location | Status |
|---------|----------|--------|
| TicketService | `app/services/support/tickets.py` | Complete |
| ConversationService | `app/services/support/conversations.py` | Complete |
| MessageService | `app/services/support/messages.py` | Complete |
| ChannelService | `app/services/support/channels.py` | Complete |
| ContactService | `app/services/support/contacts.py` | Complete |
| WebhookService | `app/services/support/webhooks.py` | Complete |
| SLAService | `app/services/support/sla.py` | Complete |
| RoutingService | `app/services/support/routing.py` | Complete |
| AutomationService | `app/services/support/automation.py` | Complete |

### Services Missing (Gap Analysis)
| Service Needed | Models Covered | Priority |
|----------------|----------------|----------|
| AgentService | Agent, Team, TeamMember | High |
| CannedResponseService | CannedResponse | High |
| KnowledgeBaseService | KBCategory, KBArticle, KBArticleFeedback | High |
| CSATService | CSATSurvey, CSATResponse | Medium |
| TagService | TicketTag | Medium |
| CustomFieldService | TicketCustomField | Medium |
| EscalationService | EscalationPolicy, EscalationLevel | Medium |
| QueueService | SupportQueue | Low |
| SettingsService | SupportSettings | Low |
| TemplateService | SupportEmailTemplate | Low |

---

## Service Definitions

### 1. AgentService

**Location**: `app/services/support/agents.py`

**Responsibility**: Agent and team management, workload tracking, availability.

```python
class AgentService:
    """
    Manages support agents and teams.

    Agents represent users who handle tickets/conversations.
    Teams group agents by domain/skill for routing.
    """

    # === AGENT QUERIES ===
    def list_agents(self, filters: AgentFilters, pagination: PaginationParams) -> PaginatedResult[Agent]
    def get_agent(self, agent_id: int) -> Agent
    def get_agent_by_email(self, email: str) -> Agent | None
    def get_agent_by_employee_id(self, employee_id: int) -> Agent | None
    def search_agents(self, query: str, limit: int = 20) -> list[Agent]

    # === AGENT MUTATIONS ===
    def create_agent(self, data: AgentCreate) -> Agent
    def update_agent(self, agent_id: int, data: AgentUpdate) -> Agent
    def activate_agent(self, agent_id: int) -> Agent
    def deactivate_agent(self, agent_id: int) -> Agent
    def delete_agent(self, agent_id: int) -> bool

    # === TEAM QUERIES ===
    def list_teams(self, domain: str | None = None, active_only: bool = True) -> list[Team]
    def get_team(self, team_id: int) -> Team
    def get_team_by_name(self, name: str) -> Team | None
    def get_team_members(self, team_id: int, active_only: bool = True) -> list[Agent]

    # === TEAM MUTATIONS ===
    def create_team(self, data: TeamCreate) -> Team
    def update_team(self, team_id: int, data: TeamUpdate) -> Team
    def delete_team(self, team_id: int) -> bool

    # === MEMBERSHIP ===
    def add_member(self, team_id: int, agent_id: int, role: str = "member") -> TeamMember
    def remove_member(self, team_id: int, agent_id: int) -> bool
    def update_member_role(self, team_id: int, agent_id: int, role: str) -> TeamMember
    def get_agent_teams(self, agent_id: int) -> list[Team]

    # === WORKLOAD ===
    def get_agent_workload(self, agent_id: int) -> AgentWorkload
    def get_team_workload(self, team_id: int) -> TeamWorkload
    def is_agent_available(self, agent_id: int) -> bool
    def get_available_agents(self, team_id: int) -> list[Agent]

    # === SKILLS ===
    def get_agents_by_skill(self, skill: str) -> list[Agent]
    def add_skill(self, agent_id: int, skill: str) -> Agent
    def remove_skill(self, agent_id: int, skill: str) -> Agent
```

**Data Classes**:
```python
@dataclass
class AgentFilters:
    is_active: bool | None = None
    domain: str | None = None
    team_id: int | None = None
    skill: str | None = None
    search: str | None = None

@dataclass
class AgentCreate:
    email: str
    display_name: str
    employee_id: int | None = None
    domains: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    capacity: int = 10
    routing_weight: int = 1

@dataclass
class AgentUpdate:
    display_name: str | None = None
    domains: list[str] | None = None
    skills: list[str] | None = None
    capacity: int | None = None
    routing_weight: int | None = None
    channel_caps: dict | None = None

@dataclass
class TeamCreate:
    name: str
    description: str | None = None
    domain: str = "support"
    assignment_rule: str = "round_robin"

@dataclass
class TeamUpdate:
    name: str | None = None
    description: str | None = None
    assignment_rule: str | None = None

@dataclass
class AgentWorkload:
    agent_id: int
    open_tickets: int
    open_conversations: int
    total_active: int
    capacity: int
    utilization_pct: float

@dataclass
class TeamWorkload:
    team_id: int
    total_open: int
    total_agents: int
    available_agents: int
    avg_utilization_pct: float
```

---

### 2. CannedResponseService

**Location**: `app/services/support/canned_responses.py`

**Responsibility**: Manage canned response templates with scoping and variable rendering.

```python
class CannedResponseService:
    """
    Manages canned response templates (macros).

    Canned responses can be:
    - Personal (agent-only)
    - Team (shared within team)
    - Global (all agents)
    """

    # === QUERIES ===
    def list(
        self,
        scope: str | None = None,
        team_id: int | None = None,
        agent_id: int | None = None,
        category: str | None = None,
        search: str | None = None,
        active_only: bool = True,
    ) -> list[CannedResponse]

    def get(self, response_id: int) -> CannedResponse
    def get_by_shortcode(self, shortcode: str, agent_id: int | None = None) -> CannedResponse | None

    def get_available_for_agent(self, agent_id: int) -> list[CannedResponse]
        """Get all responses available to an agent (personal + team + global)."""

    # === MUTATIONS ===
    def create(self, data: CannedResponseCreate) -> CannedResponse
    def update(self, response_id: int, data: CannedResponseUpdate) -> CannedResponse
    def delete(self, response_id: int) -> bool

    # === RENDERING ===
    def render(
        self,
        response_id: int,
        variables: dict[str, str] | None = None,
        ticket: Ticket | None = None,
        conversation: OmniConversation | None = None,
    ) -> str
        """Render template with variable substitution."""

    def get_supported_variables(self) -> list[str]
        """Return list of supported placeholder variables."""

    # === USAGE TRACKING ===
    def record_usage(self, response_id: int) -> None
    def get_most_used(self, limit: int = 10) -> list[CannedResponse]
```

**Data Classes**:
```python
@dataclass
class CannedResponseCreate:
    name: str
    content: str
    shortcode: str | None = None
    scope: str = "personal"  # personal, team, global
    team_id: int | None = None
    agent_id: int | None = None
    category: str | None = None

@dataclass
class CannedResponseUpdate:
    name: str | None = None
    content: str | None = None
    shortcode: str | None = None
    scope: str | None = None
    team_id: int | None = None
    category: str | None = None
    is_active: bool | None = None
```

**Supported Variables**:
```
{{ticket.number}}, {{ticket.subject}}, {{ticket.status}}
{{customer.name}}, {{customer.email}}, {{customer.company}}
{{agent.name}}, {{agent.email}}
{{conversation.channel}}, {{conversation.subject}}
{{date}}, {{time}}, {{datetime}}
```

---

### 3. KnowledgeBaseService

**Location**: `app/services/support/knowledge_base.py`

**Responsibility**: Knowledge base category and article management with search.

```python
class KnowledgeBaseService:
    """
    Manages knowledge base content.

    Supports:
    - Hierarchical categories
    - Articles with versioning
    - Visibility controls (public/internal/restricted)
    - Feedback tracking
    - Full-text search
    """

    # === CATEGORY QUERIES ===
    def list_categories(
        self,
        parent_id: int | None = None,
        visibility: str | None = None,
        active_only: bool = True,
    ) -> list[KBCategory]

    def get_category(self, category_id: int) -> KBCategory
    def get_category_by_slug(self, slug: str) -> KBCategory | None
    def get_category_tree(self) -> list[dict]
        """Return nested category hierarchy."""

    # === CATEGORY MUTATIONS ===
    def create_category(self, data: KBCategoryCreate) -> KBCategory
    def update_category(self, category_id: int, data: KBCategoryUpdate) -> KBCategory
    def delete_category(self, category_id: int) -> bool
    def reorder_categories(self, category_ids: list[int]) -> None

    # === ARTICLE QUERIES ===
    def list_articles(
        self,
        category_id: int | None = None,
        status: str | None = None,
        visibility: str | None = None,
        search: str | None = None,
        pagination: PaginationParams | None = None,
    ) -> PaginatedResult[KBArticle]

    def get_article(self, article_id: int) -> KBArticle
    def get_article_by_slug(self, slug: str) -> KBArticle | None
    def search_articles(self, query: str, limit: int = 20) -> list[KBArticle]

    # === ARTICLE MUTATIONS ===
    def create_article(self, data: KBArticleCreate) -> KBArticle
    def update_article(self, article_id: int, data: KBArticleUpdate) -> KBArticle
    def publish_article(self, article_id: int) -> KBArticle
    def unpublish_article(self, article_id: int) -> KBArticle
    def archive_article(self, article_id: int) -> KBArticle
    def delete_article(self, article_id: int) -> bool

    # === ATTACHMENTS ===
    def add_attachment(self, article_id: int, data: KBAttachmentData) -> KBArticleAttachment
    def remove_attachment(self, article_id: int, attachment_id: int) -> bool
    def reorder_attachments(self, article_id: int, attachment_ids: list[int]) -> None

    # === FEEDBACK ===
    def record_helpful(self, article_id: int, is_helpful: bool, feedback: str | None = None) -> None
    def get_feedback(self, article_id: int) -> list[KBArticleFeedback]
    def get_helpfulness_stats(self, article_id: int) -> dict

    # === ANALYTICS ===
    def record_view(self, article_id: int) -> None
    def get_popular_articles(self, limit: int = 10) -> list[KBArticle]
    def get_low_rated_articles(self, threshold: float = 0.5) -> list[KBArticle]
```

**Data Classes**:
```python
@dataclass
class KBCategoryCreate:
    name: str
    slug: str | None = None  # Auto-generated if not provided
    description: str | None = None
    icon: str | None = None
    parent_id: int | None = None
    visibility: str = "public"  # public, internal, restricted

@dataclass
class KBCategoryUpdate:
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    icon: str | None = None
    parent_id: int | None = None
    visibility: str | None = None
    is_active: bool | None = None

@dataclass
class KBArticleCreate:
    title: str
    content: str
    category_id: int
    slug: str | None = None
    excerpt: str | None = None
    visibility: str = "public"
    search_keywords: str | None = None
    related_article_ids: list[int] = field(default_factory=list)
    team_ids: list[int] = field(default_factory=list)

@dataclass
class KBArticleUpdate:
    title: str | None = None
    content: str | None = None
    category_id: int | None = None
    slug: str | None = None
    excerpt: str | None = None
    visibility: str | None = None
    search_keywords: str | None = None
    related_article_ids: list[int] | None = None
    team_ids: list[int] | None = None

@dataclass
class KBAttachmentData:
    filename: str
    url: str
    mime_type: str | None = None
    size_bytes: int | None = None
```

---

### 4. CSATService

**Location**: `app/services/support/csat.py`

**Responsibility**: Customer satisfaction surveys and response management.

```python
class CSATService:
    """
    Manages customer satisfaction surveys.

    Supports:
    - CSAT (1-5 rating)
    - NPS (0-10 Net Promoter Score)
    - CES (1-7 Customer Effort Score)
    """

    # === SURVEY QUERIES ===
    def list_surveys(self, survey_type: str | None = None, active_only: bool = True) -> list[CSATSurvey]
    def get_survey(self, survey_id: int) -> CSATSurvey
    def get_active_survey_for_trigger(self, trigger: str) -> CSATSurvey | None

    # === SURVEY MUTATIONS ===
    def create_survey(self, data: CSATSurveyCreate) -> CSATSurvey
    def update_survey(self, survey_id: int, data: CSATSurveyUpdate) -> CSATSurvey
    def activate_survey(self, survey_id: int) -> CSATSurvey
    def deactivate_survey(self, survey_id: int) -> CSATSurvey
    def delete_survey(self, survey_id: int) -> bool

    # === RESPONSE COLLECTION ===
    def send_survey(
        self,
        survey_id: int,
        ticket_id: int | None = None,
        conversation_id: int | None = None,
        customer_id: int | None = None,
    ) -> str
        """Send survey and return response token."""

    def record_response(
        self,
        token: str,
        rating: int,
        answers: dict | None = None,
        feedback_text: str | None = None,
    ) -> CSATResponse

    def get_pending_responses(self, customer_id: int | None = None) -> list[CSATResponse]

    # === RESPONSE QUERIES ===
    def list_responses(
        self,
        survey_id: int | None = None,
        agent_id: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        pagination: PaginationParams | None = None,
    ) -> PaginatedResult[CSATResponse]

    def get_response(self, response_id: int) -> CSATResponse
    def get_responses_for_ticket(self, ticket_id: int) -> list[CSATResponse]
    def get_responses_for_agent(self, agent_id: int) -> list[CSATResponse]

    # === METRICS ===
    def get_csat_score(
        self,
        agent_id: int | None = None,
        team_id: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> float | None
        """Calculate CSAT score (% of 4-5 ratings)."""

    def get_nps_score(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> float | None
        """Calculate NPS (% promoters - % detractors)."""

    def get_survey_metrics(self, survey_id: int) -> CSATMetrics
```

**Data Classes**:
```python
@dataclass
class CSATSurveyCreate:
    name: str
    survey_type: str = "csat"  # csat, nps, ces
    trigger: str = "ticket_resolved"  # ticket_resolved, ticket_closed, manual
    questions: list[dict] = field(default_factory=list)
    delay_hours: int = 0
    send_via: str = "email"  # email, in_app, both
    conditions: dict = field(default_factory=dict)

@dataclass
class CSATSurveyUpdate:
    name: str | None = None
    questions: list[dict] | None = None
    delay_hours: int | None = None
    send_via: str | None = None
    conditions: dict | None = None
    is_active: bool | None = None

@dataclass
class CSATMetrics:
    survey_id: int
    total_sent: int
    total_responded: int
    response_rate: float
    avg_rating: float
    score: float  # CSAT % or NPS or CES avg
    rating_distribution: dict[int, int]
```

---

### 5. TagService

**Location**: `app/services/support/tags.py`

**Responsibility**: Ticket tag management with usage tracking.

```python
class TagService:
    """
    Manages ticket tags for categorization.
    """

    # === QUERIES ===
    def list(self, active_only: bool = True, search: str | None = None) -> list[TicketTag]
    def get(self, tag_id: int) -> TicketTag
    def get_by_name(self, name: str) -> TicketTag | None
    def get_popular(self, limit: int = 20) -> list[TicketTag]

    # === MUTATIONS ===
    def create(self, data: TagCreate) -> TicketTag
    def update(self, tag_id: int, data: TagUpdate) -> TicketTag
    def delete(self, tag_id: int) -> bool
    def merge(self, target_id: int, source_ids: list[int]) -> TicketTag
        """Merge multiple tags into one, updating all references."""

    # === USAGE ===
    def get_usage_count(self, tag_id: int) -> int
    def recalculate_usage_counts(self) -> int
        """Recalculate all tag usage counts. Returns count updated."""
```

**Data Classes**:
```python
@dataclass
class TagCreate:
    name: str
    color: str | None = None
    description: str | None = None

@dataclass
class TagUpdate:
    name: str | None = None
    color: str | None = None
    description: str | None = None
    is_active: bool | None = None
```

---

### 6. CustomFieldService

**Location**: `app/services/support/custom_fields.py`

**Responsibility**: Custom field definition and validation.

```python
class CustomFieldService:
    """
    Manages custom ticket fields.

    Supports field types:
    - text, textarea, number
    - select, multi_select
    - date, datetime
    - checkbox
    - url, email
    """

    # === QUERIES ===
    def list(self, active_only: bool = True) -> list[TicketCustomField]
    def get(self, field_id: int) -> TicketCustomField
    def get_by_key(self, field_key: str) -> TicketCustomField | None
    def get_required_fields(self) -> list[TicketCustomField]
    def get_fields_for_form(self, form_type: str) -> list[TicketCustomField]
        """Get fields for create/edit/list forms."""

    # === MUTATIONS ===
    def create(self, data: CustomFieldCreate) -> TicketCustomField
    def update(self, field_id: int, data: CustomFieldUpdate) -> TicketCustomField
    def delete(self, field_id: int) -> bool
    def reorder(self, field_ids: list[int]) -> None

    # === VALIDATION ===
    def validate_value(self, field_key: str, value: Any) -> tuple[bool, str | None]
        """Validate a value against field definition. Returns (valid, error_message)."""

    def validate_all(self, values: dict[str, Any]) -> dict[str, str]
        """Validate all custom field values. Returns dict of field_key -> error_message."""
```

**Data Classes**:
```python
@dataclass
class CustomFieldCreate:
    name: str
    field_key: str
    field_type: str  # text, textarea, number, select, multi_select, date, datetime, checkbox, url, email
    description: str | None = None
    options: list[str] | None = None  # For select/multi_select
    default_value: str | None = None
    is_required: bool = False
    min_length: int | None = None
    max_length: int | None = None
    regex_pattern: str | None = None
    show_in_list: bool = False
    show_in_create: bool = True

@dataclass
class CustomFieldUpdate:
    name: str | None = None
    description: str | None = None
    options: list[str] | None = None
    default_value: str | None = None
    is_required: bool | None = None
    min_length: int | None = None
    max_length: int | None = None
    regex_pattern: str | None = None
    show_in_list: bool | None = None
    show_in_create: bool | None = None
    is_active: bool | None = None
```

---

### 7. EscalationService

**Location**: `app/services/support/escalation.py`

**Responsibility**: Escalation policy management and execution.

```python
class EscalationService:
    """
    Manages multi-level escalation policies.

    Escalation triggers:
    - SLA breach (response/resolution)
    - Priority change
    - Manual escalation
    - Time-based (no response after X hours)
    """

    # === POLICY QUERIES ===
    def list_policies(self, active_only: bool = True) -> list[EscalationPolicy]
    def get_policy(self, policy_id: int) -> EscalationPolicy
    def get_matching_policy(self, ticket: Ticket) -> EscalationPolicy | None

    # === POLICY MUTATIONS ===
    def create_policy(self, data: EscalationPolicyCreate) -> EscalationPolicy
    def update_policy(self, policy_id: int, data: EscalationPolicyUpdate) -> EscalationPolicy
    def delete_policy(self, policy_id: int) -> bool

    # === LEVEL MANAGEMENT ===
    def add_level(self, policy_id: int, data: EscalationLevelCreate) -> EscalationLevel
    def update_level(self, level_id: int, data: EscalationLevelUpdate) -> EscalationLevel
    def remove_level(self, level_id: int) -> bool
    def reorder_levels(self, policy_id: int, level_ids: list[int]) -> None

    # === EXECUTION ===
    def check_and_escalate(self, ticket: Ticket) -> EscalationResult | None
        """Check if ticket should be escalated and execute if needed."""

    def escalate_ticket(self, ticket_id: int, reason: str, to_level: int | None = None) -> EscalationResult
        """Manually escalate a ticket."""

    def get_escalation_history(self, ticket_id: int) -> list[EscalationLog]

    # === SCHEDULED CHECK ===
    def process_pending_escalations(self) -> int
        """Check all tickets for pending escalations. Called by scheduler."""
```

**Data Classes**:
```python
@dataclass
class EscalationPolicyCreate:
    name: str
    description: str | None = None
    conditions: dict = field(default_factory=dict)
    priority: int = 0

@dataclass
class EscalationPolicyUpdate:
    name: str | None = None
    description: str | None = None
    conditions: dict | None = None
    priority: int | None = None
    is_active: bool | None = None

@dataclass
class EscalationLevelCreate:
    level: int
    trigger: str  # sla_breach, time_based, priority_change
    trigger_hours: int
    escalate_to_team_id: int | None = None
    escalate_to_user_id: int | None = None
    notify_current_assignee: bool = True
    notify_team_lead: bool = False
    reassign_ticket: bool = False
    change_priority: bool = False
    new_priority: str | None = None
    notification_template: str | None = None

@dataclass
class EscalationLevelUpdate:
    trigger: str | None = None
    trigger_hours: int | None = None
    escalate_to_team_id: int | None = None
    escalate_to_user_id: int | None = None
    notify_current_assignee: bool | None = None
    notify_team_lead: bool | None = None
    reassign_ticket: bool | None = None
    change_priority: bool | None = None
    new_priority: str | None = None
    notification_template: str | None = None

@dataclass
class EscalationResult:
    escalated: bool
    level: int
    actions_taken: list[str]
    notifications_sent: list[str]
```

---

### 8. QueueService

**Location**: `app/services/support/queues.py`

**Responsibility**: Custom ticket queue/view management.

```python
class QueueService:
    """
    Manages custom ticket queues (saved views/filters).

    Queues can be:
    - System (predefined, read-only)
    - Public (visible to all)
    - Private (owner-only)
    """

    # === QUERIES ===
    def list(
        self,
        owner_id: int | None = None,
        include_public: bool = True,
        include_system: bool = True,
    ) -> list[SupportQueue]

    def get(self, queue_id: int) -> SupportQueue
    def get_by_name(self, name: str, owner_id: int | None = None) -> SupportQueue | None

    # === MUTATIONS ===
    def create(self, data: QueueCreate) -> SupportQueue
    def update(self, queue_id: int, data: QueueUpdate) -> SupportQueue
    def delete(self, queue_id: int) -> bool
    def reorder(self, queue_ids: list[int]) -> None

    # === EXECUTION ===
    def get_tickets(self, queue_id: int, pagination: PaginationParams | None = None) -> PaginatedResult[Ticket]
        """Execute queue filters and return matching tickets."""

    def get_count(self, queue_id: int) -> int
        """Get ticket count for queue."""
```

**Data Classes**:
```python
@dataclass
class QueueCreate:
    name: str
    description: str | None = None
    queue_type: str = "custom"  # system, public, private
    filters: dict = field(default_factory=dict)
    sort_by: str = "created_at"
    sort_direction: str = "desc"
    is_public: bool = False
    owner_id: int | None = None
    icon: str | None = None
    color: str | None = None

@dataclass
class QueueUpdate:
    name: str | None = None
    description: str | None = None
    filters: dict | None = None
    sort_by: str | None = None
    sort_direction: str | None = None
    is_public: bool | None = None
    icon: str | None = None
    color: str | None = None
    is_active: bool | None = None
```

---

### 9. NotificationService (Support-specific)

**Location**: `app/services/support/notifications.py`

**Responsibility**: Support-specific notification dispatch and preference management.

```python
class SupportNotificationService:
    """
    Handles support-related notifications.

    Integrates with base NotificationService for actual delivery.
    Manages support-specific events and templates.
    """

    # === DISPATCH ===
    def notify_ticket_created(self, ticket: Ticket) -> None
    def notify_ticket_assigned(self, ticket: Ticket, agent: Agent) -> None
    def notify_ticket_updated(self, ticket: Ticket, changes: dict) -> None
    def notify_ticket_resolved(self, ticket: Ticket) -> None
    def notify_ticket_escalated(self, ticket: Ticket, level: int) -> None
    def notify_sla_warning(self, ticket: Ticket, target: str, remaining_minutes: int) -> None
    def notify_sla_breach(self, ticket: Ticket, target: str) -> None

    def notify_conversation_assigned(self, conversation: OmniConversation, agent: Agent) -> None
    def notify_new_message(self, message: OmniMessage) -> None

    # === PREFERENCES ===
    def get_preferences(self, user_id: int) -> list[NotificationPreference]
    def update_preference(self, user_id: int, event_type: str, data: PreferenceUpdate) -> NotificationPreference
    def should_notify(self, user_id: int, event_type: str, channel: str) -> bool

    # === TEMPLATES ===
    def get_template(self, template_type: str) -> SupportEmailTemplate | None
    def render_template(self, template_type: str, context: dict) -> tuple[str, str, str]
        """Render template. Returns (subject, body_html, body_text)."""
```

---

## Service Dependencies

```
┌────────────────────────────────────────────────────────────────────┐
│                      NEW SERVICE DEPENDENCIES                       │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  AgentService ◄───────── RoutingService                            │
│       │                        │                                    │
│       ▼                        ▼                                    │
│  CannedResponseService    TicketService ◄─── EscalationService     │
│       │                        │                                    │
│       ▼                        ▼                                    │
│  MessageService ◄──────── ConversationService                      │
│                                │                                    │
│                                ▼                                    │
│  KnowledgeBaseService     CSATService                              │
│       │                        │                                    │
│       └────────────────────────┼─────────────────────────┐         │
│                                │                         │         │
│                                ▼                         ▼         │
│                       SupportNotificationService                   │
│                                │                                    │
│                                ▼                                    │
│                        NotificationService (base)                  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Standalone Services (no dependencies)                        │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │  TagService                                                  │   │
│  │  CustomFieldService                                          │   │
│  │  QueueService                                                │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

---

## File Structure (Final)

```
app/services/support/
├── __init__.py              # Export all services
├── types.py                 # Shared dataclasses
├── errors.py                # Support-specific errors
│
│ # Core Services (EXISTING)
├── tickets.py               # TicketService
├── conversations.py         # ConversationService
├── messages.py              # MessageService
├── channels.py              # ChannelService
├── contacts.py              # ContactService
├── webhooks.py              # WebhookService
│
│ # Cross-Cutting Services (EXISTING)
├── sla.py                   # SLAService
├── routing.py               # RoutingService
├── automation.py            # AutomationService
│
│ # NEW SERVICES
├── agents.py                # AgentService - agents/teams/workload
├── canned_responses.py      # CannedResponseService - templates
├── knowledge_base.py        # KnowledgeBaseService - KB articles
├── csat.py                  # CSATService - surveys/feedback
├── tags.py                  # TagService - ticket tags
├── custom_fields.py         # CustomFieldService - custom fields
├── escalation.py            # EscalationService - escalation policies
├── queues.py                # QueueService - saved views
├── notifications.py         # SupportNotificationService
│
└── providers/               # Channel-specific implementations
    ├── __init__.py
    ├── base.py
    ├── email.py
    ├── whatsapp.py
    └── chatwoot.py
```

---

## Implementation Priority

### Phase 1: High Priority (Week 1-2)
1. **AgentService** - Required for routing and assignment
2. **CannedResponseService** - High agent productivity impact
3. **KnowledgeBaseService** - Self-service reduction

### Phase 2: Medium Priority (Week 3-4)
4. **CSATService** - Customer feedback loop
5. **EscalationService** - SLA enforcement
6. **TagService** - Organization/filtering

### Phase 3: Lower Priority (Week 5+)
7. **CustomFieldService** - Data flexibility
8. **QueueService** - Agent productivity
9. **SupportNotificationService** - Enhanced notifications

---

## Testing Strategy

### Unit Tests
- Each service method tested in isolation
- Mock database and dependencies
- Test validation, edge cases, error handling

### Integration Tests
- Service-to-service interactions
- Database transactions
- Event emission and handling

### E2E Tests
- Full escalation flow
- CSAT survey send-respond-metrics flow
- KB article create-publish-search flow

---

## Success Criteria

1. All models have corresponding service layer
2. No direct database access in routes
3. Consistent error handling across services
4. Full test coverage for critical paths
5. Documentation for all public methods
