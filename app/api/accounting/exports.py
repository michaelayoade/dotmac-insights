"""Exports: Report exports (CSV/PDF), cache metadata, export status."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth import Require
from app.cache import get_redis_client, CACHE_TTL
from app.database import get_db

router = APIRouter()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

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


# =============================================================================
# CACHE & EXPORT METADATA
# =============================================================================

@router.get("/cache-metadata", dependencies=[Depends(Require("accounting:read"))])
async def get_accounting_cache_metadata() -> Dict[str, Any]:
    """Expose TTL metadata for cached accounting endpoints.

    Returns:
        Cache configuration and availability status
    """
    cache_keys = [
        {"key": "accounting-dashboard", "ttl_seconds": 60},
        {"key": "trial-balance", "ttl_seconds": 60},
        {"key": "balance-sheet", "ttl_seconds": 60},
        {"key": "income-statement", "ttl_seconds": 60},
        {"key": "accounts-payable", "ttl_seconds": 60},
        {"key": "accounts-receivable", "ttl_seconds": 60},
        {"key": "cash-flow", "ttl_seconds": 60},
        {"key": "income-statement-comparative", "ttl_seconds": 300},
        {"key": "tax-dashboard", "ttl_seconds": 60},
        {"key": "receivables-aging-enhanced", "ttl_seconds": 60},
    ]
    client = await get_redis_client()

    return {
        "as_of": datetime.utcnow().isoformat() + "Z",
        "presets": CACHE_TTL,
        "cache_available": client is not None,
        "keys": cache_keys,
    }


@router.get("/exports/status", dependencies=[Depends(Require("books:read"))])
def get_export_status() -> Dict[str, Any]:
    """Lightweight health signal for export services.

    Returns:
        Export service availability status
    """
    from app.services.export_service import WEASYPRINT_AVAILABLE

    return {
        "as_of": datetime.utcnow().isoformat() + "Z",
        "services": {
            "csv": {"available": True},
            "pdf": {
                "available": bool(WEASYPRINT_AVAILABLE),
                "requires": "weasyprint",
            },
        },
    }


# =============================================================================
# TRIAL BALANCE EXPORT
# =============================================================================

@router.get("/trial-balance/export", dependencies=[Depends(Require("books:read"))])
def export_trial_balance(
    format: str = Query("csv", description="Export format: csv or pdf"),
    as_of_date: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    cost_center: Optional[str] = None,
    filename: Optional[str] = Query(None, description="Override download filename (without extension)"),
    db: Session = Depends(get_db),
    user=Depends(Require("accounting:read")),
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
    from app.services.export_service import ExportService, ExportError
    from app.services.audit_logger import AuditLogger
    from .reports import get_trial_balance

    if format not in ("csv", "pdf"):
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'pdf'")

    # Get report data
    data = get_trial_balance(
        as_of_date=as_of_date,
        fiscal_year=fiscal_year,
        cost_center=cost_center,
        drill=False,
        db=db,
    )

    export_service = ExportService()

    # Audit log the export
    audit = AuditLogger(db)
    audit.log_export(
        doctype="trial_balance",
        document_id=0,
        user_id=user.id,
        document_name=f"Trial Balance {as_of_date or 'today'}",
        remarks=f"Exported as {format.upper()}",
    )
    db.commit()

    try:
        base_filename = filename or "trial_balance"
        if format == "csv":
            content = export_service.export_csv(data, "trial_balance")
            return _stream_export(content, "text/csv", base_filename, "csv")
        else:
            content = export_service.export_pdf(data, "trial_balance")
            return _stream_export(content, "application/pdf", base_filename, "pdf")
    except ExportError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# BALANCE SHEET EXPORT
# =============================================================================

@router.get("/balance-sheet/export", dependencies=[Depends(Require("books:read"))])
def export_balance_sheet(
    format: str = Query("csv", description="Export format: csv or pdf"),
    as_of_date: Optional[str] = None,
    comparative_date: Optional[str] = None,
    filename: Optional[str] = Query(None, description="Override download filename (without extension)"),
    db: Session = Depends(get_db),
    user=Depends(Require("accounting:read")),
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
    from app.services.export_service import ExportService, ExportError
    from app.services.audit_logger import AuditLogger
    from .reports import get_balance_sheet

    if format not in ("csv", "pdf"):
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'pdf'")

    # Get report data
    data = get_balance_sheet(
        as_of_date=as_of_date,
        comparative_date=comparative_date,
        common_size=False,
        db=db,
    )

    export_service = ExportService()

    # Audit log the export
    audit = AuditLogger(db)
    audit.log_export(
        doctype="balance_sheet",
        document_id=0,
        user_id=user.id,
        document_name=f"Balance Sheet {as_of_date or 'today'}",
        remarks=f"Exported as {format.upper()}",
    )
    db.commit()

    try:
        base_filename = filename or "balance_sheet"
        if format == "csv":
            content = export_service.export_csv(data, "balance_sheet")
            return _stream_export(content, "text/csv", base_filename, "csv")
        else:
            content = export_service.export_pdf(data, "balance_sheet")
            return _stream_export(content, "application/pdf", base_filename, "pdf")
    except ExportError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# INCOME STATEMENT EXPORT
# =============================================================================

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
    user=Depends(Require("accounting:read")),
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
    from app.services.export_service import ExportService, ExportError
    from app.services.audit_logger import AuditLogger
    from .reports import get_income_statement

    if format not in ("csv", "pdf"):
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'pdf'")

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

    export_service = ExportService()

    # Audit log the export
    audit = AuditLogger(db)
    audit.log_export(
        doctype="income_statement",
        document_id=0,
        user_id=user.id,
        document_name=f"Income Statement {start_date or ''} to {end_date or 'today'}",
        remarks=f"Exported as {format.upper()}, basis: {basis}",
    )
    db.commit()

    try:
        base_filename = filename or "income_statement"
        if format == "csv":
            content = export_service.export_csv(data, "income_statement")
            return _stream_export(content, "text/csv", base_filename, "csv")
        else:
            content = export_service.export_pdf(data, "income_statement")
            return _stream_export(content, "application/pdf", base_filename, "pdf")
    except ExportError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# GENERAL LEDGER EXPORT
# =============================================================================

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
    user=Depends(Require("accounting:read")),
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
    from app.services.export_service import ExportService, ExportError
    from app.services.audit_logger import AuditLogger
    from .ledger import get_general_ledger

    if format not in ("csv", "pdf"):
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'pdf'")

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

    export_service = ExportService()

    # Audit log the export
    audit = AuditLogger(db)
    audit.log_export(
        doctype="general_ledger",
        document_id=0,
        user_id=user.id,
        document_name=f"General Ledger {start_date or ''} to {end_date or ''}",
        remarks=f"Exported as {format.upper()}, {data.get('total', 0)} records",
    )
    db.commit()

    try:
        base_filename = filename or "general_ledger"
        if format == "csv":
            content = export_service.export_csv(data, "general_ledger")
            return _stream_export(content, "text/csv", base_filename, "csv")
        else:
            content = export_service.export_pdf(data, "general_ledger")
            return _stream_export(content, "application/pdf", base_filename, "pdf")
    except ExportError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# RECEIVABLES AGING EXPORT
# =============================================================================

@router.get("/receivables-aging/export", dependencies=[Depends(Require("books:read"))])
def export_receivables_aging(
    format: str = Query("csv", description="Export format: csv or pdf"),
    as_of_date: Optional[str] = None,
    filename: Optional[str] = Query(None, description="Override download filename (without extension)"),
    db: Session = Depends(get_db),
    user=Depends(Require("accounting:read")),
):
    """Export receivables aging report to CSV or PDF.

    Args:
        format: Export format (csv or pdf)
        as_of_date: Report as of date
        filename: Custom filename for download

    Returns:
        Streaming file response
    """
    from app.services.export_service import ExportService, ExportError
    from app.services.audit_logger import AuditLogger
    from .receivables import get_receivables_aging

    if format not in ("csv", "pdf"):
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'pdf'")

    # Get report data
    data = get_receivables_aging(as_of_date=as_of_date, db=db)

    export_service = ExportService()

    # Audit log the export
    audit = AuditLogger(db)
    audit.log_export(
        doctype="receivables_aging",
        document_id=0,
        user_id=user.id,
        document_name=f"Receivables Aging {as_of_date or 'today'}",
        remarks=f"Exported as {format.upper()}",
    )
    db.commit()

    try:
        base_filename = filename or "receivables_aging"
        if format == "csv":
            content = export_service.export_csv(data, "receivables_aging")
            return _stream_export(content, "text/csv", base_filename, "csv")
        else:
            content = export_service.export_pdf(data, "receivables_aging")
            return _stream_export(content, "application/pdf", base_filename, "pdf")
    except ExportError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# PAYABLES AGING EXPORT
# =============================================================================

@router.get("/payables-aging/export", dependencies=[Depends(Require("books:read"))])
def export_payables_aging(
    format: str = Query("csv", description="Export format: csv or pdf"),
    as_of_date: Optional[str] = None,
    filename: Optional[str] = Query(None, description="Override download filename (without extension)"),
    db: Session = Depends(get_db),
    user=Depends(Require("accounting:read")),
):
    """Export payables aging report to CSV or PDF.

    Args:
        format: Export format (csv or pdf)
        as_of_date: Report as of date
        filename: Custom filename for download

    Returns:
        Streaming file response
    """
    from app.services.export_service import ExportService, ExportError
    from app.services.audit_logger import AuditLogger
    from .payables import get_payables_aging

    if format not in ("csv", "pdf"):
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'pdf'")

    # Get report data
    data = get_payables_aging(as_of_date=as_of_date, db=db)

    export_service = ExportService()

    # Audit log the export
    audit = AuditLogger(db)
    audit.log_export(
        doctype="payables_aging",
        document_id=0,
        user_id=user.id,
        document_name=f"Payables Aging {as_of_date or 'today'}",
        remarks=f"Exported as {format.upper()}",
    )
    db.commit()

    try:
        base_filename = filename or "payables_aging"
        if format == "csv":
            content = export_service.export_csv(data, "payables_aging")
            return _stream_export(content, "text/csv", base_filename, "csv")
        else:
            content = export_service.export_pdf(data, "payables_aging")
            return _stream_export(content, "application/pdf", base_filename, "pdf")
    except ExportError as e:
        raise HTTPException(status_code=400, detail=str(e))
