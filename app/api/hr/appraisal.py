"""
Appraisal/Performance Management Router

Endpoints for AppraisalTemplate, Appraisal.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any, Optional, List
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.auth import User
from app.services.audit_logger import AuditLogger, serialize_for_audit
from app.models.hr_appraisal import (
    AppraisalTemplate,
    AppraisalTemplateGoal,
    Appraisal,
    AppraisalStatus,
    AppraisalGoal,
)
from .helpers import decimal_or_default, csv_response, validate_date_order, status_counts

router = APIRouter()


# =============================================================================
# APPRAISAL TEMPLATE
# =============================================================================

class AppraisalTemplateGoalPayload(BaseModel):
    kra: Optional[str] = None
    per_weightage: Optional[Decimal] = Decimal("0")
    idx: Optional[int] = 0


class AppraisalTemplateCreate(BaseModel):
    template_name: str
    description: Optional[str] = None
    goals: Optional[List[AppraisalTemplateGoalPayload]] = Field(default=None)


class AppraisalTemplateUpdate(BaseModel):
    template_name: Optional[str] = None
    description: Optional[str] = None
    goals: Optional[List[AppraisalTemplateGoalPayload]] = Field(default=None)


@router.get("/appraisal-templates", dependencies=[Depends(Require("hr:read"))])
async def list_appraisal_templates(
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List appraisal templates with filtering."""
    query = db.query(AppraisalTemplate)

    if search:
        query = query.filter(AppraisalTemplate.template_name.ilike(f"%{search}%"))

    total = query.count()
    templates = query.order_by(AppraisalTemplate.template_name).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": t.id,
                "erpnext_id": t.erpnext_id,
                "template_name": t.template_name,
                "goal_count": len(t.goals),
            }
            for t in templates
        ],
    }


@router.get("/appraisal-templates/{template_id}", dependencies=[Depends(Require("hr:read"))])
async def get_appraisal_template(
    template_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get appraisal template detail with goals."""
    t = db.query(AppraisalTemplate).filter(AppraisalTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Appraisal template not found")

    goals = [
        {
            "id": g.id,
            "kra": g.kra,
            "per_weightage": float(g.per_weightage) if g.per_weightage else 0,
            "idx": g.idx,
        }
        for g in sorted(t.goals, key=lambda x: x.idx)
    ]

    return {
        "id": t.id,
        "erpnext_id": t.erpnext_id,
        "template_name": t.template_name,
        "description": t.description,
        "goals": goals,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


@router.post("/appraisal-templates", dependencies=[Depends(Require("hr:write"))])
async def create_appraisal_template(
    payload: AppraisalTemplateCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new appraisal template with goals."""
    template = AppraisalTemplate(
        template_name=payload.template_name,
        description=payload.description,
    )
    db.add(template)
    db.flush()

    if payload.goals:
        for idx, g in enumerate(payload.goals):
            goal = AppraisalTemplateGoal(
                appraisal_template_id=template.id,
                kra=g.kra,
                per_weightage=decimal_or_default(g.per_weightage),
                idx=g.idx if g.idx is not None else idx,
            )
            db.add(goal)

    db.commit()
    return await get_appraisal_template(template.id, db)


@router.patch("/appraisal-templates/{template_id}", dependencies=[Depends(Require("hr:write"))])
async def update_appraisal_template(
    template_id: int,
    payload: AppraisalTemplateUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update an appraisal template and optionally replace goals."""
    template = db.query(AppraisalTemplate).filter(AppraisalTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Appraisal template not found")

    update_data = payload.model_dump(exclude_unset=True)
    goals_data = update_data.pop("goals", None)

    for field, value in update_data.items():
        if value is not None:
            setattr(template, field, value)

    if goals_data is not None:
        db.query(AppraisalTemplateGoal).filter(
            AppraisalTemplateGoal.appraisal_template_id == template.id
        ).delete(synchronize_session=False)
        for idx, g in enumerate(goals_data):
            goal = AppraisalTemplateGoal(
                appraisal_template_id=template.id,
                kra=g.get("kra"),
                per_weightage=decimal_or_default(g.get("per_weightage")),
                idx=g.get("idx") if g.get("idx") is not None else idx,
            )
            db.add(goal)

    db.commit()
    return await get_appraisal_template(template.id, db)


@router.delete("/appraisal-templates/{template_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_appraisal_template(
    template_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete an appraisal template."""
    template = db.query(AppraisalTemplate).filter(AppraisalTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Appraisal template not found")

    db.delete(template)
    db.commit()
    return {"message": "Appraisal template deleted", "id": template_id}


# =============================================================================
# APPRAISAL
# =============================================================================

class AppraisalGoalPayload(BaseModel):
    kra: Optional[str] = None
    per_weightage: Optional[Decimal] = Decimal("0")
    goal: Optional[str] = None
    score_earned: Optional[Decimal] = Decimal("0")
    self_score: Optional[Decimal] = Decimal("0")
    idx: Optional[int] = 0


class AppraisalCreate(BaseModel):
    employee: str
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    appraisal_template: Optional[str] = None
    appraisal_template_id: Optional[int] = None
    start_date: date
    end_date: date
    status: Optional[AppraisalStatus] = AppraisalStatus.DRAFT
    company: Optional[str] = None
    total_score: Optional[Decimal] = Decimal("0")
    self_score: Optional[Decimal] = Decimal("0")
    final_score: Optional[Decimal] = Decimal("0")
    feedback: Optional[str] = None
    reflections: Optional[str] = None
    goals: Optional[List[AppraisalGoalPayload]] = Field(default=None)


class AppraisalUpdate(BaseModel):
    employee: Optional[str] = None
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    appraisal_template: Optional[str] = None
    appraisal_template_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[AppraisalStatus] = None
    company: Optional[str] = None
    total_score: Optional[Decimal] = None
    self_score: Optional[Decimal] = None
    final_score: Optional[Decimal] = None
    feedback: Optional[str] = None
    reflections: Optional[str] = None
    goals: Optional[List[AppraisalGoalPayload]] = Field(default=None)


class AppraisalBulkAction(BaseModel):
    appraisal_ids: List[int]


def _require_appraisal_status(appraisal: Appraisal, allowed: List[AppraisalStatus]):
    if appraisal.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition from {appraisal.status.value if appraisal.status else None}",
        )


def _load_appraisal(db: Session, appraisal_id: int) -> Appraisal:
    appraisal = db.query(Appraisal).filter(Appraisal.id == appraisal_id).first()
    if not appraisal:
        raise HTTPException(status_code=404, detail="Appraisal not found")
    return appraisal


@router.get("/appraisals", dependencies=[Depends(Require("hr:read"))])
async def list_appraisals(
    employee_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    company: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List appraisals with filtering."""
    query = db.query(Appraisal)

    if employee_id:
        query = query.filter(Appraisal.employee_id == employee_id)
    if status:
        try:
            status_enum = AppraisalStatus(status)
            query = query.filter(Appraisal.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    if from_date:
        query = query.filter(Appraisal.start_date >= from_date)
    if to_date:
        query = query.filter(Appraisal.end_date <= to_date)
    if company:
        query = query.filter(Appraisal.company.ilike(f"%{company}%"))

    total = query.count()
    appraisals = query.order_by(Appraisal.start_date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": a.id,
                "erpnext_id": a.erpnext_id,
                "employee": a.employee,
                "employee_id": a.employee_id,
                "employee_name": a.employee_name,
                "start_date": a.start_date.isoformat() if a.start_date else None,
                "end_date": a.end_date.isoformat() if a.end_date else None,
                "status": a.status.value if a.status else None,
                "total_score": float(a.total_score) if a.total_score else 0,
                "final_score": float(a.final_score) if a.final_score else 0,
                "company": a.company,
            }
            for a in appraisals
        ],
    }


@router.get("/appraisals/export", dependencies=[Depends(Require("hr:read"))])
async def export_appraisals(
    employee_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Export appraisals to CSV."""
    query = db.query(Appraisal)
    if employee_id:
        query = query.filter(Appraisal.employee_id == employee_id)
    if status:
        try:
            status_enum = AppraisalStatus(status)
            query = query.filter(Appraisal.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    if from_date:
        query = query.filter(Appraisal.start_date >= from_date)
    if to_date:
        query = query.filter(Appraisal.end_date <= to_date)
    if company:
        query = query.filter(Appraisal.company.ilike(f"%{company}%"))

    rows = [["id", "employee", "employee_name", "start_date", "end_date", "status", "total_score", "final_score", "company"]]
    for a in query.order_by(Appraisal.start_date.desc()).all():
        rows.append([
            a.id,
            a.employee,
            a.employee_name or "",
            a.start_date.isoformat() if a.start_date else "",
            a.end_date.isoformat() if a.end_date else "",
            a.status.value if a.status else "",
            float(a.total_score or 0),
            float(a.final_score or 0),
            a.company or "",
        ])
    return csv_response(rows, "appraisals.csv")


@router.get("/appraisals/summary", dependencies=[Depends(Require("hr:read"))])
async def appraisals_summary(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get appraisals summary by status."""
    query = db.query(Appraisal.status, func.count(Appraisal.id), func.avg(Appraisal.final_score))

    if from_date:
        query = query.filter(Appraisal.start_date >= from_date)
    if to_date:
        query = query.filter(Appraisal.end_date <= to_date)
    if company:
        query = query.filter(Appraisal.company.ilike(f"%{company}%"))

    results = query.group_by(Appraisal.status).all()

    summary = {}
    for row in results:
        status_val = row[0].value if row[0] else None
        summary[status_val] = {
            "count": int(row[1] or 0),
            "avg_final_score": float(row[2]) if row[2] else 0,
        }

    return {"by_status": summary}


@router.get("/appraisals/{appraisal_id}", dependencies=[Depends(Require("hr:read"))])
async def get_appraisal(
    appraisal_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get appraisal detail with goals."""
    a = db.query(Appraisal).filter(Appraisal.id == appraisal_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Appraisal not found")

    goals = [
        {
            "id": g.id,
            "kra": g.kra,
            "per_weightage": float(g.per_weightage) if g.per_weightage else 0,
            "goal": g.goal,
            "score_earned": float(g.score_earned) if g.score_earned else 0,
            "self_score": float(g.self_score) if g.self_score else 0,
            "idx": g.idx,
        }
        for g in sorted(a.goals, key=lambda x: x.idx)
    ]

    return {
        "id": a.id,
        "erpnext_id": a.erpnext_id,
        "employee": a.employee,
        "employee_id": a.employee_id,
        "employee_name": a.employee_name,
        "appraisal_template": a.appraisal_template,
        "appraisal_template_id": a.appraisal_template_id,
        "start_date": a.start_date.isoformat() if a.start_date else None,
        "end_date": a.end_date.isoformat() if a.end_date else None,
        "status": a.status.value if a.status else None,
        "company": a.company,
        "total_score": float(a.total_score) if a.total_score else 0,
        "self_score": float(a.self_score) if a.self_score else 0,
        "final_score": float(a.final_score) if a.final_score else 0,
        "feedback": a.feedback,
        "reflections": a.reflections,
        "goals": goals,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


@router.post("/appraisals", dependencies=[Depends(Require("hr:write"))])
async def create_appraisal(
    payload: AppraisalCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new appraisal with goals."""
    validate_date_order(payload.start_date, payload.end_date)

    appraisal = Appraisal(
        employee=payload.employee,
        employee_id=payload.employee_id,
        employee_name=payload.employee_name,
        appraisal_template=payload.appraisal_template,
        appraisal_template_id=payload.appraisal_template_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status=payload.status or AppraisalStatus.DRAFT,
        company=payload.company,
        total_score=decimal_or_default(payload.total_score),
        self_score=decimal_or_default(payload.self_score),
        final_score=decimal_or_default(payload.final_score),
        feedback=payload.feedback,
        reflections=payload.reflections,
    )
    db.add(appraisal)
    db.flush()

    if payload.goals:
        for idx, g in enumerate(payload.goals):
            goal = AppraisalGoal(
                appraisal_id=appraisal.id,
                kra=g.kra,
                per_weightage=decimal_or_default(g.per_weightage),
                goal=g.goal,
                score_earned=decimal_or_default(g.score_earned),
                self_score=decimal_or_default(g.self_score),
                idx=g.idx if g.idx is not None else idx,
            )
            db.add(goal)

    db.commit()
    return await get_appraisal(appraisal.id, db)


@router.patch("/appraisals/{appraisal_id}", dependencies=[Depends(Require("hr:write"))])
async def update_appraisal(
    appraisal_id: int,
    payload: AppraisalUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update an appraisal and optionally replace goals."""
    appraisal = db.query(Appraisal).filter(Appraisal.id == appraisal_id).first()
    if not appraisal:
        raise HTTPException(status_code=404, detail="Appraisal not found")

    update_data = payload.model_dump(exclude_unset=True)
    goals_data = update_data.pop("goals", None)

    decimal_fields = ["total_score", "self_score", "final_score"]
    for field, value in update_data.items():
        if value is not None:
            if field in decimal_fields:
                setattr(appraisal, field, decimal_or_default(value))
            else:
                setattr(appraisal, field, value)

    validate_date_order(appraisal.start_date, appraisal.end_date)

    if goals_data is not None:
        db.query(AppraisalGoal).filter(
            AppraisalGoal.appraisal_id == appraisal.id
        ).delete(synchronize_session=False)
        for idx, g in enumerate(goals_data):
            goal = AppraisalGoal(
                appraisal_id=appraisal.id,
                kra=g.get("kra"),
                per_weightage=decimal_or_default(g.get("per_weightage")),
                goal=g.get("goal"),
                score_earned=decimal_or_default(g.get("score_earned")),
                self_score=decimal_or_default(g.get("self_score")),
                idx=g.get("idx") if g.get("idx") is not None else idx,
            )
            db.add(goal)

    db.commit()
    return await get_appraisal(appraisal.id, db)


@router.delete("/appraisals/{appraisal_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_appraisal(
    appraisal_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete an appraisal."""
    appraisal = db.query(Appraisal).filter(Appraisal.id == appraisal_id).first()
    if not appraisal:
        raise HTTPException(status_code=404, detail="Appraisal not found")

    db.delete(appraisal)
    db.commit()
    return {"message": "Appraisal deleted", "id": appraisal_id}


@router.post("/appraisals/{appraisal_id}/submit", dependencies=[Depends(Require("hr:write"))])
async def submit_appraisal(
    appraisal_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Submit an appraisal for review."""
    appraisal = _load_appraisal(db, appraisal_id)
    _require_appraisal_status(appraisal, [AppraisalStatus.DRAFT])
    appraisal.status = AppraisalStatus.SUBMITTED
    db.commit()
    return await get_appraisal(appraisal_id, db)


@router.post("/appraisals/{appraisal_id}/complete", dependencies=[Depends(Require("hr:write"))])
async def complete_appraisal(
    appraisal_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Mark an appraisal as completed."""
    appraisal = _load_appraisal(db, appraisal_id)
    _require_appraisal_status(appraisal, [AppraisalStatus.SUBMITTED])
    appraisal.status = AppraisalStatus.COMPLETED
    db.commit()
    return await get_appraisal(appraisal_id, db)


@router.post("/appraisals/{appraisal_id}/cancel", dependencies=[Depends(Require("hr:write"))])
async def cancel_appraisal(
    appraisal_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Cancel an appraisal."""
    appraisal = _load_appraisal(db, appraisal_id)
    _require_appraisal_status(appraisal, [AppraisalStatus.DRAFT, AppraisalStatus.SUBMITTED])
    appraisal.status = AppraisalStatus.CANCELLED
    db.commit()
    return await get_appraisal(appraisal_id, db)


@router.post("/appraisals/bulk/submit", dependencies=[Depends(Require("hr:write"))])
async def bulk_submit_appraisals(
    payload: AppraisalBulkAction,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Bulk submit appraisals."""
    updated = 0
    for app_id in payload.appraisal_ids:
        appraisal = db.query(Appraisal).filter(Appraisal.id == app_id).first()
        if appraisal and appraisal.status == AppraisalStatus.DRAFT:
            appraisal.status = AppraisalStatus.SUBMITTED
            updated += 1
    db.commit()
    return {"updated": updated, "requested": len(payload.appraisal_ids)}


@router.post("/appraisals/bulk/complete", dependencies=[Depends(Require("hr:write"))])
async def bulk_complete_appraisals(
    payload: AppraisalBulkAction,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Bulk complete appraisals."""
    updated = 0
    for app_id in payload.appraisal_ids:
        appraisal = db.query(Appraisal).filter(Appraisal.id == app_id).first()
        if appraisal and appraisal.status == AppraisalStatus.SUBMITTED:
            appraisal.status = AppraisalStatus.COMPLETED
            updated += 1
    db.commit()
    return {"updated": updated, "requested": len(payload.appraisal_ids)}
