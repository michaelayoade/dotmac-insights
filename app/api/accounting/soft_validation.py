"""Soft validation endpoints for finance records."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import Require
from app.database import get_db
from app.models.validation import FinanceValidationIssue
from app.services.validation.soft_validation_service import SoftValidationService, finance_models

router = APIRouter()


class FinanceValidationRequest(BaseModel):
    """Request payload to run soft validation on finance records."""

    models: Optional[List[str]] = Field(
        default=None,
        description="Optional list of model names (e.g. Invoice, Payment). Defaults to all finance models.",
    )
    record_ids: Optional[List[int]] = Field(
        default=None,
        description="Optional list of record IDs to validate (applied per model).",
    )
    limit: Optional[int] = Field(
        default=None,
        gt=0,
        le=10000,
        description="Optional per-model limit to cap records validated in one call.",
    )


class FinanceValidationIssueItem(BaseModel):
    id: int
    model_name: str
    record_id: int
    scope: str
    issues: List[dict]
    detected_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FinanceValidationIssueList(BaseModel):
    data: List[FinanceValidationIssueItem]
    total: int
    limit: int
    offset: int


class FinanceValidationSummaryResponse(BaseModel):
    total: int
    by_model: List[Dict[str, object]]
    by_severity: List[Dict[str, object]]


def _resolve_models(model_names: Optional[List[str]] = None):
    models = finance_models()
    model_map = {model.__name__.lower(): model for model in models}
    if not model_names:
        return models

    unknown = [name for name in model_names if name.lower() not in model_map]
    if unknown:
        available = sorted(model_map.keys())
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Unknown model(s) requested",
                "unknown": unknown,
                "available": available,
            },
        )
    return [model_map[name.lower()] for name in model_names]


@router.post(
    "/validation/finance",
    dependencies=[Depends(Require("books:admin"))],
)
def validate_finance_records(
    payload: FinanceValidationRequest,
    db: Session = Depends(get_db),
) -> Dict[str, object]:
    """Run soft validation for finance records and persist issues."""
    models = _resolve_models(payload.models)
    summary = SoftValidationService(db).validate_records(
        models,
        record_ids=payload.record_ids,
        limit=payload.limit,
    )
    db.commit()
    return summary


@router.get(
    "/validation/finance/issues",
    response_model=FinanceValidationIssueList,
    dependencies=[Depends(Require("books:admin"))],
)
def list_finance_validation_issues(
    scope: Optional[str] = None,
    model: Optional[str] = None,
    record_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> FinanceValidationIssueList:
    query = db.query(FinanceValidationIssue)
    if scope:
        query = query.filter(FinanceValidationIssue.scope == scope)
    if model:
        query = query.filter(func.lower(FinanceValidationIssue.model_name) == model.lower())
    if record_id is not None:
        query = query.filter(FinanceValidationIssue.record_id == record_id)

    total = query.count()
    items = (
        query.order_by(FinanceValidationIssue.detected_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return FinanceValidationIssueList(data=items, total=total, limit=limit, offset=offset)


@router.get(
    "/validation/finance/issues/summary",
    response_model=FinanceValidationSummaryResponse,
    dependencies=[Depends(Require("books:admin"))],
)
def finance_validation_summary(
    scope: Optional[str] = None,
    db: Session = Depends(get_db),
) -> FinanceValidationSummaryResponse:
    query = db.query(FinanceValidationIssue)
    if scope:
        query = query.filter(FinanceValidationIssue.scope == scope)

    total = query.count()

    model_rows = (
        query.with_entities(
            FinanceValidationIssue.model_name,
            func.count(FinanceValidationIssue.id),
        )
        .group_by(FinanceValidationIssue.model_name)
        .order_by(func.count(FinanceValidationIssue.id).desc())
        .all()
    )
    by_model = [{"model": row[0], "count": row[1]} for row in model_rows]

    severity_counts: Dict[str, int] = {}
    for issue in query.all():
        for item in issue.issues or []:
            severity = (item or {}).get("severity") or "unknown"
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
    by_severity = [{"severity": key, "count": value} for key, value in severity_counts.items()]

    return FinanceValidationSummaryResponse(
        total=total,
        by_model=by_model,
        by_severity=by_severity,
    )
