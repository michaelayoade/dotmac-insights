---
name: architecture-design
description: System design and architecture skill for planning new features, services, and integrations. Produces high-level designs, tradeoffs, and ADRs. Invoke with /architecture-design [command].
---

# Architecture Design Skill

Design and review system architecture for new features or major refactors.

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
| Critical | Design flaw likely to cause data loss, outage, or security failure | Must fix before merge |
| High | Incorrect results or broken core behavior in the proposed design | Should fix |
| Medium | Edge-case, performance, or maintainability risk | Consider fixing |
| Low | Style or minor improvement | Optional |

## Commands

### `/architecture-design plan [feature]`
Create a high-level design with components, data flow, and storage impact. Read `reference.md` before drafting.

### `/architecture-design review [proposal_or_diff]`
Review a design for correctness, scalability, and maintainability. Read `reference.md` for the template.

### `/architecture-design adr [decision]`
Draft an ADR with context, decision, and consequences. Read `reference.md` for ADR format.

## References
- See `reference.md` for the design template and ADR format.
