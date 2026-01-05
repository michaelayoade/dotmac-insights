"""
HR Recruitment Routes - Recruitment Management with SSR + HTMX.

Permission Requirements:
- hr:read - View job openings, applicants, offers, interviews
- hr:write - Manage recruitment
"""
from typing import Optional, Any
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.core.security import is_htmx_request, htmx_toast, set_flash
from app.models.hr_recruitment import (
    Interview,
    JobApplicant,
    JobApplicantStatus,
    JobOpeningStatus,
)
from app.services.hr.recruitment import RecruitmentService
from app.services.hr.organization import OrganizationService
from app.services.hr.recruitment_types import (
    ApplicantFilters,
    ApplicantPipelineMove,
    InterviewFilters,
    InterviewScheduleData,
    InterviewUpdateData,
    JobOfferCreateData,
    JobOfferFilters,
    JobOfferUpdateData,
    JobOpeningCreateData,
    JobOpeningFilters,
    JobOpeningUpdateData,
)
from app.services.types import PaginationParams
from app.services.hr.errors import (
    ApplicantNotFoundError,
    ApplicantPipelineError,
    DepartmentNotFoundError,
    DesignationNotFoundError,
    InterviewNotFoundError,
    JobOfferNotFoundError,
    JobOpeningNotFoundError,
    ValidationError,
)

RequireHRRead = Depends(require_scope("hr:read"))
RequireHRWrite = Depends(require_scope("hr:write"))

router = APIRouter(prefix="/recruitment", tags=["hr-recruitment"])
templates = get_template_env()


def _form_str(form: Any, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


def _form_int(form: Any, key: str) -> Optional[int]:
    value = _form_str(form, key, "")
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _form_date(form: Any, key: str) -> Optional[date]:
    value = _form_str(form, key, "")
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _form_datetime(form: Any, key: str) -> Optional[datetime]:
    value = _form_str(form, key, "")
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _form_decimal(form: Any, key: str) -> Optional[Decimal]:
    value = _form_str(form, key, "")
    if not value:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def _normalize_enum(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _job_opening_status(value: str) -> Optional[JobOpeningStatus]:
    if not value:
        return None
    try:
        return JobOpeningStatus(_normalize_enum(value))
    except ValueError:
        return None


def _format_datetime_input(value: Optional[datetime]) -> str:
    if not value:
        return ""
    return value.strftime("%Y-%m-%dT%H:%M")


def _format_date_input(value: Optional[date]) -> str:
    if not value:
        return ""
    return value.strftime("%Y-%m-%d")


def _format_datetime_display(value: Optional[datetime]) -> str:
    if not value:
        return "-"
    return value.strftime("%b %d, %Y %H:%M")


def _format_date_display(value: Optional[date]) -> str:
    if not value:
        return "-"
    return value.strftime("%b %d, %Y")


def _status_label(value: Any) -> str:
    if not value:
        return ""
    raw = value.value if hasattr(value, "value") else str(value)
    return raw.replace("_", " ").title()


def _offer_status_label(value: Any) -> str:
    if not value:
        return ""
    raw = value.value if hasattr(value, "value") else str(value)
    if raw == "pending":
        return "Draft"
    return raw.replace("_", " ").title()


def _applicant_status(value: str) -> Optional[JobApplicantStatus]:
    if not value:
        return None
    try:
        return JobApplicantStatus(_normalize_enum(value))
    except ValueError:
        return None


def get_department_options(db):
    service = OrganizationService(db)
    result = service.list_departments(pagination=PaginationParams(offset=0, limit=500))
    departments = sorted(result.items, key=lambda d: d.department_name or "")
    return [{"value": str(d.id), "label": d.department_name} for d in departments]


def get_designation_options(db):
    service = OrganizationService(db)
    result = service.list_designations(pagination=PaginationParams(offset=0, limit=500))
    designations = sorted(result.items, key=lambda d: d.designation_name or "")
    return [{"value": str(d.id), "label": d.designation_name} for d in designations]


def get_applicant_options(db):
    service = RecruitmentService(db)
    result = service.list_applicants(pagination=PaginationParams(offset=0, limit=500))
    applicants = sorted(result.items, key=lambda a: a.applicant_name or "")
    return [{"value": str(a.id), "label": a.applicant_name} for a in applicants]


def _build_interview_form_data(interview: Interview) -> dict[str, Any]:
    return {
        "applicant_id": str(interview.job_applicant_id) if interview.job_applicant_id else "",
        "scheduled_date": _format_datetime_input(interview.scheduled_date),
        "interviewer_name": interview.interviewer_name or "",
        "interview_type": interview.interview_type or "",
        "duration_minutes": interview.duration_minutes or 60,
        "location": interview.location or "",
        "meeting_link": interview.meeting_link or "",
        "notes": interview.notes or "",
    }


def _build_offer_form_data(offer) -> dict[str, Any]:
    return {
        "applicant_id": str(offer.job_applicant_id) if offer.job_applicant_id else "",
        "offer_date": _format_date_input(offer.offer_date),
        "expiry_date": _format_date_input(offer.expiry_date),
        "designation": offer.designation or "",
        "salary_structure": offer.salary_structure or "",
        "base": str(offer.base) if offer.base is not None else "",
    }


def _enrich_interview_display(interview: Interview, applicant: Optional[JobApplicant]) -> None:
    interview.applicant_name = applicant.applicant_name if applicant else None
    interview.job_opening = (applicant.job_opening or applicant.job_title) if applicant else None
    interview.scheduled_on = _format_datetime_display(interview.scheduled_date)
    interview.interviewer = interview.interviewer_name
    interview.status_label = _status_label(interview.status)
    interview.result_label = _status_label(interview.result)


def _enrich_offer_display(offer, applicant: Optional[JobApplicant]) -> None:
    if applicant and not offer.applicant_name:
        offer.applicant_name = applicant.applicant_name
    offer.job_title = (applicant.job_title or applicant.job_opening) if applicant else None
    offer.offer_salary = offer.base
    offer.status_label = _offer_status_label(offer.status)


def _render_opening_form(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    *,
    opening=None,
    errors: Optional[dict] = None,
    form_data: Optional[dict] = None,
):
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Job Opening"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Recruitment", "href": "/hr/recruitment"},
        {"label": "Job Opening"},
    ])
    context["opening"] = opening
    context["department_options"] = get_department_options(db)
    context["designation_options"] = get_designation_options(db)
    context["errors"] = errors or {}
    context["form_data"] = form_data

    template = templates.get_template("modules/hr/templates/recruitment/pages/opening_form.html")
    return HTMLResponse(template.render(context), status_code=422 if errors else 200)


def _render_interview_form(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    *,
    interview: Optional[Interview] = None,
    errors: Optional[dict] = None,
    form_data: Optional[dict] = None,
    applicant_id: Optional[int] = None,
):
    if form_data is None:
        form_data = _build_interview_form_data(interview) if interview else {}
    selected_applicant = (
        str(form_data.get("applicant_id"))
        if form_data.get("applicant_id")
        else (str(applicant_id) if applicant_id else (str(interview.job_applicant_id) if interview else ""))
    )
    form_title = "Edit Interview" if interview else "Schedule Interview"
    form_subtitle = "Update interview details for an applicant" if interview else "Set interview details for an applicant"

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = form_title
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Recruitment", "href": "/hr/recruitment"},
        {"label": form_title},
    ])
    context["applicant_options"] = get_applicant_options(db)
    context["errors"] = errors or {}
    context["form_data"] = form_data
    context["selected_applicant_id"] = selected_applicant
    context["interview"] = interview
    context["form_action"] = f"/hr/recruitment/interviews/{interview.id}" if interview else "/hr/recruitment/interviews"
    context["submit_label"] = "Update Interview" if interview else "Schedule Interview"
    context["form_title"] = form_title
    context["form_subtitle"] = form_subtitle
    context["cancel_href"] = f"/hr/recruitment/interviews/{interview.id}" if interview else "/hr/recruitment/interviews"

    template = templates.get_template("modules/hr/templates/recruitment/pages/interview_form.html")
    return HTMLResponse(template.render(context), status_code=422 if errors else 200)


def _render_offer_form(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    *,
    offer=None,
    errors: Optional[dict] = None,
    form_data: Optional[dict] = None,
    applicant_id: Optional[int] = None,
):
    if form_data is None:
        form_data = _build_offer_form_data(offer) if offer else {}
    selected_applicant = (
        str(form_data.get("applicant_id"))
        if form_data.get("applicant_id")
        else (str(applicant_id) if applicant_id else (str(offer.job_applicant_id) if offer else ""))
    )
    form_title = "Edit Job Offer" if offer else "Create Job Offer"
    form_subtitle = "Update the offer details for an applicant" if offer else "Prepare an offer for an applicant"

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = form_title
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Recruitment", "href": "/hr/recruitment"},
        {"label": form_title},
    ])
    context["applicant_options"] = get_applicant_options(db)
    context["errors"] = errors or {}
    context["form_data"] = form_data
    context["selected_applicant_id"] = selected_applicant
    context["offer"] = offer
    context["form_action"] = f"/hr/recruitment/offers/{offer.id}" if offer else "/hr/recruitment/offers"
    context["submit_label"] = "Update Offer" if offer else "Create Offer"
    context["form_title"] = form_title
    context["form_subtitle"] = form_subtitle
    context["cancel_href"] = f"/hr/recruitment/offers/{offer.id}" if offer else "/hr/recruitment/offers"

    template = templates.get_template("modules/hr/templates/recruitment/pages/offer_form.html")
    return HTMLResponse(template.render(context), status_code=422 if errors else 200)


@router.get("", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def job_openings_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Job openings list page."""
    service = RecruitmentService(db, user)

    # Build filters
    filters = JobOpeningFilters(
        search=q,
        status=_job_opening_status(status) if status else None,
        department_id=_form_int({"department": department}, "department") if department else None,
    )
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    # Get openings via service
    result = service.list_job_openings(filters=filters, pagination=pagination)

    context = get_base_context(request, response, user, csrf_token)
    context["openings"] = result.items
    context["search_query"] = q or ""
    context["status"] = status
    context["department"] = department
    context["department_options"] = get_department_options(db)
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/recruitment/partials/openings_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Job Openings"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Recruitment"},
    ])

    template = templates.get_template("modules/hr/templates/recruitment/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def job_opening_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New job opening form."""
    return _render_opening_form(request, response, user, csrf_token, db)


@router.get("/{opening_id}/edit", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def job_opening_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    opening_id: int,
):
    """Edit job opening form."""
    service = RecruitmentService(db, user)
    try:
        opening = service.get_job_opening(opening_id)
    except JobOpeningNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return _render_opening_form(request, response, user, csrf_token, db, opening=opening)


@router.post("", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def job_opening_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    csrf: CSRFProtect,
):
    """Create a job opening."""
    form = await request.form()
    errors: dict[str, str] = {}

    job_title = _form_str(form, "job_title")
    if not job_title:
        errors["job_title"] = "Job title is required"

    department_id = _form_int(form, "department")
    designation_id = _form_int(form, "designation")
    org_service = OrganizationService(db, user)
    department = None
    designation = None
    if department_id:
        try:
            department = org_service.get_department(department_id)
        except DepartmentNotFoundError:
            department = None
            errors["department"] = "Department not found"
    if designation_id:
        try:
            designation = org_service.get_designation(designation_id)
        except DesignationNotFoundError:
            designation = None
            errors["designation"] = "Designation not found"

    if errors:
        return _render_opening_form(
            request,
            response,
            user,
            csrf_token,
            db,
            errors=errors,
            form_data=dict(form),
        )

    service = RecruitmentService(db, user)
    opening = service.create_job_opening(
        JobOpeningCreateData(
            job_title=job_title,
            department_id=department_id,
            department=department.department_name if department else None,
            designation_id=designation_id,
            designation=designation.designation_name if designation else None,
            description=_form_str(form, "description") or None,
        )
    )
    status = _job_opening_status(_form_str(form, "status"))
    if status and status != JobOpeningStatus.OPEN:
        service.update_job_opening(opening.id, JobOpeningUpdateData(status=status))

    db.commit()

    set_flash(response, "Job opening created successfully.", "success")
    return RedirectResponse(url=f"/hr/recruitment/{opening.id}", status_code=303)


@router.post("/{opening_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def job_opening_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    csrf: CSRFProtect,
    opening_id: int,
):
    """Update a job opening."""
    form = await request.form()
    errors: dict[str, str] = {}

    job_title = _form_str(form, "job_title")
    if not job_title:
        errors["job_title"] = "Job title is required"

    department_id = _form_int(form, "department")
    designation_id = _form_int(form, "designation")
    org_service = OrganizationService(db, user)
    department = None
    designation = None
    if department_id:
        try:
            department = org_service.get_department(department_id)
        except DepartmentNotFoundError:
            department = None
            errors["department"] = "Department not found"
    if designation_id:
        try:
            designation = org_service.get_designation(designation_id)
        except DesignationNotFoundError:
            designation = None
            errors["designation"] = "Designation not found"

    if errors:
        service = RecruitmentService(db, user)
        try:
            opening = service.get_job_opening(opening_id)
        except JobOpeningNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return _render_opening_form(
            request,
            response,
            user,
            csrf_token,
            db,
            opening=opening,
            errors=errors,
            form_data=dict(form),
        )

    service = RecruitmentService(db, user)
    try:
        opening = service.update_job_opening(
            opening_id,
            JobOpeningUpdateData(
                job_title=job_title,
                department_id=department_id,
                department=department.department_name if department else None,
                designation_id=designation_id,
                designation=designation.designation_name if designation else None,
                description=_form_str(form, "description") or None,
                status=_job_opening_status(_form_str(form, "status")),
            ),
        )
    except JobOpeningNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    db.commit()

    set_flash(response, "Job opening updated successfully.", "success")
    return RedirectResponse(url=f"/hr/recruitment/{opening.id}", status_code=303)


@router.post("/{opening_id}/close", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def job_opening_close(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    opening_id: int,
):
    """Close a job opening."""
    service = RecruitmentService(db, user)
    try:
        opening = service.close_job_opening(opening_id)
        db.commit()
    except JobOpeningNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))

    if is_htmx_request(request):
        htmx_toast(response, "Job opening closed.", "success")
        response.headers["HX-Redirect"] = f"/hr/recruitment/{opening.id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Job opening closed.", "success")
    return RedirectResponse(url=f"/hr/recruitment/{opening.id}", status_code=303)


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def job_openings_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    return await job_openings_list(request, response, user, csrf_token, db, q, page, per_page)


@router.get("/applicants", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def applicants_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Job applicants list page."""
    service = RecruitmentService(db, user)

    # Build filters
    filters = ApplicantFilters(search=q) if q else None
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    # Get applicants via service
    result = service.list_applicants(filters=filters, pagination=pagination)

    context = get_base_context(request, response, user, csrf_token)
    context["applicants"] = result.items
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/recruitment/partials/applicants_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Job Applicants"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Applicants"},
    ])

    template = templates.get_template("modules/hr/templates/recruitment/pages/applicants_list.html")
    return HTMLResponse(template.render(context))


@router.get("/applicants/{applicant_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def applicant_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    applicant_id: int,
):
    """Applicant detail page."""
    service = RecruitmentService(db, user)
    try:
        applicant = service.get_applicant(applicant_id)
    except ApplicantNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    interviews_result = service.list_interviews(
        filters=InterviewFilters(job_applicant_id=applicant_id),
        pagination=PaginationParams(offset=0, limit=200),
    )
    interviews = interviews_result.items
    for interview in interviews:
        _enrich_interview_display(interview, applicant)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = applicant.applicant_name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Recruitment", "href": "/hr/recruitment"},
        {"label": "Applicants", "href": "/hr/recruitment/applicants"},
        {"label": applicant.applicant_name},
    ])
    context["applicant"] = applicant
    context["interviews"] = interviews

    template = templates.get_template("modules/hr/templates/recruitment/pages/applicant_detail.html")
    return HTMLResponse(template.render(context))


@router.post("/applicants/{applicant_id}/status", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def applicant_update_status(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    applicant_id: int,
):
    """Update applicant pipeline status."""
    form = await request.form()
    status_raw = _form_str(form, "status")
    target_status = _applicant_status(status_raw)
    if not target_status:
        return RedirectResponse(
            url=f"/hr/recruitment/applicants/{applicant_id}", status_code=303
        )

    service = RecruitmentService(db, user)
    try:
        service.advance_applicant(
            applicant_id, ApplicantPipelineMove(to_status=target_status)
        )
        db.commit()
    except ApplicantNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except (ApplicantPipelineError, ValidationError) as exc:
        db.rollback()
        if is_htmx_request(request):
            htmx_toast(response, str(exc), "error")
            response.headers["HX-Redirect"] = f"/hr/recruitment/applicants/{applicant_id}"
            return HTMLResponse("", headers=dict(response.headers))
        set_flash(response, str(exc), "error")
        return RedirectResponse(
            url=f"/hr/recruitment/applicants/{applicant_id}", status_code=303
        )

    if is_htmx_request(request):
        htmx_toast(response, "Applicant status updated.", "success")
        response.headers["HX-Redirect"] = f"/hr/recruitment/applicants/{applicant_id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Applicant status updated.", "success")
    return RedirectResponse(url=f"/hr/recruitment/applicants/{applicant_id}", status_code=303)


@router.get("/offers", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def offers_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Job offers list page."""
    service = RecruitmentService(db, user)

    # Build filters
    filters = JobOfferFilters(search=q) if q else None
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    # Get offers via service
    result = service.list_job_offers(filters=filters, pagination=pagination)
    offers = result.items

    # Enrich display data
    applicant_ids = [offer.job_applicant_id for offer in offers if offer.job_applicant_id]
    if applicant_ids:
        applicants = service.get_applicants_by_ids(applicant_ids)
        applicants_map = {applicant.id: applicant for applicant in applicants}
        for offer in offers:
            _enrich_offer_display(offer, applicants_map.get(offer.job_applicant_id))

    context = get_base_context(request, response, user, csrf_token)
    context["offers"] = offers
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/recruitment/partials/offers_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Job Offers"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Job Offers"},
    ])

    template = templates.get_template("modules/hr/templates/recruitment/pages/offers_list.html")
    return HTMLResponse(template.render(context))


@router.get("/interviews", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def interviews_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Interviews list page."""
    service = RecruitmentService(db, user)

    # Build filters
    filters = InterviewFilters(search=q) if q else None
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    # Get interviews via service
    result = service.list_interviews(filters=filters, pagination=pagination)
    interviews = result.items

    # Enrich display data
    applicant_ids = [interview.job_applicant_id for interview in interviews if interview.job_applicant_id]
    if applicant_ids:
        applicants = service.get_applicants_by_ids(applicant_ids)
        applicants_map = {applicant.id: applicant for applicant in applicants}
        for interview in interviews:
            _enrich_interview_display(interview, applicants_map.get(interview.job_applicant_id))

    context = get_base_context(request, response, user, csrf_token)
    context["interviews"] = interviews
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/recruitment/partials/interviews_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Interviews"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Interviews"},
    ])

    template = templates.get_template("modules/hr/templates/recruitment/pages/interviews_list.html")
    return HTMLResponse(template.render(context))


@router.get("/interviews/new", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def interview_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    applicant: Optional[int] = Query(None),
):
    """Schedule interview form."""
    return _render_interview_form(
        request,
        response,
        user,
        csrf_token,
        db,
        applicant_id=applicant,
    )


@router.post("/interviews", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def interview_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    csrf: CSRFProtect,
):
    """Schedule an interview."""
    form = await request.form()
    errors: dict[str, str] = {}

    applicant_id = _form_int(form, "applicant_id")
    scheduled_date = _form_datetime(form, "scheduled_date")
    interviewer_name = _form_str(form, "interviewer_name") or None
    interview_type = _form_str(form, "interview_type") or None
    duration_minutes = _form_int(form, "duration_minutes") or 60
    location = _form_str(form, "location") or None
    meeting_link = _form_str(form, "meeting_link") or None
    notes = _form_str(form, "notes") or None

    if not applicant_id:
        errors["applicant_id"] = "Applicant is required"
    if not scheduled_date:
        errors["scheduled_date"] = "Scheduled date is required"

    service = RecruitmentService(db, user)
    applicant = None
    if applicant_id:
        try:
            applicant = service.get_applicant(applicant_id)
        except ApplicantNotFoundError:
            applicant = None
    if applicant_id and not applicant:
        errors["applicant_id"] = "Applicant not found"

    if errors:
        return _render_interview_form(
            request,
            response,
            user,
            csrf_token,
            db,
            errors=errors,
            form_data=dict(form),
            applicant_id=applicant_id,
        )

    try:
        interview = service.schedule_interview(
            InterviewScheduleData(
                job_applicant_id=applicant_id,
                scheduled_date=scheduled_date,
                interviewer_name=interviewer_name,
                interview_type=interview_type,
                duration_minutes=duration_minutes,
                location=location,
                meeting_link=meeting_link,
                notes=notes,
            )
        )
        db.commit()
    except (ApplicantNotFoundError, ValidationError) as exc:
        db.rollback()
        errors["applicant_id"] = str(exc)
        return _render_interview_form(
            request,
            response,
            user,
            csrf_token,
            db,
            errors=errors,
            form_data=dict(form),
            applicant_id=applicant_id,
        )

    set_flash(response, "Interview scheduled.", "success")
    return RedirectResponse(
        url=f"/hr/recruitment/applicants/{interview.job_applicant_id}",
        status_code=303,
    )


@router.get("/interviews/{interview_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def interview_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    interview_id: int,
):
    """Interview detail page."""
    service = RecruitmentService(db, user)
    try:
        interview = service.get_interview(interview_id)
    except InterviewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    applicant = None
    if interview.job_applicant_id:
        try:
            applicant = service.get_applicant(interview.job_applicant_id)
        except ApplicantNotFoundError:
            applicant = None
    _enrich_interview_display(interview, applicant)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = interview.applicant_name or f"Interview #{interview.id}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Recruitment", "href": "/hr/recruitment"},
        {"label": "Interviews", "href": "/hr/recruitment/interviews"},
        {"label": interview.applicant_name or f"Interview #{interview.id}"},
    ])
    context["interview"] = interview
    context["applicant"] = applicant

    template = templates.get_template("modules/hr/templates/recruitment/pages/interview_detail.html")
    return HTMLResponse(template.render(context))


@router.get("/interviews/{interview_id}/edit", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def interview_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    interview_id: int,
):
    """Edit interview form."""
    service = RecruitmentService(db, user)
    try:
        interview = service.get_interview(interview_id)
    except InterviewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return _render_interview_form(
        request,
        response,
        user,
        csrf_token,
        db,
        interview=interview,
    )


@router.post("/interviews/{interview_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def interview_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    csrf: CSRFProtect,
    interview_id: int,
):
    """Update an interview."""
    form = await request.form()
    errors: dict[str, str] = {}

    scheduled_date = _form_datetime(form, "scheduled_date")
    interviewer_name = _form_str(form, "interviewer_name") or None
    interview_type = _form_str(form, "interview_type") or None
    duration_minutes = _form_int(form, "duration_minutes") or 60
    location = _form_str(form, "location") or None
    meeting_link = _form_str(form, "meeting_link") or None
    notes = _form_str(form, "notes") or None

    if not scheduled_date:
        errors["scheduled_date"] = "Scheduled date is required"

    service = RecruitmentService(db, user)
    try:
        interview = service.get_interview(interview_id)
    except InterviewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if errors:
        return _render_interview_form(
            request,
            response,
            user,
            csrf_token,
            db,
            interview=interview,
            errors=errors,
            form_data=dict(form),
        )

    service.update_interview(
        interview_id,
        InterviewUpdateData(
            scheduled_date=scheduled_date,
            interviewer_name=interviewer_name,
            interview_type=interview_type,
            duration_minutes=duration_minutes,
            location=location,
            meeting_link=meeting_link,
            notes=notes,
        ),
    )
    db.commit()

    set_flash(response, "Interview updated.", "success")
    return RedirectResponse(
        url=f"/hr/recruitment/interviews/{interview_id}",
        status_code=303,
    )


@router.get("/offers/new", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def offer_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    applicant: Optional[int] = Query(None),
):
    """Create offer form."""
    return _render_offer_form(
        request,
        response,
        user,
        csrf_token,
        db,
        applicant_id=applicant,
    )


@router.post("/offers", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def offer_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    csrf: CSRFProtect,
):
    """Create a job offer."""
    form = await request.form()
    errors: dict[str, str] = {}

    applicant_id = _form_int(form, "applicant_id")
    offer_date = _form_date(form, "offer_date")
    base = _form_decimal(form, "base")
    designation = _form_str(form, "designation") or None
    salary_structure = _form_str(form, "salary_structure") or None
    expiry_date = _form_date(form, "expiry_date")

    if not applicant_id:
        errors["applicant_id"] = "Applicant is required"
    if not offer_date:
        errors["offer_date"] = "Offer date is required"

    service = RecruitmentService(db, user)
    applicant = None
    if applicant_id:
        try:
            applicant = service.get_applicant(applicant_id)
        except ApplicantNotFoundError:
            applicant = None
    if applicant_id and not applicant:
        errors["applicant_id"] = "Applicant not found"

    if base is None:
        errors["base"] = "Base salary is required"

    if errors:
        return _render_offer_form(
            request,
            response,
            user,
            csrf_token,
            db,
            errors=errors,
            form_data=dict(form),
            applicant_id=applicant_id,
        )

    try:
        offer = service.create_job_offer(
            JobOfferCreateData(
                job_applicant_id=applicant_id,
                job_applicant=applicant.erpnext_id or str(applicant.id),
                applicant_name=applicant.applicant_name,
                applicant_email=applicant.email_id,
                offer_date=offer_date,
                designation=designation,
                base=base,
                salary_structure=salary_structure,
                company=applicant.company,
                expiry_date=expiry_date,
            )
        )
        db.commit()
    except (ApplicantNotFoundError, ValidationError) as exc:
        db.rollback()
        errors["applicant_id"] = str(exc)
        return _render_offer_form(
            request,
            response,
            user,
            csrf_token,
            db,
            errors=errors,
            form_data=dict(form),
            applicant_id=applicant_id,
        )

    set_flash(response, "Job offer created.", "success")
    return RedirectResponse(
        url=f"/hr/recruitment/offers",
        status_code=303,
    )


@router.get("/offers/{offer_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def offer_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    offer_id: int,
):
    """Job offer detail page."""
    service = RecruitmentService(db, user)
    try:
        offer = service.get_job_offer(offer_id)
    except JobOfferNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    applicant = None
    if offer.job_applicant_id:
        try:
            applicant = service.get_applicant(offer.job_applicant_id)
        except ApplicantNotFoundError:
            applicant = None
    _enrich_offer_display(offer, applicant)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = offer.applicant_name or f"Offer #{offer.id}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Recruitment", "href": "/hr/recruitment"},
        {"label": "Job Offers", "href": "/hr/recruitment/offers"},
        {"label": offer.applicant_name or f"Offer #{offer.id}"},
    ])
    context["offer"] = offer
    context["applicant"] = applicant
    context["offer_date_display"] = _format_date_display(offer.offer_date)
    context["expiry_date_display"] = _format_date_display(offer.expiry_date)

    template = templates.get_template("modules/hr/templates/recruitment/pages/offer_detail.html")
    return HTMLResponse(template.render(context))


@router.get("/offers/{offer_id}/edit", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def offer_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    offer_id: int,
):
    """Edit job offer form."""
    service = RecruitmentService(db, user)
    try:
        offer = service.get_job_offer(offer_id)
    except JobOfferNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return _render_offer_form(
        request,
        response,
        user,
        csrf_token,
        db,
        offer=offer,
    )


@router.post("/offers/{offer_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def offer_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    csrf: CSRFProtect,
    offer_id: int,
):
    """Update a job offer."""
    form = await request.form()
    errors: dict[str, str] = {}

    offer_date = _form_date(form, "offer_date")
    base = _form_decimal(form, "base")
    designation = _form_str(form, "designation") or None
    salary_structure = _form_str(form, "salary_structure") or None
    expiry_date = _form_date(form, "expiry_date")

    if not offer_date:
        errors["offer_date"] = "Offer date is required"
    if base is None:
        errors["base"] = "Base salary is required"

    service = RecruitmentService(db, user)
    try:
        offer = service.get_job_offer(offer_id)
    except JobOfferNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if errors:
        return _render_offer_form(
            request,
            response,
            user,
            csrf_token,
            db,
            offer=offer,
            errors=errors,
            form_data=dict(form),
        )

    try:
        service.update_job_offer(
            offer_id,
            JobOfferUpdateData(
                offer_date=offer_date,
                designation=designation,
                base=base,
                salary_structure=salary_structure,
                expiry_date=expiry_date,
            ),
        )
        db.commit()
    except ApplicantPipelineError as exc:
        db.rollback()
        set_flash(response, str(exc), "error")
        return RedirectResponse(
            url=f"/hr/recruitment/offers/{offer_id}",
            status_code=303,
        )

    set_flash(response, "Job offer updated.", "success")
    return RedirectResponse(
        url=f"/hr/recruitment/offers/{offer_id}",
        status_code=303,
    )


@router.get("/{opening_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def job_opening_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    opening_id: int,
):
    """Job opening detail page."""
    service = RecruitmentService(db, user)

    try:
        opening = service.get_job_opening(opening_id)
    except JobOpeningNotFoundError:
        raise HTTPException(status_code=404, detail="Job opening not found")

    # Get applicants for this opening
    applicant_filters = ApplicantFilters(job_opening_id=opening_id)
    applicants_result = service.list_applicants(filters=applicant_filters)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = opening.job_title
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Recruitment", "href": "/hr/recruitment"},
        {"label": opening.job_title},
    ])
    context["opening"] = opening
    context["applicants"] = applicants_result.items

    template = templates.get_template("modules/hr/templates/recruitment/pages/opening_detail.html")
    return HTMLResponse(template.render(context))
