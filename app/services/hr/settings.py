"""HR Settings service implementation.

Handles HR configuration, policies, salary bands, and deduction settings.
"""
from __future__ import annotations

from dataclasses import fields
from datetime import date
from typing import TYPE_CHECKING, List, Optional, Sequence

from sqlalchemy import and_, func, or_, select

from app.models.hr_settings import (
    DEFAULT_EMPLOYMENT_TYPE_CONFIGS,
    DocumentChecklistTemplate,
    EmploymentTypeDeductionConfig,
    HolidayCalendar,
    HRHoliday,
    HRSettings,
    LeaveEncashmentPolicy,
    SalaryBand,
)
from app.services.base import PaginatedResult, Pagination, SortParam, paginate
from app.services.hr.errors import (
    NotFoundError,
    ValidationError,
)
from app.services.hr.settings_types import (
    ChecklistTemplateCreateData,
    ChecklistTemplateFilters,
    ChecklistTemplateUpdateData,
    DeductionConfigCreateData,
    DeductionConfigFilters,
    DeductionConfigUpdateData,
    HolidayCalendarCreateData,
    HolidayCalendarFilters,
    HolidayCalendarUpdateData,
    HRSettingsUpdateData,
    LeaveEncashmentPolicyData,
    LeaveEncashmentPolicyUpdateData,
    SalaryBandCreateData,
    SalaryBandFilters,
    SalaryBandUpdateData,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.web.auth import Principal

__all__ = ["HRSettingsService"]


# Custom errors for settings module
class HRSettingsNotFoundError(NotFoundError):
    """HR Settings not found."""

    def __init__(self, company: Optional[str]) -> None:
        super().__init__(f"HR Settings not found for company: {company or 'default'}")
        self.company = company


class HolidayCalendarNotFoundError(NotFoundError):
    """Holiday calendar not found."""

    def __init__(self, calendar_id: int) -> None:
        super().__init__(f"Holiday calendar {calendar_id} not found")
        self.calendar_id = calendar_id


class SalaryBandNotFoundError(NotFoundError):
    """Salary band not found."""

    def __init__(self, band_id: int) -> None:
        super().__init__(f"Salary band {band_id} not found")
        self.band_id = band_id


class ChecklistTemplateNotFoundError(NotFoundError):
    """Checklist template not found."""

    def __init__(self, template_id: int) -> None:
        super().__init__(f"Checklist template {template_id} not found")
        self.template_id = template_id


class DeductionConfigNotFoundError(NotFoundError):
    """Deduction config not found."""

    def __init__(self, config_id: int) -> None:
        super().__init__(f"Deduction config {config_id} not found")
        self.config_id = config_id


class HRSettingsService:
    """Service for managing HR settings and configuration."""

    def __init__(
        self,
        db: "Session",
        principal: Optional["Principal"] = None,
    ) -> None:
        self.db = db
        self.principal = principal

    # =========================================================================
    # HR Settings (Global Configuration)
    # =========================================================================

    def get_settings(self, company: Optional[str] = None) -> HRSettings:
        """Get HR settings for a company (or default)."""
        settings = self.db.scalar(
            select(HRSettings).where(HRSettings.company == company)
        )
        if not settings:
            # Create default settings if not exists
            settings = self._create_default_settings(company)
        return settings

    def _create_default_settings(self, company: Optional[str] = None) -> HRSettings:
        """Create default HR settings for a company."""
        settings = HRSettings(company=company)
        self.db.add(settings)
        self.db.flush()
        return settings

    def update_settings(
        self,
        data: HRSettingsUpdateData,
        company: Optional[str] = None,
    ) -> HRSettings:
        """Update HR settings for a company."""
        settings = self.get_settings(company)

        # Update all non-None fields from data
        for field_obj in fields(data):
            value = getattr(data, field_obj.name)
            if value is not None:
                setattr(settings, field_obj.name, value)

        if self.principal:
            settings.updated_by_id = self.principal.user_id

        self.db.flush()
        return settings

    # =========================================================================
    # Leave Encashment Policy
    # =========================================================================

    def list_encashment_policies(
        self,
        company: Optional[str] = None,
        leave_type_id: Optional[int] = None,
    ) -> Sequence[LeaveEncashmentPolicy]:
        """List leave encashment policies."""
        query = select(LeaveEncashmentPolicy)

        conditions = []
        if company is not None:
            conditions.append(LeaveEncashmentPolicy.company == company)
        if leave_type_id is not None:
            conditions.append(LeaveEncashmentPolicy.leave_type_id == leave_type_id)

        if conditions:
            query = query.where(and_(*conditions))

        return self.db.scalars(query).all()

    def get_encashment_policy(self, policy_id: int) -> LeaveEncashmentPolicy:
        """Get a leave encashment policy by ID."""
        policy = self.db.get(LeaveEncashmentPolicy, policy_id)
        if not policy:
            raise NotFoundError(f"Leave encashment policy {policy_id} not found")
        return policy

    def create_encashment_policy(
        self,
        data: LeaveEncashmentPolicyData,
    ) -> LeaveEncashmentPolicy:
        """Create a leave encashment policy."""
        policy = LeaveEncashmentPolicy(
            company=data.company,
            leave_type_id=data.leave_type_id,
            is_encashable=data.is_encashable,
            max_encashment_days_yearly=data.max_encashment_days_yearly,
            min_balance_to_encash=data.min_balance_to_encash,
            encashment_rate_percent=data.encashment_rate_percent,
            allow_partial_encashment=data.allow_partial_encashment,
            encash_on_separation=data.encash_on_separation,
            taxable=data.taxable,
            is_active=data.is_active,
        )

        self.db.add(policy)
        self.db.flush()
        return policy

    def update_encashment_policy(
        self,
        policy_id: int,
        data: LeaveEncashmentPolicyUpdateData,
    ) -> LeaveEncashmentPolicy:
        """Update a leave encashment policy."""
        policy = self.get_encashment_policy(policy_id)

        if data.is_encashable is not None:
            policy.is_encashable = data.is_encashable
        if data.max_encashment_days_yearly is not None:
            policy.max_encashment_days_yearly = data.max_encashment_days_yearly
        if data.min_balance_to_encash is not None:
            policy.min_balance_to_encash = data.min_balance_to_encash
        if data.encashment_rate_percent is not None:
            policy.encashment_rate_percent = data.encashment_rate_percent
        if data.allow_partial_encashment is not None:
            policy.allow_partial_encashment = data.allow_partial_encashment
        if data.encash_on_separation is not None:
            policy.encash_on_separation = data.encash_on_separation
        if data.taxable is not None:
            policy.taxable = data.taxable
        if data.is_active is not None:
            policy.is_active = data.is_active

        self.db.flush()
        return policy

    # =========================================================================
    # Holiday Calendar
    # =========================================================================

    def list_holiday_calendars(
        self,
        filters: Optional[HolidayCalendarFilters] = None,
        pagination: Optional[Pagination] = None,
        sort: Optional[SortParam] = None,
    ) -> PaginatedResult[HolidayCalendar]:
        """List holiday calendars with optional filters."""
        query = select(HolidayCalendar)

        if filters:
            conditions = []

            if filters.company is not None:
                conditions.append(HolidayCalendar.company == filters.company)

            if filters.location is not None:
                conditions.append(HolidayCalendar.location == filters.location)

            if filters.year is not None:
                conditions.append(HolidayCalendar.year == filters.year)

            if filters.is_active is not None:
                conditions.append(HolidayCalendar.is_active == filters.is_active)

            if filters.search:
                conditions.append(
                    HolidayCalendar.name.ilike(f"%{filters.search}%")
                )

            if conditions:
                query = query.where(and_(*conditions))

        # Default sort by year descending, then name
        if sort:
            col = getattr(HolidayCalendar, sort.field, None)
            if col is not None:
                query = query.order_by(col.desc() if sort.descending else col.asc())
        else:
            query = query.order_by(HolidayCalendar.year.desc(), HolidayCalendar.name)

        return paginate(self.db, query, pagination)

    def get_holiday_calendar(self, calendar_id: int) -> HolidayCalendar:
        """Get a holiday calendar by ID."""
        calendar = self.db.get(HolidayCalendar, calendar_id)
        if not calendar:
            raise HolidayCalendarNotFoundError(calendar_id)
        return calendar

    def create_holiday_calendar(
        self,
        data: HolidayCalendarCreateData,
    ) -> HolidayCalendar:
        """Create a holiday calendar."""
        calendar = HolidayCalendar(
            name=data.name,
            company=data.company,
            location=data.location,
            year=data.year,
            is_default=data.is_default,
        )

        if self.principal:
            calendar.created_by_id = self.principal.user_id

        self.db.add(calendar)
        self.db.flush()

        # Add holidays
        for holiday_data in data.holidays:
            holiday = HRHoliday(
                calendar_id=calendar.id,
                name=holiday_data.name,
                date=holiday_data.date,
                is_optional=holiday_data.is_optional,
                is_recurring=holiday_data.is_recurring,
                description=holiday_data.description,
            )
            self.db.add(holiday)

        self.db.flush()
        return calendar

    def update_holiday_calendar(
        self,
        calendar_id: int,
        data: HolidayCalendarUpdateData,
    ) -> HolidayCalendar:
        """Update a holiday calendar."""
        calendar = self.get_holiday_calendar(calendar_id)

        if data.name is not None:
            calendar.name = data.name
        if data.is_default is not None:
            calendar.is_default = data.is_default
        if data.is_active is not None:
            calendar.is_active = data.is_active

        # Update holidays if provided
        if data.holidays is not None:
            # Remove existing holidays
            self.db.execute(
                HRHoliday.__table__.delete().where(
                    HRHoliday.calendar_id == calendar_id
                )
            )

            # Add new holidays
            for holiday_data in data.holidays:
                holiday = HRHoliday(
                    calendar_id=calendar_id,
                    name=holiday_data.name,
                    date=holiday_data.date,
                    is_optional=holiday_data.is_optional,
                    is_recurring=holiday_data.is_recurring,
                    description=holiday_data.description,
                )
                self.db.add(holiday)

        self.db.flush()
        return calendar

    def get_holidays_for_period(
        self,
        start_date: date,
        end_date: date,
        company: Optional[str] = None,
        location: Optional[str] = None,
    ) -> Sequence[HRHoliday]:
        """Get holidays for a date range."""
        query = (
            select(HRHoliday)
            .join(HolidayCalendar)
            .where(
                and_(
                    HRHoliday.date >= start_date,
                    HRHoliday.date <= end_date,
                    HolidayCalendar.is_active == True,
                )
            )
            .order_by(HRHoliday.date)
        )

        if company is not None:
            query = query.where(HolidayCalendar.company == company)

        if location is not None:
            query = query.where(HolidayCalendar.location == location)

        return self.db.scalars(query).all()

    # =========================================================================
    # Salary Band
    # =========================================================================

    def list_salary_bands(
        self,
        filters: Optional[SalaryBandFilters] = None,
        pagination: Optional[Pagination] = None,
        sort: Optional[SortParam] = None,
    ) -> PaginatedResult[SalaryBand]:
        """List salary bands with optional filters."""
        query = select(SalaryBand)

        if filters:
            conditions = []

            if filters.company is not None:
                conditions.append(SalaryBand.company == filters.company)

            if filters.grade is not None:
                conditions.append(SalaryBand.grade == filters.grade)

            if filters.is_active is not None:
                conditions.append(SalaryBand.is_active == filters.is_active)

            if filters.search:
                conditions.append(
                    or_(
                        SalaryBand.name.ilike(f"%{filters.search}%"),
                        SalaryBand.grade.ilike(f"%{filters.search}%"),
                    )
                )

            if conditions:
                query = query.where(and_(*conditions))

        # Default sort by name
        if sort:
            col = getattr(SalaryBand, sort.field, None)
            if col is not None:
                query = query.order_by(col.desc() if sort.descending else col.asc())
        else:
            query = query.order_by(SalaryBand.name)

        return paginate(self.db, query, pagination)

    def get_salary_band(self, band_id: int) -> SalaryBand:
        """Get a salary band by ID."""
        band = self.db.get(SalaryBand, band_id)
        if not band:
            raise SalaryBandNotFoundError(band_id)
        return band

    def create_salary_band(self, data: SalaryBandCreateData) -> SalaryBand:
        """Create a salary band."""
        if data.min_salary > data.max_salary:
            raise ValidationError("Min salary cannot be greater than max salary")

        band = SalaryBand(
            company=data.company,
            name=data.name,
            grade=data.grade,
            currency=data.currency,
            min_salary=data.min_salary,
            max_salary=data.max_salary,
            mid_salary=data.mid_salary or (data.min_salary + data.max_salary) / 2,
        )

        self.db.add(band)
        self.db.flush()
        return band

    def update_salary_band(
        self,
        band_id: int,
        data: SalaryBandUpdateData,
    ) -> SalaryBand:
        """Update a salary band."""
        band = self.get_salary_band(band_id)

        if data.name is not None:
            band.name = data.name
        if data.grade is not None:
            band.grade = data.grade
        if data.min_salary is not None:
            band.min_salary = data.min_salary
        if data.max_salary is not None:
            band.max_salary = data.max_salary
        if data.mid_salary is not None:
            band.mid_salary = data.mid_salary
        if data.currency is not None:
            band.currency = data.currency
        if data.is_active is not None:
            band.is_active = data.is_active

        # Validate salary range
        if band.min_salary > band.max_salary:
            raise ValidationError("Min salary cannot be greater than max salary")

        self.db.flush()
        return band

    # =========================================================================
    # Document Checklist Template
    # =========================================================================

    def list_checklist_templates(
        self,
        filters: Optional[ChecklistTemplateFilters] = None,
        pagination: Optional[Pagination] = None,
        sort: Optional[SortParam] = None,
    ) -> PaginatedResult[DocumentChecklistTemplate]:
        """List checklist templates with optional filters."""
        query = select(DocumentChecklistTemplate)

        if filters:
            conditions = []

            if filters.company is not None:
                conditions.append(DocumentChecklistTemplate.company == filters.company)

            if filters.template_type is not None:
                conditions.append(
                    DocumentChecklistTemplate.template_type == filters.template_type
                )

            if filters.is_active is not None:
                conditions.append(
                    DocumentChecklistTemplate.is_active == filters.is_active
                )

            if filters.search:
                conditions.append(
                    DocumentChecklistTemplate.name.ilike(f"%{filters.search}%")
                )

            if conditions:
                query = query.where(and_(*conditions))

        # Default sort by name
        if sort:
            col = getattr(DocumentChecklistTemplate, sort.field, None)
            if col is not None:
                query = query.order_by(col.desc() if sort.descending else col.asc())
        else:
            query = query.order_by(DocumentChecklistTemplate.name)

        return paginate(self.db, query, pagination)

    def get_checklist_template(self, template_id: int) -> DocumentChecklistTemplate:
        """Get a checklist template by ID."""
        template = self.db.get(DocumentChecklistTemplate, template_id)
        if not template:
            raise ChecklistTemplateNotFoundError(template_id)
        return template

    def create_checklist_template(
        self,
        data: ChecklistTemplateCreateData,
    ) -> DocumentChecklistTemplate:
        """Create a checklist template."""
        template = DocumentChecklistTemplate(
            company=data.company,
            name=data.name,
            template_type=data.template_type,
            items=data.items,
        )

        if self.principal:
            template.created_by_id = self.principal.user_id

        self.db.add(template)
        self.db.flush()
        return template

    def update_checklist_template(
        self,
        template_id: int,
        data: ChecklistTemplateUpdateData,
    ) -> DocumentChecklistTemplate:
        """Update a checklist template."""
        template = self.get_checklist_template(template_id)

        if data.name is not None:
            template.name = data.name
        if data.items is not None:
            template.items = data.items
        if data.is_active is not None:
            template.is_active = data.is_active

        self.db.flush()
        return template

    # =========================================================================
    # Employment Type Deduction Config
    # =========================================================================

    def list_deduction_configs(
        self,
        filters: Optional[DeductionConfigFilters] = None,
        pagination: Optional[Pagination] = None,
        sort: Optional[SortParam] = None,
    ) -> PaginatedResult[EmploymentTypeDeductionConfig]:
        """List deduction configs with optional filters."""
        query = select(EmploymentTypeDeductionConfig)

        if filters:
            conditions = []

            if filters.company is not None:
                conditions.append(
                    EmploymentTypeDeductionConfig.company == filters.company
                )

            if filters.employment_type is not None:
                conditions.append(
                    EmploymentTypeDeductionConfig.employment_type
                    == filters.employment_type
                )

            if filters.is_active is not None:
                conditions.append(
                    EmploymentTypeDeductionConfig.is_active == filters.is_active
                )

            if conditions:
                query = query.where(and_(*conditions))

        # Default sort by display name
        if sort:
            col = getattr(EmploymentTypeDeductionConfig, sort.field, None)
            if col is not None:
                query = query.order_by(col.desc() if sort.descending else col.asc())
        else:
            query = query.order_by(EmploymentTypeDeductionConfig.display_name)

        return paginate(self.db, query, pagination)

    def get_deduction_config(self, config_id: int) -> EmploymentTypeDeductionConfig:
        """Get a deduction config by ID."""
        config = self.db.get(EmploymentTypeDeductionConfig, config_id)
        if not config:
            raise DeductionConfigNotFoundError(config_id)
        return config

    def create_deduction_config(
        self,
        data: DeductionConfigCreateData,
    ) -> EmploymentTypeDeductionConfig:
        """Create a deduction config."""
        config = EmploymentTypeDeductionConfig(
            company=data.company,
            employment_type=data.employment_type,
            display_name=data.display_name,
            description=data.description,
            paye_applicable=data.paye_applicable,
            pension_applicable=data.pension_applicable,
            nhf_applicable=data.nhf_applicable,
            nhis_applicable=data.nhis_applicable,
            nsitf_applicable=data.nsitf_applicable,
            itf_applicable=data.itf_applicable,
            pension_min_service_months=data.pension_min_service_months,
            counts_for_itf_headcount=data.counts_for_itf_headcount,
            gratuity_eligible=data.gratuity_eligible,
            gratuity_min_service_years=data.gratuity_min_service_years,
            is_payroll_employee=data.is_payroll_employee,
        )

        if self.principal:
            config.created_by_id = self.principal.user_id

        self.db.add(config)
        self.db.flush()
        return config

    def update_deduction_config(
        self,
        config_id: int,
        data: DeductionConfigUpdateData,
    ) -> EmploymentTypeDeductionConfig:
        """Update a deduction config."""
        config = self.get_deduction_config(config_id)

        if data.display_name is not None:
            config.display_name = data.display_name
        if data.description is not None:
            config.description = data.description
        if data.paye_applicable is not None:
            config.paye_applicable = data.paye_applicable
        if data.pension_applicable is not None:
            config.pension_applicable = data.pension_applicable
        if data.nhf_applicable is not None:
            config.nhf_applicable = data.nhf_applicable
        if data.nhis_applicable is not None:
            config.nhis_applicable = data.nhis_applicable
        if data.nsitf_applicable is not None:
            config.nsitf_applicable = data.nsitf_applicable
        if data.itf_applicable is not None:
            config.itf_applicable = data.itf_applicable
        if data.pension_min_service_months is not None:
            config.pension_min_service_months = data.pension_min_service_months
        if data.counts_for_itf_headcount is not None:
            config.counts_for_itf_headcount = data.counts_for_itf_headcount
        if data.gratuity_eligible is not None:
            config.gratuity_eligible = data.gratuity_eligible
        if data.gratuity_min_service_years is not None:
            config.gratuity_min_service_years = data.gratuity_min_service_years
        if data.is_payroll_employee is not None:
            config.is_payroll_employee = data.is_payroll_employee
        if data.is_active is not None:
            config.is_active = data.is_active

        self.db.flush()
        return config

    def initialize_default_deduction_configs(
        self,
        company: Optional[str] = None,
    ) -> List[EmploymentTypeDeductionConfig]:
        """Create default deduction configs for all employment types."""
        created = []

        for config_data in DEFAULT_EMPLOYMENT_TYPE_CONFIGS:
            # Check if config already exists
            existing = self.db.scalar(
                select(EmploymentTypeDeductionConfig).where(
                    and_(
                        EmploymentTypeDeductionConfig.company == company,
                        EmploymentTypeDeductionConfig.employment_type
                        == config_data["employment_type"],
                    )
                )
            )

            if existing:
                continue

            config = EmploymentTypeDeductionConfig(
                company=company,
                employment_type=config_data["employment_type"],
                display_name=config_data["display_name"],
                description=config_data.get("description"),
                paye_applicable=config_data.get("paye_applicable", True),
                pension_applicable=config_data.get("pension_applicable", True),
                nhf_applicable=config_data.get("nhf_applicable", True),
                nhis_applicable=config_data.get("nhis_applicable", True),
                nsitf_applicable=config_data.get("nsitf_applicable", True),
                itf_applicable=config_data.get("itf_applicable", True),
                pension_min_service_months=config_data.get(
                    "pension_min_service_months", 0
                ),
                counts_for_itf_headcount=config_data.get(
                    "counts_for_itf_headcount", True
                ),
                gratuity_eligible=config_data.get("gratuity_eligible", True),
                gratuity_min_service_years=config_data.get(
                    "gratuity_min_service_years", 5
                ),
            )

            if self.principal:
                config.created_by_id = self.principal.user_id

            self.db.add(config)
            created.append(config)

        self.db.flush()
        return created
