"""
Subscription Web Service - Facade for subscription UI operations.

This service wraps the domain services from app/services/subscriptions/
to provide a unified interface for the web routes.

Services integrated:
- SubscriptionService: Core subscription CRUD and lifecycle
- PaymentSubscriptionService: Recurring billing subscriptions
- TariffService: Tariff/plan management
- ProvisioningService: MikroTik/RADIUS provisioning
- UsageService: Bandwidth/traffic usage tracking
- BillingService: Billing operations
- SubscriptionFinanceService: Invoice/payment integration
- SessionService: Active RADIUS session management
- BillingConfigService: Billing configuration
- ServiceTypeConfigService: Service type configuration
- ServiceTransactionService: Transaction tracking
- SubscriptionReportsService: Reports and analytics
- RADIUSSettingsService: RADIUS settings management
- RADIUSCredentialConfigService: RADIUS credential generation settings
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Dict, Any, List
from datetime import datetime, date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.services.types import PaginatedResult, PaginationParams
from app.services.errors import NotFoundError, ValidationError

# Domain services
from app.services.subscriptions import (
    # Core subscription service
    SubscriptionService,
    SubscriptionFilters,
    SubscriptionCreateData,
    SubscriptionUpdateData,
    NetworkAssignmentData,
    ProvisioningConfigData,
    UpgradeResult,
    DowngradeResult,
    RenewalResult,
    StatusTransition,
    # Tariff service
    TariffService,
    # Payment subscription service
    PaymentSubscriptionService,
    PaymentSubscriptionFilters,
    PaymentSubscriptionCreateData,
    PaymentSubscriptionUpdateData,
    # Usage service
    UsageService,
    UsageFilters,
    UsageSummary,
    DataCapStatus,
    # Session service
    SessionService,
    SessionFilters,
    ActiveSession,
    SessionHistory,
    DisconnectResult,
    # Provisioning service
    ProvisioningService,
    ProvisioningLogFilters,
    ProvisioningResult,
    # Billing service
    BillingService,
    DailyBillingResult,
    # Finance service
    SubscriptionFinanceService,
    SubscriptionBillingInfo,
    # Config services
    BillingConfigService,
    BillingConfig,
    ServiceTypeConfigService,
    ServiceTypeConfig,
    # Transaction service
    ServiceTransactionService,
    ServiceTransactionFilters,
    ServiceTransactionCreateData,
    PartyTransactionHistory,
    # Reports service
    SubscriptionReportsService,
    ReportPeriod,
    ReportGroupBy,
    DashboardSummary,
    DashboardKPIs,
    MRRSummary,
    ChurnSummary,
    RevenueSummary,
    # RADIUS settings service
    RADIUSSettingsService,
    RADIUSSettingsData,
    RADIUSSettingsUpdate,
    NASConfigData,
    NASConfigFilters,
    AttributeMappingData,
    AttributeMappingFilters,
    # RADIUS credential service
    RADIUSCredentialConfigService,
    RADIUSCredentialConfig,
)

# Models
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.tariff import Tariff, TariffType
from app.models.payment_subscription import PaymentSubscription
from app.models.provisioning_log import ProvisioningLog

if TYPE_CHECKING:
    from app.auth import Principal


class SubscriptionWebService:
    """
    Facade service for subscription web UI operations.

    Wraps the domain services to provide a consistent interface
    for route handlers. Does NOT commit transactions - that's the
    responsibility of the route handler.
    """

    def __init__(
        self,
        db: Session,
        user_id: Optional[int] = None,
        principal: Optional["Principal"] = None,
    ):
        self.db = db
        self.user_id = user_id
        self.principal = principal

        # Initialize ALL domain services
        self._subscription_svc = SubscriptionService(db, principal)
        self._tariff_svc = TariffService(db, principal)
        self._usage_svc = UsageService(db, principal)
        self._session_svc = SessionService(db, principal=principal)
        self._provisioning_svc = ProvisioningService(db, principal)
        self._billing_svc = BillingService(db, principal)
        self._payment_svc = PaymentSubscriptionService(db, principal)
        self._finance_svc = SubscriptionFinanceService(db, principal)
        self._billing_config_svc = BillingConfigService(db, principal)
        self._service_type_config_svc = ServiceTypeConfigService(db, principal)
        self._transaction_svc = ServiceTransactionService(db, principal)
        self._reports_svc = SubscriptionReportsService(db, principal)
        self._radius_settings_svc = RADIUSSettingsService(db, principal)
        self._radius_credential_config_svc = RADIUSCredentialConfigService(db, principal)

    # =========================================================================
    # SUBSCRIPTION CRUD
    # =========================================================================

    def list_subscriptions(
        self,
        filters: Optional[SubscriptionFilters] = None,
        pagination: Optional[PaginationParams] = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> PaginatedResult[Subscription]:
        """List subscriptions with filtering and pagination."""
        if filters is None:
            filters = SubscriptionFilters()
        if pagination is None:
            pagination = PaginationParams(offset=0, limit=25)

        return self._subscription_svc.list_subscriptions(
            filters=filters,
            pagination=pagination,
        )

    def get_subscription(self, subscription_id: int) -> Subscription:
        """Get a subscription by ID with relations loaded."""
        return self._subscription_svc.get_subscription(subscription_id, include_relations=True)

    def get_subscription_or_none(self, subscription_id: int) -> Optional[Subscription]:
        """Get a subscription by ID, or None if not found."""
        try:
            return self._subscription_svc.get_subscription(subscription_id)
        except NotFoundError:
            return None

    def create_subscription(self, data: SubscriptionCreateData) -> Subscription:
        """Create a new subscription."""
        return self._subscription_svc.create_subscription(data)

    def update_subscription(self, subscription_id: int, data: SubscriptionUpdateData) -> Subscription:
        """Update a subscription."""
        return self._subscription_svc.update_subscription(subscription_id, data)

    def delete_subscription(self, subscription_id: int) -> None:
        """Cancel/delete a subscription (soft delete)."""
        self._subscription_svc.cancel(subscription_id)

    # =========================================================================
    # STATUS MANAGEMENT
    # =========================================================================

    def get_status_transitions(self, subscription_id: int) -> List[Dict[str, Any]]:
        """Get available status transitions for a subscription."""
        transitions = self._subscription_svc.get_available_transitions(subscription_id)
        return [
            {
                "status": t.target_status,
                "label": t.label,
                "color": t.color,
            }
            for t in transitions
        ]

    def change_status(self, subscription_id: int, new_status: str) -> Subscription:
        """Change subscription status with validation."""
        return self._subscription_svc.change_status(subscription_id, new_status)

    def activate(self, subscription_id: int) -> Subscription:
        """Activate a subscription."""
        return self._subscription_svc.activate(subscription_id)

    def suspend(self, subscription_id: int, reason: Optional[str] = None) -> Subscription:
        """Suspend a subscription."""
        return self._subscription_svc.suspend(subscription_id, reason=reason)

    def cancel(self, subscription_id: int, reason: Optional[str] = None) -> Subscription:
        """Cancel a subscription."""
        return self._subscription_svc.cancel(subscription_id, reason=reason)

    def reactivate(self, subscription_id: int) -> Subscription:
        """Reactivate a suspended subscription."""
        return self._subscription_svc.reactivate(subscription_id)

    def extend_grace_period(
        self,
        subscription_id: int,
        days: int,
        reason: Optional[str] = None,
    ) -> Subscription:
        """Extend grace period for a suspended subscription."""
        return self._subscription_svc.extend_grace_period(subscription_id, days, reason)

    # =========================================================================
    # PLAN CHANGES
    # =========================================================================

    def get_upgrade_preview(
        self,
        subscription_id: int,
        new_tariff_id: int,
        effective: str = "immediate",
    ) -> Dict[str, Any]:
        """Get upgrade preview with proration calculation."""
        subscription = self._subscription_svc.get_subscription(subscription_id)
        new_tariff = self._tariff_svc.get_tariff(new_tariff_id)

        # Calculate proration
        if effective == "immediate":
            days_remaining = 0
            if subscription.end_date:
                days_remaining = (subscription.end_date - date.today()).days
                days_remaining = max(0, days_remaining)

            # Monthly proration
            daily_old = float(subscription.price) / 30
            daily_new = float(new_tariff.price) / 30
            credit = daily_old * days_remaining
            charge = daily_new * days_remaining
            net = charge - credit
        else:
            # Next cycle - no proration
            credit = 0
            charge = float(new_tariff.price)
            net = charge

        return {
            "subscription": subscription,
            "current_tariff": subscription.tariff,
            "new_tariff": new_tariff,
            "effective": effective,
            "credit": credit,
            "charge": charge,
            "net": net,
            "speed_change": {
                "download": {
                    "old": subscription.download_speed,
                    "new": new_tariff.download_speed,
                },
                "upload": {
                    "old": subscription.upload_speed,
                    "new": new_tariff.upload_speed,
                },
            },
        }

    def execute_upgrade(
        self,
        subscription_id: int,
        new_tariff_id: int,
        effective: str = "immediate",
        prorate: bool = True,
    ) -> UpgradeResult:
        """Execute plan upgrade."""
        return self._subscription_svc.upgrade(
            subscription_id,
            new_tariff_id,
            effective=effective,
            prorate=prorate,
        )

    def get_downgrade_preview(
        self,
        subscription_id: int,
        new_tariff_id: int,
        effective: str = "next_cycle",
    ) -> Dict[str, Any]:
        """Get downgrade preview with credit calculation."""
        subscription = self._subscription_svc.get_subscription(subscription_id)
        new_tariff = self._tariff_svc.get_tariff(new_tariff_id)

        # Downgrade typically effective at next cycle
        credit = float(subscription.price) - float(new_tariff.price)

        return {
            "subscription": subscription,
            "current_tariff": subscription.tariff,
            "new_tariff": new_tariff,
            "effective": effective,
            "credit": credit,
            "speed_change": {
                "download": {
                    "old": subscription.download_speed,
                    "new": new_tariff.download_speed,
                },
                "upload": {
                    "old": subscription.upload_speed,
                    "new": new_tariff.upload_speed,
                },
            },
        }

    def execute_downgrade(
        self,
        subscription_id: int,
        new_tariff_id: int,
        effective: str = "next_cycle",
        prorate: bool = False,
    ) -> DowngradeResult:
        """Execute plan downgrade."""
        return self._subscription_svc.downgrade(
            subscription_id,
            new_tariff_id,
            effective=effective,
            prorate=prorate,
        )

    def get_renewal_info(self, subscription_id: int) -> Dict[str, Any]:
        """Get renewal information for a subscription."""
        subscription = self._subscription_svc.get_subscription(subscription_id)

        return {
            "subscription": subscription,
            "current_end_date": subscription.end_date,
            "price": subscription.price,
            "currency": subscription.currency,
            "billing_cycle": subscription.billing_cycle,
            "renewal_options": [
                {"periods": 1, "label": "1 period", "new_end_date": self._add_periods(subscription.end_date, 1, subscription.billing_cycle)},
                {"periods": 3, "label": "3 periods", "new_end_date": self._add_periods(subscription.end_date, 3, subscription.billing_cycle)},
                {"periods": 6, "label": "6 periods", "new_end_date": self._add_periods(subscription.end_date, 6, subscription.billing_cycle)},
                {"periods": 12, "label": "12 periods", "new_end_date": self._add_periods(subscription.end_date, 12, subscription.billing_cycle)},
            ],
        }

    def execute_renewal(
        self,
        subscription_id: int,
        periods: int = 1,
        new_end_date: Optional[date] = None,
    ) -> RenewalResult:
        """Execute subscription renewal."""
        return self._subscription_svc.renew(
            subscription_id,
            periods=periods,
            new_end_date=new_end_date,
        )

    def _add_periods(self, base_date: Optional[date], periods: int, billing_cycle: str) -> date:
        """Calculate new end date based on billing cycle."""
        if not base_date:
            base_date = date.today()

        if billing_cycle == "daily":
            return base_date + timedelta(days=periods)
        elif billing_cycle == "weekly":
            return base_date + timedelta(weeks=periods)
        elif billing_cycle == "monthly":
            month = base_date.month + periods
            year = base_date.year + (month - 1) // 12
            month = ((month - 1) % 12) + 1
            day = min(base_date.day, 28)
            return date(year, month, day)
        elif billing_cycle == "quarterly":
            return self._add_periods(base_date, periods * 3, "monthly")
        elif billing_cycle == "yearly":
            return date(base_date.year + periods, base_date.month, base_date.day)
        else:
            return base_date + timedelta(days=30 * periods)

    # =========================================================================
    # NETWORK ASSIGNMENT
    # =========================================================================

    def assign_network(
        self,
        subscription_id: int,
        data: NetworkAssignmentData,
    ) -> Subscription:
        """Assign network configuration to subscription."""
        return self._subscription_svc.assign_network(subscription_id, data)

    def configure_provisioning(
        self,
        subscription_id: int,
        data: ProvisioningConfigData,
    ) -> Subscription:
        """Configure provisioning settings."""
        return self._subscription_svc.configure_provisioning(subscription_id, data)

    # =========================================================================
    # USAGE
    # =========================================================================

    def get_subscription_usage(
        self,
        subscription_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Get usage data for a subscription."""
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        usage_records = self._usage_svc.get_subscription_usage(
            subscription_id,
            start_date=start_date,
            end_date=end_date,
        )
        summary = self._usage_svc.get_usage_summary(
            subscription_id,
            start_date=start_date,
            end_date=end_date,
        )

        return {
            "records": usage_records,
            "summary": summary,
            "start_date": start_date,
            "end_date": end_date,
        }

    def get_data_cap_status(self, subscription_id: int) -> DataCapStatus:
        """Get data cap status for a subscription."""
        return self._usage_svc.get_data_cap_status(subscription_id)

    def list_usage(
        self,
        filters: Optional[UsageFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult:
        """List usage records with filtering."""
        if filters is None:
            filters = UsageFilters()
        if pagination is None:
            pagination = PaginationParams(offset=0, limit=25)

        return self._usage_svc.list_usage(filters, pagination)

    def get_usage_summary(
        self,
        subscription_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> UsageSummary:
        """Get usage summary for a subscription."""
        return self._usage_svc.get_usage_summary(
            subscription_id,
            start_date=start_date,
            end_date=end_date,
        )

    # =========================================================================
    # SESSIONS
    # =========================================================================

    def get_subscription_sessions(self, subscription_id: int) -> List[ActiveSession]:
        """Get active sessions for a subscription."""
        return self._session_svc.get_subscription_sessions(subscription_id)

    def disconnect_subscription_sessions(
        self,
        subscription_id: int,
        triggered_by: Optional[str] = None,
    ) -> str:
        """Disconnect all active sessions for a subscription. Returns task ID."""
        from app.tasks.provisioning_tasks import disconnect_subscription_session
        result = disconnect_subscription_session.delay(
            subscription_id=subscription_id,
            triggered_by=triggered_by or "manual",
        )
        return result.id

    def get_session_history(
        self,
        subscription_id: int,
        page: int = 1,
        per_page: int = 25,
    ) -> Dict[str, Any]:
        """Get session history for a subscription."""
        subscription = self._subscription_svc.get_subscription(subscription_id)
        if not subscription.ppp_username:
            return {"items": [], "total": 0, "page": page, "per_page": per_page}

        history = self._session_svc.get_user_session_history(
            subscription.ppp_username,
            limit=per_page,
            offset=(page - 1) * per_page,
        )
        return {
            "items": history,
            "total": len(history),
            "page": page,
            "per_page": per_page,
        }

    def list_active_sessions(
        self,
        filters: Optional[SessionFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[ActiveSession]:
        """List all active sessions with filtering."""
        if filters is None:
            filters = SessionFilters()
        if pagination is None:
            pagination = PaginationParams(offset=0, limit=25)

        return self._session_svc.list_active_sessions(filters, pagination)

    # =========================================================================
    # PROVISIONING
    # =========================================================================

    def queue_provision(
        self,
        subscription_id: int,
        triggered_by: Optional[str] = None,
        force: bool = False,
    ) -> str:
        """Queue a provisioning task. Returns task ID."""
        from app.tasks.provisioning_tasks import provision_subscription
        result = provision_subscription.delay(
            subscription_id=subscription_id,
            triggered_by=triggered_by or "manual",
            force=force,
        )
        return result.id

    def queue_deprovision(
        self,
        subscription_id: int,
        triggered_by: Optional[str] = None,
    ) -> str:
        """Queue a deprovisioning task. Returns task ID."""
        from app.tasks.provisioning_tasks import deprovision_subscription
        result = deprovision_subscription.delay(
            subscription_id=subscription_id,
            triggered_by=triggered_by or "manual",
        )
        return result.id

    def queue_provision_update(
        self,
        subscription_id: int,
        triggered_by: Optional[str] = None,
    ) -> str:
        """Queue a provisioning update task. Returns task ID."""
        from app.tasks.provisioning_tasks import update_subscription_provisioning
        result = update_subscription_provisioning.delay(
            subscription_id=subscription_id,
            triggered_by=triggered_by or "manual",
        )
        return result.id

    def get_provisioning_logs(
        self,
        subscription_id: Optional[int] = None,
        filters: Optional[ProvisioningLogFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[ProvisioningLog]:
        """Get provisioning logs."""
        if filters is None:
            filters = ProvisioningLogFilters(subscription_id=subscription_id)
        if pagination is None:
            pagination = PaginationParams(offset=0, limit=25)

        return self._provisioning_svc.list_logs(filters, pagination)

    def test_router_connection(self, router_id: int) -> Dict[str, Any]:
        """Test connection to a router."""
        return self._provisioning_svc.test_router_connection(router_id)

    # =========================================================================
    # BILLING
    # =========================================================================

    def get_billing_info(self, subscription_id: int) -> SubscriptionBillingInfo:
        """Get billing information for a subscription."""
        return self._finance_svc.get_billing_info(subscription_id)

    def generate_invoice(self, subscription_id: int) -> Dict[str, Any]:
        """Generate an invoice for a subscription."""
        return self._finance_svc.generate_subscription_invoice(subscription_id)

    def run_daily_billing(self) -> DailyBillingResult:
        """Run daily billing for all billable subscriptions."""
        return self._billing_svc.run_daily_billing()

    def get_billing_config(self) -> BillingConfig:
        """Get billing configuration."""
        return self._billing_config_svc.get_config()

    def update_billing_config(self, data: Dict[str, Any]) -> BillingConfig:
        """Update billing configuration."""
        return self._billing_config_svc.update_config(data)

    # =========================================================================
    # SERVICE TYPE CONFIGURATION
    # =========================================================================

    def get_service_type_config(self) -> ServiceTypeConfig:
        """Get service type configuration."""
        return self._service_type_config_svc.get_config()

    def update_service_type_config(self, data: Dict[str, Any]) -> ServiceTypeConfig:
        """Update service type configuration."""
        return self._service_type_config_svc.update_config(data)

    def get_grace_period_days(self, service_type: str) -> int:
        """Get grace period days for a service type."""
        return self._service_type_config_svc.get_grace_period_days(service_type)

    # =========================================================================
    # TARIFFS
    # =========================================================================

    def list_tariffs(
        self,
        q: Optional[str] = None,
        tariff_type: Optional[str] = None,
        enabled_only: bool = True,
        page: int = 1,
        per_page: int = 25,
    ) -> Dict[str, Any]:
        """List tariffs with filtering and pagination."""
        tariffs = self._tariff_svc.list_tariffs(
            search=q,
            tariff_type=tariff_type,
            enabled_only=enabled_only,
        )

        # Manual pagination
        total = len(tariffs)
        start = (page - 1) * per_page
        end = start + per_page
        items = tariffs[start:end]

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
        }

    def get_tariff(self, tariff_id: int) -> Tariff:
        """Get a tariff by ID."""
        return self._tariff_svc.get_tariff(tariff_id)

    def get_tariff_subscriber_count(self, tariff_id: int) -> int:
        """Get count of active subscribers using a tariff."""
        return self._tariff_svc.get_subscription_count(tariff_id)

    def get_tariffs_for_upgrade(self, subscription_id: int) -> List[Tariff]:
        """Get tariffs available for upgrade (higher price)."""
        subscription = self._subscription_svc.get_subscription(subscription_id)
        return self._tariff_svc.get_tariffs_above_price(
            float(subscription.price),
            subscription.service_type.value if subscription.service_type else None,
        )

    def get_tariffs_for_downgrade(self, subscription_id: int) -> List[Tariff]:
        """Get tariffs available for downgrade (lower price)."""
        subscription = self._subscription_svc.get_subscription(subscription_id)
        return self._tariff_svc.get_tariffs_below_price(
            float(subscription.price),
            subscription.service_type.value if subscription.service_type else None,
        )

    # =========================================================================
    # PAYMENT SUBSCRIPTIONS
    # =========================================================================

    def list_payment_subscriptions(
        self,
        filters: Optional[PaymentSubscriptionFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[PaymentSubscription]:
        """List payment subscriptions with filtering."""
        if filters is None:
            filters = PaymentSubscriptionFilters()
        if pagination is None:
            pagination = PaginationParams(offset=0, limit=25)

        return self._payment_svc.list_payment_subscriptions(filters, pagination)

    def get_payment_subscription(self, payment_sub_id: int) -> PaymentSubscription:
        """Get a payment subscription by ID."""
        return self._payment_svc.get_payment_subscription(payment_sub_id)

    def create_payment_subscription(
        self,
        data: PaymentSubscriptionCreateData,
    ) -> PaymentSubscription:
        """Create a new payment subscription."""
        return self._payment_svc.create_payment_subscription(data)

    def update_payment_subscription(
        self,
        payment_sub_id: int,
        data: PaymentSubscriptionUpdateData,
    ) -> PaymentSubscription:
        """Update a payment subscription."""
        return self._payment_svc.update_payment_subscription(payment_sub_id, data)

    def pause_payment_subscription(self, payment_sub_id: int) -> PaymentSubscription:
        """Pause a payment subscription."""
        return self._payment_svc.pause(payment_sub_id)

    def resume_payment_subscription(self, payment_sub_id: int) -> PaymentSubscription:
        """Resume a paused payment subscription."""
        return self._payment_svc.resume(payment_sub_id)

    def cancel_payment_subscription(
        self,
        payment_sub_id: int,
        reason: Optional[str] = None,
    ) -> PaymentSubscription:
        """Cancel a payment subscription."""
        return self._payment_svc.cancel(payment_sub_id, reason=reason)

    def retry_payment_subscription(self, payment_sub_id: int) -> Dict[str, Any]:
        """Retry a failed payment subscription charge."""
        return self._payment_svc.retry_charge(payment_sub_id)

    def link_payment_subscription(
        self,
        subscription_id: int,
        payment_sub_id: int,
    ) -> PaymentSubscription:
        """Link a payment subscription to a service subscription."""
        return self._payment_svc.link_to_service_subscription(
            payment_sub_id,
            subscription_id,
        )

    # =========================================================================
    # SERVICE TRANSACTIONS
    # =========================================================================

    def list_service_transactions(
        self,
        filters: Optional[ServiceTransactionFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult:
        """List service transactions with filtering."""
        if filters is None:
            filters = ServiceTransactionFilters()
        if pagination is None:
            pagination = PaginationParams(offset=0, limit=25)

        return self._transaction_svc.list_transactions(filters, pagination)

    def create_service_transaction(
        self,
        data: ServiceTransactionCreateData,
    ) -> Any:
        """Create a service transaction."""
        return self._transaction_svc.create_transaction(data)

    def get_party_transaction_history(
        self,
        party_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> PartyTransactionHistory:
        """Get transaction history for a party."""
        return self._transaction_svc.get_party_history(
            party_id,
            start_date=start_date,
            end_date=end_date,
        )

    # =========================================================================
    # REPORTS & ANALYTICS
    # =========================================================================

    def get_dashboard_summary(self) -> DashboardSummary:
        """Get dashboard summary data."""
        return self._reports_svc.get_dashboard_summary()

    def get_dashboard_kpis(
        self,
        period: ReportPeriod = ReportPeriod.THIS_MONTH,
    ) -> DashboardKPIs:
        """Get dashboard KPIs."""
        return self._reports_svc.get_dashboard_kpis(period)

    def get_mrr_summary(
        self,
        period: ReportPeriod = ReportPeriod.THIS_MONTH,
    ) -> MRRSummary:
        """Get MRR summary."""
        return self._reports_svc.get_mrr_summary(period)

    def get_churn_summary(
        self,
        period: ReportPeriod = ReportPeriod.THIS_MONTH,
    ) -> ChurnSummary:
        """Get churn summary."""
        return self._reports_svc.get_churn_summary(period)

    def get_revenue_summary(
        self,
        period: ReportPeriod = ReportPeriod.THIS_MONTH,
        group_by: ReportGroupBy = ReportGroupBy.DAY,
    ) -> RevenueSummary:
        """Get revenue summary."""
        return self._reports_svc.get_revenue_summary(period, group_by)

    def get_usage_report(
        self,
        period: ReportPeriod = ReportPeriod.THIS_MONTH,
    ) -> Dict[str, Any]:
        """Get usage report."""
        return self._reports_svc.get_usage_report(period)

    def get_provisioning_report(
        self,
        period: ReportPeriod = ReportPeriod.THIS_MONTH,
    ) -> Dict[str, Any]:
        """Get provisioning report."""
        return self._reports_svc.get_provisioning_report(period)

    # =========================================================================
    # RADIUS SETTINGS
    # =========================================================================

    def get_radius_settings(self) -> RADIUSSettingsData:
        """Get RADIUS settings."""
        return self._radius_settings_svc.get_settings()

    def update_radius_settings(self, data: RADIUSSettingsUpdate) -> RADIUSSettingsData:
        """Update RADIUS settings."""
        return self._radius_settings_svc.update_settings(data)

    def list_nas_configs(
        self,
        filters: Optional[NASConfigFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult:
        """List NAS configurations."""
        if filters is None:
            filters = NASConfigFilters()
        if pagination is None:
            pagination = PaginationParams(offset=0, limit=25)

        return self._radius_settings_svc.list_nas_configs(filters, pagination)

    def create_nas_config(self, data: NASConfigData) -> Any:
        """Create a NAS configuration."""
        return self._radius_settings_svc.create_nas_config(data)

    def list_attribute_mappings(
        self,
        filters: Optional[AttributeMappingFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult:
        """List RADIUS attribute mappings."""
        if filters is None:
            filters = AttributeMappingFilters()
        if pagination is None:
            pagination = PaginationParams(offset=0, limit=25)

        return self._radius_settings_svc.list_attribute_mappings(filters, pagination)

    def create_attribute_mapping(self, data: AttributeMappingData) -> Any:
        """Create a RADIUS attribute mapping."""
        return self._radius_settings_svc.create_attribute_mapping(data)

    def test_radius_connection(self) -> Dict[str, Any]:
        """Test RADIUS server connection."""
        return self._radius_settings_svc.test_connection()

    def get_radius_health_status(self) -> Dict[str, Any]:
        """Get RADIUS health status."""
        return self._radius_settings_svc.get_health_status()

    # =========================================================================
    # RADIUS CREDENTIAL GENERATION SETTINGS
    # =========================================================================

    def get_radius_credential_config(self) -> RADIUSCredentialConfig:
        """Get RADIUS credential generation configuration."""
        return self._radius_credential_config_svc.get_config()

    def update_radius_credential_config(self, updates: Dict[str, Any]) -> RADIUSCredentialConfig:
        """Update RADIUS credential generation configuration."""
        return self._radius_credential_config_svc.update_config(updates)

    def reset_radius_credential_config(self) -> RADIUSCredentialConfig:
        """Reset RADIUS credential generation configuration to defaults."""
        return self._radius_credential_config_svc.reset_to_defaults()

    def get_radius_credential_config_schema(self) -> Dict[str, Any]:
        """Get RADIUS credential configuration schema for UI rendering."""
        return self._radius_credential_config_svc.get_schema()
