"""Notification template registry and rendering helpers."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, cast

import structlog

from app.config import settings
from app.models.notification import NotificationEventType

logger = structlog.get_logger()


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return ""


def render_template(template: str, context: Dict[str, Any]) -> str:
    """Render a template string with safe fallback values."""
    return template.format_map(_SafeFormatDict(context))


@dataclass(frozen=True)
class NotificationTemplate:
    title: str
    message: str
    icon: str
    priority: str
    context: Dict[str, Any]
    email_subject: Optional[str] = None
    email_body_html: Optional[str] = None
    email_body_text: Optional[str] = None


class NotificationTemplateRegistry:
    """Loads notification templates from disk with defaults."""

    def __init__(self, templates_path: Optional[str] = None):
        self.templates_path = templates_path or settings.notification_templates_path
        self._templates: Optional[Dict[str, Any]] = None

    def _load_templates(self) -> Dict[str, Any]:
        path = Path(self.templates_path)
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = cast(Dict[str, Any], json.load(handle))
        except FileNotFoundError:
            logger.warning("notification_templates_missing", path=str(path))
            data = {}
        except json.JSONDecodeError as exc:
            logger.error("notification_templates_invalid", path=str(path), error=str(exc))
            data = {}

        self._templates = data
        return data

    def _get_templates(self) -> Dict[str, Any]:
        if self._templates is None:
            return self._load_templates()
        return self._templates

    def get_template(self, event_type: NotificationEventType) -> NotificationTemplate:
        templates = self._get_templates()
        defaults = templates.get("defaults", {})
        event_templates = templates.get("events", {})
        event_template = event_templates.get(event_type.value, {})

        merged = {**defaults, **event_template}
        context = {
            **defaults.get("context", {}),
            **event_template.get("context", {}),
        }

        return NotificationTemplate(
            title=merged.get("title", "Notification"),
            message=merged.get("message", "{message}"),
            icon=merged.get("icon", "bell"),
            priority=merged.get("priority", "normal"),
            context=context,
            email_subject=merged.get("email_subject"),
            email_body_html=merged.get("email_body_html"),
            email_body_text=merged.get("email_body_text"),
        )
