"""Web-layer helpers for subscription routes."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.models.gateway_transaction import GatewayTransaction, GatewayProvider
from app.models.invoice import Invoice
from app.models.party import CustomerAccount
from app.models.subscription import Subscription
from app.services.subscriptions import PaymentSubscriptionService, TariffService
from app.modules.subscriptions._services import SubscriptionWebService


class PaymentSubscriptionQueryService:
    """Queries for payment subscription routes."""

    def __init__(self, db: Session):
        self.db = db

    def get_service_subscription(self, subscription_id: int) -> Optional[Subscription]:
        return (
            self.db.query(Subscription)
            .filter(Subscription.id == subscription_id)
            .first()
        )

    def get_customer_account(self, party_id: int) -> Optional[CustomerAccount]:
        return (
            self.db.query(CustomerAccount)
            .filter(CustomerAccount.party_id == party_id)
            .first()
        )

    def list_gateway_transactions(
        self,
        provider: GatewayProvider,
        customer_account_id: Optional[int],
        limit: int = 20,
    ) -> list[GatewayTransaction]:
        query = self.db.query(GatewayTransaction).filter(GatewayTransaction.provider == provider)
        if customer_account_id:
            query = query.filter(GatewayTransaction.customer_account_id == customer_account_id)
        return query.order_by(GatewayTransaction.created_at.desc()).limit(limit).all()

    def list_service_subscriptions(self, party_id: int) -> list[Subscription]:
        return (
            self.db.query(Subscription)
            .filter(Subscription.party_id == party_id)
            .order_by(Subscription.plan_name)
            .all()
        )


class PaymentSubscriptionWebService:
    """Commit wrapper for payment subscription actions."""

    def __init__(self, db: Session, service: PaymentSubscriptionService):
        self.db = db
        self.service = service

    def pause(self, subscription_id: int):
        subscription = self.service.pause(subscription_id)
        self.db.commit()
        return subscription

    def resume(self, subscription_id: int):
        subscription = self.service.resume(subscription_id)
        self.db.commit()
        return subscription

    def cancel(self, subscription_id: int, reason: Optional[str] = None):
        subscription = self.service.cancel(subscription_id, reason=reason)
        self.db.commit()
        return subscription

    def record_charge_attempt(self, subscription_id: int, success: bool, reference: Optional[str], amount):
        self.service.record_charge_attempt(subscription_id, success=success, reference=reference, amount=amount)
        self.db.commit()

    def link_to_service_subscription(self, subscription_id: int, service_subscription_id: int):
        subscription = self.service.link_to_service_subscription(subscription_id, service_subscription_id)
        self.db.commit()
        return subscription

    def unlink_service_subscription(self, subscription_id: int):
        subscription = self.service.unlink_service_subscription(subscription_id)
        self.db.commit()
        return subscription


class SubscriptionCommitService:
    """Commit wrapper for SubscriptionWebService actions."""

    def __init__(self, db: Session, service: SubscriptionWebService):
        self.db = db
        self.service = service

    def create_subscription(self, data):
        subscription = self.service.create_subscription(data)
        self.db.commit()
        return subscription

    def update_subscription(self, subscription_id: int, data):
        subscription = self.service.update_subscription(subscription_id, data)
        self.db.commit()
        return subscription

    def activate(self, subscription_id: int):
        subscription = self.service.activate(subscription_id)
        self.db.commit()
        return subscription

    def reactivate(self, subscription_id: int):
        subscription = self.service.reactivate(subscription_id)
        self.db.commit()
        return subscription

    def suspend(self, subscription_id: int):
        subscription = self.service.suspend(subscription_id)
        self.db.commit()
        return subscription

    def cancel(self, subscription_id: int):
        subscription = self.service.cancel(subscription_id)
        self.db.commit()
        return subscription

    def change_status(self, subscription_id: int, status: str):
        subscription = self.service.change_status(subscription_id, status)
        self.db.commit()
        return subscription

    def execute_upgrade(self, **kwargs):
        result = self.service.execute_upgrade(**kwargs)
        self.db.commit()
        return result

    def execute_downgrade(self, **kwargs):
        result = self.service.execute_downgrade(**kwargs)
        self.db.commit()
        return result

    def execute_renewal(self, **kwargs):
        result = self.service.execute_renewal(**kwargs)
        self.db.commit()
        return result

    def extend_grace_period(self, **kwargs):
        self.service.extend_grace_period(**kwargs)
        self.db.commit()

    def assign_network(self, subscription_id: int, data):
        subscription = self.service.assign_network(subscription_id, data)
        self.db.commit()
        return subscription

    def configure_provisioning(self, subscription_id: int, data):
        subscription = self.service.configure_provisioning(subscription_id, data)
        self.db.commit()
        return subscription


class SubscriptionQueryService:
    """Queries for subscription service routes."""

    def __init__(self, db: Session):
        self.db = db

    def list_subscriptions_with_party(self, subscription_ids: set[int]) -> dict[int, Subscription]:
        if not subscription_ids:
            return {}
        subs = (
            self.db.query(Subscription)
            .options(joinedload(Subscription.party))
            .filter(Subscription.id.in_(subscription_ids))
            .all()
        )
        return {sub.id: sub for sub in subs}

    def list_recent_invoices(self, limit: int = 20) -> list[Invoice]:
        return (
            self.db.query(Invoice)
            .filter(Invoice.is_deleted == False)
            .order_by(Invoice.invoice_date.desc())
            .limit(limit)
            .all()
        )


class TariffWebService:
    """Commit wrapper for tariff mutations."""

    def __init__(self, db: Session, service: TariffService):
        self.db = db
        self.service = service

    def toggle_enabled(self, tariff_id: int):
        tariff = self.service.get_tariff(tariff_id)
        tariff.enabled = not tariff.enabled
        self.db.commit()
        return tariff
