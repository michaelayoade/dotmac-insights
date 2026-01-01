# Extended Coding Reference

## Advanced Route Patterns

### Action Endpoints (Status Changes)

```python
@router.post("/items/{item_id}/approve", dependencies=[Depends(Require("module:write"))])
def approve_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Approve an item."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if item.status != ItemStatus.PENDING:
        raise HTTPException(status_code=400, detail="Only pending items can be approved")

    item.status = ItemStatus.APPROVED
    item.approved_by_id = current_user.id
    item.approved_at = now()
    db.commit()
    return get_item(item_id, db)
```

### Bulk Actions

```python
class BulkActionPayload(BaseModel):
    ids: List[int]

@router.post("/items/bulk/approve", dependencies=[Depends(Require("module:write"))])
def bulk_approve_items(
    payload: BulkActionPayload,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Bulk approve items."""
    updated = 0
    for item_id in payload.ids:
        item = db.query(Item).filter(Item.id == item_id).first()
        if item and item.status == ItemStatus.PENDING:
            item.status = ItemStatus.APPROVED
            updated += 1
    db.commit()
    return {"updated": updated, "requested": len(payload.ids)}
```

### CSV Export

```python
@router.get("/items/export", dependencies=[Depends(Require("module:read"))])
def export_items(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Export items to CSV."""
    query = db.query(Item)
    if status:
        query = query.filter(Item.status == ItemStatus(status))

    rows = [["id", "name", "status", "amount", "created_at"]]
    for item in query.order_by(Item.created_at.desc()).all():
        rows.append([
            str(item.id),
            item.name,
            item.status.value if item.status else "",
            str(item.amount) if item.amount else "",
            item.created_at.isoformat() if item.created_at else "",
        ])
    return csv_response(rows, "items.csv")
```

### Summary/Stats Endpoint

```python
@router.get("/items/summary", dependencies=[Depends(Require("module:read"))])
def items_summary(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get items summary by status."""
    results = db.query(
        Item.status, func.count(Item.id)
    ).group_by(Item.status).all()

    return {"status_counts": status_counts(results)}
```

## Child Resource Patterns

### Nested CRUD (Parent-Child)

```python
@router.get("/orders/{order_id}/items", dependencies=[Depends(Require("sales:read"))])
def list_order_items(
    order_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List items for an order."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return {
        "order_id": order_id,
        "data": [
            {
                "id": item.id,
                "product_name": item.product_name,
                "quantity": item.quantity,
                "price": float(item.price) if item.price else 0,
            }
            for item in order.items
        ],
    }


@router.post("/orders/{order_id}/items", dependencies=[Depends(Require("sales:write"))])
def add_order_item(
    order_id: int,
    payload: OrderItemCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add item to order."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    item = OrderItem(
        order_id=order_id,
        product_name=payload.product_name,
        quantity=payload.quantity,
        price=decimal_or_default(payload.price),
    )
    db.add(item)
    db.commit()
    return get_order(order_id, db)  # Return full order
```

### Replace Child Collection

```python
@router.patch("/orders/{order_id}", dependencies=[Depends(Require("sales:write"))])
def update_order(
    order_id: int,
    payload: OrderUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update order, optionally replacing items."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    update_data = payload.model_dump(exclude_unset=True)
    items_data = update_data.pop("items", None)

    # Update scalar fields
    for field, value in update_data.items():
        if value is not None:
            setattr(order, field, value)

    # Replace child collection if provided
    if items_data is not None:
        db.query(OrderItem).filter(OrderItem.order_id == order.id).delete(synchronize_session=False)
        for idx, item in enumerate(items_data):
            db.add(OrderItem(
                order_id=order.id,
                product_name=item.get("product_name"),
                quantity=item.get("quantity", 1),
                price=decimal_or_default(item.get("price")),
                idx=idx,
            ))

    db.commit()
    return get_order(order_id, db)
```

## Complex Query Patterns

### Date Range + Multiple Filters

```python
@router.get("/reports/sales", dependencies=[Depends(Require("reports:read"))])
def sales_report(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    customer_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Sales report with filters."""
    query = db.query(Order)

    if from_date:
        query = query.filter(Order.order_date >= from_date)
    if to_date:
        query = query.filter(Order.order_date <= to_date)
    if customer_id:
        query = query.filter(Order.customer_id == customer_id)
    if status:
        query = query.filter(Order.status == OrderStatus(status))

    orders = query.order_by(Order.order_date.desc()).all()

    total_amount = sum(o.total or Decimal(0) for o in orders)

    return {
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "total_orders": len(orders),
        "total_amount": float(total_amount),
        "data": [serialize_order(o) for o in orders],
    }
```

### OR Conditions for Search

```python
from sqlalchemy import or_

if search:
    search_term = f"%{search}%"
    query = query.filter(
        or_(
            Item.name.ilike(search_term),
            Item.description.ilike(search_term),
            Item.code.ilike(search_term),
        )
    )
```

### Eager Loading Relationships

```python
from sqlalchemy.orm import joinedload

query = db.query(Order).options(
    joinedload(Order.customer),
    joinedload(Order.items),
)
```

## Audit Trail Pattern

```python
from app.services.audit_logger import AuditLogger, serialize_for_audit

@router.delete("/items/{item_id}", dependencies=[Depends(Require("module:write"))])
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete an item with audit logging."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Audit log
    audit = AuditLogger(db)
    audit.log_delete(
        doctype="item",
        document_id=item.id,
        user_id=current_user.id,
        document_name=item.name,
        before_data=serialize_for_audit(item),
    )

    db.delete(item)
    db.commit()
    return {"message": "Item deleted", "id": item_id}
```

## Router Aggregation Pattern

### Module __init__.py

```python
"""
Module Router

Aggregates all sub-modules.
"""

from fastapi import APIRouter

from .items import router as items_router
from .categories import router as categories_router
from .reports import router as reports_router

router = APIRouter()

router.include_router(items_router)
router.include_router(categories_router)
router.include_router(reports_router, prefix="/reports")
```

### API Root __init__.py

```python
from fastapi import APIRouter

from .hr import router as hr_router
from .sales import router as sales_router
from .projects import router as projects_router

api_router = APIRouter()

api_router.include_router(hr_router, prefix="/hr", tags=["HR"])
api_router.include_router(sales_router, prefix="/sales", tags=["Sales"])
api_router.include_router(projects_router, prefix="/projects", tags=["Projects"])

# V1 prefix for new clients
api_router.include_router(hr_router, prefix="/v1/hr", tags=["HR"])
```

## Helper Functions

### helpers.py Template

```python
"""
Module Helpers

Common utilities for this module.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, List
import csv
import io

from fastapi.responses import StreamingResponse


def decimal_or_default(val, default: Decimal = Decimal("0")) -> Decimal:
    """Convert value to Decimal or return default."""
    if val is None:
        return default
    return Decimal(str(val))


def now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


def csv_response(rows: List[List[Any]], filename: str) -> StreamingResponse:
    """Return CSV as downloadable file."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def status_counts(results) -> dict:
    """Convert SQLAlchemy group_by results to dict."""
    return {
        (row[0].value if row[0] else "unknown"): int(row[1] or 0)
        for row in results
    }


def validate_date_order(start, end, field: str = "date range"):
    """Validate start <= end."""
    if start and end and start > end:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Invalid {field}: start must be before end")
```

## Enum Patterns

### Definition

```python
import enum

class ItemStatus(enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
```

### Filtering by Enum

```python
if status:
    try:
        status_enum = ItemStatus(status)
        query = query.filter(Item.status == status_enum)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
```

### Serialization

```python
"status": item.status.value if item.status else None
```

## Soft Delete Pattern

### In Routes

```python
@router.delete("/items/{item_id}", dependencies=[Depends(Require("module:write"))])
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Soft delete an item."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.is_deleted = True
    item.deleted_at = now()
    item.deleted_by_id = current_user.id
    db.commit()
    return {"message": "Item deleted", "id": item_id}
```

### Include Deleted in Queries

```python
@router.get("/items", dependencies=[Depends(Require("module:read"))])
def list_items(
    include_deleted: bool = False,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    query = db.query(Item)
    if not include_deleted:
        query = query.filter(Item.is_deleted == False)
    # ...
```
