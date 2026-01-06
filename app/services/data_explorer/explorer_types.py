"""Type definitions for data explorer service.

These dataclasses define the contract for data exploration operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExploreFilters:
    """Filters for exploring table data."""
    order_by: Optional[str] = None
    order_dir: str = "desc"
    date_column: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    search: Optional[str] = None


@dataclass
class ExportFilters:
    """Filters for exporting table data."""
    date_column: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    search: Optional[str] = None


@dataclass
class TableInfo:
    """Information about a single table."""
    name: str
    count: int
    columns: List[str]
    date_columns: List[str]
    category: str
    category_label: str


@dataclass
class TableListResult:
    """Result of listing all tables."""
    tables: Dict[str, TableInfo]
    categories: Dict[str, str]
    by_category: Dict[str, List[TableInfo]]
    total_tables: int
    total_records: int


@dataclass
class ExploreResult:
    """Result of exploring table data."""
    table: str
    total: int
    limit: int
    offset: int
    date_columns: List[str]
    columns: List[str]
    filters_applied: Dict[str, Any]
    data: List[Dict[str, Any]]


@dataclass
class TableStats:
    """Statistics for a single table."""
    table: str
    total_records: int
    stats: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExportResult:
    """Result of exporting table data."""
    content: str
    filename: str
    media_type: str


@dataclass
class SearchResult:
    """Result of searching across tables."""
    parties: List[Dict[str, Any]]
    customer_accounts: List[Dict[str, Any]]
    invoices: List[Dict[str, Any]]
    employees: List[Dict[str, Any]]
    pops: List[Dict[str, Any]]


@dataclass
class DataQualityReport:
    """Data quality report across tables."""
    parties: Dict[str, Any]
    customer_accounts: Dict[str, Any]
    invoices: Dict[str, Any]
    conversations: Dict[str, Any]
    summary: Dict[str, Any]


@dataclass
class QueryRequest:
    """Request for running a custom query."""
    table: str
    filters: Optional[Dict[str, Any]] = None
    group_by: Optional[List[str]] = None
    aggregate: Optional[Dict[str, str]] = None
    limit: int = 100


@dataclass
class QueryResult:
    """Result of a custom query."""
    data: List[Dict[str, Any]]
    grouped: bool
    total: Optional[int] = None
    limit: Optional[int] = None
