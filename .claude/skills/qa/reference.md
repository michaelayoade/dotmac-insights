# QA Skill Reference

## Code Review Patterns

### Security Vulnerabilities to Check

#### SQL Injection
```python
# BAD
query = f"SELECT * FROM users WHERE id = {user_id}"
db.execute(query)

# GOOD
db.query(User).filter(User.id == user_id).first()
```

#### Command Injection
```python
# BAD
os.system(f"convert {filename} output.png")

# GOOD
subprocess.run(["convert", filename, "output.png"], check=True)
```

#### Path Traversal
```python
# BAD
file_path = os.path.join(upload_dir, user_filename)

# GOOD
safe_name = secure_filename(user_filename)
file_path = os.path.join(upload_dir, safe_name)
if not file_path.startswith(upload_dir):
    raise ValueError("Invalid path")
```

#### Auth Bypass
```python
# BAD - missing auth
@router.get("/admin/users")
def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()

# GOOD
@router.get("/admin/users", dependencies=[Depends(Require("admin:read"))])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()
```

#### Secrets in Code
```python
# BAD
API_KEY = "sk-1234567890abcdef"

# GOOD
API_KEY = os.environ.get("API_KEY")
```

---

### Logic Errors to Check

#### Off-by-One
```python
# BAD
for i in range(len(items) + 1):  # IndexError on last iteration
    process(items[i])

# GOOD
for i in range(len(items)):
    process(items[i])
```

#### Null/None Checks
```python
# BAD
return user.email.lower()  # AttributeError if user is None

# GOOD
return user.email.lower() if user and user.email else None
```

#### Race Conditions
```python
# BAD - TOCTOU (time-of-check to time-of-use)
if item.quantity > 0:
    # Another request could decrement between check and update
    item.quantity -= 1

# GOOD - atomic operation
result = db.query(Item).filter(
    Item.id == item_id,
    Item.quantity > 0
).update({"quantity": Item.quantity - 1})
if result == 0:
    raise HTTPException(400, "Out of stock")
```

#### Integer Overflow
```python
# BAD - potential overflow in 32-bit systems
total = price * quantity * 1000000

# GOOD - use Decimal for money
from decimal import Decimal
total = Decimal(str(price)) * Decimal(str(quantity))
```

---

### Code Smells

#### Missing Error Handling
```python
# BAD
data = json.loads(request.body)
user = db.query(User).filter(User.id == data["user_id"]).first()
return user.name

# GOOD
try:
    data = json.loads(request.body)
except json.JSONDecodeError:
    raise HTTPException(400, "Invalid JSON")

user_id = data.get("user_id")
if not user_id:
    raise HTTPException(400, "user_id required")

user = db.query(User).filter(User.id == user_id).first()
if not user:
    raise HTTPException(404, "User not found")

return user.name
```

#### N+1 Query
```python
# BAD - N+1 queries
orders = db.query(Order).all()
for order in orders:
    print(order.customer.name)  # Lazy load each customer

# GOOD - eager load
from sqlalchemy.orm import joinedload
orders = db.query(Order).options(joinedload(Order.customer)).all()
```

#### Unbounded Query
```python
# BAD - could return millions of rows
return db.query(LogEntry).all()

# GOOD - always paginate
return db.query(LogEntry).limit(limit).offset(offset).all()
```

---

## Test Generation Patterns

### Pytest Style (This Project)

```python
"""Tests for item CRUD operations."""
import pytest
from decimal import Decimal
from datetime import datetime

from app.models.item import Item, ItemStatus


class TestItemCreate:
    """Tests for item creation."""

    def test_create_item_success(self, db, auth_client):
        """Create item with valid data."""
        response = auth_client.post("/api/items", json={
            "name": "Test Item",
            "amount": "100.00",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Item"
        assert data["id"] is not None

    def test_create_item_missing_name(self, db, auth_client):
        """Reject item without required name."""
        response = auth_client.post("/api/items", json={
            "amount": "100.00",
        })
        assert response.status_code == 422

    def test_create_item_empty_name(self, db, auth_client):
        """Reject item with empty name."""
        response = auth_client.post("/api/items", json={
            "name": "",
            "amount": "100.00",
        })
        assert response.status_code == 400

    def test_create_item_requires_auth(self, db, client):
        """Unauthenticated request rejected."""
        response = client.post("/api/items", json={"name": "Test"})
        assert response.status_code == 401


class TestItemEdgeCases:
    """Edge case tests for items."""

    @pytest.mark.parametrize("name", [
        "A",  # Single character
        "A" * 255,  # Max length
        "Test 🎉 Item",  # Emoji
        "مرحبا",  # Arabic
        "Test\nItem",  # Newline
        "  Padded  ",  # Whitespace
    ])
    def test_create_item_various_names(self, db, auth_client, name):
        """Handle various valid name formats."""
        response = auth_client.post("/api/items", json={"name": name})
        assert response.status_code == 200

    @pytest.mark.parametrize("amount,expected", [
        ("0", Decimal("0")),
        ("0.01", Decimal("0.01")),
        ("999999999.99", Decimal("999999999.99")),
        ("-100.00", Decimal("-100.00")),  # If negatives allowed
    ])
    def test_create_item_amount_boundaries(self, db, auth_client, amount, expected):
        """Handle amount boundary values."""
        response = auth_client.post("/api/items", json={
            "name": "Test",
            "amount": amount,
        })
        assert response.status_code == 200
        assert Decimal(response.json()["amount"]) == expected
```

---

## Edge Case Categories

### String Inputs
```python
edge_cases = [
    "",                          # Empty
    " ",                         # Whitespace only
    "   trimmed   ",             # Needs trimming
    "a",                         # Single char
    "a" * 1000,                  # Very long
    "Hello\x00World",            # Null byte
    "<script>alert(1)</script>", # XSS attempt
    "Robert'); DROP TABLE--",    # SQL injection attempt
    "🎉🎊🎁",                    # Emoji only
    "مرحبا بالعالم",              # RTL text
    "Ω≈ç√∫",                     # Special chars
    "​",                          # Zero-width space
    "ＡＢＣＤＥ",                  # Full-width
]
```

### Numeric Inputs
```python
edge_cases = [
    0,
    1,
    -1,
    0.0,
    0.001,
    -0.001,
    2**31 - 1,      # Max 32-bit signed
    2**31,          # Overflow 32-bit signed
    2**63 - 1,      # Max 64-bit signed
    float('inf'),
    float('-inf'),
    float('nan'),
]
```

### Date/Time Inputs
```python
edge_cases = [
    "2000-01-01",                    # Y2K
    "2038-01-19T03:14:07Z",          # Y2K38 (32-bit Unix)
    "2000-02-29",                    # Leap year
    "2100-02-29",                    # NOT a leap year
    "2024-03-10T02:30:00-05:00",     # DST spring forward (doesn't exist)
    "2024-11-03T01:30:00-05:00",     # DST fall back (ambiguous)
    "1970-01-01T00:00:00Z",          # Unix epoch
    "9999-12-31T23:59:59Z",          # Far future
]
```

### Collection Inputs
```python
edge_cases = [
    [],                              # Empty
    [None],                          # Single None
    [1],                             # Single element
    list(range(10000)),              # Large collection
    [1, 1, 1, 1],                    # All duplicates
    [{"nested": {"deep": "value"}}], # Deeply nested
]
```

---

## Risk Assessment Matrix

### Change Type vs Risk Level

| Change Type | Typical Risk | Rationale |
|-------------|--------------|-----------|
| Add new field (nullable) | LOW | Backward compatible |
| Add new field (required) | HIGH | Breaks existing clients |
| Rename field | HIGH | Breaks all consumers |
| Change field type | CRITICAL | Silent data corruption |
| Add new endpoint | LOW | No existing behavior affected |
| Modify endpoint response | MEDIUM | May break clients |
| Delete endpoint | CRITICAL | Breaks all consumers |
| Add validation | MEDIUM | May reject previously valid input |
| Remove validation | HIGH | May allow invalid data |
| Change business logic | HIGH | Behavior changes |
| Refactor (same behavior) | LOW | If well tested |
| Database migration | HIGH | Data integrity risk |
| Dependency update | MEDIUM | Potential breaking changes |

### Blast Radius Indicators

```
HIGH RISK indicators:
- File is imported by 10+ other files
- Function is called in multiple modules
- Model has 5+ relationships
- Endpoint is used by external systems
- Code is in critical path (auth, payments)

LOW RISK indicators:
- New file with no dependents
- Internal helper function
- Isolated feature
- Well-tested code path
```

---

## Test Plan Template

```markdown
# Test Plan: [Feature Name]

## Overview
[1-2 sentence description]

## Scope
- In scope: [what we're testing]
- Out of scope: [what we're not testing]

## Test Environment
- [ ] Development database seeded
- [ ] Test user accounts created
- [ ] External service mocks configured

## Functional Tests

### Happy Path
- [ ] [Primary use case works]
- [ ] [Expected output is correct]

### Validation
- [ ] Required fields enforced
- [ ] Invalid input rejected with clear error
- [ ] Boundary values handled

### Authorization
- [ ] Unauthenticated access rejected
- [ ] Unauthorized role rejected
- [ ] Authorized role succeeds

### Edge Cases
- [ ] Empty input
- [ ] Maximum size input
- [ ] Special characters
- [ ] Concurrent access

## Integration Tests
- [ ] Database operations commit/rollback correctly
- [ ] External API calls handled
- [ ] Event publishing works

## Security Tests
- [ ] No SQL injection
- [ ] No XSS in output
- [ ] No auth bypass
- [ ] No sensitive data in logs

## Performance Tests
- [ ] Response time under load
- [ ] No N+1 queries
- [ ] Pagination works for large datasets

## Regression Tests
- [ ] Existing functionality unchanged
- [ ] Related features still work

## Sign-off
- [ ] All critical tests pass
- [ ] No blockers remaining
- [ ] Ready for deployment
```

---

## Review Checklist

### Before Approving Any PR

```markdown
## Security
- [ ] No hardcoded secrets
- [ ] Input validation on all user data
- [ ] Auth checks on protected endpoints
- [ ] No SQL/command injection vectors

## Logic
- [ ] Edge cases handled (null, empty, boundaries)
- [ ] Error handling present
- [ ] No obvious bugs

## Performance
- [ ] No N+1 queries
- [ ] Queries are indexed
- [ ] Large datasets paginated

## Testing
- [ ] Tests added for new code
- [ ] Tests pass locally
- [ ] Edge cases tested

## Code Quality
- [ ] Follows project conventions
- [ ] No dead code
- [ ] Clear naming
- [ ] Appropriate comments (not excessive)

## Documentation
- [ ] API changes documented
- [ ] Breaking changes noted
- [ ] Migration steps if needed
```
