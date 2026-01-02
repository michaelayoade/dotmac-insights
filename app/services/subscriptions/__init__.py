"""Subscription services module.

This module provides services for managing subscriptions:
- SubscriptionService: Service subscriptions (internet, voice, etc.)
- PaymentSubscriptionService: Recurring billing subscriptions
- TariffService: Tariff/plan management
- ProvisioningService: MikroTik/RADIUS provisioning orchestration
- UsageService: Bandwidth/traffic usage tracking
- BillingService: Billing operations including daily billing
- SubscriptionFinanceService: Invoice/payment integration
- SessionService: Active RADIUS session management
- BillingConfigService: Billing configuration management
- ServiceTypeConfigService: Service type configuration (SLAs, fees, lifecycle)
- ServiceTransactionService: Service transaction tracking and audit trail
- SubscriptionReportsService: Reports and dashboard analytics
"""
from .subscriptions import (
    SubscriptionService,
    UpgradeResult,
    DowngradeResult,
    RenewalResult,
)
from .payment_subscriptions import PaymentSubscriptionService
from .tariffs import TariffService
from .provisioning import ProvisioningService
from .usage import UsageService
from .billing import BillingService
from .finance import SubscriptionFinanceService
from .sessions import SessionService
from .billing_config import BillingConfigService, BillingConfig, get_billing_config

# Service type configuration
from .service_type_config import (
    ServiceTypeConfigService,
    ServiceTypeConfig,
    ServiceTypeDefinition,
    LifecycleSettings,
    PlanChangeSettings,
    ContractSettings,
    get_service_type_config,
    SERVICE_TYPE_CONFIG_SCHEMA,
)

# Service transactions
from .service_transactions import (
    ServiceTransactionService,
    ServiceTransactionType,
    ServiceTransactionStatus,
    ServiceTransactionFilters,
    ServiceTransactionCreateData,
    ServiceTransactionSummary,
    PartyTransactionHistory,
)

# RADIUS settings
from .radius_settings import RADIUSSettingsService
from .radius_settings_types import (
    RADIUSServerConfig,
    RADIUSFailoverConfig,
    AuthenticationConfig,
    AccountingConfig,
    SessionLimitConfig,
    CoAConfig,
    BandwidthConfig,
    IPPoolConfig,
    NASDefaultsConfig,
    RADIUSDBConfig,
    LoggingConfig,
    RADIUSSettingsData,
    RADIUSSettingsUpdate,
    AttributeMappingData,
    AttributeMappingFilters,
    NASConfigData,
    NASConfigFilters,
    DictionaryEntryData,
    DictionaryFilters,
    RADIUSTestResult,
    CoATestResult,
    RADIUSHealthStatus,
)

# Reports and analytics
from .reports import (
    SubscriptionReportsService,
    ReportPeriod,
    ReportGroupBy,
    # Dashboard
    DashboardSummary,
    DashboardKPIs,
    DashboardCharts,
    # MRR
    MRRSummary,
    MRRBreakdown,
    MRRTrend,
    MRRMovement,
    # Churn
    ChurnSummary,
    ChurnByReason,
    RetentionCohort,
    # Revenue
    RevenueSummary,
    RevenueByType,
    RevenueByPlan,
    ARAgingSummary,
    # Usage
    UsageReport,
    TopUsersReport,
    UsageTrend,
    # Provisioning
    ProvisioningReport,
    ProvisioningSuccessRate,
    # Customer
    CustomerLTVReport,
    CustomerSegment,
)

from .subscription_types import (
    # Core subscription types
    SubscriptionFilters,
    SubscriptionCreateData,
    SubscriptionUpdateData,
    NetworkAssignmentData,
    ProvisioningConfigData,
    StatusTransition,
    SubscriptionStats,
    # Provisioning types
    ProvisioningRequest,
    ProvisioningResult,
    ProvisioningLogFilters,
    ProvisioningLogEntry,
    RouterConnectionTest,
    # Usage types
    UsageFilters,
    UsageRecord,
    UsageSummary,
    DataCapStatus,
    # RADIUS types
    RADIUSUserConfig,
    RADIUSRateLimit,
    RADIUSSessionInfo,
    # Financial types
    SubscriptionInvoiceData,
    SubscriptionBillingInfo,
    # Billing types (daily/recurring)
    DailyBillingConfig,
    DailyBillingResult,
    BillingRunSummary,
    BillableSubscription,
    ChargeRequest,
    ChargeResult,
    # Session types (RADIUS/NAS)
    ActiveSession,
    SessionFilters,
    SessionHistory,
    DisconnectRequest,
    DisconnectResult,
    SessionStats,
)

from .payment_subscription_types import (
    PaymentSubscriptionFilters,
    PaymentSubscriptionCreateData,
    PaymentSubscriptionUpdateData,
    BillingActionResult,
    PaymentSubscriptionStats,
)

__all__ = [
    # Services
    "SubscriptionService",
    "PaymentSubscriptionService",
    "TariffService",
    "ProvisioningService",
    "UsageService",
    "BillingService",
    "SubscriptionFinanceService",
    "SessionService",
    "BillingConfigService",
    "ServiceTypeConfigService",
    "ServiceTransactionService",
    "SubscriptionReportsService",
    "RADIUSSettingsService",
    # Configuration classes
    "BillingConfig",
    "get_billing_config",
    "ServiceTypeConfig",
    "ServiceTypeDefinition",
    "LifecycleSettings",
    "PlanChangeSettings",
    "ContractSettings",
    "get_service_type_config",
    "SERVICE_TYPE_CONFIG_SCHEMA",
    # Service transaction types
    "ServiceTransactionType",
    "ServiceTransactionStatus",
    "ServiceTransactionFilters",
    "ServiceTransactionCreateData",
    "ServiceTransactionSummary",
    "PartyTransactionHistory",
    # Lifecycle results
    "UpgradeResult",
    "DowngradeResult",
    "RenewalResult",
    # Core subscription types
    "SubscriptionFilters",
    "SubscriptionCreateData",
    "SubscriptionUpdateData",
    "NetworkAssignmentData",
    "ProvisioningConfigData",
    "StatusTransition",
    "SubscriptionStats",
    # Provisioning types
    "ProvisioningRequest",
    "ProvisioningResult",
    "ProvisioningLogFilters",
    "ProvisioningLogEntry",
    "RouterConnectionTest",
    # Usage types
    "UsageFilters",
    "UsageRecord",
    "UsageSummary",
    "DataCapStatus",
    # RADIUS types
    "RADIUSUserConfig",
    "RADIUSRateLimit",
    "RADIUSSessionInfo",
    # Financial types
    "SubscriptionInvoiceData",
    "SubscriptionBillingInfo",
    # Billing types (daily/recurring)
    "DailyBillingConfig",
    "DailyBillingResult",
    "BillingRunSummary",
    "BillableSubscription",
    "ChargeRequest",
    "ChargeResult",
    # Session types (RADIUS/NAS)
    "ActiveSession",
    "SessionFilters",
    "SessionHistory",
    "DisconnectRequest",
    "DisconnectResult",
    "SessionStats",
    # Payment subscription types
    "PaymentSubscriptionFilters",
    "PaymentSubscriptionCreateData",
    "PaymentSubscriptionUpdateData",
    "BillingActionResult",
    "PaymentSubscriptionStats",
    # Report types
    "ReportPeriod",
    "ReportGroupBy",
    "DashboardSummary",
    "DashboardKPIs",
    "DashboardCharts",
    "MRRSummary",
    "MRRBreakdown",
    "MRRTrend",
    "MRRMovement",
    "ChurnSummary",
    "ChurnByReason",
    "RetentionCohort",
    "RevenueSummary",
    "RevenueByType",
    "RevenueByPlan",
    "ARAgingSummary",
    "UsageReport",
    "TopUsersReport",
    "UsageTrend",
    "ProvisioningReport",
    "ProvisioningSuccessRate",
    "CustomerLTVReport",
    "CustomerSegment",
    # RADIUS settings types
    "RADIUSServerConfig",
    "RADIUSFailoverConfig",
    "AuthenticationConfig",
    "AccountingConfig",
    "SessionLimitConfig",
    "CoAConfig",
    "BandwidthConfig",
    "IPPoolConfig",
    "NASDefaultsConfig",
    "RADIUSDBConfig",
    "LoggingConfig",
    "RADIUSSettingsData",
    "RADIUSSettingsUpdate",
    "AttributeMappingData",
    "AttributeMappingFilters",
    "NASConfigData",
    "NASConfigFilters",
    "DictionaryEntryData",
    "DictionaryFilters",
    "RADIUSTestResult",
    "CoATestResult",
    "RADIUSHealthStatus",
]
