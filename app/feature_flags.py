"""
Feature Flags Module

Provides feature flag configuration for gradual rollout of new features.
Flags are configurable via environment variables with FF_ prefix.

Usage:
    from app.feature_flags import feature_flags

    if feature_flags.CONTACTS_DUAL_WRITE_ENABLED:
        await legacy_customer_service.sync_from_unified(db, contact)

Environment variables:
    FF_CONTACTS_DUAL_WRITE_ENABLED=true
    FF_CONTACTS_OUTBOUND_SYNC_ENABLED=true
    FF_CONTACTS_RECONCILIATION_ENABLED=true
    FF_SOFT_DELETE_ENABLED=true
"""
from pydantic_settings import BaseSettings
from app.config import settings


class FeatureFlags(BaseSettings):
    """Feature flags for gradual rollout of new functionality."""

    # =========================================================================
    # CONTACTS DOMAIN FLAGS
    # =========================================================================

    # Enable dual-write to both unified_contacts and legacy tables (customers)
    # When true, creating/updating a UnifiedContact also updates the legacy Customer
    CONTACTS_DUAL_WRITE_ENABLED: bool = False

    # Enable outbound sync to external systems (Splynx, ERPNext)
    # When true, contact changes are pushed to external systems
    CONTACTS_OUTBOUND_SYNC_ENABLED: bool = False

    # Enable dry-run mode for outbound sync (log only, no actual API calls)
    # When true with OUTBOUND_SYNC_ENABLED, logs sync intent but skips API push
    # Useful for staging burn-in before enabling real pushes
    CONTACTS_OUTBOUND_DRY_RUN: bool = True

    # Enable reconciliation job to detect drift between systems
    # When true, periodic reconciliation compares local vs external data
    CONTACTS_RECONCILIATION_ENABLED: bool = False

    # =========================================================================
    # DATA MANAGEMENT FLAGS
    # =========================================================================

    # Enable soft delete for entities with dependencies (customers, employees)
    # When true, DELETE requests mark records as deleted instead of hard delete
    SOFT_DELETE_ENABLED: bool = False

    # =========================================================================
    # TICKETS DOMAIN FLAGS
    # =========================================================================

    # Enable dual-write to both unified_tickets and legacy tables (tickets, conversations)
    # When true, creating/updating a UnifiedTicket also updates the legacy Ticket
    TICKETS_DUAL_WRITE_ENABLED: bool = False

    # Enable outbound sync to external systems (Splynx, ERPNext, Chatwoot)
    # When true, ticket changes are pushed to external systems
    TICKETS_OUTBOUND_SYNC_ENABLED: bool = False

    # Enable dry-run mode for ticket outbound sync (log only, no actual API calls)
    # When true with OUTBOUND_SYNC_ENABLED, logs sync intent but skips API push
    TICKETS_OUTBOUND_DRY_RUN: bool = True

    # Enable reconciliation job to detect drift between ticket systems
    # When true, periodic reconciliation compares local vs external ticket data
    TICKETS_RECONCILIATION_ENABLED: bool = False

    # =========================================================================
    # COMPLIANCE ADD-ONS
    # =========================================================================

    # Enable Nigeria compliance bundle (VAT, WHT, PAYE, CIT, e-invoicing)
    NIGERIA_COMPLIANCE_ENABLED: bool = False

    # Enable statutory payroll deductions (reserved for compliance add-ons)
    STATUTORY_CALCULATIONS_ENABLED: bool = False

    # =========================================================================
    # BILLING DOMAIN FLAGS
    # =========================================================================

    # Enable outbound sync for invoices and payments to ERPNext
    # When true, invoice/payment changes are pushed to ERPNext
    BILLING_OUTBOUND_SYNC_ENABLED: bool = False

    # Enable dry-run mode for billing outbound sync (log only, no actual API calls)
    # When true with OUTBOUND_SYNC_ENABLED, logs sync intent but skips API push
    BILLING_OUTBOUND_DRY_RUN: bool = True

    # =========================================================================
    # FUTURE FLAGS (not yet implemented)
    # =========================================================================

    # Enable native billing APIs (bypass ERPNext)
    # BILLING_NATIVE_ENABLED: bool = False

    class Config:
        env_prefix = "FF_"
        env_file = ".env"
        extra = "ignore"


# Singleton instance
feature_flags = FeatureFlags()


def get_feature_flags() -> FeatureFlags:
    """Get the feature flags instance (for dependency injection)."""
    return feature_flags


def is_feature_enabled(flag_name: str) -> bool:
    """
    Check if a feature flag is enabled.

    Args:
        flag_name: Name of the flag (e.g., "CONTACTS_DUAL_WRITE_ENABLED")

    Returns:
        True if the flag is enabled, False otherwise

    Example:
        if is_feature_enabled("CONTACTS_DUAL_WRITE_ENABLED"):
            # do dual write
    """
    return getattr(feature_flags, flag_name, False)


def refresh_feature_flags():
    """
    Refresh feature flags from platform (best effort).
    This is a synchronous wrapper; platform integration logic lives in
    app.services.platform_integration.refresh_feature_flags_from_platform.
    """
    from app.services.platform_integration import refresh_feature_flags_from_platform

    if settings.platform_api_url:
        refresh_feature_flags_from_platform()
