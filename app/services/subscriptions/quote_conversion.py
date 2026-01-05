"""Quote to Subscription Conversion Service.

Enables converting CRM quotations with internet service plans
into active subscriptions.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionType
from app.models.sales import Quotation, QuotationItem
from app.models.tariff import Tariff
from app.models.party import Party
from app.utils.datetime_utils import utc_now

logger = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    """Result of quote to subscription conversion."""
    success: bool
    subscription_id: Optional[int]
    invoice_id: Optional[int]
    message: str
    errors: List[str]


@dataclass
class ConversionInput:
    """Input for quote conversion."""
    quotation_id: int
    start_date: Optional[datetime] = None
    generate_invoice: bool = True
    provision_immediately: bool = False
    ppp_username: Optional[str] = None
    ppp_password: Optional[str] = None
    router_id: Optional[int] = None
    access_method: Optional[str] = None  # pppoe, hotspot, dhcp


class QuoteConversionService:
    """Service for converting quotations to subscriptions."""

    def __init__(self, session: AsyncSession, company_id: int):
        self.session = session
        self.company_id = company_id

    async def convert_to_subscription(
        self,
        input_data: ConversionInput,
    ) -> ConversionResult:
        """Convert a quotation to a subscription.

        Flow:
        1. Validate quotation exists and is in valid state
        2. Extract service plan items from quotation
        3. Create subscription(s) for each service item
        4. Generate invoice if requested
        5. Trigger provisioning if requested
        """
        errors: List[str] = []

        # Load quotation with items
        q = select(Quotation).where(Quotation.id == input_data.quotation_id)
        result = await self.session.execute(q)
        quotation = result.scalar()

        if not quotation:
            return ConversionResult(
                success=False,
                subscription_id=None,
                invoice_id=None,
                message="Quotation not found",
                errors=["Quotation not found"],
            )

        # Validate quotation state
        if quotation.status not in ["accepted", "approved"]:
            return ConversionResult(
                success=False,
                subscription_id=None,
                invoice_id=None,
                message=f"Quotation must be accepted/approved, current status: {quotation.status}",
                errors=[f"Invalid quotation status: {quotation.status}"],
            )

        # Get quotation items
        items_q = select(QuotationItem).where(QuotationItem.quotation_id == quotation.id)
        items_result = await self.session.execute(items_q)
        items = list(items_result.scalars().all())

        if not items:
            return ConversionResult(
                success=False,
                subscription_id=None,
                invoice_id=None,
                message="Quotation has no items",
                errors=["No items found in quotation"],
            )

        # Find service plan items (items linked to tariffs)
        service_items = []
        for item in items:
            if item.tariff_id:
                tariff = await self.session.get(Tariff, item.tariff_id)
                if tariff:
                    service_items.append((item, tariff))
            elif item.item_code and "plan" in item.item_code.lower():
                # Try to find tariff by code
                tariff_q = select(Tariff).where(Tariff.code == item.item_code)
                tariff_result = await self.session.execute(tariff_q)
                tariff = tariff_result.scalar()
                if tariff:
                    service_items.append((item, tariff))

        if not service_items:
            return ConversionResult(
                success=False,
                subscription_id=None,
                invoice_id=None,
                message="No service plan items found in quotation",
                errors=["No tariff/plan items found"],
            )

        # Get or create party
        party_id = quotation.party_id
        if not party_id:
            return ConversionResult(
                success=False,
                subscription_id=None,
                invoice_id=None,
                message="Quotation has no linked party/customer",
                errors=["No party linked to quotation"],
            )

        # Create subscription for each service item
        start_date = input_data.start_date or utc_now()
        created_subscriptions: List[Subscription] = []

        for item, tariff in service_items:
            try:
                subscription = Subscription(
                    party_id=party_id,
                    tariff_id=tariff.id,
                    service_type=SubscriptionType.INTERNET,
                    plan_name=tariff.name,
                    plan_code=tariff.code,
                    description=item.description or tariff.description,
                    price=item.rate or tariff.price,
                    currency=quotation.currency or "NGN",
                    billing_cycle=tariff.billing_cycle or "monthly",
                    download_speed=tariff.download_speed,
                    upload_speed=tariff.upload_speed,
                    data_cap=tariff.data_cap,
                    status=SubscriptionStatus.PENDING,
                    start_date=start_date,
                    access_method=input_data.access_method or "pppoe",
                    ppp_username=input_data.ppp_username,
                    ppp_password=input_data.ppp_password,
                    router_id=input_data.router_id,
                )

                self.session.add(subscription)
                created_subscriptions.append(subscription)

            except Exception as e:
                errors.append(f"Failed to create subscription for {tariff.name}: {str(e)}")

        await self.session.flush()

        if not created_subscriptions:
            return ConversionResult(
                success=False,
                subscription_id=None,
                invoice_id=None,
                message="Failed to create any subscriptions",
                errors=errors,
            )

        # Update quotation status
        quotation.status = "converted"
        quotation.converted_at = utc_now()

        # Generate invoice if requested
        invoice_id = None
        if input_data.generate_invoice:
            invoice_id = await self._generate_invoice(quotation, created_subscriptions)

        # Provision if requested
        if input_data.provision_immediately:
            for sub in created_subscriptions:
                await self._provision_subscription(sub)

        await self.session.flush()

        primary_subscription = created_subscriptions[0]

        logger.info(
            "Quotation converted to subscription",
            extra={
                "quotation_id": quotation.id,
                "subscription_id": primary_subscription.id,
                "subscriptions_created": len(created_subscriptions),
            },
        )

        return ConversionResult(
            success=True,
            subscription_id=primary_subscription.id,
            invoice_id=invoice_id,
            message=f"Created {len(created_subscriptions)} subscription(s) from quotation",
            errors=errors,
        )

    async def _generate_invoice(
        self,
        quotation: Quotation,
        subscriptions: List[Subscription],
    ) -> Optional[int]:
        """Generate invoice for converted subscriptions."""
        # This would integrate with the invoice service
        # For now, return None and log
        logger.info(
            "Would generate invoice for subscriptions",
            extra={
                "quotation_id": quotation.id,
                "subscription_count": len(subscriptions),
            },
        )
        return None

    async def _provision_subscription(
        self,
        subscription: Subscription,
    ) -> bool:
        """Trigger provisioning for a subscription."""
        # This would integrate with the provisioning service
        # For now, just update status
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.provisioned_at = utc_now()
        return True

    async def validate_quotation_for_conversion(
        self,
        quotation_id: int,
    ) -> tuple[bool, List[str]]:
        """Validate if a quotation can be converted."""
        errors: List[str] = []

        quotation = await self.session.get(Quotation, quotation_id)
        if not quotation:
            return False, ["Quotation not found"]

        if quotation.status not in ["accepted", "approved"]:
            errors.append(f"Quotation status must be accepted/approved, got: {quotation.status}")

        if not quotation.party_id:
            errors.append("No customer/party linked to quotation")

        # Check for service items
        items_q = select(QuotationItem).where(QuotationItem.quotation_id == quotation_id)
        items_result = await self.session.execute(items_q)
        items = list(items_result.scalars().all())

        has_service_item = False
        for item in items:
            if item.tariff_id:
                has_service_item = True
                break
            if item.item_code and "plan" in item.item_code.lower():
                has_service_item = True
                break

        if not has_service_item:
            errors.append("No service plan items found in quotation")

        return len(errors) == 0, errors

    async def get_conversion_preview(
        self,
        quotation_id: int,
    ) -> dict:
        """Get a preview of what will be created on conversion."""
        quotation = await self.session.get(Quotation, quotation_id)
        if not quotation:
            return {"error": "Quotation not found"}

        items_q = select(QuotationItem).where(QuotationItem.quotation_id == quotation_id)
        items_result = await self.session.execute(items_q)
        items = list(items_result.scalars().all())

        subscriptions_preview = []
        total_mrr = Decimal("0")

        for item in items:
            tariff = None
            if item.tariff_id:
                tariff = await self.session.get(Tariff, item.tariff_id)

            if tariff:
                price = item.rate or tariff.price
                subscriptions_preview.append({
                    "plan_name": tariff.name,
                    "price": float(price),
                    "download_speed": tariff.download_speed,
                    "upload_speed": tariff.upload_speed,
                    "data_cap": tariff.data_cap,
                })
                total_mrr += price

        return {
            "quotation_id": quotation_id,
            "party_id": quotation.party_id,
            "subscriptions": subscriptions_preview,
            "total_mrr": float(total_mrr),
            "invoice_total": float(quotation.grand_total or 0),
        }
