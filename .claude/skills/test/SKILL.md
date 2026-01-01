---
name: test
description: Testing skill for generating, running, and analyzing tests. Supports unit, integration, and E2E tests. Invoke with /test [command].
---

# Test Skill

Generate, run, and analyze tests for the DotMAC codebase. Matches existing pytest patterns and conventions.

## Commands

### `/test generate [file_or_function]`
Generate tests for a module, class, or function.

**Process:**
1. Read the target code
2. Analyze existing tests for patterns (`tests/unit/`, `tests/integration/`, `tests/e2e/`)
3. Determine test type (unit, integration, e2e)
4. Generate tests matching project conventions

**Output:** Complete test file or test class ready to use.

**Test Categories Generated:**
- Happy path (valid inputs, expected behavior)
- Edge cases (empty, null, boundaries)
- Error conditions (invalid inputs, exceptions)
- RBAC/auth (permission checks using `auth_client_with_scope`)
- Concurrency (if applicable)

---

### `/test run [pattern]`
Run tests with optional pattern filtering.

**Examples:**
```bash
/test run                           # Run all tests
/test run test_contacts             # Run matching tests
/test run -m accounting             # Run by marker
/test run --unit                    # Run unit tests only
/test run --e2e                     # Run e2e tests only
/test run --failed                  # Run previously failed
```

**Markers Available:**
`critical`, `slow`, `integration`, `e2e`, `accounting`, `crm`, `hr`, `projects`, `support`, `field_service`, `inbox`, `inventory`, `expenses`

---

### `/test coverage [module]`
Analyze test coverage for a module or file.

**Output:**
```
## Coverage Report: [module]

### Overall Coverage: XX%

### Uncovered Lines
| File | Lines | Functions |
|------|-------|-----------|
| ... | ... | ... |

### Suggested Tests
1. [Specific test to add for coverage]
```

---

### `/test fixture [entity]`
Generate a factory function for test data.

**Process:**
1. Read the model definition
2. Generate factory following `tests/e2e/fixtures/factories.py` pattern
3. Include sensible defaults
4. Add randomization where appropriate

**Output:** Factory function ready to add to `factories.py`

---

### `/test mock [class_or_function]`
Generate mock classes for unit testing.

**Process:**
1. Analyze the target class/function
2. Generate dataclass-based mock following `tests/unit/conftest.py` pattern
3. Include all required attributes

---

### `/test debug [test_name]`
Debug a failing test.

**Process:**
1. Run the test with verbose output
2. Analyze the failure
3. Suggest fixes based on:
   - Fixture issues
   - Database state
   - Assertion mismatches
   - Auth/RBAC problems

---

### `/test smoke`
Run critical path smoke tests for deployment verification.

**Runs:**
```bash
pytest -m critical --tb=short
```

---

### `/test api [endpoint]`
Generate API integration tests for an endpoint.

**Output:** Tests covering:
- HTTP methods (GET, POST, PUT, PATCH, DELETE)
- Status codes (200, 201, 400, 401, 403, 404, 422)
- Request validation
- Response schema
- Pagination (if list endpoint)
- Filtering (if applicable)
- RBAC scopes

---

### `/test e2e [flow]`
Generate end-to-end workflow test.

**Process:**
1. Identify the business flow
2. Create test class with step-by-step tests
3. Use factories for setup
4. Assert state at each step

**Example flows:**
- Invoice-to-Cash
- Lead-to-Customer
- Ticket lifecycle
- Leave request

---

## Project Conventions

### Test Structure
```
tests/
├── conftest.py              # Shared fixtures (auth, db cleanup)
├── unit/
│   ├── conftest.py          # Mock classes
│   └── services/            # Service unit tests
├── integration/
│   ├── conftest.py          # Integration fixtures
│   └── api/                 # API tests
└── e2e/
    ├── conftest.py          # E2E fixtures
    ├── fixtures/
    │   ├── factories.py     # Test data factories
    │   └── workflow_helpers.py
    └── [module]/            # E2E tests by module
```

### Fixtures Available

| Fixture | Description | Usage |
|---------|-------------|-------|
| `client` | Superuser client (legacy) | Quick tests |
| `auth_client_with_scope` | RBAC-aware client factory | `client = auth_client_with_scope(["contacts:read"])` |
| `service_token_client` | Service token client factory | API consumer tests |
| `unauthenticated_client` | No auth client | 401 tests |
| `superuser_client` | Explicit superuser | Admin tests |
| `e2e_db` | E2E database session | E2E tests |
| `e2e_superuser_client` | E2E superuser client | E2E tests |

### Test Naming

| Type | Pattern | Example |
|------|---------|---------|
| Unit | `test_[function]_[scenario]` | `test_calculate_sla_with_holidays` |
| Integration | `test_[action]_[resource]` | `test_create_contact_success` |
| E2E | `test_[flow_step]` | `test_submit_invoice` |

### Assertions

```python
# HTTP assertions (E2E)
from tests.e2e.conftest import assert_http_ok, assert_http_error, get_json

assert_http_ok(response, "Create invoice")
assert_http_error(response, 400, "Invalid payload")
data = get_json(response)

# Standard assertions
assert response.status_code == 200
assert data["id"] is not None
assert "error" not in data
```

### Markers

```python
# Module-level marker
pytestmark = pytest.mark.accounting

# Test-level marker
@pytest.mark.critical
def test_payment_processing():
    ...

@pytest.mark.slow
def test_large_report_generation():
    ...
```

---

## Automatic Activation

This skill activates when:
- User asks to "write tests" or "add tests"
- User asks to "run tests" or "test this"
- User asks about "coverage" or "untested code"
- User asks to debug a failing test
- User needs fixtures or mocks

---

## Anti-Patterns to Avoid

- **Testing implementation details** - Test behavior, not internals
- **Fragile assertions** - Don't assert on random IDs or timestamps
- **Missing cleanup** - Use fixtures with cleanup, not manual teardown
- **Hardcoded test data** - Use factories with defaults
- **Skipping auth tests** - Always test RBAC with `auth_client_with_scope`
- **Testing framework code** - Don't test FastAPI/SQLAlchemy behavior
- **Over-mocking** - Only mock external services, not internal modules

---

## Running Tests

```bash
# All tests
pytest

# Specific file
pytest tests/unit/services/test_sla_engine.py

# By marker
pytest -m critical
pytest -m "accounting and not slow"

# With coverage
pytest --cov=app --cov-report=html

# Verbose with traceback
pytest -v --tb=short

# Stop on first failure
pytest -x

# Re-run failed
pytest --lf
```
