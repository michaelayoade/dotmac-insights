"""Data cleaning pipeline for migration.

Provides normalizers for common data types:
- Phone numbers (Nigerian format, E.164)
- Email addresses
- Names (title case, trimming)
- Addresses (Nigerian state standardization)
- Currency values
- Dates (multi-format parsing)
"""
from __future__ import annotations

import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional
from dataclasses import dataclass, field


@dataclass
class CleaningResult:
    """Result of a cleaning operation."""
    value: Any
    warnings: list[str] = field(default_factory=list)
    original: Any = None


@dataclass
class CleaningRules:
    """Configuration for data cleaning."""
    phone_enabled: bool = True
    phone_country_code: str = "234"
    phone_format: str = "e164"  # e164, local, international

    email_enabled: bool = True
    email_lowercase: bool = True
    email_fix_typos: bool = True

    name_enabled: bool = True
    name_case: str = "title"  # title, upper, lower, none
    name_trim: bool = True
    name_remove_extra_spaces: bool = True

    address_enabled: bool = True
    address_standardize_states: bool = True

    currency_enabled: bool = True
    currency_remove_symbols: bool = True
    currency_decimal_places: int = 2

    date_enabled: bool = True
    date_input_formats: list[str] = field(default_factory=lambda: [
        "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y",
        "%d %b %Y", "%d %B %Y", "%Y/%m/%d"
    ])
    date_output_format: str = "%Y-%m-%d"

    empty_values: list[str] = field(default_factory=lambda: [
        "", "N/A", "n/a", "null", "NULL", "-", "None", "none", "NA", "N.A."
    ])

    @classmethod
    def from_dict(cls, data: dict) -> "CleaningRules":
        """Create CleaningRules from a dictionary."""
        rules = cls()
        if data.get("phone"):
            rules.phone_enabled = data["phone"].get("enabled", True)
            rules.phone_country_code = data["phone"].get("country_code", "234")
            rules.phone_format = data["phone"].get("format", "e164")
        if data.get("email"):
            rules.email_enabled = data["email"].get("enabled", True)
            rules.email_lowercase = data["email"].get("lowercase", True)
            rules.email_fix_typos = data["email"].get("fix_typos", True)
        if data.get("name"):
            rules.name_enabled = data["name"].get("enabled", True)
            rules.name_case = data["name"].get("case", "title")
            rules.name_trim = data["name"].get("trim", True)
        if data.get("address"):
            rules.address_enabled = data["address"].get("enabled", True)
            rules.address_standardize_states = data["address"].get("standardize_states", True)
        if data.get("currency"):
            rules.currency_enabled = data["currency"].get("enabled", True)
            rules.currency_remove_symbols = data["currency"].get("remove_symbols", True)
            rules.currency_decimal_places = data["currency"].get("decimals", 2)
        if data.get("date"):
            rules.date_enabled = data["date"].get("enabled", True)
            if data["date"].get("formats"):
                rules.date_input_formats = data["date"]["formats"]
        if data.get("empty_values"):
            rules.empty_values = data["empty_values"].get("treat_as_null", rules.empty_values)
        return rules


class PhoneNormalizer:
    """Nigerian phone number normalization."""

    # Nigerian mobile prefixes by network
    NETWORK_PREFIXES = {
        # MTN
        "0803", "0806", "0813", "0814", "0816", "0903", "0906", "0913", "0916",
        # Glo
        "0805", "0807", "0811", "0815", "0705", "0905",
        # Airtel
        "0802", "0808", "0812", "0701", "0708", "0902", "0907", "0912",
        # 9mobile
        "0809", "0817", "0818", "0909", "0908",
    }

    def normalize(self, phone: str, country_code: str = "234", output_format: str = "e164") -> CleaningResult:
        """Normalize a phone number.

        Args:
            phone: Raw phone number
            country_code: Country code (default: 234 for Nigeria)
            output_format: Output format (e164, local, international)

        Returns:
            CleaningResult with normalized phone
        """
        if not phone:
            return CleaningResult(value=None, original=phone)

        original = phone
        warnings = []

        # Remove all non-digit characters except leading +
        phone = phone.strip()
        if phone.startswith("+"):
            phone = "+" + re.sub(r"\D", "", phone[1:])
        else:
            phone = re.sub(r"\D", "", phone)

        if not phone:
            return CleaningResult(value=None, original=original, warnings=["Empty phone after cleaning"])

        # Handle different formats
        if phone.startswith("+"):
            # Already has country code
            phone = phone[1:]  # Remove +
        elif phone.startswith(country_code):
            # Has country code without +
            pass
        elif phone.startswith("0"):
            # Local format (e.g., 08012345678)
            phone = country_code + phone[1:]
        else:
            # Assume it needs country code
            phone = country_code + phone

        # Validate length for Nigerian numbers
        if country_code == "234":
            if len(phone) != 13:  # 234 + 10 digits
                warnings.append(f"Unusual phone length: {len(phone)} digits")

            # Check if prefix is valid
            local_number = "0" + phone[3:]
            prefix = local_number[:4]
            if prefix not in self.NETWORK_PREFIXES:
                warnings.append(f"Unknown network prefix: {prefix}")

        # Format output
        if output_format == "e164":
            result = f"+{phone}"
        elif output_format == "local":
            result = "0" + phone[len(country_code):]
        elif output_format == "international":
            result = f"+{phone[:3]} {phone[3:6]} {phone[6:9]} {phone[9:]}"
        else:
            result = f"+{phone}"

        return CleaningResult(value=result, original=original, warnings=warnings)


class EmailNormalizer:
    """Email validation and normalization."""

    # Common email typos
    DOMAIN_TYPOS = {
        "gmial.com": "gmail.com",
        "gmai.com": "gmail.com",
        "gamil.com": "gmail.com",
        "gmail.co": "gmail.com",
        "gmal.com": "gmail.com",
        "hotmal.com": "hotmail.com",
        "hotmai.com": "hotmail.com",
        "hotmial.com": "hotmail.com",
        "yaho.com": "yahoo.com",
        "yahooo.com": "yahoo.com",
        "outloo.com": "outlook.com",
        "outlok.com": "outlook.com",
    }

    EMAIL_REGEX = re.compile(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    )

    def normalize(self, email: str, lowercase: bool = True, fix_typos: bool = True) -> CleaningResult:
        """Normalize an email address.

        Args:
            email: Raw email address
            lowercase: Convert to lowercase
            fix_typos: Fix common domain typos

        Returns:
            CleaningResult with normalized email
        """
        if not email:
            return CleaningResult(value=None, original=email)

        original = email
        warnings = []

        # Strip whitespace
        email = email.strip()

        # Lowercase
        if lowercase:
            email = email.lower()

        # Fix common typos
        if fix_typos and "@" in email:
            local, domain = email.rsplit("@", 1)
            if domain in self.DOMAIN_TYPOS:
                corrected = self.DOMAIN_TYPOS[domain]
                warnings.append(f"Corrected domain: {domain} -> {corrected}")
                domain = corrected
            email = f"{local}@{domain}"

        # Validate format
        if not self.EMAIL_REGEX.match(email):
            warnings.append("Invalid email format")

        return CleaningResult(value=email, original=original, warnings=warnings)


class NameNormalizer:
    """Name normalization."""

    def normalize(self, name: str, case: str = "title", trim: bool = True, remove_extra_spaces: bool = True) -> CleaningResult:
        """Normalize a name.

        Args:
            name: Raw name
            case: Case transformation (title, upper, lower, none)
            trim: Trim whitespace
            remove_extra_spaces: Remove multiple consecutive spaces

        Returns:
            CleaningResult with normalized name
        """
        if not name:
            return CleaningResult(value=None, original=name)

        original = name
        warnings = []

        # Trim
        if trim:
            name = name.strip()

        # Remove extra spaces
        if remove_extra_spaces:
            name = re.sub(r"\s+", " ", name)

        # Case transformation
        if case == "title":
            # Smart title case that handles common exceptions
            name = self._smart_title_case(name)
        elif case == "upper":
            name = name.upper()
        elif case == "lower":
            name = name.lower()

        return CleaningResult(value=name, original=original, warnings=warnings)

    def _smart_title_case(self, name: str) -> str:
        """Smart title case that handles common prefixes/suffixes."""
        # Words that should stay lowercase (unless first word)
        lowercase_words = {"and", "or", "the", "of", "in", "for", "to", "with"}
        # Words that should stay uppercase
        uppercase_words = {"LLC", "LTD", "PLC", "INC", "USA", "UK", "NG"}

        words = name.split()
        result = []
        for i, word in enumerate(words):
            upper_word = word.upper()
            if upper_word in uppercase_words:
                result.append(upper_word)
            elif i > 0 and word.lower() in lowercase_words:
                result.append(word.lower())
            else:
                result.append(word.capitalize())
        return " ".join(result)


class AddressNormalizer:
    """Nigerian address normalization."""

    # Nigerian states with aliases
    STATE_ALIASES = {
        "lagos state": "Lagos",
        "lagos": "Lagos",
        "fct": "FCT",
        "fct abuja": "FCT",
        "abuja": "FCT",
        "federal capital territory": "FCT",
        "akwa ibom": "Akwa Ibom",
        "akwa-ibom": "Akwa Ibom",
        "akwaibom": "Akwa Ibom",
        "cross river": "Cross River",
        "cross-river": "Cross River",
        "crossriver": "Cross River",
        "rivers state": "Rivers",
        "rivers": "Rivers",
        "ogun state": "Ogun",
        "ogun": "Ogun",
        "oyo state": "Oyo",
        "oyo": "Oyo",
        "kano state": "Kano",
        "kano": "Kano",
        "kaduna state": "Kaduna",
        "kaduna": "Kaduna",
        "delta state": "Delta",
        "delta": "Delta",
        "enugu state": "Enugu",
        "enugu": "Enugu",
        "anambra state": "Anambra",
        "anambra": "Anambra",
        "imo state": "Imo",
        "imo": "Imo",
        "edo state": "Edo",
        "edo": "Edo",
        "kwara state": "Kwara",
        "kwara": "Kwara",
        "plateau state": "Plateau",
        "plateau": "Plateau",
        "benue state": "Benue",
        "benue": "Benue",
        "kogi state": "Kogi",
        "kogi": "Kogi",
        "osun state": "Osun",
        "osun": "Osun",
        "ondo state": "Ondo",
        "ondo": "Ondo",
        "ekiti state": "Ekiti",
        "ekiti": "Ekiti",
        "abia state": "Abia",
        "abia": "Abia",
        "ebonyi state": "Ebonyi",
        "ebonyi": "Ebonyi",
        "bayelsa state": "Bayelsa",
        "bayelsa": "Bayelsa",
        "adamawa state": "Adamawa",
        "adamawa": "Adamawa",
        "taraba state": "Taraba",
        "taraba": "Taraba",
        "borno state": "Borno",
        "borno": "Borno",
        "yobe state": "Yobe",
        "yobe": "Yobe",
        "gombe state": "Gombe",
        "gombe": "Gombe",
        "bauchi state": "Bauchi",
        "bauchi": "Bauchi",
        "jigawa state": "Jigawa",
        "jigawa": "Jigawa",
        "katsina state": "Katsina",
        "katsina": "Katsina",
        "kebbi state": "Kebbi",
        "kebbi": "Kebbi",
        "sokoto state": "Sokoto",
        "sokoto": "Sokoto",
        "zamfara state": "Zamfara",
        "zamfara": "Zamfara",
        "niger state": "Niger",
        "niger": "Niger",
        "nasarawa state": "Nasarawa",
        "nasarawa": "Nasarawa",
    }

    VALID_STATES = [
        "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa",
        "Benue", "Borno", "Cross River", "Delta", "Ebonyi", "Edo",
        "Ekiti", "Enugu", "FCT", "Gombe", "Imo", "Jigawa", "Kaduna",
        "Kano", "Katsina", "Kebbi", "Kogi", "Kwara", "Lagos", "Nasarawa",
        "Niger", "Ogun", "Ondo", "Osun", "Oyo", "Plateau", "Rivers",
        "Sokoto", "Taraba", "Yobe", "Zamfara"
    ]

    def normalize(self, value: str, standardize_states: bool = True) -> CleaningResult:
        """Normalize an address or state.

        Args:
            value: Address or state string
            standardize_states: Standardize Nigerian state names

        Returns:
            CleaningResult with normalized value
        """
        if not value:
            return CleaningResult(value=None, original=value)

        original = value
        warnings = []

        # Trim and clean
        value = value.strip()
        value = re.sub(r"\s+", " ", value)

        # Try to standardize state if it's a state value
        if standardize_states:
            lower_value = value.lower()
            if lower_value in self.STATE_ALIASES:
                standardized = self.STATE_ALIASES[lower_value]
                if standardized != value:
                    warnings.append(f"Standardized state: {value} -> {standardized}")
                value = standardized
            elif value not in self.VALID_STATES and len(value) < 30:
                # Might be an unknown state abbreviation
                warnings.append(f"Unknown state format: {value}")

        return CleaningResult(value=value, original=original, warnings=warnings)


class CurrencyNormalizer:
    """Currency value normalization."""

    CURRENCY_SYMBOLS = {
        "₦": "NGN",
        "$": "USD",
        "€": "EUR",
        "£": "GBP",
        "¥": "JPY",
    }

    def normalize(self, value: str | int | float, remove_symbols: bool = True, decimal_places: int = 2) -> CleaningResult:
        """Normalize a currency value.

        Args:
            value: Raw currency value
            remove_symbols: Remove currency symbols
            decimal_places: Number of decimal places

        Returns:
            CleaningResult with normalized Decimal value
        """
        if value is None:
            return CleaningResult(value=None, original=value)

        original = value
        warnings = []

        # Handle numeric types directly
        if isinstance(value, (int, float, Decimal)):
            try:
                result = round(Decimal(str(value)), decimal_places)
                return CleaningResult(value=result, original=original)
            except (InvalidOperation, ValueError):
                return CleaningResult(value=None, original=original, warnings=["Invalid numeric value"])

        # Handle string values
        value = str(value).strip()

        if not value:
            return CleaningResult(value=None, original=original)

        # Remove currency symbols
        if remove_symbols:
            for symbol in self.CURRENCY_SYMBOLS.keys():
                value = value.replace(symbol, "")

        # Remove common formatting
        value = value.replace(",", "")  # Remove thousands separator
        value = value.replace(" ", "")  # Remove spaces
        value = value.strip()

        # Handle parentheses for negative values
        if value.startswith("(") and value.endswith(")"):
            value = "-" + value[1:-1]

        try:
            result = round(Decimal(value), decimal_places)
            if result < 0:
                warnings.append("Negative value")
            return CleaningResult(value=result, original=original, warnings=warnings)
        except (InvalidOperation, ValueError) as e:
            return CleaningResult(value=None, original=original, warnings=[f"Invalid currency value: {e}"])


class DateNormalizer:
    """Date normalization with multi-format support."""

    def normalize(
        self,
        value: str | date | datetime,
        input_formats: Optional[list[str]] = None,
        output_format: str = "%Y-%m-%d"
    ) -> CleaningResult:
        """Normalize a date value.

        Args:
            value: Raw date value
            input_formats: List of input formats to try
            output_format: Output format string

        Returns:
            CleaningResult with normalized date string
        """
        if value is None:
            return CleaningResult(value=None, original=value)

        original = value
        warnings = []

        # Handle date/datetime objects
        if isinstance(value, datetime):
            return CleaningResult(value=value.strftime(output_format), original=original)
        if isinstance(value, date):
            return CleaningResult(value=value.strftime(output_format), original=original)

        # Handle string values
        value = str(value).strip()

        if not value:
            return CleaningResult(value=None, original=original)

        # Default input formats
        if not input_formats:
            input_formats = [
                "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y",
                "%d %b %Y", "%d %B %Y", "%Y/%m/%d",
                "%d.%m.%Y", "%Y.%m.%d",
            ]

        # Try each format
        for fmt in input_formats:
            try:
                parsed = datetime.strptime(value, fmt)
                result = parsed.strftime(output_format)
                return CleaningResult(value=result, original=original, warnings=warnings)
            except ValueError:
                continue

        # Try ISO format as fallback
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            result = parsed.strftime(output_format)
            return CleaningResult(value=result, original=original, warnings=warnings)
        except ValueError:
            pass

        warnings.append(f"Could not parse date: {value}")
        return CleaningResult(value=None, original=original, warnings=warnings)


class DataCleaningPipeline:
    """Main data cleaning pipeline."""

    def __init__(self, rules: Optional[CleaningRules] = None):
        """Initialize the pipeline.

        Args:
            rules: Cleaning rules configuration
        """
        self.rules = rules or CleaningRules()
        self.normalizers = {
            "phone": PhoneNormalizer(),
            "email": EmailNormalizer(),
            "name": NameNormalizer(),
            "address": AddressNormalizer(),
            "currency": CurrencyNormalizer(),
            "date": DateNormalizer(),
        }

    def clean_value(self, value: Any, normalizer: str) -> CleaningResult:
        """Clean a single value with a specific normalizer.

        Args:
            value: Value to clean
            normalizer: Normalizer type to use

        Returns:
            CleaningResult
        """
        # Check for empty values
        if value is None:
            return CleaningResult(value=None, original=value)
        if isinstance(value, str) and value.strip() in self.rules.empty_values:
            return CleaningResult(value=None, original=value, warnings=["Treated as null"])

        if normalizer == "phone" and self.rules.phone_enabled:
            return self.normalizers["phone"].normalize(
                value,
                country_code=self.rules.phone_country_code,
                output_format=self.rules.phone_format
            )
        elif normalizer == "email" and self.rules.email_enabled:
            return self.normalizers["email"].normalize(
                value,
                lowercase=self.rules.email_lowercase,
                fix_typos=self.rules.email_fix_typos
            )
        elif normalizer == "name" and self.rules.name_enabled:
            return self.normalizers["name"].normalize(
                value,
                case=self.rules.name_case,
                trim=self.rules.name_trim,
                remove_extra_spaces=self.rules.name_remove_extra_spaces
            )
        elif normalizer == "address" and self.rules.address_enabled:
            return self.normalizers["address"].normalize(
                value,
                standardize_states=self.rules.address_standardize_states
            )
        elif normalizer == "currency" and self.rules.currency_enabled:
            return self.normalizers["currency"].normalize(
                value,
                remove_symbols=self.rules.currency_remove_symbols,
                decimal_places=self.rules.currency_decimal_places
            )
        elif normalizer == "date" and self.rules.date_enabled:
            return self.normalizers["date"].normalize(
                value,
                input_formats=self.rules.date_input_formats,
                output_format=self.rules.date_output_format
            )
        else:
            # No normalization, just return value
            return CleaningResult(value=value, original=value)

    def clean_row(
        self,
        row: dict[str, Any],
        field_normalizers: dict[str, str]
    ) -> tuple[dict[str, Any], list[dict]]:
        """Clean a row of data.

        Args:
            row: Dict of field -> value
            field_normalizers: Dict of field -> normalizer type

        Returns:
            Tuple of (cleaned_row, warnings)
        """
        cleaned = {}
        all_warnings = []

        for field, value in row.items():
            normalizer = field_normalizers.get(field)
            if normalizer:
                result = self.clean_value(value, normalizer)
                cleaned[field] = result.value
                if result.warnings:
                    all_warnings.append({
                        "field": field,
                        "original": result.original,
                        "cleaned": result.value,
                        "warnings": result.warnings
                    })
            else:
                # No normalizer specified, handle empty values
                if isinstance(value, str) and value.strip() in self.rules.empty_values:
                    cleaned[field] = None
                else:
                    cleaned[field] = value

        return cleaned, all_warnings
