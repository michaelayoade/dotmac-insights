# Performance Module Architecture

Performance scoring engine for Dotmac Insights covering KPI/KRA definition, data binding to ERP sources, scheduled computation, manager review/overrides, and transparent dashboards for employees, managers, and HR/Exec.

## Components
- **Performance Registry Service**: CRUD for KPIs, KRAs, scorecard templates, role/department mappings, scoring rules, and KPI→data bindings. Lives in FastAPI with SQLAlchemy models.
- **Metrics Computation Engine**: Celery beat schedules (daily/weekly/monthly) enqueue compute jobs; workers fetch bindings, run queries/aggregations, and persist `kpi_result` / `kra_result` / `performance_result` snapshots (immutable after finalization).
- **Review & Override Workflow**: Managers review provisional results, add notes, override scores with required reason; audit log records every change; HR/Exec finalize periods.
- **Performance Data Warehouse Tables**: Aggregated tables inside the ERP/Postgres DB for fast reads (no recompute per request). Historical per period.
- **Dashboards & Reporting UI**: Employee dashboard (own data with evidence links), manager/team view with exception queues, exec heatmaps and trends, bonus eligibility view, training/PIP triggers.
- **Integrations**: Ingest from ticketing, field service/work orders, monitoring, finance/billing, CRM/sales, projects/dev. Export to payroll/bonus module and learning/training module.

## Data Model (new tables)
- **evaluation_period**: `id, period_start, period_end, frequency (daily/weekly/monthly/quarterly), status (open/finalized)`.
- **scorecard_template**: `id, name, role_id?, department_id?, version, effective_from/to, is_active`.
- **kra_definition**: `id, name, description, weight_default`.
- **kpi_definition**: `id, name, description, target_type (numeric/%/duration/count), direction (higher_is_better/lower_is_better/target_band), weight_default, aggregation_period, scoring_method (linear/banded/capped/sigmoid), guardrail_group?`.
- **kra_kpi_map**: `kra_id, kpi_id, weight_override?`.
- **scorecard_template_items**: `template_id, kra_id, kpi_id, weight_override?, target_override?, scoring_method_override?`.
- **kpi_binding**: `kpi_id, source_type (ERP_TABLE/EVENT_STREAM/EXTERNAL_API), source_ref, filter_json, aggregation (count/sum/avg/percentile/ratio), ownership_rule (assigned_to/closed_by/technician_id/team_id/etc), formula_json (for ratios/derived), sample_query?, preview_result?`.
- **employee_scorecard_instance**: `id, employee_id, template_id (versioned), period_id, status (draft/review/final), computed_at, finalized_at, reviewer_id?`.
- **kpi_result**: `employee_id, kpi_id, period_id, actual_value, target_value, raw_score, weighted_score, computed_at, computed_by, evidence_ref (ticket ids/job ids)`.
- **kra_result**: `employee_id, kra_id, period_id, score`.
- **performance_result**: `employee_id, period_id, total_score, rating_band, status (provisional/final)`.
- **score_override**: `entity_type (KPI/KRA/Overall), entity_id, employee_id?, period_id, old_score, new_score, reason, reviewer_id, created_at`.
- **performance_review_note**: `employee_id, period_id, manager_id, note, created_at`.
- **audit_log**: `who, what, before/after, reason, timestamp` (can reuse global audit table).
- **bonus_policy**: `id, name, rules_json (bands, hard gates), effective_from/to`.
- **manager_relationships** (existing/extended): supports review permissions.

> Align foreign keys to existing `employees`, `departments`, `roles`, `users` tables already in the ERP schema.

## Scoring Logic (standardized)
- **Higher is better**: `raw = actual/target`, `score = min(raw, cap) * 100`.
- **Lower is better**: `raw = target/actual`, `score = min(raw, cap) * 100`.
- **Target band**: full score inside band; outside band apply penalties and cap.
- **Derived/ratio**: use `formula_json` to compute numerator/denominator and safe-divide.
- **Guardrails**: pair speed metrics with quality metrics (e.g., closures + reopen rate) via guardrail groups in templates; minimum guardrail score can cap primary KPI score.

## Ownership Rules
- Per KPI binding define attribution: `assigned_owner` (assignee), `closed_by`, `technician_id`, `team_based`, `created_by`, or custom resolver. v1: single owner; v2 can allow weighted contributors.
- Evidence capture: store contributing record ids per KPI result for explainability and audits.

## Compute Pipeline
1) Scheduler enumerates open `evaluation_period`s and active employees/templates.
2) For each KPI binding, build query (SQL/ORM) with filters and aggregation; attribute ownership per rule; compute `actual_value`.
3) Compute `raw_score` via scoring method and `weighted_score` via KPI weight.
4) Aggregate per KRA (`kra_result`) and overall (`performance_result`).
5) Persist results as snapshots; mark `employee_scorecard_instance` status = `draft`.
6) Notify managers/employees (event/webhook); expose in API/UI.
7) Review flow: manager adds notes or overrides (requires reason → `score_override` + `audit_log`); HR/Exec finalizes period (locks results).

## API Surface (proposed)
- **Admin**: CRUD for KPIs/KRAs/templates/bindings; test-run binding preview; activate/deactivate templates; manage bonus policies.
- **Compute Ops**: `POST /performance/compute?period_id=` trigger recompute for a period/employee (idempotent); `GET /performance/periods`.
- **Manager/HR**: list team scorecards, approve/override, add notes, finalize; exception queues (low performers, SLA breaches).
- **Employee**: my dashboard, KPI breakdown with evidence, trend over time, explanations of scoring and targets.
- **Exec**: org/department heatmaps, leaderboards, bonus eligibility export.

## RBAC & Governance
- Employees see only their own scorecards and evidence.
- Managers limited to direct/indirect reports (via `manager_relationships`).
- HR full read/write; Admin config only.
- Every override or config change recorded in `audit_log`; period finalization makes results immutable.

## Data Sources (Dotmac ERP mappings)
- **Ticketing/Helpdesk**: tickets created/closed, SLA breaches, reopen rate, MTTR, CSAT.
- **Field Service/Work Orders**: jobs completed, first-time fix, travel-to-fix time, preventive maintenance completion.
- **Monitoring/NOC**: uptime %, outage counts, detection time, false positives.
- **Finance/Billing**: invoice accuracy, collections/DSO, reconciliation time, revenue leakage flags.
- **CRM/Sales**: pipeline conversion, deal cycle time, churn (account managers).
- **Projects/Dev**: velocity, lead time, escaped defects, deployment frequency (optional for v2).

## Bonus & Training Hooks
- Bonus policies apply bands and hard gates to `performance_result.total_score`; export factor to payroll module.
- Training/PIP: rule-based triggers when KPI or KRA scores drop below thresholds; enqueue recommendations.

## Phased Delivery
- **Phase 1 (MVP)**: Templates (KRA/KPI/weights/targets), ticketing + work order bindings, monthly scoring, manager review/override, employee & manager dashboards.
- **Phase 2**: Add monitoring/finance/CRM sources, banded scoring + guardrails, bonus policy export, evidence links UI.
- **Phase 3**: Team scoring/shared ownership, anomaly detection, deeper recommendations, PIP workflow automation.
