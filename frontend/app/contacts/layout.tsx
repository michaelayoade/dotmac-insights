'use client';

import {
  LayoutDashboard,
  Users,
  UserPlus,
  Building2,
  UserCircle,
  Target,
  TrendingUp,
  Activity,
  Search,
  FileUp,
  Merge,
  Settings,
  Filter,
  Tags,
} from 'lucide-react';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import { ModuleLayout } from '@/components/ModuleLayout';
import type { NavSectionType as NavSection, QuickLink, WorkflowPhase, WorkflowStep } from '@/components/ModuleLayout';

// Unified Contact Hub:
// Single source of truth for all contact data across:
// - Customers (from Splynx/ERPNext)
// - Leads (from ERPNext/CRM)
// - CRM Contacts (people within organizations)
// - Inbox Contacts (from messaging channels)

const sections: NavSection[] = [
  {
    key: 'overview',
    label: 'Dashboard',
    description: 'Contact hub overview',
    icon: LayoutDashboard,
    items: [
      { name: 'Dashboard', href: '/contacts', description: 'Overview & KPIs' },
      { name: 'Analytics', href: '/contacts/analytics', description: 'Contact insights' },
    ],
  },
  {
    key: 'directory',
    label: 'Directory',
    description: 'Browse all contacts',
    icon: Users,
    items: [
      { name: 'All Contacts', href: '/contacts/all', description: 'Complete directory' },
      { name: 'Customers', href: '/contacts/customers', description: 'Active customers' },
      { name: 'Leads', href: '/contacts/leads', description: 'Leads & prospects' },
      { name: 'Organizations', href: '/contacts/organizations', description: 'Companies' },
      { name: 'People', href: '/contacts/people', description: 'Individual contacts' },
    ],
  },
  {
    key: 'pipeline',
    label: 'Lifecycle',
    description: 'Lead to customer journey',
    icon: Target,
    items: [
      { name: 'Sales Funnel', href: '/contacts/funnel', description: 'Conversion stages' },
      { name: 'Qualification', href: '/contacts/qualification', description: 'Lead scoring' },
      { name: 'Churned', href: '/contacts/churned', description: 'Lost customers' },
    ],
  },
  {
    key: 'segments',
    label: 'Segments',
    description: 'Contact segments & lists',
    icon: Filter,
    items: [
      { name: 'Categories', href: '/contacts/categories', description: 'By category' },
      { name: 'Territories', href: '/contacts/territories', description: 'By territory' },
      { name: 'Tags', href: '/contacts/tags', description: 'Tagged contacts' },
      { name: 'Custom Lists', href: '/contacts/lists', description: 'Saved segments' },
    ],
  },
  {
    key: 'tools',
    label: 'Tools',
    description: 'Bulk operations & import',
    icon: Settings,
    items: [
      { name: 'Import', href: '/contacts/import', description: 'Bulk import' },
      { name: 'Export', href: '/contacts/export', description: 'Export data' },
      { name: 'Duplicates', href: '/contacts/duplicates', description: 'Find & merge' },
      { name: 'Data Quality', href: '/contacts/quality', description: 'Clean up data' },
    ],
  },
];

const quickLinks: QuickLink[] = [
  { label: 'New Contact', href: '/contacts/new', icon: UserPlus, color: 'cyan-400' },
  { label: 'New Lead', href: '/contacts/new?type=lead', icon: Target, color: 'violet-400' },
  { label: 'Import', href: '/contacts/import', icon: FileUp, color: 'amber-400' },
  { label: 'Find Duplicates', href: '/contacts/duplicates', icon: Merge, color: 'rose-400' },
];

const workflowPhases: WorkflowPhase[] = [
  { key: 'lead', label: 'Lead', description: 'Capture & qualify' },
  { key: 'prospect', label: 'Prospect', description: 'Nurture interest' },
  { key: 'customer', label: 'Customer', description: 'Active accounts' },
  { key: 'advocate', label: 'Advocate', description: 'Referral program' },
];

const workflowSteps: WorkflowStep[] = [
  { label: 'Capture lead', color: 'violet' },
  { label: 'Qualify & nurture', color: 'cyan' },
  { label: 'Convert to customer', color: 'emerald' },
  { label: 'Grow & retain', color: 'amber' },
];

function getWorkflowPhase(sectionKey: string | null): string {
  if (!sectionKey) return 'lead';
  if (sectionKey === 'directory') return 'customer';
  if (sectionKey === 'pipeline') return 'prospect';
  if (sectionKey === 'segments') return 'advocate';
  return 'lead';
}

export default function ContactsLayout({ children }: { children: React.ReactNode }) {
  const { hasAccess, isLoading: authLoading } = useRequireScope('contacts:read');

  if (authLoading) {
    return (
      <div className="min-h-screen bg-slate-deep flex justify-center items-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-400" />
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
      moduleSubtitle="Contact Hub"
      sidebarTitle="Contact Hub"
      sidebarDescription="Unified contact management"
      baseRoute="/contacts"
      accentColor="cyan"
      icon={Users}
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
