# Testing Playbook: Achieving High Test Coverage

A practical guide for the dotmac-insights team to run, write, and fix tests to achieve and maintain high test coverage.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Environment Setup](#2-environment-setup)
3. [Running Tests](#3-running-tests)
4. [Measuring Coverage](#4-measuring-coverage)
5. [Identifying Coverage Gaps](#5-identifying-coverage-gaps)
6. [Writing Tests](#6-writing-tests)
7. [Fixing Failing Tests](#7-fixing-failing-tests)
8. [Test Maintenance](#8-test-maintenance)
9. [CI/CD Integration](#9-cicd-integration)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Overview

### Coverage Targets

| Test Type | Current | Target | Priority |
|-----------|---------|--------|----------|
| Python Unit Tests | ~30% | 65% | High |
| Python Integration Tests | ~25% | 55% | High |
| Frontend E2E Tests | 15 specs | 25+ specs | High |
| Frontend Component Tests | ~20% | 80% | Medium |

### Test Pyramid

```
        /\
       /  \      E2E Tests (15-20%)
      /----\     - Full user journeys
     /      \    - Critical paths only
    /--------\
   /          \  Integration Tests (30-40%)
  /------------\ - API endpoints
 /              \- Service interactions
/----------------\
                  Unit Tests (40-50%)
                  - Individual functions
                  - Business logic
                  - Edge cases
```

### Priority Order

1. **P0 - Critical Path Tests**: Payment flows, document posting, SLA calculations
2. **P1 - Core Module Tests**: CRUD operations, API endpoints, validations
3. **P2 - Edge Cases**: Error handling, boundary conditions, RBAC
4. **P3 - UI/UX Tests**: Component rendering, interactions, accessibility

---

## 2. Environment Setup

### Python Backend

```bash
# Install test dependencies
cd /root/dotmac/dotmac-insights
poetry install --with dev

# Verify pytest is available
poetry run pytest --version

# Set up test database (SQLite for unit tests)
export TEST_DATABASE_URL="sqlite:///./test.db"
export TESTING=1
```

### Frontend

```bash
# Install dependencies
cd frontend
npm install

# Install Playwright browsers (for E2E)
npx playwright install chromium

# Set environment variables
export E2E_BASE_URL="http://localhost:3000"
export E2E_API_URL="http://localhost:8000"
export E2E_JWT_SECRET="test-secret-for-e2e-testing"
```

### Quick Verification

```bash
# Backend - run a quick test
poetry run pytest tests/unit -x --tb=short -q

# Frontend - run component tests
cd frontend && npm run test -- --run

# Frontend - run E2E smoke test
cd frontend && npx playwright test smoke.spec.ts
```

---

## 3. Running Tests

### Python Tests

```bash
# Run all tests
poetry run pytest

# Run only unit tests (fast, no external deps)
poetry run pytest tests/unit -v

# Run integration tests
poetry run pytest tests/integration -v

# Run E2E tests
poetry run pytest tests/e2e -v

# Run specific test file
poetry run pytest tests/unit/services/test_payment_allocation_service.py -v

# Run tests matching a pattern
poetry run pytest -k "payment" -v

# Run with verbose output and stop on first failure
poetry run pytest -x -v --tb=long

```

### Frontend Component Tests

```bash
cd frontend

# Run all component tests
npm run test

# Run in watch mode (for development)
npm run test -- --watch

# Run specific test file
npm run test -- components/ui/DataTable.test.tsx

# Run with coverage
npm run test -- --coverage
```

### Frontend E2E Tests

```bash
cd frontend

# Run all E2E tests
npx playwright test

# Run specific spec file
npx playwright test crm-pipeline.spec.ts

# Run in headed mode (see browser)
npx playwright test --headed

# Run with UI mode (interactive)
npx playwright test --ui

# Run specific test by name
npx playwright test -g "creates invoice"

# Run only failed tests from last run
npx playwright test --last-failed

# Generate HTML report
npx playwright show-report
```

---

## 4. Measuring Coverage

### Python Coverage

```bash
# Run with coverage report
poetry run pytest --cov=app --cov-report=html:coverage_html --cov-report=term-missing

# View HTML report
open coverage_html/index.html  # macOS
xdg-open coverage_html/index.html  # Linux

# Generate XML for CI
poetry run pytest --cov=app --cov-report=xml

# Check coverage for specific module
poetry run pytest --cov=app/services --cov-report=term-missing tests/unit/services/
```

**Understanding Coverage Output:**
```
Name                                    Stmts   Miss  Cover   Missing
---------------------------------------------------------------------
app/services/payment_allocation.py        150     45    70%   23-25, 89-102
app/services/document_posting.py          200     80    60%   45-67, 120-145
```

- **Stmts**: Total statements in file
- **Miss**: Statements not executed during tests
- **Cover**: Percentage covered
- **Missing**: Line numbers not covered

### Frontend Coverage

```bash
cd frontend

# Run with coverage
npm run test -- --coverage

# Coverage thresholds (in vitest.config.ts)
# statements: 0
# branches: 0
# functions: 0
# lines: 0
```

### Identifying Low Coverage Files

```bash
# Python - find files under 50% coverage
poetry run pytest --cov=app --cov-report=term-missing 2>&1 | grep -E "^\s+\d+%|^\s+[0-4][0-9]%"

# Or use coverage report
poetry run coverage report --fail-under=50 --skip-covered
```

---

## 5. Identifying Coverage Gaps

### Step 1: Generate Coverage Report

```bash
# Python
poetry run pytest --cov=app --cov-report=html:coverage_html
open coverage_html/index.html  # macOS
xdg-open coverage_html/index.html  # Linux

# Frontend
npm run test -- --coverage
```

### Step 2: Prioritize by Risk

Use this matrix to prioritize what to test:

| Module | Business Impact | Complexity | Current Coverage | Priority |
|--------|-----------------|------------|------------------|----------|
| Payment Allocation | Critical | High | 40% | P0 |
| Document Posting | Critical | High | 35% | P0 |
| SLA Engine | High | Medium | 45% | P0 |
| Routing Engine | High | Medium | 50% | P1 |
| Contact CRUD | Medium | Low | 60% | P2 |

### Step 3: Identify Untested Code Paths

Look for these patterns in uncovered code:

1. **Error handling blocks** (except/catch)
2. **Edge cases** (empty lists, null values, boundaries)
3. **Conditional branches** (if/else paths)
4. **Validation logic**
5. **State transitions**

### Step 4: Create Test Backlog

```markdown
## Test Backlog Template

### [Module Name] - Current Coverage: X%

#### Missing Tests:
- [ ] Test case 1: [description] - Lines XX-YY
- [ ] Test case 2: [description] - Lines XX-YY

#### Priority: P0/P1/P2

#### Estimated Effort: X hours

#### Owner: [Name]
```

---

## 6. Writing Tests

### Python Unit Test Template

```python
"""
Tests for [ModuleName]

Run with: pytest tests/unit/services/test_module_name.py -v
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.services.module_name import ServiceClass


class TestServiceClass:
    """Tests for ServiceClass."""

    @pytest.fixture
    def service(self, db_session):
        """Create service instance for testing."""
        return ServiceClass(db_session)

    @pytest.fixture
    def sample_data(self):
        """Sample test data."""
        return {
            "id": 1,
            "name": "Test Item",
            "amount": 1000.00,
        }

    # ==========================================
    # Happy Path Tests
    # ==========================================

    def test_create_success(self, service, sample_data):
        """Test successful creation."""
        result = service.create(sample_data)

        assert result is not None
        assert result.name == sample_data["name"]
        assert result.amount == sample_data["amount"]

    def test_get_by_id_returns_item(self, service, sample_data):
        """Test retrieval by ID."""
        created = service.create(sample_data)

        result = service.get_by_id(created.id)

        assert result is not None
        assert result.id == created.id

    # ==========================================
    # Edge Cases
    # ==========================================

    def test_create_with_zero_amount(self, service):
        """Test creation with zero amount."""
        data = {"name": "Zero Test", "amount": 0}

        result = service.create(data)

        assert result.amount == 0

    def test_get_by_id_not_found_returns_none(self, service):
        """Test retrieval of non-existent item."""
        result = service.get_by_id(99999)

        assert result is None

    # ==========================================
    # Error Cases
    # ==========================================

    def test_create_with_negative_amount_raises_error(self, service):
        """Test that negative amounts are rejected."""
        data = {"name": "Negative Test", "amount": -100}

        with pytest.raises(ValueError, match="Amount cannot be negative"):
            service.create(data)

    def test_create_with_missing_name_raises_error(self, service):
        """Test that missing name is rejected."""
        data = {"amount": 100}

        with pytest.raises(ValueError, match="Name is required"):
            service.create(data)

    # ==========================================
    # Integration with Dependencies
    # ==========================================

    @patch("app.services.module_name.external_api")
    def test_sync_calls_external_api(self, mock_api, service):
        """Test that sync calls external API correctly."""
        mock_api.return_value = {"status": "success"}

        result = service.sync()

        mock_api.assert_called_once()
        assert result["status"] == "success"
```

### Python API Integration Test Template

```python
"""
Integration tests for [Endpoint Name] API

Run with: pytest tests/integration/api/test_endpoint.py -v
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


class TestEndpointAPI:
    """Integration tests for /api/endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        """Authentication headers for requests."""
        return {"Authorization": "Bearer test-token"}

    # ==========================================
    # List Endpoint
    # ==========================================

    def test_list_returns_paginated_results(self, client, auth_headers):
        """GET /api/items returns paginated list."""
        response = client.get("/api/items", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "items" in data or "data" in data
        assert "total" in data

    def test_list_with_filter(self, client, auth_headers):
        """GET /api/items with filter returns filtered results."""
        response = client.get(
            "/api/items?status=active",
            headers=auth_headers
        )

        assert response.status_code == 200

    # ==========================================
    # Create Endpoint
    # ==========================================

    def test_create_returns_201(self, client, auth_headers):
        """POST /api/items creates new item."""
        payload = {"name": "Test Item", "amount": 1000}

        response = client.post(
            "/api/items",
            json=payload,
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == payload["name"]

    def test_create_with_invalid_data_returns_422(self, client, auth_headers):
        """POST /api/items with invalid data returns 422."""
        payload = {"name": ""}  # Invalid: empty name

        response = client.post(
            "/api/items",
            json=payload,
            headers=auth_headers
        )

        assert response.status_code == 422

    # ==========================================
    # RBAC Tests
    # ==========================================

    def test_unauthorized_returns_401(self, client):
        """Request without auth returns 401."""
        response = client.get("/api/items")

        assert response.status_code == 401

    def test_insufficient_scope_returns_403(self, client):
        """Request with wrong scope returns 403."""
        headers = {"Authorization": "Bearer readonly-token"}

        response = client.post(
            "/api/items",
            json={"name": "Test"},
            headers=headers
        )

        assert response.status_code == 403
```

### Frontend Component Test Template

```typescript
/**
 * Tests for ComponentName
 *
 * Run with: npm run test -- ComponentName.test.tsx
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ComponentName } from './ComponentName';

// Mock dependencies
vi.mock('@/hooks/useApi', () => ({
  useApi: () => ({
    data: mockData,
    isLoading: false,
    error: null,
  }),
}));

const mockData = [
  { id: 1, name: 'Item 1' },
  { id: 2, name: 'Item 2' },
];

describe('ComponentName', () => {
  const defaultProps = {
    items: mockData,
    onSelect: vi.fn(),
    onDelete: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ==========================================
  // Rendering Tests
  // ==========================================

  describe('rendering', () => {
    it('renders without crashing', () => {
      render(<ComponentName {...defaultProps} />);

      expect(screen.getByRole('list')).toBeInTheDocument();
    });

    it('renders all items', () => {
      render(<ComponentName {...defaultProps} />);

      expect(screen.getByText('Item 1')).toBeInTheDocument();
      expect(screen.getByText('Item 2')).toBeInTheDocument();
    });

    it('renders empty state when no items', () => {
      render(<ComponentName {...defaultProps} items={[]} />);

      expect(screen.getByText(/no items/i)).toBeInTheDocument();
    });

    it('renders loading state', () => {
      render(<ComponentName {...defaultProps} isLoading />);

      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });
  });

  // ==========================================
  // Interaction Tests
  // ==========================================

  describe('interactions', () => {
    it('calls onSelect when item is clicked', async () => {
      const user = userEvent.setup();
      render(<ComponentName {...defaultProps} />);

      await user.click(screen.getByText('Item 1'));

      expect(defaultProps.onSelect).toHaveBeenCalledWith(mockData[0]);
    });

    it('calls onDelete when delete button is clicked', async () => {
      const user = userEvent.setup();
      render(<ComponentName {...defaultProps} />);

      await user.click(screen.getAllByRole('button', { name: /delete/i })[0]);

      expect(defaultProps.onDelete).toHaveBeenCalledWith(1);
    });

    it('shows confirmation before delete', async () => {
      const user = userEvent.setup();
      render(<ComponentName {...defaultProps} />);

      await user.click(screen.getAllByRole('button', { name: /delete/i })[0]);

      expect(screen.getByText(/are you sure/i)).toBeInTheDocument();
    });
  });

  // ==========================================
  // Accessibility Tests
  // ==========================================

  describe('accessibility', () => {
    it('has correct ARIA labels', () => {
      render(<ComponentName {...defaultProps} />);

      expect(screen.getByRole('list')).toHaveAttribute('aria-label');
    });

    it('is keyboard navigable', async () => {
      const user = userEvent.setup();
      render(<ComponentName {...defaultProps} />);

      await user.tab();

      expect(screen.getByText('Item 1').closest('li')).toHaveFocus();
    });
  });
});
```

### Frontend E2E Test Template

```typescript
/**
 * E2E Tests for [Module Name]
 *
 * Run with: npx playwright test module-name.spec.ts
 */

import { test, expect, setupAuth, expectAccessDenied } from './fixtures/auth';
import { createTestItem, deleteTestItem } from './fixtures/api-helpers';
import { ModulePage } from './pages';

test.describe('Module Name - Authenticated', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page, ['module:read', 'module:write']);
  });

  test.describe('List View', () => {
    test('renders list with data', async ({ page }) => {
      const modulePage = new ModulePage(page);
      await modulePage.goto();

      await expect(page.getByRole('heading', { name: /module/i })).toBeVisible();
      await expect(modulePage.dataTable).toBeVisible();
    });

    test('search filters results', async ({ page }) => {
      const modulePage = new ModulePage(page);
      await modulePage.goto();

      await modulePage.search('test');

      await expect(
        page.locator('table tbody tr').first()
          .or(page.getByText(/no results/i))
      ).toBeVisible();
    });
  });

  test.describe('Create', () => {
    test('creates item successfully', async ({ page, request }) => {
      const modulePage = new ModulePage(page);
      await modulePage.goto();

      await modulePage.clickCreate();
      await modulePage.fillField('name', `E2E Test ${Date.now()}`);
      await modulePage.submitForm();

      await expect(page).toHaveURL(/\/module\/\d+/);
    });

    test('validates required fields', async ({ page }) => {
      await page.goto('/module/new');

      await page.getByRole('button', { name: /save/i }).click();

      await expect(page.getByText(/required/i)).toBeVisible();
    });
  });

  test.describe('Edit', () => {
    test('updates item successfully', async ({ page, request }) => {
      const item = await createTestItem(request);

      try {
        await page.goto(`/module/${item.id}/edit`);

        const newName = `Updated ${Date.now()}`;
        await page.getByLabel(/name/i).fill(newName);
        await page.getByRole('button', { name: /save/i }).click();

        await expect(page.getByText(newName)).toBeVisible();
      } finally {
        await deleteTestItem(request, item.id);
      }
    });
  });

  test.describe('Delete', () => {
    test('deletes item with confirmation', async ({ page, request }) => {
      const item = await createTestItem(request);

      await page.goto(`/module/${item.id}`);
      await page.getByRole('button', { name: /delete/i }).click();
      await page.getByRole('button', { name: /confirm/i }).click();

      await expect(page).toHaveURL('/module');
    });
  });
});

test.describe('Module Name - RBAC', () => {
  test('read-only user cannot create', async ({ page }) => {
    await setupAuth(page, ['module:read']);
    await page.goto('/module');

    await expect(page.getByRole('button', { name: /create/i })).toBeHidden();
  });

  test('unauthorized user sees access denied', async ({ page }) => {
    await setupAuth(page, ['other:read']);
    await page.goto('/module');

    await expectAccessDenied(page);
  });
});
```

---

## 7. Fixing Failing Tests

### Triage Process

```
┌─────────────────────────────────────────────────────────┐
│                   Test Failure                          │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ Step 1: Reproduce Locally                               │
│ - Run the specific test                                 │
│ - Check if it's flaky (run 3x)                         │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ Step 2: Identify Failure Type                           │
│ - Assertion failure?                                    │
│ - Timeout?                                              │
│ - Import/Setup error?                                   │
│ - Environment issue?                                    │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ Step 3: Determine Root Cause                            │
│ - Code change broke test?                               │
│ - Test was always wrong?                                │
│ - External dependency changed?                          │
│ - Test environment issue?                               │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ Step 4: Apply Fix                                       │
│ - Fix the code (if bug)                                 │
│ - Fix the test (if test was wrong)                      │
│ - Update test fixtures                                  │
│ - Mark as skip with TODO (last resort)                  │
└─────────────────────────────────────────────────────────┘
```

### Common Failure Patterns and Fixes

#### 1. Timeout Failures (E2E)

**Symptom:**
```
Error: Timeout 30000ms exceeded.
```

**Fixes:**
```typescript
// Increase timeout for slow operations
await expect(element).toBeVisible({ timeout: 15000 });

// Wait for specific condition before proceeding
await page.waitForLoadState('networkidle');

// Wait for API response
await page.waitForResponse(resp => resp.url().includes('/api/data'));
```

#### 2. Element Not Found (E2E)

**Symptom:**
```
Error: Locator.click: Error: strict mode violation: locator matched 0 elements
```

**Fixes:**
```typescript
// Use more specific locators
// Bad
await page.locator('button').click();

// Good
await page.getByRole('button', { name: /submit/i }).click();

// Wait for element to appear
await page.waitForSelector('[data-testid="submit-btn"]');
```

#### 3. Assertion Mismatch

**Symptom:**
```
AssertionError: Expected 100, got 99.99
```

**Fixes:**
```python
# Use approximate comparison for floats
assert result == pytest.approx(100, rel=0.01)

# Use flexible text matching
assert "success" in response.text.lower()
```

#### 4. Flaky Tests

**Symptom:** Test passes sometimes, fails other times.

**Fixes:**
```python
# Add explicit waits instead of fixed delays
# Bad
await page.waitForTimeout(1000)

# Good
await page.waitForSelector('[data-testid="loaded"]')

# Use retry logic for assertions
@pytest.mark.flaky(reruns=3)
def test_external_api():
    ...
```

#### 5. Database State Issues

**Symptom:** Test fails due to leftover data from previous tests.

**Fixes:**
```python
# Use transactions that rollback
@pytest.fixture
def db_session():
    session = TestSession()
    yield session
    session.rollback()

# Use unique identifiers
test_name = f"Test Item {uuid.uuid4()}"

# Clean up in finally block
try:
    result = create_item()
    assert result.id is not None
finally:
    delete_item(result.id)
```

### Skip Tests Properly

When you must skip a test temporarily:

```python
# Python
@pytest.mark.skip(reason="TODO: Fix after API v2 migration - JIRA-123")
def test_legacy_endpoint():
    pass

@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Requires local database"
)
def test_local_only():
    pass
```

```typescript
// TypeScript/Playwright
test.skip('broken test', async () => {
  // TODO: Fix after component refactor - JIRA-456
});

test.fixme('known issue', async () => {
  // Known issue being worked on
});
```

---

## 8. Test Maintenance

### Weekly Tasks

| Day | Task | Owner |
|-----|------|-------|
| Monday | Review CI failures from weekend | On-call |
| Tuesday | Triage flaky test report | QA Lead |
| Wednesday | Fix top 3 flaky tests | Rotating |
| Thursday | Review coverage delta | Tech Lead |
| Friday | Update test documentation | Rotating |

### Monthly Tasks

1. **Coverage Review**
   - Generate full coverage report
   - Identify modules below target
   - Create tickets for gaps

2. **Flaky Test Audit**
   - Review tests with >5% flake rate
   - Fix or quarantine flaky tests
   - Document patterns

3. **Test Performance**
   - Identify slow tests (>10s)
   - Optimize or parallelize
   - Update CI timeouts

### Quarterly Tasks

1. **Test Strategy Review**
   - Review coverage targets
   - Update test pyramid ratios
   - Plan for new modules

2. **Tooling Upgrade**
   - Update pytest/playwright versions
   - Review new testing tools
   - Update CI configuration

---

## 9. CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/tests.yml
name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  python-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install poetry
          poetry install --with dev

      - name: Run unit tests
        run: poetry run pytest tests/unit --cov=app --cov-report=xml

      - name: Run integration tests
        run: poetry run pytest tests/integration --cov=app --cov-append --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: coverage.xml
          fail_ci_if_error: true

  frontend-tests:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: npm ci

      - name: Run component tests
        run: npm run test -- --coverage --run

      - name: Install Playwright
        run: npx playwright install --with-deps chromium

      - name: Run E2E tests
        run: npx playwright test
        env:
          E2E_JWT_SECRET: ${{ secrets.E2E_JWT_SECRET }}

      - name: Upload test report
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: frontend/playwright-report
```

### PR Checks

Every PR must pass:

1. **Unit Tests** - All passing
2. **Integration Tests** - All passing
3. **E2E Smoke Tests** - All passing
4. **Coverage Delta** - No decrease >2%
5. **Linting** - No new issues

### Coverage Gates

```yaml
# In codecov.yml
coverage:
  status:
    project:
      default:
        target: 60%
        threshold: 2%
    patch:
      default:
        target: 80%
        threshold: 5%
```

---

## 10. Troubleshooting

### Python Issues

#### ImportError in tests
```bash
# Ensure you're in the right environment
poetry shell

# Reinstall dependencies
poetry install --with dev

# Check Python path
python -c "import sys; print(sys.path)"
```

#### Database connection issues
```bash
# Use SQLite for unit tests
export TEST_DATABASE_URL="sqlite:///./test.db"

# Check connection
poetry run python -c "from app.database import engine; print(engine.url)"
```

#### Async test issues
```python
# Use pytest-asyncio
@pytest.mark.asyncio
async def test_async_function():
    result = await async_operation()
    assert result is not None
```

### Frontend Issues

#### Module not found
```bash
# Clear cache and reinstall
rm -rf node_modules
npm ci

# Check tsconfig paths
cat tsconfig.json | grep paths
```

#### Playwright browser issues
```bash
# Reinstall browsers
npx playwright install

# Run with debug
DEBUG=pw:browser npx playwright test
```

#### React Testing Library issues
```typescript
// Wrap in act() for state updates
import { act } from '@testing-library/react';

await act(async () => {
  await user.click(button);
});

// Use findBy for async elements
const element = await screen.findByText('Loaded');
```

### E2E Issues

#### Authentication failures
```bash
# Check JWT secret is set
echo $E2E_JWT_SECRET

# Verify token generation
node -e "console.log(require('./tests/e2e/fixtures/auth').createTestToken(['*']))"
```

#### Selector not working
```typescript
// Use Playwright Inspector
npx playwright test --debug

// Or use codegen
npx playwright codegen http://localhost:3000
```

#### API not responding
```bash
# Check API is running
curl http://localhost:8000/health

# Check CORS settings
curl -I -X OPTIONS http://localhost:8000/api/admin/me
```

---

## Quick Reference

### Commands Cheat Sheet

```bash
# Python
poetry run pytest tests/unit -v                    # Run unit tests
poetry run pytest -k "payment" -v                  # Run tests matching pattern
poetry run pytest --cov=app --cov-report=html:coverage_html  # Run with coverage
poetry run pytest -x --tb=short                    # Stop on first failure

# Frontend Component Tests
npm run test                            # Run all
npm run test -- --watch                 # Watch mode
npm run test -- --coverage              # With coverage

# Frontend E2E
npx playwright test                     # Run all
npx playwright test --headed            # See browser
npx playwright test --ui                # Interactive mode
npx playwright show-report              # View report
```

### Test File Naming

```
tests/
├── unit/
│   └── services/
│       └── test_<service_name>.py      # test_ prefix
├── integration/
│   └── api/
│       └── test_<endpoint>_api.py      # test_ prefix + _api suffix
└── e2e/
    └── <workflow>/
        └── test_<workflow>_flow.py     # test_ prefix + _flow suffix

frontend/tests/
├── components/
│   └── <Component>.test.tsx            # .test.tsx suffix
└── e2e/
    └── <module>.spec.ts                # .spec.ts suffix
```

### Coverage Targets by File Type

| File Type | Target | Notes |
|-----------|--------|-------|
| Services | 80% | Core business logic |
| API Routes | 70% | CRUD + validation |
| Models | 60% | Properties + methods |
| Utils | 90% | Pure functions |
| Components | 80% | Render + interactions |
| Hooks | 85% | All code paths |

---

## Getting Help

- **Testing questions**: Post in #engineering-testing Slack channel
- **CI failures**: Check GitHub Actions logs first
- **Coverage reports**: Available in CI artifacts
- **Test data issues**: Contact DevOps for database refresh

---

*Last updated: December 2024*
*Maintainer: Engineering Team*
