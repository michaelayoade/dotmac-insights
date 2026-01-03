"""Type definitions for comment service.

These dataclasses define the contract for comment operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

__all__ = [
    "CommentCreateData",
    "CommentUpdateData",
]


@dataclass
class CommentCreateData:
    """Data for creating a comment."""

    entity_type: str  # project, task, milestone
    entity_id: int
    content: str
    company: Optional[str] = None


@dataclass
class CommentUpdateData:
    """Data for updating a comment (content only)."""

    content: str
