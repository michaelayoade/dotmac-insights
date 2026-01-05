"""Service layer for sync management in settings."""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.sync_cursor import SyncCursor, FailedSyncRecord
from app.models.sync_log import SyncLog, SyncStatus, SyncSource
from app.models.sync_schedule import SyncSchedule
from app.utils.datetime_utils import utc_now


class SettingsSyncService:
    """Service for sync stats, logs, and schedule management."""

    def __init__(self, db: Session):
        self.db = db

    def get_entity_stats(self, source: SyncSource, entity_type: str) -> dict:
        """Get stats for a specific entity type."""
        cursor = self.get_cursor(source, entity_type)

        last_log = (
            self.db.query(SyncLog)
            .filter(
                SyncLog.source == source,
                SyncLog.entity_type == entity_type,
            )
            .order_by(desc(SyncLog.started_at))
            .first()
        )

        yesterday = utc_now() - timedelta(hours=24)
        recent_failures = (
            self.db.query(func.count(SyncLog.id))
            .filter(
                SyncLog.source == source,
                SyncLog.entity_type == entity_type,
                SyncLog.status == SyncStatus.FAILED,
                SyncLog.started_at >= yesterday,
            )
            .scalar()
            or 0
        )

        failed_records = (
            self.db.query(func.count(FailedSyncRecord.id))
            .filter(
                FailedSyncRecord.source == source,
                FailedSyncRecord.entity_type == entity_type,
                FailedSyncRecord.is_resolved == False,
            )
            .scalar()
            or 0
        )

        return {
            "cursor": cursor,
            "last_log": last_log,
            "recent_failures": recent_failures,
            "failed_records": failed_records,
            "last_sync_at": cursor.last_sync_at if cursor else None,
            "records_synced": cursor.records_synced if cursor else 0,
        }

    def get_overall_stats(self) -> dict:
        """Get overall sync statistics."""
        yesterday = utc_now() - timedelta(hours=24)

        total_syncs = (
            self.db.query(func.count(SyncLog.id))
            .filter(SyncLog.started_at >= yesterday)
            .scalar()
            or 0
        )
        successful_syncs = (
            self.db.query(func.count(SyncLog.id))
            .filter(
                SyncLog.started_at >= yesterday,
                SyncLog.status == SyncStatus.COMPLETED,
            )
            .scalar()
            or 0
        )
        failed_syncs = (
            self.db.query(func.count(SyncLog.id))
            .filter(
                SyncLog.started_at >= yesterday,
                SyncLog.status == SyncStatus.FAILED,
            )
            .scalar()
            or 0
        )
        records_created = (
            self.db.query(func.sum(SyncLog.records_created))
            .filter(SyncLog.started_at >= yesterday)
            .scalar()
            or 0
        )
        records_updated = (
            self.db.query(func.sum(SyncLog.records_updated))
            .filter(SyncLog.started_at >= yesterday)
            .scalar()
            or 0
        )
        pending_failures = (
            self.db.query(func.count(FailedSyncRecord.id))
            .filter(FailedSyncRecord.is_resolved == False)
            .scalar()
            or 0
        )

        return {
            "total_syncs": total_syncs,
            "successful_syncs": successful_syncs,
            "failed_syncs": failed_syncs,
            "records_created": records_created,
            "records_updated": records_updated,
            "pending_failures": pending_failures,
            "success_rate": round((successful_syncs / total_syncs * 100) if total_syncs > 0 else 0, 1),
        }

    def list_recent_logs(self, limit: int = 10) -> list[SyncLog]:
        return (
            self.db.query(SyncLog)
            .order_by(desc(SyncLog.started_at))
            .limit(limit)
            .all()
        )

    def get_cursor(self, source: SyncSource, entity_type: str) -> Optional[SyncCursor]:
        return (
            self.db.query(SyncCursor)
            .filter(
                SyncCursor.source == source,
                SyncCursor.entity_type == entity_type,
            )
            .first()
        )

    def list_logs(
        self,
        source: SyncSource,
        entity_type: str,
        page: int,
        per_page: int,
    ) -> tuple[list[SyncLog], int]:
        logs_query = (
            self.db.query(SyncLog)
            .filter(
                SyncLog.source == source,
                SyncLog.entity_type == entity_type,
            )
            .order_by(desc(SyncLog.started_at))
        )
        total = logs_query.count()
        offset = (page - 1) * per_page
        logs = logs_query.offset(offset).limit(per_page).all()
        return logs, total

    def list_failed_records(
        self,
        source: SyncSource,
        entity_type: str,
        limit: int = 10,
    ) -> list[FailedSyncRecord]:
        return (
            self.db.query(FailedSyncRecord)
            .filter(
                FailedSyncRecord.source == source,
                FailedSyncRecord.entity_type == entity_type,
                FailedSyncRecord.is_resolved == False,
            )
            .order_by(desc(FailedSyncRecord.created_at))
            .limit(limit)
            .all()
        )

    def reset_cursor(self, source: SyncSource, entity_type: str) -> Optional[SyncCursor]:
        cursor = self.get_cursor(source, entity_type)
        if cursor:
            cursor.reset()
            self.db.commit()
        return cursor

    def get_failed_record(self, record_id: int) -> Optional[FailedSyncRecord]:
        return self.db.query(FailedSyncRecord).filter(FailedSyncRecord.id == record_id).first()

    def retry_failed_record(self, record: FailedSyncRecord) -> None:
        record.mark_retry()
        self.db.commit()

    def resolve_failed_record(self, record: FailedSyncRecord, notes: str) -> None:
        record.mark_resolved(notes)
        self.db.commit()

    def list_schedules(self) -> list[SyncSchedule]:
        return (
            self.db.query(SyncSchedule)
            .order_by(SyncSchedule.is_system.desc(), SyncSchedule.name)
            .all()
        )

    def toggle_schedule(self, schedule_id: int) -> Optional[SyncSchedule]:
        schedule = self.db.query(SyncSchedule).filter(SyncSchedule.id == schedule_id).first()
        if not schedule:
            return None
        schedule.is_enabled = not schedule.is_enabled
        self.db.commit()
        return schedule
