"""HR sync functions for ERPNext.

This module handles syncing of HR-related entities:
- Employees
- Departments
- Designations
- ERPNext Users
- HD Teams and Members
- Employee relationship resolution
"""
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, Optional

import httpx
import structlog

from app.models.employee import Employee, EmploymentStatus
from app.models.hr import Department, Designation, ERPNextUser, HDTeam, HDTeamMember
from app.models.hr_attendance import Attendance, AttendanceStatus
from app.models.hr_leave import (
    LeaveAllocation,
    LeaveAllocationStatus,
    LeaveApplication,
    LeaveApplicationStatus,
    LeaveType,
)
from app.models.hr_payroll import (
    PayrollEntry,
    SalaryComponent,
    SalaryComponentType,
    SalarySlip,
    SalarySlipDeduction,
    SalarySlipEarning,
    SalarySlipStatus,
    SalaryStructure,
    SalaryStructureDeduction,
    SalaryStructureEarning,
)
from app.models.sales import SalesPerson

if TYPE_CHECKING:
    from app.sync.erpnext import ERPNextSync

logger = structlog.get_logger()


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _parse_date(value: Any) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return datetime.fromisoformat(str(value)).date()
    except (ValueError, TypeError):
        return None


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _parse_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    try:
        return Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError):
        return default


def _map_salary_component_type(value: Any) -> SalaryComponentType:
    if value and "deduction" in str(value).strip().lower():
        return SalaryComponentType.DEDUCTION
    return SalaryComponentType.EARNING


def _map_salary_slip_status(value: Any, docstatus: Any) -> SalarySlipStatus:
    if value:
        key = str(value).strip().lower()
        mapping = {
            "draft": SalarySlipStatus.DRAFT,
            "submitted": SalarySlipStatus.SUBMITTED,
            "cancelled": SalarySlipStatus.CANCELLED,
            "canceled": SalarySlipStatus.CANCELLED,
            "paid": SalarySlipStatus.PAID,
            "void": SalarySlipStatus.VOIDED,
            "voided": SalarySlipStatus.VOIDED,
        }
        if key in mapping:
            return mapping[key]
    if str(docstatus) == "2":
        return SalarySlipStatus.CANCELLED
    if str(docstatus) == "1":
        return SalarySlipStatus.SUBMITTED
    return SalarySlipStatus.DRAFT


def _map_leave_allocation_status(value: Any, docstatus: Any) -> LeaveAllocationStatus:
    if value:
        key = str(value).strip().lower()
        mapping = {
            "draft": LeaveAllocationStatus.DRAFT,
            "submitted": LeaveAllocationStatus.SUBMITTED,
            "open": LeaveAllocationStatus.SUBMITTED,
            "cancelled": LeaveAllocationStatus.CANCELLED,
            "canceled": LeaveAllocationStatus.CANCELLED,
        }
        if key in mapping:
            return mapping[key]
    if str(docstatus) == "2":
        return LeaveAllocationStatus.CANCELLED
    if str(docstatus) == "1":
        return LeaveAllocationStatus.SUBMITTED
    return LeaveAllocationStatus.DRAFT


def _map_leave_application_status(value: Any, docstatus: Any) -> LeaveApplicationStatus:
    if value:
        key = str(value).strip().lower()
        mapping = {
            "open": LeaveApplicationStatus.OPEN,
            "approved": LeaveApplicationStatus.APPROVED,
            "rejected": LeaveApplicationStatus.REJECTED,
            "cancelled": LeaveApplicationStatus.CANCELLED,
            "canceled": LeaveApplicationStatus.CANCELLED,
        }
        if key in mapping:
            return mapping[key]
    if str(docstatus) == "2":
        return LeaveApplicationStatus.CANCELLED
    if str(docstatus) == "1":
        return LeaveApplicationStatus.APPROVED
    return LeaveApplicationStatus.OPEN


def _map_attendance_status(value: Any) -> AttendanceStatus:
    if not value:
        return AttendanceStatus.PRESENT
    key = str(value).strip().lower().replace(" ", "_")
    mapping = {
        "present": AttendanceStatus.PRESENT,
        "absent": AttendanceStatus.ABSENT,
        "on_leave": AttendanceStatus.ON_LEAVE,
        "half_day": AttendanceStatus.HALF_DAY,
        "work_from_home": AttendanceStatus.WORK_FROM_HOME,
    }
    return mapping.get(key, AttendanceStatus.PRESENT)


async def sync_employees(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync employees from ERPNext."""
    sync_client.start_sync("employees", "full" if full_sync else "incremental")

    try:
        filters = sync_client._get_incremental_filter("employees", full_sync)

        employees = await sync_client._fetch_all_doctype(
            client,
            "Employee",
            fields=[
                "name", "employee_name", "company_email", "cell_number",
                "designation", "department", "reports_to", "status",
                "employment_type", "date_of_joining", "relieving_date", "modified",
            ],
            filters=filters,
        )

        for emp_data in employees:
            erpnext_id = emp_data.get("name")
            existing = sync_client.db.query(Employee).filter(
                Employee.erpnext_id == erpnext_id
            ).first()

            # Map status
            status_str = (emp_data.get("status", "") or "").lower()
            status_map = {
                "active": EmploymentStatus.ACTIVE,
                "inactive": EmploymentStatus.INACTIVE,
                "left": EmploymentStatus.TERMINATED,
                "on_leave": EmploymentStatus.ON_LEAVE,
            }
            status = status_map.get(status_str, EmploymentStatus.ACTIVE)

            if existing:
                existing.name = emp_data.get("employee_name", "")
                existing.email = emp_data.get("company_email")
                existing.phone = emp_data.get("cell_number")
                existing.designation = emp_data.get("designation")
                existing.department = emp_data.get("department")
                existing.reports_to = emp_data.get("reports_to")
                existing.status = status
                existing.employment_type = emp_data.get("employment_type")
                existing.last_synced_at = datetime.utcnow()

                if emp_data.get("date_of_joining"):
                    try:
                        existing.date_of_joining = datetime.fromisoformat(emp_data["date_of_joining"]).date()
                    except (ValueError, TypeError):
                        pass

                if emp_data.get("relieving_date"):
                    try:
                        existing.date_of_leaving = datetime.fromisoformat(emp_data["relieving_date"]).date()
                    except (ValueError, TypeError):
                        pass

                sync_client.increment_updated()
            else:
                employee = Employee(
                    erpnext_id=erpnext_id,
                    name=emp_data.get("employee_name", ""),
                    email=emp_data.get("company_email"),
                    phone=emp_data.get("cell_number"),
                    designation=emp_data.get("designation"),
                    department=emp_data.get("department"),
                    reports_to=emp_data.get("reports_to"),
                    status=status,
                    employment_type=emp_data.get("employment_type"),
                )

                if emp_data.get("date_of_joining"):
                    try:
                        employee.date_of_joining = datetime.fromisoformat(emp_data["date_of_joining"]).date()
                    except (ValueError, TypeError):
                        pass

                if emp_data.get("relieving_date"):
                    try:
                        employee.date_of_leaving = datetime.fromisoformat(emp_data["relieving_date"]).date()
                    except (ValueError, TypeError):
                        pass

                sync_client.db.add(employee)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client._update_sync_cursor("employees", employees, len(employees))
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_departments(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync departments from ERPNext HR module."""
    sync_client.start_sync("erpnext_departments", "full" if full_sync else "incremental")

    try:
        departments = await sync_client._fetch_all_doctype(
            client,
            "Department",
            fields=["*"],
        )

        for dept_data in departments:
            erpnext_id = dept_data.get("name")
            existing = sync_client.db.query(Department).filter(
                Department.erpnext_id == erpnext_id
            ).first()

            if existing:
                existing.department_name = dept_data.get("department_name") or str(erpnext_id or "")
                existing.parent_department = dept_data.get("parent_department")
                existing.company = dept_data.get("company")
                existing.is_group = dept_data.get("is_group", 0) == 1
                existing.lft = dept_data.get("lft")
                existing.rgt = dept_data.get("rgt")
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                department = Department(
                    erpnext_id=erpnext_id,
                    department_name=dept_data.get("department_name") or str(erpnext_id or ""),
                    parent_department=dept_data.get("parent_department"),
                    company=dept_data.get("company"),
                    is_group=dept_data.get("is_group", 0) == 1,
                    lft=dept_data.get("lft"),
                    rgt=dept_data.get("rgt"),
                )
                sync_client.db.add(department)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_designations(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync job designations from ERPNext."""
    sync_client.start_sync("erpnext_designations", "full" if full_sync else "incremental")

    try:
        designations = await sync_client._fetch_all_doctype(
            client,
            "Designation",
            fields=["*"],
        )

        for desig_data in designations:
            erpnext_id = desig_data.get("name")
            existing = sync_client.db.query(Designation).filter(
                Designation.erpnext_id == erpnext_id
            ).first()

            if existing:
                existing.designation_name = desig_data.get("designation_name") or str(erpnext_id or "")
                existing.description = desig_data.get("description")
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                designation = Designation(
                    erpnext_id=erpnext_id,
                    designation_name=desig_data.get("designation_name") or str(erpnext_id or ""),
                    description=desig_data.get("description"),
                )
                sync_client.db.add(designation)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_erpnext_users(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync ERPNext system users."""
    sync_client.start_sync("erpnext_users", "full" if full_sync else "incremental")

    try:
        users = await sync_client._fetch_all_doctype(
            client,
            "User",
            fields=["name", "email", "full_name", "first_name", "last_name", "enabled", "user_type"],
        )

        for user_data in users:
            email = user_data.get("email") or user_data.get("name")
            if not email:
                continue

            existing = sync_client.db.query(ERPNextUser).filter(
                ERPNextUser.email == email
            ).first()

            # Try to find linked employee by email
            employee_id = None
            employee = sync_client.db.query(Employee).filter(
                Employee.email == email
            ).first()
            if employee:
                employee_id = employee.id

            if existing:
                existing.erpnext_id = user_data.get("name")
                existing.full_name = user_data.get("full_name")
                existing.first_name = user_data.get("first_name")
                existing.last_name = user_data.get("last_name")
                existing.enabled = user_data.get("enabled", 1) == 1
                existing.user_type = user_data.get("user_type")
                existing.employee_id = employee_id
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                erpnext_user = ERPNextUser(
                    erpnext_id=user_data.get("name"),
                    email=email,
                    full_name=user_data.get("full_name"),
                    first_name=user_data.get("first_name"),
                    last_name=user_data.get("last_name"),
                    enabled=user_data.get("enabled", 1) == 1,
                    user_type=user_data.get("user_type"),
                    employee_id=employee_id,
                )
                sync_client.db.add(erpnext_user)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_hd_teams(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync helpdesk teams and their members from ERPNext."""
    sync_client.start_sync("erpnext_hd_teams", "full" if full_sync else "incremental")

    try:
        teams = await sync_client._fetch_all_doctype(
            client,
            "HD Team",
            fields=["*"],
        )

        for team_data in teams:
            erpnext_id = team_data.get("name")
            existing = sync_client.db.query(HDTeam).filter(
                HDTeam.erpnext_id == erpnext_id
            ).first()

            if existing:
                existing.team_name = team_data.get("team_name") or str(erpnext_id or "")
                existing.description = team_data.get("description")
                existing.assignment_rule = team_data.get("assignment_rule")
                existing.ignore_restrictions = team_data.get("ignore_restrictions", 0) == 1
                existing.last_synced_at = datetime.utcnow()
                team = existing
                sync_client.increment_updated()
            else:
                team = HDTeam(
                    erpnext_id=erpnext_id,
                    team_name=team_data.get("team_name") or str(erpnext_id or ""),
                    description=team_data.get("description"),
                    assignment_rule=team_data.get("assignment_rule"),
                    ignore_restrictions=team_data.get("ignore_restrictions", 0) == 1,
                )
                sync_client.db.add(team)
                sync_client.db.flush()
                sync_client.increment_created()

            # Sync team members
            try:
                if not erpnext_id:
                    continue
                team_doc = await sync_client._fetch_document(client, "HD Team", str(erpnext_id))
                members_data = team_doc.get("users", [])

                # Clear existing members for this team
                sync_client.db.query(HDTeamMember).filter(
                    HDTeamMember.team_id == team.id
                ).delete()

                for member_data in members_data:
                    user_email = member_data.get("user")
                    if not user_email:
                        continue

                    # Try to find linked employee by email
                    employee_id = None
                    employee = sync_client.db.query(Employee).filter(
                        Employee.email == user_email
                    ).first()
                    if employee:
                        employee_id = employee.id

                    member = HDTeamMember(
                        team_id=team.id,
                        user=user_email,
                        user_name=member_data.get("user_name"),
                        employee_id=employee_id,
                    )
                    sync_client.db.add(member)
            except Exception as e:
                logger.warning(f"Could not fetch members for HD Team {erpnext_id}: {e}")

        sync_client.db.commit()
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_salary_components(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync salary components from ERPNext."""
    sync_client.start_sync("salary_components", "full" if full_sync else "incremental")

    try:
        filters = sync_client._get_incremental_filter("salary_components", full_sync)
        components = await sync_client._fetch_all_doctype(
            client,
            "Salary Component",
            fields=[
                "name",
                "salary_component",
                "salary_component_abbr",
                "type",
                "description",
                "is_tax_applicable",
                "is_flexible_benefit",
                "depends_on_payment_days",
                "variable_based_on_taxable_salary",
                "exempted_from_income_tax",
                "statistical_component",
                "do_not_include_in_total",
                "disabled",
                "modified",
            ],
            filters=filters,
        )

        for comp_data in components:
            erpnext_id = comp_data.get("name")
            salary_component_name = (
                comp_data.get("salary_component")
                or comp_data.get("salary_component_name")
                or erpnext_id
                or ""
            )
            if not salary_component_name:
                continue
            existing = None
            if erpnext_id:
                existing = sync_client.db.query(SalaryComponent).filter(
                    SalaryComponent.erpnext_id == erpnext_id
                ).first()
            if not existing and salary_component_name:
                existing = sync_client.db.query(SalaryComponent).filter(
                    SalaryComponent.salary_component_name == salary_component_name
                ).first()

            component_type = _map_salary_component_type(comp_data.get("type"))
            salary_component_abbr = comp_data.get("salary_component_abbr") or comp_data.get("abbr")

            if existing:
                existing.erpnext_id = erpnext_id
                existing.salary_component_name = salary_component_name
                existing.salary_component_abbr = salary_component_abbr
                existing.type = component_type
                existing.description = comp_data.get("description")
                existing.is_tax_applicable = _coerce_bool(comp_data.get("is_tax_applicable"))
                existing.is_payable = _coerce_bool(comp_data.get("is_payable", True))
                existing.is_flexible_benefit = _coerce_bool(comp_data.get("is_flexible_benefit"))
                existing.depends_on_payment_days = _coerce_bool(comp_data.get("depends_on_payment_days", True))
                existing.variable_based_on_taxable_salary = _coerce_bool(
                    comp_data.get("variable_based_on_taxable_salary")
                )
                existing.exempted_from_income_tax = _coerce_bool(comp_data.get("exempted_from_income_tax"))
                existing.statistical_component = _coerce_bool(comp_data.get("statistical_component"))
                existing.do_not_include_in_total = _coerce_bool(comp_data.get("do_not_include_in_total"))
                existing.disabled = _coerce_bool(comp_data.get("disabled"))
                existing.default_account = comp_data.get("default_account")
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                component = SalaryComponent(
                    erpnext_id=erpnext_id,
                    salary_component_name=salary_component_name,
                    salary_component_abbr=salary_component_abbr,
                    type=component_type,
                    description=comp_data.get("description"),
                    is_tax_applicable=_coerce_bool(comp_data.get("is_tax_applicable")),
                    is_payable=_coerce_bool(comp_data.get("is_payable", True)),
                    is_flexible_benefit=_coerce_bool(comp_data.get("is_flexible_benefit")),
                    depends_on_payment_days=_coerce_bool(comp_data.get("depends_on_payment_days", True)),
                    variable_based_on_taxable_salary=_coerce_bool(
                        comp_data.get("variable_based_on_taxable_salary")
                    ),
                    exempted_from_income_tax=_coerce_bool(comp_data.get("exempted_from_income_tax")),
                    statistical_component=_coerce_bool(comp_data.get("statistical_component")),
                    do_not_include_in_total=_coerce_bool(comp_data.get("do_not_include_in_total")),
                    disabled=_coerce_bool(comp_data.get("disabled")),
                    default_account=comp_data.get("default_account"),
                )
                sync_client.db.add(component)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client._update_sync_cursor("salary_components", components, len(components))
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_salary_structures(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync salary structures and child rows from ERPNext."""
    sync_client.start_sync("salary_structures", "full" if full_sync else "incremental")

    try:
        filters = sync_client._get_incremental_filter("salary_structures", full_sync)
        structures = await sync_client._fetch_all_doctype(
            client,
            "Salary Structure",
            fields=[
                "name",
                "company",
                "is_active",
                "payroll_frequency",
                "currency",
                "payment_account",
                "mode_of_payment",
                "modified",
            ],
            filters=filters,
        )

        for structure_data in structures:
            erpnext_id = structure_data.get("name")
            salary_structure_name = structure_data.get("salary_structure_name") or erpnext_id or ""
            if not salary_structure_name:
                continue
            existing = None
            if erpnext_id:
                existing = sync_client.db.query(SalaryStructure).filter(
                    SalaryStructure.erpnext_id == erpnext_id
                ).first()
            if not existing and salary_structure_name:
                existing = sync_client.db.query(SalaryStructure).filter(
                    SalaryStructure.salary_structure_name == salary_structure_name
                ).first()

            is_active_raw = structure_data.get("is_active")
            if is_active_raw is None:
                is_active_value = "Yes"
            else:
                is_active_str = str(is_active_raw).strip().lower()
                if is_active_str in {"yes", "no"}:
                    is_active_value = "Yes" if is_active_str == "yes" else "No"
                else:
                    is_active_value = "Yes" if _coerce_bool(is_active_raw) else "No"

            if existing:
                existing.erpnext_id = erpnext_id
                existing.salary_structure_name = salary_structure_name
                existing.company = structure_data.get("company")
                existing.is_active = is_active_value
                existing.payroll_frequency = structure_data.get("payroll_frequency")
                existing.currency = structure_data.get("currency") or existing.currency
                existing.payment_account = structure_data.get("payment_account")
                existing.mode_of_payment = structure_data.get("mode_of_payment")
                existing.last_synced_at = datetime.utcnow()
                structure = existing
                sync_client.increment_updated()
            else:
                structure = SalaryStructure(
                    erpnext_id=erpnext_id,
                    salary_structure_name=salary_structure_name,
                    company=structure_data.get("company"),
                    is_active=is_active_value,
                    payroll_frequency=structure_data.get("payroll_frequency"),
                    currency=structure_data.get("currency") or "USD",
                    payment_account=structure_data.get("payment_account"),
                    mode_of_payment=structure_data.get("mode_of_payment"),
                )
                sync_client.db.add(structure)
                sync_client.db.flush()
                sync_client.increment_created()

            if not erpnext_id:
                continue

            try:
                structure_doc = await sync_client._fetch_document(client, "Salary Structure", str(erpnext_id))
                earnings = structure_doc.get("earnings", [])
                deductions = structure_doc.get("deductions", [])

                sync_client.db.query(SalaryStructureEarning).filter(
                    SalaryStructureEarning.salary_structure_id == structure.id
                ).delete()
                sync_client.db.query(SalaryStructureDeduction).filter(
                    SalaryStructureDeduction.salary_structure_id == structure.id
                ).delete()

                for row in earnings:
                    earning = SalaryStructureEarning(
                        salary_structure_id=structure.id,
                        erpnext_name=row.get("name"),
                        salary_component=row.get("salary_component") or "",
                        abbr=row.get("abbr"),
                        amount=_parse_decimal(row.get("amount")),
                        amount_based_on_formula=_coerce_bool(row.get("amount_based_on_formula")),
                        formula=row.get("formula"),
                        condition=row.get("condition"),
                        statistical_component=_coerce_bool(row.get("statistical_component")),
                        do_not_include_in_total=_coerce_bool(row.get("do_not_include_in_total")),
                        idx=int(row.get("idx") or 0),
                    )
                    sync_client.db.add(earning)

                for row in deductions:
                    deduction = SalaryStructureDeduction(
                        salary_structure_id=structure.id,
                        erpnext_name=row.get("name"),
                        salary_component=row.get("salary_component") or "",
                        abbr=row.get("abbr"),
                        amount=_parse_decimal(row.get("amount")),
                        amount_based_on_formula=_coerce_bool(row.get("amount_based_on_formula")),
                        formula=row.get("formula"),
                        condition=row.get("condition"),
                        statistical_component=_coerce_bool(row.get("statistical_component")),
                        do_not_include_in_total=_coerce_bool(row.get("do_not_include_in_total")),
                        idx=int(row.get("idx") or 0),
                    )
                    sync_client.db.add(deduction)
            except Exception as e:
                logger.warning("salary_structure_children_fetch_failed", structure=erpnext_id, error=str(e))

        sync_client.db.commit()
        sync_client._update_sync_cursor("salary_structures", structures, len(structures))
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_payroll_entries(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync payroll entries from ERPNext."""
    sync_client.start_sync("payroll_entries", "full" if full_sync else "incremental")

    try:
        filters = sync_client._get_incremental_filter("payroll_entries", full_sync)
        entries = await sync_client._fetch_all_doctype(
            client,
            "Payroll Entry",
            fields=[
                "name",
                "posting_date",
                "payroll_frequency",
                "start_date",
                "end_date",
                "company",
                "department",
                "branch",
                "designation",
                "currency",
                "exchange_rate",
                "payment_account",
                "bank_account",
                "salary_slips_created",
                "salary_slips_submitted",
                "docstatus",
                "modified",
            ],
            filters=filters,
        )

        for entry_data in entries:
            erpnext_id = entry_data.get("name")
            existing = None
            if erpnext_id:
                existing = sync_client.db.query(PayrollEntry).filter(
                    PayrollEntry.erpnext_id == erpnext_id
                ).first()

            posting_date = _parse_date(entry_data.get("posting_date"))
            start_date = _parse_date(entry_data.get("start_date"))
            end_date = _parse_date(entry_data.get("end_date"))

            if not posting_date or not start_date or not end_date:
                continue

            if existing:
                existing.posting_date = posting_date
                existing.payroll_frequency = entry_data.get("payroll_frequency")
                existing.start_date = start_date
                existing.end_date = end_date
                existing.company = entry_data.get("company")
                existing.department = entry_data.get("department")
                existing.branch = entry_data.get("branch")
                existing.designation = entry_data.get("designation")
                existing.currency = entry_data.get("currency") or existing.currency
                existing.exchange_rate = _parse_decimal(entry_data.get("exchange_rate"), Decimal("1"))
                existing.payment_account = entry_data.get("payment_account")
                existing.bank_account = entry_data.get("bank_account")
                existing.salary_slips_created = _coerce_bool(entry_data.get("salary_slips_created"))
                existing.salary_slips_submitted = _coerce_bool(entry_data.get("salary_slips_submitted"))
                existing.docstatus = int(entry_data.get("docstatus") or 0)
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                entry = PayrollEntry(
                    erpnext_id=erpnext_id,
                    posting_date=posting_date,
                    payroll_frequency=entry_data.get("payroll_frequency"),
                    start_date=start_date,
                    end_date=end_date,
                    company=entry_data.get("company"),
                    department=entry_data.get("department"),
                    branch=entry_data.get("branch"),
                    designation=entry_data.get("designation"),
                    currency=entry_data.get("currency") or "USD",
                    exchange_rate=_parse_decimal(entry_data.get("exchange_rate"), Decimal("1")),
                    payment_account=entry_data.get("payment_account"),
                    bank_account=entry_data.get("bank_account"),
                    salary_slips_created=_coerce_bool(entry_data.get("salary_slips_created")),
                    salary_slips_submitted=_coerce_bool(entry_data.get("salary_slips_submitted")),
                    docstatus=int(entry_data.get("docstatus") or 0),
                )
                sync_client.db.add(entry)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client._update_sync_cursor("payroll_entries", entries, len(entries))
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_salary_slips(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync salary slips and child rows from ERPNext."""
    sync_client.start_sync("salary_slips", "full" if full_sync else "incremental")

    try:
        filters = sync_client._get_incremental_filter("salary_slips", full_sync)
        slips = await sync_client._fetch_all_doctype(
            client,
            "Salary Slip",
            fields=[
                "name",
                "employee",
                "employee_name",
                "department",
                "designation",
                "branch",
                "salary_structure",
                "posting_date",
                "start_date",
                "end_date",
                "payroll_frequency",
                "company",
                "currency",
                "total_working_days",
                "absent_days",
                "payment_days",
                "leave_without_pay",
                "gross_pay",
                "total_deduction",
                "net_pay",
                "rounded_total",
                "status",
                "docstatus",
                "bank_name",
                "bank_account_no",
                "payroll_entry",
                "modified",
            ],
            filters=filters,
        )

        employees_by_erpnext_id: Dict[str, int] = {
            e.erpnext_id: e.id
            for e in sync_client.db.query(Employee).filter(Employee.erpnext_id.isnot(None)).all()
        }

        for slip_data in slips:
            erpnext_id = slip_data.get("name")
            existing = None
            if erpnext_id:
                existing = sync_client.db.query(SalarySlip).filter(
                    SalarySlip.erpnext_id == erpnext_id
                ).first()

            posting_date = _parse_date(slip_data.get("posting_date"))
            start_date = _parse_date(slip_data.get("start_date"))
            end_date = _parse_date(slip_data.get("end_date"))
            if not posting_date or not start_date or not end_date:
                continue

            employee_ref = slip_data.get("employee")
            employee_id = employees_by_erpnext_id.get(employee_ref) if employee_ref else None
            status = _map_salary_slip_status(slip_data.get("status"), slip_data.get("docstatus"))

            if existing:
                existing.employee = employee_ref or existing.employee
                existing.employee_id = employee_id
                existing.employee_name = slip_data.get("employee_name")
                existing.department = slip_data.get("department")
                existing.designation = slip_data.get("designation")
                existing.branch = slip_data.get("branch")
                existing.salary_structure = slip_data.get("salary_structure")
                existing.posting_date = posting_date
                existing.start_date = start_date
                existing.end_date = end_date
                existing.payroll_frequency = slip_data.get("payroll_frequency")
                existing.company = slip_data.get("company")
                existing.currency = slip_data.get("currency") or existing.currency
                existing.total_working_days = _parse_decimal(slip_data.get("total_working_days"))
                existing.absent_days = _parse_decimal(slip_data.get("absent_days"))
                existing.payment_days = _parse_decimal(slip_data.get("payment_days"))
                existing.leave_without_pay = _parse_decimal(slip_data.get("leave_without_pay"))
                existing.gross_pay = _parse_decimal(slip_data.get("gross_pay"))
                existing.total_deduction = _parse_decimal(slip_data.get("total_deduction"))
                existing.net_pay = _parse_decimal(slip_data.get("net_pay"))
                existing.rounded_total = _parse_decimal(slip_data.get("rounded_total"))
                existing.status = status
                existing.docstatus = int(slip_data.get("docstatus") or 0)
                existing.bank_name = slip_data.get("bank_name")
                existing.bank_account_no = slip_data.get("bank_account_no")
                existing.payroll_entry = slip_data.get("payroll_entry")
                existing.last_synced_at = datetime.utcnow()
                slip = existing
                sync_client.increment_updated()
            else:
                slip = SalarySlip(
                    erpnext_id=erpnext_id,
                    employee=employee_ref or "",
                    employee_id=employee_id,
                    employee_name=slip_data.get("employee_name"),
                    department=slip_data.get("department"),
                    designation=slip_data.get("designation"),
                    branch=slip_data.get("branch"),
                    salary_structure=slip_data.get("salary_structure"),
                    posting_date=posting_date,
                    start_date=start_date,
                    end_date=end_date,
                    payroll_frequency=slip_data.get("payroll_frequency"),
                    company=slip_data.get("company"),
                    currency=slip_data.get("currency") or "USD",
                    total_working_days=_parse_decimal(slip_data.get("total_working_days")),
                    absent_days=_parse_decimal(slip_data.get("absent_days")),
                    payment_days=_parse_decimal(slip_data.get("payment_days")),
                    leave_without_pay=_parse_decimal(slip_data.get("leave_without_pay")),
                    gross_pay=_parse_decimal(slip_data.get("gross_pay")),
                    total_deduction=_parse_decimal(slip_data.get("total_deduction")),
                    net_pay=_parse_decimal(slip_data.get("net_pay")),
                    rounded_total=_parse_decimal(slip_data.get("rounded_total")),
                    status=status,
                    docstatus=int(slip_data.get("docstatus") or 0),
                    bank_name=slip_data.get("bank_name"),
                    bank_account_no=slip_data.get("bank_account_no"),
                    payroll_entry=slip_data.get("payroll_entry"),
                )
                sync_client.db.add(slip)
                sync_client.db.flush()
                sync_client.increment_created()

            if not erpnext_id:
                continue

            try:
                slip_doc = await sync_client._fetch_document(client, "Salary Slip", str(erpnext_id))
                earnings = slip_doc.get("earnings", [])
                deductions = slip_doc.get("deductions", [])

                sync_client.db.query(SalarySlipEarning).filter(
                    SalarySlipEarning.salary_slip_id == slip.id
                ).delete()
                sync_client.db.query(SalarySlipDeduction).filter(
                    SalarySlipDeduction.salary_slip_id == slip.id
                ).delete()

                for row in earnings:
                    earning = SalarySlipEarning(
                        salary_slip_id=slip.id,
                        erpnext_name=row.get("name"),
                        salary_component=row.get("salary_component") or "",
                        abbr=row.get("abbr"),
                        amount=_parse_decimal(row.get("amount")),
                        default_amount=_parse_decimal(row.get("default_amount")),
                        additional_amount=_parse_decimal(row.get("additional_amount")),
                        year_to_date=_parse_decimal(row.get("year_to_date")),
                        statistical_component=_coerce_bool(row.get("statistical_component")),
                        do_not_include_in_total=_coerce_bool(row.get("do_not_include_in_total")),
                        idx=int(row.get("idx") or 0),
                    )
                    sync_client.db.add(earning)

                for row in deductions:
                    deduction = SalarySlipDeduction(
                        salary_slip_id=slip.id,
                        erpnext_name=row.get("name"),
                        salary_component=row.get("salary_component") or "",
                        abbr=row.get("abbr"),
                        amount=_parse_decimal(row.get("amount")),
                        default_amount=_parse_decimal(row.get("default_amount")),
                        additional_amount=_parse_decimal(row.get("additional_amount")),
                        year_to_date=_parse_decimal(row.get("year_to_date")),
                        statistical_component=_coerce_bool(row.get("statistical_component")),
                        do_not_include_in_total=_coerce_bool(row.get("do_not_include_in_total")),
                        idx=int(row.get("idx") or 0),
                    )
                    sync_client.db.add(deduction)
            except Exception as e:
                logger.warning("salary_slip_children_fetch_failed", slip=erpnext_id, error=str(e))

        sync_client.db.commit()
        sync_client._update_sync_cursor("salary_slips", slips, len(slips))
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_leave_types(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync leave types from ERPNext."""
    sync_client.start_sync("leave_types", "full" if full_sync else "incremental")

    try:
        filters = sync_client._get_incremental_filter("leave_types", full_sync)
        leave_types = await sync_client._fetch_all_doctype(
            client,
            "Leave Type",
            fields=[
                "name",
                "leave_type_name",
                "max_leaves_allowed",
                "max_continuous_days_allowed",
                "is_carry_forward",
                "is_lwp",
                "is_optional_leave",
                "is_compensatory",
                "allow_encashment",
                "include_holiday",
                "is_earned_leave",
                "earned_leave_frequency",
                "rounding",
                "modified",
            ],
            filters=filters,
        )

        for lt_data in leave_types:
            erpnext_id = lt_data.get("name")
            leave_type_name = lt_data.get("leave_type_name") or lt_data.get("leave_type") or erpnext_id or ""
            if not leave_type_name:
                continue
            existing = None
            if erpnext_id:
                existing = sync_client.db.query(LeaveType).filter(
                    LeaveType.erpnext_id == erpnext_id
                ).first()
            if not existing and leave_type_name:
                existing = sync_client.db.query(LeaveType).filter(
                    LeaveType.leave_type_name == leave_type_name
                ).first()

            if existing:
                existing.erpnext_id = erpnext_id
                existing.leave_type_name = leave_type_name
                existing.max_leaves_allowed = int(lt_data.get("max_leaves_allowed") or 0)
                existing.max_continuous_days_allowed = (
                    int(lt_data.get("max_continuous_days_allowed"))
                    if lt_data.get("max_continuous_days_allowed") is not None
                    else None
                )
                existing.is_carry_forward = _coerce_bool(lt_data.get("is_carry_forward"))
                existing.is_lwp = _coerce_bool(lt_data.get("is_lwp"))
                existing.is_optional_leave = _coerce_bool(lt_data.get("is_optional_leave"))
                existing.is_compensatory = _coerce_bool(lt_data.get("is_compensatory"))
                existing.allow_encashment = _coerce_bool(lt_data.get("allow_encashment"))
                existing.include_holiday = _coerce_bool(lt_data.get("include_holiday"))
                existing.is_earned_leave = _coerce_bool(lt_data.get("is_earned_leave"))
                existing.earned_leave_frequency = lt_data.get("earned_leave_frequency")
                existing.rounding = _parse_decimal(lt_data.get("rounding"), Decimal("0.5"))
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                leave_type = LeaveType(
                    erpnext_id=erpnext_id,
                    leave_type_name=leave_type_name,
                    max_leaves_allowed=int(lt_data.get("max_leaves_allowed") or 0),
                    max_continuous_days_allowed=(
                        int(lt_data.get("max_continuous_days_allowed"))
                        if lt_data.get("max_continuous_days_allowed") is not None
                        else None
                    ),
                    is_carry_forward=_coerce_bool(lt_data.get("is_carry_forward")),
                    is_lwp=_coerce_bool(lt_data.get("is_lwp")),
                    is_optional_leave=_coerce_bool(lt_data.get("is_optional_leave")),
                    is_compensatory=_coerce_bool(lt_data.get("is_compensatory")),
                    allow_encashment=_coerce_bool(lt_data.get("allow_encashment")),
                    include_holiday=_coerce_bool(lt_data.get("include_holiday")),
                    is_earned_leave=_coerce_bool(lt_data.get("is_earned_leave")),
                    earned_leave_frequency=lt_data.get("earned_leave_frequency"),
                    rounding=_parse_decimal(lt_data.get("rounding"), Decimal("0.5")),
                )
                sync_client.db.add(leave_type)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client._update_sync_cursor("leave_types", leave_types, len(leave_types))
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_leave_allocations(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync leave allocations from ERPNext."""
    sync_client.start_sync("leave_allocations", "full" if full_sync else "incremental")

    try:
        filters = sync_client._get_incremental_filter("leave_allocations", full_sync)
        allocations = await sync_client._fetch_all_doctype(
            client,
            "Leave Allocation",
            # Use minimal field set - some fields may not exist in all ERPNext versions
            fields=[
                "name",
                "employee",
                "employee_name",
                "leave_type",
                "from_date",
                "to_date",
                "new_leaves_allocated",
                "docstatus",
                "company",
                "modified",
            ],
            filters=filters,
        )

        employees_by_erpnext_id: Dict[str, int] = {
            e.erpnext_id: e.id
            for e in sync_client.db.query(Employee).filter(Employee.erpnext_id.isnot(None)).all()
        }
        leave_types_by_name: Dict[str, int] = {
            lt.leave_type_name: lt.id
            for lt in sync_client.db.query(LeaveType).all()
        }
        leave_types_by_erpnext: Dict[str, int] = {
            lt.erpnext_id: lt.id
            for lt in sync_client.db.query(LeaveType).filter(LeaveType.erpnext_id.isnot(None)).all()
        }

        for alloc_data in allocations:
            erpnext_id = alloc_data.get("name")
            existing = None
            if erpnext_id:
                existing = sync_client.db.query(LeaveAllocation).filter(
                    LeaveAllocation.erpnext_id == erpnext_id
                ).first()

            employee_ref = alloc_data.get("employee")
            employee_id = employees_by_erpnext_id.get(employee_ref) if employee_ref else None
            leave_type_name = alloc_data.get("leave_type") or ""
            leave_type_id = (
                leave_types_by_erpnext.get(leave_type_name)
                or leave_types_by_name.get(leave_type_name)
            )

            from_date = _parse_date(alloc_data.get("from_date"))
            to_date = _parse_date(alloc_data.get("to_date"))
            if not from_date or not to_date:
                continue

            status = _map_leave_allocation_status(alloc_data.get("status"), alloc_data.get("docstatus"))

            if existing:
                existing.employee = employee_ref or existing.employee
                existing.employee_id = employee_id
                existing.employee_name = alloc_data.get("employee_name")
                existing.leave_type = leave_type_name or existing.leave_type
                existing.leave_type_id = leave_type_id
                existing.from_date = from_date
                existing.to_date = to_date
                existing.new_leaves_allocated = _parse_decimal(alloc_data.get("new_leaves_allocated"))
                existing.total_leaves_allocated = _parse_decimal(alloc_data.get("total_leaves_allocated"))
                existing.unused_leaves = _parse_decimal(alloc_data.get("unused_leaves"))
                existing.carry_forwarded_leaves = _parse_decimal(alloc_data.get("carry_forwarded_leaves"))
                existing.carry_forwarded_leaves_count = _parse_decimal(
                    alloc_data.get("carry_forwarded_leaves_count")
                )
                existing.leave_policy = alloc_data.get("leave_policy")
                existing.status = status
                existing.docstatus = int(alloc_data.get("docstatus") or 0)
                existing.company = alloc_data.get("company")
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                allocation = LeaveAllocation(
                    erpnext_id=erpnext_id,
                    employee=employee_ref or "",
                    employee_id=employee_id,
                    employee_name=alloc_data.get("employee_name"),
                    leave_type=leave_type_name or "",
                    leave_type_id=leave_type_id,
                    from_date=from_date,
                    to_date=to_date,
                    new_leaves_allocated=_parse_decimal(alloc_data.get("new_leaves_allocated")),
                    total_leaves_allocated=_parse_decimal(alloc_data.get("total_leaves_allocated")),
                    unused_leaves=_parse_decimal(alloc_data.get("unused_leaves")),
                    carry_forwarded_leaves=_parse_decimal(alloc_data.get("carry_forwarded_leaves")),
                    carry_forwarded_leaves_count=_parse_decimal(
                        alloc_data.get("carry_forwarded_leaves_count")
                    ),
                    leave_policy=alloc_data.get("leave_policy"),
                    status=status,
                    docstatus=int(alloc_data.get("docstatus") or 0),
                    company=alloc_data.get("company"),
                )
                sync_client.db.add(allocation)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client._update_sync_cursor("leave_allocations", allocations, len(allocations))
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_leave_applications(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync leave applications from ERPNext."""
    sync_client.start_sync("leave_applications", "full" if full_sync else "incremental")

    try:
        filters = sync_client._get_incremental_filter("leave_applications", full_sync)
        applications = await sync_client._fetch_all_doctype(
            client,
            "Leave Application",
            fields=[
                "name",
                "employee",
                "employee_name",
                "leave_type",
                "from_date",
                "to_date",
                "half_day",
                "half_day_date",
                "total_leave_days",
                "description",
                "leave_approver",
                "leave_approver_name",
                "status",
                "docstatus",
                "posting_date",
                "company",
                "modified",
            ],
            filters=filters,
        )

        employees_by_erpnext_id: Dict[str, int] = {
            e.erpnext_id: e.id
            for e in sync_client.db.query(Employee).filter(Employee.erpnext_id.isnot(None)).all()
        }
        leave_types_by_name: Dict[str, int] = {
            lt.leave_type_name: lt.id
            for lt in sync_client.db.query(LeaveType).all()
        }
        leave_types_by_erpnext: Dict[str, int] = {
            lt.erpnext_id: lt.id
            for lt in sync_client.db.query(LeaveType).filter(LeaveType.erpnext_id.isnot(None)).all()
        }

        for app_data in applications:
            erpnext_id = app_data.get("name")
            existing = None
            if erpnext_id:
                existing = sync_client.db.query(LeaveApplication).filter(
                    LeaveApplication.erpnext_id == erpnext_id
                ).first()

            employee_ref = app_data.get("employee")
            employee_id = employees_by_erpnext_id.get(employee_ref) if employee_ref else None
            leave_type_name = app_data.get("leave_type") or ""
            leave_type_id = (
                leave_types_by_erpnext.get(leave_type_name)
                or leave_types_by_name.get(leave_type_name)
            )

            from_date = _parse_date(app_data.get("from_date"))
            to_date = _parse_date(app_data.get("to_date"))
            posting_date = _parse_date(app_data.get("posting_date"))
            if not from_date or not to_date or not posting_date:
                continue

            status = _map_leave_application_status(app_data.get("status"), app_data.get("docstatus"))

            if existing:
                existing.employee = employee_ref or existing.employee
                existing.employee_id = employee_id
                existing.employee_name = app_data.get("employee_name")
                existing.leave_type = leave_type_name or existing.leave_type
                existing.leave_type_id = leave_type_id
                existing.from_date = from_date
                existing.to_date = to_date
                existing.half_day = _coerce_bool(app_data.get("half_day"))
                existing.half_day_date = _parse_date(app_data.get("half_day_date"))
                existing.total_leave_days = _parse_decimal(app_data.get("total_leave_days"))
                existing.description = app_data.get("description")
                existing.leave_approver = app_data.get("leave_approver")
                existing.leave_approver_name = app_data.get("leave_approver_name")
                existing.status = status
                existing.docstatus = int(app_data.get("docstatus") or 0)
                existing.posting_date = posting_date
                existing.company = app_data.get("company")
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                application = LeaveApplication(
                    erpnext_id=erpnext_id,
                    employee=employee_ref or "",
                    employee_id=employee_id,
                    employee_name=app_data.get("employee_name"),
                    leave_type=leave_type_name or "",
                    leave_type_id=leave_type_id,
                    from_date=from_date,
                    to_date=to_date,
                    half_day=_coerce_bool(app_data.get("half_day")),
                    half_day_date=_parse_date(app_data.get("half_day_date")),
                    total_leave_days=_parse_decimal(app_data.get("total_leave_days")),
                    description=app_data.get("description"),
                    leave_approver=app_data.get("leave_approver"),
                    leave_approver_name=app_data.get("leave_approver_name"),
                    status=status,
                    docstatus=int(app_data.get("docstatus") or 0),
                    posting_date=posting_date,
                    company=app_data.get("company"),
                )
                sync_client.db.add(application)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client._update_sync_cursor("leave_applications", applications, len(applications))
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


async def sync_attendances(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync attendances from ERPNext."""
    sync_client.start_sync("attendances", "full" if full_sync else "incremental")

    try:
        filters = sync_client._get_incremental_filter("attendances", full_sync)
        attendances = await sync_client._fetch_all_doctype(
            client,
            "Attendance",
            fields=[
                "name",
                "employee",
                "employee_name",
                "attendance_date",
                "status",
                "leave_type",
                "leave_application",
                "shift",
                "in_time",
                "out_time",
                "working_hours",
                "late_entry",
                "early_exit",
                "company",
                "docstatus",
                "modified",
            ],
            filters=filters,
        )

        employees_by_erpnext_id: Dict[str, int] = {
            e.erpnext_id: e.id
            for e in sync_client.db.query(Employee).filter(Employee.erpnext_id.isnot(None)).all()
        }

        # Track pending additions to handle duplicates in same batch
        pending_by_key: Dict[tuple, Attendance] = {}

        for att_data in attendances:
            erpnext_id = att_data.get("name")
            employee_ref = att_data.get("employee")
            employee_id = employees_by_erpnext_id.get(employee_ref) if employee_ref else None
            attendance_date = _parse_date(att_data.get("attendance_date"))
            if not attendance_date:
                continue

            # Look up by erpnext_id first
            existing = None
            if erpnext_id:
                existing = sync_client.db.query(Attendance).filter(
                    Attendance.erpnext_id == erpnext_id
                ).first()

            # Fall back to employee_id + date (unique constraint)
            if not existing and employee_id:
                existing = sync_client.db.query(Attendance).filter(
                    Attendance.employee_id == employee_id,
                    Attendance.attendance_date == attendance_date,
                ).first()

            # Check pending additions in current batch (not yet committed)
            batch_key = (employee_id, attendance_date)
            if not existing and batch_key in pending_by_key:
                existing = pending_by_key[batch_key]

            status = _map_attendance_status(att_data.get("status"))

            if existing:
                existing.employee = employee_ref or existing.employee
                existing.employee_id = employee_id
                existing.employee_name = att_data.get("employee_name")
                existing.attendance_date = attendance_date
                existing.status = status
                existing.leave_type = att_data.get("leave_type")
                existing.leave_application = att_data.get("leave_application")
                existing.shift = att_data.get("shift")
                existing.in_time = _parse_datetime(att_data.get("in_time"))
                existing.out_time = _parse_datetime(att_data.get("out_time"))
                existing.working_hours = _parse_decimal(att_data.get("working_hours"))
                existing.check_in_latitude = att_data.get("check_in_latitude")
                existing.check_in_longitude = att_data.get("check_in_longitude")
                existing.check_out_latitude = att_data.get("check_out_latitude")
                existing.check_out_longitude = att_data.get("check_out_longitude")
                existing.device_info = att_data.get("device_info")
                existing.late_entry = _coerce_bool(att_data.get("late_entry"))
                existing.early_exit = _coerce_bool(att_data.get("early_exit"))
                existing.company = att_data.get("company")
                existing.docstatus = int(att_data.get("docstatus") or 0)
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                attendance = Attendance(
                    erpnext_id=erpnext_id,
                    employee=employee_ref or "",
                    employee_id=employee_id,
                    employee_name=att_data.get("employee_name"),
                    attendance_date=attendance_date,
                    status=status,
                    leave_type=att_data.get("leave_type"),
                    leave_application=att_data.get("leave_application"),
                    shift=att_data.get("shift"),
                    in_time=_parse_datetime(att_data.get("in_time")),
                    out_time=_parse_datetime(att_data.get("out_time")),
                    working_hours=_parse_decimal(att_data.get("working_hours")),
                    check_in_latitude=att_data.get("check_in_latitude"),
                    check_in_longitude=att_data.get("check_in_longitude"),
                    check_out_latitude=att_data.get("check_out_latitude"),
                    check_out_longitude=att_data.get("check_out_longitude"),
                    device_info=att_data.get("device_info"),
                    late_entry=_coerce_bool(att_data.get("late_entry")),
                    early_exit=_coerce_bool(att_data.get("early_exit")),
                    company=att_data.get("company"),
                    docstatus=int(att_data.get("docstatus") or 0),
                )
                sync_client.db.add(attendance)
                # Track in pending dict to detect duplicates in same batch
                if employee_id and attendance_date:
                    pending_by_key[batch_key] = attendance
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client._update_sync_cursor("attendances", attendances, len(attendances))
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


def resolve_employee_relationships(sync_client: "ERPNextSync") -> int:
    """Resolve FK relationships for employees based on text field values."""
    # Build lookup maps
    dept_map = {
        d.erpnext_id: d.id
        for d in sync_client.db.query(Department).filter(Department.erpnext_id.isnot(None)).all()
    }
    desig_map = {
        d.designation_name: d.id
        for d in sync_client.db.query(Designation).all()
    }
    emp_map = {
        e.erpnext_id: e.id
        for e in sync_client.db.query(Employee).filter(Employee.erpnext_id.isnot(None)).all()
    }

    updated = 0
    for emp in sync_client.db.query(Employee).all():
        changed = False

        # Resolve department
        if emp.department and emp.department in dept_map:
            if emp.department_id != dept_map[emp.department]:
                emp.department_id = dept_map[emp.department]
                changed = True

        # Resolve designation
        if emp.designation and emp.designation in desig_map:
            if emp.designation_id != desig_map[emp.designation]:
                emp.designation_id = desig_map[emp.designation]
                changed = True

        # Resolve reports_to (manager)
        if emp.reports_to and emp.reports_to in emp_map:
            if emp.reports_to_id != emp_map[emp.reports_to]:
                emp.reports_to_id = emp_map[emp.reports_to]
                changed = True

        if changed:
            updated += 1

    sync_client.db.commit()
    logger.info(f"Resolved {updated} employee relationships")
    return updated


def resolve_sales_person_employees(sync_client: "ERPNextSync") -> int:
    """Resolve FK relationships for sales persons to employees."""
    # Build employee lookup by erpnext_id
    emp_map = {
        e.erpnext_id: e.id
        for e in sync_client.db.query(Employee).filter(Employee.erpnext_id.isnot(None)).all()
    }

    updated = 0
    for sp in sync_client.db.query(SalesPerson).all():
        if sp.employee and sp.employee in emp_map:
            if sp.employee_id != emp_map[sp.employee]:
                sp.employee_id = emp_map[sp.employee]
                updated += 1

    sync_client.db.commit()
    logger.info(f"Linked {updated} sales persons to employees")
    return updated
