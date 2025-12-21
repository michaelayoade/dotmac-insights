"""IFRS cross-statement validation and tie-back checks.

This module provides validation functions to ensure:
1. Cross-statement consistency (P&L → Equity → Balance Sheet → Cash Flow)
2. Arithmetic accuracy (subtotals = sum of components)
3. Sign convention compliance
4. Balance sheet equation integrity
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import Account, AccountType, GLEntry


# =============================================================================
# Sign Convention Documentation
# =============================================================================
"""
IFRS Sign Conventions (enforced throughout the system):

BALANCE SHEET (cumulative balances):
- Assets: Positive debit balance (debit - credit > 0)
- Liabilities: Positive credit balance (stored as positive in API responses)
- Equity: Positive credit balance (stored as positive in API responses)

INCOME STATEMENT (period flows):
- Revenue: Positive amounts (credit increases)
- Expenses: Positive amounts (debit increases)
- Net Income = Revenue - Expenses (positive = profit)

CASH FLOW STATEMENT:
- Inflows: Positive amounts
- Outflows: Negative amounts
- Net change = Opening + Net Flow = Closing

STATEMENT OF CHANGES IN EQUITY:
- Opening balances: Positive
- Increases (profit, issues): Positive
- Decreases (losses, dividends, buybacks): Negative
- Closing balance = Opening + all movements
"""


class ValidationSeverity(str, Enum):
    """Severity levels for validation issues."""
    ERROR = "error"      # Blocks data - must be fixed
    WARNING = "warning"  # Data returned but flagged


@dataclass
class ValidationIssue:
    """A single validation error or warning."""
    code: str
    message: str
    field: Optional[str] = None
    expected: Optional[Any] = None
    actual: Optional[Any] = None
    severity: ValidationSeverity = ValidationSeverity.ERROR


@dataclass
class ValidationResult:
    """Result of validation checks."""
    is_valid: bool
    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)

    def add_error(
        self,
        code: str,
        message: str,
        field: Optional[str] = None,
        expected: Any = None,
        actual: Any = None,
    ) -> None:
        """Add a validation error."""
        self.errors.append(ValidationIssue(
            code=code,
            message=message,
            field=field,
            expected=expected,
            actual=actual,
            severity=ValidationSeverity.ERROR,
        ))
        self.is_valid = False

    def add_warning(
        self,
        code: str,
        message: str,
        field: Optional[str] = None,
        expected: Any = None,
        actual: Any = None,
    ) -> None:
        """Add a validation warning."""
        self.warnings.append(ValidationIssue(
            code=code,
            message=message,
            field=field,
            expected=expected,
            actual=actual,
            severity=ValidationSeverity.WARNING,
        ))

    def merge(self, other: "ValidationResult") -> None:
        """Merge another validation result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if not other.is_valid:
            self.is_valid = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API response format."""
        return {
            "is_valid": self.is_valid,
            "errors": [
                {
                    "code": e.code,
                    "message": e.message,
                    "field": e.field,
                    "expected": _serialize_value(e.expected),
                    "actual": _serialize_value(e.actual),
                }
                for e in self.errors
            ],
            "warnings": [
                {
                    "code": w.code,
                    "message": w.message,
                    "field": w.field,
                    "expected": _serialize_value(w.expected),
                    "actual": _serialize_value(w.actual),
                }
                for w in self.warnings
            ],
        }


def _serialize_value(value: Any) -> Any:
    """Serialize value for JSON response."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


# Tolerance for floating point comparisons (0.01 for currency)
RECONCILIATION_TOLERANCE = Decimal("0.01")


# =============================================================================
# Cross-Statement Tie-Back Validations
# =============================================================================

def validate_retained_earnings_movement(
    prior_retained_earnings: Decimal,
    current_retained_earnings: Decimal,
    profit_after_tax: Decimal,
    dividends_paid: Decimal,
    other_adjustments: Decimal = Decimal("0"),
) -> ValidationResult:
    """Validate retained earnings movement reconciliation.

    IAS 1 requires: Closing RE = Opening RE + PAT - Dividends ± Other Adjustments

    Args:
        prior_retained_earnings: Opening retained earnings balance
        current_retained_earnings: Closing retained earnings balance
        profit_after_tax: Net income from Income Statement
        dividends_paid: Dividends declared/paid (positive amount)
        other_adjustments: Other movements (prior period adjustments, etc.)

    Returns:
        ValidationResult with any errors/warnings
    """
    result = ValidationResult(is_valid=True)

    expected_closing = (
        prior_retained_earnings
        + profit_after_tax
        - dividends_paid
        + other_adjustments
    )

    difference = abs(current_retained_earnings - expected_closing)

    if difference > RECONCILIATION_TOLERANCE:
        result.add_error(
            code="RE_MOVEMENT_MISMATCH",
            message=(
                f"Retained earnings movement does not reconcile. "
                f"Expected {float(expected_closing):.2f}, got {float(current_retained_earnings):.2f}. "
                f"Difference: {float(difference):.2f}"
            ),
            field="retained_earnings",
            expected=float(expected_closing),
            actual=float(current_retained_earnings),
        )

    return result


def validate_equity_to_balance_sheet(
    equity_statement_closing: Decimal,
    balance_sheet_equity: Decimal,
) -> ValidationResult:
    """Validate equity statement closing equals balance sheet equity.

    The total equity from Statement of Changes in Equity must equal
    the total equity shown on the Balance Sheet.

    Args:
        equity_statement_closing: Total closing equity from SOCE
        balance_sheet_equity: Total equity from Balance Sheet

    Returns:
        ValidationResult with any errors/warnings
    """
    result = ValidationResult(is_valid=True)

    difference = abs(equity_statement_closing - balance_sheet_equity)

    if difference > RECONCILIATION_TOLERANCE:
        result.add_error(
            code="EQUITY_STATEMENT_BS_MISMATCH",
            message=(
                f"Equity statement closing ({float(equity_statement_closing):.2f}) "
                f"does not match balance sheet equity ({float(balance_sheet_equity):.2f}). "
                f"Difference: {float(difference):.2f}"
            ),
            field="total_equity",
            expected=float(equity_statement_closing),
            actual=float(balance_sheet_equity),
        )

    return result


def validate_cash_flow_to_balance_sheet(
    cf_opening_cash: Decimal,
    cf_net_change: Decimal,
    cf_closing_cash: Decimal,
    bs_cash: Decimal,
    fx_effect: Decimal = Decimal("0"),
) -> ValidationResult:
    """Validate cash flow statement ties to balance sheet cash.

    IAS 7 requires:
    1. Opening Cash + Net Change + FX Effect = Closing Cash (internal consistency)
    2. Closing Cash = Balance Sheet Cash (cross-statement tie)

    Args:
        cf_opening_cash: Opening cash from Cash Flow Statement
        cf_net_change: Net change in cash (Operating + Investing + Financing)
        cf_closing_cash: Closing cash from Cash Flow Statement
        bs_cash: Cash and cash equivalents from Balance Sheet
        fx_effect: Effect of exchange rate changes on cash

    Returns:
        ValidationResult with any errors/warnings
    """
    result = ValidationResult(is_valid=True)

    # Validate internal cash flow consistency
    expected_closing = cf_opening_cash + cf_net_change + fx_effect
    internal_diff = abs(cf_closing_cash - expected_closing)

    if internal_diff > RECONCILIATION_TOLERANCE:
        result.add_error(
            code="CASH_FLOW_INTERNAL_MISMATCH",
            message=(
                f"Cash flow does not reconcile internally. "
                f"Opening ({float(cf_opening_cash):.2f}) + Net Change ({float(cf_net_change):.2f}) "
                f"+ FX ({float(fx_effect):.2f}) = {float(expected_closing):.2f}, "
                f"but closing shows {float(cf_closing_cash):.2f}"
            ),
            field="closing_cash",
            expected=float(expected_closing),
            actual=float(cf_closing_cash),
        )

    # Validate cash flow closing ties to balance sheet
    bs_diff = abs(cf_closing_cash - bs_cash)

    if bs_diff > RECONCILIATION_TOLERANCE:
        result.add_error(
            code="CASH_FLOW_BS_MISMATCH",
            message=(
                f"Cash flow closing cash ({float(cf_closing_cash):.2f}) "
                f"does not match balance sheet cash ({float(bs_cash):.2f}). "
                f"Difference: {float(bs_diff):.2f}"
            ),
            field="closing_cash",
            expected=float(bs_cash),
            actual=float(cf_closing_cash),
        )

    return result


def validate_profit_to_cash_flow(
    pl_net_income: Decimal,
    cf_net_income: Decimal,
) -> ValidationResult:
    """Validate P&L net income matches cash flow starting point.

    For indirect method cash flow, the starting net income must equal
    the net income from the Income Statement.

    Args:
        pl_net_income: Net income from Income Statement
        cf_net_income: Starting net income in Cash Flow Statement

    Returns:
        ValidationResult with any errors/warnings
    """
    result = ValidationResult(is_valid=True)

    difference = abs(pl_net_income - cf_net_income)

    if difference > RECONCILIATION_TOLERANCE:
        result.add_error(
            code="NET_INCOME_CF_MISMATCH",
            message=(
                f"P&L net income ({float(pl_net_income):.2f}) does not match "
                f"cash flow statement starting net income ({float(cf_net_income):.2f}). "
                f"Difference: {float(difference):.2f}"
            ),
            field="net_income",
            expected=float(pl_net_income),
            actual=float(cf_net_income),
        )

    return result


def validate_balance_sheet_equation(
    total_assets: Decimal,
    total_liabilities: Decimal,
    total_equity: Decimal,
) -> ValidationResult:
    """Validate the fundamental accounting equation.

    Assets = Liabilities + Equity

    Args:
        total_assets: Total assets from Balance Sheet
        total_liabilities: Total liabilities from Balance Sheet
        total_equity: Total equity from Balance Sheet

    Returns:
        ValidationResult with any errors/warnings
    """
    result = ValidationResult(is_valid=True)

    expected_assets = total_liabilities + total_equity
    difference = abs(total_assets - expected_assets)

    if difference > RECONCILIATION_TOLERANCE:
        result.add_error(
            code="BALANCE_SHEET_EQUATION_MISMATCH",
            message=(
                f"Balance sheet equation does not balance. "
                f"Assets ({float(total_assets):.2f}) ≠ Liabilities ({float(total_liabilities):.2f}) "
                f"+ Equity ({float(total_equity):.2f}) = {float(expected_assets):.2f}. "
                f"Difference: {float(difference):.2f}"
            ),
            field="total_assets",
            expected=float(expected_assets),
            actual=float(total_assets),
        )

    return result


# =============================================================================
# Income Statement Subtotal Validations
# =============================================================================

def validate_income_statement_subtotals(
    revenue: Decimal,
    cogs: Decimal,
    gross_profit: Decimal,
    operating_expenses: Decimal,
    operating_profit: Decimal,
    finance_income: Decimal,
    finance_costs: Decimal,
    profit_before_tax: Decimal,
    tax_expense: Decimal,
    profit_after_tax: Decimal,
) -> ValidationResult:
    """Validate all Income Statement subtotals are correct.

    Validates the P&L waterfall:
    - Gross Profit = Revenue - COGS
    - Operating Profit (EBIT) = Gross Profit - Operating Expenses
    - Profit Before Tax (EBT) = EBIT + Finance Income - Finance Costs
    - Profit After Tax (PAT) = EBT - Tax Expense

    Args:
        revenue: Total revenue
        cogs: Cost of goods sold
        gross_profit: Gross profit
        operating_expenses: Total operating expenses
        operating_profit: Operating profit (EBIT)
        finance_income: Finance income
        finance_costs: Finance costs
        profit_before_tax: Profit before tax (EBT)
        tax_expense: Tax expense
        profit_after_tax: Profit after tax (PAT)

    Returns:
        ValidationResult with any errors/warnings
    """
    result = ValidationResult(is_valid=True)

    # Gross Profit = Revenue - COGS
    expected_gp = revenue - cogs
    if abs(gross_profit - expected_gp) > RECONCILIATION_TOLERANCE:
        result.add_error(
            code="GROSS_PROFIT_MISMATCH",
            message=(
                f"Gross profit ({float(gross_profit):.2f}) does not equal "
                f"Revenue ({float(revenue):.2f}) - COGS ({float(cogs):.2f}) = {float(expected_gp):.2f}"
            ),
            field="gross_profit",
            expected=float(expected_gp),
            actual=float(gross_profit),
        )

    # Operating Profit = Gross Profit - Operating Expenses
    expected_op = gross_profit - operating_expenses
    if abs(operating_profit - expected_op) > RECONCILIATION_TOLERANCE:
        result.add_error(
            code="OPERATING_PROFIT_MISMATCH",
            message=(
                f"Operating profit ({float(operating_profit):.2f}) does not equal "
                f"Gross Profit ({float(gross_profit):.2f}) - OpEx ({float(operating_expenses):.2f}) = {float(expected_op):.2f}"
            ),
            field="operating_income",
            expected=float(expected_op),
            actual=float(operating_profit),
        )

    # PBT = Operating Profit + Finance Income - Finance Costs
    expected_pbt = operating_profit + finance_income - finance_costs
    if abs(profit_before_tax - expected_pbt) > RECONCILIATION_TOLERANCE:
        result.add_error(
            code="PROFIT_BEFORE_TAX_MISMATCH",
            message=(
                f"Profit before tax ({float(profit_before_tax):.2f}) does not equal "
                f"EBIT ({float(operating_profit):.2f}) + Finance Income ({float(finance_income):.2f}) "
                f"- Finance Costs ({float(finance_costs):.2f}) = {float(expected_pbt):.2f}"
            ),
            field="profit_before_tax",
            expected=float(expected_pbt),
            actual=float(profit_before_tax),
        )

    # PAT = PBT - Tax Expense
    expected_pat = profit_before_tax - tax_expense
    if abs(profit_after_tax - expected_pat) > RECONCILIATION_TOLERANCE:
        result.add_error(
            code="PROFIT_AFTER_TAX_MISMATCH",
            message=(
                f"Profit after tax ({float(profit_after_tax):.2f}) does not equal "
                f"PBT ({float(profit_before_tax):.2f}) - Tax ({float(tax_expense):.2f}) = {float(expected_pat):.2f}"
            ),
            field="profit_after_tax",
            expected=float(expected_pat),
            actual=float(profit_after_tax),
        )

    return result


# =============================================================================
# Cash Flow Operating Activities Validation
# =============================================================================

def validate_operating_activities_reconciliation(
    net_income: Decimal,
    depreciation_amortization: Decimal,
    working_capital_changes: Decimal,
    other_adjustments: Decimal,
    cash_from_operations: Decimal,
) -> ValidationResult:
    """Validate indirect method cash from operations reconciliation.

    CFO = Net Income + D&A + Working Capital Changes + Other Non-Cash Items

    Args:
        net_income: Net income (starting point)
        depreciation_amortization: Add back D&A
        working_capital_changes: Net working capital changes
        other_adjustments: Other non-cash adjustments
        cash_from_operations: Calculated CFO

    Returns:
        ValidationResult with any errors/warnings
    """
    result = ValidationResult(is_valid=True)

    expected_cfo = (
        net_income
        + depreciation_amortization
        + working_capital_changes
        + other_adjustments
    )

    difference = abs(cash_from_operations - expected_cfo)

    if difference > RECONCILIATION_TOLERANCE:
        result.add_error(
            code="CFO_RECONCILIATION_MISMATCH",
            message=(
                f"Cash from operations ({float(cash_from_operations):.2f}) does not reconcile. "
                f"Expected: Net Income ({float(net_income):.2f}) + D&A ({float(depreciation_amortization):.2f}) "
                f"+ WC Changes ({float(working_capital_changes):.2f}) + Other ({float(other_adjustments):.2f}) "
                f"= {float(expected_cfo):.2f}"
            ),
            field="operating_activities.net",
            expected=float(expected_cfo),
            actual=float(cash_from_operations),
        )

    return result


# =============================================================================
# Equity Statement Validation
# =============================================================================

def validate_equity_component_movement(
    component_name: str,
    opening_balance: Decimal,
    movements: Dict[str, Decimal],
    closing_balance: Decimal,
) -> ValidationResult:
    """Validate a single equity component movement reconciliation.

    Closing = Opening + Sum of all movements

    Args:
        component_name: Name of the equity component
        opening_balance: Opening balance
        movements: Dict of movement_type -> amount
        closing_balance: Closing balance

    Returns:
        ValidationResult with any errors/warnings
    """
    result = ValidationResult(is_valid=True)

    total_movements = sum(movements.values())
    expected_closing = opening_balance + total_movements
    difference = abs(closing_balance - expected_closing)

    if difference > RECONCILIATION_TOLERANCE:
        result.add_error(
            code="EQUITY_COMPONENT_MISMATCH",
            message=(
                f"{component_name}: Closing ({float(closing_balance):.2f}) does not equal "
                f"Opening ({float(opening_balance):.2f}) + Movements ({float(total_movements):.2f}) "
                f"= {float(expected_closing):.2f}"
            ),
            field=f"components.{component_name}",
            expected=float(expected_closing),
            actual=float(closing_balance),
        )

    return result


# =============================================================================
# Trial Balance Validation
# =============================================================================

def validate_trial_balance(
    total_debits: Decimal,
    total_credits: Decimal,
) -> ValidationResult:
    """Validate trial balance debits equal credits.

    Args:
        total_debits: Sum of all debit balances
        total_credits: Sum of all credit balances

    Returns:
        ValidationResult with any errors/warnings
    """
    result = ValidationResult(is_valid=True)

    difference = abs(total_debits - total_credits)

    if difference > RECONCILIATION_TOLERANCE:
        result.add_error(
            code="TRIAL_BALANCE_MISMATCH",
            message=(
                f"Trial balance does not balance. "
                f"Debits ({float(total_debits):.2f}) ≠ Credits ({float(total_credits):.2f}). "
                f"Difference: {float(difference):.2f}"
            ),
            field="trial_balance",
            expected=float(total_debits),
            actual=float(total_credits),
        )

    return result


# =============================================================================
# Sign Convention Validation
# =============================================================================

def validate_sign_convention(
    value: Decimal,
    expected_sign: str,
    field_name: str,
    context: str = "",
) -> ValidationResult:
    """Validate a value follows expected sign convention.

    Args:
        value: The value to check
        expected_sign: "positive", "negative", or "any"
        field_name: Name of the field
        context: Additional context for error message

    Returns:
        ValidationResult with any errors/warnings
    """
    result = ValidationResult(is_valid=True)

    if expected_sign == "positive" and value < 0:
        result.add_warning(
            code="UNEXPECTED_NEGATIVE",
            message=f"{field_name} is negative ({float(value):.2f}) but expected positive. {context}",
            field=field_name,
            expected="positive",
            actual=float(value),
        )
    elif expected_sign == "negative" and value > 0:
        result.add_warning(
            code="UNEXPECTED_POSITIVE",
            message=f"{field_name} is positive ({float(value):.2f}) but expected negative. {context}",
            field=field_name,
            expected="negative",
            actual=float(value),
        )

    return result


# =============================================================================
# Comprehensive Statement Validation
# =============================================================================

def validate_all_statements(
    balance_sheet: Dict[str, Any],
    income_statement: Dict[str, Any],
    cash_flow: Dict[str, Any],
    equity_statement: Dict[str, Any],
) -> ValidationResult:
    """Run all cross-statement validations.

    This is the main entry point for comprehensive validation across
    all four financial statements.

    Args:
        balance_sheet: Balance sheet data
        income_statement: Income statement data
        cash_flow: Cash flow statement data
        equity_statement: Equity statement data

    Returns:
        ValidationResult with all errors/warnings consolidated
    """
    result = ValidationResult(is_valid=True)

    # Extract key values
    bs_total_assets = Decimal(str(balance_sheet.get("total_assets", 0)))
    bs_total_liabilities = Decimal(str(balance_sheet.get("total_liabilities", 0)))
    bs_total_equity = Decimal(str(balance_sheet.get("total_equity", 0)))
    bs_cash = Decimal(str(balance_sheet.get("cash_and_equivalents", 0)))
    bs_retained_earnings = Decimal(str(balance_sheet.get("retained_earnings", 0)))

    pl_net_income = Decimal(str(income_statement.get("net_income", 0)))
    pl_revenue = Decimal(str(income_statement.get("revenue", {}).get("total", 0)))
    pl_cogs = Decimal(str(income_statement.get("cost_of_goods_sold", {}).get("total", 0)))
    pl_gross_profit = Decimal(str(income_statement.get("gross_profit", 0)))
    pl_operating_expenses = Decimal(str(income_statement.get("operating_expenses", {}).get("total", 0)))
    pl_operating_income = Decimal(str(income_statement.get("operating_income", 0)))
    pl_finance_income = Decimal(str(income_statement.get("finance_income", {}).get("total", 0)))
    pl_finance_costs = Decimal(str(income_statement.get("finance_costs", {}).get("total", 0)))
    pl_profit_before_tax = Decimal(str(income_statement.get("profit_before_tax", 0)))
    pl_tax_expense = Decimal(str(income_statement.get("tax_expense", {}).get("total", 0)))

    cf_opening = Decimal(str(cash_flow.get("opening_cash", 0)))
    cf_closing = Decimal(str(cash_flow.get("closing_cash", 0)))
    cf_net_change = Decimal(str(cash_flow.get("net_change_in_cash", 0)))
    cf_net_income = Decimal(str(cash_flow.get("operating_activities", {}).get("net_income", 0)))
    cf_fx_effect = Decimal(str(cash_flow.get("fx_effect_on_cash", 0)))

    eq_closing = Decimal(str(equity_statement.get("summary", {}).get("total_closing_equity", 0)))
    eq_opening = Decimal(str(equity_statement.get("summary", {}).get("total_opening_equity", 0)))
    eq_dividends = abs(Decimal(str(equity_statement.get("summary", {}).get("transactions_with_owners", {}).get("dividends_paid", 0))))

    # 1. Balance Sheet Equation
    result.merge(validate_balance_sheet_equation(
        bs_total_assets, bs_total_liabilities, bs_total_equity
    ))

    # 2. Income Statement Subtotals
    result.merge(validate_income_statement_subtotals(
        pl_revenue, pl_cogs, pl_gross_profit,
        pl_operating_expenses, pl_operating_income,
        pl_finance_income, pl_finance_costs,
        pl_profit_before_tax, pl_tax_expense, pl_net_income
    ))

    # 3. P&L Net Income → Cash Flow
    result.merge(validate_profit_to_cash_flow(pl_net_income, cf_net_income))

    # 4. Cash Flow → Balance Sheet Cash
    result.merge(validate_cash_flow_to_balance_sheet(
        cf_opening, cf_net_change, cf_closing, bs_cash, cf_fx_effect
    ))

    # 5. Equity Statement → Balance Sheet Equity
    result.merge(validate_equity_to_balance_sheet(eq_closing, bs_total_equity))

    # 6. Retained Earnings Movement
    prior_re = eq_opening - (bs_total_equity - bs_retained_earnings)  # Approximate
    result.merge(validate_retained_earnings_movement(
        prior_re, bs_retained_earnings, pl_net_income, eq_dividends
    ))

    return result


# =============================================================================
# Database-Level Validation Helpers
# =============================================================================

def get_cash_balance_from_db(db: Session, as_of: date) -> Decimal:
    """Get total cash and cash equivalents from GL as of a date.

    Args:
        db: Database session
        as_of: Date to calculate balance as of

    Returns:
        Total cash balance
    """
    from app.api.accounting.helpers import CURRENT_ASSET_TYPES

    cash_types = {"Bank", "Cash"}

    # Get all cash-type accounts
    cash_accounts = db.query(Account).filter(
        Account.account_type.in_(cash_types),
        Account.disabled == False,
    ).all()

    if not cash_accounts:
        return Decimal("0")

    account_ids = [acc.erpnext_id for acc in cash_accounts]

    # Sum GL balances for cash accounts
    result = db.query(
        func.sum(GLEntry.debit - GLEntry.credit).label("balance")
    ).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date <= as_of,
        GLEntry.account.in_(account_ids),
    ).scalar()

    return Decimal(str(result or 0))


def get_retained_earnings_from_db(db: Session, as_of: date) -> Decimal:
    """Get retained earnings balance from GL as of a date.

    Args:
        db: Database session
        as_of: Date to calculate balance as of

    Returns:
        Retained earnings balance
    """
    from app.api.accounting.helpers import RETAINED_EARNINGS_TYPES

    # Get retained earnings accounts
    re_accounts = db.query(Account).filter(
        Account.root_type == AccountType.EQUITY,
    ).all()

    re_account_ids = [
        acc.erpnext_id for acc in re_accounts
        if acc.account_type in RETAINED_EARNINGS_TYPES
        or any(kw in (acc.account_name or "").lower() for kw in ["retained", "accumulated profit", "accumulated loss"])
    ]

    if not re_account_ids:
        return Decimal("0")

    # Credit balance for equity
    result = db.query(
        func.sum(GLEntry.credit - GLEntry.debit).label("balance")
    ).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date <= as_of,
        GLEntry.account.in_(re_account_ids),
    ).scalar()

    return Decimal(str(result or 0))
