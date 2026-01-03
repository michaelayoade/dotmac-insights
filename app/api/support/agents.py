"""Agent and team management endpoints.

Refactored to use AgentService for all business logic.
"""
from __future__ import annotations

from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import Require, get_principal, Principal
from app.services.support import (
    AgentService,
    AgentCreate,
    AgentUpdate,
    AgentFilters,
    TeamCreate,
    TeamUpdate,
    AgentNotFoundError,
    DuplicateAgentError,
    TeamNotFoundError,
    DuplicateTeamError,
    TeamMembershipError,
)

from .helpers import serialize_agent, serialize_team

router = APIRouter()


# =============================================================================
# DEPENDENCIES
# =============================================================================

def get_agent_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> AgentService:
    """Dependency to get AgentService instance."""
    return AgentService(db, principal)


# =============================================================================
# PYDANTIC MODELS (API Input Validation)
# =============================================================================

class AgentCreateRequest(BaseModel):
    employee_id: Optional[int] = None
    email: Optional[str] = None
    display_name: Optional[str] = None
    domains: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    channel_caps: Optional[dict] = None
    routing_weight: int = 1
    capacity: Optional[int] = None


class AgentUpdateRequest(BaseModel):
    employee_id: Optional[int] = None
    email: Optional[str] = None
    display_name: Optional[str] = None
    domains: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    channel_caps: Optional[dict] = None
    routing_weight: Optional[int] = None
    capacity: Optional[int] = None
    is_active: Optional[bool] = None


class TeamCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    assignment_rule: Optional[str] = None
    domain: Optional[str] = None


class TeamUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    assignment_rule: Optional[str] = None
    domain: Optional[str] = None
    is_active: Optional[bool] = None


class TeamMemberCreateRequest(BaseModel):
    agent_id: int
    role: Optional[str] = "member"


# =============================================================================
# AGENTS
# =============================================================================

@router.get("/agents", dependencies=[Depends(Require("support:read"))])
def list_agents(
    team_id: Optional[int] = None,
    domain: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    service: AgentService = Depends(get_agent_service),
) -> Dict[str, Any]:
    """List agents with optional filtering by team, domain, or search."""
    filters = AgentFilters(
        team_id=team_id,
        domain=domain,
        is_active=is_active,
        search=search,
    )
    agents = service.list_agents(filters=filters)

    return {
        "total": len(agents),
        "data": [serialize_agent(a) for a in agents],
    }


@router.post("/agents", dependencies=[Depends(Require("support:write"))], status_code=201)
def create_agent(
    payload: AgentCreateRequest,
    db: Session = Depends(get_db),
    service: AgentService = Depends(get_agent_service),
) -> Dict[str, Any]:
    """Create a unified agent (linked to employee if provided)."""
    try:
        data = AgentCreate(
            email=payload.email or "",
            display_name=payload.display_name or "",
            employee_id=payload.employee_id,
            domains=payload.domains or [],
            skills=payload.skills or [],
            channel_caps=payload.channel_caps or {},
            routing_weight=payload.routing_weight,
            capacity=payload.capacity or 10,
        )
        agent = service.create_agent(data)
        db.commit()
        return {"id": agent.id}
    except DuplicateAgentError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/agents/{agent_id}", dependencies=[Depends(Require("support:read"))])
def get_agent(
    agent_id: int,
    service: AgentService = Depends(get_agent_service),
) -> Dict[str, Any]:
    """Get agent details with team memberships."""
    try:
        agent = service.get_agent(agent_id)
        teams = service.get_agent_teams(agent_id)
        workload = service.get_agent_workload(agent_id)

        return {
            "id": agent.id,
            "employee_id": agent.employee_id,
            "email": agent.email,
            "display_name": agent.display_name,
            "domains": agent.domains,
            "skills": agent.skills,
            "channel_caps": agent.channel_caps,
            "routing_weight": agent.routing_weight,
            "capacity": agent.capacity,
            "is_active": agent.is_active,
            "teams": [
                {"team_id": t.id, "team_name": t.name, "domain": t.domain}
                for t in teams
            ],
            "workload": {
                "open_tickets": workload.open_tickets,
                "open_conversations": workload.open_conversations,
                "total_active": workload.total_active,
                "utilization_pct": workload.utilization_pct,
            },
            "created_at": agent.created_at.isoformat() if agent.created_at else None,
            "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
        }
    except AgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/agents/{agent_id}", dependencies=[Depends(Require("support:write"))])
def update_agent(
    agent_id: int,
    payload: AgentUpdateRequest,
    db: Session = Depends(get_db),
    service: AgentService = Depends(get_agent_service),
) -> Dict[str, Any]:
    """Update agent metadata."""
    try:
        data = AgentUpdate(
            display_name=payload.display_name,
            domains=payload.domains,
            skills=payload.skills,
            channel_caps=payload.channel_caps,
            routing_weight=payload.routing_weight,
            capacity=payload.capacity,
            is_active=payload.is_active,
        )
        agent = service.update_agent(agent_id, data)
        db.commit()
        return {"id": agent.id}
    except AgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/agents/{agent_id}", dependencies=[Depends(Require("support:write"))])
def delete_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    service: AgentService = Depends(get_agent_service),
) -> Response:
    """Delete an agent."""
    try:
        service.delete_agent(agent_id)
        db.commit()
        return Response(status_code=204)
    except AgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/agents/{agent_id}/workload", dependencies=[Depends(Require("support:read"))])
def get_agent_workload(
    agent_id: int,
    service: AgentService = Depends(get_agent_service),
) -> Dict[str, Any]:
    """Get agent workload metrics."""
    try:
        workload = service.get_agent_workload(agent_id)
        return {
            "agent_id": workload.agent_id,
            "open_tickets": workload.open_tickets,
            "open_conversations": workload.open_conversations,
            "total_active": workload.total_active,
            "capacity": workload.capacity,
            "utilization_pct": workload.utilization_pct,
            "is_available": workload.utilization_pct < 100,
        }
    except AgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# TEAMS
# =============================================================================

@router.get("/teams", dependencies=[Depends(Require("support:read"))])
def list_teams(
    domain: Optional[str] = None,
    active_only: bool = True,
    service: AgentService = Depends(get_agent_service),
) -> List[Dict[str, Any]]:
    """List teams with optional filtering."""
    teams = service.list_teams(domain=domain, active_only=active_only)
    return [serialize_team(t) for t in teams]


@router.post("/teams", dependencies=[Depends(Require("support:write"))], status_code=201)
def create_team(
    payload: TeamCreateRequest,
    db: Session = Depends(get_db),
    service: AgentService = Depends(get_agent_service),
) -> Dict[str, Any]:
    """Create a team."""
    try:
        data = TeamCreate(
            name=payload.name,
            description=payload.description,
            assignment_rule=payload.assignment_rule or "round_robin",
            domain=payload.domain or "support",
        )
        team = service.create_team(data)
        db.commit()
        return {"id": team.id, "name": team.name}
    except DuplicateTeamError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/teams/{team_id}", dependencies=[Depends(Require("support:read"))])
def get_team(
    team_id: int,
    service: AgentService = Depends(get_agent_service),
) -> Dict[str, Any]:
    """Get team details with members and workload."""
    try:
        team = service.get_team(team_id)
        members = service.get_team_members(team_id, active_only=False)
        workload = service.get_team_workload(team_id)

        return {
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "domain": team.domain,
            "assignment_rule": team.assignment_rule,
            "is_active": team.is_active,
            "members": [
                {
                    "agent_id": m.id,
                    "display_name": m.display_name,
                    "email": m.email,
                    "is_active": m.is_active,
                }
                for m in members
            ],
            "workload": {
                "total_open": workload.total_open,
                "total_agents": workload.total_agents,
                "available_agents": workload.available_agents,
                "avg_utilization_pct": workload.avg_utilization_pct,
            },
            "created_at": team.created_at.isoformat() if team.created_at else None,
            "updated_at": team.updated_at.isoformat() if team.updated_at else None,
        }
    except TeamNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/teams/{team_id}", dependencies=[Depends(Require("support:write"))])
def update_team(
    team_id: int,
    payload: TeamUpdateRequest,
    db: Session = Depends(get_db),
    service: AgentService = Depends(get_agent_service),
) -> Dict[str, Any]:
    """Update a team."""
    try:
        data = TeamUpdate(
            name=payload.name,
            description=payload.description,
            assignment_rule=payload.assignment_rule,
            domain=payload.domain,
            is_active=payload.is_active,
        )
        team = service.update_team(team_id, data)
        db.commit()
        return {"id": team.id, "name": team.name}
    except TeamNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DuplicateTeamError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/teams/{team_id}", dependencies=[Depends(Require("support:write"))])
def delete_team(
    team_id: int,
    db: Session = Depends(get_db),
    service: AgentService = Depends(get_agent_service),
) -> Response:
    """Delete a team and its members."""
    try:
        service.delete_team(team_id)
        db.commit()
        return Response(status_code=204)
    except TeamNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/teams/{team_id}/workload", dependencies=[Depends(Require("support:read"))])
def get_team_workload(
    team_id: int,
    service: AgentService = Depends(get_agent_service),
) -> Dict[str, Any]:
    """Get team workload metrics."""
    try:
        workload = service.get_team_workload(team_id)
        return {
            "team_id": workload.team_id,
            "total_open": workload.total_open,
            "total_agents": workload.total_agents,
            "available_agents": workload.available_agents,
            "avg_utilization_pct": workload.avg_utilization_pct,
        }
    except TeamNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# TEAM MEMBERS
# =============================================================================

@router.get("/teams/{team_id}/members", dependencies=[Depends(Require("support:read"))])
def list_team_members(
    team_id: int,
    active_only: bool = True,
    service: AgentService = Depends(get_agent_service),
) -> List[Dict[str, Any]]:
    """List team members."""
    try:
        members = service.get_team_members(team_id, active_only=active_only)
        return [
            {
                "agent_id": m.id,
                "display_name": m.display_name,
                "email": m.email,
                "is_active": m.is_active,
                "capacity": m.capacity,
            }
            for m in members
        ]
    except TeamNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/teams/{team_id}/members", dependencies=[Depends(Require("support:write"))], status_code=201)
def add_team_member(
    team_id: int,
    payload: TeamMemberCreateRequest,
    db: Session = Depends(get_db),
    service: AgentService = Depends(get_agent_service),
) -> Dict[str, Any]:
    """Add an agent to a team."""
    try:
        member = service.add_member(team_id, payload.agent_id, payload.role or "member")
        db.commit()
        return {"id": member.id, "team_id": member.team_id, "agent_id": member.agent_id}
    except TeamNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AgentNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TeamMembershipError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/teams/{team_id}/members/{agent_id}", dependencies=[Depends(Require("support:write"))])
def remove_team_member(
    team_id: int,
    agent_id: int,
    db: Session = Depends(get_db),
    service: AgentService = Depends(get_agent_service),
) -> Response:
    """Remove an agent from a team."""
    try:
        service.remove_member(team_id, agent_id)
        db.commit()
        return Response(status_code=204)
    except TeamMembershipError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# SKILLS
# =============================================================================

@router.get("/agents/by-skill/{skill}", dependencies=[Depends(Require("support:read"))])
def get_agents_by_skill(
    skill: str,
    service: AgentService = Depends(get_agent_service),
) -> List[Dict[str, Any]]:
    """Get agents with a specific skill."""
    agents = service.get_agents_by_skill(skill)
    return [serialize_agent(a) for a in agents]


@router.post("/agents/{agent_id}/skills/{skill}", dependencies=[Depends(Require("support:write"))], status_code=201)
def add_agent_skill(
    agent_id: int,
    skill: str,
    level: int = 1,
    db: Session = Depends(get_db),
    service: AgentService = Depends(get_agent_service),
) -> Dict[str, Any]:
    """Add a skill to an agent."""
    try:
        agent = service.add_skill(agent_id, skill, level)
        db.commit()
        return {"id": agent.id, "skills": agent.skills}
    except AgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/agents/{agent_id}/skills/{skill}", dependencies=[Depends(Require("support:write"))])
def remove_agent_skill(
    agent_id: int,
    skill: str,
    db: Session = Depends(get_db),
    service: AgentService = Depends(get_agent_service),
) -> Dict[str, Any]:
    """Remove a skill from an agent."""
    try:
        agent = service.remove_skill(agent_id, skill)
        db.commit()
        return {"id": agent.id, "skills": agent.skills}
    except AgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
