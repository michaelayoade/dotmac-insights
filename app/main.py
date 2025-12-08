from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog

from app.database import engine, Base
from app.api import api_router
from app.config import settings
from app.auth import verify_api_key

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
        auth_enabled=bool(settings.api_key),
    )

    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("database_tables_created")

    yield

    # Shutdown
    logger.info("shutting_down_application")


app = FastAPI(
    title="Dotmac Insights",
    description="Unified data platform for Dotmac Technologies - syncing Splynx, ERPNext, and Chatwoot",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS - only allow specified origins in production
if settings.cors_origins_list:
    # Production: Only allow specified origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["X-API-Key", "Content-Type", "Authorization"],
    )
    logger.info("cors_configured", origins=settings.cors_origins_list)
elif not settings.is_production:
    # Development only: Allow all origins (with warning)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.warning("cors_permissive_mode", message="CORS allowing all origins - development only")
else:
    # Production without CORS configured: No CORS middleware (same-origin only)
    logger.info("cors_disabled", message="No CORS origins configured - same-origin requests only")


# Determine if auth is required
if settings.api_key:
    # Auth enabled: Protect all API routes
    app.include_router(
        api_router,
        prefix="/api",
        dependencies=[Depends(verify_api_key)],
    )
    logger.info("api_auth_enabled")
else:
    # No auth (development mode)
    app.include_router(api_router, prefix="/api")
    if settings.is_production:
        logger.error("api_auth_disabled_in_production", message="API_KEY not set - API is unprotected!")
    else:
        logger.warning("api_auth_disabled", message="No API_KEY set - API is unprotected")


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
