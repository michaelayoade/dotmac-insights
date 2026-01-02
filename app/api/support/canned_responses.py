"""Canned Responses (Macros) API endpoints.

Refactored to use CannedResponseService for all business logic.
"""
from __future__ import annotations

from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import Require, get_principal, Principal
from app.models.ticket import Ticket
from app.services.support import (
    CannedResponseService,
    CannedResponseCreate,
    CannedResponseUpdate,
    CannedResponseNotFoundError,
    DuplicateShortcodeError,
)

router = APIRouter()


# =============================================================================
# DEPENDENCIES
# =============================================================================

def get_canned_response_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> CannedResponseService:
    """Dependency to get CannedResponseService instance."""
    return CannedResponseService(db, principal)


# =============================================================================
# PYDANTIC MODELS (API Input Validation)
# =============================================================================

class CannedResponseCreateRequest(BaseModel):
    name: str
    shortcode: Optional[str] = None
    content: str
    scope: str = "personal"
    team_id: Optional[int] = None
    agent_id: Optional[int] = None
    category: Optional[str] = None


class CannedResponseUpdateRequest(BaseModel):
    name: Optional[str] = None
    shortcode: Optional[str] = None
    content: Optional[str] = None
    scope: Optional[str] = None
    team_id: Optional[int] = None
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
    agent_id: Optional[int] = None,
    search: Optional[str] = None,
    include_inactive: bool = False,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    service: CannedResponseService = Depends(get_canned_response_service),
) -> Dict[str, Any]:
    """List canned responses with filtering."""
    responses = service.list(
        scope=scope,
        team_id=team_id,
        agent_id=agent_id,
        category=category,
        search=search,
        active_only=not include_inactive,
    )

    # Apply pagination
    total = len(responses)
    paginated = responses[offset:offset + limit]

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
            for r in paginated
        ],
    }


@router.post("/canned-responses", dependencies=[Depends(Require("support:write"))], status_code=201)
def create_canned_response(
    payload: CannedResponseCreateRequest,
    db: Session = Depends(get_db),
    service: CannedResponseService = Depends(get_canned_response_service),
) -> Dict[str, Any]:
    """Create a canned response."""
    try:
        data = CannedResponseCreate(
            name=payload.name,
            content=payload.content,
            shortcode=payload.shortcode,
            scope=payload.scope,
            team_id=payload.team_id,
            agent_id=payload.agent_id,
            category=payload.category,
        )
        response = service.create(data)
        db.commit()
        return {"id": response.id, "name": response.name}
    except DuplicateShortcodeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/canned-responses/search", dependencies=[Depends(Require("support:read"))])
def search_by_shortcode(
    q: str = Query(..., min_length=1),
    service: CannedResponseService = Depends(get_canned_response_service),
) -> List[Dict[str, Any]]:
    """Search canned responses by shortcode or name.

    Useful for autocomplete when typing /shortcode in ticket reply.
    """
    responses = service.list(search=q, active_only=True)

    # Sort by usage count and limit to 10
    responses = sorted(responses, key=lambda r: r.usage_count or 0, reverse=True)[:10]

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
    service: CannedResponseService = Depends(get_canned_response_service),
) -> List[str]:
    """List unique canned response categories."""
    return service.get_categories()


@router.get("/canned-responses/variables", dependencies=[Depends(Require("support:read"))])
def list_supported_variables(
    service: CannedResponseService = Depends(get_canned_response_service),
) -> List[str]:
    """List supported placeholder variables for canned responses."""
    return service.get_supported_variables()


@router.get("/canned-responses/popular", dependencies=[Depends(Require("support:read"))])
def get_popular_responses(
    limit: int = Query(default=10, le=50),
    service: CannedResponseService = Depends(get_canned_response_service),
) -> List[Dict[str, Any]]:
    """Get most frequently used canned responses."""
    responses = service.get_most_used(limit=limit)
    return [
        {
            "id": r.id,
            "name": r.name,
            "shortcode": r.shortcode,
            "category": r.category,
            "usage_count": r.usage_count,
        }
        for r in responses
    ]


@router.get("/canned-responses/for-agent/{agent_id}", dependencies=[Depends(Require("support:read"))])
def get_responses_for_agent(
    agent_id: int,
    service: CannedResponseService = Depends(get_canned_response_service),
) -> List[Dict[str, Any]]:
    """Get all canned responses available to an agent (personal + team + global)."""
    responses = service.get_available_for_agent(agent_id)
    return [
        {
            "id": r.id,
            "name": r.name,
            "shortcode": r.shortcode,
            "content_preview": r.content[:100] + "..." if len(r.content) > 100 else r.content,
            "scope": r.scope,
            "category": r.category,
        }
        for r in responses
    ]


@router.get("/canned-responses/{response_id}", dependencies=[Depends(Require("support:read"))])
def get_canned_response(
    response_id: int,
    service: CannedResponseService = Depends(get_canned_response_service),
) -> Dict[str, Any]:
    """Get canned response details."""
    try:
        response = service.get(response_id)
        variables = service.extract_variables(response.content)

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
            "variables_used": variables,
            "created_at": response.created_at.isoformat() if response.created_at else None,
            "updated_at": response.updated_at.isoformat() if response.updated_at else None,
        }
    except CannedResponseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/canned-responses/{response_id}", dependencies=[Depends(Require("support:write"))])
def update_canned_response(
    response_id: int,
    payload: CannedResponseUpdateRequest,
    db: Session = Depends(get_db),
    service: CannedResponseService = Depends(get_canned_response_service),
) -> Dict[str, Any]:
    """Update a canned response."""
    try:
        data = CannedResponseUpdate(
            name=payload.name,
            content=payload.content,
            shortcode=payload.shortcode,
            scope=payload.scope,
            team_id=payload.team_id,
            category=payload.category,
            is_active=payload.is_active,
        )
        response = service.update(response_id, data)
        db.commit()
        return {"id": response.id, "name": response.name}
    except CannedResponseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DuplicateShortcodeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/canned-responses/{response_id}", dependencies=[Depends(Require("support:write"))])
def delete_canned_response(
    response_id: int,
    db: Session = Depends(get_db),
    service: CannedResponseService = Depends(get_canned_response_service),
) -> Response:
    """Delete a canned response."""
    try:
        service.delete(response_id)
        db.commit()
        return Response(status_code=204)
    except CannedResponseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/canned-responses/{response_id}/render", dependencies=[Depends(Require("support:read"))])
def render_canned_response(
    response_id: int,
    payload: RenderRequest,
    db: Session = Depends(get_db),
    service: CannedResponseService = Depends(get_canned_response_service),
) -> Dict[str, Any]:
    """Render a canned response with context variables.

    If ticket_id is provided, pulls context from the ticket.
    Additional context can be passed in the context field.
    """
    try:
        response = service.get(response_id)

        # Get ticket if provided
        ticket = None
        if payload.ticket_id:
            ticket = db.query(Ticket).filter(Ticket.id == payload.ticket_id).first()

        # Render with context
        rendered = service.render(
            response_id,
            variables=payload.context,
            ticket=ticket,
        )

        # Record usage
        service.record_usage(response_id)
        db.commit()

        return {
            "id": response.id,
            "name": response.name,
            "rendered_content": rendered,
            "context_used": payload.context or {},
        }
    except CannedResponseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/canned-responses/by-shortcode/{shortcode}", dependencies=[Depends(Require("support:read"))])
def get_by_shortcode(
    shortcode: str,
    agent_id: Optional[int] = None,
    service: CannedResponseService = Depends(get_canned_response_service),
) -> Dict[str, Any]:
    """Get a canned response by its shortcode."""
    response = service.get_by_shortcode(shortcode, agent_id=agent_id)
    if not response:
        raise HTTPException(status_code=404, detail=f"No canned response found with shortcode '{shortcode}'")

    return {
        "id": response.id,
        "name": response.name,
        "shortcode": response.shortcode,
        "content": response.content,
        "scope": response.scope,
        "category": response.category,
    }
