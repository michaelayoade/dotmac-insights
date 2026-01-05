"""Purchasing Analytics Service."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import func, extract
from sqlalchemy.orm import Session

from app.models.accounting import (
    PurchaseInvoice,
    PurchaseInvoiceStatus,
    GLEntry,
    Account,
    AccountType,
)

from .types import ExpenseFilters


class PurchasingAnalyticsService:
    """Service for purchasing analytics and reporting."""

    def __init__(self, db: Session):
        self.db = db

    def get_purchases_by_supplier(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Get purchases breakdown by supplier."""
        query = self.db.query(
            PurchaseInvoice.supplier_name,
            func.count(PurchaseInvoice.id).label("bill_count"),
            func.sum(PurchaseInvoice.grand_total).label("total_purchases"),
            func.sum(PurchaseInvoice.outstanding_amount).label("outstanding"),
        ).filter(
            PurchaseInvoice.status != PurchaseInvoiceStatus.RETURN,
        )

        if start_date:
            query = query.filter(PurchaseInvoice.posting_date >= start_date)
        if end_date:
            query = query.filter(PurchaseInvoice.posting_date <= end_date)

        query = query.group_by(PurchaseInvoice.supplier_name)
        results = query.order_by(func.sum(PurchaseInvoice.grand_total).desc()).limit(limit).all()

        total = sum(float(r.total_purchases or 0) for r in results)

        return {
            "total": total,
            "suppliers": [
                {
                    "name": r.supplier_name,
                    "bill_count": r.bill_count,
                    "total_purchases": float(r.total_purchases or 0),
                    "outstanding": float(r.outstanding or 0),
                    "percentage": round(float(r.total_purchases or 0) / total * 100, 1) if total > 0 else 0,
                }
                for r in results
            ],
        }

    def get_expenses_by_cost_center(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Get expenses breakdown by cost center."""
        expense_account_ids = self._get_expense_account_ids()

        query = self.db.query(
            GLEntry.cost_center,
            func.sum(GLEntry.debit).label("total"),
            func.count(GLEntry.id).label("entry_count"),
        ).filter(
            GLEntry.account.in_(expense_account_ids),
            GLEntry.is_cancelled == False,
            GLEntry.debit > 0,
            GLEntry.cost_center.isnot(None),
        )

        if start_date:
            query = query.filter(GLEntry.posting_date >= start_date)
        if end_date:
            query = query.filter(GLEntry.posting_date <= end_date)

        query = query.group_by(GLEntry.cost_center)
        results = query.order_by(func.sum(GLEntry.debit).desc()).all()

        total = sum(float(r.total or 0) for r in results)

        return {
            "total": total,
            "cost_centers": [
                {
                    "name": r.cost_center or "Unassigned",
                    "total": float(r.total or 0),
                    "entry_count": r.entry_count,
                    "percentage": round(float(r.total or 0) / total * 100, 1) if total > 0 else 0,
                }
                for r in results
            ],
        }

    def get_expense_trend(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        granularity: str = "month",
    ) -> Dict[str, Any]:
        """Get expense trend over time."""
        expense_account_ids = self._get_expense_account_ids()

        # Determine date grouping
        if granularity == "day":
            date_trunc = func.date(GLEntry.posting_date)
        elif granularity == "week":
            date_trunc = func.date(func.date_trunc('week', GLEntry.posting_date))
        else:  # month
            date_trunc = func.date(func.date_trunc('month', GLEntry.posting_date))

        query = self.db.query(
            date_trunc.label("period"),
            func.sum(GLEntry.debit).label("total"),
            func.count(GLEntry.id).label("entry_count"),
        ).filter(
            GLEntry.account.in_(expense_account_ids),
            GLEntry.is_cancelled == False,
            GLEntry.debit > 0,
        )

        if start_date:
            query = query.filter(GLEntry.posting_date >= start_date)
        if end_date:
            query = query.filter(GLEntry.posting_date <= end_date)

        query = query.group_by(date_trunc).order_by(date_trunc)
        results = query.all()

        return {
            "granularity": granularity,
            "trend": [
                {
                    "period": r.period.isoformat() if r.period else None,
                    "total": float(r.total or 0),
                    "entry_count": r.entry_count,
                }
                for r in results
            ],
        }

    def get_expense_types(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Get expense breakdown by account type."""
        expense_accounts = self.db.query(Account).filter(
            Account.root_type == AccountType.EXPENSE,
            Account.disabled == False,
        ).all()
        expense_account_map = {a.erpnext_id: a for a in expense_accounts}
        expense_account_ids = list(expense_account_map.keys())

        query = self.db.query(
            GLEntry.account,
            func.sum(GLEntry.debit).label("total_debit"),
            func.count(GLEntry.id).label("entry_count"),
        ).filter(
            GLEntry.account.in_(expense_account_ids),
            GLEntry.is_cancelled == False,
            GLEntry.debit > 0,
        )

        if start_date:
            query = query.filter(GLEntry.posting_date >= start_date)
        if end_date:
            query = query.filter(GLEntry.posting_date <= end_date)

        query = query.group_by(GLEntry.account)
        results = query.order_by(func.sum(GLEntry.debit).desc()).all()

        total_expenses = sum(float(r.total_debit) for r in results)

        return {
            "total_expenses": total_expenses,
            "expense_types": [
                {
                    "account": r.account,
                    "account_name": expense_account_map.get(r.account, type('', (), {'account_name': r.account})).account_name,
                    "total": float(r.total_debit),
                    "entry_count": r.entry_count,
                    "percentage": round(float(r.total_debit) / total_expenses * 100, 1) if total_expenses > 0 else 0,
                }
                for r in results
            ],
        }

    def _get_expense_account_ids(self) -> List[str]:
        """Get list of expense account IDs."""
        accounts = self.db.query(Account.erpnext_id).filter(
            Account.root_type == AccountType.EXPENSE,
            Account.disabled == False,
        ).all()
        return [a[0] for a in accounts if a[0]]
