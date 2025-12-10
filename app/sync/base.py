from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, List, Callable, Dict, TypeVar, Coroutine
from functools import wraps
import json
import structlog
from sqlalchemy.orm import Session
from app.models.sync_log import SyncLog, SyncStatus, SyncSource
from app.models.sync_cursor import SyncCursor, FailedSyncRecord
from app.config import settings

logger = structlog.get_logger()

T = TypeVar('T')


def utcnow() -> datetime:
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and blocking requests."""
    pass


class CircuitBreaker:
    """Simple circuit breaker implementation for external API calls."""

    def __init__(self, name: str, fail_max: int = 5, reset_timeout: int = 60):
        self.name = name
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half-open

    def can_execute(self) -> bool:
        """Check if the circuit allows execution."""
        if self.state == "closed":
            return True
        if self.state == "open":
            # Check if reset timeout has passed
            if self.last_failure_time and utcnow() - self.last_failure_time > timedelta(seconds=self.reset_timeout):
                self.state = "half-open"
                logger.info("circuit_breaker_half_open", name=self.name)
                return True
            return False
        # half-open - allow one request
        return True

    def record_success(self):
        """Record a successful execution."""
        if self.state == "half-open":
            logger.info("circuit_breaker_closed", name=self.name)
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self, error: Optional[Exception] = None):
        """Record a failed execution."""
        self.failure_count += 1
        self.last_failure_time = utcnow()
        if self.failure_count >= self.fail_max:
            self.state = "open"
            logger.warning(
                "circuit_breaker_opened",
                name=self.name,
                failures=self.failure_count,
                error=str(error) if error else None,
            )

    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        return self.state == "open" and not self.can_execute()

    async def execute(self, coro: Coroutine[Any, Any, T]) -> T:
        """Execute a coroutine with circuit breaker protection.

        Args:
            coro: The async coroutine to execute

        Returns:
            The result of the coroutine

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Re-raises any exception from the coroutine
        """
        if not self.can_execute():
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is open. "
                f"Will retry after {self.reset_timeout}s."
            )

        try:
            result = await coro
            self.record_success()
            return result
        except Exception as e:
            self.record_failure(e)
            raise


# Global circuit breakers per service
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create a circuit breaker for a service."""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            name=name,
            fail_max=settings.circuit_breaker_fail_max,
            reset_timeout=settings.circuit_breaker_reset_timeout,
        )
    return _circuit_breakers[name]


class BaseSyncClient(ABC):
    """Base class for all sync integrations."""

    source: SyncSource

    def __init__(self, db: Session):
        self.db = db
        self.current_sync_log: Optional[SyncLog] = None
        self._circuit_breaker: Optional[CircuitBreaker] = None

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Get circuit breaker for this sync client."""
        if self._circuit_breaker is None:
            self._circuit_breaker = get_circuit_breaker(self.source.value)
        return self._circuit_breaker

    def get_cursor(self, entity_type: str) -> Optional[SyncCursor]:
        """Get the sync cursor for an entity type."""
        return self.db.query(SyncCursor).filter(
            SyncCursor.source == self.source,
            SyncCursor.entity_type == entity_type,
        ).first()

    def get_or_create_cursor(self, entity_type: str) -> SyncCursor:
        """Get or create a sync cursor for an entity type."""
        cursor = self.get_cursor(entity_type)
        if not cursor:
            cursor = SyncCursor(
                source=self.source,
                entity_type=entity_type,
            )
            self.db.add(cursor)
            self.db.commit()
        return cursor

    def update_cursor(
        self,
        entity_type: str,
        timestamp: Optional[datetime] = None,
        modified_at: Optional[str] = None,
        last_id: Optional[str] = None,
        cursor_value: Optional[str] = None,
        records_count: int = 0,
    ):
        """Update the sync cursor after successful sync."""
        cursor = self.get_or_create_cursor(entity_type)
        cursor.update_cursor(
            timestamp=timestamp,
            modified_at=modified_at,
            last_id=last_id,
            cursor_value=cursor_value,
            records_count=records_count,
        )
        self.db.commit()

    def reset_cursor(self, entity_type: str):
        """Reset cursor for full sync."""
        cursor = self.get_cursor(entity_type)
        if cursor:
            cursor.reset()
            self.db.commit()

    def add_to_dlq(
        self,
        entity_type: str,
        external_id: str,
        payload: Any,
        error_message: str,
        error_type: Optional[str] = None,
        commit: bool = True,
    ):
        """Add a failed record to the dead letter queue.

        Args:
            entity_type: Type of entity that failed
            external_id: External ID of the failed record
            payload: The raw data that failed to process
            error_message: Error message describing the failure
            error_type: Optional error classification
            commit: Whether to commit immediately (default True)
        """
        failed_record = FailedSyncRecord(
            source=self.source,
            entity_type=entity_type,
            external_id=external_id,
            payload=json.dumps(payload) if not isinstance(payload, str) else payload,
            error_message=error_message[:2000] if error_message else "Unknown error",  # Truncate long errors
            error_type=error_type,
            next_retry_at=utcnow() + timedelta(minutes=5),  # Retry in 5 minutes
        )
        self.db.add(failed_record)

        if commit:
            try:
                self.db.commit()
            except Exception as e:
                logger.error("failed_to_commit_dlq_record", error=str(e))
                self.db.rollback()

        logger.warning(
            "record_added_to_dlq",
            source=self.source.value,
            entity_type=entity_type,
            external_id=external_id,
            error=error_message[:200] if error_message else None,
        )

    def get_pending_dlq_records(self, entity_type: Optional[str] = None, limit: int = 100) -> List[FailedSyncRecord]:
        """Get pending DLQ records ready for retry."""
        query = self.db.query(FailedSyncRecord).filter(
            FailedSyncRecord.source == self.source,
            FailedSyncRecord.is_resolved == False,
            FailedSyncRecord.retry_count < FailedSyncRecord.max_retries,
            FailedSyncRecord.next_retry_at <= utcnow(),
        )
        if entity_type:
            query = query.filter(FailedSyncRecord.entity_type == entity_type)
        return query.order_by(FailedSyncRecord.created_at).limit(limit).all()

    def schedule_dlq_retry(self, record: FailedSyncRecord, backoff_minutes: int = 5):
        """Schedule a DLQ record for retry with exponential backoff.

        Args:
            record: The failed record to schedule
            backoff_minutes: Base backoff time in minutes (will be multiplied by retry_count)
        """
        record.mark_retry()
        # Exponential backoff: 5, 10, 20, 40 minutes...
        delay = backoff_minutes * (2 ** (record.retry_count - 1))
        record.next_retry_at = utcnow() + timedelta(minutes=min(delay, 60))  # Cap at 60 min
        self.db.commit()

    def start_sync(self, entity_type: str, sync_type: str = "incremental") -> SyncLog:
        """Start a new sync operation and create a log entry."""
        self.current_sync_log = SyncLog(
            source=self.source,
            entity_type=entity_type,
            sync_type=sync_type,
            status=SyncStatus.STARTED,
            started_at=utcnow(),
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

    def fail_sync(self, error_message: str, error_details: Optional[str] = None) -> None:
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

    def flush_batch(self):
        """Commit current batch to reduce transaction size."""
        self.db.commit()

    def process_in_batches(self, items: List[Any], processor: Callable[[Any], Optional[str]], batch_size: int = 500) -> None:
        """Process items in batches with periodic commits.

        Args:
            items: List of items to process
            processor: Function to call for each item, should return 'created', 'updated', or 'failed'
            batch_size: Number of items to process before committing
        """
        for i, item in enumerate(items, 1):
            try:
                result = processor(item)
                if result == "created":
                    self.increment_created()
                elif result == "updated":
                    self.increment_updated()
                elif result == "failed":
                    self.increment_failed()
            except Exception as e:
                logger.warning("batch_item_failed", error=str(e), item_index=i)
                self.increment_failed()

            # Commit every batch_size items
            if i % batch_size == 0:
                self.db.commit()
                logger.debug("batch_committed", processed=i, total=len(items))

        # Final commit for remaining items
        self.db.commit()

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if the API connection is working."""
        pass

    @abstractmethod
    async def sync_all(self, full_sync: bool = False):
        """Sync all entity types."""
        pass
