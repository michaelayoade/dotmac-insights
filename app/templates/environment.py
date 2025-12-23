"""
Jinja2 Environment Configuration.

Provides a configured Jinja2 environment with:
- Package-based template loader
- Custom filters for formatting
- Global context variables (branding, settings)
- Autoescaping for HTML templates
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound

from app.templates.filters import register_filters


# Template directory path
TEMPLATES_DIR = Path(__file__).parent


@lru_cache(maxsize=1)
def get_template_env() -> Environment:
    """
    Get the configured Jinja2 environment.

    Returns a cached Environment instance with:
    - FileSystemLoader pointing to app/templates
    - Autoescape enabled for HTML files
    - Custom filters registered
    - Global context variables set
    """
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(
            enabled_extensions=("html", "htm", "xml", "html.j2"),
            default_for_string=False,
        ),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )

    # Register custom filters
    register_filters(env)

    # Add global context (branding)
    _set_globals(env)

    return env


def _set_globals(env: Environment) -> None:
    """Set global template variables."""
    # Import here to avoid circular imports
    from app.config import settings

    env.globals["settings"] = settings
    env.globals["company_name"] = getattr(settings, "company_name", "dotMac Limited")
    env.globals["product_name"] = getattr(settings, "product_name", "DotMac Insights")
    env.globals["support_email"] = getattr(settings, "support_email", "support@dotmac.com")
    env.globals["base_currency"] = getattr(settings, "base_currency", "NGN")


def render_template(
    template_name: str,
    context: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> str:
    """
    Render a template by name with the given context.

    Args:
        template_name: Path to template relative to templates dir (e.g., "emails/notification.html.j2")
        context: Dictionary of template variables
        **kwargs: Additional variables passed directly to render

    Returns:
        Rendered template string

    Raises:
        TemplateNotFound: If template does not exist
    """
    env = get_template_env()
    template = env.get_template(template_name)
    ctx = {**(context or {}), **kwargs}
    return template.render(ctx)


def render_string(
    template_str: str,
    context: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> str:
    """
    Render a template string with the given context.

    Useful for rendering templates stored in database or config files.

    Args:
        template_str: Jinja2 template string
        context: Dictionary of template variables
        **kwargs: Additional variables passed directly to render

    Returns:
        Rendered string
    """
    env = get_template_env()
    template = env.from_string(template_str)
    ctx = {**(context or {}), **kwargs}
    return template.render(ctx)


def template_exists(template_name: str) -> bool:
    """Check if a template exists."""
    env = get_template_env()
    try:
        env.get_template(template_name)
        return True
    except TemplateNotFound:
        return False


class TemplateRenderer:
    """
    Helper class for template rendering with a shared environment.

    Useful when rendering multiple templates in a service.
    """

    def __init__(self):
        self.env = get_template_env()

    def render(
        self,
        template_name: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Render a template by name."""
        template = self.env.get_template(template_name)
        ctx = {**(context or {}), **kwargs}
        return template.render(ctx)

    def render_string(
        self,
        template_str: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Render a template string."""
        template = self.env.from_string(template_str)
        ctx = {**(context or {}), **kwargs}
        return template.render(ctx)

    def exists(self, template_name: str) -> bool:
        """Check if a template exists."""
        try:
            self.env.get_template(template_name)
            return True
        except TemplateNotFound:
            return False
