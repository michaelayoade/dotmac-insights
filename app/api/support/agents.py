"""Agent and team management endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agent import Agent, Team, TeamMember
from app.models.employee import Employee
from app.auth import Require

from .helpers import serialize_agent, serialize_team

router = APIRouter()


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class AgentCreateRequest(BaseModel):
    employee_id: Optional[int] = None
    email: Optional[str] = None
    display_name: Optional[str] = None
    domains: Optional[dict] = None
    skills: Optional[dict] = None
    channel_caps: Optional[dict] = None
    routing_weight: int = 1
    capacity: Optional[int] = None
    is_active: bool = True


class AgentUpdateRequest(BaseModel):
    employee_id: Optional[int] = None
    email: Optional[str] = None
    display_name: Optional[str] = None
    domains: Optional[dict] = None
    skills: Optional[dict] = None
    channel_caps: Optional[dict] = None
    routing_weight: Optional[int] = None
    capacity: Optional[int] = None
    is_active: Optional[bool] = None


class TeamCreateRequest(BaseModel):
    team_name: str
    description: Optional[str] = None
    assignment_rule: Optional[str] = None
    domain: Optional[str] = None
    is_active: bool = True


class TeamUpdateRequest(BaseModel):
    team_name: Optional[str] = None
    description: Optional[str] = None
    assignment_rule: Optional[str] = None
    domain: Optional[str] = None
    is_active: Optional[bool] = None


class TeamMemberCreateRequest(BaseModel):
    agent_id: int
    role: Optional[str] = None


# =============================================================================
# AGENTS
# =============================================================================

@router.get("/agents", dependencies=[Depends(Require("support:read"))])
def list_agents(
    team_id: Optional[int] = None,
    domain: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List agents with optional filtering by team or domain."""
    query = db.query(Agent)
    if domain:
        query = query.filter(Agent.domains.contains({domain: True}))
    agents = query.all()

    team_membership = {}
    if team_id:
        member_rows = db.query(TeamMember).filter(TeamMember.team_id == team_id).all()
        team_membership = {m.agent_id: m for m in member_rows}

    return {
        "total": len(agents),
        "data": [
            serialize_agent(a, team_membership.get(a.id))
            for a in agents
        ],
    }


@router.post("/agents", dependencies=[Depends(Require("support:write"))], status_code=201)
def create_agent(
    payload: AgentCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a unified agent (linked to employee if provided)."""
    display_name = payload.display_name
    email = payload.email
    if payload.employee_id:
        emp = db.query(Employee).filter(Employee.id == payload.employee_id).first()
        if emp:
            display_name = display_name or emp.name
            email = email or emp.email
    agent = Agent(
        employee_id=payload.employee_id,
        email=email,
        display_name=display_name,
        domains=payload.domains,
        skills=payload.skills,
        channel_caps=payload.channel_caps,
        routing_weight=payload.routing_weight,
        capacity=payload.capacity,
        is_active=payload.is_active,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return {"id": agent.id}


@router.get("/agents/{agent_id}", dependencies=[Depends(Require("support:read"))])
def get_agent(
    agent_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get agent details."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get team memberships
    memberships = db.query(TeamMember).filter(TeamMember.agent_id == agent_id).all()
    teams = []
    for m in memberships:
        team = db.query(Team).filter(Team.id == m.team_id).first()
        if team:
            teams.append({
                "team_id": team.id,
                "team_name": team.name,
                "role": m.role,
                "is_active": m.is_active,
            })

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
        "teams": teams,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
        "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
    }


@router.patch("/agents/{agent_id}", dependencies=[Depends(Require("support:write"))])
def update_agent(
    agent_id: int,
    payload: AgentUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update agent metadata."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if payload.employee_id is not None:
        agent.employee_id = payload.employee_id
    if payload.email is not None:
        agent.email = payload.email
    if payload.display_name is not None:
        agent.display_name = payload.display_name
    if payload.domains is not None:
        agent.domains = payload.domains
    if payload.skills is not None:
        agent.skills = payload.skills
    if payload.channel_caps is not None:
        agent.channel_caps = payload.channel_caps
    if payload.routing_weight is not None:
        agent.routing_weight = payload.routing_weight
    if payload.capacity is not None:
        agent.capacity = payload.capacity
    if payload.is_active is not None:
        agent.is_active = payload.is_active

    agent.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(agent)
    return {"id": agent.id}


@router.delete("/agents/{agent_id}", dependencies=[Depends(Require("support:write"))])
def delete_agent(
    agent_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Delete an agent."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(agent)
    db.commit()
    return Response(status_code=204)


# =============================================================================
# TEAMS
# =============================================================================

@router.get("/teams", dependencies=[Depends(Require("support:read"))])
def list_teams(
    domain: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List teams with members."""
    query = db.query(Team)
    if domain:
        query = query.filter(Team.domain == domain)
    teams = query.all()
    return [serialize_team(t) for t in teams]


@router.post("/teams", dependencies=[Depends(Require("support:write"))], status_code=201)
def create_team(
    payload: TeamCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a team."""
    team = Team(
        name=payload.team_name,
        description=payload.description,
        assignment_rule=payload.assignment_rule,
        domain=payload.domain,
        is_active=payload.is_active,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return {"id": team.id, "team_name": team.name}


@router.get("/teams/{team_id}", dependencies=[Depends(Require("support:read"))])
def get_team(
    team_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get team details with members."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    members = []
    for m in team.members:
        agent = db.query(Agent).filter(Agent.id == m.agent_id).first()
        members.append({
            "id": m.id,
            "agent_id": m.agent_id,
            "agent_name": agent.display_name if agent else None,
            "agent_email": agent.email if agent else None,
            "role": m.role,
            "is_active": m.is_active,
        })

    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "domain": team.domain,
        "assignment_rule": team.assignment_rule,
        "is_active": team.is_active,
        "members": members,
        "created_at": team.created_at.isoformat() if team.created_at else None,
        "updated_at": team.updated_at.isoformat() if team.updated_at else None,
    }


@router.patch("/teams/{team_id}", dependencies=[Depends(Require("support:write"))])
def update_team(
    team_id: int,
    payload: TeamUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a team."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    if payload.team_name is not None:
        team.name = payload.team_name
    if payload.description is not None:
        team.description = payload.description
    if payload.assignment_rule is not None:
        team.assignment_rule = payload.assignment_rule
    if payload.domain is not None:
        team.domain = payload.domain
    if payload.is_active is not None:
        team.is_active = payload.is_active

    db.commit()
    db.refresh(team)
    return {"id": team.id, "team_name": team.name}


@router.delete("/teams/{team_id}", dependencies=[Depends(Require("support:write"))])
def delete_team(
    team_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Delete a team and its members."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    db.delete(team)
    db.commit()
    return Response(status_code=204)


# =============================================================================
# TEAM MEMBERS
# =============================================================================

@router.post("/teams/{team_id}/members", dependencies=[Depends(Require("support:write"))], status_code=201)
def add_team_member(
    team_id: int,
    payload: TeamMemberCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add an agent to a team."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    agent = db.query(Agent).filter(Agent.id == payload.agent_id).first()
    if not agent:
        raise HTTPException(status_code=400, detail="agent_id does not exist")

    # Check if already a member
    existing = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.agent_id == payload.agent_id
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Agent is already a member of this team")

    member = TeamMember(
        team_id=team_id,
        agent_id=payload.agent_id,
        role=payload.role,
        is_active=True,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return {"id": member.id, "team_id": member.team_id}


@router.delete("/teams/{team_id}/members/{member_id}", dependencies=[Depends(Require("support:write"))])
def remove_team_member(
    team_id: int,
    member_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Remove an agent from a team."""
    member = db.query(TeamMember).filter(
        TeamMember.id == member_id, TeamMember.team_id == team_id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    db.delete(member)
    db.commit()
    return Response(status_code=204)
