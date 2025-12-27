"""Celery tasks for data migration."""
import structlog
from typing import Optional
import redis

from app.worker import celery_app
from app.config import settings
from app.database import SessionLocal
from app.services.migration.service import MigrationService
from app.models.migration import MigrationJob, MigrationStatus

logger = structlog.get_logger()

# Redis client for distributed locks and progress updates
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        redis_url = settings.redis_url or "redis://localhost:6379/0"
        _redis_client = redis.from_url(redis_url)
    return _redis_client


class MigrationLock:
    """Distributed lock for migration jobs."""

    def __init__(self, job_id: int, timeout: int = 3600):
        self.lock_name = f"migration_lock:{job_id}"
        self.timeout = timeout
        self.redis = get_redis_client()
        self._lock = None

    def __enter__(self):
        self._lock = self.redis.lock(self.lock_name, timeout=self.timeout)
        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            raise MigrationLockError(f"Migration job {self.lock_name} is already running")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._lock:
            try:
                self._lock.release()
            except redis.exceptions.LockError:
                pass


class MigrationLockError(Exception):
    """Raised when a migration lock cannot be acquired."""
    pass


def publish_progress(job_id: int, progress: dict) -> None:
    """Publish migration progress to Redis for real-time updates."""
    try:
        redis_client = get_redis_client()
        channel = f"migration:progress:{job_id}"
        redis_client.publish(channel, str(progress))
    except Exception as e:
        logger.warning("failed_to_publish_progress", job_id=job_id, error=str(e))


@celery_app.task(bind=True, max_retries=0, time_limit=3600, soft_time_limit=3500)
def execute_migration_task(self, job_id: int):
    """Execute a migration job in the background.

    Args:
        job_id: ID of the migration job to execute
    """
    logger.info("migration_task_started", job_id=job_id, task_id=self.request.id)

    db = SessionLocal()
    try:
        with MigrationLock(job_id):
            service = MigrationService(db)

            # Get job
            job = service.get_job(job_id)
            if not job:
                logger.error("migration_job_not_found", job_id=job_id)
                return {"error": "Job not found"}

            if job.status not in (MigrationStatus.VALIDATED, MigrationStatus.MAPPED):
                logger.error("migration_invalid_status", job_id=job_id, status=job.status.value)
                return {"error": f"Cannot execute in status {job.status.value}"}

            # Execute migration
            service.execute(job_id)

            # Get final progress
            progress = service.get_progress(job_id)
            logger.info("migration_task_completed", job_id=job_id, **progress)

            return progress

    except MigrationLockError as e:
        logger.warning("migration_lock_failed", job_id=job_id, error=str(e))
        return {"error": str(e)}

    except Exception as e:
        logger.exception("migration_task_failed", job_id=job_id, error=str(e))

        # Try to mark job as failed
        try:
            job = db.query(MigrationJob).filter(MigrationJob.id == job_id).first()
            if job:
                job.fail(str(e))
                db.commit()
        except Exception:
            pass

        return {"error": str(e)}

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=0)
def rollback_migration_task(self, job_id: int, user_id: Optional[int] = None):
    """Rollback a completed migration in the background.

    Args:
        job_id: ID of the migration job to rollback
        user_id: ID of the user initiating the rollback
    """
    logger.info("rollback_task_started", job_id=job_id, task_id=self.request.id)

    db = SessionLocal()
    try:
        with MigrationLock(job_id):
            service = MigrationService(db, user_id=user_id)
            result = service.rollback(job_id)
            logger.info("rollback_task_completed", job_id=job_id, **result)
            return result

    except MigrationLockError as e:
        logger.warning("rollback_lock_failed", job_id=job_id, error=str(e))
        return {"error": str(e)}

    except Exception as e:
        logger.exception("rollback_task_failed", job_id=job_id, error=str(e))
        return {"error": str(e)}

    finally:
        db.close()


@celery_app.task
def cleanup_old_migrations(days: int = 30):
    """Cleanup migration jobs and files older than specified days.

    Args:
        days: Number of days to keep migration data
    """
    import os
    from datetime import timedelta
    from app.utils.datetime_utils import utc_now

    logger.info("cleanup_migrations_started", days=days)

    db = SessionLocal()
    try:
        cutoff = utc_now() - timedelta(days=days)

        # Find old completed/failed/cancelled jobs
        old_jobs = db.query(MigrationJob).filter(
            MigrationJob.created_at < cutoff,
            MigrationJob.status.in_([
                MigrationStatus.COMPLETED,
                MigrationStatus.FAILED,
                MigrationStatus.CANCELLED,
                MigrationStatus.ROLLED_BACK,
            ])
        ).all()

        deleted_count = 0
        for job in old_jobs:
            # Delete source file if exists
            if job.source_file_path and os.path.exists(job.source_file_path):
                try:
                    os.remove(job.source_file_path)
                except Exception as e:
                    logger.warning("failed_to_delete_file", path=job.source_file_path, error=str(e))

            db.delete(job)
            deleted_count += 1

        db.commit()
        logger.info("cleanup_migrations_completed", deleted_count=deleted_count)

        return {"deleted": deleted_count}

    except Exception as e:
        logger.exception("cleanup_migrations_failed", error=str(e))
        db.rollback()
        return {"error": str(e)}

    finally:
        db.close()
