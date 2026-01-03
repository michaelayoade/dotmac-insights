"""Utility modules."""
from app.utils.company_context import (
    get_default_company,
    get_company_context,
    ensure_company,
    has_company_column,
    apply_company_filter,
    with_company,
    CompanyMixin,
)


def escape_like_pattern(value: str) -> str:
    """Escape SQL LIKE special characters to prevent pattern injection.

    User input containing % or _ can match unintended rows in LIKE queries.
    This function escapes those characters so they are treated literally.

    Usage:
        query.filter(Model.name.ilike(f"%{escape_like_pattern(search)}%", escape="\\\\"))

    Args:
        value: The user-provided search string

    Returns:
        Escaped string safe for use in LIKE patterns
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


__all__ = [
    "get_default_company",
    "get_company_context",
    "ensure_company",
    "has_company_column",
    "apply_company_filter",
    "with_company",
    "CompanyMixin",
    "escape_like_pattern",
]
