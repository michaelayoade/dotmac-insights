"""CRM domain services.

This module contains business logic for:
- Opportunities (deal pipeline)
- Activities
- Pipeline stages
"""
from .opportunities import OpportunityService

__all__ = [
    "OpportunityService",
]
