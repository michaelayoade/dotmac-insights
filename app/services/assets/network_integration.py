"""Asset-Network Integration Service - Track routers/CPE as fixed assets."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from dataclasses import dataclass

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.router import Router
from app.models.asset import Asset
from app.models.pop import Pop
from app.utils.datetime_utils import utc_now

logger = logging.getLogger(__name__)


@dataclass
class AssetNetworkLink:
    """Represents a link between an asset and network device."""
    asset_id: int
    router_id: int
    asset_name: str
    router_title: str
    pop_name: Optional[str]
    linked_at: datetime


@dataclass
class NetworkDeviceAssetInfo:
    """Asset information for a network device."""
    router_id: int
    router_title: str
    asset_id: Optional[int]
    asset_name: Optional[str]
    purchase_date: Optional[datetime]
    purchase_cost: Optional[Decimal]
    current_value: Optional[Decimal]
    depreciation_rate: Optional[float]
    warranty_expiry: Optional[datetime]
    location: Optional[str]


class AssetNetworkService:
    """Service for managing asset-network device relationships."""

    def __init__(self, session: AsyncSession, company_id: int):
        self.session = session
        self.company_id = company_id

    async def link_asset_to_router(
        self,
        asset_id: int,
        router_id: int,
    ) -> AssetNetworkLink:
        """Link an asset to a network router.

        This allows tracking routers/CPE as fixed assets for
        depreciation and inventory control.
        """
        asset = await self.session.get(Asset, asset_id)
        if not asset:
            raise ValueError(f"Asset {asset_id} not found")

        router = await self.session.get(Router, router_id)
        if not router:
            raise ValueError(f"Router {router_id} not found")

        # Update router with asset reference
        # Note: This requires adding asset_id column to Router model
        # For now, we'll store in additional_attributes JSON
        import json
        attrs = json.loads(router.additional_attributes or "{}")
        attrs["asset_id"] = asset_id
        router.additional_attributes = json.dumps(attrs)

        # Update asset with router reference
        if hasattr(asset, "custom_fields"):
            fields = asset.custom_fields or {}
            fields["network_device_id"] = router_id
            fields["network_device_type"] = "router"
            asset.custom_fields = fields

        await self.session.flush()

        pop_name = None
        if router.pop_id:
            pop = await self.session.get(Pop, router.pop_id)
            pop_name = pop.name if pop else None

        logger.info(
            "Asset linked to router",
            extra={
                "asset_id": asset_id,
                "router_id": router_id,
            },
        )

        return AssetNetworkLink(
            asset_id=asset_id,
            router_id=router_id,
            asset_name=asset.name,
            router_title=router.title,
            pop_name=pop_name,
            linked_at=utc_now(),
        )

    async def unlink_asset_from_router(
        self,
        router_id: int,
    ) -> bool:
        """Remove asset link from a router."""
        router = await self.session.get(Router, router_id)
        if not router:
            return False

        import json
        attrs = json.loads(router.additional_attributes or "{}")
        asset_id = attrs.pop("asset_id", None)
        router.additional_attributes = json.dumps(attrs)

        # Clear reference on asset side
        if asset_id:
            asset = await self.session.get(Asset, asset_id)
            if asset and hasattr(asset, "custom_fields"):
                fields = asset.custom_fields or {}
                fields.pop("network_device_id", None)
                fields.pop("network_device_type", None)
                asset.custom_fields = fields

        await self.session.flush()
        return True

    async def get_router_asset_info(
        self,
        router_id: int,
    ) -> NetworkDeviceAssetInfo:
        """Get asset information for a router."""
        router = await self.session.get(Router, router_id)
        if not router:
            raise ValueError(f"Router {router_id} not found")

        import json
        attrs = json.loads(router.additional_attributes or "{}")
        asset_id = attrs.get("asset_id")

        asset = None
        if asset_id:
            asset = await self.session.get(Asset, asset_id)

        pop_name = None
        if router.pop_id:
            pop = await self.session.get(Pop, router.pop_id)
            pop_name = pop.name if pop else None

        return NetworkDeviceAssetInfo(
            router_id=router_id,
            router_title=router.title,
            asset_id=asset.id if asset else None,
            asset_name=asset.name if asset else None,
            purchase_date=asset.purchase_date if asset else None,
            purchase_cost=asset.purchase_cost if asset else None,
            current_value=asset.current_value if asset else None,
            depreciation_rate=asset.depreciation_rate if asset else None,
            warranty_expiry=asset.warranty_expiry if asset else None,
            location=pop_name or router.address,
        )

    async def list_unlinked_routers(self) -> List[Router]:
        """List routers without asset links."""
        q = select(Router)
        result = await self.session.execute(q)
        routers = list(result.scalars().all())

        unlinked = []
        for router in routers:
            import json
            attrs = json.loads(router.additional_attributes or "{}")
            if "asset_id" not in attrs:
                unlinked.append(router)

        return unlinked

    async def list_linked_devices(self) -> List[AssetNetworkLink]:
        """List all asset-router links."""
        q = select(Router)
        result = await self.session.execute(q)
        routers = list(result.scalars().all())

        links = []
        for router in routers:
            import json
            attrs = json.loads(router.additional_attributes or "{}")
            asset_id = attrs.get("asset_id")

            if asset_id:
                asset = await self.session.get(Asset, asset_id)
                if asset:
                    pop_name = None
                    if router.pop_id:
                        pop = await self.session.get(Pop, router.pop_id)
                        pop_name = pop.name if pop else None

                    links.append(AssetNetworkLink(
                        asset_id=asset_id,
                        router_id=router.id,
                        asset_name=asset.name,
                        router_title=router.title,
                        pop_name=pop_name,
                        linked_at=utc_now(),  # Would store actual link time
                    ))

        return links

    async def sync_location_from_pop(
        self,
        router_id: int,
    ) -> bool:
        """Sync asset location from router's POP."""
        router = await self.session.get(Router, router_id)
        if not router or not router.pop_id:
            return False

        import json
        attrs = json.loads(router.additional_attributes or "{}")
        asset_id = attrs.get("asset_id")

        if not asset_id:
            return False

        asset = await self.session.get(Asset, asset_id)
        if not asset:
            return False

        pop = await self.session.get(Pop, router.pop_id)
        if pop:
            asset.location = pop.name
            await self.session.flush()
            return True

        return False

    async def trigger_depreciation_on_decommission(
        self,
        router_id: int,
        decommission_date: Optional[datetime] = None,
    ) -> Optional[Decimal]:
        """Calculate and record depreciation when router is decommissioned."""
        router = await self.session.get(Router, router_id)
        if not router:
            return None

        import json
        attrs = json.loads(router.additional_attributes or "{}")
        asset_id = attrs.get("asset_id")

        if not asset_id:
            return None

        asset = await self.session.get(Asset, asset_id)
        if not asset:
            return None

        decommission_date = decommission_date or utc_now()

        # Calculate depreciation
        # This would use the asset's depreciation method
        if asset.purchase_date and asset.purchase_cost:
            years_used = (decommission_date - asset.purchase_date).days / 365
            depreciation_rate = asset.depreciation_rate or 0.2  # Default 20% per year

            depreciated_value = asset.purchase_cost * Decimal(str(1 - depreciation_rate)) ** Decimal(str(years_used))
            depreciation_amount = asset.purchase_cost - depreciated_value

            # Update asset
            asset.current_value = max(Decimal("0"), depreciated_value)
            asset.status = "decommissioned"

            await self.session.flush()

            logger.info(
                "Depreciation calculated on decommission",
                extra={
                    "asset_id": asset_id,
                    "router_id": router_id,
                    "depreciation": float(depreciation_amount),
                },
            )

            return depreciation_amount

        return None
