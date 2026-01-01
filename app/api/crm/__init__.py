"""
CRM API Module - Unified Customer Relationship Management

Consolidates all CRM functionality:
- Contacts (leads, prospects, customers, churned, persons)
- Lifecycle management (lead → prospect → customer → churned)
- Opportunities and pipeline
- Activities (calls, meetings, tasks, notes)
- Bulk operations
- Analytics

Routes:
========

Contacts (/crm/contacts):
- GET /contacts - List contacts with filters
- GET /contacts/leads - List leads only
- GET /contacts/customers - List customers only
- GET /contacts/organizations - List organizations
- POST /contacts - Create contact
- GET /contacts/{id} - Get contact details
- GET /contacts/{id}/persons - Get person contacts for organization
- PATCH /contacts/{id} - Update contact
- DELETE /contacts/{id} - Delete contact
- GET /contacts/search/full-text - Full-text search

Lifecycle (/crm/contacts):
- POST /contacts/{id}/qualify - Qualify a lead
- POST /contacts/{id}/convert-to-prospect - Convert lead to prospect
- POST /contacts/{id}/convert-to-customer - Convert to customer
- POST /contacts/{id}/mark-churned - Mark customer as churned
- POST /contacts/{id}/reactivate - Reactivate churned customer
- POST /contacts/{id}/assign - Assign to owner
- POST /contacts/{id}/suspend - Suspend contact
- POST /contacts/{id}/activate - Activate contact

Opportunities (/crm/opportunities):
- GET /opportunities - List opportunities
- POST /opportunities - Create opportunity
- GET /opportunities/{id} - Get opportunity
- PATCH /opportunities/{id} - Update opportunity
- DELETE /opportunities/{id} - Delete opportunity

Pipeline (/crm/pipeline):
- GET /pipeline - Kanban view of pipeline
- GET /pipeline/stages - Get pipeline stages
- POST /pipeline/stages - Create stage
- PATCH /pipeline/{id}/stage - Move opportunity to stage

Activities (/crm/activities):
- GET /activities - List activities
- POST /activities - Create activity
- GET /activities/{id} - Get activity
- PATCH /activities/{id} - Update activity
- DELETE /activities/{id} - Delete activity
"""
from fastapi import APIRouter

# Import routers
from .contacts_crud import router as contacts_crud_router
from .lifecycle import router as lifecycle_router
from .leads import router as leads_router
from .opportunities import router as opportunities_router
from .activities import router as activities_router
from .pipeline import router as pipeline_router
from .sales import router as sales_router
from .config import router as config_router

# Create main CRM router
router = APIRouter(prefix="/crm", tags=["crm"])

# Contact management endpoints - mount at /crm/contacts
contacts_router = APIRouter(prefix="/contacts", tags=["crm-contacts"])
contacts_router.include_router(contacts_crud_router)
contacts_router.include_router(lifecycle_router)

router.include_router(contacts_router)

# Include other CRM routers
router.include_router(leads_router)
router.include_router(opportunities_router)
router.include_router(activities_router)
router.include_router(pipeline_router)

# Sales documents sub-module (orders, quotations)
router.include_router(sales_router)

# Configuration sub-module (territories, sales-persons, customer-groups)
router.include_router(config_router)
