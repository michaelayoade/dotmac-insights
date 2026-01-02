---
name: performance-review
description: Database and query performance optimization skill. Detects N+1 queries, missing indexes, inefficient patterns, and suggests fixes. Invoke with /performance-review [command] or when analyzing slow endpoints.
---

# Performance Review Skill

Analyze and optimize database performance in this FastAPI/SQLAlchemy application.

## Automatic Activation
- Trigger when editing routes, queries, or models that add filters, joins, or ordering.
- Require index checks for new filter/order_by fields.

## Severity Levels
| Severity | Criteria | Action |
|----------|----------|--------|
| Critical | Security flaw, data loss, crash | Must fix before merge |
| High | Incorrect results or broken core behavior | Should fix |
| Medium | Edge-case, performance, or maintainability risk | Consider fixing |
| Low | Style or minor improvement | Optional |

## Commands

### `/performance-review scan [file_or_module]`
Scan code for performance anti-patterns.

**What I detect:**

| Issue | Severity | Pattern |
|-------|----------|---------|
| N+1 Query | Critical | Loop with lazy-loaded relationships |
| Missing Index | High | Filter/order on non-indexed column |
| Select All | Medium | `query.all()` without limit |
| Eager Load Missing | Medium | Relationship access without `joinedload`/`selectinload` |
| Count + Query | Medium | Separate `.count()` then `.all()` on same query |
| In-Memory Filter | Low | Python filtering after fetching all rows |

**Output format (standardized):**
```
## Performance Scan: [target]

### Findings
- [Severity][file:line] Issue summary + impact

### Risks
- [Perf risk and scale impact]

### Fixes
- [Index/eager-load/pagination changes]

### Tests
- [Bench or regression checks]
```

---

### `/performance-review n+1 [file]`
Deep scan for N+1 query patterns.

**Detection patterns:**
```python
# ANTI-PATTERN 1: Loop accessing relationship
for order in orders:
    print(order.customer.name)  # N+1! Each iteration queries customer

# ANTI-PATTERN 2: List comprehension with relationship
[item.category.name for item in items]  # N+1!

# ANTI-PATTERN 3: Serialization accessing relationships
{"customer": invoice.customer.name}  # N+1 in loop!
```

**Fix patterns:**
```python
# FIX 1: Use joinedload for single relationships
from sqlalchemy.orm import joinedload
orders = db.query(Order).options(joinedload(Order.customer)).all()

# FIX 2: Use selectinload for collections
from sqlalchemy.orm import selectinload
orders = db.query(Order).options(selectinload(Order.items)).all()

# FIX 3: Chain for nested relationships
db.query(Invoice).options(
    joinedload(Invoice.customer),
    selectinload(Invoice.lines).joinedload(InvoiceLine.product)
).all()
```

---

### `/performance-review indexes [model_or_table]`
Analyze index coverage for a model or across the schema.

**What I check:**
1. Foreign keys without indexes
2. Columns used in `filter()` without indexes
3. Columns used in `order_by()` without indexes
4. Composite index opportunities
5. Partial index candidates (PostgreSQL)

**Output:**
```sql
-- Recommended indexes for [Model]

-- High priority: FK without index
CREATE INDEX ix_invoices_customer_id ON invoices(customer_id);

-- Medium: Frequently filtered column
CREATE INDEX ix_invoices_status ON invoices(status);

-- Composite: Common filter combination
CREATE INDEX ix_invoices_status_date ON invoices(status, invoice_date);

-- Partial: Status-specific queries
CREATE INDEX ix_invoices_pending ON invoices(invoice_date)
WHERE status = 'pending';
```

---

### `/performance-review query [endpoint_or_function]`
Analyze query efficiency for a specific endpoint.

**Analysis includes:**
1. Number of queries executed
2. Query patterns (are they optimized?)
3. Relationship loading strategy
4. Pagination efficiency
5. Suggested rewrites

**Example output:**
```
## Query Analysis: GET /invoices

### Current Behavior
- Queries executed: 1 + N (N+1 pattern detected)
- Relationships accessed: customer, lines
- Loading strategy: Lazy (default)

### Recommended Changes
1. Add eager loading:
   query.options(
       joinedload(Invoice.customer),
       selectinload(Invoice.lines)
   )

2. Use subquery for count:
   total = db.query(func.count(Invoice.id)).filter(...).scalar()

### Expected Improvement
- Queries: 1+N → 2-3 (fixed)
- Estimated speedup: 5-10x for 100 records
```

---

### `/performance-review slow`
Find potentially slow endpoints across the codebase.

**Heuristics:**
- Endpoints with `query.all()` without limit
- Multiple queries in single endpoint
- Large object serialization
- Missing pagination on list endpoints
- Complex joins without indexes

---

### `/performance-review model [ModelName]`
Analyze a SQLAlchemy model for performance issues.

**Checks:**
1. Index coverage on commonly queried fields
2. Relationship loading defaults
3. Column types (appropriate sizes)
4. Composite primary key efficiency
5. Polymorphic configurations

---

## Quick Reference

### Eager Loading Cheat Sheet

| Scenario | Strategy | Code |
|----------|----------|------|
| Single parent | `joinedload` | `.options(joinedload(Order.customer))` |
| Collection | `selectinload` | `.options(selectinload(Order.items))` |
| Nested single | Chain joinedload | `.options(joinedload(A.b).joinedload(B.c))` |
| Nested collection | Mixed | `.options(selectinload(A.bs).joinedload(B.c))` |
| Multiple roots | Multiple options | `.options(joinedload(A.b), selectinload(A.cs))` |
| Conditional | `contains_eager` | After explicit join |

### Index Patterns

```python
# Single column index
class Invoice(Base):
    status: Mapped[str] = mapped_column(String(50), index=True)

# Composite index in __table_args__
__table_args__ = (
    Index('ix_invoice_status_date', 'status', 'invoice_date'),
)

# Partial index (PostgreSQL)
__table_args__ = (
    Index('ix_invoice_pending', 'invoice_date',
          postgresql_where=text("status = 'pending'")),
)
```

## Required Checks
- N+1 risks and relationship loading strategy.
- Index coverage for filter/order_by fields.
- Pagination on list endpoints.

### Query Optimization Patterns

```python
# BAD: Count then query (2 full scans)
total = query.count()
items = query.offset(offset).limit(limit).all()

# GOOD: Use window function or separate count query
from sqlalchemy import func
total = db.query(func.count(Item.id)).filter(...).scalar()
items = db.query(Item).filter(...).offset(offset).limit(limit).all()

# BAD: Load all then filter in Python
items = db.query(Item).all()
active = [i for i in items if i.status == 'active']

# GOOD: Filter in database
active = db.query(Item).filter(Item.status == 'active').all()

# BAD: Fetch all columns when only need few
items = db.query(Item).all()  # Loads all columns

# GOOD: Select specific columns
items = db.query(Item.id, Item.name).all()
```

### Common N+1 Fixes in This Codebase

```python
# Invoice with customer (accounting module)
db.query(Invoice).options(
    joinedload(Invoice.customer),
    joinedload(Invoice.contact),
).filter(...)

# Expense claim with lines (expenses module)
db.query(ExpenseClaim).options(
    selectinload(ExpenseClaim.lines)
).filter(...)

# Ticket with messages (support module)
db.query(Ticket).options(
    selectinload(Ticket.messages),
    joinedload(Ticket.assigned_to)
).filter(...)
```

## Anti-Patterns to Avoid

### 1. Query in Loop
```python
# BAD
for order_id in order_ids:
    order = db.query(Order).get(order_id)  # N queries!

# GOOD
orders = db.query(Order).filter(Order.id.in_(order_ids)).all()
order_map = {o.id: o for o in orders}
```

### 2. Lazy Relationship in Serialization
```python
# BAD - N+1 in list comprehension
return [{"customer": inv.customer.name} for inv in invoices]

# GOOD - Eager load first
invoices = db.query(Invoice).options(joinedload(Invoice.customer)).all()
return [{"customer": inv.customer.name} for inv in invoices]
```

### 3. Unbounded Queries
```python
# BAD - Could return millions of rows
items = db.query(Item).all()

# GOOD - Always paginate
items = db.query(Item).limit(100).all()
```

### 4. String Concatenation in Queries
```python
# BAD - SQL injection risk AND no query plan caching
db.execute(f"SELECT * FROM items WHERE name = '{name}'")

# GOOD - Parameterized query
db.query(Item).filter(Item.name == name)
```

## Automatic Activation

This skill activates automatically when:
- Reviewing code with database queries
- Asked about "slow", "performance", "optimize"
- Detecting patterns like `.all()` in loops
- Analyzing endpoints that access relationships

## Performance Severity Levels

| Level | Criteria | Example |
|-------|----------|---------|
| Critical | O(N) queries, production impact | N+1 on list endpoint |
| High | Missing index on filtered FK | `filter(Invoice.customer_id == x)` no index |
| Medium | Suboptimal but bounded | Count + query separate |
| Low | Minor inefficiency | Select all columns when few needed |

## Integration with This Codebase

**Models location:** `app/models/`
**Common relationships to check:**
- `Invoice.customer`, `Invoice.contact`, `Invoice.lines`
- `ExpenseClaim.lines`, `ExpenseClaim.employee`
- `Ticket.messages`, `Ticket.assigned_to`
- `Employee.department`, `Employee.reports_to`
- `Order.items`, `Order.customer`

**Existing eager loading patterns:**
- `selectinload` used for collections (lines, messages, items)
- `joinedload` used for single relationships (customer, employee)
