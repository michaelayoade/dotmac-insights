"""
Phone and email normalization utilities.

Provides standardization of contact data to improve data quality.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Dict, Any


# Nigerian mobile prefixes (MTN, Glo, Airtel, 9mobile)
NIGERIAN_MOBILE_PREFIXES = {
    # MTN
    "0703", "0706", "0803", "0806", "0810", "0813", "0814", "0816", "0903", "0906", "0913",
    # Glo
    "0705", "0805", "0807", "0811", "0815", "0905", "0915",
    # Airtel
    "0701", "0708", "0802", "0808", "0812", "0901", "0902", "0904", "0907", "0912",
    # 9mobile (formerly Etisalat)
    "0809", "0817", "0818", "0908", "0909",
}

# Common invalid phone patterns
INVALID_PHONE_PATTERNS = [
    r"^0{5,}$",  # All zeros
    r"^1234567890$",  # Sequential
    r"^0000000000$",  # All zeros with leading zero
    r"^000",  # Starts with 000
]

# Email validation pattern
EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)

# Common disposable email domains
DISPOSABLE_DOMAINS = {
    "tempmail.com", "throwaway.email", "guerrillamail.com", "mailinator.com",
    "10minutemail.com", "trashmail.com", "fakeinbox.com", "getnada.com",
}


@dataclass
class NormalizedPhone:
    """Result of phone normalization."""
    original: str
    normalized: Optional[str]  # E.164 format or None if invalid
    is_valid: bool
    country_code: Optional[str]  # e.g., "+234"
    national_number: Optional[str]  # e.g., "8012345678"
    phone_type: Optional[str]  # "mobile", "landline", "unknown"
    carrier_prefix: Optional[str]  # e.g., "0801"
    error: Optional[str]  # Error message if invalid


@dataclass
class NormalizedEmail:
    """Result of email normalization."""
    original: str
    normalized: Optional[str]  # Lowercase, trimmed
    is_valid: bool
    local_part: Optional[str]  # Before @
    domain: Optional[str]  # After @
    is_disposable: bool
    error: Optional[str]


def normalize_phone(phone: str, country: str = "NG") -> NormalizedPhone:
    """Normalize phone number to E.164 format.

    Supports Nigerian phone numbers with various input formats:
    - 0801234567 → +2348012345678
    - +2348012345678 → +2348012345678
    - 234-801-234-5678 → +2348012345678
    - 08012345678 → +2348012345678

    Args:
        phone: The phone number to normalize
        country: Country code (default "NG" for Nigeria)

    Returns:
        NormalizedPhone with normalization results
    """
    if not phone:
        return NormalizedPhone(
            original=phone or "",
            normalized=None,
            is_valid=False,
            country_code=None,
            national_number=None,
            phone_type=None,
            carrier_prefix=None,
            error="Empty phone number",
        )

    original = phone
    # Remove all non-digit characters except +
    cleaned = "".join(c for c in phone if c.isdigit() or c == "+")

    # Check for invalid patterns
    digits_only = "".join(c for c in cleaned if c.isdigit())
    for pattern in INVALID_PHONE_PATTERNS:
        if re.match(pattern, digits_only):
            return NormalizedPhone(
                original=original,
                normalized=None,
                is_valid=False,
                country_code=None,
                national_number=None,
                phone_type=None,
                carrier_prefix=None,
                error=f"Invalid phone pattern: {pattern}",
            )

    if country == "NG":
        return _normalize_nigerian_phone(original, cleaned)

    # Generic international handling
    if cleaned.startswith("+"):
        return NormalizedPhone(
            original=original,
            normalized=cleaned,
            is_valid=len(cleaned) >= 10,
            country_code=cleaned[:4] if len(cleaned) >= 4 else None,
            national_number=cleaned[4:] if len(cleaned) > 4 else None,
            phone_type="unknown",
            carrier_prefix=None,
            error=None if len(cleaned) >= 10 else "Phone number too short",
        )

    return NormalizedPhone(
        original=original,
        normalized=None,
        is_valid=False,
        country_code=None,
        national_number=None,
        phone_type=None,
        carrier_prefix=None,
        error=f"Unsupported country: {country}",
    )


def _normalize_nigerian_phone(original: str, cleaned: str) -> NormalizedPhone:
    """Normalize Nigerian phone number."""
    # Remove + if present for processing
    digits = cleaned.lstrip("+")

    # Handle different formats
    national_number = None
    carrier_prefix = None

    if digits.startswith("234"):
        # Already has country code: 2348012345678
        national_number = digits[3:]
    elif digits.startswith("0"):
        # Local format: 08012345678
        national_number = digits[1:]
    else:
        # Might be missing leading zero: 8012345678
        national_number = digits

    # Validate length (should be 10 digits for national number)
    if not national_number or len(national_number) != 10:
        return NormalizedPhone(
            original=original,
            normalized=None,
            is_valid=False,
            country_code="+234",
            national_number=national_number,
            phone_type=None,
            carrier_prefix=None,
            error=f"Invalid length: expected 10 digits, got {len(national_number or '')}",
        )

    # Check carrier prefix
    carrier_prefix = "0" + national_number[:3]
    is_mobile = carrier_prefix in NIGERIAN_MOBILE_PREFIXES

    # Format as E.164
    normalized = f"+234{national_number}"

    return NormalizedPhone(
        original=original,
        normalized=normalized,
        is_valid=True,
        country_code="+234",
        national_number=national_number,
        phone_type="mobile" if is_mobile else "landline",
        carrier_prefix=carrier_prefix,
        error=None,
    )


def normalize_email(email: str) -> NormalizedEmail:
    """Normalize email address.

    Applies:
    - Lowercase conversion
    - Whitespace trimming
    - Format validation
    - Disposable domain detection

    Args:
        email: The email address to normalize

    Returns:
        NormalizedEmail with normalization results
    """
    if not email:
        return NormalizedEmail(
            original=email or "",
            normalized=None,
            is_valid=False,
            local_part=None,
            domain=None,
            is_disposable=False,
            error="Empty email address",
        )

    original = email
    # Trim and lowercase
    cleaned = email.strip().lower()

    # Validate format
    if not EMAIL_PATTERN.match(cleaned):
        return NormalizedEmail(
            original=original,
            normalized=None,
            is_valid=False,
            local_part=None,
            domain=None,
            is_disposable=False,
            error="Invalid email format",
        )

    # Split into parts
    local_part, domain = cleaned.rsplit("@", 1)

    # Check for disposable domain
    is_disposable = domain in DISPOSABLE_DOMAINS

    return NormalizedEmail(
        original=original,
        normalized=cleaned,
        is_valid=True,
        local_part=local_part,
        domain=domain,
        is_disposable=is_disposable,
        error=None,
    )


def is_valid_phone(phone: str, country: str = "NG") -> bool:
    """Quick check if phone is valid without full normalization."""
    result = normalize_phone(phone, country)
    return result.is_valid


def is_valid_email(email: str) -> bool:
    """Quick check if email is valid without full normalization."""
    result = normalize_email(email)
    return result.is_valid


def detect_duplicates(
    records: List[Dict[str, Any]],
    match_fields: List[str],
    case_insensitive: bool = True,
) -> Dict[str, List[int]]:
    """Detect duplicate records by matching field values.

    Args:
        records: List of record dicts with 'id' key
        match_fields: Fields to match on (e.g., ["primary_email"])
        case_insensitive: Whether to match case-insensitively

    Returns:
        Dict mapping match_key to list of record IDs that share that value
    """
    # Build index of values to record IDs
    value_to_ids: Dict[str, List[int]] = {}

    for record in records:
        record_id = record.get("id")
        if record_id is None:
            continue

        # Build match key from fields
        key_parts = []
        for field in match_fields:
            value = record.get(field)
            if value is None:
                break
            if case_insensitive and isinstance(value, str):
                value = value.lower().strip()
            key_parts.append(str(value))

        if len(key_parts) != len(match_fields):
            # Skip records with missing match fields
            continue

        match_key = "|".join(key_parts)

        if match_key not in value_to_ids:
            value_to_ids[match_key] = []
        value_to_ids[match_key].append(record_id)

    # Filter to only duplicates (2+ records with same key)
    duplicates = {
        key: ids
        for key, ids in value_to_ids.items()
        if len(ids) > 1
    }

    return duplicates
