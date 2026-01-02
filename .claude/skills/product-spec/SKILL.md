---
name: product-spec
description: Product specification skill for capturing requirements, acceptance criteria, and scope. Invoke with /product-spec [command].
---

# Product Specification Skill

Turn user needs into clear requirements and acceptance criteria.

## Standard Output Format
```
### Findings
- [Severity][section] Issue summary + impact

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
| Critical | Missing requirement that leads to security/data loss or core failure | Must fix before merge |
| High | Incorrect or ambiguous requirement that breaks core behavior | Should fix |
| Medium | Edge-case, acceptance-criteria gap, or unclear scope | Consider fixing |
| Low | Style or minor improvement | Optional |

## Commands

### `/product-spec draft [feature]`
Draft a spec with goals, scope, requirements, and acceptance criteria. Read `reference.md` before drafting.

### `/product-spec review [spec]`
Review a spec for clarity, completeness, and testability. Read `reference.md` for the template.

## References
- See `reference.md` for the spec template and acceptance criteria format.
