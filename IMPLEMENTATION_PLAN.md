# Integrated Security + Sync/Migration Implementation Plan

## Executive Summary

MVP focused on security hardening, schema integrity, and contacts migration with a 3-4 week timeline. Phases 5-9 deferred until metrics confirm stability.

**MVP Scope**: Phase 1-4 (Security + Schema + FK Cleanup + Contacts)
**Timeline**: 3-4 weeks
**Deferred**: Tickets, Billing native APIs, Inventory FKs, GL refactor (after stability metrics met)

---

## Phase 1: Secure & Validate APIs

**Duration**: Week 1 (Days 1-5)
**Goal**: Lock down API security, verify RBAC, test webhook signatures

### 1.1 Add Contacts/Tickets/Billing Scopes to Permission Seeds

| Item | DRI | DoD |
|------|-----|-----|
| Create migration for new permissions | Backend Lead | Migration runs, scopes in DB, roles updated |
| Unit test: permission exists | Backend Lead | `test_permissions.py` passes |

**File**: `alembic/versions/20251218_add_domain_rbac_scopes.py`

```python
NEW_PERMISSIONS = [
    # Contacts
    ("contacts:read", "View contacts and customers", "contacts"),
    ("contacts:write", "Create, update, delete contacts", "contacts"),
    ("contacts:export", "Export contact data", "contacts"),
    # Tickets
    ("tickets:read", "View support tickets", "support"),
    ("tickets:write", "Create, update tickets", "support"),
    # Billing
    ("billing:read", "View invoices and payments", "billing"),
    ("billing:write", "Create, update invoices and payments", "billing"),
]

ROLE_PERMISSION_UPDATES = {
    "admin": ["contacts:*", "tickets:*", "billing:*"],
    "operator": ["contacts:read", "contacts:write", "tickets:read", "tickets:write"],
    "analyst": ["contacts:read", "contacts:export", "billing:read"],
    "viewer": ["contacts:read"],
}
```

---

### 1.2 Contacts RBAC Tests

| Item | DRI | DoD |
|------|-----|-----|
| Create test file | Backend Lead | `tests/test_contacts_rbac.py` exists |
| Positive tests (4) | Backend Lead | All pass in CI |
| Negative tests (4) | Backend Lead | All pass in CI |

**File**: `tests/test_contacts_rbac.py`

```python
import pytest
from httpx import AsyncClient

class TestContactsRBAC:
    """RBAC enforcement tests for contacts endpoints."""

    # Positive
    async def test_user_with_contacts_read_can_list(self, auth_client_with_scope):
        """User with contacts:read can GET /api/contacts."""
        client = auth_client_with_scope(["contacts:read"])
        response = await client.get("/api/contacts/")
        assert response.status_code == 200

    async def test_user_with_contacts_write_can_create(self, auth_client_with_scope):
        """User with contacts:write can POST /api/contacts."""
        client = auth_client_with_scope(["contacts:write"])
        response = await client.post("/api/contacts/", json={...})
        assert response.status_code in (200, 201)

    async def test_service_token_with_scope_can_access(self, service_token_client):
        """Service token with contacts:read scope can access."""
        client = service_token_client(scopes=["contacts:read"])
        response = await client.get("/api/contacts/")
        assert response.status_code == 200

    # Negative
    async def test_user_without_contacts_read_gets_403(self, auth_client_with_scope):
        """User without contacts:read gets 403."""
        client = auth_client_with_scope(["analytics:read"])  # No contacts scope
        response = await client.get("/api/contacts/")
        assert response.status_code == 403

    async def test_user_without_contacts_write_gets_403_on_post(self, auth_client_with_scope):
        """User with only contacts:read gets 403 on POST."""
        client = auth_client_with_scope(["contacts:read"])
        response = await client.post("/api/contacts/", json={...})
        assert response.status_code == 403

    async def test_invalid_token_gets_401(self, client):
        """Invalid/expired token gets 401."""
        response = await client.get(
            "/api/contacts/",
            headers={"Authorization": "Bearer invalid-token"}
        )
        assert response.status_code == 401

    async def test_service_token_without_scope_gets_403(self, service_token_client):
        """Service token without contacts scope gets 403."""
        client = service_token_client(scopes=["sync:splynx:read"])
        response = await client.get("/api/contacts/")
        assert response.status_code == 403
```

---

### 1.3 Webhook Security Tests

| Item | DRI | DoD |
|------|-----|-----|
| Create test file | Backend Lead | `tests/test_webhooks_security.py` exists |
| Paystack signature tests (3) | Backend Lead | All pass |
| Flutterwave signature tests (3) | Backend Lead | All pass |
| Idempotency test | Backend Lead | Passes |

**File**: `tests/test_webhooks_security.py`

```python
import pytest
import hmac
import hashlib
from httpx import AsyncClient

class TestPaystackWebhookSecurity:
    """Paystack webhook signature verification tests."""

    @pytest.fixture
    def valid_signature(self, payload: bytes, secret: str) -> str:
        return hmac.new(secret.encode(), payload, hashlib.sha512).hexdigest()

    async def test_valid_signature_accepted(self, client, db):
        """Valid signature + payload → 200 + DB write."""
        payload = b'{"event": "charge.success", "data": {...}}'
        signature = self.valid_signature(payload, settings.paystack_webhook_secret)

        response = await client.post(
            "/api/integrations/webhooks/paystack",
            content=payload,
            headers={"x-paystack-signature": signature}
        )
        assert response.status_code == 200
        # Verify DB write
        event = await db.execute(select(WebhookEvent).order_by(WebhookEvent.id.desc()))
        assert event.scalar_one().provider == "paystack"

    async def test_invalid_signature_rejected(self, client):
        """Invalid signature → 401, no DB write."""
        response = await client.post(
            "/api/integrations/webhooks/paystack",
            content=b'{"event": "charge.success"}',
            headers={"x-paystack-signature": "invalid"}
        )
        assert response.status_code == 401

    async def test_missing_signature_rejected(self, client):
        """Missing signature header → 422."""
        response = await client.post(
            "/api/integrations/webhooks/paystack",
            content=b'{"event": "charge.success"}'
        )
        assert response.status_code == 422

    async def test_replay_attack_idempotent(self, client, db):
        """Duplicate provider_event_id → 200 but no duplicate record."""
        # First request
        payload = b'{"event": "charge.success", "data": {"id": "evt_123"}}'
        sig = self.valid_signature(payload, settings.paystack_webhook_secret)
        await client.post("/api/integrations/webhooks/paystack", content=payload, headers={"x-paystack-signature": sig})

        count_before = await db.scalar(select(func.count(WebhookEvent.id)))

        # Replay
        await client.post("/api/integrations/webhooks/paystack", content=payload, headers={"x-paystack-signature": sig})

        count_after = await db.scalar(select(func.count(WebhookEvent.id)))
        assert count_after == count_before  # Idempotent
```

---

### 1.4 Verify Omni Webhook Signature

| Item | DRI | DoD |
|------|-----|-----|
| Audit `app/api/omni.py` | Backend Lead | Document current auth mechanism |
| Add Chatwoot signature verification if missing | Backend Lead | Code + test |
| Test: invalid signature → 401 | Backend Lead | Test passes |

---

### 1.5 Monitoring Setup

| Metric | Alert Threshold | Dashboard |
|--------|-----------------|-----------|
| `webhook_401_count` | >10/hour | Grafana webhook panel |
| `webhook_403_count` | >10/hour | Grafana webhook panel |
| `contacts_403_count` | >5/hour | Grafana API panel |

**Implementation**: Add Prometheus counters in middleware

---

## Phase 2: Schema Hygiene

**Duration**: Week 1-2 (Days 3-10)
**Goal**: Add critical indexes, CHECK constraints, fix ServiceToken FK

### 2.1 Data Quality Prechecks

| Item | DRI | DoD |
|------|-----|-----|
| Create precheck script | Backend Lead | `scripts/schema_prechecks.py` runs without error |

**File**: `scripts/schema_prechecks.py`

```python
#!/usr/bin/env python3
"""
Pre-check data quality before applying constraints.
Run this BEFORE the constraint migration.
"""

CHECKS = [
    # Journal Entry balance check
    {
        "name": "journal_entries_balanced",
        "query": """
            SELECT COUNT(*) as unbalanced_count
            FROM journal_entries
            WHERE ABS(total_debit - total_credit) > 0.01
        """,
        "threshold": 0,
        "fix_query": """
            SELECT id, posting_date, total_debit, total_credit,
                   (total_debit - total_credit) as diff
            FROM journal_entries
            WHERE ABS(total_debit - total_credit) > 0.01
            LIMIT 100
        """,
    },
    # Payment allocation balance
    {
        "name": "payments_allocation_valid",
        "query": """
            SELECT COUNT(*) as invalid_count
            FROM payments
            WHERE (total_allocated + unallocated_amount) > (amount + 0.01)
               OR total_allocated < 0
               OR unallocated_amount < 0
        """,
        "threshold": 0,
    },
    # Supplier FK backfill readiness
    {
        "name": "purchase_invoices_supplier_match",
        "query": """
            SELECT COUNT(*) as unmatched
            FROM purchase_invoices pi
            LEFT JOIN suppliers s ON pi.supplier = s.name OR pi.supplier = s.erpnext_id
            WHERE s.id IS NULL AND pi.supplier IS NOT NULL
        """,
        "threshold": 0,
    },
]

def run_checks():
    for check in CHECKS:
        result = db.execute(text(check["query"])).scalar()
        status = "PASS" if result <= check["threshold"] else "FAIL"
        print(f"[{status}] {check['name']}: {result}")
        if status == "FAIL" and "fix_query" in check:
            print("  Sample records to fix:")
            for row in db.execute(text(check["fix_query"])):
                print(f"    {row}")
```

---

### 2.2 High-Traffic Index Migration (CONCURRENTLY)

| Item | DRI | DoD |
|------|-----|-----|
| Create migration | Backend Lead | Migration file exists |
| Test in staging | DevOps | Indexes created, no locks |
| Deploy to prod | DevOps | Indexes visible in `pg_indexes` |

**File**: `alembic/versions/20251218_add_critical_indexes.py`

```python
"""Add critical indexes for high-traffic queries.

Uses CREATE INDEX CONCURRENTLY to avoid table locks.
"""

def upgrade():
    # Must run outside transaction for CONCURRENTLY
    op.execute("COMMIT")

    # Journal Entry
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_journal_entries_posting_date
        ON journal_entries (posting_date)
    """)

    # GL Entry - composite for account balance queries
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_gl_entries_posting_date_account
        ON gl_entries (posting_date, account)
    """)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_gl_entries_party
        ON gl_entries (party_type, party)
    """)

    # Invoice
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_invoices_invoice_date
        ON invoices (invoice_date)
    """)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_invoices_status_due_date
        ON invoices (status, due_date)
    """)

    # Bank Transaction
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_bank_transactions_date_account
        ON bank_transactions (date, bank_account)
    """)

    # Project
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_projects_status_end_date
        ON projects (status, expected_end_date)
    """)

def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_journal_entries_posting_date")
    op.execute("DROP INDEX IF EXISTS ix_gl_entries_posting_date_account")
    op.execute("DROP INDEX IF EXISTS ix_gl_entries_party")
    op.execute("DROP INDEX IF EXISTS ix_invoices_invoice_date")
    op.execute("DROP INDEX IF EXISTS ix_invoices_status_due_date")
    op.execute("DROP INDEX IF EXISTS ix_bank_transactions_date_account")
    op.execute("DROP INDEX IF EXISTS ix_projects_status_end_date")
```

---

### 2.3 CHECK Constraints (NOT VALID + VALIDATE)

| Item | DRI | DoD |
|------|-----|-----|
| Run prechecks | Backend Lead | All checks pass |
| Create NOT VALID migration | Backend Lead | Constraints added |
| Fix violating records | Backend Lead | Zero violations |
| VALIDATE constraints | Backend Lead | Constraints enforced |

**File**: `alembic/versions/20251218_add_check_constraints_not_valid.py`

```python
"""Add CHECK constraints as NOT VALID first.

Strategy:
1. Add constraint as NOT VALID (instant, doesn't scan table)
2. Run data cleanup to fix violations
3. Run separate migration to VALIDATE (scans but doesn't lock)
"""

def upgrade():
    # Journal Entry balance (NOT VALID - doesn't block existing data)
    op.execute("""
        ALTER TABLE journal_entries
        ADD CONSTRAINT chk_journal_entry_balanced
        CHECK (ABS(total_debit - total_credit) < 0.01)
        NOT VALID
    """)

    # Payment allocation balance
    op.execute("""
        ALTER TABLE payments
        ADD CONSTRAINT chk_payment_allocation_balance
        CHECK (
            total_allocated >= 0
            AND unallocated_amount >= 0
        )
        NOT VALID
    """)

def downgrade():
    op.execute("ALTER TABLE journal_entries DROP CONSTRAINT IF EXISTS chk_journal_entry_balanced")
    op.execute("ALTER TABLE payments DROP CONSTRAINT IF EXISTS chk_payment_allocation_balance")
```

**File**: `alembic/versions/20251218_validate_check_constraints.py`

```python
"""Validate CHECK constraints after data cleanup."""

def upgrade():
    # Validate (scans table but doesn't lock writes)
    op.execute("ALTER TABLE journal_entries VALIDATE CONSTRAINT chk_journal_entry_balanced")
    op.execute("ALTER TABLE payments VALIDATE CONSTRAINT chk_payment_allocation_balance")
```

---

### 2.4 ServiceToken FK Fix

| Item | DRI | DoD |
|------|-----|-----|
| Create migration | Backend Lead | FK changed to SET NULL |
| Test: delete user doesn't cascade tokens | Backend Lead | Integration test passes |

**File**: `alembic/versions/20251218_fix_service_token_fk.py`

```python
def upgrade():
    # created_by_id
    op.drop_constraint('service_tokens_created_by_id_fkey', 'service_tokens', type_='foreignkey')
    op.create_foreign_key(
        'service_tokens_created_by_id_fkey',
        'service_tokens', 'users',
        ['created_by_id'], ['id'],
        ondelete='SET NULL'
    )

    # revoked_by_id
    op.drop_constraint('service_tokens_revoked_by_id_fkey', 'service_tokens', type_='foreignkey')
    op.create_foreign_key(
        'service_tokens_revoked_by_id_fkey',
        'service_tokens', 'users',
        ['revoked_by_id'], ['id'],
        ondelete='SET NULL'
    )
```

---

### 2.5 Monitoring Setup

| Metric | Source | Dashboard |
|--------|--------|-----------|
| `query_p99_contacts` | pg_stat_statements | Grafana DB panel |
| `query_p99_tickets` | pg_stat_statements | Grafana DB panel |
| `index_usage_ratio` | pg_stat_user_indexes | Grafana DB panel |

---

## Phase 3: FK Cleanup

**Duration**: Week 2 (Days 8-14)
**Goal**: Add missing FKs with backfill, fix cascade policies

### 3.1 Supplier FK to PurchaseInvoice

| Item | DRI | DoD |
|------|-----|-----|
| Create migration (NOT VALID) | Backend Lead | FK added |
| Backfill script | Backend Lead | 100% matched |
| VALIDATE FK | Backend Lead | Constraint active |

**File**: `alembic/versions/20251219_add_supplier_fk.py`

```python
def upgrade():
    # Add column
    op.add_column('purchase_invoices', sa.Column('supplier_id', sa.Integer(), nullable=True))

    # Add FK as NOT VALID
    op.execute("""
        ALTER TABLE purchase_invoices
        ADD CONSTRAINT fk_purchase_invoices_supplier_id
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        NOT VALID
    """)

    # Backfill
    op.execute("""
        UPDATE purchase_invoices pi
        SET supplier_id = s.id
        FROM suppliers s
        WHERE (pi.supplier = s.name OR pi.supplier = s.erpnext_id)
          AND pi.supplier_id IS NULL
    """)

    # Create index
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_purchase_invoices_supplier_id
        ON purchase_invoices (supplier_id)
    """)
```

**File**: `alembic/versions/20251219_validate_supplier_fk.py`

```python
def upgrade():
    op.execute("ALTER TABLE purchase_invoices VALIDATE CONSTRAINT fk_purchase_invoices_supplier_id")
```

---

### 3.2 Bank Account FK to BankTransaction

| Item | DRI | DoD |
|------|-----|-----|
| Create migration | Backend Lead | FK + index added |
| Backfill | Backend Lead | 100% matched |
| VALIDATE | Backend Lead | Constraint active |

```python
def upgrade():
    op.add_column('bank_transactions', sa.Column('bank_account_id', sa.Integer(), nullable=True))

    op.execute("""
        ALTER TABLE bank_transactions
        ADD CONSTRAINT fk_bank_transactions_bank_account_id
        FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id)
        NOT VALID
    """)

    # Backfill
    op.execute("""
        UPDATE bank_transactions bt
        SET bank_account_id = ba.id
        FROM bank_accounts ba
        WHERE (bt.bank_account = ba.name OR bt.bank_account = ba.erpnext_id)
          AND bt.bank_account_id IS NULL
    """)
```

---

### 3.3 Sales FKs (quotation_id, customer_id)

| Item | DRI | DoD |
|------|-----|-----|
| SalesOrder.quotation_id | Backend Lead | FK + backfill |
| ERPNextLead.customer_id | Backend Lead | FK (matches Splynx Lead) |

---

### 3.4 Cascade Policies

| Item | DRI | DoD |
|------|-----|-----|
| CreditNote → Invoice: CASCADE | Backend Lead | FK updated |
| CorporateCardTxn → Card: CASCADE | Backend Lead | FK updated |
| Customer/Employee: RESTRICT + soft delete | Backend Lead | Code + migration |

**Soft delete for Customer/Employee:**

```python
# Add to models
is_deleted: Mapped[bool] = mapped_column(default=False, index=True)
deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
deleted_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

# Add check in delete endpoint
@router.delete("/{customer_id}")
async def delete_customer(customer_id: int, db: AsyncSession):
    # Check for related records
    has_invoices = await db.scalar(select(exists().where(Invoice.customer_id == customer_id)))
    if has_invoices:
        raise HTTPException(400, "Cannot delete customer with invoices. Use soft delete.")

    # Soft delete
    customer.is_deleted = True
    customer.deleted_at = utc_now()
```

---

## Phase 4: Contacts Domain Completion

**Duration**: Week 2-4 (Days 10-28)
**Goal**: UnifiedContact backfill, dual-write with feature flag, outbound sync, reconciler

### 4.1 Feature Flags Setup

| Item | DRI | DoD |
|------|-----|-----|
| Add feature flag system | Backend Lead | `app/feature_flags.py` exists ✅ |
| Add flags for contacts features | Backend Lead | Flags configurable via env ✅ |

**File**: `app/feature_flags.py`

```python
from pydantic_settings import BaseSettings

class FeatureFlags(BaseSettings):
    # Contacts
    CONTACTS_DUAL_WRITE_ENABLED: bool = False
    CONTACTS_OUTBOUND_SYNC_ENABLED: bool = False
    CONTACTS_OUTBOUND_DRY_RUN: bool = True
    CONTACTS_RECONCILIATION_ENABLED: bool = False

    # Tickets
    TICKETS_DUAL_WRITE_ENABLED: bool = False
    TICKETS_OUTBOUND_SYNC_ENABLED: bool = False
    TICKETS_OUTBOUND_DRY_RUN: bool = True
    TICKETS_RECONCILIATION_ENABLED: bool = False

    # Data Management
    SOFT_DELETE_ENABLED: bool = False

    class Config:
        env_prefix = "FF_"

feature_flags = FeatureFlags()
```

---

### 4.2 Run UnifiedContact Backfill

| Item | DRI | DoD |
|------|-----|-----|
| Run --status precheck | Backend Lead | Status output documented |
| Run --dry-run | Backend Lead | No errors, counts match |
| Execute backfill | Backend Lead | All records have unified_contact_id |
| Verify --status | Backend Lead | "Ready for NOT NULL" |

```bash
# Week 2 Day 1
python scripts/backfill_unified_contacts.py --status
python scripts/backfill_unified_contacts.py --dry-run
python scripts/backfill_unified_contacts.py
python scripts/backfill_unified_contacts.py --status
```

---

### 4.3 Dual-Write Hooks (Behind Feature Flag)

| Item | DRI | DoD |
|------|-----|-----|
| Modify contacts API | Backend Lead | Dual-write behind flag |
| Unit tests for dual-write | Backend Lead | Tests pass |
| Integration test | Backend Lead | Both tables updated |

**File**: `app/api/contacts/contacts.py`

```python
from app.config.feature_flags import feature_flags

@router.post("/")
async def create_contact(contact: ContactCreate, db: AsyncSession):
    # Always create in UnifiedContact (new primary)
    unified = await unified_contact_service.create(db, contact)

    # Dual-write to legacy Customer (behind flag)
    if feature_flags.CONTACTS_DUAL_WRITE_ENABLED:
        if contact.contact_type in (ContactType.CUSTOMER, ContactType.CHURNED):
            await legacy_customer_service.sync_from_unified(db, unified)

    # Queue outbound sync (behind flag)
    if feature_flags.CONTACTS_OUTBOUND_SYNC_ENABLED:
        await outbound_sync_queue.enqueue(
            entity_type="unified_contact",
            entity_id=unified.id,
            operation="create",
        )

    return unified
```

---

### 4.4 Outbound Sync Service

| Item | DRI | DoD |
|------|-----|-----|
| Create base outbound sync | Backend Lead | `app/sync/outbound/base.py` |
| Contacts outbound to Splynx | Backend Lead | Code + test |
| Contacts outbound to ERPNext | Backend Lead | Code + test |
| Celery task for queue processing | Backend Lead | Task runs |

**File**: `app/sync/outbound/contacts.py`

```python
class ContactsOutboundSync(OutboundSyncBase):
    """Push UnifiedContact changes to external systems."""

    async def sync_to_splynx(self, contact: UnifiedContact) -> Optional[int]:
        """Create or update customer in Splynx."""
        if not feature_flags.CONTACTS_OUTBOUND_SYNC_ENABLED:
            return None

        if contact.splynx_id:
            # Update existing
            await self.splynx_client.update_customer(contact.splynx_id, self._to_splynx_payload(contact))
            return contact.splynx_id
        else:
            # Create new
            result = await self.splynx_client.create_customer(self._to_splynx_payload(contact))
            return result.get("id")

    def _to_splynx_payload(self, contact: UnifiedContact) -> dict:
        return {
            "name": contact.name,
            "email": contact.email,
            "phone": contact.phone,
            # ... map all fields
        }
```

---

### 4.5 Reconciliation Job + Dashboard

| Item | DRI | DoD |
|------|-----|-----|
| Reconciliation Celery task | Backend Lead | Task runs, logs drift |
| OutboundSyncLog table | Backend Lead | Migration + model |
| Dashboard endpoint | Backend Lead | API returns drift report |
| Drift metric | Backend Lead | Prometheus gauge |

**File**: `app/tasks/reconciliation_tasks.py`

```python
@celery_app.task
def reconcile_contacts_with_splynx():
    """Compare UnifiedContact with Splynx and report drift."""
    if not feature_flags.CONTACTS_RECONCILIATION_ENABLED:
        return {"status": "disabled"}

    drift_report = {
        "missing_in_dotmac": [],
        "missing_in_splynx": [],
        "field_mismatches": [],
    }

    # Fetch all from Splynx
    splynx_customers = splynx_client.list_all_customers()
    splynx_by_id = {c["id"]: c for c in splynx_customers}

    # Compare with UnifiedContact
    for contact in db.query(UnifiedContact).filter(UnifiedContact.splynx_id.isnot(None)):
        splynx_record = splynx_by_id.get(contact.splynx_id)
        if not splynx_record:
            drift_report["missing_in_splynx"].append(contact.id)
            continue

        # Field comparison
        mismatches = compare_fields(contact, splynx_record)
        if mismatches:
            drift_report["field_mismatches"].append({
                "unified_id": contact.id,
                "splynx_id": contact.splynx_id,
                "mismatches": mismatches,
            })

    # Update metrics
    drift_pct = len(drift_report["field_mismatches"]) / len(splynx_customers) * 100
    DRIFT_GAUGE.labels(system="splynx", entity="contacts").set(drift_pct)

    return drift_report
```

**Dashboard endpoint**: `app/api/admin/reconciliation.py`

```python
@router.get("/reconciliation/contacts")
async def get_contacts_drift_report(
    system: str = Query("splynx"),
    _: User = Depends(Require("admin:read"))
):
    """Return latest drift report for contacts."""
    pass
```

---

### 4.6 Monitoring

| Metric | Description | Alert |
|--------|-------------|-------|
| `contacts_drift_pct{system}` | % records with field mismatches | >5% |
| `contacts_sync_lag_seconds` | Time since last successful sync | >300s |
| `outbound_sync_success_rate` | Success / Total outbound syncs | <95% |
| `contacts_query_p99_ms` | p99 latency for contact queries | >200ms |

---

## Execution Checklist (MVP)

### Week 1: Security + Schema (Days 1-7)

| Day | Task | DRI | Status |
|-----|------|-----|--------|
| 1 | Add RBAC scopes migration | | [ ] |
| 1 | Create `test_contacts_rbac.py` | | [ ] |
| 2 | Create `test_webhooks_security.py` | | [ ] |
| 2 | Verify omni webhook auth | | [ ] |
| 3 | Run `schema_prechecks.py` | | [ ] |
| 3 | Create indexes migration (CONCURRENTLY) | | [ ] |
| 4 | Create CHECK constraints (NOT VALID) | | [ ] |
| 4 | Fix data violations | | [ ] |
| 5 | VALIDATE constraints | | [ ] |
| 5 | ServiceToken FK fix | | [ ] |
| 6-7 | Testing + monitoring setup | | [ ] |

### Week 2: FK Cleanup + Contacts Backfill (Days 8-14)

| Day | Task | DRI | Status |
|-----|------|-----|--------|
| 8 | Supplier FK migration | | [ ] |
| 8 | Bank account FK migration | | [ ] |
| 9 | Sales FKs (quotation_id) | | [ ] |
| 9 | Cascade policy updates | | [ ] |
| 10 | VALIDATE all new FKs | | [ ] |
| 11 | Run UnifiedContact backfill | | [ ] |
| 12 | Verify backfill complete | | [ ] |
| 13-14 | Testing | | [ ] |

### Week 3-4: Contacts Features (Days 15-28)

| Day | Task | DRI | Status |
|-----|------|-----|--------|
| 15 | Feature flags setup | | [ ] |
| 16 | Dual-write implementation | | [ ] |
| 17 | Dual-write tests | | [ ] |
| 18 | Outbound sync base | | [ ] |
| 19 | Outbound sync Splynx | | [ ] |
| 20 | Outbound sync ERPNext | | [ ] |
| 21 | Reconciliation task | | [ ] |
| 22 | Dashboard endpoint | | [ ] |
| 23 | Monitoring setup | | [ ] |
| 24-25 | Integration testing | | [ ] |
| 26-27 | Staged rollout (flag enable) | | [ ] |
| 28 | Stability verification | | [ ] |

---

## Stability Metrics (Gate for Phase 5+)

Before proceeding to Phase 5 (Tickets), these metrics must be met for 1 week:

| Metric | Target |
|--------|--------|
| Contacts drift % | <2% |
| Outbound sync success rate | >98% |
| Contacts query p99 | <100ms |
| Zero 500 errors on contacts API | 0 |
| Reconciliation job success | 100% |

---

## Deferred Phases (Post-Stability)

| Phase | Description | Prerequisites |
|-------|-------------|---------------|
| 5 | Tickets/Support UnifiedTicket | Contacts stable 1 week |
| 6 | Billing native APIs | Tickets stable 1 week |
| 7 | Outbound sync architecture | Billing stable |
| 8 | Temporal/data hygiene | All domains stable |
| 9 | Inventory/GL refactor | Full stability |

---

## Phase 6: UnifiedTicket Domain (IMPLEMENTED)

**Status**: Complete
**Goal**: Consolidate tickets from Ticket, Conversation, OmniConversation into a single UnifiedTicket model with dual-write, outbound sync, and reconciliation.

### 6.1-6.4 Foundation (Complete)

| Task | Files | Status |
|------|-------|--------|
| UnifiedTicket model | `app/models/unified_ticket.py` | ✅ |
| Migration | `alembic/versions/20251218_add_unified_ticket.py` | ✅ |
| Backfill script | `scripts/backfill_unified_tickets.py` | ✅ |
| Feature flags | `app/feature_flags.py` (TICKETS_*) | ✅ |
| Backlink columns | `alembic/versions/20251218_add_unified_ticket_backlinks.py` | ✅ |

### 6.5-6.7 Sync Services (Complete)

| Service | File | Description |
|---------|------|-------------|
| Dual-write | `app/services/legacy_ticket_sync.py` | Bi-directional sync UnifiedTicket ↔ legacy Ticket/Conversation |
| Outbound sync | `app/services/ticket_outbound_sync.py` | Push to Splynx, ERPNext, Chatwoot with idempotency |
| Reconciliation | `app/services/tickets_reconciliation.py` | Drift detection for all systems |

### Feature Flags

```python
FF_TICKETS_DUAL_WRITE_ENABLED=false   # Sync to legacy tables
FF_TICKETS_OUTBOUND_SYNC_ENABLED=false # Push to external systems
FF_TICKETS_OUTBOUND_DRY_RUN=true      # Log only, no API calls
FF_TICKETS_RECONCILIATION_ENABLED=false # Run drift detection
```

### Metrics Added

| Metric | Type | Labels |
|--------|------|--------|
| `tickets_dual_write_success_total` | Counter | operation |
| `tickets_dual_write_failures_total` | Counter | - |
| `tickets_drift_pct` | Gauge | system |

### RBAC Scopes

Ticket API endpoints now accept both `tickets:read/write` and `support:read/write` for backward compatibility:

```python
ticket_read_dep = Depends(Require("tickets:read", "support:read"))
ticket_write_dep = Depends(Require("tickets:write", "support:write"))
```

---

## Ticket Burn-In Plan

### Phase 1: Dual-Write (Staging)

**Duration**: 48 hours minimum

1. Enable `FF_TICKETS_DUAL_WRITE_ENABLED=true` in staging
2. Monitor:
   - `tickets_dual_write_success_total` / `tickets_dual_write_failures_total`
   - Application logs for dual-write errors
3. Success criteria:
   - Dual-write success rate >99%
   - No 500 errors on ticket endpoints
   - Legacy table data matches unified data

### Phase 2: Outbound Sync Dry-Run (Staging)

**Duration**: 48 hours minimum

1. Enable `FF_TICKETS_OUTBOUND_SYNC_ENABLED=true` (dry-run remains true)
2. Monitor:
   - Log entries for `[DRY-RUN] Would push ticket to...`
   - Payload shapes and idempotency key generation
3. Success criteria:
   - All tickets generate valid payloads
   - No errors in sync log processing

### Phase 3: Outbound Sync Live (Staging)

**Duration**: 48 hours minimum

1. Disable dry-run: `FF_TICKETS_OUTBOUND_DRY_RUN=false`
2. Monitor:
   - `outbound_sync_total{entity_type="unified_ticket",status="success|failure"}`
   - External system responses in `outbound_sync_log`
3. Success criteria:
   - Outbound sync success rate >98%
   - External systems reflect ticket changes

### Phase 4: Reconciliation (Staging)

**Duration**: 24 hours

1. Enable `FF_TICKETS_RECONCILIATION_ENABLED=true`
2. Monitor:
   - `tickets_drift_pct{system="*"}`
   - Reconciliation job completion
3. Success criteria:
   - Drift <2% for all systems
   - Reconciliation job runs without errors

### Phase 5: Production Rollout

Roll out flags one at a time with 24h soak between each:

1. `FF_TICKETS_DUAL_WRITE_ENABLED=true`
2. `FF_TICKETS_OUTBOUND_SYNC_ENABLED=true` (dry-run=true)
3. `FF_TICKETS_OUTBOUND_DRY_RUN=false`
4. `FF_TICKETS_RECONCILIATION_ENABLED=true`

### Rollback Procedure

If metrics degrade below thresholds:

1. Disable offending flag immediately
2. Check `outbound_sync_log` for failed operations
3. Run reconciliation to detect drift
4. Fix root cause before re-enabling
