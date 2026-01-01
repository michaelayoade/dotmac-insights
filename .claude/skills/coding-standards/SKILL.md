---
name: coding-standards
description: Enforces DotMac BOS coding standards when writing or modifying Python code. Use automatically when creating routes, models, schemas, or any Python code in this FastAPI project.
---

# DotMac BOS Coding Standards

Apply these standards to ALL code written in this project.

## Quick Reference

### API Routes

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional

from app.database import get_db
from app.auth import Require

router = APIRouter()

@router.get("/items", dependencies=[Depends(Require("module:read"))])
def list_items(
    search: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List items with filtering."""
    query = db.query(Item)

    if search:
        query = query.filter(Item.name.ilike(f"%{search}%"))
    if status:
        try:
            status_enum = ItemStatus(status)
            query = query.filter(Item.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    total = query.count()
    items = query.order_by(Item.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": item.id,
                "name": item.name,
                "status": item.status.value if item.status else None,
                "amount": float(item.amount) if item.amount else None,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in items
        ],
    }
```

### Get Single Item

```python
@router.get("/items/{item_id}", dependencies=[Depends(Require("module:read"))])
def get_item(item_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get item detail."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    return {
        "id": item.id,
        "name": item.name,
        # ... all fields
    }
```

### Create/Update Patterns

```python
@router.post("/items", dependencies=[Depends(Require("module:write"))])
def create_item(payload: ItemCreate, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Create a new item."""
    item = Item(
        name=payload.name,
        status=payload.status or ItemStatus.ACTIVE,
        amount=decimal_or_default(payload.amount),
    )
    db.add(item)
    db.commit()
    return get_item(item.id, db)

@router.patch("/items/{item_id}", dependencies=[Depends(Require("module:write"))])
def update_item(item_id: int, payload: ItemUpdate, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Update an item."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(item, field, value)

    db.commit()
    return get_item(item_id, db)
```

## Required Patterns

### Authentication
- ALWAYS use `dependencies=[Depends(Require("scope:action"))]` for protected routes
- Scopes: `module:read`, `module:write` (e.g., `hr:read`, `books:write`)

### Response Format
- Return `Dict[str, Any]` (not Pydantic response models)
- List endpoints: `{"total": N, "limit": N, "offset": N, "data": [...]}`
- Enum values: `item.status.value if item.status else None`
- Decimals: `float(item.amount) if item.amount else None`
- Dates: `item.created_at.isoformat() if item.created_at else None`

### Error Handling
- 404: `raise HTTPException(status_code=404, detail="Resource not found")`
- 400: `raise HTTPException(status_code=400, detail=f"Invalid value: {value}")`
- 403: `raise HTTPException(status_code=403, detail="Permission denied")`

### Pagination
- Always use: `limit: int = Query(default=100, le=500), offset: int = 0`

### Helpers
- Use `from .helpers import decimal_or_default` for Decimal fields
- Use `from .helpers import csv_response` for CSV exports
- Use `from .helpers import now` for UTC datetime

## Pydantic Schemas

```python
class ItemCreate(BaseModel):
    name: str  # Required fields have no default
    description: Optional[str] = None
    amount: Optional[Decimal] = Decimal("0")
    status: Optional[ItemStatus] = ItemStatus.ACTIVE

class ItemUpdate(BaseModel):
    name: Optional[str] = None  # All optional for PATCH
    description: Optional[str] = None
    amount: Optional[Decimal] = None
    status: Optional[ItemStatus] = None
```

## SQLAlchemy Models

```python
from sqlalchemy import String, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    status: Mapped[ItemStatus] = mapped_column(Enum(ItemStatus), default=ItemStatus.ACTIVE)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Foreign keys with dual pattern
    category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"), nullable=True)
    category_rel: Mapped[Optional["Category"]] = relationship(foreign_keys=[category_id])
```

## File Organization

```
app/api/module_name/
├── __init__.py          # Router aggregation
├── schemas.py           # Pydantic models (if complex)
├── crud.py              # Basic CRUD operations
├── feature_a.py         # Feature-specific routes
└── helpers.py           # Shared utilities
```

Router aggregation in `__init__.py`:
```python
from fastapi import APIRouter
from .crud import router as crud_router
from .feature_a import router as feature_a_router

router = APIRouter()
router.include_router(crud_router)
router.include_router(feature_a_router)
```

## Import Order

1. `from __future__ import annotations`
2. Standard library
3. Third-party (fastapi, sqlalchemy, pydantic)
4. Local imports

```python
from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Optional, List
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require
from app.models.module import Item, ItemStatus
from .helpers import decimal_or_default
```

## Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Models | PascalCase | `Employee`, `SalarySlip` |
| Tables | snake_case plural | `employees`, `salary_slips` |
| Fields | snake_case | `employee_name`, `is_active` |
| Routes | kebab-case | `/salary-slips`, `/job-openings` |
| Scopes | module:action | `hr:read`, `books:write` |
| Functions | snake_case | `list_employees`, `get_employee` |
| Schemas | PascalCase+Suffix | `EmployeeCreate`, `EmployeeUpdate` |

## Don'ts

- DON'T use Pydantic response_model for API responses
- DON'T forget null checks on optional fields
- DON'T hardcode IDs or values
- DON'T skip authentication on write endpoints
- DON'T use `datetime.now()` - use `datetime.utcnow()` or `now()` helper
- DON'T return raw model objects - always serialize to dict
