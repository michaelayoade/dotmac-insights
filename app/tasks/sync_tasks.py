"""Celery tasks for data synchronization."""
import asyncio
from datetime import datetime
from typing import Optional
import structlog
import redis

from app.worker import celery_app
from app.config import settings
from app.database import SessionLocal
from app.cache import invalidate_analytics_cache
from app.sync.base import BaseSyncClient
from app.sync.splynx import SplynxSync
from app.sync.erpnext import ERPNextSync
from app.sync.chatwoot import ChatwootSync

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


def _invalidate_analytics_cache(task_name: str) -> None:
    """Invalidate analytics cache after sync completes."""
    try:
        run_async(invalidate_analytics_cache())
        logger.info("analytics_cache_invalidated", task=task_name)
    except Exception as exc:
        logger.warning("analytics_cache_invalidation_failed", task=task_name, error=str(exc))


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_splynx_customers(self, full_sync: bool = False):
    """Sync customers from Splynx.

    Args:
        full_sync: If True, sync all records. If False, only sync recently modified.
    """
    task_name = "sync_splynx_customers"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name):
            db = SessionLocal()
            try:
                sync_client = SplynxSync(db)
                run_async(sync_client.sync_customers_task(full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_splynx_invoices(self, full_sync: bool = False):
    """Sync invoices from Splynx."""
    task_name = "sync_splynx_invoices"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name):
            db = SessionLocal()
            try:
                sync_client = SplynxSync(db)
                run_async(sync_client.sync_invoices_task(full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_splynx_payments(self, full_sync: bool = False):
    """Sync payments from Splynx."""
    task_name = "sync_splynx_payments"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name):
            db = SessionLocal()
            try:
                sync_client = SplynxSync(db)
                run_async(sync_client.sync_payments_task(full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_splynx_services(self, full_sync: bool = False):
    """Sync services from Splynx."""
    task_name = "sync_splynx_services"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name):
            db = SessionLocal()
            try:
                sync_client = SplynxSync(db)
                run_async(sync_client.sync_services_task(full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_splynx_credit_notes(self, full_sync: bool = False):
    """Sync credit notes from Splynx."""
    task_name = "sync_splynx_credit_notes"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name):
            db = SessionLocal()
            try:
                sync_client = SplynxSync(db)
                run_async(sync_client.sync_credit_notes_task(full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_splynx_tickets(self, full_sync: bool = False):
    """Sync tickets from Splynx."""
    task_name = "sync_splynx_tickets"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name):
            db = SessionLocal()
            try:
                sync_client = SplynxSync(db)
                run_async(sync_client.sync_tickets_task(full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_splynx_tariffs(self, full_sync: bool = False):
    """Sync tariffs from Splynx."""
    task_name = "sync_splynx_tariffs"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name):
            db = SessionLocal()
            try:
                sync_client = SplynxSync(db)
                run_async(sync_client.sync_tariffs_task(full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_splynx_routers(self, full_sync: bool = False):
    """Sync routers from Splynx."""
    task_name = "sync_splynx_routers"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name):
            db = SessionLocal()
            try:
                sync_client = SplynxSync(db)
                run_async(sync_client.sync_routers_task(full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def sync_splynx_all(self, full_sync: bool = True):
    """Run full sync of all Splynx entities.

    This is the nightly full sync task that syncs:
    - Locations/POPs
    - Customers
    - Services
    - Invoices
    - Payments
    """
    task_name = "sync_splynx_all"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name, timeout=1800):  # 30 minute timeout for full sync
            db = SessionLocal()
            try:
                sync_client = SplynxSync(db)
                run_async(sync_client.sync_all(full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


@celery_app.task
def health_check():
    """Simple health check task to verify Celery is working."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# ERPNext Tasks
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_erpnext_all(self, full_sync: bool = False):
    """Sync all ERPNext entities."""
    task_name = "sync_erpnext_all"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name, timeout=1800):
            db = SessionLocal()
            try:
                sync_client = ERPNextSync(db)
                run_async(sync_client.sync_all(full_sync=full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_erpnext_customers(self, full_sync: bool = False):
    """Sync ERPNext customers."""
    task_name = "sync_erpnext_customers"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name):
            db = SessionLocal()
            try:
                sync_client = ERPNextSync(db)
                run_async(sync_client.sync_customers_task(full_sync=full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_erpnext_invoices(self, full_sync: bool = False):
    """Sync ERPNext invoices."""
    task_name = "sync_erpnext_invoices"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name):
            db = SessionLocal()
            try:
                sync_client = ERPNextSync(db)
                run_async(sync_client.sync_invoices_task(full_sync=full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_erpnext_payments(self, full_sync: bool = False):
    """Sync ERPNext payments."""
    task_name = "sync_erpnext_payments"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name):
            db = SessionLocal()
            try:
                sync_client = ERPNextSync(db)
                run_async(sync_client.sync_payments_task(full_sync=full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_erpnext_expenses(self, full_sync: bool = False):
    """Sync ERPNext expenses."""
    task_name = "sync_erpnext_expenses"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name):
            db = SessionLocal()
            try:
                sync_client = ERPNextSync(db)
                run_async(sync_client.sync_expenses_task(full_sync=full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_erpnext_hd_tickets(self, full_sync: bool = False):
    """Sync ERPNext HD Tickets (Help Desk)."""
    task_name = "sync_erpnext_hd_tickets"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name, timeout=900):  # 15 minute timeout for large ticket sync
            db = SessionLocal()
            try:
                sync_client = ERPNextSync(db)
                run_async(sync_client.sync_hd_tickets_task(full_sync=full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_erpnext_accounting(self, full_sync: bool = False):
    """Sync ERPNext accounting data (Chart of Accounts, GL Entries, Journal Entries, etc.)."""
    task_name = "sync_erpnext_accounting"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name, timeout=1800):  # 30 minute timeout for accounting data
            db = SessionLocal()
            try:
                sync_client = ERPNextSync(db)
                run_async(sync_client.sync_accounting_task(full_sync=full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_erpnext_extended_accounting(self, full_sync: bool = False):
    """Sync ERPNext extended accounting (Suppliers, Cost Centers, Fiscal Years, Bank Transactions)."""
    task_name = "sync_erpnext_extended_accounting"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name, timeout=1800):
            db = SessionLocal()
            try:
                sync_client = ERPNextSync(db)
                run_async(sync_client.sync_extended_accounting_task(full_sync=full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_erpnext_sales(self, full_sync: bool = False):
    """Sync ERPNext sales data (Customer Groups, Territories, Items, Leads, Quotations, Sales Orders)."""
    task_name = "sync_erpnext_sales"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name, timeout=1800):
            db = SessionLocal()
            try:
                sync_client = ERPNextSync(db)
                run_async(sync_client.sync_sales_task(full_sync=full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_erpnext_hr(self, full_sync: bool = False):
    """Sync ERPNext HR data (Departments, Designations, Users, HD Teams)."""
    task_name = "sync_erpnext_hr"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name, timeout=1800):
            db = SessionLocal()
            try:
                sync_client = ERPNextSync(db)
                run_async(sync_client.sync_hr_task(full_sync=full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_erpnext_items(self, full_sync: bool = False):
    """Sync ERPNext inventory items."""
    task_name = "sync_erpnext_items"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name, timeout=900):
            db = SessionLocal()
            try:
                sync_client = ERPNextSync(db)
                run_async(sync_client.sync_items_task(full_sync=full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


# Chatwoot Tasks
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_chatwoot_all(self, full_sync: bool = False):
    """Sync all Chatwoot entities."""
    task_name = "sync_chatwoot_all"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name, timeout=900):
            db = SessionLocal()
            try:
                sync_client = ChatwootSync(db)
                run_async(sync_client.sync_all(full_sync=full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_chatwoot_contacts(self, full_sync: bool = False):
    """Sync Chatwoot contacts."""
    task_name = "sync_chatwoot_contacts"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name):
            db = SessionLocal()
            try:
                sync_client = ChatwootSync(db)
                run_async(sync_client.sync_contacts_task(full_sync=full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_chatwoot_conversations(self, full_sync: bool = False):
    """Sync Chatwoot conversations/messages."""
    task_name = "sync_chatwoot_conversations"
    logger.info("task_started", task=task_name, full_sync=full_sync)

    try:
        with TaskLock(task_name):
            db = SessionLocal()
            try:
                sync_client = ChatwootSync(db)
                run_async(sync_client.sync_conversations_task(full_sync=full_sync))
                _invalidate_analytics_cache(task_name)
                logger.info("task_completed", task=task_name)
                return {"status": "success", "task": task_name}
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        raise self.retry(exc=e)


# DLQ Processor Tasks
@celery_app.task(bind=True, max_retries=1)
def process_dlq_records(self, source: Optional[str] = None, limit: int = 100):
    """Process failed sync records from the Dead Letter Queue.

    Retries failed records with exponential backoff. Records that exceed
    max_retries are marked as permanently failed.

    Args:
        source: Optional source filter ('SPLYNX', 'ERPNEXT', 'CHATWOOT')
        limit: Maximum number of records to process per run
    """
    from app.models.sync_cursor import FailedSyncRecord
    from app.models.sync_log import SyncSource
    from app.sync.base import utcnow
    import json

    task_name = "process_dlq_records"
    logger.info("task_started", task=task_name, source=source, limit=limit)

    try:
        with TaskLock(task_name, timeout=300):
            db = SessionLocal()
            try:
                # Build query for pending DLQ records
                query = db.query(FailedSyncRecord).filter(
                    FailedSyncRecord.is_resolved == False,
                    FailedSyncRecord.retry_count < FailedSyncRecord.max_retries,
                    FailedSyncRecord.next_retry_at <= utcnow(),
                )

                if source:
                    try:
                        source_enum = SyncSource(source)
                        query = query.filter(FailedSyncRecord.source == source_enum)
                    except ValueError:
                        logger.warning("dlq_invalid_source", source=source)

                records = query.order_by(FailedSyncRecord.created_at).limit(limit).all()
                logger.info("dlq_records_found", count=len(records))

                processed = 0
                succeeded = 0
                failed = 0

                for record in records:
                    processed += 1
                    try:
                        # Get the appropriate sync client
                        sync_client: Optional[BaseSyncClient] = None
                        if record.source == SyncSource.SPLYNX:
                            sync_client = SplynxSync(db)
                        elif record.source == SyncSource.ERPNEXT:
                            sync_client = ERPNextSync(db)
                        elif record.source == SyncSource.CHATWOOT:
                            sync_client = ChatwootSync(db)

                        if not sync_client:
                            logger.warning("dlq_unknown_source", record_id=record.id, source=record.source)
                            continue

                        # Parse payload and attempt reprocessing
                        payload = json.loads(record.payload) if isinstance(record.payload, str) else record.payload

                        # For now, just mark as retry and let the next regular sync handle it
                        # In the future, could implement entity-specific reprocessing
                        record.mark_retry()
                        # Exponential backoff: 5, 10, 20, 40 minutes (capped at 60)
                        backoff_minutes = 5 * (2 ** (record.retry_count - 1))
                        from datetime import timedelta
                        record.next_retry_at = utcnow() + timedelta(minutes=min(backoff_minutes, 60))

                        logger.info(
                            "dlq_record_scheduled_retry",
                            record_id=record.id,
                            entity_type=record.entity_type,
                            external_id=record.external_id,
                            retry_count=record.retry_count,
                            next_retry_at=record.next_retry_at.isoformat(),
                        )

                        # Check if max retries exceeded
                        if record.retry_count >= record.max_retries:
                            record.is_resolved = True
                            logger.warning(
                                "dlq_record_max_retries_exceeded",
                                record_id=record.id,
                                entity_type=record.entity_type,
                                external_id=record.external_id,
                            )
                            failed += 1
                        else:
                            succeeded += 1

                    except Exception as e:
                        logger.error(
                            "dlq_record_processing_error",
                            record_id=record.id,
                            error=str(e),
                        )
                        record.error_message = f"DLQ processing error: {str(e)[:500]}"
                        record.mark_retry()
                        failed += 1

                db.commit()
                logger.info(
                    "task_completed",
                    task=task_name,
                    processed=processed,
                    succeeded=succeeded,
                    failed=failed,
                )
                return {
                    "status": "success",
                    "task": task_name,
                    "processed": processed,
                    "succeeded": succeeded,
                    "failed": failed,
                }
            finally:
                db.close()
    except TaskLockError:
        logger.warning("task_skipped_locked", task=task_name)
        return {"status": "skipped", "reason": "lock_held", "task": task_name}
    except Exception as e:
        logger.error("task_failed", task=task_name, error=str(e))
        return {"status": "failed", "task": task_name, "error": str(e)}
