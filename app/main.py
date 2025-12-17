from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog

from app.api import api_router
from app.config import settings
from app.auth import get_current_principal

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
    )

    yield

    # Shutdown
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
    dependencies=[Depends(get_current_principal)],
)
logger.info("api_jwt_auth_enabled")



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
