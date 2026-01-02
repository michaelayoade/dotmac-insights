"""Type definitions for accounting settings service.

These dataclasses define the contract for settings operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional

__all__ = [
    "AgingConfig",
    "AttachmentConfig",
    "CacheConfig",
    "QueryLimitsConfig",
    "SettingsUpdateData",
]


@dataclass
class AgingConfig:
    """Configuration for aging reports."""

    bucket_boundaries: List[int] = field(default_factory=lambda: [0, 30, 60, 90])
    max_invoices: int = 10000

    def get_bucket_label(self, days_overdue: int) -> str:
        """Get the bucket label for a given days overdue value.

        Args:
            days_overdue: Number of days overdue (0 = current)

        Returns:
            Bucket label (e.g., "current", "1-30", "31-60", "61-90", "90+")
        """
        if days_overdue <= 0:
            return "current"

        for i, boundary in enumerate(self.bucket_boundaries[1:], 1):
            prev_boundary = self.bucket_boundaries[i - 1]
            if days_overdue <= boundary:
                return f"{prev_boundary + 1}-{boundary}"

        last = self.bucket_boundaries[-1]
        return f"{last}+"

    def get_bucket_names(self) -> List[str]:
        """Get list of all bucket names in order."""
        names = ["current"]
        for i, boundary in enumerate(self.bucket_boundaries[1:], 1):
            prev = self.bucket_boundaries[i - 1]
            names.append(f"{prev + 1}-{boundary}")
        names.append(f"{self.bucket_boundaries[-1]}+")
        return names


@dataclass
class AttachmentConfig:
    """Configuration for file attachments."""

    upload_directory: str = "/data/attachments"
    max_file_size_mb: int = 10
    allowed_extensions: List[str] = field(default_factory=lambda: [
        ".pdf", ".png", ".jpg", ".jpeg", ".gif",
        ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt"
    ])

    @property
    def max_file_size_bytes(self) -> int:
        """Return max file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024

    @property
    def allowed_extensions_set(self) -> set:
        """Return allowed extensions as a set for faster lookup."""
        return set(self.allowed_extensions)


@dataclass
class CacheConfig:
    """Configuration for caching."""

    dashboard_ttl: int = 60
    report_ttl: int = 300
    aging_ttl: int = 60
    enable_aging_cache: bool = True
    enable_dashboard_cache: bool = True


@dataclass
class QueryLimitsConfig:
    """Configuration for query limits and security."""

    max_gl_export_rows: int = 10000
    supplier_search_min_chars: int = 2
    reconciliation_tolerance: Decimal = Decimal("0.01")
    default_pagination_limit: int = 50
    max_pagination_limit: int = 500
    max_top_items: int = 25
    default_currency: str = "NGN"


@dataclass
class SettingsUpdateData:
    """Data for updating accounting operational settings."""

    # Aging Configuration
    aging_bucket_boundaries: Optional[List[int]] = None
    max_aging_invoices: Optional[int] = None

    # Attachment Settings
    upload_directory: Optional[str] = None
    max_file_size_mb: Optional[int] = None
    allowed_extensions: Optional[List[str]] = None

    # Cache TTL Settings
    dashboard_cache_ttl: Optional[int] = None
    report_cache_ttl: Optional[int] = None
    aging_cache_ttl: Optional[int] = None

    # Query/Security Limits
    max_gl_export_rows: Optional[int] = None
    supplier_search_min_chars: Optional[int] = None
    reconciliation_tolerance: Optional[Decimal] = None

    # Default Values
    default_currency: Optional[str] = None
    default_pagination_limit: Optional[int] = None
    max_pagination_limit: Optional[int] = None
    max_top_items: Optional[int] = None

    # Feature Flags
    enable_aging_cache: Optional[bool] = None
    enable_dashboard_cache: Optional[bool] = None
