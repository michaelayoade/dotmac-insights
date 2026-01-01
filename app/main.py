from pathlib import Path

from fastapi import FastAPI, Depends, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.exceptions import HTTPException
from contextlib import asynccontextmanager
import structlog

from app.templates.environment import get_template_env

from app.api import api_router, public_api_router
from app.web.routes import web_router
from app.config import settings
from app.auth import get_current_principal
from app.middleware.metrics import get_metrics_response
from app.observability.otel import setup_otel, shutdown_otel
from app.middleware.license import enforce_license
from app.services.rbac_sync import ensure_admin_has_all_permissions
from app.services.platform_client import init_platform_client, close_platform_client
from app.events import register_subscription_events

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    if settings.environment == "production" and (settings.e2e_jwt_secret or settings.e2e_auth_enabled):
        logger.error(
            "e2e_auth_disallowed_in_production",
            e2e_auth_enabled=settings.e2e_auth_enabled,
            e2e_jwt_secret_configured=bool(settings.e2e_jwt_secret),
        )
        raise RuntimeError("E2E auth must be disabled in production")

    logger.info(
        "starting_application",
        app="dotmac-bos",
        environment=settings.environment,
        jwt_configured=bool(settings.jwks_url),
        otel_enabled=settings.otel_enabled,
    )

    # Initialize OTEL instrumentation (if enabled)
    # Pass app for FastAPI instrumentation
    otel_initialized = setup_otel(app)
    if otel_initialized:
        logger.info("otel_setup_complete")

    # Initialize async platform client for license validation & feature flags
    await init_platform_client()
    logger.info("platform_client_initialized")

    ensure_admin_has_all_permissions()

    # Register SQLAlchemy event handlers for provisioning
    register_subscription_events()
    logger.info("subscription_events_registered")

    yield

    # Shutdown
    await close_platform_client()
    shutdown_otel()
    logger.info("shutting_down_application")


app = FastAPI(
    title="DotMac BOS",
    description="Business Operating System - Comprehensive ERP platform for business operations",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
if not settings.cors_origins_list:
    logger.error("cors_not_configured", message="CORS origins must be configured")
    raise RuntimeError("CORS_ORIGINS must be set; refusing to start with wildcard CORS")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    # Restrict to specific methods instead of wildcard
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    # Restrict to specific headers instead of wildcard
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-CSRF-Token",
        "HX-Request",
        "HX-Current-URL",
        "HX-Target",
        "HX-Trigger",
        "HX-Boosted",
    ],
)
logger.info("cors_configured", origins=settings.cors_origins_list)


# Include API routes with JWT/RBAC authentication
# Each route handles its own scope requirements via Require() dependency
app.include_router(
    api_router,
    prefix="/api",
    dependencies=[Depends(get_current_principal), Depends(enforce_license)],
)
logger.info("api_jwt_auth_enabled")

# Public endpoints that must remain unauthenticated (e.g., third-party webhooks)
app.include_router(
    public_api_router,
    prefix="/api",
)

# Mount static files for SSR frontend
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    logger.info("static_files_mounted", path=str(STATIC_DIR))

# Include SSR web routes (no /api prefix)
# This provides HTML pages rendered server-side with HTMX
app.include_router(web_router)
logger.info("web_router_mounted")


# Custom exception handlers for SSR error pages
templates = get_template_env()


@app.exception_handler(403)
async def forbidden_handler(request: Request, exc: HTTPException):
    """Render 403 error page for web requests, JSON for API requests."""
    if request.url.path.startswith("/api/"):
        return Response(
            content='{"detail": "' + str(exc.detail or "Forbidden") + '"}',
            status_code=403,
            media_type="application/json",
        )

    template = templates.get_template("errors/403.html")
    context = {
        "csrf_token": "",
        "product_name": "DotMac BOS",
        "detail": exc.detail,
    }
    return HTMLResponse(template.render(context), status_code=403)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    """Render 404 error page for web requests, JSON for API requests."""
    if request.url.path.startswith("/api/"):
        return Response(
            content='{"detail": "' + str(exc.detail or "Not Found") + '"}',
            status_code=404,
            media_type="application/json",
        )

    template = templates.get_template("errors/404.html")
    context = {
        "csrf_token": "",
        "product_name": "DotMac BOS",
        "detail": exc.detail,
    }
    return HTMLResponse(template.render(context), status_code=404)


@app.get("/health")
async def health_check():
    """Health check endpoint (public)."""
    return {"status": "healthy"}


# Convenience health endpoint under /api for environments that prefix requests
@app.get("/api/health")
async def api_health_check():
    """Health check for clients that expect /api/health."""
    return {"status": "healthy"}


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.

    Exposes application metrics for monitoring:
    - webhook_auth_failures_total: Webhook authentication failures by provider
    - contacts_auth_failures_total: Contacts API auth failures
    - contacts_dual_write_success_total: Successful contact dual-write operations
    - contacts_dual_write_failures_total: Failed contact dual-write operations
    - tickets_dual_write_success_total: Successful ticket dual-write operations
    - tickets_dual_write_failures_total: Failed ticket dual-write operations
    - outbound_sync_total: Outbound sync attempts by entity/target/status
    - contacts_drift_pct: Contact field drift percentage by system
    - tickets_drift_pct: Ticket field drift percentage by system
    - contacts_query_latency_seconds: Contacts API query latency
    - api_request_latency_seconds: General API request latency
    - api_requests_total: Total API requests by method/endpoint/status
    """
    metrics_bytes, content_type = get_metrics_response()
    return Response(content=metrics_bytes, media_type=content_type)
