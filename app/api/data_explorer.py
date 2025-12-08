from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text, inspect
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.database import get_db
from app.models.customer import Customer
from app.models.subscription import Subscription
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.conversation import Conversation, Message
from app.models.pop import Pop
from app.models.employee import Employee
from app.models.expense import Expense
from app.models.sync_log import SyncLog

router = APIRouter()

# Available tables for exploration
TABLES = {
    "customers": Customer,
    "subscriptions": Subscription,
    "invoices": Invoice,
    "payments": Payment,
    "conversations": Conversation,
    "messages": Message,
    "pops": Pop,
    "employees": Employee,
    "expenses": Expense,
    "sync_logs": SyncLog,
}


@router.get("/tables")
async def list_tables(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """List all available tables with record counts."""
    tables = {}

    for name, model in TABLES.items():
        count = db.query(model).count()
        tables[name] = {
            "count": count,
            "columns": [c.key for c in inspect(model).mapper.column_attrs],
        }

    return tables


@router.get("/tables/{table_name}")
async def explore_table(
    table_name: str,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    order_by: Optional[str] = None,
    order_dir: str = Query(default="desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Explore data in a specific table."""
    if table_name not in TABLES:
        raise HTTPException(status_code=404, detail=f"Table not found: {table_name}")

    model = TABLES[table_name]
    query = db.query(model)

    # Apply ordering
    if order_by:
        column = getattr(model, order_by, None)
        if column is None:
            raise HTTPException(status_code=400, detail=f"Invalid column: {order_by}")
        if order_dir == "desc":
            query = query.order_by(column.desc())
        else:
            query = query.order_by(column.asc())
    else:
        # Default order by id desc
        if hasattr(model, "id"):
            query = query.order_by(model.id.desc())

    total = query.count()
    records = query.offset(offset).limit(limit).all()

    # Convert to dict
    data = []
    for record in records:
        row = {}
        for column in inspect(model).mapper.column_attrs:
            value = getattr(record, column.key)
            # Handle datetime serialization
            if isinstance(value, datetime):
                value = value.isoformat()
            # Handle enums
            elif hasattr(value, "value"):
                value = value.value
            row[column.key] = value
        data.append(row)

    return {
        "table": table_name,
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": data,
    }


@router.get("/tables/{table_name}/stats")
async def get_table_stats(
    table_name: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get statistics for a table."""
    if table_name not in TABLES:
        raise HTTPException(status_code=404, detail=f"Table not found: {table_name}")

    model = TABLES[table_name]

    stats = {
        "table": table_name,
        "total_records": db.query(model).count(),
    }

    # Add specific stats based on table
    if table_name == "customers":
        stats["by_status"] = {
            row.status.value: row.count
            for row in db.query(Customer.status, func.count(Customer.id).label("count"))
            .group_by(Customer.status)
            .all()
        }
        stats["by_type"] = {
            row.customer_type.value: row.count
            for row in db.query(Customer.customer_type, func.count(Customer.id).label("count"))
            .group_by(Customer.customer_type)
            .all()
        }

    elif table_name == "subscriptions":
        stats["by_status"] = {
            row.status.value: row.count
            for row in db.query(Subscription.status, func.count(Subscription.id).label("count"))
            .group_by(Subscription.status)
            .all()
        }
        stats["by_plan"] = {
            row.plan_name: row.count
            for row in db.query(Subscription.plan_name, func.count(Subscription.id).label("count"))
            .group_by(Subscription.plan_name)
            .order_by(func.count(Subscription.id).desc())
            .limit(20)
            .all()
        }

    elif table_name == "invoices":
        stats["by_status"] = {
            row.status.value: row.count
            for row in db.query(Invoice.status, func.count(Invoice.id).label("count"))
            .group_by(Invoice.status)
            .all()
        }
        total_amount = db.query(func.sum(Invoice.total_amount)).scalar()
        total_paid = db.query(func.sum(Invoice.amount_paid)).scalar()
        stats["total_invoiced"] = float(total_amount or 0)
        stats["total_paid"] = float(total_paid or 0)

    elif table_name == "payments":
        stats["by_method"] = {
            row.payment_method.value: row.count
            for row in db.query(Payment.payment_method, func.count(Payment.id).label("count"))
            .group_by(Payment.payment_method)
            .all()
        }
        total = db.query(func.sum(Payment.amount)).scalar()
        stats["total_payments"] = float(total or 0)

    elif table_name == "conversations":
        stats["by_status"] = {
            row.status.value: row.count
            for row in db.query(Conversation.status, func.count(Conversation.id).label("count"))
            .group_by(Conversation.status)
            .all()
        }
        stats["by_channel"] = {
            row.channel: row.count
            for row in db.query(Conversation.channel, func.count(Conversation.id).label("count"))
            .group_by(Conversation.channel)
            .all()
            if row.channel
        }

    elif table_name == "pops":
        stats["active"] = db.query(Pop).filter(Pop.is_active == True).count()
        stats["inactive"] = db.query(Pop).filter(Pop.is_active == False).count()

    elif table_name == "employees":
        stats["by_department"] = {
            row.department: row.count
            for row in db.query(Employee.department, func.count(Employee.id).label("count"))
            .group_by(Employee.department)
            .all()
            if row.department
        }
        stats["by_status"] = {
            row.status.value: row.count
            for row in db.query(Employee.status, func.count(Employee.id).label("count"))
            .group_by(Employee.status)
            .all()
        }

    return stats


@router.get("/data-quality")
async def check_data_quality(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Check data quality and completeness across all tables."""
    report = {}

    # Customers
    total_customers = db.query(Customer).count()
    customers_with_email = db.query(Customer).filter(Customer.email.isnot(None)).count()
    customers_with_phone = db.query(Customer).filter(Customer.phone.isnot(None)).count()
    customers_with_pop = db.query(Customer).filter(Customer.pop_id.isnot(None)).count()
    customers_linked_splynx = db.query(Customer).filter(Customer.splynx_id.isnot(None)).count()
    customers_linked_erpnext = db.query(Customer).filter(Customer.erpnext_id.isnot(None)).count()
    customers_linked_chatwoot = db.query(Customer).filter(Customer.chatwoot_contact_id.isnot(None)).count()

    report["customers"] = {
        "total": total_customers,
        "completeness": {
            "has_email": customers_with_email,
            "has_phone": customers_with_phone,
            "has_pop": customers_with_pop,
        },
        "linkage": {
            "linked_to_splynx": customers_linked_splynx,
            "linked_to_erpnext": customers_linked_erpnext,
            "linked_to_chatwoot": customers_linked_chatwoot,
        },
        "quality_score": round(
            (customers_with_email + customers_with_phone + customers_with_pop)
            / (total_customers * 3)
            * 100
            if total_customers > 0
            else 0,
            2,
        ),
    }

    # Invoices
    total_invoices = db.query(Invoice).count()
    invoices_with_customer = db.query(Invoice).filter(Invoice.customer_id.isnot(None)).count()

    report["invoices"] = {
        "total": total_invoices,
        "linked_to_customer": invoices_with_customer,
        "unlinked": total_invoices - invoices_with_customer,
    }

    # Conversations
    total_conversations = db.query(Conversation).count()
    conversations_with_customer = db.query(Conversation).filter(Conversation.customer_id.isnot(None)).count()

    report["conversations"] = {
        "total": total_conversations,
        "linked_to_customer": conversations_with_customer,
        "unlinked": total_conversations - conversations_with_customer,
    }

    # Overall data health
    total_records = sum([
        total_customers,
        db.query(Subscription).count(),
        total_invoices,
        db.query(Payment).count(),
        total_conversations,
    ])

    report["summary"] = {
        "total_records": total_records,
        "last_sync_check": datetime.utcnow().isoformat(),
    }

    return report


@router.get("/search")
async def search_all(
    q: str = Query(..., min_length=2),
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Search across all major tables."""
    results = {}
    search_term = f"%{q}%"

    # Search customers
    customers = (
        db.query(Customer)
        .filter(
            Customer.name.ilike(search_term)
            | Customer.email.ilike(search_term)
            | Customer.phone.ilike(search_term)
            | Customer.account_number.ilike(search_term)
        )
        .limit(limit)
        .all()
    )
    results["customers"] = [
        {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "status": c.status.value,
        }
        for c in customers
    ]

    # Search invoices
    invoices = (
        db.query(Invoice)
        .filter(Invoice.invoice_number.ilike(search_term))
        .limit(limit)
        .all()
    )
    results["invoices"] = [
        {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "total_amount": float(inv.total_amount),
            "status": inv.status.value,
        }
        for inv in invoices
    ]

    # Search employees
    employees = (
        db.query(Employee)
        .filter(
            Employee.name.ilike(search_term)
            | Employee.email.ilike(search_term)
        )
        .limit(limit)
        .all()
    )
    results["employees"] = [
        {
            "id": e.id,
            "name": e.name,
            "email": e.email,
            "department": e.department,
        }
        for e in employees
    ]

    # Search POPs
    pops = (
        db.query(Pop)
        .filter(
            Pop.name.ilike(search_term)
            | Pop.code.ilike(search_term)
        )
        .limit(limit)
        .all()
    )
    results["pops"] = [
        {
            "id": p.id,
            "name": p.name,
            "code": p.code,
        }
        for p in pops
    ]

    return results


def _apply_filters(query, model, filters: Dict[str, Any]):
    """Apply filters to a query, handling both simple values and operator dicts."""
    if not filters:
        return query

    for column_name, value in filters.items():
        column = getattr(model, column_name, None)
        if column is None:
            continue

        if isinstance(value, dict):
            # Handle operators: {"gt": 100, "lt": 500}
            for op, val in value.items():
                if op == "gt":
                    query = query.filter(column > val)
                elif op == "gte":
                    query = query.filter(column >= val)
                elif op == "lt":
                    query = query.filter(column < val)
                elif op == "lte":
                    query = query.filter(column <= val)
                elif op == "eq":
                    query = query.filter(column == val)
                elif op == "ne":
                    query = query.filter(column != val)
                elif op == "like":
                    query = query.filter(column.ilike(f"%{val}%"))
                elif op == "in":
                    query = query.filter(column.in_(val))
        else:
            # Simple equality
            query = query.filter(column == value)

    return query


@router.post("/query")
async def run_custom_query(
    table: str,
    filters: Optional[Dict[str, Any]] = None,
    group_by: Optional[List[str]] = None,
    aggregate: Optional[Dict[str, str]] = None,  # {"column": "sum|count|avg|min|max"}
    limit: int = Query(default=100, le=1000),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Run a custom query with filters, grouping, and aggregation."""
    if table not in TABLES:
        raise HTTPException(status_code=404, detail=f"Table not found: {table}")

    model = TABLES[table]

    # Handle grouping and aggregation
    if group_by and aggregate:
        select_columns = []
        for col_name in group_by:
            column = getattr(model, col_name, None)
            if column:
                select_columns.append(column)

        for col_name, agg_func in aggregate.items():
            column = getattr(model, col_name, None)
            if column:
                if agg_func == "count":
                    select_columns.append(func.count(column).label(f"{col_name}_count"))
                elif agg_func == "sum":
                    select_columns.append(func.sum(column).label(f"{col_name}_sum"))
                elif agg_func == "avg":
                    select_columns.append(func.avg(column).label(f"{col_name}_avg"))
                elif agg_func == "min":
                    select_columns.append(func.min(column).label(f"{col_name}_min"))
                elif agg_func == "max":
                    select_columns.append(func.max(column).label(f"{col_name}_max"))

        query = db.query(*select_columns)

        # Apply ALL filters (including operator filters) to the aggregation query
        query = _apply_filters(query, model, filters)

        for col_name in group_by:
            column = getattr(model, col_name, None)
            if column:
                query = query.group_by(column)

        results = query.limit(limit).all()

        # Convert results to dict
        data = []
        for row in results:
            row_dict = {}
            for i, col_name in enumerate(group_by):
                value = row[i]
                if hasattr(value, "value"):
                    value = value.value
                row_dict[col_name] = value

            for j, (col_name, agg_func) in enumerate(aggregate.items()):
                row_dict[f"{col_name}_{agg_func}"] = float(row[len(group_by) + j] or 0)
            data.append(row_dict)

        return {"data": data, "grouped": True}

    # Regular query (no aggregation)
    query = db.query(model)
    query = _apply_filters(query, model, filters)

    total = query.count()
    records = query.limit(limit).all()

    data = []
    for record in records:
        row = {}
        for column in inspect(model).mapper.column_attrs:
            value = getattr(record, column.key)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif hasattr(value, "value"):
                value = value.value
            row[column.key] = value
        data.append(row)

    return {"total": total, "limit": limit, "data": data, "grouped": False}
