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
from app.models.asset import Asset, AssetStatus
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

        # Update router with direct asset FK reference
        router.asset_id = asset_id

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
            asset_name=asset.asset_name,
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

        if not router.asset_id:
            return False

        # Clear the FK reference
        router.asset_id = None

        await self.session.flush()

        logger.info(
            "Asset unlinked from router",
            extra={"router_id": router_id},
        )

        return True

    async def get_router_asset_info(
        self,
        router_id: int,
    ) -> NetworkDeviceAssetInfo:
        """Get asset information for a router."""
        router = await self.session.get(Router, router_id)
        if not router:
            raise ValueError(f"Router {router_id} not found")

        # Use direct FK relationship
        asset = None
        if router.asset_id:
            asset = await self.session.get(Asset, router.asset_id)

        pop_name = None
        if router.pop_id:
            pop = await self.session.get(Pop, router.pop_id)
            pop_name = pop.name if pop else None

        return NetworkDeviceAssetInfo(
            router_id=router_id,
            router_title=router.title,
            asset_id=asset.id if asset else None,
            asset_name=asset.asset_name if asset else None,
            purchase_date=asset.purchase_date if asset else None,
            purchase_cost=asset.gross_purchase_amount if asset else None,
            current_value=asset.asset_value if asset else None,
            depreciation_rate=None,  # Calculated from finance books
            warranty_expiry=asset.warranty_expiry_date if asset else None,
            location=pop_name or router.address,
        )

    async def list_unlinked_routers(self) -> List[Router]:
        """List routers without asset links."""
        q = select(Router).where(Router.asset_id.is_(None))
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def list_linked_devices(self) -> List[AssetNetworkLink]:
        """List all asset-router links."""
        # Query routers with asset links, joining to get asset and pop info
        q = (
            select(Router)
            .where(Router.asset_id.isnot(None))
        )
        result = await self.session.execute(q)
        routers = list(result.scalars().all())

        links = []
        for router in routers:
            asset = await self.session.get(Asset, router.asset_id)
            if asset:
                pop_name = None
                if router.pop_id:
                    pop = await self.session.get(Pop, router.pop_id)
                    pop_name = pop.name if pop else None

                links.append(AssetNetworkLink(
                    asset_id=router.asset_id,
                    router_id=router.id,
                    asset_name=asset.asset_name,
                    router_title=router.title,
                    pop_name=pop_name,
                    linked_at=asset.updated_at,  # Use asset update time as proxy
                ))

        return links

    async def sync_location_from_pop(
        self,
        router_id: int,
    ) -> bool:
        """Sync asset location from router's POP."""
        router = await self.session.get(Router, router_id)
        if not router or not router.pop_id or not router.asset_id:
            return False

        asset = await self.session.get(Asset, router.asset_id)
        if not asset:
            return False

        pop = await self.session.get(Pop, router.pop_id)
        if pop:
            asset.location = pop.name
            await self.session.flush()

            logger.info(
                "Asset location synced from POP",
                extra={
                    "asset_id": router.asset_id,
                    "router_id": router_id,
                    "location": pop.name,
                },
            )
            return True

        return False

    async def trigger_depreciation_on_decommission(
        self,
        router_id: int,
        decommission_date: Optional[datetime] = None,
    ) -> Optional[Decimal]:
        """Calculate and record depreciation when router is decommissioned."""
        router = await self.session.get(Router, router_id)
        if not router or not router.asset_id:
            return None

        asset = await self.session.get(Asset, router.asset_id)
        if not asset:
            return None

        decommission_date = decommission_date or utc_now()

        # Calculate depreciation using asset's finance book settings if available
        purchase_cost = asset.gross_purchase_amount
        purchase_date = asset.purchase_date

        if not purchase_date or not purchase_cost or purchase_cost <= 0:
            return None

        # Convert date to datetime for calculation
        from datetime import datetime as dt
        if isinstance(purchase_date, dt):
            purchase_datetime = purchase_date
        else:
            purchase_datetime = dt.combine(purchase_date, dt.min.time())

        years_used = (decommission_date - purchase_datetime).days / 365

        # Get depreciation rate from finance books or use default
        depreciation_rate = Decimal("0.2")  # Default 20% per year
        if asset.finance_books:
            for fb in asset.finance_books:
                if fb.rate_of_depreciation and fb.rate_of_depreciation > 0:
                    depreciation_rate = fb.rate_of_depreciation / Decimal("100")
                    break

        # Declining balance depreciation
        depreciated_value = purchase_cost * (Decimal("1") - depreciation_rate) ** Decimal(str(years_used))
        depreciation_amount = purchase_cost - depreciated_value

        # Update asset
        asset.asset_value = max(Decimal("0"), depreciated_value)
        asset.status = AssetStatus.SCRAPPED
        asset.disposal_date = decommission_date.date() if hasattr(decommission_date, 'date') else decommission_date

        await self.session.flush()

        logger.info(
            "Depreciation calculated on decommission",
            extra={
                "asset_id": router.asset_id,
                "router_id": router_id,
                "depreciation": float(depreciation_amount),
                "final_value": float(depreciated_value),
            },
        )

        return depreciation_amount
