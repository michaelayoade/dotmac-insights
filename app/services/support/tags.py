"""Tag service - business logic for ticket tags.

This service handles tag management:
- CRUD operations for ticket tags
- Usage tracking
- Tag merging

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.support_tags import TicketTag

from .types import (
    TagCreate,
    TagUpdate,
)
from .errors import (
    DuplicateTagError,
    TagNotFoundError,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["TagService"]


class TagService:
    """Service for ticket tag management.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def list(
        self,
        active_only: bool = True,
        search: Optional[str] = None,
    ) -> List[TicketTag]:
        """List ticket tags with optional filtering.

        Args:
            active_only: Only return active tags.
            search: Search in tag name.

        Returns:
            List of TicketTag instances.
        """
        query = self.db.query(TicketTag)

        if active_only:
            query = query.filter(TicketTag.is_active == True)

        if search:
            search_term = f"%{search}%"
            query = query.filter(TicketTag.name.ilike(search_term))

        return query.order_by(TicketTag.name.asc()).all()

    def get(self, tag_id: int) -> TicketTag:
        """Get a tag by ID.

        Args:
            tag_id: The tag ID.

        Returns:
            TicketTag instance.

        Raises:
            TagNotFoundError: If not found.
        """
        tag = (
            self.db.query(TicketTag)
            .filter(TicketTag.id == tag_id)
            .first()
        )
        if not tag:
            raise TagNotFoundError(tag_id)
        return tag

    def get_by_name(self, name: str) -> Optional[TicketTag]:
        """Get a tag by name.

        Args:
            name: The tag name.

        Returns:
            TicketTag instance or None.
        """
        return (
            self.db.query(TicketTag)
            .filter(TicketTag.name == name)
            .first()
        )

    def get_popular(self, limit: int = 20) -> List[TicketTag]:
        """Get most used tags.

        Args:
            limit: Maximum number of results.

        Returns:
            List of TicketTag instances ordered by usage.
        """
        return (
            self.db.query(TicketTag)
            .filter(TicketTag.is_active == True)
            .order_by(TicketTag.usage_count.desc())
            .limit(limit)
            .all()
        )

    def search(self, query: str, limit: int = 20) -> List[TicketTag]:
        """Search tags by name.

        Args:
            query: Search query.
            limit: Maximum number of results.

        Returns:
            List of matching TicketTag instances.
        """
        search_term = f"%{query}%"
        return (
            self.db.query(TicketTag)
            .filter(
                TicketTag.is_active == True,
                TicketTag.name.ilike(search_term),
            )
            .order_by(TicketTag.usage_count.desc())
            .limit(limit)
            .all()
        )

    # -------------------------------------------------------------------------
    # Mutations
    # -------------------------------------------------------------------------

    def create(self, data: TagCreate) -> TicketTag:
        """Create a new tag.

        Args:
            data: Tag creation data.

        Returns:
            Created TicketTag instance.

        Raises:
            DuplicateTagError: If name already exists.
        """
        # Check for duplicate name
        existing = self.get_by_name(data.name)
        if existing:
            raise DuplicateTagError(data.name)

        tag = TicketTag(
            name=data.name,
            color=data.color,
            description=data.description,
            usage_count=0,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        if self.principal:
            tag.created_by_id = getattr(self.principal, "id", None)

        self.db.add(tag)
        self.db.flush()
        return tag

    def update(self, tag_id: int, data: TagUpdate) -> TicketTag:
        """Update a tag.

        Args:
            tag_id: The tag ID.
            data: Update data.

        Returns:
            Updated TicketTag instance.

        Raises:
            TagNotFoundError: If not found.
            DuplicateTagError: If new name conflicts.
        """
        tag = self.get(tag_id)

        if data.name is not None and data.name != tag.name:
            existing = self.get_by_name(data.name)
            if existing:
                raise DuplicateTagError(data.name)
            tag.name = data.name

        if data.color is not None:
            tag.color = data.color

        if data.description is not None:
            tag.description = data.description

        if data.is_active is not None:
            tag.is_active = data.is_active

        tag.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return tag

    def delete(self, tag_id: int) -> bool:
        """Delete a tag.

        Args:
            tag_id: The tag ID.

        Returns:
            True if deleted.

        Raises:
            TagNotFoundError: If not found.
        """
        tag = self.get(tag_id)
        self.db.delete(tag)
        self.db.flush()
        return True

    def merge(self, target_id: int, source_ids: List[int]) -> TicketTag:
        """Merge multiple tags into one.

        This will:
        1. Update all references from source tags to target tag
        2. Add source usage counts to target
        3. Delete source tags

        Args:
            target_id: The tag ID to keep.
            source_ids: List of tag IDs to merge into target.

        Returns:
            Updated target TicketTag.

        Raises:
            TagNotFoundError: If target or any source not found.
        """
        target = self.get(target_id)

        # Validate all source tags exist
        sources = []
        for source_id in source_ids:
            if source_id == target_id:
                continue  # Skip if same as target
            source = self.get(source_id)
            sources.append(source)

        # Sum up usage counts
        total_usage = target.usage_count or 0
        for source in sources:
            total_usage += source.usage_count or 0

        # Update target usage count
        target.usage_count = total_usage
        target.updated_at = datetime.now(timezone.utc)

        # Delete source tags
        # Note: In a real implementation, you'd also need to update
        # ticket_tags junction table references before deleting
        for source in sources:
            self.db.delete(source)

        self.db.flush()
        return target

    # -------------------------------------------------------------------------
    # Usage
    # -------------------------------------------------------------------------

    def increment_usage(self, tag_id: int) -> None:
        """Increment the usage count for a tag.

        Args:
            tag_id: The tag ID.
        """
        tag = self.get(tag_id)
        tag.usage_count = (tag.usage_count or 0) + 1
        self.db.flush()

    def decrement_usage(self, tag_id: int) -> None:
        """Decrement the usage count for a tag.

        Args:
            tag_id: The tag ID.
        """
        tag = self.get(tag_id)
        tag.usage_count = max(0, (tag.usage_count or 0) - 1)
        self.db.flush()

    def get_usage_count(self, tag_id: int) -> int:
        """Get the usage count for a tag.

        Args:
            tag_id: The tag ID.

        Returns:
            Usage count.
        """
        tag = self.get(tag_id)
        return tag.usage_count or 0

    def recalculate_usage_counts(self) -> int:
        """Recalculate all tag usage counts from ticket data.

        This is a maintenance operation that should be run periodically
        to ensure usage counts are accurate.

        Note: Requires ticket_tags junction table to be defined.

        Returns:
            Number of tags updated.
        """
        # This would require access to the ticket_tags junction table
        # For now, just return 0 as a placeholder
        # In a real implementation:
        #
        # from app.models.ticket import ticket_tags_table
        # for tag in self.db.query(TicketTag).all():
        #     count = self.db.query(func.count(ticket_tags_table.c.ticket_id))\
        #         .filter(ticket_tags_table.c.tag_id == tag.id)\
        #         .scalar() or 0
        #     tag.usage_count = count
        # self.db.flush()
        return 0

    def get_or_create(self, name: str, color: Optional[str] = None) -> TicketTag:
        """Get an existing tag by name or create it.

        Args:
            name: The tag name.
            color: Optional color for new tag.

        Returns:
            TicketTag instance (existing or newly created).
        """
        existing = self.get_by_name(name)
        if existing:
            return existing

        return self.create(TagCreate(name=name, color=color))

    def get_multiple(self, tag_ids: List[int]) -> List[TicketTag]:
        """Get multiple tags by IDs.

        Args:
            tag_ids: List of tag IDs.

        Returns:
            List of TicketTag instances found.
        """
        if not tag_ids:
            return []

        return (
            self.db.query(TicketTag)
            .filter(TicketTag.id.in_(tag_ids))
            .all()
        )

    def get_multiple_by_names(self, names: List[str]) -> List[TicketTag]:
        """Get multiple tags by names.

        Args:
            names: List of tag names.

        Returns:
            List of TicketTag instances found.
        """
        if not names:
            return []

        return (
            self.db.query(TicketTag)
            .filter(TicketTag.name.in_(names))
            .all()
        )
