"""Celery tasks for network monitoring.

Tasks for SNMP polling, metrics aggregation, and cleanup.

Beat Schedule (in worker.py):
- poll_devices: Every 5 minutes
- aggregate_metrics: Hourly at :05
- cleanup_metrics: Daily at 3 AM
"""
import asyncio
from typing import Optional
import structlog
import redis

from celery import shared_task

from app.config import settings
from app.database import async_session_maker

logger = structlog.get_logger()

# Redis client for distributed locks
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client for locks."""
    global _redis_client
    if _redis_client is None:
        redis_url = settings.redis_url or "redis://localhost:6379/0"
        _redis_client = redis.from_url(redis_url)
    return _redis_client


class TaskLock:
    """Distributed lock using Redis to prevent concurrent task execution."""

    def __init__(self, lock_name: str, timeout: int = 600):
        self.lock_name = f"celery_lock:{lock_name}"
        self.timeout = timeout
        self.redis = get_redis_client()
        self._lock = None

    def __enter__(self):
        self._lock = self.redis.lock(self.lock_name, timeout=self.timeout)
        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            raise TaskLockError(f"Could not acquire lock: {self.lock_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._lock:
            try:
                self._lock.release()
            except redis.exceptions.LockError:
                # Lock may have expired
                pass


class TaskLockError(Exception):
    """Raised when a task lock cannot be acquired."""

    pass


def run_async(coro):
    """Run async coroutine in sync context for Celery tasks."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(name="monitoring.poll_devices")
def poll_devices() -> dict:
    """Poll all enabled devices via SNMP.

    Collects CPU, memory, uptime, and interface traffic metrics.
    Runs every 5 minutes by default.

    Returns:
        Dict with polling statistics
    """
    task_name = "monitoring.poll_devices"
    logger.info("task_started", task=task_name)

    try:
        with TaskLock(task_name, timeout=300):  # 5 minute timeout
            result = run_async(_poll_devices())
            logger.info(
                "task_completed",
                task=task_name,
                total=result.total_routers,
                successful=result.successful,
                failed=result.failed,
            )
            return {
                "status": "success",
                "total_routers": result.total_routers,
                "successful": result.successful,
                "failed": result.failed,
                "duration_seconds": result.duration_seconds,
            }
    except TaskLockError:
        logger.warning("task_skipped", task=task_name, reason="lock_not_acquired")
        return {"status": "skipped", "reason": "lock_not_acquired"}
    except Exception as exc:
        logger.exception("task_failed", task=task_name, error=str(exc))
        return {"status": "error", "error": str(exc)}


async def _poll_devices():
    """Async implementation of device polling."""
    from app.services.network.snmp_poller import SNMPPollerService

    async with async_session_maker() as db:
        poller = SNMPPollerService(db)
        result = await poller.poll_all_devices()
        await db.commit()
        return result


@shared_task(name="monitoring.aggregate_metrics")
def aggregate_metrics() -> dict:
    """Aggregate raw metrics into hourly rollups.

    Creates InterfaceMetricRollup records with avg, max, min, p95 rates.
    Runs hourly at :05.

    Returns:
        Dict with aggregation statistics
    """
    task_name = "monitoring.aggregate_metrics"
    logger.info("task_started", task=task_name)

    try:
        with TaskLock(task_name, timeout=300):
            result = run_async(_aggregate_metrics())
            logger.info(
                "task_completed",
                task=task_name,
                records_created=result.records_created,
            )
            return {
                "status": "success",
                "records_created": result.records_created,
                "interfaces_processed": result.interfaces_processed,
                "duration_seconds": result.duration_seconds,
            }
    except TaskLockError:
        logger.warning("task_skipped", task=task_name, reason="lock_not_acquired")
        return {"status": "skipped", "reason": "lock_not_acquired"}
    except Exception as exc:
        logger.exception("task_failed", task=task_name, error=str(exc))
        return {"status": "error", "error": str(exc)}


async def _aggregate_metrics():
    """Async implementation of metrics aggregation."""
    from app.services.network.snmp_poller import SNMPPollerService

    async with async_session_maker() as db:
        poller = SNMPPollerService(db)
        result = await poller.aggregate_hourly()
        await db.commit()
        return result


@shared_task(name="monitoring.cleanup_metrics")
def cleanup_metrics() -> dict:
    """Delete old raw metrics based on retention policy.

    Retention periods:
    - Raw metrics (5-min): 7 days
    - Hourly rollups: 90 days
    - Daily rollups: 2 years

    Runs daily at 3 AM.

    Returns:
        Dict with cleanup statistics
    """
    task_name = "monitoring.cleanup_metrics"
    logger.info("task_started", task=task_name)

    try:
        with TaskLock(task_name, timeout=600):
            result = run_async(_cleanup_metrics())
            logger.info(
                "task_completed",
                task=task_name,
                deleted_device_metrics=result.deleted_device_metrics,
                deleted_interface_metrics=result.deleted_interface_metrics,
            )
            return {
                "status": "success",
                "deleted_device_metrics": result.deleted_device_metrics,
                "deleted_interface_metrics": result.deleted_interface_metrics,
                "duration_seconds": result.duration_seconds,
            }
    except TaskLockError:
        logger.warning("task_skipped", task=task_name, reason="lock_not_acquired")
        return {"status": "skipped", "reason": "lock_not_acquired"}
    except Exception as exc:
        logger.exception("task_failed", task=task_name, error=str(exc))
        return {"status": "error", "error": str(exc)}


async def _cleanup_metrics():
    """Async implementation of metrics cleanup."""
    from app.services.network.snmp_poller import SNMPPollerService

    async with async_session_maker() as db:
        poller = SNMPPollerService(db)
        result = await poller.cleanup_old_metrics()
        await db.commit()
        return result


@shared_task(name="monitoring.poll_single_device")
def poll_single_device(router_id: int) -> dict:
    """Poll a single device on-demand.

    Args:
        router_id: ID of the router to poll

    Returns:
        Dict with polling result
    """
    task_name = "monitoring.poll_single_device"
    logger.info("task_started", task=task_name, router_id=router_id)

    try:
        result = run_async(_poll_single_device(router_id))
        if result and result.success:
            logger.info(
                "task_completed",
                task=task_name,
                router_id=router_id,
                duration_ms=result.poll_duration_ms,
            )
            return {
                "status": "success",
                "router_id": router_id,
                "poll_duration_ms": result.poll_duration_ms,
                "interfaces_count": len(result.interfaces) if result.interfaces else 0,
            }
        else:
            error = result.error if result else "No result returned"
            logger.warning(
                "task_failed",
                task=task_name,
                router_id=router_id,
                error=error,
            )
            return {
                "status": "error",
                "router_id": router_id,
                "error": error,
            }
    except Exception as exc:
        logger.exception("task_failed", task=task_name, router_id=router_id, error=str(exc))
        return {"status": "error", "router_id": router_id, "error": str(exc)}


async def _poll_single_device(router_id: int):
    """Async implementation of single device polling."""
    from app.services.network.snmp_poller import SNMPPollerService

    async with async_session_maker() as db:
        poller = SNMPPollerService(db)
        result = await poller.poll_device(router_id)
        await db.commit()
        return result


@shared_task(name="monitoring.get_poll_statistics")
def get_poll_statistics() -> dict:
    """Get polling statistics for monitoring dashboard.

    Returns:
        Dict with polling statistics
    """
    task_name = "monitoring.get_poll_statistics"

    try:
        stats = run_async(_get_poll_statistics())
        return {
            "status": "success",
            "total_configs": stats.total_configs,
            "enabled_configs": stats.enabled_configs,
            "successful_polls_24h": stats.successful_polls_24h,
            "failed_polls_24h": stats.failed_polls_24h,
            "routers_with_errors": stats.routers_with_errors,
        }
    except Exception as exc:
        logger.exception("task_failed", task=task_name, error=str(exc))
        return {"status": "error", "error": str(exc)}


async def _get_poll_statistics():
    """Async implementation of getting poll statistics."""
    from app.services.network.snmp_poller import SNMPPollerService

    async with async_session_maker() as db:
        poller = SNMPPollerService(db)
        return await poller.get_poll_statistics()
