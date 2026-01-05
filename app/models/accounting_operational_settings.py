"""
Accounting Operational Settings Model

Runtime/operational settings for accounting module (separate from BooksSettings policy).
Includes configuration for:
- Aging bucket thresholds
- Attachment upload limits
- Cache TTL settings
- Query/security limits
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    String, Boolean, Integer, Numeric, DateTime,
    ForeignKey, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# Default values as module constants for reference
DEFAULT_AGING_BUCKETS = [0, 30, 60, 90]
DEFAULT_ALLOWED_EXTENSIONS = [
    ".pdf", ".png", ".jpg", ".jpeg", ".gif",
    ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt"
]


class AccountingOperationalSettings(Base):
    """
    Runtime/operational accounting settings.

    One record per company (company=null for global defaults).
    Complements BooksSettings which handles accounting policy.
    """
    __tablename__ = "accounting_operational_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True,
        comment="Company scope (null = global defaults)"
    )

    # =========================================================================
    # AGING CONFIGURATION
    # =========================================================================
    aging_bucket_boundaries: Mapped[List[int]] = mapped_column(
        JSONB, default=lambda: DEFAULT_AGING_BUCKETS,
        comment="Day boundaries for aging buckets (e.g., [0, 30, 60, 90])"
    )
    max_aging_invoices: Mapped[int] = mapped_column(
        Integer, default=10000,
        comment="Maximum invoices to process in aging reports (DoS protection)"
    )

    # =========================================================================
    # ATTACHMENT SETTINGS
    # =========================================================================
    upload_directory: Mapped[str] = mapped_column(
        String(500), default="/data/attachments",
        comment="Directory for file uploads"
    )
    max_file_size_mb: Mapped[int] = mapped_column(
        Integer, default=10,
        comment="Maximum file upload size in MB"
    )
    allowed_extensions: Mapped[List[str]] = mapped_column(
        JSONB, default=lambda: DEFAULT_ALLOWED_EXTENSIONS,
        comment="Allowed file extensions for uploads"
    )

    # =========================================================================
    # CACHE TTL SETTINGS (seconds)
    # =========================================================================
    dashboard_cache_ttl: Mapped[int] = mapped_column(
        Integer, default=60,
        comment="Dashboard cache TTL in seconds"
    )
    report_cache_ttl: Mapped[int] = mapped_column(
        Integer, default=300,
        comment="Report cache TTL in seconds"
    )
    aging_cache_ttl: Mapped[int] = mapped_column(
        Integer, default=60,
        comment="Aging report cache TTL in seconds"
    )

    # =========================================================================
    # QUERY/SECURITY LIMITS
    # =========================================================================
    max_gl_export_rows: Mapped[int] = mapped_column(
        Integer, default=10000,
        comment="Maximum rows in GL export"
    )
    supplier_search_min_chars: Mapped[int] = mapped_column(
        Integer, default=2,
        comment="Minimum characters required for supplier search (DoS protection)"
    )
    reconciliation_tolerance: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), default=Decimal("0.01"),
        comment="Tolerance for reconciliation matching"
    )

    # =========================================================================
    # DEFAULT VALUES
    # =========================================================================
    default_currency: Mapped[str] = mapped_column(
        String(3), default="NGN",
        comment="Default currency code (ISO 4217)"
    )
    default_pagination_limit: Mapped[int] = mapped_column(
        Integer, default=50,
        comment="Default pagination page size"
    )
    max_pagination_limit: Mapped[int] = mapped_column(
        Integer, default=500,
        comment="Maximum pagination page size"
    )
    max_top_items: Mapped[int] = mapped_column(
        Integer, default=25,
        comment="Maximum items for 'top N' queries"
    )

    # =========================================================================
    # FEATURE FLAGS
    # =========================================================================
    enable_aging_cache: Mapped[bool] = mapped_column(
        Boolean, default=True,
        comment="Enable caching for aging reports"
    )
    enable_dashboard_cache: Mapped[bool] = mapped_column(
        Boolean, default=True,
        comment="Enable caching for dashboard"
    )

    # =========================================================================
    # TIMESTAMPS
    # =========================================================================
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    updated_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        Index("ix_acct_ops_settings_company", "company"),
        CheckConstraint("max_file_size_mb > 0 AND max_file_size_mb <= 100"),
        CheckConstraint("max_aging_invoices > 0 AND max_aging_invoices <= 100000"),
        CheckConstraint("dashboard_cache_ttl >= 0 AND dashboard_cache_ttl <= 3600"),
        CheckConstraint("report_cache_ttl >= 0 AND report_cache_ttl <= 3600"),
        CheckConstraint("reconciliation_tolerance >= 0 AND reconciliation_tolerance <= 1"),
        CheckConstraint("default_pagination_limit > 0 AND default_pagination_limit <= 1000"),
        CheckConstraint("max_pagination_limit > 0 AND max_pagination_limit <= 10000"),
    )

    @property
    def max_file_size_bytes(self) -> int:
        """Return max file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024

    @property
    def allowed_extensions_set(self) -> set:
        """Return allowed extensions as a set for faster lookup."""
        return set(self.allowed_extensions or DEFAULT_ALLOWED_EXTENSIONS)

    def get_aging_bucket_label(self, days_overdue: int) -> str:
        """Get the bucket label for a given days overdue value.

        Args:
            days_overdue: Number of days overdue (0 = current)

        Returns:
            Bucket label (e.g., "current", "1-30", "31-60", "61-90", "90+")
        """
        boundaries = self.aging_bucket_boundaries or DEFAULT_AGING_BUCKETS

        if days_overdue <= 0:
            return "current"

        # Find the appropriate bucket
        for i, boundary in enumerate(boundaries[1:], 1):
            prev_boundary = boundaries[i - 1]
            if days_overdue <= boundary:
                return f"{prev_boundary + 1}-{boundary}"

        # Beyond last boundary
        last = boundaries[-1]
        return f"{last}+"
