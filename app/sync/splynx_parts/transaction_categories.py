from datetime import datetime
import structlog

from app.models.transaction_category import TransactionCategory

logger = structlog.get_logger()


async def sync_transaction_categories(sync_client, client, full_sync: bool):
    """Sync transaction categories from Splynx."""
    sync_client.start_sync("transaction_categories", "full" if full_sync else "incremental")
    batch_size = 100

    try:
        categories = await sync_client._fetch_paginated(
            client, "/admin/finance/transaction-categories"
        )
        logger.info("splynx_transaction_categories_fetched", count=len(categories))

        for i, cat_data in enumerate(categories, 1):
            splynx_id = cat_data.get("id")
            existing = sync_client.db.query(TransactionCategory).filter(
                TransactionCategory.splynx_id == splynx_id
            ).first()

            # Parse boolean fields
            is_active = cat_data.get("active") in (1, "1", True)
            is_system = cat_data.get("is_system") in (1, "1", True)

            if existing:
                existing.name = cat_data.get("name") or cat_data.get("title") or f"Category {splynx_id}"
                existing.title = cat_data.get("title")
                existing.description = cat_data.get("description")
                existing.category_type = cat_data.get("type")
                existing.accounting_code = cat_data.get("accounting_code")
                existing.tax_code = cat_data.get("tax_code")
                existing.is_active = is_active
                existing.is_system = is_system
                existing.parent_id = cat_data.get("parent_id")
                existing.sort_order = cat_data.get("sort_order") or 0
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                category = TransactionCategory(
                    splynx_id=splynx_id,
                    name=cat_data.get("name") or cat_data.get("title") or f"Category {splynx_id}",
                    title=cat_data.get("title"),
                    description=cat_data.get("description"),
                    category_type=cat_data.get("type"),
                    accounting_code=cat_data.get("accounting_code"),
                    tax_code=cat_data.get("tax_code"),
                    is_active=is_active,
                    is_system=is_system,
                    parent_id=cat_data.get("parent_id"),
                    sort_order=cat_data.get("sort_order") or 0,
                    last_synced_at=datetime.utcnow(),
                )
                sync_client.db.add(category)
                sync_client.increment_created()

            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("transaction_categories_batch_committed", processed=i, total=len(categories))

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "splynx_transaction_categories_synced",
            created=sync_client.current_sync_log.records_created,
            updated=sync_client.current_sync_log.records_updated,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
