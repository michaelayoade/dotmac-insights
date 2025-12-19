"""
Unified Contacts API Module

Provides comprehensive contact management endpoints:
- CRUD operations for unified contacts
- Lifecycle management (lead → prospect → customer → churned)
- Bulk operations (update, assign, tag, import, merge)
- Analytics and reporting
- Full-text search

Routes:
- GET /contacts - List contacts with filters
- GET /contacts/leads - List leads only
- GET /contacts/customers - List customers only
- GET /contacts/organizations - List organizations
- POST /contacts - Create contact
- GET /contacts/{id} - Get contact details
- GET /contacts/{id}/persons - Get person contacts for organization
- PATCH /contacts/{id} - Update contact
- DELETE /contacts/{id} - Delete contact

Lifecycle:
- POST /contacts/{id}/qualify - Qualify a lead
- POST /contacts/{id}/convert-to-prospect - Convert lead to prospect
- POST /contacts/{id}/convert-to-customer - Convert to customer
- POST /contacts/{id}/mark-churned - Mark customer as churned
- POST /contacts/{id}/reactivate - Reactivate churned customer
- POST /contacts/{id}/assign - Assign to owner
- POST /contacts/{id}/suspend - Suspend contact
- POST /contacts/{id}/activate - Activate contact

Bulk:
- POST /contacts/bulk/update - Bulk update
- POST /contacts/bulk/assign - Bulk assign
- POST /contacts/bulk/tags - Bulk tag operations
- POST /contacts/bulk/delete - Bulk delete
- POST /contacts/merge - Merge duplicate contacts
- GET /contacts/duplicates - Find duplicates
- POST /contacts/import - Bulk import

Analytics:
- GET /contacts/analytics/dashboard - Dashboard metrics
- GET /contacts/analytics/funnel - Sales funnel
- GET /contacts/analytics/by-category - By category
- GET /contacts/analytics/by-territory - By territory
- GET /contacts/analytics/by-source - By lead source
- GET /contacts/analytics/by-owner - By owner
- GET /contacts/analytics/lifecycle - Lifecycle durations
- GET /contacts/analytics/churn - Churn analysis

Search:
- GET /contacts/search/full-text - Full-text search
"""
from fastapi import APIRouter
from .contacts import router as contacts_router
from .lifecycle import router as lifecycle_router
from .bulk import router as bulk_router
from .analytics import router as analytics_router
from .reconciliation import router as reconciliation_router

router = APIRouter(prefix="/contacts", tags=["contacts"])

# Main CRUD operations
router.include_router(contacts_router)

# Lifecycle management (same prefix, different endpoints)
router.include_router(lifecycle_router)

# Bulk operations
router.include_router(bulk_router)

# Analytics
router.include_router(analytics_router)

# Reconciliation dashboard
router.include_router(reconciliation_router, prefix="/reconciliation")
