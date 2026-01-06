"""
CRM API Module - Party-based Customer Relationship Management

Core CRM functionality now centers on Parties:
- Parties (persons + organizations) with roles and relations
- Leads (Party + PartyRole)
- Opportunities and pipeline
- Activities (calls, meetings, tasks, notes)
- Campaigns
- Dashboard with analytics

Routes:
========

Parties (/crm/parties):
- GET /parties - List parties with filters
- POST /parties - Create party
- GET /parties/{id} - Get party details
- PATCH /parties/{id} - Update party
- POST /parties/{id}/roles - Add party role
- GET /parties/{id}/roles - List party roles

Leads (/crm/leads):
- GET /leads - List leads
- POST /leads - Create lead
- GET /leads/{id} - Get lead
- PATCH /leads/{id} - Update lead
- DELETE /leads/{id} - Delete lead
- POST /leads/{id}/qualify - Qualify lead
- POST /leads/{id}/convert/* - Convert lead

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

Campaigns (/crm/campaigns):
- GET /campaigns - List campaigns
- POST /campaigns - Create campaign
- GET /campaigns/{id} - Get campaign
- PATCH /campaigns/{id} - Update campaign
- DELETE /campaigns/{id} - Delete campaign

Dashboard (/crm/dashboard):
- GET /dashboard/summary - Dashboard summary with KPIs
- GET /dashboard/pipeline - Pipeline chart
- GET /dashboard/funnel - Funnel chart
- GET /dashboard/leaderboard - Sales leaderboard

Nurture Sequences (/crm/nurture):
- GET /nurture - List sequences
- POST /nurture - Create sequence
- GET /nurture/{id} - Get sequence
- POST /nurture/{id}/steps - Add step
- POST /nurture/{id}/enroll - Enroll contact

Segments (/crm/segments):
- GET /segments - List segments
- POST /segments - Create segment
- GET /segments/{id}/members - Get members
- POST /segments/{id}/refresh - Refresh dynamic segment

Scoring (/crm/scoring):
- GET /scoring/rules - List scoring rules
- POST /scoring/rules - Create rule
- POST /scoring/calculate - Calculate lead score
- GET /scoring/distribution - Score distribution

Communications (/crm/communications):
- GET /communications - List communications
- POST /communications - Create communication
- POST /communications/bulk - Bulk schedule
- POST /communications/{id}/opened - Record open
"""
from fastapi import APIRouter

# Import routers
from .parties import router as parties_router
from .opportunities import router as opportunities_router
from .activities import router as activities_router
from .pipeline import router as pipeline_router
from .config import router as config_router
from .leads import router as leads_router
from .campaigns import router as campaigns_router
from .dashboard import router as dashboard_router
from .nurture import router as nurture_router
from .segments import router as segments_router
from .scoring import router as scoring_router
from .communications import router as communications_router
from .customer_health import router as customer_health_router

# Create main CRM router
router = APIRouter(prefix="/crm", tags=["crm"])

# Party-based identity endpoints
router.include_router(parties_router, prefix="/parties", tags=["crm-parties"])

# Leads (Party + PartyRole)
router.include_router(leads_router)

# Include other CRM routers
router.include_router(opportunities_router)
router.include_router(activities_router)
router.include_router(pipeline_router)

# Campaigns
router.include_router(campaigns_router)

# Dashboard
router.include_router(dashboard_router)


# Configuration sub-module (territories, sales-persons, customer-groups)
router.include_router(config_router)

# Marketing automation
router.include_router(nurture_router)
router.include_router(segments_router)
router.include_router(scoring_router)
router.include_router(communications_router)

# Customer Health Analytics (CRM-Support Integration)
router.include_router(customer_health_router)
