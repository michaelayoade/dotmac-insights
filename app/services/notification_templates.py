"""Notification template registry and rendering helpers.

All templates are loaded from Jinja2 files in app/templates/notifications/.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import structlog
from jinja2 import TemplateNotFound

from app.models.notification import NotificationEventType
from app.templates.environment import get_template_env, render_string

logger = structlog.get_logger()


def render_template(template: str, context: Dict[str, Any]) -> str:
    """
    Render a Jinja2 template string with the given context.

    Args:
        template: Jinja2 template string
        context: Dictionary of template variables

    Returns:
        Rendered string

    Raises:
        jinja2.TemplateError: If template rendering fails
    """
    return render_string(template, context)


@dataclass(frozen=True)
class NotificationTemplate:
    """Represents a notification template with all its attributes."""
    title: str
    message: str
    icon: str
    priority: str
    context: Dict[str, Any]
    email_subject: Optional[str] = None
    email_body_html: Optional[str] = None
    email_body_text: Optional[str] = None


class NotificationTemplateRegistry:
    """
    Loads notification templates from Jinja2 files.

    Template files are located at: app/templates/notifications/{event_type}.txt.j2
    """

    def __init__(self):
        self._template_env = get_template_env()

    def get_template(
        self,
        event_type: NotificationEventType,
        context: Optional[Dict[str, Any]] = None,
    ) -> NotificationTemplate:
        """
        Get a notification template for the given event type.

        Args:
            event_type: The notification event type
            context: Optional context to use for rendering

        Returns:
            NotificationTemplate with resolved values

        Raises:
            TemplateNotFound: If no template exists for the event type
        """
        template_name = f"notifications/{event_type.value}.txt.j2"
        merged_context = context or {}

        template = self._template_env.get_template(template_name)

        # Render the template to get the message
        rendered = template.render(merged_context)

        # Extract title, icon, priority from template module
        # These are set as {% set title = "..." %} in the template
        module = template.module
        title = getattr(module, "title", event_type.value.replace("_", " ").title())
        icon = getattr(module, "icon", "bell")
        priority = getattr(module, "priority", "normal")

        return NotificationTemplate(
            title=str(title),
            message=rendered.strip(),
            icon=str(icon),
            priority=str(priority),
            context=merged_context,
        )

    def render(
        self,
        event_type: NotificationEventType,
        context: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Get and render a notification template.

        Args:
            event_type: The notification event type
            context: Template context variables

        Returns:
            Dict with 'title', 'message', 'icon', and 'priority' keys
        """
        template = self.get_template(event_type, context)

        return {
            "title": template.title,
            "message": template.message,
            "icon": template.icon,
            "priority": template.priority,
        }
