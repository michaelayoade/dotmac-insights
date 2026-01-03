"""Celery tasks for support automation, SLA monitoring, and routing."""
from datetime import datetime
from typing import Optional

import structlog
import redis

from app.worker import celery_app
from app.config import settings
from app.database import SessionLocal
from app.models.support_automation import AutomationTrigger
from app.services.sla_engine import SLAEngine
from app.services.routing_engine import RoutingEngine
from app.services.automation_executor import AutomationExecutor

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


class SupportTaskLock:
    """Distributed lock for support automation tasks."""

    def __init__(self, lock_name: str, timeout: int = 300):
        self.lock_name = f"support_task:{lock_name}"
        self.timeout = timeout
        self.redis = get_redis_client()
        self._lock = None

    def __enter__(self):
        self._lock = self.redis.lock(self.lock_name, timeout=self.timeout)
        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            raise SupportTaskLockError(f"Could not acquire lock: {self.lock_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._lock:
            try:
                self._lock.release()
            except redis.exceptions.LockError:
                pass
        return False


class SupportTaskLockError(Exception):
    """Raised when a task lock cannot be acquired."""
    pass


# =============================================================================
# SLA MONITORING TASKS
# =============================================================================

@celery_app.task(
    name="support.check_sla_warnings",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def check_sla_warnings(self, threshold_minutes: int = 60):
    """Check for tickets approaching SLA breach.

    Runs periodically to identify tickets that need attention before
    they breach their SLA targets.

    Args:
        threshold_minutes: Minutes before deadline to trigger warning
    """
    try:
        with SupportTaskLock("sla_warnings", timeout=120):
            db = SessionLocal()
            try:
                sla_engine = SLAEngine(db)
                warnings = sla_engine.find_sla_warnings(threshold_minutes)

                logger.info(
                    "sla_warnings_check_complete",
                    warnings_found=len(warnings),
                    threshold_minutes=threshold_minutes,
                )

                # Trigger automation for each warning
                if warnings:
                    executor = AutomationExecutor(db)
                    for ticket in warnings:
                        try:
                            executor.execute_trigger(
                                AutomationTrigger.SLA_WARNING,
                                ticket,
                                {"threshold_minutes": threshold_minutes},
                            )
                        except Exception as e:
                            logger.error(
                                "sla_warning_automation_failed",
                                ticket_id=ticket.id,
                                error=str(e),
                            )

                return {
                    "status": "success",
                    "warnings_found": len(warnings),
                    "ticket_ids": [t.id for t in warnings],
                }

            finally:
                db.close()

    except SupportTaskLockError:
        logger.info("sla_warnings_task_skipped_lock")
        return {"status": "skipped", "reason": "lock_held"}
    except Exception as e:
        logger.error("sla_warnings_task_failed", error=str(e))
        raise self.retry(exc=e)


@celery_app.task(
    name="support.check_sla_breaches",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def check_sla_breaches(self):
    """Check for and log SLA breaches.

    Runs periodically to identify tickets that have breached their SLA
    and logs the breaches for reporting.
    """
    try:
        with SupportTaskLock("sla_breaches", timeout=120):
            db = SessionLocal()
            try:
                sla_engine = SLAEngine(db)
                result = sla_engine.process_sla_checks()

                logger.info(
                    "sla_breaches_check_complete",
                    warnings=result["warnings_found"],
                    breaches=result["breaches_found"],
                    logged=result["breaches_logged"],
                )

                # Trigger automation for breaches
                if result["breaches_found"] > 0:
                    executor = AutomationExecutor(db)
                    breaches = sla_engine.find_sla_breaches()
                    for ticket, breach_type in breaches:
                        try:
                            executor.execute_trigger(
                                AutomationTrigger.SLA_BREACHED,
                                ticket,
                                {"breach_type": breach_type},
                            )
                        except Exception as e:
                            logger.error(
                                "sla_breach_automation_failed",
                                ticket_id=ticket.id,
                                error=str(e),
                            )

                return {
                    "status": "success",
                    **result,
                }

            finally:
                db.close()

    except SupportTaskLockError:
        logger.info("sla_breaches_task_skipped_lock")
        return {"status": "skipped", "reason": "lock_held"}
    except Exception as e:
        logger.error("sla_breaches_task_failed", error=str(e))
        raise self.retry(exc=e)


# =============================================================================
# IDLE TICKET TASKS
# =============================================================================

@celery_app.task(
    name="support.check_idle_tickets",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def check_idle_tickets(self, idle_hours: int = 24):
    """Check for idle tickets and trigger automation.

    Runs periodically to find tickets that haven't been updated
    and triggers the TICKET_IDLE automation.

    Args:
        idle_hours: Hours of inactivity to consider idle
    """
    try:
        with SupportTaskLock("idle_tickets", timeout=180):
            db = SessionLocal()
            try:
                executor = AutomationExecutor(db)
                result = executor.process_idle_tickets(idle_hours)

                logger.info(
                    "idle_tickets_check_complete",
                    found=result["idle_tickets_found"],
                    triggered=result["automations_triggered"],
                )

                return {
                    "status": "success",
                    **result,
                }

            finally:
                db.close()

    except SupportTaskLockError:
        logger.info("idle_tickets_task_skipped_lock")
        return {"status": "skipped", "reason": "lock_held"}
    except Exception as e:
        logger.error("idle_tickets_task_failed", error=str(e))
        raise self.retry(exc=e)


# =============================================================================
# AUTO-ASSIGNMENT TASKS
# =============================================================================

@celery_app.task(
    name="support.auto_assign_tickets",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def auto_assign_tickets(self, limit: int = 50):
    """Auto-assign unassigned tickets.

    Runs periodically to assign tickets that weren't automatically
    assigned at creation time.

    Args:
        limit: Maximum tickets to process per run
    """
    try:
        with SupportTaskLock("auto_assign", timeout=180):
            db = SessionLocal()
            try:
                routing_engine = RoutingEngine(db)
                result = routing_engine.auto_assign_batch(limit)

                logger.info(
                    "auto_assign_complete",
                    processed=result["processed"],
                    assigned=result["assigned"],
                    failed=result["failed"],
                )

                return {
                    "status": "success",
                    "processed": result["processed"],
                    "assigned": result["assigned"],
                    "failed": result["failed"],
                }

            finally:
                db.close()

    except SupportTaskLockError:
        logger.info("auto_assign_task_skipped_lock")
        return {"status": "skipped", "reason": "lock_held"}
    except Exception as e:
        logger.error("auto_assign_task_failed", error=str(e))
        raise self.retry(exc=e)


@celery_app.task(
    name="support.rebalance_workload",
    bind=True,
    max_retries=1,
)
def rebalance_workload(self, team_id: Optional[int] = None):
    """Rebalance ticket workload across agents.

    Runs periodically to redistribute tickets from overloaded
    agents to underloaded ones.

    Args:
        team_id: Optional team to rebalance (None = all teams)
    """
    try:
        with SupportTaskLock("rebalance", timeout=300):
            db = SessionLocal()
            try:
                routing_engine = RoutingEngine(db)
                result = routing_engine.rebalance_workload(team_id)

                logger.info(
                    "workload_rebalance_complete",
                    rebalanced=result["rebalanced"],
                )

                return {
                    "status": "success",
                    **result,
                }

            finally:
                db.close()

    except SupportTaskLockError:
        logger.info("rebalance_task_skipped_lock")
        return {"status": "skipped", "reason": "lock_held"}
    except Exception as e:
        logger.error("rebalance_task_failed", error=str(e))
        raise


# =============================================================================
# TICKET EVENT TASKS
# =============================================================================

@celery_app.task(name="support.process_ticket_event")
def process_ticket_event(ticket_id: int, trigger: str, context: Optional[dict] = None):
    """Process a ticket event and execute matching automations.

    Called when ticket events occur (create, update, reply, etc.).

    Args:
        ticket_id: ID of the ticket
        trigger: The trigger event type
        context: Additional context about the event
    """
    db = SessionLocal()
    try:
        from app.models.ticket import Ticket
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

        if not ticket:
            logger.warning(
                "ticket_event_ticket_not_found",
                ticket_id=ticket_id,
                trigger=trigger,
            )
            return {"status": "error", "reason": "ticket_not_found"}

        try:
            trigger_enum = AutomationTrigger(trigger)
        except ValueError:
            logger.warning(
                "ticket_event_invalid_trigger",
                ticket_id=ticket_id,
                trigger=trigger,
            )
            return {"status": "error", "reason": "invalid_trigger"}

        executor = AutomationExecutor(db)
        result = executor.execute_trigger(trigger_enum, ticket, context or {})

        return {
            "status": "success",
            "ticket_id": ticket_id,
            "trigger": trigger,
            "rules_executed": result["rules_executed"],
            "actions_performed": result["actions_performed"],
        }

    except Exception as e:
        logger.error(
            "ticket_event_processing_failed",
            ticket_id=ticket_id,
            trigger=trigger,
            error=str(e),
        )
        return {"status": "error", "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="support.apply_sla_to_ticket")
def apply_sla_to_ticket(ticket_id: int):
    """Apply SLA policy to a ticket.

    Called after ticket creation to set SLA deadlines.

    Args:
        ticket_id: ID of the ticket
    """
    db = SessionLocal()
    try:
        from app.models.ticket import Ticket
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

        if not ticket:
            logger.warning("apply_sla_ticket_not_found", ticket_id=ticket_id)
            return {"status": "error", "reason": "ticket_not_found"}

        sla_engine = SLAEngine(db)
        result = sla_engine.update_ticket_sla(ticket)

        logger.info(
            "sla_applied",
            ticket_id=ticket_id,
            policy_id=result.get("policy_id"),
            targets=len(result.get("targets_set", [])),
        )

        return {
            "status": "success",
            "ticket_id": ticket_id,
            **result,
        }

    except Exception as e:
        logger.error(
            "apply_sla_failed",
            ticket_id=ticket_id,
            error=str(e),
        )
        return {"status": "error", "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="support.auto_assign_ticket")
def auto_assign_ticket(ticket_id: int):
    """Auto-assign a single ticket.

    Called after ticket creation if auto-assignment is enabled.

    Args:
        ticket_id: ID of the ticket
    """
    db = SessionLocal()
    try:
        from app.models.ticket import Ticket
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

        if not ticket:
            logger.warning("auto_assign_ticket_not_found", ticket_id=ticket_id)
            return {"status": "error", "reason": "ticket_not_found"}

        routing_engine = RoutingEngine(db)
        result = routing_engine.auto_assign(ticket)

        if result.get("assigned"):
            logger.info(
                "ticket_auto_assigned",
                ticket_id=ticket_id,
                agent_id=result.get("agent_id"),
                rule_id=result.get("rule_id"),
            )
        else:
            logger.debug(
                "ticket_not_auto_assigned",
                ticket_id=ticket_id,
                reason=result.get("reason"),
            )

        return {
            "status": "success",
            "ticket_id": ticket_id,
            **result,
        }

    except Exception as e:
        logger.error(
            "auto_assign_ticket_failed",
            ticket_id=ticket_id,
            error=str(e),
        )
        return {"status": "error", "error": str(e)}
    finally:
        db.close()
