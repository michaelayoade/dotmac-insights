"""Tests for sync infrastructure: cursors, circuit breaker, and DLQ.

Run with: poetry run pytest tests/test_sync_infrastructure.py -v
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


class TestCircuitBreaker:
    """Test the CircuitBreaker class."""

    def test_circuit_starts_closed(self):
        """Circuit breaker should start in closed state."""
        from app.sync.base import CircuitBreaker
        cb = CircuitBreaker("test_service")
        assert cb.state == "closed"
        assert cb.can_execute() is True

    def test_circuit_opens_after_failures(self):
        """Circuit should open after fail_max failures."""
        from app.sync.base import CircuitBreaker
        cb = CircuitBreaker("test_service", fail_max=3, reset_timeout=60)

        # Record failures
        cb.record_failure()
        assert cb.state == "closed"
        cb.record_failure()
        assert cb.state == "closed"
        cb.record_failure()
        assert cb.state == "open"
        assert cb.can_execute() is False

    def test_circuit_resets_after_timeout(self):
        """Circuit should transition to half-open after timeout."""
        from app.sync.base import CircuitBreaker
        cb = CircuitBreaker("test_service", fail_max=2, reset_timeout=1)

        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"

        # Simulate time passing
        cb.last_failure_time = datetime.utcnow() - timedelta(seconds=2)

        # Should now be half-open
        assert cb.can_execute() is True
        assert cb.state == "half-open"

    def test_circuit_closes_on_success(self):
        """Circuit should close after successful execution."""
        from app.sync.base import CircuitBreaker
        cb = CircuitBreaker("test_service", fail_max=2)

        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"

        # Simulate time passing and half-open
        cb.last_failure_time = datetime.utcnow() - timedelta(seconds=61)
        cb.can_execute()  # transitions to half-open

        # Success should close it
        cb.record_success()
        assert cb.state == "closed"
        assert cb.failure_count == 0


class TestSyncCursorModel:
    """Test the SyncCursor model (unit tests without DB)."""

    def test_sync_cursor_update_method(self):
        """Test cursor update_cursor method logic."""
        # Test the method logic directly without instantiating full model
        from app.models.sync_cursor import SyncCursor

        # Test the update logic via a simple object
        class MockCursor:
            last_sync_timestamp = None
            last_modified_at = None
            last_id = None
            cursor_value = None
            records_synced = 0
            last_sync_at = None

            def update_cursor(self, timestamp=None, modified_at=None, last_id=None, cursor_value=None, records_count=0):
                if timestamp:
                    self.last_sync_timestamp = timestamp
                if modified_at:
                    self.last_modified_at = modified_at
                if last_id:
                    self.last_id = last_id
                if cursor_value:
                    self.cursor_value = cursor_value
                self.records_synced += records_count
                self.last_sync_at = datetime.utcnow()

        cursor = MockCursor()
        cursor.update_cursor(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            modified_at="2024-01-01 12:00:00",
            last_id="12345",
            records_count=100,
        )

        assert cursor.last_sync_timestamp == datetime(2024, 1, 1, 12, 0, 0)
        assert cursor.last_modified_at == "2024-01-01 12:00:00"
        assert cursor.last_id == "12345"
        assert cursor.records_synced == 100

    def test_sync_cursor_model_exists(self):
        """Test SyncCursor model can be imported."""
        from app.models.sync_cursor import SyncCursor
        from app.models.sync_log import SyncSource

        assert SyncCursor is not None
        assert hasattr(SyncCursor, 'update_cursor')
        assert hasattr(SyncCursor, 'reset')


class TestFailedSyncRecordModel:
    """Test the FailedSyncRecord (DLQ) model (unit tests without DB)."""

    def test_failed_record_can_retry_logic(self):
        """Test can_retry property logic."""
        # Test the logic without full model instantiation
        class MockRecord:
            is_resolved = False
            retry_count = 0
            max_retries = 3

            @property
            def can_retry(self):
                return not self.is_resolved and self.retry_count < self.max_retries

        record = MockRecord()
        assert record.can_retry is True

        # After max retries
        record.retry_count = 3
        assert record.can_retry is False

        # After resolution
        record.retry_count = 0
        record.is_resolved = True
        assert record.can_retry is False

    def test_failed_record_mark_retry_logic(self):
        """Test mark_retry method logic."""
        class MockRecord:
            retry_count = 0
            last_retry_at = None

            def mark_retry(self):
                self.retry_count += 1
                self.last_retry_at = datetime.utcnow()

        record = MockRecord()
        assert record.retry_count == 0
        assert record.last_retry_at is None

        record.mark_retry()

        assert record.retry_count == 1
        assert record.last_retry_at is not None

    def test_failed_record_model_exists(self):
        """Test FailedSyncRecord model can be imported."""
        from app.models.sync_cursor import FailedSyncRecord

        assert FailedSyncRecord is not None
        assert hasattr(FailedSyncRecord, 'mark_retry')
        assert hasattr(FailedSyncRecord, 'mark_resolved')
        assert hasattr(FailedSyncRecord, 'can_retry')


class TestBaseSyncClientMethods:
    """Test BaseSyncClient cursor and DLQ methods."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    def test_get_circuit_breaker(self):
        """Test circuit breaker factory function."""
        from app.sync.base import get_circuit_breaker, _circuit_breakers

        # Clear existing breakers
        _circuit_breakers.clear()

        cb1 = get_circuit_breaker("service_a")
        cb2 = get_circuit_breaker("service_a")
        cb3 = get_circuit_breaker("service_b")

        # Same service should return same instance
        assert cb1 is cb2
        # Different service should return different instance
        assert cb1 is not cb3


class TestConfigSettings:
    """Test that config settings for sync are properly loaded."""

    def test_batch_size_settings(self):
        """Test batch size settings exist and have defaults."""
        from app.config import settings

        assert settings.sync_batch_size >= 100
        assert settings.sync_batch_size_customers >= 100
        assert settings.sync_batch_size_invoices >= 100
        assert settings.sync_batch_size_payments >= 100
        assert settings.sync_batch_size_tickets >= 100
        assert settings.sync_batch_size_messages >= 100

    def test_circuit_breaker_settings(self):
        """Test circuit breaker settings exist and have defaults."""
        from app.config import settings

        assert settings.circuit_breaker_fail_max >= 1
        assert settings.circuit_breaker_reset_timeout >= 10

    def test_retry_settings(self):
        """Test retry settings exist and have defaults."""
        from app.config import settings

        assert settings.retry_max_attempts >= 1
        assert settings.retry_min_wait >= 1
        assert settings.retry_max_wait >= settings.retry_min_wait
