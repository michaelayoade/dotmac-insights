"""CSAT (Customer Satisfaction) survey API endpoints.

Refactored to use CSATService for all business logic.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.database import get_db
from app.auth import Require, get_principal, Principal
from app.models.support_csat import SurveyTrigger, SurveyType
from app.models.ticket import Ticket
from app.cache import cached, CACHE_TTL
from app.services.support import (
    CSATService,
    CSATSurveyCreate,
    CSATSurveyUpdate,
    CSATSurveyNotFoundError,
    CSATResponseNotFoundError,
    InvalidSurveyTokenError,
)

router = APIRouter()


# =============================================================================
# DEPENDENCIES
# =============================================================================

def get_csat_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> CSATService:
    """Dependency to get CSATService instance."""
    return CSATService(db, principal)


# =============================================================================
# PYDANTIC MODELS (API Input Validation)
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


class SurveyUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
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
# HELPER FUNCTIONS
# =============================================================================

def serialize_survey(s, include_stats: bool = False) -> Dict[str, Any]:
    """Serialize a survey to dict."""
    result = {
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "survey_type": s.survey_type,
        "trigger": s.trigger,
        "delay_hours": s.delay_hours,
        "send_via": s.send_via,
        "is_active": s.is_active,
        "response_count": len(s.responses) if hasattr(s, 'responses') else 0,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }
    if include_stats:
        result["questions"] = s.questions
        result["conditions"] = s.conditions
        result["updated_at"] = s.updated_at.isoformat() if s.updated_at else None
    return result


def serialize_response(r) -> Dict[str, Any]:
    """Serialize a CSAT response to dict."""
    return {
        "id": r.id,
        "survey_id": r.survey_id,
        "survey_name": r.survey.name if r.survey else None,
        "ticket_id": r.ticket_id,
        "party_id": r.party_id,
        "agent_id": r.agent_id,
        "rating": r.rating,
        "feedback_text": r.feedback_text,
        "sent_at": r.sent_at.isoformat() if r.sent_at else None,
        "responded_at": r.responded_at.isoformat() if r.responded_at else None,
        "response_channel": r.response_channel,
    }


# =============================================================================
# SURVEYS
# =============================================================================

@router.get("/csat/surveys", dependencies=[Depends(Require("support:csat:read"))])
def list_surveys(
    active_only: bool = True,
    survey_type: Optional[str] = None,
    service: CSATService = Depends(get_csat_service),
) -> List[Dict[str, Any]]:
    """List CSAT surveys."""
    surveys = service.list_surveys(
        survey_type=survey_type,
        active_only=active_only,
    )
    return [serialize_survey(s) for s in surveys]


@router.post("/csat/surveys", dependencies=[Depends(Require("support:csat:write"))], status_code=201)
def create_survey(
    payload: SurveyCreateRequest,
    db: Session = Depends(get_db),
    service: CSATService = Depends(get_csat_service),
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

    data = CSATSurveyCreate(
        name=payload.name,
        survey_type=payload.survey_type,
        trigger=payload.trigger,
        questions=payload.questions,
        delay_hours=payload.delay_hours,
        send_via=payload.send_via,
        conditions=payload.conditions,
    )
    survey = service.create_survey(data)
    db.commit()
    return {"id": survey.id, "name": survey.name}


@router.get("/csat/surveys/{survey_id}", dependencies=[Depends(Require("support:csat:read"))])
def get_survey(
    survey_id: int,
    service: CSATService = Depends(get_csat_service),
) -> Dict[str, Any]:
    """Get survey details with metrics."""
    try:
        survey = service.get_survey(survey_id)
        metrics = service.get_survey_metrics(survey_id)

        result = serialize_survey(survey, include_stats=True)
        result["stats"] = {
            "total_sent": metrics.total_sent,
            "total_responses": metrics.total_responded,
            "response_rate": metrics.response_rate,
            "avg_rating": metrics.avg_rating,
            "score": metrics.score,
            "rating_distribution": metrics.rating_distribution,
        }
        return result
    except CSATSurveyNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/csat/surveys/{survey_id}", dependencies=[Depends(Require("support:csat:write"))])
def update_survey(
    survey_id: int,
    payload: SurveyUpdateRequest,
    db: Session = Depends(get_db),
    service: CSATService = Depends(get_csat_service),
) -> Dict[str, Any]:
    """Update a survey."""
    try:
        data = CSATSurveyUpdate(
            name=payload.name,
            questions=payload.questions,
            delay_hours=payload.delay_hours,
            send_via=payload.send_via,
            conditions=payload.conditions,
            is_active=payload.is_active,
        )
        survey = service.update_survey(survey_id, data)
        db.commit()
        return {"id": survey.id, "name": survey.name}
    except CSATSurveyNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/csat/surveys/{survey_id}", dependencies=[Depends(Require("support:csat:write"))])
def delete_survey(
    survey_id: int,
    db: Session = Depends(get_db),
    service: CSATService = Depends(get_csat_service),
) -> Response:
    """Delete a survey."""
    try:
        service.delete_survey(survey_id)
        db.commit()
        return Response(status_code=204)
    except CSATSurveyNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/csat/surveys/{survey_id}/activate", dependencies=[Depends(Require("support:csat:write"))])
def activate_survey(
    survey_id: int,
    db: Session = Depends(get_db),
    service: CSATService = Depends(get_csat_service),
) -> Dict[str, Any]:
    """Activate a survey."""
    try:
        survey = service.activate_survey(survey_id)
        db.commit()
        return {"id": survey.id, "is_active": survey.is_active}
    except CSATSurveyNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/csat/surveys/{survey_id}/deactivate", dependencies=[Depends(Require("support:csat:write"))])
def deactivate_survey(
    survey_id: int,
    db: Session = Depends(get_db),
    service: CSATService = Depends(get_csat_service),
) -> Dict[str, Any]:
    """Deactivate a survey."""
    try:
        survey = service.deactivate_survey(survey_id)
        db.commit()
        return {"id": survey.id, "is_active": survey.is_active}
    except CSATSurveyNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/csat/surveys/{survey_id}/toggle", dependencies=[Depends(Require("support:csat:write"))])
def toggle_survey(
    survey_id: int,
    db: Session = Depends(get_db),
    service: CSATService = Depends(get_csat_service),
) -> Dict[str, Any]:
    """Toggle survey active status."""
    try:
        survey = service.get_survey(survey_id)
        if survey.is_active:
            survey = service.deactivate_survey(survey_id)
        else:
            survey = service.activate_survey(survey_id)
        db.commit()
        return {"id": survey.id, "is_active": survey.is_active}
    except CSATSurveyNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/csat/surveys/{survey_id}/metrics", dependencies=[Depends(Require("support:csat:read"))])
def get_survey_metrics(
    survey_id: int,
    service: CSATService = Depends(get_csat_service),
) -> Dict[str, Any]:
    """Get detailed metrics for a survey."""
    try:
        metrics = service.get_survey_metrics(survey_id)
        return {
            "survey_id": metrics.survey_id,
            "total_sent": metrics.total_sent,
            "total_responded": metrics.total_responded,
            "response_rate": metrics.response_rate,
            "avg_rating": metrics.avg_rating,
            "score": metrics.score,
            "rating_distribution": metrics.rating_distribution,
        }
    except CSATSurveyNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


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
    offset: int = Query(default=0, ge=0),
    service: CSATService = Depends(get_csat_service),
) -> Dict[str, Any]:
    """List CSAT responses."""
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    responses = service.list_responses(
        survey_id=survey_id,
        agent_id=agent_id,
        start_date=start_date,
        responded_only=True,
        limit=limit,
        offset=offset,
    )

    # Apply rating filters (service doesn't have these params)
    if rating_min is not None:
        responses = [r for r in responses if r.rating and r.rating >= rating_min]
    if rating_max is not None:
        responses = [r for r in responses if r.rating and r.rating <= rating_max]

    return {
        "total": len(responses),
        "limit": limit,
        "offset": offset,
        "data": [serialize_response(r) for r in responses],
    }


@router.get("/csat/responses/{response_id}", dependencies=[Depends(Require("support:csat:read"))])
def get_response(
    response_id: int,
    service: CSATService = Depends(get_csat_service),
) -> Dict[str, Any]:
    """Get response details."""
    try:
        response = service.get_response(response_id)
        result = serialize_response(response)
        result["answers"] = response.answers
        result["created_at"] = response.created_at.isoformat() if response.created_at else None
        return result
    except CSATResponseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/csat/responses/for-ticket/{ticket_id}", dependencies=[Depends(Require("support:csat:read"))])
def get_responses_for_ticket(
    ticket_id: int,
    service: CSATService = Depends(get_csat_service),
) -> List[Dict[str, Any]]:
    """Get all CSAT responses for a ticket."""
    responses = service.get_responses_for_ticket(ticket_id)
    return [serialize_response(r) for r in responses]


@router.get("/csat/responses/for-agent/{agent_id}", dependencies=[Depends(Require("support:csat:read"))])
def get_responses_for_agent(
    agent_id: int,
    service: CSATService = Depends(get_csat_service),
) -> List[Dict[str, Any]]:
    """Get all CSAT responses for an agent."""
    responses = service.get_responses_for_agent(agent_id, responded_only=True)
    return [serialize_response(r) for r in responses]


@router.get("/csat/responses/pending", dependencies=[Depends(Require("support:csat:read"))])
def get_pending_responses(
    party_id: Optional[int] = None,
    service: CSATService = Depends(get_csat_service),
) -> List[Dict[str, Any]]:
    """Get pending (not yet responded) survey responses."""
    responses = service.get_pending_responses(party_id=party_id)
    return [serialize_response(r) for r in responses]


# =============================================================================
# PUBLIC RESPONSE SUBMISSION (No Auth)
# =============================================================================

@router.post("/csat/respond/{token}")
def submit_response(
    token: str,
    payload: ResponseSubmitRequest,
    db: Session = Depends(get_db),
    service: CSATService = Depends(get_csat_service),
) -> Dict[str, Any]:
    """Submit a survey response (public endpoint)."""
    # Validate rating based on survey type
    response = service.get_response_by_token(token)
    if not response:
        raise HTTPException(status_code=404, detail="Survey not found or already completed")

    if response.responded_at:
        raise HTTPException(status_code=400, detail="Survey already completed")

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

    try:
        service.record_response(
            token=token,
            rating=payload.rating,
            answers=payload.answers,
            feedback_text=payload.feedback_text,
            response_channel="web",
        )
        db.commit()
        return {"status": "success", "message": "Thank you for your feedback!"}
    except InvalidSurveyTokenError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# SEND SURVEY
# =============================================================================

@router.post("/csat/send/{ticket_id}", dependencies=[Depends(Require("support:csat:write"))])
def queue_survey_for_ticket(
    ticket_id: int,
    survey_id: Optional[int] = None,
    db: Session = Depends(get_db),
    service: CSATService = Depends(get_csat_service),
) -> Dict[str, Any]:
    """Queue a survey to be sent for a ticket.

    Creates a CSATResponse record with a token for the customer to respond.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Find applicable survey
    if survey_id:
        try:
            survey = service.get_survey(survey_id)
            if not survey.is_active:
                raise HTTPException(status_code=400, detail="Survey is not active")
        except CSATSurveyNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
    else:
        survey = service.get_active_survey_for_trigger(SurveyTrigger.TICKET_RESOLVED.value)
        if not survey:
            raise HTTPException(status_code=404, detail="No active survey found")

    # Try to get agent from ticket
    agent_id = None
    if ticket.assigned_to:
        from app.models.agent import Agent
        agent = db.query(Agent).filter(
            Agent.display_name == ticket.assigned_to
        ).first()
        if agent:
            agent_id = agent.id

    # Send survey using service
    token = service.send_survey(
        survey_id=survey.id,
        ticket_id=ticket_id,
        party_id=ticket.party_id,
        agent_id=agent_id,
    )
    db.commit()

    return {
        "survey_id": survey.id,
        "response_token": token,
        "survey_url": f"/csat/respond/{token}",
    }


# =============================================================================
# ANALYTICS
# =============================================================================

@router.get("/csat/analytics/summary", dependencies=[Depends(Require("analytics:read"))])
@cached("csat-summary", ttl=CACHE_TTL["medium"])
async def csat_summary(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db),
    service: CSATService = Depends(get_csat_service),
) -> Dict[str, Any]:
    """Get CSAT summary metrics."""
    from app.models.support_csat import CSATSurvey, CSATResponse

    start_dt = datetime.now(timezone.utc) - timedelta(days=days)

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

    # Get scores from service
    csat_score = service.get_csat_score(start_date=start_dt)
    nps_score = service.get_nps_score(start_date=start_dt)
    ces_score = service.get_ces_score(start_date=start_dt)

    return {
        "period_days": days,
        "total_responses": stats.total or 0,
        "average_rating": round(float(stats.avg_rating or 0), 2),
        "response_rate": round(total_responded / total_sent * 100, 1) if total_sent > 0 else 0,
        "scores": {
            "csat": csat_score,
            "nps": nps_score,
            "ces": ces_score,
        },
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
    service: CSATService = Depends(get_csat_service),
) -> List[Dict[str, Any]]:
    """Get CSAT scores by agent."""
    from app.models.support_csat import CSATResponse
    from app.models.agent import Agent

    start_dt = datetime.now(timezone.utc) - timedelta(days=days)

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

    results = []
    for row in by_agent:
        # Get CSAT score from service for each agent
        agent_csat = service.get_agent_csat_score(row.agent_id, start_date=start_dt) if row.agent_id else None
        results.append({
            "agent_id": row.agent_id,
            "agent_name": row.display_name,
            "response_count": row.count,
            "avg_rating": round(float(row.avg_rating or 0), 2),
            "csat_score": agent_csat,
            "positive_count": row.positive or 0,
            "negative_count": row.negative or 0,
            "satisfaction_pct": round((row.positive or 0) / row.count * 100, 1) if row.count > 0 else 0,
        })

    return results


@router.get("/csat/analytics/trends", dependencies=[Depends(Require("analytics:read"))])
@cached("csat-trends", ttl=CACHE_TTL["medium"])
async def csat_trends(
    months: int = Query(default=6, le=12),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get CSAT trends over time."""
    from sqlalchemy import extract
    from app.models.support_csat import CSATResponse

    start_dt = datetime.now(timezone.utc) - timedelta(days=months * 30)

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


@router.get("/csat/scores", dependencies=[Depends(Require("support:csat:read"))])
def get_all_scores(
    days: int = Query(default=30, le=90),
    service: CSATService = Depends(get_csat_service),
) -> Dict[str, Any]:
    """Get all satisfaction scores (CSAT, NPS, CES)."""
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    return {
        "period_days": days,
        "csat_score": service.get_csat_score(start_date=start_date),
        "nps_score": service.get_nps_score(start_date=start_date),
        "ces_score": service.get_ces_score(start_date=start_date),
    }
