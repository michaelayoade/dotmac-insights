"""Payroll service for HR module.

Handles salary components, structures, assignments, payroll entries,
and salary slips.
"""
from __future__ import annotations

import ast
import operator
from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import and_, delete, func, or_, select

from app.utils.datetime_utils import utc_now
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.hr_payroll import (
    PayrollEntry,
    SalaryComponent,
    SalaryComponentType,
    SalarySlip,
    SalarySlipDeduction,
    SalarySlipEarning,
    SalarySlipStatus,
    SalaryStructure,
    SalaryStructureAssignment,
    SalaryStructureDeduction,
    SalaryStructureEarning,
)
from app.services.base import apply_sort, paginate
from app.services.hr.payroll_types import (
    BulkSlipResult,
    ComponentAmount,
    PayrollEntryCreateData,
    PayrollEntryFilters,
    PayrollEntryUpdateData,
    PayrollSummary,
    SalaryComponentCreateData,
    SalaryComponentUpdateData,
    SalarySlipCreateData,
    SalarySlipFilters,
    SalarySlipUpdateData,
    SalaryStructureCreateData,
    SalaryStructureFilters,
    SalaryStructureUpdateData,
    SlipCalculation,
    SlipDeductionData,
    SlipEarningData,
    SlipGenerationResult,
    SlipPaymentData,
    StructureAssignmentCreateData,
    StructureAssignmentFilters,
    StructureAssignmentUpdateData,
    YTDEarnings,
)
from app.services.activity_logger import ActivityLogger
from app.services.hr.errors import (
    NoSalaryAssignmentError,
    PayrollAlreadyProcessedError,
    PayrollEntryNotFoundError,
    SalaryComponentNotFoundError,
    SalarySlipNotFoundError,
    SalaryStructureAssignmentNotFoundError,
    SalaryStructureNotFoundError,
    SlipStatusTransitionError,
)
from app.services.types import PaginatedResult, PaginationParams, SortParams

if TYPE_CHECKING:
    from app.models.hr_settings import HRSettings
    from app.web.context import Principal

# Map day names to weekday numbers
WEEKDAY_MAP = {
    "MONDAY": 0,
    "TUESDAY": 1,
    "WEDNESDAY": 2,
    "THURSDAY": 3,
    "FRIDAY": 4,
    "SATURDAY": 5,
    "SUNDAY": 6,
}

__all__ = ["PayrollService"]


class PayrollService:
    """Service for payroll management operations.

    Uses HR settings for configurable behavior:
    - work_week_days: Which days are working days (for calculating payment days)
    - payroll_frequency: Default payroll frequency
    - salary_payment_day: Default payment day of month
    - payroll_cutoff_day: Default cutoff day for payroll processing
    - salary_currency: Default currency for salary
    """

    def __init__(
        self, db: Session, principal: Optional["Principal"] = None
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

    # ==========================================================================
    # Salary Components
    # ==========================================================================

    def list_salary_components(
        self,
        component_type: Optional[SalaryComponentType] = None,
        include_disabled: bool = False,
        pagination: Optional[PaginationParams] = None,
        sort: Optional[SortParams] = None,
    ) -> PaginatedResult[SalaryComponent]:
        """List salary components with optional filters."""
        query = select(SalaryComponent)

        if component_type:
            query = query.where(SalaryComponent.type == component_type)
        if not include_disabled:
            query = query.where(SalaryComponent.disabled == False)

        if sort:
            query = apply_sort(query, SalaryComponent, sort)
        else:
            query = query.order_by(SalaryComponent.salary_component_name)

        return paginate(self.db, query, pagination)

    def get_salary_component(self, component_id: int) -> SalaryComponent:
        """Get a salary component by ID."""
        component = self.db.get(SalaryComponent, component_id)
        if not component:
            raise SalaryComponentNotFoundError(component_id)
        return component

    def get_salary_component_by_name(self, name: str) -> Optional[SalaryComponent]:
        """Get a salary component by name."""
        return self.db.scalar(
            select(SalaryComponent).where(
                SalaryComponent.salary_component_name == name
            )
        )

    def create_salary_component(
        self, data: SalaryComponentCreateData
    ) -> SalaryComponent:
        """Create a new salary component."""
        component = SalaryComponent(
            salary_component_name=data.salary_component_name,
            salary_component_abbr=data.salary_component_abbr,
            type=data.type,
            description=data.description,
            is_tax_applicable=data.is_tax_applicable,
            is_payable=data.is_payable,
            is_flexible_benefit=data.is_flexible_benefit,
            depends_on_payment_days=data.depends_on_payment_days,
            variable_based_on_taxable_salary=data.variable_based_on_taxable_salary,
            exempted_from_income_tax=data.exempted_from_income_tax,
            statistical_component=data.statistical_component,
            do_not_include_in_total=data.do_not_include_in_total,
            default_account=data.default_account,
        )
        self.db.add(component)
        self.db.flush()
        return component

    def update_salary_component(
        self, component_id: int, data: SalaryComponentUpdateData
    ) -> SalaryComponent:
        """Update a salary component."""
        component = self.get_salary_component(component_id)

        if data.salary_component_name is not None:
            component.salary_component_name = data.salary_component_name
        if data.salary_component_abbr is not None:
            component.salary_component_abbr = data.salary_component_abbr
        if data.type is not None:
            component.type = data.type
        if data.description is not None:
            component.description = data.description
        if data.is_tax_applicable is not None:
            component.is_tax_applicable = data.is_tax_applicable
        if data.is_payable is not None:
            component.is_payable = data.is_payable
        if data.is_flexible_benefit is not None:
            component.is_flexible_benefit = data.is_flexible_benefit
        if data.depends_on_payment_days is not None:
            component.depends_on_payment_days = data.depends_on_payment_days
        if data.variable_based_on_taxable_salary is not None:
            component.variable_based_on_taxable_salary = (
                data.variable_based_on_taxable_salary
            )
        if data.exempted_from_income_tax is not None:
            component.exempted_from_income_tax = data.exempted_from_income_tax
        if data.statistical_component is not None:
            component.statistical_component = data.statistical_component
        if data.do_not_include_in_total is not None:
            component.do_not_include_in_total = data.do_not_include_in_total
        if data.default_account is not None:
            component.default_account = data.default_account
        if data.disabled is not None:
            component.disabled = data.disabled

        self.db.flush()
        return component

    def delete_salary_component(self, component_id: int) -> None:
        """Delete a salary component (soft delete by disabling)."""
        component = self.get_salary_component(component_id)
        component.disabled = True
        self.db.flush()

    # ==========================================================================
    # Salary Structures
    # ==========================================================================

    def list_salary_structures(
        self,
        filters: Optional[SalaryStructureFilters] = None,
        pagination: Optional[PaginationParams] = None,
        sort: Optional[SortParams] = None,
    ) -> PaginatedResult[SalaryStructure]:
        """List salary structures with filters."""
        query = select(SalaryStructure)

        if filters:
            if filters.company is not None:
                query = query.where(SalaryStructure.company == filters.company)
            if filters.is_active is not None:
                active_val = "Yes" if filters.is_active else "No"
                query = query.where(SalaryStructure.is_active == active_val)
            if filters.payroll_frequency is not None:
                query = query.where(
                    SalaryStructure.payroll_frequency == filters.payroll_frequency
                )
            if filters.search:
                query = query.where(
                    SalaryStructure.salary_structure_name.ilike(
                        f"%{filters.search}%"
                    )
                )

        if sort:
            query = apply_sort(query, SalaryStructure, sort)
        else:
            query = query.order_by(SalaryStructure.salary_structure_name)

        return paginate(self.db, query, pagination)

    def get_salary_structure(self, structure_id: int) -> SalaryStructure:
        """Get a salary structure by ID with earnings and deductions."""
        structure = self.db.get(SalaryStructure, structure_id)
        if not structure:
            raise SalaryStructureNotFoundError(structure_id)
        return structure

    def get_salary_structure_by_name(self, name: str) -> Optional[SalaryStructure]:
        """Get a salary structure by name."""
        return self.db.scalar(
            select(SalaryStructure).where(
                SalaryStructure.salary_structure_name == name
            )
        )

    def create_salary_structure(
        self, data: SalaryStructureCreateData
    ) -> SalaryStructure:
        """Create a new salary structure with earnings and deductions."""
        structure = SalaryStructure(
            salary_structure_name=data.salary_structure_name,
            company=data.company,
            payroll_frequency=data.payroll_frequency,
            currency=data.currency,
            payment_account=data.payment_account,
            mode_of_payment=data.mode_of_payment,
        )
        self.db.add(structure)
        self.db.flush()

        # Add earnings
        for idx, earning in enumerate(data.earnings):
            self.db.add(
                SalaryStructureEarning(
                    salary_structure_id=structure.id,
                    salary_component=earning.salary_component,
                    abbr=earning.abbr,
                    amount=earning.amount,
                    amount_based_on_formula=earning.amount_based_on_formula,
                    formula=earning.formula,
                    condition=earning.condition,
                    statistical_component=earning.statistical_component,
                    do_not_include_in_total=earning.do_not_include_in_total,
                    idx=earning.idx or idx,
                )
            )

        # Add deductions
        for idx, deduction in enumerate(data.deductions):
            self.db.add(
                SalaryStructureDeduction(
                    salary_structure_id=structure.id,
                    salary_component=deduction.salary_component,
                    abbr=deduction.abbr,
                    amount=deduction.amount,
                    amount_based_on_formula=deduction.amount_based_on_formula,
                    formula=deduction.formula,
                    condition=deduction.condition,
                    statistical_component=deduction.statistical_component,
                    do_not_include_in_total=deduction.do_not_include_in_total,
                    idx=deduction.idx or idx,
                )
            )

        self.db.flush()
        return structure

    def update_salary_structure(
        self, structure_id: int, data: SalaryStructureUpdateData
    ) -> SalaryStructure:
        """Update a salary structure."""
        structure = self.get_salary_structure(structure_id)

        if data.salary_structure_name is not None:
            structure.salary_structure_name = data.salary_structure_name
        if data.company is not None:
            structure.company = data.company
        if data.is_active is not None:
            structure.is_active = "Yes" if data.is_active else "No"
        if data.payroll_frequency is not None:
            structure.payroll_frequency = data.payroll_frequency
        if data.currency is not None:
            structure.currency = data.currency
        if data.payment_account is not None:
            structure.payment_account = data.payment_account
        if data.mode_of_payment is not None:
            structure.mode_of_payment = data.mode_of_payment

        # Replace earnings if provided
        if data.earnings is not None:
            for earning in structure.earnings:
                self.db.delete(earning)
            for idx, earning in enumerate(data.earnings):
                self.db.add(
                    SalaryStructureEarning(
                        salary_structure_id=structure.id,
                        salary_component=earning.salary_component,
                        abbr=earning.abbr,
                        amount=earning.amount,
                        amount_based_on_formula=earning.amount_based_on_formula,
                        formula=earning.formula,
                        condition=earning.condition,
                        statistical_component=earning.statistical_component,
                        do_not_include_in_total=earning.do_not_include_in_total,
                        idx=earning.idx or idx,
                    )
                )

        # Replace deductions if provided
        if data.deductions is not None:
            for deduction in structure.deductions:
                self.db.delete(deduction)
            for idx, deduction in enumerate(data.deductions):
                self.db.add(
                    SalaryStructureDeduction(
                        salary_structure_id=structure.id,
                        salary_component=deduction.salary_component,
                        abbr=deduction.abbr,
                        amount=deduction.amount,
                        amount_based_on_formula=deduction.amount_based_on_formula,
                        formula=deduction.formula,
                        condition=deduction.condition,
                        statistical_component=deduction.statistical_component,
                        do_not_include_in_total=deduction.do_not_include_in_total,
                        idx=deduction.idx or idx,
                    )
                )

        self.db.flush()
        return structure

    def delete_salary_structure(self, structure_id: int) -> None:
        """Delete a salary structure (soft delete by deactivating)."""
        structure = self.get_salary_structure(structure_id)
        structure.is_active = "No"
        self.db.flush()

    # ==========================================================================
    # Salary Structure Assignments
    # ==========================================================================

    def list_structure_assignments(
        self,
        filters: Optional[StructureAssignmentFilters] = None,
        pagination: Optional[PaginationParams] = None,
        sort: Optional[SortParams] = None,
    ) -> PaginatedResult[SalaryStructureAssignment]:
        """List salary structure assignments with filters."""
        query = select(SalaryStructureAssignment)

        if filters:
            if filters.employee_id is not None:
                query = query.where(
                    SalaryStructureAssignment.employee_id == filters.employee_id
                )
            if filters.salary_structure_id is not None:
                query = query.where(
                    SalaryStructureAssignment.salary_structure_id
                    == filters.salary_structure_id
                )
            if filters.from_date is not None:
                query = query.where(
                    SalaryStructureAssignment.from_date >= filters.from_date
                )
            if filters.company is not None:
                query = query.where(
                    SalaryStructureAssignment.company == filters.company
                )

        if sort:
            query = apply_sort(query, SalaryStructureAssignment, sort)
        else:
            query = query.order_by(SalaryStructureAssignment.from_date.desc())

        return paginate(self.db, query, pagination)

    def get_structure_assignment(
        self, assignment_id: int
    ) -> SalaryStructureAssignment:
        """Get a salary structure assignment by ID."""
        assignment = self.db.get(SalaryStructureAssignment, assignment_id)
        if not assignment:
            raise SalaryStructureAssignmentNotFoundError(assignment_id)
        return assignment

    def get_employee_current_assignment(
        self, employee_id: int, as_of: Optional[date] = None
    ) -> Optional[SalaryStructureAssignment]:
        """Get the current salary structure assignment for an employee."""
        check_date = as_of or date.today()
        return self.db.scalar(
            select(SalaryStructureAssignment)
            .where(
                and_(
                    SalaryStructureAssignment.employee_id == employee_id,
                    SalaryStructureAssignment.from_date <= check_date,
                )
            )
            .order_by(SalaryStructureAssignment.from_date.desc())
            .limit(1)
        )

    def create_structure_assignment(
        self, data: StructureAssignmentCreateData
    ) -> SalaryStructureAssignment:
        """Create a new salary structure assignment."""
        assignment = SalaryStructureAssignment(
            employee_id=data.employee_id,
            employee=data.employee,
            employee_name=data.employee_name,
            salary_structure_id=data.salary_structure_id,
            salary_structure=data.salary_structure,
            from_date=data.from_date,
            base=data.base,
            variable=data.variable,
            income_tax_slab=data.income_tax_slab,
            company=data.company,
        )
        self.db.add(assignment)
        self.db.flush()
        return assignment

    def update_structure_assignment(
        self, assignment_id: int, data: StructureAssignmentUpdateData
    ) -> SalaryStructureAssignment:
        """Update a salary structure assignment."""
        assignment = self.get_structure_assignment(assignment_id)

        if data.salary_structure_id is not None:
            assignment.salary_structure_id = data.salary_structure_id
        if data.salary_structure is not None:
            assignment.salary_structure = data.salary_structure
        if data.from_date is not None:
            assignment.from_date = data.from_date
        if data.base is not None:
            assignment.base = data.base
        if data.variable is not None:
            assignment.variable = data.variable
        if data.income_tax_slab is not None:
            assignment.income_tax_slab = data.income_tax_slab

        self.db.flush()
        return assignment

    def delete_structure_assignment(self, assignment_id: int) -> None:
        """Delete a salary structure assignment."""
        assignment = self.get_structure_assignment(assignment_id)
        self.db.delete(assignment)
        self.db.flush()

    # ==========================================================================
    # Payroll Entries
    # ==========================================================================

    def list_payroll_entries(
        self,
        filters: Optional[PayrollEntryFilters] = None,
        pagination: Optional[PaginationParams] = None,
        sort: Optional[SortParams] = None,
    ) -> PaginatedResult[PayrollEntry]:
        """List payroll entries with filters."""
        query = select(PayrollEntry)

        if filters:
            if filters.company is not None:
                query = query.where(PayrollEntry.company == filters.company)
            if filters.department is not None:
                query = query.where(PayrollEntry.department == filters.department)
            if filters.from_date is not None:
                query = query.where(PayrollEntry.start_date >= filters.from_date)
            if filters.to_date is not None:
                query = query.where(PayrollEntry.end_date <= filters.to_date)
            if filters.payroll_frequency is not None:
                query = query.where(
                    PayrollEntry.payroll_frequency == filters.payroll_frequency
                )
            if filters.salary_slips_created is not None:
                query = query.where(
                    PayrollEntry.salary_slips_created == filters.salary_slips_created
                )
            if filters.salary_slips_submitted is not None:
                query = query.where(
                    PayrollEntry.salary_slips_submitted
                    == filters.salary_slips_submitted
                )

        if sort:
            query = apply_sort(query, PayrollEntry, sort)
        else:
            query = query.order_by(PayrollEntry.posting_date.desc())

        return paginate(self.db, query, pagination)

    def get_payroll_entry(self, entry_id: int) -> PayrollEntry:
        """Get a payroll entry by ID."""
        entry = self.db.get(PayrollEntry, entry_id)
        if not entry:
            raise PayrollEntryNotFoundError(entry_id)
        return entry

    def create_payroll_entry(self, data: PayrollEntryCreateData) -> PayrollEntry:
        """Create a new payroll entry."""
        entry = PayrollEntry(
            posting_date=data.posting_date,
            start_date=data.start_date,
            end_date=data.end_date,
            payroll_frequency=data.payroll_frequency,
            company=data.company,
            department=data.department,
            branch=data.branch,
            designation=data.designation,
            currency=data.currency,
            exchange_rate=data.exchange_rate,
            region_code=data.region_code,
            payment_account=data.payment_account,
            bank_account=data.bank_account,
        )

        if self.principal and self.principal.user_id:
            entry.created_by_id = self.principal.user_id

        self.db.add(entry)
        self.db.flush()
        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="hr.payroll.entry.create",
            user_id=self.principal.user_id if self.principal else None,
            user_email=getattr(self.principal, "email", None),
            entity_type="payroll_entry",
            entity_id=str(entry.id),
            summary=f"Created payroll entry {entry.erpnext_id or entry.id}",
            metadata={"company": entry.company},
        )
        return entry

    def update_payroll_entry(
        self, entry_id: int, data: PayrollEntryUpdateData
    ) -> PayrollEntry:
        """Update a payroll entry."""
        entry = self.get_payroll_entry(entry_id)

        if entry.salary_slips_created:
            raise PayrollAlreadyProcessedError(
                entry_id, "Cannot update payroll entry after slips are created"
            )

        if data.posting_date is not None:
            entry.posting_date = data.posting_date
        if data.payroll_frequency is not None:
            entry.payroll_frequency = data.payroll_frequency
        if data.department is not None:
            entry.department = data.department
        if data.branch is not None:
            entry.branch = data.branch
        if data.designation is not None:
            entry.designation = data.designation
        if data.currency is not None:
            entry.currency = data.currency
        if data.exchange_rate is not None:
            entry.exchange_rate = data.exchange_rate
        if data.region_code is not None:
            entry.region_code = data.region_code
        if data.payment_account is not None:
            entry.payment_account = data.payment_account
        if data.bank_account is not None:
            entry.bank_account = data.bank_account

        if self.principal and self.principal.user_id:
            entry.updated_by_id = self.principal.user_id

        self.db.flush()
        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="hr.payroll.entry.update",
            user_id=self.principal.user_id if self.principal else None,
            user_email=getattr(self.principal, "email", None),
            entity_type="payroll_entry",
            entity_id=str(entry.id),
            summary=f"Updated payroll entry {entry.erpnext_id or entry.id}",
        )
        return entry

    def delete_payroll_entry(self, entry_id: int) -> None:
        """Delete a payroll entry and its salary slips."""
        entry = self.get_payroll_entry(entry_id)

        if entry.salary_slips_submitted:
            raise PayrollAlreadyProcessedError(
                entry_id, "Cannot delete payroll entry with submitted slips"
            )

        # Delete associated salary slips
        self.db.execute(
            delete(SalarySlip)
            .where(SalarySlip.payroll_entry == entry.erpnext_id)
        )

        self.db.delete(entry)
        self.db.flush()
        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="hr.payroll.entry.delete",
            user_id=self.principal.user_id if self.principal else None,
            user_email=getattr(self.principal, "email", None),
            entity_type="payroll_entry",
            entity_id=str(entry.id),
            summary=f"Deleted payroll entry {entry.erpnext_id or entry.id}",
        )

    # ==========================================================================
    # Salary Slips
    # ==========================================================================

    def list_salary_slips(
        self,
        filters: Optional[SalarySlipFilters] = None,
        pagination: Optional[PaginationParams] = None,
        sort: Optional[SortParams] = None,
    ) -> PaginatedResult[SalarySlip]:
        """List salary slips with filters."""
        query = select(SalarySlip)

        if filters:
            if filters.employee_id is not None:
                query = query.where(SalarySlip.employee_id == filters.employee_id)
            if filters.status is not None:
                query = query.where(SalarySlip.status == filters.status)
            if filters.from_date is not None:
                query = query.where(SalarySlip.start_date >= filters.from_date)
            if filters.to_date is not None:
                query = query.where(SalarySlip.end_date <= filters.to_date)
            if filters.company is not None:
                query = query.where(SalarySlip.company == filters.company)
            if filters.department is not None:
                query = query.where(SalarySlip.department == filters.department)
            if filters.payroll_entry is not None:
                query = query.where(SalarySlip.payroll_entry == filters.payroll_entry)

        if sort:
            query = apply_sort(query, SalarySlip, sort)
        else:
            query = query.order_by(SalarySlip.posting_date.desc())

        return paginate(self.db, query, pagination)

    def list_salary_slip_years(self, employee_id: int) -> List[int]:
        """List distinct payroll years for an employee."""
        stmt = (
            select(func.extract("year", SalarySlip.posting_date))
            .where(SalarySlip.employee_id == employee_id)
            .distinct()
            .order_by(func.extract("year", SalarySlip.posting_date).desc())
        )
        years = self.db.scalars(stmt).all()
        return [int(y) for y in years if y]

    def get_salary_slip(self, slip_id: int) -> SalarySlip:
        """Get a salary slip by ID with earnings and deductions."""
        slip = self.db.get(SalarySlip, slip_id)
        if not slip:
            raise SalarySlipNotFoundError(slip_id)
        return slip

    def create_salary_slip(self, data: SalarySlipCreateData) -> SalarySlip:
        """Create a new salary slip with earnings and deductions."""
        slip = SalarySlip(
            employee_id=data.employee_id,
            employee=data.employee,
            employee_name=data.employee_name,
            department=data.department,
            designation=data.designation,
            branch=data.branch,
            salary_structure=data.salary_structure,
            posting_date=data.posting_date,
            start_date=data.start_date,
            end_date=data.end_date,
            payroll_frequency=data.payroll_frequency,
            company=data.company,
            currency=data.currency,
            region_code=data.region_code,
            total_working_days=data.total_working_days,
            absent_days=data.absent_days,
            payment_days=data.payment_days,
            leave_without_pay=data.leave_without_pay,
            gross_pay=data.gross_pay,
            total_deduction=data.total_deduction,
            net_pay=data.net_pay,
            rounded_total=data.net_pay.quantize(Decimal("1")),
            bank_name=data.bank_name,
            bank_account_no=data.bank_account_no,
            payroll_entry=data.payroll_entry,
            status=SalarySlipStatus.DRAFT,
        )

        if self.principal and self.principal.user_id:
            slip.created_by_id = self.principal.user_id

        self.db.add(slip)
        self.db.flush()

        # Add earnings
        for idx, earning in enumerate(data.earnings):
            self.db.add(
                SalarySlipEarning(
                    salary_slip_id=slip.id,
                    salary_component=earning.salary_component,
                    abbr=earning.abbr,
                    amount=earning.amount,
                    default_amount=earning.default_amount,
                    additional_amount=earning.additional_amount,
                    year_to_date=earning.year_to_date,
                    statistical_component=earning.statistical_component,
                    do_not_include_in_total=earning.do_not_include_in_total,
                    idx=earning.idx or idx,
                )
            )

        # Add deductions
        for idx, deduction in enumerate(data.deductions):
            self.db.add(
                SalarySlipDeduction(
                    salary_slip_id=slip.id,
                    salary_component=deduction.salary_component,
                    abbr=deduction.abbr,
                    amount=deduction.amount,
                    default_amount=deduction.default_amount,
                    additional_amount=deduction.additional_amount,
                    year_to_date=deduction.year_to_date,
                    statistical_component=deduction.statistical_component,
                    do_not_include_in_total=deduction.do_not_include_in_total,
                    idx=deduction.idx or idx,
                )
            )

        self.db.flush()
        return slip

    def update_salary_slip(
        self, slip_id: int, data: SalarySlipUpdateData
    ) -> SalarySlip:
        """Update a salary slip."""
        slip = self.get_salary_slip(slip_id)

        if slip.status != SalarySlipStatus.DRAFT:
            raise SlipStatusTransitionError(
                slip_id,
                slip.status.value,
                "update",
            )

        if data.total_working_days is not None:
            slip.total_working_days = data.total_working_days
        if data.absent_days is not None:
            slip.absent_days = data.absent_days
        if data.payment_days is not None:
            slip.payment_days = data.payment_days
        if data.leave_without_pay is not None:
            slip.leave_without_pay = data.leave_without_pay
        if data.gross_pay is not None:
            slip.gross_pay = data.gross_pay
        if data.total_deduction is not None:
            slip.total_deduction = data.total_deduction
        if data.net_pay is not None:
            slip.net_pay = data.net_pay
            slip.rounded_total = data.net_pay.quantize(Decimal("1"))

        # Replace earnings if provided
        if data.earnings is not None:
            for earning in slip.earnings:
                self.db.delete(earning)
            for idx, earning in enumerate(data.earnings):
                self.db.add(
                    SalarySlipEarning(
                        salary_slip_id=slip.id,
                        salary_component=earning.salary_component,
                        abbr=earning.abbr,
                        amount=earning.amount,
                        default_amount=earning.default_amount,
                        additional_amount=earning.additional_amount,
                        year_to_date=earning.year_to_date,
                        statistical_component=earning.statistical_component,
                        do_not_include_in_total=earning.do_not_include_in_total,
                        idx=earning.idx or idx,
                    )
                )

        # Replace deductions if provided
        if data.deductions is not None:
            for deduction in slip.deductions:
                self.db.delete(deduction)
            for idx, deduction in enumerate(data.deductions):
                self.db.add(
                    SalarySlipDeduction(
                        salary_slip_id=slip.id,
                        salary_component=deduction.salary_component,
                        abbr=deduction.abbr,
                        amount=deduction.amount,
                        default_amount=deduction.default_amount,
                        additional_amount=deduction.additional_amount,
                        year_to_date=deduction.year_to_date,
                        statistical_component=deduction.statistical_component,
                        do_not_include_in_total=deduction.do_not_include_in_total,
                        idx=deduction.idx or idx,
                    )
                )

        if self.principal and self.principal.user_id:
            slip.updated_by_id = self.principal.user_id

        self.db.flush()
        return slip

    def submit_salary_slip(self, slip_id: int) -> SalarySlip:
        """Submit a draft salary slip."""
        slip = self.get_salary_slip(slip_id)

        if slip.status != SalarySlipStatus.DRAFT:
            raise SlipStatusTransitionError(
                slip_id, slip.status.value, SalarySlipStatus.SUBMITTED.value
            )

        slip.status = SalarySlipStatus.SUBMITTED
        slip.docstatus = 1
        slip.status_changed_at = utc_now()
        if self.principal and self.principal.user_id:
            slip.status_changed_by_id = self.principal.user_id
            slip.updated_by_id = self.principal.user_id

        self.db.flush()
        return slip

    def mark_slip_paid(self, slip_id: int, data: SlipPaymentData) -> SalarySlip:
        """Mark a submitted salary slip as paid."""
        slip = self.get_salary_slip(slip_id)

        if slip.status != SalarySlipStatus.SUBMITTED:
            raise SlipStatusTransitionError(
                slip_id, slip.status.value, SalarySlipStatus.PAID.value
            )

        slip.status = SalarySlipStatus.PAID
        slip.paid_at = data.paid_at or utc_now()
        slip.payment_reference = data.payment_reference
        slip.payment_mode = data.payment_mode
        slip.status_changed_at = utc_now()

        if self.principal and self.principal.user_id:
            slip.paid_by_id = self.principal.user_id
            slip.status_changed_by_id = self.principal.user_id
            slip.updated_by_id = self.principal.user_id

        self.db.flush()
        return slip

    def cancel_salary_slip(self, slip_id: int) -> SalarySlip:
        """Cancel a salary slip."""
        slip = self.get_salary_slip(slip_id)

        if slip.status == SalarySlipStatus.PAID:
            raise SlipStatusTransitionError(
                slip_id, slip.status.value, SalarySlipStatus.CANCELLED.value
            )

        slip.status = SalarySlipStatus.CANCELLED
        slip.docstatus = 2
        slip.status_changed_at = utc_now()
        if self.principal and self.principal.user_id:
            slip.status_changed_by_id = self.principal.user_id
            slip.updated_by_id = self.principal.user_id

        self.db.flush()
        return slip

    def void_salary_slip(self, slip_id: int, reason: str) -> SalarySlip:
        """Void a paid salary slip."""
        slip = self.get_salary_slip(slip_id)

        if slip.status != SalarySlipStatus.PAID:
            raise SlipStatusTransitionError(
                slip_id, slip.status.value, SalarySlipStatus.VOIDED.value
            )

        slip.status = SalarySlipStatus.VOIDED
        slip.void_reason = reason
        slip.voided_at = utc_now()
        slip.status_changed_at = utc_now()
        if self.principal and self.principal.user_id:
            slip.voided_by_id = self.principal.user_id
            slip.status_changed_by_id = self.principal.user_id
            slip.updated_by_id = self.principal.user_id

        self.db.flush()
        return slip

    def delete_salary_slip(self, slip_id: int) -> None:
        """Delete a salary slip (must be in DRAFT status)."""
        slip = self.get_salary_slip(slip_id)

        if slip.status != SalarySlipStatus.DRAFT:
            raise SlipStatusTransitionError(
                slip_id, slip.status.value, "delete"
            )

        self.db.delete(slip)
        self.db.flush()

    def bulk_submit_slips(self, slip_ids: List[int]) -> BulkSlipResult:
        """Bulk submit salary slips by IDs."""
        result = BulkSlipResult()

        for slip_id in slip_ids:
            try:
                slip = self.db.get(SalarySlip, slip_id)
                if slip and slip.status == SalarySlipStatus.DRAFT:
                    self.submit_salary_slip(slip_id)
                    result.submitted_count += 1
                else:
                    result.failed_ids.append(slip_id)
            except Exception as e:
                result.failed_ids.append(slip_id)
                result.errors.append(f"Slip {slip_id}: {str(e)}")

        self.db.flush()
        return result

    def bulk_cancel_slips(self, slip_ids: List[int]) -> BulkSlipResult:
        """Bulk cancel salary slips by IDs."""
        result = BulkSlipResult()

        for slip_id in slip_ids:
            try:
                slip = self.db.get(SalarySlip, slip_id)
                if slip and slip.status == SalarySlipStatus.SUBMITTED:
                    self.cancel_salary_slip(slip_id)
                    result.cancelled_count += 1
                else:
                    result.failed_ids.append(slip_id)
            except Exception as e:
                result.failed_ids.append(slip_id)
                result.errors.append(f"Slip {slip_id}: {str(e)}")

        self.db.flush()
        return result

    def get_slips_summary(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        company: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get salary slips summary statistics by status."""
        from sqlalchemy import func

        query = select(
            SalarySlip.status,
            func.count(SalarySlip.id),
            func.sum(SalarySlip.gross_pay),
            func.sum(SalarySlip.net_pay),
        )

        if from_date:
            query = query.where(SalarySlip.start_date >= from_date)
        if to_date:
            query = query.where(SalarySlip.end_date <= to_date)
        if company:
            query = query.where(SalarySlip.company == company)

        query = query.group_by(SalarySlip.status)
        results = self.db.execute(query).all()

        summary = {}
        total_gross = Decimal("0")
        total_net = Decimal("0")
        total_count = 0

        for row in results:
            status_val = row[0].value if row[0] else None
            count = int(row[1] or 0)
            gross = row[2] or Decimal("0")
            net = row[3] or Decimal("0")

            summary[status_val] = {
                "count": count,
                "gross_pay": float(gross),
                "net_pay": float(net),
            }
            total_count += count
            total_gross += gross
            total_net += net

        return {
            "by_status": summary,
            "totals": {
                "count": total_count,
                "gross_pay": float(total_gross),
                "net_pay": float(total_net),
            },
        }

    # ==========================================================================
    # Payroll Processing
    # ==========================================================================

    def generate_salary_slips(self, payroll_entry_id: int) -> SlipGenerationResult:
        """Generate salary slips for all eligible employees in a payroll entry."""
        entry = self.get_payroll_entry(payroll_entry_id)
        result = SlipGenerationResult(payroll_entry_id=payroll_entry_id)

        if entry.salary_slips_created:
            raise PayrollAlreadyProcessedError(
                payroll_entry_id, "Salary slips already created"
            )

        # Get eligible employees
        employees = self._get_eligible_employees(entry)

        for employee in employees:
            try:
                # Check if employee has salary structure assignment
                assignment = self.get_employee_current_assignment(
                    employee.id, entry.start_date
                )
                if not assignment:
                    result.skipped_count += 1
                    result.skipped_employees.append(employee.id)
                    result.errors.append(
                        f"No salary assignment for employee {employee.id}"
                    )
                    continue

                # Calculate salary slip (uses settings for work week days)
                calculation = self.calculate_slip_components(
                    employee.id, entry.start_date, entry.end_date, entry.company
                )

                # Create salary slip
                slip_data = SalarySlipCreateData(
                    employee_id=employee.id,
                    employee=employee.erpnext_id or str(employee.id),
                    employee_name=employee.name,
                    department=employee.department,
                    designation=employee.designation,
                    salary_structure=assignment.salary_structure,
                    posting_date=entry.posting_date,
                    start_date=entry.start_date,
                    end_date=entry.end_date,
                    payroll_frequency=entry.payroll_frequency,
                    company=entry.company,
                    currency=entry.currency,
                    region_code=entry.region_code,
                    total_working_days=calculation.total_working_days,
                    absent_days=calculation.absent_days,
                    payment_days=calculation.payment_days,
                    leave_without_pay=calculation.leave_without_pay,
                    gross_pay=calculation.gross_pay,
                    total_deduction=calculation.total_deduction,
                    net_pay=calculation.net_pay,
                    payroll_entry=entry.erpnext_id,
                    earnings=[
                        SlipEarningData(
                            salary_component=e.component_name,
                            abbr=e.abbr,
                            amount=e.amount,
                            default_amount=e.amount,
                        )
                        for e in calculation.earnings
                    ],
                    deductions=[
                        SlipDeductionData(
                            salary_component=d.component_name,
                            abbr=d.abbr,
                            amount=d.amount,
                            default_amount=d.amount,
                        )
                        for d in calculation.deductions
                    ],
                )
                self.create_salary_slip(slip_data)
                result.created_count += 1

            except Exception as e:
                result.failed_count += 1
                result.failed_employees.append(employee.id)
                result.errors.append(f"Employee {employee.id}: {str(e)}")

        # Update payroll entry
        entry.salary_slips_created = True
        if self.principal and self.principal.user_id:
            entry.updated_by_id = self.principal.user_id

        self.db.flush()
        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="hr.payroll.slips.generate",
            user_id=self.principal.user_id if self.principal else None,
            user_email=getattr(self.principal, "email", None),
            entity_type="payroll_entry",
            entity_id=str(entry.id),
            summary=f"Generated salary slips for payroll entry {entry.erpnext_id or entry.id}",
            metadata={"created": result.created_count, "failed": result.failed_count, "skipped": result.skipped_count},
        )
        return result

    def submit_salary_slips(self, payroll_entry_id: int) -> BulkSlipResult:
        """Submit all draft salary slips for a payroll entry."""
        entry = self.get_payroll_entry(payroll_entry_id)
        result = BulkSlipResult()

        slips = self.db.scalars(
            select(SalarySlip).where(
                and_(
                    SalarySlip.payroll_entry == entry.erpnext_id,
                    SalarySlip.status == SalarySlipStatus.DRAFT,
                )
            )
        ).all()

        for slip in slips:
            try:
                self.submit_salary_slip(slip.id)
                result.submitted_count += 1
            except Exception as e:
                result.failed_ids.append(slip.id)
                result.errors.append(f"Slip {slip.id}: {str(e)}")

        # Update payroll entry
        entry.salary_slips_submitted = True
        entry.status_changed_at = utc_now()
        if self.principal and self.principal.user_id:
            entry.status_changed_by_id = self.principal.user_id
            entry.updated_by_id = self.principal.user_id

        self.db.flush()
        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="hr.payroll.slips.submit",
            user_id=self.principal.user_id if self.principal else None,
            user_email=getattr(self.principal, "email", None),
            entity_type="payroll_entry",
            entity_id=str(entry.id),
            summary=f"Submitted salary slips for payroll entry {entry.erpnext_id or entry.id}",
            metadata={"submitted": result.submitted_count, "failed": len(result.failed_ids)},
        )
        return result

    def calculate_slip_components(
        self, employee_id: int, start_date: date, end_date: date, company: Optional[str] = None
    ) -> SlipCalculation:
        """Calculate salary slip components for an employee.

        Uses HR settings for:
        - work_week_days: Which days are working days
        """
        # Get current salary structure assignment
        assignment = self.get_employee_current_assignment(employee_id, start_date)
        if not assignment or not assignment.salary_structure_id:
            raise NoSalaryAssignmentError(employee_id)

        structure = self.get_salary_structure(assignment.salary_structure_id)

        # Calculate working days (uses settings for work week days)
        total_days, absent_days, lwp = self._calculate_working_days(
            employee_id, start_date, end_date, company or assignment.company
        )
        payment_days = total_days - absent_days - lwp

        # Calculate earnings
        earnings: List[ComponentAmount] = []
        gross_pay = Decimal("0")

        for struct_earning in structure.earnings:
            if struct_earning.statistical_component:
                continue

            component = self.get_salary_component_by_name(
                struct_earning.salary_component
            )

            # Calculate amount (formula evaluation would go here)
            if struct_earning.amount_based_on_formula and struct_earning.formula:
                # Simple formula evaluation - in production, use a safe evaluator
                amount = self._evaluate_formula(
                    struct_earning.formula,
                    base=assignment.base,
                    variable=assignment.variable,
                    payment_days=payment_days,
                    total_working_days=total_days,
                )
            else:
                amount = struct_earning.amount

            # Pro-rate based on payment days
            if component and component.depends_on_payment_days and total_days > 0:
                amount = (amount * payment_days / total_days).quantize(
                    Decimal("0.01")
                )

            earnings.append(
                ComponentAmount(
                    component_name=struct_earning.salary_component,
                    component_type=SalaryComponentType.EARNING,
                    abbr=struct_earning.abbr,
                    amount=amount,
                    is_tax_applicable=component.is_tax_applicable if component else False,
                    depends_on_payment_days=(
                        component.depends_on_payment_days if component else True
                    ),
                )
            )

            if not struct_earning.do_not_include_in_total:
                gross_pay += amount

        # Calculate deductions
        deductions: List[ComponentAmount] = []
        total_deduction = Decimal("0")

        for struct_deduction in structure.deductions:
            if struct_deduction.statistical_component:
                continue

            component = self.get_salary_component_by_name(
                struct_deduction.salary_component
            )

            # Calculate amount
            if (
                struct_deduction.amount_based_on_formula
                and struct_deduction.formula
            ):
                amount = self._evaluate_formula(
                    struct_deduction.formula,
                    base=assignment.base,
                    variable=assignment.variable,
                    gross_pay=gross_pay,
                    payment_days=payment_days,
                    total_working_days=total_days,
                )
            else:
                amount = struct_deduction.amount

            # Pro-rate if needed
            if component and component.depends_on_payment_days and total_days > 0:
                amount = (amount * payment_days / total_days).quantize(
                    Decimal("0.01")
                )

            deductions.append(
                ComponentAmount(
                    component_name=struct_deduction.salary_component,
                    component_type=SalaryComponentType.DEDUCTION,
                    abbr=struct_deduction.abbr,
                    amount=amount,
                    is_tax_applicable=False,
                    depends_on_payment_days=(
                        component.depends_on_payment_days if component else True
                    ),
                )
            )

            if not struct_deduction.do_not_include_in_total:
                total_deduction += amount

        net_pay = gross_pay - total_deduction

        return SlipCalculation(
            employee_id=employee_id,
            start_date=start_date,
            end_date=end_date,
            total_working_days=total_days,
            payment_days=payment_days,
            absent_days=absent_days,
            leave_without_pay=lwp,
            earnings=earnings,
            deductions=deductions,
            gross_pay=gross_pay,
            total_deduction=total_deduction,
            net_pay=net_pay,
        )

    def get_ytd_earnings(self, employee_id: int, year: int) -> YTDEarnings:
        """Get year-to-date earnings for an employee."""
        # Get all salary slips for the year
        slips = self.db.scalars(
            select(SalarySlip).where(
                and_(
                    SalarySlip.employee_id == employee_id,
                    SalarySlip.status.in_(
                        [SalarySlipStatus.SUBMITTED, SalarySlipStatus.PAID]
                    ),
                    func.extract("year", SalarySlip.start_date) == year,
                )
            )
        ).all()

        result = YTDEarnings(employee_id=employee_id, year=year)

        for slip in slips:
            result.gross_earnings += slip.gross_pay
            result.total_deductions += slip.total_deduction
            result.net_earnings += slip.net_pay

            # Aggregate by component
            for earning in slip.earnings:
                if earning.salary_component not in result.component_totals:
                    result.component_totals[earning.salary_component] = Decimal("0")
                result.component_totals[earning.salary_component] += earning.amount

            for deduction in slip.deductions:
                key = f"-{deduction.salary_component}"
                if key not in result.component_totals:
                    result.component_totals[key] = Decimal("0")
                result.component_totals[key] += deduction.amount

        return result

    def get_payroll_summary(self, payroll_entry_id: int) -> PayrollSummary:
        """Get summary of a payroll run."""
        entry = self.get_payroll_entry(payroll_entry_id)

        slips = self.db.scalars(
            select(SalarySlip).where(
                SalarySlip.payroll_entry == entry.erpnext_id
            )
        ).all()

        by_dept: Dict[str, Decimal] = {}
        total_gross = Decimal("0")
        total_deductions = Decimal("0")
        total_net = Decimal("0")

        for slip in slips:
            total_gross += slip.gross_pay
            total_deductions += slip.total_deduction
            total_net += slip.net_pay

            dept = slip.department or "Unassigned"
            if dept not in by_dept:
                by_dept[dept] = Decimal("0")
            by_dept[dept] += slip.net_pay

        return PayrollSummary(
            payroll_entry_id=payroll_entry_id,
            start_date=entry.start_date,
            end_date=entry.end_date,
            total_employees=len(slips),
            total_gross_pay=total_gross,
            total_deductions=total_deductions,
            total_net_pay=total_net,
            by_department=by_dept,
        )

    # ==========================================================================
    # Private Helpers
    # ==========================================================================

    def _get_eligible_employees(self, entry: PayrollEntry) -> List[Employee]:
        """Get employees eligible for a payroll entry."""
        from app.models.employee import EmploymentStatus

        query = select(Employee).where(
            Employee.status == EmploymentStatus.ACTIVE
        )

        if entry.company:
            query = query.where(Employee.company == entry.company)
        if entry.department:
            query = query.where(Employee.department == entry.department)
        if entry.designation:
            query = query.where(Employee.designation == entry.designation)

        return list(self.db.scalars(query).all())

    def _calculate_working_days(
        self, employee_id: int, start_date: date, end_date: date, company: Optional[str] = None
    ) -> tuple[Decimal, Decimal, Decimal]:
        """Calculate working days, absent days, and LWP for a period.

        Uses HR settings for:
        - work_week_days: Which days of the week are working days
        """
        from app.models.hr_attendance import Attendance, AttendanceStatus
        from app.models.hr_leave import LeaveApplication, LeaveApplicationStatus
        from datetime import timedelta

        # Get settings for work week days
        settings = self._get_settings(company)

        # Convert work_week_days from settings to weekday numbers
        work_weekdays = {
            WEEKDAY_MAP[day.upper()]
            for day in settings.work_week_days
            if day.upper() in WEEKDAY_MAP
        }

        # Count working days based on settings
        total_days = Decimal("0")
        current = start_date
        while current <= end_date:
            if current.weekday() in work_weekdays:
                total_days += 1
            current += timedelta(days=1)

        # Count absences
        absent_count = self.db.scalar(
            select(func.count(Attendance.id)).where(
                and_(
                    Attendance.employee_id == employee_id,
                    Attendance.attendance_date >= start_date,
                    Attendance.attendance_date <= end_date,
                    Attendance.status == AttendanceStatus.ABSENT,
                )
            )
        ) or 0

        # Count LWP
        lwp_count = self.db.scalar(
            select(func.sum(LeaveApplication.total_leave_days)).where(
                and_(
                    LeaveApplication.employee_id == employee_id,
                    LeaveApplication.status == LeaveApplicationStatus.APPROVED,
                    LeaveApplication.from_date <= end_date,
                    LeaveApplication.to_date >= start_date,
                )
            )
        ) or Decimal("0")

        return (total_days, Decimal(str(absent_count)), lwp_count)

    def _evaluate_formula(
        self, formula: str, **variables: Decimal
    ) -> Decimal:
        """Evaluate a simple formula with variables safely.

        Supports basic arithmetic operations: +, -, *, /, (, )
        Variables are substituted before evaluation.

        Args:
            formula: Expression string like "base * 0.1" or "(base + variable) * 0.05"
            **variables: Variable values to substitute (base, variable, gross_pay, etc.)

        Returns:
            Calculated result as Decimal, or Decimal("0") on error.
        """
        # Supported operators for safe evaluation
        SAFE_OPERATORS = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }

        def safe_eval_node(node: ast.AST) -> Decimal:
            """Recursively evaluate AST node with only safe operations."""
            if isinstance(node, ast.Expression):
                return safe_eval_node(node.body)
            elif isinstance(node, ast.Constant):
                # Python 3.8+ uses ast.Constant for numbers
                if isinstance(node.value, (int, float, Decimal)):
                    return Decimal(str(node.value))
                raise ValueError(f"Unsupported constant type: {type(node.value)}")
            elif isinstance(node, ast.Num):
                # Python 3.7 compatibility
                return Decimal(str(node.n))
            elif isinstance(node, ast.BinOp):
                left = safe_eval_node(node.left)
                right = safe_eval_node(node.right)
                op_func = SAFE_OPERATORS.get(type(node.op))
                if op_func is None:
                    raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
                return Decimal(str(op_func(left, right)))
            elif isinstance(node, ast.UnaryOp):
                operand = safe_eval_node(node.operand)
                op_func = SAFE_OPERATORS.get(type(node.op))
                if op_func is None:
                    raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
                return Decimal(str(op_func(operand)))
            else:
                raise ValueError(f"Unsupported AST node: {type(node).__name__}")

        try:
            # Substitute variable names with their values
            expr = formula
            # Sort by length descending to avoid partial replacements
            # e.g., replace "gross_pay" before "gross"
            for name in sorted(variables.keys(), key=len, reverse=True):
                value = variables[name]
                expr = expr.replace(name, str(value))

            # Parse and safely evaluate
            tree = ast.parse(expr, mode='eval')
            result = safe_eval_node(tree)
            return result.quantize(Decimal("0.01"))
        except Exception:
            return Decimal("0")

    # ==========================================================================
    # Enhanced Payroll Generation with Nigerian Tax Compliance
    # ==========================================================================

    def generate_salary_slips_with_tax(
        self, payroll_entry_id: int
    ) -> "SlipGenerationDetailResult":
        """Generate salary slips with Nigerian tax compliance.

        This enhanced version:
        - Calculates PAYE, Pension, NHF, NHIS based on Nigerian tax law
        - Respects employment type eligibility (INTERN, NYSC exempt from some deductions)
        - Returns detailed results with tax breakdown

        Args:
            payroll_entry_id: The payroll entry to generate slips for.

        Returns:
            SlipGenerationDetailResult with created/skipped details.

        Raises:
            PayrollEntryNotFoundError: If payroll entry doesn't exist.
            PayrollAlreadyProcessedError: If slips already generated.
        """
        from app.feature_flags import feature_flags
        from app.services.hr.payroll_types import (
            CreatedSlipDetail,
            SkippedSlipDetail,
            SlipGenerationDetailResult,
        )

        entry = self.get_payroll_entry(payroll_entry_id)

        if entry.salary_slips_created:
            raise PayrollAlreadyProcessedError(
                payroll_entry_id, "Salary slips already created"
            )

        result = SlipGenerationDetailResult(payroll_entry_id=payroll_entry_id)

        # Get eligible assignments
        assignments = self._get_eligible_assignments(entry)

        for assignment in assignments:
            try:
                detail = self._create_slip_with_tax(entry, assignment)
                if detail:
                    result.created_details.append(detail)
                    result.created_count += 1
            except Exception as e:
                result.skipped_details.append(SkippedSlipDetail(
                    employee_id=assignment.employee_id or 0,
                    employee=assignment.employee or "",
                    reason=str(e),
                ))
                result.skipped_count += 1

        # Mark entry as having slips created
        entry.salary_slips_created = True
        if self.principal and self.principal.user_id:
            entry.updated_by_id = self.principal.user_id

        self.db.flush()
        return result

    def _get_eligible_assignments(
        self, entry: PayrollEntry
    ) -> List[SalaryStructureAssignment]:
        """Get eligible salary structure assignments for a payroll entry."""
        query = select(SalaryStructureAssignment).where(
            SalaryStructureAssignment.from_date <= entry.end_date
        )

        if entry.company:
            query = query.where(SalaryStructureAssignment.company == entry.company)

        # Apply department/designation filters by joining with Employee
        if entry.department or entry.designation:
            query = query.join(
                Employee, SalaryStructureAssignment.employee_id == Employee.id
            )
            if entry.department:
                query = query.where(Employee.department == entry.department)
            if entry.designation:
                query = query.where(Employee.designation == entry.designation)

        all_assignments = list(self.db.scalars(query))

        # Filter to only the most recent assignment per employee
        employee_assignments: dict[int, SalaryStructureAssignment] = {}
        for assignment in all_assignments:
            if assignment.employee_id is None:
                continue
            existing = employee_assignments.get(assignment.employee_id)
            if existing is None or (
                assignment.from_date
                and existing.from_date
                and assignment.from_date > existing.from_date
            ):
                employee_assignments[assignment.employee_id] = assignment

        return list(employee_assignments.values())

    def _create_slip_with_tax(
        self, entry: PayrollEntry, assignment: SalaryStructureAssignment
    ) -> Optional["CreatedSlipDetail"]:
        """Create a single salary slip with tax calculations."""
        from app.feature_flags import feature_flags
        from app.services.hr.payroll_types import CreatedSlipDetail

        # Check if slip already exists
        existing = self.db.scalar(
            select(SalarySlip).where(
                and_(
                    SalarySlip.employee_id == assignment.employee_id,
                    SalarySlip.start_date == entry.start_date,
                    SalarySlip.end_date == entry.end_date,
                )
            )
        )
        if existing:
            raise ValueError("Salary slip already exists")

        # Get salary structure
        if not assignment.salary_structure_id:
            raise ValueError("No salary structure assigned")

        structure = self.get_salary_structure(assignment.salary_structure_id)

        # Calculate earnings and categorize for tax
        gross_pay = Decimal("0")
        basic_salary = Decimal("0")
        housing_allowance = Decimal("0")
        transport_allowance = Decimal("0")
        other_allowances = Decimal("0")

        for earning in structure.earnings:
            if earning.statistical_component or earning.do_not_include_in_total:
                continue
            amount = earning.amount or Decimal("0")
            gross_pay += amount
            comp_name = (earning.salary_component or "").lower()

            if "basic" in comp_name:
                basic_salary += amount
            elif "housing" in comp_name:
                housing_allowance += amount
            elif "transport" in comp_name:
                transport_allowance += amount
            else:
                other_allowances += amount

        # Use base from assignment if no basic component
        if basic_salary == Decimal("0") and assignment.base:
            basic_salary = assignment.base

        # Get employee info for tax eligibility
        employee = self.db.get(Employee, assignment.employee_id)
        employment_type = None
        months_of_service = None

        if employee:
            if hasattr(employee, "employment_type_enum") and employee.employment_type_enum:
                employment_type = (
                    employee.employment_type_enum.value
                    if hasattr(employee.employment_type_enum, "value")
                    else str(employee.employment_type_enum)
                )
            else:
                employment_type = employee.employment_type

            if employee.date_of_joining:
                today = entry.posting_date or date.today()
                doj = (
                    employee.date_of_joining.date()
                    if hasattr(employee.date_of_joining, "date")
                    else employee.date_of_joining
                )
                delta = today - doj
                months_of_service = delta.days // 30

        # Calculate statutory deductions
        if feature_flags.NIGERIA_COMPLIANCE_ENABLED:
            from app.api.tax.payroll_integration import (
                calculate_slip_deductions,
                STATUTORY_COMPONENTS,
            )

            statutory = calculate_slip_deductions(
                basic_salary=basic_salary,
                housing_allowance=housing_allowance,
                transport_allowance=transport_allowance,
                other_allowances=other_allowances,
                employment_type=employment_type,
                months_of_service=months_of_service,
                db=self.db,
                payroll_date=entry.posting_date,
            )
        else:
            statutory = {
                "paye": Decimal("0"),
                "pension_employee": Decimal("0"),
                "pension_employer": Decimal("0"),
                "nhf": Decimal("0"),
                "nhis_employee": Decimal("0"),
                "nhis_employer": Decimal("0"),
                "total_employee_deductions": Decimal("0"),
                "total_employer_contributions": Decimal("0"),
                "is_paye_exempt": True,
            }
            STATUTORY_COMPONENTS = {
                "PAYE": {"name": "PAYE", "abbr": "PAYE"},
                "PENSION_EMPLOYEE": {"name": "Pension (Employee)", "abbr": "PEN-E"},
                "NHF": {"name": "NHF", "abbr": "NHF"},
                "NHIS_EMPLOYEE": {"name": "NHIS (Employee)", "abbr": "NHIS-E"},
            }

        # Sum non-statutory deductions
        structure_deductions = Decimal("0")
        for deduction in structure.deductions:
            if deduction.statistical_component or deduction.do_not_include_in_total:
                continue
            comp_name = (deduction.salary_component or "").lower()
            if any(x in comp_name for x in ["paye", "pension", "nhf", "nhis"]):
                continue
            structure_deductions += deduction.amount or Decimal("0")

        total_deduction = statutory["total_employee_deductions"] + structure_deductions
        net_pay = gross_pay - total_deduction

        # Create salary slip
        slip = SalarySlip(
            employee=assignment.employee,
            employee_id=assignment.employee_id,
            employee_name=assignment.employee_name,
            salary_structure=structure.salary_structure_name,
            posting_date=entry.posting_date,
            start_date=entry.start_date,
            end_date=entry.end_date,
            payroll_frequency=structure.payroll_frequency,
            company=entry.company or structure.company,
            currency=entry.currency or structure.currency,
            gross_pay=gross_pay,
            total_deduction=total_deduction,
            net_pay=net_pay,
            rounded_total=net_pay,
            status=SalarySlipStatus.DRAFT,
            payroll_entry=entry.erpnext_id or f"PAYROLL-{entry.id}",
        )
        if self.principal and self.principal.user_id:
            slip.created_by_id = self.principal.user_id

        self.db.add(slip)
        self.db.flush()

        # Add earnings
        for idx, earning in enumerate(structure.earnings):
            self.db.add(
                SalarySlipEarning(
                    salary_slip_id=slip.id,
                    salary_component=earning.salary_component,
                    abbr=earning.abbr,
                    amount=earning.amount or Decimal("0"),
                    default_amount=earning.amount or Decimal("0"),
                    statistical_component=earning.statistical_component,
                    do_not_include_in_total=earning.do_not_include_in_total,
                    idx=idx,
                )
            )

        # Add statutory deductions
        deduction_idx = 0
        if statutory["paye"] > Decimal("0"):
            self.db.add(
                SalarySlipDeduction(
                    salary_slip_id=slip.id,
                    salary_component=STATUTORY_COMPONENTS["PAYE"]["name"],
                    abbr=STATUTORY_COMPONENTS["PAYE"]["abbr"],
                    amount=statutory["paye"],
                    default_amount=statutory["paye"],
                    idx=deduction_idx,
                )
            )
            deduction_idx += 1

        if statutory["pension_employee"] > Decimal("0"):
            self.db.add(
                SalarySlipDeduction(
                    salary_slip_id=slip.id,
                    salary_component=STATUTORY_COMPONENTS["PENSION_EMPLOYEE"]["name"],
                    abbr=STATUTORY_COMPONENTS["PENSION_EMPLOYEE"]["abbr"],
                    amount=statutory["pension_employee"],
                    default_amount=statutory["pension_employee"],
                    idx=deduction_idx,
                )
            )
            deduction_idx += 1

        if statutory["nhf"] > Decimal("0"):
            self.db.add(
                SalarySlipDeduction(
                    salary_slip_id=slip.id,
                    salary_component=STATUTORY_COMPONENTS["NHF"]["name"],
                    abbr=STATUTORY_COMPONENTS["NHF"]["abbr"],
                    amount=statutory["nhf"],
                    default_amount=statutory["nhf"],
                    idx=deduction_idx,
                )
            )
            deduction_idx += 1

        if statutory["nhis_employee"] > Decimal("0"):
            self.db.add(
                SalarySlipDeduction(
                    salary_slip_id=slip.id,
                    salary_component=STATUTORY_COMPONENTS["NHIS_EMPLOYEE"]["name"],
                    abbr=STATUTORY_COMPONENTS["NHIS_EMPLOYEE"]["abbr"],
                    amount=statutory["nhis_employee"],
                    default_amount=statutory["nhis_employee"],
                    idx=deduction_idx,
                )
            )
            deduction_idx += 1

        # Add non-statutory deductions
        for deduction in structure.deductions:
            comp_name = (deduction.salary_component or "").lower()
            if any(x in comp_name for x in ["paye", "pension", "nhf", "nhis"]):
                continue
            self.db.add(
                SalarySlipDeduction(
                    salary_slip_id=slip.id,
                    salary_component=deduction.salary_component,
                    abbr=deduction.abbr,
                    amount=deduction.amount or Decimal("0"),
                    default_amount=deduction.amount or Decimal("0"),
                    statistical_component=deduction.statistical_component,
                    do_not_include_in_total=deduction.do_not_include_in_total,
                    idx=deduction_idx,
                )
            )
            deduction_idx += 1

        self.db.flush()

        return CreatedSlipDetail(
            id=slip.id,
            employee=assignment.employee or "",
            employee_id=assignment.employee_id or 0,
            gross_pay=gross_pay,
            net_pay=net_pay,
            paye=statutory["paye"],
            pension=statutory["pension_employee"],
            is_paye_exempt=statutory.get("is_paye_exempt", False),
        )

    def regenerate_salary_slips(
        self, payroll_entry_id: int
    ) -> "SlipGenerationDetailResult":
        """Delete draft slips and regenerate for a payroll entry.

        Only draft slips are deleted; submitted/paid slips are preserved.
        """
        from app.services.hr.payroll_types import SlipGenerationDetailResult

        entry = self.get_payroll_entry(payroll_entry_id)

        # Delete only draft slips for this entry
        payroll_ref = entry.erpnext_id or f"PAYROLL-{entry.id}"
        deleted_count = self.db.execute(
            delete(SalarySlip).where(
                and_(
                    SalarySlip.payroll_entry == payroll_ref,
                    SalarySlip.status == SalarySlipStatus.DRAFT,
                )
            )
        ).rowcount

        # Reset the flag to allow regeneration
        entry.salary_slips_created = False
        self.db.flush()

        # Regenerate slips
        result = self.generate_salary_slips_with_tax(payroll_entry_id)
        result.deleted_drafts = deleted_count

        return result

    def get_payable_slips(
        self, payroll_entry_id: int, slip_ids: List[int]
    ) -> List[SalarySlip]:
        """Get salary slips that are payable for a payroll entry.

        Validates that slips:
        - Exist
        - Belong to the payroll entry
        - Are in a payable status (DRAFT or SUBMITTED)
        - Have a positive net_pay amount
        """
        entry = self.get_payroll_entry(payroll_entry_id)
        payroll_ref = entry.erpnext_id or f"PAYROLL-{entry.id}"

        slips = list(
            self.db.scalars(
                select(SalarySlip).where(SalarySlip.id.in_(slip_ids))
            )
        )

        # Validate all slips
        slip_map = {s.id: s for s in slips}
        missing = [sid for sid in slip_ids if sid not in slip_map]
        if missing:
            raise SalarySlipNotFoundError(missing[0])

        payable = []
        for slip in slips:
            if slip.payroll_entry != payroll_ref:
                raise ValueError(
                    f"Slip {slip.id} does not belong to payroll entry {payroll_entry_id}"
                )
            if slip.status not in (SalarySlipStatus.SUBMITTED, SalarySlipStatus.DRAFT):
                raise SlipStatusTransitionError(
                    slip.id, slip.status.value, "payout"
                )
            if not slip.net_pay or slip.net_pay <= 0:
                raise ValueError(f"Slip {slip.id} has no payable amount")
            payable.append(slip)

        return payable

    def mark_slips_paid_by_transfer(
        self,
        slip_ids: List[int],
        references: dict[int, str],
    ) -> None:
        """Mark salary slips as paid with transfer references.

        Args:
            slip_ids: List of slip IDs that were paid.
            references: Mapping of slip_id to payment reference.
        """
        for slip_id in slip_ids:
            slip = self.get_salary_slip(slip_id)
            slip.status = SalarySlipStatus.PAID
            slip.payment_reference = references.get(slip_id)
            slip.payment_mode = "bank_transfer"
            slip.paid_at = utc_now()
            if self.principal and self.principal.user_id:
                slip.paid_by_id = self.principal.user_id

        self.db.flush()
