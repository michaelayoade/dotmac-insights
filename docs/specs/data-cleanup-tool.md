# Product Specification: Data Cleanup & Normalization Tool

**Date:** 2026-01-01
**Version:** 1.0
**Status:** Draft
**Related Architecture:** [data-cleanup-tool.md](../architecture/data-cleanup-tool.md)

---

## Problem

Operators face ongoing data quality issues in production:
- Customer phone numbers in inconsistent formats (080..., +234..., 234...)
- Duplicate customer records created through different channels
- Email addresses with typos or invalid formats
- Missing required fields that cause downstream errors
- Orphaned records from deleted parent entities

Currently, fixing these requires:
1. Developer intervention with raw SQL
2. No preview of changes before execution
3. No audit trail of what was changed
4. No ability to undo mistakes
5. No visibility into overall data quality

---

## Goals

1. **Self-service cleanup**: Operators can identify and fix data issues without developer help
2. **Safe operations**: All changes are previewed before execution and can be rolled back
3. **Full audit trail**: Every change is logged with before/after values
4. **Proactive detection**: System scans for issues and surfaces them before they cause problems
5. **Reusable rules**: Common cleanup patterns can be saved and rerun

---

## Non-Goals

- Real-time data validation (handled by application layer)
- Automated cleanup without human review
- Data archival or purging (separate concern)
- Schema changes or migrations
- External data import (handled by Migration module)

---

## Stakeholders

| Role | Interest |
|------|----------|
| Operations Manager | Overall data quality visibility, compliance |
| Customer Support | Fixing individual customer data issues |
| Finance | Accurate customer/subscription data for billing |
| IT Admin | Bulk cleanup operations, audit compliance |
| Developer | Reduced ad-hoc data fix requests |

---

## User Stories

### Epic 1: Data Quality Visibility

**US-1.1: View Data Quality Dashboard**
> As an operations manager, I want to see an overview of data quality across the system so that I can prioritize cleanup efforts.

**US-1.2: Scan for Issues**
> As an IT admin, I want to trigger a scan for data quality issues so that I can identify problems proactively.

**US-1.3: View Issue Details**
> As a customer support agent, I want to see which specific records have issues so that I can fix them.

### Epic 2: Data Cleanup

**US-2.1: Preview Changes**
> As an operator, I want to preview what changes will be made before executing them so that I don't accidentally corrupt data.

**US-2.2: Normalize Phone Numbers**
> As an operator, I want to standardize all phone numbers to E.164 format so that SMS notifications work correctly.

**US-2.3: Fix Email Formats**
> As an operator, I want to correct invalid email addresses so that invoices are delivered successfully.

**US-2.4: Fill Missing Fields**
> As an operator, I want to set default values for required fields that are missing so that records are complete.

**US-2.5: Merge Duplicates**
> As an operator, I want to merge duplicate customer records so that we have a single view of the customer.

### Epic 3: Safety & Compliance

**US-3.1: Rollback Changes**
> As an IT admin, I want to undo a cleanup operation if it caused problems so that I can recover from mistakes.

**US-3.2: View Audit Trail**
> As a compliance officer, I want to see who made what changes and when so that we maintain audit compliance.

**US-3.3: Exclude Records**
> As an operator, I want to exclude specific records from a cleanup operation so that I can handle exceptions.

### Epic 4: Efficiency

**US-4.1: Save Cleanup Rules**
> As an IT admin, I want to save cleanup configurations as reusable rules so that I can run them regularly.

**US-4.2: Bulk Operations**
> As an operator, I want to clean thousands of records in a single operation so that I don't have to fix them one by one.

**US-4.3: Keyboard Shortcuts**
> As a power user, I want keyboard shortcuts for common actions so that I can work efficiently.

---

## Requirements

### R1: Data Quality Dashboard
The system shall provide a dashboard showing:
- Issue counts by severity (critical, high, medium, low)
- Data quality score (percentage of clean records)
- Recent issues with quick-fix actions
- Recent cleanup jobs with status
- Quick action buttons for common cleanups

### R2: Issue Detection
The system shall detect the following issue types:
- **Duplicates**: Records with matching key fields (email, phone, name)
- **Invalid Format**: Phone numbers, emails, dates not matching expected patterns
- **Missing Required**: Null or empty required fields
- **Invalid Values**: Enum fields with values not in allowed set
- **Orphaned Records**: Foreign keys pointing to deleted records
- **Stale Data**: Records not updated beyond threshold

### R3: Scan Operations
The system shall support:
- Manual scan trigger with entity type and issue type filters
- Progress indication during scan (percentage, current step)
- Scan history with results summary
- HTMX-based polling for real-time progress updates

### R4: Cleanup Actions
The system shall support these cleanup actions:
- **Normalize**: Apply formatting rules (phone, email, name, address)
- **Set Default**: Fill missing fields with specified defaults
- **Merge**: Combine duplicate records (Phase 4)
- **Delete**: Remove records with confirmation (Phase 4)
- **Set Null**: Clear invalid values

### R5: Preview Capability
Before any cleanup execution:
- Show before/after comparison for each affected record
- Allow user to select/deselect individual records
- Show count of records to be modified
- Limit preview to 500 records with sampling for larger sets

### R6: Execution & Audit
During cleanup execution:
- Process records in batches (1000 records/batch)
- Log each change to audit log with before/after values
- Store rollback data for undo capability
- Show progress during execution
- Mark resolved issues as RESOLVED

### R7: Rollback Capability
The system shall support:
- One-click rollback for completed jobs
- Confirmation before rollback
- Audit logging of rollback action
- Reopening of issues after rollback

### R8: Cleanup Rules
The system shall support:
- Creating named cleanup rules with configuration
- System-provided default rules (phone normalization, email fix, etc.)
- User-created custom rules
- Activating/deactivating rules
- Running saved rules on demand

### R9: Permissions
The system shall enforce:
- `admin:read` scope for viewing issues and dashboard
- `admin:write` scope for scans, cleanups, and rule management

### R10: Performance
The system shall:
- Process scans of 100k+ records without timeout
- Use background jobs for scans > 10k records
- Not lock tables during cleanup operations
- Complete preview generation in < 10 seconds for 500 records

---

## Acceptance Criteria

### AC-1: Dashboard Display
```gherkin
Given I am logged in with admin:read scope
When I navigate to /settings/data-cleanup/
Then I see issue counts grouped by severity
And I see a data quality score percentage
And I see the 5 most recent issues
And I see the 5 most recent cleanup jobs
And I see a "Scan Now" button
```

### AC-2: Trigger Scan
```gherkin
Given I am on the data cleanup dashboard
When I click "Scan Now"
Then a scan modal appears with entity type checkboxes
When I select "Customers" and "Contacts" and click "Start Scan"
Then a scan job is created and I see a progress indicator
And the progress updates every 2 seconds via HTMX polling
When the scan completes
Then I see a summary of issues found
And the issues appear in the issues list
```

### AC-3: View Issues
```gherkin
Given there are detected cleanup issues
When I navigate to /settings/data-cleanup/issues
Then I see a filterable table of issues
And each issue shows: type, severity, entity, field, record count, status
When I click an issue row
Then I see the affected records with their problematic values
And I see a "Fix This" button
```

### AC-4: Preview Cleanup
```gherkin
Given I am viewing an issue with 50 affected records
When I click "Fix This"
Then I see a cleanup configuration form
When I configure the cleanup action and click "Preview"
Then I see a table with: checkbox, record name, before value, after value
And all checkboxes are selected by default
And I see "Execute" and "Cancel" buttons
And I see the count "50 records will be modified"
```

### AC-5: Execute Cleanup
```gherkin
Given I am on the preview screen with 45 records selected
When I click "Execute"
Then a confirmation modal appears showing "45 records will be modified"
When I confirm
Then the cleanup job executes
And I see a progress indicator
When complete, I see a success message with count
And the issue status changes to "Resolved"
And I can view the job in job history
```

### AC-6: Rollback Cleanup
```gherkin
Given there is a completed cleanup job that modified 45 records
When I view the job detail and click "Rollback"
Then a confirmation modal appears
When I confirm
Then the original values are restored
And the job status changes to "Rolled Back"
And the issue status changes back to "Open"
And an audit log entry is created for the rollback
```

### AC-7: Audit Trail
```gherkin
Given a cleanup job has executed
When I view the audit log
Then I see entries for each modified record
And each entry shows: timestamp, user, action, before value, after value
And entries are linked to the cleanup job
```

### AC-8: Save Cleanup Rule
```gherkin
Given I am on the cleanup rules page
When I click "New Rule"
Then I see a form with: name, description, entity type, issue type, action type, configuration
When I fill the form and click "Save"
Then the rule appears in the rules list
And I can click "Run" to execute it
```

### AC-9: Phone Normalization
```gherkin
Given there are customers with phone formats: "0801234567", "234-801-234-5678", "+234 801 234 5678"
When I run phone normalization cleanup
Then all phones are converted to E.164 format: "+2348012345678"
And the original values are preserved in rollback data
```

### AC-10: Duplicate Detection
```gherkin
Given there are 3 customers with email "john@example.com"
When I run a duplicate scan
Then an issue is created with type "duplicate", record_count 3
And the sample_values show the 3 customer names
And the severity is "HIGH"
```

### AC-11: Exclude from Cleanup
```gherkin
Given I am on the preview screen with 50 records
When I uncheck 5 records
And I click "Execute Selected (45)"
Then only the 45 selected records are modified
And the 5 unchecked records remain unchanged
```

### AC-12: Performance - Large Scan
```gherkin
Given there are 50,000 customer records
When I trigger a scan
Then the scan completes within 60 seconds
And progress is reported every 2 seconds
And the UI remains responsive during the scan
```

---

## UI/UX Requirements

### UX-1: Progressive Disclosure
- Dashboard shows summary; drill down for details
- Issue list shows counts; click for affected records
- Cleanup shows simple form; advanced options expandable

### UX-2: Confirmation for Destructive Actions
- Execute cleanup: confirm with record count
- Rollback: confirm with warning about re-opening issues
- Delete records: double confirmation required

### UX-3: Visual Feedback
- Severity badges: Critical (red), High (orange), Medium (yellow), Low (gray)
- Status badges: Open (blue), In Progress (yellow), Resolved (green), Ignored (gray)
- Progress bars for scans and cleanups
- Toast notifications for success/error

### UX-4: Responsive Design
- Works on tablet (1024px) and desktop
- Tables scroll horizontally on smaller screens
- Modals are full-screen on mobile

### UX-5: Keyboard Navigation
- `j/k`: Navigate issue list
- `Enter`: Open selected issue
- `x`: Toggle record checkbox
- `Shift+E`: Execute cleanup
- `Esc`: Cancel/close modal

### UX-6: Empty States
- No issues: "Your data is clean!" with last scan time
- No scans: "Run your first scan" with button
- No jobs: "No cleanup jobs yet" with CTA

---

## Delivery Milestones

### Phase 1: Foundation (MVP)
**Deliverables:**
- Database models and migration
- Dashboard with mock/static data
- Issue list page (read-only)
- Basic navigation in Settings

**Acceptance:**
- AC-1 (Dashboard Display) - with static data
- Can navigate to cleanup section in settings

---

### Phase 2: Detection
**Deliverables:**
- Scanner infrastructure
- DuplicateDetector
- PhoneFormatDetector
- EmailFormatDetector
- MissingFieldDetector
- HTMX progress polling

**Acceptance:**
- AC-2 (Trigger Scan)
- AC-3 (View Issues)
- AC-10 (Duplicate Detection)
- AC-12 (Performance - Large Scan)

---

### Phase 3: Cleanup Actions
**Deliverables:**
- Preview capability
- NORMALIZE action
- SET_DEFAULT action
- Execution with audit logging
- Job history page

**Acceptance:**
- AC-4 (Preview Cleanup)
- AC-5 (Execute Cleanup)
- AC-7 (Audit Trail)
- AC-9 (Phone Normalization)
- AC-11 (Exclude from Cleanup)

---

### Phase 4: Advanced Features
**Deliverables:**
- MERGE action for duplicates
- DELETE action with safeguards
- Rollback capability
- Saved rules/templates
- Data Explorer integration

**Acceptance:**
- AC-6 (Rollback Cleanup)
- AC-8 (Save Cleanup Rule)

---

### Phase 5: Polish
**Deliverables:**
- Keyboard shortcuts
- Bulk actions bar
- Export issues to CSV
- Scheduled scans (optional)
- Quality trend charts

**Acceptance:**
- UX-5 (Keyboard Navigation)
- All remaining UX requirements

---

## Open Questions

| # | Question | Status | Decision |
|---|----------|--------|----------|
| Q1 | Should we support scheduled/recurring scans? | Open | Consider for Phase 5 |
| Q2 | How long to retain rollback data? | Open | Suggest 30 days default |
| Q3 | Should merge action auto-redirect relations? | Open | Yes, with preview |
| Q4 | Max records per cleanup job? | Open | Suggest 10,000 with warning |
| Q5 | Integration with existing Data Explorer? | Decided | Yes, add issue indicators |

---

## Dependencies

- Existing migration cleaning module (`app/services/migration/cleaning.py`)
- Audit logger service (`app/services/audit_logger.py`)
- Settings module layout and navigation
- HTMX/Alpine.js patterns from app layout

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Data quality score | > 95% | Dashboard metric |
| Developer data fix requests | -80% | Support tickets |
| Time to fix data issue | < 5 min | User testing |
| Cleanup job success rate | > 99% | System logs |
| Rollback usage | < 5% of jobs | System logs |
