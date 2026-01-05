"""Shared schemas for soft validation endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SoftValidationRequest(BaseModel):
    """Request payload to run soft validation on records."""

    models: Optional[List[str]] = Field(
        default=None,
        description="Optional list of model names to validate.",
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


class ValidationIssueItem(BaseModel):
    id: int
    model_name: str
    record_id: int
    scope: str
    issues: List[dict]
    detected_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ValidationIssueList(BaseModel):
    data: List[ValidationIssueItem]
    total: int
    limit: int
    offset: int


class ValidationSummaryResponse(BaseModel):
    total: int
    by_model: List[Dict[str, object]]
    by_severity: List[Dict[str, object]]
