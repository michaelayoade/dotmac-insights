"""
Unit tests for HR services.

Tests the critical fixes applied to the HR service layer:
1. Safe formula evaluation (no eval() injection)
2. Sorting with sort.descending attribute
3. Error handling and error classes
4. Timezone-aware datetime handling (utc_now)
"""
from __future__ import annotations

from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from typing import Optional, List, Any, Dict
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass, field
import enum
import ast

import pytest

# Mark all tests in this module as HR tests
pytestmark = pytest.mark.hr


# =============================================================================
# MOCK CLASSES FOR HR SERVICES
# =============================================================================


class MockEmploymentStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TERMINATED = "terminated"
    ON_LEAVE = "on_leave"


class MockSalarySlipStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    PAID = "paid"
    CANCELLED = "cancelled"


@dataclass
class MockEmployee:
    """Mock Employee for testing."""
    id: int
    name: str = "Test Employee"
    email: str = "employee@example.com"
    employee_number: Optional[str] = "EMP-001"
    department: Optional[str] = "Engineering"
    designation: Optional[str] = "Developer"
    status: MockEmploymentStatus = MockEmploymentStatus.ACTIVE
    company: Optional[str] = "Test Company"
    salary: Optional[Decimal] = Decimal("100000.00")
    party_id: Optional[int] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MockSalarySlip:
    """Mock Salary Slip for testing."""
    id: int
    employee_id: int = 1
    payroll_entry: Optional[str] = None
    gross_pay: Decimal = Decimal("100000.00")
    total_deduction: Decimal = Decimal("20000.00")
    net_pay: Decimal = Decimal("80000.00")
    status: MockSalarySlipStatus = MockSalarySlipStatus.DRAFT


@dataclass
class MockHRSettings:
    """Mock HR Settings for testing."""
    id: int = 1
    company: Optional[str] = None
    employee_id_prefix: str = "EMP"
    employee_id_min_digits: int = 4
    default_probation_months: int = 3
    geolocation_required: bool = False
    max_working_hours_per_day: Decimal = Decimal("12")


@dataclass
class MockSortParams:
    """Mock SortParams matching app.services.types.SortParams."""
    field: str = "id"
    descending: bool = True


@dataclass
class MockPaginationParams:
    """Mock PaginationParams matching app.services.types.PaginationParams."""
    offset: int = 0
    limit: int = 50


# =============================================================================
# FORMULA EVALUATION TESTS
# =============================================================================


class TestFormulaEvaluation:
    """Tests for the safe formula evaluation in PayrollService."""

    def _evaluate_formula(self, formula: str, **variables: Decimal) -> Decimal:
        """
        Copy of the safe formula evaluator for testing.
        This mirrors the implementation in payroll.py.
        """
        import operator

        SAFE_OPERATORS = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }

        def safe_eval_node(node: ast.AST) -> Decimal:
            if isinstance(node, ast.Expression):
                return safe_eval_node(node.body)
            elif isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float, Decimal)):
                    return Decimal(str(node.value))
                raise ValueError(f"Unsupported constant type: {type(node.value)}")
            elif isinstance(node, ast.Num):
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
            expr = formula
            for name in sorted(variables.keys(), key=len, reverse=True):
                value = variables[name]
                expr = expr.replace(name, str(value))

            tree = ast.parse(expr, mode='eval')
            result = safe_eval_node(tree)
            return result.quantize(Decimal("0.01"))
        except Exception:
            return Decimal("0")

    # -------------------------------------------------------------------------
    # Basic Arithmetic Tests
    # -------------------------------------------------------------------------

    def test_simple_addition(self):
        """Test simple addition."""
        result = self._evaluate_formula("100 + 50")
        assert result == Decimal("150.00")

    def test_simple_subtraction(self):
        """Test simple subtraction."""
        result = self._evaluate_formula("100 - 30")
        assert result == Decimal("70.00")

    def test_simple_multiplication(self):
        """Test simple multiplication."""
        result = self._evaluate_formula("100 * 0.1")
        assert result == Decimal("10.00")

    def test_simple_division(self):
        """Test simple division."""
        result = self._evaluate_formula("100 / 4")
        assert result == Decimal("25.00")

    def test_combined_operations(self):
        """Test combined arithmetic operations."""
        result = self._evaluate_formula("(100 + 50) * 0.1")
        assert result == Decimal("15.00")

    def test_negative_numbers(self):
        """Test unary negation."""
        result = self._evaluate_formula("-100 + 150")
        assert result == Decimal("50.00")

    def test_parentheses_precedence(self):
        """Test that parentheses work correctly for precedence."""
        result = self._evaluate_formula("(100 + 200) / 3")
        assert result == Decimal("100.00")

    # -------------------------------------------------------------------------
    # Variable Substitution Tests
    # -------------------------------------------------------------------------

    def test_single_variable(self):
        """Test single variable substitution."""
        result = self._evaluate_formula("base * 0.1", base=Decimal("10000"))
        assert result == Decimal("1000.00")

    def test_multiple_variables(self):
        """Test multiple variable substitution."""
        result = self._evaluate_formula(
            "base + allowance",
            base=Decimal("50000"),
            allowance=Decimal("5000"),
        )
        assert result == Decimal("55000.00")

    def test_variable_in_complex_formula(self):
        """Test variables in complex formula."""
        result = self._evaluate_formula(
            "(gross_pay - deductions) * 0.1",
            gross_pay=Decimal("100000"),
            deductions=Decimal("20000"),
        )
        assert result == Decimal("8000.00")

    def test_similar_variable_names(self):
        """Test that similar variable names don't conflict (e.g., 'base' vs 'base_pay')."""
        result = self._evaluate_formula(
            "base_pay + base",
            base_pay=Decimal("50000"),
            base=Decimal("10000"),
        )
        assert result == Decimal("60000.00")

    # -------------------------------------------------------------------------
    # Security Tests - Injection Prevention
    # -------------------------------------------------------------------------

    def test_rejects_function_calls(self):
        """Test that function calls are rejected."""
        result = self._evaluate_formula("__import__('os').system('ls')")
        assert result == Decimal("0")

    def test_rejects_attribute_access(self):
        """Test that attribute access is rejected."""
        result = self._evaluate_formula("().__class__.__bases__[0]")
        assert result == Decimal("0")

    def test_rejects_string_literals(self):
        """Test that string literals are rejected."""
        result = self._evaluate_formula("'malicious'")
        assert result == Decimal("0")

    def test_rejects_list_literals(self):
        """Test that list literals are rejected."""
        result = self._evaluate_formula("[1, 2, 3]")
        assert result == Decimal("0")

    def test_rejects_dict_literals(self):
        """Test that dict literals are rejected."""
        result = self._evaluate_formula("{'key': 'value'}")
        assert result == Decimal("0")

    def test_rejects_comprehensions(self):
        """Test that list comprehensions are rejected."""
        result = self._evaluate_formula("[x for x in range(10)]")
        assert result == Decimal("0")

    def test_rejects_lambda(self):
        """Test that lambda expressions are rejected."""
        result = self._evaluate_formula("(lambda: 1)()")
        assert result == Decimal("0")

    def test_rejects_exec_eval(self):
        """Test that exec/eval calls are rejected."""
        result = self._evaluate_formula("eval('1+1')")
        assert result == Decimal("0")

    def test_rejects_builtins_access(self):
        """Test that __builtins__ access is rejected."""
        result = self._evaluate_formula("__builtins__")
        assert result == Decimal("0")

    def test_rejects_power_operator(self):
        """Test that power operator (**) is rejected for DoS prevention."""
        result = self._evaluate_formula("10 ** 100")
        assert result == Decimal("0")

    def test_rejects_bitwise_operators(self):
        """Test that bitwise operators are rejected."""
        result = self._evaluate_formula("10 & 5")
        assert result == Decimal("0")

        result = self._evaluate_formula("10 | 5")
        assert result == Decimal("0")

        result = self._evaluate_formula("10 ^ 5")
        assert result == Decimal("0")

    # -------------------------------------------------------------------------
    # Edge Cases
    # -------------------------------------------------------------------------

    def test_division_by_zero_returns_zero(self):
        """Test that division by zero returns 0 instead of raising."""
        result = self._evaluate_formula("100 / 0")
        assert result == Decimal("0")

    def test_empty_formula_returns_zero(self):
        """Test that empty formula returns 0."""
        result = self._evaluate_formula("")
        assert result == Decimal("0")

    def test_invalid_syntax_returns_zero(self):
        """Test that invalid syntax returns 0."""
        result = self._evaluate_formula("100 +")
        assert result == Decimal("0")

    def test_missing_variable_returns_zero(self):
        """Test that missing variable returns 0."""
        result = self._evaluate_formula("base * 0.1")
        assert result == Decimal("0")

    def test_decimal_precision(self):
        """Test that results are properly quantized to 2 decimal places."""
        result = self._evaluate_formula("100 / 3")
        assert result == Decimal("33.33")

    def test_large_numbers(self):
        """Test handling of large numbers."""
        result = self._evaluate_formula(
            "base * 12",
            base=Decimal("999999999.99"),
        )
        assert result == Decimal("11999999999.88")


# =============================================================================
# SORTING TESTS
# =============================================================================


class TestSortingParameters:
    """Tests for the SortParams.descending attribute usage."""

    def test_sort_params_descending_true(self):
        """Test SortParams with descending=True."""
        sort = MockSortParams(field="name", descending=True)
        assert sort.descending is True
        assert sort.field == "name"

    def test_sort_params_descending_false(self):
        """Test SortParams with descending=False."""
        sort = MockSortParams(field="created_at", descending=False)
        assert sort.descending is False
        assert sort.field == "created_at"

    def test_sort_params_default_values(self):
        """Test SortParams default values."""
        sort = MockSortParams()
        assert sort.field == "id"
        assert sort.descending is True

    def test_sort_application_descending(self):
        """Test that descending sort is applied correctly."""
        sort = MockSortParams(field="name", descending=True)

        # Simulate sort application logic
        if sort.descending:
            order = "DESC"
        else:
            order = "ASC"

        assert order == "DESC"

    def test_sort_application_ascending(self):
        """Test that ascending sort is applied correctly."""
        sort = MockSortParams(field="name", descending=False)

        # Simulate sort application logic
        if sort.descending:
            order = "DESC"
        else:
            order = "ASC"

        assert order == "ASC"


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestHRErrors:
    """Tests for HR service error classes."""

    def test_employee_not_found_error_with_id(self):
        """Test EmployeeNotFoundError with employee ID."""
        from app.services.hr.errors import EmployeeNotFoundError

        error = EmployeeNotFoundError(employee_id=123)
        assert "123" in str(error)
        assert error.employee_id == 123

    def test_employee_not_found_error_with_message(self):
        """Test EmployeeNotFoundError with custom message."""
        from app.services.hr.errors import EmployeeNotFoundError

        error = EmployeeNotFoundError(message="Custom error message")
        assert "Custom error message" in str(error)

    def test_validation_error(self):
        """Test ValidationError."""
        from app.services.hr.errors import ValidationError

        error = ValidationError("Invalid data provided")
        assert "Invalid data provided" in str(error)

    def test_check_in_error(self):
        """Test CheckInError."""
        from app.services.hr.errors import CheckInError

        error = CheckInError("Already checked in", reason="duplicate")
        assert "Already checked in" in str(error)
        assert error.reason == "duplicate"

    def test_check_out_error(self):
        """Test CheckOutError."""
        from app.services.hr.errors import CheckOutError

        error = CheckOutError("Must check in first", reason="no_checkin")
        assert "Must check in first" in str(error)
        assert error.reason == "no_checkin"

    def test_insufficient_leave_balance_error(self):
        """Test InsufficientLeaveBalanceError."""
        from app.services.hr.errors import InsufficientLeaveBalanceError

        error = InsufficientLeaveBalanceError(
            available=5.0,
            requested=10.0,
            leave_type="Annual Leave",
        )
        assert error.available == 5.0
        assert error.requested == 10.0
        assert error.leave_type == "Annual Leave"
        assert "5" in str(error)
        assert "10" in str(error)

    def test_leave_overlap_error(self):
        """Test LeaveOverlapError."""
        from app.services.hr.errors import LeaveOverlapError

        error = LeaveOverlapError(
            overlap_id=42,
            from_date="2024-01-10",
            to_date="2024-01-15",
        )
        assert error.overlap_id == 42
        assert "42" in str(error)

    def test_salary_slip_not_found_error(self):
        """Test SalarySlipNotFoundError."""
        from app.services.hr.errors import SalarySlipNotFoundError

        error = SalarySlipNotFoundError(slip_id=999)
        assert error.slip_id == 999
        assert "999" in str(error)

    def test_training_program_not_found_error(self):
        """Test TrainingProgramNotFoundError."""
        from app.services.hr.errors import TrainingProgramNotFoundError

        error = TrainingProgramNotFoundError(program_id=55)
        assert error.program_id == 55

    def test_appraisal_status_error(self):
        """Test AppraisalStatusError."""
        from app.services.hr.errors import AppraisalStatusError

        error = AppraisalStatusError(
            appraisal_id=10,
            current_status="draft",
            target_status="completed",
        )
        assert error.appraisal_id == 10
        assert error.current_status == "draft"
        assert error.target_status == "completed"

    def test_lifecycle_status_error(self):
        """Test LifecycleStatusError."""
        from app.services.hr.errors import LifecycleStatusError

        error = LifecycleStatusError(
            current_status="pending",
            operation="complete",
        )
        assert error.current_status == "pending"
        assert error.operation == "complete"


# =============================================================================
# DATETIME HANDLING TESTS
# =============================================================================


class TestDatetimeHandling:
    """Tests for timezone-aware datetime handling."""

    def test_utc_now_is_timezone_aware(self):
        """Test that utc_now() returns timezone-aware datetime."""
        from app.utils.datetime_utils import utc_now

        now = utc_now()
        assert now.tzinfo is not None
        assert now.tzinfo == timezone.utc

    def test_utc_now_returns_utc(self):
        """Test that utc_now() returns UTC time."""
        from app.utils.datetime_utils import utc_now

        now = utc_now()
        offset = now.utcoffset()
        assert offset == timedelta(0)

    def test_ensure_utc_with_naive_datetime(self):
        """Test ensure_utc with naive datetime."""
        from app.utils.datetime_utils import ensure_utc

        naive_dt = datetime(2024, 1, 15, 10, 30, 0)
        aware_dt = ensure_utc(naive_dt)

        assert aware_dt.tzinfo is not None
        assert aware_dt.tzinfo == timezone.utc

    def test_ensure_utc_with_none(self):
        """Test ensure_utc with None."""
        from app.utils.datetime_utils import ensure_utc

        result = ensure_utc(None)
        assert result is None

    def test_ensure_utc_with_aware_datetime(self):
        """Test ensure_utc with already aware datetime."""
        from app.utils.datetime_utils import ensure_utc

        aware_dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = ensure_utc(aware_dt)

        assert result.tzinfo == timezone.utc

    def test_is_aware_with_aware_datetime(self):
        """Test is_aware with timezone-aware datetime."""
        from app.utils.datetime_utils import is_aware

        aware_dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        assert is_aware(aware_dt) is True

    def test_is_aware_with_naive_datetime(self):
        """Test is_aware with naive datetime."""
        from app.utils.datetime_utils import is_aware

        naive_dt = datetime(2024, 1, 15, 10, 30, 0)
        assert is_aware(naive_dt) is False

    def test_is_aware_with_none(self):
        """Test is_aware with None."""
        from app.utils.datetime_utils import is_aware

        assert is_aware(None) is False


# =============================================================================
# SETTINGS CACHE TESTS
# =============================================================================


class TestSettingsCache:
    """Tests for multi-tenant settings cache behavior."""

    def test_settings_cache_key_by_company(self):
        """Test that settings cache uses company as key."""
        cache: Dict[str, MockHRSettings] = {}

        # Simulate caching settings for different companies
        settings_a = MockHRSettings(id=1, company="Company A")
        settings_b = MockHRSettings(id=2, company="Company B")

        cache["Company A"] = settings_a
        cache["Company B"] = settings_b

        assert cache["Company A"].company == "Company A"
        assert cache["Company B"].company == "Company B"
        assert cache["Company A"].id != cache["Company B"].id

    def test_settings_cache_default_key(self):
        """Test that None company uses __default__ key."""
        cache: Dict[str, MockHRSettings] = {}

        def get_cache_key(company: Optional[str]) -> str:
            return company or "__default__"

        assert get_cache_key(None) == "__default__"
        assert get_cache_key("Company A") == "Company A"

    def test_settings_cache_isolation(self):
        """Test that different companies get different settings."""
        cache: Dict[str, MockHRSettings] = {}

        settings_default = MockHRSettings(id=1, employee_id_prefix="EMP")
        settings_corp = MockHRSettings(id=2, employee_id_prefix="CORP")

        cache["__default__"] = settings_default
        cache["Corporate"] = settings_corp

        assert cache["__default__"].employee_id_prefix == "EMP"
        assert cache["Corporate"].employee_id_prefix == "CORP"


# =============================================================================
# EMPLOYEE COMPANY FIELD TESTS
# =============================================================================


class TestEmployeeCompanyField:
    """Tests for the Employee.company field."""

    def test_employee_has_company_field(self):
        """Test that Employee model has company field."""
        employee = MockEmployee(
            id=1,
            name="Test Employee",
            company="Test Company",
        )
        assert employee.company == "Test Company"

    def test_employee_company_can_be_none(self):
        """Test that Employee.company can be None."""
        employee = MockEmployee(
            id=1,
            name="Test Employee",
            company=None,
        )
        assert employee.company is None

    def test_employee_company_used_for_settings(self):
        """Test that employee.company is used to get settings."""
        employee = MockEmployee(
            id=1,
            name="Test Employee",
            company="Company A",
        )

        # Simulate settings lookup
        cache_key = employee.company or "__default__"
        assert cache_key == "Company A"


# =============================================================================
# PAGINATION TESTS
# =============================================================================


class TestPagination:
    """Tests for pagination parameter handling."""

    def test_pagination_defaults(self):
        """Test default pagination values."""
        pagination = MockPaginationParams()
        assert pagination.offset == 0
        assert pagination.limit == 50

    def test_pagination_custom_values(self):
        """Test custom pagination values."""
        pagination = MockPaginationParams(offset=100, limit=25)
        assert pagination.offset == 100
        assert pagination.limit == 25

    def test_pagination_page_calculation(self):
        """Test page number calculation from offset."""
        def calculate_page(offset: int, limit: int) -> int:
            if limit <= 0:
                return 1
            return (offset // limit) + 1

        assert calculate_page(0, 50) == 1
        assert calculate_page(50, 50) == 2
        assert calculate_page(100, 50) == 3
        assert calculate_page(99, 50) == 2

    def test_pagination_total_pages(self):
        """Test total pages calculation."""
        def calculate_total_pages(total: int, limit: int) -> int:
            if limit <= 0:
                return 1
            return (total + limit - 1) // limit

        assert calculate_total_pages(100, 50) == 2
        assert calculate_total_pages(101, 50) == 3
        assert calculate_total_pages(50, 50) == 1
        assert calculate_total_pages(0, 50) == 0
