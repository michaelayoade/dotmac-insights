---
name: delivery-planning
description: Delivery planning skill for milestones, estimates, dependencies, and rollout. Invoke with /delivery-planning [command].
---

# Delivery Planning Skill

Plan implementation milestones and delivery for a feature or project.

## Standard Output Format
```
### Findings
- [Severity][milestone] Issue summary + impact

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
| Critical | Missing dependency or rollout gap likely to cause outage/data loss | Must fix before merge |
| High | Plan flaw that risks missing core delivery goals | Should fix |
| Medium | Sequencing, estimation, or resourcing risk | Consider fixing |
| Low | Style or minor improvement | Optional |

## Commands

### `/delivery-planning plan [feature]`
Create milestones, deliverables, and dependencies with estimates. Read `reference.md` before drafting.

### `/delivery-planning review [plan]`
Review a plan for risk, scope, and sequencing. Read `reference.md` for the template.

## References
- See `reference.md` for the milestone template and rollout checklist.
