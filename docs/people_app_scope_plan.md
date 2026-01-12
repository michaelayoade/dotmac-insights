# People App Scope Plan

## Scope Decisions
- Keep: HR, expenses, payroll, performance, recruitment, training.
- Keep: asset assignment to employees only (no depreciation, maintenance, or finance books).
- Keep: approvals/workflows for HR actions and expense requests.

## Phase 1: Inventory (Keep vs. Strip)

### Keep (Core People App)

#### HR Models
- `app/models/hr.py`
- `app/models/employee.py`
- `app/models/hr_settings.py`
- `app/models/hr_attendance.py`
- `app/models/hr_leave.py`
- `app/models/hr_payroll.py`
- `app/models/hr_appraisal.py`
- `app/models/hr_training.py`
- `app/models/hr_recruitment.py`
- `app/models/hr_lifecycle.py`

#### HR Routes + UI
- `app/modules/hr/__init__.py`
- `app/modules/hr/routes/` (all routes)
- `app/modules/hr/templates/` (all templates)

#### Expenses
- `app/models/expense.py`
- `app/modules/expenses/` (routes + templates)
- any expense services/APIs already used by routes

#### Assets (Assignment Only)
- `app/models/asset.py` (keep basic asset register + custodian/employee link)
- `app/models/asset_settings.py` (keep only if still referenced)
- `app/modules/assets/` (keep assignment-focused pages)
- `app/assets/__init__.py` (slim to basic CRUD + assignment endpoints)
- `app/services/assets/` (slim to CRUD + assignment only)

#### Shared Platform (Keep)
- Auth/RBAC: `app/models/auth.py`
- Notifications: `app/models/notification.py` + templates
- Attachments: `app/models/document_attachment.py`
- Activity log: `app/models/activity_log.py`
- Workflows/approvals: `app/models/workflow_task.py` and related services
- Settings/preferences: `app/models/settings.py`, `app/models/user_preference.py`

### Strip (Out of Scope)
- Accounting/tax/reporting: `app/models/accounting.py`, `app/modules/accounting/`, `app/modules/reports/`, `app/models/tax*.py`
- CRM/marketing/sales: `app/models/crm*.py`, `app/models/marketing.py`, `app/models/sales.py`, `app/integrations/marketing/`
- Inventory: `app/models/inventory.py`, `app/modules/inventory/`
- Subscriptions/billing: `app/models/subscription.py`, `app/modules/subscriptions/`
- Network/ISP: `app/modules/network/`, `app/models/router.py`, `app/models/tariff.py`, `app/models/ipv4_*`, `app/models/ipv6_*`, `app/models/radius_*`, `app/models/data_bundle.py`
- Support/omnichannel: `app/models/ticket.py`, `app/models/support_*`, `app/modules/support/`
- Field service/projects: `app/models/field_service.py`, `app/models/project.py`, `app/modules/field_service/`
- Open banking/payments/finance integrations: `app/models/payment*.py`, `app/models/open_banking.py`

## Phase 2: Asset Module Slimming (Assignment Only)

### Keep
- Asset register fields
- Employee assignment (custodian) fields
- Basic CRUD for assets

### Remove
- Depreciation schedules
- Finance books
- Capitalization/disposal workflows
- Maintenance workflows and reminders
- Network integration hooks

### Affected Areas
- `app/models/asset.py`
- `app/services/assets/`
- `app/assets/__init__.py`
- `app/tasks/asset_tasks.py`
- `app/modules/assets/templates/`

## Phase 3: App Wiring Cleanup
- Remove router registrations for stripped modules
- Remove menu/nav items for stripped modules
- Remove background jobs for stripped modules
- Prune settings for removed domains

## Phase 4: Database Migrations
- Create new Alembic migration to drop removed tables
- Drop asset tables tied to depreciation/finance books
- Verify FKs from kept tables do not reference stripped tables
- Snapshot/export data if needed before dropping

## Phase 5: Tests and Validation
- Remove tests for stripped modules
- Keep HR/expenses/payroll/performance/recruitment/training tests
- Add or update tests for asset assignment only
- Run smoke tests for:
  - employee creation
  - payroll run
  - expense claim + approval
  - asset assignment to employee
  - appraisal/recruitment/training flows

## Implementation Order
1. Slim assets to assignment-only
2. Remove out-of-scope modules from app wiring/UI
3. Add migrations to drop unused tables
4. Update tests
5. Run targeted test pass
