"""
Scorecards API - Employee scorecard instances and results
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel
from enum import Enum

from app.database import get_db
from app.auth import Require
from app.models.performance import (
    EmployeeScorecardInstance,
    ScorecardInstanceStatus,
    EvaluationPeriod,
    ScorecardTemplate,
    KPIResult,
    KRAResult,
    KPIDefinition,
    KRADefinition,
)
from app.models.employee import Employee
from app.services.performance_notification_service import PerformanceNotificationService

router = APIRouter(prefix="/scorecards", tags=["performance-scorecards"])


# ============= SCHEMAS =============
class ScorecardStatusEnum(str, Enum):
    pending = "pending"
    computing = "computing"
    computed = "computed"
    in_review = "in_review"
    approved = "approved"
    disputed = "disputed"
    finalized = "finalized"


class KPIResultResponse(BaseModel):
    id: int
    kpi_id: int
    kpi_code: str
    kpi_name: str
    kra_id: Optional[int]
    raw_value: Optional[float]
    target_value: Optional[float]
    computed_score: Optional[float]
    final_score: Optional[float]
    weightage_in_kra: Optional[float]
    weighted_score: Optional[float]
    evidence_links: Optional[List[str]]

    class Config:
        from_attributes = True


class KRAResultResponse(BaseModel):
    id: int
    kra_id: int
    kra_code: str
    kra_name: str
    computed_score: Optional[float]
    final_score: Optional[float]
    weightage_in_scorecard: Optional[float]
    weighted_score: Optional[float]
    kpi_results: List[KPIResultResponse] = []

    class Config:
        from_attributes = True


class ScorecardResponse(BaseModel):
    id: int
    employee_id: int
    employee_name: Optional[str]
    employee_code: Optional[str]
    department: Optional[str]
    designation: Optional[str]
    evaluation_period_id: int
    period_code: str
    period_name: str
    template_id: int
    template_name: str
    status: str
    total_weighted_score: Optional[float]
    final_rating: Optional[str]
    reviewed_by_id: Optional[int]
    reviewed_at: Optional[datetime]
    finalized_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScorecardDetailResponse(ScorecardResponse):
    kra_results: List[KRAResultResponse] = []


class ScorecardListResponse(BaseModel):
    items: List[ScorecardResponse]
    total: int


class GenerateScorecardRequest(BaseModel):
    employee_ids: Optional[List[int]] = None  # None = all employees
    template_id: Optional[int] = None  # None = use default or auto-match


# ============= HELPERS =============
def build_scorecard_response(
    scorecard: EmployeeScorecardInstance,
    db: Session,
    include_results: bool = False
) -> ScorecardResponse | ScorecardDetailResponse:
    # Get related entities
    employee = db.query(Employee).filter(Employee.id == scorecard.employee_id).first()
    period = db.query(EvaluationPeriod).filter(EvaluationPeriod.id == scorecard.evaluation_period_id).first()
    template = db.query(ScorecardTemplate).filter(ScorecardTemplate.id == scorecard.template_id).first()

    employee_name = employee.name if employee else None
    employee_code = employee.erpnext_id if employee else None
    department = employee.department if employee else None
    designation = employee.designation if employee else None
    period_code = period.code if period else ""
    period_name = period.name if period else ""
    template_name = template.name if template else ""
    status = scorecard.status.value if isinstance(scorecard.status, ScorecardInstanceStatus) else scorecard.status
    total_weighted_score = float(scorecard.total_weighted_score) if scorecard.total_weighted_score else None

    if not include_results:
        return ScorecardResponse(
            id=scorecard.id,
            employee_id=scorecard.employee_id,
            employee_name=employee_name,
            employee_code=employee_code,
            department=department,
            designation=designation,
            evaluation_period_id=scorecard.evaluation_period_id,
            period_code=period_code,
            period_name=period_name,
            template_id=scorecard.template_id,
            template_name=template_name,
            status=status,
            total_weighted_score=total_weighted_score,
            final_rating=scorecard.final_rating,
            reviewed_by_id=scorecard.reviewed_by_id,
            reviewed_at=scorecard.reviewed_at,
            finalized_at=scorecard.finalized_at,
            created_at=scorecard.created_at,
            updated_at=scorecard.updated_at,
        )

    # Get KRA results with nested KPI results
    kra_results_data = []
    kra_results = db.query(KRAResult).filter(KRAResult.scorecard_instance_id == scorecard.id).all()

    for kra_result in kra_results:
        kra = db.query(KRADefinition).filter(KRADefinition.id == kra_result.kra_id).first()

        # Get KPI results for this KRA
        kpi_results = db.query(KPIResult).filter(
            KPIResult.scorecard_instance_id == scorecard.id,
            KPIResult.kra_id == kra_result.kra_id
        ).all()

        kpi_results_data = []
        for kpi_result in kpi_results:
            kpi = db.query(KPIDefinition).filter(KPIDefinition.id == kpi_result.kpi_id).first()
            kpi_results_data.append(KPIResultResponse(
                id=kpi_result.id,
                kpi_id=kpi_result.kpi_id,
                kpi_code=kpi.code if kpi else "",
                kpi_name=kpi.name if kpi else "",
                kra_id=kpi_result.kra_id,
                raw_value=float(kpi_result.raw_value) if kpi_result.raw_value else None,
                target_value=float(kpi_result.target_value) if kpi_result.target_value else None,
                computed_score=float(kpi_result.computed_score) if kpi_result.computed_score else None,
                final_score=float(kpi_result.final_score) if kpi_result.final_score else None,
                weightage_in_kra=float(kpi_result.weightage_in_kra) if kpi_result.weightage_in_kra else None,
                weighted_score=float(kpi_result.weighted_score) if kpi_result.weighted_score else None,
                evidence_links=kpi_result.evidence_links,
            ))

        kra_results_data.append(KRAResultResponse(
            id=kra_result.id,
            kra_id=kra_result.kra_id,
            kra_code=kra.code if kra else "",
            kra_name=kra.name if kra else "",
            computed_score=float(kra_result.computed_score) if kra_result.computed_score else None,
            final_score=float(kra_result.final_score) if kra_result.final_score else None,
            weightage_in_scorecard=float(kra_result.weightage_in_scorecard) if kra_result.weightage_in_scorecard else None,
            weighted_score=float(kra_result.weighted_score) if kra_result.weighted_score else None,
            kpi_results=kpi_results_data,
        ))

    return ScorecardDetailResponse(
        id=scorecard.id,
        employee_id=scorecard.employee_id,
        employee_name=employee_name,
        employee_code=employee_code,
        department=department,
        designation=designation,
        evaluation_period_id=scorecard.evaluation_period_id,
        period_code=period_code,
        period_name=period_name,
        template_id=scorecard.template_id,
        template_name=template_name,
        status=status,
        total_weighted_score=total_weighted_score,
        final_rating=scorecard.final_rating,
        reviewed_by_id=scorecard.reviewed_by_id,
        reviewed_at=scorecard.reviewed_at,
        finalized_at=scorecard.finalized_at,
        created_at=scorecard.created_at,
        updated_at=scorecard.updated_at,
        kra_results=kra_results_data,
    )


# ============= ENDPOINTS =============
@router.get("", response_model=ScorecardListResponse, dependencies=[Depends(Require("performance:read"))])
async def list_scorecards(
    period_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    department: Optional[str] = None,
    status: Optional[ScorecardStatusEnum] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List employee scorecards with filtering."""
    query = db.query(EmployeeScorecardInstance)

    if period_id:
        query = query.filter(EmployeeScorecardInstance.evaluation_period_id == period_id)

    if employee_id:
        query = query.filter(EmployeeScorecardInstance.employee_id == employee_id)

    if status:
        query = query.filter(EmployeeScorecardInstance.status == status.value)

    if department:
        # Join with Employee to filter by department
        query = query.join(Employee, EmployeeScorecardInstance.employee_id == Employee.id).filter(
            Employee.department == department
        )

    total = query.count()
    scorecards = query.order_by(EmployeeScorecardInstance.created_at.desc()).offset(offset).limit(limit).all()

    items = [build_scorecard_response(sc, db) for sc in scorecards]

    return ScorecardListResponse(items=items, total=total)


@router.get("/my", dependencies=[Depends(Require("performance:self"))])
async def get_my_scorecards(
    period_id: Optional[int] = None,
    # current_user: User = Depends(get_current_user),  # TODO: Add auth
    db: Session = Depends(get_db),
):
    """Get current user's scorecards."""
    # TODO: Get employee_id from current_user
    # For now, return empty list
    return {"items": [], "total": 0, "message": "Auth not implemented yet"}


@router.get("/team", dependencies=[Depends(Require("performance:team"))])
async def get_team_scorecards(
    period_id: Optional[int] = None,
    # current_user: User = Depends(get_current_user),  # TODO: Add auth
    db: Session = Depends(get_db),
):
    """Get scorecards for manager's team."""
    # TODO: Get team members based on manager relationships
    return {"items": [], "total": 0, "message": "Auth not implemented yet"}


@router.get("/{scorecard_id}", response_model=ScorecardDetailResponse, dependencies=[Depends(Require("performance:read"))])
async def get_scorecard(scorecard_id: int, db: Session = Depends(get_db)):
    """Get a single scorecard with full results."""
    scorecard = db.query(EmployeeScorecardInstance).filter(
        EmployeeScorecardInstance.id == scorecard_id
    ).first()

    if not scorecard:
        raise HTTPException(status_code=404, detail="Scorecard not found")

    return build_scorecard_response(scorecard, db, include_results=True)


@router.post("/generate", dependencies=[Depends(Require("performance:admin"))])
async def generate_scorecards(
    period_id: int,
    payload: GenerateScorecardRequest,
    db: Session = Depends(get_db),
):
    """Generate scorecards for employees in a period."""
    period = db.query(EvaluationPeriod).filter(EvaluationPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")

    if period.status.value not in ['draft', 'active']:
        raise HTTPException(status_code=400, detail=f"Cannot generate scorecards for period in {period.status.value} status")

    # Get template
    template = None
    if payload.template_id:
        template = db.query(ScorecardTemplate).filter(ScorecardTemplate.id == payload.template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
    else:
        # Use default template
        template = db.query(ScorecardTemplate).filter(
            ScorecardTemplate.is_default == True,
            ScorecardTemplate.is_active == True
        ).first()

    if not template:
        raise HTTPException(status_code=400, detail="No template specified and no default template found")

    # Get employees
    if payload.employee_ids:
        employees = db.query(Employee).filter(Employee.id.in_(payload.employee_ids)).all()
    else:
        # Get all active employees (with status filter if available)
        employees = db.query(Employee).filter(Employee.status == 'Active').all()

    created_count = 0
    skipped_count = 0
    errors = []

    created_scorecards = []
    for emp in employees:
        # Check if scorecard already exists
        existing = db.query(EmployeeScorecardInstance).filter(
            EmployeeScorecardInstance.employee_id == emp.id,
            EmployeeScorecardInstance.evaluation_period_id == period_id
        ).first()

        if existing:
            skipped_count += 1
            continue

        try:
            scorecard = EmployeeScorecardInstance(
                employee_id=emp.id,
                evaluation_period_id=period_id,
                template_id=template.id,
                status=ScorecardInstanceStatus.PENDING,
            )
            db.add(scorecard)
            created_scorecards.append(scorecard)
            created_count += 1
        except Exception as e:
            errors.append({"employee_id": emp.id, "error": str(e)})

    db.commit()

    # Send notifications to employees about their generated scorecards
    notification_service = PerformanceNotificationService(db)
    for scorecard in created_scorecards:
        db.refresh(scorecard)
        notification_service.notify_scorecard_generated(scorecard, period)

    return {
        "success": True,
        "created": created_count,
        "skipped": skipped_count,
        "errors": errors,
        "message": f"Generated {created_count} scorecards, skipped {skipped_count} existing"
    }


@router.post("/{scorecard_id}/compute", dependencies=[Depends(Require("performance:admin"))])
async def compute_scorecard(scorecard_id: int, db: Session = Depends(get_db)):
    """Trigger computation for a single scorecard."""
    scorecard = db.query(EmployeeScorecardInstance).filter(
        EmployeeScorecardInstance.id == scorecard_id
    ).first()

    if not scorecard:
        raise HTTPException(status_code=404, detail="Scorecard not found")

    if scorecard.status not in [ScorecardInstanceStatus.PENDING, ScorecardInstanceStatus.COMPUTED]:
        if isinstance(scorecard.status, str) and scorecard.status not in ['pending', 'computed']:
            raise HTTPException(status_code=400, detail=f"Cannot compute scorecard in {scorecard.status} status")

    # Mark as computing
    scorecard.status = ScorecardInstanceStatus.COMPUTING
    db.commit()

    # TODO: Queue Celery task
    # from app.tasks.performance_tasks import compute_scorecard
    # compute_scorecard.delay(scorecard_id)

    return {
        "success": True,
        "message": "Scorecard computation queued",
        "scorecard_id": scorecard_id,
        "status": "computing"
    }


@router.post("/{scorecard_id}/submit", dependencies=[Depends(Require("performance:write"))])
async def submit_scorecard(scorecard_id: int, db: Session = Depends(get_db)):
    """Submit scorecard for manager review."""
    scorecard = db.query(EmployeeScorecardInstance).filter(
        EmployeeScorecardInstance.id == scorecard_id
    ).first()

    if not scorecard:
        raise HTTPException(status_code=404, detail="Scorecard not found")

    valid_statuses = ['computed', ScorecardInstanceStatus.COMPUTED]
    if scorecard.status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Can only submit computed scorecards")

    scorecard.status = ScorecardInstanceStatus.IN_REVIEW
    db.commit()

    # Notify manager that a review is requested
    period = db.query(EvaluationPeriod).filter(EvaluationPeriod.id == scorecard.evaluation_period_id).first()
    employee = db.query(Employee).filter(Employee.id == scorecard.employee_id).first()
    if period and employee and employee.reports_to:
        # Find manager by name
        manager = db.query(Employee).filter(Employee.name == employee.reports_to).first()
        notification_service = PerformanceNotificationService(db)
        manager_user_id = notification_service._get_user_id_for_employee(manager)
        if manager_user_id:
            notification_service.notify_review_requested(scorecard, period, manager_user_id)

    return {"success": True, "message": "Scorecard submitted for review", "status": "in_review"}


@router.delete("/{scorecard_id}", dependencies=[Depends(Require("performance:admin"))])
async def delete_scorecard(scorecard_id: int, db: Session = Depends(get_db)):
    """Delete a pending scorecard."""
    scorecard = db.query(EmployeeScorecardInstance).filter(
        EmployeeScorecardInstance.id == scorecard_id
    ).first()

    if not scorecard:
        raise HTTPException(status_code=404, detail="Scorecard not found")

    if scorecard.status not in [ScorecardInstanceStatus.PENDING, 'pending']:
        raise HTTPException(status_code=400, detail="Can only delete pending scorecards")

    db.delete(scorecard)
    db.commit()

    return {"success": True, "message": "Scorecard deleted"}
