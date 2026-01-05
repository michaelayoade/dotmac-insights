"""GL Expense Service."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import GLEntry, Account, AccountType
from app.services.types import PaginationParams, PaginatedResult
from app.services.errors import NotFoundError

from .types import ExpenseFilters


class GLExpenseService:
    """Service for GL-based expense entries."""

    def __init__(self, db: Session):
        self.db = db
        self._expense_account_ids: Optional[List[str]] = None

    def _get_expense_account_ids(self) -> List[str]:
        """Get cached expense account IDs."""
        if self._expense_account_ids is None:
            accounts = self.db.query(Account.erpnext_id).filter(
                Account.root_type == AccountType.EXPENSE,
                Account.disabled == False,
            ).all()
            self._expense_account_ids = [a[0] for a in accounts if a[0]]
        return self._expense_account_ids

    def list_expenses(
        self,
        filters: ExpenseFilters,
        pagination: PaginationParams,
    ) -> PaginatedResult[GLEntry]:
        """List expense entries from GL."""
        expense_account_ids = self._get_expense_account_ids()

        query = self.db.query(GLEntry).filter(
            GLEntry.account.in_(expense_account_ids),
            GLEntry.is_cancelled == False,
            GLEntry.debit > 0,
        )

        if filters.account:
            query = query.filter(GLEntry.account.ilike(f"%{filters.account}%"))

        if filters.cost_center:
            query = query.filter(GLEntry.cost_center == filters.cost_center)

        if filters.start_date:
            query = query.filter(GLEntry.posting_date >= filters.start_date)

        if filters.end_date:
            query = query.filter(GLEntry.posting_date <= filters.end_date)

        if filters.min_amount is not None:
            query = query.filter(GLEntry.debit >= filters.min_amount)

        total = query.count()
        expenses = query.order_by(GLEntry.posting_date.desc()).offset(pagination.offset).limit(pagination.limit).all()

        return PaginatedResult(data=expenses, total=total)

    def get_expense(self, expense_id: int) -> Dict[str, Any]:
        """Get expense entry details."""
        expense = self.db.query(GLEntry).filter(GLEntry.id == expense_id).first()
        if not expense:
            raise NotFoundError(f"Expense {expense_id} not found")

        account = self.db.query(Account).filter(
            Account.erpnext_id == expense.account
        ).first()

        return {
            "expense": expense,
            "account": account,
        }

    def get_expense_summary(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Decimal]:
        """Get expense summary by account."""
        expense_account_ids = self._get_expense_account_ids()

        query = self.db.query(
            GLEntry.account,
            func.sum(GLEntry.debit).label("total"),
        ).filter(
            GLEntry.account.in_(expense_account_ids),
            GLEntry.is_cancelled == False,
            GLEntry.debit > 0,
        )

        if start_date:
            query = query.filter(GLEntry.posting_date >= start_date)
        if end_date:
            query = query.filter(GLEntry.posting_date <= end_date)

        results = query.group_by(GLEntry.account).all()

        return {r.account: Decimal(str(r.total)) for r in results}
