# Pre-Production Checklist

Use this list before enabling production traffic or toggling risky feature flags.

## Auth & RBAC
- [ ] JWT/service token paths: valid → 200, invalid/expired → 401, missing scope → 403 (tests green).
- [ ] Role/permission seeds applied and idempotent; contacts/tickets/billing scopes present.
- [ ] Public routes limited to intended webhooks; HMAC/signature enforced; no JWT required there.

## API/Controllers
- [ ] Contacts CRUD/lifecycle respect `CONTACTS_DUAL_WRITE_ENABLED` and `SOFT_DELETE_ENABLED`; no legacy orphans on delete.
- [ ] Webhook endpoints accept external payloads without JWT and reject bad signatures (Paystack/Flutterwave/Omni).
- [ ] RBAC tests for contacts endpoints pass in CI.

## Services/Sync
- [ ] Legacy sync matches only by IDs (no email fallback); dual-write failures emit logs + metrics.
- [ ] Outbound sync uses idempotency (hash/key), retries with backoff + DLQ, and metrics; dry-run mode verified in staging.
- [ ] Reconciliation job (if enabled) emits drift metrics and reports.

## Persistence/Migrations
- [ ] All Alembic migrations applied; staging burn-in complete.
- [ ] CHECK/FK constraints validated; no migrations reference nonexistent columns.
- [ ] UnifiedContact backfill done; known data gaps documented (e.g., missing emails) with a remediation plan.

## Background/Jobs
- [ ] Workers available (Celery/task queue); outbound sync/reconciliation tasks wired and monitored.
- [ ] Feature flags default safe; rollout/rollback steps documented.

## Monitoring/Observability
- [ ] `/metrics` accessible; counters for webhook auth failures, contacts auth failures, outbound sync status, drift %, contacts p99 latency collected.
- [ ] Alerts configured for: webhook 401/403 spikes, sync success rate dips, drift % over threshold, contacts p99 over SLO.

## Data Integrity
- [ ] No orphan legacy customers after contact delete/soft-delete paths.
- [ ] Soft delete enforced when flag on; hard delete policy defined and tested.
- [ ] Do-not-contact/opt-in changes propagate to legacy when dual-write is on.

## Performance & Security
- [ ] Load test key endpoints (contacts list/search, webhook ingest); p99 within SLO.
- [ ] CORS restricted to allowed origins; PII in responses limited to need-to-know.

## Runbooks
- [ ] Deployment runbook includes schema_prechecks, migration order, and flag toggles.
- [ ] Rollback plan for feature flags (disable dual-write/outbound sync if issues arise).
