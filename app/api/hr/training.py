"""
Training Management Router

Endpoints for TrainingProgram, TrainingEvent, TrainingResult.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any, Optional, List
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Require, get_current_principal
from app.models.hr_training import (
    TrainingEventStatus,
    TrainingResult,
    TrainingResultStatus,
)
from app.services.hr.training import TrainingService
from app.services.hr.training_types import (
    EventEmployeeData,
    TrainingEventCreateData,
    TrainingEventFilters,
    TrainingEventUpdateData,
    TrainingProgramCreateData,
    TrainingProgramFilters,
    TrainingProgramUpdateData,
    TrainingResultCreateData,
    TrainingResultFilters,
    TrainingResultUpdateData,
)
from app.services.hr.errors import (
    TrainingEventNotFoundError,
    TrainingProgramNotFoundError,
    TrainingResultNotFoundError,
    ValidationError,
)
from app.services.types import PaginationParams
from .helpers import decimal_or_default, csv_response, status_counts

router = APIRouter()


# =============================================================================
# TRAINING PROGRAM
# =============================================================================

class TrainingProgramCreate(BaseModel):
    training_program_name: str
    description: Optional[str] = None
    trainer_name: Optional[str] = None
    trainer_email: Optional[str] = None
    supplier: Optional[str] = None


class TrainingProgramUpdate(BaseModel):
    training_program_name: Optional[str] = None
    description: Optional[str] = None
    trainer_name: Optional[str] = None
    trainer_email: Optional[str] = None
    supplier: Optional[str] = None


@router.get("/training-programs", dependencies=[Depends(Require("hr:read"))])
async def list_training_programs(
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List training programs with filtering."""
    service = TrainingService(db)
    result = service.list_programs(
        TrainingProgramFilters(search=search),
        pagination=PaginationParams(offset=offset, limit=limit),
    )
    programs = result.items
    total = result.total

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": p.id,
                "erpnext_id": p.erpnext_id,
                "training_program_name": p.training_program_name,
                "trainer_name": p.trainer_name,
                "supplier": p.supplier,
            }
            for p in programs
        ],
    }


@router.get("/training-programs/{program_id}", dependencies=[Depends(Require("hr:read"))])
async def get_training_program(
    program_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get training program detail."""
    service = TrainingService(db)
    try:
        p = service.get_program(program_id)
    except TrainingProgramNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {
        "id": p.id,
        "erpnext_id": p.erpnext_id,
        "training_program_name": p.training_program_name,
        "description": p.description,
        "trainer_name": p.trainer_name,
        "trainer_email": p.trainer_email,
        "supplier": p.supplier,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.post("/training-programs", dependencies=[Depends(Require("hr:write"))])
async def create_training_program(
    payload: TrainingProgramCreate,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new training program."""
    service = TrainingService(db, principal)
    try:
        program = service.create_program(
            TrainingProgramCreateData(
                training_program_name=payload.training_program_name,
                description=payload.description,
                trainer_name=payload.trainer_name,
                trainer_email=payload.trainer_email,
                supplier=payload.supplier,
            )
        )
        db.commit()
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_training_program(program.id, db)


@router.patch("/training-programs/{program_id}", dependencies=[Depends(Require("hr:write"))])
async def update_training_program(
    program_id: int,
    payload: TrainingProgramUpdate,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a training program."""
    service = TrainingService(db, principal)
    try:
        service.update_program(
            program_id,
            TrainingProgramUpdateData(
                training_program_name=payload.training_program_name,
                description=payload.description,
                trainer_name=payload.trainer_name,
                trainer_email=payload.trainer_email,
                supplier=payload.supplier,
            ),
        )
        db.commit()
    except TrainingProgramNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_training_program(program_id, db)


@router.delete("/training-programs/{program_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_training_program(
    program_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete a training program."""
    service = TrainingService(db, principal)
    try:
        service.delete_program(program_id)
        db.commit()
    except TrainingProgramNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))

    return {"message": "Training program deleted", "id": program_id}


# =============================================================================
# TRAINING EVENT
# =============================================================================

class TrainingEventEmployeePayload(BaseModel):
    employee: str
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    department: Optional[str] = None
    status: Optional[str] = None
    attendance: Optional[str] = None
    idx: Optional[int] = 0


class TrainingEventCreate(BaseModel):
    event_name: str
    training_program: Optional[str] = None
    training_program_id: Optional[int] = None
    type: Optional[str] = None
    level: Optional[str] = None
    status: Optional[TrainingEventStatus] = TrainingEventStatus.SCHEDULED
    company: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    trainer_name: Optional[str] = None
    trainer_email: Optional[str] = None
    course: Optional[str] = None
    introduction: Optional[str] = None
    employees: Optional[List[TrainingEventEmployeePayload]] = Field(default=None)


class TrainingEventUpdate(BaseModel):
    event_name: Optional[str] = None
    training_program: Optional[str] = None
    training_program_id: Optional[int] = None
    type: Optional[str] = None
    level: Optional[str] = None
    status: Optional[TrainingEventStatus] = None
    company: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    trainer_name: Optional[str] = None
    trainer_email: Optional[str] = None
    course: Optional[str] = None
    introduction: Optional[str] = None
    employees: Optional[List[TrainingEventEmployeePayload]] = Field(default=None)


@router.get("/training-events", dependencies=[Depends(Require("hr:read"))])
async def list_training_events(
    status: Optional[str] = None,
    training_program_id: Optional[int] = None,
    company: Optional[str] = None,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List training events with filtering."""
    status_enum = None
    if status:
        try:
            status_enum = TrainingEventStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    service = TrainingService(db)
    result = service.list_events(
        TrainingEventFilters(
            training_program_id=training_program_id,
            status=status_enum,
            company=company,
            from_date=from_time,
            to_date=to_time,
            search=search,
        ),
        pagination=PaginationParams(offset=offset, limit=limit),
    )
    events = result.items
    total = result.total

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": e.id,
                "erpnext_id": e.erpnext_id,
                "event_name": e.event_name,
                "training_program": e.training_program,
                "type": e.type,
                "level": e.level,
                "status": e.status.value if e.status else None,
                "start_time": e.start_time.isoformat() if e.start_time else None,
                "end_time": e.end_time.isoformat() if e.end_time else None,
                "location": e.location,
                "company": e.company,
                "employee_count": len(e.employees),
            }
            for e in events
        ],
    }


@router.get("/training-events/summary", dependencies=[Depends(Require("hr:read"))])
async def training_events_summary(
    company: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get training events summary by status."""
    service = TrainingService(db)
    metrics = service.get_metrics(company)
    return {
        "status_counts": {
            "scheduled": metrics.scheduled_events,
            "completed": metrics.completed_events,
            "cancelled": metrics.cancelled_events,
        }
    }


@router.get("/training-events/{event_id}", dependencies=[Depends(Require("hr:read"))])
async def get_training_event(
    event_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get training event detail with employees."""
    service = TrainingService(db)
    try:
        e = service.get_event(event_id)
    except TrainingEventNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    employees = [
        {
            "id": emp.id,
            "employee": emp.employee,
            "employee_id": emp.employee_id,
            "employee_name": emp.employee_name,
            "department": emp.department,
            "status": emp.status,
            "attendance": emp.attendance,
            "idx": emp.idx,
        }
        for emp in sorted(e.employees, key=lambda x: x.idx)
    ]

    return {
        "id": e.id,
        "erpnext_id": e.erpnext_id,
        "event_name": e.event_name,
        "training_program": e.training_program,
        "training_program_id": e.training_program_id,
        "type": e.type,
        "level": e.level,
        "status": e.status.value if e.status else None,
        "company": e.company,
        "start_time": e.start_time.isoformat() if e.start_time else None,
        "end_time": e.end_time.isoformat() if e.end_time else None,
        "location": e.location,
        "trainer_name": e.trainer_name,
        "trainer_email": e.trainer_email,
        "course": e.course,
        "introduction": e.introduction,
        "employees": employees,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


@router.post("/training-events", dependencies=[Depends(Require("hr:write"))])
async def create_training_event(
    payload: TrainingEventCreate,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new training event with employees."""
    employees = []
    if payload.employees:
        for idx, emp in enumerate(payload.employees):
            if emp.employee_id is None:
                raise HTTPException(status_code=400, detail="employee_id is required for event employees")
            employees.append(
                EventEmployeeData(
                    employee_id=emp.employee_id,
                    employee=emp.employee,
                    employee_name=emp.employee_name,
                    department=emp.department,
                    status=emp.status or "Invited",
                    idx=emp.idx if emp.idx is not None else idx,
                )
            )

    service = TrainingService(db, principal)
    try:
        event = service.create_event(
            TrainingEventCreateData(
                event_name=payload.event_name,
                training_program=payload.training_program,
                training_program_id=payload.training_program_id,
                type=payload.type,
                level=payload.level,
                company=payload.company,
                start_time=payload.start_time,
                end_time=payload.end_time,
                location=payload.location,
                trainer_name=payload.trainer_name,
                trainer_email=payload.trainer_email,
                course=payload.course,
                introduction=payload.introduction,
                employees=employees,
            )
        )
        if payload.status and payload.status != TrainingEventStatus.SCHEDULED:
            if payload.status == TrainingEventStatus.COMPLETED:
                service.complete_event(event.id)
            elif payload.status == TrainingEventStatus.CANCELLED:
                service.cancel_event(event.id)
            else:
                raise HTTPException(status_code=400, detail="Unsupported status transition on create")
        db.commit()
    except (TrainingProgramNotFoundError, ValidationError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_training_event(event.id, db)


@router.patch("/training-events/{event_id}", dependencies=[Depends(Require("hr:write"))])
async def update_training_event(
    event_id: int,
    payload: TrainingEventUpdate,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a training event and optionally replace employees."""
    employees = None
    if payload.employees is not None:
        employees = []
        for idx, emp in enumerate(payload.employees):
            if emp.employee_id is None:
                raise HTTPException(status_code=400, detail="employee_id is required for event employees")
            employees.append(
                EventEmployeeData(
                    employee_id=emp.employee_id,
                    employee=emp.employee,
                    employee_name=emp.employee_name,
                    department=emp.department,
                    status=emp.status or "Invited",
                    idx=emp.idx if emp.idx is not None else idx,
                )
            )

    service = TrainingService(db, principal)
    try:
        service.update_event(
            event_id,
            TrainingEventUpdateData(
                event_name=payload.event_name,
                training_program=payload.training_program,
                training_program_id=payload.training_program_id,
                type=payload.type,
                level=payload.level,
                status=payload.status,
                start_time=payload.start_time,
                end_time=payload.end_time,
                location=payload.location,
                trainer_name=payload.trainer_name,
                trainer_email=payload.trainer_email,
                course=payload.course,
                introduction=payload.introduction,
                employees=employees,
            ),
        )
        db.commit()
    except TrainingEventNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except (TrainingProgramNotFoundError, ValidationError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_training_event(event_id, db)


@router.delete("/training-events/{event_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_training_event(
    event_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete a training event."""
    service = TrainingService(db, principal)
    try:
        service.delete_event(event_id)
        db.commit()
    except TrainingEventNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))

    return {"message": "Training event deleted", "id": event_id}


@router.post("/training-events/{event_id}/complete", dependencies=[Depends(Require("hr:write"))])
async def complete_training_event(
    event_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Mark a training event as completed."""
    service = TrainingService(db, principal)
    try:
        service.complete_event(event_id)
        db.commit()
    except TrainingEventNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_training_event(event_id, db)


@router.post("/training-events/{event_id}/cancel", dependencies=[Depends(Require("hr:write"))])
async def cancel_training_event(
    event_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Cancel a training event."""
    service = TrainingService(db, principal)
    try:
        service.cancel_event(event_id)
        db.commit()
    except TrainingEventNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_training_event(event_id, db)


# =============================================================================
# TRAINING RESULT
# =============================================================================

class TrainingResultCreate(BaseModel):
    training_event: str
    training_event_id: Optional[int] = None
    employee: str
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    hours: Optional[Decimal] = Decimal("0")
    grade: Optional[str] = None
    result: Optional[TrainingResultStatus] = TrainingResultStatus.PENDING
    comments: Optional[str] = None


class TrainingResultUpdate(BaseModel):
    training_event: Optional[str] = None
    training_event_id: Optional[int] = None
    employee: Optional[str] = None
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    hours: Optional[Decimal] = None
    grade: Optional[str] = None
    result: Optional[TrainingResultStatus] = None
    comments: Optional[str] = None


@router.get("/training-results", dependencies=[Depends(Require("hr:read"))])
async def list_training_results(
    training_event_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    result: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List training results with filtering."""
    result_enum = None
    if result:
        try:
            result_enum = TrainingResultStatus(result)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid result: {result}")

    service = TrainingService(db)
    result_page = service.list_results(
        TrainingResultFilters(
            training_event_id=training_event_id,
            employee_id=employee_id,
            result=result_enum,
        ),
        pagination=PaginationParams(offset=offset, limit=limit),
    )
    results = result_page.items
    total = result_page.total

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": r.id,
                "erpnext_id": r.erpnext_id,
                "training_event": r.training_event,
                "training_event_id": r.training_event_id,
                "employee": r.employee,
                "employee_id": r.employee_id,
                "employee_name": r.employee_name,
                "hours": float(r.hours) if r.hours else 0,
                "grade": r.grade,
                "result": r.result.value if r.result else None,
            }
            for r in results
        ],
    }


@router.get("/training-results/summary", dependencies=[Depends(Require("hr:read"))])
async def training_results_summary(
    training_event_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get training results summary by result status."""
    query = db.query(TrainingResult.result, func.count(TrainingResult.id))

    if training_event_id:
        query = query.filter(TrainingResult.training_event_id == training_event_id)

    results = query.group_by(TrainingResult.result).all()

    return {"result_counts": status_counts(results)}


@router.get("/training-results/{result_id}", dependencies=[Depends(Require("hr:read"))])
async def get_training_result(
    result_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get training result detail."""
    service = TrainingService(db)
    try:
        r = service.get_result(result_id)
    except TrainingResultNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {
        "id": r.id,
        "erpnext_id": r.erpnext_id,
        "training_event": r.training_event,
        "training_event_id": r.training_event_id,
        "employee": r.employee,
        "employee_id": r.employee_id,
        "employee_name": r.employee_name,
        "hours": float(r.hours) if r.hours else 0,
        "grade": r.grade,
        "result": r.result.value if r.result else None,
        "comments": r.comments,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.post("/training-results", dependencies=[Depends(Require("hr:write"))])
async def create_training_result(
    payload: TrainingResultCreate,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new training result."""
    if payload.training_event_id is None:
        raise HTTPException(status_code=400, detail="training_event_id is required")
    if payload.employee_id is None:
        raise HTTPException(status_code=400, detail="employee_id is required")

    service = TrainingService(db, principal)
    try:
        result = service.create_result(
            TrainingResultCreateData(
                training_event=payload.training_event,
                training_event_id=payload.training_event_id,
                employee=payload.employee,
                employee_id=payload.employee_id,
                employee_name=payload.employee_name,
                hours=decimal_or_default(payload.hours),
                grade=payload.grade,
                result=payload.result or TrainingResultStatus.PENDING,
                comments=payload.comments,
            )
        )
        db.commit()
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_training_result(result.id, db)


@router.patch("/training-results/{result_id}", dependencies=[Depends(Require("hr:write"))])
async def update_training_result(
    result_id: int,
    payload: TrainingResultUpdate,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a training result."""
    service = TrainingService(db, principal)
    try:
        service.update_result(
            result_id,
            TrainingResultUpdateData(
                hours=decimal_or_default(payload.hours) if payload.hours is not None else None,
                grade=payload.grade,
                result=payload.result,
                comments=payload.comments,
            ),
        )
        db.commit()
    except TrainingResultNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await get_training_result(result_id, db)


@router.delete("/training-results/{result_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_training_result(
    result_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete a training result."""
    service = TrainingService(db, principal)
    try:
        service.delete_result(result_id)
        db.commit()
    except TrainingResultNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))

    return {"message": "Training result deleted", "id": result_id}


@router.post("/training-results/{result_id}/pass", dependencies=[Depends(Require("hr:write"))])
async def pass_training_result(
    result_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Mark a training result as passed."""
    service = TrainingService(db, principal)
    try:
        service.update_result(
            result_id,
            TrainingResultUpdateData(result=TrainingResultStatus.PASSED),
        )
        db.commit()
    except TrainingResultNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))

    return await get_training_result(result_id, db)


@router.post("/training-results/{result_id}/fail", dependencies=[Depends(Require("hr:write"))])
async def fail_training_result(
    result_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
) -> Dict[str, Any]:
    """Mark a training result as failed."""
    service = TrainingService(db, principal)
    try:
        service.update_result(
            result_id,
            TrainingResultUpdateData(result=TrainingResultStatus.FAILED),
        )
        db.commit()
    except TrainingResultNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))

    return await get_training_result(result_id, db)
