# DotMAC Insights - Development Makefile
#
# This Makefile provides convenient commands for development tasks.
# Run `make help` to see all available commands.

.PHONY: help install clean lint format \
        test test-unit test-critical test-integration test-e2e test-coverage test-watch \
        test-frontend test-frontend-coverage test-frontend-e2e \
        docker-up docker-down db-migrate db-upgrade db-downgrade

# =============================================================================
# HELP
# =============================================================================

help:
	@echo "DotMAC Insights Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install          - Install all dependencies (Python + Frontend)"
	@echo "  make clean            - Clean generated files and caches"
	@echo ""
	@echo "Python Tests:"
	@echo "  make test             - Run all Python tests (unit + integration)"
	@echo "  make test-unit        - Run unit tests only (SQLite)"
	@echo "  make test-critical    - Run critical path tests only (fast)"
	@echo "  make test-integration - Run integration tests (requires PostgreSQL)"
	@echo "  make test-e2e         - Run E2E tests (requires PostgreSQL)"
	@echo "  make test-coverage    - Run tests with HTML coverage report"
	@echo "  make test-watch       - Run tests in watch mode (requires pytest-watch)"
	@echo "  make test-module M=   - Run tests for specific module (e.g., M=crm)"
	@echo ""
	@echo "Frontend Tests:"
	@echo "  make test-frontend          - Run frontend unit tests (Vitest)"
	@echo "  make test-frontend-coverage - Run frontend tests with coverage"
	@echo "  make test-frontend-e2e      - Run Playwright E2E tests"
	@echo "  make test-frontend-e2e-ui   - Run Playwright in UI mode"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint             - Run linter (ruff)"
	@echo "  make format           - Format code (ruff)"
	@echo "  make type-check       - Run type checking (mypy)"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate       - Create a new migration"
	@echo "  make db-upgrade       - Apply all pending migrations"
	@echo "  make db-downgrade     - Rollback last migration"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up        - Start development services"
	@echo "  make docker-down      - Stop development services"

# =============================================================================
# SETUP
# =============================================================================

install:
	@echo "Installing Python dependencies..."
	poetry install
	@echo "Installing Node dependencies..."
	npm ci
	@echo "Building CSS..."
	npm run css:build
	@echo "Installing Playwright browsers..."
	npx playwright install --with-deps chromium
	@echo "Installing pre-commit hooks..."
	poetry run pre-commit install || true
	@echo "Done! Run 'make test' to verify installation."

css-build:
	npm run css:build

css-watch:
	npm run css:watch

clean:
	@echo "Cleaning Python caches..."
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf coverage_html
	rm -rf coverage.xml
	rm -rf htmlcov
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaning frontend caches..."
	rm -rf frontend/.next
	rm -rf frontend/coverage
	rm -rf frontend/playwright-report
	rm -rf frontend/test-results
	@echo "Done!"

# =============================================================================
# PYTHON TESTS
# =============================================================================

# Default test database URL for unit tests
TEST_DB_URL ?= sqlite:///./test.db

test:
	poetry run pytest tests/ --ignore=tests/e2e -v --tb=short

test-unit:
	TEST_DATABASE_URL="$(TEST_DB_URL)" \
	poetry run pytest tests/ \
		--ignore=tests/e2e \
		--ignore=tests/test_migrations.py \
		--ignore=tests/test_payroll_integration.py \
		-v --tb=short \
		-m "not slow and not integration"

test-critical:
	TEST_DATABASE_URL="$(TEST_DB_URL)" \
	poetry run pytest tests/ \
		-m critical \
		-v --tb=short \
		-x

test-integration:
	poetry run pytest \
		tests/test_payroll_integration.py \
		tests/test_entitlement_gating.py \
		tests/test_bank_reconciliation_pagination.py \
		tests/test_webhooks_security.py \
		-v --tb=short

test-e2e:
	poetry run pytest tests/e2e/ -v --tb=short

test-module:
ifndef M
	@echo "Usage: make test-module M=<module>"
	@echo "Available modules: accounting, crm, hr, projects, support, field_service, inbox, inventory, expenses"
	@exit 1
endif
	poetry run pytest tests/e2e/$(M)/ -v --tb=short -m $(M)

test-coverage:
	TEST_DATABASE_URL="$(TEST_DB_URL)" \
	poetry run pytest tests/ \
		--ignore=tests/e2e \
		--cov=app \
		--cov-report=html:coverage_html \
		--cov-report=term-missing \
		--cov-report=xml:coverage.xml \
		-v
	@echo ""
	@echo "Coverage report generated at: coverage_html/index.html"
	@echo "Open with: open coverage_html/index.html (macOS) or xdg-open coverage_html/index.html (Linux)"

test-watch:
	poetry run ptw --runner "pytest tests/ --ignore=tests/e2e --tb=short -q"

# =============================================================================
# FRONTEND TESTS
# =============================================================================

test-frontend:
	cd frontend && npm run test

test-frontend-coverage:
	cd frontend && npm run test:coverage
	@echo ""
	@echo "Coverage report generated at: frontend/coverage/index.html"

test-frontend-e2e:
	cd frontend && npm run test:e2e

test-frontend-e2e-ui:
	cd frontend && npm run test:e2e:ui

test-frontend-e2e-headed:
	cd frontend && npm run test:e2e:headed

# =============================================================================
# CODE QUALITY
# =============================================================================

lint:
	poetry run ruff check .

format:
	poetry run ruff format .
	poetry run ruff check --fix .

type-check:
	poetry run mypy app/ --ignore-missing-imports

# =============================================================================
# DATABASE
# =============================================================================

db-migrate:
ifndef MSG
	@echo "Usage: make db-migrate MSG='your migration message'"
	@exit 1
endif
	poetry run alembic revision --autogenerate -m "$(MSG)"

db-upgrade:
	poetry run alembic upgrade head

db-downgrade:
	poetry run alembic downgrade -1

# =============================================================================
# DOCKER
# =============================================================================

docker-up:
	docker-compose up -d postgres redis

docker-down:
	docker-compose down

# =============================================================================
# COMBINED COMMANDS
# =============================================================================

# Run all tests (Python unit + frontend)
test-all: test-unit test-frontend
	@echo "All tests passed!"

# Full CI-like check
ci-check: lint type-check test-unit test-frontend
	@echo "All CI checks passed!"
