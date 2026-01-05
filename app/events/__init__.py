"""
SQLAlchemy event handlers for real-time triggers.

This module contains event listeners that react to model changes
and trigger background tasks for processing.
"""

from app.events.subscription_events import register_subscription_events

__all__ = [
    "register_subscription_events",
]
