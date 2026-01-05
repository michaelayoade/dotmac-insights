"""Subscription Equipment Tracking Service - CPE/inventory integration."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from dataclasses import dataclass

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import Subscription, SubscriptionStatus
from app.models.inventory import SerialNumber
from app.models.sales import Item
from app.utils.datetime_utils import utc_now

logger = logging.getLogger(__name__)


@dataclass
class EquipmentAssignment:
    """Equipment assignment to a subscription."""
    subscription_id: int
    item_id: int
    item_name: str
    serial_number: Optional[str]
    serial_id: Optional[int]
    assigned_at: datetime
    status: str  # reserved, issued, returned


@dataclass
class EquipmentReservation:
    """Result of equipment reservation."""
    success: bool
    subscription_id: int
    item_id: int
    serial_id: Optional[int]
    serial_number: Optional[str]
    message: str


class SubscriptionEquipmentService:
    """Service for managing subscription equipment (CPE, routers, etc.)."""

    def __init__(self, session: AsyncSession, company_id: int):
        self.session = session
        self.company_id = company_id

    async def reserve_equipment(
        self,
        subscription_id: int,
        item_id: int,
        serial_id: Optional[int] = None,
    ) -> EquipmentReservation:
        """Reserve equipment for a subscription.

        Reserves a serial number from inventory without issuing.
        Called during subscription creation.
        """
        subscription = await self.session.get(Subscription, subscription_id)
        if not subscription:
            return EquipmentReservation(
                success=False,
                subscription_id=subscription_id,
                item_id=item_id,
                serial_id=None,
                serial_number=None,
                message="Subscription not found",
            )

        item = await self.session.get(Item, item_id)
        if not item:
            return EquipmentReservation(
                success=False,
                subscription_id=subscription_id,
                item_id=item_id,
                serial_id=None,
                serial_number=None,
                message="Item not found",
            )

        # If specific serial requested, use that
        if serial_id:
            serial = await self.session.get(SerialNumber, serial_id)
            if not serial or serial.item_id != item_id:
                return EquipmentReservation(
                    success=False,
                    subscription_id=subscription_id,
                    item_id=item_id,
                    serial_id=serial_id,
                    serial_number=None,
                    message="Serial number not found or doesn't match item",
                )
            serial_status = serial.status.value if hasattr(serial.status, 'value') else str(serial.status)
            if serial_status not in ("available", "active"):
                return EquipmentReservation(
                    success=False,
                    subscription_id=subscription_id,
                    item_id=item_id,
                    serial_id=serial_id,
                    serial_number=serial.serial_no,
                    message=f"Serial number not available, status: {serial_status}",
                )
        else:
            # Find an available serial number
            from app.models.inventory import SerialStatus
            q = select(SerialNumber).where(
                and_(
                    SerialNumber.item_id == item_id,
                    SerialNumber.status.in_([SerialStatus.AVAILABLE, SerialStatus.ACTIVE]),
                )
            ).limit(1)

            result = await self.session.execute(q)
            serial = result.scalar()

            if not serial:
                return EquipmentReservation(
                    success=False,
                    subscription_id=subscription_id,
                    item_id=item_id,
                    serial_id=None,
                    serial_number=None,
                    message="No available serial numbers for this item",
                )

        # Reserve the serial number
        from app.models.inventory import SerialStatus
        serial.status = SerialStatus.RESERVED
        serial.reserved_for_subscription_id = subscription_id
        serial.reserved_at = utc_now()

        # Update subscription with equipment reference
        subscription.description = (subscription.description or "") + \
            f"\nEquipment: {item.item_name} (S/N: {serial.serial_no})"

        await self.session.flush()

        logger.info(
            "Equipment reserved for subscription",
            extra={
                "subscription_id": subscription_id,
                "item_id": item_id,
                "serial_number": serial.serial_no,
            },
        )

        return EquipmentReservation(
            success=True,
            subscription_id=subscription_id,
            item_id=item_id,
            serial_id=serial.id,
            serial_number=serial.serial_no,
            message="Equipment reserved successfully",
        )

    async def issue_equipment(
        self,
        subscription_id: int,
        post_cogs: bool = True,
    ) -> bool:
        """Issue reserved equipment (convert to sold/issued).

        Called when subscription is activated.
        Optionally posts COGS journal entry.
        """
        subscription = await self.session.get(Subscription, subscription_id)
        if not subscription:
            return False

        # Find reserved serial numbers for this subscription
        from app.models.inventory import SerialStatus
        q = select(SerialNumber).where(
            and_(
                SerialNumber.reserved_for_subscription_id == subscription_id,
                SerialNumber.status == SerialStatus.RESERVED,
            )
        )
        result = await self.session.execute(q)
        serials = list(result.scalars().all())

        for serial in serials:
            serial.status = SerialStatus.ISSUED
            serial.issued_at = utc_now()
            serial.issued_to_party_id = subscription.party_id

            # Post COGS if requested
            if post_cogs:
                await self._post_cogs(serial)

        await self.session.flush()

        logger.info(
            "Equipment issued for subscription",
            extra={
                "subscription_id": subscription_id,
                "serials_issued": len(serials),
            },
        )

        return len(serials) > 0

    async def return_equipment(
        self,
        subscription_id: int,
        serial_id: int,
        condition: str = "good",
        notes: Optional[str] = None,
    ) -> bool:
        """Return equipment to inventory.

        Called when subscription is cancelled or equipment replaced.
        """
        serial = await self.session.get(SerialNumber, serial_id)
        if not serial:
            return False

        # Verify it was issued to this subscription
        if serial.reserved_for_subscription_id != subscription_id:
            return False

        # Update serial status based on condition
        from app.models.inventory import SerialStatus
        if condition == "good":
            serial.status = SerialStatus.AVAILABLE
        elif condition == "damaged":
            serial.status = SerialStatus.DAMAGED
        elif condition == "lost":
            serial.status = SerialStatus.LOST
        else:
            serial.status = SerialStatus.RETURNED

        serial.returned_at = utc_now()
        serial.return_notes = notes
        serial.reserved_for_subscription_id = None

        await self.session.flush()

        logger.info(
            "Equipment returned from subscription",
            extra={
                "subscription_id": subscription_id,
                "serial_id": serial_id,
                "condition": condition,
            },
        )

        return True

    async def get_subscription_equipment(
        self,
        subscription_id: int,
    ) -> List[EquipmentAssignment]:
        """Get equipment assigned to a subscription."""
        q = select(SerialNumber).where(
            SerialNumber.reserved_for_subscription_id == subscription_id
        )
        result = await self.session.execute(q)
        serials = list(result.scalars().all())

        assignments = []
        for serial in serials:
            item = await self.session.get(Item, serial.item_id) if serial.item_id else None
            item_name = item.item_name if item else (serial.item_name or "Unknown")

            assignments.append(EquipmentAssignment(
                subscription_id=subscription_id,
                item_id=serial.item_id or 0,
                item_name=item_name,
                serial_number=serial.serial_no,
                serial_id=serial.id,
                assigned_at=serial.reserved_at or serial.issued_at or utc_now(),
                status=serial.status.value if hasattr(serial.status, 'value') else str(serial.status),
            ))

        return assignments

    async def get_available_equipment(
        self,
        item_id: int,
    ) -> List[SerialNumber]:
        """Get available serial numbers for an item."""
        from app.models.inventory import SerialStatus
        q = select(SerialNumber).where(
            and_(
                SerialNumber.item_id == item_id,
                SerialNumber.status.in_([SerialStatus.AVAILABLE, SerialStatus.ACTIVE]),
            )
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def _post_cogs(self, serial: SerialNumber) -> Optional[int]:
        """Post COGS journal entry when equipment is issued.

        Returns journal entry ID if posted.
        """
        # This would integrate with the accounting journal entry service
        # For now, just log
        logger.info(
            "Would post COGS for equipment issue",
            extra={
                "serial_id": serial.id,
                "item_id": serial.item_id,
            },
        )
        return None

    async def handle_subscription_cancellation(
        self,
        subscription_id: int,
    ) -> int:
        """Handle equipment when subscription is cancelled.

        Returns count of equipment items returned to stock.
        """
        assignments = await self.get_subscription_equipment(subscription_id)

        returned_count = 0
        for assignment in assignments:
            if assignment.serial_id:
                success = await self.return_equipment(
                    subscription_id=subscription_id,
                    serial_id=assignment.serial_id,
                    condition="good",
                    notes="Subscription cancelled",
                )
                if success:
                    returned_count += 1

        return returned_count
