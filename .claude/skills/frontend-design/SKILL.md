---
name: frontend-design
description: This skill should be used when users ask to review UI/UX, audit a template, check layout or responsiveness, validate data-testids for E2E, or assess HTMX/Alpine/Tailwind frontend patterns (e.g., "review this template", "audit the sidebar", "check data-testids", "responsive review").
---

# Frontend Design Review Skill

Review and improve frontend design for DotMac BOS (HTMX + Alpine.js + TailwindCSS, Jinja2 templates).

## When to Use
- Use when asked to review UI/UX, layout, responsiveness, or accessibility.
- Use when asked to polish a template or page in `app/modules/*/templates/`.
- Use when asked to check data-testid compliance for E2E tests.
- Use when asked to verify interaction states (hover, focus, loading, errors).
- Use when asked to audit visual consistency (spacing, typography, colors).

## Severity Levels
| Severity | Criteria | Action |
|----------|----------|--------|
| Critical | Blocks core flow or causes major UX failure | Must fix before merge |
| High | Significant usability or accessibility issue | Should fix |
| Medium | Inconsistent layout or minor UX risk | Consider fixing |
| Low | Polish or cosmetic improvement | Optional |

## Tech Stack

- **Rendering**: Server-side with Jinja2 templates
- **Interactivity**: HTMX for dynamic content, Alpine.js for client-side state
- **Styling**: TailwindCSS with custom design tokens
- **Layout**: Fixed sidebar (72px/288px) + scrollable main content
- **Fonts**: DM Sans (display), Source Sans 3 (body)

## Commands

### `/frontend-design review [page_or_template]`
Comprehensive design review of a page or template.

**What I analyze:**
Layout, navigation, information density, responsive behavior, accessibility, and HTMX interaction patterns.

**Output format (standardized):**
```markdown
## Design Review: [page/template]

### Findings
- [Severity][template:line] Issue summary + impact

### Risks
- [Usability, responsiveness, accessibility risks]

### Fixes
- [Actionable improvements]

### Tests
- [Manual checks across breakpoints]
```

---

### `/frontend-design sidebar`
Review sidebar navigation design and information organization.

**What I check:**
- Navigation grouping logic
- Visual hierarchy of sections vs items
- Active state visibility
- Overflow handling for many items
- Mobile sidebar behavior
- Icon consistency
- Section headers and labels

---

### `/frontend-design layout [template]`
Analyze page layout structure and content arrangement.

**What I check:**
- Grid system usage (columns, gaps)
- Content width and max-width
- Panel arrangement (cards, sections)
- Header/content/footer structure
- Sticky elements
- Scroll behavior

---

### `/frontend-design info-density [template]`
Analyze information density and data presentation.

**What I check:**
- Data tables: column priorities, mobile handling
- Cards: essential vs secondary info
- Lists: grouping and scanning patterns
- Forms: field organization, sections
- Dashboards: metric hierarchy, at-a-glance clarity

---

### `/frontend-design responsive [template]`
Review responsive design implementation.

**Breakpoints used:**
- `sm`: 640px
- `md`: 768px
- `lg`: 1024px (sidebar visible)
- `xl`: 1280px
- `2xl`: 1536px

**What I check:**
- Mobile-first approach
- Critical content visibility at each breakpoint
- Touch target sizes (min 44x44px)
- Navigation on mobile
- Table responsiveness
- Form layouts

---

### `/frontend-design accessibility [template]`
Audit accessibility compliance.

**What I check:**
- Semantic HTML structure
- ARIA labels and roles
- Color contrast (WCAG AA)
- Focus management
- Keyboard navigation
- Screen reader compatibility
- Skip links

---

### `/frontend-design htmx-patterns [template]`
Review HTMX implementation patterns.

**What I check:**
- Loading indicators (`htmx-indicator`)
- Error handling (`htmx:responseError`)
- Swap strategies (`hx-swap`)
- History management (`hx-push-url`)
- Progressive enhancement
- Target selection (`hx-target`)

---

### `/frontend-design testid [template]`
Audit data-testid compliance for E2E testing.

**What I check:**
- Page header has `data-testid="page-title"`
- Tables have `data-testid="<entity>-table"`
- Empty states have `data-testid="empty-state"` or `<entity>-empty-state`
- Primary actions have `data-testid="<action>-button"`
- Filters use proper testid patterns (`<filter>-filter-button`, `<filter>-option-<value>`)
- Naming follows kebab-case convention
- Identifiers are stable (not dynamic text)

**Output format:**
```markdown
## Data-testid Audit: [template]

### Missing Required Hooks
- [template:line] Missing `page-title` on header
- [template:line] Table missing entity-prefixed testid

### Naming Issues
- [template:line] Uses camelCase instead of kebab-case
- [template:line] Uses dynamic value in testid

### Compliance Score
X/Y required hooks present
```

---

### `/frontend-design page-structure [template]`
Verify page follows Global Layout Standard ordering.

**Expected order:**
1. Page header (title, description, breadcrumbs)
2. Primary actions (right-aligned CTAs)
3. Summary/Stats
4. Filters/Search
5. Main content
6. Empty state
7. Pagination
8. Modals/overlays
9. Scripts

**What I check:**
- Blocks appear in correct order
- No missing required sections for page type
- Proper page type structure (Dashboard, List, Detail, Form, Chart)

---

### `/frontend-design component [component_path]`
Review a specific UI component.

**What I check:**
- Reusability and props/slots
- Consistency with design system
- Variant coverage (sizes, states)
- Accessibility
- Documentation

---

### `/frontend-design interactions [template]`
Audit interaction states and loading patterns.

**What I check:**
- Buttons have hover, focus, and active states
- Links have visible focus states
- Loading indicators present for async actions (`htmx-indicator`)
- Actions disabled during loading
- Error handling (global banners, field-level inline errors)
- Empty states distinct from error states

---

## References

- `references/reference.md`

### `/frontend-design visual [template]`
Audit visual consistency against design system.

**What I check:**
- Spacing follows 4px base scale (4/8/12/16/20/24/32/40/48/64)
- Typography matches scale (title, heading, body, muted)
- Color tokens used correctly (primary, neutral, semantic)
- Border radii consistent (12-16px cards, 10-12px buttons)
- Shadows appropriate for element elevation

---

### `/frontend-design full-review [template]`
Comprehensive review covering all standards.

**Runs all checks:**
1. Page structure (Global Layout Standard)
2. Data-testid compliance
3. Visual system (spacing, typography, colors)
4. Interaction states (hover, focus, loading, errors)
5. Accessibility
6. Responsive behavior

**Output format:**
```markdown
## Full Review: [template]

### Structure ✓/✗
### Testid Compliance ✓/✗
### Visual System ✓/✗
### Interactions ✓/✗
### Accessibility ✓/✗
### Responsive ✓/✗

### Critical Issues
- ...

### Recommendations
- ...
```

---

### `/frontend-design module [module_name]`
Review a module's page structure against `docs/module-ui-structure.md`.

**What I check:**
- Dashboard has KPI stats + charts + quick actions
- List pages have: stats row, filters, table, bulk actions, pagination
- Detail pages have: summary cards, tabs, activity timeline
- Form pages have: sectioned fields, validation, footer actions
- Board/Calendar/Map pages follow their respective patterns
- All pages have required data-testid hooks
- Stats cards correctly use filterable vs display-only patterns

**Output format:**
```markdown
## Module Review: [module_name]

### Pages Analyzed
| Page | Type | Status |
|------|------|--------|
| /module/list | List | ✓/✗ |
| /module/{id} | Detail | ✓/✗ |

### Missing Patterns
- [page] Missing stats row (expected for List page)
- [page] Missing bulk actions bar

### Testid Gaps
- [page] Missing data-testid="stats-grid"

### Recommendations
- ...
```

---

## References

### `reference.md` - Design System
- Global Layout Standard (page block ordering)
- Data-testid Standards (naming rules, required hooks, patterns)
- Visual System (spacing, typography, colors, radii, shadows)
- Component Standards (buttons, inputs, tabs, cards, tables, badges)
- Interaction and State (hover, focus, loading, errors)
- Accessibility requirements
- Data Formatting rules
- Layout skeleton and sidebar patterns
- Component class recipes and design tokens

### `docs/module-ui-structure.md` - Page Patterns
- **Page Type Patterns**: List, Detail, Form, Dashboard, Board/Kanban, Calendar, Map, Chart/Report
- Stats card specifications (filterable vs display-only)
- Card grid view alternative to tables
- Module-by-module route structure with stats per list
- Data-testid requirements per page type
- Actual pages vs alias routes

## Anti-Patterns I Avoid Suggesting

- Over-engineering simple layouts
- Adding unnecessary animations
- Breaking existing patterns for "improvement"
- Suggesting redesigns when the issue is minor
- Proposing desktop-only solutions

## Integration with Project

**Template Locations:**
- Base layouts: `app/templates/layouts/`
- Components: `app/templates/components/`
- Module pages: `app/modules/*/templates/`

**Existing Patterns to Follow:**
- Read existing templates before suggesting changes
- Match button styles, card patterns, and spacing
- Use existing component includes where available
- Follow established color usage
