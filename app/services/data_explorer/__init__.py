"""Data Explorer service module.

Provides internal data exploration capabilities for web modules and background tasks.
NOT exposed via API endpoints.
"""
from .explorer import DataExplorerService
from .explorer_types import (
    ExploreFilters,
    ExportFilters,
    TableInfo,
    TableListResult,
    ExploreResult,
    TableStats,
    ExportResult,
    SearchResult,
    DataQualityReport,
    QueryRequest,
    QueryResult,
)
from .table_registry import (
    TABLES,
    TABLE_CATEGORIES,
    TABLE_TO_CATEGORY,
    get_date_columns,
    get_model_columns,
    get_table_model,
    is_valid_table,
)
from .cleaner import DataCleanerService
from .cleaner_types import (
    RecordChange,
    OperationError,
    BulkUpdatePreview,
    BulkUpdateResult,
    NormalizePreview,
    NormalizeResult,
    DuplicateGroup,
    DuplicateReport,
    MergePreview,
    MergeResult,
    MatchingRule,
    OrphanRecord,
    OrphanReport,
    LinkMatch,
    LinkPreview,
    LinkResult,
    CleaningOperationSummary,
    RollbackPreview,
    RollbackResult,
    CleaningFilters,
)

__all__ = [
    # Services
    "DataExplorerService",
    "DataCleanerService",
    # Filter types
    "ExploreFilters",
    "ExportFilters",
    "CleaningFilters",
    # Explorer result types
    "TableInfo",
    "TableListResult",
    "ExploreResult",
    "TableStats",
    "ExportResult",
    "SearchResult",
    "DataQualityReport",
    "QueryRequest",
    "QueryResult",
    # Cleaner types
    "RecordChange",
    "OperationError",
    "BulkUpdatePreview",
    "BulkUpdateResult",
    "NormalizePreview",
    "NormalizeResult",
    "DuplicateGroup",
    "DuplicateReport",
    "MergePreview",
    "MergeResult",
    "MatchingRule",
    "OrphanRecord",
    "OrphanReport",
    "LinkMatch",
    "LinkPreview",
    "LinkResult",
    "CleaningOperationSummary",
    "RollbackPreview",
    "RollbackResult",
    # Registry
    "TABLES",
    "TABLE_CATEGORIES",
    "TABLE_TO_CATEGORY",
    "get_date_columns",
    "get_model_columns",
    "get_table_model",
    "is_valid_table",
]
