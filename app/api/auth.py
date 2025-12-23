"""Authentication session endpoints for browser clients."""
from __future__ import annotations

import time
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import (
    AUTH_COOKIE_NAME,
    get_or_create_user,
    get_origin_from_request,
    is_token_denylisted,
    validate_origin,
    verify_jwt,
)
from app.config import settings
from app.database import get_db
from app.middleware.rate_limit import (
    check_auth_rate_limit,
    clear_auth_rate_limit,
    record_auth_failure,
)

logger = structlog.get_logger("auth.session")
router = APIRouter(prefix="/auth", tags=["auth"])


class SessionCreateRequest(BaseModel):
    token: str = Field(..., min_length=1)


class SessionResponse(BaseModel):
    authenticated: bool


@router.post(
    "/session",
    response_model=SessionResponse,
    dependencies=[Depends(check_auth_rate_limit)],
)
async def create_session(
    payload: SessionCreateRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionResponse:
    """Validate a JWT and set it as an httpOnly cookie.

    Security:
    - Rate limited: 10 requests/minute, 5-minute block on excess
    - Requires valid Origin header matching CORS allowed origins (Login CSRF protection)
    - Validates JWT signature and expiration
    - Checks token denylist for revoked tokens
    """
    # Login CSRF Protection: Validate Origin header
    origin = get_origin_from_request(request)
    if not validate_origin(origin, settings.cors_origins_list):
        logger.warning(
            "login_csrf_rejected",
            origin=origin,
            allowed_origins=settings.cors_origins_list,
        )
        await record_auth_failure(request)
        raise HTTPException(
            status_code=403,
            detail="Invalid origin. Cross-origin login requests are not allowed.",
        )

    token = payload.token.strip()
    if "." not in token:
        logger.warning("invalid_token_format", has_dots=False)
        await record_auth_failure(request)
        raise HTTPException(status_code=400, detail="Invalid JWT token")

    try:
        claims = await verify_jwt(token)
    except HTTPException:
        await record_auth_failure(request)
        raise

    if claims.jti and await is_token_denylisted(claims.jti, db):
        logger.warning("token_denylisted", jti=claims.jti)
        await record_auth_failure(request)
        raise HTTPException(status_code=401, detail="Token has been revoked")

    # Security: Require exp claim - tokens without expiration are rejected
    if claims.exp is None:
        logger.warning("token_missing_exp", sub=claims.sub)
        await record_auth_failure(request)
        raise HTTPException(
            status_code=400,
            detail="Token must have an expiration claim (exp)",
        )

    now = int(time.time())
    max_age = claims.exp - now
    if max_age <= 0:
        logger.warning("token_expired", sub=claims.sub, exp=claims.exp)
        await record_auth_failure(request)
        raise HTTPException(status_code=401, detail="Token expired")
    expires_at = datetime.fromtimestamp(claims.exp, tz=timezone.utc)

    user = await get_or_create_user(claims, db)
    if not user.is_active:
        logger.warning("user_disabled", user_id=user.id, email=user.email)
        await record_auth_failure(request)
        raise HTTPException(status_code=403, detail="User account is disabled")

    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=max_age,
        expires=expires_at,
        path="/",
    )

    # Clear rate limit on successful auth
    await clear_auth_rate_limit(request)

    logger.info(
        "session_created",
        user_id=user.id,
        origin=origin,
        expires_at=expires_at.isoformat() if expires_at else None,
    )

    return SessionResponse(authenticated=True)


@router.delete("/session")
async def clear_session(request: Request, response: Response) -> dict:
    """Clear the authentication cookie (logout)."""
    from app.middleware.rate_limit import get_client_ip

    client_ip = get_client_ip(request)
    logger.info("session_cleared", client_ip=client_ip)

    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return {"status": "logged_out"}
