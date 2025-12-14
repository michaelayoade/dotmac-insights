"""
Document Number Generator Service

Provides thread-safe, concurrency-safe generation of unique document numbers
based on configurable format patterns.

Features:
- Format tokens: {PREFIX}, {YYYY}, {YY}, {MM}, {DD}, {FY}, {Q}, {####}
- Configurable reset frequencies (never, yearly, monthly, quarterly)
- Row-level locking for concurrent safety
- Automatic sequence management
"""

import re
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN, ROUND_UP, ROUND_HALF_DOWN, ROUND_HALF_EVEN
from typing import Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.books_settings import (
    DocumentNumberFormat,
    DocumentType,
    ResetFrequency,
    BooksSettings,
    CurrencySettings,
    RoundingMethod,
)


class NumberGeneratorError(Exception):
    """Base exception for number generator errors."""
    pass


class FormatNotFoundError(NumberGeneratorError):
    """Raised when no format is configured for a document type."""
    pass


class SequenceExhaustedError(NumberGeneratorError):
    """Raised when sequence reaches maximum value."""
    pass


class NumberGenerator:
    """
    Generates unique document numbers based on configurable formats.

    Usage:
        generator = NumberGenerator(db_session)
        invoice_number = generator.get_next_number(DocumentType.INVOICE)
        # Returns: "INV-202412-0001"
    """

    # Regex to find sequence placeholders like {####}
    SEQUENCE_PATTERN = re.compile(r'\{(#+)\}')

    # Token patterns
    TOKEN_PATTERNS = {
        '{PREFIX}': lambda ctx: ctx['prefix'],
        '{YYYY}': lambda ctx: str(ctx['year']),
        '{YY}': lambda ctx: str(ctx['year'])[-2:],
        '{MM}': lambda ctx: f"{ctx['month']:02d}",
        '{DD}': lambda ctx: f"{ctx['day']:02d}",
        '{FY}': lambda ctx: ctx['fiscal_year'],
        '{Q}': lambda ctx: str(ctx['quarter']),
        '{COMPANY}': lambda ctx: ctx.get('company_code', ''),
        '{BRANCH}': lambda ctx: ctx.get('branch_code', ''),
    }

    def __init__(self, db: Session):
        self.db = db

    def get_next_number(
        self,
        document_type: DocumentType,
        company: Optional[str] = None,
        posting_date: Optional[date] = None,
        company_code: Optional[str] = None,
        branch_code: Optional[str] = None,
    ) -> str:
        """
        Generate the next document number for the given type.

        Args:
            document_type: Type of document (INVOICE, BILL, etc.)
            company: Company scope (None for global)
            posting_date: Date to use for tokens (defaults to today)
            company_code: Short company code for {COMPANY} token
            branch_code: Branch code for {BRANCH} token

        Returns:
            Generated document number string

        Raises:
            FormatNotFoundError: If no format is configured
            SequenceExhaustedError: If sequence reaches max
        """
        if posting_date is None:
            posting_date = date.today()

        # Get the format configuration with row lock
        format_config = self._get_format_with_lock(document_type, company)

        if format_config is None:
            raise FormatNotFoundError(
                f"No number format configured for {document_type.value}"
                + (f" in company {company}" if company else "")
            )

        # Check if sequence needs reset
        self._check_and_reset_sequence(format_config, posting_date)

        # Increment sequence
        next_seq = format_config.current_number + 1

        # Check for overflow based on min_digits
        max_seq = 10 ** format_config.min_digits - 1
        if next_seq > max_seq:
            # Try to use more digits if pattern allows
            if next_seq > 10 ** 10:  # Absolute max
                raise SequenceExhaustedError(
                    f"Sequence exhausted for {document_type.value}"
                )

        # Update the sequence
        format_config.current_number = next_seq
        format_config.updated_at = datetime.utcnow()

        # Build context for token replacement
        context = self._build_context(
            format_config, posting_date, next_seq, company_code, branch_code
        )

        # Generate the number
        number = self._apply_format(format_config.format_pattern, context)

        # Commit the sequence update
        self.db.flush()

        return number

    def preview_format(
        self,
        format_pattern: str,
        prefix: str = "DOC",
        sequence: int = 1,
        min_digits: int = 4,
        posting_date: Optional[date] = None,
        fiscal_year_start_month: int = 1,
    ) -> str:
        """
        Preview what a format pattern would generate.

        Useful for UI to show example before saving.
        """
        if posting_date is None:
            posting_date = date.today()

        context = {
            'prefix': prefix,
            'year': posting_date.year,
            'month': posting_date.month,
            'day': posting_date.day,
            'quarter': (posting_date.month - 1) // 3 + 1,
            'fiscal_year': self._get_fiscal_year_string(
                posting_date, fiscal_year_start_month
            ),
            'sequence': sequence,
            'min_digits': min_digits,
            'company_code': 'CO',
            'branch_code': 'HQ',
        }

        return self._apply_format(format_pattern, context)

    def get_current_sequence(
        self,
        document_type: DocumentType,
        company: Optional[str] = None,
    ) -> Optional[int]:
        """Get the current sequence number without incrementing."""
        format_config = self._get_format(document_type, company)
        if format_config:
            return format_config.current_number
        return None

    def reset_sequence(
        self,
        document_type: DocumentType,
        company: Optional[str] = None,
        new_starting_number: int = 1,
    ) -> bool:
        """
        Manually reset a sequence to a new starting number.

        Returns True if successful, False if format not found.
        """
        format_config = self._get_format_with_lock(document_type, company)

        if format_config is None:
            return False

        format_config.current_number = new_starting_number - 1  # Will be incremented on next use
        format_config.last_reset_date = date.today()
        format_config.last_reset_period = self._get_period_key(
            date.today(), format_config.reset_frequency
        )
        format_config.updated_at = datetime.utcnow()

        self.db.flush()
        return True

    def _get_format(
        self,
        document_type: DocumentType,
        company: Optional[str] = None,
    ) -> Optional[DocumentNumberFormat]:
        """Get format config without locking."""
        # First try company-specific
        if company:
            stmt = select(DocumentNumberFormat).where(
                DocumentNumberFormat.document_type == document_type,
                DocumentNumberFormat.company == company,
                DocumentNumberFormat.is_active == True,
            )
            result = self.db.execute(stmt).scalar_one_or_none()
            if result:
                return result

        # Fall back to global
        stmt = select(DocumentNumberFormat).where(
            DocumentNumberFormat.document_type == document_type,
            DocumentNumberFormat.company.is_(None),
            DocumentNumberFormat.is_active == True,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def _get_format_with_lock(
        self,
        document_type: DocumentType,
        company: Optional[str] = None,
    ) -> Optional[DocumentNumberFormat]:
        """Get format config with row-level lock for concurrent safety."""
        # First try company-specific with lock
        if company:
            stmt = (
                select(DocumentNumberFormat)
                .where(
                    DocumentNumberFormat.document_type == document_type,
                    DocumentNumberFormat.company == company,
                    DocumentNumberFormat.is_active == True,
                )
                .with_for_update()
            )
            result = self.db.execute(stmt).scalar_one_or_none()
            if result:
                return result

        # Fall back to global with lock
        stmt = (
            select(DocumentNumberFormat)
            .where(
                DocumentNumberFormat.document_type == document_type,
                DocumentNumberFormat.company.is_(None),
                DocumentNumberFormat.is_active == True,
            )
            .with_for_update()
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def _check_and_reset_sequence(
        self,
        format_config: DocumentNumberFormat,
        posting_date: date,
    ) -> None:
        """Check if sequence needs reset based on frequency."""
        if format_config.reset_frequency == ResetFrequency.NEVER:
            return

        current_period = self._get_period_key(posting_date, format_config.reset_frequency)
        last_period = format_config.last_reset_period

        if last_period != current_period:
            # Reset sequence
            format_config.current_number = format_config.starting_number - 1
            format_config.last_reset_date = posting_date
            format_config.last_reset_period = current_period

    def _get_period_key(self, d: date, frequency: ResetFrequency) -> str:
        """Get period key string for comparison."""
        if frequency == ResetFrequency.YEARLY:
            return str(d.year)
        elif frequency == ResetFrequency.MONTHLY:
            return f"{d.year}-{d.month:02d}"
        elif frequency == ResetFrequency.QUARTERLY:
            quarter = (d.month - 1) // 3 + 1
            return f"{d.year}-Q{quarter}"
        return ""

    def _build_context(
        self,
        format_config: DocumentNumberFormat,
        posting_date: date,
        sequence: int,
        company_code: Optional[str],
        branch_code: Optional[str],
    ) -> dict:
        """Build context dictionary for token replacement."""
        # Get fiscal year settings
        settings = self._get_books_settings(format_config.company)
        fy_start_month = settings.fiscal_year_start_month if settings else 1

        return {
            'prefix': format_config.prefix,
            'year': posting_date.year,
            'month': posting_date.month,
            'day': posting_date.day,
            'quarter': (posting_date.month - 1) // 3 + 1,
            'fiscal_year': self._get_fiscal_year_string(posting_date, fy_start_month),
            'sequence': sequence,
            'min_digits': format_config.min_digits,
            'company_code': company_code or '',
            'branch_code': branch_code or '',
        }

    def _get_fiscal_year_string(self, d: date, start_month: int) -> str:
        """Get fiscal year string like '2024-25'."""
        if d.month >= start_month:
            fy_start = d.year
        else:
            fy_start = d.year - 1

        fy_end = fy_start + 1
        return f"{fy_start}-{str(fy_end)[-2:]}"

    def _apply_format(self, pattern: str, context: dict) -> str:
        """Apply format pattern with context to generate number."""
        result = pattern

        # Replace standard tokens
        for token, resolver in self.TOKEN_PATTERNS.items():
            if token in result:
                result = result.replace(token, resolver(context))

        # Replace sequence placeholder {####}
        match = self.SEQUENCE_PATTERN.search(result)
        if match:
            hash_count = len(match.group(1))
            # Use at least the configured min_digits
            digits = max(hash_count, context.get('min_digits', 4))
            seq_str = str(context['sequence']).zfill(digits)
            result = self.SEQUENCE_PATTERN.sub(seq_str, result)

        return result

    def _get_books_settings(self, company: Optional[str]) -> Optional[BooksSettings]:
        """Get books settings for company or global."""
        if company:
            stmt = select(BooksSettings).where(BooksSettings.company == company)
            result = self.db.execute(stmt).scalar_one_or_none()
            if result:
                return result

        # Fall back to global
        stmt = select(BooksSettings).where(BooksSettings.company.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()


class AmountFormatter:
    """
    Formats monetary amounts according to currency settings.

    Usage:
        formatter = AmountFormatter(db_session)
        formatted = formatter.format(Decimal("1234.56"), "NGN")
        # Returns: "₦1,234.56"
    """

    ROUNDING_MODES = {
        RoundingMethod.ROUND_HALF_UP: ROUND_HALF_UP,
        RoundingMethod.ROUND_HALF_DOWN: ROUND_HALF_DOWN,
        RoundingMethod.ROUND_DOWN: ROUND_DOWN,
        RoundingMethod.ROUND_UP: ROUND_UP,
        RoundingMethod.BANKERS: ROUND_HALF_EVEN,
    }

    def __init__(self, db: Session):
        self.db = db
        self._cache: dict[str, CurrencySettings] = {}

    def format(
        self,
        amount: Decimal,
        currency_code: str,
        show_symbol: bool = True,
    ) -> str:
        """Format an amount according to currency settings."""
        settings = self._get_currency_settings(currency_code)

        if settings:
            return self._format_with_settings(amount, settings, show_symbol)

        # Default formatting
        return f"{currency_code} {amount:,.2f}"

    def round(
        self,
        amount: Decimal,
        currency_code: str,
    ) -> Decimal:
        """Round an amount according to currency settings."""
        settings = self._get_currency_settings(currency_code)

        if settings:
            rounding = self.ROUNDING_MODES.get(
                settings.rounding_method, ROUND_HALF_UP
            )
            quantum = Decimal(10) ** -settings.decimal_places
            return amount.quantize(quantum, rounding=rounding)

        # Default to 2 decimal places
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _get_currency_settings(self, currency_code: str) -> Optional[CurrencySettings]:
        """Get currency settings with caching."""
        if currency_code in self._cache:
            return self._cache[currency_code]

        stmt = select(CurrencySettings).where(
            CurrencySettings.currency_code == currency_code,
            CurrencySettings.is_enabled == True,
        )
        settings = self.db.execute(stmt).scalar_one_or_none()

        if settings:
            self._cache[currency_code] = settings

        return settings

    def _format_with_settings(
        self,
        amount: Decimal,
        settings: CurrencySettings,
        show_symbol: bool,
    ) -> str:
        """Format amount using currency settings."""
        # Round first
        rounding = self.ROUNDING_MODES.get(
            settings.rounding_method, ROUND_HALF_UP
        )
        quantum = Decimal(10) ** -settings.decimal_places
        rounded = amount.quantize(quantum, rounding=rounding)

        # Format the number
        is_negative = rounded < 0
        abs_amount = abs(rounded)

        # Split into integer and decimal parts
        int_part = int(abs_amount)
        dec_part = abs_amount - int_part

        # Format integer part with thousands separator
        int_str = ""
        int_digits = str(int_part)
        for i, digit in enumerate(reversed(int_digits)):
            if i > 0 and i % 3 == 0:
                int_str = settings.thousands_separator + int_str
            int_str = digit + int_str

        # Format decimal part
        if settings.decimal_places > 0:
            dec_str = str(dec_part)[2:].ljust(settings.decimal_places, '0')[:settings.decimal_places]
            number_str = f"{int_str}{settings.decimal_separator}{dec_str}"
        else:
            number_str = int_str

        # Add symbol
        if show_symbol:
            if settings.symbol_position.value == "before":
                result = f"{settings.symbol}{number_str}"
            else:
                result = f"{number_str}{settings.symbol}"
        else:
            result = number_str

        # Handle negative
        if is_negative:
            result = f"-{result}"

        return result


def seed_default_formats(db: Session) -> None:
    """Seed default document number formats if none exist."""
    from sqlalchemy import func

    # Check if any formats exist
    count = db.execute(
        select(func.count(DocumentNumberFormat.id))
    ).scalar()

    if count > 0:
        return  # Already has formats

    defaults = [
        (DocumentType.INVOICE, "INV", "{PREFIX}-{YYYY}{MM}-{####}"),
        (DocumentType.BILL, "BILL", "{PREFIX}-{YYYY}{MM}-{####}"),
        (DocumentType.PAYMENT, "PAY", "{PREFIX}-{YYYY}{MM}-{####}"),
        (DocumentType.RECEIPT, "RCP", "{PREFIX}-{YYYY}{MM}-{####}"),
        (DocumentType.CREDIT_NOTE, "CN", "{PREFIX}-{YYYY}-{####}"),
        (DocumentType.DEBIT_NOTE, "DN", "{PREFIX}-{YYYY}-{####}"),
        (DocumentType.JOURNAL_ENTRY, "JV", "{PREFIX}-{FY}-{#####}"),
        (DocumentType.PURCHASE_ORDER, "PO", "{PREFIX}-{YYYY}{MM}-{####}"),
        (DocumentType.SALES_ORDER, "SO", "{PREFIX}-{YYYY}{MM}-{####}"),
        (DocumentType.QUOTATION, "QTN", "{PREFIX}-{YYYY}-{####}"),
    ]

    for doc_type, prefix, pattern in defaults:
        format_config = DocumentNumberFormat(
            document_type=doc_type,
            company=None,  # Global default
            prefix=prefix,
            format_pattern=pattern,
            min_digits=4,
            starting_number=1,
            current_number=0,
            reset_frequency=ResetFrequency.NEVER,
            is_active=True,
        )
        db.add(format_config)

    db.flush()


def seed_default_currencies(db: Session) -> None:
    """Seed default currency settings if none exist."""
    from sqlalchemy import func

    count = db.execute(
        select(func.count(CurrencySettings.id))
    ).scalar()

    if count > 0:
        return

    currencies = [
        ("NGN", "Nigerian Naira", "₦", 2, True),
        ("USD", "US Dollar", "$", 2, False),
        ("EUR", "Euro", "€", 2, False),
        ("GBP", "British Pound", "£", 2, False),
        ("KES", "Kenyan Shilling", "KSh", 2, False),
        ("GHS", "Ghanaian Cedi", "GH₵", 2, False),
        ("ZAR", "South African Rand", "R", 2, False),
    ]

    for code, name, symbol, decimals, is_base in currencies:
        currency = CurrencySettings(
            currency_code=code,
            currency_name=name,
            symbol=symbol,
            decimal_places=decimals,
            is_base_currency=is_base,
            is_enabled=True,
        )
        db.add(currency)

    db.flush()


def generate_voucher_number(db: Session, doctype: str, company: Optional[str] = None) -> str:
    """
    Convenience function to generate a document number.

    This function maps doctype strings to DocumentType enum values and
    generates the next number in sequence. If no format is configured,
    falls back to a simple pattern.

    Args:
        db: Database session
        doctype: Document type string (e.g., "supplier_payment", "invoice")
        company: Optional company scope

    Returns:
        Generated document number string
    """
    from datetime import datetime

    # Map common doctype strings to enum values
    DOCTYPE_MAP = {
        "supplier_payment": DocumentType.PAYMENT,
        "customer_payment": DocumentType.RECEIPT,
        "payment": DocumentType.PAYMENT,
        "receipt": DocumentType.RECEIPT,
        "invoice": DocumentType.INVOICE,
        "sales_invoice": DocumentType.INVOICE,
        "bill": DocumentType.BILL,
        "purchase_invoice": DocumentType.BILL,
        "credit_note": DocumentType.CREDIT_NOTE,
        "debit_note": DocumentType.DEBIT_NOTE,
        "journal_entry": DocumentType.JOURNAL_ENTRY,
        "purchase_order": DocumentType.PURCHASE_ORDER,
        "sales_order": DocumentType.SALES_ORDER,
        "quotation": DocumentType.QUOTATION,
        "delivery_note": DocumentType.DELIVERY_NOTE,
        "goods_receipt": DocumentType.GOODS_RECEIPT,
    }

    doc_type_enum = DOCTYPE_MAP.get(doctype.lower())

    if doc_type_enum:
        generator = NumberGenerator(db)
        try:
            return generator.get_next_number(doc_type_enum, company=company)
        except FormatNotFoundError:
            pass  # Fall through to default generation

    # Fallback: Generate a simple numbered format
    prefix_map = {
        "supplier_payment": "SP",
        "customer_payment": "CP",
        "payment": "PAY",
        "receipt": "RCP",
        "invoice": "INV",
        "bill": "BILL",
        "credit_note": "CN",
        "debit_note": "DN",
        "journal_entry": "JV",
    }

    prefix = prefix_map.get(doctype.lower(), doctype.upper()[:3])
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    import uuid
    unique_suffix = uuid.uuid4().hex[:4].upper()

    return f"{prefix}-{timestamp}-{unique_suffix}"


def seed_default_settings(db: Session) -> None:
    """Seed default books settings if none exist."""
    from sqlalchemy import func

    count = db.execute(
        select(func.count(BooksSettings.id))
    ).scalar()

    if count > 0:
        return

    settings = BooksSettings(
        company=None,  # Global default
        base_currency="NGN",
        currency_precision=2,
        fiscal_year_start_month=1,
        fiscal_year_start_day=1,
    )
    db.add(settings)
    db.flush()
