# Data Cleanup & Normalization Tool - Architecture Design

**Date:** 2026-01-01
**Status:** Proposed
**Scope:** New module for data quality management with UI-based cleanup capabilities

## Overview

A comprehensive data cleanup and normalization tool that enables operators to identify, preview, and fix data quality issues across the system. Integrated into Settings as a sibling to the existing Migration module.

---

## Assumptions

1. Operators need to clean existing production data without developer intervention
2. All cleanup operations must be auditable and (where possible) reversible
3. Tool should reuse existing data cleaning infrastructure from migration module
4. Primary focus on Customer, Subscription, and Contact data initially
5. Tool runs within web request context (async background jobs for large datasets)

---

## Components

### 1. Routes Layer
**Path:** `app/modules/settings/cleanup_routes.py`

```
GET  /settings/data-cleanup/                    # Dashboard with data quality overview
GET  /settings/data-cleanup/issues              # List detected issues
GET  /settings/data-cleanup/issues/{id}         # Issue detail
POST /settings/data-cleanup/scan                # Trigger data quality scan
GET  /settings/data-cleanup/scan/{id}/progress  # Poll scan progress

GET  /settings/data-cleanup/rules               # List cleanup rules
GET  /settings/data-cleanup/rules/new           # Create rule form
POST /settings/data-cleanup/rules               # Save rule
GET  /settings/data-cleanup/rules/{id}          # Rule detail
PUT  /settings/data-cleanup/rules/{id}          # Update rule
DELETE /settings/data-cleanup/rules/{id}        # Delete rule

POST /settings/data-cleanup/preview             # Preview cleanup (dry-run)
POST /settings/data-cleanup/execute             # Execute cleanup
GET  /settings/data-cleanup/jobs                # List cleanup jobs
GET  /settings/data-cleanup/jobs/{id}           # Job detail with results
POST /settings/data-cleanup/jobs/{id}/rollback  # Rollback job
```

### 2. Service Layer
**Path:** `app/services/cleanup/`

```
cleanup/
├── __init__.py
├── service.py          # CleanupService - orchestration
├── scanner.py          # DataQualityScanner - issue detection
├── rules.py            # CleanupRule engine
├── executor.py         # CleanupExecutor - apply changes
└── rollback.py         # RollbackService - undo operations
```

### 3. Data Models
**Path:** `app/models/cleanup.py`

### 4. Templates
**Path:** `app/modules/settings/templates/pages/cleanup/`

```
cleanup/
├── pages/
│   ├── dashboard.html      # Quality overview + quick actions
│   ├── issues_list.html    # Detected issues with filters
│   ├── issue_detail.html   # Single issue with affected records
│   ├── rules_list.html     # Saved cleanup rules
│   ├── rule_form.html      # Create/edit rule
│   ├── preview.html        # Dry-run results
│   ├── jobs_list.html      # Cleanup job history
│   └── job_detail.html     # Job results + rollback option
└── partials/
    ├── quality_metrics.html    # Dashboard cards
    ├── issues_table.html       # Issue list with severity
    ├── affected_records.html   # Records for an issue
    ├── preview_diff.html       # Before/after comparison
    └── job_progress.html       # HTMX polling fragment
```

---

## Data Model

### CleanupRule
Reusable cleanup configuration saved by users.

```python
class CleanupRule(Base):
    __tablename__ = "cleanup_rules"

    id: int
    name: str                           # "Normalize Customer Phones"
    description: str | None
    entity_type: str                    # "customer", "contact", "subscription"

    # Detection criteria
    issue_type: CleanupIssueType        # DUPLICATE, INVALID_FORMAT, MISSING_FIELD, etc.
    detection_config: dict              # JSON - field patterns, thresholds

    # Action configuration
    action_type: CleanupActionType      # NORMALIZE, MERGE, DELETE, SET_DEFAULT
    action_config: dict                 # JSON - normalization rules, merge strategy

    # Metadata
    is_system: bool = False             # Built-in vs user-created
    is_active: bool = True
    created_by_id: int
    created_at: datetime
    updated_at: datetime
```

### CleanupIssue
Detected data quality issues.

```python
class CleanupIssue(Base):
    __tablename__ = "cleanup_issues"

    id: int
    scan_id: int                        # FK to CleanupScan

    issue_type: CleanupIssueType
    severity: IssueSeverity             # CRITICAL, HIGH, MEDIUM, LOW
    entity_type: str                    # "customer", "contact"
    field_name: str | None              # "phone", "email", "name"

    # Affected records
    record_ids: list[int]               # JSON array of affected PKs
    record_count: int
    sample_values: list[dict]           # JSON - sample bad values for display

    # Resolution
    status: IssueStatus                 # OPEN, IN_PROGRESS, RESOLVED, IGNORED
    resolution_job_id: int | None       # FK to CleanupJob that fixed it
    resolved_at: datetime | None

    created_at: datetime
```

### CleanupScan
Background scan job for detecting issues.

```python
class CleanupScan(Base):
    __tablename__ = "cleanup_scans"

    id: int
    entity_types: list[str]             # JSON - ["customer", "contact"]
    issue_types: list[str] | None       # JSON - null = all types

    status: ScanStatus                  # PENDING, RUNNING, COMPLETED, FAILED
    progress_pct: int = 0
    current_step: str | None            # "Scanning customers..."

    # Results
    issues_found: int = 0
    records_scanned: int = 0
    duration_seconds: float | None

    started_by_id: int
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None
```

### CleanupJob
Execution of cleanup operations.

```python
class CleanupJob(Base):
    __tablename__ = "cleanup_jobs"

    id: int
    name: str                           # Auto-generated or user-provided
    rule_id: int | None                 # FK - null for ad-hoc cleanup
    issue_ids: list[int]                # JSON - issues being resolved

    # Scope
    entity_type: str
    record_ids: list[int]               # JSON - specific records to clean

    # Execution
    status: JobStatus                   # PENDING, PREVIEWING, PREVIEW_READY,
                                        # EXECUTING, COMPLETED, FAILED, ROLLED_BACK
    action_type: CleanupActionType
    action_config: dict                 # JSON

    # Results
    records_processed: int = 0
    records_changed: int = 0
    records_failed: int = 0
    changes_log: list[dict]             # JSON - before/after for each record

    # Rollback support
    is_rollbackable: bool = True
    rollback_data: dict | None          # JSON - data needed to undo
    rolled_back_at: datetime | None
    rolled_back_by_id: int | None

    # Audit
    created_by_id: int
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
```

### Enums

```python
class CleanupIssueType(str, Enum):
    DUPLICATE = "duplicate"                 # Duplicate records
    INVALID_FORMAT = "invalid_format"       # Bad phone/email/etc format
    MISSING_REQUIRED = "missing_required"   # Null required fields
    INVALID_VALUE = "invalid_value"         # Value not in allowed set
    ORPHANED = "orphaned"                   # FK points to deleted record
    INCONSISTENT = "inconsistent"           # Conflicting data across fields
    STALE = "stale"                         # Old data needing refresh

class CleanupActionType(str, Enum):
    NORMALIZE = "normalize"                 # Apply formatting rules
    MERGE = "merge"                         # Merge duplicate records
    DELETE = "delete"                       # Remove records
    SET_DEFAULT = "set_default"             # Fill missing with default
    SET_NULL = "set_null"                   # Clear invalid values
    LINK = "link"                           # Fix orphaned FKs
    CUSTOM = "custom"                       # User-defined transformation

class IssueSeverity(str, Enum):
    CRITICAL = "critical"                   # Breaks functionality
    HIGH = "high"                           # Causes errors
    MEDIUM = "medium"                       # Data quality issue
    LOW = "low"                             # Cosmetic/minor

class IssueStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    IGNORED = "ignored"

class JobStatus(str, Enum):
    PENDING = "pending"
    PREVIEWING = "previewing"
    PREVIEW_READY = "preview_ready"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
```

---

## Data Flow

### 1. Issue Detection Flow
```
User triggers scan → CleanupScan created (PENDING)
                   → Background task starts
                   → Scanner iterates entity types
                   → For each: run issue detectors
                   → Create CleanupIssue records
                   → Update scan progress (HTMX polling)
                   → Scan completed
```

### 2. Cleanup Execution Flow
```
User selects issues → Choose/create rule
                    → POST /preview (dry-run)
                    → CleanupJob created (PREVIEWING)
                    → Executor simulates changes
                    → Returns before/after diff
                    → User reviews preview
                    → POST /execute
                    → Executor applies changes
                    → AuditLogger records each change
                    → Job completed
                    → Issues marked RESOLVED
```

### 3. Rollback Flow
```
User clicks rollback → Validate job is rollbackable
                     → Load rollback_data
                     → Restore original values
                     → AuditLogger records rollback
                     → Job marked ROLLED_BACK
                     → Issues reopened
```

---

## Issue Detectors

### Built-in Detectors

| Detector | Entity Types | Description |
|----------|--------------|-------------|
| `DuplicateDetector` | All | Finds duplicates by configurable fields (name, email, phone) |
| `PhoneFormatDetector` | Customer, Contact | Invalid phone formats |
| `EmailFormatDetector` | Customer, Contact, Employee | Invalid email addresses |
| `MissingFieldDetector` | All | Null/empty required fields |
| `OrphanedRecordDetector` | All | Broken foreign key references |
| `EnumValueDetector` | All | Values not in allowed enum set |
| `DateRangeDetector` | All | Dates outside valid range |
| `AddressIncompleteDetector` | Customer, Supplier | Missing address components |

### Detector Interface

```python
class IssueDetector(ABC):
    issue_type: CleanupIssueType
    supported_entities: list[str]

    @abstractmethod
    async def detect(
        self,
        db: Session,
        entity_type: str,
        config: dict
    ) -> list[CleanupIssue]:
        """Scan entity and return detected issues."""
        pass

    @abstractmethod
    def get_config_schema(self) -> dict:
        """Return JSON schema for detector configuration."""
        pass
```

---

## UI Design

### Dashboard (`/settings/data-cleanup/`)

```
┌─────────────────────────────────────────────────────────────────┐
│ Data Cleanup                                          [Scan Now]│
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────┐│
│  │ 47           │ │ 12           │ │ 156          │ │ 8       ││
│  │ Critical     │ │ High         │ │ Medium       │ │ Low     ││
│  │ Issues       │ │ Issues       │ │ Issues       │ │ Issues  ││
│  └──────────────┘ └──────────────┘ └──────────────┘ └─────────┘│
│                                                                 │
│  Data Quality Score: 87% ████████████████░░░                   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Recent Issues                                    [View All] ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │ ● 23 duplicate customers by email         HIGH    [Fix]    ││
│  │ ● 156 invalid phone formats               MEDIUM  [Fix]    ││
│  │ ● 12 customers missing address            HIGH    [Fix]    ││
│  │ ● 8 orphaned subscriptions                CRITICAL[Fix]    ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Quick Actions                                               ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │ [Normalize All Phones] [Fix Email Formats] [Find Duplicates]││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Recent Jobs                                      [View All] ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │ Phone normalization    234 records   Completed   2hrs ago  ││
│  │ Duplicate merge        12 records    Completed   1 day ago ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### Preview Screen (`/settings/data-cleanup/preview`)

```
┌─────────────────────────────────────────────────────────────────┐
│ Preview: Normalize Phone Numbers                                │
│ 156 records will be modified                       [Execute]   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ☑ Select All                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ ☑ │ Customer        │ Before          │ After              ││
│  ├───┼─────────────────┼─────────────────┼────────────────────┤│
│  │ ☑ │ John Doe        │ 0801-234-5678   │ +2348012345678    ││
│  │ ☑ │ Jane Smith      │ 08098765432     │ +2348098765432    ││
│  │ ☐ │ Bob Wilson      │ +234 803 111... │ +2348031112222    ││
│  │ ☑ │ Alice Brown     │ 0701 234 5678   │ +2347012345678    ││
│  └───┴─────────────────┴─────────────────┴────────────────────┘│
│                                                                 │
│  [Cancel]                              [Execute Selected (155)] │
└─────────────────────────────────────────────────────────────────┘
```

---

## Integration with Data Explorer

Add cleanup entry points to Data Explorer:

1. **Table-level action**: "Scan for Issues" button on each table view
2. **Row selection**: "Clean Selected" in bulk actions bar
3. **Filter by quality**: Add filter for "Has Issues" in table view
4. **Quick fix column**: Show issue indicator on records with problems

```html
<!-- In data_explorer table row -->
{% if record.has_cleanup_issues %}
<span class="text-amber-500" title="{{ record.issue_count }} issues">
    <svg><!-- warning icon --></svg>
</span>
{% endif %}
```

---

## Non-Functional Requirements

### Performance
- Scans should process 100k+ records without timeout
- Use batch processing (1000 records per batch)
- Background jobs for scans > 10k records
- Preview limited to 500 records with sampling for larger sets

### Availability
- Cleanup operations should not lock tables
- Use row-level operations, not bulk UPDATE
- Progress tracking via HTMX polling (2s interval)

### Security
- Require `admin:write` scope for all mutations
- Require `admin:read` scope for viewing issues
- Audit log all cleanup operations
- Sanitize all user input in rule configurations

### Observability
- Log scan duration and record counts
- Track cleanup success/failure rates
- Alert on failed cleanup jobs
- Dashboard metrics for data quality trends

---

## Tradeoffs

### Option A: Inline Cleanup (Current Design)
**Pros:** Immediate feedback, simpler architecture, reuses migration cleaning
**Cons:** Limited to web request timeouts, may block UI for large datasets

### Option B: Full Background Job System
**Pros:** Handles any dataset size, non-blocking
**Cons:** More complex, requires Celery/Redis, delayed feedback

**Decision:** Start with Option A for MVP, add background jobs for scans > 10k records

### Option A: Store Full Rollback Data
**Pros:** Complete undo capability, simple restore
**Cons:** Storage intensive for large cleanups

### Option B: Store Only Changes (Diff)
**Pros:** Efficient storage
**Cons:** More complex rollback logic

**Decision:** Option A for MVP, optimize later if storage becomes issue

---

## Rollout Plan

### Phase 1: Foundation
- [ ] Database models and migrations
- [ ] CleanupService skeleton
- [ ] Dashboard page with mock data
- [ ] Basic issue list view

### Phase 2: Detection
- [ ] Scanner infrastructure
- [ ] DuplicateDetector
- [ ] PhoneFormatDetector
- [ ] EmailFormatDetector
- [ ] MissingFieldDetector
- [ ] HTMX progress polling

### Phase 3: Cleanup Actions
- [ ] Preview/dry-run capability
- [ ] NORMALIZE action (reuse migration cleaning)
- [ ] SET_DEFAULT action
- [ ] Execution with audit logging
- [ ] Job history

### Phase 4: Advanced Features
- [ ] MERGE action for duplicates
- [ ] DELETE action with safeguards
- [ ] Rollback capability
- [ ] Saved rules/templates
- [ ] Data Explorer integration

### Phase 5: Polish
- [ ] Keyboard shortcuts
- [ ] Bulk operations bar
- [ ] Export issues to CSV
- [ ] Scheduled scans
- [ ] Quality trend dashboard

---

## Migration

```python
# alembic/versions/YYYYMMDD_add_data_cleanup.py

def upgrade():
    # Create enums
    op.execute("""
        CREATE TYPE cleanup_issue_type AS ENUM (
            'duplicate', 'invalid_format', 'missing_required',
            'invalid_value', 'orphaned', 'inconsistent', 'stale'
        );
        CREATE TYPE cleanup_action_type AS ENUM (
            'normalize', 'merge', 'delete', 'set_default',
            'set_null', 'link', 'custom'
        );
        CREATE TYPE issue_severity AS ENUM (
            'critical', 'high', 'medium', 'low'
        );
        CREATE TYPE issue_status AS ENUM (
            'open', 'in_progress', 'resolved', 'ignored'
        );
        CREATE TYPE cleanup_job_status AS ENUM (
            'pending', 'previewing', 'preview_ready',
            'executing', 'completed', 'failed', 'rolled_back'
        );
        CREATE TYPE cleanup_scan_status AS ENUM (
            'pending', 'running', 'completed', 'failed'
        );
    """)

    # Create tables
    op.create_table('cleanup_rules', ...)
    op.create_table('cleanup_scans', ...)
    op.create_table('cleanup_issues', ...)
    op.create_table('cleanup_jobs', ...)

    # Indexes for common queries
    op.create_index('ix_cleanup_issues_status', 'cleanup_issues', ['status'])
    op.create_index('ix_cleanup_issues_severity', 'cleanup_issues', ['severity'])
    op.create_index('ix_cleanup_issues_entity_type', 'cleanup_issues', ['entity_type'])
    op.create_index('ix_cleanup_jobs_status', 'cleanup_jobs', ['status'])
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `app/models/cleanup.py` | SQLAlchemy models |
| `app/modules/settings/cleanup_routes.py` | Route handlers |
| `app/services/cleanup/service.py` | Orchestration |
| `app/services/cleanup/scanner.py` | Issue detection |
| `app/services/cleanup/detectors/*.py` | Individual detectors |
| `app/services/cleanup/executor.py` | Apply changes |
| `app/services/cleanup/rollback.py` | Undo operations |
| `app/modules/settings/templates/pages/cleanup/*.html` | Templates |
| `alembic/versions/YYYYMMDD_add_data_cleanup.py` | Migration |
| `tests/services/cleanup/test_*.py` | Unit tests |

---

## Review Checklist

- [ ] Models follow existing patterns (timestamps, soft delete if needed)
- [ ] Routes use consistent permission decorators
- [ ] Templates extend settings layout
- [ ] Audit logging for all mutations
- [ ] HTMX patterns match existing modules
- [ ] Error handling with user-friendly messages
- [ ] Tests for all detectors and actions
