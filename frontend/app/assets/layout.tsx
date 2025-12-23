'use client';

import {
  LayoutDashboard,
  Package,
  Layers,
  Calendar,
  Clock,
  Wrench,
  Shield,
  FileWarning,
  Settings,
  Building2,
  TrendingDown,
} from 'lucide-react';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import { ModuleLayout } from '@/components/ModuleLayout';
import type { NavSectionType as NavSection, QuickLink, WorkflowPhase, WorkflowStep } from '@/components/ModuleLayout';

// Asset Management Flow:
// 1. ACQUIRE: Purchase, capitalize, categorize
// 2. OPERATE: Maintain, insure, track
// 3. DEPRECIATE: Schedule, post, review
// 4. DISPOSE: Retire, sell, write-off

const sections: NavSection[] = [
  {
    key: 'overview',
    label: 'Dashboard',
    description: 'Asset overview',
    icon: LayoutDashboard,
    items: [
      { name: 'Dashboard', href: '/assets', description: 'Asset overview' },
    ],
  },
  {
    key: 'register',
    label: 'Asset Register',
    description: 'All assets & categories',
    icon: Package,
    items: [
      { name: 'All Assets', href: '/assets/list', description: 'Full asset register' },
      { name: 'Categories', href: '/assets/categories', description: 'Asset categories' },
    ],
  },
  {
    key: 'depreciation',
    label: 'Depreciation',
    description: 'Schedules & entries',
    icon: TrendingDown,
    items: [
      { name: 'Schedule', href: '/assets/depreciation', description: 'Depreciation schedule' },
      { name: 'Pending', href: '/assets/depreciation/pending', description: 'Pending entries' },
    ],
  },
  {
    key: 'maintenance',
    label: 'Maintenance',
    description: 'Service & warranties',
    icon: Wrench,
    items: [
      { name: 'Due', href: '/assets/maintenance', description: 'Maintenance due' },
      { name: 'Warranty', href: '/assets/maintenance/warranty', description: 'Expiring warranties' },
      { name: 'Insurance', href: '/assets/maintenance/insurance', description: 'Expiring insurance' },
    ],
  },
  {
    key: 'config',
    label: 'Configuration',
    description: 'Settings & preferences',
    icon: Settings,
    items: [
      { name: 'Settings', href: '/assets/settings', description: 'Preferences' },
    ],
  },
];

const quickLinks: QuickLink[] = [
  { label: 'Assets', href: '/assets/list', icon: Package, color: 'indigo-400' },
  { label: 'Depreciation', href: '/assets/depreciation', icon: TrendingDown, color: 'amber-400' },
  { label: 'Maintenance', href: '/assets/maintenance', icon: Wrench, color: 'emerald-400' },
  { label: 'Warranty', href: '/assets/maintenance/warranty', icon: Shield, color: 'rose-400' },
];

const workflowPhases: WorkflowPhase[] = [
  { key: 'acquire', label: 'Acquire', description: 'Purchase & capitalize' },
  { key: 'operate', label: 'Operate', description: 'Maintain & track' },
  { key: 'depreciate', label: 'Depreciate', description: 'Schedule & post' },
];

const workflowSteps: WorkflowStep[] = [
  { label: 'Acquire & capitalize', color: 'indigo' },
  { label: 'Operate & maintain', color: 'emerald' },
  { label: 'Depreciate & post', color: 'amber' },
  { label: 'Dispose & retire', color: 'rose' },
];

function getWorkflowPhase(sectionKey: string | null): string {
  if (!sectionKey) return 'acquire';
  if (sectionKey === 'register') return 'acquire';
  if (sectionKey === 'maintenance') return 'operate';
  if (sectionKey === 'depreciation') return 'depreciate';
  return 'acquire';
}

export default function AssetsLayout({ children }: { children: React.ReactNode }) {
  const { hasAccess, isLoading: authLoading } = useRequireScope('assets:read');

  if (authLoading) {
    return (
      <div className="min-h-screen bg-slate-deep flex justify-center items-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-400" />
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
      moduleSubtitle="Assets"
      sidebarTitle="Fixed Asset Management"
      sidebarDescription="Assets, depreciation & maintenance"
      baseRoute="/assets"
      accentColor="indigo"
      icon={Building2}
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
