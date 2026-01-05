"""Type definitions for lifecycle service.

These dataclasses define the contract for employee lifecycle operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from app.models.hr_lifecycle import BoardingStatus

__all__ = [
    # Onboarding
    "OnboardingFilters",
    "OnboardingCreateData",
    "OnboardingUpdateData",
    "OnboardingActivityData",
    # Separation
    "SeparationFilters",
    "SeparationCreateData",
    "SeparationUpdateData",
    "SeparationActivityData",
    # Promotion
    "PromotionFilters",
    "PromotionCreateData",
    "PromotionUpdateData",
    "PromotionDetailData",
    # Transfer
    "TransferFilters",
    "TransferCreateData",
    "TransferUpdateData",
    "TransferDetailData",
    # Results
    "LifecycleMetrics",
    "EmployeeLifecycleHistory",
]


# ==============================================================================
# Onboarding Types
# ==============================================================================


@dataclass
class OnboardingActivityData:
    """Activity in an onboarding process."""

    activity_name: str
    user: Optional[str] = None
    role: Optional[str] = None
    required_for_employee_creation: bool = False
    status: str = "Pending"
    completed_on: Optional[date] = None
    idx: int = 0


@dataclass
class OnboardingFilters:
    """Filters for listing onboardings."""

    employee_id: Optional[int] = None
    boarding_status: Optional[BoardingStatus] = None
    company: Optional[str] = None
    department: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    search: Optional[str] = None  # Search employee name


@dataclass
class OnboardingCreateData:
    """Data for creating an onboarding."""

    employee_id: int
    employee: str
    date_of_joining: date
    employee_name: Optional[str] = None
    job_applicant: Optional[str] = None
    job_offer: Optional[str] = None
    company: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    employee_onboarding_template: Optional[str] = None
    activities: List[OnboardingActivityData] = field(default_factory=list)


@dataclass
class OnboardingUpdateData:
    """Data for updating an onboarding (all fields optional)."""

    date_of_joining: Optional[date] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    activities: Optional[List[OnboardingActivityData]] = None


# ==============================================================================
# Separation Types
# ==============================================================================


@dataclass
class SeparationActivityData:
    """Activity in a separation process."""

    activity_name: str
    user: Optional[str] = None
    role: Optional[str] = None
    status: str = "Pending"
    completed_on: Optional[date] = None
    idx: int = 0


@dataclass
class SeparationFilters:
    """Filters for listing separations."""

    employee_id: Optional[int] = None
    boarding_status: Optional[BoardingStatus] = None
    company: Optional[str] = None
    department: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    search: Optional[str] = None  # Search employee name


@dataclass
class SeparationCreateData:
    """Data for creating a separation."""

    employee_id: int
    employee: str
    separation_date: date
    employee_name: Optional[str] = None
    resignation_letter_date: Optional[date] = None
    company: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    reason_for_leaving: Optional[str] = None
    exit_interview: Optional[str] = None
    employee_separation_template: Optional[str] = None
    activities: List[SeparationActivityData] = field(default_factory=list)


@dataclass
class SeparationUpdateData:
    """Data for updating a separation (all fields optional)."""

    separation_date: Optional[date] = None
    resignation_letter_date: Optional[date] = None
    reason_for_leaving: Optional[str] = None
    exit_interview: Optional[str] = None
    activities: Optional[List[SeparationActivityData]] = None


# ==============================================================================
# Promotion Types
# ==============================================================================


@dataclass
class PromotionDetailData:
    """Detail of what changed in a promotion."""

    property: str  # designation, department, grade, etc.
    current: Optional[str] = None
    new: Optional[str] = None
    idx: int = 0


@dataclass
class PromotionFilters:
    """Filters for listing promotions."""

    employee_id: Optional[int] = None
    company: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    search: Optional[str] = None


@dataclass
class PromotionCreateData:
    """Data for creating a promotion."""

    employee_id: int
    employee: str
    promotion_date: date
    employee_name: Optional[str] = None
    company: Optional[str] = None
    details: List[PromotionDetailData] = field(default_factory=list)


@dataclass
class PromotionUpdateData:
    """Data for updating a promotion (all fields optional)."""

    promotion_date: Optional[date] = None
    details: Optional[List[PromotionDetailData]] = None


# ==============================================================================
# Transfer Types
# ==============================================================================


@dataclass
class TransferDetailData:
    """Detail of what changed in a transfer."""

    property: str  # department, branch, company, etc.
    current: Optional[str] = None
    new: Optional[str] = None
    idx: int = 0


@dataclass
class TransferFilters:
    """Filters for listing transfers."""

    employee_id: Optional[int] = None
    company: Optional[str] = None
    new_company: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    search: Optional[str] = None


@dataclass
class TransferCreateData:
    """Data for creating a transfer."""

    employee_id: int
    employee: str
    transfer_date: date
    employee_name: Optional[str] = None
    company: Optional[str] = None
    new_company: Optional[str] = None
    details: List[TransferDetailData] = field(default_factory=list)


@dataclass
class TransferUpdateData:
    """Data for updating a transfer (all fields optional)."""

    transfer_date: Optional[date] = None
    new_company: Optional[str] = None
    details: Optional[List[TransferDetailData]] = None


# ==============================================================================
# Result Types
# ==============================================================================


@dataclass
class LifecycleMetrics:
    """Lifecycle metrics and statistics."""

    # Onboarding
    pending_onboardings: int = 0
    in_progress_onboardings: int = 0
    completed_onboardings: int = 0
    onboardings_this_month: int = 0

    # Separation
    pending_separations: int = 0
    in_progress_separations: int = 0
    completed_separations: int = 0
    separations_this_month: int = 0

    # Promotions & Transfers
    total_promotions: int = 0
    promotions_this_year: int = 0
    total_transfers: int = 0
    transfers_this_year: int = 0


@dataclass
class EmployeeLifecycleHistory:
    """Lifecycle history for an employee."""

    employee_id: int
    employee_name: str
    date_of_joining: Optional[date] = None
    onboarding_status: Optional[str] = None
    separation_date: Optional[date] = None
    separation_status: Optional[str] = None
    total_promotions: int = 0
    total_transfers: int = 0
    latest_promotion_date: Optional[date] = None
    latest_transfer_date: Optional[date] = None
