"""
Web router aggregation for SSR frontend.

Mounts all module routers and provides common endpoints.

Module System:
- Modules with MODULE_CONFIG are auto-discovered via ModuleRegistry
- Legacy modules are still manually imported below
- Run ModuleRegistry.discover_modules() to register new-style modules
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Request, Response, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import or_, func

from app.web.dependencies import (
    SessionUser,
    OptionalUser,
    CSRFToken,
    DB,
    ensure_csrf_token,
)
from app.web.context import get_base_context, get_navigation_context, build_pagination_context
from app.web.modules import ModuleRegistry
from app.templates.environment import get_template_env

# Services imports
from app.services.identity import party_service
from app.services.support.tickets import TicketService
from app.services.accounting.receivables import ReceivablesService
from app.services.accounting.settings import AccountingSettingsService
from app.services.accounting.approvals import ApprovalsService
from app.services.workflow_task_service import WorkflowTaskService
from app.services.subscriptions import SubscriptionService
from app.services.marketing.analytics_service import MarketingAnalyticsService
from app.currency import get_currency_symbol
from app.config import settings

logger = logging.getLogger(__name__)

# =============================================================================
# MODULE AUTO-DISCOVERY
# =============================================================================
# Note: Module discovery is deferred to avoid circular imports during startup.
# ModuleRegistry.discover_modules() is called lazily when needed (e.g., by get_base_context)
# or explicitly at app startup via the lifespan handler.

# =============================================================================
# WEB ROUTER
# =============================================================================
web_router = APIRouter(tags=["web"])

# Template environment
templates = get_template_env()


@web_router.get("/", response_class=HTMLResponse)
async def launcher(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Launcher page - module grid with favorites and badges."""
    from datetime import datetime
    from app.services.launcher import LauncherService
    from app.web.context import get_module_registry

    context = get_base_context(request, response, user, csrf_token)
    # NOTE: Do NOT include navigation - clean launcher UI
    context["page_title"] = "Launcher"
    context["now"] = datetime.utcnow()

    # Get launcher service for favorites
    launcher_service = LauncherService(db, user)
    favorites = launcher_service.get_user_favorites()
    context["favorites"] = favorites

    # Get modules from registry, filtered by user permissions
    all_modules = get_module_registry(user)

    group_aliases = {
        "analytics": "Admin",
        "system": "Admin",
    }

    group_themes = {
        "customer": "customer",
        "finance": "finance",
        "procurement": "procurement",
        "facility": "facility",
        "operations": "operations",
        "isp": "isp",
        "people": "people",
        "marketing": "marketing",
        "analytics": "analytics",
        "system": "system",
        "admin": "system",
    }
    fallback_themes = ["teal", "lime", "rose", "purple"]

    def resolve_theme(module: dict, index: int) -> str:
        group = (module.get("group") or "").lower()
        for key, theme in group_themes.items():
            if key in group:
                return theme
        return fallback_themes[index % len(fallback_themes)]

    theme_by_id = {}
    for idx, module in enumerate(all_modules):
        raw_group = module.get("group", "Other")
        mapped_group = group_aliases.get(raw_group.lower(), raw_group)
        themed_module = {**module, "group": mapped_group}
        theme_by_id[module.get("id")] = resolve_theme(themed_module, idx)

    # Mark favorites on all modules
    modules = []
    for module in all_modules:
        raw_group = module.get("group", "Other")
        mapped_group = group_aliases.get(raw_group.lower(), raw_group)
        modules.append({
            **module,
            "group": mapped_group,
            "is_favorite": module["id"] in favorites,
            "icon_theme": theme_by_id.get(module.get("id")),
        })

    # Group modules by domain
    DOMAIN_ORDER = [
        "Customer", "Finance", "Procurement", "Facility",
        "Operations", "ISP", "People", "Marketing", "Admin"
    ]

    domain_groups = {}
    for module in modules:
        group = module.get("group", "Other")
        if group not in domain_groups:
            domain_groups[group] = []
        domain_groups[group].append(module)

    # Sort domains by defined order
    sorted_domains = []
    for domain in DOMAIN_ORDER:
        if domain in domain_groups:
            sorted_domains.append({
                "name": domain,
                "modules": domain_groups[domain]
            })
    # Add any remaining domains not in order
    for domain, mods in domain_groups.items():
        if domain not in DOMAIN_ORDER:
            sorted_domains.append({"name": domain, "modules": mods})

    context["domains"] = sorted_domains
    context["modules"] = modules

    # Get favorite modules for top section (maintain order)
    favorite_modules = []
    for fav_id in favorites:
        for module in all_modules:
            if module["id"] == fav_id:
                raw_group = module.get("group", "Other")
                mapped_group = group_aliases.get(raw_group.lower(), raw_group)
                favorite_modules.append({
                    **module,
                    "group": mapped_group,
                    "is_favorite": True,
                    "icon_theme": theme_by_id.get(module.get("id")),
                })
                break
    context["favorite_modules"] = favorite_modules

    template = templates.get_template("pages/launcher.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# LAUNCHER FAVORITES API
# =============================================================================


@web_router.post("/launcher/favorites/{module_id}", response_class=HTMLResponse)
async def add_favorite(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    module_id: str,
):
    """Add module to favorites (HTMX endpoint)."""
    from app.services.launcher import LauncherService
    from app.core.security import is_htmx_request

    launcher_service = LauncherService(db, user)
    launcher_service.add_favorite(module_id)

    if is_htmx_request(request):
        # Return updated star button (now filled/active)
        return HTMLResponse(f'''
            <button
                class="absolute top-3 right-3 p-1.5 rounded-lg text-amber-400 hover:text-amber-400 hover:bg-amber-50 transition-colors z-10"
                hx-delete="/launcher/favorites/{module_id}"
                hx-swap="outerHTML"
                @click.prevent.stop
                aria-label="Remove from favorites"
                data-testid="favorite-btn-{module_id}"
            >
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.176 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.93 8.72c-.783-.57-.38-1.81.588-1.81h3.462a1 1 0 00.95-.69l1.07-3.292z"/>
                </svg>
            </button>
        ''')

    # Full page redirect for non-HTMX
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/", status_code=303)


@web_router.delete("/launcher/favorites/{module_id}", response_class=HTMLResponse)
async def remove_favorite(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    module_id: str,
):
    """Remove module from favorites (HTMX endpoint)."""
    from app.services.launcher import LauncherService
    from app.core.security import is_htmx_request

    launcher_service = LauncherService(db, user)
    launcher_service.remove_favorite(module_id)

    if is_htmx_request(request):
        # Return updated star button (now outline/inactive)
        return HTMLResponse(f'''
            <button
                class="absolute top-3 right-3 p-1.5 rounded-lg text-gray-300 hover:text-amber-400 hover:bg-amber-50 transition-colors z-10"
                hx-post="/launcher/favorites/{module_id}"
                hx-swap="outerHTML"
                @click.prevent.stop
                aria-label="Add to favorites"
                data-testid="favorite-btn-{module_id}"
            >
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.176 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.93 8.72c-.783-.57-.38-1.81.588-1.81h3.462a1 1 0 00.95-.69l1.07-3.292z"/>
                </svg>
            </button>
        ''')

    # Full page redirect for non-HTMX
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/", status_code=303)


@web_router.get("/launcher/badge/{module_id}", response_class=HTMLResponse)
async def module_badge(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    module_id: str,
):
    """Get module badge/stats (HTMX endpoint for lazy loading)."""
    from app.services.launcher import LauncherService

    launcher_service = LauncherService(db, user)
    badge = launcher_service.get_module_badge(module_id)

    if not badge:
        return HTMLResponse("")

    color_classes = {
        "amber": "bg-amber-100 text-amber-700",
        "red": "bg-red-100 text-red-700",
        "blue": "bg-blue-100 text-blue-700",
        "green": "bg-green-100 text-green-700",
    }

    classes = color_classes.get(badge.color, "bg-gray-100 text-gray-700")

    html = f'''
    <span class="absolute -top-1 -right-1 inline-flex items-center justify-center
                px-2 py-0.5 text-xs font-bold rounded-full {classes}"
          data-testid="badge-{module_id}">
        {badge.count}
    </span>
    '''

    return HTMLResponse(html)


def _build_dashboard_stats(db):
    """Build dashboard stats using services.

    Uses:
    - party_service.count_parties() for party count
    - TicketService.get_dashboard_stats() for open ticket count
    - ReceivablesService.get_invoice_stats() for revenue and pending invoices
    - MarketingAnalyticsService.get_dashboard_stats() for campaigns
    - SubscriptionService.get_stats() for active subscriptions
    """
    # 1. Total Parties (via party service)
    party_count = party_service.count_parties(db)

    # 2. Open Tickets (via ticket service)
    ticket_service = TicketService(db)
    ticket_stats = ticket_service.get_dashboard_stats()
    open_tickets = ticket_stats.get("total_open", 0)

    # 3 & 4. Revenue MTD and Pending Invoices (via receivables service)
    settings_service = AccountingSettingsService(db)
    receivables_service = ReceivablesService(db, settings_service)
    invoice_stats = receivables_service.get_invoice_stats()

    # 5. Active Campaigns (via marketing analytics service)
    try:
        marketing_service = MarketingAnalyticsService(db)
        marketing_stats = marketing_service.get_dashboard_stats()
        active_campaigns = marketing_stats[0]["value"] if marketing_stats else 0
    except Exception:
        logger.exception("dashboard_marketing_stats_failed")
        active_campaigns = 0

    # 6. Active Subscriptions (via subscription service)
    try:
        sub_service = SubscriptionService(db)
        sub_stats = sub_service.get_stats()
        active_subs = sub_stats.active
    except Exception:
        logger.exception("dashboard_subscription_stats_failed")
        active_subs = 0

    # Get currency symbol for formatting
    currency_symbol = get_currency_symbol(settings.base_currency)

    stats = [
        {
            "key": "parties",
            "label": "Total Parties",
            "value": f"{party_count:,}",
            "subtext": "People & organizations",
            "icon": "users",
            "icon_bg": "bg-primary-50",
            "icon_color": "text-primary-600",
            "accent_gradient": "from-primary-400 to-primary-600",
            "href": "/parties",
        },
        {
            "key": "tickets",
            "label": "Open Tickets",
            "value": f"{open_tickets:,}",
            "subtext": "Awaiting response",
            "icon": "ticket",
            "icon_bg": "bg-amber-50",
            "icon_color": "text-amber-600",
            "accent_gradient": "from-amber-400 to-amber-600",
            "href": "/support/tickets?status=open",
        },
        {
            "key": "revenue",
            "label": "Revenue (MTD)",
            "value": f"{currency_symbol}{float(invoice_stats.total_revenue):,.0f}",
            "subtext": "This month",
            "icon": "currency",
            "icon_bg": "bg-emerald-50",
            "icon_color": "text-emerald-600",
            "accent_gradient": "from-emerald-400 to-emerald-600",
            "href": "/accounting/invoices?status=paid",
        },
        {
            "key": "invoices",
            "label": "Pending Invoices",
            "value": f"{invoice_stats.pending_count:,}",
            "subtext": "Awaiting payment",
            "icon": "invoice",
            "icon_bg": "bg-red-50",
            "icon_color": "text-red-600",
            "accent_gradient": "from-red-400 to-red-600",
            "href": "/accounting/invoices?status=pending",
        },
        {
            "key": "campaigns",
            "label": "Active Campaigns",
            "value": f"{active_campaigns:,}",
            "subtext": "Marketing campaigns",
            "icon": "megaphone",
            "icon_bg": "bg-purple-50",
            "icon_color": "text-purple-600",
            "accent_gradient": "from-purple-400 to-purple-600",
            "href": "/marketing/campaigns",
        },
        {
            "key": "subscriptions",
            "label": "Active Subscriptions",
            "value": f"{active_subs:,}",
            "subtext": "Service plans",
            "icon": "repeat",
            "icon_bg": "bg-blue-50",
            "icon_color": "text-blue-600",
            "accent_gradient": "from-blue-400 to-blue-600",
            "href": "/subscriptions?status=active",
        },
    ]

    return stats


def _build_attention_summary(db, user: SessionUser) -> dict:
    approvals_count = 0
    tasks_count = 0
    overdue_count = 0

    if user.has_scope("tasks:read"):
        tasks_service = WorkflowTaskService(db)
        tasks_count = tasks_service.count_my_tasks(user.id)

    if user.has_scope("accounting:read"):
        approvals_service = ApprovalsService(db, user)
        approvals_count = approvals_service.get_stats().get("pending", 0)

        from app.models.invoice import Invoice, InvoiceStatus

        overdue_count = db.query(func.count(Invoice.id)).filter(
            Invoice.status == InvoiceStatus.OVERDUE
        ).scalar() or 0

    total = approvals_count + tasks_count + overdue_count
    if total == 0:
        return {"total": 0}

    details = []
    if approvals_count:
        details.append(f"Approvals: {approvals_count}")
    if tasks_count:
        details.append(f"Tasks: {tasks_count}")
    if overdue_count:
        details.append(f"Overdue: {overdue_count}")

    if tasks_count:
        attention_href = "/tasks"
    elif approvals_count:
        attention_href = "/accounting/approvals"
    else:
        attention_href = "/accounting/invoices?status=overdue"

    return {
        "total": total,
        "details": ", ".join(details),
        "href": attention_href,
    }


@web_router.get("/ui/attention", response_class=HTMLResponse)
async def attention_badge(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
):
    """Render the global attention badge for the top bar."""
    summary = _build_attention_summary(db, user)
    template = templates.get_template("components/ui/attention_badge.html")
    return HTMLResponse(template.render({"attention": summary}))


@web_router.get("/dashboard/stats", response_class=HTMLResponse)
async def dashboard_stats(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
):
    """Dashboard stats partial for HTMX refresh."""
    stats = _build_dashboard_stats(db)

    # Build stats cards HTML
    html_parts = []
    for stat in stats:
        icon_html = _get_stat_icon_html(stat.get("icon", "chart"))
        change_html = ""
        if stat.get("change"):
            direction = "rotate-180" if stat["change"] < 0 else ""
            change_class = "text-emerald-600" if stat["change"] > 0 else "text-red-600"
            change_html = f'''
                <span class="inline-flex items-center gap-0.5 text-sm font-medium {change_class}">
                    <svg class="w-4 h-4 {direction}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7"/>
                    </svg>
                    {abs(stat["change"])}%
                </span>
            '''
        subtext_html = f'<p class="mt-1 text-xs text-gray-400 font-body">{stat.get("subtext", "")}</p>' if stat.get("subtext") else ""

        href = stat.get("href", "#")
        html_parts.append(f'''
        <a href="{href}" class="group relative bg-white rounded-2xl shadow-warm-sm ring-1 ring-gray-100 p-6 hover:shadow-warm-md hover:ring-gray-200 transition-all duration-300 block cursor-pointer" data-testid="stat-card-{stat.get('key', '')}">
            <div class="flex items-start justify-between">
                <div class="flex-1">
                    <dt class="text-sm font-medium text-gray-500 font-body">{stat.get("label", "")}</dt>
                    <dd class="mt-2 flex items-baseline gap-2">
                        <span class="text-3xl font-display font-bold text-gray-900 tracking-tight">{stat.get("value", "0")}</span>
                        {change_html}
                    </dd>
                    {subtext_html}
                </div>
                <div class="flex-shrink-0 p-3 rounded-xl {stat.get("icon_bg", "bg-primary-50")} {stat.get("icon_color", "text-primary-600")} group-hover:scale-110 transition-transform duration-300">
                    {icon_html}
                </div>
            </div>
            <div class="absolute bottom-0 left-6 right-6 h-0.5 bg-gradient-to-r {stat.get("accent_gradient", "from-primary-400 to-primary-600")} rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
        </a>
        ''')

    return HTMLResponse("".join(html_parts))


def _get_stat_icon_html(icon_name: str) -> str:
    """Generate SVG icon HTML for stat cards."""
    icons = {
        "users": '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"/></svg>',
        "ticket": '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M18.364 5.636l-3.536 3.536m0 5.656l3.536 3.536M9.172 9.172L5.636 5.636m3.536 9.192l-3.536 3.536M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-5 0a4 4 0 11-8 0 4 4 0 018 0z"/></svg>',
        "currency": '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
        "invoice": '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2z"/></svg>',
        "megaphone": '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M11 5.882V19.24a1.76 1.76 0 01-3.417.592l-2.147-6.15M18 13a3 3 0 100-6M5.436 13.683A4.001 4.001 0 017 6h1.832c4.1 0 7.625-1.234 9.168-3v14c-1.543-1.766-5.067-3-9.168-3H7a3.988 3.988 0 01-1.564-.317z"/></svg>',
        "repeat": '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>',
    }
    return icons.get(icon_name, '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>')


@web_router.get("/parties/{party_id}", response_class=HTMLResponse)
async def party_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    party_id: int,
):
    """Party detail page."""
    from sqlalchemy.orm import joinedload, load_only
    from app.models.party import Party

    party = (
        db.query(Party)
        .options(
            load_only(
                Party.id,
                Party.type,
                Party.status,
                Party.name,
                Party.first_name,
                Party.last_name,
                Party.legal_name,
                Party.trading_name,
                Party.primary_email,
                Party.primary_phone,
                Party.timezone,
                Party.locale,
                Party.tax_id,
                Party.tags,
                Party.created_at,
            ),
            joinedload(Party.roles),
        )
        .filter(Party.id == party_id)
        .first()
    )
    if not party:
        return HTMLResponse("Party not found", status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = party.name or f"Party #{party.id}"
    context["party"] = party

    template = templates.get_template("pages/party_detail.html")
    return HTMLResponse(template.render(context))


@web_router.get("/parties", response_class=HTMLResponse)
async def parties_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = None,
    type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    per_page: int = 25,
):
    """Party list page."""
    from app.models.party import Party
    from sqlalchemy import func
    from sqlalchemy.orm import load_only

    query = db.query(Party).options(
        load_only(
            Party.id,
            Party.type,
            Party.status,
            Party.name,
            Party.first_name,
            Party.last_name,
            Party.legal_name,
            Party.trading_name,
            Party.primary_email,
            Party.primary_phone,
            Party.timezone,
            Party.locale,
            Party.tax_id,
            Party.tags,
            Party.created_at,
        )
    )
    if type in {"person", "organization"}:
        query = query.filter(Party.type == type)
    if status in {"active", "inactive", "blocked"}:
        query = query.filter(Party.status == status)
    if q:
        search = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Party.name.ilike(search),
                Party.primary_email.ilike(search),
                Party.primary_phone.ilike(search),
            )
        )

    total = query.with_entities(func.count(Party.id)).scalar() or 0
    offset = max(page - 1, 0) * per_page
    parties = query.order_by(Party.name.asc()).offset(offset).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Parties"
    context["parties"] = parties
    context["pagination"] = build_pagination_context(page, per_page, total)
    context["filters"] = {"q": q or "", "type": type or "", "status": status or ""}

    template = templates.get_template("pages/parties_list.html")
    return HTMLResponse(template.render(context))


@web_router.get("/crm/contacts-legacy", response_class=HTMLResponse)
async def crm_contacts_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    per_page: int = 25,
):
    """Legacy contact list page (deprecated)."""
    from app.models.party import Party
    from sqlalchemy.orm import load_only

    query = db.query(Party).options(
        load_only(
            Party.id,
            Party.type,
            Party.status,
            Party.name,
            Party.first_name,
            Party.last_name,
            Party.legal_name,
            Party.trading_name,
            Party.primary_email,
            Party.primary_phone,
            Party.timezone,
            Party.locale,
            Party.tax_id,
            Party.tags,
            Party.created_at,
        )
    ).filter(Party.type == "person")
    if status in {"active", "inactive", "blocked"}:
        query = query.filter(Party.status == status)
    if q:
        search = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Party.name.ilike(search),
                Party.primary_email.ilike(search),
                Party.primary_phone.ilike(search),
            )
        )

    total = query.with_entities(func.count(Party.id)).scalar() or 0
    offset = max(page - 1, 0) * per_page
    parties = query.order_by(Party.name.asc()).offset(offset).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Contacts (Legacy)"
    context["parties"] = parties
    context["pagination"] = build_pagination_context(page, per_page, total)
    context["filters"] = {"q": q or "", "type": "person", "status": status or ""}
    context["base_url"] = "/crm/contacts-legacy"
    context["detail_base_url"] = "/crm/contacts-legacy"
    context["contacts_view"] = True

    template = templates.get_template("pages/parties_list.html")
    return HTMLResponse(template.render(context))


@web_router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    response: Response,
    user: OptionalUser,
    csrf_token: CSRFToken,
):
    """Login page - redirects to dashboard if already logged in."""
    if user:
        return RedirectResponse(url="/", status_code=303)

    context = get_base_context(request, response, user, csrf_token)
    context["page_title"] = "Login"
    context["next_url"] = request.query_params.get("next", "/")

    template = templates.get_template("pages/login.html")
    return HTMLResponse(template.render(context))


@web_router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    response: Response,
    csrf_token: CSRFToken,
    db: DB,
):
    """Handle login form submission.

    Note: This endpoint is for direct login if supported.
    Most deployments use SSO via /auth/sso instead.
    """
    from app.core.security import set_flash, validate_csrf
    from app.config import settings
    from app.auth import AUTH_COOKIE_NAME
    from jose import jwt
    import time

    # Validate CSRF
    await validate_csrf(request)

    form = await request.form()
    raw_email = form.get("email", "")
    email = raw_email.strip() if isinstance(raw_email, str) else ""
    password = form.get("password", "")
    next_url = form.get("next", "/")

    if settings.e2e_auth_enabled and settings.e2e_jwt_secret:
        if not email:
            set_flash(response, "Email is required.", "error")
        else:
            now = int(time.time())
            payload = {
                "sub": f"e2e-{email.replace('@', '-at-')}",
                "email": email,
                "name": email.split("@")[0] if "@" in email else email,
                "scopes": ["*"],
                "iat": now,
                "exp": now + 86400,
            }
            token = jwt.encode(payload, settings.e2e_jwt_secret, algorithm="HS256")
            redirect = RedirectResponse(url=next_url, status_code=303)
            redirect.set_cookie(
                key=AUTH_COOKIE_NAME,
                value=token,
                httponly=True,
                secure=request.url.scheme == "https",
                samesite="lax",
                path="/",
                max_age=86400,
            )
            return redirect

    # For now, direct login is not supported - redirect to SSO
    # In production, this would be handled by the external auth provider
    set_flash(response, "Please use SSO to sign in.", "info")

    context = get_base_context(request, response, None, csrf_token)
    context["page_title"] = "Login"
    context["next_url"] = next_url
    context["email"] = email

    template = templates.get_template("pages/login.html")
    return HTMLResponse(template.render(context))


@web_router.get("/auth/sso")
async def sso_redirect(request: Request):
    """Redirect to SSO provider for authentication.

    In production, this redirects to the configured OIDC provider.
    For development, this may redirect to a local auth server.
    """
    from app.config import settings

    # Get the 'next' URL to redirect back to after auth
    next_url = request.query_params.get("next", "/")

    # In a real implementation, this would:
    # 1. Generate a state token for CSRF protection
    # 2. Store the state and next_url in session/cookie
    # 3. Redirect to the OIDC authorization endpoint

    # For now, redirect to the auth provider's login page
    # The auth provider should be configured to redirect back with a JWT token
    auth_base = settings.jwt_issuer or "http://localhost:3000"
    auth_url = f"{auth_base}/login?redirect={request.url_for('auth_callback')}&next={next_url}"

    return RedirectResponse(url=auth_url, status_code=302)


@web_router.get("/auth/callback")
async def auth_callback(
    request: Request,
    response: Response,
):
    """Handle callback from SSO provider.

    The auth provider redirects here with a token after successful authentication.
    """
    from app.auth import AUTH_COOKIE_NAME
    from app.core.security import set_flash

    # Get token from query params or headers
    token = request.query_params.get("token")
    next_url = request.query_params.get("next", "/")

    if not token:
        set_flash(response, "Authentication failed. Please try again.", "error")
        return RedirectResponse(url="/login", status_code=303)

    # Set the auth cookie
    redirect = RedirectResponse(url=next_url, status_code=303)
    redirect.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=86400 * 7,  # 7 days
    )

    return redirect


@web_router.get("/logout")
async def logout(request: Request, response: Response):
    """Logout - clears session cookie and redirects to login."""
    from app.auth import AUTH_COOKIE_NAME
    from app.core.security import set_flash

    redirect = RedirectResponse(url="/login", status_code=303)
    redirect.delete_cookie(AUTH_COOKIE_NAME, path="/")
    set_flash(redirect, "You have been logged out.", "info")
    return redirect


@web_router.get("/health")
async def health_check():
    """Health check endpoint for load balancers."""
    return {"status": "ok"}


@web_router.get("/crm-legacy", response_class=HTMLResponse)
@web_router.get("/crm-legacy/{path:path}", response_class=HTMLResponse)
async def crm_deprecated(request: Request):
    """CRM legacy placeholder; direct users to the current CRM UI."""
    return HTMLResponse(
        "<html><body><h1>CRM UI Deprecated</h1>"
        "<p>The legacy CRM web UI has been removed.</p>"
        "<p>Use the current CRM UI at <code>/crm</code>.</p>"
        "</body></html>",
        status_code=410,
    )


# =============================================================================
# MODULE ROUTERS - Consolidated Structure
# =============================================================================

# Sales module (includes quotations, orders, invoices/subscriptions redirects)
from app.modules.sales import router as sales_router

# Accounting module (includes all accounting sub-routes)
from app.modules.accounting.routes import router as accounting_router

# HR module (includes employees, leave, payroll, expenses/performance redirects)
from app.modules.hr.routes import router as hr_router

# Support module (includes tickets, agents, SLA, KB, etc.)
from app.modules.support.routes import (
    router as support_router,
    dashboard_router as support_dashboard_router,
    agents_router as support_agents_router,
    sla_router as support_sla_router,
    conversations_router as support_conversations_router,
    teams_router as support_teams_router,
    canned_router as support_canned_router,
    kb_router as support_kb_router,
    automation_router as support_automation_router,
    csat_router as support_csat_router,
    routing_router as support_routing_router,
    tags_router as support_tags_router,
    queues_router as support_queues_router,
    escalations_router as support_escalations_router,
    channels_router as support_channels_router,
    webhooks_router as support_webhooks_router,
)

# Operations module (NEW - aggregates projects, field_service, inventory, assets, vehicles)
from app.modules.operations.routes import router as operations_router

# Purchasing module (includes suppliers)
from app.modules.purchasing.routes import router as purchasing_router

# Network module
from app.modules.network.routes import router as network_router

# Analytics module
from app.modules.analytics.routes import router as analytics_router

# CRM module (contacts and CRM workflows)
from app.modules.crm import router as crm_router

# Finance module (analytics and reporting)
from app.modules.finance import router as finance_router

# Settings module (includes workflow tasks redirect)
from app.modules.settings.routes import router as settings_router

# Standalone modules that are kept for direct access (linked via redirects from parent modules)
from app.modules.invoices.routes import router as invoices_router
from app.modules.subscriptions.routes import router as subscriptions_router
from app.modules.subscriptions.service_routes import router as subscriptions_services_router
from app.modules.subscribers.routes import router as subscribers_router
from app.modules.subscriptions.tariff_routes import router as tariffs_router
from app.modules.subscriptions.payment_routes import router as payment_subscriptions_router
from app.modules.expenses.routes import router as expenses_router
from app.modules.performance.routes import router as performance_router
from app.modules.suppliers.routes import router as suppliers_router
from app.modules.reports.routes import router as reports_router
from app.modules.omnichannel.routes import router as omnichannel_router
from app.modules.workflow_tasks.routes import router as workflow_tasks_router
from app.modules.payments.routes import router as payments_router

# Legacy standalone modules (kept for backwards compatibility, accessed via parent modules)
from app.modules.inventory.routes import router as inventory_router
from app.modules.projects.routes import (
    router as projects_router,
    dashboard_router as projects_dashboard_router,
    tasks_router as projects_tasks_router,
    milestones_router as projects_milestones_router,
)
from app.modules.projects.gantt_routes import router as projects_gantt_router
from app.modules.field_service.routes import router as field_service_router
from app.modules.field_service.calendar_routes import router as field_service_calendar_router
from app.modules.assets.routes import router as assets_router
from app.modules.vehicles.routes import router as vehicles_router

# =============================================================================
# ROUTE REGISTRATION
# =============================================================================

# Core consolidated modules with landing pages
web_router.include_router(sales_router)
web_router.include_router(accounting_router)
web_router.include_router(hr_router)
web_router.include_router(purchasing_router)
web_router.include_router(operations_router)
web_router.include_router(network_router)
web_router.include_router(analytics_router)
web_router.include_router(crm_router)
web_router.include_router(finance_router)
web_router.include_router(settings_router)

# Support module with all sub-routers
web_router.include_router(support_router)
web_router.include_router(support_dashboard_router)
web_router.include_router(support_agents_router)
web_router.include_router(support_sla_router)
web_router.include_router(support_conversations_router)
web_router.include_router(support_teams_router)
web_router.include_router(support_canned_router)
web_router.include_router(support_kb_router)
web_router.include_router(support_automation_router)
web_router.include_router(support_csat_router)
web_router.include_router(support_routing_router)
web_router.include_router(support_tags_router)
web_router.include_router(support_queues_router)
web_router.include_router(support_escalations_router)
web_router.include_router(support_channels_router)
web_router.include_router(support_webhooks_router)

# Standalone modules (linked from parent modules)
web_router.include_router(invoices_router)
web_router.include_router(subscriptions_router)
web_router.include_router(subscriptions_services_router)
web_router.include_router(subscribers_router)
web_router.include_router(tariffs_router)
web_router.include_router(payment_subscriptions_router)
web_router.include_router(expenses_router)
web_router.include_router(performance_router)
web_router.include_router(suppliers_router)
web_router.include_router(reports_router)
web_router.include_router(omnichannel_router)
web_router.include_router(workflow_tasks_router)
web_router.include_router(payments_router)

# Legacy operations sub-modules (for backwards compatibility)
web_router.include_router(inventory_router)
web_router.include_router(projects_router)
web_router.include_router(projects_dashboard_router)
web_router.include_router(projects_tasks_router)
web_router.include_router(projects_milestones_router)
web_router.include_router(projects_gantt_router)
web_router.include_router(field_service_router)
web_router.include_router(field_service_calendar_router)
web_router.include_router(assets_router)
web_router.include_router(vehicles_router)

# =============================================================================
# AUTO-DISCOVERED MODULE ROUTERS
# =============================================================================
# Include routers from modules that have MODULE_CONFIG (new modular system)
# Trigger discovery now that all imports are done (avoid circular import issues)
# These are in addition to the manual imports above - FastAPI handles duplicates
_discovered_count = ModuleRegistry.discover_modules()
logger.info(f"Auto-discovered {_discovered_count} modules")
for _router in ModuleRegistry.get_all_routers():
    web_router.include_router(_router)
