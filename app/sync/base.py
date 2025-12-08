from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict, Any, List
import structlog
from sqlalchemy.orm import Session
from app.models.sync_log import SyncLog, SyncStatus, SyncSource

logger = structlog.get_logger()


class BaseSyncClient(ABC):
    """Base class for all sync integrations."""

    source: SyncSource = None

    def __init__(self, db: Session):
        self.db = db
        self.current_sync_log: Optional[SyncLog] = None

    def start_sync(self, entity_type: str, sync_type: str = "incremental") -> SyncLog:
        """Start a new sync operation and create a log entry."""
        self.current_sync_log = SyncLog(
            source=self.source,
            entity_type=entity_type,
            sync_type=sync_type,
            status=SyncStatus.STARTED,
            started_at=datetime.utcnow(),
        )
        self.db.add(self.current_sync_log)
        self.db.commit()

        logger.info(
            "sync_started",
            source=self.source.value,
            entity_type=entity_type,
            sync_type=sync_type,
        )
        return self.current_sync_log

    def complete_sync(self, status: SyncStatus = SyncStatus.COMPLETED):
        """Mark the current sync as complete."""
        if self.current_sync_log:
            self.current_sync_log.complete(status)
            self.db.commit()

            logger.info(
                "sync_completed",
                source=self.source.value,
                entity_type=self.current_sync_log.entity_type,
                status=status.value,
                records_created=self.current_sync_log.records_created,
                records_updated=self.current_sync_log.records_updated,
                duration_seconds=self.current_sync_log.duration_seconds,
            )

    def fail_sync(self, error_message: str, error_details: str = None):
        """Mark the current sync as failed."""
        if self.current_sync_log:
            self.current_sync_log.fail(error_message, error_details)
            self.db.commit()

            logger.error(
                "sync_failed",
                source=self.source.value,
                entity_type=self.current_sync_log.entity_type,
                error=error_message,
            )

    def increment_created(self, count: int = 1):
        if self.current_sync_log:
            self.current_sync_log.records_created += count

    def increment_updated(self, count: int = 1):
        if self.current_sync_log:
            self.current_sync_log.records_updated += count

    def increment_fetched(self, count: int = 1):
        if self.current_sync_log:
            self.current_sync_log.records_fetched += count

    def increment_failed(self, count: int = 1):
        if self.current_sync_log:
            self.current_sync_log.records_failed += count

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if the API connection is working."""
        pass

    @abstractmethod
    async def sync_all(self, full_sync: bool = False):
        """Sync all entity types."""
        pass
