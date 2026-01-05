"""Accounting settings service - business logic for operational settings.

This service provides access to configurable accounting settings:
- Aging bucket configuration
- Attachment upload limits
- Cache TTL settings
- Query/security limits

Routes and other services should use this to access configuration
instead of hardcoding values.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Session

from app.models.accounting_operational_settings import (
    AccountingOperationalSettings,
    DEFAULT_AGING_BUCKETS,
    DEFAULT_ALLOWED_EXTENSIONS,
)
from app.services.errors import NotFoundError, ValidationError

from .settings_types import (
    AgingConfig,
    AttachmentConfig,
    CacheConfig,
    QueryLimitsConfig,
    SettingsUpdateData,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["AccountingSettingsService"]


class AccountingSettingsService:
    """Service for accessing accounting operational settings.

    Provides typed configuration objects for different setting categories.
    Supports company-scoped settings with global fallback.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for audit fields).
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _get_settings(self, company: Optional[str] = None) -> AccountingOperationalSettings:
        """Get settings for a company with global fallback.

        Args:
            company: Company code to get settings for. If None, returns global.

        Returns:
            Settings object (company-specific or global fallback).
        """
        # Try company-specific first
        if company:
            settings = self.db.query(AccountingOperationalSettings).filter(
                AccountingOperationalSettings.company == company
            ).first()
            if settings:
                return settings

        # Fall back to global (company=NULL)
        settings = self.db.query(AccountingOperationalSettings).filter(
            AccountingOperationalSettings.company.is_(None)
        ).first()

        if settings:
            return settings

        # Return in-memory defaults without persisting (read should not modify)
        return AccountingOperationalSettings(company=None)

    # -------------------------------------------------------------------------
    # Public accessors - typed configuration objects
    # -------------------------------------------------------------------------

    def get_settings(self, company: Optional[str] = None) -> AccountingOperationalSettings:
        """Get the full settings object for a company.

        Args:
            company: Company code (None for global defaults).

        Returns:
            AccountingOperationalSettings instance.
        """
        return self._get_settings(company)

    def get_aging_config(self, company: Optional[str] = None) -> AgingConfig:
        """Get aging report configuration.

        Args:
            company: Company code (None for global defaults).

        Returns:
            AgingConfig with bucket boundaries and limits.
        """
        settings = self._get_settings(company)
        return AgingConfig(
            bucket_boundaries=settings.aging_bucket_boundaries or DEFAULT_AGING_BUCKETS,
            max_invoices=settings.max_aging_invoices,
        )

    def get_attachment_config(self, company: Optional[str] = None) -> AttachmentConfig:
        """Get attachment upload configuration.

        Args:
            company: Company code (None for global defaults).

        Returns:
            AttachmentConfig with upload directory, size limits, and extensions.
        """
        settings = self._get_settings(company)
        return AttachmentConfig(
            upload_directory=settings.upload_directory,
            max_file_size_mb=settings.max_file_size_mb,
            allowed_extensions=settings.allowed_extensions or DEFAULT_ALLOWED_EXTENSIONS,
        )

    def get_cache_config(self, company: Optional[str] = None) -> CacheConfig:
        """Get cache TTL configuration.

        Args:
            company: Company code (None for global defaults).

        Returns:
            CacheConfig with TTL values and feature flags.
        """
        settings = self._get_settings(company)
        return CacheConfig(
            dashboard_ttl=settings.dashboard_cache_ttl,
            report_ttl=settings.report_cache_ttl,
            aging_ttl=settings.aging_cache_ttl,
            enable_aging_cache=settings.enable_aging_cache,
            enable_dashboard_cache=settings.enable_dashboard_cache,
        )

    def get_query_limits(self, company: Optional[str] = None) -> QueryLimitsConfig:
        """Get query limits and security configuration.

        Args:
            company: Company code (None for global defaults).

        Returns:
            QueryLimitsConfig with pagination, export, and security limits.
        """
        settings = self._get_settings(company)
        return QueryLimitsConfig(
            max_gl_export_rows=settings.max_gl_export_rows,
            supplier_search_min_chars=settings.supplier_search_min_chars,
            reconciliation_tolerance=settings.reconciliation_tolerance,
            default_pagination_limit=settings.default_pagination_limit,
            max_pagination_limit=settings.max_pagination_limit,
            max_top_items=settings.max_top_items,
            default_currency=settings.default_currency,
        )

    # -------------------------------------------------------------------------
    # Mutations
    # -------------------------------------------------------------------------

    def update_settings(
        self,
        data: SettingsUpdateData,
        company: Optional[str] = None,
    ) -> AccountingOperationalSettings:
        """Update accounting operational settings.

        Args:
            data: Fields to update.
            company: Company code (None for global defaults).

        Returns:
            Updated settings object.

        Raises:
            ValidationError: If validation fails.
        """
        settings = self._get_settings(company)

        # Validate aging buckets if provided
        if data.aging_bucket_boundaries is not None:
            if len(data.aging_bucket_boundaries) < 2:
                raise ValidationError("aging_bucket_boundaries must have at least 2 values")
            if data.aging_bucket_boundaries[0] != 0:
                raise ValidationError("aging_bucket_boundaries must start with 0")
            if sorted(data.aging_bucket_boundaries) != data.aging_bucket_boundaries:
                raise ValidationError("aging_bucket_boundaries must be in ascending order")

        # Validate allowed extensions if provided
        if data.allowed_extensions is not None:
            for ext in data.allowed_extensions:
                if not ext.startswith("."):
                    raise ValidationError(f"Extension '{ext}' must start with '.'")

        # Apply updates (only non-None values)
        update_fields = [
            "aging_bucket_boundaries", "max_aging_invoices",
            "upload_directory", "max_file_size_mb", "allowed_extensions",
            "dashboard_cache_ttl", "report_cache_ttl", "aging_cache_ttl",
            "max_gl_export_rows", "supplier_search_min_chars", "reconciliation_tolerance",
            "default_currency", "default_pagination_limit", "max_pagination_limit",
            "max_top_items", "enable_aging_cache", "enable_dashboard_cache",
        ]

        for field_name in update_fields:
            value = getattr(data, field_name, None)
            if value is not None:
                setattr(settings, field_name, value)

        # Set audit fields
        if self.principal and hasattr(self.principal, "user_id"):
            settings.updated_by_id = self.principal.user_id

        self.db.flush()
        return settings

    def create_company_settings(
        self,
        company: str,
        data: Optional[SettingsUpdateData] = None,
    ) -> AccountingOperationalSettings:
        """Create company-specific settings (copies from global defaults).

        Args:
            company: Company code.
            data: Optional overrides to apply.

        Returns:
            New company-specific settings.

        Raises:
            ValidationError: If company settings already exist.
        """
        if not company:
            raise ValidationError("Company code is required")

        # Check if company settings already exist
        existing = self.db.query(AccountingOperationalSettings).filter(
            AccountingOperationalSettings.company == company
        ).first()
        if existing:
            raise ValidationError(f"Settings for company '{company}' already exist")

        # Get global defaults
        global_settings = self._get_settings(None)

        # Create new company settings copying from global
        settings = AccountingOperationalSettings(
            company=company,
            aging_bucket_boundaries=global_settings.aging_bucket_boundaries,
            max_aging_invoices=global_settings.max_aging_invoices,
            upload_directory=global_settings.upload_directory,
            max_file_size_mb=global_settings.max_file_size_mb,
            allowed_extensions=global_settings.allowed_extensions,
            dashboard_cache_ttl=global_settings.dashboard_cache_ttl,
            report_cache_ttl=global_settings.report_cache_ttl,
            aging_cache_ttl=global_settings.aging_cache_ttl,
            max_gl_export_rows=global_settings.max_gl_export_rows,
            supplier_search_min_chars=global_settings.supplier_search_min_chars,
            reconciliation_tolerance=global_settings.reconciliation_tolerance,
            default_currency=global_settings.default_currency,
            default_pagination_limit=global_settings.default_pagination_limit,
            max_pagination_limit=global_settings.max_pagination_limit,
            max_top_items=global_settings.max_top_items,
            enable_aging_cache=global_settings.enable_aging_cache,
            enable_dashboard_cache=global_settings.enable_dashboard_cache,
        )

        self.db.add(settings)
        self.db.flush()

        # Apply any overrides
        if data:
            return self.update_settings(data, company)

        return settings

    def delete_company_settings(self, company: str) -> None:
        """Delete company-specific settings (revert to global).

        Args:
            company: Company code.

        Raises:
            NotFoundError: If company settings don't exist.
            ValidationError: If trying to delete global settings.
        """
        if not company:
            raise ValidationError("Cannot delete global settings")

        settings = self.db.query(AccountingOperationalSettings).filter(
            AccountingOperationalSettings.company == company
        ).first()

        if not settings:
            raise NotFoundError(f"Settings for company '{company}' not found")

        self.db.delete(settings)
        self.db.flush()
