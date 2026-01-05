"""Data Cleaner Service.

Provides data cleaning and bulk editing capabilities:
- Bulk field updates with preview and rollback
- Phone/email/address normalization
- Duplicate detection and merging
- Orphan record linking

All operations support preview mode and maintain full audit trails.
"""
from __future__ import annotations

import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models.cleaning_operation import (
    CleaningOperation,
    CleaningOperationType,
    CleaningOperationStatus,
)
from app.services.audit_logger import AuditLogger, serialize_for_audit
from app.services.activity_logger import ActivityLogger
from app.services.errors import NotFoundError, ValidationError
from app.utils.address_normalizer import AddressNormalizer
from app.utils.normalizers import (
    normalize_phone,
    normalize_email,
    detect_duplicates,
)
from .table_registry import TABLES, is_valid_table
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

if TYPE_CHECKING:
    from app.auth import Principal


# Maximum records per bulk operation
MAX_BULK_RECORDS = 1000

# Tables that can be cleaned (subset of TABLE_REGISTRY)
CLEANABLE_TABLES = {
    "parties",
    "customer_accounts",
    "leads",
    "invoices",
    "payments",
    "credit_notes",
    "tickets",
    "conversations",
    "subscriptions",
    "employees",
}


class DataCleanerService:
    """Service for cleaning and bulk editing data.

    All write operations create audit trails and support rollback.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user (for audit fields).
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal
        self.audit_logger = AuditLogger(db)
        self.address_normalizer = AddressNormalizer()

    # =========================================================================
    # BULK UPDATE OPERATIONS
    # =========================================================================

    def preview_bulk_update(
        self,
        table: str,
        filters: Dict[str, Any],
        updates: Dict[str, Any],
        limit: int = 50,
    ) -> BulkUpdatePreview:
        """Preview bulk field updates without applying.

        Args:
            table: Target table name
            filters: Filters to select records
            updates: Field-value pairs to update
            limit: Max sample records to return

        Returns:
            Preview with affected count and sample changes
        """
        if not is_valid_table(table):
            raise NotFoundError(f"Table not found: {table}")

        if table not in CLEANABLE_TABLES:
            raise ValidationError(f"Table not allowed for cleaning: {table}")

        if not updates:
            raise ValidationError("No updates specified")

        model = TABLES[table]
        query = self._apply_filters(self.db.query(model), model, filters)

        total_count = query.count()
        if total_count > MAX_BULK_RECORDS:
            raise ValidationError(
                f"Too many records ({total_count}). Max allowed: {MAX_BULK_RECORDS}"
            )

        # Get sample records for preview
        sample_records = query.limit(limit).all()
        sample_changes: List[RecordChange] = []

        for record in sample_records:
            before = serialize_for_audit(record)
            after = {**before}

            changed_fields = []
            for field, value in updates.items():
                if hasattr(record, field):
                    old_value = before.get(field)
                    if old_value != value:
                        after[field] = value
                        changed_fields.append(field)

            if changed_fields:
                sample_changes.append(
                    RecordChange(
                        record_id=record.id,
                        before=before,
                        after=after,
                        changed_fields=changed_fields,
                    )
                )

        return BulkUpdatePreview(
            table=table,
            filters_applied=filters,
            updates_planned=updates,
            records_affected=total_count,
            sample_changes=sample_changes,
        )

    def execute_bulk_update(
        self,
        table: str,
        filters: Dict[str, Any],
        updates: Dict[str, Any],
        record_ids: Optional[List[int]] = None,
    ) -> BulkUpdateResult:
        """Apply bulk updates with full audit trail.

        Args:
            table: Target table name
            filters: Filters to select records
            updates: Field-value pairs to update
            record_ids: Optional subset of record IDs (from preview)

        Returns:
            Result with operation ID for rollback
        """
        if not is_valid_table(table):
            raise NotFoundError(f"Table not found: {table}")

        if table not in CLEANABLE_TABLES:
            raise ValidationError(f"Table not allowed for cleaning: {table}")

        model = TABLES[table]
        query = self._apply_filters(self.db.query(model), model, filters)

        if record_ids:
            query = query.filter(model.id.in_(record_ids))

        total_count = query.count()
        if total_count > MAX_BULK_RECORDS:
            raise ValidationError(
                f"Too many records ({total_count}). Max allowed: {MAX_BULK_RECORDS}"
            )

        # Create operation record
        operation_id = str(uuid.uuid4())
        operation = CleaningOperation(
            operation_id=operation_id,
            operation_type=CleaningOperationType.BULK_UPDATE,
            table_name=table,
            operation_config={"filters": filters, "updates": updates},
        )
        self.db.add(operation)
        operation.start()

        # Process records
        records = query.all()
        changes_log: List[Dict[str, Any]] = []
        rollback_data: Dict[str, Any] = {}
        errors: List[OperationError] = []
        records_updated = 0

        user_id = self.principal.user_id if self.principal else None

        for record in records:
            try:
                before = serialize_for_audit(record)
                rollback_data[str(record.id)] = before

                changed_fields = []
                for field, value in updates.items():
                    if hasattr(record, field):
                        old_value = getattr(record, field)
                        if self._serialize_value(old_value) != value:
                            setattr(record, field, value)
                            changed_fields.append(field)

                if changed_fields:
                    after = serialize_for_audit(record)
                    changes_log.append({
                        "record_id": record.id,
                        "before": before,
                        "after": after,
                        "changed_fields": changed_fields,
                    })

                    # Log to audit trail
                    self.audit_logger.log_update(
                        doctype=table,
                        document_id=record.id,
                        old_values=before,
                        new_values=after,
                        user_id=user_id,
                        remarks=f"Bulk update operation {operation_id}",
                    )

                    records_updated += 1

            except Exception as e:
                errors.append(
                    OperationError(record_id=record.id, error=str(e))
                )

        # Complete operation
        operation.complete(
            records_affected=records_updated,
            records_failed=len(errors),
            changes_log=changes_log,
            rollback_data=rollback_data,
            errors=[{"record_id": e.record_id, "error": e.error, "field": e.field} for e in errors],
        )
        operation.summary = {
            "updates": updates,
            "filters": filters,
        }

        self.db.flush()

        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="ops.data_cleanup.bulk_update",
            user_id=user_id,
            entity_type="data_cleanup",
            entity_id=operation_id,
            summary=f"Bulk update on {table}",
            metadata={"records_updated": records_updated, "records_failed": len(errors)},
        )
        return BulkUpdateResult(
            operation_id=operation_id,
            table=table,
            records_updated=records_updated,
            records_failed=len(errors),
            errors=errors,
            rollback_available=True,
            changes_log=[
                RecordChange(
                    record_id=c["record_id"],
                    before=c["before"],
                    after=c["after"],
                    changed_fields=c["changed_fields"],
                )
                for c in changes_log[:50]  # Limit for response size
            ],
        )

    # =========================================================================
    # NORMALIZATION OPERATIONS
    # =========================================================================

    def preview_normalize_phones(
        self,
        country: str = "NG",
        filters: Optional[CleaningFilters] = None,
    ) -> NormalizePreview:
        """Preview phone normalization to E.164 format.

        Args:
            country: Country code for normalization (default "NG")
            filters: Optional filters to select records

        Returns:
            Preview with normalization statistics
        """
        from app.models.party import Party

        query = self.db.query(Party).filter(Party.primary_phone.isnot(None))

        if filters:
            query = self._apply_cleaning_filters(query, Party, filters)

        records = query.limit(MAX_BULK_RECORDS).all()

        records_to_normalize = 0
        already_normalized = 0
        invalid_values = 0
        sample_changes: List[RecordChange] = []
        invalid_samples: List[Dict[str, Any]] = []

        for record in records:
            phone = record.primary_phone
            if not phone:
                continue

            result = normalize_phone(phone, country)

            if result.is_valid:
                if result.normalized != phone:
                    records_to_normalize += 1
                    if len(sample_changes) < 50:
                        sample_changes.append(
                            RecordChange(
                                record_id=record.id,
                                before={"primary_phone": phone},
                                after={"primary_phone": result.normalized},
                                changed_fields=["primary_phone"],
                            )
                        )
                else:
                    already_normalized += 1
            else:
                invalid_values += 1
                if len(invalid_samples) < 20:
                    invalid_samples.append({
                        "record_id": record.id,
                        "value": phone,
                        "error": result.error,
                    })

        return NormalizePreview(
            field="primary_phone",
            records_to_normalize=records_to_normalize,
            already_normalized=already_normalized,
            invalid_values=invalid_values,
            sample_changes=sample_changes,
            invalid_samples=invalid_samples,
        )

    def execute_normalize_phones(
        self,
        country: str = "NG",
        record_ids: Optional[List[int]] = None,
    ) -> NormalizeResult:
        """Apply phone normalization to E.164 format.

        Args:
            country: Country code for normalization
            record_ids: Optional subset of record IDs

        Returns:
            Result with operation ID for rollback
        """
        from app.models.party import Party

        query = self.db.query(Party).filter(Party.primary_phone.isnot(None))

        if record_ids:
            query = query.filter(Party.id.in_(record_ids))

        records = query.limit(MAX_BULK_RECORDS).all()

        # Create operation record
        operation_id = str(uuid.uuid4())
        operation = CleaningOperation(
            operation_id=operation_id,
            operation_type=CleaningOperationType.NORMALIZE,
            table_name="parties",
            operation_config={"field": "primary_phone", "country": country},
        )
        self.db.add(operation)
        operation.start()

        changes_log: List[Dict[str, Any]] = []
        rollback_data: Dict[str, Any] = {}
        errors: List[OperationError] = []
        records_normalized = 0
        records_skipped = 0

        user_id = self.principal.user_id if self.principal else None

        for record in records:
            phone = record.primary_phone
            if not phone:
                records_skipped += 1
                continue

            result = normalize_phone(phone, country)

            if result.is_valid and result.normalized != phone:
                try:
                    rollback_data[str(record.id)] = {"primary_phone": phone}
                    record.primary_phone = result.normalized

                    changes_log.append({
                        "record_id": record.id,
                        "before": {"primary_phone": phone},
                        "after": {"primary_phone": result.normalized},
                        "changed_fields": ["primary_phone"],
                    })

                    self.audit_logger.log_update(
                        doctype="parties",
                        document_id=record.id,
                        old_values={"primary_phone": phone},
                        new_values={"primary_phone": result.normalized},
                        user_id=user_id,
                        remarks=f"Phone normalization {operation_id}",
                    )

                    records_normalized += 1

                except Exception as e:
                    errors.append(
                        OperationError(
                            record_id=record.id,
                            error=str(e),
                            field="primary_phone",
                        )
                    )
            elif not result.is_valid:
                errors.append(
                    OperationError(
                        record_id=record.id,
                        error=result.error or "Invalid phone",
                        field="primary_phone",
                    )
                )
            else:
                records_skipped += 1

        operation.complete(
            records_affected=records_normalized,
            records_failed=len(errors),
            changes_log=changes_log,
            rollback_data=rollback_data,
            errors=[{"record_id": e.record_id, "error": e.error, "field": e.field} for e in errors],
        )
        operation.summary = {"field": "primary_phone", "country": country}

        self.db.flush()

        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="ops.data_cleanup.normalize_phones",
            user_id=user_id,
            entity_type="data_cleanup",
            entity_id=operation_id,
            summary="Normalized phone numbers",
            metadata={"normalized": records_normalized, "skipped": records_skipped, "failed": len(errors)},
        )
        return NormalizeResult(
            operation_id=operation_id,
            field="primary_phone",
            records_normalized=records_normalized,
            records_skipped=records_skipped,
            records_failed=len(errors),
            errors=errors,
            rollback_available=True,
        )

    def preview_normalize_emails(
        self,
        filters: Optional[CleaningFilters] = None,
    ) -> NormalizePreview:
        """Preview email normalization (lowercase, trim).

        Args:
            filters: Optional filters to select records

        Returns:
            Preview with normalization statistics
        """
        from app.models.party import Party

        query = self.db.query(Party).filter(Party.primary_email.isnot(None))

        if filters:
            query = self._apply_cleaning_filters(query, Party, filters)

        records = query.limit(MAX_BULK_RECORDS).all()

        records_to_normalize = 0
        already_normalized = 0
        invalid_values = 0
        sample_changes: List[RecordChange] = []
        invalid_samples: List[Dict[str, Any]] = []

        for record in records:
            email = record.primary_email
            if not email:
                continue

            result = normalize_email(email)

            if result.is_valid:
                if result.normalized != email:
                    records_to_normalize += 1
                    if len(sample_changes) < 50:
                        sample_changes.append(
                            RecordChange(
                                record_id=record.id,
                                before={"primary_email": email},
                                after={"primary_email": result.normalized},
                                changed_fields=["primary_email"],
                            )
                        )
                else:
                    already_normalized += 1
            else:
                invalid_values += 1
                if len(invalid_samples) < 20:
                    invalid_samples.append({
                        "record_id": record.id,
                        "value": email,
                        "error": result.error,
                    })

        return NormalizePreview(
            field="primary_email",
            records_to_normalize=records_to_normalize,
            already_normalized=already_normalized,
            invalid_values=invalid_values,
            sample_changes=sample_changes,
            invalid_samples=invalid_samples,
        )

    def execute_normalize_emails(
        self,
        record_ids: Optional[List[int]] = None,
    ) -> NormalizeResult:
        """Apply email normalization (lowercase, trim).

        Args:
            record_ids: Optional subset of record IDs

        Returns:
            Result with operation ID for rollback
        """
        from app.models.party import Party

        query = self.db.query(Party).filter(Party.primary_email.isnot(None))

        if record_ids:
            query = query.filter(Party.id.in_(record_ids))

        records = query.limit(MAX_BULK_RECORDS).all()

        # Create operation record
        operation_id = str(uuid.uuid4())
        operation = CleaningOperation(
            operation_id=operation_id,
            operation_type=CleaningOperationType.NORMALIZE,
            table_name="parties",
            operation_config={"field": "primary_email"},
        )
        self.db.add(operation)
        operation.start()

        changes_log: List[Dict[str, Any]] = []
        rollback_data: Dict[str, Any] = {}
        errors: List[OperationError] = []
        records_normalized = 0
        records_skipped = 0

        user_id = self.principal.user_id if self.principal else None

        for record in records:
            email = record.primary_email
            if not email:
                records_skipped += 1
                continue

            result = normalize_email(email)

            if result.is_valid and result.normalized != email:
                try:
                    rollback_data[str(record.id)] = {"primary_email": email}
                    record.primary_email = result.normalized

                    changes_log.append({
                        "record_id": record.id,
                        "before": {"primary_email": email},
                        "after": {"primary_email": result.normalized},
                        "changed_fields": ["primary_email"],
                    })

                    self.audit_logger.log_update(
                        doctype="parties",
                        document_id=record.id,
                        old_values={"primary_email": email},
                        new_values={"primary_email": result.normalized},
                        user_id=user_id,
                        remarks=f"Email normalization {operation_id}",
                    )

                    records_normalized += 1

                except Exception as e:
                    errors.append(
                        OperationError(
                            record_id=record.id,
                            error=str(e),
                            field="primary_email",
                        )
                    )
            elif not result.is_valid:
                errors.append(
                    OperationError(
                        record_id=record.id,
                        error=result.error or "Invalid email",
                        field="primary_email",
                    )
                )
            else:
                records_skipped += 1

        operation.complete(
            records_affected=records_normalized,
            records_failed=len(errors),
            changes_log=changes_log,
            rollback_data=rollback_data,
            errors=[{"record_id": e.record_id, "error": e.error, "field": e.field} for e in errors],
        )
        operation.summary = {"field": "primary_email"}

        self.db.flush()

        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="ops.data_cleanup.normalize_emails",
            user_id=user_id,
            entity_type="data_cleanup",
            entity_id=operation_id,
            summary="Normalized email addresses",
            metadata={"normalized": records_normalized, "skipped": records_skipped, "failed": len(errors)},
        )
        return NormalizeResult(
            operation_id=operation_id,
            field="primary_email",
            records_normalized=records_normalized,
            records_skipped=records_skipped,
            records_failed=len(errors),
            errors=errors,
            rollback_available=True,
        )

    # =========================================================================
    # DUPLICATE DETECTION
    # =========================================================================

    def find_duplicates(
        self,
        table: str,
        match_fields: List[str],
    ) -> DuplicateReport:
        """Find duplicate records by matching fields.

        Args:
            table: Target table name
            match_fields: Fields to match on (e.g., ["primary_email"])

        Returns:
            Report with duplicate groups
        """
        if not is_valid_table(table):
            raise NotFoundError(f"Table not found: {table}")

        if table not in CLEANABLE_TABLES:
            raise ValidationError(f"Table not allowed for cleaning: {table}")

        model = TABLES[table]

        # Validate match fields exist
        for field in match_fields:
            if not hasattr(model, field):
                raise ValidationError(f"Field not found: {field}")

        # Get all records
        records = self.db.query(model).limit(MAX_BULK_RECORDS * 2).all()

        # Convert to dicts
        record_dicts = []
        for record in records:
            record_dict = {"id": record.id}
            for field in match_fields:
                record_dict[field] = getattr(record, field)
            record_dicts.append(record_dict)

        # Detect duplicates
        duplicates_map = detect_duplicates(record_dicts, match_fields)

        # Build groups
        groups: List[DuplicateGroup] = []
        total_duplicates = 0

        for match_key, ids in duplicates_map.items():
            if len(ids) < 2:
                continue

            group_records = [r for r in records if r.id in ids]
            records_data = [serialize_for_audit(r) for r in group_records]

            # Suggest oldest record as primary
            oldest = min(group_records, key=lambda r: r.created_at if hasattr(r, 'created_at') and r.created_at else datetime.max)

            groups.append(
                DuplicateGroup(
                    match_key=match_key,
                    record_ids=ids,
                    records=records_data,
                    suggested_primary=oldest.id,
                )
            )
            total_duplicates += len(ids) - 1

        return DuplicateReport(
            table=table,
            match_fields=match_fields,
            total_groups=len(groups),
            total_duplicates=total_duplicates,
            groups=groups[:100],  # Limit for response size
        )

    def preview_merge_duplicates(
        self,
        table: str,
        primary_id: int,
        duplicate_ids: List[int],
        field_resolution: Optional[Dict[str, str]] = None,
    ) -> MergePreview:
        """Preview merging duplicate records into primary.

        Args:
            table: Target table name
            primary_id: ID of record to keep
            duplicate_ids: IDs of records to merge into primary
            field_resolution: Field -> resolution strategy mapping

        Returns:
            Preview showing merge result
        """
        if not is_valid_table(table):
            raise NotFoundError(f"Table not found: {table}")

        model = TABLES[table]

        primary = self.db.query(model).filter(model.id == primary_id).first()
        if not primary:
            raise NotFoundError(f"Primary record not found: {primary_id}")

        duplicates = self.db.query(model).filter(model.id.in_(duplicate_ids)).all()
        if len(duplicates) != len(duplicate_ids):
            raise ValidationError("Some duplicate records not found")

        primary_data = serialize_for_audit(primary)
        duplicate_data = [serialize_for_audit(d) for d in duplicates]

        # Calculate merged result (use primary values by default)
        merged_result = {**primary_data}

        if field_resolution:
            for field, strategy in field_resolution.items():
                if strategy == "keep_newest":
                    # Find newest value among all records
                    all_records = [primary] + duplicates
                    newest = max(all_records, key=lambda r: r.updated_at if hasattr(r, 'updated_at') and r.updated_at else datetime.min)
                    merged_result[field] = getattr(newest, field) if hasattr(newest, field) else merged_result.get(field)
                elif strategy.isdigit():
                    # Use value from specific record ID
                    source_id = int(strategy)
                    source = next((r for r in duplicates if r.id == source_id), None)
                    if source and hasattr(source, field):
                        merged_result[field] = getattr(source, field)

        # Count related records that would be relinked
        related_records: Dict[str, int] = {}

        # Check common FK relationships
        fk_tables = {
            "parties": [
                ("invoices", "party_id"),
                ("payments", "party_id"),
                ("tickets", "party_id"),
                ("subscriptions", "party_id"),
            ],
            "customer_accounts": [
                ("invoices", "customer_account_id"),
                ("payments", "customer_account_id"),
                ("tickets", "customer_account_id"),
                ("subscriptions", "customer_account_id"),
            ],
        }

        for fk_table, fk_field in fk_tables.get(table, []):
            if fk_table in TABLES:
                fk_model = TABLES[fk_table]
                fk_column = getattr(fk_model, fk_field, None)
                if fk_column:
                    count = (
                        self.db.query(fk_model)
                        .filter(fk_column.in_(duplicate_ids))
                        .count()
                    )
                    if count > 0:
                        related_records[fk_table] = count

        return MergePreview(
            primary_record=primary_data,
            duplicate_records=duplicate_data,
            merged_result=merged_result,
            related_records_to_relink=related_records,
            records_to_delete=duplicate_ids,
        )

    def execute_merge_duplicates(
        self,
        table: str,
        primary_id: int,
        duplicate_ids: List[int],
        field_resolution: Optional[Dict[str, str]] = None,
    ) -> MergeResult:
        """Merge duplicates: update primary, relink FKs, soft-delete duplicates.

        Args:
            table: Target table name
            primary_id: ID of record to keep
            duplicate_ids: IDs of records to merge
            field_resolution: Field -> resolution strategy mapping

        Returns:
            Result with operation ID for rollback
        """
        if not is_valid_table(table):
            raise NotFoundError(f"Table not found: {table}")

        model = TABLES[table]

        primary = self.db.query(model).filter(model.id == primary_id).first()
        if not primary:
            raise NotFoundError(f"Primary record not found: {primary_id}")

        duplicates = self.db.query(model).filter(model.id.in_(duplicate_ids)).all()

        # Create operation record
        operation_id = str(uuid.uuid4())
        operation = CleaningOperation(
            operation_id=operation_id,
            operation_type=CleaningOperationType.MERGE,
            table_name=table,
            operation_config={
                "primary_id": primary_id,
                "duplicate_ids": duplicate_ids,
                "field_resolution": field_resolution,
            },
        )
        self.db.add(operation)
        operation.start()

        changes_log: List[Dict[str, Any]] = []
        rollback_data: Dict[str, Any] = {
            "primary": serialize_for_audit(primary),
            "duplicates": {str(d.id): serialize_for_audit(d) for d in duplicates},
            "relinked": {},
        }
        errors: List[OperationError] = []
        records_relinked: Dict[str, int] = {}

        user_id = self.principal.user_id if self.principal else None

        try:
            # Apply field resolution to primary
            if field_resolution:
                for field, strategy in field_resolution.items():
                    if strategy == "keep_newest":
                        all_records = [primary] + duplicates
                        newest = max(all_records, key=lambda r: r.updated_at if hasattr(r, 'updated_at') and r.updated_at else datetime.min)
                        if hasattr(primary, field):
                            setattr(primary, field, getattr(newest, field))
                    elif strategy.isdigit():
                        source_id = int(strategy)
                        source = next((r for r in duplicates if r.id == source_id), None)
                        if source and hasattr(source, field):
                            setattr(primary, field, getattr(source, field))

            # Relink foreign keys
            fk_tables = {
                "parties": [
                    ("invoices", "party_id"),
                    ("payments", "party_id"),
                    ("tickets", "party_id"),
                    ("subscriptions", "party_id"),
                ],
                "customer_accounts": [
                    ("invoices", "customer_account_id"),
                    ("payments", "customer_account_id"),
                    ("tickets", "customer_account_id"),
                    ("subscriptions", "customer_account_id"),
                ],
            }

            for fk_table, fk_field in fk_tables.get(table, []):
                if fk_table in TABLES:
                    fk_model = TABLES[fk_table]
                    fk_column = getattr(fk_model, fk_field, None)
                    if fk_column:
                        affected = (
                            self.db.query(fk_model)
                            .filter(fk_column.in_(duplicate_ids))
                            .all()
                        )

                        relinked_ids = []
                        for record in affected:
                            old_value = getattr(record, fk_field)
                            setattr(record, fk_field, primary_id)
                            relinked_ids.append(record.id)

                        if relinked_ids:
                            records_relinked[fk_table] = len(relinked_ids)
                            rollback_data["relinked"][fk_table] = {
                                str(r.id): {fk_field: old_value} for r in affected
                            }

            # Soft-delete duplicates (set status to inactive if available)
            for duplicate in duplicates:
                before = serialize_for_audit(duplicate)

                if hasattr(duplicate, "status"):
                    duplicate.status = "INACTIVE"
                if hasattr(duplicate, "is_active"):
                    duplicate.is_active = False

                after = serialize_for_audit(duplicate)
                changes_log.append({
                    "record_id": duplicate.id,
                    "before": before,
                    "after": after,
                    "changed_fields": ["status"],
                })

                self.audit_logger.log_update(
                    doctype=table,
                    document_id=duplicate.id,
                    old_values=before,
                    new_values=after,
                    user_id=user_id,
                    remarks=f"Merged into {primary_id} (operation {operation_id})",
                )

        except Exception as e:
            errors.append(
                OperationError(record_id=primary_id, error=str(e))
            )

        operation.complete(
            records_affected=len(duplicates),
            records_failed=len(errors),
            changes_log=changes_log,
            rollback_data=rollback_data,
            errors=[{"record_id": e.record_id, "error": e.error, "field": e.field} for e in errors],
        )
        operation.summary = {
            "primary_id": primary_id,
            "merged_ids": duplicate_ids,
            "records_relinked": records_relinked,
        }

        self.db.flush()

        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="ops.data_cleanup.merge_duplicates",
            user_id=user_id,
            entity_type="data_cleanup",
            entity_id=operation_id,
            summary=f"Merged duplicates in {table}",
            metadata={
                "primary_id": primary_id,
                "merged_ids": duplicate_ids,
                "records_relinked": records_relinked,
            },
        )
        return MergeResult(
            operation_id=operation_id,
            primary_id=primary_id,
            merged_ids=duplicate_ids,
            records_relinked=records_relinked,
            errors=errors,
            rollback_available=True,
        )

    # =========================================================================
    # ORPHAN RECORD LINKING
    # =========================================================================

    def find_orphans(
        self,
        table: str,
        fk_field: str,
    ) -> OrphanReport:
        """Find records with null FK references.

        Args:
            table: Target table name
            fk_field: Foreign key field to check

        Returns:
            Report with orphan records
        """
        if not is_valid_table(table):
            raise NotFoundError(f"Table not found: {table}")

        model = TABLES[table]
        fk_column = getattr(model, fk_field, None)
        if fk_column is None:
            raise ValidationError(f"Field not found: {fk_field}")

        orphans = (
            self.db.query(model)
            .filter(fk_column.is_(None))
            .limit(MAX_BULK_RECORDS)
            .all()
        )

        sample_orphans: List[OrphanRecord] = []
        for record in orphans[:50]:
            sample_orphans.append(
                OrphanRecord(
                    record_id=record.id,
                    record_data=serialize_for_audit(record),
                    match_value=None,
                    potential_matches=[],
                )
            )

        return OrphanReport(
            table=table,
            fk_field=fk_field,
            total_orphans=len(orphans),
            sample_orphans=sample_orphans,
        )

    def preview_link_orphans(
        self,
        table: str,
        fk_field: str,
        matching_rules: List[MatchingRule],
    ) -> LinkPreview:
        """Preview linking orphans using matching rules.

        Args:
            table: Source table with orphans
            fk_field: FK field that is null
            matching_rules: Rules for matching orphans to targets

        Returns:
            Preview with potential matches
        """
        if not is_valid_table(table):
            raise NotFoundError(f"Table not found: {table}")

        model = TABLES[table]
        fk_column = getattr(model, fk_field, None)
        if fk_column is None:
            raise ValidationError(f"Field not found: {fk_field}")

        orphans = (
            self.db.query(model)
            .filter(fk_column.is_(None))
            .limit(MAX_BULK_RECORDS)
            .all()
        )

        matches: List[LinkMatch] = []
        unmatched = 0

        for record in orphans:
            matched = False

            for rule in matching_rules:
                orphan_value = getattr(record, rule.orphan_field, None)
                if not orphan_value:
                    continue

                target_model = TABLES.get(rule.target_table)
                if not target_model:
                    continue

                target_column = getattr(target_model, rule.target_field, None)
                if not target_column:
                    continue

                # Find matching target
                if rule.match_type == "exact":
                    target = (
                        self.db.query(target_model)
                        .filter(target_column == orphan_value)
                        .first()
                    )
                elif rule.match_type == "contains":
                    target = (
                        self.db.query(target_model)
                        .filter(target_column.ilike(f"%{orphan_value}%"))
                        .first()
                    )
                else:
                    target = None

                if target:
                    matches.append(
                        LinkMatch(
                            orphan_id=record.id,
                            target_id=target.id,
                            match_confidence=1.0 if rule.match_type == "exact" else 0.8,
                            match_reason=f"{rule.match_type} match on {rule.orphan_field}",
                        )
                    )
                    matched = True
                    break

            if not matched:
                unmatched += 1

        return LinkPreview(
            table=table,
            fk_field=fk_field,
            matches_found=len(matches),
            unmatched=unmatched,
            sample_matches=matches[:50],
        )

    def execute_link_orphans(
        self,
        table: str,
        fk_field: str,
        links: Dict[int, int],
    ) -> LinkResult:
        """Apply orphan linking.

        Args:
            table: Source table with orphans
            fk_field: FK field to update
            links: Mapping of orphan_id -> target_id

        Returns:
            Result with operation ID for rollback
        """
        if not is_valid_table(table):
            raise NotFoundError(f"Table not found: {table}")

        model = TABLES[table]
        fk_column = getattr(model, fk_field, None)
        if fk_column is None:
            raise ValidationError(f"Field not found: {fk_field}")

        # Create operation record
        operation_id = str(uuid.uuid4())
        operation = CleaningOperation(
            operation_id=operation_id,
            operation_type=CleaningOperationType.LINK,
            table_name=table,
            operation_config={"fk_field": fk_field, "links": links},
        )
        self.db.add(operation)
        operation.start()

        changes_log: List[Dict[str, Any]] = []
        rollback_data: Dict[str, Any] = {}
        errors: List[OperationError] = []
        records_linked = 0

        user_id = self.principal.user_id if self.principal else None

        for orphan_id, target_id in links.items():
            record = self.db.query(model).filter(model.id == orphan_id).first()
            if not record:
                errors.append(
                    OperationError(record_id=orphan_id, error="Record not found")
                )
                continue

            try:
                old_value = getattr(record, fk_field)
                rollback_data[str(orphan_id)] = {fk_field: old_value}

                setattr(record, fk_field, target_id)

                changes_log.append({
                    "record_id": orphan_id,
                    "before": {fk_field: old_value},
                    "after": {fk_field: target_id},
                    "changed_fields": [fk_field],
                })

                self.audit_logger.log_update(
                    doctype=table,
                    document_id=orphan_id,
                    old_values={fk_field: old_value},
                    new_values={fk_field: target_id},
                    user_id=user_id,
                    remarks=f"Orphan linking {operation_id}",
                )

                records_linked += 1

            except Exception as e:
                errors.append(
                    OperationError(record_id=orphan_id, error=str(e), field=fk_field)
                )

        operation.complete(
            records_affected=records_linked,
            records_failed=len(errors),
            changes_log=changes_log,
            rollback_data=rollback_data,
            errors=[{"record_id": e.record_id, "error": e.error, "field": e.field} for e in errors],
        )
        operation.summary = {"fk_field": fk_field}

        self.db.flush()

        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="ops.data_cleanup.link_orphans",
            user_id=user_id,
            entity_type="data_cleanup",
            entity_id=operation_id,
            summary=f"Linked orphans in {table}",
            metadata={
                "fk_field": fk_field,
                "records_linked": records_linked,
                "records_failed": len(errors),
            },
        )
        return LinkResult(
            operation_id=operation_id,
            table=table,
            fk_field=fk_field,
            records_linked=records_linked,
            records_unmatched=len(links) - records_linked,
            errors=errors,
            rollback_available=True,
        )

    # =========================================================================
    # ROLLBACK
    # =========================================================================

    def list_operations(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> List[CleaningOperationSummary]:
        """List recent cleaning operations.

        Args:
            limit: Max operations to return
            offset: Pagination offset

        Returns:
            List of operation summaries
        """
        operations = (
            self.db.query(CleaningOperation)
            .order_by(CleaningOperation.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        from app.models.auth import User

        summaries: List[CleaningOperationSummary] = []
        for op in operations:
            user_name = None
            if op.created_by_id:
                user = self.db.query(User).filter(User.id == op.created_by_id).first()
                if user:
                    user_name = user.name

            summaries.append(
                CleaningOperationSummary(
                    operation_id=op.operation_id,
                    operation_type=op.operation_type.value,
                    table=op.table_name,
                    records_affected=op.records_affected,
                    records_failed=op.records_failed,
                    created_at=op.created_at,
                    created_by_id=op.created_by_id or 0,
                    created_by_name=user_name,
                    is_rolled_back=op.is_rolled_back,
                    rolled_back_at=op.rolled_back_at,
                    summary=op.summary or {},
                )
            )

        return summaries

    def preview_rollback(
        self,
        operation_id: str,
    ) -> RollbackPreview:
        """Preview rolling back an operation.

        Args:
            operation_id: ID of operation to rollback

        Returns:
            Preview showing what will be restored
        """
        operation = (
            self.db.query(CleaningOperation)
            .filter(CleaningOperation.operation_id == operation_id)
            .first()
        )

        if not operation:
            raise NotFoundError(f"Operation not found: {operation_id}")

        if not operation.is_rollbackable:
            raise ValidationError("Operation cannot be rolled back")

        sample_restorations: List[RecordChange] = []
        rollback_data = operation.rollback_data or {}

        for record_id, before_state in list(rollback_data.items())[:20]:
            sample_restorations.append(
                RecordChange(
                    record_id=int(record_id),
                    before={},  # Current state unknown without query
                    after=before_state,
                    changed_fields=list(before_state.keys()),
                )
            )

        return RollbackPreview(
            operation_id=operation_id,
            operation_type=operation.operation_type.value,
            table=operation.table_name,
            records_to_restore=len(rollback_data),
            sample_restorations=sample_restorations,
        )

    def rollback_operation(
        self,
        operation_id: str,
    ) -> RollbackResult:
        """Rollback a previous cleaning operation.

        Args:
            operation_id: ID of operation to rollback

        Returns:
            Result of rollback
        """
        operation = (
            self.db.query(CleaningOperation)
            .filter(CleaningOperation.operation_id == operation_id)
            .first()
        )

        if not operation:
            raise NotFoundError(f"Operation not found: {operation_id}")

        if not operation.is_rollbackable:
            raise ValidationError("Operation cannot be rolled back")

        model = TABLES.get(operation.table_name)
        if not model:
            raise ValidationError(f"Table not found: {operation.table_name}")

        rollback_data = operation.rollback_data or {}
        errors: List[OperationError] = []
        records_restored = 0

        user_id = self.principal.user_id if self.principal else None

        for record_id_str, before_state in rollback_data.items():
            record_id = int(record_id_str)
            record = self.db.query(model).filter(model.id == record_id).first()

            if not record:
                errors.append(
                    OperationError(record_id=record_id, error="Record not found")
                )
                continue

            try:
                current_state = serialize_for_audit(record)

                for field, value in before_state.items():
                    if hasattr(record, field):
                        setattr(record, field, value)

                self.audit_logger.log_update(
                    doctype=operation.table_name,
                    document_id=record_id,
                    old_values=current_state,
                    new_values=before_state,
                    user_id=user_id,
                    remarks=f"Rollback of operation {operation_id}",
                )

                records_restored += 1

            except Exception as e:
                errors.append(
                    OperationError(record_id=record_id, error=str(e))
                )

        # Mark operation as rolled back
        operation.rollback(user_id or 0)

        self.db.flush()

        return RollbackResult(
            operation_id=operation_id,
            records_restored=records_restored,
            records_failed=len(errors),
            errors=errors,
            success=len(errors) == 0,
        )

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _apply_filters(
        self,
        query: Any,
        model: Any,
        filters: Optional[Dict[str, Any]],
    ) -> Any:
        """Apply filters to a query."""
        if not filters:
            return query

        for column_name, value in filters.items():
            column = getattr(model, column_name, None)
            if column is None:
                continue

            if isinstance(value, dict):
                for op, val in value.items():
                    if op == "eq":
                        query = query.filter(column == val)
                    elif op == "ne":
                        query = query.filter(column != val)
                    elif op == "like":
                        query = query.filter(column.ilike(f"%{val}%"))
                    elif op == "in":
                        query = query.filter(column.in_(val))
                    elif op == "is_null":
                        if val:
                            query = query.filter(column.is_(None))
                        else:
                            query = query.filter(column.isnot(None))
            else:
                query = query.filter(column == value)

        return query

    def _apply_cleaning_filters(
        self,
        query: Any,
        model: Any,
        filters: CleaningFilters,
    ) -> Any:
        """Apply CleaningFilters to a query."""
        if filters.status:
            if hasattr(model, "status"):
                query = query.filter(model.status == filters.status)

        if filters.created_after:
            if hasattr(model, "created_at"):
                query = query.filter(model.created_at >= filters.created_after)

        if filters.created_before:
            if hasattr(model, "created_at"):
                query = query.filter(model.created_at <= filters.created_before)

        if filters.has_field:
            column = getattr(model, filters.has_field, None)
            if column:
                query = query.filter(column.isnot(None))

        if filters.missing_field:
            column = getattr(model, filters.missing_field, None)
            if column:
                query = query.filter(column.is_(None))

        if filters.field_equals:
            for field, value in filters.field_equals.items():
                column = getattr(model, field, None)
                if column:
                    query = query.filter(column == value)

        if filters.field_contains:
            for field, substring in filters.field_contains.items():
                column = getattr(model, field, None)
                if column:
                    query = query.filter(column.ilike(f"%{substring}%"))

        if filters.record_ids:
            query = query.filter(model.id.in_(filters.record_ids))

        return query

    def _serialize_value(self, value: Any) -> Any:
        """Serialize a value for comparison."""
        if isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, date):
            return value.isoformat()
        elif isinstance(value, Decimal):
            return str(value)
        elif isinstance(value, Enum):
            return value.value
        return value
