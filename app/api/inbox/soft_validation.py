"""Soft validation endpoints for omnichannel records."""
from __future__ import annotations

from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import Require
from app.database import get_db
from app.models.validation import FinanceValidationIssue
from app.services.validation.soft_validation_service import SoftValidationService, omnichannel_models
from app.api.validation.soft_validation_schemas import (
    SoftValidationRequest,
    ValidationIssueList,
    ValidationSummaryResponse,
)

router = APIRouter()


def _resolve_models(model_names: Optional[list[str]] = None):
    models = omnichannel_models()
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
    "/validation/omnichannel",
    dependencies=[Depends(Require("support:write"))],
)
def validate_omnichannel_records(
    payload: SoftValidationRequest,
    db: Session = Depends(get_db),
) -> Dict[str, object]:
    """Run soft validation for omnichannel records and persist issues."""
    models = _resolve_models(payload.models)
    summary = SoftValidationService(db).validate_records(
        models,
        record_ids=payload.record_ids,
        limit=payload.limit,
    )
    db.commit()
    return summary


@router.get(
    "/validation/omnichannel/issues",
    response_model=ValidationIssueList,
    dependencies=[Depends(Require("support:read"))],
)
def list_omnichannel_validation_issues(
    model: Optional[str] = None,
    record_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> ValidationIssueList:
    query = db.query(FinanceValidationIssue).filter(FinanceValidationIssue.scope == "omnichannel")
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
    return ValidationIssueList(data=items, total=total, limit=limit, offset=offset)


@router.get(
    "/validation/omnichannel/issues/summary",
    response_model=ValidationSummaryResponse,
    dependencies=[Depends(Require("support:read"))],
)
def omnichannel_validation_summary(
    db: Session = Depends(get_db),
) -> ValidationSummaryResponse:
    query = db.query(FinanceValidationIssue).filter(FinanceValidationIssue.scope == "omnichannel")

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

    return ValidationSummaryResponse(
        total=total,
        by_model=by_model,
        by_severity=by_severity,
    )
