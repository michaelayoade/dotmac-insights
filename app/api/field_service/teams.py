"""
Field Teams and Technicians API

Management of field service teams, technicians, and their skills.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import date, timedelta
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require, Principal, get_current_principal
from app.services.field_service import (
    TeamService,
    TeamFilters,
    TeamCreateData,
    TeamUpdateData,
    TeamMemberData,
    TechnicianFilters,
    TechnicianSkillData,
    ZoneFilters,
    ZoneCreateData,
    ZoneUpdateData,
)
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError

router = APIRouter()


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================

class FieldTeamCreate(BaseModel):
    """Schema for creating a field team."""
    name: str
    description: Optional[str] = None
    coverage_zone_ids: Optional[List[int]] = None
    max_daily_orders: int = 10
    supervisor_id: Optional[int] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None


class FieldTeamUpdate(BaseModel):
    """Schema for updating a field team."""
    name: Optional[str] = None
    description: Optional[str] = None
    coverage_zone_ids: Optional[List[int]] = None
    max_daily_orders: Optional[int] = None
    supervisor_id: Optional[int] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    is_active: Optional[bool] = None


class TeamMemberAdd(BaseModel):
    """Schema for adding a team member."""
    employee_id: int
    role: str = "technician"  # lead, technician, helper


class TechnicianSkillCreate(BaseModel):
    """Schema for adding a technician skill."""
    skill_type: str
    proficiency_level: str = "intermediate"  # basic, intermediate, expert
    certification: Optional[str] = None
    certification_number: Optional[str] = None
    certification_date: Optional[date] = None
    certification_expiry: Optional[date] = None


class ServiceZoneCreate(BaseModel):
    """Schema for creating a service zone."""
    name: str
    code: str
    description: Optional[str] = None
    coverage_areas: Optional[List[str]] = None
    center_latitude: Optional[float] = None
    center_longitude: Optional[float] = None
    default_team_id: Optional[int] = None


class ServiceZoneUpdate(BaseModel):
    """Schema for updating a service zone."""
    name: Optional[str] = None
    description: Optional[str] = None
    coverage_areas: Optional[List[str]] = None
    center_latitude: Optional[float] = None
    center_longitude: Optional[float] = None
    default_team_id: Optional[int] = None
    is_active: Optional[bool] = None


# =============================================================================
# FIELD TEAMS
# =============================================================================

@router.get("/teams", dependencies=[Depends(Require("explorer:read"))])
async def list_teams(
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """List field teams."""
    service = TeamService(db, principal)
    filters = TeamFilters(is_active=is_active, search=search)
    pagination = PaginationParams(limit=limit, offset=offset)

    result = service.list_teams(filters, pagination)

    return {
        "total": result.total,
        "limit": result.limit,
        "offset": result.offset,
        "data": [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "coverage_zone_ids": t.coverage_zone_ids,
                "max_daily_orders": t.max_daily_orders,
                "supervisor_id": t.supervisor_id,
                "supervisor_name": t.supervisor.name if t.supervisor else None,
                "contact_phone": t.contact_phone,
                "contact_email": t.contact_email,
                "is_active": t.is_active,
                "member_count": len(t.members),
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in result.items
        ],
    }


@router.get("/teams/{team_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_team(
    team_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get detailed team information."""
    service = TeamService(db, principal)

    try:
        team = service.get_team(team_id)
    except NotFoundError:
        raise HTTPException(404, "Team not found")

    stats = service.get_team_stats(team_id)

    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "coverage_zone_ids": team.coverage_zone_ids,
        "max_daily_orders": team.max_daily_orders,
        "supervisor_id": team.supervisor_id,
        "supervisor": {
            "id": team.supervisor.id,
            "name": team.supervisor.name,
            "email": team.supervisor.email,
        } if team.supervisor else None,
        "contact_phone": team.contact_phone,
        "contact_email": team.contact_email,
        "is_active": team.is_active,
        "active_orders": stats["active_orders"],
        "today_orders": stats["today_orders"],
        "members": [
            {
                "id": m.id,
                "employee_id": m.employee_id,
                "employee_name": m.employee.name if m.employee else None,
                "role": m.role,
                "is_active": m.is_active,
                "joined_date": m.joined_date.isoformat() if m.joined_date else None,
            }
            for m in team.members
        ],
        "created_at": team.created_at.isoformat() if team.created_at else None,
        "updated_at": team.updated_at.isoformat() if team.updated_at else None,
    }


@router.post("/teams", dependencies=[Depends(Require("field-service:admin"))])
async def create_team(
    payload: FieldTeamCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new field team."""
    service = TeamService(db, principal)

    data = TeamCreateData(
        name=payload.name,
        description=payload.description,
        coverage_zone_ids=payload.coverage_zone_ids,
        max_daily_orders=payload.max_daily_orders,
        supervisor_id=payload.supervisor_id,
        contact_phone=payload.contact_phone,
        contact_email=payload.contact_email,
    )

    team = service.create_team(data)
    db.commit()

    return await get_team(team.id, db, principal)


@router.patch("/teams/{team_id}", dependencies=[Depends(Require("field-service:admin"))])
async def update_team(
    team_id: int,
    payload: FieldTeamUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a field team."""
    service = TeamService(db, principal)

    data = TeamUpdateData(
        name=payload.name,
        description=payload.description,
        coverage_zone_ids=payload.coverage_zone_ids,
        max_daily_orders=payload.max_daily_orders,
        supervisor_id=payload.supervisor_id,
        contact_phone=payload.contact_phone,
        contact_email=payload.contact_email,
        is_active=payload.is_active,
    )

    try:
        service.update_team(team_id, data)
        db.commit()
    except NotFoundError:
        raise HTTPException(404, "Team not found")

    return await get_team(team_id, db, principal)


@router.delete("/teams/{team_id}", dependencies=[Depends(Require("field-service:admin"))])
async def delete_team(
    team_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Deactivate a field team."""
    service = TeamService(db, principal)

    try:
        service.deactivate_team(team_id)
        db.commit()
    except NotFoundError:
        raise HTTPException(404, "Team not found")

    return {"message": "Team deactivated", "id": team_id}


# =============================================================================
# TEAM MEMBERS
# =============================================================================

@router.post("/teams/{team_id}/members", dependencies=[Depends(Require("field-service:admin"))])
async def add_team_member(
    team_id: int,
    payload: TeamMemberAdd,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Add a member to a team."""
    service = TeamService(db, principal)

    data = TeamMemberData(
        employee_id=payload.employee_id,
        role=payload.role,
    )

    try:
        member = service.add_member(team_id, data)
        db.commit()
    except NotFoundError as e:
        raise HTTPException(404, str(e))
    except ValidationError as e:
        raise HTTPException(400, str(e))

    employee_name = member.employee.name if member.employee else None

    return {
        "message": "Member added",
        "member_id": member.id,
        "employee_name": employee_name,
    }


@router.delete("/teams/{team_id}/members/{employee_id}", dependencies=[Depends(Require("field-service:admin"))])
async def remove_team_member(
    team_id: int,
    employee_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Remove a member from a team."""
    service = TeamService(db, principal)

    try:
        service.remove_member(team_id, employee_id)
        db.commit()
    except NotFoundError:
        raise HTTPException(404, "Team member not found")

    return {"message": "Member removed"}


# =============================================================================
# TECHNICIANS
# =============================================================================

@router.get("/technicians", dependencies=[Depends(Require("explorer:read"))])
async def list_technicians(
    team_id: Optional[int] = None,
    skill_type: Optional[str] = None,
    is_available: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """List field technicians."""
    service = TeamService(db, principal)
    filters = TechnicianFilters(
        team_id=team_id,
        skill_type=skill_type,
        is_available=is_available,
        search=search,
    )
    pagination = PaginationParams(limit=limit, offset=offset)

    result = service.list_technicians(filters, pagination)

    # Build response with additional data
    data = []
    for tech in result.items:
        skills = service.get_technician_skills(tech.id)
        teams = service.get_technician_teams(tech.id)

        data.append({
            "id": tech.id,
            "employee_name": tech.name,
            "company_email": tech.email,
            "cell_number": tech.phone,
            "department": tech.department,
            "designation": tech.designation,
            "today_orders": 0,  # Can be computed if needed
            "teams": [
                {"team_id": m.team_id, "role": m.role}
                for m in teams
            ],
            "skills": [
                {
                    "id": s.id,
                    "skill_type": s.skill_type,
                    "proficiency_level": s.proficiency_level,
                    "certification": s.certification,
                    "certification_expiry": s.certification_expiry.isoformat() if s.certification_expiry else None,
                }
                for s in skills
            ],
        })

    return {
        "total": result.total,
        "limit": result.limit,
        "offset": result.offset,
        "data": data,
    }


@router.get("/technicians/{technician_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_technician(
    technician_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get detailed technician information."""
    service = TeamService(db, principal)

    try:
        tech = service.get_technician(technician_id)
    except NotFoundError:
        raise HTTPException(404, "Technician not found")

    skills = service.get_technician_skills(technician_id)
    teams = service.get_technician_teams(technician_id)

    return {
        "id": tech.id,
        "employee_name": tech.name,
        "company_email": tech.email,
        "cell_number": tech.phone,
        "department": tech.department,
        "designation": tech.designation,
        "teams": [
            {
                "team_id": m.team_id,
                "team_name": m.team.name if m.team else None,
                "role": m.role,
                "joined_date": m.joined_date.isoformat() if m.joined_date else None,
            }
            for m in teams
        ],
        "skills": [
            {
                "id": s.id,
                "skill_type": s.skill_type,
                "proficiency_level": s.proficiency_level,
                "certification": s.certification,
                "certification_number": s.certification_number,
                "certification_date": s.certification_date.isoformat() if s.certification_date else None,
                "certification_expiry": s.certification_expiry.isoformat() if s.certification_expiry else None,
            }
            for s in skills
        ],
        "performance": {
            "completed_30_days": 0,  # Can be computed if needed
            "avg_rating": 0.0,
        },
        "today_schedule": [],  # Can be computed if needed
    }


# =============================================================================
# TECHNICIAN SKILLS
# =============================================================================

@router.post("/technicians/{technician_id}/skills", dependencies=[Depends(Require("field-service:admin"))])
async def add_skill(
    technician_id: int,
    payload: TechnicianSkillCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Add a skill to a technician."""
    service = TeamService(db, principal)

    data = TechnicianSkillData(
        skill_type=payload.skill_type,
        proficiency_level=payload.proficiency_level,
        certification=payload.certification,
        certification_number=payload.certification_number,
        certification_date=payload.certification_date,
        certification_expiry=payload.certification_expiry,
    )

    try:
        skill = service.add_skill(technician_id, data)
        db.commit()
    except NotFoundError:
        raise HTTPException(404, "Technician not found")

    return {
        "id": skill.id,
        "skill_type": skill.skill_type,
        "proficiency_level": skill.proficiency_level,
    }


@router.delete("/technicians/{technician_id}/skills/{skill_id}", dependencies=[Depends(Require("field-service:admin"))])
async def remove_skill(
    technician_id: int,
    skill_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Remove a skill from a technician."""
    service = TeamService(db, principal)

    try:
        service.remove_skill(technician_id, skill_id)
        db.commit()
    except NotFoundError:
        raise HTTPException(404, "Skill not found")

    return {"message": "Skill removed"}


# =============================================================================
# SERVICE ZONES
# =============================================================================

@router.get("/zones", dependencies=[Depends(Require("explorer:read"))])
async def list_zones(
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """List service zones."""
    service = TeamService(db, principal)
    filters = ZoneFilters(is_active=is_active)
    zones = service.list_zones(filters)

    return {
        "total": len(zones),
        "data": [
            {
                "id": z.id,
                "name": z.name,
                "code": z.code,
                "description": z.description,
                "coverage_areas": z.coverage_areas,
                "center_latitude": float(z.center_latitude) if z.center_latitude else None,
                "center_longitude": float(z.center_longitude) if z.center_longitude else None,
                "default_team_id": z.default_team_id,
                "default_team_name": z.default_team.name if z.default_team else None,
                "is_active": z.is_active,
            }
            for z in zones
        ],
    }


@router.post("/zones", dependencies=[Depends(Require("field-service:admin"))])
async def create_zone(
    payload: ServiceZoneCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a service zone."""
    service = TeamService(db, principal)

    data = ZoneCreateData(
        name=payload.name,
        code=payload.code,
        description=payload.description,
        coverage_areas=payload.coverage_areas,
        center_latitude=payload.center_latitude,
        center_longitude=payload.center_longitude,
        default_team_id=payload.default_team_id,
    )

    try:
        zone = service.create_zone(data)
        db.commit()
    except ValidationError as e:
        raise HTTPException(400, str(e))

    return {
        "id": zone.id,
        "name": zone.name,
        "code": zone.code,
    }


@router.patch("/zones/{zone_id}", dependencies=[Depends(Require("field-service:admin"))])
async def update_zone(
    zone_id: int,
    payload: ServiceZoneUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a service zone."""
    service = TeamService(db, principal)

    data = ZoneUpdateData(
        name=payload.name,
        description=payload.description,
        coverage_areas=payload.coverage_areas,
        center_latitude=payload.center_latitude,
        center_longitude=payload.center_longitude,
        default_team_id=payload.default_team_id,
        is_active=payload.is_active,
    )

    try:
        zone = service.update_zone(zone_id, data)
        db.commit()
    except NotFoundError:
        raise HTTPException(404, "Zone not found")

    return {
        "id": zone.id,
        "name": zone.name,
        "code": zone.code,
        "is_active": zone.is_active,
    }
