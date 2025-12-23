"""Event bus for cross-module communication using Redis pub/sub."""
from __future__ import annotations

import json
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

import structlog
from redis import Redis

from app.config import settings
from app.models.notification import NotificationEventType

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)

# Global event bus instance
_event_bus: Optional["EventBus"] = None

# Registry of event handlers (populated at import time via @subscribe decorator)
_handler_registry: Dict[str, List[Callable]] = defaultdict(list)


class EventEncoder(json.JSONEncoder):
    """JSON encoder that handles Event-specific types."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, NotificationEventType):
            return obj.value
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return super().default(obj)


@dataclass
class Event:
    """
    Immutable event structure for cross-module communication.

    Events are published to the event bus and dispatched to all registered
    handlers. The event bus also forwards events to the NotificationService
    for webhook/email/in-app notification delivery.
    """

    event_type: str  # NotificationEventType value
    payload: Dict[str, Any] = field(default_factory=dict)
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    user_ids: Optional[List[int]] = None
    company: Optional[str] = None
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Create event from dictionary."""
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)

    def __repr__(self) -> str:
        return f"<Event({self.event_type}, id={self.event_id[:8]}, entity={self.entity_type}:{self.entity_id})>"


def subscribe(event_type: NotificationEventType) -> Callable:
    """
    Decorator to register an event handler.

    Usage:
        @subscribe(NotificationEventType.APPROVAL_REQUESTED)
        def on_approval_requested(event: Event, db: Session):
            # Handle the event
            pass

    Handlers are called asynchronously via Celery when events are published.
    """

    def decorator(func: Callable) -> Callable:
        _handler_registry[event_type.value].append(func)
        logger.debug(
            "event_handler_registered",
            event_type=event_type.value,
            handler=func.__name__,
        )
        return func

    return decorator


class EventBus:
    """
    Redis-based event bus for cross-module communication.

    The event bus provides:
    - Decoupled event publishing and handling
    - Async handler execution via Celery
    - Integration with existing NotificationService
    - Event persistence in Redis for debugging

    Usage:
        # Get the global event bus instance
        bus = get_event_bus()

        # Publish an event
        event_id = bus.publish(Event(
            event_type=NotificationEventType.APPROVAL_REQUESTED.value,
            entity_type="approval",
            entity_id=123,
            user_ids=[1, 2, 3],
            payload={"document_type": "journal_entry", "amount": 5000}
        ))
    """

    def __init__(self, redis_url: Optional[str] = None):
        """Initialize event bus with Redis connection."""
        self.redis_url = redis_url or settings.redis_url
        self._redis: Optional[Redis] = None
        self._handlers = _handler_registry

    @property
    def redis(self) -> Optional[Redis]:
        """Get Redis client, connecting lazily."""
        if self._redis is None and self.redis_url:
            try:
                self._redis = Redis.from_url(self.redis_url, decode_responses=True)
                self._redis.ping()
            except Exception as e:
                logger.warning("redis_connection_failed", error=str(e))
                self._redis = None
        return self._redis

    def publish(
        self,
        event: Event,
        dispatch_async: bool = True,
        notify: bool = True,
    ) -> str:
        """
        Publish an event to the bus.

        Args:
            event: The event to publish
            dispatch_async: If True, dispatch handlers via Celery (default)
            notify: If True, also emit via NotificationService (default)

        Returns:
            The event ID
        """
        logger.info(
            "event_published",
            event_type=event.event_type,
            event_id=event.event_id,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
        )

        # Store event in Redis for debugging/replay (optional)
        if self.redis:
            try:
                key = f"events:{event.event_id}"
                self.redis.setex(
                    key,
                    3600,  # 1 hour TTL
                    json.dumps(event.to_dict(), cls=EventEncoder),
                )
            except Exception as e:
                logger.warning("event_store_failed", error=str(e))

        # Dispatch to handlers
        if dispatch_async:
            self._dispatch_async(event)
        else:
            self._dispatch_sync(event)

        # Also notify via NotificationService if requested
        if notify:
            self._notify(event)

        return event.event_id

    def _dispatch_async(self, event: Event) -> None:
        """Dispatch event handlers asynchronously via Celery."""
        try:
            from app.tasks.event_tasks import dispatch_event

            dispatch_event.delay(event.to_dict())
        except Exception as e:
            logger.warning(
                "async_dispatch_failed",
                event_id=event.event_id,
                error=str(e),
            )
            # Fall back to sync dispatch
            self._dispatch_sync(event)

    def _dispatch_sync(self, event: Event) -> None:
        """Dispatch event handlers synchronously (fallback)."""
        handlers = self._handlers.get(event.event_type, [])
        if not handlers:
            return

        try:
            from app.database import SessionLocal
        except Exception as e:
            logger.error(
                "event_dispatch_no_session",
                event_id=event.event_id,
                error=str(e),
            )
            return

        with SessionLocal() as db:
            for handler in handlers:
                try:
                    if handler.__code__.co_argcount >= 2:
                        handler(event, db)
                    else:
                        handler(event)
                    db.commit()
                except Exception as e:
                    db.rollback()
                    logger.error(
                        "event_handler_error",
                        event_id=event.event_id,
                        handler=handler.__name__,
                        error=str(e),
                    )

    def _notify(self, event: Event) -> None:
        """Forward event to NotificationService for webhooks/email/in-app."""
        try:
            # Import here to avoid circular dependency
            from app.database import SessionLocal
            from app.services.notification_service import NotificationService
            from app.models.notification import NotificationEventType as NET

            # Only notify for known event types
            try:
                event_type_enum = NET(event.event_type)
            except ValueError:
                logger.debug(
                    "unknown_event_type_skip_notify",
                    event_type=event.event_type,
                )
                return

            with SessionLocal() as db:
                notification_service = NotificationService(db)
                notification_service.emit_event(
                    event_type=event_type_enum,
                    payload=event.payload,
                    entity_type=event.entity_type,
                    entity_id=event.entity_id,
                    user_ids=event.user_ids,
                    company=event.company,
                )
        except Exception as e:
            logger.warning(
                "notification_forward_failed",
                event_id=event.event_id,
                error=str(e),
            )

    def get_handlers(self, event_type: str) -> List[Callable]:
        """Get registered handlers for an event type."""
        return self._handlers.get(event_type, [])

    def get_event(self, event_id: str) -> Optional[Event]:
        """Retrieve a stored event by ID (for debugging)."""
        if not self.redis:
            return None
        try:
            key = f"events:{event_id}"
            data = self.redis.get(key)
            if data:
                return Event.from_dict(json.loads(data))
        except Exception:
            pass
        return None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def publish_event(
    event_type: NotificationEventType,
    payload: Optional[Dict[str, Any]] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    user_ids: Optional[List[int]] = None,
    company: Optional[str] = None,
    dispatch_async: bool = True,
    notify: bool = True,
) -> str:
    """
    Convenience function to publish an event.

    This is the primary way to publish events from application code.

    Args:
        event_type: Type of event (from NotificationEventType enum)
        payload: Event data payload
        entity_type: Type of related entity
        entity_id: ID of related entity
        user_ids: Specific users to notify
        company: Company context
        dispatch_async: If True, dispatch handlers via Celery
        notify: If True, also emit via NotificationService

    Returns:
        The event ID

    Example:
        from app.services.event_bus import publish_event
        from app.models.notification import NotificationEventType

        publish_event(
            event_type=NotificationEventType.APPROVAL_REQUESTED,
            entity_type="approval",
            entity_id=approval.id,
            user_ids=[approver.id],
            payload={
                "doctype": "journal_entry",
                "document_id": doc.id,
                "amount": doc.total,
            }
        )
    """
    event = Event(
        event_type=event_type.value,
        payload=payload or {},
        entity_type=entity_type,
        entity_id=entity_id,
        user_ids=user_ids,
        company=company,
    )
    return get_event_bus().publish(event, dispatch_async=dispatch_async, notify=notify)
