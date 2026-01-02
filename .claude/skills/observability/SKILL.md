---
name: observability
description: Observability skill for logging, metrics, tracing, and runbooks. Invoke with /observability [command].
---

# Observability Skill

Add or review logging, metrics, and alerts for new features.

## Standard Output Format
```
### Findings
- [Severity][artifact] Issue summary + impact

### Risks
- [What could break or regress]

### Fixes
- [Concrete fix or mitigation]

### Tests
- [Verification steps]
```

## Severity Levels
| Severity | Criteria | Action |
|----------|----------|--------|
| Critical | Missing alerting or logging for core outage scenarios | Must fix before merge |
| High | Gaps that block root-cause analysis for core flows | Should fix |
| Medium | Incomplete metrics or tracing coverage | Consider fixing |
| Low | Style or minor improvement | Optional |

## Commands

### `/observability plan [feature]`
Define logs, metrics, traces, and alerts for a feature. Read `reference.md` before drafting.

### `/observability review [code_or_plan]`
Review observability coverage and runbook readiness. Read `reference.md` for checklist.

## References
- See `reference.md` for the metrics/logging checklist and runbook template.
