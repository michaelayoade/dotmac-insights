"""Sync Chatwoot Help Center content to KB models."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Dict, Any

import httpx
import structlog

from app.models.support_kb import KBCategory, KBArticle, ArticleStatus, ArticleVisibility

if TYPE_CHECKING:
    from app.sync.chatwoot import ChatwootSync

logger = structlog.get_logger()


def _map_article_status(chatwoot_status: int) -> str:
    """Map Chatwoot article status to ArticleStatus."""
    status_map = {
        0: ArticleStatus.DRAFT.value,
        1: ArticleStatus.PUBLISHED.value,
        2: ArticleStatus.ARCHIVED.value,
    }
    return status_map.get(chatwoot_status, ArticleStatus.DRAFT.value)


async def sync_help_center(
    sync_client: "ChatwootSync",
    client: httpx.AsyncClient,
    full_sync: bool = False
) -> None:
    """Sync Help Center content from Chatwoot.

    Syncs portals, categories, and articles to KBCategory and KBArticle models.

    Args:
        sync_client: The ChatwootSync instance
        client: HTTP client for API requests
        full_sync: Whether to perform a full sync (ignored - always full)
    """
    sync_client.start_sync("help_center", "full")

    try:
        # Step 1: Fetch all portals
        portals = await _fetch_portals(sync_client, client)
        sync_client.increment_fetched(len(portals))

        for portal in portals:
            portal_slug = portal.get("slug")
            if not portal_slug:
                continue

            # Create or update root category for this portal
            portal_category = await _sync_portal_as_category(sync_client, portal)

            # Step 2: Fetch and sync categories for this portal
            categories = await _fetch_categories(sync_client, client, portal_slug)
            category_map = {}  # chatwoot_id -> local category

            for cat_data in categories:
                category = await _sync_category(sync_client, cat_data, portal_slug, portal_category.id)
                if category:
                    category_map[cat_data.get("id")] = category

            # Step 3: Fetch and sync articles for this portal
            articles = await _fetch_articles(sync_client, client, portal_slug)

            for article_data in articles:
                await _sync_article(sync_client, article_data, portal_slug, category_map)

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "chatwoot_help_center_synced",
            portals=len(portals),
            created=sync_client.current_sync_log.records_created if sync_client.current_sync_log else 0,
            updated=sync_client.current_sync_log.records_updated if sync_client.current_sync_log else 0,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def _fetch_portals(
    sync_client: "ChatwootSync",
    client: httpx.AsyncClient,
) -> List[Dict[str, Any]]:
    """Fetch all Help Center portals."""
    try:
        response = await sync_client._request(
            client,
            "GET",
            f"/accounts/{sync_client.account_id}/portals",
        )
        return response if isinstance(response, list) else response.get("payload", [])
    except Exception as e:
        logger.warning("chatwoot_portals_fetch_failed", error=str(e))
        return []


async def _fetch_categories(
    sync_client: "ChatwootSync",
    client: httpx.AsyncClient,
    portal_slug: str,
) -> List[Dict[str, Any]]:
    """Fetch categories for a portal."""
    try:
        response = await sync_client._request(
            client,
            "GET",
            f"/accounts/{sync_client.account_id}/portals/{portal_slug}/categories",
        )
        return response if isinstance(response, list) else response.get("payload", [])
    except Exception as e:
        logger.warning("chatwoot_categories_fetch_failed", portal=portal_slug, error=str(e))
        return []


async def _fetch_articles(
    sync_client: "ChatwootSync",
    client: httpx.AsyncClient,
    portal_slug: str,
) -> List[Dict[str, Any]]:
    """Fetch articles for a portal."""
    try:
        response = await sync_client._request(
            client,
            "GET",
            f"/accounts/{sync_client.account_id}/portals/{portal_slug}/articles",
        )
        return response if isinstance(response, list) else response.get("payload", [])
    except Exception as e:
        logger.warning("chatwoot_articles_fetch_failed", portal=portal_slug, error=str(e))
        return []


async def _sync_portal_as_category(
    sync_client: "ChatwootSync",
    portal: Dict[str, Any],
) -> KBCategory:
    """Create or update a root KBCategory for a Chatwoot portal."""
    portal_slug = portal.get("slug")
    name = portal.get("name", portal_slug)

    existing = sync_client.db.query(KBCategory).filter(
        KBCategory.chatwoot_portal_slug == portal_slug,
        KBCategory.parent_id.is_(None),  # Root category for portal
    ).first()

    if existing:
        existing.name = name
        existing.description = portal.get("header_text")
        existing.last_synced_at = datetime.now(timezone.utc)
        existing.updated_at = datetime.now(timezone.utc)
        sync_client.increment_updated()
        return existing
    else:
        category = KBCategory(
            name=name,
            slug=f"portal-{portal_slug}",
            description=portal.get("header_text"),
            chatwoot_portal_slug=portal_slug,
            visibility=ArticleVisibility.PUBLIC.value,
            is_active=True,
            last_synced_at=datetime.now(timezone.utc),
        )
        sync_client.db.add(category)
        sync_client.db.flush()  # Get ID for child categories
        sync_client.increment_created()
        return category


async def _sync_category(
    sync_client: "ChatwootSync",
    cat_data: Dict[str, Any],
    portal_slug: str,
    parent_id: int,
) -> KBCategory:
    """Create or update a KBCategory from Chatwoot category."""
    chatwoot_id = cat_data.get("id")
    cat_slug = cat_data.get("slug", f"cat-{chatwoot_id}")
    name = cat_data.get("name", cat_slug)

    existing = sync_client.db.query(KBCategory).filter(
        KBCategory.chatwoot_portal_slug == portal_slug,
        KBCategory.chatwoot_category_id == chatwoot_id,
    ).first()

    if existing:
        existing.name = name
        existing.slug = f"{portal_slug}-{cat_slug}"
        existing.description = cat_data.get("description")
        existing.display_order = cat_data.get("position", 100)
        existing.parent_id = parent_id
        existing.last_synced_at = datetime.now(timezone.utc)
        existing.updated_at = datetime.now(timezone.utc)
        sync_client.increment_updated()
        return existing
    else:
        category = KBCategory(
            name=name,
            slug=f"{portal_slug}-{cat_slug}",
            description=cat_data.get("description"),
            icon=cat_data.get("icon"),
            parent_id=parent_id,
            display_order=cat_data.get("position", 100),
            visibility=ArticleVisibility.PUBLIC.value,
            is_active=True,
            chatwoot_portal_slug=portal_slug,
            chatwoot_category_id=chatwoot_id,
            last_synced_at=datetime.now(timezone.utc),
        )
        sync_client.db.add(category)
        sync_client.db.flush()
        sync_client.increment_created()
        return category


async def _sync_article(
    sync_client: "ChatwootSync",
    article_data: Dict[str, Any],
    portal_slug: str,
    category_map: Dict[int, KBCategory],
) -> None:
    """Create or update a KBArticle from Chatwoot article."""
    chatwoot_id = article_data.get("id")
    article_slug = article_data.get("slug", f"article-{chatwoot_id}")
    title = article_data.get("title", article_slug)

    existing = sync_client.db.query(KBArticle).filter(
        KBArticle.chatwoot_article_id == chatwoot_id
    ).first()

    # Find category
    category_id = None
    cat_id = article_data.get("category", {}).get("id") if article_data.get("category") else None
    if cat_id and cat_id in category_map:
        category_id = category_map[cat_id].id

    status = _map_article_status(article_data.get("status", 0))

    if existing:
        existing.title = title
        existing.slug = f"{portal_slug}-{article_slug}"
        existing.content = article_data.get("content", "")
        existing.excerpt = article_data.get("description")
        existing.category_id = category_id
        existing.status = status
        existing.view_count = article_data.get("views", 0)
        existing.last_synced_at = datetime.now(timezone.utc)
        existing.updated_at = datetime.now(timezone.utc)
        sync_client.increment_updated()
        logger.debug("chatwoot_article_updated", chatwoot_id=chatwoot_id, title=title)
    else:
        article = KBArticle(
            title=title,
            slug=f"{portal_slug}-{article_slug}",
            content=article_data.get("content", ""),
            excerpt=article_data.get("description"),
            category_id=category_id,
            status=status,
            visibility=ArticleVisibility.PUBLIC.value,
            view_count=article_data.get("views", 0),
            chatwoot_article_id=chatwoot_id,
            last_synced_at=datetime.now(timezone.utc),
        )
        sync_client.db.add(article)
        sync_client.increment_created()
        logger.debug("chatwoot_article_created", chatwoot_id=chatwoot_id, title=title)
