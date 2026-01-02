---
name: security-review
description: Security review skill for auth, data handling, threat modeling, and compliance checks. Invoke with /security-review [command].
---

# Security Review Skill

Review code and designs for security risks and compliance gaps.

## Standard Output Format
```
### Findings
- [Severity][file:line or section] Issue summary + impact

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
| Critical | Exploitable vulnerability or data loss risk | Must fix before merge |
| High | Auth or data exposure risk in core flows | Should fix |
| Medium | Defense-in-depth or hardening gap | Consider fixing |
| Low | Style or minor improvement | Optional |

## Commands

### `/security-review scan [file_or_diff]`
Scan for auth, injection, secrets, and data exposure risks. Read `reference.md` for checklist.

### `/security-review threat-model [feature]`
List assets, attack surfaces, and mitigations. Read `reference.md` for template.

## References
- See `reference.md` for the security checklist and threat model template.
