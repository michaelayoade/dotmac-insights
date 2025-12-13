"""
Books Settings API

Endpoints for managing:
- Company books settings (currency, fiscal year, display formats)
- Document number formats (invoice, bill, payment numbering)
- Currency settings (symbols, decimal places, formatting)
"""

from datetime import date
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, validator
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.books_settings import (
    BooksSettings,
    DocumentNumberFormat,
    CurrencySettings,
    DocumentType,
    ResetFrequency,
    RoundingMethod,
    NegativeFormat,
    SymbolPosition,
    DateFormatType,
    NumberFormatType,
)
from app.services.number_generator import (
    NumberGenerator,
    AmountFormatter,
    seed_default_formats,
    seed_default_currencies,
    seed_default_settings,
)
from app.auth import Require

router = APIRouter(prefix="/books/settings", tags=["Books Settings"])


# ============================================================================
# SCHEMAS
# ============================================================================

# --- Books Settings Schemas ---

class BooksSettingsBase(BaseModel):
    base_currency: str = Field("NGN", max_length=3)
    currency_precision: int = Field(2, ge=0, le=4)
    quantity_precision: int = Field(2, ge=0, le=6)
    rate_precision: int = Field(4, ge=0, le=6)
    exchange_rate_precision: int = Field(6, ge=0, le=8)
    rounding_method: RoundingMethod = RoundingMethod.ROUND_HALF_UP

    fiscal_year_start_month: int = Field(1, ge=1, le=12)
    fiscal_year_start_day: int = Field(1, ge=1, le=31)
    auto_create_fiscal_years: bool = True
    auto_create_fiscal_periods: bool = True

    date_format: DateFormatType = DateFormatType.DD_MM_YYYY
    number_format: NumberFormatType = NumberFormatType.COMMA_DOT
    negative_format: NegativeFormat = NegativeFormat.MINUS
    currency_symbol_position: SymbolPosition = SymbolPosition.BEFORE

    backdating_days_allowed: int = Field(7, ge=0)
    future_posting_days_allowed: int = Field(0, ge=0)
    require_posting_in_open_period: bool = True

    auto_voucher_numbering: bool = True
    allow_duplicate_party_invoice: bool = False

    require_attachment_journal_entry: bool = False
    require_attachment_expense: bool = True
    require_attachment_payment: bool = False
    require_attachment_invoice: bool = False

    require_approval_journal_entry: bool = False
    require_approval_expense: bool = True
    require_approval_payment: bool = False

    retained_earnings_account: Optional[str] = None
    fx_gain_account: Optional[str] = None
    fx_loss_account: Optional[str] = None
    default_receivable_account: Optional[str] = None
    default_payable_account: Optional[str] = None
    default_income_account: Optional[str] = None
    default_expense_account: Optional[str] = None

    allow_negative_stock: bool = False
    default_valuation_method: str = "FIFO"


class BooksSettingsCreate(BooksSettingsBase):
    company: Optional[str] = None


class BooksSettingsUpdate(BaseModel):
    base_currency: Optional[str] = None
    currency_precision: Optional[int] = Field(None, ge=0, le=4)
    quantity_precision: Optional[int] = Field(None, ge=0, le=6)
    rate_precision: Optional[int] = Field(None, ge=0, le=6)
    exchange_rate_precision: Optional[int] = Field(None, ge=0, le=8)
    rounding_method: Optional[RoundingMethod] = None

    fiscal_year_start_month: Optional[int] = Field(None, ge=1, le=12)
    fiscal_year_start_day: Optional[int] = Field(None, ge=1, le=31)
    auto_create_fiscal_years: Optional[bool] = None
    auto_create_fiscal_periods: Optional[bool] = None

    date_format: Optional[DateFormatType] = None
    number_format: Optional[NumberFormatType] = None
    negative_format: Optional[NegativeFormat] = None
    currency_symbol_position: Optional[SymbolPosition] = None

    backdating_days_allowed: Optional[int] = Field(None, ge=0)
    future_posting_days_allowed: Optional[int] = Field(None, ge=0)
    require_posting_in_open_period: Optional[bool] = None

    auto_voucher_numbering: Optional[bool] = None
    allow_duplicate_party_invoice: Optional[bool] = None

    require_attachment_journal_entry: Optional[bool] = None
    require_attachment_expense: Optional[bool] = None
    require_attachment_payment: Optional[bool] = None
    require_attachment_invoice: Optional[bool] = None

    require_approval_journal_entry: Optional[bool] = None
    require_approval_expense: Optional[bool] = None
    require_approval_payment: Optional[bool] = None

    retained_earnings_account: Optional[str] = None
    fx_gain_account: Optional[str] = None
    fx_loss_account: Optional[str] = None
    default_receivable_account: Optional[str] = None
    default_payable_account: Optional[str] = None
    default_income_account: Optional[str] = None
    default_expense_account: Optional[str] = None

    allow_negative_stock: Optional[bool] = None
    default_valuation_method: Optional[str] = None


class BooksSettingsResponse(BooksSettingsBase):
    id: int
    company: Optional[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


# --- Document Number Format Schemas ---

class DocumentNumberFormatBase(BaseModel):
    document_type: DocumentType
    prefix: str = Field(..., min_length=1, max_length=20)
    format_pattern: str = Field(..., min_length=1, max_length=100)
    min_digits: int = Field(4, ge=1, le=10)
    starting_number: int = Field(1, ge=0)
    reset_frequency: ResetFrequency = ResetFrequency.NEVER

    @validator('format_pattern')
    def validate_pattern(cls, v):
        # Must contain a sequence placeholder
        if '{#' not in v:
            raise ValueError("Format pattern must contain sequence placeholder like {####}")
        return v


class DocumentNumberFormatCreate(DocumentNumberFormatBase):
    company: Optional[str] = None


class DocumentNumberFormatUpdate(BaseModel):
    prefix: Optional[str] = Field(None, min_length=1, max_length=20)
    format_pattern: Optional[str] = Field(None, min_length=1, max_length=100)
    min_digits: Optional[int] = Field(None, ge=1, le=10)
    starting_number: Optional[int] = Field(None, ge=0)
    reset_frequency: Optional[ResetFrequency] = None
    is_active: Optional[bool] = None


class DocumentNumberFormatResponse(DocumentNumberFormatBase):
    id: int
    company: Optional[str]
    current_number: int
    last_reset_date: Optional[str]
    last_reset_period: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class NumberPreviewRequest(BaseModel):
    format_pattern: str
    prefix: str = "DOC"
    sequence: int = Field(1, ge=1)
    min_digits: int = Field(4, ge=1, le=10)
    posting_date: Optional[str] = None  # YYYY-MM-DD


class NumberPreviewResponse(BaseModel):
    preview: str
    tokens_used: List[str]


class NextNumberResponse(BaseModel):
    number: str
    sequence: int
    document_type: str


class ResetSequenceRequest(BaseModel):
    new_starting_number: int = Field(1, ge=1)


# --- Currency Settings Schemas ---

class CurrencySettingsBase(BaseModel):
    currency_code: str = Field(..., min_length=3, max_length=3)
    currency_name: str = Field(..., min_length=1, max_length=100)
    symbol: str = Field(..., min_length=1, max_length=10)
    symbol_position: SymbolPosition = SymbolPosition.BEFORE
    decimal_places: int = Field(2, ge=0, le=6)
    thousands_separator: str = Field(",", max_length=1)
    decimal_separator: str = Field(".", max_length=1)
    smallest_unit: Decimal = Field(Decimal("0.01"), gt=0)
    rounding_method: RoundingMethod = RoundingMethod.ROUND_HALF_UP
    is_base_currency: bool = False
    is_enabled: bool = True


class CurrencySettingsCreate(CurrencySettingsBase):
    pass


class CurrencySettingsUpdate(BaseModel):
    currency_name: Optional[str] = Field(None, min_length=1, max_length=100)
    symbol: Optional[str] = Field(None, min_length=1, max_length=10)
    symbol_position: Optional[SymbolPosition] = None
    decimal_places: Optional[int] = Field(None, ge=0, le=6)
    thousands_separator: Optional[str] = Field(None, max_length=1)
    decimal_separator: Optional[str] = Field(None, max_length=1)
    smallest_unit: Optional[Decimal] = Field(None, gt=0)
    rounding_method: Optional[RoundingMethod] = None
    is_base_currency: Optional[bool] = None
    is_enabled: Optional[bool] = None


class CurrencySettingsResponse(CurrencySettingsBase):
    id: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class FormatAmountRequest(BaseModel):
    amount: Decimal
    currency_code: str = "NGN"
    show_symbol: bool = True


class FormatAmountResponse(BaseModel):
    formatted: str
    rounded: Decimal


# ============================================================================
# BOOKS SETTINGS ENDPOINTS
# ============================================================================

@router.get("", response_model=BooksSettingsResponse, dependencies=[Depends(Require("books:read"))])
def get_books_settings(
    company: Optional[str] = Query(None, description="Company name (null for global)"),
    db: Session = Depends(get_db),
):
    """Get books settings for a company or global defaults."""
    # Try company-specific first
    if company:
        stmt = select(BooksSettings).where(BooksSettings.company == company)
        settings = db.execute(stmt).scalar_one_or_none()
        if settings:
            return _settings_to_response(settings)

    # Fall back to global
    stmt = select(BooksSettings).where(BooksSettings.company.is_(None))
    settings = db.execute(stmt).scalar_one_or_none()

    if not settings:
        # Seed defaults if none exist
        seed_default_settings(db)
        db.commit()
        settings = db.execute(stmt).scalar_one_or_none()

    if not settings:
        raise HTTPException(status_code=404, detail="Books settings not found")

    return _settings_to_response(settings)


@router.put("", response_model=BooksSettingsResponse, dependencies=[Depends(Require("books:write"))])
def update_books_settings(
    data: BooksSettingsUpdate,
    company: Optional[str] = Query(None, description="Company name (null for global)"),
    db: Session = Depends(get_db),
):
    """Update books settings."""
    if company:
        stmt = select(BooksSettings).where(BooksSettings.company == company)
    else:
        stmt = select(BooksSettings).where(BooksSettings.company.is_(None))

    settings = db.execute(stmt).scalar_one_or_none()

    if not settings:
        # Create new settings
        settings = BooksSettings(company=company)
        db.add(settings)

    # Update fields
    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(settings, field):
            setattr(settings, field, value)

    db.commit()
    db.refresh(settings)

    return _settings_to_response(settings)


@router.post("/seed-defaults", dependencies=[Depends(Require("books:write"))])
def seed_defaults(
    db: Session = Depends(get_db),
):
    """Seed default settings, formats, and currencies if none exist."""
    seed_default_settings(db)
    seed_default_formats(db)
    seed_default_currencies(db)
    db.commit()

    return {"message": "Default settings seeded successfully"}


# ============================================================================
# DOCUMENT NUMBER FORMAT ENDPOINTS
# ============================================================================

@router.get("/number-formats", response_model=List[DocumentNumberFormatResponse], dependencies=[Depends(Require("books:read"))])
def list_number_formats(
    company: Optional[str] = Query(None),
    document_type: Optional[DocumentType] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
):
    """List all document number formats."""
    stmt = select(DocumentNumberFormat)

    if company is not None:
        stmt = stmt.where(DocumentNumberFormat.company == company)
    if document_type is not None:
        stmt = stmt.where(DocumentNumberFormat.document_type == document_type)
    if is_active is not None:
        stmt = stmt.where(DocumentNumberFormat.is_active == is_active)

    stmt = stmt.order_by(DocumentNumberFormat.document_type)
    formats = db.execute(stmt).scalars().all()

    # Seed defaults if none exist
    if not formats:
        seed_default_formats(db)
        db.commit()
        formats = db.execute(stmt).scalars().all()

    return [_format_to_response(f) for f in formats]


@router.post("/number-formats", response_model=DocumentNumberFormatResponse, dependencies=[Depends(Require("books:write"))])
def create_number_format(
    data: DocumentNumberFormatCreate,
    db: Session = Depends(get_db),
):
    """Create a new document number format."""
    # Check for existing active format
    stmt = select(DocumentNumberFormat).where(
        DocumentNumberFormat.document_type == data.document_type,
        DocumentNumberFormat.company == data.company,
        DocumentNumberFormat.is_active == True,
    )
    existing = db.execute(stmt).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Active format already exists for {data.document_type.value}"
        )

    format_config = DocumentNumberFormat(
        document_type=data.document_type,
        company=data.company,
        prefix=data.prefix,
        format_pattern=data.format_pattern,
        min_digits=data.min_digits,
        starting_number=data.starting_number,
        current_number=data.starting_number - 1,
        reset_frequency=data.reset_frequency,
        is_active=True,
        created_by_id=None,  # Set by auth context if needed
    )

    db.add(format_config)
    db.commit()
    db.refresh(format_config)

    return _format_to_response(format_config)


@router.get("/number-formats/{format_id}", response_model=DocumentNumberFormatResponse, dependencies=[Depends(Require("books:read"))])
def get_number_format(
    format_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific document number format."""
    format_config = db.get(DocumentNumberFormat, format_id)

    if not format_config:
        raise HTTPException(status_code=404, detail="Format not found")

    return _format_to_response(format_config)


@router.put("/number-formats/{format_id}", response_model=DocumentNumberFormatResponse, dependencies=[Depends(Require("books:write"))])
def update_number_format(
    format_id: int,
    data: DocumentNumberFormatUpdate,
    db: Session = Depends(get_db),
):
    """Update a document number format."""
    format_config = db.get(DocumentNumberFormat, format_id)

    if not format_config:
        raise HTTPException(status_code=404, detail="Format not found")

    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(format_config, field):
            setattr(format_config, field, value)

    db.commit()
    db.refresh(format_config)

    return _format_to_response(format_config)


@router.delete("/number-formats/{format_id}", dependencies=[Depends(Require("books:write"))])
def delete_number_format(
    format_id: int,
    db: Session = Depends(get_db),
):
    """Delete a document number format."""
    format_config = db.get(DocumentNumberFormat, format_id)

    if not format_config:
        raise HTTPException(status_code=404, detail="Format not found")

    # Soft delete by deactivating
    format_config.is_active = False
    db.commit()

    return {"message": "Format deactivated"}


@router.post("/number-formats/preview", response_model=NumberPreviewResponse, dependencies=[Depends(Require("books:read"))])
def preview_number_format(
    data: NumberPreviewRequest,
    db: Session = Depends(get_db),
):
    """Preview what a format pattern would generate."""
    generator = NumberGenerator(db)

    posting_date = None
    if data.posting_date:
        posting_date = date.fromisoformat(data.posting_date)

    # Get fiscal year start month from settings
    settings = db.execute(
        select(BooksSettings).where(BooksSettings.company.is_(None))
    ).scalar_one_or_none()
    fy_start_month = settings.fiscal_year_start_month if settings else 1

    preview = generator.preview_format(
        format_pattern=data.format_pattern,
        prefix=data.prefix,
        sequence=data.sequence,
        min_digits=data.min_digits,
        posting_date=posting_date,
        fiscal_year_start_month=fy_start_month,
    )

    # Find tokens used
    import re
    tokens = re.findall(r'\{[^}]+\}', data.format_pattern)

    return NumberPreviewResponse(preview=preview, tokens_used=tokens)


@router.post("/number-formats/{document_type}/next", response_model=NextNumberResponse, dependencies=[Depends(Require("books:write"))])
def get_next_number(
    document_type: DocumentType,
    company: Optional[str] = Query(None),
    posting_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """Generate the next document number (increments sequence)."""
    generator = NumberGenerator(db)

    pd = None
    if posting_date:
        pd = date.fromisoformat(posting_date)

    try:
        number = generator.get_next_number(
            document_type=document_type,
            company=company,
            posting_date=pd,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Get current sequence
    seq = generator.get_current_sequence(document_type, company)

    db.commit()

    return NextNumberResponse(
        number=number,
        sequence=seq or 0,
        document_type=document_type.value,
    )


@router.post("/number-formats/{format_id}/reset", dependencies=[Depends(Require("books:write"))])
def reset_sequence(
    format_id: int,
    data: ResetSequenceRequest,
    db: Session = Depends(get_db),
):
    """Reset a sequence to a new starting number."""
    format_config = db.get(DocumentNumberFormat, format_id)

    if not format_config:
        raise HTTPException(status_code=404, detail="Format not found")

    generator = NumberGenerator(db)
    success = generator.reset_sequence(
        document_type=format_config.document_type,
        company=format_config.company,
        new_starting_number=data.new_starting_number,
    )

    if not success:
        raise HTTPException(status_code=400, detail="Failed to reset sequence")

    db.commit()

    return {
        "message": f"Sequence reset to {data.new_starting_number}",
        "document_type": format_config.document_type.value,
    }


# ============================================================================
# CURRENCY SETTINGS ENDPOINTS
# ============================================================================

@router.get("/currencies", response_model=List[CurrencySettingsResponse], dependencies=[Depends(Require("books:read"))])
def list_currencies(
    is_enabled: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
):
    """List all currency settings."""
    stmt = select(CurrencySettings)

    if is_enabled is not None:
        stmt = stmt.where(CurrencySettings.is_enabled == is_enabled)

    stmt = stmt.order_by(CurrencySettings.currency_code)
    currencies = db.execute(stmt).scalars().all()

    # Seed defaults if none exist
    if not currencies:
        seed_default_currencies(db)
        db.commit()
        currencies = db.execute(stmt).scalars().all()

    return [_currency_to_response(c) for c in currencies]


@router.post("/currencies", response_model=CurrencySettingsResponse, dependencies=[Depends(Require("books:write"))])
def create_currency(
    data: CurrencySettingsCreate,
    db: Session = Depends(get_db),
):
    """Create a new currency setting."""
    # Check for existing
    stmt = select(CurrencySettings).where(
        CurrencySettings.currency_code == data.currency_code.upper()
    )
    existing = db.execute(stmt).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Currency {data.currency_code} already exists"
        )

    # If setting as base currency, unset others
    if data.is_base_currency:
        db.execute(
            CurrencySettings.__table__.update().values(is_base_currency=False)
        )

    currency = CurrencySettings(
        currency_code=data.currency_code.upper(),
        currency_name=data.currency_name,
        symbol=data.symbol,
        symbol_position=data.symbol_position,
        decimal_places=data.decimal_places,
        thousands_separator=data.thousands_separator,
        decimal_separator=data.decimal_separator,
        smallest_unit=data.smallest_unit,
        rounding_method=data.rounding_method,
        is_base_currency=data.is_base_currency,
        is_enabled=data.is_enabled,
    )

    db.add(currency)
    db.commit()
    db.refresh(currency)

    return _currency_to_response(currency)


@router.get("/currencies/{currency_code}", response_model=CurrencySettingsResponse, dependencies=[Depends(Require("books:read"))])
def get_currency(
    currency_code: str,
    db: Session = Depends(get_db),
):
    """Get a specific currency setting."""
    stmt = select(CurrencySettings).where(
        CurrencySettings.currency_code == currency_code.upper()
    )
    currency = db.execute(stmt).scalar_one_or_none()

    if not currency:
        raise HTTPException(status_code=404, detail="Currency not found")

    return _currency_to_response(currency)


@router.put("/currencies/{currency_code}", response_model=CurrencySettingsResponse, dependencies=[Depends(Require("books:write"))])
def update_currency(
    currency_code: str,
    data: CurrencySettingsUpdate,
    db: Session = Depends(get_db),
):
    """Update a currency setting."""
    stmt = select(CurrencySettings).where(
        CurrencySettings.currency_code == currency_code.upper()
    )
    currency = db.execute(stmt).scalar_one_or_none()

    if not currency:
        raise HTTPException(status_code=404, detail="Currency not found")

    # If setting as base currency, unset others
    if data.is_base_currency:
        db.execute(
            CurrencySettings.__table__.update()
            .where(CurrencySettings.currency_code != currency_code.upper())
            .values(is_base_currency=False)
        )

    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(currency, field):
            setattr(currency, field, value)

    db.commit()
    db.refresh(currency)

    return _currency_to_response(currency)


@router.post("/currencies/format-amount", response_model=FormatAmountResponse, dependencies=[Depends(Require("books:read"))])
def format_amount(
    data: FormatAmountRequest,
    db: Session = Depends(get_db),
):
    """Format an amount according to currency settings."""
    formatter = AmountFormatter(db)

    formatted = formatter.format(
        amount=data.amount,
        currency_code=data.currency_code,
        show_symbol=data.show_symbol,
    )
    rounded = formatter.round(data.amount, data.currency_code)

    return FormatAmountResponse(formatted=formatted, rounded=rounded)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _settings_to_response(settings: BooksSettings) -> dict:
    """Convert BooksSettings model to response dict."""
    return {
        "id": settings.id,
        "company": settings.company,
        "base_currency": settings.base_currency,
        "currency_precision": settings.currency_precision,
        "quantity_precision": settings.quantity_precision,
        "rate_precision": settings.rate_precision,
        "exchange_rate_precision": settings.exchange_rate_precision,
        "rounding_method": settings.rounding_method,
        "fiscal_year_start_month": settings.fiscal_year_start_month,
        "fiscal_year_start_day": settings.fiscal_year_start_day,
        "auto_create_fiscal_years": settings.auto_create_fiscal_years,
        "auto_create_fiscal_periods": settings.auto_create_fiscal_periods,
        "date_format": settings.date_format,
        "number_format": settings.number_format,
        "negative_format": settings.negative_format,
        "currency_symbol_position": settings.currency_symbol_position,
        "backdating_days_allowed": settings.backdating_days_allowed,
        "future_posting_days_allowed": settings.future_posting_days_allowed,
        "require_posting_in_open_period": settings.require_posting_in_open_period,
        "auto_voucher_numbering": settings.auto_voucher_numbering,
        "allow_duplicate_party_invoice": settings.allow_duplicate_party_invoice,
        "require_attachment_journal_entry": settings.require_attachment_journal_entry,
        "require_attachment_expense": settings.require_attachment_expense,
        "require_attachment_payment": settings.require_attachment_payment,
        "require_attachment_invoice": settings.require_attachment_invoice,
        "require_approval_journal_entry": settings.require_approval_journal_entry,
        "require_approval_expense": settings.require_approval_expense,
        "require_approval_payment": settings.require_approval_payment,
        "retained_earnings_account": settings.retained_earnings_account,
        "fx_gain_account": settings.fx_gain_account,
        "fx_loss_account": settings.fx_loss_account,
        "default_receivable_account": settings.default_receivable_account,
        "default_payable_account": settings.default_payable_account,
        "default_income_account": settings.default_income_account,
        "default_expense_account": settings.default_expense_account,
        "allow_negative_stock": settings.allow_negative_stock,
        "default_valuation_method": settings.default_valuation_method,
        "created_at": settings.created_at.isoformat() if settings.created_at else None,
        "updated_at": settings.updated_at.isoformat() if settings.updated_at else None,
    }


def _format_to_response(format_config: DocumentNumberFormat) -> dict:
    """Convert DocumentNumberFormat model to response dict."""
    return {
        "id": format_config.id,
        "document_type": format_config.document_type,
        "company": format_config.company,
        "prefix": format_config.prefix,
        "format_pattern": format_config.format_pattern,
        "min_digits": format_config.min_digits,
        "starting_number": format_config.starting_number,
        "current_number": format_config.current_number,
        "reset_frequency": format_config.reset_frequency,
        "last_reset_date": format_config.last_reset_date.isoformat() if format_config.last_reset_date else None,
        "last_reset_period": format_config.last_reset_period,
        "is_active": format_config.is_active,
        "created_at": format_config.created_at.isoformat() if format_config.created_at else None,
        "updated_at": format_config.updated_at.isoformat() if format_config.updated_at else None,
    }


def _currency_to_response(currency: CurrencySettings) -> dict:
    """Convert CurrencySettings model to response dict."""
    return {
        "id": currency.id,
        "currency_code": currency.currency_code,
        "currency_name": currency.currency_name,
        "symbol": currency.symbol,
        "symbol_position": currency.symbol_position,
        "decimal_places": currency.decimal_places,
        "thousands_separator": currency.thousands_separator,
        "decimal_separator": currency.decimal_separator,
        "smallest_unit": currency.smallest_unit,
        "rounding_method": currency.rounding_method,
        "is_base_currency": currency.is_base_currency,
        "is_enabled": currency.is_enabled,
        "created_at": currency.created_at.isoformat() if currency.created_at else None,
        "updated_at": currency.updated_at.isoformat() if currency.updated_at else None,
    }
