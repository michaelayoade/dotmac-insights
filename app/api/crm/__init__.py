"""
CRM API Module - Party-based Customer Relationship Management

Core CRM functionality now centers on Parties:
- Parties (persons + organizations) with roles and relations
- Opportunities and pipeline
- Activities (calls, meetings, tasks, notes)

Routes:
========

Parties (/crm/parties):
- GET /parties - List parties with filters
- POST /parties - Create party
- GET /parties/{id} - Get party details
- PATCH /parties/{id} - Update party
- POST /parties/{id}/roles - Add party role
- GET /parties/{id}/roles - List party roles

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
from .parties import router as parties_router
from .opportunities import router as opportunities_router
from .activities import router as activities_router
from .pipeline import router as pipeline_router
from .sales import router as sales_router
from .config import router as config_router

# Create main CRM router
router = APIRouter(prefix="/crm", tags=["crm"])

# Party-based identity endpoints
router.include_router(parties_router, prefix="/parties", tags=["crm-parties"])

# Include other CRM routers
router.include_router(opportunities_router)
router.include_router(activities_router)
router.include_router(pipeline_router)

# Sales documents sub-module (orders, quotations)
router.include_router(sales_router)

# Configuration sub-module (territories, sales-persons, customer-groups)
router.include_router(config_router)
