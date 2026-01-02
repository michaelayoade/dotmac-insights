"""Lifecycle service implementation.

Handles employee onboarding, separation, promotion, and transfer.
"""
from __future__ import annotations

from datetime import date, datetime

from app.utils.datetime_utils import utc_now
from typing import TYPE_CHECKING, List, Optional, Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import joinedload

from app.models.hr_lifecycle import (
    BoardingStatus,
    EmployeeOnboarding,
    EmployeeOnboardingActivity,
    EmployeePromotion,
    EmployeePromotionDetail,
    EmployeeSeparation,
    EmployeeSeparationActivity,
    EmployeeTransfer,
    EmployeeTransferDetail,
)
from app.services.base import PaginatedResult, Pagination, SortParam, paginate
from app.services.hr.errors import (
    NotFoundError,
    ValidationError,
)
from app.services.hr.lifecycle_types import (
    EmployeeLifecycleHistory,
    LifecycleMetrics,
    OnboardingActivityData,
    OnboardingCreateData,
    OnboardingFilters,
    OnboardingUpdateData,
    PromotionCreateData,
    PromotionDetailData,
    PromotionFilters,
    PromotionUpdateData,
    SeparationActivityData,
    SeparationCreateData,
    SeparationFilters,
    SeparationUpdateData,
    TransferCreateData,
    TransferDetailData,
    TransferFilters,
    TransferUpdateData,
)
if TYPE_CHECKING:
    from app.models.hr_settings import HRSettings
    from sqlalchemy.orm import Session

    from app.web.auth import Principal

__all__ = ["LifecycleService"]


# Custom errors for lifecycle module
class OnboardingNotFoundError(NotFoundError):
    """Onboarding not found."""

    def __init__(self, onboarding_id: int) -> None:
        super().__init__(f"Onboarding {onboarding_id} not found")
        self.onboarding_id = onboarding_id


class SeparationNotFoundError(NotFoundError):
    """Separation not found."""

    def __init__(self, separation_id: int) -> None:
        super().__init__(f"Separation {separation_id} not found")
        self.separation_id = separation_id


class PromotionNotFoundError(NotFoundError):
    """Promotion not found."""

    def __init__(self, promotion_id: int) -> None:
        super().__init__(f"Promotion {promotion_id} not found")
        self.promotion_id = promotion_id


class TransferNotFoundError(NotFoundError):
    """Transfer not found."""

    def __init__(self, transfer_id: int) -> None:
        super().__init__(f"Transfer {transfer_id} not found")
        self.transfer_id = transfer_id


class LifecycleStatusError(ValidationError):
    """Invalid lifecycle status transition."""

    def __init__(self, entity: str, entity_id: int, current: str, target: str) -> None:
        super().__init__(
            f"Cannot transition {entity} {entity_id} from {current} to {target}"
        )
        self.entity = entity
        self.entity_id = entity_id
        self.current_status = current
        self.target_status = target


# Valid status transitions
BOARDING_STATUS_TRANSITIONS = {
    BoardingStatus.PENDING: {BoardingStatus.IN_PROGRESS},
    BoardingStatus.IN_PROGRESS: {BoardingStatus.COMPLETED, BoardingStatus.PENDING},
    BoardingStatus.COMPLETED: set(),  # Terminal state
}


class LifecycleService:
    """Service for managing employee lifecycle events.

    Uses HR settings for configurable behavior:
    - require_exit_interview: Whether exit interview is mandatory for separation
    - default_probation_months: Default probation period for onboarding
    - default_notice_period_days: Default notice period for separation
    """

    def __init__(
        self,
        db: "Session",
        principal: Optional["Principal"] = None,
    ) -> None:
        self.db = db
        self.principal = principal
        self._settings_cache: dict[str, "HRSettings"] = {}

    def _get_settings(self, company: Optional[str] = None) -> "HRSettings":
        """Get HR settings, using cache for repeated access within same request."""
        cache_key = company or "__default__"
        if cache_key in self._settings_cache:
            return self._settings_cache[cache_key]

        from .settings import HRSettingsService

        settings_service = HRSettingsService(self.db, self.principal)
        self._settings_cache[cache_key] = settings_service.get_settings(company)
        return self._settings_cache[cache_key]

    # =========================================================================
    # Onboarding
    # =========================================================================

    def list_onboardings(
        self,
        filters: Optional[OnboardingFilters] = None,
        pagination: Optional[Pagination] = None,
        sort: Optional[SortParam] = None,
    ) -> PaginatedResult[EmployeeOnboarding]:
        """List onboardings with optional filters."""
        query = select(EmployeeOnboarding).options(
            joinedload(EmployeeOnboarding.activities)
        )

        if filters:
            conditions = []

            if filters.employee_id is not None:
                conditions.append(
                    EmployeeOnboarding.employee_id == filters.employee_id
                )

            if filters.boarding_status is not None:
                conditions.append(
                    EmployeeOnboarding.boarding_status == filters.boarding_status
                )

            if filters.company is not None:
                conditions.append(EmployeeOnboarding.company == filters.company)

            if filters.department is not None:
                conditions.append(EmployeeOnboarding.department == filters.department)

            if filters.from_date is not None:
                conditions.append(
                    EmployeeOnboarding.date_of_joining >= filters.from_date
                )

            if filters.to_date is not None:
                conditions.append(
                    EmployeeOnboarding.date_of_joining <= filters.to_date
                )

            if filters.search:
                conditions.append(
                    EmployeeOnboarding.employee_name.ilike(f"%{filters.search}%")
                )

            if conditions:
                query = query.where(and_(*conditions))

        # Default sort by date of joining descending
        if sort:
            col = getattr(EmployeeOnboarding, sort.field, None)
            if col is not None:
                query = query.order_by(col.desc() if sort.descending else col.asc())
        else:
            query = query.order_by(EmployeeOnboarding.date_of_joining.desc())

        return paginate(self.db, query, pagination)

    def get_onboarding(self, onboarding_id: int) -> EmployeeOnboarding:
        """Get an onboarding by ID."""
        onboarding = self.db.scalar(
            select(EmployeeOnboarding)
            .options(joinedload(EmployeeOnboarding.activities))
            .where(EmployeeOnboarding.id == onboarding_id)
        )
        if not onboarding:
            raise OnboardingNotFoundError(onboarding_id)
        return onboarding

    def create_onboarding(self, data: OnboardingCreateData) -> EmployeeOnboarding:
        """Create a new onboarding."""
        # Check for existing onboarding for this employee
        existing = self.db.scalar(
            select(EmployeeOnboarding).where(
                and_(
                    EmployeeOnboarding.employee_id == data.employee_id,
                    EmployeeOnboarding.boarding_status != BoardingStatus.COMPLETED,
                )
            )
        )
        if existing:
            raise ValidationError(
                f"Employee already has an active onboarding (ID: {existing.id})"
            )

        onboarding = EmployeeOnboarding(
            employee_id=data.employee_id,
            employee=data.employee,
            employee_name=data.employee_name,
            date_of_joining=data.date_of_joining,
            job_applicant=data.job_applicant,
            job_offer=data.job_offer,
            company=data.company,
            department=data.department,
            designation=data.designation,
            employee_onboarding_template=data.employee_onboarding_template,
            boarding_status=BoardingStatus.PENDING,
        )

        if self.principal:
            onboarding.created_by_id = self.principal.user_id

        self.db.add(onboarding)
        self.db.flush()

        # Add activities
        for idx, act_data in enumerate(data.activities):
            activity = EmployeeOnboardingActivity(
                employee_onboarding_id=onboarding.id,
                activity_name=act_data.activity_name,
                user=act_data.user,
                role=act_data.role,
                required_for_employee_creation=act_data.required_for_employee_creation,
                status=act_data.status,
                completed_on=act_data.completed_on,
                idx=idx,
            )
            self.db.add(activity)

        self.db.flush()
        return onboarding

    def update_onboarding(
        self,
        onboarding_id: int,
        data: OnboardingUpdateData,
    ) -> EmployeeOnboarding:
        """Update an onboarding."""
        onboarding = self.get_onboarding(onboarding_id)

        if onboarding.boarding_status == BoardingStatus.COMPLETED:
            raise ValidationError("Cannot update a completed onboarding")

        if data.date_of_joining is not None:
            onboarding.date_of_joining = data.date_of_joining
        if data.department is not None:
            onboarding.department = data.department
        if data.designation is not None:
            onboarding.designation = data.designation

        # Update activities if provided
        if data.activities is not None:
            self.db.execute(
                EmployeeOnboardingActivity.__table__.delete().where(
                    EmployeeOnboardingActivity.employee_onboarding_id == onboarding_id
                )
            )

            for idx, act_data in enumerate(data.activities):
                activity = EmployeeOnboardingActivity(
                    employee_onboarding_id=onboarding_id,
                    activity_name=act_data.activity_name,
                    user=act_data.user,
                    role=act_data.role,
                    required_for_employee_creation=act_data.required_for_employee_creation,
                    status=act_data.status,
                    completed_on=act_data.completed_on,
                    idx=idx,
                )
                self.db.add(activity)

        if self.principal:
            onboarding.updated_by_id = self.principal.user_id

        self.db.flush()
        return onboarding

    def _validate_boarding_transition(
        self,
        entity: str,
        entity_id: int,
        current: BoardingStatus,
        target: BoardingStatus,
    ) -> None:
        """Validate boarding status transition."""
        allowed = BOARDING_STATUS_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise LifecycleStatusError(entity, entity_id, current.value, target.value)

    def start_onboarding(self, onboarding_id: int) -> EmployeeOnboarding:
        """Start an onboarding process."""
        onboarding = self.get_onboarding(onboarding_id)
        self._validate_boarding_transition(
            "onboarding", onboarding_id, onboarding.boarding_status, BoardingStatus.IN_PROGRESS
        )

        onboarding.boarding_status = BoardingStatus.IN_PROGRESS
        onboarding.status_changed_at = utc_now()

        if self.principal:
            onboarding.status_changed_by_id = self.principal.user_id

        self.db.flush()
        return onboarding

    def complete_onboarding(self, onboarding_id: int) -> EmployeeOnboarding:
        """Complete an onboarding process."""
        onboarding = self.get_onboarding(onboarding_id)
        self._validate_boarding_transition(
            "onboarding", onboarding_id, onboarding.boarding_status, BoardingStatus.COMPLETED
        )

        # Check if all required activities are completed
        for activity in onboarding.activities:
            if activity.required_for_employee_creation and activity.status != "Completed":
                raise ValidationError(
                    f"Required activity '{activity.activity_name}' is not completed"
                )

        onboarding.boarding_status = BoardingStatus.COMPLETED
        onboarding.status_changed_at = utc_now()

        if self.principal:
            onboarding.status_changed_by_id = self.principal.user_id

        self.db.flush()
        return onboarding

    def complete_activity(
        self,
        onboarding_id: int,
        activity_id: int,
    ) -> EmployeeOnboardingActivity:
        """Mark an onboarding activity as completed."""
        onboarding = self.get_onboarding(onboarding_id)
        activity = self.db.get(EmployeeOnboardingActivity, activity_id)

        if not activity or activity.employee_onboarding_id != onboarding_id:
            raise ValidationError(
                f"Activity {activity_id} not found in onboarding {onboarding_id}"
            )

        activity.status = "Completed"
        activity.completed_on = date.today()

        self.db.flush()
        return activity

    # =========================================================================
    # Separation
    # =========================================================================

    def list_separations(
        self,
        filters: Optional[SeparationFilters] = None,
        pagination: Optional[Pagination] = None,
        sort: Optional[SortParam] = None,
    ) -> PaginatedResult[EmployeeSeparation]:
        """List separations with optional filters."""
        query = select(EmployeeSeparation).options(
            joinedload(EmployeeSeparation.activities)
        )

        if filters:
            conditions = []

            if filters.employee_id is not None:
                conditions.append(
                    EmployeeSeparation.employee_id == filters.employee_id
                )

            if filters.boarding_status is not None:
                conditions.append(
                    EmployeeSeparation.boarding_status == filters.boarding_status
                )

            if filters.company is not None:
                conditions.append(EmployeeSeparation.company == filters.company)

            if filters.department is not None:
                conditions.append(EmployeeSeparation.department == filters.department)

            if filters.from_date is not None:
                conditions.append(
                    EmployeeSeparation.separation_date >= filters.from_date
                )

            if filters.to_date is not None:
                conditions.append(
                    EmployeeSeparation.separation_date <= filters.to_date
                )

            if filters.search:
                conditions.append(
                    EmployeeSeparation.employee_name.ilike(f"%{filters.search}%")
                )

            if conditions:
                query = query.where(and_(*conditions))

        # Default sort by separation date descending
        if sort:
            col = getattr(EmployeeSeparation, sort.field, None)
            if col is not None:
                query = query.order_by(col.desc() if sort.descending else col.asc())
        else:
            query = query.order_by(EmployeeSeparation.separation_date.desc())

        return paginate(self.db, query, pagination)

    def get_separation(self, separation_id: int) -> EmployeeSeparation:
        """Get a separation by ID."""
        separation = self.db.scalar(
            select(EmployeeSeparation)
            .options(joinedload(EmployeeSeparation.activities))
            .where(EmployeeSeparation.id == separation_id)
        )
        if not separation:
            raise SeparationNotFoundError(separation_id)
        return separation

    def create_separation(self, data: SeparationCreateData) -> EmployeeSeparation:
        """Create a new separation."""
        # Check for existing separation for this employee
        existing = self.db.scalar(
            select(EmployeeSeparation).where(
                and_(
                    EmployeeSeparation.employee_id == data.employee_id,
                    EmployeeSeparation.boarding_status != BoardingStatus.COMPLETED,
                )
            )
        )
        if existing:
            raise ValidationError(
                f"Employee already has an active separation (ID: {existing.id})"
            )

        separation = EmployeeSeparation(
            employee_id=data.employee_id,
            employee=data.employee,
            employee_name=data.employee_name,
            separation_date=data.separation_date,
            resignation_letter_date=data.resignation_letter_date,
            company=data.company,
            department=data.department,
            designation=data.designation,
            reason_for_leaving=data.reason_for_leaving,
            exit_interview=data.exit_interview,
            employee_separation_template=data.employee_separation_template,
            boarding_status=BoardingStatus.PENDING,
        )

        if self.principal:
            separation.created_by_id = self.principal.user_id

        self.db.add(separation)
        self.db.flush()

        # Add activities
        for idx, act_data in enumerate(data.activities):
            activity = EmployeeSeparationActivity(
                employee_separation_id=separation.id,
                activity_name=act_data.activity_name,
                user=act_data.user,
                role=act_data.role,
                status=act_data.status,
                completed_on=act_data.completed_on,
                idx=idx,
            )
            self.db.add(activity)

        self.db.flush()
        return separation

    def update_separation(
        self,
        separation_id: int,
        data: SeparationUpdateData,
    ) -> EmployeeSeparation:
        """Update a separation."""
        separation = self.get_separation(separation_id)

        if separation.boarding_status == BoardingStatus.COMPLETED:
            raise ValidationError("Cannot update a completed separation")

        if data.separation_date is not None:
            separation.separation_date = data.separation_date
        if data.resignation_letter_date is not None:
            separation.resignation_letter_date = data.resignation_letter_date
        if data.reason_for_leaving is not None:
            separation.reason_for_leaving = data.reason_for_leaving
        if data.exit_interview is not None:
            separation.exit_interview = data.exit_interview

        # Update activities if provided
        if data.activities is not None:
            self.db.execute(
                EmployeeSeparationActivity.__table__.delete().where(
                    EmployeeSeparationActivity.employee_separation_id == separation_id
                )
            )

            for idx, act_data in enumerate(data.activities):
                activity = EmployeeSeparationActivity(
                    employee_separation_id=separation_id,
                    activity_name=act_data.activity_name,
                    user=act_data.user,
                    role=act_data.role,
                    status=act_data.status,
                    completed_on=act_data.completed_on,
                    idx=idx,
                )
                self.db.add(activity)

        if self.principal:
            separation.updated_by_id = self.principal.user_id

        self.db.flush()
        return separation

    def start_separation(self, separation_id: int) -> EmployeeSeparation:
        """Start a separation process."""
        separation = self.get_separation(separation_id)
        self._validate_boarding_transition(
            "separation", separation_id, separation.boarding_status, BoardingStatus.IN_PROGRESS
        )

        separation.boarding_status = BoardingStatus.IN_PROGRESS
        separation.status_changed_at = utc_now()

        if self.principal:
            separation.status_changed_by_id = self.principal.user_id

        self.db.flush()
        return separation

    def complete_separation(self, separation_id: int) -> EmployeeSeparation:
        """Complete a separation process.

        Uses HR settings for:
        - require_exit_interview: Whether exit interview is mandatory
        """
        separation = self.get_separation(separation_id)
        self._validate_boarding_transition(
            "separation", separation_id, separation.boarding_status, BoardingStatus.COMPLETED
        )

        # Check settings for exit interview requirement
        settings = self._get_settings(separation.company)
        if settings.require_exit_interview and not separation.exit_interview:
            raise ValidationError(
                "Exit interview is required before completing separation"
            )

        separation.boarding_status = BoardingStatus.COMPLETED
        separation.status_changed_at = utc_now()

        if self.principal:
            separation.status_changed_by_id = self.principal.user_id

        self.db.flush()
        return separation

    # =========================================================================
    # Promotion
    # =========================================================================

    def list_promotions(
        self,
        filters: Optional[PromotionFilters] = None,
        pagination: Optional[Pagination] = None,
        sort: Optional[SortParam] = None,
    ) -> PaginatedResult[EmployeePromotion]:
        """List promotions with optional filters."""
        query = select(EmployeePromotion).options(
            joinedload(EmployeePromotion.details)
        )

        if filters:
            conditions = []

            if filters.employee_id is not None:
                conditions.append(EmployeePromotion.employee_id == filters.employee_id)

            if filters.company is not None:
                conditions.append(EmployeePromotion.company == filters.company)

            if filters.from_date is not None:
                conditions.append(EmployeePromotion.promotion_date >= filters.from_date)

            if filters.to_date is not None:
                conditions.append(EmployeePromotion.promotion_date <= filters.to_date)

            if filters.search:
                conditions.append(
                    EmployeePromotion.employee_name.ilike(f"%{filters.search}%")
                )

            if conditions:
                query = query.where(and_(*conditions))

        # Default sort by promotion date descending
        if sort:
            col = getattr(EmployeePromotion, sort.field, None)
            if col is not None:
                query = query.order_by(col.desc() if sort.descending else col.asc())
        else:
            query = query.order_by(EmployeePromotion.promotion_date.desc())

        return paginate(self.db, query, pagination)

    def get_promotion(self, promotion_id: int) -> EmployeePromotion:
        """Get a promotion by ID."""
        promotion = self.db.scalar(
            select(EmployeePromotion)
            .options(joinedload(EmployeePromotion.details))
            .where(EmployeePromotion.id == promotion_id)
        )
        if not promotion:
            raise PromotionNotFoundError(promotion_id)
        return promotion

    def create_promotion(self, data: PromotionCreateData) -> EmployeePromotion:
        """Create a new promotion."""
        promotion = EmployeePromotion(
            employee_id=data.employee_id,
            employee=data.employee,
            employee_name=data.employee_name,
            promotion_date=data.promotion_date,
            company=data.company,
            docstatus=0,
        )

        if self.principal:
            promotion.created_by_id = self.principal.user_id

        self.db.add(promotion)
        self.db.flush()

        # Add details
        for idx, detail_data in enumerate(data.details):
            detail = EmployeePromotionDetail(
                employee_promotion_id=promotion.id,
                property=detail_data.property,
                current=detail_data.current,
                new=detail_data.new,
                idx=idx,
            )
            self.db.add(detail)

        self.db.flush()
        return promotion

    def update_promotion(
        self,
        promotion_id: int,
        data: PromotionUpdateData,
    ) -> EmployeePromotion:
        """Update a promotion."""
        promotion = self.get_promotion(promotion_id)

        if promotion.docstatus == 1:
            raise ValidationError("Cannot update a submitted promotion")

        if data.promotion_date is not None:
            promotion.promotion_date = data.promotion_date

        # Update details if provided
        if data.details is not None:
            self.db.execute(
                EmployeePromotionDetail.__table__.delete().where(
                    EmployeePromotionDetail.employee_promotion_id == promotion_id
                )
            )

            for idx, detail_data in enumerate(data.details):
                detail = EmployeePromotionDetail(
                    employee_promotion_id=promotion_id,
                    property=detail_data.property,
                    current=detail_data.current,
                    new=detail_data.new,
                    idx=idx,
                )
                self.db.add(detail)

        if self.principal:
            promotion.updated_by_id = self.principal.user_id

        self.db.flush()
        return promotion

    def submit_promotion(self, promotion_id: int) -> EmployeePromotion:
        """Submit a promotion (make it official)."""
        promotion = self.get_promotion(promotion_id)

        if promotion.docstatus == 1:
            raise ValidationError("Promotion is already submitted")

        if not promotion.details:
            raise ValidationError("Promotion must have at least one detail")

        promotion.docstatus = 1
        promotion.status_changed_at = utc_now()

        if self.principal:
            promotion.status_changed_by_id = self.principal.user_id

        self.db.flush()
        return promotion

    # =========================================================================
    # Transfer
    # =========================================================================

    def list_transfers(
        self,
        filters: Optional[TransferFilters] = None,
        pagination: Optional[Pagination] = None,
        sort: Optional[SortParam] = None,
    ) -> PaginatedResult[EmployeeTransfer]:
        """List transfers with optional filters."""
        query = select(EmployeeTransfer).options(joinedload(EmployeeTransfer.details))

        if filters:
            conditions = []

            if filters.employee_id is not None:
                conditions.append(EmployeeTransfer.employee_id == filters.employee_id)

            if filters.company is not None:
                conditions.append(EmployeeTransfer.company == filters.company)

            if filters.new_company is not None:
                conditions.append(EmployeeTransfer.new_company == filters.new_company)

            if filters.from_date is not None:
                conditions.append(EmployeeTransfer.transfer_date >= filters.from_date)

            if filters.to_date is not None:
                conditions.append(EmployeeTransfer.transfer_date <= filters.to_date)

            if filters.search:
                conditions.append(
                    EmployeeTransfer.employee_name.ilike(f"%{filters.search}%")
                )

            if conditions:
                query = query.where(and_(*conditions))

        # Default sort by transfer date descending
        if sort:
            col = getattr(EmployeeTransfer, sort.field, None)
            if col is not None:
                query = query.order_by(col.desc() if sort.descending else col.asc())
        else:
            query = query.order_by(EmployeeTransfer.transfer_date.desc())

        return paginate(self.db, query, pagination)

    def get_transfer(self, transfer_id: int) -> EmployeeTransfer:
        """Get a transfer by ID."""
        transfer = self.db.scalar(
            select(EmployeeTransfer)
            .options(joinedload(EmployeeTransfer.details))
            .where(EmployeeTransfer.id == transfer_id)
        )
        if not transfer:
            raise TransferNotFoundError(transfer_id)
        return transfer

    def create_transfer(self, data: TransferCreateData) -> EmployeeTransfer:
        """Create a new transfer."""
        transfer = EmployeeTransfer(
            employee_id=data.employee_id,
            employee=data.employee,
            employee_name=data.employee_name,
            transfer_date=data.transfer_date,
            company=data.company,
            new_company=data.new_company,
            docstatus=0,
        )

        if self.principal:
            transfer.created_by_id = self.principal.user_id

        self.db.add(transfer)
        self.db.flush()

        # Add details
        for idx, detail_data in enumerate(data.details):
            detail = EmployeeTransferDetail(
                employee_transfer_id=transfer.id,
                property=detail_data.property,
                current=detail_data.current,
                new=detail_data.new,
                idx=idx,
            )
            self.db.add(detail)

        self.db.flush()
        return transfer

    def update_transfer(
        self,
        transfer_id: int,
        data: TransferUpdateData,
    ) -> EmployeeTransfer:
        """Update a transfer."""
        transfer = self.get_transfer(transfer_id)

        if transfer.docstatus == 1:
            raise ValidationError("Cannot update a submitted transfer")

        if data.transfer_date is not None:
            transfer.transfer_date = data.transfer_date
        if data.new_company is not None:
            transfer.new_company = data.new_company

        # Update details if provided
        if data.details is not None:
            self.db.execute(
                EmployeeTransferDetail.__table__.delete().where(
                    EmployeeTransferDetail.employee_transfer_id == transfer_id
                )
            )

            for idx, detail_data in enumerate(data.details):
                detail = EmployeeTransferDetail(
                    employee_transfer_id=transfer_id,
                    property=detail_data.property,
                    current=detail_data.current,
                    new=detail_data.new,
                    idx=idx,
                )
                self.db.add(detail)

        if self.principal:
            transfer.updated_by_id = self.principal.user_id

        self.db.flush()
        return transfer

    def submit_transfer(self, transfer_id: int) -> EmployeeTransfer:
        """Submit a transfer (make it official)."""
        transfer = self.get_transfer(transfer_id)

        if transfer.docstatus == 1:
            raise ValidationError("Transfer is already submitted")

        if not transfer.details:
            raise ValidationError("Transfer must have at least one detail")

        transfer.docstatus = 1
        transfer.status_changed_at = utc_now()

        if self.principal:
            transfer.status_changed_by_id = self.principal.user_id

        self.db.flush()
        return transfer

    # =========================================================================
    # Metrics & Reporting
    # =========================================================================

    def get_metrics(self, company: Optional[str] = None) -> LifecycleMetrics:
        """Get lifecycle metrics and statistics."""
        metrics = LifecycleMetrics()

        company_cond_onboarding = (
            EmployeeOnboarding.company == company if company else True
        )
        company_cond_separation = (
            EmployeeSeparation.company == company if company else True
        )
        company_cond_promotion = (
            EmployeePromotion.company == company if company else True
        )
        company_cond_transfer = EmployeeTransfer.company == company if company else True

        today = date.today()
        month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)

        # Onboarding counts
        metrics.pending_onboardings = (
            self.db.scalar(
                select(func.count(EmployeeOnboarding.id)).where(
                    and_(
                        company_cond_onboarding,
                        EmployeeOnboarding.boarding_status == BoardingStatus.PENDING,
                    )
                )
            )
            or 0
        )

        metrics.in_progress_onboardings = (
            self.db.scalar(
                select(func.count(EmployeeOnboarding.id)).where(
                    and_(
                        company_cond_onboarding,
                        EmployeeOnboarding.boarding_status == BoardingStatus.IN_PROGRESS,
                    )
                )
            )
            or 0
        )

        metrics.completed_onboardings = (
            self.db.scalar(
                select(func.count(EmployeeOnboarding.id)).where(
                    and_(
                        company_cond_onboarding,
                        EmployeeOnboarding.boarding_status == BoardingStatus.COMPLETED,
                    )
                )
            )
            or 0
        )

        metrics.onboardings_this_month = (
            self.db.scalar(
                select(func.count(EmployeeOnboarding.id)).where(
                    and_(
                        company_cond_onboarding,
                        EmployeeOnboarding.date_of_joining >= month_start,
                    )
                )
            )
            or 0
        )

        # Separation counts
        metrics.pending_separations = (
            self.db.scalar(
                select(func.count(EmployeeSeparation.id)).where(
                    and_(
                        company_cond_separation,
                        EmployeeSeparation.boarding_status == BoardingStatus.PENDING,
                    )
                )
            )
            or 0
        )

        metrics.in_progress_separations = (
            self.db.scalar(
                select(func.count(EmployeeSeparation.id)).where(
                    and_(
                        company_cond_separation,
                        EmployeeSeparation.boarding_status == BoardingStatus.IN_PROGRESS,
                    )
                )
            )
            or 0
        )

        metrics.completed_separations = (
            self.db.scalar(
                select(func.count(EmployeeSeparation.id)).where(
                    and_(
                        company_cond_separation,
                        EmployeeSeparation.boarding_status == BoardingStatus.COMPLETED,
                    )
                )
            )
            or 0
        )

        metrics.separations_this_month = (
            self.db.scalar(
                select(func.count(EmployeeSeparation.id)).where(
                    and_(
                        company_cond_separation,
                        EmployeeSeparation.separation_date >= month_start,
                    )
                )
            )
            or 0
        )

        # Promotion counts
        metrics.total_promotions = (
            self.db.scalar(
                select(func.count(EmployeePromotion.id)).where(company_cond_promotion)
            )
            or 0
        )

        metrics.promotions_this_year = (
            self.db.scalar(
                select(func.count(EmployeePromotion.id)).where(
                    and_(
                        company_cond_promotion,
                        EmployeePromotion.promotion_date >= year_start,
                    )
                )
            )
            or 0
        )

        # Transfer counts
        metrics.total_transfers = (
            self.db.scalar(
                select(func.count(EmployeeTransfer.id)).where(company_cond_transfer)
            )
            or 0
        )

        metrics.transfers_this_year = (
            self.db.scalar(
                select(func.count(EmployeeTransfer.id)).where(
                    and_(
                        company_cond_transfer,
                        EmployeeTransfer.transfer_date >= year_start,
                    )
                )
            )
            or 0
        )

        return metrics

    def get_employee_history(self, employee_id: int) -> EmployeeLifecycleHistory:
        """Get lifecycle history for an employee."""
        # Get onboarding info
        onboarding = self.db.scalar(
            select(EmployeeOnboarding).where(
                EmployeeOnboarding.employee_id == employee_id
            )
        )

        # Get separation info
        separation = self.db.scalar(
            select(EmployeeSeparation).where(
                EmployeeSeparation.employee_id == employee_id
            )
        )

        # Get promotion count
        promotion_count = (
            self.db.scalar(
                select(func.count(EmployeePromotion.id)).where(
                    EmployeePromotion.employee_id == employee_id
                )
            )
            or 0
        )

        # Get latest promotion
        latest_promotion = self.db.scalar(
            select(EmployeePromotion)
            .where(EmployeePromotion.employee_id == employee_id)
            .order_by(EmployeePromotion.promotion_date.desc())
        )

        # Get transfer count
        transfer_count = (
            self.db.scalar(
                select(func.count(EmployeeTransfer.id)).where(
                    EmployeeTransfer.employee_id == employee_id
                )
            )
            or 0
        )

        # Get latest transfer
        latest_transfer = self.db.scalar(
            select(EmployeeTransfer)
            .where(EmployeeTransfer.employee_id == employee_id)
            .order_by(EmployeeTransfer.transfer_date.desc())
        )

        employee_name = ""
        if onboarding:
            employee_name = onboarding.employee_name or ""
        elif separation:
            employee_name = separation.employee_name or ""
        elif latest_promotion:
            employee_name = latest_promotion.employee_name or ""

        return EmployeeLifecycleHistory(
            employee_id=employee_id,
            employee_name=employee_name,
            date_of_joining=onboarding.date_of_joining if onboarding else None,
            onboarding_status=(
                onboarding.boarding_status.value if onboarding else None
            ),
            separation_date=separation.separation_date if separation else None,
            separation_status=(
                separation.boarding_status.value if separation else None
            ),
            total_promotions=promotion_count,
            total_transfers=transfer_count,
            latest_promotion_date=(
                latest_promotion.promotion_date if latest_promotion else None
            ),
            latest_transfer_date=(
                latest_transfer.transfer_date if latest_transfer else None
            ),
        )

    def get_pending_onboardings(
        self,
        company: Optional[str] = None,
        limit: int = 10,
    ) -> Sequence[EmployeeOnboarding]:
        """Get pending/in-progress onboardings."""
        query = (
            select(EmployeeOnboarding)
            .where(
                EmployeeOnboarding.boarding_status.in_([
                    BoardingStatus.PENDING,
                    BoardingStatus.IN_PROGRESS,
                ])
            )
            .order_by(EmployeeOnboarding.date_of_joining.asc())
            .limit(limit)
        )

        if company:
            query = query.where(EmployeeOnboarding.company == company)

        return self.db.scalars(query).all()

    def get_pending_separations(
        self,
        company: Optional[str] = None,
        limit: int = 10,
    ) -> Sequence[EmployeeSeparation]:
        """Get pending/in-progress separations."""
        query = (
            select(EmployeeSeparation)
            .where(
                EmployeeSeparation.boarding_status.in_([
                    BoardingStatus.PENDING,
                    BoardingStatus.IN_PROGRESS,
                ])
            )
            .order_by(EmployeeSeparation.separation_date.asc())
            .limit(limit)
        )

        if company:
            query = query.where(EmployeeSeparation.company == company)

        return self.db.scalars(query).all()
