# Testing Guide

This document provides comprehensive guidance for testing in the DotMAC Insights codebase.

## Table of Contents

- [Quick Start](#quick-start)
- [Test Organization](#test-organization)
- [Running Tests](#running-tests)
- [Test Markers](#test-markers)
- [Writing Tests](#writing-tests)
- [Coverage](#coverage)
- [CI/CD Integration](#cicd-integration)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

```bash
# Install all dependencies
make install

# Run Python unit tests
make test-unit

# Run critical tests only (fastest)
make test-critical

# Run with coverage report
make test-coverage

# Run frontend unit tests
make test-frontend

# Run frontend E2E tests
make test-frontend-e2e

# Watch mode for TDD
make test-watch
```

---

## Test Organization

### Python Tests (`tests/`)

```
tests/
├── conftest.py                  # Shared fixtures (auth, DB cleanup)
├── test_smoke.py                # @critical - App boot, health checks
├── test_auth_security.py        # Auth/RBAC tests
├── test_*.py                    # Unit/integration tests
├── e2e/
│   ├── conftest.py              # E2E fixtures (PostgreSQL)
│   ├── fixtures/
│   │   ├── factories.py         # Test data factories
│   │   └── workflow_helpers.py  # State verification helpers
│   ├── accounting/              # @accounting marker
│   ├── crm/                     # @crm marker
│   ├── hr/                      # @hr marker
│   ├── projects/                # @projects marker
│   └── support/                 # @support marker
```

### Frontend Tests (`frontend/tests/`)

```
frontend/tests/
├── setup.ts                     # Vitest setup (mocks)
├── utils/
│   └── render.tsx               # Custom render with providers
├── e2e/
│   ├── fixtures/
│   │   ├── auth.ts              # JWT auth helpers
│   │   ├── api-helpers.ts       # Test data creation
│   │   └── smoke-pages.ts       # Page registry
│   ├── smoke.spec.ts            # Page load tests
│   ├── contacts.spec.ts         # Contacts module
│   ├── support-tickets.spec.ts  # Support module
│   ├── expenses.spec.ts         # Expenses module
│   ├── banking.spec.ts          # Banking module
│   ├── payroll.spec.ts          # Payroll module
│   ├── webhooks.spec.ts         # Webhooks/admin
│   └── settings.spec.ts         # Settings module
```

---

## Running Tests

### Python Tests

| Command | Description |
|---------|-------------|
| `make test` | Run all unit tests |
| `make test-unit` | Run unit tests (SQLite) |
| `make test-critical` | Run critical path tests only |
| `make test-integration` | Run integration tests (PostgreSQL required) |
| `make test-e2e` | Run E2E tests (PostgreSQL required) |
| `make test-module M=crm` | Run tests for specific module |
| `make test-coverage` | Run with HTML coverage report |
| `make test-watch` | Watch mode (requires pytest-watch) |

### Frontend Tests

| Command | Description |
|---------|-------------|
| `make test-frontend` | Run Vitest unit tests |
| `make test-frontend-coverage` | Run with coverage report |
| `make test-frontend-e2e` | Run Playwright E2E tests |
| `make test-frontend-e2e-ui` | Playwright UI mode (interactive) |
| `make test-frontend-e2e-headed` | Run in visible browser |

### Direct pytest Commands

```bash
# Run specific test file
poetry run pytest tests/test_auth_security.py -v

# Run specific test
poetry run pytest tests/test_auth_security.py::TestOriginValidation::test_valid_origin -v

# Run by marker
poetry run pytest -m critical
poetry run pytest -m "crm and not slow"

# Run with verbose output
poetry run pytest tests/ -v --tb=long

# Stop on first failure
poetry run pytest tests/ -x
```

### Direct Playwright Commands

```bash
cd frontend

# Run all E2E tests
npx playwright test

# Run specific spec file
npx playwright test contacts.spec.ts

# Debug mode
npx playwright test --debug

# UI mode (interactive)
npx playwright test --ui

# Generate test from recording
npx playwright codegen http://localhost:3000
```

---

## Test Markers

Use pytest markers to categorize and selectively run tests:

| Marker | Description | Usage |
|--------|-------------|-------|
| `@pytest.mark.critical` | Must-pass on every commit | Smoke tests, core functionality |
| `@pytest.mark.slow` | Takes >10 seconds | Large data tests, full flows |
| `@pytest.mark.integration` | Needs external services | Database, Redis tests |
| `@pytest.mark.e2e` | Full stack required | API workflow tests |
| `@pytest.mark.accounting` | Accounting module | Module-specific E2E |
| `@pytest.mark.crm` | CRM module | Module-specific E2E |
| `@pytest.mark.hr` | HR module | Module-specific E2E |
| `@pytest.mark.projects` | Projects module | Module-specific E2E |
| `@pytest.mark.support` | Support module | Module-specific E2E |
| `@pytest.mark.field_service` | Field service module | Module-specific tests |
| `@pytest.mark.inbox` | Inbox/conversations | Module-specific tests |
| `@pytest.mark.inventory` | Inventory module | Module-specific tests |
| `@pytest.mark.expenses` | Expenses module | Module-specific tests |

### Running by Marker

```bash
# Run only critical tests
pytest -m critical

# Run everything except slow tests
pytest -m "not slow"

# Run CRM E2E tests
pytest tests/e2e/crm/ -m crm

# Combine markers
pytest -m "critical or smoke"
pytest -m "integration and not slow"
```

---

## Writing Tests

### Python Unit Test Example

```python
import pytest
from app.services.payment_allocation import PaymentAllocationService

@pytest.mark.critical
def test_allocate_payment_full_amount(client):
    """Test full payment allocation to single invoice."""
    service = PaymentAllocationService()
    result = service.allocate(payment_id=1, invoice_id=1, amount=100.00)

    assert result.success is True
    assert result.remaining_amount == 0
    assert result.invoice_status == "paid"
```

### Python Integration Test Example

```python
import pytest
from tests.e2e.conftest import assert_http_ok, get_json

@pytest.mark.integration
def test_create_contact(auth_client_with_scope):
    """Test contact creation via API."""
    client = auth_client_with_scope(["contacts:write"])

    payload = {
        "contact_name": "Test Contact",
        "email_id": "test@example.com",
        "contact_type": "Customer"
    }

    response = client.post("/api/contacts", json=payload)
    assert_http_ok(response, "Create contact")

    data = get_json(response)
    assert data["contact_name"] == "Test Contact"
```

### Python E2E Test Example

```python
import pytest
from tests.e2e.fixtures.factories import create_invoice, create_payment
from tests.e2e.fixtures.workflow_helpers import verify_invoice_status

pytestmark = pytest.mark.accounting

class TestInvoicePaymentFlow:
    def test_full_payment_marks_invoice_paid(self, e2e_superuser_client, e2e_db):
        """Test that full payment allocation marks invoice as paid."""
        # Create invoice
        invoice = create_invoice(e2e_db, grand_total=1000.00)

        # Create payment
        payment = create_payment(e2e_db, amount=1000.00)

        # Allocate payment
        response = e2e_superuser_client.post(
            f"/api/accounting/payments/{payment.name}/allocate",
            json={"invoice": invoice.name, "amount": 1000.00}
        )
        assert response.status_code == 200

        # Verify invoice is now paid
        verify_invoice_status(e2e_db, invoice.name, "Paid")
```

### Frontend Component Test Example

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@/tests/utils/render';
import { DataTable } from '@/components/DataTable';

describe('DataTable', () => {
  const columns = [
    { key: 'name', header: 'Name' },
    { key: 'email', header: 'Email' },
  ];

  const data = [
    { id: 1, name: 'John', email: 'john@example.com' },
    { id: 2, name: 'Jane', email: 'jane@example.com' },
  ];

  it('renders data rows', () => {
    render(<DataTable columns={columns} data={data} keyField="id" />);

    expect(screen.getByText('John')).toBeInTheDocument();
    expect(screen.getByText('jane@example.com')).toBeInTheDocument();
  });

  it('handles row click', () => {
    const onRowClick = vi.fn();
    render(
      <DataTable
        columns={columns}
        data={data}
        keyField="id"
        onRowClick={onRowClick}
      />
    );

    fireEvent.click(screen.getByText('John'));
    expect(onRowClick).toHaveBeenCalledWith(data[0]);
  });
});
```

### Frontend E2E Test Example

```typescript
import { test, expect, setupAuth } from './fixtures/auth';

test.describe('Contacts', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page, ['contacts:read', 'contacts:write']);
  });

  test('creates a new contact', async ({ page }) => {
    await page.goto('/contacts/new');

    await page.getByLabel(/name/i).fill('New Contact');
    await page.getByLabel(/email/i).fill('new@example.com');
    await page.getByRole('button', { name: /save/i }).click();

    await expect(page.getByText(/created successfully/i)).toBeVisible();
  });
});
```

---

## Coverage

### Viewing Coverage Reports

```bash
# Python coverage
make test-coverage
open coverage_html/index.html  # macOS
xdg-open coverage_html/index.html  # Linux

# Frontend coverage
make test-frontend-coverage
open frontend/coverage/index.html
```

### Coverage Targets

| Module | Current | Target (6mo) |
|--------|---------|--------------|
| `app/api/` | - | 40% |
| `app/services/` | - | 50% |
| `app/models/` | - | 30% |
| Frontend components | 0% | 80% |
| Frontend hooks | 0% | 90% |

### Excluding from Coverage

In Python, use pragmas:
```python
if TYPE_CHECKING:  # pragma: no cover
    from typing import Optional
```

In TypeScript, configure in `vitest.config.ts`:
```typescript
coverage: {
  exclude: ['**/*.stories.tsx', '**/index.ts']
}
```

---

## CI/CD Integration

Tests run automatically on push to `main`/`develop` and pull requests.

### CI Jobs

| Job | Description | Blocking |
|-----|-------------|----------|
| `lint` | Ruff linting & formatting | Yes |
| `test-critical` | Critical path tests | Yes |
| `test-unit` | Unit tests with coverage | Yes |
| `test-migrations` | Migration up/down tests | Yes |
| `test-integration` | Integration tests | Yes |
| `test-e2e-python` | E2E tests (parallel by module) | No |
| `frontend-build` | TypeScript check & build | Yes |
| `test-frontend-unit` | Vitest unit tests | Yes |
| `test-frontend-e2e` | Playwright E2E tests | No |
| `coverage-report` | Combined coverage summary | No |

### Artifacts

After CI runs, these artifacts are available:
- `coverage-unit` - Python unit test coverage
- `coverage-integration` - Integration test coverage
- `coverage-e2e-*` - E2E coverage by module
- `coverage-frontend` - Frontend coverage
- `playwright-report` - E2E test report with traces

---

## Troubleshooting

### Tests fail with database errors

Ensure PostgreSQL is running for integration/E2E tests:
```bash
docker-compose up -d postgres redis

# Or use make
make docker-up
```

### Coverage not collected

Ensure pytest-cov is installed:
```bash
poetry add --group dev pytest-cov
```

### Playwright tests timeout

1. Ensure backend is running:
```bash
poetry run uvicorn app.main:app --reload &
```

2. Check environment variables:
```bash
export E2E_BASE_URL=http://localhost:3000
export E2E_API_URL=http://localhost:8000
export E2E_JWT_SECRET=your-secret
```

3. Increase timeout in `playwright.config.ts`

### Tests pass locally but fail in CI

1. Check for hardcoded paths or environment-specific code
2. Ensure all dependencies are in `pyproject.toml` or `package.json`
3. Check if tests depend on specific database state

### Pre-commit hooks failing

Install hooks:
```bash
poetry run pre-commit install
```

Run manually:
```bash
poetry run pre-commit run --all-files
```

### Vitest can't find modules

Check `vitest.config.ts` has correct path aliases:
```typescript
resolve: {
  alias: {
    '@': path.resolve(__dirname, './'),
  },
},
```

---

## Best Practices

1. **Use markers** - Tag tests appropriately for selective running
2. **Test one thing** - Each test should verify a single behavior
3. **Use factories** - Create test data with factories, not fixtures
4. **Clean up** - Tests should not leave state that affects other tests
5. **Mock at boundaries** - Mock external services, not internal code
6. **Name clearly** - Test names should describe the behavior being tested
7. **Keep fast** - Unit tests should run in milliseconds
8. **Don't skip** - Fix flaky tests instead of skipping them
