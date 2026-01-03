from pathlib import Path
import json
import uuid
from datetime import datetime

from fastapi import FastAPI, Depends, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.exceptions import HTTPException
from contextlib import asynccontextmanager
from sqlalchemy import text
from sqlalchemy.orm import Session
import structlog

from app.templates.environment import get_template_env

from app.api import api_router, public_api_router
from app.web.routes import web_router
from app.config import settings
from app.auth import get_current_principal
from app.middleware.metrics import get_metrics_response
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.observability.otel import setup_otel, shutdown_otel
from app.middleware.license import enforce_license
from app.services.rbac_sync import ensure_admin_has_all_permissions
from app.services.platform_client import init_platform_client, close_platform_client
from app.events import register_subscription_events
from app.database import get_db

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

    if settings.is_production and settings.auth_disabled:
        logger.error("auth_disabled_in_production")
        raise RuntimeError("AUTH_DISABLED must be false in production")

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

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggingMiddleware)
logger.info("security_middleware_enabled")


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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global handler for unhandled exceptions."""
    error_id = str(uuid.uuid4())[:8]

    logger.exception(
        "unhandled_exception",
        error_id=error_id,
        path=request.url.path,
        method=request.method,
        client_ip=request.client.host if request.client else "unknown",
        exc_type=type(exc).__name__,
    )

    if request.url.path.startswith("/api/"):
        return Response(
            content=json.dumps({"detail": "Internal server error", "error_id": error_id}),
            status_code=500,
            media_type="application/json",
        )

    template = templates.get_template("errors/500.html")
    context = {
        "csrf_token": "",
        "product_name": "DotMac BOS",
        "error_id": error_id,
    }
    return HTMLResponse(template.render(context), status_code=500)


@app.get("/health", tags=["System"])
async def health_check():
    """Liveness probe - always returns healthy if process is running."""
    return {"status": "healthy"}


@app.get("/health/ready", tags=["System"])
async def readiness_check(db: Session = Depends(get_db)):
    """Readiness probe - checks all dependencies."""
    from app.cache import get_redis_client

    checks = {"database": "unknown", "redis": "unknown"}
    all_healthy = True

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)[:50]}"
        all_healthy = False
        logger.error("health_check_db_failed", error=str(e))

    try:
        redis_client = await get_redis_client()
        if redis_client:
            await redis_client.ping()
            checks["redis"] = "healthy"
        else:
            checks["redis"] = "not_configured"
    except Exception as e:
        checks["redis"] = f"unhealthy: {str(e)[:50]}"
        if settings.redis_url:
            all_healthy = False
            logger.error("health_check_redis_failed", error=str(e))

    status_code = 200 if all_healthy else 503
    return Response(
        content=json.dumps({
            "status": "ready" if all_healthy else "not_ready",
            "checks": checks,
            "timestamp": datetime.utcnow().isoformat(),
        }),
        status_code=status_code,
        media_type="application/json",
    )


@app.get("/api/health", tags=["System"])
async def api_health_check():
    """Health check for clients that expect /api/health."""
    return {"status": "healthy"}


@app.get("/api/health/ready", tags=["System"])
async def api_readiness_check(db: Session = Depends(get_db)):
    """Readiness check for clients that expect /api/health/ready."""
    return await readiness_check(db)


@app.get("/metrics", tags=["System"])
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
