"""
Field Teams and Technicians API

Management of field service teams, technicians, and their skills.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any, Optional, List
from datetime import datetime, date
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require
from app.models.field_service import (
    FieldTeam,
    FieldTeamMember,
    TechnicianSkill,
    ServiceZone,
    ServiceOrder,
    ServiceOrderStatus,
)
from app.models.employee import Employee

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
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List field teams."""
    query = db.query(FieldTeam)

    if is_active is not None:
        query = query.filter(FieldTeam.is_active == is_active)

    if search:
        query = query.filter(FieldTeam.name.ilike(f"%{search}%"))

    total = query.count()
    teams = query.order_by(FieldTeam.name).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
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
            for t in teams
        ],
    }


@router.get("/teams/{team_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_team(team_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get detailed team information."""
    team = db.query(FieldTeam).filter(FieldTeam.id == team_id).first()
    if not team:
        raise HTTPException(404, "Team not found")

    # Get active orders count
    active_orders = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.assigned_team_id == team_id,
        ServiceOrder.status.notin_([ServiceOrderStatus.COMPLETED, ServiceOrderStatus.CANCELLED])
    ).scalar() or 0

    # Get today's orders
    today = date.today()
    today_orders = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.assigned_team_id == team_id,
        ServiceOrder.scheduled_date == today
    ).scalar() or 0

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
        "active_orders": active_orders,
        "today_orders": today_orders,
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
) -> Dict[str, Any]:
    """Create a new field team."""
    team = FieldTeam(
        name=payload.name,
        description=payload.description,
        coverage_zone_ids=payload.coverage_zone_ids,
        max_daily_orders=payload.max_daily_orders,
        supervisor_id=payload.supervisor_id,
        contact_phone=payload.contact_phone,
        contact_email=payload.contact_email,
    )

    db.add(team)
    db.commit()
    db.refresh(team)

    return await get_team(team.id, db)


@router.patch("/teams/{team_id}", dependencies=[Depends(Require("field-service:admin"))])
async def update_team(
    team_id: int,
    payload: FieldTeamUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a field team."""
    team = db.query(FieldTeam).filter(FieldTeam.id == team_id).first()
    if not team:
        raise HTTPException(404, "Team not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(team, key, value)

    db.commit()
    db.refresh(team)

    return await get_team(team_id, db)


@router.delete("/teams/{team_id}", dependencies=[Depends(Require("field-service:admin"))])
async def delete_team(team_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Deactivate a field team."""
    team = db.query(FieldTeam).filter(FieldTeam.id == team_id).first()
    if not team:
        raise HTTPException(404, "Team not found")

    team.is_active = False
    db.commit()

    return {"message": "Team deactivated", "id": team_id}


# =============================================================================
# TEAM MEMBERS
# =============================================================================

@router.post("/teams/{team_id}/members", dependencies=[Depends(Require("field-service:admin"))])
async def add_team_member(
    team_id: int,
    payload: TeamMemberAdd,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add a member to a team."""
    team = db.query(FieldTeam).filter(FieldTeam.id == team_id).first()
    if not team:
        raise HTTPException(404, "Team not found")

    employee = db.query(Employee).filter(Employee.id == payload.employee_id).first()
    if not employee:
        raise HTTPException(400, "Employee not found")

    # Check if already a member
    existing = db.query(FieldTeamMember).filter(
        FieldTeamMember.team_id == team_id,
        FieldTeamMember.employee_id == payload.employee_id
    ).first()

    if existing:
        if existing.is_active:
            raise HTTPException(400, "Employee is already a member of this team")
        else:
            existing.is_active = True
            existing.role = payload.role
            db.commit()
            return {"message": "Member reactivated", "member_id": existing.id}

    member = FieldTeamMember(
        team_id=team_id,
        employee_id=payload.employee_id,
        role=payload.role,
    )

    db.add(member)
    db.commit()

    return {
        "message": "Member added",
        "member_id": member.id,
        "employee_name": employee.name,
    }


@router.delete("/teams/{team_id}/members/{employee_id}", dependencies=[Depends(Require("field-service:admin"))])
async def remove_team_member(
    team_id: int,
    employee_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Remove a member from a team."""
    member = db.query(FieldTeamMember).filter(
        FieldTeamMember.team_id == team_id,
        FieldTeamMember.employee_id == employee_id
    ).first()

    if not member:
        raise HTTPException(404, "Team member not found")

    member.is_active = False
    db.commit()

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
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List field technicians."""
    # Get employees who are team members
    query = db.query(Employee).join(
        FieldTeamMember,
        and_(
            FieldTeamMember.employee_id == Employee.id,
            FieldTeamMember.is_active == True
        )
    ).distinct()

    if team_id:
        query = query.filter(FieldTeamMember.team_id == team_id)

    if skill_type:
        query = query.join(
            TechnicianSkill,
            TechnicianSkill.employee_id == Employee.id
        ).filter(
            TechnicianSkill.skill_type == skill_type,
            TechnicianSkill.is_active == True
        )

    if search:
        query = query.filter(Employee.name.ilike(f"%{search}%"))

    total = query.count()
    technicians = query.offset(offset).limit(limit).all()

    result = []
    for tech in technicians:
        # Get assigned orders count for today
        today = date.today()
        today_orders = db.query(func.count(ServiceOrder.id)).filter(
            ServiceOrder.assigned_technician_id == tech.id,
            ServiceOrder.scheduled_date == today,
            ServiceOrder.status.notin_([ServiceOrderStatus.COMPLETED, ServiceOrderStatus.CANCELLED])
        ).scalar() or 0

        # Get skills
        skills = db.query(TechnicianSkill).filter(
            TechnicianSkill.employee_id == tech.id,
            TechnicianSkill.is_active == True
        ).all()

        # Get team memberships
        memberships = db.query(FieldTeamMember).filter(
            FieldTeamMember.employee_id == tech.id,
            FieldTeamMember.is_active == True
        ).all()

        result.append({
            "id": tech.id,
            "employee_name": tech.name,
            "company_email": tech.email,
            "cell_number": tech.phone,
            "department": tech.department,
            "designation": tech.designation,
            "today_orders": today_orders,
            "teams": [
                {"team_id": m.team_id, "role": m.role}
                for m in memberships
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
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": result,
    }


@router.get("/technicians/{technician_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_technician(technician_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get detailed technician information."""
    tech = db.query(Employee).filter(Employee.id == technician_id).first()
    if not tech:
        raise HTTPException(404, "Technician not found")

    # Get today's schedule
    today = date.today()
    today_orders = db.query(ServiceOrder).filter(
        ServiceOrder.assigned_technician_id == technician_id,
        ServiceOrder.scheduled_date == today
    ).order_by(ServiceOrder.scheduled_start_time).all()

    # Get skills
    skills = db.query(TechnicianSkill).filter(
        TechnicianSkill.employee_id == technician_id,
        TechnicianSkill.is_active == True
    ).all()

    # Get team memberships
    memberships = db.query(FieldTeamMember).filter(
        FieldTeamMember.employee_id == technician_id,
        FieldTeamMember.is_active == True
    ).all()

    # Performance stats (last 30 days)
    thirty_days_ago = date.today() - timedelta(days=30)
    completed_orders = db.query(func.count(ServiceOrder.id)).filter(
        ServiceOrder.assigned_technician_id == technician_id,
        ServiceOrder.status == ServiceOrderStatus.COMPLETED,
        ServiceOrder.actual_end_time >= thirty_days_ago
    ).scalar() or 0

    avg_rating = db.query(func.avg(ServiceOrder.customer_rating)).filter(
        ServiceOrder.assigned_technician_id == technician_id,
        ServiceOrder.customer_rating.isnot(None),
        ServiceOrder.actual_end_time >= thirty_days_ago
    ).scalar() or 0

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
            for m in memberships
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
            "completed_30_days": completed_orders,
            "avg_rating": round(float(avg_rating), 1),
        },
        "today_schedule": [
            {
                "id": o.id,
                "order_number": o.order_number,
                "status": o.status.value,
                "scheduled_start_time": o.scheduled_start_time.isoformat() if o.scheduled_start_time else None,
                "customer_name": o.customer.name if o.customer else None,
                "service_address": o.service_address,
                "title": o.title,
            }
            for o in today_orders
        ],
    }


# =============================================================================
# TECHNICIAN SKILLS
# =============================================================================

@router.post("/technicians/{technician_id}/skills", dependencies=[Depends(Require("field-service:admin"))])
async def add_skill(
    technician_id: int,
    payload: TechnicianSkillCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add a skill to a technician."""
    employee = db.query(Employee).filter(Employee.id == technician_id).first()
    if not employee:
        raise HTTPException(404, "Technician not found")

    skill = TechnicianSkill(
        employee_id=technician_id,
        skill_type=payload.skill_type,
        proficiency_level=payload.proficiency_level,
        certification=payload.certification,
        certification_number=payload.certification_number,
        certification_date=payload.certification_date,
        certification_expiry=payload.certification_expiry,
    )

    db.add(skill)
    db.commit()

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
) -> Dict[str, Any]:
    """Remove a skill from a technician."""
    skill = db.query(TechnicianSkill).filter(
        TechnicianSkill.id == skill_id,
        TechnicianSkill.employee_id == technician_id
    ).first()

    if not skill:
        raise HTTPException(404, "Skill not found")

    skill.is_active = False
    db.commit()

    return {"message": "Skill removed"}


# =============================================================================
# SERVICE ZONES
# =============================================================================

@router.get("/zones", dependencies=[Depends(Require("explorer:read"))])
async def list_zones(
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List service zones."""
    query = db.query(ServiceZone)

    if is_active is not None:
        query = query.filter(ServiceZone.is_active == is_active)

    zones = query.order_by(ServiceZone.name).all()

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
) -> Dict[str, Any]:
    """Create a service zone."""
    # Check for duplicate code
    existing = db.query(ServiceZone).filter(ServiceZone.code == payload.code).first()
    if existing:
        raise HTTPException(400, f"Zone with code '{payload.code}' already exists")

    zone = ServiceZone(
        name=payload.name,
        code=payload.code,
        description=payload.description,
        coverage_areas=payload.coverage_areas,
        center_latitude=payload.center_latitude,
        center_longitude=payload.center_longitude,
        default_team_id=payload.default_team_id,
    )

    db.add(zone)
    db.commit()

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
) -> Dict[str, Any]:
    """Update a service zone."""
    zone = db.query(ServiceZone).filter(ServiceZone.id == zone_id).first()
    if not zone:
        raise HTTPException(404, "Zone not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(zone, key, value)

    db.commit()

    return {
        "id": zone.id,
        "name": zone.name,
        "code": zone.code,
        "is_active": zone.is_active,
    }


# Import missing
from datetime import timedelta
from sqlalchemy import and_
