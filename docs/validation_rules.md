# Soft Validation Rules

This document defines the soft validation rules applied across all modules. Soft validation never blocks writes; it records warnings that are returned via HTTP headers and can be logged for cleanup.

## Output Format

Warnings are emitted per request in the `X-Validation-Warnings` header. The value is a base64-encoded JSON array of warning objects. `X-Validation-Warnings-Count` contains the total count.

Example decoded payload:

```json
[
  {
    "severity": "warning",
    "code": "missing_required",
    "field": "scheduled_at",
    "message": "scheduled_at is required",
    "model": "SocialPost",
    "record_id": 123
  }
]
```

## Persistence

Soft validation warnings are stored in `finance_validation_issues` for audit and backfill workflows. Each record stores `model_name`, `record_id`, `scope`, `issues`, and `detected_at`. Scopes include `finance`, `inventory`, `assets`, `omnichannel`, and `marketing`. Updates overwrite the previous issue list for the same record.

## Validation Endpoint

`POST /v1/accounting/validation/finance` runs soft validation on finance models and stores findings. Optional request fields:

- `models`: list of model names (e.g., `Invoice`, `PaymentSubscription`)
- `record_ids`: list of record IDs (applied per model)
- `limit`: per-model cap to prevent large scans

Additional module endpoints:

- `POST /v1/inbox/validation/omnichannel`
- `POST /v1/marketing/validation/marketing`

## Severity

- `info`: low-risk issues that help with data hygiene.
- `warning`: missing or inconsistent data that can cause workflow problems.
- `error`: serious issues, but still non-blocking in soft mode.

## Core Rule Categories (Global)

1) Requiredness
   - Warn when non-nullable columns are missing and no defaults exist.
   - Conditional requiredness can be added in module rules (future).

2) Format & Pattern
   - Email, phone (E.164), URL, UUID, slug, ISO datetime.

3) Enum & Allowed Values
   - Warn on invalid enum values; normalize when possible.

4) Range & Length
   - Warn on values outside reasonable ranges or exceeding string length limits.

5) Uniqueness (Soft)
   - Warn on duplicates when not enforced at the DB layer.

6) Referential Integrity
   - Warn when an FK points to a missing or inactive record.

7) Temporal Rules
   - Warn when start/end or scheduled/published timestamps are reversed.

8) Consistency Rules
   - Status requires related fields (e.g., delivered_at when delivery_status=delivered).

9) Security / Secrets
   - Warn when expected credentials or tokens are missing.

10) Completeness for UX
   - Warn when key UI fields are missing (display name, title, summary).

## Current Implemented Rules

The following checks are automatically applied to all SQLAlchemy models:

- Non-nullable columns without defaults must not be `None`.
- String columns must not exceed declared `length`.
- Enum columns must contain valid values.
- Date range checks for common field pairs:
  - `starts_at` <= `ends_at`
  - `start_at` <= `end_at`
  - `start_date` <= `end_date`
  - `from_date` <= `to_date`
  - `scheduled_at` <= `published_at`

## Module Rule Packs (Implemented)

- Marketing
  - Social posts scheduled require `scheduled_at`.
  - Social posts published require `published_at`.
  - WhatsApp posts require recipients or a default recipient.
  - Email sends require timestamps for delivered/opened/clicked/bounced statuses; failed sends require `error`.

- Omnichannel
  - Inbound messages require `participant_id`.
  - Outbound messages require `agent_id` (when present on the model).
  - `delivery_status` requires corresponding timestamps (`sent_at`, `delivered_at`, `read_at`).
  - Resolved/closed conversations require `resolved_at`.
  - Snoozed conversations require `snoozed_until`.
  - Conversations require valid `channel_id`, `status`, and `priority`, plus non-negative counts.
  - Channels enforce supported types, Chatwoot inbox IDs, and configuration for active channels.
  - Participants require a supported `channel_type` and a reasonable handle format.
  - Attachments require filename or URL, non-negative sizes, and MIME type for URLs.
  - Webhook events require `provider_event_id`, retry timestamps, and consistent processed/error state.
  - Routing rules require conditions, supported action types, and required action values.
  - Inbox contacts require email or phone and valid formats.

- Finance
  - Journal entries must balance (`total_debit == total_credit`).
  - Journal entry totals must match the sum of line items.
  - Journal entry line items must not have both debit and credit and must have a non-zero amount.

- Accounting + Billing
  - Invoices: paid invoices require `paid_date`, totals and balances must reconcile.
  - Invoice lines: quantity > 0, rate/amount must not be negative.
  - Purchase invoices: totals reconcile, positive conversion rate, due date after posting date, paid invoices require zero outstanding.
  - Credit/Debit notes: required dates for issued/applied statuses, totals must reconcile.
  - Payments: amount > 0, allocations cannot exceed amount, completed payments require `payment_date`.
  - Supplier payments: allocation totals cannot exceed paid amount.
  - Payment allocations: exactly one of `payment_id` or `supplier_payment_id`, allocated amount > 0.
  - Bank transactions: deposit/withdrawal sanity, allocation totals reconcile, reconciled transactions require zero unallocated.
  - Bank transaction payments: allocated amount > 0, payment entry required.
  - Bank reconciliations: completed reconciliations require total_amount.
  - GL entries: debit/credit sanity, account reference required when account name is present.
  - Accounts: root_type recommended for non-group accounts.
  - Exchange rates: positive rate, distinct currency pair.
  - Fiscal periods: hard closed periods require closed_at.
  - Gateway transactions: amount > 0, net amount reconciles, success requires completed_at, failure requires reason.
- Payment subscriptions: amount > 0, period order valid, cancelled/expired should have cancelled_at.
- Tax/VAT:
  - Tax code rates between 0 and 100, valid date ranges, tax-inclusive codes should have a positive rate.
  - Sales/purchase tax template details: rate within bounds, non-negative tax_amount, account_head required for non-zero rate.
  - Item tax templates: tax_rate within bounds, tax_type required for non-zero rate.
  - Tax filing periods: date order valid, due_date after period_end, non-negative tax base/amount, paid amounts reconcile, filed/paid status requires timestamps/amounts.
  - Tax payments: amount > 0, payment_date not before period start and not after due date.
- Assets:
  - Asset values and quantities must be non-negative; available_for_use_date cannot precede purchase_date.
  - Disposed assets require disposal_date; disposed assets should not be flagged for maintenance.
  - Insurance/warranty date ranges must be valid; insured assets should have insurance_start_date.
  - Depreciation settings: positive counts/frequencies, valid depreciation rates, schedules require dates when amounts are set.
  - CWIP-enabled categories should have a CWIP account configured.
  - Asset settings alert thresholds must be non-negative.
- Inventory:
  - Items: stock items require stock_uom; serial/batch tracking only for stock items; rates/reorder values non-negative.
  - Warehouses: non-group warehouses should have an inventory account.
  - Stock entries: transfers require distinct from/to warehouses, submitted entries require posting_date; line items require qty > 0 and valid warehouses.
  - Stock ledger entries: actual_qty should not be zero; warehouse required; balances should not be negative.
  - Landed cost: charges and amounts non-negative; vouchers require tax lines; taxes require expense_account when amount > 0.
  - Stock receipts/issues: totals > 0; approved/posted entries require approved_at; non-draft entries require posting_date.
  - Transfers: from/to required and distinct; approved/in-transit/completed require approved_at; rejected require rejection_reason.
  - Batches: expiry must be after manufacturing_date; expired batches should be disabled.
  - Serials: status transitions require corresponding timestamps; delivered/issued serials should not remain in a warehouse.
- Marketing:
  - Campaigns: active/completed campaigns should have `starts_at`; completed campaigns should have `ends_at`; budget non-negative.
  - Journey templates and audiences should not have empty configuration.
  - Journeys: active journeys should define `entry_trigger`.
  - Journey steps: wait steps require delay, email steps require `email_template_id`, webhook steps require `webhook_url`, condition steps require `condition_config`.
  - Journey enrollments: active enrollments should have `current_step_id` and `next_action_at`.
  - Social accounts require access tokens for publishing.
  - Email templates should include subject or body content.
  - Email campaigns: scheduled/sent campaigns require `scheduled_at`, send windows must be valid.
  - Integrations: connected integrations require credentials.
  - Consents: revoked consents should include `source`.
  - Suppressions: suppressions should include `reason`.
  - Marketing webhooks: `payload_hash` is recommended for idempotency.

## Recommended Next Rules (Planned)

- CRM: opportunities require `stage` and `party_id`; leads require primary contact info.
- Finance: tax rates must be within valid ranges.
- HR: leave applications require valid date ranges and leave type.
