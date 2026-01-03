"""Email Templates API - REST endpoints for support notification templates.

Provides endpoints for:
- Template CRUD
- Template rendering and preview
- Template type and placeholder reference
- Default template initialization
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import Principal, Require, get_current_principal
from app.database import get_db
from app.services.support.email_templates import EmailTemplateService
from app.services.support.types import EmailTemplateCreate, EmailTemplateUpdate
from app.services.support.errors import (
    DuplicateTemplateTypeError,
    EmailTemplateNotFoundError,
)

router = APIRouter()

# RBAC dependencies
template_read_dep = Depends(Require("support:templates:read", "support:read"))
template_write_dep = Depends(Require("support:templates:write", "support:write"))


# ---------------------------------------------------------------------------
# Service Dependency
# ---------------------------------------------------------------------------


def get_template_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> EmailTemplateService:
    """Dependency to get an EmailTemplateService instance."""
    return EmailTemplateService(db, principal)


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------


class EmailTemplateCreateRequest(BaseModel):
    """Request to create an email template."""

    name: str = Field(..., min_length=1, max_length=100)
    template_type: str = Field(..., min_length=1, max_length=50)
    subject: str = Field(..., min_length=1)
    body_html: str = Field(..., min_length=1)
    body_text: Optional[str] = None


class EmailTemplateUpdateRequest(BaseModel):
    """Request to update an email template."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    subject: Optional[str] = Field(None, min_length=1)
    body_html: Optional[str] = Field(None, min_length=1)
    body_text: Optional[str] = None
    is_active: Optional[bool] = None


class RenderRequest(BaseModel):
    """Request to render a template."""

    context: Dict[str, Any] = Field(default_factory=dict)


class PreviewRequest(BaseModel):
    """Request to preview a template."""

    sample_context: Optional[Dict[str, Any]] = None


class DuplicateRequest(BaseModel):
    """Request to duplicate a template."""

    new_name: Optional[str] = None
    company: Optional[str] = None


# ---------------------------------------------------------------------------
# Response Serializers
# ---------------------------------------------------------------------------


def serialize_template(template) -> Dict[str, Any]:
    """Serialize an email template for API response."""
    return {
        "id": template.id,
        "company": template.company,
        "name": template.name,
        "template_type": template.template_type,
        "subject": template.subject,
        "body_html": template.body_html,
        "body_text": template.body_text,
        "is_active": template.is_active,
        "supported_placeholders": template.supported_placeholders,
    }


def serialize_rendered(subject: str, body_html: str, body_text: Optional[str]) -> Dict[str, Any]:
    """Serialize rendered template output."""
    return {
        "subject": subject,
        "body_html": body_html,
        "body_text": body_text,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    dependencies=[template_read_dep],
)
def list_templates(
    active_only: bool = True,
    template_type: Optional[str] = None,
    company: Optional[str] = None,
    service: EmailTemplateService = Depends(get_template_service),
) -> Dict[str, Any]:
    """List email templates with optional filtering.

    Args:
        active_only: Only return active templates.
        template_type: Filter by template type.
        company: Filter by company.

    Returns:
        List of templates.
    """
    templates = service.list(
        active_only=active_only,
        template_type=template_type,
        company=company,
    )
    return {
        "count": len(templates),
        "data": [serialize_template(t) for t in templates],
    }


@router.post(
    "",
    dependencies=[template_write_dep],
    status_code=201,
)
def create_template(
    request: EmailTemplateCreateRequest,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
    service: EmailTemplateService = Depends(get_template_service),
) -> Dict[str, Any]:
    """Create a new email template.

    Args:
        request: Template data.
        company: Optional company scope.

    Returns:
        Created template.
    """
    try:
        data = EmailTemplateCreate(
            name=request.name,
            template_type=request.template_type,
            subject=request.subject,
            body_html=request.body_html,
            body_text=request.body_text,
        )
        template = service.create(data, company)
        db.commit()
        return serialize_template(template)
    except DuplicateTemplateTypeError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.get(
    "/types",
    dependencies=[template_read_dep],
)
def get_template_types(
    service: EmailTemplateService = Depends(get_template_service),
) -> Dict[str, Any]:
    """Get list of standard template types.

    Returns:
        List of template type strings.
    """
    types = service.get_template_types()
    return {"types": types}


@router.get(
    "/placeholders",
    dependencies=[template_read_dep],
)
def get_placeholders(
    template_type: Optional[str] = None,
    service: EmailTemplateService = Depends(get_template_service),
) -> Dict[str, Any]:
    """Get available placeholders for templates.

    Args:
        template_type: Optional template type for type-specific placeholders.

    Returns:
        List of placeholder strings.
    """
    placeholders = service.get_placeholders(template_type)
    return {"template_type": template_type, "placeholders": placeholders}


@router.get(
    "/{template_id}",
    dependencies=[template_read_dep],
)
def get_template(
    template_id: int,
    service: EmailTemplateService = Depends(get_template_service),
) -> Dict[str, Any]:
    """Get a template by ID.

    Args:
        template_id: The template ID.

    Returns:
        Template details.
    """
    try:
        template = service.get(template_id)
        return serialize_template(template)
    except EmailTemplateNotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.patch(
    "/{template_id}",
    dependencies=[template_write_dep],
)
def update_template(
    template_id: int,
    request: EmailTemplateUpdateRequest,
    db: Session = Depends(get_db),
    service: EmailTemplateService = Depends(get_template_service),
) -> Dict[str, Any]:
    """Update an email template.

    Args:
        template_id: The template ID.
        request: Update data.

    Returns:
        Updated template.
    """
    try:
        data = EmailTemplateUpdate(
            name=request.name,
            subject=request.subject,
            body_html=request.body_html,
            body_text=request.body_text,
            is_active=request.is_active,
        )
        template = service.update(template_id, data)
        db.commit()
        return serialize_template(template)
    except EmailTemplateNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.delete(
    "/{template_id}",
    dependencies=[template_write_dep],
)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    service: EmailTemplateService = Depends(get_template_service),
) -> Response:
    """Delete an email template.

    Args:
        template_id: The template ID.

    Returns:
        204 No Content on success.
    """
    try:
        service.delete(template_id)
        db.commit()
        return Response(status_code=204)
    except EmailTemplateNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/{template_id}/duplicate",
    dependencies=[template_write_dep],
    status_code=201,
)
def duplicate_template(
    template_id: int,
    request: DuplicateRequest,
    db: Session = Depends(get_db),
    service: EmailTemplateService = Depends(get_template_service),
) -> Dict[str, Any]:
    """Duplicate an existing template.

    Args:
        template_id: The template ID to duplicate.
        request: Duplicate options.

    Returns:
        New template.
    """
    try:
        template = service.duplicate(
            template_id,
            new_name=request.new_name,
            company=request.company,
        )
        db.commit()
        return serialize_template(template)
    except EmailTemplateNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/{template_id}/preview",
    dependencies=[template_read_dep],
)
def preview_template(
    template_id: int,
    request: PreviewRequest,
    service: EmailTemplateService = Depends(get_template_service),
) -> Dict[str, Any]:
    """Preview a template with sample data.

    Args:
        template_id: The template ID.
        request: Optional sample context.

    Returns:
        Rendered template.
    """
    try:
        subject, body_html, body_text = service.preview(
            template_id,
            sample_context=request.sample_context,
        )
        return serialize_rendered(subject, body_html, body_text)
    except EmailTemplateNotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/{template_id}/render",
    dependencies=[template_read_dep],
)
def render_template(
    template_id: int,
    request: RenderRequest,
    service: EmailTemplateService = Depends(get_template_service),
) -> Dict[str, Any]:
    """Render a template with context data.

    Args:
        template_id: The template ID.
        request: Context data for placeholders.

    Returns:
        Rendered template.
    """
    try:
        subject, body_html, body_text = service.render(template_id, request.context)
        return serialize_rendered(subject, body_html, body_text)
    except EmailTemplateNotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/{template_id}/validate",
    dependencies=[template_read_dep],
)
def validate_template(
    template_id: int,
    service: EmailTemplateService = Depends(get_template_service),
) -> Dict[str, Any]:
    """Validate a template for common issues.

    Args:
        template_id: The template ID.

    Returns:
        Validation result.
    """
    try:
        is_valid, issues = service.validate_template(template_id)
        return {
            "template_id": template_id,
            "is_valid": is_valid,
            "issues": issues,
        }
    except EmailTemplateNotFoundError as exc:
        raise HTTPException(status_code=exc.http_code, detail=exc.message)


@router.post(
    "/ensure-defaults",
    dependencies=[template_write_dep],
)
def ensure_default_templates(
    company: Optional[str] = None,
    db: Session = Depends(get_db),
    service: EmailTemplateService = Depends(get_template_service),
) -> Dict[str, Any]:
    """Ensure default templates exist.

    Creates standard notification templates if they don't exist.

    Args:
        company: Optional company scope.

    Returns:
        List of templates (existing or newly created).
    """
    templates = service.ensure_default_templates(company)
    db.commit()
    return {
        "count": len(templates),
        "data": [serialize_template(t) for t in templates],
    }
