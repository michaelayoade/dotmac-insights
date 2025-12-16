'use client';

import {
  LayoutDashboard,
  FileText,
  CreditCard,
  Receipt,
  TrendingUp,
  Lightbulb,
  Users,
  ShoppingCart,
  Settings,
} from 'lucide-react';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import { ModuleLayout, NavSection, QuickLink, WorkflowPhase, WorkflowStep } from '@/components/ModuleLayout';

// Sales Flow:
// 1. QUOTE: Create quotations, manage opportunities
// 2. ORDER: Convert quotes to orders
// 3. INVOICE: Bill customers, track AR
// 4. COLLECT: Receive payments, manage aging

const sections: NavSection[] = [
  {
    key: 'overview',
    label: 'Dashboard',
    description: 'AR overview & metrics',
    icon: LayoutDashboard,
    items: [
      { name: 'Dashboard', href: '/sales', description: 'Overview & KPIs' },
      { name: 'Analytics', href: '/sales/analytics', description: 'Sales trends' },
      { name: 'Insights', href: '/sales/insights', description: 'AI recommendations' },
    ],
  },
  {
    key: 'orders',
    label: 'Orders',
    description: 'Quotations & sales orders',
    icon: ShoppingCart,
    items: [
      { name: 'Quotations', href: '/sales/quotations', description: 'Proposals & quotes' },
      { name: 'Sales Orders', href: '/sales/orders', description: 'Order management' },
    ],
  },
  {
    key: 'receivables',
    label: 'Accounts Receivable',
    description: 'Invoices & payments',
    icon: FileText,
    items: [
      { name: 'Invoices', href: '/sales/invoices', description: 'Customer billing' },
      { name: 'Payments', href: '/sales/payments', description: 'Incoming payments' },
      { name: 'Credit Notes', href: '/sales/credit-notes', description: 'Customer credits' },
    ],
  },
  {
    key: 'customers',
    label: 'Customers',
    description: 'Customer management',
    icon: Users,
    items: [
      { name: 'Customers', href: '/sales/customers', description: 'Customer directory' },
    ],
  },
];

const quickLinks: QuickLink[] = [
  { label: 'New Invoice', href: '/sales/invoices/new', icon: FileText, color: 'emerald-400' },
  { label: 'New Quote', href: '/sales/quotations/new', icon: Receipt, color: 'amber-400' },
  { label: 'Receive Pay', href: '/sales/payments/new', icon: CreditCard, color: 'teal-400' },
  { label: 'Analytics', href: '/sales/analytics', icon: TrendingUp, color: 'cyan-400' },
];

const workflowPhases: WorkflowPhase[] = [
  { key: 'quote', label: 'Quote', description: 'Create proposals' },
  { key: 'invoice', label: 'Invoice', description: 'Bill customers' },
  { key: 'collect', label: 'Collect', description: 'Receive payments' },
];

const workflowSteps: WorkflowStep[] = [
  { label: 'Create quotation', color: 'amber' },
  { label: 'Convert to order', color: 'violet' },
  { label: 'Generate invoice', color: 'emerald' },
  { label: 'Collect payment', color: 'teal' },
];

function getWorkflowPhase(sectionKey: string | null): string {
  if (!sectionKey) return 'quote';
  if (sectionKey === 'orders') return 'quote';
  if (sectionKey === 'receivables') return 'invoice';
  return 'collect';
}

export default function SalesLayout({ children }: { children: React.ReactNode }) {
  const { hasAccess, isLoading: authLoading } = useRequireScope('analytics:read');

  if (authLoading) {
    return (
      <div className="min-h-screen bg-slate-deep flex justify-center items-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-400" />
      </div>
    );
  }

  if (!hasAccess) {
    return (
      <div className="min-h-screen bg-slate-deep p-8">
        <AccessDenied />
      </div>
    );
  }

  return (
    <ModuleLayout
      moduleName="Dotmac"
      moduleSubtitle="Sales"
      sidebarTitle="Accounts Receivable"
      sidebarDescription="Invoicing, payments & collections"
      baseRoute="/sales"
      accentColor="emerald"
      icon={TrendingUp}
      sections={sections}
      quickLinks={quickLinks}
      workflowPhases={workflowPhases}
      getWorkflowPhase={getWorkflowPhase}
      workflowSteps={workflowSteps}
    >
      {children}
    </ModuleLayout>
  );
}
