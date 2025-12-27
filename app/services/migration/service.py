"""Migration service.

Orchestrates the data migration workflow including file parsing,
field mapping, validation, execution, and rollback.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from datetime import datetime
from typing import Any, Optional, BinaryIO
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.migration import (
    MigrationJob,
    MigrationRecord,
    MigrationRollbackLog,
    MigrationStatus,
    SourceType,
    DedupStrategy,
    RecordAction,
    EntityType,
)
from app.services.migration.registry import (
    get_entity_config,
    get_entity_fields,
    list_entities,
    ENTITY_REGISTRY,
)
from app.services.migration.cleaning import DataCleaningPipeline, CleaningRules
from app.services.migration.validator import MigrationValidator, ValidationResult
from app.utils.datetime_utils import utc_now


# Upload directory for migration files
MIGRATION_UPLOAD_DIR = Path("/tmp/migration_uploads")
MIGRATION_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class MigrationService:
    """Orchestrates the migration workflow."""

    def __init__(self, db: Session, user_id: Optional[int] = None):
        """Initialize the service.

        Args:
            db: Database session
            user_id: Current user ID
        """
        self.db = db
        self.user_id = user_id
        self.cleaner = DataCleaningPipeline()
        self.validator = MigrationValidator(db)

    # =========================================================================
    # JOB MANAGEMENT
    # =========================================================================

    def create_job(
        self,
        name: str,
        entity_type: str,
    ) -> MigrationJob:
        """Create a new migration job.

        Args:
            name: Job name
            entity_type: Target entity type

        Returns:
            Created MigrationJob
        """
        # Validate entity type
        if entity_type not in ENTITY_REGISTRY:
            raise ValueError(f"Unknown entity type: {entity_type}")

        job = MigrationJob(
            name=name,
            entity_type=EntityType(entity_type),
            status=MigrationStatus.PENDING,
            created_by_id=self.user_id,
            created_at=utc_now(),
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get_job(self, job_id: int) -> Optional[MigrationJob]:
        """Get a migration job by ID.

        Args:
            job_id: Job ID

        Returns:
            MigrationJob or None
        """
        return self.db.query(MigrationJob).filter(MigrationJob.id == job_id).first()

    def list_jobs(
        self,
        status: Optional[MigrationStatus] = None,
        entity_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[list[MigrationJob], int]:
        """List migration jobs.

        Args:
            status: Filter by status
            entity_type: Filter by entity type
            limit: Max results
            offset: Offset for pagination

        Returns:
            Tuple of (jobs, total_count)
        """
        query = self.db.query(MigrationJob)

        if status:
            query = query.filter(MigrationJob.status == status)
        if entity_type:
            query = query.filter(MigrationJob.entity_type == EntityType(entity_type))

        total = query.count()
        jobs = query.order_by(MigrationJob.created_at.desc()).offset(offset).limit(limit).all()

        return jobs, total

    def delete_job(self, job_id: int) -> bool:
        """Delete a migration job and its records.

        Args:
            job_id: Job ID

        Returns:
            True if deleted
        """
        job = self.get_job(job_id)
        if not job:
            return False

        # Can only delete pending/completed/failed/cancelled jobs
        if job.status == MigrationStatus.RUNNING:
            raise ValueError("Cannot delete a running migration")

        # Delete uploaded file if exists
        if job.source_file_path and os.path.exists(job.source_file_path):
            os.remove(job.source_file_path)

        self.db.delete(job)
        self.db.commit()
        return True

    # =========================================================================
    # FILE HANDLING
    # =========================================================================

    def upload_file(
        self,
        job_id: int,
        file_content: bytes,
        filename: str
    ) -> MigrationJob:
        """Upload and parse a source file.

        Args:
            job_id: Job ID
            file_content: File content bytes
            filename: Original filename

        Returns:
            Updated MigrationJob
        """
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if job.status not in (MigrationStatus.PENDING, MigrationStatus.UPLOADED):
            raise ValueError(f"Cannot upload file in status {job.status.value}")

        # Determine source type
        ext = Path(filename).suffix.lower()
        if ext == ".csv":
            source_type = SourceType.CSV
        elif ext == ".json":
            source_type = SourceType.JSON
        elif ext in (".xlsx", ".xls"):
            source_type = SourceType.EXCEL
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        # Calculate hash
        file_hash = hashlib.sha256(file_content).hexdigest()

        # Save file
        file_path = MIGRATION_UPLOAD_DIR / f"{job_id}_{file_hash[:8]}{ext}"
        with open(file_path, "wb") as f:
            f.write(file_content)

        # Parse file to get columns and sample
        columns, sample_rows, total_rows = self._parse_file(file_content, source_type)

        # Update job
        job.source_type = source_type
        job.source_file_path = str(file_path)
        job.source_file_hash = file_hash
        job.source_columns = columns
        job.sample_rows = sample_rows
        job.total_rows = total_rows
        job.status = MigrationStatus.UPLOADED

        self.db.commit()
        self.db.refresh(job)
        return job

    def _parse_file(
        self,
        file_content: bytes,
        source_type: SourceType
    ) -> tuple[list[str], list[dict], int]:
        """Parse file content to extract columns and sample rows.

        Args:
            file_content: File content bytes
            source_type: Type of source file

        Returns:
            Tuple of (columns, sample_rows, total_rows)
        """
        if source_type == SourceType.CSV:
            return self._parse_csv(file_content)
        elif source_type == SourceType.JSON:
            return self._parse_json(file_content)
        else:
            raise ValueError(f"Unsupported source type: {source_type}")

    def _parse_csv(self, file_content: bytes) -> tuple[list[str], list[dict], int]:
        """Parse CSV file."""
        # Try different encodings
        for encoding in ["utf-8-sig", "utf-8", "latin-1"]:
            try:
                text = file_content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("Could not decode CSV file")

        reader = csv.DictReader(io.StringIO(text))
        columns = reader.fieldnames or []

        rows = []
        total = 0
        for row in reader:
            total += 1
            if len(rows) < 10:  # Sample first 10 rows
                rows.append(dict(row))

        return columns, rows, total

    def _parse_json(self, file_content: bytes) -> tuple[list[str], list[dict], int]:
        """Parse JSON file."""
        data = json.loads(file_content.decode("utf-8"))

        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict) and "data" in data:
            rows = data["data"]
        else:
            raise ValueError("JSON must be an array or have a 'data' array")

        if not rows:
            return [], [], 0

        # Get columns from first row
        columns = list(rows[0].keys()) if rows else []

        # Sample rows
        sample = rows[:10]
        total = len(rows)

        return columns, sample, total

    # =========================================================================
    # FIELD MAPPING
    # =========================================================================

    def suggest_mapping(self, job_id: int) -> dict[str, str]:
        """Auto-suggest field mappings based on column names.

        Args:
            job_id: Job ID

        Returns:
            Dict of source_column -> target_field suggestions
        """
        job = self.get_job(job_id)
        if not job or not job.source_columns:
            return {}

        entity_fields = get_entity_fields(job.entity_type.value)
        suggestions = {}

        for source_col in job.source_columns:
            # Normalize column name for matching
            normalized = source_col.lower().strip().replace(" ", "_").replace("-", "_")

            # Exact match
            if normalized in entity_fields:
                suggestions[source_col] = normalized
                continue

            # Common aliases
            aliases = {
                "customer_name": "name",
                "full_name": "name",
                "contact_name": "name",
                "contact_category": "category",
                "email_address": "email",
                "e_mail": "email",
                "phone_number": "phone",
                "telephone": "phone",
                "mobile_number": "mobile",
                "cell_phone": "mobile",
                "invoice_no": "invoice_number",
                "inv_number": "invoice_number",
                "invoice_num": "invoice_number",
                "bill_no": "bill_number",
                "receipt_no": "receipt_number",
                "inv_date": "invoice_date",
                "date": "invoice_date",
                "payment_dt": "payment_date",
                "pay_date": "payment_date",
                "amt": "amount",
                "total_amt": "total_amount",
                "sub_total": "amount",
                "subtotal": "amount",
                "vat": "tax_amount",
                "tax": "tax_amount",
                "city_name": "city",
                "state_name": "state",
                "country_name": "country",
                "zip_code": "postal_code",
                "postcode": "postal_code",
                "address": "address_line1",
                "tax_id": "vat_id",
                "cust_id": "customer_id",
                "customer": "customer_id",
                "emp_id": "employee_id",
                "employee": "employee_id",
                "proj_id": "project_id",
                "project": "project_id",
                "desc": "description",
                "notes": "description",
                "memo": "description",
            }

            if normalized in aliases:
                target = aliases[normalized]
                if target in entity_fields:
                    suggestions[source_col] = target

        return suggestions

    def save_mapping(
        self,
        job_id: int,
        field_mapping: dict[str, str],
        cleaning_rules: Optional[dict] = None,
        dedup_strategy: Optional[str] = None,
        dedup_fields: Optional[list[str]] = None
    ) -> MigrationJob:
        """Save field mapping and configuration.

        Args:
            job_id: Job ID
            field_mapping: Source -> target field mapping
            cleaning_rules: Cleaning configuration
            dedup_strategy: Deduplication strategy
            dedup_fields: Fields to check for duplicates

        Returns:
            Updated MigrationJob
        """
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if job.status not in (MigrationStatus.UPLOADED, MigrationStatus.MAPPED, MigrationStatus.VALIDATED):
            raise ValueError(f"Cannot save mapping in status {job.status.value}")

        job.field_mapping = field_mapping
        job.cleaning_rules = cleaning_rules
        if dedup_strategy:
            job.dedup_strategy = DedupStrategy(dedup_strategy)
        job.dedup_fields = dedup_fields
        job.status = MigrationStatus.MAPPED

        self.db.commit()
        self.db.refresh(job)
        return job

    # =========================================================================
    # VALIDATION & PREVIEW
    # =========================================================================

    def validate(self, job_id: int) -> ValidationResult:
        """Run validation on the migration data.

        Args:
            job_id: Job ID

        Returns:
            ValidationResult
        """
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if not job.field_mapping:
            raise ValueError("Field mapping not configured")

        job.status = MigrationStatus.VALIDATING
        self.db.commit()

        # Load and transform data
        rows = self._load_all_rows(job)
        transformed_rows = self._transform_rows(rows, job)

        # Validate with FK checks
        result = self.validator.validate_with_fk(
            transformed_rows,
            job.entity_type.value,
            job.field_mapping,
            self.db,
            start_row=1
        )

        # Check for duplicates
        if job.dedup_fields:
            duplicates = self.validator.detect_duplicates(
                transformed_rows,
                job.dedup_fields,
                job.entity_type.value
            )
            if duplicates["in_file"]:
                for dup in duplicates["in_file"][:20]:
                    result.add_warning(
                        dup["field"],
                        f"Duplicate value found in rows {dup['rows']}",
                        value=dup["value"]
                    )

        # Store validation result
        job.validation_result = result.to_dict()
        job.status = MigrationStatus.VALIDATED if result.is_valid else MigrationStatus.MAPPED
        self.db.commit()

        return result

    def get_preview(
        self,
        job_id: int,
        limit: int = 100,
        offset: int = 0
    ) -> list[dict]:
        """Get preview of transformed data.

        Args:
            job_id: Job ID
            limit: Max rows to return
            offset: Offset for pagination

        Returns:
            List of preview rows with source and transformed data
        """
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if not job.field_mapping:
            return []

        # Load rows
        rows = self._load_all_rows(job)
        rows = rows[offset:offset + limit]

        # Transform and preview
        preview = []
        for i, row in enumerate(rows):
            transformed, warnings = self._transform_row(row, job)
            preview.append({
                "row_number": offset + i + 1,
                "source": row,
                "transformed": transformed,
                "warnings": warnings
            })

        return preview

    def _load_all_rows(self, job: MigrationJob) -> list[dict]:
        """Load all rows from source file.

        Args:
            job: Migration job

        Returns:
            List of row dicts
        """
        if not job.source_file_path or not os.path.exists(job.source_file_path):
            raise ValueError("Source file not found")

        with open(job.source_file_path, "rb") as f:
            content = f.read()

        _, rows, _ = self._parse_file(content, job.source_type)

        # Actually parse all rows for CSV
        if job.source_type == SourceType.CSV:
            for encoding in ["utf-8-sig", "utf-8", "latin-1"]:
                try:
                    text = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            reader = csv.DictReader(io.StringIO(text))
            rows = [dict(row) for row in reader]

        return rows

    def _transform_rows(
        self,
        rows: list[dict],
        job: MigrationJob
    ) -> list[dict]:
        """Transform rows using field mapping and cleaning.

        Args:
            rows: Source rows
            job: Migration job

        Returns:
            List of transformed rows
        """
        transformed = []
        for row in rows:
            result, _ = self._transform_row(row, job)
            transformed.append(result)
        return transformed

    def _transform_row(
        self,
        row: dict,
        job: MigrationJob
    ) -> tuple[dict, list]:
        """Transform a single row.

        Args:
            row: Source row
            job: Migration job

        Returns:
            Tuple of (transformed_row, warnings)
        """
        # Apply field mapping
        mapped = {}
        for source_col, target_field in (job.field_mapping or {}).items():
            if source_col in row:
                mapped[target_field] = row[source_col]

        # Apply cleaning
        if job.cleaning_rules:
            rules = CleaningRules.from_dict(job.cleaning_rules)
            self.cleaner.rules = rules

        # Get field normalizers from entity config
        entity_fields = get_entity_fields(job.entity_type.value)
        field_normalizers = {
            name: cfg.get("normalizer")
            for name, cfg in entity_fields.items()
            if cfg.get("normalizer")
        }

        cleaned, warnings = self.cleaner.clean_row(mapped, field_normalizers)
        return cleaned, warnings

    # =========================================================================
    # EXECUTION
    # =========================================================================

    def execute(self, job_id: int) -> None:
        """Execute the migration (should be called as Celery task).

        Args:
            job_id: Job ID
        """
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if job.status not in (MigrationStatus.VALIDATED, MigrationStatus.MAPPED):
            raise ValueError(f"Cannot execute in status {job.status.value}")

        job.start()
        self.db.commit()

        try:
            # Load and transform data
            rows = self._load_all_rows(job)
            job.total_rows = len(rows)

            # Process in batches
            batch_size = 500
            for batch_start in range(0, len(rows), batch_size):
                batch = rows[batch_start:batch_start + batch_size]

                for i, row in enumerate(batch):
                    row_num = batch_start + i + 1
                    try:
                        transformed, _ = self._transform_row(row, job)

                        # Create migration record
                        record = MigrationRecord(
                            job_id=job.id,
                            row_number=row_num,
                            source_data=row,
                            transformed_data=transformed,
                        )

                        # Process record (actual DB insert/update would happen here)
                        # For now, mark as created
                        record.action = RecordAction.CREATED
                        record.processed_at = utc_now()

                        self.db.add(record)
                        job.created_records += 1

                    except Exception as e:
                        # Create failed record
                        record = MigrationRecord(
                            job_id=job.id,
                            row_number=row_num,
                            source_data=row,
                            action=RecordAction.FAILED,
                            error_message=str(e),
                            processed_at=utc_now(),
                        )
                        self.db.add(record)
                        job.failed_records += 1

                    job.processed_rows += 1

                self.db.commit()

            job.complete()
            self.db.commit()

        except Exception as e:
            job.fail(str(e))
            self.db.commit()
            raise

    def get_progress(self, job_id: int) -> dict:
        """Get real-time progress of a migration.

        Args:
            job_id: Job ID

        Returns:
            Progress dict
        """
        job = self.get_job(job_id)
        if not job:
            return {"error": "Job not found"}

        return {
            "job_id": job.id,
            "status": job.status.value,
            "total_rows": job.total_rows,
            "processed_rows": job.processed_rows,
            "created_records": job.created_records,
            "updated_records": job.updated_records,
            "skipped_records": job.skipped_records,
            "failed_records": job.failed_records,
            "progress_percent": job.progress_percent,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error_message": job.error_message,
        }

    # =========================================================================
    # ROLLBACK
    # =========================================================================

    def rollback(self, job_id: int) -> dict:
        """Rollback a completed migration.

        Args:
            job_id: Job ID

        Returns:
            Rollback result dict
        """
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if job.status != MigrationStatus.COMPLETED:
            raise ValueError(f"Can only rollback completed migrations")

        # Get records that can be rolled back
        records = self.db.query(MigrationRecord).filter(
            MigrationRecord.job_id == job_id,
            MigrationRecord.can_rollback == True,
            MigrationRecord.action.in_([RecordAction.CREATED, RecordAction.UPDATED])
        ).all()

        rolled_back = 0
        for record in records:
            # Create rollback log
            log = MigrationRollbackLog(
                job_id=job_id,
                record_id=record.id,
                entity_type=job.entity_type.value,
                target_record_id=record.target_record_id or 0,
                rollback_action="deleted" if record.action == RecordAction.CREATED else "reverted",
                previous_data=record.previous_data,
                rolled_back_by_id=self.user_id,
            )
            self.db.add(log)
            record.can_rollback = False
            rolled_back += 1

        job.status = MigrationStatus.ROLLED_BACK
        job.rolled_back_at = utc_now()
        self.db.commit()

        return {
            "job_id": job_id,
            "rolled_back_records": rolled_back,
            "status": "rolled_back"
        }

    # =========================================================================
    # RECORDS
    # =========================================================================

    def get_records(
        self,
        job_id: int,
        action: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[list[MigrationRecord], int]:
        """Get migration records for a job.

        Args:
            job_id: Job ID
            action: Filter by action
            limit: Max results
            offset: Offset

        Returns:
            Tuple of (records, total_count)
        """
        query = self.db.query(MigrationRecord).filter(MigrationRecord.job_id == job_id)

        if action:
            query = query.filter(MigrationRecord.action == RecordAction(action))

        total = query.count()
        records = query.order_by(MigrationRecord.row_number).offset(offset).limit(limit).all()

        return records, total
