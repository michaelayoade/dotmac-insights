'use client';

import {
  LayoutDashboard,
  CalendarClock,
  Clock3,
  Wallet2,
  TrendingUp,
  Settings,
  Users,
  UserPlus,
  Activity,
} from 'lucide-react';
import { useMemo } from 'react';
import { ModuleLayout, NavSection, QuickLink, WorkflowPhase, WorkflowStep } from '@/components/ModuleLayout';
import { useEntitlements } from '@/hooks/useApi';

// HR Information Flow:
// 1. SETUP: Define policies, structures, components (Foundation)
// 2. PEOPLE: Recruit, onboard, manage employee lifecycle (Core)
// 3. TIME & ATTENDANCE: Track time, leave, shifts (Daily Operations)
// 4. COMPENSATION: Payroll processing, salary management (Monthly Cycle)
// 5. DEVELOPMENT: Training, appraisals, career growth (Continuous)
// 6. ANALYTICS: Reports, insights, compliance (Monitoring)

const baseSections: NavSection[] = [
  {
    key: 'overview',
    label: 'Dashboard',
    description: 'HR overview and pending actions',
    icon: LayoutDashboard,
    items: [
      { name: 'Overview', href: '/hr', description: 'Dashboard & metrics' },
      { name: 'Analytics', href: '/hr/analytics', description: 'Reports & insights' },
    ],
  },
  {
    key: 'people',
    label: 'People Management',
    description: 'Recruitment to offboarding',
    icon: Users,
    items: [
      { name: 'Recruitment', href: '/hr/recruitment', description: 'Job openings & hiring' },
      { name: 'Lifecycle', href: '/hr/lifecycle', description: 'Onboarding & offboarding' },
    ],
  },
  {
    key: 'time',
    label: 'Time & Leave',
    description: 'Attendance and leave management',
    icon: Clock3,
    items: [
      { name: 'Attendance', href: '/hr/attendance', description: 'Check-in/out & shifts' },
      { name: 'Leave', href: '/hr/leave', description: 'Leave types & applications' },
    ],
  },
  {
    key: 'compensation',
    label: 'Compensation',
    description: 'Payroll and salary structures',
    icon: Wallet2,
    items: [
      { name: 'Payroll', href: '/hr/payroll', description: 'Salary slips & processing' },
    ],
  },
  {
    key: 'development',
    label: 'Development',
    description: 'Training and performance',
    icon: TrendingUp,
    items: [
      { name: 'Training', href: '/hr/training', description: 'Programs & events' },
      { name: 'Appraisals', href: '/hr/appraisals', description: 'Performance reviews' },
    ],
  },
  {
    key: 'config',
    label: 'Configuration',
    description: 'HR policies and settings',
    icon: Settings,
    items: [
      { name: 'Settings', href: '/hr/settings', description: 'HR configuration' },
    ],
  },
];

const quickLinks: QuickLink[] = [
  { label: 'Leave', href: '/hr/leave', icon: CalendarClock, color: 'amber-400' },
  { label: 'Payroll', href: '/hr/payroll', icon: Wallet2, color: 'violet-400' },
  { label: 'Recruit', href: '/hr/recruitment', icon: UserPlus, color: 'emerald-400' },
  { label: 'Reports', href: '/hr/analytics', icon: Activity, color: 'cyan-400' },
];

const workflowPhases: WorkflowPhase[] = [
  { key: 'setup', label: 'Setup', description: 'Configure people policies' },
  { key: 'operate', label: 'Operate', description: 'Daily people operations' },
  { key: 'analyze', label: 'Analyze', description: 'Review & improve' },
];

const workflowSteps: WorkflowStep[] = [
  { label: 'Recruit & Hire', color: 'violet' },
  { label: 'Onboard Employee', color: 'emerald' },
  { label: 'Manage Time & Leave', color: 'amber' },
  { label: 'Process Payroll', color: 'cyan' },
  { label: 'Develop & Review', color: 'rose' },
];

function getWorkflowPhase(sectionKey: string | null): string {
  if (!sectionKey) return 'setup';
  if (sectionKey === 'overview') return 'analyze';
  if (sectionKey === 'people' || sectionKey === 'config') return 'setup';
  return 'operate';
}

export default function HrLayout({ children }: { children: React.ReactNode }) {
  const { data: entitlements } = useEntitlements();
  const nigeriaEnabled = entitlements?.feature_flags?.NIGERIA_COMPLIANCE_ENABLED ?? false;
  const sections = useMemo(() => {
    if (!nigeriaEnabled) {
      return baseSections;
    }
    return baseSections.map((section) => {
      if (section.key !== 'compensation') return section;
      return {
        ...section,
        items: [
          ...section.items,
          { name: 'Statutory (Nigeria)', href: '/books/tax/paye', description: 'PAYE compliance tools' },
        ],
      };
    });
  }, [nigeriaEnabled]);

  return (
    <ModuleLayout
      moduleName="Dotmac People"
      moduleSubtitle="People"
      sidebarTitle="Human Resources"
      sidebarDescription="People operations & workforce management"
      baseRoute="/hr"
      accentColor="amber"
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
