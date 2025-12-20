"""Inventory sync functions for ERPNext.

This module handles syncing of inventory-related entities:
- Items (products/services)
- Item Groups
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import httpx
import structlog

from app.models.sales import Item, ItemGroup

if TYPE_CHECKING:
    from app.sync.erpnext import ERPNextSync

logger = structlog.get_logger()


async def sync_items(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync items (products/services) from ERPNext."""
    sync_client.start_sync("items", "full" if full_sync else "incremental")

    try:
        items = await sync_client._fetch_all_doctype(
            client,
            "Item",
            fields=["*"],
        )

        batch_size = 500
        for i, item_data in enumerate(items, 1):
            erpnext_id = item_data.get("name")
            existing = sync_client.db.query(Item).filter(
                Item.erpnext_id == erpnext_id
            ).first()

            if existing:
                existing.item_code = item_data.get("item_code") or str(erpnext_id or "")
                existing.item_name = item_data.get("item_name") or ""
                existing.item_group = item_data.get("item_group")
                existing.description = item_data.get("description")
                existing.is_stock_item = item_data.get("is_stock_item", 1) == 1
                existing.is_fixed_asset = item_data.get("is_fixed_asset", 0) == 1
                existing.is_sales_item = item_data.get("is_sales_item", 1) == 1
                existing.is_purchase_item = item_data.get("is_purchase_item", 1) == 1
                existing.stock_uom = item_data.get("stock_uom")
                existing.default_warehouse = item_data.get("default_warehouse")
                existing.standard_rate = Decimal(str(item_data.get("standard_rate", 0) or 0))
                existing.valuation_rate = Decimal(str(item_data.get("valuation_rate", 0) or 0))
                existing.disabled = item_data.get("disabled", 0) == 1
                existing.has_variants = item_data.get("has_variants", 0) == 1
                existing.variant_of = item_data.get("variant_of")
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                item = Item(
                    erpnext_id=erpnext_id,
                    item_code=item_data.get("item_code") or str(erpnext_id or ""),
                    item_name=item_data.get("item_name") or "",
                    item_group=item_data.get("item_group"),
                    description=item_data.get("description"),
                    is_stock_item=item_data.get("is_stock_item", 1) == 1,
                    is_fixed_asset=item_data.get("is_fixed_asset", 0) == 1,
                    is_sales_item=item_data.get("is_sales_item", 1) == 1,
                    is_purchase_item=item_data.get("is_purchase_item", 1) == 1,
                    stock_uom=item_data.get("stock_uom"),
                    default_warehouse=item_data.get("default_warehouse"),
                    standard_rate=Decimal(str(item_data.get("standard_rate", 0) or 0)),
                    valuation_rate=Decimal(str(item_data.get("valuation_rate", 0) or 0)),
                    disabled=item_data.get("disabled", 0) == 1,
                    has_variants=item_data.get("has_variants", 0) == 1,
                    variant_of=item_data.get("variant_of"),
                )
                sync_client.db.add(item)
                sync_client.increment_created()

            # Batch commit
            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("items_batch_committed", processed=i, total=len(items))

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_item_groups(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync item groups from ERPNext."""
    sync_client.start_sync("item_groups", "full" if full_sync else "incremental")

    try:
        groups = await sync_client._fetch_all_doctype(
            client,
            "Item Group",
            fields=["*"],
        )

        for group_data in groups:
            erpnext_id = group_data.get("name")
            existing = sync_client.db.query(ItemGroup).filter(
                ItemGroup.erpnext_id == erpnext_id
            ).first()

            if existing:
                existing.item_group_name = group_data.get("item_group_name") or str(erpnext_id or "")
                existing.parent_item_group = group_data.get("parent_item_group")
                existing.is_group = group_data.get("is_group", 0) == 1
                existing.lft = group_data.get("lft")
                existing.rgt = group_data.get("rgt")
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                item_group = ItemGroup(
                    erpnext_id=erpnext_id,
                    item_group_name=group_data.get("item_group_name") or str(erpnext_id or ""),
                    parent_item_group=group_data.get("parent_item_group"),
                    is_group=group_data.get("is_group", 0) == 1,
                    lft=group_data.get("lft"),
                    rgt=group_data.get("rgt"),
                )
                sync_client.db.add(item_group)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
