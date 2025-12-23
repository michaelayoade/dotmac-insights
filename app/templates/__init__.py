"""
Jinja2 Template System for DotMac Insights.

This package provides templating infrastructure for:
- Customer notifications (service orders, tickets, invoices)
- Internal notifications (approvals, alerts, reminders)
- PDF report generation (financial statements)
- Email templates (HTML and plain text)
"""

from app.templates.environment import get_template_env, render_template
from app.templates.filters import register_filters

__all__ = ["get_template_env", "render_template", "register_filters"]
