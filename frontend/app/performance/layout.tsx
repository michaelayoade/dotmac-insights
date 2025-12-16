'use client';

import {
  LayoutDashboard,
  Target,
  ClipboardCheck,
  BarChart3,
  Settings,
  Calendar,
  Users,
  FileText,
  Medal,
  Gauge,
  LineChart,
  Award,
} from 'lucide-react';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import { ModuleLayout, NavSection, QuickLink, WorkflowPhase, WorkflowStep } from '@/components/ModuleLayout';

// Performance Management Flow:
// 1. SETUP: Define KPIs, KRAs, templates
// 2. PERIOD: Create evaluation periods
// 3. COMPUTE: Generate and compute scorecards
// 4. REVIEW: Manager review and overrides
// 5. FINALIZE: HR finalizes, generate reports

const sections: NavSection[] = [
  {
    key: 'overview',
    label: 'Dashboard',
    description: 'Performance overview',
    icon: LayoutDashboard,
    items: [
      { name: 'Dashboard', href: '/performance', description: 'Overview & KPIs' },
      { name: 'Analytics', href: '/performance/analytics', description: 'Trends & insights' },
    ],
  },
  {
    key: 'setup',
    label: 'Setup',
    description: 'KPIs, KRAs & templates',
    icon: Settings,
    items: [
      { name: 'KPIs', href: '/performance/kpis', description: 'KPI definitions' },
      { name: 'KRAs', href: '/performance/kras', description: 'Key result areas' },
      { name: 'Templates', href: '/performance/templates', description: 'Scorecard templates' },
    ],
  },
  {
    key: 'periods',
    label: 'Periods',
    description: 'Evaluation periods',
    icon: Calendar,
    items: [
      { name: 'Periods', href: '/performance/periods', description: 'Manage periods' },
    ],
  },
  {
    key: 'scorecards',
    label: 'Scorecards',
    description: 'Employee scorecards',
    icon: ClipboardCheck,
    items: [
      { name: 'All Scorecards', href: '/performance/scorecards', description: 'View all scorecards' },
      { name: 'My Scorecard', href: '/performance/my-scorecard', description: 'Your performance' },
      { name: 'Team', href: '/performance/team', description: 'Team scorecards' },
    ],
  },
  {
    key: 'reviews',
    label: 'Reviews',
    description: 'Review workflow',
    icon: FileText,
    items: [
      { name: 'Review Queue', href: '/performance/reviews', description: 'Pending reviews' },
    ],
  },
  {
    key: 'reports',
    label: 'Reports',
    description: 'Performance reports',
    icon: BarChart3,
    items: [
      { name: 'Distribution', href: '/performance/reports/distribution', description: 'Score distribution' },
      { name: 'By Department', href: '/performance/reports/departments', description: 'Dept breakdown' },
      { name: 'Bonus Eligibility', href: '/performance/reports/bonus', description: 'Bonus calculations' },
    ],
  },
];

const quickLinks: QuickLink[] = [
  { label: 'New Period', href: '/performance/periods/new', icon: Calendar, color: 'violet-400' },
  { label: 'New Template', href: '/performance/templates/new', icon: FileText, color: 'cyan-400' },
  { label: 'Review Queue', href: '/performance/reviews', icon: ClipboardCheck, color: 'amber-400' },
  { label: 'Analytics', href: '/performance/analytics', icon: LineChart, color: 'emerald-400' },
];

const workflowPhases: WorkflowPhase[] = [
  { key: 'setup', label: 'Setup', description: 'Define metrics' },
  { key: 'period', label: 'Period', description: 'Create period' },
  { key: 'compute', label: 'Compute', description: 'Score employees' },
  { key: 'review', label: 'Review', description: 'Manager review' },
  { key: 'finalize', label: 'Finalize', description: 'HR approval' },
];

const workflowSteps: WorkflowStep[] = [
  { label: 'Define KPIs & KRAs', color: 'violet' },
  { label: 'Create period', color: 'cyan' },
  { label: 'Compute scores', color: 'amber' },
  { label: 'Manager review', color: 'emerald' },
  { label: 'Finalize & report', color: 'teal' },
];

function getWorkflowPhase(sectionKey: string | null): string {
  if (!sectionKey) return 'setup';
  if (sectionKey === 'setup') return 'setup';
  if (sectionKey === 'periods') return 'period';
  if (sectionKey === 'scorecards') return 'compute';
  if (sectionKey === 'reviews') return 'review';
  if (sectionKey === 'reports') return 'finalize';
  return 'setup';
}

export default function PerformanceLayout({ children }: { children: React.ReactNode }) {
  const { hasAccess, isLoading: authLoading } = useRequireScope('analytics:read');

  if (authLoading) {
    return (
      <div className="min-h-screen bg-slate-deep flex justify-center items-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-violet-400" />
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
      moduleSubtitle="Performance"
      sidebarTitle="Performance"
      sidebarDescription="KPIs, scorecards & reviews"
      baseRoute="/performance"
      accentColor="violet"
      icon={Award}
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
