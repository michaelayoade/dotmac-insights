"""
Books Settings Routes - Accounting module configuration.

Handles currency, fiscal year, document numbering, and display settings.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response, Depends, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import get_base_context, get_navigation_context, build_breadcrumbs
from app.templates.environment import get_template_env
from app.core.security import is_htmx_request, set_flash
from app.models.books_settings import (
    BooksSettings, DocumentNumberFormat, CurrencySettings,
    DocumentType, ResetFrequency, RoundingMethod, NegativeFormat,
    SymbolPosition, DateFormatType, NumberFormatType
)

# Permission dependencies
RequireBooksSettingsRead = Depends(require_scope("books:settings:read"))
RequireBooksSettingsWrite = Depends(require_scope("books:settings:write"))

router = APIRouter(prefix="/books", tags=["settings-books"])
templates = get_template_env()


def _form_int(form: Any, key: str, default: int) -> int:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    try:
        if value in ("", None):
            return default
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _form_str(form: Any, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value)


def _form_bool(form: Any, key: str) -> bool:
    value = form.get(key)
    if isinstance(value, UploadFile):
        return False
    return value in ("true", "on", "1", True)


def get_settings_nav(user, current_section: str = "books") -> list[dict]:
    """Get settings navigation."""
    from app.modules.settings.routes import SETTINGS_CATEGORIES
    nav_items = []
    for cat in SETTINGS_CATEGORIES:
        if cat["scope"] is None or user.has_scope(cat["scope"]):
            nav_items.append({
                **cat,
                "is_current": current_section == cat["id"],
            })
    return nav_items


BOOKS_TABS = [
    {"id": "general", "label": "General", "href": "/settings/books"},
    {"id": "documents", "label": "Document Numbers", "href": "/settings/books/documents"},
    {"id": "currencies", "label": "Currencies", "href": "/settings/books/currencies"},
]


@router.get("", response_class=HTMLResponse, dependencies=[RequireBooksSettingsRead])
async def books_settings_index(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Books settings - general configuration."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "books")
    context["books_tabs"] = BOOKS_TABS
    context["current_tab"] = "general"

    # Get or create settings
    settings = db.query(BooksSettings).filter(BooksSettings.company == None).first()
    if not settings:
        settings = BooksSettings()

    context["page_title"] = "Books Settings"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Accounting", "href": "/settings/books"},
        {"label": "General"},
    ])

    context["settings"] = settings
    context["can_edit"] = user.has_scope("books:settings:write")

    # Enum options
    context["rounding_methods"] = [{"value": e.value, "label": e.value.replace("_", " ").title()} for e in RoundingMethod]
    context["date_formats"] = [{"value": e.value, "label": e.value} for e in DateFormatType]
    context["number_formats"] = [{"value": e.value, "label": e.value} for e in NumberFormatType]
    context["negative_formats"] = [{"value": e.value, "label": e.value.replace("_", " ").title()} for e in NegativeFormat]
    context["symbol_positions"] = [{"value": e.value, "label": e.value.title()} for e in SymbolPosition]

    template = templates.get_template("modules/settings/templates/pages/books/general.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireBooksSettingsWrite])
async def save_books_settings(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _csrf: CSRFProtect,
):
    """Save books settings."""
    form = await request.form()

    settings = db.query(BooksSettings).filter(BooksSettings.company == None).first()
    if not settings:
        settings = BooksSettings()
        db.add(settings)

    settings_any: Any = settings

    # Update fields
    settings_any.base_currency = _form_str(form, "base_currency", "NGN")
    settings_any.currency_precision = _form_int(form, "currency_precision", 2)
    settings_any.quantity_precision = _form_int(form, "quantity_precision", 2)
    settings_any.rate_precision = _form_int(form, "rate_precision", 4)
    settings_any.exchange_rate_precision = _form_int(form, "exchange_rate_precision", 6)
    settings_any.rounding_method = RoundingMethod(_form_str(form, "rounding_method", RoundingMethod.ROUND_HALF_UP.value))

    settings_any.fiscal_year_start_month = _form_int(form, "fiscal_year_start_month", 1)
    settings_any.fiscal_year_start_day = _form_int(form, "fiscal_year_start_day", 1)
    settings_any.auto_create_fiscal_years = _form_bool(form, "auto_create_fiscal_years")
    settings_any.auto_create_fiscal_periods = _form_bool(form, "auto_create_fiscal_periods")

    settings_any.date_format = DateFormatType(_form_str(form, "date_format", DateFormatType.DD_MM_YYYY.value))
    settings_any.number_format = NumberFormatType(_form_str(form, "number_format", NumberFormatType.COMMA_DOT.value))
    settings_any.negative_format = NegativeFormat(_form_str(form, "negative_format", NegativeFormat.MINUS.value))
    settings_any.currency_symbol_position = SymbolPosition(
        _form_str(form, "currency_symbol_position", SymbolPosition.BEFORE.value)
    )

    settings_any.backdating_days_allowed = _form_int(form, "backdating_days_allowed", 0)
    settings_any.future_posting_days_allowed = _form_int(form, "future_posting_days_allowed", 0)
    settings_any.require_posting_in_open_period = _form_bool(form, "require_posting_in_open_period")

    db.commit()

    set_flash(response, "Books settings saved successfully.", "success")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/settings/books", status_code=303)


@router.get("/documents", response_class=HTMLResponse, dependencies=[RequireBooksSettingsRead])
async def document_formats_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Document number format configuration."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "books")
    context["books_tabs"] = BOOKS_TABS
    context["current_tab"] = "documents"

    formats = db.query(DocumentNumberFormat).order_by(DocumentNumberFormat.document_type).all()

    context["page_title"] = "Document Number Formats"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Accounting", "href": "/settings/books"},
        {"label": "Document Numbers"},
    ])

    context["formats"] = formats
    context["document_types"] = [{"value": e.value, "label": e.value.replace("_", " ").title()} for e in DocumentType]
    context["reset_frequencies"] = [{"value": e.value, "label": e.value.title()} for e in ResetFrequency]
    context["can_edit"] = user.has_scope("books:settings:write")

    template = templates.get_template("modules/settings/templates/pages/books/documents.html")
    return HTMLResponse(template.render(context))


@router.get("/currencies", response_class=HTMLResponse, dependencies=[RequireBooksSettingsRead])
async def currencies_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Currency settings configuration."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "books")
    context["books_tabs"] = BOOKS_TABS
    context["current_tab"] = "currencies"

    currencies = db.query(CurrencySettings).order_by(CurrencySettings.currency_code).all()

    context["page_title"] = "Currency Settings"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Accounting", "href": "/settings/books"},
        {"label": "Currencies"},
    ])

    context["currencies"] = currencies
    context["can_edit"] = user.has_scope("books:settings:write")

    template = templates.get_template("modules/settings/templates/pages/books/currencies.html")
    return HTMLResponse(template.render(context))
