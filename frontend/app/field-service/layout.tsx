'use client';

import {
  LayoutDashboard,
  ClipboardList,
  Calendar,
  Users,
  BarChart3,
  Settings,
  Truck,
  MapPin,
  Wrench,
  Clock,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';
import { ModuleLayout, NavSection, QuickLink, WorkflowPhase, WorkflowStep } from '@/components/ModuleLayout';

// Field Service Information Flow:
// 1. ORDERS: Create and manage service orders (Core)
// 2. SCHEDULE: Plan and dispatch technicians (Planning)
// 3. TEAMS: Manage technicians and skills (Resources)
// 4. EXECUTION: Track work in progress (Operations)
// 5. ANALYTICS: Reports and performance metrics (Monitoring)

const sections: NavSection[] = [
  {
    key: 'overview',
    label: 'Dashboard',
    description: 'Field service overview and KPIs',
    icon: LayoutDashboard,
    items: [
      { name: 'Overview', href: '/field-service', description: 'Dashboard & metrics' },
      { name: 'Analytics', href: '/field-service/analytics', description: 'Reports & performance' },
    ],
  },
  {
    key: 'orders',
    label: 'Service Orders',
    description: 'Work orders and dispatch',
    icon: ClipboardList,
    items: [
      { name: 'All Orders', href: '/field-service/orders', description: 'View all service orders' },
      { name: 'New Order', href: '/field-service/orders/new', description: 'Create service order' },
    ],
  },
  {
    key: 'scheduling',
    label: 'Scheduling',
    description: 'Calendar and dispatch planning',
    icon: Calendar,
    items: [
      { name: 'Schedule', href: '/field-service/schedule', description: 'Dispatch calendar' },
    ],
  },
  {
    key: 'resources',
    label: 'Resources',
    description: 'Teams and technicians',
    icon: Users,
    items: [
      { name: 'Teams', href: '/field-service/teams', description: 'Manage field teams' },
    ],
  },
];

const quickLinks: QuickLink[] = [
  { label: 'New Order', href: '/field-service/orders/new', icon: ClipboardList, color: 'teal-400' },
  { label: 'Schedule', href: '/field-service/schedule', icon: Calendar, color: 'violet-400' },
  { label: 'Teams', href: '/field-service/teams', icon: Users, color: 'amber-400' },
  { label: 'Analytics', href: '/field-service/analytics', icon: BarChart3, color: 'cyan-400' },
];

const workflowPhases: WorkflowPhase[] = [
  { key: 'plan', label: 'Plan', description: 'Create & schedule orders' },
  { key: 'execute', label: 'Execute', description: 'Dispatch & track work' },
  { key: 'analyze', label: 'Analyze', description: 'Review performance' },
];

const workflowSteps: WorkflowStep[] = [
  { label: 'Create Order', color: 'teal' },
  { label: 'Assign Technician', color: 'violet' },
  { label: 'Dispatch', color: 'amber' },
  { label: 'Execute Work', color: 'emerald' },
  { label: 'Complete & Review', color: 'cyan' },
];

function getWorkflowPhase(sectionKey: string | null): string {
  if (!sectionKey) return 'plan';
  if (sectionKey === 'overview') return 'analyze';
  if (sectionKey === 'orders' || sectionKey === 'scheduling') return 'plan';
  return 'execute';
}

export default function FieldServiceLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuleLayout
      moduleName="Dotmac Field Service"
      moduleSubtitle="Service"
      sidebarTitle="Field Service"
      sidebarDescription="Dispatch & service order management"
      baseRoute="/field-service"
      accentColor="teal"
      icon={Truck}
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
