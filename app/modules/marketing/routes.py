"""
Marketing Routes - SSR for campaigns, journeys, social, and email.

All routes delegate to services in app/services/marketing.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Request, Response, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope, csrf_protect
from app.web.context import get_base_context, get_navigation_context
from app.templates.environment import get_template_env
from app.services.errors import ValidationError
from app.core.security import set_flash
from app.models.marketing import SocialPostStatus, SocialPlatform
from app.services.secrets_service import get_secrets

from app.services.marketing import (
    CampaignService,
    JourneyService,
    SocialMediaService,
    EmailCampaignService,
    AudienceService,
    IntegrationService,
    MarketingAnalyticsService,
    ConsentService,
)
from app.services.marketing.consent_service import parse_unsubscribe_token
from app.services.marketing.oauth_service import MarketingOAuthService

RequireMarketingRead = Depends(require_scope("marketing:read"))
RequireMarketingWrite = Depends(require_scope("marketing:write"))

protected_router = APIRouter(prefix="/marketing", tags=["marketing"], dependencies=[RequireMarketingRead])
public_router = APIRouter(prefix="/marketing", tags=["marketing-public"])
templates = get_template_env()


# =============================================================================
# Service Providers
# =============================================================================

def get_campaign_service(db: DB) -> CampaignService:
    return CampaignService(db)


def get_journey_service(db: DB) -> JourneyService:
    return JourneyService(db)


def get_social_service(db: DB) -> SocialMediaService:
    return SocialMediaService(db)


def get_email_service(db: DB) -> EmailCampaignService:
    return EmailCampaignService(db)


def get_audience_service(db: DB) -> AudienceService:
    return AudienceService(db)


def get_integration_service(db: DB) -> IntegrationService:
    return IntegrationService(db)


def get_analytics_service(db: DB) -> MarketingAnalyticsService:
    return MarketingAnalyticsService(db)


def get_consent_service(db: DB) -> ConsentService:
    return ConsentService(db)


def _form_str(form: dict, key: str) -> str:
    value = form.get(key)
    if value is None:
        return ""
    return str(value).strip()


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_time(value: str) -> time | None:
    if not value:
        return None
    try:
        return time.fromisoformat(value)
    except ValueError:
        return None


def _parse_list(raw_value: str) -> list[str]:
    """Parse a comma or newline separated string into a list of trimmed values."""
    if not raw_value:
        return []
    items = []
    for chunk in raw_value.replace(",", "\n").splitlines():
        value = chunk.strip()
        if value:
            items.append(value)
    return items


def _encrypt_secret(value: str) -> str:
    secrets_service = get_secrets()
    return secrets_service.encrypt(value)


# =============================================================================
# Dashboard
# =============================================================================

@protected_router.get("", response_class=HTMLResponse)
async def marketing_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Marketing Dashboard"

    analytics_service = get_analytics_service(db)
    context["stats"] = analytics_service.get_dashboard_stats()
    context["upcoming_sends"] = analytics_service.get_upcoming_sends()
    context["journeys"] = analytics_service.get_active_journeys()
    context["social_posts"] = analytics_service.get_scheduled_posts()
    context["audiences"] = analytics_service.get_top_audiences()

    template = templates.get_template("modules/marketing/templates/pages/dashboard.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# Campaigns
# =============================================================================

@protected_router.get("/campaigns", response_class=HTMLResponse)
async def marketing_campaigns(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Marketing Campaigns"

    campaign_service = get_campaign_service(db)
    context["campaign_highlights"] = campaign_service.get_highlights()
    context["campaigns"] = campaign_service.list_campaigns()

    template = templates.get_template("modules/marketing/templates/pages/campaigns.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# Journeys
# =============================================================================

@protected_router.get("/journeys", response_class=HTMLResponse)
async def marketing_journeys(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Customer Journeys"

    journey_service = get_journey_service(db)
    context["journeys"] = journey_service.list_journeys()
    context["templates"] = journey_service.list_templates()

    template = templates.get_template("modules/marketing/templates/pages/journey_list.html")
    return HTMLResponse(template.render(context))


@protected_router.get("/journeys/templates", response_class=HTMLResponse)
async def marketing_journey_templates(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Journey Templates"

    journey_service = get_journey_service(db)
    context["templates"] = journey_service.list_templates()

    template = templates.get_template("modules/marketing/templates/pages/journey_templates.html")
    return HTMLResponse(template.render(context))


@protected_router.get("/journeys/{journey_id}/builder", response_class=HTMLResponse)
async def marketing_journey_builder(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    journey_id: int,
):
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Journey Builder"

    journey_service = get_journey_service(db)
    context["steps"] = journey_service.get_journey_steps(journey_id)
    context["journey"] = {}
    context["analytics"] = {}

    template = templates.get_template("modules/marketing/templates/pages/journey_builder.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# Social
# =============================================================================

@protected_router.get("/social/calendar", response_class=HTMLResponse)
async def marketing_social_calendar(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Social Calendar"

    social_service = get_social_service(db)
    context["days"] = social_service.list_calendar_days()
    context["social_posts"] = social_service.list_calendar_posts()

    template = templates.get_template("modules/marketing/templates/pages/social_calendar.html")
    return HTMLResponse(template.render(context))


@protected_router.get("/social/compose", response_class=HTMLResponse)
async def marketing_social_compose(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Compose Social Post"

    social_service = get_social_service(db)
    accounts = social_service.list_accounts_for_compose()
    context["accounts"] = accounts

    template = templates.get_template("modules/marketing/templates/pages/social_compose.html")
    return HTMLResponse(template.render(context))


@protected_router.post("/social/compose", dependencies=[RequireMarketingWrite, Depends(csrf_protect)])
async def submit_social_compose(
    request: Request,
    response: Response,
    db: DB,
):
    form = await request.form()
    account_id_raw = _form_str(form, "account_id")
    content = _form_str(form, "content")
    media_urls = _parse_list(_form_str(form, "media_urls"))
    recipients = _parse_list(_form_str(form, "recipients"))
    date_str = _form_str(form, "schedule_date")
    time_str = _form_str(form, "schedule_time")
    action = _form_str(form, "action") or "draft"

    if not account_id_raw.isdigit():
        set_flash(response, "Select a social account.", "error")
        return RedirectResponse(url="/marketing/social/compose", status_code=303)

    content = content.strip()
    if not content:
        set_flash(response, "Add text before scheduling.", "error")
        return RedirectResponse(url="/marketing/social/compose", status_code=303)

    schedule_date = _parse_date(date_str)
    schedule_time = _parse_time(time_str)
    scheduled_at = None
    if action == "schedule":
        if not schedule_date or not schedule_time:
            set_flash(response, "Schedule date and time are required.", "error")
            return RedirectResponse(url="/marketing/social/compose", status_code=303)
        scheduled_at = datetime.combine(schedule_date, schedule_time, tzinfo=timezone.utc)

    social_service = get_social_service(db)
    metrics = {}
    if recipients:
        metrics["recipients"] = recipients

    status = SocialPostStatus.SCHEDULED if scheduled_at else SocialPostStatus.DRAFT

    try:
        social_service.create_post(
            {
                "account_id": int(account_id_raw),
                "content": content,
                "media_urls": media_urls,
                "scheduled_at": scheduled_at,
                "status": status,
                "metrics": metrics,
            }
        )
        db.commit()
        set_flash(response, "Social post saved.", "success")
        return RedirectResponse(url="/marketing/social/posts", status_code=303)
    except ValidationError as exc:
        db.rollback()
        set_flash(response, str(exc), "error")
        return RedirectResponse(url="/marketing/social/compose", status_code=303)


@protected_router.get("/social/posts", response_class=HTMLResponse)
async def marketing_social_posts(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Social Posts"

    social_service = get_social_service(db)
    context["posts"] = social_service.list_posts()

    template = templates.get_template("modules/marketing/templates/pages/social_posts.html")
    return HTMLResponse(template.render(context))


@protected_router.get("/social/accounts", response_class=HTMLResponse)
async def marketing_social_accounts(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Social Accounts"

    social_service = get_social_service(db)
    context["accounts"] = social_service.list_accounts()

    template = templates.get_template("modules/marketing/templates/pages/social_accounts.html")
    return HTMLResponse(template.render(context))


@protected_router.post("/social/accounts", dependencies=[RequireMarketingWrite, Depends(csrf_protect)])
async def create_social_account(
    request: Request,
    response: Response,
    db: DB,
):
    form = await request.form()
    platform_raw = _form_str(form, "platform") or "whatsapp"
    account_id = _form_str(form, "account_id")
    display_name = _form_str(form, "display_name")
    profile_url = _form_str(form, "profile_url")
    access_token = _form_str(form, "access_token")
    default_recipient = _form_str(form, "default_recipient")

    try:
        platform = SocialPlatform(platform_raw)
    except ValueError:
        set_flash(response, "Unsupported platform.", "error")
        return RedirectResponse(url="/marketing/social/accounts", status_code=303)

    if not account_id:
        set_flash(response, "Account ID is required.", "error")
        return RedirectResponse(url="/marketing/social/accounts", status_code=303)

    social_service = get_social_service(db)
    stats = {}
    if default_recipient:
        stats["default_recipient"] = default_recipient

    try:
        social_service.create_account(
            {
                "platform": platform,
                "account_id": account_id,
                "display_name": display_name or None,
                "profile_url": profile_url or None,
                "access_token_encrypted": _encrypt_secret(access_token) if access_token else None,
                "stats": stats,
            }
        )
        db.commit()
        set_flash(response, "Social account created.", "success")
        return RedirectResponse(url="/marketing/social/accounts", status_code=303)
    except ValidationError as exc:
        db.rollback()
        set_flash(response, str(exc), "error")
        return RedirectResponse(url="/marketing/social/accounts", status_code=303)


# =============================================================================
# Email
# =============================================================================

@protected_router.get("/email/campaigns", response_class=HTMLResponse)
async def marketing_email_campaigns(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Email Campaigns"

    email_service = get_email_service(db)
    context["email_kpis"] = email_service.get_kpis()
    context["campaigns"] = email_service.list_campaigns()

    template = templates.get_template("modules/marketing/templates/pages/email_campaigns.html")
    return HTMLResponse(template.render(context))


@protected_router.get("/email/templates", response_class=HTMLResponse)
async def marketing_email_templates(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Email Templates"

    email_service = get_email_service(db)
    context["templates"] = email_service.list_templates()

    template = templates.get_template("modules/marketing/templates/pages/email_templates.html")
    return HTMLResponse(template.render(context))


@protected_router.get("/email/analytics", response_class=HTMLResponse)
async def marketing_email_analytics(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Email Analytics"

    email_service = get_email_service(db)
    context["metrics"] = email_service.get_metrics()
    context["top_campaigns"] = email_service.get_top_campaigns()

    template = templates.get_template("modules/marketing/templates/pages/email_analytics.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# Audiences, Integrations, Consent
# =============================================================================

@protected_router.get("/audiences", response_class=HTMLResponse)
async def marketing_audiences(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Audiences"

    audience_service = get_audience_service(db)
    context["audiences"] = audience_service.list_audiences()

    template = templates.get_template("modules/marketing/templates/pages/audiences.html")
    return HTMLResponse(template.render(context))


@protected_router.get("/integrations", response_class=HTMLResponse)
async def marketing_integrations(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Integrations"

    integration_service = get_integration_service(db)
    context["integrations"] = integration_service.list_integrations()
    callback_base_url = integration_service.get_callback_base_url(str(request.base_url))
    context["callback_base_url"] = callback_base_url
    context["oauth_providers"] = integration_service.list_default_providers()
    whatsapp_integration = integration_service.get_or_create_by_type("whatsapp")
    context["whatsapp_settings"] = whatsapp_integration.settings or {}

    template = templates.get_template("modules/marketing/templates/pages/integrations.html")
    return HTMLResponse(template.render(context))


@protected_router.post("/integrations/callback-settings", dependencies=[RequireMarketingWrite, Depends(csrf_protect)])
async def update_callback_settings(
    request: Request,
    response: Response,
    db: DB,
):
    form = await request.form()
    callback_base_url = _form_str(form, "callback_base_url")
    if not callback_base_url:
        set_flash(response, "Callback base URL is required.", "error")
        return RedirectResponse(url="/marketing/integrations", status_code=303)

    integration_service = get_integration_service(db)
    for provider in integration_service.list_default_providers():
        integration_service.update_settings_by_type(
            provider["id"],
            {"callback_base_url": callback_base_url.rstrip("/")},
        )
    db.commit()
    set_flash(response, "Callback URL saved.", "success")
    return RedirectResponse(url="/marketing/integrations", status_code=303)


@protected_router.post("/integrations/custom", dependencies=[RequireMarketingWrite, Depends(csrf_protect)])
async def create_custom_integration(
    request: Request,
    response: Response,
    db: DB,
):
    form = await request.form()
    name = _form_str(form, "name")
    integration_type = _form_str(form, "integration_type")
    description = _form_str(form, "description")
    webhook_url = _form_str(form, "webhook_url")
    credentials = _form_str(form, "credentials")

    if not name or not integration_type:
        set_flash(response, "Name and type are required.", "error")
        return RedirectResponse(url="/marketing/integrations", status_code=303)

    integration_service = get_integration_service(db)
    integration_service.create_custom_integration(
        {
            "name": name,
            "integration_type": integration_type,
            "description": description,
            "webhook_url": webhook_url,
            "credentials": credentials or None,
        }
    )
    db.commit()
    set_flash(response, "Custom integration created.", "success")
    return RedirectResponse(url="/marketing/integrations", status_code=303)


@protected_router.post("/integrations/whatsapp-settings", dependencies=[RequireMarketingWrite, Depends(csrf_protect)])
async def update_whatsapp_settings(
    request: Request,
    response: Response,
    db: DB,
):
    form = await request.form()
    phone_number_id = _form_str(form, "phone_number_id")
    default_recipient = _form_str(form, "default_recipient")

    if not phone_number_id:
        set_flash(response, "WhatsApp phone number ID is required.", "error")
        return RedirectResponse(url="/marketing/integrations", status_code=303)

    integration_service = get_integration_service(db)
    integration_service.update_settings_by_type(
        "whatsapp",
        {
            "phone_number_id": phone_number_id,
            "default_recipient": default_recipient or None,
        },
    )
    db.commit()
    set_flash(response, "WhatsApp settings saved.", "success")
    return RedirectResponse(url="/marketing/integrations", status_code=303)


@protected_router.get("/integrations/{provider}/connect", dependencies=[RequireMarketingWrite])
async def connect_integration(
    request: Request,
    response: Response,
    db: DB,
    provider: str,
):
    integration_service = get_integration_service(db)
    callback_base_url = integration_service.get_callback_base_url(str(request.base_url))
    oauth_service = MarketingOAuthService(integration_service)
    try:
        auth_url = oauth_service.build_authorize_url(provider, callback_base_url)
        db.commit()
        return RedirectResponse(url=auth_url, status_code=302)
    except Exception as exc:
        db.rollback()
        set_flash(response, str(exc), "error")
        return RedirectResponse(url="/marketing/integrations", status_code=303)


@protected_router.get("/integrations/{provider}/callback", dependencies=[RequireMarketingWrite])
async def integration_callback(
    request: Request,
    response: Response,
    db: DB,
    provider: str,
    code: str | None = None,
    state: str | None = None,
):
    if not code or not state:
        set_flash(response, "Invalid OAuth callback.", "error")
        return RedirectResponse(url="/marketing/integrations", status_code=303)

    integration_service = get_integration_service(db)
    callback_base_url = integration_service.get_callback_base_url(str(request.base_url))
    oauth_service = MarketingOAuthService(integration_service)
    try:
        await oauth_service.handle_callback(provider, code, state, callback_base_url)
        db.commit()
        set_flash(response, "Integration connected.", "success")
    except Exception as exc:
        db.rollback()
        set_flash(response, str(exc), "error")
    return RedirectResponse(url="/marketing/integrations", status_code=303)


@protected_router.get("/consent", response_class=HTMLResponse)
async def marketing_consent(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Consent & Suppression"

    consent_service = get_consent_service(db)
    context["overview"] = consent_service.get_overview()
    context["records"] = consent_service.list_records()
    context["suppressions"] = consent_service.list_suppressions()

    template = templates.get_template("modules/marketing/templates/pages/consent.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# Public Unsubscribe
# =============================================================================

@public_router.get("/consent/unsubscribe", response_class=HTMLResponse)
async def marketing_unsubscribe_form(
    request: Request,
    response: Response,
):
    context = get_base_context(request, response)
    context["navigation"] = []
    context["page_title"] = "Unsubscribe"
    context["token"] = request.query_params.get("token", "")

    template = templates.get_template("modules/marketing/templates/pages/consent_unsubscribe.html")
    return HTMLResponse(template.render(context))


@public_router.post("/consent/unsubscribe", response_class=HTMLResponse)
async def marketing_unsubscribe(
    request: Request,
    response: Response,
    db: DB,
):
    context = get_base_context(request, response)
    context["navigation"] = []
    context["page_title"] = "Unsubscribe"

    form = await request.form()
    token = (form.get("token") or request.query_params.get("token") or "").strip()
    context["token"] = token

    consent_service = get_consent_service(db)
    try:
        party_id, channel = parse_unsubscribe_token(token)
        consent_service.unsubscribe(party_id, channel, source="unsubscribe_link")
        db.commit()
        context["status"] = "success"
    except ValidationError as exc:
        db.rollback()
        context["status"] = "error"
        context["error_message"] = str(exc)

    template = templates.get_template("modules/marketing/templates/pages/consent_unsubscribe.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# Router Export
# =============================================================================

router = APIRouter()
router.include_router(protected_router)
router.include_router(public_router)
