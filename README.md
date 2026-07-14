# DotMac BOS

**Business Operating System** - A comprehensive, modular ERP platform for managing all aspects of business operations.

DotMac BOS integrates with external systems (Splynx, ERPNext, Chatwoot) while providing a unified, modern interface for CRM, Support, Finance, HR, Inventory, Projects, and more.

## Features

### Core Modules

| Module | Description | Status |
|--------|-------------|--------|
| **CRM** | Contact management, opportunities, sales pipeline | ✅ Complete |
| **Support** | Ticket management, SLA tracking, conversations | ✅ Complete |
| **Finance** | Invoicing, payments, credit notes, AR/AP | ✅ Complete |
| **Accounting** | Chart of accounts, journal entries, financial reports | ✅ Complete |
| **HR** | Employees, departments, leave management, payroll | ✅ Complete |
| **Inventory** | Items, stock levels, warehouses, transfers | ✅ Complete |
| **Projects** | Tasks, timesheets, milestones | ✅ Complete |
| **Field Service** | Work orders, technician dispatch, scheduling | ✅ Complete |
| **Purchasing** | Purchase orders, suppliers, expenses | ✅ Complete |

### Technical Features

- **SSR + HTMX**: Fast, server-side rendered pages with HTMX for interactivity
- **Real-time Updates**: WebSocket support for live data
- **Multi-source Sync**: Automated sync from Splynx, ERPNext, and Chatwoot
- **Unified Data Model**: Consolidated customer, contact, and transaction views
- **REST API**: Full API for mobile apps and integrations
- **Multi-currency**: Support for NGN, USD, and other currencies
- **RBAC**: Role-based access control with granular permissions
- **Audit Trail**: Complete tracking of all changes
- **Observability**: OpenTelemetry integration for tracing and metrics, with
  the bounded scrape contract in `docs/METRICS_SCRAPE_SAFETY.md`

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.0 |
| Frontend | Jinja2 Templates, HTMX, Alpine.js, Tailwind CSS |
| Database | PostgreSQL 15+ |
| Cache | Redis |
| Task Queue | Celery |
| Auth | JWT/OIDC (better-auth compatible) |

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis (for background tasks)
- Node.js 18+ (for Tailwind CSS build)

### Installation

```bash
# Clone repository
git clone https://github.com/dotmac/dotmac-bos.git
cd dotmac-bos

# Install Python dependencies
poetry install

# Copy environment file
cp .env.example .env
# Edit .env with your configuration

# Run database migrations
poetry run alembic upgrade head

# Start the server
poetry run uvicorn app.main:app --reload
```

### Environment Configuration

```env
# Database
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/dotmac_bos

# Authentication
ENVIRONMENT=development
JWKS_URL=https://auth.example.com/.well-known/jwks.json
JWT_ISSUER=https://auth.example.com
CORS_ORIGINS=http://localhost:3000

# Company
DEFAULT_COMPANY=dotmac
COMPANY_NAME=dotMac Limited
PRODUCT_NAME=DotMac BOS

# External Integrations (optional)
SPLYNX_API_URL=https://your-splynx.com/api/2.0
SPLYNX_AUTH_BASIC=base64_encoded_key_secret

ERPNEXT_API_URL=https://your-erpnext.com
ERPNEXT_API_KEY=your_key
ERPNEXT_API_SECRET=your_secret

CHATWOOT_API_URL=https://your-chatwoot.com/api/v1
CHATWOOT_API_TOKEN=your_token

# Redis (for Celery)
REDIS_URL=redis://localhost:6379/0
```

### Running Services

```bash
# Terminal 1: Web Server
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Celery Worker (optional)
poetry run celery -A app.worker:celery_app worker --loglevel=info

# Terminal 3: Celery Beat (optional, for scheduled tasks)
poetry run celery -A app.worker:celery_app beat --loglevel=info
```

### Docker Deployment

```bash
# Development
docker-compose up -d --build

# Production
cp .env.production.example .env.production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Project Structure

```
dotmac-bos/
├── app/
│   ├── api/                    # JSON API routes (mobile/external)
│   ├── core/                   # Core utilities (security, config)
│   ├── models/                 # SQLAlchemy models
│   ├── modules/                # Feature modules
│   │   ├── crm/               # CRM module (contacts, pipeline)
│   │   ├── support/           # Support module (tickets)
│   │   └── .../               # Other modules
│   ├── services/              # Business logic services
│   ├── templates/             # Jinja2 templates
│   │   ├── layouts/           # Base layouts
│   │   ├── components/        # Reusable UI components
│   │   └── pages/             # Full page templates
│   ├── static/                # Static assets (CSS, JS)
│   └── web/                   # SSR web routes
├── tests/                     # Test suite
├── e2e/                       # Playwright E2E tests
├── migrations/                # Alembic migrations
└── scripts/                   # Utility scripts
```

## Module Architecture

Each module follows a consistent structure:

```
app/modules/{module}/
├── routes.py                  # SSR page routes
└── templates/
    ├── pages/                 # Full page templates
    │   ├── list.html         # List/index page
    │   ├── detail.html       # Detail view
    │   └── form.html         # Create/edit form
    └── partials/             # HTMX partials
        ├── table.html        # Table component
        └── row.html          # Single row
```

## API Endpoints

### Web Routes (SSR)

| Route | Description |
|-------|-------------|
| `/` | Dashboard |
| `/crm/contacts` | Contact list |
| `/crm/contacts/{id}` | Contact detail |
| `/support/tickets` | Ticket list |
| `/support/tickets/{id}` | Ticket detail |
| `/accounting/invoices` | Invoice list |
| `/hr/employees` | Employee list |

### JSON API

| Endpoint | Description |
|----------|-------------|
| `GET /api/customers` | List customers |
| `GET /api/finance/dashboard` | Finance KPIs |
| `GET /api/accounting/balance-sheet` | Balance sheet |
| `GET /api/analytics/overview` | Analytics overview |
| `POST /api/sync/all` | Trigger full sync |

Full API documentation available at `/docs` (Swagger UI).

## Testing

```bash
# Run unit tests
poetry run pytest tests/unit/

# Run integration tests
poetry run pytest tests/integration/

# Run E2E tests (requires running server)
cd e2e && npx playwright test

# Run all tests with coverage
poetry run pytest --cov=app --cov-report=html
```

## Design System

DotMac BOS uses a custom design system built on Tailwind CSS:

- **Typography**: DM Sans (display) + Source Sans 3 (body)
- **Primary Color**: Deep Teal (#0d7377)
- **Accent Color**: Warm Amber (#f2a900)
- **Shadows**: Warm shadow system with subtle brown tints
- **Borders**: Rounded corners (xl for cards, lg for buttons)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

Proprietary - dotMac Limited. All rights reserved.

## Support

For issues or questions:
- Email: support@dotmac.ng
- GitHub Issues: [Report a bug](https://github.com/dotmac/dotmac-bos/issues)
