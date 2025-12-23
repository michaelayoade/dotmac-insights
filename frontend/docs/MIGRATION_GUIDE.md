# Frontend Centralization Migration Guide

This guide documents patterns to migrate to centralized utilities.

## 1. Form Error State Migration (17 files)

### Before
```tsx
import { useState } from 'react';

const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

const validate = () => {
  const errs: Record<string, string> = {};
  if (!name) errs.name = 'Name is required';
  if (!email) errs.email = 'Email is required';
  setFieldErrors(errs);
  return Object.keys(errs).length === 0;
};
```

### After
```tsx
import { useFormErrors } from '@/hooks';

const { errors, setErrors, hasAnyErrors, clearAll } = useFormErrors();

const validate = () => {
  const errs: Record<string, string> = {};
  if (!name) errs.name = 'Name is required';
  if (!email) errs.email = 'Email is required';
  setErrors(errs);
  return !Object.keys(errs).length; // or check hasAnyErrors after setErrors
};

// In handleSubmit:
clearAll(); // Clear previous errors before validation
```

### Files to migrate
```
app/contacts/new/page.tsx
app/contacts/import/page.tsx
app/contacts/[id]/edit/page.tsx
app/sales/invoices/new/page.tsx
app/sales/credit-notes/new/page.tsx
app/sales/credit-notes/[id]/edit/page.tsx
app/sales/invoices/[id]/edit/page.tsx
app/sales/orders/new/page.tsx
app/sales/orders/[id]/edit/page.tsx
app/sales/quotations/new/page.tsx
app/sales/quotations/[id]/edit/page.tsx
app/sales/payments/new/page.tsx
app/sales/customers/new/page.tsx
app/sales/payments/[id]/edit/page.tsx
app/sales/customers/[id]/edit/page.tsx
app/projects/new/page.tsx
app/support/tickets/new/page.tsx
```

---

## 2. Date Formatting Migration (51 files)

### Before
```tsx
function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return '—';
  const date = new Date(dateString);
  return date.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}
```

### After
```tsx
import { formatDate, formatDateTime, formatRelativeTime } from '@/lib/formatters';

// Usage is the same, just import instead of define locally
```

### Migration command (for simple cases)
```bash
# Find files with local formatDate
grep -l "function formatDate\|const formatDate =" frontend/app/**/*.tsx

# Approach:
# 1. Add import: import { formatDate } from '@/lib/formatters';
# 2. Remove local function definition
# 3. Verify usage matches (same signature)
```

---

## 3. MetricCard → StatCard Migration (20 files)

### Before
```tsx
interface MetricCardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon: React.ElementType;
  colorClass?: string;
  loading?: boolean;
  href?: string;
}

function MetricCard({ title, value, ... }: MetricCardProps) {
  // Local implementation
}

<MetricCard title="Revenue" value="₦1.2M" icon={DollarSign} colorClass="text-green-400" />
```

### After
```tsx
import { StatCard } from '@/components/StatCard';

// Simple usage
<StatCard
  title="Revenue"
  value="₦1.2M"
  icon={DollarSign}
  colorClass="text-green-400"
/>

// With trend (adapt from 'up'/'down' to numeric)
// Before: trend="up" trendLabel="+5% vs last week"
// After:
<StatCard
  title="Revenue"
  value="₦1.2M"
  icon={DollarSign}
  colorClass="text-green-400"
  trend={{ value: 5, label: "vs last week" }}
/>

// Negative trend
// Before: trend="down" trendLabel="-3% vs last week"
// After:
<StatCard
  title="Expenses"
  value="₦800K"
  trend={{ value: -3, label: "vs last week" }}
/>
```

### Files to migrate
```
app/expenses/card-analytics/page.tsx
app/hr/payroll/page.tsx
app/hr/leave/page.tsx
app/hr/page.tsx
app/books/income-statement/page.tsx
app/books/page.tsx
app/purchasing/page.tsx
app/admin/security/page.tsx
app/admin/platform/page.tsx
app/customers/page.tsx
app/projects/analytics/page.tsx
app/inbox/contacts/companies/page.tsx
app/inbox/routing/teams/page.tsx
app/support/teams/page.tsx
app/support/csat/page.tsx
app/support/analytics/page.tsx
app/support/kb/page.tsx
app/support/canned-responses/page.tsx
app/support/page.tsx
app/support/agents/page.tsx
```

---

## 4. Loading/Error State Migration

### Before
```tsx
if (isLoading) {
  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <Loader2 className="w-8 h-8 animate-spin text-slate-muted" />
    </div>
  );
}

if (error) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px]">
      <AlertTriangle className="w-12 h-12 mb-4 text-rose-400" />
      <p>Failed to load data</p>
    </div>
  );
}
```

### After
```tsx
import { DashboardShell } from '@/components/ui/DashboardShell';

return (
  <DashboardShell
    isLoading={isLoading}
    error={error}
    onRetry={mutate}
    isEmpty={data?.length === 0}
    emptyState={{
      title: 'No items yet',
      description: 'Create your first item to get started.',
    }}
  >
    {/* Page content */}
  </DashboardShell>
);
```

---

## 5. Currency Formatting Migration

### Before
```tsx
function formatCurrency(value: number | undefined | null, currency = 'NGN'): string {
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
  }).format(value || 0);
}
```

### After
```tsx
import { formatCurrency } from '@/lib/formatters';
// or for compact display:
import { formatCompactCurrency } from '@/lib/formatters';
```

### Files to migrate (52 files)
```
app/contacts/churned/page.tsx
app/contacts/customers/page.tsx
app/contacts/analytics/page.tsx
app/contacts/organizations/page.tsx
app/contacts/territories/page.tsx
app/contacts/page.tsx
app/contacts/[id]/page.tsx
app/contacts/categories/page.tsx
app/expenses/reports/page.tsx
app/expenses/approvals/page.tsx
app/purchasing/aging/page.tsx
app/purchasing/expenses/page.tsx
app/purchasing/debit-notes/page.tsx
app/purchasing/debit-notes/[id]/page.tsx
app/purchasing/payments/[id]/page.tsx
app/purchasing/payments/page.tsx
app/purchasing/analytics/page.tsx
app/purchasing/orders/page.tsx
app/purchasing/erpnext-expenses/page.tsx
app/purchasing/orders/[id]/page.tsx
app/purchasing/erpnext-expenses/[id]/page.tsx
app/purchasing/page.tsx
app/purchasing/bills/page.tsx
app/purchasing/bills/[id]/page.tsx
app/purchasing/suppliers/[id]/page.tsx
app/purchasing/suppliers/page.tsx
app/sales/invoices/[id]/page.tsx
app/sales/invoices/page.tsx
app/sales/page.tsx
app/sales/opportunities/[id]/page.tsx
app/sales/opportunities/page.tsx
app/sales/credit-notes/[id]/page.tsx
app/sales/credit-notes/page.tsx
app/sales/invoices/[id]/edit/page.tsx
app/sales/orders/[id]/page.tsx
app/sales/orders/page.tsx
app/sales/pipeline/page.tsx
app/sales/quotations/[id]/page.tsx
app/sales/quotations/page.tsx
app/sales/payments/new/page.tsx
app/sales/payments/[id]/page.tsx
app/sales/payments/page.tsx
app/sales/payments/[id]/edit/page.tsx
app/sales/customers/[id]/page.tsx
app/sales/analytics/page.tsx
app/sales/insights/page.tsx
app/performance/reports/bonus/page.tsx
app/projects/analytics/page.tsx
app/projects/page.tsx
app/projects/[id]/page.tsx
app/fleet/page.tsx
app/fleet/[id]/page.tsx
```

---

## Central Import Locations

| Pattern | Import From |
|---------|-------------|
| StatCard, MiniStatCard, RatioCard | `@/components/StatCard` |
| formatDate, formatCurrency, etc. | `@/lib/formatters` |
| useFormErrors, validateForm | `@/hooks` |
| DashboardShell, LoadingState | `@/components/ui/DashboardShell` |
| StatusBadge, Badge | `@/components/Badge` |
| DataTable, Pagination | `@/components/DataTable` |
| useTableSort | `@/hooks` |
| STATUS_VARIANT_MAP | `@/lib/design-tokens` |

---

## 6. Status Color Maps Migration (15 files)

### Before
```tsx
const statusColors: Record<string, string> = {
  active: 'bg-green-500/20 text-green-400 border-green-500/30',
  pending: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  closed: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
};

<span className={cn('px-2 py-1 rounded-full text-xs', statusColors[item.status])}>
  {item.status}
</span>
```

### After
```tsx
import { StatusBadge } from '@/components/Badge';

<StatusBadge status={item.status} />
```

### Files to migrate
```
app/contacts/all/page.tsx
app/contacts/customers/page.tsx
app/contacts/page.tsx
app/contacts/[id]/page.tsx
app/books/page.tsx
app/sales/leads/[id]/page.tsx
app/sales/leads/page.tsx
app/sales/opportunities/[id]/page.tsx
app/sales/opportunities/page.tsx
app/purchasing/page.tsx
app/sales/activities/page.tsx
app/projects/analytics/page.tsx
app/projects/[id]/page.tsx
app/field-service/schedule/page.tsx
app/field-service/page.tsx
```

---

## Summary of Affected Files

| Pattern | Files | Priority |
|---------|-------|----------|
| Local formatCurrency | 52 | High |
| Local formatDate | 51 | High |
| Local MetricCard | 20 | High |
| Form error state | 17 | High |
| Status color maps | 15 | Medium |

**Total: ~155 files need migration**

## Already Completed

- `app/sales/invoices/new/page.tsx` - migrated to useFormErrors + formatCurrency

## Quick Migration Commands

```bash
# Find all files with local formatCurrency
grep -l "function formatCurrency\|const formatCurrency =" frontend/app/**/*.tsx

# Find all files with local formatDate
grep -l "function formatDate\|const formatDate =" frontend/app/**/*.tsx

# Find all files with local MetricCard
grep -l "function MetricCard\|const MetricCard" frontend/app/**/*.tsx
```
