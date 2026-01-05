"""Type definitions for data cleaner service.

These dataclasses define the contract for data cleaning operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# =============================================================================
# COMMON TYPES
# =============================================================================


@dataclass
class RecordChange:
    """Single record change with before/after state."""
    record_id: int
    before: Dict[str, Any]
    after: Dict[str, Any]
    changed_fields: List[str]


@dataclass
class OperationError:
    """Error that occurred during operation."""
    record_id: int
    error: str
    field: Optional[str] = None


# =============================================================================
# BULK UPDATE TYPES
# =============================================================================


@dataclass
class BulkUpdatePreview:
    """Preview of bulk update operation."""
    table: str
    filters_applied: Dict[str, Any]
    updates_planned: Dict[str, Any]
    records_affected: int
    sample_changes: List[RecordChange]  # First N records


@dataclass
class BulkUpdateResult:
    """Result of executed bulk update."""
    operation_id: str  # UUID for rollback
    table: str
    records_updated: int
    records_failed: int
    errors: List[OperationError]
    rollback_available: bool
    changes_log: List[RecordChange]


# =============================================================================
# NORMALIZATION TYPES
# =============================================================================


@dataclass
class NormalizePreview:
    """Preview of normalization operation."""
    field: str  # "primary_phone", "primary_email", "addresses"
    records_to_normalize: int
    already_normalized: int
    invalid_values: int
    sample_changes: List[RecordChange]
    invalid_samples: List[Dict[str, Any]]  # Records that can't be normalized


@dataclass
class NormalizeResult:
    """Result of normalization operation."""
    operation_id: str
    field: str
    records_normalized: int
    records_skipped: int
    records_failed: int
    errors: List[OperationError]
    rollback_available: bool


# =============================================================================
# DUPLICATE DETECTION TYPES
# =============================================================================


@dataclass
class DuplicateGroup:
    """Group of duplicate records."""
    match_key: str  # The value that matched (e.g., email address)
    record_ids: List[int]
    records: List[Dict[str, Any]]  # Full record data
    suggested_primary: int  # ID of recommended primary (oldest or most complete)


@dataclass
class DuplicateReport:
    """Report of all duplicates found."""
    table: str
    match_fields: List[str]
    total_groups: int
    total_duplicates: int  # Records that would be merged (excluding primaries)
    groups: List[DuplicateGroup]


@dataclass
class MergePreview:
    """Preview of merge operation."""
    primary_record: Dict[str, Any]
    duplicate_records: List[Dict[str, Any]]
    merged_result: Dict[str, Any]  # What primary will look like after merge
    related_records_to_relink: Dict[str, int]  # table_name -> count
    records_to_delete: List[int]  # IDs to soft-delete


@dataclass
class MergeResult:
    """Result of merge operation."""
    operation_id: str
    primary_id: int
    merged_ids: List[int]
    records_relinked: Dict[str, int]  # table_name -> count relinked
    errors: List[OperationError]
    rollback_available: bool


# =============================================================================
# ORPHAN LINKING TYPES
# =============================================================================


@dataclass
class MatchingRule:
    """Rule for matching orphan records to targets."""
    orphan_field: str  # Field on orphan record to match
    target_table: str  # Table to search for matches
    target_field: str  # Field on target table to match against
    match_type: str = "exact"  # "exact" | "fuzzy" | "contains"


@dataclass
class OrphanRecord:
    """An orphan record with potential matches."""
    record_id: int
    record_data: Dict[str, Any]
    match_value: Optional[str]  # Value used for matching
    potential_matches: List[Dict[str, Any]]  # Possible target records


@dataclass
class OrphanReport:
    """Report of orphan records found."""
    table: str
    fk_field: str
    total_orphans: int
    sample_orphans: List[OrphanRecord]


@dataclass
class LinkMatch:
    """A single orphan-to-target link."""
    orphan_id: int
    target_id: int
    match_confidence: float  # 0.0 to 1.0
    match_reason: str  # e.g., "exact email match"


@dataclass
class LinkPreview:
    """Preview of orphan linking operation."""
    table: str
    fk_field: str
    matches_found: int
    unmatched: int
    sample_matches: List[LinkMatch]


@dataclass
class LinkResult:
    """Result of linking operation."""
    operation_id: str
    table: str
    fk_field: str
    records_linked: int
    records_unmatched: int
    errors: List[OperationError]
    rollback_available: bool


# =============================================================================
# OPERATION TRACKING & ROLLBACK
# =============================================================================


@dataclass
class CleaningOperationSummary:
    """Summary of a cleaning operation for listing."""
    operation_id: str
    operation_type: str  # "bulk_update" | "normalize" | "merge" | "link"
    table: str
    records_affected: int
    records_failed: int
    created_at: datetime
    created_by_id: int
    created_by_name: Optional[str]
    is_rolled_back: bool
    rolled_back_at: Optional[datetime]
    summary: Dict[str, Any]


@dataclass
class RollbackPreview:
    """Preview of rollback operation."""
    operation_id: str
    operation_type: str
    table: str
    records_to_restore: int
    sample_restorations: List[RecordChange]  # Shows what will be restored


@dataclass
class RollbackResult:
    """Result of rollback operation."""
    operation_id: str
    records_restored: int
    records_failed: int
    errors: List[OperationError]
    success: bool


# =============================================================================
# FILTER TYPES
# =============================================================================


@dataclass
class CleaningFilters:
    """Filters for selecting records to clean."""
    status: Optional[str] = None  # e.g., "active"
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    has_field: Optional[str] = None  # Field must not be null
    missing_field: Optional[str] = None  # Field must be null
    field_equals: Optional[Dict[str, Any]] = None  # field_name -> value
    field_contains: Optional[Dict[str, str]] = None  # field_name -> substring
    record_ids: Optional[List[int]] = None  # Specific IDs to include
