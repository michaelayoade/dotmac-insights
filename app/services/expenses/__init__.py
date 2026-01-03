"""Expense management services.

This package provides access to all expense-related business logic.

The services are implemented in standalone files for now but can be
refactored into this package structure over time.

Usage:
    from app.services.expenses import ExpenseService, ExpensePostingService

    def my_route(db: Session = Depends(get_db)):
        expense_service = ExpenseService(db)
        claim = expense_service.create_claim(data)
        db.commit()
"""
# Re-export existing services from parent directory
from app.services.expense_service import ExpenseService
from app.services.expense_posting_service import ExpensePostingService
from app.services.expense_policy_service import ExpensePolicyService, PolicyViolation
from app.services.cash_advance_service import CashAdvanceService

# Services from this package
from .categories import ExpenseCategoryService

# Type definitions from this package
from .types import (
    # Enums
    ClaimStatus,
    FundingMethod,
    # Expense claim types
    ExpenseClaimFilters,
    ExpenseLineData,
    ExpenseClaimCreateData,
    ExpenseClaimUpdateData,
    # Cash advance types
    CashAdvanceFilters,
    CashAdvanceCreateData,
    # Expense report types
    ExpenseReportFilters,
    ExpenseSummaryResult,
)

__all__ = [
    # Services
    "ExpenseService",
    "ExpensePostingService",
    "ExpensePolicyService",
    "PolicyViolation",
    "CashAdvanceService",
    "ExpenseCategoryService",
    # Enums
    "ClaimStatus",
    "FundingMethod",
    # Expense claim types
    "ExpenseClaimFilters",
    "ExpenseLineData",
    "ExpenseClaimCreateData",
    "ExpenseClaimUpdateData",
    # Cash advance types
    "CashAdvanceFilters",
    "CashAdvanceCreateData",
    # Expense report types
    "ExpenseReportFilters",
    "ExpenseSummaryResult",
]
