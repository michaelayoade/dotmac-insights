"""Async web helpers for data bundle routes."""
from __future__ import annotations

from app.services.subscriptions.data_bundles import DataBundleService
from app.services.subscriptions.data_bundle_types import BundleProductCreate, BundleProductUpdate


class DataBundlesWebService:
    """Commit wrapper for data bundle mutations."""

    def __init__(self, db):
        self.db = db
        self.service = DataBundleService(db)

    async def create_product(self, data: BundleProductCreate):
        product = await self.service.create_product(data)
        await self.db.commit()
        return product

    async def update_product(self, product_id: int, data: BundleProductUpdate):
        product = await self.service.update_product(product_id, data)
        if not product:
            return None
        await self.db.commit()
        return product

    async def toggle_product(self, product_id: int, is_active: bool):
        await self.service.update_product(product_id, BundleProductUpdate(is_active=is_active))
        await self.db.commit()

    async def delete_product(self, product_id: int) -> bool:
        deleted = await self.service.delete_product(product_id)
        if deleted:
            await self.db.commit()
        return deleted
