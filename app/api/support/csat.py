"""CSAT (Customer Satisfaction) survey API endpoints."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.database import get_db
from app.models.support_csat import (
    CSATSurvey,
    CSATResponse,
    SurveyTrigger,
    SurveyType,
)
from app.models.ticket import Ticket
from app.auth import Require
from app.cache import cached, CACHE_TTL

router = APIRouter()


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class SurveyCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    survey_type: str = SurveyType.CSAT.value
    trigger: str = SurveyTrigger.TICKET_RESOLVED.value
    questions: Optional[List[dict]] = None
    delay_hours: int = 0
    send_via: str = "email"
    conditions: Optional[dict] = None
    is_active: bool = True


class SurveyUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    survey_type: Optional[str] = None
    trigger: Optional[str] = None
    questions: Optional[List[dict]] = None
    delay_hours: Optional[int] = None
    send_via: Optional[str] = None
    conditions: Optional[dict] = None
    is_active: Optional[bool] = None


class ResponseSubmitRequest(BaseModel):
    rating: int
    answers: Optional[Dict[str, Any]] = None
    feedback_text: Optional[str] = None


# =============================================================================
# SURVEYS
# =============================================================================

@router.get("/csat/surveys", dependencies=[Depends(Require("support:csat:read"))])
def list_surveys(
    active_only: bool = True,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List CSAT surveys."""
    query = db.query(CSATSurvey)
    if active_only:
        query = query.filter(CSATSurvey.is_active == True)
    surveys = query.order_by(CSATSurvey.name).all()

    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "survey_type": s.survey_type,
            "trigger": s.trigger,
            "delay_hours": s.delay_hours,
            "send_via": s.send_via,
            "is_active": s.is_active,
            "response_count": len(s.responses),
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in surveys
    ]


@router.post("/csat/surveys", dependencies=[Depends(Require("support:csat:write"))], status_code=201)
def create_survey(
    payload: SurveyCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a CSAT survey."""
    # Validate survey type
    try:
        SurveyType(payload.survey_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid survey_type: {payload.survey_type}")

    # Validate trigger
    try:
        SurveyTrigger(payload.trigger)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid trigger: {payload.trigger}")

    survey = CSATSurvey(
        name=payload.name,
        description=payload.description,
        survey_type=payload.survey_type,
        trigger=payload.trigger,
        questions=payload.questions,
        delay_hours=payload.delay_hours,
        send_via=payload.send_via,
        conditions=payload.conditions,
        is_active=payload.is_active,
    )
    db.add(survey)
    db.commit()
    db.refresh(survey)
    return {"id": survey.id, "name": survey.name}


@router.get("/csat/surveys/{survey_id}", dependencies=[Depends(Require("support:csat:read"))])
def get_survey(
    survey_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get survey details."""
    survey = db.query(CSATSurvey).filter(CSATSurvey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    # Get response stats
    stats = db.query(
        func.count(CSATResponse.id).label("total"),
        func.avg(CSATResponse.rating).label("avg_rating"),
    ).filter(
        CSATResponse.survey_id == survey_id,
        CSATResponse.rating.isnot(None),
    ).first()

    return {
        "id": survey.id,
        "name": survey.name,
        "description": survey.description,
        "survey_type": survey.survey_type,
        "trigger": survey.trigger,
        "questions": survey.questions,
        "delay_hours": survey.delay_hours,
        "send_via": survey.send_via,
        "conditions": survey.conditions,
        "is_active": survey.is_active,
        "stats": {
            "total_responses": stats.total or 0,
            "avg_rating": round(float(stats.avg_rating or 0), 2),
        },
        "created_at": survey.created_at.isoformat() if survey.created_at else None,
        "updated_at": survey.updated_at.isoformat() if survey.updated_at else None,
    }


@router.patch("/csat/surveys/{survey_id}", dependencies=[Depends(Require("support:csat:write"))])
def update_survey(
    survey_id: int,
    payload: SurveyUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a survey."""
    survey = db.query(CSATSurvey).filter(CSATSurvey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    if payload.name is not None:
        survey.name = payload.name
    if payload.description is not None:
        survey.description = payload.description
    if payload.survey_type is not None:
        try:
            SurveyType(payload.survey_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid survey_type: {payload.survey_type}")
        survey.survey_type = payload.survey_type
    if payload.trigger is not None:
        survey.trigger = payload.trigger
    if payload.questions is not None:
        survey.questions = cast(Any, payload.questions)
    if payload.delay_hours is not None:
        survey.delay_hours = payload.delay_hours
    if payload.send_via is not None:
        survey.send_via = payload.send_via
    if payload.conditions is not None:
        survey.conditions = cast(Any, payload.conditions)
    if payload.is_active is not None:
        survey.is_active = payload.is_active

    db.commit()
    db.refresh(survey)
    return {"id": survey.id, "name": survey.name}


@router.delete("/csat/surveys/{survey_id}", dependencies=[Depends(Require("support:csat:write"))])
def delete_survey(
    survey_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Delete a survey."""
    survey = db.query(CSATSurvey).filter(CSATSurvey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    db.delete(survey)
    db.commit()
    return Response(status_code=204)


@router.post("/csat/surveys/{survey_id}/toggle", dependencies=[Depends(Require("support:csat:write"))])
def toggle_survey(
    survey_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Toggle survey active status."""
    survey = db.query(CSATSurvey).filter(CSATSurvey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    survey.is_active = not survey.is_active
    db.commit()
    return {"id": survey.id, "is_active": survey.is_active}


# =============================================================================
# RESPONSES
# =============================================================================

@router.get("/csat/responses", dependencies=[Depends(Require("support:csat:read"))])
def list_responses(
    survey_id: Optional[int] = None,
    agent_id: Optional[int] = None,
    rating_min: Optional[int] = None,
    rating_max: Optional[int] = None,
    days: int = Query(default=30, le=90),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List CSAT responses."""
    start_dt = datetime.utcnow() - timedelta(days=days)

    query = db.query(CSATResponse).filter(CSATResponse.responded_at >= start_dt)

    if survey_id:
        query = query.filter(CSATResponse.survey_id == survey_id)
    if agent_id:
        query = query.filter(CSATResponse.agent_id == agent_id)
    if rating_min is not None:
        query = query.filter(CSATResponse.rating >= rating_min)
    if rating_max is not None:
        query = query.filter(CSATResponse.rating <= rating_max)

    total = query.count()
    responses = query.order_by(CSATResponse.responded_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": r.id,
                "survey_id": r.survey_id,
                "survey_name": r.survey.name if r.survey else None,
                "ticket_id": r.ticket_id,
                "customer_id": r.customer_id,
                "agent_id": r.agent_id,
                "rating": r.rating,
                "feedback_text": r.feedback_text,
                "sent_at": r.sent_at.isoformat() if r.sent_at else None,
                "responded_at": r.responded_at.isoformat() if r.responded_at else None,
                "response_channel": r.response_channel,
            }
            for r in responses
        ],
    }


@router.get("/csat/responses/{response_id}", dependencies=[Depends(Require("support:csat:read"))])
def get_response(
    response_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get response details."""
    response = db.query(CSATResponse).filter(CSATResponse.id == response_id).first()
    if not response:
        raise HTTPException(status_code=404, detail="Response not found")

    return {
        "id": response.id,
        "survey_id": response.survey_id,
        "survey_name": response.survey.name if response.survey else None,
        "ticket_id": response.ticket_id,
        "customer_id": response.customer_id,
        "agent_id": response.agent_id,
        "rating": response.rating,
        "answers": response.answers,
        "feedback_text": response.feedback_text,
        "sent_at": response.sent_at.isoformat() if response.sent_at else None,
        "responded_at": response.responded_at.isoformat() if response.responded_at else None,
        "response_channel": response.response_channel,
        "created_at": response.created_at.isoformat() if response.created_at else None,
    }


# =============================================================================
# PUBLIC RESPONSE SUBMISSION (No Auth)
# =============================================================================

@router.post("/csat/respond/{token}")
def submit_response(
    token: str,
    payload: ResponseSubmitRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Submit a survey response (public endpoint)."""
    response = db.query(CSATResponse).filter(CSATResponse.response_token == token).first()
    if not response:
        raise HTTPException(status_code=404, detail="Survey not found or already completed")

    if response.responded_at:
        raise HTTPException(status_code=400, detail="Survey already completed")

    # Validate rating based on survey type
    survey = response.survey
    if survey:
        if survey.survey_type == SurveyType.CSAT.value:
            if not 1 <= payload.rating <= 5:
                raise HTTPException(status_code=400, detail="CSAT rating must be 1-5")
        elif survey.survey_type == SurveyType.NPS.value:
            if not 0 <= payload.rating <= 10:
                raise HTTPException(status_code=400, detail="NPS rating must be 0-10")
        elif survey.survey_type == SurveyType.CES.value:
            if not 1 <= payload.rating <= 7:
                raise HTTPException(status_code=400, detail="CES rating must be 1-7")

    response.rating = payload.rating
    response.answers = payload.answers
    response.feedback_text = payload.feedback_text
    response.responded_at = datetime.utcnow()
    response.response_channel = "web"

    db.commit()

    return {"status": "success", "message": "Thank you for your feedback!"}


# =============================================================================
# ANALYTICS
# =============================================================================

@router.get("/csat/analytics/summary", dependencies=[Depends(Require("analytics:read"))])
@cached("csat-summary", ttl=CACHE_TTL["medium"])
async def csat_summary(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get CSAT summary metrics."""
    start_dt = datetime.utcnow() - timedelta(days=days)

    # Overall stats
    stats = db.query(
        func.count(CSATResponse.id).label("total"),
        func.avg(CSATResponse.rating).label("avg_rating"),
    ).filter(
        CSATResponse.responded_at >= start_dt,
        CSATResponse.rating.isnot(None),
    ).first()

    # By survey type
    by_type = db.query(
        CSATSurvey.survey_type,
        func.count(CSATResponse.id).label("count"),
        func.avg(CSATResponse.rating).label("avg_rating"),
    ).join(CSATSurvey, CSATResponse.survey_id == CSATSurvey.id).filter(
        CSATResponse.responded_at >= start_dt,
        CSATResponse.rating.isnot(None),
    ).group_by(CSATSurvey.survey_type).all()

    # Response rate
    total_sent = db.query(func.count(CSATResponse.id)).filter(
        CSATResponse.sent_at >= start_dt
    ).scalar() or 0
    total_responded = db.query(func.count(CSATResponse.id)).filter(
        CSATResponse.responded_at >= start_dt
    ).scalar() or 0

    return {
        "period_days": days,
        "total_responses": stats.total or 0,
        "average_rating": round(float(stats.avg_rating or 0), 2),
        "response_rate": round(total_responded / total_sent * 100, 1) if total_sent > 0 else 0,
        "by_survey_type": [
            {
                "type": row.survey_type,
                "count": row.count,
                "avg_rating": round(float(row.avg_rating or 0), 2),
            }
            for row in by_type
        ],
    }


@router.get("/csat/analytics/by-agent", dependencies=[Depends(Require("analytics:read"))])
@cached("csat-by-agent", ttl=CACHE_TTL["medium"])
async def csat_by_agent(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get CSAT scores by agent."""
    start_dt = datetime.utcnow() - timedelta(days=days)

    from app.models.agent import Agent

    by_agent = db.query(
        CSATResponse.agent_id,
        Agent.display_name,
        func.count(CSATResponse.id).label("count"),
        func.avg(CSATResponse.rating).label("avg_rating"),
        func.sum(case((CSATResponse.rating >= 4, 1), else_=0)).label("positive"),
        func.sum(case((CSATResponse.rating <= 2, 1), else_=0)).label("negative"),
    ).join(Agent, CSATResponse.agent_id == Agent.id, isouter=True).filter(
        CSATResponse.responded_at >= start_dt,
        CSATResponse.rating.isnot(None),
        CSATResponse.agent_id.isnot(None),
    ).group_by(CSATResponse.agent_id, Agent.display_name).order_by(
        func.avg(CSATResponse.rating).desc()
    ).all()

    return [
        {
            "agent_id": row.agent_id,
            "agent_name": row.display_name,
            "response_count": row.count,
            "avg_rating": round(float(row.avg_rating or 0), 2),
            "positive_count": row.positive or 0,
            "negative_count": row.negative or 0,
            "satisfaction_pct": round((row.positive or 0) / row.count * 100, 1) if row.count > 0 else 0,
        }
        for row in by_agent
    ]


@router.get("/csat/analytics/trends", dependencies=[Depends(Require("analytics:read"))])
@cached("csat-trends", ttl=CACHE_TTL["medium"])
async def csat_trends(
    months: int = Query(default=6, le=12),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get CSAT trends over time."""
    from sqlalchemy import extract

    start_dt = datetime.utcnow() - timedelta(days=months * 30)

    trends = db.query(
        extract("year", CSATResponse.responded_at).label("year"),
        extract("month", CSATResponse.responded_at).label("month"),
        func.count(CSATResponse.id).label("count"),
        func.avg(CSATResponse.rating).label("avg_rating"),
    ).filter(
        CSATResponse.responded_at >= start_dt,
        CSATResponse.rating.isnot(None),
    ).group_by(
        extract("year", CSATResponse.responded_at),
        extract("month", CSATResponse.responded_at),
    ).order_by(
        extract("year", CSATResponse.responded_at),
        extract("month", CSATResponse.responded_at),
    ).all()

    return [
        {
            "year": int(row.year),
            "month": int(row.month),
            "period": f"{int(row.year)}-{int(row.month):02d}",
            "response_count": row.count,
            "avg_rating": round(float(row.avg_rating or 0), 2),
        }
        for row in trends
    ]


# =============================================================================
# HELPER ENDPOINTS
# =============================================================================

@router.post("/csat/send/{ticket_id}", dependencies=[Depends(Require("support:csat:write"))])
def queue_survey_for_ticket(
    ticket_id: int,
    survey_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Queue a survey to be sent for a ticket.

    Creates a CSATResponse record with a token for the customer to respond.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Find applicable survey
    if survey_id:
        survey = db.query(CSATSurvey).filter(CSATSurvey.id == survey_id, CSATSurvey.is_active == True).first()
    else:
        survey = db.query(CSATSurvey).filter(CSATSurvey.is_active == True).first()

    if not survey:
        raise HTTPException(status_code=404, detail="No active survey found")

    # Generate response token
    token = secrets.token_urlsafe(32)

    response = CSATResponse(
        survey_id=survey.id,
        ticket_id=ticket_id,
        customer_id=ticket.customer_id,
        response_token=token,
        sent_at=datetime.utcnow(),
    )

    # Try to get agent from ticket
    if ticket.assigned_to:
        from app.models.agent import Agent
        agent = db.query(Agent).filter(
            Agent.display_name == ticket.assigned_to
        ).first()
        if agent:
            response.agent_id = agent.id

    db.add(response)
    db.commit()
    db.refresh(response)

    return {
        "id": response.id,
        "survey_id": survey.id,
        "response_token": token,
        "survey_url": f"/csat/respond/{token}",
    }
