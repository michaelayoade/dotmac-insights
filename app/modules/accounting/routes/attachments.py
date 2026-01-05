"""
Attachments routes for accounting module.

Provides HTMX endpoints for attachment management within document detail pages.
"""
import os
from fastapi import APIRouter, UploadFile, File, Form

from ._deps import (
    Request, Response, HTMLResponse, Optional,
    SessionUser, CSRFToken, CSRFProtect, DB,
    RequireAccountingRead, RequireAccountingWrite,
    templates,
    get_base_context, validate_csrf, HTTPException,
)
from app.services.accounting import DocumentAttachmentService
from app.services.accounting.web_services import AccountingAttachmentsWebService
from app.services.accounting.attachments_types import AttachmentUploadData
from app.services.errors import NotFoundError

router = APIRouter()


def _get_service(db: DB, user: SessionUser) -> DocumentAttachmentService:
    return DocumentAttachmentService(db, user)


def _get_web_service(db: DB, user: SessionUser) -> AccountingAttachmentsWebService:
    return AccountingAttachmentsWebService(db, _get_service(db, user))


@router.get("/documents/{doctype}/{doc_id}/attachments", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def get_attachments_panel(
    doctype: str,
    doc_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Get attachments panel for a document (HTMX partial)."""
    service = _get_service(db, user)
    web_service = _get_web_service(db, user)
    attachments = service.list_attachments(doctype, doc_id)

    context = get_base_context(request, response, user, csrf_token)
    context["doctype"] = doctype
    context["document_id"] = doc_id
    context["attachments"] = attachments
    context["can_edit"] = True

    template = templates.get_template("modules/accounting/templates/attachments/partials/attachments_panel.html")
    return HTMLResponse(template.render(context))


@router.post("/documents/{doctype}/{doc_id}/attachments", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def upload_attachment(
    doctype: str,
    doc_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf_protect: CSRFProtect,
    db: DB,
    file: UploadFile = File(...),
    attachment_type: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    is_primary: bool = Form(False),
):
    """Upload an attachment for a document (HTMX)."""
    await validate_csrf(request, csrf_protect)

    service = _get_service(db, user)

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Validate file
    validation = service.validate_file(file.filename or "", file_size)
    if not validation.is_valid:
        raise HTTPException(status_code=400, detail=validation.error)

    # Ensure upload directory exists
    service.ensure_upload_directory(doctype, doc_id)

    # Get file path for storage
    file_path = service.get_upload_path(doctype, doc_id, validation.sanitized_filename)

    # Write file to disk
    with open(file_path, "wb") as f:
        f.write(content)

    # Create attachment record
    upload_data = AttachmentUploadData(
        doctype=doctype,
        document_id=doc_id,
        file_name=file.filename or "upload",
        file_path=file_path,
        file_type=file.content_type,
        file_size=file_size,
        attachment_type=attachment_type,
        description=description,
        is_primary=is_primary,
    )

    web_service.create_attachment(upload_data)

    # Return updated attachments panel
    attachments = service.list_attachments(doctype, doc_id)

    context = get_base_context(request, response, user, csrf_token)
    context["doctype"] = doctype
    context["document_id"] = doc_id
    context["attachments"] = attachments
    context["can_edit"] = True

    template = templates.get_template("modules/accounting/templates/attachments/partials/attachments_panel.html")
    return HTMLResponse(template.render(context))


@router.delete("/documents/{doctype}/{doc_id}/attachments/{attachment_id}", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def delete_attachment(
    doctype: str,
    doc_id: int,
    attachment_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_protect: CSRFProtect,
    db: DB,
):
    """Delete an attachment (HTMX)."""
    await validate_csrf(request, csrf_protect)

    service = _get_service(db, user)
    web_service = _get_web_service(db, user)

    try:
        # Delete record and get file path
        file_path = web_service.delete_attachment(attachment_id)

        # Delete file from disk
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass  # File might already be deleted

        # Return empty response (element will be removed)
        return HTMLResponse("")

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/documents/{doctype}/{doc_id}/attachments/{attachment_id}/primary", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def set_primary_attachment(
    doctype: str,
    doc_id: int,
    attachment_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf_protect: CSRFProtect,
    db: DB,
):
    """Set an attachment as primary (HTMX)."""
    await validate_csrf(request, csrf_protect)

    service = _get_service(db, user)
    web_service = _get_web_service(db, user)

    try:
        web_service.set_primary(attachment_id)

        # Return updated attachments panel
        attachments = service.list_attachments(doctype, doc_id)

        context = get_base_context(request, response, user, csrf_token)
        context["doctype"] = doctype
        context["document_id"] = doc_id
        context["attachments"] = attachments
        context["can_edit"] = True

        template = templates.get_template("modules/accounting/templates/attachments/partials/attachments_panel.html")
        return HTMLResponse(template.render(context))

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
