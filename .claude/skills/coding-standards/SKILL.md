---
name: coding-standards
description: Enforces DotMac BOS coding standards when writing or modifying Python code. Use automatically when creating routes, models, schemas, or any Python code in this FastAPI project.
---

# DotMac BOS Coding Standards

Apply these standards to all Python code written in this project.

## Standard Output Format
When reporting implementation guidance or review feedback, use:
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

## Core Rules
- **Reference first**: Read `reference.md` before making Python changes to confirm patterns and file organization.
- **Auth**: Always add `dependencies=[Depends(Require("module:read"))]` or `dependencies=[Depends(Require("module:write"))]`.
- **Responses**: Return plain dicts; list endpoints must include `total`, `limit`, `offset`, `data`.
- **Serialization**: Enums use `.value`; Decimals use `float(...)`; datetimes use `.isoformat()`.
- **Pagination**: `limit: int = Query(default=100, le=500)` and `offset: int = 0`.
- **Errors**: 404 `Resource not found`, 400 `Invalid value: {value}`, 403 `Permission denied`.
- **Helpers**: Use `decimal_or_default`, `csv_response`, `now` where applicable.
- **Models**: SQLAlchemy 2.0 typed `Mapped[...]`; index foreign keys; explicit `foreign_keys` in relationships; use `SoftDeleteMixin` where needed.

## References
- Use `reference.md` for full route templates, CRUD patterns, and file organization examples.

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
