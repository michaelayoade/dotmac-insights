---
name: frontend-design
description: Frontend design review skill for HTMX/Alpine.js/TailwindCSS applications. Reviews layouts, sidebars, information architecture, responsive design, and UX patterns. Invoke with /frontend-design [command].
---

# Frontend Design Review Skill

Review and improve frontend design for DotMac BOS (HTMX + Alpine.js + TailwindCSS, Jinja2 templates).

## When to Use
- Asked to review UI/UX, layout, responsiveness, or accessibility.
- Asked to polish a template or page in `app/modules/*/templates/`.

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

### `/frontend-design component [component_path]`
Review a specific UI component.

**What I check:**
- Reusability and props/slots
- Consistency with design system
- Variant coverage (sizes, states)
- Accessibility
- Documentation

---

## References
- Use `reference.md` for the layout skeleton, sidebar patterns, and component class recipes.

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
