UI Standards

Purpose
- Provide a consistent page hierarchy and structure across modules.
- Make UI predictable for users and stable for E2E tests via data-testid.
- Define visual, interaction, and accessibility conventions for all UI.

Global Layout Standard (all pages)
Order of blocks inside the page content:
1) Page header
   - Title (page_title) and optional description
   - Optional breadcrumbs
2) Primary actions
   - Right-aligned CTA(s); keep to 1-3
3) Summary/Stats (if applicable)
4) Filters/Search (if applicable)
5) Main content
6) Empty state (inside main content block)
7) Pagination (if list/table)
8) Modals/overlays (end of page)
9) Scripts (last)

Visual System

Spacing scale
- Base spacing unit: 4px.
- Use 4/8/12/16/20/24/32/40/48/64 for layout spacing.
- Section spacing: 24-32px.

Typography scale
- Title: 24-32px, font-weight 600-700.
- Section heading: 16-18px, font-weight 600.
- Body: 14-16px, font-weight 400-500.
- Muted: 12-14px, color gray-500.

Color tokens
- Primary: brand color (buttons, links, highlights).
- Neutral: gray-50 to gray-900.
- Success, Warning, Error, Info states.
- Keep contrast >= WCAG AA for text.

Radii and shadows
- Cards and panels: 12-16px radius.
- Buttons and inputs: 10-12px radius.
- Shadows: one subtle elevation for cards, one stronger for modals.

Grid and Layout
- Max content width: 1280px (or existing app layout).
- Use 12-column grid for complex layouts, 1-2 columns for simple pages.
- Sidebar layouts must preserve main content width and avoid horizontal scroll.

Page Types

Dashboard
1) Page header + timeframe selector
2) KPI stats grid (2-6 cards)
3) Primary charts (1-3 max)
4) Secondary insights (tables/mini charts)
5) Recent activity list
6) Quick actions

List/Table
1) Header + primary action
2) Stats (optional)
3) Filters/search bar
4) Table/list container
5) Empty state (if no data)
6) Pagination
7) Bulk actions bar (if selection enabled)

Detail/View
1) Header with title + status badge + actions
2) Summary cards (key fields)
3) Sections or tabs
   - Overview
   - Related lists/tables
   - Activity/history
4) Side panel (optional)

Form
1) Header + subtitle
2) Sectioned fields (required then optional)
3) Inline validation
4) Footer actions (Cancel, Submit)

Charts/Graphs
1) Chart container with title + subtitle
2) Time filter in header (if applicable)
3) Legend placement consistent (right or bottom)
4) Empty state for no data

Component Standards

Buttons
- Primary: solid primary color, used for main action.
- Secondary: neutral outline or soft fill.
- Destructive: red tone with confirmation where needed.
- Loading state: spinner + disabled.

Inputs
- Consistent height and padding across forms.
- Visible focus ring.
- Inline error text below field with data-error.

Tabs
- Tab list uses role="tablist".
- Active tab has clear visual state.
- HTMX tabs must update content region with id.

Cards
- Title + optional subtitle.
- Content aligned with spacing scale.

Tables
- Sticky header optional for long lists.
- Always show empty state when no rows.
- Row hover state is required for affordance.

Badges
- Use consistent color mapping for statuses.
- Always provide text label.

Interaction and State

Hover/focus/active
- Buttons and links must have hover and focus states.
- Focus ring visible for keyboard users.

Loading
- Use skeletons or htmx indicators for async content.
- Disable actions while loading.

Errors
- Global errors: banner at top of page.
- Field errors: inline message under field.
- Empty states are distinct from error states.

Accessibility
- All form inputs have labels.
- All interactive elements keyboard reachable.
- Use aria-label where text is not visible.
- Avoid color-only indicators.

Data Formatting
- Currency uses currency_symbol where possible.
- Dates use a single format across the app.
- Percentages include % sign and consistent precision.

Data-testid Standard

Naming rules
- Use kebab-case.
- Prefer nouns over verbs.
- Use stable identifiers, not dynamic text.
- Prefer short, consistent prefixes:
  - page-title
  - table name: <entity>-table
  - search input: <entity>-search
  - filters: <filter>-filter, <filter>-filter-button, <filter>-option-<value>
  - buttons: <action>-button
  - empty states: empty-state or <entity>-empty-state

Required hooks
- Page header: data-testid="page-title"
- Main content area: data-testid="main-content" (already set in layout)
- Table/list wrapper: data-testid="<entity>-table"
- Empty state container: data-testid="empty-state" or "<entity>-empty-state"
- Primary action button: data-testid="<action>-button"

Examples
- data-testid="invoice-table"
- data-testid="invoice-search"
- data-testid="status-filter-button"
- data-testid="status-option-paid"
- data-testid="new-invoice-button"
- data-testid="empty-state"

Component Patterns

Stat cards
- Container: data-testid="stats-grid"
- Card: data-testid="stat-card-<key>"

Tables
- Wrapper: data-testid="<entity>-table"
- Row: data-testid="<entity>-row-<id>"
- Key cell: data-testid="<entity>-name" or "<entity>-number"

Bulk actions
- Bar: data-testid="bulk-actions-bar"
- Select all: data-testid="select-all-<entity>"
- Row checkbox: data-testid="select-<entity>-<id>"

Empty states
- Use a single container with data-testid="empty-state" or "<entity>-empty-state"
- Keep a short title, one sentence description, and one CTA (if applicable)

Navigation and breadcrumbs
- Use page_title for the header title
- Ensure breadcrumbs match module hierarchy

Implementation Checklist
- Page header includes data-testid="page-title"
- Main content block follows order in Global Layout Standard
- Filters use data-testid hooks
- Tables and empty states use data-testid hooks
- Actions use data-testid hooks
- Charts include title + empty state

Review Checklist
- Title and description match the page content.
- Primary action is clear and singular.
- Filters do not wrap awkwardly on mobile.
- Tables render with empty state and pagination.
- Buttons and links have focus states.
- All data-testid hooks match naming rules.
