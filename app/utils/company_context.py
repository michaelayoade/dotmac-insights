"""Company context utilities for ensuring company scoping.

This module provides utilities to:
1. Get the current company context (from settings or request)
2. Ensure company is set on new records
3. Apply company filters to queries
"""
from typing import Optional, TypeVar, Type
from sqlalchemy.orm import Session
from sqlalchemy import inspect

from app.config import settings

T = TypeVar('T')


def get_default_company() -> str:
    """Get the default company from settings.

    Returns:
        The default company name, or raises ValueError if not configured.
    """
    if not settings.default_company:
        # In development, allow a fallback
        if settings.environment == "development":
            return "DotMac Limited"
        raise ValueError(
            "DEFAULT_COMPANY must be configured. "
            "Set the DEFAULT_COMPANY environment variable."
        )
    return settings.default_company


def get_company_context(
    explicit_company: Optional[str] = None,
    allow_null: bool = False,
) -> Optional[str]:
    """Get the company context for the current operation.

    Args:
        explicit_company: An explicitly provided company value (takes precedence)
        allow_null: If True, allows returning None when no company is set

    Returns:
        The company to use for the operation

    Raises:
        ValueError: If no company can be determined and allow_null is False
    """
    if explicit_company:
        return explicit_company

    try:
        return get_default_company()
    except ValueError:
        if allow_null:
            return None
        raise


def ensure_company(
    obj: T,
    company: Optional[str] = None,
    force: bool = False,
) -> T:
    """Ensure an object has a company set.

    Args:
        obj: The SQLAlchemy model instance
        company: Optional explicit company to set
        force: If True, overwrite existing company value

    Returns:
        The object with company set
    """
    # Check if object has company attribute
    if not hasattr(obj, 'company'):
        return obj

    # Don't overwrite if already set (unless force=True)
    current_company = getattr(obj, 'company', None)
    if current_company and not force:
        return obj

    # Get company context
    company_to_set = get_company_context(company, allow_null=True)
    if company_to_set:
        setattr(obj, 'company', company_to_set)

    return obj


def has_company_column(model_class: Type) -> bool:
    """Check if a model class has a company column.

    Args:
        model_class: The SQLAlchemy model class

    Returns:
        True if the model has a company column
    """
    try:
        mapper = inspect(model_class)
        return 'company' in [col.key for col in mapper.columns]
    except Exception:
        return False


def apply_company_filter(
    query,
    model_class: Type,
    company: Optional[str] = None,
    include_null: bool = True,
):
    """Apply company filter to a query.

    Args:
        query: The SQLAlchemy query
        model_class: The model class being queried
        company: Optional explicit company to filter by
        include_null: If True, also include records with NULL company

    Returns:
        The filtered query
    """
    if not has_company_column(model_class):
        return query

    company_value = get_company_context(company, allow_null=True)

    if not company_value:
        # No company context, return unfiltered
        return query

    if include_null:
        # Include records matching company OR with NULL company
        return query.filter(
            (model_class.company == company_value) |
            (model_class.company.is_(None))
        )
    else:
        # Strict filtering - only matching company
        return query.filter(model_class.company == company_value)


class CompanyMixin:
    """Mixin for models that should auto-set company on creation.

    Usage:
        class MyModel(CompanyMixin, Base):
            __tablename__ = 'my_table'
            company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

        # In your API endpoint:
        obj = MyModel(name="Test")
        obj.set_company_from_context()
        db.add(obj)
    """

    def set_company_from_context(
        self,
        company: Optional[str] = None,
        force: bool = False,
    ) -> None:
        """Set company from context if not already set.

        Args:
            company: Optional explicit company value
            force: If True, overwrite existing value
        """
        ensure_company(self, company, force)


# Convenience function for use in API endpoints
def with_company(
    db: Session,
    obj: T,
    company: Optional[str] = None,
) -> T:
    """Convenience function to ensure company is set and add to session.

    Usage:
        new_invoice = with_company(db, Invoice(customer_id=1, amount=100))
        db.commit()

    Args:
        db: The database session
        obj: The model instance
        company: Optional explicit company

    Returns:
        The object with company set
    """
    ensure_company(obj, company)
    return obj
