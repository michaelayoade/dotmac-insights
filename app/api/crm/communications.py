"""
Communications API - Proactive outreach management.

Manage multi-channel communications and track engagement.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Principal, get_current_principal
from app.utils.company_context import get_company_id
from app.services.crm.communication import CRMCommunicationService
from app.services.crm.communication_types import (
    CommunicationFilters,
    CommunicationCreateData,
    CommunicationUpdateData,
    CommunicationScheduleData,
)

router = APIRouter(prefix="/communications", tags=["crm-communications"])


def get_communication_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> CRMCommunicationService:
    """Create a CRMCommunicationService instance."""
    company_id = get_company_id(principal)
    return CRMCommunicationService(db, company_id, principal.user_id)


# ============= SCHEMAS =============
class CommunicationCreate(BaseModel):
    """Create a communication."""

    party_id: int
    channel: str  # email, sms, whatsapp, call
    communication_type: str = "outreach"
    subject: Optional[str] = None
    content: str = ""
    template_id: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    campaign_id: Optional[int] = None
    sequence_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    personalization_data: dict = Field(default_factory=dict)
    priority: str = "normal"
    track_opens: bool = True
    track_clicks: bool = True


class CommunicationUpdate(BaseModel):
    """Update a communication."""

    subject: Optional[str] = None
    content: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    priority: Optional[str] = None


class BulkScheduleRequest(BaseModel):
    """Schedule communications for multiple contacts."""

    party_ids: List[int]
    channel: str
    subject: Optional[str] = None
    content: str = ""
    template_id: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    campaign_id: Optional[int] = None
    respect_preferences: bool = True
    respect_frequency_limits: bool = True


class RecordEventRequest(BaseModel):
    """Record a tracking event."""

    link_url: Optional[str] = None  # For click events


class MarkFailedRequest(BaseModel):
    """Mark a communication as failed."""

    error: str


# ============= COMMUNICATION ENDPOINTS =============
@router.get("")
async def list_communications(
    search: Optional[str] = None,
    channel: Optional[str] = None,
    status: Optional[str] = None,
    party_id: Optional[int] = None,
    campaign_id: Optional[int] = None,
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    service: CRMCommunicationService = Depends(get_communication_service),
):
    """List communications."""
    filters = CommunicationFilters(
        search=search,
        channel=channel,
        status=status,
        party_id=party_id,
        campaign_id=campaign_id,
        created_after=created_after,
        created_before=created_before,
    )
    communications, total = service.list_communications(filters, skip, limit)
    return {
        "items": [_serialize_communication(c) for c in communications],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/summary")
async def get_summary(
    days: int = Query(30, ge=1, le=365),
    service: CRMCommunicationService = Depends(get_communication_service),
):
    """Get communications summary."""
    summary = service.get_summary(days)
    return {
        "total_communications": summary.total_communications,
        "pending_count": summary.pending_count,
        "sent_count": summary.sent_count,
        "delivered_count": summary.delivered_count,
        "opened_count": summary.opened_count,
        "clicked_count": summary.clicked_count,
        "failed_count": summary.failed_count,
        "delivery_rate": summary.delivery_rate,
        "open_rate": summary.open_rate,
        "click_rate": summary.click_rate,
        "reply_rate": summary.reply_rate,
        "by_channel": summary.by_channel,
        "sent_today": summary.sent_today,
        "sent_this_week": summary.sent_this_week,
        "sent_this_month": summary.sent_this_month,
        "top_templates": summary.top_templates,
        "best_sending_times": summary.best_sending_times,
    }


@router.post("")
async def create_communication(
    data: CommunicationCreate,
    service: CRMCommunicationService = Depends(get_communication_service),
    db: Session = Depends(get_db),
):
    """Create a communication."""
    try:
        create_data = CommunicationCreateData(
            party_id=data.party_id,
            channel=data.channel,
            communication_type=data.communication_type,
            subject=data.subject,
            content=data.content,
            template_id=data.template_id,
            scheduled_at=data.scheduled_at,
            campaign_id=data.campaign_id,
            sequence_id=data.sequence_id,
            opportunity_id=data.opportunity_id,
            personalization_data=data.personalization_data,
            priority=data.priority,
            track_opens=data.track_opens,
            track_clicks=data.track_clicks,
        )
        communication = service.create_communication(create_data)
        db.commit()
        return _serialize_communication(communication)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{communication_id}")
async def get_communication(
    communication_id: int,
    service: CRMCommunicationService = Depends(get_communication_service),
):
    """Get a communication by ID."""
    communication = service.get_communication(communication_id)
    if not communication:
        raise HTTPException(status_code=404, detail="Communication not found")
    return _serialize_communication(communication)


@router.patch("/{communication_id}")
async def update_communication(
    communication_id: int,
    data: CommunicationUpdate,
    service: CRMCommunicationService = Depends(get_communication_service),
    db: Session = Depends(get_db),
):
    """Update a communication (only if not sent)."""
    try:
        update_data = CommunicationUpdateData(
            subject=data.subject,
            content=data.content,
            scheduled_at=data.scheduled_at,
            priority=data.priority,
        )
        communication = service.update_communication(communication_id, update_data)
        if not communication:
            raise HTTPException(status_code=404, detail="Communication not found")
        db.commit()
        return _serialize_communication(communication)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{communication_id}")
async def delete_communication(
    communication_id: int,
    service: CRMCommunicationService = Depends(get_communication_service),
    db: Session = Depends(get_db),
):
    """Delete a communication (only if not sent)."""
    try:
        if not service.delete_communication(communication_id):
            raise HTTPException(status_code=404, detail="Communication not found")
        db.commit()
        return {"success": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bulk")
async def schedule_bulk(
    data: BulkScheduleRequest,
    service: CRMCommunicationService = Depends(get_communication_service),
    db: Session = Depends(get_db),
):
    """Schedule communications for multiple contacts."""
    schedule_data = CommunicationScheduleData(
        party_ids=data.party_ids,
        channel=data.channel,
        subject=data.subject,
        content=data.content,
        template_id=data.template_id,
        scheduled_at=data.scheduled_at,
        campaign_id=data.campaign_id,
        respect_preferences=data.respect_preferences,
        respect_frequency_limits=data.respect_frequency_limits,
    )
    result = service.schedule_bulk(schedule_data)
    db.commit()
    return {
        "total_requested": result.total_requested,
        "scheduled_count": result.scheduled_count,
        "skipped_do_not_contact": result.skipped_do_not_contact,
        "skipped_frequency_limit": result.skipped_frequency_limit,
        "skipped_no_contact_info": result.skipped_no_contact_info,
        "failed_count": result.failed_count,
        "scheduled_ids": result.scheduled_ids,
        "skipped_party_ids": result.skipped_party_ids,
        "failure_details": result.failure_details,
    }


# ============= TRACKING ENDPOINTS =============
@router.post("/{communication_id}/sent")
async def mark_sent(
    communication_id: int,
    service: CRMCommunicationService = Depends(get_communication_service),
    db: Session = Depends(get_db),
):
    """Mark a communication as sent."""
    communication = service.mark_sent(communication_id)
    if not communication:
        raise HTTPException(status_code=404, detail="Communication not found")
    db.commit()
    return _serialize_communication(communication)


@router.post("/{communication_id}/delivered")
async def mark_delivered(
    communication_id: int,
    service: CRMCommunicationService = Depends(get_communication_service),
    db: Session = Depends(get_db),
):
    """Mark a communication as delivered."""
    communication = service.mark_delivered(communication_id)
    if not communication:
        raise HTTPException(status_code=404, detail="Communication not found")
    db.commit()
    return _serialize_communication(communication)


@router.post("/{communication_id}/opened")
async def record_open(
    communication_id: int,
    service: CRMCommunicationService = Depends(get_communication_service),
    db: Session = Depends(get_db),
):
    """Record an open event."""
    communication = service.record_open(communication_id)
    if not communication:
        raise HTTPException(status_code=404, detail="Communication not found")
    db.commit()
    return _serialize_communication(communication)


@router.post("/{communication_id}/clicked")
async def record_click(
    communication_id: int,
    data: RecordEventRequest,
    service: CRMCommunicationService = Depends(get_communication_service),
    db: Session = Depends(get_db),
):
    """Record a click event."""
    communication = service.record_click(communication_id, data.link_url)
    if not communication:
        raise HTTPException(status_code=404, detail="Communication not found")
    db.commit()
    return _serialize_communication(communication)


@router.post("/{communication_id}/replied")
async def record_reply(
    communication_id: int,
    service: CRMCommunicationService = Depends(get_communication_service),
    db: Session = Depends(get_db),
):
    """Record a reply."""
    communication = service.record_reply(communication_id)
    if not communication:
        raise HTTPException(status_code=404, detail="Communication not found")
    db.commit()
    return _serialize_communication(communication)


@router.post("/{communication_id}/failed")
async def mark_failed(
    communication_id: int,
    data: MarkFailedRequest,
    service: CRMCommunicationService = Depends(get_communication_service),
    db: Session = Depends(get_db),
):
    """Mark a communication as failed."""
    communication = service.mark_failed(communication_id, data.error)
    if not communication:
        raise HTTPException(status_code=404, detail="Communication not found")
    db.commit()
    return _serialize_communication(communication)


# ============= ANALYTICS ENDPOINTS =============
@router.get("/channels/{channel}/performance")
async def get_channel_performance(
    channel: str,
    service: CRMCommunicationService = Depends(get_communication_service),
):
    """Get performance metrics for a channel."""
    perf = service.get_channel_performance(channel)
    return {
        "channel": perf.channel,
        "total_sent": perf.total_sent,
        "delivered": perf.delivered,
        "opened": perf.opened,
        "clicked": perf.clicked,
        "replied": perf.replied,
        "failed": perf.failed,
        "delivery_rate": perf.delivery_rate,
        "open_rate": perf.open_rate,
        "click_rate": perf.click_rate,
        "reply_rate": perf.reply_rate,
        "failure_rate": perf.failure_rate,
        "avg_time_to_open_minutes": perf.avg_time_to_open_minutes,
        "best_day_of_week": perf.best_day_of_week,
        "best_hour_of_day": perf.best_hour_of_day,
        "trend_vs_last_period": perf.trend_vs_last_period,
    }


@router.get("/contacts/{party_id}/preferences")
async def get_contact_preferences(
    party_id: int,
    service: CRMCommunicationService = Depends(get_communication_service),
):
    """Get communication preferences for a contact."""
    prefs = service.get_contact_preferences(party_id)
    if not prefs:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {
        "party_id": prefs.party_id,
        "party_name": prefs.party_name,
        "preferred_channel": prefs.preferred_channel,
        "do_not_contact": prefs.do_not_contact,
        "contact_frequency_limit": prefs.contact_frequency_limit,
        "best_contact_time": prefs.best_contact_time,
        "responsive_channels": prefs.responsive_channels,
        "avg_response_time_hours": prefs.avg_response_time_hours,
        "total_communications": prefs.total_communications,
        "last_contacted_at": prefs.last_contacted_at.isoformat() if prefs.last_contacted_at else None,
        "last_response_at": prefs.last_response_at.isoformat() if prefs.last_response_at else None,
        "days_since_contact": prefs.days_since_contact,
        "overall_open_rate": prefs.overall_open_rate,
        "overall_click_rate": prefs.overall_click_rate,
        "overall_reply_rate": prefs.overall_reply_rate,
    }


@router.get("/{communication_id}/metrics")
async def get_communication_metrics(
    communication_id: int,
    service: CRMCommunicationService = Depends(get_communication_service),
):
    """Get detailed metrics for a communication."""
    metrics = service.get_communication_metrics(communication_id)
    if not metrics:
        raise HTTPException(status_code=404, detail="Communication not found")
    return {
        "communication_id": metrics.communication_id,
        "party_id": metrics.party_id,
        "party_name": metrics.party_name,
        "channel": metrics.channel,
        "status": metrics.status,
        "created_at": metrics.created_at.isoformat(),
        "scheduled_at": metrics.scheduled_at.isoformat() if metrics.scheduled_at else None,
        "sent_at": metrics.sent_at.isoformat() if metrics.sent_at else None,
        "delivered_at": metrics.delivered_at.isoformat() if metrics.delivered_at else None,
        "opened_at": metrics.opened_at.isoformat() if metrics.opened_at else None,
        "clicked_at": metrics.clicked_at.isoformat() if metrics.clicked_at else None,
        "open_count": metrics.open_count,
        "click_count": metrics.click_count,
        "links_clicked": metrics.links_clicked,
        "time_to_open_seconds": metrics.time_to_open_seconds,
        "replied": metrics.replied,
        "reply_at": metrics.reply_at.isoformat() if metrics.reply_at else None,
        "converted": metrics.converted,
    }


# ============= SERIALIZERS =============
def _serialize_communication(communication) -> dict:
    """Serialize a communication."""
    return {
        "id": communication.id,
        "party_id": communication.party_id,
        "channel": communication.channel,
        "communication_type": communication.communication_type,
        "subject": communication.subject,
        "content": communication.content,
        "template_id": communication.template_id,
        "status": communication.status,
        "priority": communication.priority,
        "scheduled_at": communication.scheduled_at.isoformat() if communication.scheduled_at else None,
        "sent_at": communication.sent_at.isoformat() if communication.sent_at else None,
        "delivered_at": communication.delivered_at.isoformat() if communication.delivered_at else None,
        "opened_at": communication.opened_at.isoformat() if communication.opened_at else None,
        "clicked_at": communication.clicked_at.isoformat() if communication.clicked_at else None,
        "open_count": communication.open_count,
        "click_count": communication.click_count,
        "replied": communication.replied,
        "campaign_id": communication.campaign_id,
        "sequence_id": communication.sequence_id,
        "opportunity_id": communication.opportunity_id,
        "created_at": communication.created_at.isoformat() if communication.created_at else None,
    }
