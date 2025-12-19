from fastapi import FastAPI, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog

from app.api import api_router, public_api_router
from app.config import settings
from app.auth import get_current_principal
from app.middleware.metrics import get_metrics_response
from app.observability.otel import setup_otel, shutdown_otel
from app.middleware.license import enforce_license

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
    logger.info(
        "starting_application",
        app="dotmac-insights",
        environment=settings.environment,
        jwt_configured=bool(settings.jwks_url),
        otel_enabled=settings.otel_enabled,
    )

    # Initialize OTEL instrumentation (if enabled)
    # Pass app for FastAPI instrumentation
    otel_initialized = setup_otel(app)
    if otel_initialized:
        logger.info("otel_setup_complete")

    yield

    # Shutdown
    shutdown_otel()
    logger.info("shutting_down_application")


app = FastAPI(
    title="Dotmac Insights",
    description="Unified data platform for Dotmac Technologies - syncing Splynx, ERPNext, and Chatwoot",
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
    allow_methods=["*"],
    allow_headers=["*"],
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



@app.get("/")
async def root():
    """Root endpoint (public)."""
    return {
        "name": "Dotmac Insights",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "environment": settings.environment,
    }


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
