# Module UI Page Structure

Standard page structures for DotMac BOS. Defines patterns for all page types.

---

## Page Type Index

| Type | Description | Example Routes |
|------|-------------|----------------|
| List | Entity list with stats, filters, table | `/support/tickets`, `/accounting/invoices` |
| Detail | Single entity view with tabs | `/support/tickets/{id}` |
| Form | Create/edit entity | `/support/tickets/new` |
| Dashboard | Module overview with KPIs + charts | `/support`, `/accounting` |
| Board/Kanban | Drag-drop column view | `/crm/opportunities/board` |
| Calendar | Date-based scheduling | `/field-service/calendar` |
| Map | Geographic visualization | `/field-service/map` |
| Chart/Report | Data visualization focused | `/network/traffic`, `/reports/*` |
| Hub/Card Grid | Card-based navigation hub | `/reports`, `/settings` |

---

## Global Layout Standards

Every page uses the shared app shell. This section defines required layout regions and hooks.

**Layout Regions:**
- Top Bar: module title, global actions, user menu
- Sidebar: primary navigation and module links
- Main Content: page-specific content (all page patterns apply here)

**Data-testid Requirements:**
```
data-testid="app-shell"
data-testid="top-bar"
data-testid="sidebar"
data-testid="sidebar-toggle"      (mobile)
data-testid="global-search-input" (if present)
data-testid="notifications-button"
data-testid="user-menu"
data-testid="main-content"
```

**Layout Notes:**
- Provide a skip link to `main-content` for keyboard users.
- Keep the top bar sticky when content scrolls.
- Sidebar supports collapsible state and mobile overlay.

---

## 1. List Page Pattern

Standard entity listing with contextual stats.

```
┌─────────────────────────────────────────────────────────┐
│ Page Title                       [+ Primary Action]     │
│ Description text                                        │
├─────────────────────────────────────────────────────────┤
│ STATS ROW (2-6 cards, clickable when filterable)        │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│ │ Total   │ │ Status1 │ │ Status2 │ │ Status3 │        │
│ └─────────┘ └─────────┘ └─────────┘ └─────────┘        │
├─────────────────────────────────────────────────────────┤
│ FILTERS BAR                                             │
│ [Search...] [Status ▼] [Date ▼] [More ▼] [Columns]     │
├─────────────────────────────────────────────────────────┤
│ TABLE                                                   │
│ ┌───────────────────────────────────────────────────┐   │
│ │ [☐] Header Row (sortable)                         │   │
│ ├───────────────────────────────────────────────────┤   │
│ │ [☐] Data Row 1                                    │   │
│ │ [☐] Data Row 2                                    │   │
│ └───────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│ BULK ACTIONS (visible when items selected)              │
│ [3 selected] [Action 1] [Action 2] [Delete] [Clear]    │
├─────────────────────────────────────────────────────────┤
│ PAGINATION                                              │
│ Showing 1-25 of 150          [<] [1] [2] [3] ... [>]   │
└─────────────────────────────────────────────────────────┘
```

**Data-testid Requirements:**
```
data-testid="main-content"        (from layout)
data-testid="page-title"
data-testid="page-description"    (optional)
data-testid="stats-grid"
data-testid="stat-card-{key}"
data-testid="filters-bar"
data-testid="{entity}-search"
data-testid="{filter}-filter"
data-testid="{entity}-table"       (table view only)
data-testid="{entity}-row-{id}"    (table view only)
data-testid="empty-state"
data-testid="bulk-actions-bar"
data-testid="pagination"
data-testid="new-{entity}-button"
data-testid="{entity}-grid"        (card grid only)
data-testid="{entity}-card-{id}"   (card grid only)
```

**Stats Card Behavior:**
- Clickable stats filter the list (e.g., clicking "Overdue" shows only overdue items)
- Non-filterable stats (totals, amounts) are display-only with `cursor-default`
- Add `hover:ring-{color}-200` only to filterable stats
- Bulk actions sit directly below the data region and above pagination when present

---

## 2. Detail Page Pattern

Single entity view with summary and tabs.

```
┌─────────────────────────────────────────────────────────┐
│ ← Back Link    Entity #ID          [Edit] [Delete] [▼] │
│                Title / Name                             │
│                [Status Badge] [Type Badge]              │
├─────────────────────────────────────────────────────────┤
│ SUMMARY CARDS (key fields, 3-5 cards)                   │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│ │ Field 1 │ │ Field 2 │ │ Field 3 │ │ Field 4 │        │
│ └─────────┘ └─────────┘ └─────────┘ └─────────┘        │
├─────────────────────────────────────────────────────────┤
│ TABS                                                    │
│ [Overview] [Related] [Files] [Activity]                │
├─────────────────────────────────────────────────────────┤
│ TAB CONTENT PANEL                                       │
│                                                         │
│ (content varies by tab and entity type)                 │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Data-testid Requirements:**
```
data-testid="main-content"
data-testid="page-title"
data-testid="back-link"
data-testid="{entity}-summary"
data-testid="summary-{field}"
data-testid="tabs"
data-testid="tab-{name}"
data-testid="tab-panel-{name}"
data-testid="edit-button"
data-testid="delete-button"
data-testid="actions-menu"
```

**Common Tab Patterns:**
| Tab | Content |
|-----|---------|
| Overview | Primary details, description, metadata |
| Related | Linked entities (invoices, tickets, etc.) |
| Files | Attachments with upload |
| Activity | Timeline/audit log |
| Notes | Internal notes/comments |

---

## 3. Form Page Pattern

Create or edit an entity.

```
┌─────────────────────────────────────────────────────────┐
│ Create/Edit Entity                                      │
│ Description text                                        │
├─────────────────────────────────────────────────────────┤
│ FORM CARD                                               │
│ ┌───────────────────────────────────────────────────┐   │
│ │ Section 1: Required Fields                        │   │
│ │ ┌─────────────────┐ ┌─────────────────┐          │   │
│ │ │ Field 1 *       │ │ Field 2 *       │          │   │
│ │ │ [error msg]     │ └─────────────────┘          │   │
│ │ └─────────────────┘                              │   │
│ ├───────────────────────────────────────────────────┤   │
│ │ Section 2: Optional Fields                        │   │
│ │ ┌─────────────────┐ ┌─────────────────┐          │   │
│ │ │ Field 3         │ │ Field 4         │          │   │
│ │ └─────────────────┘ └─────────────────┘          │   │
│ └───────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│ FOOTER                            [Cancel] [Submit]     │
└─────────────────────────────────────────────────────────┘
```

**Data-testid Requirements:**
```
data-testid="main-content"
data-testid="page-title"
data-testid="{entity}-form"
data-testid="{field}-input"
data-testid="{field}-select"
data-testid="{field}-error"
data-testid="submit-button"
data-testid="cancel-button"
```

---

## 4. Dashboard Page Pattern

Module overview with KPIs, charts, and quick actions.

```
┌─────────────────────────────────────────────────────────┐
│ Module Dashboard                 [Period: This Month ▼] │
│ Overview of module activity                             │
├─────────────────────────────────────────────────────────┤
│ KPI STATS (4-6 cards)                                   │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│ │ KPI 1   │ │ KPI 2   │ │ KPI 3   │ │ KPI 4   │        │
│ │ + trend │ │ + trend │ │ + trend │ │ + trend │        │
│ └─────────┘ └─────────┘ └─────────┘ └─────────┘        │
├─────────────────────────────────────────────────────────┤
│ PRIMARY CHARTS (1-2 charts, side by side)               │
│ ┌─────────────────────────┐ ┌─────────────────────────┐ │
│ │ Chart Title             │ │ Chart Title             │ │
│ │ [Chart Visualization]   │ │ [Chart Visualization]   │ │
│ │                         │ │                         │ │
│ └─────────────────────────┘ └─────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ SECONDARY CONTENT (lists/tables + quick actions)        │
│ ┌─────────────────────────┐ ┌─────────────────────────┐ │
│ │ Recent Items / Alerts   │ │ Quick Actions           │ │
│ │ [Mini table or list]    │ │ [Action cards/links]    │ │
│ │ [View All →]            │ │                         │ │
│ └─────────────────────────┘ └─────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Data-testid Requirements:**
```
data-testid="main-content"
data-testid="page-title"
data-testid="period-selector"
data-testid="dashboard-stats"
data-testid="stat-card-{key}"
data-testid="chart-{name}"
data-testid="chart-{name}-empty"
data-testid="recent-{entity}"
data-testid="quick-actions"
data-testid="quick-action-{name}"
data-testid="dashboard-empty"
```

**KPI Card with Trend:**
```html
<div class="..." data-testid="stat-card-revenue">
    <dt class="text-sm text-gray-500">Revenue MTD</dt>
    <dd class="mt-2 text-3xl font-bold text-gray-900">$45,200</dd>
    <dd class="mt-1 flex items-center text-sm text-emerald-600">
        <svg>↑</svg> 12% vs last month
    </dd>
</div>
```

**Dashboard Notes:**
- When a dashboard KPI mirrors a list stat, use the same label and color semantics.
- Provide empty states for charts and the overall dashboard when data is unavailable.

---

## 5. Board/Kanban Page Pattern

Column-based drag-drop view for workflow stages.

```
┌─────────────────────────────────────────────────────────┐
│ Board Title                      [+ Add] [List View]    │
│ Description                                             │
├─────────────────────────────────────────────────────────┤
│ FILTERS (optional)                                      │
│ [Search...] [Assignee ▼] [Priority ▼]                  │
├─────────────────────────────────────────────────────────┤
│ COLUMNS (horizontally scrollable)                       │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│ │Column 1 │ │Column 2 │ │Column 3 │ │Column 4 │        │
│ │ (12)    │ │  (8)    │ │  (5)    │ │  (3)    │        │
│ ├─────────┤ ├─────────┤ ├─────────┤ ├─────────┤        │
│ │ Card    │ │ Card    │ │ Card    │ │ Card    │        │
│ │ Card    │ │ Card    │ │         │ │         │        │
│ │ Card    │ │         │ │         │ │         │        │
│ │ ...     │ │         │ │         │ │         │        │
│ └─────────┘ └─────────┘ └─────────┘ └─────────┘        │
└─────────────────────────────────────────────────────────┘
```

**Data-testid Requirements:**
```
data-testid="main-content"
data-testid="page-title"
data-testid="board"
data-testid="board-column-{status}"
data-testid="board-card-{id}"
data-testid="view-toggle"
data-testid="board-column-count-{status}"
data-testid="board-column-empty-{status}"
data-testid="board-card-drag-handle"
data-testid="board-drop-target"
```

**Board Notes:**
- Provide visible drop targets and drag handles for accessibility and clarity.
- If filters are present, include `data-testid="filters-bar"`.
- Include keyboard navigation for drag/drop (arrow keys to move focus, space/enter to pick up and drop).
- Announce drag state changes via aria-live region.
- Provide `role="list"`/`role="listitem"` semantics for columns/cards.
- Use roving tab index and `aria-live` announcements for drag/drop state changes.

**Board Loading/Empty States:**
- Show per-column empty placeholders using `data-testid="board-column-empty-{status}"`.
- When loading, use a skeleton column state with `data-testid="board-loading"`.

---

## 6. Calendar Page Pattern

Date-based scheduling and event view.

```
┌─────────────────────────────────────────────────────────┐
│ Calendar                [+ New] [Day|Week|Month] [Today]│
├──────────────────────────────────┬──────────────────────┤
│ CALENDAR GRID                    │ SIDE PANEL (optional)│
│                                  │                      │
│ ┌─────────────────────────────┐  │ Today's Events       │
│ │ Mon  Tue  Wed  Thu  Fri ... │  │ ┌──────────────────┐ │
│ ├─────────────────────────────┤  │ │ Event 1          │ │
│ │ [Events placed on grid]     │  │ │ Event 2          │ │
│ │                             │  │ │ Event 3          │ │
│ │                             │  │ └──────────────────┘ │
│ │                             │  │                      │
│ └─────────────────────────────┘  │ Filters             │
│                                  │ [Technician ▼]      │
│                                  │ [Type ▼]            │
└──────────────────────────────────┴──────────────────────┘
```

**Data-testid Requirements:**
```
data-testid="main-content"
data-testid="page-title"
data-testid="calendar"
data-testid="calendar-view-toggle" (when view toggles exist)
data-testid="calendar-today-btn"
data-testid="calendar-nav-prev"
data-testid="calendar-nav-next"
data-testid="calendar-event-{id}"
data-testid="calendar-sidebar"
data-testid="calendar-empty"
```

**Calendar Notes:**
- If a view toggle is not present, omit the testid and document the fixed view.

---

## 7. Map Page Pattern

Geographic visualization with entity markers.

```
┌─────────────────────────────────────────────────────────┐
│ Map View                              [List View] [⟳]   │
├──────────────────────────────────────┬──────────────────┤
│ MAP CONTAINER                        │ SIDEBAR          │
│                                      │                  │
│ ┌──────────────────────────────────┐ │ Stats            │
│ │                                  │ │ ┌──────────────┐ │
│ │                                  │ │ │ In Field: 5  │ │
│ │         [Map with markers]       │ │ │ Available: 3 │ │
│ │                                  │ │ └──────────────┘ │
│ │                                  │ │                  │
│ │                                  │ │ Active Items     │
│ │                                  │ │ ┌──────────────┐ │
│ └──────────────────────────────────┘ │ │ Item list    │ │
│                                      │ │ (scrollable) │ │
│ LEGEND                               │ └──────────────┘ │
│ [●] In Progress [●] Pending [●] Done │                  │
└──────────────────────────────────────┴──────────────────┘
```

**Data-testid Requirements:**
```
data-testid="main-content"
data-testid="page-title"
data-testid="map-container"
data-testid="map-marker-{id}"
data-testid="map-legend"
data-testid="map-sidebar"
data-testid="map-sidebar-stats"
data-testid="map-sidebar-list"
data-testid="map-empty"
data-testid="map-error"
```

---

## 8. Chart/Report Page Pattern

Data visualization focused pages.

```
┌─────────────────────────────────────────────────────────┐
│ Report Title                [Date Range ▼] [Export ▼]   │
│ Description                                             │
├─────────────────────────────────────────────────────────┤
│ FILTERS (optional)                                      │
│ [Account ▼] [Period ▼] [Compare ▼]                     │
├─────────────────────────────────────────────────────────┤
│ SUMMARY METRICS (optional, 3-4 cards)                   │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐                    │
│ │ Metric 1│ │ Metric 2│ │ Metric 3│                    │
│ └─────────┘ └─────────┘ └─────────┘                    │
├─────────────────────────────────────────────────────────┤
│ CHART(S)                                                │
│ ┌───────────────────────────────────────────────────┐   │
│ │ Chart Title                                       │   │
│ │ [Chart Visualization]                             │   │
│ │                                                   │   │
│ │ Legend: [●] Series 1 [●] Series 2                │   │
│ └───────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│ DATA TABLE (optional, for detailed breakdown)           │
│ ┌───────────────────────────────────────────────────┐   │
│ │ Sortable table with data                          │   │
│ └───────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**Data-testid Requirements:**
```
data-testid="main-content"
data-testid="page-title"
data-testid="report-filters"
data-testid="date-range-picker"
data-testid="export-button"
data-testid="report-summary"
data-testid="chart-{name}"
data-testid="chart-{name}-empty"
data-testid="report-table"
```

**Empty State for Charts:**
```html
<div data-testid="chart-revenue-empty" class="py-12 text-center">
    <svg class="mx-auto h-12 w-12 text-gray-400">...</svg>
    <h3 class="mt-2 text-sm font-medium text-gray-900">No data available</h3>
    <p class="mt-1 text-sm text-gray-500">
        Select a different date range or filter.
    </p>
</div>
```

---

## Stats Card Specifications

**Standard Stats Card (Filterable):**
```html
<a href="?status=overdue"
   class="bg-white rounded-2xl shadow-warm-sm ring-1 ring-gray-100 p-4
          hover:ring-red-200 hover:shadow-warm-md transition-all cursor-pointer group"
   data-testid="stat-card-overdue">
    <p class="text-xs font-medium text-gray-500 uppercase tracking-wide">Overdue</p>
    <p class="mt-1 text-2xl font-display font-bold text-red-600">$12,800</p>
    <p class="text-xs text-gray-400 mt-1 group-hover:text-red-600">View overdue →</p>
</a>
```

**Display-Only Stats Card (Non-filterable):**
```html
<div class="bg-white rounded-2xl shadow-warm-sm ring-1 ring-gray-100 p-4"
     data-testid="stat-card-total">
    <p class="text-xs font-medium text-gray-500 uppercase tracking-wide">Total</p>
    <p class="mt-1 text-2xl font-display font-bold text-gray-900">156</p>
    <p class="text-xs text-gray-400 mt-1">All time</p>
</div>
```

**Color Guide:**
| Stat Type | Text Color | Hover Ring |
|-----------|------------|------------|
| Neutral/Total | `text-gray-900` | - (not clickable) |
| Active/Success | `text-emerald-600` | `hover:ring-emerald-200` |
| Pending/In Progress | `text-amber-600` | `hover:ring-amber-200` |
| Overdue/Error | `text-red-600` | `hover:ring-red-200` |
| Info/Primary | `text-primary-600` | `hover:ring-primary-200` |

---

## Card Grid View (Alternative to Table)

For entities better suited to card display:

```
┌─────────────────────────────────────────────────────────┐
│ CARD GRID                                               │
│ ┌───────────┐ ┌───────────┐ ┌───────────┐              │
│ │ Card 1    │ │ Card 2    │ │ Card 3    │              │
│ │ [Image]   │ │ [Image]   │ │ [Image]   │              │
│ │ Title     │ │ Title     │ │ Title     │              │
│ │ Subtitle  │ │ Subtitle  │ │ Subtitle  │              │
│ │ [Badge]   │ │ [Badge]   │ │ [Badge]   │              │
│ └───────────┘ └───────────┘ └───────────┘              │
│ ┌───────────┐ ┌───────────┐ ┌───────────┐              │
│ │ Card 4    │ │ Card 5    │ │ Card 6    │              │
│ │ ...       │ │ ...       │ │ ...       │              │
│ └───────────┘ └───────────┘ └───────────┘              │
└─────────────────────────────────────────────────────────┘
```

**Data-testid for Card Grid:**
```
data-testid="{entity}-grid"
data-testid="{entity}-card-{id}"
data-testid="empty-state"
```

**Hub Pages (Card Grid):**
- Use the same card grid structure for module hubs like `/reports` and `/settings`.
- Prefer `data-testid="{module}-grid"` and `data-testid="{module}-card-{id}"` where `{module}` is the hub name.

---

## Loading State Standards (All Pages)

- Use skeletons for primary content regions instead of spinners when possible.
- Prefer scoped loading hooks over page-global loading.

**Recommended Loading Hooks:**
```
data-testid="page-loading"
data-testid="{entity}-table-loading"
data-testid="{entity}-grid-loading"
data-testid="chart-{name}-loading"
data-testid="dashboard-loading"
```

---

## Module Routes

### Actual Pages vs Aliases

**Actual Pages** have their own UI and templates.
**Alias Routes** redirect to another page or module.

---

### Accounting

| Route | Type | Stats (if List) |
|-------|------|-----------------|
| `/accounting` | Dashboard | KPIs: Revenue MTD, Expenses MTD, Net Income, Cash Balance |
| `/accounting/invoices` | List | Total, Outstanding, Overdue, Paid MTD |
| `/accounting/invoices/{id}` | Detail | - |
| `/accounting/invoices/new` | Form | - |
| `/accounting/payments/ar` | List | Received MTD, Pending, Unallocated |
| `/accounting/payments/ap` | List | Paid MTD, Pending, Scheduled |
| `/accounting/payments/{id}` | Detail | - |
| `/accounting/journal-entries` | List | Total, Pending Review, This Period |
| `/accounting/accounts` | List (Tree) | By Type counts |
| `/accounting/bank-accounts` | List | Total Balance, Unreconciled |
| `/accounting/bank-accounts/{id}/reconcile` | Form (special) | - |
| `/accounting/suppliers` | List | Total, Active, With Balance |
| `/accounting/aging/ar` | Chart/Report | Current, 30, 60, 90+ buckets |
| `/accounting/aging/ap` | Chart/Report | Current, 30, 60, 90+ buckets |
| `/accounting/reports/balance-sheet` | Chart/Report | Assets, Liabilities, Equity |
| `/accounting/reports/income-statement` | Chart/Report | Revenue, Expenses, Net |
| `/accounting/reports/trial-balance` | Chart/Report | Debits, Credits |
| `/accounting/reports/cash-flow` | Chart/Report | Operating, Investing, Financing |
| `/accounting/tax/codes` | List | Active, By Rate |
| `/accounting/tax/filings` | List | Pending, Filed, Overdue |

---

### Support

| Route | Type | Stats (if List) |
|-------|------|-----------------|
| `/support` | Dashboard | Open, In Progress, Resolved Today, Overdue, CSAT |
| `/support/tickets` | List | Open, In Progress, Waiting, On Hold, Resolved Today, Overdue |
| `/support/tickets/{id}` | Detail | - |
| `/support/tickets/new` | Form | - |
| `/support/agents` | List | Total, Available, Busy, Offline |
| `/support/queues` | List | Per-queue counts |
| `/support/sla` | List | Active, At Risk Today |
| `/support/sla/breaches` | List | Response, Resolution, By Priority |
| `/support/kb/articles` | List | Published, Draft, Views MTD |
| `/support/kb/articles/{id}` | Detail | - |
| `/support/canned-responses` | List | Total, By Category |
| `/support/channels` | List | Active, Ticket volume |
| `/support/automation` | List | Active, Triggers Today |

---

### HR

| Route | Type | Stats (if List) |
|-------|------|-----------------|
| `/hr` | Dashboard | Total Employees, Present Today, On Leave, Open Positions |
| `/hr/employees` | List | Total, Active, On Leave, New MTD |
| `/hr/employees/{id}` | Detail | - |
| `/hr/employees/new` | Form | - |
| `/hr/departments` | List | Total, Headcount per dept |
| `/hr/designations` | List | Total, By Level |
| `/hr/teams` | List | Total, Members per team |
| `/hr/attendance` | List | Present, Absent, Late, Leave Today |
| `/hr/leave` | List | Pending, Approved, Rejected, On Leave Now |
| `/hr/leave/{id}` | Detail | - |
| `/hr/payroll` | List | Draft, Processing, Completed |
| `/hr/payroll/{id}` | Detail | - |
| `/hr/recruitment` | List | Open, Applicants, Interviews |
| `/hr/recruitment/{id}` | Detail | - |
| `/hr/training` | List | Active, Upcoming, Completed |
| `/hr/appraisal` | List | Pending, In Review, Completed |
| `/hr/org-chart` | Chart (special) | - |
| `/hr/my/*` | Self-service pages | Personal stats |

---

### Field Service

| Route | Type | Stats (if List) |
|-------|------|-----------------|
| `/field-service` | Dashboard | Today's Orders, In Progress, Completed, Overdue |
| `/field-service/orders` | List | Today, Scheduled, In Progress, Completed Today, Overdue |
| `/field-service/orders/{id}` | Detail | - |
| `/field-service/orders/new` | Form | - |
| `/field-service/calendar` | Calendar | (Stats in sidebar) |
| `/field-service/dispatch` | Board | Unassigned, In Field, Returning |
| `/field-service/map` | Map | (Stats in sidebar) |
| `/field-service/technicians` | List | Total, Available, On Job, Off Duty |
| `/field-service/technicians/{id}` | Detail/Calendar | - |
| `/field-service/teams` | List | Total, Members, Active Jobs |
| `/field-service/service-types` | List | Active, Avg Duration |

---

### Projects

| Route | Type | Stats (if List) |
|-------|------|-----------------|
| `/projects` | List | Active, On Track, At Risk, Completed MTD |
| `/projects/{id}` | Detail (tabbed) | - |
| `/projects/{id}/tasks` | List (tab) | Total, To Do, In Progress, Done, Overdue |
| `/projects/{id}/milestones` | List (tab) | Total, Upcoming, Completed |
| `/projects/{id}/gantt` | Chart (tab) | - |
| `/projects/new` | Form | - |
| `/projects/templates` | List | Total, Usage count |

---

### Subscriptions

| Route | Type | Stats (if List) |
|-------|------|-----------------|
| `/subscriptions` | List | Active, MRR, Expiring Soon, Suspended |
| `/subscriptions/{id}` | Detail (tabbed) | - |
| `/subscriptions/{id}/usage` | Chart (tab) | - |
| `/subscriptions/new` | Form | - |
| `/subscriptions/tariffs` | List | Active, Subscribers per plan |
| `/subscriptions/tariffs/{id}` | Detail | - |
| `/subscriptions/bundles` | List | Active, Sold MTD |
| `/subscriptions/services` | List | Active, Inactive |
| `/subscriptions/equipment` | List | Deployed, Available, Faulty |

---

### Network

| Route | Type | Stats (if List) |
|-------|------|-----------------|
| `/network` | Dashboard | Routers Online %, Active Alerts, Bandwidth |
| `/network/routers` | List | Total, Online, Offline, Warning |
| `/network/routers/{id}` | Detail | - |
| `/network/pops` | List | Total, Online, Capacity |
| `/network/pops/{id}` | Detail | - |
| `/network/ip-management` | List | Total, Assigned, Available, Util % |
| `/network/addresses` | List | Assigned, Static, Dynamic |
| `/network/networks` | List | Subnets, Utilization |
| `/network/noc/alerts` | List | Critical, Warning, Info, Acknowledged |
| `/network/traffic` | Chart | - |

---

### CRM

| Route | Type | Stats (if List) |
|-------|------|-----------------|
| `/crm` | Dashboard | Contacts, Pipeline Value, Won MTD |
| `/crm/contacts` | List | Total, Customers, Leads, New MTD |
| `/crm/contacts/{id}` | Detail | - |
| `/crm/contacts/new` | Form | - |
| `/crm/leads` | List | Total, New, Qualified, Converted |
| `/crm/opportunities` | List | Open, Pipeline Value, Won, Lost |
| `/crm/opportunities/board` | Board | (Columns by stage) |
| `/crm/activities` | List | Today, Overdue, Completed |
| `/crm/campaigns` | List | Active, Leads Generated |

---

### Sales

| Route | Type | Stats (if List) |
|-------|------|-----------------|
| `/sales` | Dashboard | Quotations, Orders, Revenue MTD |
| `/sales/quotations` | List | Total, Draft, Sent, Accepted |
| `/sales/quotations/{id}` | Detail | - |
| `/sales/orders` | List | Pending, Fulfilled, Revenue MTD |
| `/sales/orders/{id}` | Detail | - |

---

### Purchasing

| Route | Type | Stats (if List) |
|-------|------|-----------------|
| `/purchasing` | Dashboard | Orders, Bills, Spend MTD |
| `/purchasing/orders` | List | Draft, Pending, Received |
| `/purchasing/orders/{id}` | Detail | - |
| `/purchasing/bills` | List | Unpaid, Overdue, Paid MTD |
| `/purchasing/expenses` | List | Pending, Approved, Rejected |
| `/purchasing/debit-notes` | List | Draft, Applied |
| `/purchasing/payments` | Alias → `/accounting/payments/ap` | - |

---

### Inventory

| Route | Type | Stats (if List) |
|-------|------|-----------------|
| `/inventory` | Dashboard | Items, Low Stock, Stock Value |
| `/inventory/items` | List | Total, In Stock, Low Stock, Out |
| `/inventory/items/{id}` | Detail | - |
| `/inventory/stock-entries` | List | Today, This Week, By Type |
| `/inventory/warehouses` | List | Total, Capacity |
| `/inventory/transfers` | List | Pending, In Transit, Completed |
| `/inventory/batches` | List | Active, Expiring, Expired |
| `/inventory/serials` | List | In Stock, Sold, Returned |

---

### Expenses

| Route | Type | Stats (if List) |
|-------|------|-----------------|
| `/expenses` | List | Total MTD, Pending, Approved, Rejected |
| `/expenses/{id}` | Detail | - |
| `/expenses/new` | Form | - |
| `/expenses/categories` | List | Active, Spend per Category |
| `/expenses/advances` | List | Outstanding, Cleared, Overdue |

---

### Vehicles

| Route | Type | Stats (if List) |
|-------|------|-----------------|
| `/vehicles` | List | Total, Available, In Use, Maintenance |
| `/vehicles/{id}` | Detail | - |
| `/vehicles/maintenance` | List | Scheduled, Overdue, Completed |
| `/vehicles/fuel-logs` | List | Liters MTD, Cost MTD |
| `/vehicles/assignments` | List | Active, By Driver |

---

### Reports

| Route | Type | Notes |
|-------|------|-------|
| `/reports` | Hub (card grid) | Links to all reports |
| `/reports/balance-sheet` | Chart/Report | - |
| `/reports/income-statement` | Chart/Report | - |
| `/reports/cash-flow` | Chart/Report | - |
| `/reports/trial-balance` | Chart/Report | - |
| `/reports/vat` | Chart/Report | - |

---

### Settings

| Route | Type | Stats (if List) |
|-------|------|-----------------|
| `/settings` | Hub (card grid) | - |
| `/settings/company` | Form | - |
| `/settings/users` | List | Total, Active, Admins |
| `/settings/roles` | List | Total, Users per Role |
| `/settings/integrations` | List | Connected, Errors |
| `/settings/webhooks` | List | Active, Deliveries |
| `/settings/sync` | Dashboard | Last Sync, Pending, Errors |
| `/settings/migration` | Form/Status | - |
| `/settings/cleaner` | List | Scans, Issues |

---

### Workflow Tasks

| Route | Type | Stats (if List) |
|-------|------|-----------------|
| `/workflow-tasks` | List | Pending, Urgent, Due Today |
| `/workflow-tasks/{id}` | Detail | - |
