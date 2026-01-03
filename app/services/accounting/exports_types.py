"""Type definitions for report export service.

These dataclasses define the contract for report export operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional

__all__ = [
    "ExportFormat",
    "ExportServiceStatus",
    "CacheMetadata",
    "CacheKeyInfo",
    "TrialBalanceExportParams",
    "BalanceSheetExportParams",
    "IncomeStatementExportParams",
    "GeneralLedgerExportParams",
    "AgingExportParams",
]


class ExportFormat(str, Enum):
    """Supported export formats."""

    CSV = "csv"
    PDF = "pdf"


@dataclass
class CacheKeyInfo:
    """Information about a cache key."""

    key: str
    ttl_seconds: int


@dataclass
class CacheMetadata:
    """Cache metadata for accounting endpoints."""

    as_of: str
    cache_available: bool
    keys: List[CacheKeyInfo] = field(default_factory=list)


@dataclass
class ExportServiceStatus:
    """Status of export services."""

    as_of: str
    csv_available: bool = True
    pdf_available: bool = False
    pdf_requires: str = "weasyprint"


@dataclass
class TrialBalanceExportParams:
    """Parameters for trial balance export."""

    format: ExportFormat
    as_of_date: Optional[date] = None
    fiscal_year: Optional[str] = None
    cost_center: Optional[str] = None
    filename: Optional[str] = None


@dataclass
class BalanceSheetExportParams:
    """Parameters for balance sheet export."""

    format: ExportFormat
    as_of_date: Optional[date] = None
    comparative_date: Optional[date] = None
    filename: Optional[str] = None


@dataclass
class IncomeStatementExportParams:
    """Parameters for income statement export."""

    format: ExportFormat
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    fiscal_year: Optional[str] = None
    cost_center: Optional[str] = None
    basis: str = "accrual"
    filename: Optional[str] = None


@dataclass
class GeneralLedgerExportParams:
    """Parameters for general ledger export."""

    format: ExportFormat
    account: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    party_type: Optional[str] = None
    party: Optional[str] = None
    voucher_type: Optional[str] = None
    limit: int = 1000
    filename: Optional[str] = None


@dataclass
class AgingExportParams:
    """Parameters for aging report export."""

    format: ExportFormat
    as_of_date: Optional[date] = None
    filename: Optional[str] = None
