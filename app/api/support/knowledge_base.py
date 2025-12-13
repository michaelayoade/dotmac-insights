"""Knowledge Base API endpoints."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.database import get_db
from app.models.support_kb import (
    KBCategory,
    KBArticle,
    KBArticleAttachment,
    KBArticleFeedback,
    ArticleStatus,
    ArticleVisibility,
)
from app.auth import Require

router = APIRouter()


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class CategoryCreateRequest(BaseModel):
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    parent_id: Optional[int] = None
    display_order: int = 100
    visibility: str = ArticleVisibility.PUBLIC.value
    is_active: bool = True


class CategoryUpdateRequest(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    parent_id: Optional[int] = None
    display_order: Optional[int] = None
    visibility: Optional[str] = None
    is_active: Optional[bool] = None


class ArticleCreateRequest(BaseModel):
    title: str
    slug: Optional[str] = None
    category_id: Optional[int] = None
    content: str
    excerpt: Optional[str] = None
    status: str = ArticleStatus.DRAFT.value
    visibility: str = ArticleVisibility.PUBLIC.value
    search_keywords: Optional[str] = None
    team_ids: Optional[List[int]] = None
    related_article_ids: Optional[List[int]] = None


class ArticleUpdateRequest(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    category_id: Optional[int] = None
    content: Optional[str] = None
    excerpt: Optional[str] = None
    status: Optional[str] = None
    visibility: Optional[str] = None
    search_keywords: Optional[str] = None
    team_ids: Optional[List[int]] = None
    related_article_ids: Optional[List[int]] = None


class AttachmentCreateRequest(BaseModel):
    filename: str
    url: str
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None


class FeedbackCreateRequest(BaseModel):
    is_helpful: bool
    feedback_text: Optional[str] = None


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')


# =============================================================================
# CATEGORIES
# =============================================================================

@router.get("/kb/categories", dependencies=[Depends(Require("support:kb:read"))])
def list_categories(
    parent_id: Optional[int] = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List knowledge base categories."""
    query = db.query(KBCategory)

    if not include_inactive:
        query = query.filter(KBCategory.is_active == True)

    if parent_id is not None:
        query = query.filter(KBCategory.parent_id == parent_id)
    else:
        # Get root categories by default
        query = query.filter(KBCategory.parent_id.is_(None))

    categories = query.order_by(KBCategory.display_order, KBCategory.name).all()

    def serialize_category(cat: KBCategory, depth: int = 0) -> Dict[str, Any]:
        result = {
            "id": cat.id,
            "name": cat.name,
            "slug": cat.slug,
            "description": cat.description,
            "icon": cat.icon,
            "parent_id": cat.parent_id,
            "display_order": cat.display_order,
            "visibility": cat.visibility,
            "is_active": cat.is_active,
            "article_count": len(cat.articles),
        }
        if depth < 2:  # Limit recursion depth
            result["children"] = [
                serialize_category(child, depth + 1)
                for child in cat.children
                if include_inactive or child.is_active
            ]
        return result

    return [serialize_category(c) for c in categories]


@router.post("/kb/categories", dependencies=[Depends(Require("support:kb:write"))], status_code=201)
def create_category(
    payload: CategoryCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a knowledge base category."""
    slug = payload.slug or slugify(payload.name)

    # Check slug uniqueness
    existing = db.query(KBCategory).filter(KBCategory.slug == slug).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Category with slug '{slug}' already exists")

    # Validate visibility
    try:
        ArticleVisibility(payload.visibility)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid visibility: {payload.visibility}")

    category = KBCategory(
        name=payload.name,
        slug=slug,
        description=payload.description,
        icon=payload.icon,
        parent_id=payload.parent_id,
        display_order=payload.display_order,
        visibility=payload.visibility,
        is_active=payload.is_active,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return {"id": category.id, "slug": category.slug}


@router.get("/kb/categories/{category_id}", dependencies=[Depends(Require("support:kb:read"))])
def get_category(
    category_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get category details."""
    category = db.query(KBCategory).filter(KBCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    return {
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "description": category.description,
        "icon": category.icon,
        "parent_id": category.parent_id,
        "display_order": category.display_order,
        "visibility": category.visibility,
        "is_active": category.is_active,
        "article_count": len(category.articles),
        "children": [
            {"id": c.id, "name": c.name, "slug": c.slug}
            for c in category.children
        ],
        "created_at": category.created_at.isoformat() if category.created_at else None,
        "updated_at": category.updated_at.isoformat() if category.updated_at else None,
    }


@router.patch("/kb/categories/{category_id}", dependencies=[Depends(Require("support:kb:write"))])
def update_category(
    category_id: int,
    payload: CategoryUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a category."""
    category = db.query(KBCategory).filter(KBCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    if payload.name is not None:
        category.name = payload.name
    if payload.slug is not None:
        existing = db.query(KBCategory).filter(
            KBCategory.slug == payload.slug,
            KBCategory.id != category_id
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Category with slug '{payload.slug}' already exists")
        category.slug = payload.slug
    if payload.description is not None:
        category.description = payload.description
    if payload.icon is not None:
        category.icon = payload.icon
    if payload.parent_id is not None:
        category.parent_id = payload.parent_id
    if payload.display_order is not None:
        category.display_order = payload.display_order
    if payload.visibility is not None:
        category.visibility = payload.visibility
    if payload.is_active is not None:
        category.is_active = payload.is_active

    db.commit()
    db.refresh(category)
    return {"id": category.id, "slug": category.slug}


@router.delete("/kb/categories/{category_id}", dependencies=[Depends(Require("support:kb:write"))])
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Delete a category."""
    category = db.query(KBCategory).filter(KBCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    if category.articles:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete category: {len(category.articles)} articles reference it"
        )
    if category.children:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete category: {len(category.children)} child categories exist"
        )

    db.delete(category)
    db.commit()
    return Response(status_code=204)


# =============================================================================
# ARTICLES
# =============================================================================

@router.get("/kb/articles", dependencies=[Depends(Require("support:kb:read"))])
def list_articles(
    category_id: Optional[int] = None,
    status: Optional[str] = None,
    visibility: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List knowledge base articles."""
    query = db.query(KBArticle)

    if category_id:
        query = query.filter(KBArticle.category_id == category_id)
    if status:
        query = query.filter(KBArticle.status == status)
    if visibility:
        query = query.filter(KBArticle.visibility == visibility)
    if search:
        search_term = f"%{search}%"
        query = query.filter(or_(
            KBArticle.title.ilike(search_term),
            KBArticle.content.ilike(search_term),
            KBArticle.search_keywords.ilike(search_term),
        ))

    total = query.count()
    articles = query.order_by(KBArticle.updated_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": a.id,
                "title": a.title,
                "slug": a.slug,
                "category_id": a.category_id,
                "category_name": a.category.name if a.category else None,
                "excerpt": a.excerpt,
                "status": a.status,
                "visibility": a.visibility,
                "view_count": a.view_count,
                "helpful_count": a.helpful_count,
                "not_helpful_count": a.not_helpful_count,
                "version": a.version,
                "published_at": a.published_at.isoformat() if a.published_at else None,
                "updated_at": a.updated_at.isoformat() if a.updated_at else None,
            }
            for a in articles
        ],
    }


@router.post("/kb/articles", dependencies=[Depends(Require("support:kb:write"))], status_code=201)
def create_article(
    payload: ArticleCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a knowledge base article."""
    slug = payload.slug or slugify(payload.title)

    # Check slug uniqueness
    existing = db.query(KBArticle).filter(KBArticle.slug == slug).first()
    if existing:
        # Append a number if slug exists
        base_slug = slug
        counter = 1
        while existing:
            slug = f"{base_slug}-{counter}"
            existing = db.query(KBArticle).filter(KBArticle.slug == slug).first()
            counter += 1

    # Validate status and visibility
    try:
        ArticleStatus(payload.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {payload.status}")
    try:
        ArticleVisibility(payload.visibility)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid visibility: {payload.visibility}")

    article = KBArticle(
        title=payload.title,
        slug=slug,
        category_id=payload.category_id,
        content=payload.content,
        excerpt=payload.excerpt or payload.content[:200] + "..." if len(payload.content) > 200 else payload.content,
        status=payload.status,
        visibility=payload.visibility,
        search_keywords=payload.search_keywords,
        team_ids=payload.team_ids,
        related_article_ids=payload.related_article_ids,
    )

    if payload.status == ArticleStatus.PUBLISHED.value:
        article.published_at = datetime.utcnow()

    db.add(article)
    db.commit()
    db.refresh(article)
    return {"id": article.id, "slug": article.slug}


@router.get("/kb/articles/{article_id}", dependencies=[Depends(Require("support:kb:read"))])
def get_article(
    article_id: int,
    increment_views: bool = True,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get article details."""
    article = db.query(KBArticle).filter(KBArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    if increment_views:
        article.view_count += 1
        db.commit()

    return {
        "id": article.id,
        "title": article.title,
        "slug": article.slug,
        "category_id": article.category_id,
        "category_name": article.category.name if article.category else None,
        "content": article.content,
        "excerpt": article.excerpt,
        "status": article.status,
        "visibility": article.visibility,
        "search_keywords": article.search_keywords,
        "view_count": article.view_count,
        "helpful_count": article.helpful_count,
        "not_helpful_count": article.not_helpful_count,
        "helpfulness_score": round(
            article.helpful_count / (article.helpful_count + article.not_helpful_count) * 100
            if (article.helpful_count + article.not_helpful_count) > 0 else 0,
            1
        ),
        "version": article.version,
        "team_ids": article.team_ids,
        "related_article_ids": article.related_article_ids,
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "attachments": [
            {
                "id": att.id,
                "filename": att.filename,
                "url": att.url,
                "mime_type": att.mime_type,
                "size_bytes": att.size_bytes,
            }
            for att in article.attachments
        ],
        "created_at": article.created_at.isoformat() if article.created_at else None,
        "updated_at": article.updated_at.isoformat() if article.updated_at else None,
    }


@router.patch("/kb/articles/{article_id}", dependencies=[Depends(Require("support:kb:write"))])
def update_article(
    article_id: int,
    payload: ArticleUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update an article."""
    article = db.query(KBArticle).filter(KBArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    if payload.title is not None:
        article.title = payload.title
    if payload.slug is not None:
        existing = db.query(KBArticle).filter(
            KBArticle.slug == payload.slug,
            KBArticle.id != article_id
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Article with slug '{payload.slug}' already exists")
        article.slug = payload.slug
    if payload.category_id is not None:
        article.category_id = payload.category_id
    if payload.content is not None:
        article.content = payload.content
        article.version += 1
    if payload.excerpt is not None:
        article.excerpt = payload.excerpt
    if payload.status is not None:
        article.status = payload.status
    if payload.visibility is not None:
        article.visibility = payload.visibility
    if payload.search_keywords is not None:
        article.search_keywords = payload.search_keywords
    if payload.team_ids is not None:
        article.team_ids = payload.team_ids
    if payload.related_article_ids is not None:
        article.related_article_ids = payload.related_article_ids

    db.commit()
    db.refresh(article)
    return {"id": article.id, "slug": article.slug, "version": article.version}


@router.delete("/kb/articles/{article_id}", dependencies=[Depends(Require("support:kb:write"))])
def delete_article(
    article_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Delete an article."""
    article = db.query(KBArticle).filter(KBArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    db.delete(article)
    db.commit()
    return Response(status_code=204)


@router.post("/kb/articles/{article_id}/publish", dependencies=[Depends(Require("support:kb:write"))])
def publish_article(
    article_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Publish a draft article."""
    article = db.query(KBArticle).filter(KBArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    article.status = ArticleStatus.PUBLISHED.value
    article.published_at = datetime.utcnow()
    db.commit()
    return {"id": article.id, "status": article.status, "published_at": article.published_at.isoformat()}


@router.post("/kb/articles/{article_id}/archive", dependencies=[Depends(Require("support:kb:write"))])
def archive_article(
    article_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Archive an article."""
    article = db.query(KBArticle).filter(KBArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    article.status = ArticleStatus.ARCHIVED.value
    db.commit()
    return {"id": article.id, "status": article.status}


# =============================================================================
# ARTICLE ATTACHMENTS
# =============================================================================

@router.post("/kb/articles/{article_id}/attachments", dependencies=[Depends(Require("support:kb:write"))], status_code=201)
def add_attachment(
    article_id: int,
    payload: AttachmentCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add an attachment to an article."""
    article = db.query(KBArticle).filter(KBArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    attachment = KBArticleAttachment(
        article_id=article_id,
        filename=payload.filename,
        url=payload.url,
        mime_type=payload.mime_type,
        size_bytes=payload.size_bytes,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return {"id": attachment.id}


@router.delete(
    "/kb/articles/{article_id}/attachments/{attachment_id}",
    dependencies=[Depends(Require("support:kb:write"))],
)
def remove_attachment(
    article_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Remove an attachment from an article."""
    attachment = db.query(KBArticleAttachment).filter(
        KBArticleAttachment.id == attachment_id,
        KBArticleAttachment.article_id == article_id
    ).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    db.delete(attachment)
    db.commit()
    return Response(status_code=204)


# =============================================================================
# ARTICLE FEEDBACK
# =============================================================================

@router.post("/kb/articles/{article_id}/feedback", dependencies=[Depends(Require("support:kb:read"))], status_code=201)
def submit_feedback(
    article_id: int,
    payload: FeedbackCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Submit feedback on an article."""
    article = db.query(KBArticle).filter(KBArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    feedback = KBArticleFeedback(
        article_id=article_id,
        is_helpful=payload.is_helpful,
        feedback_text=payload.feedback_text,
    )
    db.add(feedback)

    # Update article counters
    if payload.is_helpful:
        article.helpful_count += 1
    else:
        article.not_helpful_count += 1

    db.commit()
    db.refresh(feedback)
    return {"id": feedback.id}


# =============================================================================
# PUBLIC ENDPOINTS (No Auth Required)
# =============================================================================

@router.get("/kb/public/categories")
def list_public_categories(
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List public knowledge base categories (no auth required)."""
    categories = db.query(KBCategory).filter(
        KBCategory.is_active == True,
        KBCategory.visibility == ArticleVisibility.PUBLIC.value,
        KBCategory.parent_id.is_(None),
    ).order_by(KBCategory.display_order, KBCategory.name).all()

    def serialize(cat: KBCategory) -> Dict[str, Any]:
        return {
            "id": cat.id,
            "name": cat.name,
            "slug": cat.slug,
            "description": cat.description,
            "icon": cat.icon,
            "children": [
                serialize(c) for c in cat.children
                if c.is_active and c.visibility == ArticleVisibility.PUBLIC.value
            ],
        }

    return [serialize(c) for c in categories]


@router.get("/kb/public/articles")
def search_public_articles(
    category_slug: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=20, le=50),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Search public articles (no auth required)."""
    query = db.query(KBArticle).filter(
        KBArticle.status == ArticleStatus.PUBLISHED.value,
        KBArticle.visibility == ArticleVisibility.PUBLIC.value,
    )

    if category_slug:
        category = db.query(KBCategory).filter(KBCategory.slug == category_slug).first()
        if category:
            query = query.filter(KBArticle.category_id == category.id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(or_(
            KBArticle.title.ilike(search_term),
            KBArticle.content.ilike(search_term),
            KBArticle.search_keywords.ilike(search_term),
        ))

    total = query.count()
    articles = query.order_by(KBArticle.view_count.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "data": [
            {
                "id": a.id,
                "title": a.title,
                "slug": a.slug,
                "excerpt": a.excerpt,
                "category_name": a.category.name if a.category else None,
                "view_count": a.view_count,
            }
            for a in articles
        ],
    }


@router.get("/kb/public/articles/{slug}")
def get_public_article(
    slug: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a public article by slug (no auth required)."""
    article = db.query(KBArticle).filter(
        KBArticle.slug == slug,
        KBArticle.status == ArticleStatus.PUBLISHED.value,
        KBArticle.visibility == ArticleVisibility.PUBLIC.value,
    ).first()

    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Increment view count
    article.view_count += 1
    db.commit()

    return {
        "id": article.id,
        "title": article.title,
        "slug": article.slug,
        "content": article.content,
        "category_name": article.category.name if article.category else None,
        "view_count": article.view_count,
        "helpful_count": article.helpful_count,
        "not_helpful_count": article.not_helpful_count,
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "attachments": [
            {"filename": att.filename, "url": att.url}
            for att in article.attachments
        ],
    }
