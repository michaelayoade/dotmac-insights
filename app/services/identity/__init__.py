"""Identity services (Party-based model).

This module contains business logic for:
- Parties (persons and organizations)
- Party roles (customer, lead, vendor, etc.)
- Party relations (employment, contact-of, etc.)
"""
from .parties import PartyService

# Legacy module-level functions for backward compatibility
# TODO: Remove after all routes are migrated
from . import party_service

__all__ = [
    "PartyService",
    "party_service",  # Legacy - remove after migration
]
