"""Email template service - business logic for support notification templates.

This service handles email template management:
- CRUD operations for notification templates
- Template rendering with placeholders
- Template type management

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.support_settings import SupportEmailTemplate

from .types import (
    EmailTemplateCreate,
    EmailTemplateUpdate,
)
from .errors import (
    DuplicateTemplateTypeError,
    EmailTemplateNotFoundError,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["EmailTemplateService"]

# Standard template types
TEMPLATE_TYPES = [
    "TICKET_CREATED",
    "TICKET_ASSIGNED",
    "TICKET_IN_PROGRESS",
    "TICKET_WAITING",
    "TICKET_ON_HOLD",
    "TICKET_REPLIED",
    "TICKET_RESOLVED",
    "TICKET_CLOSED",
    "TICKET_REOPENED",
    "TICKET_ESCALATED",
    "SLA_WARNING",
    "SLA_BREACH",
    "CUSTOMER_REPLIED",
    "AUTO_CLOSE_WARNING",
    "CSAT_SURVEY",
    "CSAT_REMINDER",
    "AGENT_ASSIGNED",
    "AGENT_MENTIONED",
    "PASSWORD_RESET",
    "WELCOME",
]

# Standard placeholders
STANDARD_PLACEHOLDERS = [
    "{{ticket_id}}",
    "{{ticket_subject}}",
    "{{ticket_status}}",
    "{{ticket_priority}}",
    "{{ticket_url}}",
    "{{customer_name}}",
    "{{customer_email}}",
    "{{agent_name}}",
    "{{agent_email}}",
    "{{team_name}}",
    "{{company_name}}",
    "{{portal_url}}",
    "{{created_at}}",
    "{{updated_at}}",
    "{{message_body}}",
]


class EmailTemplateService:
    """Service for email template management.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def list(
        self,
        active_only: bool = True,
        template_type: Optional[str] = None,
        company: Optional[str] = None,
    ) -> List[SupportEmailTemplate]:
        """List email templates with optional filtering.

        Args:
            active_only: Only return active templates.
            template_type: Filter by template type.
            company: Filter by company.

        Returns:
            List of SupportEmailTemplate instances.
        """
        query = self.db.query(SupportEmailTemplate)

        if company:
            query = query.filter(
                or_(SupportEmailTemplate.company == company, SupportEmailTemplate.company.is_(None))
            )

        if active_only:
            query = query.filter(SupportEmailTemplate.is_active == True)

        if template_type:
            query = query.filter(SupportEmailTemplate.template_type == template_type.upper())

        return query.order_by(SupportEmailTemplate.template_type.asc()).all()

    def get(self, template_id: int) -> SupportEmailTemplate:
        """Get a template by ID.

        Args:
            template_id: The template ID.

        Returns:
            SupportEmailTemplate instance.

        Raises:
            EmailTemplateNotFoundError: If not found.
        """
        template = (
            self.db.query(SupportEmailTemplate)
            .filter(SupportEmailTemplate.id == template_id)
            .first()
        )
        if not template:
            raise EmailTemplateNotFoundError(template_id)
        return template

    def get_by_type(
        self,
        template_type: str,
        company: Optional[str] = None,
    ) -> Optional[SupportEmailTemplate]:
        """Get a template by type.

        Args:
            template_type: The template type.
            company: Optional company filter.

        Returns:
            SupportEmailTemplate instance or None.
        """
        query = self.db.query(SupportEmailTemplate).filter(
            SupportEmailTemplate.template_type == template_type.upper(),
            SupportEmailTemplate.is_active == True,
        )

        if company:
            # Prefer company-specific, fall back to global
            company_template = query.filter(SupportEmailTemplate.company == company).first()
            if company_template:
                return company_template
            return query.filter(SupportEmailTemplate.company.is_(None)).first()

        return query.first()

    def get_template_types(self) -> List[str]:
        """Get list of standard template types.

        Returns:
            List of template type strings.
        """
        return TEMPLATE_TYPES.copy()

    def get_placeholders(self, template_type: Optional[str] = None) -> List[str]:
        """Get available placeholders for a template type.

        Args:
            template_type: Optional template type for type-specific placeholders.

        Returns:
            List of placeholder strings.
        """
        placeholders = STANDARD_PLACEHOLDERS.copy()

        # Add type-specific placeholders
        if template_type:
            template_type = template_type.upper()
            if template_type in ["TICKET_ESCALATED", "SLA_WARNING", "SLA_BREACH"]:
                placeholders.extend([
                    "{{escalation_level}}",
                    "{{escalation_reason}}",
                    "{{sla_target}}",
                    "{{time_remaining}}",
                ])
            elif template_type == "CSAT_SURVEY":
                placeholders.extend([
                    "{{survey_url}}",
                    "{{survey_expiry}}",
                ])

        return placeholders

    # -------------------------------------------------------------------------
    # Mutations
    # -------------------------------------------------------------------------

    def create(self, data: EmailTemplateCreate, company: Optional[str] = None) -> SupportEmailTemplate:
        """Create a new email template.

        Args:
            data: Template creation data.
            company: Optional company scope.

        Returns:
            Created SupportEmailTemplate instance.

        Raises:
            DuplicateTemplateTypeError: If template type already exists for company.
        """
        template_type = data.template_type.upper()

        # Check for duplicate type
        existing = self.get_by_type(template_type, company)
        if existing and existing.company == company:
            raise DuplicateTemplateTypeError(template_type)

        template = SupportEmailTemplate(
            company=company,
            name=data.name,
            template_type=template_type,
            subject=data.subject,
            body_html=data.body_html,
            body_text=data.body_text,
            is_active=True,
        )

        self.db.add(template)
        self.db.flush()
        return template

    def update(self, template_id: int, data: EmailTemplateUpdate) -> SupportEmailTemplate:
        """Update an email template.

        Args:
            template_id: The template ID.
            data: Update data.

        Returns:
            Updated SupportEmailTemplate instance.

        Raises:
            EmailTemplateNotFoundError: If not found.
        """
        template = self.get(template_id)

        if data.name is not None:
            template.name = data.name

        if data.subject is not None:
            template.subject = data.subject

        if data.body_html is not None:
            template.body_html = data.body_html

        if data.body_text is not None:
            template.body_text = data.body_text

        if data.is_active is not None:
            template.is_active = data.is_active

        self.db.flush()
        return template

    def delete(self, template_id: int) -> bool:
        """Delete an email template.

        Args:
            template_id: The template ID.

        Returns:
            True if deleted.

        Raises:
            EmailTemplateNotFoundError: If not found.
        """
        template = self.get(template_id)
        self.db.delete(template)
        self.db.flush()
        return True

    def duplicate(
        self,
        template_id: int,
        new_name: Optional[str] = None,
        company: Optional[str] = None,
    ) -> SupportEmailTemplate:
        """Duplicate an existing template.

        Args:
            template_id: The template ID to duplicate.
            new_name: New name for the duplicate.
            company: Company for the new template.

        Returns:
            New SupportEmailTemplate instance.

        Raises:
            EmailTemplateNotFoundError: If source not found.
        """
        source = self.get(template_id)

        template = SupportEmailTemplate(
            company=company,
            name=new_name or f"{source.name} (Copy)",
            template_type=source.template_type,
            subject=source.subject,
            body_html=source.body_html,
            body_text=source.body_text,
            supported_placeholders=source.supported_placeholders,
            is_active=True,
        )

        self.db.add(template)
        self.db.flush()
        return template

    # -------------------------------------------------------------------------
    # Rendering
    # -------------------------------------------------------------------------

    def render(
        self,
        template_id: int,
        context: Dict[str, Any],
    ) -> tuple[str, str, Optional[str]]:
        """Render a template with context data.

        Args:
            template_id: The template ID.
            context: Dict of placeholder values.

        Returns:
            Tuple of (subject, body_html, body_text).

        Raises:
            EmailTemplateNotFoundError: If not found.
        """
        template = self.get(template_id)
        return self._render_template(template, context)

    def render_by_type(
        self,
        template_type: str,
        context: Dict[str, Any],
        company: Optional[str] = None,
    ) -> Optional[tuple[str, str, Optional[str]]]:
        """Render a template by type with context data.

        Args:
            template_type: The template type.
            context: Dict of placeholder values.
            company: Optional company filter.

        Returns:
            Tuple of (subject, body_html, body_text) or None if template not found.
        """
        template = self.get_by_type(template_type, company)
        if not template:
            return None
        return self._render_template(template, context)

    def _render_template(
        self,
        template: SupportEmailTemplate,
        context: Dict[str, Any],
    ) -> tuple[str, str, Optional[str]]:
        """Render a template with context data.

        Args:
            template: The template instance.
            context: Dict of placeholder values.

        Returns:
            Tuple of (subject, body_html, body_text).
        """
        subject = self._replace_placeholders(template.subject, context)
        body_html = self._replace_placeholders(template.body_html, context)
        body_text = None
        if template.body_text:
            body_text = self._replace_placeholders(template.body_text, context)

        return subject, body_html, body_text

    def _replace_placeholders(self, text: str, context: Dict[str, Any]) -> str:
        """Replace placeholders in text with context values.

        Args:
            text: The template text.
            context: Dict of placeholder values.

        Returns:
            Text with placeholders replaced.
        """
        if not text:
            return text

        # Find all placeholders in the text
        pattern = r'\{\{(\w+)\}\}'

        def replacer(match):
            key = match.group(1)
            value = context.get(key, "")
            if value is None:
                return ""
            return str(value)

        return re.sub(pattern, replacer, text)

    def preview(
        self,
        template_id: int,
        sample_context: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, str, Optional[str]]:
        """Preview a template with sample data.

        Args:
            template_id: The template ID.
            sample_context: Optional custom sample data.

        Returns:
            Tuple of (subject, body_html, body_text).
        """
        # Default sample context
        context = sample_context or {
            "ticket_id": "TKT-000001",
            "ticket_subject": "Sample Ticket Subject",
            "ticket_status": "Open",
            "ticket_priority": "Medium",
            "ticket_url": "https://example.com/tickets/1",
            "customer_name": "John Doe",
            "customer_email": "john@example.com",
            "agent_name": "Jane Smith",
            "agent_email": "jane@company.com",
            "team_name": "Support Team",
            "company_name": "Example Company",
            "portal_url": "https://portal.example.com",
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "message_body": "This is a sample message body.",
        }

        return self.render(template_id, context)

    # -------------------------------------------------------------------------
    # Default Templates
    # -------------------------------------------------------------------------

    def ensure_default_templates(self, company: Optional[str] = None) -> List[SupportEmailTemplate]:
        """Ensure default templates exist.

        Creates standard notification templates if they don't exist.

        Args:
            company: Optional company scope.

        Returns:
            List of SupportEmailTemplate instances.
        """
        default_templates = [
            {
                "name": "Ticket Created",
                "template_type": "TICKET_CREATED",
                "subject": "[{{ticket_id}}] New ticket: {{ticket_subject}}",
                "body_html": """
<p>Hello {{customer_name}},</p>
<p>Thank you for contacting us. Your support ticket has been created.</p>
<p><strong>Ticket:</strong> {{ticket_id}}<br>
<strong>Subject:</strong> {{ticket_subject}}</p>
<p>Our team will review your request and respond as soon as possible.</p>
<p>You can track your ticket at: <a href="{{ticket_url}}">{{ticket_url}}</a></p>
<p>Best regards,<br>{{company_name}} Support</p>
""",
                "body_text": """Hello {{customer_name}},

Thank you for contacting us. Your support ticket has been created.

Ticket: {{ticket_id}}
Subject: {{ticket_subject}}

Our team will review your request and respond as soon as possible.

You can track your ticket at: {{ticket_url}}

Best regards,
{{company_name}} Support
""",
            },
            {
                "name": "Ticket Assigned",
                "template_type": "TICKET_ASSIGNED",
                "subject": "[{{ticket_id}}] Ticket assigned: {{ticket_subject}}",
                "body_html": """
<p>Hello {{customer_name}},</p>
<p>Your support ticket has been assigned to {{agent_name}}.</p>
<p><strong>Ticket:</strong> {{ticket_id}}<br>
<strong>Subject:</strong> {{ticket_subject}}</p>
<p>We'll follow up as soon as we have an update.</p>
<p>You can track your ticket at: <a href="{{ticket_url}}">{{ticket_url}}</a></p>
<p>Best regards,<br>{{company_name}} Support</p>
""",
                "body_text": """Hello {{customer_name}},

Your support ticket has been assigned to {{agent_name}}.

Ticket: {{ticket_id}}
Subject: {{ticket_subject}}

We'll follow up as soon as we have an update.

You can track your ticket at: {{ticket_url}}

Best regards,
{{company_name}} Support
""",
            },
            {
                "name": "Ticket In Progress",
                "template_type": "TICKET_IN_PROGRESS",
                "subject": "[{{ticket_id}}] We're working on your ticket",
                "body_html": """
<p>Hello {{customer_name}},</p>
<p>Your support ticket is now in progress.</p>
<p><strong>Ticket:</strong> {{ticket_id}}<br>
<strong>Subject:</strong> {{ticket_subject}}</p>
<p>We'll update you when we have more information.</p>
<p>You can track your ticket at: <a href="{{ticket_url}}">{{ticket_url}}</a></p>
<p>Best regards,<br>{{company_name}} Support</p>
""",
                "body_text": """Hello {{customer_name}},

Your support ticket is now in progress.

Ticket: {{ticket_id}}
Subject: {{ticket_subject}}

We'll update you when we have more information.

You can track your ticket at: {{ticket_url}}

Best regards,
{{company_name}} Support
""",
            },
            {
                "name": "Ticket Waiting on Customer",
                "template_type": "TICKET_WAITING",
                "subject": "[{{ticket_id}}] Waiting for your response",
                "body_html": """
<p>Hello {{customer_name}},</p>
<p>We're waiting for more information to continue working on your ticket.</p>
<p><strong>Ticket:</strong> {{ticket_id}}<br>
<strong>Subject:</strong> {{ticket_subject}}</p>
<p>Please reply with any additional details so we can proceed.</p>
<p>You can update your ticket at: <a href="{{ticket_url}}">{{ticket_url}}</a></p>
<p>Best regards,<br>{{company_name}} Support</p>
""",
                "body_text": """Hello {{customer_name}},

We're waiting for more information to continue working on your ticket.

Ticket: {{ticket_id}}
Subject: {{ticket_subject}}

Please reply with any additional details so we can proceed.

You can update your ticket at: {{ticket_url}}

Best regards,
{{company_name}} Support
""",
            },
            {
                "name": "Ticket On Hold",
                "template_type": "TICKET_ON_HOLD",
                "subject": "[{{ticket_id}}] Ticket on hold",
                "body_html": """
<p>Hello {{customer_name}},</p>
<p>Your support ticket is on hold while we wait on an external dependency.</p>
<p><strong>Ticket:</strong> {{ticket_id}}<br>
<strong>Subject:</strong> {{ticket_subject}}</p>
<p>We'll update you as soon as we can resume work.</p>
<p>You can track your ticket at: <a href="{{ticket_url}}">{{ticket_url}}</a></p>
<p>Best regards,<br>{{company_name}} Support</p>
""",
                "body_text": """Hello {{customer_name}},

Your support ticket is on hold while we wait on an external dependency.

Ticket: {{ticket_id}}
Subject: {{ticket_subject}}

We'll update you as soon as we can resume work.

You can track your ticket at: {{ticket_url}}

Best regards,
{{company_name}} Support
""",
            },
            {
                "name": "Ticket Replied",
                "template_type": "TICKET_REPLIED",
                "subject": "Re: [{{ticket_id}}] {{ticket_subject}}",
                "body_html": """
<p>Hello {{customer_name}},</p>
<p>{{agent_name}} has replied to your ticket:</p>
<blockquote>{{message_body}}</blockquote>
<p>You can view the full conversation at: <a href="{{ticket_url}}">{{ticket_url}}</a></p>
<p>Best regards,<br>{{company_name}} Support</p>
""",
                "body_text": """Hello {{customer_name}},

{{agent_name}} has replied to your ticket:

{{message_body}}

You can view the full conversation at: {{ticket_url}}

Best regards,
{{company_name}} Support
""",
            },
            {
                "name": "Ticket Resolved",
                "template_type": "TICKET_RESOLVED",
                "subject": "[{{ticket_id}}] Your ticket has been resolved",
                "body_html": """
<p>Hello {{customer_name}},</p>
<p>Your support ticket has been resolved.</p>
<p><strong>Ticket:</strong> {{ticket_id}}<br>
<strong>Subject:</strong> {{ticket_subject}}</p>
<p>If you have any further questions, you can reply to this email or reopen the ticket.</p>
<p>Best regards,<br>{{company_name}} Support</p>
""",
                "body_text": """Hello {{customer_name}},

Your support ticket has been resolved.

Ticket: {{ticket_id}}
Subject: {{ticket_subject}}

If you have any further questions, you can reply to this email or reopen the ticket.

Best regards,
{{company_name}} Support
""",
            },
            {
                "name": "Ticket Closed",
                "template_type": "TICKET_CLOSED",
                "subject": "[{{ticket_id}}] Ticket closed",
                "body_html": """
<p>Hello {{customer_name}},</p>
<p>Your support ticket has been closed.</p>
<p><strong>Ticket:</strong> {{ticket_id}}<br>
<strong>Subject:</strong> {{ticket_subject}}</p>
<p>If you still need help, reply to this email to reopen the ticket.</p>
<p>Best regards,<br>{{company_name}} Support</p>
""",
                "body_text": """Hello {{customer_name}},

Your support ticket has been closed.

Ticket: {{ticket_id}}
Subject: {{ticket_subject}}

If you still need help, reply to this email to reopen the ticket.

Best regards,
{{company_name}} Support
""",
            },
            {
                "name": "Ticket Reopened",
                "template_type": "TICKET_REOPENED",
                "subject": "[{{ticket_id}}] Ticket reopened",
                "body_html": """
<p>Hello {{customer_name}},</p>
<p>Your support ticket has been reopened and is back in our queue.</p>
<p><strong>Ticket:</strong> {{ticket_id}}<br>
<strong>Subject:</strong> {{ticket_subject}}</p>
<p>We'll follow up as soon as possible.</p>
<p>You can track your ticket at: <a href="{{ticket_url}}">{{ticket_url}}</a></p>
<p>Best regards,<br>{{company_name}} Support</p>
""",
                "body_text": """Hello {{customer_name}},

Your support ticket has been reopened and is back in our queue.

Ticket: {{ticket_id}}
Subject: {{ticket_subject}}

We'll follow up as soon as possible.

You can track your ticket at: {{ticket_url}}

Best regards,
{{company_name}} Support
""",
            },
            {
                "name": "Ticket Escalated",
                "template_type": "TICKET_ESCALATED",
                "subject": "[{{ticket_id}}] Ticket escalated",
                "body_html": """
<p>Hello {{customer_name}},</p>
<p>Your support ticket has been escalated to ensure it receives additional attention.</p>
<p><strong>Ticket:</strong> {{ticket_id}}<br>
<strong>Subject:</strong> {{ticket_subject}}</p>
<p>We'll keep you updated on progress.</p>
<p>You can track your ticket at: <a href="{{ticket_url}}">{{ticket_url}}</a></p>
<p>Best regards,<br>{{company_name}} Support</p>
""",
                "body_text": """Hello {{customer_name}},

Your support ticket has been escalated to ensure it receives additional attention.

Ticket: {{ticket_id}}
Subject: {{ticket_subject}}

We'll keep you updated on progress.

You can track your ticket at: {{ticket_url}}

Best regards,
{{company_name}} Support
""",
            },
            {
                "name": "SLA Warning",
                "template_type": "SLA_WARNING",
                "subject": "[URGENT] SLA Warning: {{ticket_id}} - {{ticket_subject}}",
                "body_html": """
<p>Hello {{agent_name}},</p>
<p><strong>SLA Warning:</strong> Ticket {{ticket_id}} is approaching its SLA deadline.</p>
<p><strong>Subject:</strong> {{ticket_subject}}<br>
<strong>Priority:</strong> {{ticket_priority}}<br>
<strong>Time Remaining:</strong> {{time_remaining}}</p>
<p>Please address this ticket as soon as possible.</p>
<p><a href="{{ticket_url}}">View Ticket</a></p>
""",
                "body_text": """Hello {{agent_name}},

SLA Warning: Ticket {{ticket_id}} is approaching its SLA deadline.

Subject: {{ticket_subject}}
Priority: {{ticket_priority}}
Time Remaining: {{time_remaining}}

Please address this ticket as soon as possible.

View Ticket: {{ticket_url}}
""",
            },
            {
                "name": "SLA Breach",
                "template_type": "SLA_BREACH",
                "subject": "[CRITICAL] SLA Breach: {{ticket_id}} - {{ticket_subject}}",
                "body_html": """
<p><strong>SLA BREACH ALERT</strong></p>
<p>Ticket {{ticket_id}} has breached its SLA.</p>
<p><strong>Subject:</strong> {{ticket_subject}}<br>
<strong>Priority:</strong> {{ticket_priority}}<br>
<strong>SLA Target:</strong> {{sla_target}}</p>
<p>Immediate action is required.</p>
<p><a href="{{ticket_url}}">View Ticket</a></p>
""",
                "body_text": """SLA BREACH ALERT

Ticket {{ticket_id}} has breached its SLA.

Subject: {{ticket_subject}}
Priority: {{ticket_priority}}
SLA Target: {{sla_target}}

Immediate action is required.

View Ticket: {{ticket_url}}
""",
            },
        ]

        created = []
        for t_data in default_templates:
            existing = self.get_by_type(t_data["template_type"], company)
            if existing:
                created.append(existing)
                continue

            template = SupportEmailTemplate(
                company=company,
                name=t_data["name"],
                template_type=t_data["template_type"],
                subject=t_data["subject"],
                body_html=t_data["body_html"],
                body_text=t_data["body_text"],
                is_active=True,
            )
            self.db.add(template)
            created.append(template)

        self.db.flush()
        return created

    def validate_template(self, template_id: int) -> tuple[bool, List[str]]:
        """Validate a template for common issues.

        Args:
            template_id: The template ID.

        Returns:
            Tuple of (is_valid, list_of_issues).
        """
        template = self.get(template_id)
        issues = []

        # Check for required content
        if not template.subject:
            issues.append("Subject is empty")

        if not template.body_html:
            issues.append("HTML body is empty")

        # Check for unrecognized placeholders
        all_placeholders = set(STANDARD_PLACEHOLDERS)
        type_specific = self.get_placeholders(template.template_type)
        all_placeholders.update(type_specific)

        # Extract placeholders from template
        pattern = r'\{\{(\w+)\}\}'

        for field, content in [("subject", template.subject), ("body_html", template.body_html)]:
            if not content:
                continue
            found = re.findall(pattern, content)
            for placeholder in found:
                if f"{{{{{placeholder}}}}}" not in all_placeholders:
                    issues.append(f"Unknown placeholder '{{{{{placeholder}}}}}' in {field}")

        return len(issues) == 0, issues
