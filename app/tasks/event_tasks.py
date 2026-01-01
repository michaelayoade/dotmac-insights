"""Celery tasks for event bus dispatch."""
from __future__ import annotations

from typing import Any, Dict

import structlog

from app.worker import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="events.dispatch",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    soft_time_limit=60,
    time_limit=120,
)
def dispatch_event(self, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dispatch an event to all registered handlers.

    This task is called by the EventBus when publishing events asynchronously.
    It imports handlers and executes them with a database session.

    Args:
        event_dict: Serialized Event dictionary

    Returns:
        Summary of handler execution results
    """
    from app.services.event_bus import Event, _handler_registry
    from app.database import SessionLocal

    event = Event.from_dict(event_dict)
    event_type = event.event_type

    logger.info(
        "dispatching_event",
        event_id=event.event_id,
        event_type=event_type,
    )

    # Import handler modules to populate registry
    # These imports register handlers via @subscribe decorator
    try:
        import app.tasks.workflow_tasks  # noqa: F401
    except ImportError:
        pass

    handlers = _handler_registry.get(event_type, [])

    if not handlers:
        logger.debug(
            "no_handlers_for_event",
            event_type=event_type,
            event_id=event.event_id,
        )
        return {
            "event_id": event.event_id,
            "event_type": event_type,
            "handlers_executed": 0,
            "handlers_failed": 0,
        }

    executed = 0
    failed = 0
    errors = []

    with SessionLocal() as db:
        for handler in handlers:
            try:
                logger.debug(
                    "executing_handler",
                    handler=handler.__name__,
                    event_id=event.event_id,
                )
                # Call handler with event and db session
                handler(event, db)
                db.commit()
                executed += 1
            except Exception as e:
                db.rollback()
                failed += 1
                error_msg = f"{handler.__name__}: {str(e)}"
                errors.append(error_msg)
                logger.error(
                    "handler_execution_failed",
                    handler=handler.__name__,
                    event_id=event.event_id,
                    error=str(e),
                    exc_info=True,
                )

    result = {
        "event_id": event.event_id,
        "event_type": event_type,
        "handlers_executed": executed,
        "handlers_failed": failed,
    }

    if errors:
        result["errors"] = errors

    logger.info(
        "event_dispatch_complete",
        **result,
    )

    return result
