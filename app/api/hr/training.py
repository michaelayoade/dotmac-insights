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
from app.models.auth import User
from app.services.audit_logger import AuditLogger, serialize_for_audit
from app.models.hr_training import (
    TrainingProgram,
    TrainingEvent,
    TrainingEventStatus,
    TrainingEventEmployee,
    TrainingResult,
    TrainingResultStatus,
)
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
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List training programs with filtering."""
    query = db.query(TrainingProgram)

    if search:
        query = query.filter(TrainingProgram.training_program_name.ilike(f"%{search}%"))

    total = query.count()
    programs = query.order_by(TrainingProgram.training_program_name).offset(offset).limit(limit).all()

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
    p = db.query(TrainingProgram).filter(TrainingProgram.id == program_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Training program not found")

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
) -> Dict[str, Any]:
    """Create a new training program."""
    program = TrainingProgram(
        training_program_name=payload.training_program_name,
        description=payload.description,
        trainer_name=payload.trainer_name,
        trainer_email=payload.trainer_email,
        supplier=payload.supplier,
    )
    db.add(program)
    db.commit()
    return await get_training_program(program.id, db)


@router.patch("/training-programs/{program_id}", dependencies=[Depends(Require("hr:write"))])
async def update_training_program(
    program_id: int,
    payload: TrainingProgramUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a training program."""
    program = db.query(TrainingProgram).filter(TrainingProgram.id == program_id).first()
    if not program:
        raise HTTPException(status_code=404, detail="Training program not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(program, field, value)

    db.commit()
    return await get_training_program(program.id, db)


@router.delete("/training-programs/{program_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_training_program(
    program_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a training program."""
    program = db.query(TrainingProgram).filter(TrainingProgram.id == program_id).first()
    if not program:
        raise HTTPException(status_code=404, detail="Training program not found")

    db.delete(program)
    db.commit()
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


def _require_event_status(event: TrainingEvent, allowed: List[TrainingEventStatus]):
    if event.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition from {event.status.value if event.status else None}",
        )


def _load_event(db: Session, event_id: int) -> TrainingEvent:
    event = db.query(TrainingEvent).filter(TrainingEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Training event not found")
    return event


@router.get("/training-events", dependencies=[Depends(Require("hr:read"))])
async def list_training_events(
    status: Optional[str] = None,
    training_program_id: Optional[int] = None,
    company: Optional[str] = None,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List training events with filtering."""
    query = db.query(TrainingEvent)

    if status:
        try:
            status_enum = TrainingEventStatus(status)
            query = query.filter(TrainingEvent.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    if training_program_id:
        query = query.filter(TrainingEvent.training_program_id == training_program_id)
    if company:
        query = query.filter(TrainingEvent.company.ilike(f"%{company}%"))
    if from_time:
        query = query.filter(TrainingEvent.start_time >= from_time)
    if to_time:
        query = query.filter(TrainingEvent.end_time <= to_time)
    if search:
        query = query.filter(TrainingEvent.event_name.ilike(f"%{search}%"))

    total = query.count()
    events = query.order_by(TrainingEvent.start_time.desc()).offset(offset).limit(limit).all()

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
    query = db.query(TrainingEvent.status, func.count(TrainingEvent.id))

    if company:
        query = query.filter(TrainingEvent.company.ilike(f"%{company}%"))

    results = query.group_by(TrainingEvent.status).all()

    return {"status_counts": status_counts(results)}


@router.get("/training-events/{event_id}", dependencies=[Depends(Require("hr:read"))])
async def get_training_event(
    event_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get training event detail with employees."""
    e = db.query(TrainingEvent).filter(TrainingEvent.id == event_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Training event not found")

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
) -> Dict[str, Any]:
    """Create a new training event with employees."""
    event = TrainingEvent(
        event_name=payload.event_name,
        training_program=payload.training_program,
        training_program_id=payload.training_program_id,
        type=payload.type,
        level=payload.level,
        status=payload.status or TrainingEventStatus.SCHEDULED,
        company=payload.company,
        start_time=payload.start_time,
        end_time=payload.end_time,
        location=payload.location,
        trainer_name=payload.trainer_name,
        trainer_email=payload.trainer_email,
        course=payload.course,
        introduction=payload.introduction,
    )
    db.add(event)
    db.flush()

    if payload.employees:
        for idx, emp in enumerate(payload.employees):
            employee = TrainingEventEmployee(
                training_event_id=event.id,
                employee=emp.employee,
                employee_id=emp.employee_id,
                employee_name=emp.employee_name,
                department=emp.department,
                status=emp.status,
                attendance=emp.attendance,
                idx=emp.idx if emp.idx is not None else idx,
            )
            db.add(employee)

    db.commit()
    return await get_training_event(event.id, db)


@router.patch("/training-events/{event_id}", dependencies=[Depends(Require("hr:write"))])
async def update_training_event(
    event_id: int,
    payload: TrainingEventUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a training event and optionally replace employees."""
    event = db.query(TrainingEvent).filter(TrainingEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Training event not found")

    update_data = payload.model_dump(exclude_unset=True)
    employees_data = update_data.pop("employees", None)

    for field, value in update_data.items():
        if value is not None:
            setattr(event, field, value)

    if employees_data is not None:
        db.query(TrainingEventEmployee).filter(
            TrainingEventEmployee.training_event_id == event.id
        ).delete(synchronize_session=False)
        for idx, emp in enumerate(employees_data):
            employee = TrainingEventEmployee(
                training_event_id=event.id,
                employee=emp.get("employee"),
                employee_id=emp.get("employee_id"),
                employee_name=emp.get("employee_name"),
                department=emp.get("department"),
                status=emp.get("status"),
                attendance=emp.get("attendance"),
                idx=emp.get("idx") if emp.get("idx") is not None else idx,
            )
            db.add(employee)

    db.commit()
    return await get_training_event(event.id, db)


@router.delete("/training-events/{event_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_training_event(
    event_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a training event."""
    event = db.query(TrainingEvent).filter(TrainingEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Training event not found")

    db.delete(event)
    db.commit()
    return {"message": "Training event deleted", "id": event_id}


@router.post("/training-events/{event_id}/complete", dependencies=[Depends(Require("hr:write"))])
async def complete_training_event(
    event_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Mark a training event as completed."""
    event = _load_event(db, event_id)
    _require_event_status(event, [TrainingEventStatus.SCHEDULED])
    event.status = TrainingEventStatus.COMPLETED
    db.commit()
    return await get_training_event(event_id, db)


@router.post("/training-events/{event_id}/cancel", dependencies=[Depends(Require("hr:write"))])
async def cancel_training_event(
    event_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Cancel a training event."""
    event = _load_event(db, event_id)
    _require_event_status(event, [TrainingEventStatus.SCHEDULED])
    event.status = TrainingEventStatus.CANCELLED
    db.commit()
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
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List training results with filtering."""
    query = db.query(TrainingResult)

    if training_event_id:
        query = query.filter(TrainingResult.training_event_id == training_event_id)
    if employee_id:
        query = query.filter(TrainingResult.employee_id == employee_id)
    if result:
        try:
            result_enum = TrainingResultStatus(result)
            query = query.filter(TrainingResult.result == result_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid result: {result}")

    total = query.count()
    results = query.order_by(TrainingResult.created_at.desc()).offset(offset).limit(limit).all()

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
    r = db.query(TrainingResult).filter(TrainingResult.id == result_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Training result not found")

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
) -> Dict[str, Any]:
    """Create a new training result."""
    result = TrainingResult(
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
    db.add(result)
    db.commit()
    return await get_training_result(result.id, db)


@router.patch("/training-results/{result_id}", dependencies=[Depends(Require("hr:write"))])
async def update_training_result(
    result_id: int,
    payload: TrainingResultUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a training result."""
    result = db.query(TrainingResult).filter(TrainingResult.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Training result not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            if field == "hours":
                setattr(result, field, decimal_or_default(value))
            else:
                setattr(result, field, value)

    db.commit()
    return await get_training_result(result.id, db)


@router.delete("/training-results/{result_id}", dependencies=[Depends(Require("hr:write"))])
async def delete_training_result(
    result_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a training result."""
    result = db.query(TrainingResult).filter(TrainingResult.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Training result not found")

    db.delete(result)
    db.commit()
    return {"message": "Training result deleted", "id": result_id}


@router.post("/training-results/{result_id}/pass", dependencies=[Depends(Require("hr:write"))])
async def pass_training_result(
    result_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Mark a training result as passed."""
    result = db.query(TrainingResult).filter(TrainingResult.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Training result not found")

    result.result = TrainingResultStatus.PASSED
    db.commit()
    return await get_training_result(result_id, db)


@router.post("/training-results/{result_id}/fail", dependencies=[Depends(Require("hr:write"))])
async def fail_training_result(
    result_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Mark a training result as failed."""
    result = db.query(TrainingResult).filter(TrainingResult.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Training result not found")

    result.result = TrainingResultStatus.FAILED
    db.commit()
    return await get_training_result(result_id, db)
