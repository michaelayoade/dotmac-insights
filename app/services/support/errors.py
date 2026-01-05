"""Support-specific service errors.

These errors extend the base ServiceError classes with domain-specific
error types for support operations.
"""
from app.services.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceError,
    ValidationError,
)

__all__ = [
    # Re-export base errors for convenience
    "ServiceError",
    "NotFoundError",
    "ValidationError",
    "ConflictError",
    "ForbiddenError",
    # Conversation errors
    "ConversationNotFoundError",
    "ConversationClosedError",
    "ConversationAssignmentError",
    # Message errors
    "MessageNotFoundError",
    "MessageDeliveryError",
    "DuplicateMessageError",
    # Channel errors
    "ChannelNotFoundError",
    "ChannelInactiveError",
    "ChannelConfigError",
    # Contact errors
    "ContactNotFoundError",
    "ContactResolutionError",
    "DuplicateContactError",
    # Webhook errors
    "WebhookValidationError",
    "WebhookProcessingError",
    "DuplicateWebhookError",
    # Routing errors
    "RoutingRuleNotFoundError",
    "NoMatchingRuleError",
    # SLA errors
    "SLAConfigError",
    # Agent errors
    "AgentNotFoundError",
    "DuplicateAgentError",
    # Team errors
    "TeamNotFoundError",
    "DuplicateTeamError",
    "TeamMembershipError",
    # Canned response errors
    "CannedResponseNotFoundError",
    "DuplicateShortcodeError",
    # Knowledge base errors
    "KBCategoryNotFoundError",
    "KBArticleNotFoundError",
    "DuplicateSlugError",
    # CSAT errors
    "CSATSurveyNotFoundError",
    "CSATResponseNotFoundError",
    "InvalidSurveyTokenError",
    # Tag errors
    "TagNotFoundError",
    "DuplicateTagError",
    # Escalation errors
    "EscalationPolicyNotFoundError",
    "EscalationLevelNotFoundError",
    "DuplicatePolicyError",
    # Queue errors
    "QueueNotFoundError",
    "DuplicateQueueError",
    # Settings errors
    "SettingsNotFoundError",
    # Custom field errors
    "CustomFieldNotFoundError",
    "DuplicateFieldKeyError",
    # Email template errors
    "EmailTemplateNotFoundError",
    "DuplicateTemplateTypeError",
]


# ==============================================================================
# Conversation Errors
# ==============================================================================


class ConversationNotFoundError(NotFoundError):
    """Raised when a conversation is not found."""

    def __init__(self, conversation_id: int | None = None, message: str | None = None):
        if message is None:
            message = f"Conversation not found: {conversation_id}" if conversation_id else "Conversation not found"
        super().__init__(message)
        self.conversation_id = conversation_id


class ConversationClosedError(ConflictError):
    """Raised when attempting to modify a closed conversation."""

    def __init__(self, conversation_id: int | None = None, message: str | None = None):
        if message is None:
            message = f"Conversation {conversation_id} is closed and cannot be modified" if conversation_id else "Conversation is closed"
        super().__init__(message)
        self.conversation_id = conversation_id


class ConversationAssignmentError(ValidationError):
    """Raised when conversation assignment fails."""

    def __init__(self, message: str = "Failed to assign conversation"):
        super().__init__(message)


# ==============================================================================
# Message Errors
# ==============================================================================


class MessageNotFoundError(NotFoundError):
    """Raised when a message is not found."""

    def __init__(self, message_id: int | None = None, message: str | None = None):
        if message is None:
            message = f"Message not found: {message_id}" if message_id else "Message not found"
        super().__init__(message)
        self.message_id = message_id


class MessageDeliveryError(ServiceError):
    """Raised when message delivery fails."""

    http_code = 502  # Bad Gateway (external service failure)

    def __init__(
        self,
        message: str = "Message delivery failed",
        provider_error: str | None = None,
        error_code: str | None = None,
    ):
        super().__init__(message)
        self.provider_error = provider_error
        self.error_code = error_code


class DuplicateMessageError(ConflictError):
    """Raised when a duplicate message is detected."""

    def __init__(self, provider_message_id: str | None = None, message: str | None = None):
        if message is None:
            message = f"Duplicate message detected: {provider_message_id}" if provider_message_id else "Duplicate message"
        super().__init__(message)
        self.provider_message_id = provider_message_id


# ==============================================================================
# Channel Errors
# ==============================================================================


class ChannelNotFoundError(NotFoundError):
    """Raised when a channel is not found."""

    def __init__(self, channel_id: int | None = None, channel_name: str | None = None, message: str | None = None):
        if message is None:
            if channel_id:
                message = f"Channel not found: {channel_id}"
            elif channel_name:
                message = f"Channel not found: {channel_name}"
            else:
                message = "Channel not found"
        super().__init__(message)
        self.channel_id = channel_id
        self.channel_name = channel_name


class ChannelInactiveError(ConflictError):
    """Raised when attempting to use an inactive channel."""

    def __init__(self, channel_id: int | None = None, message: str | None = None):
        if message is None:
            message = f"Channel {channel_id} is inactive" if channel_id else "Channel is inactive"
        super().__init__(message)
        self.channel_id = channel_id


class ChannelConfigError(ValidationError):
    """Raised when channel configuration is invalid."""

    def __init__(self, message: str = "Invalid channel configuration", field: str | None = None):
        super().__init__(message)
        self.field = field


# ==============================================================================
# Contact Errors
# ==============================================================================


class ContactNotFoundError(NotFoundError):
    """Raised when a contact is not found."""

    def __init__(self, contact_id: int | None = None, email: str | None = None, message: str | None = None):
        if message is None:
            if contact_id:
                message = f"Contact not found: {contact_id}"
            elif email:
                message = f"Contact not found for email: {email}"
            else:
                message = "Contact not found"
        super().__init__(message)
        self.contact_id = contact_id
        self.email = email


class ContactResolutionError(ServiceError):
    """Raised when contact resolution fails."""

    def __init__(self, message: str = "Failed to resolve contact", identifier: str | None = None):
        super().__init__(message)
        self.identifier = identifier


class DuplicateContactError(ConflictError):
    """Raised when a duplicate contact is detected."""

    def __init__(self, email: str | None = None, phone: str | None = None, message: str | None = None):
        if message is None:
            if email:
                message = f"Contact already exists with email: {email}"
            elif phone:
                message = f"Contact already exists with phone: {phone}"
            else:
                message = "Duplicate contact"
        super().__init__(message)
        self.email = email
        self.phone = phone


# ==============================================================================
# Webhook Errors
# ==============================================================================


class WebhookValidationError(ValidationError):
    """Raised when webhook validation fails (signature, format, etc.)."""

    def __init__(self, message: str = "Webhook validation failed", reason: str | None = None):
        super().__init__(message)
        self.reason = reason


class WebhookProcessingError(ServiceError):
    """Raised when webhook processing fails."""

    def __init__(self, message: str = "Webhook processing failed", event_id: int | None = None):
        super().__init__(message)
        self.event_id = event_id


class DuplicateWebhookError(ConflictError):
    """Raised when a duplicate webhook event is detected."""

    def __init__(self, provider_event_id: str | None = None, message: str | None = None):
        if message is None:
            message = f"Duplicate webhook event: {provider_event_id}" if provider_event_id else "Duplicate webhook event"
        super().__init__(message)
        self.provider_event_id = provider_event_id


# ==============================================================================
# Routing Errors
# ==============================================================================


class RoutingRuleNotFoundError(NotFoundError):
    """Raised when a routing rule is not found."""

    def __init__(self, rule_id: int | None = None, message: str | None = None):
        if message is None:
            message = f"Routing rule not found: {rule_id}" if rule_id else "Routing rule not found"
        super().__init__(message)
        self.rule_id = rule_id


class NoMatchingRuleError(ServiceError):
    """Raised when no routing rule matches (informational, not necessarily an error)."""

    http_code = 200  # Not an error, just no match

    def __init__(self, message: str = "No matching routing rule found"):
        super().__init__(message)


# ==============================================================================
# SLA Errors
# ==============================================================================


class SLAConfigError(ValidationError):
    """Raised when SLA configuration is invalid."""

    def __init__(self, message: str = "Invalid SLA configuration", field: str | None = None):
        super().__init__(message)
        self.field = field


# ==============================================================================
# Agent Errors
# ==============================================================================


class AgentNotFoundError(NotFoundError):
    """Raised when an agent is not found."""

    def __init__(self, agent_id: int | None = None, email: str | None = None, message: str | None = None):
        if message is None:
            if agent_id:
                message = f"Agent not found: {agent_id}"
            elif email:
                message = f"Agent not found for email: {email}"
            else:
                message = "Agent not found"
        super().__init__(message)
        self.agent_id = agent_id
        self.email = email


class DuplicateAgentError(ConflictError):
    """Raised when a duplicate agent is detected."""

    def __init__(self, email: str | None = None, message: str | None = None):
        if message is None:
            message = f"Agent already exists with email: {email}" if email else "Duplicate agent"
        super().__init__(message)
        self.email = email


# ==============================================================================
# Team Errors
# ==============================================================================


class TeamNotFoundError(NotFoundError):
    """Raised when a team is not found."""

    def __init__(self, team_id: int | None = None, name: str | None = None, message: str | None = None):
        if message is None:
            if team_id:
                message = f"Team not found: {team_id}"
            elif name:
                message = f"Team not found: {name}"
            else:
                message = "Team not found"
        super().__init__(message)
        self.team_id = team_id
        self.name = name


class DuplicateTeamError(ConflictError):
    """Raised when a duplicate team is detected."""

    def __init__(self, name: str | None = None, message: str | None = None):
        if message is None:
            message = f"Team already exists with name: {name}" if name else "Duplicate team"
        super().__init__(message)
        self.name = name


class TeamMembershipError(ValidationError):
    """Raised when team membership operation fails."""

    def __init__(self, message: str = "Team membership operation failed"):
        super().__init__(message)


# ==============================================================================
# Canned Response Errors
# ==============================================================================


class CannedResponseNotFoundError(NotFoundError):
    """Raised when a canned response is not found."""

    def __init__(self, response_id: int | None = None, shortcode: str | None = None, message: str | None = None):
        if message is None:
            if response_id:
                message = f"Canned response not found: {response_id}"
            elif shortcode:
                message = f"Canned response not found for shortcode: {shortcode}"
            else:
                message = "Canned response not found"
        super().__init__(message)
        self.response_id = response_id
        self.shortcode = shortcode


class DuplicateShortcodeError(ConflictError):
    """Raised when a duplicate shortcode is detected."""

    def __init__(self, shortcode: str | None = None, message: str | None = None):
        if message is None:
            message = f"Shortcode already exists: {shortcode}" if shortcode else "Duplicate shortcode"
        super().__init__(message)
        self.shortcode = shortcode


# ==============================================================================
# Knowledge Base Errors
# ==============================================================================


class KBCategoryNotFoundError(NotFoundError):
    """Raised when a KB category is not found."""

    def __init__(self, category_id: int | None = None, slug: str | None = None, message: str | None = None):
        if message is None:
            if category_id:
                message = f"KB category not found: {category_id}"
            elif slug:
                message = f"KB category not found for slug: {slug}"
            else:
                message = "KB category not found"
        super().__init__(message)
        self.category_id = category_id
        self.slug = slug


class KBArticleNotFoundError(NotFoundError):
    """Raised when a KB article is not found."""

    def __init__(self, article_id: int | None = None, slug: str | None = None, message: str | None = None):
        if message is None:
            if article_id:
                message = f"KB article not found: {article_id}"
            elif slug:
                message = f"KB article not found for slug: {slug}"
            else:
                message = "KB article not found"
        super().__init__(message)
        self.article_id = article_id
        self.slug = slug


class DuplicateSlugError(ConflictError):
    """Raised when a duplicate slug is detected."""

    def __init__(self, slug: str | None = None, entity_type: str = "entity", message: str | None = None):
        if message is None:
            message = f"{entity_type.title()} slug already exists: {slug}" if slug else f"Duplicate {entity_type} slug"
        super().__init__(message)
        self.slug = slug
        self.entity_type = entity_type


# ==============================================================================
# CSAT Errors
# ==============================================================================


class CSATSurveyNotFoundError(NotFoundError):
    """Raised when a CSAT survey is not found."""

    def __init__(self, survey_id: int | None = None, message: str | None = None):
        if message is None:
            message = f"CSAT survey not found: {survey_id}" if survey_id else "CSAT survey not found"
        super().__init__(message)
        self.survey_id = survey_id


class CSATResponseNotFoundError(NotFoundError):
    """Raised when a CSAT response is not found."""

    def __init__(self, response_id: int | None = None, token: str | None = None, message: str | None = None):
        if message is None:
            if response_id:
                message = f"CSAT response not found: {response_id}"
            elif token:
                message = f"CSAT response not found for token: {token}"
            else:
                message = "CSAT response not found"
        super().__init__(message)
        self.response_id = response_id
        self.token = token


class InvalidSurveyTokenError(ValidationError):
    """Raised when a survey response token is invalid or expired."""

    def __init__(self, token: str | None = None, message: str | None = None):
        if message is None:
            message = f"Invalid or expired survey token: {token}" if token else "Invalid or expired survey token"
        super().__init__(message)
        self.token = token


# ==============================================================================
# Tag Errors
# ==============================================================================


class TagNotFoundError(NotFoundError):
    """Raised when a tag is not found."""

    def __init__(self, tag_id: int | None = None, name: str | None = None, message: str | None = None):
        if message is None:
            if tag_id:
                message = f"Tag not found: {tag_id}"
            elif name:
                message = f"Tag not found: {name}"
            else:
                message = "Tag not found"
        super().__init__(message)
        self.tag_id = tag_id
        self.name = name


class DuplicateTagError(ConflictError):
    """Raised when a duplicate tag is detected."""

    def __init__(self, name: str | None = None, message: str | None = None):
        if message is None:
            message = f"Tag already exists: {name}" if name else "Duplicate tag"
        super().__init__(message)
        self.name = name


# ==============================================================================
# Escalation Errors
# ==============================================================================


class EscalationPolicyNotFoundError(NotFoundError):
    """Raised when an escalation policy is not found."""

    def __init__(self, policy_id: int | None = None, message: str | None = None):
        if message is None:
            message = f"Escalation policy not found: {policy_id}" if policy_id else "Escalation policy not found"
        super().__init__(message)
        self.policy_id = policy_id


class EscalationLevelNotFoundError(NotFoundError):
    """Raised when an escalation level is not found."""

    def __init__(self, level_id: int | None = None, message: str | None = None):
        if message is None:
            message = f"Escalation level not found: {level_id}" if level_id else "Escalation level not found"
        super().__init__(message)
        self.level_id = level_id


class DuplicatePolicyError(ConflictError):
    """Raised when a duplicate escalation policy is detected."""

    def __init__(self, name: str | None = None, message: str | None = None):
        if message is None:
            message = f"Escalation policy already exists: {name}" if name else "Duplicate escalation policy"
        super().__init__(message)
        self.name = name


# ==============================================================================
# Queue Errors
# ==============================================================================


class QueueNotFoundError(NotFoundError):
    """Raised when a support queue is not found."""

    def __init__(self, queue_id: int | None = None, name: str | None = None, message: str | None = None):
        if message is None:
            if queue_id:
                message = f"Queue not found: {queue_id}"
            elif name:
                message = f"Queue not found: {name}"
            else:
                message = "Queue not found"
        super().__init__(message)
        self.queue_id = queue_id
        self.name = name


class DuplicateQueueError(ConflictError):
    """Raised when a duplicate queue is detected."""

    def __init__(self, name: str | None = None, message: str | None = None):
        if message is None:
            message = f"Queue already exists: {name}" if name else "Duplicate queue"
        super().__init__(message)
        self.name = name


# ==============================================================================
# Settings Errors
# ==============================================================================


class SettingsNotFoundError(NotFoundError):
    """Raised when support settings are not found."""

    def __init__(self, company: str | None = None, message: str | None = None):
        if message is None:
            message = f"Settings not found for company: {company}" if company else "Settings not found"
        super().__init__(message)
        self.company = company


# ==============================================================================
# Custom Field Errors
# ==============================================================================


class CustomFieldNotFoundError(NotFoundError):
    """Raised when a custom field is not found."""

    def __init__(self, field_id: int | None = None, field_key: str | None = None, message: str | None = None):
        if message is None:
            if field_id:
                message = f"Custom field not found: {field_id}"
            elif field_key:
                message = f"Custom field not found: {field_key}"
            else:
                message = "Custom field not found"
        super().__init__(message)
        self.field_id = field_id
        self.field_key = field_key


class DuplicateFieldKeyError(ConflictError):
    """Raised when a duplicate field key is detected."""

    def __init__(self, field_key: str | None = None, message: str | None = None):
        if message is None:
            message = f"Field key already exists: {field_key}" if field_key else "Duplicate field key"
        super().__init__(message)
        self.field_key = field_key


# ==============================================================================
# Email Template Errors
# ==============================================================================


class EmailTemplateNotFoundError(NotFoundError):
    """Raised when an email template is not found."""

    def __init__(self, template_id: int | None = None, template_type: str | None = None, message: str | None = None):
        if message is None:
            if template_id:
                message = f"Email template not found: {template_id}"
            elif template_type:
                message = f"Email template not found for type: {template_type}"
            else:
                message = "Email template not found"
        super().__init__(message)
        self.template_id = template_id
        self.template_type = template_type


class DuplicateTemplateTypeError(ConflictError):
    """Raised when a duplicate template type is detected."""

    def __init__(self, template_type: str | None = None, message: str | None = None):
        if message is None:
            message = f"Template type already exists: {template_type}" if template_type else "Duplicate template type"
        super().__init__(message)
        self.template_type = template_type
