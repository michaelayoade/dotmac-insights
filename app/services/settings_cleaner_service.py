"""Service layer for data cleaner settings routes."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.cleaning_operation import CleaningOperation
from app.services.data_explorer import DataCleanerService


class SettingsCleanerService:
    """Coordinator for data cleaner actions that require persistence."""

    def __init__(self, db: Session, principal: Any):
        self.db = db
        self.principal = principal

    def execute_normalize(self, field: str):
        cleaner = DataCleanerService(self.db, self.principal)
        if field == "phones":
            result = cleaner.execute_normalize_phones()
        else:
            result = cleaner.execute_normalize_emails()
        self.db.commit()
        return result

    def execute_merge_duplicates(self, table: str, primary_id: int, duplicate_ids: list[int]):
        cleaner = DataCleanerService(self.db, self.principal)
        result = cleaner.execute_merge_duplicates(table, primary_id, duplicate_ids)
        self.db.commit()
        return result

    def execute_bulk_update(self, table: str, filters: dict, updates: dict):
        cleaner = DataCleanerService(self.db, self.principal)
        result = cleaner.execute_bulk_update(table, filters, updates)
        self.db.commit()
        return result

    def rollback_operation(self, operation_id: str):
        cleaner = DataCleanerService(self.db, self.principal)
        result = cleaner.rollback_operation(operation_id)
        self.db.commit()
        return result

    def list_operations(self, limit: int, offset: int):
        cleaner = DataCleanerService(self.db, self.principal)
        return cleaner.list_operations(limit=limit, offset=offset)

    def count_operations(self) -> int:
        return self.db.query(CleaningOperation).count()

    def get_operation(self, operation_id: str):
        return (
            self.db.query(CleaningOperation)
            .filter(CleaningOperation.operation_id == operation_id)
            .first()
        )
