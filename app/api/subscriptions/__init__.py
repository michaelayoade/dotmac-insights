"""
Subscription API Module

Provides subscription management endpoints:
- Dashboard and analytics
- Subscription CRUD and lifecycle
- Tariff/plan management
- Usage tracking
- Session management (RADIUS)
- Service transactions
- Billing operations
- Provisioning operations
- Configuration

Routes:
========

Dashboard (/subscriptions/dashboard):
- GET /dashboard - Main dashboard with KPIs and charts
- GET /dashboard/kpis - Just KPIs
- GET /dashboard/charts - Just chart data

Reports (/subscriptions/reports):
- GET /reports/mrr - MRR analytics
- GET /reports/churn - Churn analysis
- GET /reports/revenue - Revenue summary
- GET /reports/usage - Usage analytics
- GET /reports/provisioning - Provisioning success rates
- GET /reports/ltv - Customer lifetime value

Subscriptions (/subscriptions/subscriptions):
- GET / - List subscriptions
- POST / - Create subscription
- GET /{id} - Get subscription details
- PATCH /{id} - Update subscription
- DELETE /{id} - Cancel subscription
- POST /{id}/activate - Activate subscription
- POST /{id}/suspend - Suspend subscription
- POST /{id}/reactivate - Reactivate subscription
- POST /{id}/upgrade - Upgrade to higher plan
- POST /{id}/downgrade - Downgrade to lower plan
- POST /{id}/renew - Renew subscription
- POST /{id}/provision - Queue provisioning
- POST /{id}/deprovision - Queue deprovisioning
- POST /{id}/disconnect - Force disconnect session
- POST /{id}/provision-update - Queue provisioning update
- POST /{id}/extend-grace - Extend grace period
- POST /bulk/status - Bulk status change
- POST /bulk/plan - Bulk plan change

Tariffs (/subscriptions/tariffs):
- GET /tariffs - List tariffs
- POST /tariffs - Create tariff
- GET /tariffs/{id} - Get tariff details
- PATCH /tariffs/{id} - Update tariff
- DELETE /tariffs/{id} - Soft delete tariff
- POST /tariffs/{id}/toggle - Toggle enabled status
- GET /tariffs/{id}/subscribers - Get tariff subscribers
- GET /tariffs/{id}/stats - Get tariff statistics

Usage (/subscriptions/usage):
- GET /usage - Usage records
- GET /usage/{subscription_id} - Subscription usage
- GET /usage/{subscription_id}/summary - Usage summary

Sessions (/subscriptions/sessions):
- GET /sessions - Active sessions
- GET /sessions/{subscription_id} - Subscription sessions
- POST /sessions/{id}/disconnect - Disconnect session

Transactions (/subscriptions/transactions):
- GET /transactions - Service transactions
- GET /transactions/{subscription_id} - Subscription transactions
- GET /transactions/summary - Transaction summary

Billing (/subscriptions/billing):
- POST /billing/run-daily - Trigger daily billing run
- GET /billing/billable - List billable subscriptions
- GET /billing/stats - Billing statistics
- GET /billing/{subscription_id}/info - Subscription billing info

Provisioning (/subscriptions/provisioning):
- GET /provisioning/logs - List provisioning logs
- GET /provisioning/logs/{id} - Get log details
- POST /provisioning/logs/{id}/retry - Retry failed operation
- GET /provisioning/stats - Provisioning statistics
- POST /provisioning/test-router/{id} - Test router connection

Config (/subscriptions/config):
- GET /config/billing - Billing configuration
- PUT /config/billing - Update billing config
- GET /config/service-types - Service type configuration
- PUT /config/service-types - Update service type config

RADIUS Settings (/subscriptions/radius):
- GET /radius - Get RADIUS settings
- PUT /radius - Update RADIUS settings
- POST /radius/seed-defaults - Seed default settings
- GET /radius/server - Server configuration
- GET /radius/authentication - Auth configuration
- GET /radius/accounting - Accounting configuration
- GET /radius/coa - CoA configuration
- GET /radius/bandwidth - Bandwidth configuration
- GET /radius/attribute-mappings - List attribute mappings
- POST /radius/attribute-mappings - Create mapping
- GET /radius/nas-configs - List NAS configurations
- POST /radius/nas-configs - Create NAS config
- GET /radius/dictionary - List dictionary entries
- POST /radius/test-connection - Test RADIUS server
- POST /radius/test-coa - Test CoA connectivity
- GET /radius/health - System health status

RADIUS Credentials (/subscriptions/radius-credentials):
- GET /radius-credentials/config - Get credential config
- PUT /radius-credentials/config - Update credential config
- POST /radius-credentials/config/reset - Reset to defaults
- GET /radius-credentials/config/schema - Get UI schema
- POST /radius-credentials/preview - Preview generation
- POST /radius-credentials/{id}/regenerate - Regenerate credentials
- POST /radius-credentials/bulk/regenerate - Bulk regenerate
- GET /radius-credentials/validate-username - Check availability
- GET /radius-credentials/format-types - List format types
- GET /radius-credentials/sequence/current - Current counter
- POST /radius-credentials/sequence/reset - Reset counter

Data Bundles (/subscriptions/bundles):
- POST /bundles/products - Create bundle product
- GET /bundles/products - List bundle products
- GET /bundles/products/{id} - Get bundle product
- PATCH /bundles/products/{id} - Update bundle product
- DELETE /bundles/products/{id} - Delete bundle product
- POST /bundles/subscriptions/{id}/purchase - Purchase bundle
- GET /bundles/subscriptions/{id}/status - Get bundle status
- POST /bundles/{id}/activate - Activate bundle
- POST /bundles/{id}/cancel - Cancel bundle
- GET /bundles/{id} - Get bundle
- POST /bundles/usage - Record usage
- GET /bundles/subscriptions/{id}/usage - Get usage summary
- POST /bundles/{id}/handle-exhaustion - Handle exhaustion
- GET /bundles/analytics - Get analytics
- GET /bundles/analytics/revenue - Get revenue by product
"""
from fastapi import APIRouter

from .dashboard import router as dashboard_router
from .reports import router as reports_router
from .subscriptions import router as subscriptions_router
from .tariffs import router as tariffs_router
from .usage import router as usage_router
from .sessions import router as sessions_router
from .transactions import router as transactions_router
from .config import router as config_router
from .radius_settings import router as radius_settings_router
from .radius_credentials import router as radius_credentials_router
from .billing import router as billing_router
from .provisioning import router as provisioning_router
from .bundles import router as bundles_router

# Create main subscriptions router
router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

# Dashboard and analytics
router.include_router(dashboard_router, prefix="/dashboard", tags=["subscriptions-dashboard"])
router.include_router(reports_router, prefix="/reports", tags=["subscriptions-reports"])

# Core subscription management
router.include_router(subscriptions_router, prefix="/subscriptions", tags=["subscriptions-core"])

# Supporting features
router.include_router(tariffs_router, prefix="/tariffs", tags=["subscriptions-tariffs"])
router.include_router(usage_router, prefix="/usage", tags=["subscriptions-usage"])
router.include_router(sessions_router, prefix="/sessions", tags=["subscriptions-sessions"])
router.include_router(transactions_router, prefix="/transactions", tags=["subscriptions-transactions"])

# Configuration
router.include_router(config_router, prefix="/config", tags=["subscriptions-config"])
router.include_router(radius_settings_router, prefix="/radius", tags=["subscriptions-radius"])
router.include_router(radius_credentials_router, prefix="/radius-credentials", tags=["subscriptions-radius-credentials"])

# Billing and provisioning operations
router.include_router(billing_router, prefix="/billing", tags=["subscriptions-billing"])
router.include_router(provisioning_router, prefix="/provisioning", tags=["subscriptions-provisioning"])

# Data bundles
router.include_router(bundles_router, prefix="/bundles", tags=["subscriptions-bundles"])
