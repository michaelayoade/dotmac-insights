"""Knowledge Base API endpoints.

Refactored to use KnowledgeBaseService for all business logic.
"""
from __future__ import annotations

from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import Require, get_principal, Principal
from app.models.support_kb import ArticleStatus, ArticleVisibility
from app.services.support import (
    KnowledgeBaseService,
    KBCategoryCreate,
    KBCategoryUpdate,
    KBArticleCreate,
    KBArticleUpdate,
    KBAttachmentData,
    KBCategoryNotFoundError,
    KBArticleNotFoundError,
    DuplicateSlugError,
)

router = APIRouter()


# =============================================================================
# DEPENDENCIES
# =============================================================================

def get_kb_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> KnowledgeBaseService:
    """Dependency to get KnowledgeBaseService instance."""
    return KnowledgeBaseService(db, principal)


# =============================================================================
# PYDANTIC MODELS (API Input Validation)
# =============================================================================

class CategoryCreateRequest(BaseModel):
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    parent_id: Optional[int] = None
    visibility: str = ArticleVisibility.PUBLIC.value


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


class ReorderRequest(BaseModel):
    ids: List[int]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def serialize_category(cat, include_children: bool = True, depth: int = 0):
    """Serialize a category to dict."""
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
        "article_count": len(cat.articles) if hasattr(cat, 'articles') else 0,
    }
    if include_children and depth < 2:
        result["children"] = [
            serialize_category(c, include_children=True, depth=depth + 1)
            for c in (cat.children if hasattr(cat, 'children') else [])
            if c.is_active
        ]
    return result


def serialize_article(a, full: bool = False):
    """Serialize an article to dict."""
    result = {
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
    if full:
        result.update({
            "content": a.content,
            "search_keywords": a.search_keywords,
            "team_ids": a.team_ids,
            "related_article_ids": a.related_article_ids,
            "helpfulness_score": round(
                a.helpful_count / (a.helpful_count + a.not_helpful_count) * 100
                if (a.helpful_count + a.not_helpful_count) > 0 else 0,
                1
            ),
            "attachments": [
                {
                    "id": att.id,
                    "filename": att.filename,
                    "url": att.url,
                    "mime_type": att.mime_type,
                    "size_bytes": att.size_bytes,
                }
                for att in (a.attachments if hasattr(a, 'attachments') else [])
            ],
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })
    return result


# =============================================================================
# CATEGORIES
# =============================================================================

@router.get("/kb/categories", dependencies=[Depends(Require("support:kb:read"))])
def list_categories(
    parent_id: Optional[int] = None,
    include_inactive: bool = False,
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> List[Dict[str, Any]]:
    """List knowledge base categories."""
    categories = service.list_categories(
        parent_id=parent_id,
        active_only=not include_inactive,
    )
    return [serialize_category(c) for c in categories]


@router.get("/kb/categories/tree", dependencies=[Depends(Require("support:kb:read"))])
def get_category_tree(
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> List[Dict[str, Any]]:
    """Get the full category hierarchy as a tree."""
    return service.get_category_tree()


@router.post("/kb/categories", dependencies=[Depends(Require("support:kb:write"))], status_code=201)
def create_category(
    payload: CategoryCreateRequest,
    db: Session = Depends(get_db),
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> Dict[str, Any]:
    """Create a knowledge base category."""
    try:
        data = KBCategoryCreate(
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            icon=payload.icon,
            parent_id=payload.parent_id,
            visibility=payload.visibility,
        )
        category = service.create_category(data)
        db.commit()
        return {"id": category.id, "slug": category.slug}
    except DuplicateSlugError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/kb/categories/{category_id}", dependencies=[Depends(Require("support:kb:read"))])
def get_category(
    category_id: int,
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> Dict[str, Any]:
    """Get category details."""
    try:
        category = service.get_category(category_id)
        result = serialize_category(category, include_children=False)
        result["children"] = [
            {"id": c.id, "name": c.name, "slug": c.slug}
            for c in (category.children if hasattr(category, 'children') else [])
        ]
        result["created_at"] = category.created_at.isoformat() if category.created_at else None
        result["updated_at"] = category.updated_at.isoformat() if category.updated_at else None
        return result
    except KBCategoryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/kb/categories/{category_id}", dependencies=[Depends(Require("support:kb:write"))])
def update_category(
    category_id: int,
    payload: CategoryUpdateRequest,
    db: Session = Depends(get_db),
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> Dict[str, Any]:
    """Update a category."""
    try:
        data = KBCategoryUpdate(
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            icon=payload.icon,
            parent_id=payload.parent_id,
            display_order=payload.display_order,
            visibility=payload.visibility,
            is_active=payload.is_active,
        )
        category = service.update_category(category_id, data)
        db.commit()
        return {"id": category.id, "slug": category.slug}
    except KBCategoryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DuplicateSlugError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/kb/categories/{category_id}", dependencies=[Depends(Require("support:kb:write"))])
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> Response:
    """Delete a category."""
    try:
        category = service.get_category(category_id)

        # Check for articles and children
        if hasattr(category, 'articles') and category.articles:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete category: {len(category.articles)} articles reference it"
            )
        if hasattr(category, 'children') and category.children:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete category: {len(category.children)} child categories exist"
            )

        service.delete_category(category_id)
        db.commit()
        return Response(status_code=204)
    except KBCategoryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/kb/categories/reorder", dependencies=[Depends(Require("support:kb:write"))])
def reorder_categories(
    payload: ReorderRequest,
    db: Session = Depends(get_db),
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> Dict[str, str]:
    """Reorder categories."""
    service.reorder_categories(payload.ids)
    db.commit()
    return {"status": "ok"}


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
    offset: int = Query(default=0, ge=0),
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> Dict[str, Any]:
    """List knowledge base articles."""
    articles = service.list_articles(
        category_id=category_id,
        status=status,
        visibility=visibility,
        search=search,
        limit=limit,
        offset=offset,
    )

    return {
        "total": len(articles),  # Note: For proper pagination, service should return total count
        "limit": limit,
        "offset": offset,
        "data": [serialize_article(a) for a in articles],
    }


@router.post("/kb/articles", dependencies=[Depends(Require("support:kb:write"))], status_code=201)
def create_article(
    payload: ArticleCreateRequest,
    db: Session = Depends(get_db),
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> Dict[str, Any]:
    """Create a knowledge base article."""
    try:
        data = KBArticleCreate(
            title=payload.title,
            slug=payload.slug,
            category_id=payload.category_id,
            content=payload.content,
            excerpt=payload.excerpt or (payload.content[:200] + "..." if len(payload.content) > 200 else payload.content),
            visibility=payload.visibility,
            search_keywords=payload.search_keywords,
            team_ids=payload.team_ids,
            related_article_ids=payload.related_article_ids,
        )
        article = service.create_article(data)
        db.commit()
        return {"id": article.id, "slug": article.slug}
    except DuplicateSlugError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/kb/articles/popular", dependencies=[Depends(Require("support:kb:read"))])
def get_popular_articles(
    limit: int = Query(default=10, le=50),
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> List[Dict[str, Any]]:
    """Get most viewed published articles."""
    articles = service.get_popular_articles(limit=limit)
    return [serialize_article(a) for a in articles]


@router.get("/kb/articles/recent", dependencies=[Depends(Require("support:kb:read"))])
def get_recent_articles(
    status: Optional[str] = None,
    limit: int = Query(default=10, le=50),
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> List[Dict[str, Any]]:
    """Get recently updated articles."""
    articles = service.get_recent_articles(status=status, limit=limit)
    return [serialize_article(a) for a in articles]


@router.get("/kb/articles/low-rated", dependencies=[Depends(Require("support:kb:read"))])
def get_low_rated_articles(
    threshold: float = Query(default=50.0, ge=0, le=100),
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> List[Dict[str, Any]]:
    """Get articles with low helpfulness rating."""
    articles = service.get_low_rated_articles(threshold=threshold)
    return [serialize_article(a) for a in articles]


@router.get("/kb/articles/search", dependencies=[Depends(Require("support:kb:read"))])
def search_articles(
    q: str = Query(..., min_length=1),
    visibility: Optional[str] = None,
    limit: int = Query(default=20, le=50),
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> List[Dict[str, Any]]:
    """Search published articles."""
    articles = service.search_articles(
        query=q,
        visibility=visibility,
        limit=limit,
    )
    return [serialize_article(a) for a in articles]


@router.get("/kb/articles/{article_id}", dependencies=[Depends(Require("support:kb:read"))])
def get_article(
    article_id: int,
    increment_views: bool = True,
    db: Session = Depends(get_db),
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> Dict[str, Any]:
    """Get article details."""
    try:
        article = service.get_article(article_id)

        if increment_views:
            service.record_view(article_id)
            db.commit()

        return serialize_article(article, full=True)
    except KBArticleNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/kb/articles/{article_id}", dependencies=[Depends(Require("support:kb:write"))])
def update_article(
    article_id: int,
    payload: ArticleUpdateRequest,
    db: Session = Depends(get_db),
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> Dict[str, Any]:
    """Update an article."""
    try:
        data = KBArticleUpdate(
            title=payload.title,
            slug=payload.slug,
            category_id=payload.category_id,
            content=payload.content,
            excerpt=payload.excerpt,
            visibility=payload.visibility,
            search_keywords=payload.search_keywords,
            team_ids=payload.team_ids,
            related_article_ids=payload.related_article_ids,
        )
        article = service.update_article(article_id, data)
        db.commit()
        return {"id": article.id, "slug": article.slug, "version": article.version}
    except KBArticleNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DuplicateSlugError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/kb/articles/{article_id}", dependencies=[Depends(Require("support:kb:write"))])
def delete_article(
    article_id: int,
    db: Session = Depends(get_db),
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> Response:
    """Delete an article."""
    try:
        service.delete_article(article_id)
        db.commit()
        return Response(status_code=204)
    except KBArticleNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/kb/articles/{article_id}/publish", dependencies=[Depends(Require("support:kb:write"))])
def publish_article(
    article_id: int,
    db: Session = Depends(get_db),
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> Dict[str, Any]:
    """Publish a draft article."""
    try:
        article = service.publish_article(article_id)
        db.commit()
        return {
            "id": article.id,
            "status": article.status,
            "published_at": article.published_at.isoformat() if article.published_at else None,
        }
    except KBArticleNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/kb/articles/{article_id}/unpublish", dependencies=[Depends(Require("support:kb:write"))])
def unpublish_article(
    article_id: int,
    db: Session = Depends(get_db),
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> Dict[str, Any]:
    """Unpublish an article (set to draft)."""
    try:
        article = service.unpublish_article(article_id)
        db.commit()
        return {"id": article.id, "status": article.status}
    except KBArticleNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/kb/articles/{article_id}/archive", dependencies=[Depends(Require("support:kb:write"))])
def archive_article(
    article_id: int,
    db: Session = Depends(get_db),
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> Dict[str, Any]:
    """Archive an article."""
    try:
        article = service.archive_article(article_id)
        db.commit()
        return {"id": article.id, "status": article.status}
    except KBArticleNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# ARTICLE ATTACHMENTS
# =============================================================================

@router.post("/kb/articles/{article_id}/attachments", dependencies=[Depends(Require("support:kb:write"))], status_code=201)
def add_attachment(
    article_id: int,
    payload: AttachmentCreateRequest,
    db: Session = Depends(get_db),
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> Dict[str, Any]:
    """Add an attachment to an article."""
    try:
        data = KBAttachmentData(
            filename=payload.filename,
            url=payload.url,
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
        )
        attachment = service.add_attachment(article_id, data)
        db.commit()
        return {"id": attachment.id}
    except KBArticleNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete(
    "/kb/articles/{article_id}/attachments/{attachment_id}",
    dependencies=[Depends(Require("support:kb:write"))],
)
def remove_attachment(
    article_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> Response:
    """Remove an attachment from an article."""
    removed = service.remove_attachment(article_id, attachment_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Attachment not found")
    db.commit()
    return Response(status_code=204)


@router.post(
    "/kb/articles/{article_id}/attachments/reorder",
    dependencies=[Depends(Require("support:kb:write"))],
)
def reorder_attachments(
    article_id: int,
    payload: ReorderRequest,
    db: Session = Depends(get_db),
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> Dict[str, str]:
    """Reorder article attachments."""
    service.reorder_attachments(article_id, payload.ids)
    db.commit()
    return {"status": "ok"}


# =============================================================================
# ARTICLE FEEDBACK
# =============================================================================

@router.post("/kb/articles/{article_id}/feedback", dependencies=[Depends(Require("support:kb:read"))], status_code=201)
def submit_feedback(
    article_id: int,
    payload: FeedbackCreateRequest,
    db: Session = Depends(get_db),
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> Dict[str, Any]:
    """Submit feedback on an article."""
    try:
        feedback = service.record_helpful(
            article_id=article_id,
            is_helpful=payload.is_helpful,
            feedback_text=payload.feedback_text,
        )
        db.commit()
        return {"id": feedback.id}
    except KBArticleNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/kb/articles/{article_id}/feedback", dependencies=[Depends(Require("support:kb:read"))])
def get_article_feedback(
    article_id: int,
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> List[Dict[str, Any]]:
    """Get all feedback for an article."""
    try:
        service.get_article(article_id)  # Verify article exists
        feedback = service.get_feedback(article_id)
        return [
            {
                "id": f.id,
                "is_helpful": f.is_helpful,
                "feedback_text": f.feedback_text,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in feedback
        ]
    except KBArticleNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/kb/articles/{article_id}/helpfulness", dependencies=[Depends(Require("support:kb:read"))])
def get_article_helpfulness(
    article_id: int,
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> Dict[str, Any]:
    """Get helpfulness statistics for an article."""
    try:
        stats = service.get_helpfulness_stats(article_id)
        return {
            "article_id": stats.article_id,
            "helpful_count": stats.helpful_count,
            "not_helpful_count": stats.not_helpful_count,
            "total_count": stats.total_count,
            "helpful_pct": stats.helpful_pct,
        }
    except KBArticleNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# PUBLIC ENDPOINTS (No Auth Required)
# =============================================================================

@router.get("/kb/public/categories")
def list_public_categories(
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> List[Dict[str, Any]]:
    """List public knowledge base categories (no auth required)."""
    categories = service.list_categories(
        parent_id=None,
        visibility=ArticleVisibility.PUBLIC.value,
        active_only=True,
    )

    def serialize_public(cat):
        return {
            "id": cat.id,
            "name": cat.name,
            "slug": cat.slug,
            "description": cat.description,
            "icon": cat.icon,
            "children": [
                serialize_public(c) for c in (cat.children if hasattr(cat, 'children') else [])
                if c.is_active and c.visibility == ArticleVisibility.PUBLIC.value
            ],
        }

    return [serialize_public(c) for c in categories]


@router.get("/kb/public/articles")
def search_public_articles(
    category_slug: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=20, le=50),
    offset: int = Query(default=0, ge=0),
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> Dict[str, Any]:
    """Search public articles (no auth required)."""
    category_id = None
    if category_slug:
        category = service.get_category_by_slug(category_slug)
        if category:
            category_id = category.id

    articles = service.list_articles(
        category_id=category_id,
        status=ArticleStatus.PUBLISHED.value,
        visibility=ArticleVisibility.PUBLIC.value,
        search=search,
        limit=limit,
        offset=offset,
    )

    return {
        "total": len(articles),
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
    service: KnowledgeBaseService = Depends(get_kb_service),
) -> Dict[str, Any]:
    """Get a public article by slug (no auth required)."""
    article = service.get_article_by_slug(slug)

    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Only allow published, public articles
    if article.status != ArticleStatus.PUBLISHED.value:
        raise HTTPException(status_code=404, detail="Article not found")
    if article.visibility != ArticleVisibility.PUBLIC.value:
        raise HTTPException(status_code=404, detail="Article not found")

    # Increment view count
    service.record_view(article.id)
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
            for att in (article.attachments if hasattr(article, 'attachments') else [])
        ],
    }
