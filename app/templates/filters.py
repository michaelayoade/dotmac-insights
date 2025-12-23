"""
Custom Jinja2 Filters for DotMac Insights.

Provides formatting filters for:
- Currency values
- Dates and times
- Text transformations
- HTML utilities
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional, Union

from markupsafe import Markup


def register_filters(env: Any) -> None:
    """Register all custom filters with the Jinja2 environment."""
    env.filters["currency"] = currency_filter
    env.filters["format_number"] = format_number_filter
    env.filters["format_date"] = format_date_filter
    env.filters["format_time"] = format_time_filter
    env.filters["format_datetime"] = format_datetime_filter
    env.filters["title_case"] = title_case_filter
    env.filters["truncate_words"] = truncate_words_filter
    env.filters["nl2br"] = nl2br_filter
    env.filters["default_if_none"] = default_if_none_filter
    env.filters["pluralize"] = pluralize_filter
    env.filters["yesno"] = yesno_filter
    env.filters["phone"] = phone_filter
    env.filters["csv_escape"] = csv_escape_filter


def currency_filter(
    value: Optional[Union[int, float, Decimal, str]],
    symbol: str = "₦",
    decimal_places: int = 2,
) -> str:
    """
    Format a number as currency.

    Examples:
        {{ 1234.56 | currency }} -> "₦1,234.56"
        {{ 1234 | currency("$") }} -> "$1,234.00"
        {{ amount | currency(symbol="€", decimal_places=0) }} -> "€1,235"
    """
    if value is None:
        return f"{symbol}0.00"

    try:
        num = float(value)
    except (ValueError, TypeError):
        return f"{symbol}0.00"

    # Format with thousands separator and decimal places
    formatted = f"{num:,.{decimal_places}f}"
    return f"{symbol}{formatted}"


def format_number_filter(
    value: Optional[Union[int, float, Decimal, str]],
    decimal_places: int = 2,
) -> str:
    """
    Format a number with thousands separator.

    Examples:
        {{ 1234567.89 | format_number }} -> "1,234,567.89"
        {{ 1234 | format_number(0) }} -> "1,234"
    """
    if value is None:
        return "0.00"

    try:
        num = float(value)
    except (ValueError, TypeError):
        return "0.00"

    return f"{num:,.{decimal_places}f}"


def format_date_filter(
    value: Optional[Union[date, datetime, str]],
    format_str: str = "%B %d, %Y",
) -> str:
    """
    Format a date value.

    Examples:
        {{ order.date | format_date }} -> "December 23, 2025"
        {{ order.date | format_date("%Y-%m-%d") }} -> "2025-12-23"
        {{ order.date | format_date("%d/%m/%Y") }} -> "23/12/2025"
    """
    if value is None:
        return ""

    if isinstance(value, str):
        try:
            # Try common date formats
            for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
                try:
                    value = datetime.strptime(value, fmt)
                    break
                except ValueError:
                    continue
            else:
                return value  # Return original string if parsing fails
        except Exception:
            return value

    if isinstance(value, (date, datetime)):
        return value.strftime(format_str)

    return str(value)


def format_time_filter(
    value: Optional[Union[datetime, str]],
    format_str: str = "%I:%M %p",
) -> str:
    """
    Format a time value.

    Examples:
        {{ order.time | format_time }} -> "02:30 PM"
        {{ order.time | format_time("%H:%M") }} -> "14:30"
    """
    if value is None:
        return ""

    if isinstance(value, str):
        try:
            for fmt in ["%H:%M:%S", "%H:%M", "%Y-%m-%dT%H:%M:%S"]:
                try:
                    value = datetime.strptime(value, fmt)
                    break
                except ValueError:
                    continue
            else:
                return value
        except Exception:
            return value

    if isinstance(value, datetime):
        return value.strftime(format_str)

    return str(value)


def format_datetime_filter(
    value: Optional[Union[datetime, str]],
    format_str: str = "%B %d, %Y at %I:%M %p",
) -> str:
    """
    Format a datetime value.

    Examples:
        {{ order.created_at | format_datetime }} -> "December 23, 2025 at 02:30 PM"
    """
    if value is None:
        return ""

    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return value

    if isinstance(value, datetime):
        return value.strftime(format_str)

    return str(value)


def title_case_filter(value: Optional[str]) -> str:
    """
    Convert string to title case, handling special cases.

    Examples:
        {{ "installation_request" | title_case }} -> "Installation Request"
        {{ "NEW_INSTALLATION" | title_case }} -> "New Installation"
    """
    if value is None:
        return ""

    # Replace underscores and hyphens with spaces, then title case
    result = value.replace("_", " ").replace("-", " ")
    return result.title()


def truncate_words_filter(
    value: Optional[str],
    length: int = 50,
    suffix: str = "...",
) -> str:
    """
    Truncate text to a maximum number of words.

    Examples:
        {{ long_text | truncate_words(10) }} -> "First ten words of the text..."
    """
    if value is None:
        return ""

    words = value.split()
    if len(words) <= length:
        return value

    return " ".join(words[:length]) + suffix


def nl2br_filter(value: Optional[str]) -> Markup:
    """
    Convert newlines to HTML <br> tags.

    Examples:
        {{ message | nl2br }} -> "Line 1<br>Line 2"
    """
    if value is None:
        return Markup("")

    # Escape HTML entities first, then convert newlines
    from markupsafe import escape
    escaped = escape(str(value))
    result = escaped.replace("\n", Markup("<br>\n"))
    return Markup(result)


def default_if_none_filter(value: Any, default: str = "") -> Any:
    """
    Return default value if the input is None.

    Examples:
        {{ customer.phone | default_if_none("Not provided") }}
    """
    if value is None:
        return default
    return value


def pluralize_filter(
    count: Optional[int],
    singular: str = "",
    plural: str = "s",
) -> str:
    """
    Return singular or plural suffix based on count.

    Examples:
        {{ item_count }} item{{ item_count | pluralize }}
        {{ day_count }} day{{ day_count | pluralize }}
        {{ person_count }} {{ person_count | pluralize("person", "people") }}
    """
    if count is None:
        count = 0

    try:
        count = int(count)
    except (ValueError, TypeError):
        count = 0

    if count == 1:
        return singular
    return plural


def yesno_filter(
    value: Optional[bool],
    yes: str = "Yes",
    no: str = "No",
    none: str = "N/A",
) -> str:
    """
    Convert boolean to yes/no string.

    Examples:
        {{ is_active | yesno }} -> "Yes" or "No"
        {{ is_balanced | yesno("Balanced", "Unbalanced") }}
    """
    if value is None:
        return none
    return yes if value else no


def phone_filter(value: Optional[str]) -> str:
    """
    Format a phone number.

    Examples:
        {{ "2348012345678" | phone }} -> "+234 801 234 5678"
    """
    if value is None:
        return ""

    # Remove non-digit characters
    digits = "".join(c for c in str(value) if c.isdigit())

    if not digits:
        return value or ""

    # Nigerian format (11 digits starting with 0, or 13 with country code)
    if len(digits) == 11 and digits.startswith("0"):
        return f"+234 {digits[1:4]} {digits[4:7]} {digits[7:]}"
    elif len(digits) == 13 and digits.startswith("234"):
        return f"+{digits[0:3]} {digits[3:6]} {digits[6:9]} {digits[9:]}"
    elif len(digits) == 10:
        return f"({digits[0:3]}) {digits[3:6]}-{digits[6:]}"

    return value or ""


def csv_escape_filter(value: Any) -> str:
    """
    Escape a value for CSV output.

    Handles:
    - None values (empty string)
    - Strings with commas, quotes, or newlines (quoted)
    - Double quotes (doubled)
    - Numbers (converted to string)

    Examples::

        {{ item.name | csv_escape }}         -> Item Name
        {{ 'Value, with comma' | csv_escape }} -> "Value, with comma"
        {{ 'He said hello' | csv_escape }}   -> He said hello
    """
    if value is None:
        return ""

    # Convert to string
    text = str(value)

    # Check if escaping needed (contains comma, quote, newline, or carriage return)
    needs_quoting = any(c in text for c in [",", '"', "\n", "\r"])

    if needs_quoting:
        # Double any existing quotes and wrap in quotes
        escaped = text.replace('"', '""')
        return f'"{escaped}"'

    return text
