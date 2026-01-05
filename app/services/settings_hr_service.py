"""Service layer for HR settings routes."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.hr_settings import (
    HRSettings,
    LeaveEncashmentPolicy,
    HolidayCalendar,
    SalaryBand,
    EmploymentTypeDeductionConfig,
)


class SettingsHRService:
    """HR settings coordinator for read/write operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_settings(self) -> HRSettings:
        settings = self.db.query(HRSettings).filter(HRSettings.company == None).first()
        if not settings:
            settings = HRSettings()
        return settings

    def save_settings(self, values: dict[str, Any]) -> None:
        settings = self.db.query(HRSettings).filter(HRSettings.company == None).first()
        if not settings:
            settings = HRSettings()
            self.db.add(settings)

        for key, value in values.items():
            setattr(settings, key, value)

        self.db.commit()

    def list_leave_policies(self) -> list[LeaveEncashmentPolicy]:
        return self.db.query(LeaveEncashmentPolicy).order_by(LeaveEncashmentPolicy.leave_type_id).all()

    def list_holiday_calendars(self) -> list[HolidayCalendar]:
        return self.db.query(HolidayCalendar).order_by(HolidayCalendar.name).all()

    def list_salary_bands(self) -> list[SalaryBand]:
        return self.db.query(SalaryBand).order_by(SalaryBand.grade).all()

    def list_deduction_configs(self) -> list[EmploymentTypeDeductionConfig]:
        return (
            self.db.query(EmploymentTypeDeductionConfig)
            .order_by(EmploymentTypeDeductionConfig.employment_type)
            .all()
        )
