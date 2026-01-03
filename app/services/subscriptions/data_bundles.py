"""Data Bundle Service.

Manages data bundle products, customer bundles, usage tracking,
and exhaustion/expiry handling.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.data_bundle import (
    BundleStatus,
    BundleTransaction,
    BundleType,
    BundleUsageLog,
    CustomerBundle,
    DataBundleProduct,
    ExhaustionAction,
    ExpiryType,
)
from app.models.subscription import Subscription
from app.services.event_bus import EventBus
from app.services.subscriptions.data_bundle_types import (
    BundleAnalytics,
    BundlePurchaseRequest,
    BundleProductCreate,
    BundleProductResponse,
    BundleProductUpdate,
    BundleStatusResponse,
    CustomerBundleResponse,
    ExhaustionResult,
    ProductRevenue,
    UsageRecordRequest,
    UsageSummary,
)
from app.services.subscriptions.subscription_settings import (
    SubscriptionSettings,
    SubscriptionSettingsService,
    get_subscription_defaults,
)

logger = logging.getLogger(__name__)


class DataBundleService:
    """Service for managing data bundles."""

    def __init__(
        self,
        db: AsyncSession,
        event_bus: Optional[EventBus] = None,
        settings: Optional[SubscriptionSettings] = None,
    ):
        self.db = db
        self.event_bus = event_bus
        self._settings = settings
        self._settings_service: Optional[SubscriptionSettingsService] = None

    async def _get_settings(self) -> SubscriptionSettings:
        """Get subscription settings (lazy loaded)."""
        if self._settings is not None:
            return self._settings

        if self._settings_service is None:
            self._settings_service = SubscriptionSettingsService(self.db)

        self._settings = await self._settings_service.get_settings()
        return self._settings

    @property
    def settings_sync(self) -> SubscriptionSettings:
        """Get settings synchronously (uses cached or defaults)."""
        if self._settings is not None:
            return self._settings
        return get_subscription_defaults()

    # =========================================================================
    # Product Management
    # =========================================================================

    async def create_product(self, data: BundleProductCreate) -> DataBundleProduct:
        """Create a new bundle product."""
        product = DataBundleProduct(
            name=data.name,
            code=data.code.upper(),
            description=data.description,
            bundle_type=data.bundle_type.value,
            data_amount_mb=data.data_amount_mb,
            data_cap_mb=data.data_cap_mb,
            price=data.price,
            currency=data.currency,
            usage_tiers=[t.model_dump() for t in data.usage_tiers] if data.usage_tiers else None,
            overage_price_per_mb=data.overage_price_per_mb,
            expiry_type=data.expiry_type.value,
            validity_days=data.validity_days,
            rollover_percent=data.rollover_percent,
            exhaustion_action=data.exhaustion_action.value,
            throttle_speed_kbps=data.throttle_speed_kbps,
            auto_renew_product_id=data.auto_renew_product_id,
            download_speed_kbps=data.download_speed_kbps,
            upload_speed_kbps=data.upload_speed_kbps,
            alert_threshold_1=data.alert_threshold_1,
            alert_threshold_2=data.alert_threshold_2,
            alert_threshold_3=data.alert_threshold_3,
            is_active=data.is_active,
            display_order=data.display_order,
            customer_portal_visible=data.customer_portal_visible,
            category=data.category,
            tags=data.tags,
        )
        self.db.add(product)
        await self.db.flush()
        await self.db.refresh(product)

        logger.info("Created bundle product: %s (%s)", product.name, product.code)
        return product

    async def update_product(
        self, product_id: int, data: BundleProductUpdate
    ) -> Optional[DataBundleProduct]:
        """Update an existing bundle product."""
        product = await self.get_product(product_id)
        if not product:
            return None

        update_data = data.model_dump(exclude_unset=True)

        # Handle usage_tiers specially
        if "usage_tiers" in update_data and update_data["usage_tiers"]:
            update_data["usage_tiers"] = [t.model_dump() for t in data.usage_tiers]

        # Handle enums
        if "bundle_type" in update_data:
            update_data["bundle_type"] = update_data["bundle_type"].value
        if "expiry_type" in update_data:
            update_data["expiry_type"] = update_data["expiry_type"].value
        if "exhaustion_action" in update_data:
            update_data["exhaustion_action"] = update_data["exhaustion_action"].value

        for key, value in update_data.items():
            setattr(product, key, value)

        await self.db.flush()
        await self.db.refresh(product)

        logger.info("Updated bundle product: %s", product.code)
        return product

    async def get_product(self, product_id: int) -> Optional[DataBundleProduct]:
        """Get a bundle product by ID."""
        result = await self.db.execute(
            select(DataBundleProduct).where(DataBundleProduct.id == product_id)
        )
        return result.scalar_one_or_none()

    async def get_product_by_code(self, code: str) -> Optional[DataBundleProduct]:
        """Get a bundle product by code."""
        result = await self.db.execute(
            select(DataBundleProduct).where(
                DataBundleProduct.code == code.upper()
            )
        )
        return result.scalar_one_or_none()

    async def list_products(
        self,
        *,
        active_only: bool = True,
        portal_visible_only: bool = False,
        bundle_type: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[DataBundleProduct], int]:
        """List bundle products with filtering."""
        query = select(DataBundleProduct)

        if active_only:
            query = query.where(DataBundleProduct.is_active == True)
        if portal_visible_only:
            query = query.where(DataBundleProduct.customer_portal_visible == True)
        if bundle_type:
            query = query.where(DataBundleProduct.bundle_type == bundle_type)
        if category:
            query = query.where(DataBundleProduct.category == category)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Apply pagination and ordering
        query = query.order_by(
            DataBundleProduct.display_order,
            DataBundleProduct.name,
        ).offset(offset).limit(limit)

        result = await self.db.execute(query)
        products = list(result.scalars().all())

        return products, total

    async def delete_product(self, product_id: int) -> bool:
        """Delete a bundle product (if no active bundles)."""
        product = await self.get_product(product_id)
        if not product:
            return False

        # Check for active bundles
        active_count = await self.db.execute(
            select(func.count()).where(
                and_(
                    CustomerBundle.product_id == product_id,
                    CustomerBundle.status.in_([
                        BundleStatus.PENDING.value,
                        BundleStatus.ACTIVE.value,
                    ])
                )
            )
        )
        if active_count.scalar() > 0:
            raise ValueError("Cannot delete product with active bundles")

        await self.db.delete(product)
        await self.db.flush()

        logger.info("Deleted bundle product: %s", product.code)
        return True

    # =========================================================================
    # Bundle Purchase & Management
    # =========================================================================

    async def purchase_bundle(
        self,
        subscription_id: int,
        request: BundlePurchaseRequest,
    ) -> CustomerBundle:
        """Purchase a bundle for a subscription."""
        # Get product
        product = await self.get_product(request.product_id)
        if not product:
            raise ValueError(f"Bundle product not found: {request.product_id}")
        if not product.is_active:
            raise ValueError(f"Bundle product is inactive: {product.code}")

        # Verify subscription exists
        sub_result = await self.db.execute(
            select(Subscription).where(Subscription.id == subscription_id)
        )
        subscription = sub_result.scalar_one_or_none()
        if not subscription:
            raise ValueError(f"Subscription not found: {subscription_id}")

        # Calculate data allocation
        data_allocated = product.data_amount_mb or product.data_cap_mb or 0

        # Calculate expiry
        expires_at = None
        if product.validity_days and product.expiry_type != ExpiryType.NO_EXPIRY.value:
            expires_at = datetime.now(timezone.utc) + timedelta(days=product.validity_days)

        # Create bundle
        bundle = CustomerBundle(
            subscription_id=subscription_id,
            product_id=product.id,
            data_allocated_mb=data_allocated,
            data_used_mb=0,
            rollover_mb=0,
            status=BundleStatus.PENDING.value if not request.activate_immediately else BundleStatus.ACTIVE.value,
            purchased_at=datetime.now(timezone.utc),
            activated_at=datetime.now(timezone.utc) if request.activate_immediately else None,
            expires_at=expires_at,
            amount_charged=product.price,
            currency=product.currency,
            payment_reference=request.payment_reference,
        )

        self.db.add(bundle)
        await self.db.flush()
        await self.db.refresh(bundle)

        # Create purchase transaction
        transaction = BundleTransaction(
            customer_bundle_id=bundle.id,
            transaction_type="PURCHASE",
            amount=product.price,
            currency=product.currency,
            data_mb=data_allocated,
            description=f"Bundle purchase: {product.name}",
        )
        self.db.add(transaction)

        # Emit event
        if self.event_bus:
            await self.event_bus.emit(
                "bundle.purchased",
                {
                    "bundle_id": bundle.id,
                    "subscription_id": subscription_id,
                    "product_code": product.code,
                    "amount": float(product.price),
                },
            )

        logger.info(
            "Bundle purchased: subscription=%d, product=%s, amount=%s",
            subscription_id,
            product.code,
            product.price,
        )
        return bundle

    async def activate_bundle(self, bundle_id: int) -> Optional[CustomerBundle]:
        """Activate a pending bundle."""
        bundle = await self.get_bundle(bundle_id)
        if not bundle:
            return None

        if bundle.status != BundleStatus.PENDING.value:
            raise ValueError(f"Bundle is not pending: {bundle.status}")

        # Load product for expiry calculation
        product = await self.get_product(bundle.product_id)

        bundle.status = BundleStatus.ACTIVE.value
        bundle.activated_at = datetime.now(timezone.utc)

        # Calculate expiry from activation time
        if product and product.validity_days and product.expiry_type != ExpiryType.NO_EXPIRY.value:
            bundle.expires_at = datetime.now(timezone.utc) + timedelta(days=product.validity_days)

        await self.db.flush()
        await self.db.refresh(bundle)

        if self.event_bus:
            await self.event_bus.emit(
                "bundle.activated",
                {"bundle_id": bundle_id, "subscription_id": bundle.subscription_id},
            )

        logger.info("Bundle activated: %d", bundle_id)
        return bundle

    async def cancel_bundle(
        self, bundle_id: int, reason: Optional[str] = None
    ) -> Optional[CustomerBundle]:
        """Cancel a bundle."""
        bundle = await self.get_bundle(bundle_id)
        if not bundle:
            return None

        if bundle.status not in [BundleStatus.PENDING.value, BundleStatus.ACTIVE.value]:
            raise ValueError(f"Cannot cancel bundle in status: {bundle.status}")

        bundle.status = BundleStatus.CANCELLED.value
        bundle.cancelled_at = datetime.now(timezone.utc)

        await self.db.flush()
        await self.db.refresh(bundle)

        if self.event_bus:
            await self.event_bus.emit(
                "bundle.cancelled",
                {
                    "bundle_id": bundle_id,
                    "subscription_id": bundle.subscription_id,
                    "reason": reason,
                },
            )

        logger.info("Bundle cancelled: %d, reason: %s", bundle_id, reason)
        return bundle

    async def get_bundle(self, bundle_id: int) -> Optional[CustomerBundle]:
        """Get a customer bundle by ID."""
        result = await self.db.execute(
            select(CustomerBundle)
            .options(selectinload(CustomerBundle.product))
            .where(CustomerBundle.id == bundle_id)
        )
        return result.scalar_one_or_none()

    async def get_active_bundle(
        self, subscription_id: int
    ) -> Optional[CustomerBundle]:
        """Get the active bundle for a subscription."""
        result = await self.db.execute(
            select(CustomerBundle)
            .options(selectinload(CustomerBundle.product))
            .where(
                and_(
                    CustomerBundle.subscription_id == subscription_id,
                    CustomerBundle.status == BundleStatus.ACTIVE.value,
                )
            )
            .order_by(CustomerBundle.activated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_bundle_status(self, subscription_id: int) -> BundleStatusResponse:
        """Get comprehensive bundle status for a subscription."""
        # Get active bundle
        active_bundle = await self.get_active_bundle(subscription_id)

        # Get pending bundles
        pending_result = await self.db.execute(
            select(CustomerBundle)
            .options(selectinload(CustomerBundle.product))
            .where(
                and_(
                    CustomerBundle.subscription_id == subscription_id,
                    CustomerBundle.status == BundleStatus.PENDING.value,
                )
            )
            .order_by(CustomerBundle.purchased_at)
        )
        pending_bundles = list(pending_result.scalars().all())

        # Calculate totals
        total_remaining = 0
        if active_bundle:
            total_remaining = active_bundle.data_remaining_mb

        return BundleStatusResponse(
            subscription_id=subscription_id,
            has_active_bundle=active_bundle is not None,
            active_bundle=self._bundle_to_response(active_bundle) if active_bundle else None,
            pending_bundles=[self._bundle_to_response(b) for b in pending_bundles],
            total_data_remaining_mb=total_remaining,
            total_data_remaining_gb=total_remaining / 1024,
        )

    def _bundle_to_response(self, bundle: CustomerBundle) -> CustomerBundleResponse:
        """Convert bundle to response schema."""
        return CustomerBundleResponse(
            id=bundle.id,
            subscription_id=bundle.subscription_id,
            product_id=bundle.product_id,
            product_name=bundle.product.name if bundle.product else "Unknown",
            product_code=bundle.product.code if bundle.product else "UNKNOWN",
            data_allocated_mb=bundle.data_allocated_mb,
            data_used_mb=bundle.data_used_mb,
            rollover_mb=bundle.rollover_mb,
            data_remaining_mb=bundle.data_remaining_mb,
            data_remaining_gb=bundle.data_remaining_gb,
            usage_percent=bundle.usage_percent,
            status=bundle.status,
            is_active=bundle.is_active,
            is_exhausted=bundle.is_exhausted,
            is_expired=bundle.is_expired,
            purchased_at=bundle.purchased_at,
            activated_at=bundle.activated_at,
            expires_at=bundle.expires_at,
            exhausted_at=bundle.exhausted_at,
            amount_charged=bundle.amount_charged,
            currency=bundle.currency,
            invoice_id=bundle.invoice_id,
            alert_50_sent=bundle.alert_50_sent,
            alert_80_sent=bundle.alert_80_sent,
            alert_95_sent=bundle.alert_95_sent,
            created_at=bundle.created_at,
            updated_at=bundle.updated_at,
        )

    # =========================================================================
    # Usage Tracking
    # =========================================================================

    async def record_usage(self, request: UsageRecordRequest) -> Optional[int]:
        """Record usage for a subscription's active bundle.

        Returns MB added, or None if no active bundle.
        """
        bundle = await self.get_active_bundle(request.subscription_id)
        if not bundle:
            logger.debug("No active bundle for subscription %d", request.subscription_id)
            return None

        # Calculate MB
        total_bytes = request.upload_bytes + request.download_bytes
        mb_used = total_bytes // (1024 * 1024)

        if mb_used == 0:
            return 0

        # Update bundle usage
        bundle.data_used_mb += mb_used
        bundle.updated_at = datetime.now(timezone.utc)

        # Create usage log
        usage_log = BundleUsageLog(
            customer_bundle_id=bundle.id,
            recorded_at=datetime.now(timezone.utc),
            upload_bytes=request.upload_bytes,
            download_bytes=request.download_bytes,
            source=request.source,
            session_id=request.session_id,
            nas_ip=request.nas_ip,
        )
        self.db.add(usage_log)

        await self.db.flush()

        # Check thresholds and exhaustion
        await self._check_usage_thresholds(bundle)

        logger.debug(
            "Recorded %d MB usage for bundle %d (now %d/%d MB)",
            mb_used,
            bundle.id,
            bundle.data_used_mb,
            bundle.total_data_mb,
        )
        return mb_used

    async def _check_usage_thresholds(self, bundle: CustomerBundle) -> None:
        """Check usage thresholds and trigger alerts/actions."""
        product = await self.get_product(bundle.product_id)
        if not product:
            return

        usage_pct = bundle.usage_percent

        # Check alert thresholds
        if usage_pct >= product.alert_threshold_1 and not bundle.alert_50_sent:
            bundle.alert_50_sent = True
            if self.event_bus:
                await self.event_bus.emit(
                    "bundle.threshold_reached",
                    {
                        "bundle_id": bundle.id,
                        "threshold": product.alert_threshold_1,
                        "usage_percent": usage_pct,
                    },
                )

        if usage_pct >= product.alert_threshold_2 and not bundle.alert_80_sent:
            bundle.alert_80_sent = True
            if self.event_bus:
                await self.event_bus.emit(
                    "bundle.threshold_reached",
                    {
                        "bundle_id": bundle.id,
                        "threshold": product.alert_threshold_2,
                        "usage_percent": usage_pct,
                    },
                )

        if usage_pct >= product.alert_threshold_3 and not bundle.alert_95_sent:
            bundle.alert_95_sent = True
            if self.event_bus:
                await self.event_bus.emit(
                    "bundle.threshold_reached",
                    {
                        "bundle_id": bundle.id,
                        "threshold": product.alert_threshold_3,
                        "usage_percent": usage_pct,
                    },
                )

        # Check exhaustion
        if bundle.is_exhausted and bundle.status == BundleStatus.ACTIVE.value:
            await self.handle_exhaustion(bundle.id)

    # =========================================================================
    # Exhaustion Handling
    # =========================================================================

    async def handle_exhaustion(self, bundle_id: int) -> ExhaustionResult:
        """Handle bundle exhaustion based on product config."""
        bundle = await self.get_bundle(bundle_id)
        if not bundle:
            return ExhaustionResult(
                bundle_id=bundle_id,
                action_taken=ExhaustionAction.NOTIFY_ONLY,
                coa_sent=False,
                notification_sent=False,
                error="Bundle not found",
            )

        product = await self.get_product(bundle.product_id)
        if not product:
            return ExhaustionResult(
                bundle_id=bundle_id,
                action_taken=ExhaustionAction.NOTIFY_ONLY,
                coa_sent=False,
                notification_sent=False,
                error="Product not found",
            )

        # Update bundle status
        bundle.status = BundleStatus.EXHAUSTED.value
        bundle.exhausted_at = datetime.now(timezone.utc)

        action = ExhaustionAction(product.exhaustion_action)
        coa_sent = False
        new_bundle_id = None
        notification_sent = False

        try:
            if action == ExhaustionAction.BLOCK:
                # Send CoA to disconnect
                coa_sent = await self._send_block_coa(bundle.subscription_id)

            elif action == ExhaustionAction.THROTTLE:
                # Send CoA with reduced speed
                settings = await self._get_settings()
                throttle_speed = product.throttle_speed_kbps or settings.bundle_default_throttle_speed_kbps
                coa_sent = await self._send_throttle_coa(
                    bundle.subscription_id,
                    throttle_speed,
                )

            elif action == ExhaustionAction.AUTO_RENEW:
                # Auto-purchase next bundle
                if product.auto_renew_product_id:
                    new_bundle = await self.auto_renew_bundle(bundle)
                    if new_bundle:
                        new_bundle_id = new_bundle.id

            # Send notification for all actions
            if self.event_bus:
                await self.event_bus.emit(
                    "bundle.exhausted",
                    {
                        "bundle_id": bundle_id,
                        "subscription_id": bundle.subscription_id,
                        "action": action.value,
                    },
                )
                notification_sent = True

            if not bundle.exhaustion_alert_sent:
                bundle.exhaustion_alert_sent = True

        except Exception as e:
            logger.error("Error handling exhaustion for bundle %d: %s", bundle_id, e)
            return ExhaustionResult(
                bundle_id=bundle_id,
                action_taken=action,
                coa_sent=coa_sent,
                new_bundle_id=new_bundle_id,
                notification_sent=notification_sent,
                error=str(e),
            )

        await self.db.flush()

        logger.info(
            "Handled exhaustion for bundle %d: action=%s, coa=%s, renewed=%s",
            bundle_id,
            action.value,
            coa_sent,
            new_bundle_id,
        )

        return ExhaustionResult(
            bundle_id=bundle_id,
            action_taken=action,
            coa_sent=coa_sent,
            new_bundle_id=new_bundle_id,
            notification_sent=notification_sent,
        )

    async def _send_block_coa(self, subscription_id: int) -> bool:
        """Send CoA to block access."""
        # TODO: Integrate with MikroTik RADIUS CoA
        # This would send a Disconnect (PoD) packet
        logger.info("Would send block CoA for subscription %d", subscription_id)
        return True

    async def _send_throttle_coa(self, subscription_id: int, speed_kbps: int) -> bool:
        """Send CoA to throttle speed."""
        # TODO: Integrate with MikroTik RADIUS CoA
        # This would send a CoA with Mikrotik-Rate-Limit attribute
        logger.info(
            "Would send throttle CoA for subscription %d: %d kbps",
            subscription_id,
            speed_kbps,
        )
        return True

    async def auto_renew_bundle(
        self, exhausted_bundle: CustomerBundle
    ) -> Optional[CustomerBundle]:
        """Auto-renew to the next bundle."""
        product = await self.get_product(exhausted_bundle.product_id)
        if not product or not product.auto_renew_product_id:
            return None

        try:
            new_bundle = await self.purchase_bundle(
                exhausted_bundle.subscription_id,
                BundlePurchaseRequest(
                    product_id=product.auto_renew_product_id,
                    activate_immediately=True,
                ),
            )

            new_bundle.renewed_from_bundle_id = exhausted_bundle.id
            new_bundle.auto_renewed = True

            await self.db.flush()

            logger.info(
                "Auto-renewed bundle %d -> %d",
                exhausted_bundle.id,
                new_bundle.id,
            )
            return new_bundle

        except Exception as e:
            logger.error(
                "Failed to auto-renew bundle %d: %s",
                exhausted_bundle.id,
                e,
            )
            return None

    # =========================================================================
    # Expiry Handling
    # =========================================================================

    async def process_expiring_bundles(self) -> List[CustomerBundle]:
        """Process bundles that have expired."""
        now = datetime.now(timezone.utc)

        # Find expired active bundles
        result = await self.db.execute(
            select(CustomerBundle)
            .options(selectinload(CustomerBundle.product))
            .where(
                and_(
                    CustomerBundle.status == BundleStatus.ACTIVE.value,
                    CustomerBundle.expires_at <= now,
                )
            )
        )
        expired_bundles = list(result.scalars().all())

        processed = []
        for bundle in expired_bundles:
            await self._handle_expiry(bundle)
            processed.append(bundle)

        if processed:
            logger.info("Processed %d expired bundles", len(processed))

        return processed

    async def _handle_expiry(self, bundle: CustomerBundle) -> None:
        """Handle a single bundle expiry."""
        product = bundle.product

        # Calculate rollover if applicable
        rollover_mb = 0
        if product and product.expiry_type == ExpiryType.ROLLOVER.value:
            rollover_percent = product.rollover_percent or 0
            rollover_mb = int(bundle.data_remaining_mb * rollover_percent / 100)

        # Mark bundle as expired
        bundle.status = BundleStatus.EXPIRED.value

        await self.db.flush()

        # If there's rollover, apply to next pending bundle
        if rollover_mb > 0:
            next_bundle = await self._get_next_pending_bundle(bundle.subscription_id)
            if next_bundle:
                next_bundle.rollover_mb = rollover_mb
                logger.info(
                    "Applied %d MB rollover from bundle %d to %d",
                    rollover_mb,
                    bundle.id,
                    next_bundle.id,
                )

        # Emit event
        if self.event_bus:
            await self.event_bus.emit(
                "bundle.expired",
                {
                    "bundle_id": bundle.id,
                    "subscription_id": bundle.subscription_id,
                    "rollover_mb": rollover_mb,
                },
            )

    async def _get_next_pending_bundle(
        self, subscription_id: int
    ) -> Optional[CustomerBundle]:
        """Get the next pending bundle for a subscription."""
        result = await self.db.execute(
            select(CustomerBundle)
            .where(
                and_(
                    CustomerBundle.subscription_id == subscription_id,
                    CustomerBundle.status == BundleStatus.PENDING.value,
                )
            )
            .order_by(CustomerBundle.purchased_at)
            .limit(1)
        )
        return result.scalar_one_or_none()

    # =========================================================================
    # Reporting & Analytics
    # =========================================================================

    async def get_usage_summary(
        self,
        subscription_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> UsageSummary:
        """Get usage summary for a subscription over a period."""
        # Get bundles for this subscription in the period
        result = await self.db.execute(
            select(CustomerBundle).where(
                and_(
                    CustomerBundle.subscription_id == subscription_id,
                    or_(
                        and_(
                            CustomerBundle.activated_at >= start_date,
                            CustomerBundle.activated_at <= end_date,
                        ),
                        and_(
                            CustomerBundle.expires_at >= start_date,
                            CustomerBundle.expires_at <= end_date,
                        ),
                    ),
                )
            )
        )
        bundles = list(result.scalars().all())
        bundle_ids = [b.id for b in bundles]

        # Get usage logs
        if bundle_ids:
            usage_result = await self.db.execute(
                select(
                    func.sum(BundleUsageLog.upload_bytes).label("upload"),
                    func.sum(BundleUsageLog.download_bytes).label("download"),
                ).where(
                    and_(
                        BundleUsageLog.customer_bundle_id.in_(bundle_ids),
                        BundleUsageLog.recorded_at >= start_date,
                        BundleUsageLog.recorded_at <= end_date,
                    )
                )
            )
            row = usage_result.one()
            upload_bytes = row.upload or 0
            download_bytes = row.download or 0
        else:
            upload_bytes = 0
            download_bytes = 0

        # Get charges
        if bundle_ids:
            charges_result = await self.db.execute(
                select(
                    func.sum(BundleTransaction.amount).label("total"),
                ).where(
                    and_(
                        BundleTransaction.customer_bundle_id.in_(bundle_ids),
                        BundleTransaction.transaction_type.in_(["PURCHASE", "TOPUP"]),
                        BundleTransaction.created_at >= start_date,
                        BundleTransaction.created_at <= end_date,
                    )
                )
            )
            bundle_charges = charges_result.scalar() or Decimal("0")

            overage_result = await self.db.execute(
                select(
                    func.sum(BundleTransaction.amount).label("total"),
                ).where(
                    and_(
                        BundleTransaction.customer_bundle_id.in_(bundle_ids),
                        BundleTransaction.transaction_type == "OVERAGE_CHARGE",
                        BundleTransaction.created_at >= start_date,
                        BundleTransaction.created_at <= end_date,
                    )
                )
            )
            overage_charges = overage_result.scalar() or Decimal("0")
        else:
            bundle_charges = Decimal("0")
            overage_charges = Decimal("0")

        total_upload_mb = upload_bytes / (1024 * 1024)
        total_download_mb = download_bytes / (1024 * 1024)
        total_usage_mb = total_upload_mb + total_download_mb

        return UsageSummary(
            subscription_id=subscription_id,
            period_start=start_date,
            period_end=end_date,
            total_upload_mb=total_upload_mb,
            total_download_mb=total_download_mb,
            total_usage_mb=total_usage_mb,
            total_usage_gb=total_usage_mb / 1024,
            bundle_charges=bundle_charges,
            overage_charges=overage_charges,
        )

    async def get_product_revenue(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> List[ProductRevenue]:
        """Get revenue by product for a period."""
        result = await self.db.execute(
            select(
                DataBundleProduct.id,
                DataBundleProduct.name,
                DataBundleProduct.code,
                DataBundleProduct.bundle_type,
                func.count(CustomerBundle.id).label("units_sold"),
                func.sum(CustomerBundle.amount_charged).label("total_revenue"),
                DataBundleProduct.currency,
            )
            .join(CustomerBundle, CustomerBundle.product_id == DataBundleProduct.id)
            .where(
                and_(
                    CustomerBundle.purchased_at >= start_date,
                    CustomerBundle.purchased_at <= end_date,
                )
            )
            .group_by(
                DataBundleProduct.id,
                DataBundleProduct.name,
                DataBundleProduct.code,
                DataBundleProduct.bundle_type,
                DataBundleProduct.currency,
            )
            .order_by(func.sum(CustomerBundle.amount_charged).desc())
        )

        return [
            ProductRevenue(
                product_id=row.id,
                product_name=row.name,
                product_code=row.code,
                bundle_type=row.bundle_type,
                units_sold=row.units_sold,
                total_revenue=row.total_revenue or Decimal("0"),
                currency=row.currency,
            )
            for row in result.all()
        ]

    async def get_analytics(self) -> BundleAnalytics:
        """Get bundle analytics overview."""
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Active bundles
        active_count = await self.db.execute(
            select(func.count()).where(
                CustomerBundle.status == BundleStatus.ACTIVE.value
            )
        )
        total_active = active_count.scalar() or 0

        # Data stats
        data_stats = await self.db.execute(
            select(
                func.sum(CustomerBundle.data_allocated_mb + CustomerBundle.rollover_mb).label("allocated"),
                func.sum(CustomerBundle.data_used_mb).label("consumed"),
            ).where(CustomerBundle.status == BundleStatus.ACTIVE.value)
        )
        row = data_stats.one()
        total_allocated_gb = (row.allocated or 0) / 1024
        total_consumed_gb = (row.consumed or 0) / 1024
        avg_usage = (total_consumed_gb / total_allocated_gb * 100) if total_allocated_gb > 0 else 0

        # Today's exhausted
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        exhausted_today = await self.db.execute(
            select(func.count()).where(
                and_(
                    CustomerBundle.status == BundleStatus.EXHAUSTED.value,
                    CustomerBundle.exhausted_at >= today_start,
                )
            )
        )
        bundles_exhausted_today = exhausted_today.scalar() or 0

        # Expiring soon (configurable threshold)
        settings = await self._get_settings()
        expiry_threshold = now + timedelta(days=settings.bundle_expiring_soon_threshold_days)
        expiring_soon = await self.db.execute(
            select(func.count()).where(
                and_(
                    CustomerBundle.status == BundleStatus.ACTIVE.value,
                    CustomerBundle.expires_at <= expiry_threshold,
                    CustomerBundle.expires_at > now,
                )
            )
        )
        bundles_expiring_soon = expiring_soon.scalar() or 0

        # This month's revenue
        revenue_result = await self.db.execute(
            select(func.sum(CustomerBundle.amount_charged)).where(
                and_(
                    CustomerBundle.purchased_at >= month_start,
                    CustomerBundle.purchased_at <= now,
                )
            )
        )
        revenue_this_month = revenue_result.scalar() or Decimal("0")

        # Top products
        top_products = await self.get_product_revenue(month_start, now)

        return BundleAnalytics(
            total_active_bundles=total_active,
            total_data_allocated_gb=total_allocated_gb,
            total_data_consumed_gb=total_consumed_gb,
            average_usage_percent=avg_usage,
            bundles_exhausted_today=bundles_exhausted_today,
            bundles_expiring_soon=bundles_expiring_soon,
            revenue_this_month=revenue_this_month,
            top_products=top_products[:5],
        )
