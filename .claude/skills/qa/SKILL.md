---
name: qa
description: Quality Assurance skill for code review, test generation, edge case analysis, and regression risk assessment. Invoke with /qa [command] or automatically when reviewing code changes.
---

# QA Skill

Perform quality assurance tasks: code review, test generation, edge case enumeration, and regression analysis.

## Commands

### `/qa review [file_or_diff]`
Review code for issues. Automatically reads the target file or git diff.

**What I check:**
- Logic errors (off-by-one, null checks, race conditions)
- Security vulnerabilities (injection, auth bypass, secrets)
- Code smells (duplication, complexity, missing error handling)
- Pattern violations (deviation from project conventions)
- Edge cases not handled

**Required evidence:**
- Provide file/line references for each finding.
- Classify severity (Critical/High/Medium/Low).
- State the specific impact or failure mode.

**Output format (standardized):**
```
## Code Review: [filename]

### Findings
- [Severity][file:line] Issue summary + impact

### Risks
- [What could break or regress]

### Fixes
- [Concrete fix or mitigation]

### Tests
- [Specific tests to add or run]
```

---

### `/qa tests [file]`
Generate tests for a file or function. Matches existing test conventions.

**Process:**
1. Read the target file
2. Find existing tests to match style (`*_test.py`, `test_*.py`, `tests/`)
3. Generate tests covering:
   - Happy path
   - Edge cases (empty, null, boundaries)
   - Error conditions
   - All branches

**Output:** Ready-to-use test code matching project style.

---

### `/qa edge-cases [function_or_input]`
Enumerate edge cases for a function, API endpoint, or input field.

**Categories I check:**
| Category | Examples |
|----------|----------|
| Boundaries | 0, 1, -1, MAX_INT, empty, single element |
| Unicode | Emojis, RTL, zero-width, homoglyphs |
| Time | Leap years, DST, timezones, Y2K38 |
| Concurrency | Race conditions, deadlocks |
| Network | Timeouts, partial responses, retries |
| State | Null, undefined, corrupted, stale |

**Output:** Enumerated list with test values.

---

### `/qa risk [diff_or_file]`
Assess regression risk for a change.

**Analysis:**
1. What existing functionality might break
2. Blast radius (what depends on changed code)
3. Required test coverage
4. Manual verification needed
5. Downstream system impacts

**Output:**
```
## Regression Risk Assessment

### Risk Level: [LOW/MEDIUM/HIGH/CRITICAL]

### Impact Analysis
- [What could break]

### Required Testing
- [ ] [Specific test scenarios]

### Recommended Actions
- [What to verify before merge]
```

---

### `/qa spec-check [spec] [code]`
Verify code implements a specification completely.

**Checks:**
1. All requirements implemented
2. No extra behavior beyond spec
3. Edge cases from spec handled
4. Error conditions specified are covered

---

### `/qa test-plan [feature]`
Generate a test plan for a feature.

**Output format:**
```markdown
## Test Plan: [Feature Name]

### Functional Tests
- [ ] [Test case]

### Edge Cases
- [ ] [Edge case test]

### Security Tests
- [ ] [Security verification]

### Performance Considerations
- [ ] [Performance test if applicable]
```

---

## Automatic Activation

This skill activates automatically when:
- Reviewing a PR or diff
- Asked to "check", "review", or "test" code
- Creating tests for existing code
- Asked about edge cases or what could go wrong

## Review Checklist
- Verify auth/RBAC and permission scopes.
- Check validation and error handling.
- Confirm DB access is safe and efficient (no N+1, indexes).
- Confirm response serialization and pagination format.
- Call out missing tests or verification steps.

## Integration with Project

**Test Framework Detection:**
- Python: pytest (check for `conftest.py`, `pytest.ini`)
- JavaScript: jest, vitest, mocha (check `package.json`)
- Match existing test file naming and structure

**Pattern Detection:**
- Read existing tests before generating new ones
- Follow project's assertion style
- Use project's fixtures and helpers

## Quality Standards

When reviewing, I apply these severity levels:

| Severity | Criteria | Action |
|----------|----------|--------|
| Critical | Security flaw, data loss, crash | Must fix before merge |
| High | Incorrect results or broken core behavior | Should fix |
| Medium | Edge-case, performance, or maintainability risk | Consider fixing |
| Low | Style, minor improvement | Optional |

## Anti-Patterns I Avoid

- Flagging every possible issue (prioritize by impact)
- Generating tests without reading existing tests first
- Over-testing implementation details vs behavior
- Suggesting changes outside the scope of review
- False positives on intentional patterns

## References
- See `reference.md` for concrete review patterns and test examples.
