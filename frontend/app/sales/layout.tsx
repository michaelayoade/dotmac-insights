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
  Target,
  Kanban,
  CalendarDays,
  Milestone,
  UserPlus,
  Contact2,
} from 'lucide-react';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import { ModuleLayout, QuickLink, WorkflowPhase, WorkflowStep } from '@/components/ModuleLayout';
import type { NavSectionType as NavSection } from '@/components/ModuleLayout';

// CRM & Sales Flow:
// 1. LEAD: Capture and qualify leads
// 2. OPPORTUNITY: Convert leads, manage pipeline
// 3. QUOTE: Create quotations, proposals
// 4. ORDER: Convert quotes to orders
// 5. INVOICE: Bill customers, track AR
// 6. COLLECT: Receive payments, manage aging

const sections: NavSection[] = [
  {
    key: 'overview',
    label: 'Dashboard',
    description: 'CRM & sales overview',
    icon: LayoutDashboard,
    items: [
      { name: 'Dashboard', href: '/sales', description: 'Overview & KPIs' },
      { name: 'Analytics', href: '/sales/analytics', description: 'Sales trends' },
      { name: 'Insights', href: '/sales/insights', description: 'AI recommendations' },
    ],
  },
  {
    key: 'crm',
    label: 'CRM',
    description: 'Leads, pipeline & activities',
    icon: Target,
    items: [
      { name: 'Leads', href: '/sales/leads', description: 'Lead management' },
      { name: 'Opportunities', href: '/sales/opportunities', description: 'Deal pipeline' },
      { name: 'Pipeline', href: '/sales/pipeline', description: 'Kanban board' },
      { name: 'Activities', href: '/sales/activities', description: 'Tasks & meetings' },
      { name: 'Contacts', href: '/sales/contacts', description: 'Contact directory' },
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
  { label: 'New Lead', href: '/sales/leads/new', icon: UserPlus, color: 'violet-400' },
  { label: 'New Deal', href: '/sales/opportunities/new', icon: Target, color: 'cyan-400' },
  { label: 'New Quote', href: '/sales/quotations/new', icon: Receipt, color: 'amber-400' },
  { label: 'New Invoice', href: '/sales/invoices/new', icon: FileText, color: 'emerald-400' },
];

const workflowPhases: WorkflowPhase[] = [
  { key: 'lead', label: 'Lead', description: 'Capture & qualify' },
  { key: 'opportunity', label: 'Deal', description: 'Nurture pipeline' },
  { key: 'quote', label: 'Quote', description: 'Create proposals' },
  { key: 'invoice', label: 'Invoice', description: 'Bill customers' },
  { key: 'collect', label: 'Collect', description: 'Receive payments' },
];

const workflowSteps: WorkflowStep[] = [
  { label: 'Capture lead', color: 'violet' },
  { label: 'Qualify & convert', color: 'cyan' },
  { label: 'Create quotation', color: 'amber' },
  { label: 'Generate invoice', color: 'emerald' },
  { label: 'Collect payment', color: 'teal' },
];

function getWorkflowPhase(sectionKey: string | null): string {
  if (!sectionKey) return 'lead';
  if (sectionKey === 'crm') return 'opportunity';
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
      moduleSubtitle="CRM & Sales"
      sidebarTitle="CRM & Sales"
      sidebarDescription="Leads, pipeline, invoicing & collections"
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