"""Expense management services.

This package provides access to all expense-related business logic.

The services are implemented in standalone files for now but can be
refactored into this package structure over time.

Usage:
    from app.services.expense_service import ExpenseService
    from app.services.expenses import ExpenseClaimFilters

    def my_route(db: Session = Depends(get_db)):
        expense_service = ExpenseService(db)
        claim = expense_service.create_claim(data)
        db.commit()

Note: Services are imported from the parent directory directly to avoid
circular imports. This package primarily exports type definitions.
"""
# Services from this package only (no parent imports to avoid circular deps)
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
    # Services from this package
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
