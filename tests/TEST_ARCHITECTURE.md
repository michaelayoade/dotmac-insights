# DotMAC Test Architecture

## Overview

This document defines the comprehensive test system for DotMAC Insights, targeting **70% overall coverage** with **90% coverage on critical paths**.

---

## Test Pyramid

```
                    ┌─────────────┐
                    │    E2E      │  8-12 critical flows
                    │  (Manual)   │  ~5% of tests
                    ├─────────────┤
                    │    E2E      │  25+ automated flows
                    │ (Automated) │  ~10% of tests
                ┌───┴─────────────┴───┐
                │    Integration      │  API endpoint tests
                │      (API)          │  ~25% of tests
            ┌───┴─────────────────────┴───┐
            │         Unit Tests          │  Services, utilities
            │                             │  ~60% of tests
            └─────────────────────────────┘
```

---

## Directory Structure

```
tests/
├── conftest.py                    # Root fixtures (auth, db cleanup)
├── pytest.ini                     # Pytest configuration
├── TEST_ARCHITECTURE.md           # This document
│
├── unit/                          # Unit tests (isolated, mocked)
│   ├── conftest.py                # Mock classes, unit fixtures
│   ├── services/                  # Service unit tests
│   │   ├── test_approval_engine.py
│   │   ├── test_nigerian_tax_service.py
│   │   ├── test_bank_reconciliation.py
│   │   ├── test_notification_service.py
│   │   ├── test_sla_engine.py           ✓ EXISTS
│   │   ├── test_routing_engine.py       ✓ EXISTS
│   │   ├── test_document_posting.py     ✓ EXISTS
│   │   └── test_payment_allocation.py   ✓ EXISTS
│   ├── models/                    # Model validation tests
│   └── utils/                     # Utility function tests
│
├── integration/                   # Integration tests (real DB)
│   ├── conftest.py                # Integration fixtures
│   ├── api/                       # API endpoint tests
│   │   ├── accounting/            # Accounting API tests
│   │   ├── crm/                   # CRM API tests
│   │   ├── hr/                    # HR API tests
│   │   ├── support/               # Support API tests
│   │   ├── tax/                   # Tax API tests
│   │   ├── test_contacts_api.py   ✓ EXISTS
│   │   ├── test_expenses_api.py   ✓ EXISTS
│   │   ├── test_field_service.py  ✓ EXISTS
│   │   └── test_inbox_api.py      ✓ EXISTS
│   └── workflows/                 # Multi-step workflow tests
│
├── e2e/                           # End-to-end tests
│   ├── conftest.py                # E2E fixtures
│   ├── fixtures/
│   │   ├── factories.py           # Test data factories
│   │   ├── workflow_helpers.py    # Flow step helpers
│   │   └── scenarios.py           # Pre-built test scenarios
│   ├── accounting/                ✓ EXISTS
│   ├── crm/                       ✓ EXISTS
│   ├── expenses/                  ✓ EXISTS
│   ├── field_service/             ✓ EXISTS
│   ├── hr/                        ✓ EXISTS
│   ├── inbox/                     ✓ EXISTS
│   ├── projects/                  ✓ EXISTS
│   ├── support/                   ✓ EXISTS
│   ├── purchasing/                # NEW: AP workflows
│   ├── payroll/                   # NEW: Payroll workflows
│   └── performance/               # NEW: Performance reviews
│
├── security/                      # Security-focused tests
│   ├── test_auth_bypass.py
│   ├── test_injection.py
│   ├── test_rbac_enforcement.py
│   └── test_rate_limiting.py
│
├── performance/                   # Performance tests
│   ├── test_query_performance.py
│   ├── test_api_latency.py
│   └── test_concurrent_load.py
│
└── regression/                    # Regression test suites
    ├── test_critical_paths.py
    └── test_known_issues.py
```

---

## Test Categories & Markers

### Markers

```python
# pytest.ini markers
markers =
    # Priority
    critical: Must pass on every commit
    smoke: Quick sanity checks
    slow: Tests > 10 seconds

    # Type
    unit: Isolated unit tests
    integration: Tests with real database
    e2e: Full workflow tests
    security: Security-focused tests
    performance: Performance benchmarks

    # Module
    accounting: Accounting module
    crm: CRM module
    hr: HR module
    support: Support module
    field_service: Field service
    inbox: Inbox/conversations
    expenses: Expense management
    projects: Project management
    inventory: Inventory
    tax: Tax compliance
    payroll: Payroll processing
    performance_mgmt: Performance reviews
```

### Running by Category

```bash
# By priority
pytest -m critical              # CI gate
pytest -m "not slow"            # Quick feedback

# By type
pytest tests/unit/              # Unit tests only
pytest tests/integration/       # Integration only
pytest tests/e2e/               # E2E only

# By module
pytest -m accounting
pytest -m "crm or support"
pytest -m "not e2e and accounting"

# Combined
pytest -m "critical and not slow"
pytest -m "integration and accounting"
```

---

## Coverage Requirements

### Thresholds

| Category | Target | Minimum | Rationale |
|----------|--------|---------|-----------|
| **Overall** | 70% | 60% | Industry standard |
| **Critical Services** | 90% | 85% | Financial accuracy |
| **API Endpoints** | 80% | 70% | User-facing |
| **Models** | 85% | 75% | Data integrity |
| **Utilities** | 95% | 90% | Shared code |

### Critical Services (90% target)

1. `approval_engine.py` - Workflow approvals
2. `nigerian_tax_service.py` - Tax compliance
3. `bank_reconciliation.py` - Financial matching
4. `payment_allocation_service.py` - Payment posting
5. `payroll_engine.py` - Salary calculations
6. `sla_engine.py` - SLA enforcement
7. `document_posting.py` - GL posting
8. `notification_service.py` - Communications

### Coverage Enforcement

```bash
# Run with coverage
pytest --cov=app --cov-report=html --cov-report=term-missing

# Fail if below threshold
pytest --cov=app --cov-fail-under=60

# Per-module coverage
pytest --cov=app/services --cov-fail-under=70
```

---

## Test Data Strategy

### Factories

Use factory functions from `tests/e2e/fixtures/factories.py`:

```python
# Pattern: create_[entity]() - Always creates new
# Pattern: get_or_create_[entity]() - Shared resources

from tests.e2e.fixtures.factories import (
    create_customer,
    create_invoice,
    create_payment,
    create_employee,
    create_ticket,
    get_or_create_currency,
    get_or_create_fiscal_year,
)

def test_invoice_flow(e2e_db, e2e_superuser_client):
    customer = create_customer(e2e_db, name="Test Corp")
    invoice = create_invoice(e2e_db, customer_id=customer.id, amount=Decimal("1000"))
    # ...
```

### Scenarios

Pre-built test scenarios for complex setups:

```python
from tests.e2e.fixtures.scenarios import (
    setup_accounting_period,       # FY + periods + accounts
    setup_invoice_with_payments,   # Invoice + partial payments
    setup_employee_with_leaves,    # Employee + leave allocations
    setup_support_queue,           # Queue + agents + SLAs
)
```

### Database Isolation

```python
# Each test gets clean state via autouse fixture
@pytest.fixture(autouse=True)
def cleanup_db():
    yield
    # Truncate all tables after each test
```

---

## Authentication Fixtures

### Available Fixtures

| Fixture | Auth Type | Use Case |
|---------|-----------|----------|
| `auth_client_with_scope` | User + specific scopes | RBAC testing |
| `service_token_client` | Service token | API consumer testing |
| `unauthenticated_client` | None | 401 testing |
| `superuser_client` | User + superuser | Admin testing |
| `e2e_superuser_client` | User + superuser | E2E flows |

### RBAC Testing Pattern

```python
class TestContactsRBAC:
    """RBAC tests for contacts API."""

    @pytest.mark.parametrize("scopes,expected", [
        (["contacts:read"], 200),
        (["contacts:write"], 200),
        (["crm:read"], 403),
        ([], 403),
    ])
    def test_list_requires_scope(self, auth_client_with_scope, scopes, expected):
        client = auth_client_with_scope(scopes)
        response = client.get("/api/contacts")
        assert response.status_code == expected
```

---

## E2E Workflow Patterns

### Flow Structure

```python
"""
E2E Test: [Flow Name]

Tests the complete [process] from [start] through [end].

Flow:
1. [Step 1]
2. [Step 2]
...
"""
import pytest
from tests.e2e.conftest import assert_http_ok, get_json
from tests.e2e.fixtures.factories import create_[entity]

pytestmark = pytest.mark.[module]


class Test[Flow]Setup:
    """Prerequisites for the flow."""
    pass


class Test[Flow]HappyPath:
    """Happy path through the flow."""
    pass


class Test[Flow]EdgeCases:
    """Error conditions and edge cases."""
    pass


class Test[Flow]Rollback:
    """Cancellation and reversal scenarios."""
    pass
```

### Required E2E Flows

| Module | Flow | Priority | Status |
|--------|------|----------|--------|
| Accounting | Invoice → Payment → Reconciliation | P0 | ✓ Partial |
| Accounting | PO → Bill → AP Payment | P0 | NEW |
| Accounting | Multi-step Invoice Approval | P0 | NEW |
| Accounting | Bank Reconciliation | P1 | NEW |
| HR | Payroll Processing | P0 | NEW |
| HR | Employee Lifecycle | P1 | NEW |
| HR | Leave Management | P1 | ✓ EXISTS |
| HR | Performance Review | P1 | NEW |
| Support | Ticket Lifecycle | P1 | ✓ EXISTS |
| Support | SLA Breach Escalation | P1 | NEW |
| CRM | Lead → Customer | P1 | ✓ EXISTS |
| CRM | Opportunity Pipeline | P2 | NEW |

---

## CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=app --cov-fail-under=60

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
    steps:
      - uses: actions/checkout@v4
      - name: Run integration tests
        run: pytest tests/integration/ -v

  e2e-tests:
    runs-on: ubuntu-latest
    needs: [unit-tests, integration-tests]
    steps:
      - uses: actions/checkout@v4
      - name: Run E2E tests
        run: pytest tests/e2e/ -v -m "not slow"

  critical-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run critical tests
        run: pytest -m critical --tb=short
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-critical
        name: Critical Tests
        entry: pytest -m critical --tb=short -q
        language: system
        pass_filenames: false
        always_run: true
```

---

## Test Implementation Priority

### Phase 1: Critical Services (Week 1-2)

| Service | LOC | Tests Needed | Priority |
|---------|-----|--------------|----------|
| approval_engine.py | 1171 | ~50 tests | P0 |
| nigerian_tax_service.py | 1214 | ~60 tests | P0 |
| bank_reconciliation.py | 648 | ~30 tests | P0 |
| notification_service.py | 876 | ~40 tests | P1 |

### Phase 2: API Integration (Week 2-4)

| Module | Endpoints | Tests Needed | Priority |
|--------|-----------|--------------|----------|
| Accounting | 23 | ~100 tests | P0 |
| Tax | 10 | ~50 tests | P0 |
| HR | 9 | ~45 tests | P1 |
| CRM | 5 | ~25 tests | P1 |

### Phase 3: E2E Workflows (Week 4-6)

| Flow | Steps | Priority |
|------|-------|----------|
| PO → Bill → Payment | 6 | P0 |
| Payroll Processing | 8 | P0 |
| Invoice Approval | 5 | P0 |
| Employee Lifecycle | 7 | P1 |
| SLA Escalation | 4 | P1 |

### Phase 4: Security & Performance (Week 6-8)

| Test Type | Count | Priority |
|-----------|-------|----------|
| RBAC enforcement | 50+ | P0 |
| Injection prevention | 20+ | P0 |
| Rate limiting | 10+ | P1 |
| Query performance | 30+ | P1 |
| Concurrency | 20+ | P1 |

---

## Metrics & Reporting

### Coverage Reports

```bash
# Generate HTML report
pytest --cov=app --cov-report=html:coverage_html

# Generate XML for CI
pytest --cov=app --cov-report=xml:coverage.xml

# Badge generation
coverage-badge -o coverage.svg
```

### Test Result Tracking

- **Pass rate target**: 100% on main branch
- **Flaky test threshold**: <1% flake rate
- **Performance baseline**: API tests < 500ms average

---

## Appendix: Quick Reference

### Common Commands

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=term-missing

# Run specific marker
pytest -m critical
pytest -m "accounting and not slow"

# Run specific file
pytest tests/unit/services/test_approval_engine.py

# Run specific test
pytest tests/unit/services/test_approval_engine.py::TestApprovalWorkflow::test_submit_for_approval

# Verbose with short traceback
pytest -v --tb=short

# Stop on first failure
pytest -x

# Re-run failed
pytest --lf

# Run in parallel
pytest -n auto
```

### Assert Helpers

```python
from tests.e2e.conftest import (
    assert_http_ok,        # Asserts 2xx status
    assert_http_error,     # Asserts specific error status
    get_json,              # Extracts JSON from response
    assert_response_schema # Validates response structure
)
```

### Factory Helpers

```python
from tests.e2e.fixtures.factories import (
    random_string,         # Random alphanumeric
    random_email,          # Random email
    random_phone,          # Random phone
    calculate_working_days # Business days between dates
)
```
