# Dotmac Insights

Unified data platform for Dotmac Technologies - aggregating data from Splynx, ERPNext, and Chatwoot into a single database for analysis and insights.

## Features

- **Data Sync**: Automated sync from Splynx (ISP billing), ERPNext (ERP), and Chatwoot (support)
- **Unified Customer View**: Link customers across all systems
- **Web Dashboard**: Next.js frontend with customer analytics, insights, and data explorer
- **Data Explorer**: Query and explore all synced data via API or UI
- **Analytics**: Revenue trends, churn analysis, POP performance, support metrics
- **Customer 360**: Complete customer profile with finance, services, support history
- **Real-time Updates**: Configurable sync intervals via Celery

## Quick Start

### 1. Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis (optional, for Celery background tasks)
- Node.js 18+ (for frontend)
- pnpm (for building component library)

### 2. Setup

```bash
# Clone and enter directory
cd dotmac-insights

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -
# Add poetry to PATH if needed: export PATH="$HOME/.local/bin:$PATH"

# Install dependencies (no dev)
poetry install --only main

# Copy environment file and configure
cp .env.example .env
# Edit .env with your API credentials
```

### 3. Configure Environment

Edit `.env` with your credentials:

```env
# Database (psycopg3 driver)
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/dotmac_insights

# API Security (required in prod)
API_KEY=replace_me_in_prod
ENVIRONMENT=development  # development, staging, production
CORS_ORIGINS=http://localhost:3000

# Splynx API (Basic auth recommended: base64 of "key:secret")
SPLYNX_API_URL=https://your-splynx.com/api/2.0
SPLYNX_AUTH_BASIC=base64_key_secret
# or token auth:
SPLYNX_API_KEY=your_key
SPLYNX_API_SECRET=your_secret

# ERPNext API
ERPNEXT_API_URL=https://your-erpnext.com
ERPNEXT_API_KEY=your_key
ERPNEXT_API_SECRET=your_secret

# Chatwoot API
CHATWOOT_API_URL=https://your-chatwoot.com/api/v1
CHATWOOT_API_TOKEN=your_token
CHATWOOT_ACCOUNT_ID=1

# Redis (required for Celery workers/beat; unset = asyncio fallback)
REDIS_URL=redis://localhost:6379/0
```

### 4. Initialize Database

```bash
# Create database tables (run migrations)
poetry run alembic upgrade head
```

### 5. Test Connections

```bash
poetry run python cli.py test-connections
```

### 6. Run Initial Sync

```bash
# Sync all sources (full sync)
poetry run python cli.py sync all --full

# Or sync individually
poetry run python cli.py sync splynx --full
poetry run python cli.py sync erpnext --full
poetry run python cli.py sync chatwoot --full
```

### 7. Start the API Server

```bash
poetry run uvicorn app.main:app --reload
```

Access the API at: http://localhost:8000
API Documentation: http://localhost:8000/docs
Auth: click **Authorize** in Swagger UI and enter your API key in `X-API-Key` (or pass `api_key` as a query param).

> In production, `API_KEY` must be set or the app will refuse to start. CORS is locked down unless `CORS_ORIGINS` is provided. Development without an API key is allowed but logged as a warning.

### 8. Setup Frontend

The frontend requires the `@dotmac/core` and `@dotmac/design-tokens` packages from the component library.

```bash
# Clone the component library (one level up from dotmac-insights)
cd ..
git clone https://github.com/michaelayoade/dotmac-component-library.git
cd dotmac-component-library

# Install and build
pnpm install
pnpm build

# Create tarballs for local installation
cd packages/core && pnpm pack && cd ../..
cd packages/design-tokens && pnpm pack && cd ../..

# Return to frontend directory
cd ../dotmac-insights/frontend
```

### 9. Configure Frontend Environment

Create `frontend/.env.local`:

```env
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000

# Service token for development (grants all scopes)
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
NEXT_PUBLIC_SERVICE_TOKEN=your_service_token_here
```

> **Note**: The service token must match the `SERVICE_TOKEN` in your backend `.env` file.

### 10. Install and Run Frontend

```bash
cd frontend

# Install dependencies (will use local tarballs from component library)
npm install

# Start development server
npm run dev
```

Access the dashboard at: http://localhost:3000

### Quick Reference: Running the Full Stack

```bash
# Terminal 1: Backend API
cd dotmac-insights
poetry run uvicorn app.main:app --reload --host 0.0.0.0

# Terminal 2: Celery Worker (optional, for background sync)
cd dotmac-insights
poetry run celery -A app.celery_app worker --loglevel=info

# Terminal 3: Celery Beat (optional, for scheduled sync)
cd dotmac-insights
poetry run celery -A app.celery_app beat --loglevel=info

# Terminal 4: Frontend
cd dotmac-insights/frontend
npm run dev
```

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | Next.js Dashboard |
| Backend API | http://localhost:8000 | FastAPI Server |
| API Docs | http://localhost:8000/docs | Swagger UI |

## Using Docker

```bash
# Start all services (PostgreSQL, Redis, API, Celery worker, Celery beat)
docker-compose up -d --build

# View logs
docker-compose logs -f api
```

## API Endpoints

### Sync Management

- `POST /api/sync/all` - Sync all sources (Splynx via Celery if available; ERPNext/Chatwoot enqueued if Celery is on)
- `POST /api/sync/splynx` - Full Splynx sync
- `POST /api/sync/splynx/customers` - Customers only
- `POST /api/sync/splynx/invoices` - Invoices only
- `POST /api/sync/splynx/payments` - Payments only
- `POST /api/sync/splynx/services` - Services only
- `POST /api/sync/splynx/credit-notes` - Credit notes only
- `POST /api/sync/erpnext` - ERPNext full sync (Celery if available)
- `POST /api/sync/chatwoot` - Chatwoot full sync (Celery if available)
- `GET /api/sync/task/{task_id}` - Check Celery task status
- `GET /api/sync/status` - Get sync status (includes `celery_enabled` flag)
- `GET /api/sync/logs` - View sync logs
- `POST /api/sync/test-connections` - Test API connections

### Data Explorer

- `GET /api/explore/tables` - List all tables with counts
- `GET /api/explore/tables/{table}` - Browse table data
- `GET /api/explore/tables/{table}/stats` - Get table statistics
- `GET /api/explore/data-quality` - Check data quality
- `GET /api/explore/search?q=term` - Search across all tables
- `POST /api/explore/query` - Run custom queries

### Customers

- `GET /api/customers` - List customers
- `GET /api/customers/{id}` - Get customer details
- `GET /api/customers/churned` - Get churned customers

### Analytics

- `GET /api/analytics/overview` - High-level metrics
- `GET /api/analytics/revenue/trend` - Revenue trends
- `GET /api/analytics/churn/trend` - Churn trends
- `GET /api/analytics/pop/performance` - POP performance
- `GET /api/analytics/support/metrics` - Support metrics
- `GET /api/analytics/invoices/aging` - Invoice aging report
- `GET /api/analytics/customers/by-plan` - Distribution by plan

## CLI Commands

```bash
# Test connections
poetry run python cli.py test-connections

# Sync data
poetry run python cli.py sync all           # Incremental sync all
poetry run python cli.py sync all --full    # Full sync all
poetry run python cli.py sync splynx        # Sync Splynx only
poetry run python cli.py sync erpnext       # Sync ERPNext only
poetry run python cli.py sync chatwoot      # Sync Chatwoot only

# View statistics
poetry run python cli.py stats

# Initialize database
poetry run alembic upgrade head
```

## Data Model

### Core Tables

- **customers** - Unified customer records linked across all systems
- **pops** - Points of Presence / network locations
- **subscriptions** - Customer service subscriptions
- **invoices** - Billing invoices from Splynx and ERPNext
- **payments** - Payment records
- **conversations** - Support tickets from Chatwoot
- **messages** - Individual messages in conversations
- **employees** - Staff records from ERPNext
- **expenses** - Expense records for cost analysis
- **sync_logs** - Track all sync operations

### Customer Linkage

Customers are linked across systems using:
- `splynx_id` - Splynx customer ID
- `erpnext_id` - ERPNext customer name
- `chatwoot_contact_id` - Chatwoot contact ID

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Splynx    │     │   ERPNext   │     │  Chatwoot   │
│  (Billing)  │     │    (ERP)    │     │  (Support)  │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────┬───────┴───────────────────┘
                   │ REST APIs
           ┌───────▼───────┐
           │  Sync Engine  │
           │ (Python/Celery)│
           └───────┬───────┘
                   │
           ┌───────▼───────┐
           │  PostgreSQL   │
           │   Database    │
           └───────┬───────┘
                   │
           ┌───────▼───────┐
           │   FastAPI     │
           │    Server     │
           │  :8000/api    │
           └───────┬───────┘
                   │
           ┌───────▼───────┐
           │   Next.js     │
           │  Dashboard    │
           │    :3000      │
           └───────────────┘
```

## Next Steps

1. **Churn Prediction** - ML-based customer risk scoring
2. **Automated Reports** - Scheduled email reports
3. **Alerts** - Notifications for critical events
4. **Manager Views** - Role-based dashboards
5. **Mobile App** - React Native companion app

## Support

For issues or questions, contact the development team.
