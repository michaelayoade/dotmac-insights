"""Knowledge base service - business logic for KB categories and articles.

This service handles knowledge base management:
- Category CRUD and hierarchy
- Article CRUD and lifecycle
- Attachments
- Feedback and helpfulness tracking
- Search and analytics

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.support_kb import (
    ArticleStatus,
    ArticleVisibility,
    KBArticle,
    KBArticleAttachment,
    KBArticleFeedback,
    KBCategory,
)

from .types import (
    KBArticleCreate,
    KBArticleFilters,
    KBArticleStats,
    KBArticleUpdate,
    KBAttachmentData,
    KBCategoryCreate,
    KBCategoryUpdate,
    KBHelpfulnessStats,
    KBListResult,
)
from app.services.base import PaginationParams
from .errors import (
    DuplicateSlugError,
    KBArticleNotFoundError,
    KBCategoryNotFoundError,
)

if TYPE_CHECKING:
    from app.auth import Principal
    from app.services.base import PaginatedResult, PaginationParams

__all__ = ["KnowledgeBaseService"]


def slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    # Convert to lowercase and replace spaces with hyphens
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug


class KnowledgeBaseService:
    """Service for knowledge base management.

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
    # Category Queries
    # -------------------------------------------------------------------------

    def list_categories(
        self,
        parent_id: Optional[int] = None,
        visibility: Optional[str] = None,
        active_only: bool = True,
    ) -> List[KBCategory]:
        """List KB categories with optional filtering.

        Args:
            parent_id: Filter by parent category (None for root categories).
            visibility: Filter by visibility (public, internal, restricted).
            active_only: Only return active categories.

        Returns:
            List of KBCategory instances.
        """
        query = self.db.query(KBCategory)

        if active_only:
            query = query.filter(KBCategory.is_active == True)

        if parent_id is not None:
            query = query.filter(KBCategory.parent_id == parent_id)
        else:
            # Return root categories only if parent_id not specified
            query = query.filter(KBCategory.parent_id.is_(None))

        if visibility:
            query = query.filter(KBCategory.visibility == visibility)

        return query.order_by(KBCategory.display_order.asc(), KBCategory.name.asc()).all()

    def list_categories_flat(
        self,
        visibility: Optional[str] = None,
        active_only: bool = True,
    ) -> List[KBCategory]:
        """List all categories without hierarchy.

        Args:
            visibility: Filter by visibility (public, internal, restricted).
            active_only: Only return active categories.

        Returns:
            List of KBCategory instances.
        """
        query = self.db.query(KBCategory)

        if active_only:
            query = query.filter(KBCategory.is_active == True)

        if visibility:
            query = query.filter(KBCategory.visibility == visibility)

        return query.order_by(KBCategory.display_order.asc(), KBCategory.name.asc()).all()

    def get_category(self, category_id: int) -> KBCategory:
        """Get a category by ID.

        Args:
            category_id: The category ID.

        Returns:
            KBCategory instance.

        Raises:
            KBCategoryNotFoundError: If not found.
        """
        category = (
            self.db.query(KBCategory)
            .filter(KBCategory.id == category_id)
            .first()
        )
        if not category:
            raise KBCategoryNotFoundError(category_id)
        return category

    def get_category_by_slug(self, slug: str) -> Optional[KBCategory]:
        """Get a category by slug.

        Args:
            slug: The category slug.

        Returns:
            KBCategory instance or None.
        """
        return (
            self.db.query(KBCategory)
            .filter(KBCategory.slug == slug)
            .first()
        )

    def get_category_tree(self) -> List[Dict[str, Any]]:
        """Get the full category hierarchy as a nested tree.

        Returns:
            List of category dicts with nested 'children'.
        """
        # Get all active categories
        categories = (
            self.db.query(KBCategory)
            .filter(KBCategory.is_active == True)
            .order_by(KBCategory.display_order.asc(), KBCategory.name.asc())
            .all()
        )

        # Build tree structure
        category_map: Dict[int, Dict[str, Any]] = {}
        for cat in categories:
            category_map[cat.id] = {
                "id": cat.id,
                "name": cat.name,
                "slug": cat.slug,
                "description": cat.description,
                "icon": cat.icon,
                "visibility": cat.visibility,
                "parent_id": cat.parent_id,
                "children": [],
            }

        # Build hierarchy
        roots: List[Dict[str, Any]] = []
        for cat_id, cat_dict in category_map.items():
            parent_id = cat_dict["parent_id"]
            if parent_id is None:
                roots.append(cat_dict)
            elif parent_id in category_map:
                category_map[parent_id]["children"].append(cat_dict)

        return roots

    # -------------------------------------------------------------------------
    # Category Mutations
    # -------------------------------------------------------------------------

    def create_category(self, data: KBCategoryCreate) -> KBCategory:
        """Create a new KB category.

        Args:
            data: Category creation data.

        Returns:
            Created KBCategory instance.

        Raises:
            DuplicateSlugError: If slug already exists.
        """
        # Generate slug if not provided
        slug = data.slug or slugify(data.name)

        # Check for duplicate slug
        existing = self.get_category_by_slug(slug)
        if existing:
            raise DuplicateSlugError(slug, "category")

        # Get next display order
        max_order = (
            self.db.query(func.max(KBCategory.display_order))
            .filter(KBCategory.parent_id == data.parent_id)
            .scalar()
        )
        display_order = (max_order or 0) + 10

        category = KBCategory(
            name=data.name,
            slug=slug,
            description=data.description,
            icon=data.icon,
            parent_id=data.parent_id,
            visibility=data.visibility,
            display_order=display_order,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        if self.principal:
            category.created_by_id = getattr(self.principal, "id", None)

        self.db.add(category)
        self.db.flush()
        return category

    def update_category(
        self,
        category_id: int,
        data: KBCategoryUpdate,
    ) -> KBCategory:
        """Update a KB category.

        Args:
            category_id: The category ID.
            data: Update data.

        Returns:
            Updated KBCategory instance.

        Raises:
            KBCategoryNotFoundError: If not found.
            DuplicateSlugError: If new slug conflicts.
        """
        category = self.get_category(category_id)

        if data.slug is not None and data.slug != category.slug:
            existing = self.get_category_by_slug(data.slug)
            if existing:
                raise DuplicateSlugError(data.slug, "category")
            category.slug = data.slug

        if data.name is not None:
            category.name = data.name

        if data.description is not None:
            category.description = data.description

        if data.icon is not None:
            category.icon = data.icon

        if data.parent_id is not None:
            category.parent_id = data.parent_id

        if data.visibility is not None:
            category.visibility = data.visibility

        if data.display_order is not None:
            category.display_order = data.display_order

        if data.is_active is not None:
            category.is_active = data.is_active

        category.updated_at = datetime.now(timezone.utc)

        if self.principal:
            category.updated_by_id = getattr(self.principal, "id", None)

        self.db.flush()
        return category

    def delete_category(self, category_id: int) -> bool:
        """Delete a KB category.

        Args:
            category_id: The category ID.

        Returns:
            True if deleted.

        Raises:
            KBCategoryNotFoundError: If not found.
        """
        category = self.get_category(category_id)
        self.db.delete(category)
        self.db.flush()
        return True

    def reorder_categories(self, category_ids: List[int]) -> None:
        """Reorder categories.

        Args:
            category_ids: List of category IDs in desired order.
        """
        for order, cat_id in enumerate(category_ids):
            category = self.get_category(cat_id)
            category.display_order = order * 10
        self.db.flush()

    # -------------------------------------------------------------------------
    # Article Queries
    # -------------------------------------------------------------------------

    def list_articles(
        self,
        category_id: Optional[int] = None,
        status: Optional[str] = None,
        visibility: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[KBArticle]:
        """List KB articles with optional filtering.

        Args:
            category_id: Filter by category.
            status: Filter by status (draft, published, archived).
            visibility: Filter by visibility.
            search: Search in title, content, keywords.
            limit: Maximum number of results.
            offset: Offset for pagination.

        Returns:
            List of KBArticle instances.
        """
        query = self.db.query(KBArticle)

        if category_id:
            query = query.filter(KBArticle.category_id == category_id)

        if status:
            query = query.filter(KBArticle.status == status)

        if visibility:
            query = query.filter(KBArticle.visibility == visibility)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    KBArticle.title.ilike(search_term),
                    KBArticle.content.ilike(search_term),
                    KBArticle.search_keywords.ilike(search_term),
                    KBArticle.excerpt.ilike(search_term),
                )
            )

        query = query.order_by(KBArticle.created_at.desc())
        return query.offset(offset).limit(limit).all()

    def list_articles_with_stats(
        self,
        filters: Optional[KBArticleFilters] = None,
        pagination: Optional[PaginationParams] = None,
        sort_by: str = "updated_at",
        sort_dir: str = "desc",
    ) -> KBListResult:
        """List KB articles with filtering, pagination, and aggregate stats.

        This is the primary method for the KB list page - it returns everything
        needed in a single call to avoid N+1 queries.

        Args:
            filters: Optional filters for search, status, category.
            pagination: Pagination parameters (offset, limit).
            sort_by: Field to sort by (default: updated_at).
            sort_dir: Sort direction ('asc' or 'desc').

        Returns:
            KBListResult with items, total, stats, categories, and category_counts.
        """
        filters = filters or KBArticleFilters()
        pagination = pagination or PaginationParams(offset=0, limit=25)

        # Build base query
        query = self.db.query(KBArticle)

        # Apply filters
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    KBArticle.title.ilike(search_term),
                    KBArticle.content.ilike(search_term),
                    KBArticle.search_keywords.ilike(search_term),
                )
            )

        if filters.status:
            query = query.filter(KBArticle.status == filters.status)

        if filters.category_id:
            query = query.filter(KBArticle.category_id == filters.category_id)

        if filters.visibility:
            query = query.filter(KBArticle.visibility == filters.visibility)

        # Get total count
        total = query.count()

        # Apply sorting
        sort_column = getattr(KBArticle, sort_by, KBArticle.updated_at)
        if sort_dir == "desc":
            sort_column = sort_column.desc()
        query = query.order_by(sort_column)

        # Apply pagination
        items = query.offset(pagination.offset).limit(pagination.limit).all()

        # Get stats (single optimized query using conditional aggregation)
        stats_query = self.db.query(
            func.count(KBArticle.id).filter(
                KBArticle.status == ArticleStatus.PUBLISHED.value
            ).label("published"),
            func.count(KBArticle.id).filter(
                KBArticle.status == ArticleStatus.DRAFT.value
            ).label("draft"),
            func.count(KBArticle.id).filter(
                KBArticle.status == ArticleStatus.ARCHIVED.value
            ).label("archived"),
            func.coalesce(func.sum(KBArticle.view_count), 0).label("total_views"),
        ).first()

        stats = KBArticleStats(
            published_count=stats_query.published or 0,
            draft_count=stats_query.draft or 0,
            archived_count=stats_query.archived or 0,
            total_views=stats_query.total_views or 0,
        )

        # Get categories with counts (single query)
        categories = (
            self.db.query(KBCategory)
            .filter(KBCategory.is_active == True)
            .order_by(KBCategory.display_order, KBCategory.name)
            .all()
        )

        # Get category counts in single query
        category_count_query = (
            self.db.query(
                KBArticle.category_id,
                func.count(KBArticle.id).label("count"),
            )
            .filter(KBArticle.category_id.isnot(None))
            .group_by(KBArticle.category_id)
            .all()
        )
        category_counts = {row.category_id: row.count for row in category_count_query}

        return KBListResult(
            items=items,
            total=total,
            stats=stats,
            categories=categories,
            category_counts=category_counts,
        )

    def get_article_with_related(
        self,
        article_id: int,
        increment_view: bool = True,
    ) -> tuple:
        """Get an article with its related articles.

        Args:
            article_id: The article ID.
            increment_view: Whether to increment view count.

        Returns:
            Tuple of (article, related_articles).

        Raises:
            KBArticleNotFoundError: If not found.
        """
        from sqlalchemy.orm import joinedload

        article = (
            self.db.query(KBArticle)
            .options(joinedload(KBArticle.category))
            .filter(KBArticle.id == article_id)
            .first()
        )

        if not article:
            raise KBArticleNotFoundError(article_id)

        # Increment view count
        if increment_view:
            article.view_count = (article.view_count or 0) + 1
            self.db.flush()

        # Get related articles
        related_articles = []
        if article.related_article_ids:
            related_articles = (
                self.db.query(KBArticle)
                .filter(
                    KBArticle.id.in_(article.related_article_ids),
                    KBArticle.status == ArticleStatus.PUBLISHED.value,
                )
                .all()
            )

        return article, related_articles

    def get_categories_with_counts(self) -> list:
        """Get all active categories with their article counts.

        Returns:
            List of tuples (category, article_count).
        """
        categories = (
            self.db.query(KBCategory)
            .filter(KBCategory.is_active == True)
            .order_by(KBCategory.display_order, KBCategory.name)
            .all()
        )

        # Get counts in single query
        count_query = (
            self.db.query(
                KBArticle.category_id,
                func.count(KBArticle.id).label("count"),
            )
            .filter(KBArticle.category_id.isnot(None))
            .group_by(KBArticle.category_id)
            .all()
        )
        counts = {row.category_id: row.count for row in count_query}

        return [(cat, counts.get(cat.id, 0)) for cat in categories]

    def get_article(self, article_id: int) -> KBArticle:
        """Get an article by ID.

        Args:
            article_id: The article ID.

        Returns:
            KBArticle instance.

        Raises:
            KBArticleNotFoundError: If not found.
        """
        article = (
            self.db.query(KBArticle)
            .filter(KBArticle.id == article_id)
            .first()
        )
        if not article:
            raise KBArticleNotFoundError(article_id)
        return article

    def get_article_by_slug(self, slug: str) -> Optional[KBArticle]:
        """Get an article by slug.

        Args:
            slug: The article slug.

        Returns:
            KBArticle instance or None.
        """
        return (
            self.db.query(KBArticle)
            .filter(KBArticle.slug == slug)
            .first()
        )

    def search_articles(
        self,
        query: str,
        visibility: Optional[str] = None,
        limit: int = 20,
    ) -> List[KBArticle]:
        """Search published articles.

        Args:
            query: Search query.
            visibility: Filter by visibility.
            limit: Maximum number of results.

        Returns:
            List of matching KBArticle instances.
        """
        search_term = f"%{query}%"
        db_query = (
            self.db.query(KBArticle)
            .filter(
                KBArticle.status == ArticleStatus.PUBLISHED.value,
                or_(
                    KBArticle.title.ilike(search_term),
                    KBArticle.content.ilike(search_term),
                    KBArticle.search_keywords.ilike(search_term),
                    KBArticle.excerpt.ilike(search_term),
                ),
            )
        )

        if visibility:
            db_query = db_query.filter(KBArticle.visibility == visibility)
        else:
            # Default to public articles
            db_query = db_query.filter(
                KBArticle.visibility == ArticleVisibility.PUBLIC.value
            )

        return db_query.order_by(KBArticle.view_count.desc()).limit(limit).all()

    # -------------------------------------------------------------------------
    # Article Mutations
    # -------------------------------------------------------------------------

    def create_article(self, data: KBArticleCreate) -> KBArticle:
        """Create a new KB article.

        Args:
            data: Article creation data.

        Returns:
            Created KBArticle instance.

        Raises:
            DuplicateSlugError: If slug already exists.
        """
        # Generate slug if not provided
        slug = data.slug or slugify(data.title)

        # Ensure unique slug
        base_slug = slug
        counter = 1
        while self.get_article_by_slug(slug):
            slug = f"{base_slug}-{counter}"
            counter += 1

        article = KBArticle(
            title=data.title,
            slug=slug,
            content=data.content,
            category_id=data.category_id,
            excerpt=data.excerpt,
            visibility=data.visibility,
            search_keywords=data.search_keywords,
            related_article_ids=data.related_article_ids if data.related_article_ids else None,
            team_ids=data.team_ids if data.team_ids else None,
            status=ArticleStatus.DRAFT.value,
            version=1,
            view_count=0,
            helpful_count=0,
            not_helpful_count=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        if self.principal:
            article.created_by_id = getattr(self.principal, "id", None)

        self.db.add(article)
        self.db.flush()
        return article

    def update_article(
        self,
        article_id: int,
        data: KBArticleUpdate,
    ) -> KBArticle:
        """Update a KB article.

        Args:
            article_id: The article ID.
            data: Update data.

        Returns:
            Updated KBArticle instance.

        Raises:
            KBArticleNotFoundError: If not found.
            DuplicateSlugError: If new slug conflicts.
        """
        article = self.get_article(article_id)

        if data.slug is not None and data.slug != article.slug:
            existing = self.get_article_by_slug(data.slug)
            if existing:
                raise DuplicateSlugError(data.slug, "article")
            article.slug = data.slug

        if data.title is not None:
            article.title = data.title

        if data.content is not None:
            article.content = data.content
            # Increment version on content change
            article.version = (article.version or 1) + 1

        if data.category_id is not None:
            article.category_id = data.category_id

        if data.excerpt is not None:
            article.excerpt = data.excerpt

        if data.visibility is not None:
            article.visibility = data.visibility

        if data.search_keywords is not None:
            article.search_keywords = data.search_keywords

        if data.related_article_ids is not None:
            article.related_article_ids = data.related_article_ids if data.related_article_ids else None

        if data.team_ids is not None:
            article.team_ids = data.team_ids if data.team_ids else None

        article.updated_at = datetime.now(timezone.utc)

        if self.principal:
            article.updated_by_id = getattr(self.principal, "id", None)

        self.db.flush()
        return article

    def publish_article(self, article_id: int) -> KBArticle:
        """Publish an article.

        Args:
            article_id: The article ID.

        Returns:
            Updated KBArticle instance.
        """
        article = self.get_article(article_id)
        article.status = ArticleStatus.PUBLISHED.value
        article.published_at = datetime.now(timezone.utc)
        article.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return article

    def unpublish_article(self, article_id: int) -> KBArticle:
        """Unpublish an article (set to draft).

        Args:
            article_id: The article ID.

        Returns:
            Updated KBArticle instance.
        """
        article = self.get_article(article_id)
        article.status = ArticleStatus.DRAFT.value
        article.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return article

    def archive_article(self, article_id: int) -> KBArticle:
        """Archive an article.

        Args:
            article_id: The article ID.

        Returns:
            Updated KBArticle instance.
        """
        article = self.get_article(article_id)
        article.status = ArticleStatus.ARCHIVED.value
        article.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return article

    def delete_article(self, article_id: int) -> bool:
        """Delete an article.

        Args:
            article_id: The article ID.

        Returns:
            True if deleted.

        Raises:
            KBArticleNotFoundError: If not found.
        """
        article = self.get_article(article_id)
        self.db.delete(article)
        self.db.flush()
        return True

    # -------------------------------------------------------------------------
    # Attachments
    # -------------------------------------------------------------------------

    def add_attachment(
        self,
        article_id: int,
        data: KBAttachmentData,
    ) -> KBArticleAttachment:
        """Add an attachment to an article.

        Args:
            article_id: The article ID.
            data: Attachment data.

        Returns:
            Created KBArticleAttachment instance.
        """
        # Verify article exists
        self.get_article(article_id)

        # Get next display order
        max_order = (
            self.db.query(func.max(KBArticleAttachment.display_order))
            .filter(KBArticleAttachment.article_id == article_id)
            .scalar()
        )
        display_order = (max_order or 0) + 1

        attachment = KBArticleAttachment(
            article_id=article_id,
            filename=data.filename,
            url=data.url,
            mime_type=data.mime_type,
            size_bytes=data.size_bytes,
            display_order=display_order,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(attachment)
        self.db.flush()
        return attachment

    def remove_attachment(self, article_id: int, attachment_id: int) -> bool:
        """Remove an attachment from an article.

        Args:
            article_id: The article ID.
            attachment_id: The attachment ID.

        Returns:
            True if removed.
        """
        attachment = (
            self.db.query(KBArticleAttachment)
            .filter(
                KBArticleAttachment.id == attachment_id,
                KBArticleAttachment.article_id == article_id,
            )
            .first()
        )
        if attachment:
            self.db.delete(attachment)
            self.db.flush()
            return True
        return False

    def reorder_attachments(
        self,
        article_id: int,
        attachment_ids: List[int],
    ) -> None:
        """Reorder article attachments.

        Args:
            article_id: The article ID.
            attachment_ids: List of attachment IDs in desired order.
        """
        for order, att_id in enumerate(attachment_ids):
            attachment = (
                self.db.query(KBArticleAttachment)
                .filter(
                    KBArticleAttachment.id == att_id,
                    KBArticleAttachment.article_id == article_id,
                )
                .first()
            )
            if attachment:
                attachment.display_order = order
        self.db.flush()

    # -------------------------------------------------------------------------
    # Feedback
    # -------------------------------------------------------------------------

    def record_helpful(
        self,
        article_id: int,
        is_helpful: bool,
        feedback_text: Optional[str] = None,
        party_id: Optional[int] = None,
        agent_id: Optional[int] = None,
    ) -> KBArticleFeedback:
        """Record article helpfulness feedback.

        Args:
            article_id: The article ID.
            is_helpful: Whether the article was helpful.
            feedback_text: Optional feedback text.
            party_id: Optional party ID.
            agent_id: Optional agent ID.

        Returns:
            Created KBArticleFeedback instance.
        """
        article = self.get_article(article_id)

        feedback = KBArticleFeedback(
            article_id=article_id,
            is_helpful=is_helpful,
            feedback_text=feedback_text,
            party_id=party_id,
            agent_party_id=agent_id,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(feedback)

        # Update article counts
        if is_helpful:
            article.helpful_count = (article.helpful_count or 0) + 1
        else:
            article.not_helpful_count = (article.not_helpful_count or 0) + 1

        self.db.flush()
        return feedback

    def get_feedback(self, article_id: int) -> List[KBArticleFeedback]:
        """Get all feedback for an article.

        Args:
            article_id: The article ID.

        Returns:
            List of KBArticleFeedback instances.
        """
        return (
            self.db.query(KBArticleFeedback)
            .filter(KBArticleFeedback.article_id == article_id)
            .order_by(KBArticleFeedback.created_at.desc())
            .all()
        )

    def get_helpfulness_stats(self, article_id: int) -> KBHelpfulnessStats:
        """Get helpfulness statistics for an article.

        Args:
            article_id: The article ID.

        Returns:
            KBHelpfulnessStats instance.
        """
        article = self.get_article(article_id)

        helpful = article.helpful_count or 0
        not_helpful = article.not_helpful_count or 0
        total = helpful + not_helpful
        helpful_pct = (helpful / total * 100) if total > 0 else 0.0

        return KBHelpfulnessStats(
            article_id=article_id,
            helpful_count=helpful,
            not_helpful_count=not_helpful,
            total_count=total,
            helpful_pct=round(helpful_pct, 1),
        )

    # -------------------------------------------------------------------------
    # Analytics
    # -------------------------------------------------------------------------

    def record_view(self, article_id: int) -> None:
        """Record an article view.

        Args:
            article_id: The article ID.
        """
        article = self.get_article(article_id)
        article.view_count = (article.view_count or 0) + 1
        self.db.flush()

    def get_popular_articles(self, limit: int = 10) -> List[KBArticle]:
        """Get most viewed published articles.

        Args:
            limit: Maximum number of results.

        Returns:
            List of KBArticle instances.
        """
        return (
            self.db.query(KBArticle)
            .filter(KBArticle.status == ArticleStatus.PUBLISHED.value)
            .order_by(KBArticle.view_count.desc())
            .limit(limit)
            .all()
        )

    def get_low_rated_articles(self, threshold: float = 50.0) -> List[KBArticle]:
        """Get articles with low helpfulness rating.

        Args:
            threshold: Helpfulness percentage threshold.

        Returns:
            List of KBArticle instances below threshold.
        """
        # Get all published articles with feedback
        articles = (
            self.db.query(KBArticle)
            .filter(
                KBArticle.status == ArticleStatus.PUBLISHED.value,
                (KBArticle.helpful_count + KBArticle.not_helpful_count) > 0,
            )
            .all()
        )

        low_rated = []
        for article in articles:
            stats = self.get_helpfulness_stats(article.id)
            if stats.helpful_pct < threshold:
                low_rated.append(article)

        return low_rated

    def get_recent_articles(
        self,
        status: Optional[str] = None,
        limit: int = 10,
    ) -> List[KBArticle]:
        """Get recently updated articles.

        Args:
            status: Filter by status.
            limit: Maximum number of results.

        Returns:
            List of KBArticle instances.
        """
        query = self.db.query(KBArticle)

        if status:
            query = query.filter(KBArticle.status == status)

        return query.order_by(KBArticle.updated_at.desc()).limit(limit).all()
