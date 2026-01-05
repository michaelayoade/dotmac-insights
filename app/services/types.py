"""Shared type definitions for the service layer."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Sequence, TypeVar

T = TypeVar("T")

__all__ = [
    "PaginationParams",
    "PaginatedResult",
    "SortParams",
]


@dataclass(frozen=True)
class PaginationParams:
    """Immutable pagination parameters.

    Args:
        offset: Starting position (0-indexed).
        limit: Maximum number of items to return.
    """

    offset: int = 0
    limit: int = 50


@dataclass
class PaginatedResult(Generic[T]):
    """Result container for paginated queries.

    Args:
        items: The items in the current page.
        total: Total count of all matching items.
        offset: The offset used for this page.
        limit: The limit used for this page.
    """

    items: Sequence[T]
    total: int
    offset: int
    limit: int

    @property
    def has_more(self) -> bool:
        """Return True if there are more items beyond this page."""
        return self.offset + len(self.items) < self.total

    @property
    def page(self) -> int:
        """Return 1-indexed page number (for display)."""
        if self.limit <= 0:
            return 1
        return (self.offset // self.limit) + 1

    @property
    def pages(self) -> int:
        """Return total number of pages."""
        if self.limit <= 0:
            return 1
        return (self.total + self.limit - 1) // self.limit

    @property
    def data(self) -> Sequence[T]:
        """Alias for items (backwards compatibility)."""
        return self.items


@dataclass(frozen=True)
class SortParams:
    """Immutable sorting parameters.

    Args:
        field: Field name to sort by.
        descending: If True, sort in descending order.
    """

    field: str = "id"
    descending: bool = True
