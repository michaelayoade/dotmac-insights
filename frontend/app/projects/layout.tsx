'use client';

import {
  LayoutDashboard,
  ClipboardList,
  BarChart3,
  FolderKanban,
  Settings,
  FileText,
} from 'lucide-react';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import { ModuleLayout, QuickLink, WorkflowPhase, WorkflowStep } from '@/components/ModuleLayout';
import type { NavSectionType as NavSection } from '@/components/ModuleLayout';

// Project Management Flow:
// 1. PLAN: Define scope, resources, timeline
// 2. EXECUTE: Track tasks, milestones, deliverables
// 3. DELIVER: Complete, review, close out

const sections: NavSection[] = [
  {
    key: 'portfolio',
    label: 'Portfolio',
    description: 'Projects overview & details',
    icon: LayoutDashboard,
    items: [
      { name: 'Projects', href: '/projects', description: 'All projects and status' },
    ],
  },
  {
    key: 'templates',
    label: 'Templates',
    description: 'Reusable project structures',
    icon: FileText,
    items: [
      { name: 'Templates', href: '/projects/templates', description: 'Manage project templates' },
    ],
  },
  {
    key: 'analytics',
    label: 'Analytics',
    description: 'Performance & progress',
    icon: BarChart3,
    items: [
      { name: 'Analytics', href: '/projects/analytics', description: 'Trends and health' },
    ],
  },
];

const quickLinks: QuickLink[] = [
  { label: 'Projects', href: '/projects', icon: FolderKanban, color: 'amber-400' },
  { label: 'Templates', href: '/projects/templates', icon: FileText, color: 'emerald-400' },
  { label: 'Analytics', href: '/projects/analytics', icon: BarChart3, color: 'cyan-400' },
];

const workflowPhases: WorkflowPhase[] = [
  { key: 'plan', label: 'Plan', description: 'Define scope' },
  { key: 'execute', label: 'Execute', description: 'Track progress' },
  { key: 'deliver', label: 'Deliver', description: 'Complete & review' },
];

const workflowSteps: WorkflowStep[] = [
  { label: 'Plan & scope', color: 'emerald' },
  { label: 'Execute & track', color: 'amber' },
  { label: 'Deliver & review', color: 'cyan' },
];

function getWorkflowPhase(sectionKey: string | null): string {
  if (!sectionKey) return 'plan';
  if (sectionKey === 'portfolio') return 'execute';
  if (sectionKey === 'templates') return 'plan';
  return 'deliver';
}

export default function ProjectsLayout({ children }: { children: React.ReactNode }) {
  const { hasAccess, isLoading: authLoading } = useRequireScope('projects:read');

  if (authLoading) {
    return (
      <div className="min-h-screen bg-slate-deep flex justify-center items-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-400" />
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
      moduleSubtitle="Projects"
      sidebarTitle="Project Management"
      sidebarDescription="Portfolio, delivery, and performance"
      baseRoute="/projects"
      accentColor="amber"
      icon={FolderKanban}
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
