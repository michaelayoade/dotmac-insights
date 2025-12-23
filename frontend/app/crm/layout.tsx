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
  Kanban,
  CalendarDays,
  GitBranch,
  UserX,
  MapPin,
  ListFilter,
} from 'lucide-react';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import { ModuleLayout } from '@/components/ModuleLayout';
import type { NavSectionType as NavSection, QuickLink, WorkflowPhase, WorkflowStep } from '@/components/ModuleLayout';

// Unified CRM Module:
// Single source of truth for all contact and pipeline data:
// - Contacts: Leads, Prospects, Customers (from UnifiedContact API)
// - Organizations and People
// - Pipeline: Opportunities and deals
// - Activities: Tasks, meetings, calls
// - Lifecycle: Funnel stages and qualification

const sections: NavSection[] = [
  {
    key: 'overview',
    label: 'Dashboard',
    description: 'CRM overview',
    icon: LayoutDashboard,
    items: [
      { name: 'Dashboard', href: '/crm', description: 'Overview & KPIs' },
      { name: 'Analytics', href: '/crm/analytics', description: 'CRM insights' },
    ],
  },
  {
    key: 'contacts',
    label: 'Contacts',
    description: 'Contact directory',
    icon: Users,
    items: [
      { name: 'All Contacts', href: '/crm/contacts/all', description: 'Complete directory' },
      { name: 'Leads', href: '/crm/contacts/leads', description: 'Leads & prospects' },
      { name: 'Customers', href: '/crm/contacts/customers', description: 'Active customers' },
      { name: 'Organizations', href: '/crm/contacts/organizations', description: 'Companies' },
      { name: 'People', href: '/crm/contacts/people', description: 'Individual contacts' },
      { name: 'Churned', href: '/crm/contacts/churned', description: 'Lost customers' },
    ],
  },
  {
    key: 'pipeline',
    label: 'Pipeline',
    description: 'Sales pipeline & deals',
    icon: Kanban,
    items: [
      { name: 'Pipeline', href: '/crm/pipeline', description: 'Kanban board' },
      { name: 'Opportunities', href: '/crm/pipeline/opportunities', description: 'Deal management' },
    ],
  },
  {
    key: 'activities',
    label: 'Activities',
    description: 'Tasks & engagements',
    icon: CalendarDays,
    items: [
      { name: 'Activities', href: '/crm/activities', description: 'Tasks & meetings' },
    ],
  },
  {
    key: 'lifecycle',
    label: 'Lifecycle',
    description: 'Lead to customer journey',
    icon: GitBranch,
    items: [
      { name: 'Sales Funnel', href: '/crm/lifecycle/funnel', description: 'Conversion stages' },
      { name: 'Qualification', href: '/crm/lifecycle/qualification', description: 'Lead scoring' },
    ],
  },
  {
    key: 'segments',
    label: 'Segments',
    description: 'Contact segments & lists',
    icon: Filter,
    items: [
      { name: 'Categories', href: '/crm/segments/categories', description: 'By category' },
      { name: 'Territories', href: '/crm/segments/territories', description: 'By territory' },
      { name: 'Tags', href: '/crm/segments/tags', description: 'Tagged contacts' },
      { name: 'Custom Lists', href: '/crm/segments/lists', description: 'Saved segments' },
    ],
  },
  {
    key: 'tools',
    label: 'Tools',
    description: 'Bulk operations & import',
    icon: Settings,
    items: [
      { name: 'Import', href: '/crm/tools/import', description: 'Bulk import' },
      { name: 'Export', href: '/crm/tools/export', description: 'Export data' },
      { name: 'Duplicates', href: '/crm/tools/duplicates', description: 'Find & merge' },
      { name: 'Data Quality', href: '/crm/tools/quality', description: 'Clean up data' },
    ],
  },
];

const quickLinks: QuickLink[] = [
  { label: 'New Contact', href: '/crm/contacts/new', icon: UserPlus, color: 'cyan-400' },
  { label: 'New Lead', href: '/crm/contacts/new?type=lead', icon: Target, color: 'violet-400' },
  { label: 'New Deal', href: '/crm/pipeline/opportunities/new', icon: TrendingUp, color: 'emerald-400' },
  { label: 'Import', href: '/crm/tools/import', icon: FileUp, color: 'amber-400' },
];

const workflowPhases: WorkflowPhase[] = [
  { key: 'lead', label: 'Lead', description: 'Capture & qualify' },
  { key: 'prospect', label: 'Prospect', description: 'Nurture interest' },
  { key: 'opportunity', label: 'Opportunity', description: 'Manage deals' },
  { key: 'customer', label: 'Customer', description: 'Active accounts' },
  { key: 'advocate', label: 'Advocate', description: 'Referral program' },
];

const workflowSteps: WorkflowStep[] = [
  { label: 'Capture lead', color: 'violet' },
  { label: 'Qualify prospect', color: 'cyan' },
  { label: 'Close opportunity', color: 'emerald' },
  { label: 'Convert to customer', color: 'teal' },
  { label: 'Grow & retain', color: 'amber' },
];

function getWorkflowPhase(sectionKey: string | null): string {
  if (!sectionKey) return 'lead';
  if (sectionKey === 'contacts') return 'customer';
  if (sectionKey === 'pipeline') return 'opportunity';
  if (sectionKey === 'activities') return 'prospect';
  if (sectionKey === 'lifecycle') return 'prospect';
  if (sectionKey === 'segments') return 'advocate';
  return 'lead';
}

export default function CRMLayout({ children }: { children: React.ReactNode }) {
  const { hasAccess, isLoading: authLoading } = useRequireScope('crm:read');

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
      moduleSubtitle="CRM"
      sidebarTitle="CRM"
      sidebarDescription="Unified contact & pipeline management"
      baseRoute="/crm"
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
