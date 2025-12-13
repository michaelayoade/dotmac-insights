"""Canned Responses (Macros) API endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models.support_canned import CannedResponse, CannedResponseScope
from app.models.agent import Agent, Team
from app.models.ticket import Ticket
from app.auth import Require

router = APIRouter()


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class CannedResponseCreateRequest(BaseModel):
    name: str
    shortcode: Optional[str] = None
    content: str
    scope: str = CannedResponseScope.PERSONAL.value
    team_id: Optional[int] = None
    agent_id: Optional[int] = None
    category: Optional[str] = None
    is_active: bool = True


class CannedResponseUpdateRequest(BaseModel):
    name: Optional[str] = None
    shortcode: Optional[str] = None
    content: Optional[str] = None
    scope: Optional[str] = None
    team_id: Optional[int] = None
    agent_id: Optional[int] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None


class RenderRequest(BaseModel):
    ticket_id: Optional[int] = None
    context: Optional[Dict[str, Any]] = None


# =============================================================================
# CANNED RESPONSES
# =============================================================================

@router.get("/canned-responses", dependencies=[Depends(Require("support:read"))])
def list_canned_responses(
    scope: Optional[str] = None,
    category: Optional[str] = None,
    team_id: Optional[int] = None,
    search: Optional[str] = None,
    include_inactive: bool = False,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List canned responses with filtering."""
    query = db.query(CannedResponse)

    if not include_inactive:
        query = query.filter(CannedResponse.is_active == True)

    if scope:
        query = query.filter(CannedResponse.scope == scope)
    if category:
        query = query.filter(CannedResponse.category == category)
    if team_id:
        query = query.filter(or_(
            CannedResponse.team_id == team_id,
            CannedResponse.scope == CannedResponseScope.GLOBAL.value,
        ))

    if search:
        search_term = f"%{search}%"
        query = query.filter(or_(
            CannedResponse.name.ilike(search_term),
            CannedResponse.shortcode.ilike(search_term),
            CannedResponse.content.ilike(search_term),
        ))

    total = query.count()
    responses = query.order_by(
        CannedResponse.usage_count.desc(),
        CannedResponse.name
    ).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": r.id,
                "name": r.name,
                "shortcode": r.shortcode,
                "content": r.content[:200] + "..." if len(r.content) > 200 else r.content,
                "scope": r.scope,
                "team_id": r.team_id,
                "team_name": r.team.name if r.team else None,
                "agent_id": r.agent_id,
                "category": r.category,
                "usage_count": r.usage_count,
                "is_active": r.is_active,
            }
            for r in responses
        ],
    }


@router.post("/canned-responses", dependencies=[Depends(Require("support:write"))], status_code=201)
def create_canned_response(
    payload: CannedResponseCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a canned response."""
    # Validate scope
    try:
        CannedResponseScope(payload.scope)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid scope: {payload.scope}")

    # Validate shortcode uniqueness if provided
    if payload.shortcode:
        existing = db.query(CannedResponse).filter(
            CannedResponse.shortcode == payload.shortcode
        ).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Shortcode '{payload.shortcode}' already exists"
            )

    # Validate team_id if scope is TEAM
    if payload.scope == CannedResponseScope.TEAM.value:
        if not payload.team_id:
            raise HTTPException(
                status_code=400,
                detail="team_id is required for team-scoped responses"
            )
        team = db.query(Team).filter(Team.id == payload.team_id).first()
        if not team:
            raise HTTPException(status_code=400, detail="Invalid team_id")

    response = CannedResponse(
        name=payload.name,
        shortcode=payload.shortcode,
        content=payload.content,
        scope=payload.scope,
        team_id=payload.team_id,
        agent_id=payload.agent_id,
        category=payload.category,
        is_active=payload.is_active,
    )
    db.add(response)
    db.commit()
    db.refresh(response)
    return {"id": response.id, "name": response.name}


@router.get("/canned-responses/{response_id}", dependencies=[Depends(Require("support:read"))])
def get_canned_response(
    response_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get canned response details."""
    response = db.query(CannedResponse).filter(CannedResponse.id == response_id).first()
    if not response:
        raise HTTPException(status_code=404, detail="Canned response not found")

    return {
        "id": response.id,
        "name": response.name,
        "shortcode": response.shortcode,
        "content": response.content,
        "scope": response.scope,
        "team_id": response.team_id,
        "team_name": response.team.name if response.team else None,
        "agent_id": response.agent_id,
        "agent_name": response.agent.display_name if response.agent else None,
        "category": response.category,
        "usage_count": response.usage_count,
        "last_used_at": response.last_used_at.isoformat() if response.last_used_at else None,
        "is_active": response.is_active,
        "created_at": response.created_at.isoformat() if response.created_at else None,
        "updated_at": response.updated_at.isoformat() if response.updated_at else None,
    }


@router.patch("/canned-responses/{response_id}", dependencies=[Depends(Require("support:write"))])
def update_canned_response(
    response_id: int,
    payload: CannedResponseUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a canned response."""
    response = db.query(CannedResponse).filter(CannedResponse.id == response_id).first()
    if not response:
        raise HTTPException(status_code=404, detail="Canned response not found")

    if payload.name is not None:
        response.name = payload.name
    if payload.shortcode is not None:
        if payload.shortcode:
            existing = db.query(CannedResponse).filter(
                CannedResponse.shortcode == payload.shortcode,
                CannedResponse.id != response_id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"Shortcode '{payload.shortcode}' already exists"
                )
        response.shortcode = payload.shortcode
    if payload.content is not None:
        response.content = payload.content
    if payload.scope is not None:
        try:
            CannedResponseScope(payload.scope)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid scope: {payload.scope}")
        response.scope = payload.scope
    if payload.team_id is not None:
        response.team_id = payload.team_id
    if payload.agent_id is not None:
        response.agent_id = payload.agent_id
    if payload.category is not None:
        response.category = payload.category
    if payload.is_active is not None:
        response.is_active = payload.is_active

    db.commit()
    db.refresh(response)
    return {"id": response.id, "name": response.name}


@router.delete("/canned-responses/{response_id}", dependencies=[Depends(Require("support:write"))])
def delete_canned_response(
    response_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Delete a canned response."""
    response = db.query(CannedResponse).filter(CannedResponse.id == response_id).first()
    if not response:
        raise HTTPException(status_code=404, detail="Canned response not found")
    db.delete(response)
    db.commit()
    return Response(status_code=204)


@router.post("/canned-responses/{response_id}/render", dependencies=[Depends(Require("support:read"))])
def render_canned_response(
    response_id: int,
    payload: RenderRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Render a canned response with context variables.

    If ticket_id is provided, pulls context from the ticket.
    Additional context can be passed in the context field.
    """
    response = db.query(CannedResponse).filter(CannedResponse.id == response_id).first()
    if not response:
        raise HTTPException(status_code=404, detail="Canned response not found")

    context = payload.context or {}

    # Pull context from ticket if provided
    if payload.ticket_id:
        ticket = db.query(Ticket).filter(Ticket.id == payload.ticket_id).first()
        if ticket:
            context.setdefault("ticket_id", ticket.id)
            context.setdefault("ticket_subject", ticket.subject or "")
            context.setdefault("customer_name", ticket.customer_name or "Customer")

    # Update usage stats
    response.usage_count += 1
    response.last_used_at = datetime.utcnow()
    db.commit()

    rendered = response.render(context)

    return {
        "id": response.id,
        "name": response.name,
        "rendered_content": rendered,
        "context_used": context,
    }


@router.get("/canned-responses/search", dependencies=[Depends(Require("support:read"))])
def search_by_shortcode(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Search canned responses by shortcode or name.

    Useful for autocomplete when typing /shortcode in ticket reply.
    """
    search_term = f"%{q}%"
    responses = db.query(CannedResponse).filter(
        CannedResponse.is_active == True,
        or_(
            CannedResponse.shortcode.ilike(search_term),
            CannedResponse.name.ilike(search_term),
        )
    ).order_by(CannedResponse.usage_count.desc()).limit(10).all()

    return [
        {
            "id": r.id,
            "name": r.name,
            "shortcode": r.shortcode,
            "content_preview": r.content[:100] + "..." if len(r.content) > 100 else r.content,
            "category": r.category,
        }
        for r in responses
    ]


@router.get("/canned-responses/categories", dependencies=[Depends(Require("support:read"))])
def list_categories(
    db: Session = Depends(get_db),
) -> List[str]:
    """List unique canned response categories."""
    result = db.query(CannedResponse.category).filter(
        CannedResponse.category.isnot(None),
        CannedResponse.is_active == True,
    ).distinct().all()

    return [r[0] for r in result if r[0]]
