"""
Subscription API Module

Provides subscription management endpoints:
- Dashboard and analytics
- Subscription CRUD and lifecycle
- Tariff/plan management
- Usage tracking
- Session management (RADIUS)
- Service transactions
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

Subscriptions (/subscriptions):
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

Tariffs (/subscriptions/tariffs):
- GET /tariffs - List tariffs
- GET /tariffs/{id} - Get tariff details
- GET /tariffs/{id}/subscribers - Get tariff subscribers

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
