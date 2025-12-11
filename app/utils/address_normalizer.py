"""
Address normalization utilities for Nigerian addresses.

Handles cleaning and standardizing city/state data, particularly for
FCT/Abuja which has 30+ common variations in the source data.
"""

import re
from typing import Optional, Tuple, TypedDict, Dict


class CityMetadata(TypedDict):
    original: Optional[str]
    gps_extracted: Optional[Tuple[float, float]]
    is_invalid: bool
    area: Optional[str]

# Nigerian states and their major cities
NIGERIAN_STATES = {
    "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue",
    "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu",
    "FCT", "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi",
    "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo", "Osun",
    "Oyo", "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara"
}

# City to State mapping for common Nigerian cities
CITY_TO_STATE = {
    "Abuja": "FCT",
    "Lagos": "Lagos",
    "Ibadan": "Oyo",
    "Kano": "Kano",
    "Port Harcourt": "Rivers",
    "Benin City": "Edo",
    "Kaduna": "Kaduna",
    "Enugu": "Enugu",
    "Warri": "Delta",
    "Ilorin": "Kwara",
    "Jos": "Plateau",
    "Owerri": "Imo",
    "Abeokuta": "Ogun",
    "Akure": "Ondo",
    "Oshogbo": "Osun",
    "Awka": "Anambra",
    "Yola": "Adamawa",
    "Calabar": "Cross River",
    "Uyo": "Akwa Ibom",
    "Asaba": "Delta",
    "Makurdi": "Benue",
    "Minna": "Niger",
    "Lokoja": "Kogi",
    "Lafia": "Nasarawa",
    "Ado Ekiti": "Ekiti",
    # FCT areas (all map to Abuja city, FCT state)
    "Maitama": "FCT",
    "Wuse": "FCT",
    "Garki": "FCT",
    "Asokoro": "FCT",
    "Gwarinpa": "FCT",
    "Jabi": "FCT",
    "Kubwa": "FCT",
    "Lugbe": "FCT",
    "Karu": "FCT",
    "Nyanya": "FCT",
    "Mararaba": "FCT",
    "Gwagwalada": "FCT",
    "Kuje": "FCT",
    "Bwari": "FCT",
    "Dutse": "FCT",
    "Apo": "FCT",
    "Gudu": "FCT",
    "Guzape": "FCT",
    "Katampe": "FCT",
    "Lifecamp": "FCT",
    "Lokogoma": "FCT",
    "Galadimawa": "FCT",
    "Utako": "FCT",
    "Wuye": "FCT",
    "Maraba": "FCT",  # Spelling variant of Mararaba
    "Marababa": "FCT",  # Common misspelling
    "Cbd": "FCT",  # Central Business District
    # Lagos areas
    "Ikeja": "Lagos",
    "Lekki": "Lagos",
    "Victoria Island": "Lagos",
    "Ikoyi": "Lagos",
    "Surulere": "Lagos",
    "Yaba": "Lagos",
    "Ajah": "Lagos",
    "Festac": "Lagos",
    "Oshodi": "Lagos",
    "Mushin": "Lagos",
    "Alimosho": "Lagos",
    "Ikorodu": "Lagos",
    "Badagry": "Lagos",
    "Epe": "Lagos",
    "Apapa": "Lagos",
    "Bariga": "Lagos",
    "Ipaja": "Lagos",
    "Ayobo": "Lagos",
    "Abule Egba": "Lagos",
    "Ilasamaja": "Lagos",
    "Dopemu": "Lagos",
    "Ogudu": "Lagos",
}

# Patterns that indicate FCT/Abuja (case-insensitive)
FCT_PATTERNS = [
    r"^f\.?c\.?t\.?$",  # FCT, F.C.T, F.C.T., fct, etc.
    r"^f[.,]?c[.,]?t[.,]?$",  # Handle typos: F.C,T, F,C.T, etc.
    r"^f[.,]?c[.,]?[rt]?[.,]?\s*[-,<]?\s*a\s?buja\.?$",  # FCT Abuja with typos: F.C.R, F.C. Abuja, "A Buja", Fct< Abuja
    r"^f[.,]+c[.,]+t?\s*[-,<]?\s*abuja\.?$",  # F,C.T Abuja, F,.C.T Abuja, F.C. Abuja
    r"^abuja\s*[-,]?\s*f\.?c\.?t\.?$",  # Abuja FCT, Abuja, FCT
    r"^federal\s+capital\s+territory",  # Federal Capital Territory
    r"^abuja\.?$",  # Abuja, Abuja.
    r"^cbd$",  # Central Business District (Abuja)
    r"^central\s+business\s+district",  # Central Business District
    r"^.+,\s*abuja(\s+fct)?\.?$",  # "Area, Abuja" or "Area, Abuja FCT"
]

# Patterns that indicate Lagos
LAGOS_PATTERNS = [
    r"^lagos\.?$",
    r"^lagos\s+city$",
    r"^lagos\s+state$",
    r",\s*lagos$",  # "Surulere, Lagos"
]

# Pattern to detect numeric IDs (invalid city values)
NUMERIC_ID_PATTERN = r"^1000\d{5,}$"

# Pattern to detect GPS coordinates
GPS_PATTERN = r"^-?\d+\.\d+\s*,\s*-?\d+\.\d+$"

# Patterns that indicate invalid city data (addresses, attention lines, etc.)
INVALID_CITY_PATTERNS = [
    r"^attn:",  # Attention line
    r"^\d+\s+",  # Starts with house number
    r"\b(close|crescent|street|avenue|road|estate|compound|layout)\b",  # Address keywords
    r"^no\.?\s*\d+",  # "No. 11" or "No 5"
    r"^plot\s+\d+",  # "Plot 123"
    r"^new\s+york$",  # Obviously wrong
]

# States that might appear in city field (should be moved to state)
STATES_IN_CITY = {"Delta", "Osun", "Ondo", "Oyo", "Lagos"}


def _clean_string(value: Optional[str]) -> Optional[str]:
    """Clean whitespace and trailing punctuation from a string."""
    if not value:
        return None
    # Strip whitespace
    cleaned = value.strip()
    # Remove trailing periods and commas
    cleaned = cleaned.rstrip(".,").strip()
    if not cleaned:
        return None
    return cleaned


def _is_numeric_id(value: str) -> bool:
    """Check if value looks like a numeric ID (not a valid city)."""
    return bool(re.match(NUMERIC_ID_PATTERN, value))


def _is_gps_coordinates(value: str) -> bool:
    """Check if value looks like GPS coordinates."""
    return bool(re.match(GPS_PATTERN, value.strip()))


def _is_invalid_city(value: str) -> bool:
    """Check if value looks like an address or other invalid city data."""
    value_lower = value.lower().strip()
    for pattern in INVALID_CITY_PATTERNS:
        if re.search(pattern, value_lower):
            return True
    return False


def _is_state_in_city_field(value: str) -> Optional[str]:
    """Check if value is a state name appearing in city field."""
    cleaned = value.strip().title()
    if cleaned in STATES_IN_CITY:
        return cleaned
    return None


def _extract_gps_from_city(value: str) -> Optional[Tuple[float, float]]:
    """Extract GPS coordinates if city field contains them."""
    if not _is_gps_coordinates(value):
        return None
    try:
        parts = [p.strip() for p in value.split(",")]
        lat, lng = float(parts[0]), float(parts[1])
        if -90 <= lat <= 90 and -180 <= lng <= 180:
            return (lat, lng)
    except (ValueError, IndexError):
        pass
    return None


def _matches_fct_pattern(value: str) -> bool:
    """Check if value matches any FCT/Abuja pattern."""
    value_lower = value.lower().strip()
    for pattern in FCT_PATTERNS:
        if re.match(pattern, value_lower):
            return True
    return False


def _matches_lagos_pattern(value: str) -> bool:
    """Check if value matches any Lagos pattern."""
    value_lower = value.lower().strip()
    for pattern in LAGOS_PATTERNS:
        if re.search(pattern, value_lower):
            return True
    return False


def _extract_area_from_fct_string(value: str) -> Optional[str]:
    """Extract area name from FCT string like 'Katampe Main, Abuja FCT' or 'Gwarimpa, Abuja'."""
    # Remove common FCT/Abuja suffixes
    cleaned = re.sub(r"\s*,?\s*(abuja|f\.?c\.?t\.?|federal capital territory).*$", "", value, flags=re.IGNORECASE)
    cleaned = cleaned.strip().rstrip(",").strip()

    # Check if what's left is a known FCT area
    if cleaned:
        cleaned_title = cleaned.title()
        # Direct match
        if cleaned_title in CITY_TO_STATE and CITY_TO_STATE[cleaned_title] == "FCT":
            return cleaned_title
        # Handle multi-word areas - check first word
        first_word = cleaned_title.split()[0] if cleaned_title.split() else ""
        if first_word in CITY_TO_STATE and CITY_TO_STATE[first_word] == "FCT":
            return cleaned_title  # Return full area name
        # If it's a reasonable area name (not a pattern match), return it
        if len(cleaned_title) > 2 and not re.match(r"^f[.,]?c", cleaned_title.lower()):
            return cleaned_title
    return None


def _extract_known_area(value: str, state_areas: Dict[str, str], target_state: str) -> Optional[str]:
    """Extract a known area from a compound string like 'D-Dopemu 4' or 'Good Homes Lokogoma'."""
    value_lower = value.lower()
    for area, state in state_areas.items():
        if state == target_state and area.lower() in value_lower:
            return area
    return None


def normalize_city(raw_city: Optional[str]) -> Tuple[Optional[str], Optional[str], CityMetadata]:
    """
    Normalize a city value and infer state.

    Returns:
        Tuple of (normalized_city, inferred_state, metadata)

        metadata contains:
        - 'original': the original value
        - 'gps_extracted': GPS coordinates if found in city field
        - 'is_invalid': True if the value was invalid (numeric ID, etc.)
        - 'area': specific area/neighborhood if detected
    """
    metadata: CityMetadata = {
        "original": raw_city,
        "gps_extracted": None,
        "is_invalid": False,
        "area": None,
    }

    if not raw_city:
        return None, None, metadata

    # Clean the string
    cleaned = _clean_string(raw_city)
    if not cleaned:
        return None, None, metadata

    # Check for invalid values
    if _is_numeric_id(cleaned):
        metadata["is_invalid"] = True
        return None, None, metadata

    # Check for GPS coordinates in city field
    gps = _extract_gps_from_city(cleaned)
    if gps:
        metadata["gps_extracted"] = gps
        metadata["is_invalid"] = True
        return None, None, metadata

    # Check for obviously invalid data (too short, contains only special chars, etc.)
    if len(cleaned) < 2 or re.match(r"^[\d\W]+$", cleaned):
        metadata["is_invalid"] = True
        return None, None, metadata

    # Check for addresses or other invalid city data
    if _is_invalid_city(cleaned):
        metadata["is_invalid"] = True
        return None, None, metadata

    # Check if it's just a state name in city field (e.g., "Delta")
    state_only = _is_state_in_city_field(cleaned)
    if state_only:
        # Return None for city but infer state
        return None, state_only, metadata

    # Check FCT patterns first (most common)
    if _matches_fct_pattern(cleaned):
        # Try to extract specific area
        area = _extract_area_from_fct_string(cleaned)
        if area:
            metadata["area"] = area
        return "Abuja", "FCT", metadata

    # Check Lagos patterns
    if _matches_lagos_pattern(cleaned):
        return "Lagos", "Lagos", metadata

    # Check if it's a known city/area
    cleaned_title = cleaned.title()

    # Direct city match
    if cleaned_title in CITY_TO_STATE:
        state = CITY_TO_STATE[cleaned_title]
        # For FCT areas, normalize city to "Abuja"
        if state == "FCT":
            metadata["area"] = cleaned_title
            return "Abuja", "FCT", metadata
        return cleaned_title, state, metadata

    # Check first word for areas like "Lekki Phase 1", "Apo 1"
    first_word = cleaned_title.split()[0] if cleaned_title.split() else ""
    if first_word in CITY_TO_STATE:
        state = CITY_TO_STATE[first_word]
        if state == "FCT":
            metadata["area"] = cleaned_title
            return "Abuja", "FCT", metadata
        elif state == "Lagos":
            metadata["area"] = cleaned_title
            return "Lagos", "Lagos", metadata
        return first_word, state, metadata

    # Handle "City, State" or "State, City" format (e.g., "Surulere, Lagos" or "Osun, Oshogbo")
    if "," in cleaned:
        parts = [p.strip() for p in cleaned.split(",")]
        if len(parts) >= 2:
            potential_city = parts[0].title()
            potential_state = parts[-1].title()

            # Check if state part is valid (normal "City, State" format)
            if potential_state in NIGERIAN_STATES or potential_state.upper() == "FCT":
                if potential_state.upper() == "FCT":
                    metadata["area"] = potential_city
                    return "Abuja", "FCT", metadata
                return potential_city, potential_state, metadata

            # Check if city part is known
            if potential_city in CITY_TO_STATE:
                return potential_city, CITY_TO_STATE[potential_city], metadata

            # Check for reversed "State, City" format (e.g., "Osun, Oshogbo")
            if potential_city in NIGERIAN_STATES:
                # First part is a state, second part is likely the city
                if potential_state in CITY_TO_STATE:
                    return potential_state, potential_city, metadata
                # Return the city part with the state
                return potential_state, potential_city, metadata

    # Handle "City State" format without comma (e.g., "Oshogbo Osun")
    words = cleaned_title.split()
    if len(words) >= 2:
        last_word = words[-1]
        if last_word in NIGERIAN_STATES:
            city_part = " ".join(words[:-1])
            return city_part, last_word, metadata

    # Check for embedded FCT areas (e.g., "Good Homes Lokogoma", "D-Dopemu 4")
    fct_area = _extract_known_area(cleaned, CITY_TO_STATE, "FCT")
    if fct_area:
        metadata["area"] = cleaned_title
        return "Abuja", "FCT", metadata

    # Check for embedded Lagos areas
    lagos_area = _extract_known_area(cleaned, CITY_TO_STATE, "Lagos")
    if lagos_area:
        metadata["area"] = cleaned_title
        return "Lagos", "Lagos", metadata

    # Return cleaned value as-is if we can't normalize
    return cleaned_title, None, metadata


def normalize_state(raw_state: Optional[str]) -> Optional[str]:
    """
    Normalize a state value.

    Returns the canonical state name or None if invalid.
    """
    if not raw_state:
        return None

    cleaned = _clean_string(raw_state)
    if not cleaned:
        return None

    # Title case for comparison
    cleaned_title = cleaned.title()

    # Direct match
    if cleaned_title in NIGERIAN_STATES:
        return cleaned_title

    # Handle FCT variations
    if re.match(r"^f\.?c\.?t\.?$", cleaned.lower()):
        return "FCT"
    if "federal capital" in cleaned.lower():
        return "FCT"

    # Handle "State" suffix (e.g., "Lagos State" -> "Lagos")
    if cleaned_title.endswith(" State"):
        without_suffix = cleaned_title[:-6].strip()
        if without_suffix in NIGERIAN_STATES:
            return without_suffix

    return None


def normalize_address(
    raw_city: Optional[str],
    raw_state: Optional[str] = None,
    current_lat: Optional[float] = None,
    current_lng: Optional[float] = None,
) -> dict:
    """
    Normalize city and state values together.

    Args:
        raw_city: Raw city value from source
        raw_state: Raw state value from source
        current_lat: Current latitude (won't be overwritten if present)
        current_lng: Current longitude (won't be overwritten if present)

    Returns:
        Dictionary with:
        - 'city': Normalized city name
        - 'state': Normalized/inferred state name
        - 'area': Specific area/neighborhood if detected
        - 'latitude': Extracted latitude (only if GPS was in city field and no current coords)
        - 'longitude': Extracted longitude (only if GPS was in city field and no current coords)
        - 'original_city': Original city value
        - 'original_state': Original state value
        - 'was_invalid': Whether original city was invalid data
    """
    # Normalize city (may also infer state)
    city, inferred_state, metadata = normalize_city(raw_city)

    # Normalize explicit state if provided
    normalized_state = normalize_state(raw_state)

    # Use explicit state if valid, otherwise use inferred
    final_state = normalized_state or inferred_state

    # Extract GPS if present in city and no current coordinates
    latitude = None
    longitude = None
    gps_coords = metadata.get("gps_extracted")
    if gps_coords is not None and current_lat is None and current_lng is None:
        latitude, longitude = gps_coords

    return {
        "city": city,
        "state": final_state,
        "area": metadata.get("area"),
        "latitude": latitude,
        "longitude": longitude,
        "original_city": raw_city,
        "original_state": raw_state,
        "was_invalid": metadata.get("is_invalid", False),
    }
