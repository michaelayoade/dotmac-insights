"""Report Export service.

This module contains business logic for exporting accounting reports.
It coordinates between report generation, format conversion, and audit logging.

All methods that mutate data do NOT commit. The caller (route handler)
is responsible for calling db.commit() after the operation succeeds.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy.orm import Session

from app.services.errors import ValidationError

from .exports_types import (
    ExportFormat,
    ExportServiceStatus,
    CacheMetadata,
    CacheKeyInfo,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["ReportExportService"]

# Cache key configuration
CACHE_KEYS = [
    CacheKeyInfo(key="accounting-dashboard", ttl_seconds=60),
    CacheKeyInfo(key="accounting-dashboard-bundle", ttl_seconds=60),
    CacheKeyInfo(key="trial-balance", ttl_seconds=60),
    CacheKeyInfo(key="balance-sheet", ttl_seconds=60),
    CacheKeyInfo(key="income-statement", ttl_seconds=60),
    CacheKeyInfo(key="accounts-payable", ttl_seconds=60),
    CacheKeyInfo(key="accounts-receivable", ttl_seconds=60),
    CacheKeyInfo(key="cash-flow", ttl_seconds=60),
    CacheKeyInfo(key="income-statement-comparative", ttl_seconds=300),
    CacheKeyInfo(key="tax-dashboard", ttl_seconds=60),
    CacheKeyInfo(key="receivables-aging-enhanced", ttl_seconds=60),
]


class ReportExportService:
    """Service for report export coordination.

    This service:
    - Validates export format
    - Checks export service availability
    - Provides cache metadata
    - Logs export operations to audit trail

    The actual report generation is delegated to ReportsService,
    and format conversion to ExportService.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    def validate_format(self, format_str: str) -> ExportFormat:
        """Validate and convert format string to enum.

        Args:
            format_str: Format string (csv or pdf).

        Returns:
            ExportFormat enum value.

        Raises:
            ValidationError: If format is invalid.
        """
        format_lower = format_str.lower()
        try:
            return ExportFormat(format_lower)
        except ValueError:
            valid_formats = [f.value for f in ExportFormat]
            raise ValidationError(
                f"Invalid export format: {format_str}. "
                f"Valid formats: {', '.join(valid_formats)}"
            )

    def get_export_status(self) -> ExportServiceStatus:
        """Get export service availability status.

        Returns:
            ExportServiceStatus with service availability.
        """
        from app.services.export_service import WEASYPRINT_AVAILABLE

        return ExportServiceStatus(
            as_of=datetime.now(timezone.utc).isoformat() + "Z",
            csv_available=True,
            pdf_available=bool(WEASYPRINT_AVAILABLE),
            pdf_requires="weasyprint",
        )

    def is_pdf_available(self) -> bool:
        """Check if PDF export is available.

        Returns:
            True if PDF export is available.
        """
        from app.services.export_service import WEASYPRINT_AVAILABLE
        return bool(WEASYPRINT_AVAILABLE)

    async def get_cache_metadata(self) -> CacheMetadata:
        """Get cache metadata for accounting endpoints.

        Returns:
            CacheMetadata with cache configuration.
        """
        from app.cache import get_redis_client

        client = await get_redis_client()

        return CacheMetadata(
            as_of=datetime.now(timezone.utc).isoformat() + "Z",
            cache_available=client is not None,
            keys=CACHE_KEYS,
        )

    def log_export(
        self,
        report_type: str,
        format: ExportFormat,
        description: str,
        record_count: Optional[int] = None,
    ) -> None:
        """Log an export operation to audit trail.

        Args:
            report_type: Type of report (trial_balance, balance_sheet, etc.).
            format: Export format used.
            description: Human-readable description of the export.
            record_count: Optional number of records exported.

        Note: Does not commit. Caller should commit after route handler succeeds.
        """
        from app.services.audit_logger import AuditLogger

        audit = AuditLogger(self.db)

        remarks = f"Exported as {format.value.upper()}"
        if record_count is not None:
            remarks += f", {record_count} records"

        audit.log_export(
            doctype=report_type,
            document_id=0,
            user_id=self.principal.id if self.principal else None,
            document_name=description,
            remarks=remarks,
        )

    def export_to_csv(self, data: Dict[str, Any], report_type: str) -> bytes:
        """Export report data to CSV format.

        Args:
            data: Report data dictionary.
            report_type: Type of report for formatting.

        Returns:
            CSV content as bytes.

        Raises:
            ValidationError: If export fails.
        """
        from app.services.export_service import ExportService, ExportError

        export_service = ExportService()

        try:
            return export_service.export_csv(data, report_type)
        except ExportError as e:
            raise ValidationError(f"CSV export failed: {str(e)}")

    def export_to_pdf(self, data: Dict[str, Any], report_type: str) -> bytes:
        """Export report data to PDF format.

        Args:
            data: Report data dictionary.
            report_type: Type of report for formatting.

        Returns:
            PDF content as bytes.

        Raises:
            ValidationError: If export fails or PDF not available.
        """
        from app.services.export_service import ExportService, ExportError

        if not self.is_pdf_available():
            raise ValidationError(
                "PDF export is not available. Install weasyprint to enable."
            )

        export_service = ExportService()

        try:
            return export_service.export_pdf(data, report_type)
        except ExportError as e:
            raise ValidationError(f"PDF export failed: {str(e)}")

    def export(
        self,
        data: Dict[str, Any],
        report_type: str,
        format: ExportFormat,
    ) -> bytes:
        """Export report data to specified format.

        Args:
            data: Report data dictionary.
            report_type: Type of report for formatting.
            format: Export format.

        Returns:
            Exported content as bytes.

        Raises:
            ValidationError: If export fails.
        """
        if format == ExportFormat.CSV:
            return self.export_to_csv(data, report_type)
        else:
            return self.export_to_pdf(data, report_type)

    def get_content_type(self, format: ExportFormat) -> str:
        """Get HTTP content type for export format.

        Args:
            format: Export format.

        Returns:
            MIME type string.
        """
        if format == ExportFormat.CSV:
            return "text/csv"
        return "application/pdf"

    def get_file_extension(self, format: ExportFormat) -> str:
        """Get file extension for export format.

        Args:
            format: Export format.

        Returns:
            File extension (without dot).
        """
        return format.value
