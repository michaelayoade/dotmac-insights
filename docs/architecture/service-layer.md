Unified Service Layer – Lean Architecture

Status

This document describes a target architecture. The codebase is not yet aligned.
See Current State vs Target below and the migration checklist.

Goals

- Single source of truth for business logic
- Keep API and web routes thin
- Avoid transaction/caching mistakes
- Keep async/sync consistent

Design Principles

- Services are pure business logic: no Request/Response, no templates, no Pydantic.
- Routes own validation, auth, and serialization.
- Transactions are controlled at the route/use-case boundary.
- Services return domain objects or plain dicts, never ORM objects in API responses.
- Scoping (tenant/user) is enforced centrally.

Directory Layout (minimal)

app/services/
  base.py                 # query helpers, not full CRUD
  errors.py
  types.py                # simple shared types (PaginationParams, etc.)
  accounting/
    __init__.py
    invoices.py
    invoice_types.py
    ar_payments.py
    ar_payment_types.py
    ap_payments.py        # Supplier payments
    ap_payment_types.py
    journal_entries.py    # Journal entry management
    journal_entry_types.py
    ledger.py             # Chart of Accounts + GL Entries
    ledger_types.py
    banking.py            # Bank accounts, transactions, import
    banking_types.py
    tax_service.py        # Tax filing periods, payments, dashboard
    tax_types.py
  crm/
    __init__.py
    opportunities.py      # Deal pipeline management
    opportunity_types.py
  identity/
    parties.py            # Party-based identity model (replaces contacts)
    party_types.py
  support/
    tickets.py
    ticket_types.py

Current State vs Target

Current state (today):
- Services are mostly flat under app/services/ (60+ files).
- No shared base.py, types.py, or scoped_query()/paginate() helpers.
- services/errors.py exists and defines http_code/message for ServiceError.
- Pagination helpers exist in app/api/accounting/helpers.py.
- Many routes still embed DB queries directly.

Target state (this doc):
- Domain-organized services under app/services/<domain>/.
- Shared helpers in app/services/base.py and app/services/types.py.
- Service errors expose http_code/message for route translation.
- Routes call services for all business logic.

Base Service (minimal, no commit)

- No auto-commit in service methods.
- Only shared helpers: pagination, safe filters, common scoping.
- No generic CRUD unless it is truly common.

Routing Pattern

- API route:
  - Parse/validate -> call service -> serialize to schema -> return JSON
- Web route:
  - Parse/validate -> call service -> render template

Routing Integration

Error handling and service construction should be standardized in the route layer.

Error handling

Use a single ServiceError family and translate to HTTPException at the edge:

```python
try:
    invoice = service.create_invoice(data)
    db.commit()
except ServiceError as exc:
    db.rollback()
    raise HTTPException(status_code=exc.http_code, detail=exc.message)
```

Service instantiation via dependency injection

Prefer route dependencies to ensure consistent scoping and testability:

```python
def get_invoice_service(db: DB, user: SessionUser) -> InvoiceService:
    return InvoiceService(db, user)


@router.post("/invoices")
def create_invoice(
    data: InvoiceCreate,
    service: InvoiceService = Depends(get_invoice_service),
    db: DB = Depends(get_db),
):
    invoice = service.create_invoice(data.model_dump())
    db.commit()
    return InvoiceSchema.from_orm(invoice)
```

Auth & Scoping

- Services accept principal or tenant_id.
- Base helper enforces scoping consistently:
  - query = apply_scoping(query, principal)
  - No service may skip this.

Transactions

- Use unit-of-work per request:
  - try: ...; db.commit(); except: db.rollback()
- Services do not commit.

Caching

- Explicit cache per service method.
- Invalidation called by routes after commit.

---

Service Layer Template

# app/services/accounting/invoices.py
class InvoiceService:
    def __init__(self, db, principal):
        self.db = db
        self.principal = principal

    def list_invoices(self, filters, pagination):
        query = scoped_query(self.db.query(Invoice), self.principal)
        query = apply_invoice_filters(query, filters)
        return paginate(query, pagination)

    def create_invoice(self, data):
        invoice = Invoice(**data)
        self.db.add(invoice)
        self.db.flush()
        return invoice

---

Migration Checklist (Incremental)

Phase 1 – Foundations

- Define services/errors.py
- Define services/types.py (PaginationParams, FilterParams)
- Add services/base.py with:
  - scoped_query()
  - paginate() helper
  - safe_filter() with whitelist

Status:
- services/errors.py: DONE - ServiceError, NotFoundError, ValidationError, ConflictError, ForbiddenError
- services/types.py: DONE - PaginationParams, PaginatedResult, SortParams
- services/base.py: DONE - scoped_query(), paginate(), safe_filter(), apply_sort()

Phase 2 – One Pilot Module

- Pick invoices.
- Move all DB logic into InvoiceService.
- Update API + web routes to call service.
- Add tests for service methods.

Status:
- services/accounting/__init__.py: DONE
- services/accounting/invoice_types.py: DONE - InvoiceFilters, InvoiceCreateData, InvoiceUpdateData, InvoiceLineData
- services/accounting/invoices.py: DONE - InvoiceService with list, get, create, update, delete, submit, post, cancel
- api/accounting/invoices.py: DONE - Refactored to use InvoiceService
- Web routes: SSR routes may keep view-specific queries for relationship loading; service pattern optional

Phase 3 – Expand

- Repeat for payments, tickets, contacts.
- Remove duplicated code in routes as you go.

Status:
- services/accounting/ar_payment_types.py: DONE - PaymentFilters, AllocationData, PaymentCreateData, PaymentUpdateData
- services/accounting/ar_payments.py: DONE - ARPaymentService with list, get, create, update, delete, add_allocations
- api/accounting/ar_payments.py: DONE - Refactored to use ARPaymentService
- services/support/ticket_types.py: DONE - TicketFilters, TicketCreateData, TicketUpdateData, CommentData, ActivityData, AssignmentData, SLAUpdateData, DependencyData, CommunicationData, MergeData, SplitData
- services/support/tickets.py: DONE - TicketService with full CRUD, comments, activities, tags, watchers, assignment, SLA, dependencies, communications, merge/split (Segments 1-4)
- api/support/tickets.py: DONE - All ticket endpoints use TicketService
- Contacts: N/A - Replaced by Party system
- services/identity/party_types.py: DONE - PartyFilters, PartyCreateData, PartyUpdateData, PartyRoleCreateData, PartyRoleUpdateData, PartyRelationCreateData, PartyRelationUpdateData
- services/identity/parties.py: DONE - PartyService with party CRUD, roles, relations, external ID lookup
- api/crm/parties.py: DONE - All party endpoints use PartyService
- services/crm/opportunity_types.py: DONE - OpportunityFilters, OpportunityCreateData, OpportunityUpdateData, PipelineSummary, StageSummary
- services/crm/opportunities.py: DONE - OpportunityService with CRUD, stage movement, win/loss tracking, pipeline analytics
- api/crm/opportunities.py: DONE - All opportunity endpoints use OpportunityService
- services/accounting/ap_payment_types.py: DONE - APPaymentFilters, APAllocationData, APPaymentCreateData, APPaymentUpdateData
- services/accounting/ap_payments.py: DONE - APPaymentService with CRUD, allocations, workflow (submit/approve/reject/post), outstanding bills
- api/accounting/ap_payments.py: DONE - All supplier payment endpoints use APPaymentService
- services/accounting/journal_entry_types.py: DONE - JEFilters, JELineData, JECreateData, JEUpdateData
- services/accounting/journal_entries.py: DONE - JournalEntryService with CRUD, validation, workflow (submit/approve/reject/post)
- api/accounting/journal_entries.py: DONE - All journal entry endpoints use JournalEntryService
- services/accounting/ledger_types.py: DONE - AccountFilters, AccountCreateData, AccountUpdateData, AccountBalanceInfo, AccountLedgerFilters, LedgerEntry, AccountLedgerResult, ChartOfAccountsNode, GLEntryFilters, GLEntryCreateData, GLEntryUpdateData
- services/accounting/ledger.py: DONE - LedgerService with Account CRUD, account balance, account ledger with running balance, chart of accounts tree, GL Entry CRUD
- api/accounting/ledger.py: DONE - All ledger endpoints use LedgerService
- services/accounting/banking_types.py: DONE - BankAccountFilters, BankAccountCreateData, BankAccountUpdateData, BankAccountBalanceInfo, BankTransactionFilters, BankTransactionSplitData, BankTransactionCreateData, BankTransactionUpdateData, ImportColumnMapping, ParsedTransaction, ImportResult
- services/accounting/banking.py: DONE - BankingService with Bank Account CRUD, Bank Transaction CRUD with splits, CSV/OFX import, reconciliation status
- api/accounting/banking.py: DONE - All banking endpoints use BankingService
- services/accounting/tax_types.py: DONE - TaxFilingFilters, TaxFilingCreateData, TaxFilingUpdateData, TaxPaymentCreateData, TaxDashboardSummary
- services/accounting/tax_service.py: DONE - TaxService with filing period CRUD, workflow (file, pay), dashboard summary
- api/accounting/tax.py: DONE - Tax filing endpoints use TaxService
- services/accounting/fiscal_types.py: DONE - FiscalYearFilters, FiscalYearCreateData, FiscalYearUpdateData, CostCenterFilters, CostCenterCreateData, CostCenterUpdateData, ExpenseByAccount, CostCenterExpenseBreakdown
- services/accounting/fiscal.py: DONE - FiscalService with Fiscal Year CRUD, Cost Center CRUD with expense breakdown
- api/accounting/fiscal.py: DONE - All fiscal endpoints use FiscalService
- services/accounting/reports_types.py: DONE - TrialBalanceParams, FinancialRatiosParams
- services/accounting/reports.py: DONE - ReportsService with trial balance, financial ratios
- api/accounting/reports.py: PARTIAL - trial-balance/financial-ratios use ReportsService; balance-sheet/income-statement/cash-flow/equity-statement retain inline logic (complex IFRS 16/IAS 12/IAS 37 classification)

Phase 4 – Cleanup

- Ensure all routes call services.
- Add lint rule or code review rule: no DB queries in routes.
