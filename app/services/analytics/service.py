from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, cast, TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy import func, extract, case, and_, or_, desc, text
from sqlalchemy.orm import Session

from app.cache import cached, CACHE_TTL
from app.config import settings
from app.models.party import PartyRole, CustomerAccount
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.conversation import Conversation, ConversationStatus
from app.models.pop import Pop
from app.models.ticket import Ticket, TicketStatus
from app.models.employee import Employee
from app.models.expense import Expense, ExpenseStatus

if TYPE_CHECKING:
    from app.auth import Principal


def _apply_statement_timeout(db: Session) -> None:
    """Apply per-request statement timeout for Postgres connections."""
    timeout_ms = getattr(settings, "analytics_statement_timeout_ms", None)
    if not timeout_ms or not db.bind or db.bind.dialect.name != "postgresql":
        return
    try:
        db.execute(text("SET LOCAL statement_timeout = :ms"), {"ms": timeout_ms})
    except Exception:
        db.rollback()


def _parse_date_param(date_str: Optional[str], field: str) -> Optional[datetime]:
    """Parse ISO date string to datetime or raise HTTP 400 for invalid input."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field}: {date_str}") from exc


def _get_active_currencies(db: Session, filters: Optional[List[Any]] = None) -> set[str]:
    """Return distinct currencies for active subscriptions after filters."""
    query = (
        db.query(Subscription.currency)
        .filter(Subscription.status == SubscriptionStatus.ACTIVE)
    )
    if filters:
        for f in filters:
            query = query.filter(f)
    return {row.currency for row in query.distinct().all() if row.currency}


def _resolve_currency(db: Session, filters: List, currency: Optional[str]) -> Optional[str]:
    """
    Ensure MRR calculations do not mix currencies.
    - If caller supplies currency, use it.
    - If multiple currencies exist after filters and none supplied, raise 400.
    """
    currencies = _get_active_currencies(db, filters)

    if currency:
        return currency

    if len(currencies) > 1:
        raise HTTPException(
            status_code=400,
            detail="Multiple subscription currencies detected. Provide the 'currency' query parameter to choose one.",
        )

    return currencies.pop() if currencies else None


def calculate_mrr(db: Session, filters: Optional[List[Any]] = None, currency: Optional[str] = None) -> float:
    """
    Calculate Monthly Recurring Revenue normalized by billing cycle and currency.

    - Monthly plans: price as-is
    - Quarterly plans: price / 3
    - Yearly plans: price / 12
    - If multiple currencies exist and none provided, HTTP 400 is raised.
    """
    filters = filters or []
    resolved_currency = _resolve_currency(db, filters, currency)

    mrr_case = case(
        (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
        (Subscription.billing_cycle == "yearly", Subscription.price / 12),
        else_=Subscription.price,
    )

    query = (
        db.query(func.sum(mrr_case))
        .filter(Subscription.status == SubscriptionStatus.ACTIVE)
    )

    if resolved_currency:
        query = query.filter(Subscription.currency == resolved_currency)

    for f in filters:
        query = query.filter(f)

    result = query.scalar()
    return float(result or 0)


@cached("overview", ttl=CACHE_TTL["short"], include_principal=True)
async def _get_overview_impl(currency: Optional[str], db: Session, principal: "Principal") -> Dict[str, Any]:
    """Implementation of overview metrics (cached)."""
    # Customer counts
    total_customers = db.query(CustomerAccount).count()
    active_customers = db.query(CustomerAccount).filter(CustomerAccount.status == "active").count()
    churned_customers = db.query(CustomerAccount).filter(CustomerAccount.status == "cancelled").count()

    resolved_currency = _resolve_currency(db, [], currency)

    # Revenue (MRR from active subscriptions - properly normalized by billing cycle)
    mrr = calculate_mrr(db, currency=resolved_currency)

    # Outstanding balance
    outstanding_result = (
        db.query(func.sum(Invoice.balance))
        .filter(Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]))
        .scalar()
    )
    outstanding = float(outstanding_result or 0)

    # Open support tickets
    open_tickets = db.query(Conversation).filter(
        Conversation.status.in_([ConversationStatus.OPEN, ConversationStatus.PENDING])
    ).count()

    # Overdue invoices
    overdue_invoices = db.query(Invoice).filter(Invoice.status == InvoiceStatus.OVERDUE).count()

    # POP count
    pop_count = db.query(Pop).filter(Pop.is_active.is_(True)).count()

    return {
        "customers": {
            "total": total_customers,
            "active": active_customers,
            "churned": churned_customers,
            "churn_rate": round(churned_customers / total_customers * 100, 2) if total_customers > 0 else 0,
        },
        "revenue": {
            "mrr": mrr,
            "outstanding": outstanding,
            "overdue_invoices": overdue_invoices,
            "currency": resolved_currency,
        },
        "support": {
            "open_tickets": open_tickets,
        },
        "operations": {
            "pop_count": pop_count,
        },
    }


@cached("dso", ttl=CACHE_TTL["long"], include_principal=True)
async def _get_dso_impl(months: int, db: Session, principal: "Principal") -> Dict[str, Any]:
    """Implementation of DSO calculation (cached - expensive monthly iteration)."""
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=months * 30)

    results = []

    for i in range(months):
        period_start = start_date + timedelta(days=i * 30)
        period_end = period_start + timedelta(days=30)

        # Total invoiced in period
        invoiced = (
            db.query(func.sum(Invoice.total_amount))
            .filter(
                Invoice.invoice_date >= period_start,
                Invoice.invoice_date < period_end,
            )
            .scalar()
        ) or Decimal("0")

        # Average receivables (outstanding balance at period end)
        avg_receivables = (
            db.query(func.sum(Invoice.balance))
            .filter(
                Invoice.invoice_date < period_end,
                Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID])
            )
            .scalar()
        ) or Decimal("0")

        # DSO = (Average Receivables / Revenue) * Days in Period
        dso = float((avg_receivables / invoiced) * 30) if invoiced > 0 else 0

        results.append({
            "year": period_start.year,
            "month": period_start.month,
            "period": f"{period_start.year}-{period_start.month:02d}",
            "dso": round(dso, 1),
            "invoiced": float(invoiced),
            "outstanding": float(avg_receivables),
        })

    dso_values = [float(cast(Any, r["dso"])) for r in results]
    return {
        "trend": results,
        "current_dso": dso_values[-1] if dso_values else 0,
        "average_dso": round(sum(dso_values) / len(dso_values), 1) if dso_values else 0,
    }


@cached("sla_attainment", ttl=CACHE_TTL["medium"], include_principal=True)
async def _get_sla_attainment_impl(days: int, db: Session, principal: "Principal") -> Dict[str, Any]:
    """Implementation of SLA attainment metrics (cached - SQL aggregation)."""
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Calculate resolution hours in SQL (time_to_resolution_hours is a Python property)
    resolution_hours_expr = func.extract('epoch', Ticket.resolution_date - Ticket.opening_date) / 3600

    # Single aggregated query for SLA metrics
    sla_metrics = (
        db.query(
            func.count(Ticket.id).label("total"),
            func.sum(case(
                (and_(Ticket.resolution_by.isnot(None), Ticket.resolution_date.isnot(None), Ticket.resolution_date <= Ticket.resolution_by), 1),
                else_=0
            )).label("met_sla"),
            func.sum(case(
                (and_(Ticket.resolution_by.isnot(None), Ticket.resolution_date.isnot(None), Ticket.resolution_date > Ticket.resolution_by), 1),
                else_=0
            )).label("breached_sla"),
            func.avg(resolution_hours_expr).filter(
                Ticket.resolution_date.isnot(None),
                Ticket.opening_date.isnot(None)
            ).label("avg_resolution_hours"),
            func.avg(
                func.extract('epoch', Ticket.first_responded_on - Ticket.opening_date) / 3600
            ).filter(
                Ticket.first_responded_on.isnot(None),
                Ticket.opening_date.isnot(None)
            ).label("avg_response_hours"),
        )
        .filter(Ticket.created_at >= start_date)
        .first()
    )

    # By priority breakdown
    by_priority = (
        db.query(
            Ticket.priority,
            func.count(Ticket.id).label("count"),
        )
        .filter(Ticket.created_at >= start_date)
        .group_by(Ticket.priority)
        .all()
    )

    total = sla_metrics.total or 0
    met = sla_metrics.met_sla or 0
    breached = sla_metrics.breached_sla or 0
    sla_total = met + breached

    return {
        "period_days": days,
        "total_tickets": total,
        "sla_attainment": {
            "met": met,
            "breached": breached,
            "rate": round(met / sla_total * 100, 1) if sla_total > 0 else 0,
        },
        "avg_response_hours": round(float(sla_metrics.avg_response_hours or 0), 2),
        "avg_resolution_hours": round(float(sla_metrics.avg_resolution_hours or 0), 2),
        "by_priority": {p.priority.value: p.count for p in by_priority if p.priority},
    }


class AnalyticsService:
    """Service for analytics queries used by API and web routes."""

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal
        _apply_statement_timeout(self.db)

    async def get_overview(self, currency: Optional[str] = None) -> Dict[str, Any]:
        return await _get_overview_impl(currency, self.db, cast("Principal", self.principal))

    async def get_revenue_summary(
        self,
        currency: Optional[str] = None,
        months: int = 12,
    ) -> Dict[str, Any]:
        resolved_currency = _resolve_currency(self.db, [], currency)
        mrr = calculate_mrr(self.db, currency=resolved_currency)
        outstanding = (
            self.db.query(func.coalesce(func.sum(Invoice.balance), 0))
            .filter(Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]))
            .scalar() or 0
        )
        revenue_trend = self.db.query(
            extract("year", Payment.payment_date).label("year"),
            extract("month", Payment.payment_date).label("month"),
            func.sum(Payment.amount).label("total"),
        ).filter(
            Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
            Payment.payment_date.isnot(None),
            Payment.payment_date >= datetime.now(timezone.utc) - timedelta(days=months * 30),
        ).group_by(
            extract("year", Payment.payment_date),
            extract("month", Payment.payment_date),
        ).order_by(
            extract("year", Payment.payment_date),
            extract("month", Payment.payment_date),
        ).all()

        return {
            "mrr": mrr,
            "outstanding": float(outstanding),
            "currency": resolved_currency,
            "revenue_trend": [
                {
                    "year": int(row.year),
                    "month": int(row.month),
                    "period": f"{int(row.year)}-{int(row.month):02d}",
                    "revenue": float(row.total or 0),
                }
                for row in revenue_trend
            ],
        }

    async def get_revenue_trend(
        self,
        months: int = 12,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if start_date and end_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        else:
            end_dt = datetime.now(timezone.utc)
            start_dt = end_dt - timedelta(days=months * 30)

        payments = (
            self.db.query(
                extract("year", Payment.payment_date).label("year"),
                extract("month", Payment.payment_date).label("month"),
                func.sum(Payment.amount).label("total"),
                func.count(Payment.id).label("count"),
            )
            .filter(
                Payment.payment_date >= start_dt,
                Payment.payment_date <= end_dt,
                Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
            )
            .group_by(
                extract("year", Payment.payment_date),
                extract("month", Payment.payment_date),
            )
            .order_by(
                extract("year", Payment.payment_date),
                extract("month", Payment.payment_date),
            )
            .all()
        )

        return [
            {
                "year": int(p.year),
                "month": int(p.month),
                "period": f"{int(p.year)}-{int(p.month):02d}",
                "revenue": float(p.total or 0),
                "payment_count": p.count,
            }
            for p in payments
        ]

    async def get_customer_summary(self) -> Dict[str, Any]:
        total = self.db.query(func.count(CustomerAccount.id)).scalar() or 0
        active = self.db.query(func.count(CustomerAccount.id)).filter(CustomerAccount.status == "active").scalar() or 0
        churned = self.db.query(func.count(CustomerAccount.id)).filter(CustomerAccount.status == "cancelled").scalar() or 0
        new_last_30 = self.db.query(func.count(CustomerAccount.id)).filter(
            CustomerAccount.created_at >= datetime.now(timezone.utc) - timedelta(days=30)
        ).scalar() or 0

        by_status = self.db.query(
            CustomerAccount.status,
            func.count(CustomerAccount.id).label("count")
        ).group_by(CustomerAccount.status).all()

        return {
            "total_customers": total,
            "active_customers": active,
            "churned_customers": churned,
            "new_last_30_days": new_last_30,
            "by_status": {
                (row.status if row.status else "unknown"): row.count for row in by_status
            },
        }

    async def get_support_metrics(
        self,
        days: int = 30,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        if start_date and end_date:
            period_start = start_date
            period_end = end_date
            period_days = max((end_date - start_date).days, 1)
        else:
            period_end = datetime.now(timezone.utc)
            period_start = period_end - timedelta(days=days)
            period_days = days

        total = (
            self.db.query(Conversation)
            .filter(
                Conversation.created_at >= period_start,
                Conversation.created_at <= period_end,
            )
            .count()
        )

        open_count = self.db.query(Conversation).filter(
            Conversation.created_at >= period_start,
            Conversation.created_at <= period_end,
            Conversation.status == ConversationStatus.OPEN,
        ).count()

        resolved_count = self.db.query(Conversation).filter(
            Conversation.created_at >= period_start,
            Conversation.created_at <= period_end,
            Conversation.status == ConversationStatus.RESOLVED,
        ).count()

        avg_response = (
            self.db.query(func.avg(Conversation.first_response_time_seconds))
            .filter(
                Conversation.created_at >= period_start,
                Conversation.created_at <= period_end,
                Conversation.first_response_time_seconds.isnot(None),
            )
            .scalar()
        )

        avg_resolution = (
            self.db.query(func.avg(Conversation.resolution_time_seconds))
            .filter(
                Conversation.created_at >= period_start,
                Conversation.created_at <= period_end,
                Conversation.resolution_time_seconds.isnot(None),
            )
            .scalar()
        )

        by_channel = (
            self.db.query(
                Conversation.channel,
                func.count(Conversation.id).label("count"),
            )
            .filter(
                Conversation.created_at >= period_start,
                Conversation.created_at <= period_end,
            )
            .group_by(Conversation.channel)
            .all()
        )

        return {
            "period_days": period_days,
            "total_conversations": total,
            "open": open_count,
            "resolved": resolved_count,
            "resolution_rate": round(resolved_count / total * 100, 2) if total > 0 else 0,
            "avg_first_response_hours": round(float(avg_response or 0) / 3600, 2),
            "avg_resolution_hours": round(float(avg_resolution or 0) / 3600, 2),
            "by_channel": {c.channel: c.count for c in by_channel if c.channel},
            "period": {
                "start": period_start.date().isoformat(),
                "end": period_end.date().isoformat(),
            },
        }

    async def get_invoice_aging(self) -> Dict[str, Any]:
        today = func.current_date()
        days_overdue = func.greatest(
            func.date_part('day', today - func.coalesce(Invoice.due_date, Invoice.invoice_date)),
            0
        )

        aging_bucket = case(
            (days_overdue <= 0, 'current'),
            (days_overdue <= 30, '1_30_days'),
            (days_overdue <= 60, '31_60_days'),
            (days_overdue <= 90, '61_90_days'),
            else_='over_90_days'
        )

        aging_data = (
            self.db.query(
                aging_bucket.label("bucket"),
                func.count(Invoice.id).label("count"),
                func.sum(func.coalesce(Invoice.balance, Invoice.total_amount, 0)).label("amount"),
            )
            .filter(Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]))
            .group_by(aging_bucket)
            .all()
        )

        aging: Dict[str, Dict[str, float]] = {
            "current": {"count": 0.0, "amount": 0.0},
            "1_30_days": {"count": 0.0, "amount": 0.0},
            "31_60_days": {"count": 0.0, "amount": 0.0},
            "61_90_days": {"count": 0.0, "amount": 0.0},
            "over_90_days": {"count": 0.0, "amount": 0.0},
        }

        for row in aging_data:
            if row.bucket in aging:
                aging[row.bucket]["count"] = float(row.count or 0)
                aging[row.bucket]["amount"] = float(row.amount or 0)

        total_outstanding = sum(a["amount"] for a in aging.values())

        return {
            "total_outstanding": total_outstanding,
            "aging": aging,
        }

    async def get_dso(
        self,
        months: int = 12,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        if start_date and end_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

            results = []
            current = start_dt
            while current < end_dt:
                period_end = min(current + timedelta(days=30), end_dt)

                invoiced = (
                    self.db.query(func.sum(Invoice.total_amount))
                    .filter(
                        Invoice.invoice_date >= current,
                        Invoice.invoice_date < period_end,
                    )
                    .scalar()
                ) or Decimal("0")

                avg_receivables = (
                    self.db.query(func.sum(Invoice.balance))
                    .filter(
                        Invoice.invoice_date < period_end,
                        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID])
                    )
                    .scalar()
                ) or Decimal("0")

                dso = float((avg_receivables / invoiced) * 30) if invoiced > 0 else 0

                results.append({
                    "year": current.year,
                    "month": current.month,
                    "period": f"{current.year}-{current.month:02d}",
                    "dso": round(dso, 1),
                    "invoiced": float(invoiced),
                    "outstanding": float(avg_receivables),
                })

                current = period_end

            dso_values = [float(cast(Any, r["dso"])) for r in results]
            return {
                "trend": results,
                "current_dso": dso_values[-1] if dso_values else 0,
                "average_dso": round(sum(dso_values) / len(dso_values), 1) if dso_values else 0,
            }

        return await _get_dso_impl(months, self.db, cast("Principal", self.principal))

    async def get_revenue_by_territory(self, months: int = 12) -> List[Dict[str, Any]]:
        mrr_case = case(
            (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
            (Subscription.billing_cycle == "yearly", Subscription.price / 12),
            else_=Subscription.price
        )

        segment_expr = func.coalesce(PartyRole.metadata_["customer_type"].astext, "Unknown")
        by_type = (
            self.db.query(
                segment_expr.label("segment"),
                func.count(func.distinct(Subscription.party_id)).label("customer_count"),
                func.sum(mrr_case).label("mrr"),
            )
            .outerjoin(
                PartyRole,
                and_(PartyRole.party_id == Subscription.party_id, PartyRole.role == "customer"),
            )
            .filter(
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
            .group_by(segment_expr)
            .all()
        )

        return [
            {
                "territory": t.segment or "Unknown",
                "customer_count": t.customer_count,
                "mrr": float(t.mrr or 0),
            }
            for t in by_type
        ]

    async def get_sla_attainment(self, days: int = 30) -> Dict[str, Any]:
        return await _get_sla_attainment_impl(days, self.db, cast("Principal", self.principal))

    async def get_agent_productivity(self, days: int = 30) -> List[Dict[str, Any]]:
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        agents = (
            self.db.query(
                Employee.id,
                Employee.name,
                Employee.department,
                func.count(Ticket.id).label("total_tickets"),
                func.sum(case((Ticket.status == TicketStatus.RESOLVED, 1), else_=0)).label("resolved"),
                func.sum(case((Ticket.status == TicketStatus.CLOSED, 1), else_=0)).label("closed"),
                func.avg(
                    func.extract('epoch', Ticket.resolution_date - Ticket.opening_date) / 3600
                ).label("avg_resolution_hours"),
            )
            .join(Ticket, Ticket.assigned_employee_id == Employee.id)
            .filter(Ticket.created_at >= start_date)
            .group_by(Employee.id, Employee.name, Employee.department)
            .order_by(desc("total_tickets"))
            .all()
        )

        return [
            {
                "employee_id": a.id,
                "name": a.name,
                "department": a.department,
                "total_tickets": a.total_tickets,
                "resolved": a.resolved or 0,
                "closed": a.closed or 0,
                "resolution_rate": round((a.resolved or 0) / a.total_tickets * 100, 1) if a.total_tickets > 0 else 0,
                "avg_resolution_hours": round(float(a.avg_resolution_hours or 0), 2),
            }
            for a in agents
        ]

    async def get_expenses_by_category(
        self,
        months: int = 12,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        if start_date and end_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        else:
            end_dt = datetime.now(timezone.utc)
            start_dt = end_dt - timedelta(days=months * 30)

        by_category = (
            self.db.query(
                Expense.category,
                func.count(Expense.id).label("count"),
                func.sum(Expense.total_sanctioned_amount).label("total"),
            )
            .filter(
                Expense.expense_date >= start_dt,
                Expense.expense_date <= end_dt,
                Expense.status.in_([ExpenseStatus.APPROVED, ExpenseStatus.PAID]),
            )
            .group_by(Expense.category)
            .order_by(desc("total"))
            .all()
        )

        return {
            "by_category": [
                {
                    "category": c.category or "Uncategorized",
                    "count": c.count,
                    "total": float(c.total or 0),
                }
                for c in by_category
            ],
            "total_expenses": sum(float(c.total or 0) for c in by_category),
        }

    async def get_expenses_by_cost_center(
        self,
        months: int = 12,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        if start_date and end_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        else:
            end_dt = datetime.now(timezone.utc)
            start_dt = end_dt - timedelta(days=months * 30)

        by_cost_center = (
            self.db.query(
                Expense.cost_center,
                func.count(Expense.id).label("count"),
                func.sum(Expense.total_sanctioned_amount).label("total"),
            )
            .filter(
                Expense.expense_date >= start_dt,
                Expense.expense_date <= end_dt,
                Expense.status.in_([ExpenseStatus.APPROVED, ExpenseStatus.PAID]),
            )
            .group_by(Expense.cost_center)
            .order_by(desc("total"))
            .all()
        )

        return {
            "by_cost_center": [
                {
                    "cost_center": cc.cost_center or "Unassigned",
                    "count": cc.count,
                    "total": float(cc.total or 0),
                }
                for cc in by_cost_center
            ],
            "total_expenses": sum(float(cc.total or 0) for cc in by_cost_center),
        }

    async def get_tickets_by_type(self, days: int = 30) -> Dict[str, Any]:
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        by_type = (
            self.db.query(
                Ticket.ticket_type,
                func.count(Ticket.id).label("count"),
                func.sum(case((Ticket.status == TicketStatus.RESOLVED, 1), else_=0)).label("resolved"),
            )
            .filter(Ticket.created_at >= start_date)
            .group_by(Ticket.ticket_type)
            .order_by(desc("count"))
            .all()
        )

        return {
            "by_type": [
                {
                    "type": t.ticket_type or "Unclassified",
                    "count": t.count,
                    "resolved": t.resolved or 0,
                    "resolution_rate": round(
                        (int(getattr(t, "resolved", 0) or 0)) / int(getattr(t, "count", 1) or 1) * 100,
                        1,
                    )
                    if getattr(t, "count", 0)
                    else 0,
                }
                for t in by_type
            ],
            "total": sum(t.count for t in by_type),
        }

    async def get_customers_by_plan(self, currency: Optional[str] = None) -> List[Dict[str, Any]]:
        resolved_currency = _resolve_currency(self.db, [], currency)

        mrr_case = case(
            (Subscription.billing_cycle == "quarterly", Subscription.price / 3),
            (Subscription.billing_cycle == "yearly", Subscription.price / 12),
            else_=Subscription.price
        )

        query = (
            self.db.query(
                Subscription.plan_name,
                func.count(func.distinct(Subscription.party_id)).label("customer_count"),
                func.count(Subscription.id).label("subscription_count"),
                func.sum(mrr_case).label("mrr"),
            )
            .filter(Subscription.status == SubscriptionStatus.ACTIVE)
        )

        if resolved_currency:
            query = query.filter(Subscription.currency == resolved_currency)

        plans = (
            query
            .group_by(Subscription.plan_name)
            .order_by(func.count(func.distinct(Subscription.party_id)).desc())
            .all()
        )

        return [
            {
                "plan_name": p.plan_name,
                "customer_count": p.customer_count,
                "subscription_count": p.subscription_count,
                "mrr": float(p.mrr or 0),
                "currency": resolved_currency,
            }
            for p in plans
        ]

    async def get_revenue_cohort(self) -> Dict[str, Any]:
        from sqlalchemy import literal_column

        cohort_expr = func.to_char(func.date_trunc('month', PartyRole.since), 'YYYY-MM')

        cohorts = (
            self.db.query(
                cohort_expr.label("cohort_month"),
                func.count(PartyRole.party_id).label("total_customers"),
                func.sum(case((PartyRole.status == "active", 1), else_=0)).label("active"),
                func.sum(case((PartyRole.status != "active", 1), else_=0)).label("churned"),
            )
            .filter(
                PartyRole.role == "customer",
                PartyRole.since.isnot(None),
            )
            .group_by(literal_column("1"))
            .order_by(literal_column("1"))
            .all()
        )

        results = []
        for c in cohorts:
            if c.cohort_month:
                retention = (c.active / c.total_customers * 100) if c.total_customers > 0 else 0
                results.append({
                    "cohort": c.cohort_month,
                    "total_customers": c.total_customers,
                    "active": c.active,
                    "churned": c.churned,
                    "retention_rate": round(retention, 1),
                })

        return {
            "cohorts": results[-12:],
            "summary": {
                "avg_retention": round(sum(r["retention_rate"] for r in results) / len(results), 1) if results else 0,
                "total_cohorts": len(results),
            }
        }

    async def get_churn_trend(
        self,
        months: int = 12,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        end_dt = _parse_date_param(end_date, "end_date") or datetime.now(timezone.utc)
        start_dt = _parse_date_param(start_date, "start_date") or (end_dt - timedelta(days=months * 30))

        last_end_sub = (
            self.db.query(
                Subscription.party_id.label("party_id"),
                func.max(Subscription.end_date).label("last_end_date"),
            )
            .filter(Subscription.end_date.isnot(None))
            .group_by(Subscription.party_id)
            .subquery()
        )

        active_sub_exists = (
            self.db.query(Subscription.id)
            .filter(
                Subscription.party_id == last_end_sub.c.party_id,
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
            .exists()
        )

        churn_candidates = (
            self.db.query(
                func.date_trunc("month", last_end_sub.c.last_end_date).label("period_start"),
                func.count(last_end_sub.c.party_id).label("churned"),
            )
            .filter(
                last_end_sub.c.last_end_date >= start_dt,
                last_end_sub.c.last_end_date <= end_dt,
                ~active_sub_exists,
            )
            .group_by(func.date_trunc("month", last_end_sub.c.last_end_date))
            .all()
        )

        churn_map: Dict[str, int] = {
            row.period_start.strftime("%Y-%m"): int(row.churned) for row in churn_candidates
        }

        def _active_count_at(point: datetime) -> int:
            return (
                self.db.query(func.count(func.distinct(Subscription.party_id)))
                .filter(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.start_date <= point,
                    or_(Subscription.end_date.is_(None), Subscription.end_date >= point),
                )
                .scalar()
                or 0
            )

        active_start = _active_count_at(start_dt)

        data = []
        current = datetime(start_dt.year, start_dt.month, 1)
        while current <= end_dt:
            period_key = current.strftime("%Y-%m")
            churned = churn_map.get(period_key, 0)

            period_end = (current + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
            active_end = _active_count_at(period_end)

            active_base = (active_start + active_end) / 2 if (active_start or active_end) else 0
            churn_rate = round(churned / active_base * 100, 2) if active_base > 0 else 0

            data.append(
                {
                    "period": period_key,
                    "churned_count": churned,
                    "churn_rate": churn_rate,
                    "active_base": active_base,
                }
            )

            active_start = active_end
            current = (current + timedelta(days=32)).replace(day=1)

        return {
            "period": {"start": start_dt.date().isoformat(), "end": end_dt.date().isoformat()},
            "data": data,
        }

    def get_revenue_total(self, start_dt: datetime, end_dt: datetime) -> Dict[str, Any]:
        """Get total revenue collected for a date range."""
        revenue_total = (
            self.db.query(func.sum(Payment.amount))
            .filter(
                Payment.payment_date >= start_dt,
                Payment.payment_date <= end_dt,
                Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
            )
            .scalar()
        )
        payment_count = (
            self.db.query(func.count(Payment.id))
            .filter(
                Payment.payment_date >= start_dt,
                Payment.payment_date <= end_dt,
                Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
            )
            .scalar()
        )
        return {
            "total": float(revenue_total or 0),
            "count": int(payment_count or 0),
        }

    def get_expense_total(self, start_dt: datetime, end_dt: datetime) -> Dict[str, Any]:
        """Get total approved/paid expenses for a date range."""
        expense_total = (
            self.db.query(func.sum(Expense.total_sanctioned_amount))
            .filter(
                Expense.expense_date >= start_dt,
                Expense.expense_date <= end_dt,
                Expense.status.in_([ExpenseStatus.APPROVED, ExpenseStatus.PAID]),
            )
            .scalar()
        )
        expense_count = (
            self.db.query(func.count(Expense.id))
            .filter(
                Expense.expense_date >= start_dt,
                Expense.expense_date <= end_dt,
                Expense.status.in_([ExpenseStatus.APPROVED, ExpenseStatus.PAID]),
            )
            .scalar()
        )
        return {
            "total": float(expense_total or 0),
            "count": int(expense_count or 0),
        }

    def get_support_total(self, start_dt: datetime, end_dt: datetime) -> Dict[str, Any]:
        """Get total conversations and resolved count for a date range."""
        total = (
            self.db.query(func.count(Conversation.id))
            .filter(
                Conversation.created_at >= start_dt,
                Conversation.created_at <= end_dt,
            )
            .scalar()
        )
        resolved = (
            self.db.query(func.count(Conversation.id))
            .filter(
                Conversation.created_at >= start_dt,
                Conversation.created_at <= end_dt,
                Conversation.status == ConversationStatus.RESOLVED,
            )
            .scalar()
        )
        return {
            "total": int(total or 0),
            "resolved": int(resolved or 0),
        }

    def get_customer_growth(self, start_dt: datetime, end_dt: datetime) -> Dict[str, Any]:
        """Get customer growth and churn for a date range."""
        new_customers = (
            self.db.query(func.count(CustomerAccount.id))
            .filter(
                CustomerAccount.created_at >= start_dt,
                CustomerAccount.created_at <= end_dt,
            )
            .scalar()
        )
        churned_customers = (
            self.db.query(func.count(CustomerAccount.id))
            .filter(
                CustomerAccount.cancelled_at.isnot(None),
                CustomerAccount.cancelled_at >= start_dt,
                CustomerAccount.cancelled_at <= end_dt,
            )
            .scalar()
        )
        return {
            "new": int(new_customers or 0),
            "churned": int(churned_customers or 0),
        }
