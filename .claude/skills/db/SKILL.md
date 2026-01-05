---
name: db
description: Database, migrations, and Redis management skill. Create models, run Alembic migrations, manage Redis caching, and troubleshoot database issues. Invoke with /db [command].
---

# Database Management Skill

Manage PostgreSQL, SQLAlchemy models, Alembic migrations, and Redis caching in this FastAPI application.

## Standard Output Format
When reporting analysis or recommendations, use:
```
### Findings
- [Severity][file:line] Issue summary + impact

### Risks
- [What could break or regress]

### Fixes
- [Concrete fix or mitigation]

### Tests
- [Verification steps]
```

## Severity Levels
| Severity | Criteria | Action |
|----------|----------|--------|
| Critical | Security flaw, data loss, crash | Must fix before merge |
| High | Incorrect results or broken core behavior | Should fix |
| Medium | Edge-case, performance, or maintainability risk | Consider fixing |
| Low | Style or minor improvement | Optional |

## Commands

### `/db model [ModelName]`
Create a new SQLAlchemy model with proper patterns.

**Output:**
- Model class following project conventions
- Enum classes if needed
- Migration command to run
- Model registration in `app/models/__init__.py`

**Example:** See `reference.md` for the full SQLAlchemy 2.0 model template.

---

### `/db migrate [description]`
Create a new Alembic migration.

**Steps I perform:**
1. Verify model is imported in `app/models/__init__.py`
2. Generate migration with autogenerate
3. Review migration for correctness
4. Show commands to apply

**Commands:**
```bash
# Generate migration
alembic revision --autogenerate -m "add subscriptions table"

# Apply migration
alembic upgrade head

# Check current revision
alembic current

# Show migration history
alembic history --verbose
```

---

### `/db rollback [steps]`
Rollback migrations safely.

**Commands:**
```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade abc123

# Rollback all (DANGEROUS)
alembic downgrade base

# Show what will be rolled back
alembic history --indicate-current
```

**Safety checks:**
- Warn about data loss in production
- Show affected tables
- Recommend backup first

---

### `/db status`
Show database and migration status.

**Checks performed:**
1. Database connection health
2. Current migration revision
3. Pending migrations
4. Table count and sizes
5. Redis connection status

```bash
# Check current migration
alembic current

# Check for pending migrations
alembic check

# Show heads
alembic heads
```

---

### `/db seed [module]`
Generate seed data for development/testing.

**Patterns:**
```python
# Create test data
from app.database import SessionLocal
from app.models import Customer, Invoice

db = SessionLocal()

customer = Customer(
    name="Test Customer",
    email="test@example.com",
    status=CustomerStatus.ACTIVE,
)
db.add(customer)
db.commit()
```

---

### `/db cache [action]`
Manage Redis caching.

**Actions:**
- `status` - Check Redis connection and stats
- `clear [pattern]` - Clear cache by pattern
- `keys [pattern]` - List cache keys
- `add [endpoint]` - Add caching to an endpoint

**Caching pattern in this project:**
```python
from app.cache import cached

@router.get("/analytics")
@cached(prefix="customer_analytics", ttl="medium")  # 300 seconds
async def get_analytics(
    customer_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    # Expensive computation here
    return results
```

**TTL presets:**
- `short`: 60 seconds
- `medium`: 300 seconds (5 min)
- `long`: 900 seconds (15 min)
- `hourly`: 3600 seconds

**Cache commands:**
```bash
# Connect to Redis CLI
docker exec -it dotmac-redis redis-cli

# List analytics keys
KEYS analytics:*

# Clear specific cache
DEL analytics:customer_analytics:abc123

# Clear all analytics cache
redis-cli KEYS "analytics:*" | xargs redis-cli DEL

# Check memory usage
INFO memory
```

---

### `/db index [model_or_table]`
Analyze and recommend indexes.

**What I check:**
1. Foreign keys without indexes
2. Columns in WHERE clauses
3. Columns in ORDER BY
4. Composite index opportunities

**Adding indexes in models:**
```python
from sqlalchemy import Index

class Invoice(Base):
    __tablename__ = "invoices"

    # Single column index via mapped_column
    status: Mapped[str] = mapped_column(String(50), index=True)

    # Composite indexes via __table_args__
    __table_args__ = (
        Index('ix_invoice_customer_status', 'customer_id', 'status'),
        Index('ix_invoice_date_status', 'invoice_date', 'status'),
    )
```

**Adding indexes via migration:**
```python
def upgrade():
    op.create_index('ix_invoices_customer_status', 'invoices', ['customer_id', 'status'])

def downgrade():
    op.drop_index('ix_invoices_customer_status', 'invoices')
```

---

### `/db troubleshoot [issue]`
Diagnose common database issues.

**Common issues:**

| Issue | Diagnosis | Solution |
|-------|-----------|----------|
| Connection refused | PostgreSQL not running | `docker-compose up db` |
| Migration conflict | Multiple heads | `alembic merge heads` |
| Locked table | Long transaction | Check `pg_stat_activity` |
| Slow query | Missing index | Run `/db index` |
| Redis timeout | Connection pool exhausted | Check `REDIS_URL` config |
| Alembic offline | Wrong DATABASE_URL | Check `.env` file |

## References
- `reference.md` covers SQLAlchemy patterns, relationships, and Alembic examples.

**Diagnostic queries:**
```sql
-- Check active connections
SELECT * FROM pg_stat_activity WHERE datname = 'dotmac_insights';

-- Find blocking queries
SELECT blocked_locks.pid AS blocked_pid,
       blocking_locks.pid AS blocking_pid,
       blocked_activity.query AS blocked_query
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
WHERE NOT blocked_locks.granted;

-- Table sizes
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
```

---

## Project-Specific Configuration

### Database Connection
```
Location: app/config.py
Environment variable: DATABASE_URL
Format: postgresql+psycopg://user:password@host:port/database
```

### Models Location
```
app/models/           # All model files
app/models/__init__.py  # Central exports (MUST register new models here)
```

### Migration Location
```
alembic/              # Alembic configuration
alembic/versions/     # Migration files (153 existing)
alembic.ini           # Alembic config
alembic/env.py        # Migration environment
```

### Redis Configuration
```
Location: app/config.py
Environment variable: REDIS_URL
Format: redis://host:port/db
Cache utilities: app/cache.py
```

### Docker Services
```yaml
# docker-compose.yml
db:
  image: postgres:15-alpine
  ports: 5432:5432

redis:
  image: redis:7-alpine
  ports: 6379:6379
```

---

## Quick Reference

### Common Commands
```bash
# Start services
docker-compose up -d db redis

# Run migrations
alembic upgrade head

# Create migration
alembic revision --autogenerate -m "description"

# Check migration status
alembic current

# Rollback
alembic downgrade -1

# Connect to database
docker exec -it dotmac-db psql -U dotmac -d dotmac_insights

# Connect to Redis
docker exec -it dotmac-redis redis-cli
```

### Model Conventions
- Use `SoftDeleteMixin` for soft-deletable entities
- Always index foreign keys
- Use `Numeric(15, 2)` for monetary values
- Use `Enum` for status fields
- Include `created_at` and `updated_at` timestamps

### Session Patterns
```python
# In routes (dependency injection)
from app.database import get_db
db: Session = Depends(get_db)

# In services
class MyService:
    def __init__(self, db: Session):
        self.db = db

# Manual session
from app.database import SessionLocal
db = SessionLocal()
try:
    # operations
    db.commit()
finally:
    db.close()
```

---

## Automatic Activation

This skill activates when:
- User mentions "database", "migration", "alembic", "redis", "cache"
- Creating new models or tables
- Troubleshooting connection issues
- Working with SQLAlchemy queries
- Managing Redis caching
