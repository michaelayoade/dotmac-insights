"""Authentication session endpoints for browser clients."""
from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import AUTH_COOKIE_NAME, get_or_create_user, is_token_denylisted, verify_jwt
from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class SessionCreateRequest(BaseModel):
    token: str = Field(..., min_length=1)


class SessionResponse(BaseModel):
    authenticated: bool


@router.post("/session", response_model=SessionResponse)
async def create_session(
    payload: SessionCreateRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionResponse:
    """Validate a JWT and set it as an httpOnly cookie."""
    token = payload.token.strip()
    if "." not in token:
        raise HTTPException(status_code=400, detail="Invalid JWT token")

    claims = await verify_jwt(token)

    if claims.jti and await is_token_denylisted(claims.jti, db):
        raise HTTPException(status_code=401, detail="Token has been revoked")

    if claims.exp is not None:
        now = int(time.time())
        max_age = claims.exp - now
        if max_age <= 0:
            raise HTTPException(status_code=401, detail="Token expired")
        expires_at = datetime.fromtimestamp(claims.exp, tz=timezone.utc)
    else:
        max_age = None
        expires_at = None

    user = await get_or_create_user(claims, db)
    if not user.is_active:
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

    return SessionResponse(authenticated=True)


@router.delete("/session")
async def clear_session(response: Response) -> dict:
    """Clear the authentication cookie."""
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return {"status": "logged_out"}
