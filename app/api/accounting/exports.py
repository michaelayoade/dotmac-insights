"""Exports: Report exports (CSV/PDF), cache metadata, export status."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth import Require, Principal, get_current_principal
from app.cache import CACHE_TTL
from app.database import get_db
from app.services.accounting import ReportExportService
from app.services.accounting.exports_types import ExportFormat
from app.services.errors import ValidationError as ServiceValidationError

router = APIRouter()


# SERVICE DEPENDENCIES


def get_export_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> ReportExportService:
    """Dependency to get a ReportExportService instance."""
    return ReportExportService(db, principal)


# HELPER FUNCTIONS


def _export_headers(base_filename: str, extension: str) -> Dict[str, str]:
    """Build Content-Disposition headers for streamed exports."""
    filename = base_filename or "export"
    return {"Content-Disposition": f'attachment; filename="{filename}.{extension}"'}


def _stream_export(content: Any, media_type: str, base_filename: str, extension: str) -> StreamingResponse:
    """Return a streaming response with consistent headers."""
    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers=_export_headers(base_filename, extension),
    )


def _validate_format(format_str: str, service: ReportExportService) -> ExportFormat:
    """Validate export format."""
    try:
        return service.validate_format(format_str)
    except ServiceValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)


# CACHE & EXPORT METADATA


@router.get("/cache-metadata", dependencies=[Depends(Require("accounting:read"))])
async def get_accounting_cache_metadata(
    service: ReportExportService = Depends(get_export_service),
) -> Dict[str, Any]:
    """Expose TTL metadata for cached accounting endpoints.

    Returns:
        Cache configuration and availability status
    """
    cache_metadata = await service.get_cache_metadata()

    return {
        "as_of": cache_metadata.as_of,
        "presets": CACHE_TTL,
        "cache_available": cache_metadata.cache_available,
        "keys": [{"key": k.key, "ttl_seconds": k.ttl_seconds} for k in cache_metadata.keys],
    }


@router.get("/exports/status", dependencies=[Depends(Require("books:read"))])
def get_export_status(
    service: ReportExportService = Depends(get_export_service),
) -> Dict[str, Any]:
    """Lightweight health signal for export services.

    Returns:
        Export service availability status
    """
    status = service.get_export_status()

    return {
        "as_of": status.as_of,
        "services": {
            "csv": {"available": status.csv_available},
            "pdf": {
                "available": status.pdf_available,
                "requires": status.pdf_requires,
            },
        },
    }


# TRIAL BALANCE EXPORT


@router.get("/trial-balance/export", dependencies=[Depends(Require("books:read"))])
def export_trial_balance(
    format: str = Query("csv", description="Export format: csv or pdf"),
    as_of_date: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    cost_center: Optional[str] = None,
    filename: Optional[str] = Query(None, description="Override download filename (without extension)"),
    db: Session = Depends(get_db),
    service: ReportExportService = Depends(get_export_service),
):
    """Export trial balance report to CSV or PDF.

    Args:
        format: Export format (csv or pdf)
        as_of_date: Report as of date
        fiscal_year: Fiscal year filter
        cost_center: Cost center filter
        filename: Custom filename for download

    Returns:
        Streaming file response
    """
    from .reports import get_trial_balance

    export_format = _validate_format(format, service)

    # Get report data
    data = get_trial_balance(
        as_of_date=as_of_date,
        fiscal_year=fiscal_year,
        cost_center=cost_center,
        drill=False,
        db=db,
    )

    # Log the export
    service.log_export(
        report_type="trial_balance",
        format=export_format,
        description=f"Trial Balance {as_of_date or 'today'}",
    )
    db.commit()

    # Export using service
    try:
        base_filename = filename or "trial_balance"
        content = service.export(data, "trial_balance", export_format)
        content_type = service.get_content_type(export_format)
        extension = service.get_file_extension(export_format)
        return _stream_export(content, content_type, base_filename, extension)
    except ServiceValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)


# BALANCE SHEET EXPORT


@router.get("/balance-sheet/export", dependencies=[Depends(Require("books:read"))])
def export_balance_sheet(
    format: str = Query("csv", description="Export format: csv or pdf"),
    as_of_date: Optional[str] = None,
    comparative_date: Optional[str] = None,
    filename: Optional[str] = Query(None, description="Override download filename (without extension)"),
    db: Session = Depends(get_db),
    service: ReportExportService = Depends(get_export_service),
):
    """Export balance sheet report to CSV or PDF.

    Args:
        format: Export format (csv or pdf)
        as_of_date: Report as of date
        comparative_date: Comparative period date
        filename: Custom filename for download

    Returns:
        Streaming file response
    """
    from .reports import get_balance_sheet

    export_format = _validate_format(format, service)

    # Get report data
    data = get_balance_sheet(
        as_of_date=as_of_date,
        comparative_date=comparative_date,
        common_size=False,
        db=db,
    )

    # Log the export
    service.log_export(
        report_type="balance_sheet",
        format=export_format,
        description=f"Balance Sheet {as_of_date or 'today'}",
    )
    db.commit()

    # Export using service
    try:
        base_filename = filename or "balance_sheet"
        content = service.export(data, "balance_sheet", export_format)
        content_type = service.get_content_type(export_format)
        extension = service.get_file_extension(export_format)
        return _stream_export(content, content_type, base_filename, extension)
    except ServiceValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)


# INCOME STATEMENT EXPORT


@router.get("/income-statement/export", dependencies=[Depends(Require("books:read"))])
def export_income_statement(
    format: str = Query("csv", description="Export format: csv or pdf"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    cost_center: Optional[str] = None,
    basis: str = Query("accrual", description="Accounting basis: accrual or cash"),
    filename: Optional[str] = Query(None, description="Override download filename (without extension)"),
    db: Session = Depends(get_db),
    service: ReportExportService = Depends(get_export_service),
):
    """Export income statement report to CSV or PDF.

    Args:
        format: Export format (csv or pdf)
        start_date: Period start date
        end_date: Period end date
        fiscal_year: Fiscal year filter
        cost_center: Cost center filter
        basis: Accounting basis (accrual or cash)
        filename: Custom filename for download

    Returns:
        Streaming file response
    """
    from .reports import get_income_statement

    export_format = _validate_format(format, service)

    # Get report data
    data = get_income_statement(
        start_date=start_date,
        end_date=end_date,
        fiscal_year=fiscal_year,
        cost_center=cost_center,
        compare_start=None,
        compare_end=None,
        show_ytd=False,
        common_size=False,
        basis=basis,
        db=db,
    )

    # Log the export
    service.log_export(
        report_type="income_statement",
        format=export_format,
        description=f"Income Statement {start_date or ''} to {end_date or 'today'}",
    )
    db.commit()

    # Export using service
    try:
        base_filename = filename or "income_statement"
        content = service.export(data, "income_statement", export_format)
        content_type = service.get_content_type(export_format)
        extension = service.get_file_extension(export_format)
        return _stream_export(content, content_type, base_filename, extension)
    except ServiceValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)


# GENERAL LEDGER EXPORT


@router.get("/general-ledger/export", dependencies=[Depends(Require("books:read"))])
def export_general_ledger(
    format: str = Query("csv", description="Export format: csv or pdf"),
    account: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    party_type: Optional[str] = None,
    party: Optional[str] = None,
    voucher_type: Optional[str] = None,
    limit: int = Query(default=1000, le=10000),
    filename: Optional[str] = Query(None, description="Override download filename (without extension)"),
    db: Session = Depends(get_db),
    service: ReportExportService = Depends(get_export_service),
):
    """Export general ledger to CSV or PDF.

    Args:
        format: Export format (csv or pdf)
        account: Filter by account
        start_date: Period start date
        end_date: Period end date
        party_type: Filter by party type
        party: Filter by party
        voucher_type: Filter by voucher type
        limit: Max records to export
        filename: Custom filename for download

    Returns:
        Streaming file response
    """
    from .ledger import get_general_ledger

    export_format = _validate_format(format, service)

    # Get report data
    data = get_general_ledger(
        account=account,
        start_date=start_date,
        end_date=end_date,
        party_type=party_type,
        party=party,
        voucher_type=voucher_type,
        limit=limit,
        offset=0,
        db=db,
    )

    # Log the export
    service.log_export(
        report_type="general_ledger",
        format=export_format,
        description=f"General Ledger {start_date or ''} to {end_date or ''}",
        record_count=data.get("total", 0),
    )
    db.commit()

    # Export using service
    try:
        base_filename = filename or "general_ledger"
        content = service.export(data, "general_ledger", export_format)
        content_type = service.get_content_type(export_format)
        extension = service.get_file_extension(export_format)
        return _stream_export(content, content_type, base_filename, extension)
    except ServiceValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)


# RECEIVABLES AGING EXPORT


@router.get("/receivables-aging/export", dependencies=[Depends(Require("books:read"))])
def export_receivables_aging(
    format: str = Query("csv", description="Export format: csv or pdf"),
    as_of_date: Optional[str] = None,
    filename: Optional[str] = Query(None, description="Override download filename (without extension)"),
    db: Session = Depends(get_db),
    service: ReportExportService = Depends(get_export_service),
):
    """Export receivables aging report to CSV or PDF.

    Args:
        format: Export format (csv or pdf)
        as_of_date: Report as of date
        filename: Custom filename for download

    Returns:
        Streaming file response
    """
    from .receivables import get_receivables_aging

    export_format = _validate_format(format, service)

    # Get report data
    data = get_receivables_aging(as_of_date=as_of_date, db=db)

    # Log the export
    service.log_export(
        report_type="receivables_aging",
        format=export_format,
        description=f"Receivables Aging {as_of_date or 'today'}",
    )
    db.commit()

    # Export using service
    try:
        base_filename = filename or "receivables_aging"
        content = service.export(data, "receivables_aging", export_format)
        content_type = service.get_content_type(export_format)
        extension = service.get_file_extension(export_format)
        return _stream_export(content, content_type, base_filename, extension)
    except ServiceValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)


# PAYABLES AGING EXPORT


@router.get("/payables-aging/export", dependencies=[Depends(Require("books:read"))])
def export_payables_aging(
    format: str = Query("csv", description="Export format: csv or pdf"),
    as_of_date: Optional[str] = None,
    filename: Optional[str] = Query(None, description="Override download filename (without extension)"),
    db: Session = Depends(get_db),
    service: ReportExportService = Depends(get_export_service),
):
    """Export payables aging report to CSV or PDF.

    Args:
        format: Export format (csv or pdf)
        as_of_date: Report as of date
        filename: Custom filename for download

    Returns:
        Streaming file response
    """
    from .payables import get_payables_aging

    export_format = _validate_format(format, service)

    # Get report data
    data = get_payables_aging(as_of_date=as_of_date, db=db)

    # Log the export
    service.log_export(
        report_type="payables_aging",
        format=export_format,
        description=f"Payables Aging {as_of_date or 'today'}",
    )
    db.commit()

    # Export using service
    try:
        base_filename = filename or "payables_aging"
        content = service.export(data, "payables_aging", export_format)
        content_type = service.get_content_type(export_format)
        extension = service.get_file_extension(export_format)
        return _stream_export(content, content_type, base_filename, extension)
    except ServiceValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)
