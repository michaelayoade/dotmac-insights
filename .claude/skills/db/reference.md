# Database Reference - DotMac BOS

## SQLAlchemy 2.0 Patterns

### Base Model Template
```python
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List

from sqlalchemy import String, ForeignKey, Numeric, Enum as SQLEnum, DateTime, Boolean, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, SoftDeleteMixin


class MyStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MyModel(SoftDeleteMixin, Base):
    __tablename__ = "my_models"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Required string field
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Optional string field
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Enum field with default
    status: Mapped[MyStatus] = mapped_column(SQLEnum(MyStatus), default=MyStatus.DRAFT)

    # Boolean with default
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Decimal for money
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))
    tax_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)

    # Integer field
    quantity: Mapped[int] = mapped_column(default=1)
    sort_order: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Foreign key with relationship (required)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    customer: Mapped["Customer"] = relationship(foreign_keys=[customer_id])

    # Foreign key with relationship (optional)
    assigned_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    assigned_to: Mapped[Optional["User"]] = relationship(foreign_keys=[assigned_to_id])

    # One-to-many relationship (children)
    items: Mapped[List["MyModelItem"]] = relationship(back_populates="parent", cascade="all, delete-orphan")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Composite indexes
    __table_args__ = (
        Index('ix_my_models_customer_status', 'customer_id', 'status'),
        Index('ix_my_models_created_at', 'created_at'),
    )


class MyModelItem(Base):
    __tablename__ = "my_model_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("my_models.id", ondelete="CASCADE"), nullable=False, index=True)
    parent: Mapped["MyModel"] = relationship(back_populates="items")

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))
```

---

## SoftDeleteMixin Usage

```python
from app.database import SoftDeleteMixin

class Document(SoftDeleteMixin, Base):
    __tablename__ = "documents"
    # SoftDeleteMixin adds:
    # - is_deleted: bool (default False, indexed)
    # - deleted_at: Optional[datetime]
    # - deleted_by_id: Optional[int] (FK to users)
```

**Soft delete filtering is automatic.** The system filters out soft-deleted rows unless:
```python
# Include deleted records
db.query(Document).execution_options(include_deleted=True).all()
```

---

## Relationship Patterns

### One-to-One
```python
class User(Base):
    profile: Mapped["UserProfile"] = relationship(back_populates="user", uselist=False)

class UserProfile(Base):
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    user: Mapped["User"] = relationship(back_populates="profile")
```

### One-to-Many (Parent has many children)
```python
class Order(Base):
    items: Mapped[List["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    order: Mapped["Order"] = relationship(back_populates="items")
```

### Many-to-Many
```python
# Association table
ticket_tags = Table(
    "ticket_tags",
    Base.metadata,
    Column("ticket_id", ForeignKey("tickets.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

class Ticket(Base):
    tags: Mapped[List["Tag"]] = relationship(secondary=ticket_tags, back_populates="tickets")

class Tag(Base):
    tickets: Mapped[List["Ticket"]] = relationship(secondary=ticket_tags, back_populates="tags")
```

### Self-Referential (Hierarchy)
```python
class Category(Base):
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"), nullable=True, index=True)
    parent: Mapped[Optional["Category"]] = relationship(back_populates="children", remote_side="Category.id")
    children: Mapped[List["Category"]] = relationship(back_populates="parent")
```

---

## Alembic Migration Patterns

### Create Table
```python
def upgrade():
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('status', sa.Enum('active', 'paused', 'cancelled', name='subscriptionstatus'), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_subscriptions_id', 'subscriptions', ['id'])
    op.create_index('ix_subscriptions_customer_id', 'subscriptions', ['customer_id'])

def downgrade():
    op.drop_index('ix_subscriptions_customer_id', 'subscriptions')
    op.drop_index('ix_subscriptions_id', 'subscriptions')
    op.drop_table('subscriptions')
    sa.Enum(name='subscriptionstatus').drop(op.get_bind())
```

### Add Column
```python
def upgrade():
    op.add_column('invoices', sa.Column('discount_amount', sa.Numeric(15, 2), nullable=True))

def downgrade():
    op.drop_column('invoices', 'discount_amount')
```

### Add Index
```python
def upgrade():
    op.create_index('ix_invoices_customer_status', 'invoices', ['customer_id', 'status'])

def downgrade():
    op.drop_index('ix_invoices_customer_status', 'invoices')
```

### Add Foreign Key
```python
def upgrade():
    op.add_column('orders', sa.Column('warehouse_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_orders_warehouse', 'orders', 'warehouses', ['warehouse_id'], ['id'])
    op.create_index('ix_orders_warehouse_id', 'orders', ['warehouse_id'])

def downgrade():
    op.drop_index('ix_orders_warehouse_id', 'orders')
    op.drop_constraint('fk_orders_warehouse', 'orders', type_='foreignkey')
    op.drop_column('orders', 'warehouse_id')
```

### Rename Column
```python
def upgrade():
    op.alter_column('customers', 'phone', new_column_name='phone_number')

def downgrade():
    op.alter_column('customers', 'phone_number', new_column_name='phone')
```

### Data Migration
```python
def upgrade():
    # Add new column
    op.add_column('invoices', sa.Column('status_v2', sa.String(50), nullable=True))

    # Migrate data
    connection = op.get_bind()
    connection.execute(sa.text("""
        UPDATE invoices
        SET status_v2 = CASE
            WHEN status = 0 THEN 'draft'
            WHEN status = 1 THEN 'sent'
            WHEN status = 2 THEN 'paid'
            ELSE 'unknown'
        END
    """))

    # Make non-nullable
    op.alter_column('invoices', 'status_v2', nullable=False)

def downgrade():
    op.drop_column('invoices', 'status_v2')
```

---

## Redis Caching Patterns

### Using the @cached Decorator
```python
from app.cache import cached

@router.get("/dashboard/stats")
@cached(prefix="dashboard_stats", ttl="medium")
async def get_dashboard_stats(
    company_id: int,
    date_from: date,
    date_to: date,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    # Cache key is auto-generated from function args
    # Returns cached result if available
    return expensive_computation()
```

### Manual Caching
```python
from app.cache import get_redis_client

async def get_or_compute_value(key: str) -> Any:
    redis = await get_redis_client()
    if redis:
        cached = await redis.get(key)
        if cached:
            return json.loads(cached)

    # Compute value
    result = expensive_computation()

    # Cache it
    if redis:
        await redis.setex(key, 300, json.dumps(result))

    return result
```

### Cache Invalidation
```python
from app.cache import get_redis_client

async def invalidate_customer_cache(customer_id: int):
    redis = await get_redis_client()
    if redis:
        # Delete specific key
        await redis.delete(f"analytics:customer:{customer_id}")

        # Delete pattern (use with caution)
        keys = await redis.keys(f"analytics:customer:{customer_id}:*")
        if keys:
            await redis.delete(*keys)
```

---

## Common Query Patterns

### Pagination
```python
def list_items(
    db: Session,
    limit: int = 100,
    offset: int = 0,
    filters: dict = None
) -> Dict[str, Any]:
    query = db.query(Item)

    if filters:
        if filters.get("status"):
            query = query.filter(Item.status == filters["status"])
        if filters.get("search"):
            query = query.filter(Item.name.ilike(f"%{filters['search']}%"))

    total = query.count()
    items = query.order_by(Item.created_at.desc()).offset(offset).limit(limit).all()

    return {"total": total, "limit": limit, "offset": offset, "data": items}
```

### Eager Loading
```python
from sqlalchemy.orm import joinedload, selectinload

# Single relationship
query = db.query(Invoice).options(joinedload(Invoice.customer))

# Collection relationship
query = db.query(Order).options(selectinload(Order.items))

# Nested relationships
query = db.query(Invoice).options(
    joinedload(Invoice.customer),
    selectinload(Invoice.lines).joinedload(InvoiceLine.product)
)
```

### Aggregations
```python
from sqlalchemy import func

# Count
count = db.query(func.count(Invoice.id)).filter(Invoice.status == "paid").scalar()

# Sum
total = db.query(func.sum(Invoice.amount)).filter(Invoice.customer_id == customer_id).scalar() or 0

# Group by
results = db.query(
    Invoice.status,
    func.count(Invoice.id).label("count"),
    func.sum(Invoice.amount).label("total")
).group_by(Invoice.status).all()
```

### Subqueries
```python
from sqlalchemy import select

# Subquery for latest invoice per customer
latest_invoice = (
    select(Invoice.customer_id, func.max(Invoice.created_at).label("max_date"))
    .group_by(Invoice.customer_id)
    .subquery()
)

# Use in main query
query = db.query(Invoice).join(
    latest_invoice,
    (Invoice.customer_id == latest_invoice.c.customer_id) &
    (Invoice.created_at == latest_invoice.c.max_date)
)
```

---

## Troubleshooting

### Migration Conflicts
```bash
# Check for multiple heads
alembic heads

# If multiple heads exist, merge them
alembic merge heads -m "merge heads"

# Then upgrade
alembic upgrade head
```

### Reset Development Database
```bash
# Drop and recreate (DESTRUCTIVE)
docker-compose down -v db
docker-compose up -d db
alembic upgrade head
```

### Debug Queries
```python
# Print SQL
from sqlalchemy import event

@event.listens_for(engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    print(f"SQL: {statement}")
    print(f"Params: {parameters}")
```

### Check Connection Pool
```python
print(f"Pool size: {engine.pool.size()}")
print(f"Checked out: {engine.pool.checkedout()}")
print(f"Overflow: {engine.pool.overflow()}")
```
