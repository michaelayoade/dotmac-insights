# Frontend Design Reference

## Global Layout Standard

All pages must follow this block ordering inside the page content area:

1. **Page header** - Title (`page_title`) and optional description, optional breadcrumbs
2. **Primary actions** - Right-aligned CTA(s); keep to 1-3
3. **Summary/Stats** - If applicable
4. **Filters/Search** - If applicable
5. **Main content** - Primary data area
6. **Empty state** - Inside main content block when no data
7. **Pagination** - If list/table
8. **Modals/overlays** - End of page
9. **Scripts** - Last

---

## Page Type Layouts

### Dashboard
1. Page header + timeframe selector
2. KPI stats grid (2-6 cards)
3. Primary charts (1-3 max)
4. Secondary insights (tables/mini charts)
5. Recent activity list
6. Quick actions

### List/Table
1. Header + primary action
2. Stats (optional)
3. Filters/search bar
4. Table/list container
5. Empty state (if no data)
6. Pagination
7. Bulk actions bar (if selection enabled)

### Detail/View
1. Header with title + status badge + actions
2. Summary cards (key fields)
3. Sections or tabs (Overview, Related lists/tables, Activity/history)
4. Side panel (optional)

### Form
1. Header + subtitle
2. Sectioned fields (required then optional)
3. Inline validation
4. Footer actions (Cancel, Submit)

### Charts/Graphs
1. Chart container with title + subtitle
2. Time filter in header (if applicable)
3. Legend placement consistent (right or bottom)
4. Empty state for no data

---

## Data-testid Standards

### Naming Rules
- Use **kebab-case**
- Prefer **nouns over verbs**
- Use **stable identifiers**, not dynamic text
- Use short, consistent prefixes

### Required Hooks (Every Page)
| Element | data-testid |
|---------|-------------|
| Page header | `page-title` |
| Main content area | `main-content` (set in layout) |
| Table/list wrapper | `<entity>-table` |
| Empty state container | `empty-state` or `<entity>-empty-state` |
| Primary action button | `<action>-button` |

### Naming Patterns
| Element Type | Pattern | Example |
|--------------|---------|---------|
| Table | `<entity>-table` | `invoice-table` |
| Search input | `<entity>-search` | `invoice-search` |
| Filter button | `<filter>-filter-button` | `status-filter-button` |
| Filter option | `<filter>-option-<value>` | `status-option-paid` |
| Action button | `<action>-button` | `new-invoice-button` |
| Empty state | `empty-state` | `empty-state` |

### Component Patterns

#### Stat Cards
```html
<div data-testid="stats-grid">
    <div data-testid="stat-card-revenue">...</div>
    <div data-testid="stat-card-orders">...</div>
</div>
```

#### Tables
```html
<table data-testid="invoice-table">
    <tr data-testid="invoice-row-123">
        <td data-testid="invoice-number">INV-001</td>
    </tr>
</table>
```

#### Bulk Actions
```html
<div data-testid="bulk-actions-bar">...</div>
<input data-testid="select-all-invoices" type="checkbox">
<input data-testid="select-invoice-123" type="checkbox">
```

#### Empty States
```html
<div data-testid="empty-state">
    <h4>No items found</h4>
    <p>Short description</p>
    <button>CTA (optional)</button>
</div>
```

### Implementation Checklist
- [ ] Page header includes `data-testid="page-title"`
- [ ] Main content block follows Global Layout Standard order
- [ ] Filters use data-testid hooks
- [ ] Tables and empty states use data-testid hooks
- [ ] Actions use data-testid hooks
- [ ] Charts include title + empty state

---

## Visual System

### Spacing Scale
- Base unit: **4px**
- Layout spacing: 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64
- Section spacing: 24-32px

### Typography Scale
| Element | Size | Weight |
|---------|------|--------|
| Title | 24-32px | 600-700 |
| Section heading | 16-18px | 600 |
| Body | 14-16px | 400-500 |
| Muted | 12-14px | 400 (gray-500) |

### Color Tokens
- **Primary**: Brand color (buttons, links, highlights)
- **Neutral**: gray-50 to gray-900
- **Semantic**: Success, Warning, Error, Info states
- **Contrast**: Must meet WCAG AA for text

### Radii and Shadows
| Element | Radius |
|---------|--------|
| Cards, panels | 12-16px |
| Buttons, inputs | 10-12px |

- Subtle elevation: cards
- Strong elevation: modals

---

## Grid and Layout

- **Max content width**: 1280px (or existing app layout)
- **Complex layouts**: 12-column grid
- **Simple pages**: 1-2 columns
- **Sidebar layouts**: Preserve main content width, avoid horizontal scroll

---

## Component Standards

### Buttons
| Type | Usage |
|------|-------|
| Primary | Solid primary color, main action |
| Secondary | Neutral outline or soft fill |
| Destructive | Red tone with confirmation |
| Loading | Spinner + disabled state |

### Inputs
- Consistent height and padding across forms
- Visible focus ring
- Inline error text below field with `data-error`

### Tabs
- Tab list uses `role="tablist"`
- Active tab has clear visual state
- HTMX tabs update content region with id

### Cards
- Title + optional subtitle
- Content aligned with spacing scale

### Tables
- Sticky header optional for long lists
- **Always** show empty state when no rows
- Row hover state required for affordance

### Badges
- Consistent color mapping for statuses
- Always provide text label

---

## Interaction and State

### Hover/Focus/Active
- Buttons and links must have hover and focus states
- Focus ring visible for keyboard users

### Loading
- Use skeletons or `htmx-indicator` for async content
- Disable actions while loading

### Errors
| Type | Pattern |
|------|---------|
| Global | Banner at top of page |
| Field | Inline message under field |
| Empty | Distinct from error states |

---

## Accessibility

- All form inputs have labels
- All interactive elements keyboard reachable
- Use `aria-label` where text is not visible
- Avoid color-only indicators

---

## Data Formatting

| Data Type | Rule |
|-----------|------|
| Currency | Use `currency_symbol` where possible |
| Dates | Single format across the app |
| Percentages | Include % sign, consistent precision |

---

## Review Checklist

- [ ] Title and description match the page content
- [ ] Primary action is clear and singular
- [ ] Filters do not wrap awkwardly on mobile
- [ ] Tables render with empty state and pagination
- [ ] Buttons and links have focus states
- [ ] All data-testid hooks match naming rules

---

## Layout Architecture

### Main App Layout (`app/templates/layouts/app.html`)

```
+------------------+-------------------------------------------+
|     Sidebar      |              Top Bar                      |
|     (w-72)       |  [Menu] [Breadcrumbs]      [+ New]        |
|                  +-------------------------------------------+
|  - Logo          |                                           |
|  - Navigation    |           Main Content                    |
|    sections      |           (max-w-7xl mx-auto)             |
|  - User card     |                                           |
|                  |                                           |
+------------------+-------------------------------------------+
```

### Key Layout Classes

```html
<!-- Sidebar -->
<aside class="fixed inset-y-0 left-0 z-40 w-72 flex flex-col bg-gradient-to-b from-slate-850 to-slate-950">

<!-- Main area offset by sidebar -->
<div class="lg:pl-72">

<!-- Content container -->
<div class="px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
```

---

## Sidebar Navigation Patterns

### Section Headers
```html
<h3 class="px-3 mb-3 text-[10px] font-bold text-white/30 uppercase tracking-[0.2em]">
    Section Name
</h3>
```

### Navigation Links
```html
<!-- Active state -->
<a class="group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium
          bg-white/10 text-white shadow-inner-glow">
    <span class="w-5 h-5 text-primary-400">...</span>
    <span>Label</span>
    <span class="ml-auto w-1.5 h-1.5 rounded-full bg-primary-400"></span>
</a>

<!-- Inactive state -->
<a class="group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium
          text-white/60 hover:bg-white/5 hover:text-white">
    <span class="w-5 h-5 text-white/40 group-hover:text-white/70">...</span>
    <span>Label</span>
</a>
```

### User Card (Bottom of Sidebar)
```html
<div class="shrink-0 border-t border-white/5 p-4">
    <div class="flex items-center gap-3 rounded-xl bg-white/5 p-3">
        <div class="h-10 w-10 rounded-xl bg-gradient-to-br from-accent-400 to-accent-500">
            <!-- Avatar/Initials -->
        </div>
        <div class="flex-1 min-w-0">
            <p class="text-sm font-semibold text-white truncate">Name</p>
            <p class="text-xs text-white/40 truncate">email</p>
        </div>
        <!-- Logout button -->
    </div>
</div>
```

---

## Page Structure Patterns

### Standard Page Header
```html
<div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
    <div>
        <h1 class="text-2xl sm:text-3xl font-display font-bold text-gray-900 tracking-tight">
            Page Title
        </h1>
        <p class="mt-1.5 text-gray-500 font-body">
            Description text
        </p>
    </div>
    <div class="flex items-center gap-3">
        <!-- Action buttons -->
    </div>
</div>
```

### Stats Grid (Dashboard)
```html
<div class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4 mb-10">
    <!-- Stat cards -->
</div>
```

### Two-Column Layout
```html
<div class="grid grid-cols-1 gap-6 lg:grid-cols-5">
    <div class="lg:col-span-3"><!-- Wider column --></div>
    <div class="lg:col-span-2"><!-- Narrower column --></div>
</div>
```

---

## Card Patterns

### Standard Card
```html
<div class="bg-white rounded-2xl shadow-warm-sm ring-1 ring-gray-100 overflow-hidden">
    <!-- Card header -->
    <div class="px-6 py-5 border-b border-gray-100 flex items-center justify-between">
        <div>
            <h3 class="text-base font-display font-semibold text-gray-900">Title</h3>
            <p class="mt-0.5 text-sm text-gray-500 font-body">Subtitle</p>
        </div>
        <a href="#" class="text-sm font-medium text-primary-600 hover:text-primary-500">Action</a>
    </div>
    <!-- Card content -->
    <div class="p-6">
        ...
    </div>
</div>
```

---

## Design System Tokens

### Colors
```
Primary (Teal):    50-950 scale, main: 600 (#0d7377)
Accent (Amber):    50-950 scale, main: 400 (#f2a900)
Surface (Warm):    50, 100, 200 for backgrounds
Slate:             850, 950 for sidebar
```

### Shadows
```
shadow-warm-sm    - Subtle cards
shadow-warm       - Default cards
shadow-warm-md    - Elevated cards
shadow-warm-lg    - Dropdowns, modals
shadow-warm-xl    - Major modals
shadow-inner-glow - Active sidebar items
```

### Typography
```
font-display      - Headings (DM Sans)
font-body         - Body text (Source Sans 3)
tracking-tight    - Headlines
tracking-[0.2em]  - Section labels (uppercase)
```

### Spacing Conventions
```
Sidebar width:    w-72 (288px)
Main content:     max-w-7xl mx-auto
Page padding:     px-4 sm:px-6 lg:px-8
Section gap:      gap-6 or space-y-6
Card padding:     p-6
Card radius:      rounded-2xl
```

### Component Patterns
```
Cards:            rounded-2xl shadow-warm-sm ring-1 ring-gray-100
Buttons:          rounded-xl px-4 py-2.5
Inputs:           rounded-xl border-gray-200
Badges:           rounded-md px-2 py-0.5
Icons in boxes:   rounded-xl p-3
```

### State Classes
```
Active nav:       bg-white/10 text-white
Hover nav:        hover:bg-white/5 hover:text-white
Active accent:    text-primary-400
Card hover:       hover:shadow-warm-md hover:ring-gray-200
```

### Stat Card with Hover Effect
```html
<div class="group relative bg-white rounded-2xl shadow-warm-sm ring-1 ring-gray-100 p-6
            hover:shadow-warm-md hover:ring-gray-200 transition-all duration-300">
    <div class="flex items-start justify-between">
        <div class="flex-1">
            <dt class="text-sm font-medium text-gray-500 font-body">Label</dt>
            <dd class="mt-2 flex items-baseline gap-2">
                <span class="text-3xl font-display font-bold text-gray-900 tracking-tight">Value</span>
                <!-- Optional change indicator -->
            </dd>
        </div>
        <div class="flex-shrink-0 p-3 rounded-xl bg-primary-50 text-primary-600
                    group-hover:scale-110 transition-transform duration-300">
            <!-- Icon -->
        </div>
    </div>
    <!-- Hover accent line -->
    <div class="absolute bottom-0 left-6 right-6 h-0.5 bg-gradient-to-r from-primary-400 to-primary-600
                rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
</div>
```

---

## Button Patterns

### Primary Button
```html
<button class="inline-flex items-center gap-2 rounded-xl bg-primary-600 px-4 py-2.5
               text-sm font-semibold text-white shadow-lg shadow-primary-600/25
               hover:bg-primary-500 hover:shadow-primary-500/30 transition-all">
    <svg class="h-4 w-4">...</svg>
    <span>Button Text</span>
</button>
```

### Secondary Button
```html
<button class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-xl
               hover:bg-gray-200 transition-colors">
    Cancel
</button>
```

### Ghost Button (Link-style)
```html
<a href="#" class="text-sm font-medium text-primary-600 hover:text-primary-500 transition-colors">
    View all
</a>
```

---

## List Item Patterns

### Quick Action Item
```html
<a href="#" class="group flex items-center gap-4 rounded-xl p-3 hover:bg-surface-50 transition-all duration-200">
    <div class="flex-shrink-0 w-10 h-10 rounded-xl bg-primary-50 text-primary-600
                flex items-center justify-center group-hover:bg-primary-100
                group-hover:scale-105 transition-all duration-200">
        <!-- Icon -->
    </div>
    <div class="flex-1 min-w-0">
        <p class="text-sm font-medium text-gray-900 font-body">Title</p>
        <p class="text-xs text-gray-500 font-body">Description</p>
    </div>
    <svg class="w-4 h-4 text-gray-400 group-hover:text-primary-500
                group-hover:translate-x-0.5 transition-all duration-200">
        <!-- Chevron right -->
    </svg>
</a>
```

### Activity Item
```html
<div class="px-6 py-4 hover:bg-surface-50 transition-colors">
    <div class="flex items-start gap-4">
        <span class="inline-flex h-10 w-10 items-center justify-center rounded-xl
                     bg-gradient-to-br from-gray-100 to-gray-200">
            <span class="text-sm font-semibold text-gray-600">AB</span>
        </span>
        <div class="min-w-0 flex-1">
            <p class="text-sm text-gray-900 font-body">
                <span class="font-medium">User</span> did something
            </p>
            <p class="mt-0.5 text-sm text-gray-500 font-body">Description</p>
            <p class="mt-1 text-xs text-gray-400 font-body">Timestamp</p>
        </div>
    </div>
</div>
```

---

## Empty States

```html
<div class="px-6 py-12 text-center">
    <div class="mx-auto w-14 h-14 rounded-2xl bg-surface-100 flex items-center justify-center mb-4">
        <svg class="w-7 h-7 text-gray-400">...</svg>
    </div>
    <h4 class="text-sm font-medium text-gray-900 font-body">No items found</h4>
    <p class="mt-1 text-sm text-gray-500 font-body">Description or call to action.</p>
</div>
```

---

## HTMX Patterns

### With Loading Indicator
```html
<a href="/path"
   hx-get="/path"
   hx-target="#main-content"
   hx-push-url="true"
   hx-indicator="#page-loader">
    Link Text
</a>

<!-- Indicator -->
<div id="page-loader" class="htmx-indicator">
    <div class="w-5 h-5 border-2 border-primary-200 border-t-primary-600 rounded-full animate-spin"></div>
</div>
```

### HTMX Indicator CSS
```css
.htmx-indicator {
    opacity: 0;
    transition: opacity 200ms ease-out;
}
.htmx-request .htmx-indicator,
.htmx-request.htmx-indicator {
    opacity: 1;
}
```

---

## Responsive Guidelines

### Mobile-First Approach
```html
<!-- Start with mobile, add responsive classes -->
<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">

<!-- Hide on mobile, show on larger -->
<span class="hidden sm:inline-flex">

<!-- Show on mobile, hide on larger -->
<h1 class="sm:hidden">
```

### Sidebar Responsive Behavior
- Hidden on mobile (`-translate-x-full lg:translate-x-0`)
- Shown via hamburger menu (`sidebarOpen` Alpine state)
- Overlay backdrop when open on mobile

### Table Responsiveness
```html
<div class="overflow-x-auto">
    <table class="min-w-full">
        ...
    </table>
</div>
```

---

## Accessibility Checklist

- [ ] All images have `alt` text
- [ ] Interactive elements have visible focus states
- [ ] Color contrast meets WCAG AA (4.5:1 for text)
- [ ] Form inputs have associated labels
- [ ] Buttons have accessible names
- [ ] Modals trap focus
- [ ] Skip links present for main content
- [ ] ARIA labels on icon-only buttons
- [ ] Semantic HTML (`nav`, `main`, `aside`, `article`)
- [ ] `aria-current="page"` on active nav items

---

## Animation Classes

```html
animate-fade-in        - Fade from opacity 0 to 1
animate-fade-up        - Fade up from below
animate-slide-in-right - Slide in from right (toasts)
animate-slide-out-right - Slide out to right
animate-scale-in       - Scale from 0.95 to 1
animate-shimmer        - Loading shimmer effect
```

---

## Z-Index Scale

```
z-10  - Dropdowns
z-20  - Sticky header
z-30  - Mobile overlay
z-40  - Sidebar
z-50  - Modals, toasts
```
