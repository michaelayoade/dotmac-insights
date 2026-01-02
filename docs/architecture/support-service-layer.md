# Support System Service Layer Architecture

## Overview

This document defines the service layer architecture for the DotMac BOS Support System, consolidating tickets, inbox/conversations, messages, channels, webhooks, and contact management into a unified, maintainable structure.

## Current State Problems

1. **Triple Ticket System**: `Ticket`, `Conversation`, `UnifiedTicket` models with unclear ownership
2. **Logic in Routes**: Business logic scattered across API and web route handlers
3. **No Service for Omnichannel**: OmniConversation/OmniMessage operations inline
4. **Multiple Contact Models**: `Contact`, `Party`, `InboxContact`, `OmniParticipant` with unclear relationships
5. **Missing Automation**: SLA, escalation, and automation models exist but no execution services

---

## Target Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PRESENTATION LAYER                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  Web Routes (SSR/HTMX)          │  API Routes (REST/JSON)                   │
│  app/modules/*/routes.py        │  app/api/*/                               │
└─────────────────────────────────┴───────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              APPLICATION LAYER                               │
│                         app/services/support/                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │  TicketService   │  │ ConversationSvc  │  │  ChannelService  │          │
│  │  (UnifiedTicket) │  │ (OmniConversation│  │  (OmniChannel)   │          │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘          │
│           │                     │                     │                     │
│  ┌────────▼─────────┐  ┌────────▼─────────┐  ┌────────▼─────────┐          │
│  │  MessageService  │  │  ContactService  │  │  WebhookService  │          │
│  │  (OmniMessage)   │  │  (Party-based)   │  │  (ingest/route)  │          │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘          │
│           │                     │                     │                     │
│  ┌────────▼─────────────────────▼─────────────────────▼─────────┐          │
│  │                    CROSS-CUTTING SERVICES                     │          │
│  ├───────────────────────────────────────────────────────────────┤          │
│  │  SLAService  │  RoutingService  │  AutomationService          │          │
│  │  (calculate) │  (assign/route)  │  (triggers/actions)         │          │
│  └───────────────────────────────────────────────────────────────┘          │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────┐          │
│  │                      SYNC SERVICES                             │          │
│  ├───────────────────────────────────────────────────────────────┤          │
│  │  OutboundSyncService  │  InboundSyncService  │  ReconcileSvc  │          │
│  │  (push to external)   │  (webhooks/polling)  │  (fix drift)   │          │
│  └───────────────────────────────────────────────────────────────┘          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DOMAIN LAYER                                    │
│                            app/models/                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  UnifiedTicket  │  OmniConversation  │  OmniMessage  │  OmniChannel         │
│  Party          │  OmniParticipant   │  OmniAttachment │  WebhookEvent      │
│  Agent/Team     │  SLAPolicy         │  AutomationRule │  RoutingRule       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           INFRASTRUCTURE LAYER                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  PostgreSQL  │  Redis (cache/pubsub)  │  S3 (attachments)  │  External APIs │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Service Definitions

### 1. TicketService (Core)

**Location**: `app/services/support/ticket_service.py`

**Responsibility**: All operations on UnifiedTicket - the single source of truth for support cases.

```python
@dataclass
class TicketService:
    """
    Core ticket operations on UnifiedTicket model.

    This is the ONLY service that should write to UnifiedTicket.
    All other services delegate to this for ticket mutations.
    """
    db: Session
    principal: Principal  # For audit fields

    # === QUERIES ===
    def get(self, ticket_id: int) -> UnifiedTicket
    def get_by_number(self, ticket_number: str) -> UnifiedTicket
    def get_by_external_id(self, system: str, external_id: str) -> UnifiedTicket
    def list(self, filters: TicketFilters, pagination: Pagination) -> PaginatedResult[UnifiedTicket]
    def search(self, query: str, filters: TicketFilters) -> list[UnifiedTicket]

    # === MUTATIONS ===
    def create(self, data: TicketCreate) -> UnifiedTicket
    def update(self, ticket_id: int, data: TicketUpdate) -> UnifiedTicket
    def update_field(self, ticket_id: int, field: str, value: Any) -> UnifiedTicket
    def delete(self, ticket_id: int) -> None  # Soft delete

    # === BULK ===
    def bulk_update(self, ids: list[int], data: TicketUpdate) -> BulkResult
    def bulk_delete(self, ids: list[int]) -> BulkResult
    def bulk_assign(self, ids: list[int], agent_id: int | None, team_id: int | None) -> BulkResult

    # === ASSIGNMENT ===
    def assign(self, ticket_id: int, agent_id: int | None, team_id: int | None) -> UnifiedTicket
    def unassign(self, ticket_id: int) -> UnifiedTicket
    def escalate(self, ticket_id: int, reason: str) -> UnifiedTicket

    # === STATUS LIFECYCLE ===
    def open(self, ticket_id: int) -> UnifiedTicket
    def start_progress(self, ticket_id: int) -> UnifiedTicket
    def wait_for_customer(self, ticket_id: int) -> UnifiedTicket
    def resolve(self, ticket_id: int, resolution: str) -> UnifiedTicket
    def close(self, ticket_id: int) -> UnifiedTicket
    def reopen(self, ticket_id: int, reason: str) -> UnifiedTicket

    # === RELATIONSHIPS ===
    def merge(self, target_id: int, source_ids: list[int]) -> UnifiedTicket
    def split(self, ticket_id: int, data: TicketSplit) -> UnifiedTicket
    def link_conversation(self, ticket_id: int, conversation_id: int) -> None
    def link_party(self, ticket_id: int, party_id: int) -> None
```

**Events Emitted**:
- `ticket.created`, `ticket.updated`, `ticket.deleted`
- `ticket.assigned`, `ticket.escalated`
- `ticket.status_changed`, `ticket.resolved`, `ticket.closed`

---

### 2. ConversationService

**Location**: `app/services/support/conversation_service.py`

**Responsibility**: Omnichannel conversation management. Conversations are the thread containers; messages are the content.

```python
@dataclass
class ConversationService:
    """
    Manages OmniConversation lifecycle.

    A Conversation represents a communication thread with a contact
    across any channel (email, chat, whatsapp, etc).

    Conversations can be promoted to Tickets for formal tracking.
    """
    db: Session
    principal: Principal
    message_service: MessageService  # Injected
    contact_service: ContactService  # Injected

    # === QUERIES ===
    def get(self, conversation_id: int) -> OmniConversation
    def get_with_messages(self, conversation_id: int, limit: int = 50) -> ConversationWithMessages
    def list(self, filters: ConversationFilters, pagination: Pagination) -> PaginatedResult[OmniConversation]
    def list_for_contact(self, party_id: int) -> list[OmniConversation]
    def get_unread_count(self, agent_id: int | None = None) -> int
    def get_stats(self) -> InboxStats

    # === MUTATIONS ===
    def create(self, data: ConversationCreate) -> OmniConversation
    def update(self, conversation_id: int, data: ConversationUpdate) -> OmniConversation

    # === STATUS ===
    def mark_open(self, conversation_id: int) -> OmniConversation
    def mark_pending(self, conversation_id: int) -> OmniConversation
    def mark_resolved(self, conversation_id: int) -> OmniConversation
    def snooze(self, conversation_id: int, until: datetime) -> OmniConversation

    # === ASSIGNMENT ===
    def assign(self, conversation_id: int, agent_id: int | None, team_id: int | None) -> OmniConversation

    # === ACTIONS ===
    def star(self, conversation_id: int) -> OmniConversation
    def unstar(self, conversation_id: int) -> OmniConversation
    def add_tag(self, conversation_id: int, tag: str) -> OmniConversation
    def remove_tag(self, conversation_id: int, tag: str) -> OmniConversation

    # === PROMOTION ===
    def create_ticket(self, conversation_id: int, data: TicketCreate) -> UnifiedTicket
        """Promote conversation to a formal ticket, linking them."""

    def create_lead(self, conversation_id: int, data: LeadCreate) -> Lead
        """Create CRM lead from conversation contact."""

    # === MERGE ===
    def merge(self, target_id: int, source_ids: list[int]) -> OmniConversation
```

**Events Emitted**:
- `conversation.created`, `conversation.updated`
- `conversation.assigned`, `conversation.status_changed`
- `conversation.new_message` (delegated from MessageService)

---

### 3. MessageService

**Location**: `app/services/support/message_service.py`

**Responsibility**: Individual message operations within conversations.

```python
@dataclass
class MessageService:
    """
    Manages OmniMessage within conversations.

    Messages are the atomic units of communication.
    This service handles creation, delivery tracking, and attachments.
    """
    db: Session
    principal: Principal
    channel_service: ChannelService  # For outbound delivery

    # === QUERIES ===
    def get(self, message_id: int) -> OmniMessage
    def list_for_conversation(
        self,
        conversation_id: int,
        before: datetime | None = None,
        limit: int = 50
    ) -> list[OmniMessage]

    # === MUTATIONS ===
    def create_inbound(self, data: InboundMessageData) -> OmniMessage
        """Record an incoming message from external channel."""

    def create_outbound(self, data: OutboundMessageData) -> OmniMessage
        """Create and send an outgoing message."""

    def create_internal_note(self, conversation_id: int, content: str) -> OmniMessage
        """Create internal-only note (not sent to customer)."""

    # === DELIVERY ===
    def mark_delivered(self, message_id: int, provider_id: str) -> OmniMessage
    def mark_read(self, message_id: int) -> OmniMessage
    def mark_failed(self, message_id: int, error: str) -> OmniMessage
    def retry_send(self, message_id: int) -> OmniMessage

    # === ATTACHMENTS ===
    def add_attachment(self, message_id: int, attachment: AttachmentData) -> OmniAttachment
    def remove_attachment(self, message_id: int, attachment_id: int) -> None

    # === TEMPLATES ===
    def send_canned_response(
        self,
        conversation_id: int,
        canned_response_id: int,
        variables: dict[str, str] | None = None
    ) -> OmniMessage
```

**Data Classes**:
```python
@dataclass
class InboundMessageData:
    conversation_id: int
    channel_id: int
    content: str
    sender_participant_id: int
    provider_message_id: str | None = None
    sent_at: datetime | None = None
    meta: dict | None = None

@dataclass
class OutboundMessageData:
    conversation_id: int
    content: str
    is_private: bool = False  # Internal note
    attachments: list[AttachmentData] | None = None
```

---

### 4. ChannelService

**Location**: `app/services/support/channel_service.py`

**Responsibility**: Channel configuration and message routing.

```python
@dataclass
class ChannelService:
    """
    Manages OmniChannel configuration and message delivery.

    A Channel represents a communication endpoint:
    - Email inbox (IMAP/SMTP)
    - WhatsApp Business API
    - SMS gateway (Twilio, etc)
    - Chatwoot inbox
    - Web chat widget
    - Custom webhook
    """
    db: Session
    principal: Principal

    # === CHANNEL CRUD ===
    def get(self, channel_id: int) -> OmniChannel
    def list(self, active_only: bool = True) -> list[OmniChannel]
    def create(self, data: ChannelCreate) -> OmniChannel
    def update(self, channel_id: int, data: ChannelUpdate) -> OmniChannel
    def delete(self, channel_id: int) -> None
    def test_connection(self, channel_id: int) -> ConnectionTestResult

    # === MESSAGE DELIVERY ===
    def send_message(self, channel_id: int, message: OmniMessage) -> DeliveryResult
        """
        Send message through channel's configured provider.
        Returns delivery result with provider message ID.
        """

    def get_delivery_status(self, channel_id: int, provider_message_id: str) -> DeliveryStatus

    # === CHANNEL-SPECIFIC ===
    def sync_chatwoot_inbox(self, channel_id: int) -> SyncResult
    def configure_webhook(self, channel_id: int, webhook_url: str) -> str  # Returns secret
    def rotate_webhook_secret(self, channel_id: int) -> str
```

**Supported Channel Types**:
```python
class ChannelType(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    CHATWOOT = "chatwoot"
    WEB_CHAT = "web_chat"
    CUSTOM = "custom"
```

---

### 5. ContactService

**Location**: `app/services/support/contact_service.py`

**Responsibility**: Unified contact/party resolution for support interactions.

```python
@dataclass
class ContactService:
    """
    Manages contact identity resolution for support.

    Uses Party as the unified identity model.
    Handles participant identity across channels.
    """
    db: Session
    principal: Principal
    party_service: PartyService  # From identity module

    # === RESOLUTION ===
    def resolve_or_create(self, identifier: ContactIdentifier) -> Party
        """
        Find existing Party by email/phone/external_id or create new one.
        This is the primary entry point for inbound message contact resolution.
        """

    def resolve_participant(self, handle: str, channel_type: str) -> OmniParticipant
        """Resolve or create OmniParticipant for channel-specific handle."""

    def link_participant_to_party(self, participant_id: int, party_id: int) -> None

    # === QUERIES ===
    def get_party(self, party_id: int) -> Party
    def get_party_conversations(self, party_id: int) -> list[OmniConversation]
    def get_party_tickets(self, party_id: int) -> list[UnifiedTicket]
    def search(self, query: str, limit: int = 20) -> list[Party]

    # === MUTATIONS ===
    def update_party(self, party_id: int, data: PartyUpdate) -> Party
    def merge_parties(self, target_id: int, source_ids: list[int]) -> Party

    # === INBOX CONTACT SYNC ===
    def sync_inbox_contact(self, party_id: int) -> InboxContact
        """Sync Party data to denormalized InboxContact for quick inbox access."""
```

**Contact Resolution Flow**:
```
Inbound Message
      │
      ▼
┌─────────────────┐
│ Extract Handle  │  (email, phone, social ID)
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ Find Participant│────►│ Found? Return   │
└────────┬────────┘     └─────────────────┘
         │ Not Found
         ▼
┌─────────────────┐     ┌─────────────────┐
│ Search Party by │────►│ Found? Link &   │
│ email/phone     │     │ Return          │
└────────┬────────┘     └─────────────────┘
         │ Not Found
         ▼
┌─────────────────┐
│ Create Party +  │
│ Participant     │
└─────────────────┘
```

---

### 6. WebhookService

**Location**: `app/services/support/webhook_service.py`

**Responsibility**: Inbound webhook processing and event routing.

```python
@dataclass
class WebhookService:
    """
    Processes inbound webhooks from external providers.

    Responsibilities:
    - Validate webhook signatures
    - Parse provider-specific payloads
    - Route to appropriate handlers
    - Ensure idempotency
    - Audit logging
    """
    db: Session
    conversation_service: ConversationService
    message_service: MessageService
    contact_service: ContactService
    channel_service: ChannelService

    # === INGESTION ===
    def ingest(self, channel_id: int, payload: dict, headers: dict) -> WebhookResult
        """
        Main entry point for webhook processing.

        1. Validate signature using channel's webhook_secret
        2. Check idempotency (provider_event_id)
        3. Parse payload based on channel type
        4. Route to appropriate handler
        5. Record in WebhookEvent for audit
        """

    # === HANDLERS (internal) ===
    def _handle_chatwoot_event(self, channel: OmniChannel, event: ChatwootEvent) -> None
    def _handle_email_event(self, channel: OmniChannel, event: EmailEvent) -> None
    def _handle_whatsapp_event(self, channel: OmniChannel, event: WhatsAppEvent) -> None
    def _handle_sms_event(self, channel: OmniChannel, event: SMSEvent) -> None

    # === VALIDATION ===
    def validate_signature(self, channel: OmniChannel, payload: bytes, signature: str) -> bool

    # === IDEMPOTENCY ===
    def is_duplicate(self, channel_id: int, provider_event_id: str) -> bool
    def mark_processed(self, event_id: int) -> None

    # === RETRY ===
    def get_failed_events(self, channel_id: int | None = None) -> list[OmniWebhookEvent]
    def retry_event(self, event_id: int) -> WebhookResult
```

**Webhook Event Types**:
```python
class WebhookEventType(str, Enum):
    # Conversation events
    CONVERSATION_CREATED = "conversation.created"
    CONVERSATION_UPDATED = "conversation.updated"
    CONVERSATION_RESOLVED = "conversation.resolved"

    # Message events
    MESSAGE_CREATED = "message.created"
    MESSAGE_UPDATED = "message.updated"
    MESSAGE_DELIVERED = "message.delivered"
    MESSAGE_READ = "message.read"
    MESSAGE_FAILED = "message.failed"

    # Contact events
    CONTACT_CREATED = "contact.created"
    CONTACT_UPDATED = "contact.updated"

    # Agent events
    AGENT_ASSIGNED = "agent.assigned"
    AGENT_UNASSIGNED = "agent.unassigned"
```

---

### 7. SLAService

**Location**: `app/services/support/sla_service.py`

**Responsibility**: SLA calculation, tracking, and breach detection.

```python
@dataclass
class SLAService:
    """
    Calculates and tracks SLA compliance.

    Uses:
    - SLAPolicy for target definitions
    - BusinessCalendar for business hours
    - SLATarget for priority-specific targets
    """
    db: Session

    # === CALCULATION ===
    def calculate_due_dates(self, ticket: UnifiedTicket) -> SLADueDates
        """
        Calculate response_by and resolution_by based on:
        - Ticket priority
        - Applicable SLA policy
        - Business calendar
        """

    def get_remaining_time(self, ticket: UnifiedTicket, target: str) -> timedelta | None
        """Get remaining time for response or resolution target."""

    def is_breached(self, ticket: UnifiedTicket, target: str) -> bool
    def is_warning(self, ticket: UnifiedTicket, target: str) -> bool

    # === POLICY RESOLUTION ===
    def get_applicable_policy(self, ticket: UnifiedTicket) -> SLAPolicy | None
        """Find policy matching ticket's conditions (customer tier, channel, etc)."""

    # === BREACH HANDLING ===
    def check_and_record_breaches(self, ticket: UnifiedTicket) -> list[SLABreachLog]
        """Check for breaches and record in breach log."""

    def get_breaches(self, ticket_id: int) -> list[SLABreachLog]

    # === METRICS ===
    def get_sla_metrics(self, filters: SLAMetricFilters) -> SLAMetrics
        """Aggregate SLA compliance metrics."""

    # === BUSINESS HOURS ===
    def calculate_business_hours(
        self,
        start: datetime,
        end: datetime,
        calendar_id: int
    ) -> timedelta

    def add_business_hours(
        self,
        start: datetime,
        hours: float,
        calendar_id: int
    ) -> datetime
```

---

### 8. RoutingService

**Location**: `app/services/support/routing_service.py`

**Responsibility**: Automatic ticket/conversation assignment.

```python
@dataclass
class RoutingService:
    """
    Handles automatic assignment of tickets and conversations.

    Strategies:
    - Round-robin within team
    - Load-balanced by current workload
    - Skill-based matching
    - Manual (no auto-assignment)
    """
    db: Session

    # === AUTO-ASSIGNMENT ===
    def auto_assign_ticket(self, ticket: UnifiedTicket) -> Agent | None
        """
        Find and assign best agent based on routing rules.
        Returns assigned agent or None if no match.
        """

    def auto_assign_conversation(self, conversation: OmniConversation) -> Agent | None

    # === RULE MATCHING ===
    def find_matching_rule(self, ticket: UnifiedTicket) -> RoutingRule | None
    def evaluate_conditions(self, rule: RoutingRule, ticket: UnifiedTicket) -> bool

    # === AGENT SELECTION ===
    def select_agent_round_robin(self, team_id: int) -> Agent | None
    def select_agent_load_balanced(self, team_id: int) -> Agent | None
    def select_agent_skill_match(self, team_id: int, required_skills: list[str]) -> Agent | None

    # === WORKLOAD ===
    def get_agent_workload(self, agent_id: int) -> AgentWorkload
    def get_team_workload(self, team_id: int) -> TeamWorkload
    def is_agent_available(self, agent_id: int) -> bool
```

---

### 9. AutomationService

**Location**: `app/services/support/automation_service.py`

**Responsibility**: Execute automation rules based on triggers.

```python
@dataclass
class AutomationService:
    """
    Executes automation rules when triggers fire.

    Trigger → Conditions → Actions

    Example: When ticket created (trigger) and priority is urgent (condition),
    assign to support-escalation team and send Slack notification (actions).
    """
    db: Session
    ticket_service: TicketService
    conversation_service: ConversationService
    notification_service: NotificationService

    # === EXECUTION ===
    def execute_for_trigger(
        self,
        trigger: AutomationTrigger,
        entity: UnifiedTicket | OmniConversation,
        context: dict | None = None
    ) -> list[AutomationExecutionLog]
        """
        Find and execute all active rules matching the trigger.
        Returns execution logs for audit.
        """

    # === RULE EVALUATION ===
    def evaluate_rule(self, rule: AutomationRule, entity: Any, context: dict) -> bool
    def evaluate_condition(self, condition: dict, entity: Any) -> bool

    # === ACTIONS ===
    def execute_action(self, action: dict, entity: Any, context: dict) -> ActionResult
    def _action_set_priority(self, entity: Any, value: str) -> None
    def _action_set_status(self, entity: Any, value: str) -> None
    def _action_assign_agent(self, entity: Any, agent_id: int) -> None
    def _action_assign_team(self, entity: Any, team_id: int) -> None
    def _action_add_tag(self, entity: Any, tag: str) -> None
    def _action_send_notification(self, entity: Any, template: str, recipients: list) -> None
    def _action_send_webhook(self, entity: Any, url: str, payload: dict) -> None

    # === SCHEDULING ===
    def schedule_delayed_action(self, rule_id: int, entity_id: int, delay: timedelta) -> None
    def execute_scheduled_actions(self) -> int  # Called by scheduler
```

---

### 10. SyncService (Outbound/Inbound)

**Location**: `app/services/support/sync_service.py`

**Responsibility**: Bidirectional sync with external systems.

```python
@dataclass
class SyncService:
    """
    Manages synchronization with external systems:
    - Splynx (ISP billing/support)
    - ERPNext (ERP tickets)
    - Chatwoot (omnichannel)

    Uses hash-based change detection to avoid unnecessary writes.
    """
    db: Session

    # === OUTBOUND SYNC ===
    def sync_ticket_to_external(self, ticket: UnifiedTicket, systems: list[str] | None = None) -> SyncResult
    def sync_ticket_to_splynx(self, ticket: UnifiedTicket) -> SyncResult
    def sync_ticket_to_erpnext(self, ticket: UnifiedTicket) -> SyncResult
    def sync_ticket_to_chatwoot(self, ticket: UnifiedTicket) -> SyncResult

    # === INBOUND SYNC ===
    def import_from_splynx(self, external_id: str) -> UnifiedTicket
    def import_from_erpnext(self, external_id: str) -> UnifiedTicket
    def import_from_chatwoot(self, conversation_id: int) -> UnifiedTicket

    # === CHANGE DETECTION ===
    def compute_hash(self, ticket: UnifiedTicket, system: str) -> str
    def has_changed(self, ticket: UnifiedTicket, system: str) -> bool

    # === RECONCILIATION ===
    def reconcile_all(self, system: str) -> ReconcileResult
    def find_orphaned_external(self, system: str) -> list[str]  # External IDs not linked
    def find_stale_local(self, system: str, age: timedelta) -> list[UnifiedTicket]

    # === MAPPING ===
    def get_external_id(self, ticket_id: int, system: str) -> str | None
    def get_ticket_by_external_id(self, system: str, external_id: str) -> UnifiedTicket | None
    def link_external_id(self, ticket_id: int, system: str, external_id: str) -> None
```

---

## Data Flow Diagrams

### Inbound Message Flow

```
External Channel (Email/WhatsApp/Chat)
           │
           ▼
    ┌──────────────┐
    │ WebhookService│ ← Validate signature, check idempotency
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │ContactService│ ← Resolve or create Party + Participant
    └──────┬───────┘
           │
           ▼
    ┌──────────────────┐
    │ConversationService│ ← Find or create conversation
    └──────┬───────────┘
           │
           ▼
    ┌──────────────┐
    │MessageService│ ← Create inbound message
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │RoutingService│ ← Auto-assign if rules match
    └──────┬───────┘
           │
           ▼
    ┌────────────────┐
    │AutomationService│ ← Execute triggered automations
    └──────┬─────────┘
           │
           ▼
    ┌──────────────┐
    │  SLAService  │ ← Calculate SLA due dates
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │  Broadcast   │ ← WebSocket notification to agents
    └──────────────┘
```

### Outbound Message Flow

```
Agent UI (Reply)
      │
      ▼
┌───────────────────┐
│ MessageService    │ ← Create outbound message
│ create_outbound() │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ ChannelService    │ ← Route to correct channel
│ send_message()    │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ Provider API      │ ← SendGrid/Twilio/WhatsApp/etc
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ Delivery Callback │ ← Update delivery status
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ SLAService        │ ← Record first response time
└───────────────────┘
```

### Ticket Lifecycle

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │                                                             │
                    ▼                                                             │
┌─────────┐    ┌─────────┐    ┌─────────────┐    ┌──────────┐    ┌────────┐     │
│  OPEN   │───►│IN_PROGRESS│───►│  WAITING   │───►│ RESOLVED │───►│ CLOSED │     │
└─────────┘    └─────────┘    └─────────────┘    └──────────┘    └────────┘     │
     │              │               │                  │              │          │
     │              │               │                  │              │          │
     │              ▼               ▼                  │              │          │
     │         ┌─────────┐    ┌─────────┐             │              │          │
     │         │ ON_HOLD │    │(customer │             │              │          │
     │         └─────────┘    │ replied) │             │              │          │
     │                        └────┬─────┘             │              │          │
     │                             │                   │              │          │
     │◄────────────────────────────┘                   │              │          │
     │                                                 │              │          │
     │◄────────────────────────────────────────────────┘              │          │
     │                         (reopen)                               │          │
     │                                                                │          │
     └────────────────────────────────────────────────────────────────┘          │
                              (REOPENED)                                          │
                                                                                  │
                    ┌─────────────────────────────────────────────────────────────┘
                    │ (auto-close after X days)
                    ▼
              ┌──────────┐
              │  CLOSED  │
              └──────────┘
```

---

## Service Dependencies

```
┌─────────────────────────────────────────────────────────────────┐
│                      DEPENDENCY GRAPH                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  TicketService ◄─────────────────────────────────┐              │
│       │                                          │              │
│       ▼                                          │              │
│  ConversationService ────► MessageService        │              │
│       │                         │                │              │
│       ▼                         ▼                │              │
│  ContactService ◄────── ChannelService           │              │
│       │                         │                │              │
│       ▼                         │                │              │
│  PartyService (identity)        │                │              │
│                                 │                │              │
│  WebhookService ────────────────┼────────────────┘              │
│       │                         │                               │
│       └─────────────────────────┘                               │
│                                                                 │
│  ┌──────────────────────────────────────────────┐               │
│  │ Cross-Cutting (injected into above services) │               │
│  ├──────────────────────────────────────────────┤               │
│  │  SLAService                                  │               │
│  │  RoutingService                              │               │
│  │  AutomationService                           │               │
│  │  SyncService                                 │               │
│  │  NotificationService                         │               │
│  └──────────────────────────────────────────────┘               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
app/services/support/
├── __init__.py              # Export all services
├── types.py                 # Shared dataclasses (TicketCreate, etc.)
│
├── ticket_service.py        # UnifiedTicket operations
├── conversation_service.py  # OmniConversation operations
├── message_service.py       # OmniMessage operations
├── channel_service.py       # OmniChannel + delivery
├── contact_service.py       # Party/Participant resolution
├── webhook_service.py       # Inbound webhook processing
│
├── sla_service.py           # SLA calculation + breach tracking
├── routing_service.py       # Auto-assignment logic
├── automation_service.py    # Rule execution engine
├── sync_service.py          # External system sync
│
└── providers/               # Channel-specific implementations
    ├── __init__.py
    ├── base.py              # Abstract channel provider
    ├── email.py             # SMTP/IMAP provider
    ├── whatsapp.py          # WhatsApp Business API
    ├── sms.py               # Twilio/other SMS
    ├── chatwoot.py          # Chatwoot API
    └── webhook.py           # Generic webhook
```

---

## Migration Path

### Phase 1: Service Extraction (Week 1-2)
1. Create `ConversationService` - extract from routes
2. Create `MessageService` - extract from routes
3. Create `ContactService` - wrap PartyService
4. Wire up in routes, keep models unchanged

### Phase 2: Core Services (Week 3-4)
1. Refactor `TicketService` to use UnifiedTicket
2. Create `ChannelService` with provider abstraction
3. Create `WebhookService` with validation
4. Deprecate direct model access in routes

### Phase 3: Cross-Cutting (Week 5-6)
1. Implement `SLAService` calculation logic
2. Implement `RoutingService` with strategies
3. Implement `AutomationService` executor
4. Add event emission for all mutations

### Phase 4: Sync & Migration (Week 7-8)
1. Implement `SyncService` for all external systems
2. Create migration scripts for legacy Ticket → UnifiedTicket
3. Create migration scripts for legacy Conversation → OmniConversation
4. Dual-write period then cutover

---

## Testing Strategy

### Unit Tests
- Each service method tested in isolation
- Mock dependencies (other services, DB)
- Test validation, edge cases, error handling

### Integration Tests
- Service-to-service interactions
- Database transactions
- Event emission and handling

### E2E Tests
- Full inbound webhook → message → conversation flow
- Full ticket lifecycle with SLA tracking
- Sync round-trip with external systems

---

## Appendix: Type Definitions

See `app/services/support/types.py` for complete dataclass definitions:

```python
# Core types
TicketCreate, TicketUpdate, TicketFilters
ConversationCreate, ConversationUpdate, ConversationFilters
InboundMessageData, OutboundMessageData
ChannelCreate, ChannelUpdate

# Results
BulkResult, SyncResult, WebhookResult, DeliveryResult
PaginatedResult[T], SLADueDates, SLAMetrics

# Enums
TicketStatus, TicketPriority, TicketType, TicketSource
ConversationStatus, MessageDirection, ChannelType
AutomationTrigger, AutomationAction, RoutingStrategy
```
