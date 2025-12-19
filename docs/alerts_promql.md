# PromQL Cheatsheet for Contacts Rollout

Use these examples to build dashboards/alerts during burn-in.

## Dual-write
- Success rate (5m):  
  `sum(rate(contacts_dual_write_success_total[5m])) / sum(rate(contacts_dual_write_success_total[5m]) + rate(contacts_dual_write_failures_total[5m]))`
- Failures > 0 (5m):  
  `sum(rate(contacts_dual_write_failures_total[5m])) > 0`

## Outbound sync
- Success rate by target (5m):  
  `sum by (target)(rate(outbound_sync_total{status="success"}[5m])) / sum by (target)(rate(outbound_sync_total[5m]))`
- Failures by target (5m):  
  `sum by (target)(rate(outbound_sync_total{status="failure"}[5m]))`

## Drift
- Drift percentage per system:  
  `contacts_drift_pct` (alert if > 2)

## Auth failures
- Webhook auth failures (5m):  
  `sum(rate(webhook_auth_failures_total[5m]))`
- Contacts auth failures (5m):  
  `sum(rate(contacts_auth_failures_total[5m]))`

## Latency
- Contacts p99 latency (histogram_quantile):  
  `histogram_quantile(0.99, sum by (le)(rate(contacts_query_latency_seconds_bucket[5m])))`

## Error budget (contacts 500s)
- If you expose API request totals by status_code:  
  `sum(rate(api_requests_total{endpoint=~"/api/contacts.*", status_code=~"5.."}[5m]))`
