"""Web-facing query helpers for purchasing routes."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import case, func, select, or_
from sqlalchemy.orm import Session, selectinload

from app.models.purchasing_order import PurchaseOrder, PurchaseOrderStatus
from app.models.expense import Expense
from app.models.books_settings import DebitNote
from app.models.supplier_payment import SupplierPayment


class PurchasingQueryService:
    """Encapsulate purchasing UI queries to keep routes thin."""

    def __init__(self, db: Session):
        self.db = db

    def get_purchase_order_stats(self) -> dict:
        row = self.db.execute(
            select(
                func.count(PurchaseOrder.id).label("total"),
                func.sum(case((PurchaseOrder.status == PurchaseOrderStatus.DRAFT, 1), else_=0)).label("draft"),
                func.sum(case((PurchaseOrder.status == PurchaseOrderStatus.TO_RECEIVE, 1), else_=0)).label("to_receive"),
                func.sum(case((PurchaseOrder.status == PurchaseOrderStatus.COMPLETED, 1), else_=0)).label("completed"),
            )
        ).first()

        return {
            "total": row.total if row else 0,
            "draft": row.draft if row else 0,
            "to_receive": row.to_receive if row else 0,
            "completed": row.completed if row else 0,
        }

    def list_purchase_orders(
        self,
        q: Optional[str],
        status: Optional[str],
        supplier: Optional[str],
        page: int,
        per_page: int,
        sort: str,
        direction: str,
        allowed_sorts: set[str],
    ) -> tuple[list[PurchaseOrder], int]:
        query = select(PurchaseOrder)

        if q:
            search = f"%{q}%"
            query = query.where(
                or_(
                    PurchaseOrder.erpnext_id.ilike(search),
                    PurchaseOrder.supplier_name.ilike(search),
                    PurchaseOrder.supplier.ilike(search),
                )
            )

        if status:
            try:
                status_enum = PurchaseOrderStatus(status)
                query = query.where(PurchaseOrder.status == status_enum)
            except ValueError:
                pass

        if supplier:
            query = query.where(PurchaseOrder.supplier_name.ilike(f"%{supplier}%"))

        count_query = select(func.count()).select_from(query.subquery())
        total = self.db.scalar(count_query) or 0

        if sort not in allowed_sorts:
            sort = "transaction_date"
        sort_column = getattr(PurchaseOrder, sort, PurchaseOrder.transaction_date)
        if direction == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        offset = (page - 1) * per_page
        orders = self.db.execute(query.offset(offset).limit(per_page)).scalars().all()
        return orders, total

    def get_purchase_order(self, order_id: int) -> Optional[PurchaseOrder]:
        query = (
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.items))
            .where(PurchaseOrder.id == order_id)
        )
        return self.db.execute(query).scalar_one_or_none()

    def list_expenses(self, page: int, per_page: int) -> dict:
        today = date.today()
        start_of_month = today.replace(day=1)
        start_of_year = today.replace(month=1, day=1)

        query = select(Expense).order_by(Expense.posting_date.desc())
        count_query = select(func.count()).select_from(Expense)
        total = self.db.scalar(count_query) or 0

        offset = (page - 1) * per_page
        expenses = self.db.execute(query.offset(offset).limit(per_page)).scalars().all()

        mtd_total = self.db.execute(
            select(func.sum(Expense.total_claimed_amount)).where(
                Expense.posting_date >= start_of_month
            )
        ).scalar() or Decimal("0")

        ytd_total = self.db.execute(
            select(func.sum(Expense.total_claimed_amount)).where(
                Expense.posting_date >= start_of_year
            )
        ).scalar() or Decimal("0")

        by_category_rows = self.db.execute(
            select(
                Expense.expense_type,
                func.count(Expense.id).label("count"),
                func.sum(Expense.total_claimed_amount).label("total"),
            ).where(
                Expense.posting_date >= start_of_year
            ).group_by(
                Expense.expense_type
            ).order_by(
                func.sum(Expense.total_claimed_amount).desc()
            ).limit(10)
        ).all()

        by_category = [
            {
                "category": row.expense_type or "Uncategorized",
                "count": row.count,
                "total": float(row.total or 0),
            }
            for row in by_category_rows
        ]

        return {
            "expenses": expenses,
            "total": total,
            "mtd_total": mtd_total,
            "ytd_total": ytd_total,
            "by_category": by_category,
        }

    def list_debit_notes(self, page: int, per_page: int) -> dict:
        query = select(DebitNote).order_by(DebitNote.posting_date.desc())
        count_query = select(func.count()).select_from(DebitNote)
        total = self.db.scalar(count_query) or 0

        offset = (page - 1) * per_page
        notes = self.db.execute(query.offset(offset).limit(per_page)).scalars().all()

        total_amount = self.db.execute(
            select(func.sum(DebitNote.total_amount))
        ).scalar() or Decimal("0")

        outstanding = self.db.execute(
            select(func.sum(DebitNote.outstanding_amount)).where(
                DebitNote.outstanding_amount > 0
            )
        ).scalar() or Decimal("0")

        return {
            "notes": notes,
            "total": total,
            "total_amount": total_amount,
            "outstanding": outstanding,
        }

    def list_supplier_payments(self, page: int, per_page: int) -> dict:
        today = date.today()
        start_of_month = today.replace(day=1)

        query = select(SupplierPayment).order_by(SupplierPayment.posting_date.desc())
        count_query = select(func.count()).select_from(SupplierPayment)
        total = self.db.scalar(count_query) or 0

        offset = (page - 1) * per_page
        payments = self.db.execute(query.offset(offset).limit(per_page)).scalars().all()

        mtd_paid = self.db.execute(
            select(func.sum(SupplierPayment.paid_amount)).where(
                SupplierPayment.posting_date >= start_of_month
            )
        ).scalar() or Decimal("0")

        total_paid = self.db.execute(
            select(func.sum(SupplierPayment.paid_amount))
        ).scalar() or Decimal("0")

        return {
            "payments": payments,
            "total": total,
            "mtd_paid": mtd_paid,
            "total_paid": total_paid,
        }
