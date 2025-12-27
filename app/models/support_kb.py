"""Knowledge Base models: articles, categories, and feedback."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.agent import Agent


class ArticleStatus(str, Enum):
    """Status of a knowledge base article."""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ArticleVisibility(str, Enum):
    """Visibility scope of an article."""
    PUBLIC = "public"         # Anyone can view
    INTERNAL = "internal"     # Only agents
    RESTRICTED = "restricted" # Specific teams only


class KBCategory(Base):
    """Knowledge base category for organizing articles.

    Supports hierarchical categories through parent_id.
    """

    __tablename__ = "kb_categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Hierarchical structure
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kb_categories.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Display order (lower = first)
    display_order: Mapped[int] = mapped_column(Integer, default=100)

    # Visibility
    visibility: Mapped[str] = mapped_column(
        String(20), default=ArticleVisibility.PUBLIC.value, index=True
    )

    # Flags
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    parent: Mapped[Optional["KBCategory"]] = relationship(
        "KBCategory", remote_side=[id], back_populates="children"
    )
    children: Mapped[List["KBCategory"]] = relationship(
        "KBCategory", back_populates="parent", cascade="all, delete-orphan"
    )
    articles: Mapped[List["KBArticle"]] = relationship(back_populates="category")

    def __repr__(self) -> str:
        return f"<KBCategory {self.slug}>"


class KBArticle(Base):
    """Knowledge base article.

    Supports Markdown content, versioning, and helpfulness tracking.
    """

    __tablename__ = "kb_articles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)

    # Category
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kb_categories.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Content (Markdown)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Status and visibility
    status: Mapped[str] = mapped_column(String(20), default=ArticleStatus.DRAFT.value, index=True)
    visibility: Mapped[str] = mapped_column(
        String(20), default=ArticleVisibility.PUBLIC.value, index=True
    )

    # Search optimization
    search_keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metrics
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    helpful_count: Mapped[int] = mapped_column(Integer, default=0)
    not_helpful_count: Mapped[int] = mapped_column(Integer, default=0)

    # Versioning
    version: Mapped[int] = mapped_column(Integer, default=1)

    # Publication
    published_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Restricted visibility - team IDs that can access (JSON array)
    team_ids: Mapped[Optional[List[int]]] = mapped_column(JSON, nullable=True)

    # Related articles (JSON array of article IDs)
    related_article_ids: Mapped[Optional[List[int]]] = mapped_column(JSON, nullable=True)

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    category: Mapped[Optional["KBCategory"]] = relationship(back_populates="articles")
    attachments: Mapped[List["KBArticleAttachment"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )
    feedback: Mapped[List["KBArticleFeedback"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<KBArticle {self.slug}>"


class KBArticleAttachment(Base):
    """Attachment for a knowledge base article."""

    __tablename__ = "kb_article_attachments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    article_id: Mapped[int] = mapped_column(
        ForeignKey("kb_articles.id", ondelete="CASCADE"), nullable=False, index=True
    )

    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Display order
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    article: Mapped["KBArticle"] = relationship(back_populates="attachments")

    def __repr__(self) -> str:
        return f"<KBArticleAttachment {self.filename}>"


class KBArticleFeedback(Base):
    """Feedback on a knowledge base article."""

    __tablename__ = "kb_article_feedback"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    article_id: Mapped[int] = mapped_column(
        ForeignKey("kb_articles.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Was it helpful?
    is_helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # Optional feedback text
    feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Who gave feedback (one of these, or anonymous)
    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    agent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)

    # Relationships
    article: Mapped["KBArticle"] = relationship(back_populates="feedback")

    def __repr__(self) -> str:
        return f"<KBArticleFeedback article={self.article_id} helpful={self.is_helpful}>"
