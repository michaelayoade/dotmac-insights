"""Migration data validator.

Validates migration data against entity schemas and business rules.
"""
from __future__ import annotations

import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.migration.registry import (
    get_entity_config,
    get_entity_fields,
    get_required_fields,
    get_unique_fields,
    get_fk_fields,
    get_dependencies,
    FieldType,
    ENTITY_REGISTRY,
)


class ValidationSeverity(str, Enum):
    """Validation issue severity."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """A single validation issue."""
    severity: ValidationSeverity
    field: Optional[str]
    message: str
    row: Optional[int] = None
    value: Any = None


@dataclass
class ValidationResult:
    """Result of validation."""
    is_valid: bool
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    info: list[ValidationIssue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def add_error(self, field: Optional[str], message: str, row: Optional[int] = None, value: Any = None):
        self.errors.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            field=field,
            message=message,
            row=row,
            value=value
        ))
        self.is_valid = False

    def add_warning(self, field: Optional[str], message: str, row: Optional[int] = None, value: Any = None):
        self.warnings.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            field=field,
            message=message,
            row=row,
            value=value
        ))

    def add_info(self, field: Optional[str], message: str, row: Optional[int] = None, value: Any = None):
        self.info.append(ValidationIssue(
            severity=ValidationSeverity.INFO,
            field=field,
            message=message,
            row=row,
            value=value
        ))

    def merge(self, other: "ValidationResult"):
        """Merge another validation result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.info.extend(other.info)
        if not other.is_valid:
            self.is_valid = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_valid": self.is_valid,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "errors": [
                {
                    "severity": e.severity.value,
                    "field": e.field,
                    "message": e.message,
                    "row": e.row,
                    "value": str(e.value) if e.value is not None else None
                }
                for e in self.errors[:100]  # Limit to first 100 errors
            ],
            "warnings": [
                {
                    "severity": w.severity.value,
                    "field": w.field,
                    "message": w.message,
                    "row": w.row,
                    "value": str(w.value) if w.value is not None else None
                }
                for w in self.warnings[:100]
            ],
        }


class MigrationValidator:
    """Validates migration data."""

    EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    PHONE_REGEX = re.compile(r"^\+?[\d\s\-\(\)]{7,20}$")

    def __init__(self, db: Optional[Session] = None):
        """Initialize validator.

        Args:
            db: Optional database session for FK validation
        """
        self.db = db

    def validate_row(
        self,
        row: dict[str, Any],
        entity_type: str,
        row_num: int,
        field_mapping: dict[str, str]
    ) -> ValidationResult:
        """Validate a single row against entity schema.

        Args:
            row: Row data (after field mapping applied)
            entity_type: Entity type being imported
            row_num: Row number for error reporting
            field_mapping: Source -> target field mapping

        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True)
        config = get_entity_config(entity_type)

        if not config:
            result.add_error(None, f"Unknown entity type: {entity_type}", row_num)
            return result

        fields = config.get("fields", {})
        required_fields = config.get("required_fields", [])

        # Check required fields
        for req_field in required_fields:
            value = row.get(req_field)
            if value is None or (isinstance(value, str) and not value.strip()):
                result.add_error(req_field, f"Required field '{req_field}' is missing or empty", row_num)

        # Validate each field
        for field_name, value in row.items():
            if value is None:
                continue

            field_config = fields.get(field_name)
            if not field_config:
                # Unknown field, skip validation
                continue

            field_type = field_config.get("type")
            if field_type:
                field_result = self._validate_field_type(
                    field_name, value, field_type, field_config, row_num
                )
                result.merge(field_result)

        return result

    def _validate_field_type(
        self,
        field_name: str,
        value: Any,
        field_type: FieldType,
        field_config: dict,
        row_num: int
    ) -> ValidationResult:
        """Validate a field value against its type.

        Args:
            field_name: Field name
            value: Field value
            field_type: Expected field type
            field_config: Field configuration
            row_num: Row number

        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True)

        if field_type == FieldType.STRING:
            if not isinstance(value, str):
                value = str(value)
            max_length = field_config.get("max_length")
            if max_length and len(value) > max_length:
                result.add_error(
                    field_name,
                    f"Value exceeds max length ({len(value)} > {max_length})",
                    row_num,
                    value[:50]
                )

        elif field_type == FieldType.INTEGER:
            try:
                int(value)
            except (ValueError, TypeError):
                result.add_error(field_name, "Invalid integer value", row_num, value)

        elif field_type == FieldType.DECIMAL:
            try:
                Decimal(str(value))
            except (InvalidOperation, ValueError):
                result.add_error(field_name, "Invalid decimal value", row_num, value)

        elif field_type == FieldType.BOOLEAN:
            if not isinstance(value, bool):
                str_val = str(value).lower()
                if str_val not in ("true", "false", "1", "0", "yes", "no", "y", "n"):
                    result.add_error(field_name, "Invalid boolean value", row_num, value)

        elif field_type == FieldType.DATE:
            if not isinstance(value, (date, datetime)):
                # Try to parse string date
                if isinstance(value, str) and not self._is_valid_date(value):
                    result.add_error(field_name, "Invalid date format", row_num, value)

        elif field_type == FieldType.DATETIME:
            if not isinstance(value, datetime):
                if isinstance(value, str) and not self._is_valid_datetime(value):
                    result.add_error(field_name, "Invalid datetime format", row_num, value)

        elif field_type == FieldType.EMAIL:
            if isinstance(value, str) and not self.EMAIL_REGEX.match(value):
                result.add_warning(field_name, "Invalid email format", row_num, value)

        elif field_type == FieldType.PHONE:
            if isinstance(value, str) and not self.PHONE_REGEX.match(value):
                result.add_warning(field_name, "Unusual phone format", row_num, value)

        elif field_type == FieldType.ENUM:
            enum_values = field_config.get("enum_values", [])
            if enum_values:
                str_val = str(value).lower()
                if str_val not in [v.lower() for v in enum_values]:
                    result.add_error(
                        field_name,
                        f"Invalid enum value. Expected one of: {', '.join(enum_values)}",
                        row_num,
                        value
                    )

        return result

    def _is_valid_date(self, value: str) -> bool:
        """Check if string is a valid date."""
        formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]
        for fmt in formats:
            try:
                datetime.strptime(value, fmt)
                return True
            except ValueError:
                continue
        return False

    def _is_valid_datetime(self, value: str) -> bool:
        """Check if string is a valid datetime."""
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return True
        except ValueError:
            return self._is_valid_date(value)

    def validate_batch(
        self,
        rows: list[dict[str, Any]],
        entity_type: str,
        field_mapping: dict[str, str],
        start_row: int = 1
    ) -> ValidationResult:
        """Validate a batch of rows.

        Args:
            rows: List of row data
            entity_type: Entity type
            field_mapping: Source -> target field mapping
            start_row: Starting row number for error reporting

        Returns:
            ValidationResult with all issues
        """
        result = ValidationResult(is_valid=True)

        for i, row in enumerate(rows):
            row_num = start_row + i
            row_result = self.validate_row(row, entity_type, row_num, field_mapping)
            result.merge(row_result)

            # Stop after 100 errors to prevent performance issues
            if result.error_count >= 100:
                result.add_info(None, f"Validation stopped after {result.error_count} errors")
                break

        return result

    def detect_duplicates(
        self,
        rows: list[dict[str, Any]],
        dedup_fields: list[str],
        entity_type: str
    ) -> dict:
        """Detect duplicate records within the data.

        Args:
            rows: List of row data
            dedup_fields: Fields to check for duplicates
            entity_type: Entity type

        Returns:
            Dict with duplicate info
        """
        duplicates = {
            "in_file": [],  # Duplicates within the file
            "field_counts": {}  # Count of duplicates per field
        }

        for field in dedup_fields:
            seen = {}
            field_duplicates = []

            for i, row in enumerate(rows):
                value = row.get(field)
                if value is None or (isinstance(value, str) and not value.strip()):
                    continue

                # Normalize for comparison
                key = str(value).lower().strip()

                if key in seen:
                    field_duplicates.append({
                        "field": field,
                        "value": value,
                        "rows": [seen[key], i + 1]
                    })
                else:
                    seen[key] = i + 1

            if field_duplicates:
                duplicates["in_file"].extend(field_duplicates)
                duplicates["field_counts"][field] = len(field_duplicates)

        return duplicates

    def validate_relationships(
        self,
        rows: list[dict[str, Any]],
        entity_type: str,
        db: Session
    ) -> ValidationResult:
        """Validate foreign key relationships exist in the database.

        Args:
            rows: List of row data
            entity_type: Entity type
            db: Database session

        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True)
        fk_fields_config = get_fk_fields(entity_type)

        if not fk_fields_config:
            return result

        # Check each FK field
        for field_name, fk_config in fk_fields_config.items():
            fk_entity = fk_config.get("fk_entity")
            lookup_fields = fk_config.get("fk_lookup_fields", ["id"])
            is_required = fk_config.get("required", False)

            # Get target entity config to find table name
            target_config = get_entity_config(fk_entity)
            if not target_config:
                result.add_warning(
                    field_name,
                    f"Unknown FK target entity: {fk_entity}"
                )
                continue

            # Collect unique values that need to be looked up
            values_by_row: dict[int, Any] = {}
            for i, row in enumerate(rows):
                value = row.get(field_name)
                if value is not None and str(value).strip():
                    values_by_row[i + 1] = value

            if not values_by_row:
                continue

            unique_values = set(values_by_row.values())

            # Get table name from model
            table_name = self._get_table_name(fk_entity)
            if not table_name:
                result.add_warning(
                    field_name,
                    f"Cannot determine table for {fk_entity}"
                )
                continue

            # Query database to find existing values
            existing_values = self._find_existing_values(
                db, table_name, lookup_fields, unique_values
            )

            # Check which values don't exist
            missing_values = unique_values - existing_values
            if missing_values:
                # Find which rows have missing values
                for row_num, value in values_by_row.items():
                    if value in missing_values:
                        if is_required:
                            result.add_error(
                                field_name,
                                f"Referenced {fk_entity} not found: {value}",
                                row_num,
                                value
                            )
                        else:
                            result.add_warning(
                                field_name,
                                f"Referenced {fk_entity} not found: {value}",
                                row_num,
                                value
                            )

        return result

    def _get_table_name(self, entity_type: str) -> Optional[str]:
        """Get database table name for an entity type."""
        # Map entity types to table names
        table_map = {
            "contacts": "contacts",
            "customers": "customers",
            "employees": "employees",
            "invoices": "invoices",
            "payments": "payments",
            "suppliers": "suppliers",
            "purchase_invoices": "purchase_invoices",
            "accounts": "accounts",
            "projects": "projects",
            "tasks": "tasks",
            "tickets": "tickets",
            "leads": "leads",
            "opportunities": "opportunities",
            "departments": "departments",
            "designations": "designations",
            "items": "items",
            "warehouses": "warehouses",
            "expenses": "expenses",
            "bank_accounts": "bank_accounts",
            "bank_transactions": "bank_transactions",
            "journal_entries": "journal_entries",
            "cost_centers": "cost_centers",
            "fiscal_years": "fiscal_years",
            "fiscal_periods": "fiscal_periods",
            "modes_of_payment": "modes_of_payment",
            "supplier_groups": "supplier_groups",
            "credit_notes": "credit_notes",
            "supplier_payments": "supplier_payments",
            "gl_entries": "gl_entries",
            "exchange_rates": "exchange_rates",
            "asset_categories": "asset_categories",
            "assets": "assets",
        }
        return table_map.get(entity_type)

    def _find_existing_values(
        self,
        db: Session,
        table_name: str,
        lookup_fields: list[str],
        values: set[Any]
    ) -> set[Any]:
        """Find which values exist in the target table.

        Args:
            db: Database session
            table_name: Target table name
            lookup_fields: Fields to search in
            values: Values to look for

        Returns:
            Set of values that exist
        """
        if not values:
            return set()

        existing = set()

        # Convert values to strings for comparison
        str_values = [str(v) for v in values]

        # Check each lookup field
        for lookup_field in lookup_fields:
            try:
                # Build safe query with parameterized values
                placeholders = ", ".join([f":val{i}" for i in range(len(str_values))])
                query = text(f"""
                    SELECT DISTINCT {lookup_field}::text
                    FROM {table_name}
                    WHERE {lookup_field}::text IN ({placeholders})
                """)

                # Create params dict
                params = {f"val{i}": v for i, v in enumerate(str_values)}
                result = db.execute(query, params)

                for row in result:
                    if row[0]:
                        existing.add(row[0])
                        # Also add numeric version if applicable
                        try:
                            existing.add(int(row[0]))
                        except (ValueError, TypeError):
                            pass

            except Exception:
                # Table or column might not exist, skip
                continue

        return existing

    def check_dependencies(
        self,
        entity_type: str,
        db: Session
    ) -> ValidationResult:
        """Check if dependency entities have data in the database.

        This warns if you're trying to migrate an entity that depends
        on another entity that has no data.

        Args:
            entity_type: Entity type to check
            db: Database session

        Returns:
            ValidationResult with warnings for missing dependencies
        """
        result = ValidationResult(is_valid=True)
        dependencies = get_dependencies(entity_type)

        for dep_entity in dependencies:
            table_name = self._get_table_name(dep_entity)
            if not table_name:
                continue

            try:
                count_result = db.execute(
                    text(f"SELECT COUNT(*) FROM {table_name}")
                )
                count = count_result.scalar() or 0

                if count == 0:
                    dep_config = get_entity_config(dep_entity)
                    dep_name = dep_config.get("display_name", dep_entity) if dep_config else dep_entity
                    result.add_warning(
                        None,
                        f"Dependency '{dep_name}' has no data. "
                        f"Consider migrating {dep_name} first."
                    )
            except Exception:
                # Table might not exist
                pass

        return result

    def validate_with_fk(
        self,
        rows: list[dict[str, Any]],
        entity_type: str,
        field_mapping: dict[str, str],
        db: Session,
        start_row: int = 1
    ) -> ValidationResult:
        """Full validation including FK checks.

        Args:
            rows: List of row data (after field mapping)
            entity_type: Entity type
            field_mapping: Source -> target field mapping
            db: Database session
            start_row: Starting row number

        Returns:
            ValidationResult with all issues
        """
        # Run basic validation
        result = self.validate_batch(rows, entity_type, field_mapping, start_row)

        # Check dependencies
        dep_result = self.check_dependencies(entity_type, db)
        result.merge(dep_result)

        # Validate foreign keys
        fk_result = self.validate_relationships(rows, entity_type, db)
        result.merge(fk_result)

        return result
