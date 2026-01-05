"""
Nurture Sequences API - Drip campaign management.

Manage automated nurture sequences for lead engagement.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from app.database import get_db
from app.auth import Principal, get_current_principal
from app.utils.company_context import get_company_id
from app.services.crm.nurture import NurtureSequenceService
from app.services.crm.nurture_types import (
    NurtureSequenceFilters,
    NurtureSequenceCreateData,
    NurtureSequenceUpdateData,
    NurtureStepCreateData,
    NurtureStepUpdateData,
    EnrollmentCreateData,
)

router = APIRouter(prefix="/nurture", tags=["crm-nurture"])


def get_nurture_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> NurtureSequenceService:
    """Create a NurtureSequenceService instance."""
    company_id = get_company_id(principal)
    return NurtureSequenceService(db, company_id, principal.user_id)


# ============= SCHEMAS =============
class SequenceCreate(BaseModel):
    """Create a nurture sequence."""

    name: str
    description: Optional[str] = None
    target_segment_id: Optional[int] = None
    entry_trigger: Optional[str] = None
    entry_conditions: dict = Field(default_factory=dict)
    allow_reentry: bool = False
    exit_on_reply: bool = True
    exit_on_conversion: bool = True
    respect_contact_preferences: bool = True
    timezone_aware: bool = True
    send_window_start: Optional[int] = None
    send_window_end: Optional[int] = None
    exclude_weekends: bool = False
    campaign_id: Optional[int] = None


class SequenceUpdate(BaseModel):
    """Update a nurture sequence."""

    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    target_segment_id: Optional[int] = None
    entry_trigger: Optional[str] = None
    entry_conditions: Optional[dict] = None
    allow_reentry: Optional[bool] = None
    exit_on_reply: Optional[bool] = None
    exit_on_conversion: Optional[bool] = None
    respect_contact_preferences: Optional[bool] = None
    timezone_aware: Optional[bool] = None
    send_window_start: Optional[int] = None
    send_window_end: Optional[int] = None
    exclude_weekends: Optional[bool] = None


class StepCreate(BaseModel):
    """Create a nurture step."""

    step_type: str  # email, sms, task, wait, condition, webhook
    step_order: int
    name: Optional[str] = None
    delay_days: int = 0
    delay_hours: int = 0
    delay_minutes: int = 0
    subject: Optional[str] = None
    content: Optional[str] = None
    template_id: Optional[int] = None
    condition_field: Optional[str] = None
    condition_operator: Optional[str] = None
    condition_value: Optional[str] = None
    true_step_id: Optional[int] = None
    false_step_id: Optional[int] = None
    task_type: Optional[str] = None
    task_assignee_id: Optional[int] = None
    task_priority: str = "medium"
    webhook_url: Optional[str] = None
    webhook_method: str = "POST"
    webhook_headers: dict = Field(default_factory=dict)
    webhook_payload: Optional[str] = None
    is_ab_test: bool = False
    ab_variant: Optional[str] = None
    ab_weight: int = 100


class StepUpdate(BaseModel):
    """Update a nurture step."""

    name: Optional[str] = None
    step_order: Optional[int] = None
    delay_days: Optional[int] = None
    delay_hours: Optional[int] = None
    delay_minutes: Optional[int] = None
    subject: Optional[str] = None
    content: Optional[str] = None
    template_id: Optional[int] = None
    is_active: Optional[bool] = None


class EnrollmentRequest(BaseModel):
    """Enroll a contact in a sequence."""

    party_id: int
    source: str = "manual"
    source_id: Optional[str] = None


class BulkEnrollmentRequest(BaseModel):
    """Bulk enroll contacts."""

    party_ids: List[int]
    source: str = "bulk"


# ============= SEQUENCE ENDPOINTS =============
@router.get("")
async def list_sequences(
    search: Optional[str] = None,
    status: Optional[str] = None,
    campaign_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    service: NurtureSequenceService = Depends(get_nurture_service),
):
    """List nurture sequences."""
    filters = NurtureSequenceFilters(
        search=search,
        status=status,
        campaign_id=campaign_id,
    )
    sequences, total = service.list_sequences(filters, skip, limit)
    return {
        "items": [_serialize_sequence(s) for s in sequences],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/summary")
async def get_summary(
    service: NurtureSequenceService = Depends(get_nurture_service),
):
    """Get nurture sequences summary."""
    summary = service.get_summary()
    return {
        "total_sequences": summary.total_sequences,
        "active_sequences": summary.active_sequences,
        "draft_sequences": summary.draft_sequences,
        "paused_sequences": summary.paused_sequences,
        "total_enrolled": summary.total_enrolled,
        "total_completed": summary.total_completed,
        "avg_conversion_rate": summary.avg_conversion_rate,
    }


@router.post("")
async def create_sequence(
    data: SequenceCreate,
    service: NurtureSequenceService = Depends(get_nurture_service),
    db: Session = Depends(get_db),
):
    """Create a nurture sequence."""
    create_data = NurtureSequenceCreateData(
        name=data.name,
        description=data.description,
        target_segment_id=data.target_segment_id,
        entry_trigger=data.entry_trigger,
        entry_conditions=data.entry_conditions,
        allow_reentry=data.allow_reentry,
        exit_on_reply=data.exit_on_reply,
        exit_on_conversion=data.exit_on_conversion,
        respect_contact_preferences=data.respect_contact_preferences,
        timezone_aware=data.timezone_aware,
        send_window_start=data.send_window_start,
        send_window_end=data.send_window_end,
        exclude_weekends=data.exclude_weekends,
        campaign_id=data.campaign_id,
    )
    sequence = service.create_sequence(create_data)
    db.commit()
    return _serialize_sequence(sequence)


@router.get("/{sequence_id}")
async def get_sequence(
    sequence_id: int,
    service: NurtureSequenceService = Depends(get_nurture_service),
):
    """Get a nurture sequence by ID."""
    sequence = service.get_sequence(sequence_id)
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")
    return _serialize_sequence(sequence, include_steps=True)


@router.patch("/{sequence_id}")
async def update_sequence(
    sequence_id: int,
    data: SequenceUpdate,
    service: NurtureSequenceService = Depends(get_nurture_service),
    db: Session = Depends(get_db),
):
    """Update a nurture sequence."""
    update_data = NurtureSequenceUpdateData(
        name=data.name,
        description=data.description,
        status=data.status,
        target_segment_id=data.target_segment_id,
        entry_trigger=data.entry_trigger,
        entry_conditions=data.entry_conditions,
        allow_reentry=data.allow_reentry,
        exit_on_reply=data.exit_on_reply,
        exit_on_conversion=data.exit_on_conversion,
        respect_contact_preferences=data.respect_contact_preferences,
        timezone_aware=data.timezone_aware,
        send_window_start=data.send_window_start,
        send_window_end=data.send_window_end,
        exclude_weekends=data.exclude_weekends,
    )
    sequence = service.update_sequence(sequence_id, update_data)
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")
    db.commit()
    return _serialize_sequence(sequence)


@router.delete("/{sequence_id}")
async def delete_sequence(
    sequence_id: int,
    service: NurtureSequenceService = Depends(get_nurture_service),
    db: Session = Depends(get_db),
):
    """Delete a nurture sequence."""
    if not service.delete_sequence(sequence_id):
        raise HTTPException(status_code=404, detail="Sequence not found")
    db.commit()
    return {"success": True}


@router.post("/{sequence_id}/activate")
async def activate_sequence(
    sequence_id: int,
    service: NurtureSequenceService = Depends(get_nurture_service),
    db: Session = Depends(get_db),
):
    """Activate a nurture sequence."""
    sequence = service.activate_sequence(sequence_id)
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")
    db.commit()
    return _serialize_sequence(sequence)


@router.post("/{sequence_id}/pause")
async def pause_sequence(
    sequence_id: int,
    service: NurtureSequenceService = Depends(get_nurture_service),
    db: Session = Depends(get_db),
):
    """Pause a nurture sequence."""
    sequence = service.pause_sequence(sequence_id)
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")
    db.commit()
    return _serialize_sequence(sequence)


@router.get("/{sequence_id}/metrics")
async def get_sequence_metrics(
    sequence_id: int,
    service: NurtureSequenceService = Depends(get_nurture_service),
):
    """Get metrics for a nurture sequence."""
    metrics = service.get_sequence_metrics(sequence_id)
    if not metrics:
        raise HTTPException(status_code=404, detail="Sequence not found")
    return {
        "sequence_id": metrics.sequence_id,
        "sequence_name": metrics.sequence_name,
        "status": metrics.status,
        "total_steps": metrics.total_steps,
        "total_enrolled": metrics.total_enrolled,
        "active_enrolled": metrics.active_enrolled,
        "completed": metrics.completed,
        "converted": metrics.converted,
        "unsubscribed": metrics.unsubscribed,
        "conversion_rate": metrics.conversion_rate,
        "completion_rate": metrics.completion_rate,
        "avg_time_to_complete_days": metrics.avg_time_to_complete_days,
        "step_metrics": metrics.step_metrics,
    }


# ============= STEP ENDPOINTS =============
@router.post("/{sequence_id}/steps")
async def create_step(
    sequence_id: int,
    data: StepCreate,
    service: NurtureSequenceService = Depends(get_nurture_service),
    db: Session = Depends(get_db),
):
    """Add a step to a nurture sequence."""
    step_data = NurtureStepCreateData(
        step_type=data.step_type,
        step_order=data.step_order,
        name=data.name,
        delay_days=data.delay_days,
        delay_hours=data.delay_hours,
        delay_minutes=data.delay_minutes,
        subject=data.subject,
        content=data.content,
        template_id=data.template_id,
        condition_field=data.condition_field,
        condition_operator=data.condition_operator,
        condition_value=data.condition_value,
        true_step_id=data.true_step_id,
        false_step_id=data.false_step_id,
        task_type=data.task_type,
        task_assignee_id=data.task_assignee_id,
        task_priority=data.task_priority,
        webhook_url=data.webhook_url,
        webhook_method=data.webhook_method,
        webhook_headers=data.webhook_headers,
        webhook_payload=data.webhook_payload,
        is_ab_test=data.is_ab_test,
        ab_variant=data.ab_variant,
        ab_weight=data.ab_weight,
    )
    step = service.create_step(sequence_id, step_data)
    if not step:
        raise HTTPException(status_code=404, detail="Sequence not found")
    db.commit()
    return _serialize_step(step)


@router.patch("/{sequence_id}/steps/{step_id}")
async def update_step(
    sequence_id: int,
    step_id: int,
    data: StepUpdate,
    service: NurtureSequenceService = Depends(get_nurture_service),
    db: Session = Depends(get_db),
):
    """Update a nurture step."""
    update_data = NurtureStepUpdateData(
        name=data.name,
        step_order=data.step_order,
        delay_days=data.delay_days,
        delay_hours=data.delay_hours,
        delay_minutes=data.delay_minutes,
        subject=data.subject,
        content=data.content,
        template_id=data.template_id,
        is_active=data.is_active,
    )
    step = service.update_step(step_id, update_data)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    db.commit()
    return _serialize_step(step)


@router.delete("/{sequence_id}/steps/{step_id}")
async def delete_step(
    sequence_id: int,
    step_id: int,
    service: NurtureSequenceService = Depends(get_nurture_service),
    db: Session = Depends(get_db),
):
    """Delete a nurture step."""
    if not service.delete_step(step_id):
        raise HTTPException(status_code=404, detail="Step not found")
    db.commit()
    return {"success": True}


# ============= ENROLLMENT ENDPOINTS =============
@router.post("/{sequence_id}/enroll")
async def enroll_contact(
    sequence_id: int,
    data: EnrollmentRequest,
    service: NurtureSequenceService = Depends(get_nurture_service),
    db: Session = Depends(get_db),
):
    """Enroll a contact in a sequence."""
    enroll_data = EnrollmentCreateData(
        party_id=data.party_id,
        source=data.source,
        source_id=data.source_id,
    )
    enrollment = service.enroll_contact(sequence_id, enroll_data)
    if not enrollment:
        raise HTTPException(status_code=400, detail="Could not enroll contact")
    db.commit()
    return _serialize_enrollment(enrollment)


@router.post("/{sequence_id}/enroll/bulk")
async def bulk_enroll(
    sequence_id: int,
    data: BulkEnrollmentRequest,
    service: NurtureSequenceService = Depends(get_nurture_service),
    db: Session = Depends(get_db),
):
    """Bulk enroll contacts in a sequence."""
    result = service.bulk_enroll(sequence_id, data.party_ids, data.source)
    db.commit()
    return {
        "enrolled": result.enrolled_count,
        "skipped": result.skipped_count,
        "errors": result.errors,
    }


@router.post("/{sequence_id}/enrollments/{enrollment_id}/unenroll")
async def unenroll_contact(
    sequence_id: int,
    enrollment_id: int,
    service: NurtureSequenceService = Depends(get_nurture_service),
    db: Session = Depends(get_db),
):
    """Unenroll a contact from a sequence."""
    if not service.unenroll_contact(enrollment_id):
        raise HTTPException(status_code=404, detail="Enrollment not found")
    db.commit()
    return {"success": True}


@router.get("/{sequence_id}/enrollments")
async def list_enrollments(
    sequence_id: int,
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    service: NurtureSequenceService = Depends(get_nurture_service),
):
    """List enrollments for a sequence."""
    enrollments, total = service.list_enrollments(sequence_id, status, skip, limit)
    return {
        "items": [_serialize_enrollment(e) for e in enrollments],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{sequence_id}/enrollments/{enrollment_id}/progress")
async def get_enrollment_progress(
    sequence_id: int,
    enrollment_id: int,
    service: NurtureSequenceService = Depends(get_nurture_service),
):
    """Get progress for an enrollment."""
    progress = service.get_enrollment_progress(enrollment_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    return {
        "enrollment_id": progress.enrollment_id,
        "party_id": progress.party_id,
        "party_name": progress.party_name,
        "sequence_id": progress.sequence_id,
        "sequence_name": progress.sequence_name,
        "status": progress.status,
        "current_step": progress.current_step,
        "total_steps": progress.total_steps,
        "progress_percent": progress.progress_percent,
        "next_step_at": progress.next_step_at.isoformat() if progress.next_step_at else None,
        "emails_sent": progress.emails_sent,
        "emails_opened": progress.emails_opened,
        "open_rate": progress.open_rate,
        "enrolled_at": progress.enrolled_at.isoformat(),
        "completed_at": progress.completed_at.isoformat() if progress.completed_at else None,
    }


# ============= SERIALIZERS =============
def _serialize_sequence(sequence, include_steps: bool = False) -> dict:
    """Serialize a nurture sequence."""
    result = {
        "id": sequence.id,
        "name": sequence.name,
        "description": sequence.description,
        "status": sequence.status,
        "target_segment_id": sequence.target_segment_id,
        "entry_trigger": sequence.entry_trigger,
        "entry_conditions": sequence.entry_conditions,
        "allow_reentry": sequence.allow_reentry,
        "exit_on_reply": sequence.exit_on_reply,
        "exit_on_conversion": sequence.exit_on_conversion,
        "respect_contact_preferences": sequence.respect_contact_preferences,
        "timezone_aware": sequence.timezone_aware,
        "send_window_start": sequence.send_window_start,
        "send_window_end": sequence.send_window_end,
        "exclude_weekends": sequence.exclude_weekends,
        "campaign_id": sequence.campaign_id,
        "created_at": sequence.created_at.isoformat() if sequence.created_at else None,
        "updated_at": sequence.updated_at.isoformat() if sequence.updated_at else None,
    }
    if include_steps and hasattr(sequence, "steps"):
        result["steps"] = [_serialize_step(s) for s in sequence.steps]
    return result


def _serialize_step(step) -> dict:
    """Serialize a nurture step."""
    return {
        "id": step.id,
        "sequence_id": step.sequence_id,
        "step_type": step.step_type,
        "step_order": step.step_order,
        "name": step.name,
        "delay_days": step.delay_days,
        "delay_hours": step.delay_hours,
        "delay_minutes": step.delay_minutes,
        "subject": step.subject,
        "content": step.content,
        "template_id": step.template_id,
        "is_active": step.is_active,
        "created_at": step.created_at.isoformat() if step.created_at else None,
    }


def _serialize_enrollment(enrollment) -> dict:
    """Serialize an enrollment."""
    return {
        "id": enrollment.id,
        "sequence_id": enrollment.sequence_id,
        "party_id": enrollment.party_id,
        "status": enrollment.status,
        "current_step_id": enrollment.current_step_id,
        "source": enrollment.source,
        "enrolled_at": enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None,
        "completed_at": enrollment.completed_at.isoformat() if enrollment.completed_at else None,
        "next_step_at": enrollment.next_step_at.isoformat() if enrollment.next_step_at else None,
    }
