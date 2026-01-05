# Marketing Module Implementation Plan

## Overview
Create a standalone `/marketing` module for DotMac BOS with customer journeys, social media management, email campaigns, and external integrations.

## Scope Notes
- **Single-tenant** system (no tenant/org scoping needed)
- **No SMS support** (remove SMS from journeys and services)

## User Requirements
- **Standalone module** at `/marketing` (separate from CRM)
- **Template-based journeys** - pre-built templates users can customize
- **All major social platforms** - Facebook, Instagram, Twitter/X, LinkedIn, WhatsApp
- **Webhook-based + API integrations** with external platforms

## Database Models

### File: `app/models/marketing.py` (NEW)

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `MarketingCampaign` | Parent campaign container | name, type, status, budget, UTM params, metrics |
| `JourneyTemplate` | Pre-built journey blueprints | name, category, template_config (JSON), is_system_template |
| `CustomerJourney` | Active journey instance | template_id, status, entry_trigger, exit_conditions, metrics |
| `JourneyStep` | Individual journey step | step_type (email/whatsapp/wait/condition/webhook), timing, content |
| `JourneyEnrollment` | Contact in journey | party_id, status, current_step, next_action_at, engagement |
| `SocialAccount` | Connected social accounts | platform, account_id, tokens (encrypted), stats |
| `SocialPost` | Scheduled/published posts | account_id, content, media_urls, scheduled_at, metrics |
| `EmailTemplate` | Reusable email templates | subject, body_html, body_text, variables |
| `EmailCampaign` | One-off email sends | template_id, audience_id, schedule, metrics |
| `EmailSend` | Individual send record | campaign_id, party_id, status, tracking |
| `MarketingAudience` | Target segments | name, filter_criteria, member_count |
| `MarketingIntegration` | External platform connections | type, credentials (encrypted), status |
| `MarketingConsent` | Consent state by channel | party_id, channel, status, source, updated_at |
| `SuppressionEntry` | Global opt-out/suppression | party_id, channel, reason, created_at |
| `WebhookEvent` | Idempotency + audit | platform, event_id, received_at, payload_hash |

### Enums
- `MarketingCampaignType`: email, social, multi_channel, journey, paid_ad
- `JourneyStatus`: draft, active, paused, completed, archived
- `JourneyStepType`: email, whatsapp, social_post, wait, condition, split, webhook, task, exit
- `SocialPlatform`: facebook, instagram, twitter, linkedin, whatsapp
- `SocialPostStatus`: draft, scheduled, publishing, published, failed
- `EmailCampaignStatus`: draft, scheduled, sending, sent, paused, cancelled
- `ConsentChannel`: email, whatsapp
- `ConsentStatus`: granted, revoked, pending, unknown

## Service Layer

### Directory: `app/services/marketing/`

| Service | File | Responsibilities |
|---------|------|------------------|
| `JourneyService` | `journey_service.py` | Templates, journeys, steps, enrollments, execution |
| `SocialMediaService` | `social_service.py` | Accounts, posts, scheduling, publishing, metrics sync |
| `EmailCampaignService` | `email_campaign_service.py` | Templates, campaigns, sending, tracking |
| `AudienceService` | `audience_service.py` | Segments, membership, refresh |
| `IntegrationService` | `integration_service.py` | OAuth flows, API clients, webhooks |
| `MarketingAnalyticsService` | `analytics_service.py` | Dashboard metrics, reporting |
| `ConsentService` | `consent_service.py` | Consent checks, suppressions, unsubscribe handling |

### Delivery Rules (applied in services)
- Block sends if `SuppressionEntry` exists for the channel
- Require `MarketingConsent.status == granted` for email and WhatsApp sends
- Enforce local send windows and quiet hours (per campaign or global default)

## Background Tasks

### File: `app/tasks/marketing_tasks.py` (NEW)

| Task | Schedule | Purpose |
|------|----------|---------|
| `process_journey_steps` | Every 1 min | Execute pending journey step actions |
| `publish_scheduled_posts` | Every 1 min | Publish due social media posts |
| `send_email_campaign_batch` | On-demand | Send email batches (100/batch) |
| `sync_social_metrics` | Every 15 min | Fetch engagement from platforms |
| `refresh_audience_segments` | Every 4 hours | Re-evaluate dynamic segments |
| `sync_social_account_tokens` | Every 6 hours | Refresh expiring OAuth tokens |

## Module Structure

### Directory: `app/modules/marketing/`

```
marketing/
├── __init__.py           # MODULE_CONFIG, NAVIGATION, router
├── routes.py             # Dashboard, campaigns
├── journey_routes.py     # Journey builder, enrollments
├── social_routes.py      # Social calendar, compose, accounts
├── email_routes.py       # Email campaigns, templates
├── integration_routes.py # OAuth, webhook handlers
├── consent_routes.py     # Unsubscribe + consent endpoints
└── templates/
    ├── pages/
    │   ├── dashboard.html
    │   ├── campaigns.html
    │   ├── journey_list.html
    │   ├── journey_builder.html
    │   ├── social_calendar.html
    │   ├── social_compose.html
    │   ├── email_campaigns.html
    │   ├── email_templates.html
    │   ├── audiences.html
    │   ├── integrations.html
    │   └── consent.html
    └── partials/
        ├── journey_card.html
        ├── social_post_card.html
        └── ...
```

### Navigation Structure

```python
NAVIGATION = [
    {"section": "Marketing", "href": "/marketing", "links": [
        "Dashboard", "Campaigns", "Journeys", "Journey Templates"
    ]},
    {"section": "Social Media", "href": "/marketing/social", "links": [
        "Calendar", "Compose", "Posts", "Accounts"
    ]},
    {"section": "Email", "href": "/marketing/email", "links": [
        "Campaigns", "Templates", "Analytics"
    ]},
    {"section": "Configuration", "links": [
        "Audiences", "Integrations", "Consent"
    ]},
]
```

## External API Integrations

### Directory: `app/integrations/marketing/`

| Client | File | API |
|--------|------|-----|
| `MetaBusinessClient` | `meta_client.py` | Facebook/Instagram Graph API v18.0 |
| `TwitterClient` | `twitter_client.py` | Twitter API v2 |
| `LinkedInClient` | `linkedin_client.py` | LinkedIn Marketing API v2 |
| `WhatsAppBusinessClient` | `whatsapp_client.py` | WhatsApp Cloud API |

All clients use:
- Circuit breaker pattern (from `app/sync/base.py`)
- Async httpx for HTTP calls
- Encrypted token storage
- Automatic token refresh
- Webhook signature verification + replay protection

## Webhooks and Security

- Verify platform signatures (HMAC) with per-platform secrets
- Store `WebhookEvent` with platform event id + payload hash for idempotency
- Reject replayed or stale events (e.g., > 5 minutes)
- Log verification failures with request metadata (no payload secrets)

## Consent and Unsubscribe

- `GET /marketing/consent` for consent dashboard
- `POST /marketing/consent/unsubscribe` for email unsubscribe (public endpoint)
- `POST /api/marketing/webhooks/whatsapp` for WhatsApp opt-in/out events
- Ensure unsubscribe links in email templates include a signed token

## Scheduling & Time Windows

- Campaigns include `timezone`, `send_window_start`, `send_window_end`
- Journey steps honor campaign or global defaults
- Enforce quiet hours + max frequency per party (optional)

## Pre-built Journey Templates

| Template | Category | Steps |
|----------|----------|-------|
| Welcome Onboarding | onboarding | Welcome → Tour → Feature 1 → Feature 2 → Check-in |
| Lead Nurture | nurture | Education → Case Study → Education 2 → Social Proof → CTA |
| Re-engagement | reactivation | Miss You → Special Offer → Final Reminder |
| Feedback Collection | feedback | Request → Reminder → Thank You |
| Upsell Sequence | promotional | Milestone → Recommendation → Offer → Follow-up |

## Key Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/marketing` | GET | Dashboard with KPIs |
| `/marketing/journeys` | GET | Journey list |
| `/marketing/journeys/templates` | GET | Template gallery |
| `/marketing/journeys/{id}/builder` | GET | Visual builder |
| `/marketing/social/calendar` | GET | Calendar view |
| `/marketing/social/compose` | GET | Multi-platform composer |
| `/marketing/email/campaigns` | GET | Email campaign list |
| `/marketing/email/templates/{id}/edit` | GET | Template editor |
| `/marketing/integrations` | GET | Integration settings |
| `/marketing/consent` | GET | Consent and suppression settings |
| `/marketing/consent/unsubscribe` | POST | Email unsubscribe endpoint |
| `/api/marketing/webhooks/{platform}` | POST | Webhook handlers (signed) |

## Environment Variables

```bash
# Social Media OAuth
META_APP_ID=
META_APP_SECRET=
TWITTER_CLIENT_ID=
TWITTER_CLIENT_SECRET=
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=

# WhatsApp Business
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_BUSINESS_ACCOUNT_ID=

# Webhook signing secrets
META_WEBHOOK_SECRET=
TWITTER_WEBHOOK_SECRET=
LINKEDIN_WEBHOOK_SECRET=
WHATSAPP_WEBHOOK_SECRET=

# Email (existing)
SENDGRID_API_KEY=
EMAIL_UNSUBSCRIBE_SECRET=
DEFAULT_MARKETING_TIMEZONE=UTC

# Feature flag
MARKETING_MODULE_ENABLED=true
```

## Implementation Order

### Phase 1: Database & Foundation
1. Create `app/models/marketing.py` with all models
2. Create Alembic migration
3. Create `app/services/marketing/__init__.py` and type files
4. Create `app/modules/marketing/__init__.py` with MODULE_CONFIG

### Phase 2: Core Services
1. `AudienceService` - segment management
2. `EmailCampaignService` - templates and campaigns
3. `ConsentService` - consent + suppression enforcement
4. `JourneyService` - template-based journey builder

### Phase 3: Social Media
1. OAuth integration clients (Meta, Twitter, LinkedIn)
2. `SocialMediaService` - post scheduling
3. Social calendar UI

### Phase 4: Background Tasks
1. Journey step processor
2. Social post publisher
3. Email batch sender
4. Metrics sync tasks

### Phase 5: Web UI
1. Marketing dashboard
2. Journey builder (template selection + customization)
3. Social media calendar + composer
4. Email campaign management
5. Consent dashboard

### Phase 6: WhatsApp & Webhooks
1. WhatsApp Business API client
2. Inbound webhook handlers (signed)
3. Email tracking (opens/clicks)

### Phase 7: Polish
1. Pre-built journey templates (seed data)
2. Email templates library
3. Testing and documentation

## Files to Create/Modify

### New Files
- `app/models/marketing.py`
- `app/services/marketing/__init__.py`
- `app/services/marketing/journey_service.py`
- `app/services/marketing/journey_types.py`
- `app/services/marketing/social_service.py`
- `app/services/marketing/social_types.py`
- `app/services/marketing/email_campaign_service.py`
- `app/services/marketing/email_types.py`
- `app/services/marketing/audience_service.py`
- `app/services/marketing/integration_service.py`
- `app/services/marketing/analytics_service.py`
- `app/services/marketing/consent_service.py`
- `app/tasks/marketing_tasks.py`
- `app/integrations/marketing/__init__.py`
- `app/integrations/marketing/base.py`
- `app/integrations/marketing/meta_client.py`
- `app/integrations/marketing/twitter_client.py`
- `app/integrations/marketing/linkedin_client.py`
- `app/integrations/marketing/whatsapp_client.py`
- `app/modules/marketing/__init__.py`
- `app/modules/marketing/routes.py`
- `app/modules/marketing/journey_routes.py`
- `app/modules/marketing/social_routes.py`
- `app/modules/marketing/email_routes.py`
- `app/modules/marketing/integration_routes.py`
- `app/modules/marketing/consent_routes.py`
- `app/modules/marketing/templates/pages/*.html`
- `app/modules/marketing/templates/partials/*.html`
- `alembic/versions/YYYYMMDD_add_marketing_module.py`

### Modify
- `app/models/__init__.py` - Add marketing model imports
- `app/worker.py` - Add marketing tasks to beat schedule

## Reference Files
- Module pattern: `app/modules/support/__init__.py`
- Service pattern: `app/services/crm/nurture.py`
- Task pattern: `app/tasks/notification_tasks.py`
- Integration pattern: `app/integrations/payments/providers/paystack/client.py`
