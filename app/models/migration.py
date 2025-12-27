from __future__ import annotations

import enum
import hashlib
from datetime import datetime
from typing import Optional, Any

from sqlalchemy import String, Text, Enum, ForeignKey, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.datetime_utils import utc_now


class MigrationStatus(enum.Enum):
    """Status of a migration job."""
    PENDING = "pending"           # Job created, awaiting file upload
    UPLOADED = "uploaded"         # File uploaded, awaiting mapping
    MAPPED = "mapped"             # Field mapping complete
    VALIDATING = "validating"     # Running validation
    VALIDATED = "validated"       # Validation complete, ready to execute
    RUNNING = "running"           # Migration in progress
    COMPLETED = "completed"       # Migration finished successfully
    FAILED = "failed"             # Migration failed
    CANCELLED = "cancelled"       # Migration cancelled by user
    ROLLED_BACK = "rolled_back"   # Migration was rolled back


class SourceType(enum.Enum):
    """Type of source file."""
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"


class DedupStrategy(enum.Enum):
    """Strategy for handling duplicate records."""
    SKIP = "skip"       # Skip duplicates, keep existing
    UPDATE = "update"   # Update existing records
    MERGE = "merge"     # Merge data from both records


class RecordAction(enum.Enum):
    """Action taken on a migration record."""
    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"
    FAILED = "failed"


class EntityType(enum.Enum):
    """Supported entity types for migration."""
    # Core
    CONTACTS = "contacts"
    CUSTOMERS = "customers"
    EMPLOYEES = "employees"
    DEPARTMENTS = "departments"
    DESIGNATIONS = "designations"

    # Accounting
    ACCOUNTS = "accounts"
    BANK_ACCOUNTS = "bank_accounts"
    BANK_TRANSACTIONS = "bank_transactions"
    JOURNAL_ENTRIES = "journal_entries"
    COST_CENTERS = "cost_centers"
    FISCAL_YEARS = "fiscal_years"
    FISCAL_PERIODS = "fiscal_periods"
    MODES_OF_PAYMENT = "modes_of_payment"
    SUPPLIER_GROUPS = "supplier_groups"
    GL_ENTRIES = "gl_entries"
    EXCHANGE_RATES = "exchange_rates"
    PAYMENT_ALLOCATIONS = "payment_allocations"
    PAYMENT_METHODS = "payment_methods"

    # Sales
    INVOICES = "invoices"
    PAYMENTS = "payments"
    CREDIT_NOTES = "credit_notes"

    # Purchasing
    SUPPLIERS = "suppliers"
    PURCHASE_INVOICES = "purchase_invoices"
    SUPPLIER_PAYMENTS = "supplier_payments"

    # HR - Leave Management
    LEAVE_TYPES = "leave_types"
    HOLIDAY_LISTS = "holiday_lists"
    HOLIDAYS = "holidays"
    LEAVE_POLICIES = "leave_policies"
    LEAVE_POLICY_DETAILS = "leave_policy_details"
    LEAVE_ALLOCATIONS = "leave_allocations"
    LEAVE_APPLICATIONS = "leave_applications"

    # HR - Attendance
    SHIFT_TYPES = "shift_types"
    SHIFT_ASSIGNMENTS = "shift_assignments"
    ATTENDANCES = "attendances"
    ATTENDANCE_REQUESTS = "attendance_requests"

    # HR - Payroll
    SALARY_COMPONENTS = "salary_components"
    SALARY_STRUCTURES = "salary_structures"
    SALARY_STRUCTURE_EARNINGS = "salary_structure_earnings"
    SALARY_STRUCTURE_DEDUCTIONS = "salary_structure_deductions"
    SALARY_STRUCTURE_ASSIGNMENTS = "salary_structure_assignments"
    PAYROLL_ENTRIES = "payroll_entries"
    SALARY_SLIPS = "salary_slips"
    SALARY_SLIP_EARNINGS = "salary_slip_earnings"
    SALARY_SLIP_DEDUCTIONS = "salary_slip_deductions"

    # HR - Appraisals
    APPRAISAL_TEMPLATES = "appraisal_templates"
    APPRAISAL_TEMPLATE_GOALS = "appraisal_template_goals"
    APPRAISALS = "appraisals"
    APPRAISAL_GOALS = "appraisal_goals"

    # HR - Training
    TRAINING_PROGRAMS = "training_programs"
    TRAINING_EVENTS = "training_events"
    TRAINING_EVENT_EMPLOYEES = "training_event_employees"
    TRAINING_RESULTS = "training_results"

    # Tax
    TAX_CODES = "tax_codes"
    TAX_CATEGORIES = "tax_categories"
    TAX_RATES = "tax_rates"
    TAX_WITHHOLDING_CATEGORIES = "tax_withholding_categories"
    TAX_RULES = "tax_rules"
    TAX_REGIONS = "tax_regions"
    TAX_TRANSACTIONS = "tax_transactions"
    TAX_FILING_PERIODS = "tax_filing_periods"
    TAX_PAYMENTS = "tax_payments"
    COMPANY_TAX_SETTINGS = "company_tax_settings"
    NG_VAT_TRANSACTIONS = "ng_vat_transactions"
    NG_WHT_TRANSACTIONS = "ng_wht_transactions"

    # CRM
    LEADS = "leads"
    LEAD_SOURCES = "lead_sources"
    OPPORTUNITY_STAGES = "opportunity_stages"
    OPPORTUNITIES = "opportunities"
    ACTIVITIES = "activities"
    CAMPAIGNS = "campaigns"

    # Support
    TICKETS = "tickets"
    UNIFIED_TICKETS = "unified_tickets"
    TICKET_COMMENTS = "ticket_comments"
    TICKET_COMMUNICATIONS = "ticket_communications"
    AGENTS = "agents"
    CANNED_RESPONSES = "canned_responses"
    AUTOMATION_RULES = "automation_rules"
    AUTOMATION_LOGS = "automation_logs"

    # Inventory
    ITEMS = "items"
    WAREHOUSES = "warehouses"
    STOCK_ENTRIES = "stock_entries"
    STOCK_ENTRY_DETAILS = "stock_entry_details"
    STOCK_LEDGER_ENTRIES = "stock_ledger_entries"
    BATCHES = "batches"
    SERIAL_NUMBERS = "serial_numbers"
    STOCK_RECEIPTS = "stock_receipts"
    STOCK_RECEIPT_ITEMS = "stock_receipt_items"
    STOCK_ISSUES = "stock_issues"
    STOCK_ISSUE_ITEMS = "stock_issue_items"
    TRANSFER_REQUESTS = "transfer_requests"

    # Projects
    PROJECTS = "projects"
    TASKS = "tasks"

    # Assets
    ASSET_CATEGORIES = "asset_categories"
    ASSETS = "assets"

    # Expenses
    EXPENSES = "expenses"
    EXPENSE_CLAIMS = "expense_claims"
    EXPENSE_CLAIM_LINES = "expense_claim_lines"
    CASH_ADVANCES = "cash_advances"


class MigrationJob(Base):
    """Tracks a data migration job from start to completion."""

    __tablename__ = "migration_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Job identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[EntityType] = mapped_column(Enum(EntityType), nullable=False, index=True)
    source_type: Mapped[Optional[SourceType]] = mapped_column(Enum(SourceType), nullable=True)

    # Status tracking
    status: Mapped[MigrationStatus] = mapped_column(
        Enum(MigrationStatus),
        default=MigrationStatus.PENDING,
        nullable=False,
        index=True
    )

    # Progress counts
    total_rows: Mapped[int] = mapped_column(default=0)
    processed_rows: Mapped[int] = mapped_column(default=0)
    created_records: Mapped[int] = mapped_column(default=0)
    updated_records: Mapped[int] = mapped_column(default=0)
    skipped_records: Mapped[int] = mapped_column(default=0)
    failed_records: Mapped[int] = mapped_column(default=0)

    # Configuration (stored as JSON)
    field_mapping: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    cleaning_rules: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    dedup_strategy: Mapped[Optional[DedupStrategy]] = mapped_column(Enum(DedupStrategy), nullable=True)
    dedup_fields: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # File handling
    source_file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # SHA256
    source_columns: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    sample_rows: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Validation results (stored as JSON)
    validation_result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    rolled_back_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    records: Mapped[list["MigrationRecord"]] = relationship(
        "MigrationRecord",
        back_populates="job",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<MigrationJob {self.id}: {self.name} ({self.entity_type.value}) - {self.status.value}>"

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.total_rows == 0:
            return 0.0
        return round((self.processed_rows / self.total_rows) * 100, 2)

    def start(self) -> None:
        """Mark migration as started."""
        self.status = MigrationStatus.RUNNING
        self.started_at = utc_now()

    def complete(self) -> None:
        """Mark migration as completed."""
        self.status = MigrationStatus.COMPLETED
        self.completed_at = utc_now()

    def fail(self, error_message: str, error_details: Optional[str] = None) -> None:
        """Mark migration as failed."""
        self.status = MigrationStatus.FAILED
        self.error_message = error_message
        self.error_details = error_details
        self.completed_at = utc_now()

    def cancel(self) -> None:
        """Mark migration as cancelled."""
        self.status = MigrationStatus.CANCELLED
        self.completed_at = utc_now()


class MigrationRecord(Base):
    """Individual record status within a migration job."""

    __tablename__ = "migration_records"

    __table_args__ = (
        Index("ix_migration_records_job_action", "job_id", "action"),
        Index("ix_migration_records_job_row", "job_id", "row_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Job reference
    job_id: Mapped[int] = mapped_column(ForeignKey("migration_jobs.id"), nullable=False, index=True)

    # Row identification
    row_number: Mapped[int] = mapped_column(nullable=False)

    # Data snapshots (stored as JSON)
    source_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    transformed_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Result tracking
    target_record_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    target_record_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    action: Mapped[Optional[RecordAction]] = mapped_column(Enum(RecordAction), nullable=True)

    # For updates/rollback - store previous data
    previous_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    can_rollback: Mapped[bool] = mapped_column(default=True)

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    validation_errors: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    validation_warnings: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Timestamps
    processed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    job: Mapped["MigrationJob"] = relationship("MigrationJob", back_populates="records")

    def __repr__(self) -> str:
        action_str = self.action.value if self.action else "pending"
        return f"<MigrationRecord job={self.job_id} row={self.row_number} action={action_str}>"


class MigrationRollbackLog(Base):
    """Tracks rollback operations for audit purposes."""

    __tablename__ = "migration_rollback_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # References
    job_id: Mapped[int] = mapped_column(ForeignKey("migration_jobs.id"), nullable=False, index=True)
    record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("migration_records.id"), nullable=True)

    # What was rolled back
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_record_id: Mapped[int] = mapped_column(nullable=False)

    # Action taken
    rollback_action: Mapped[str] = mapped_column(String(50), nullable=False)  # deleted, reverted
    previous_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Audit
    rolled_back_at: Mapped[datetime] = mapped_column(default=utc_now)
    rolled_back_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<MigrationRollbackLog job={self.job_id} action={self.rollback_action}>"
