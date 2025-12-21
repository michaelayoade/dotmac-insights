'use client';

import Link from 'next/link';
import {
  ListChecks,
  BarChart3,
  MessageCircle,
  Inbox,
  AlertTriangle,
  ShieldCheck,
  Target,
  Settings,
  Headphones,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useConsolidatedSupportDashboard, useSupportSlaBreachesSummary } from '@/hooks/useApi';
import { ModuleLayout, NavSection, QuickLink, WorkflowPhase, WorkflowStep } from '@/components/ModuleLayout';

const sections: NavSection[] = [
  {
    key: 'desk',
    label: 'Omnichannel Desk',
    description: 'Tickets, conversations, and assignments',
    icon: Inbox,
    items: [
      { name: 'Dashboard', href: '/support', description: 'Overview & metrics' },
      { name: 'Tickets', href: '/support/tickets', description: 'Inbox, SLA, assignments' },
      { name: 'Agents', href: '/support/agents', description: 'People, capacity, skills' },
      { name: 'Teams', href: '/support/teams', description: 'Queues, members, routing' },
    ],
  },
  {
    key: 'insights',
    label: 'Analytics',
    description: 'Performance, SLA, backlog',
    icon: BarChart3,
    items: [
      { name: 'Analytics', href: '/support/analytics', description: 'Trends, SLA attainment' },
      { name: 'CSAT', href: '/support/csat', description: 'Surveys & feedback' },
    ],
  },
  {
    key: 'operations',
    label: 'Automation & SLA',
    description: 'Rules, calendars, routing',
    icon: ShieldCheck,
    items: [
      { name: 'SLA', href: '/support/sla', description: 'Policies, calendars, breaches' },
      { name: 'Automation', href: '/support/automation', description: 'Rules & logs' },
      { name: 'Routing', href: '/support/routing', description: 'Rules, workload, health' },
    ],
  },
  {
    key: 'content',
    label: 'Knowledge & Canned',
    description: 'Knowledge base & snippets',
    icon: MessageCircle,
    items: [
      { name: 'Knowledge Base', href: '/support/kb', description: 'Categories & articles' },
      { name: 'Canned Responses', href: '/support/canned-responses', description: 'Shortcodes & templates' },
    ],
  },
  {
    key: 'config',
    label: 'Configuration',
    description: 'Support settings',
    icon: Settings,
    items: [
      { name: 'Settings', href: '/support/settings', description: 'Helpdesk configuration' },
    ],
  },
];

const quickLinks: QuickLink[] = [
  { label: 'New Ticket', href: '/support/tickets/new', icon: ListChecks, color: 'emerald-400' },
  { label: 'Inbox', href: '/support/tickets', icon: MessageCircle, color: 'amber-400' },
  { label: 'Analytics', href: '/support/analytics', icon: BarChart3, color: 'cyan-400' },
  { label: 'SLA Watch', href: '/support/sla', icon: AlertTriangle, color: 'rose-400' },
];

const workflowPhases: WorkflowPhase[] = [
  { key: 'intake', label: 'Intake', description: 'Capture & categorize' },
  { key: 'resolve', label: 'Resolve', description: 'Assign & respond' },
  { key: 'analyze', label: 'Analyze', description: 'Improve & prevent' },
];

const workflowSteps: WorkflowStep[] = [
  { label: 'Capture (email/voice/chat)', color: 'teal' },
  { label: 'Triage & assign', color: 'amber' },
  { label: 'Respond & resolve', color: 'emerald' },
  { label: 'Analyze & improve', color: 'rose' },
];

function getWorkflowPhase(sectionKey: string | null): string {
  if (!sectionKey) return 'intake';
  if (sectionKey === 'desk') return 'resolve';
  return 'analyze';
}

// Live metrics component for header
function LiveMetrics() {
  const { data: dashboard } = useConsolidatedSupportDashboard();
  const { data: slaBreach } = useSupportSlaBreachesSummary({ days: 30 });

  const overdueCount = slaBreach?.currently_overdue ?? dashboard?.summary?.overdue_tickets ?? 0;
  const openCount = dashboard?.summary?.open_tickets ?? 0;
  const slaAttainment = dashboard?.summary?.sla_attainment ?? 0;

  return (
    <div className="hidden lg:flex items-center gap-4 px-4 py-1.5 bg-slate-elevated rounded-lg mr-2">
      <div className="flex items-center gap-1.5">
        <Inbox className="w-3.5 h-3.5 text-blue-400" />
        <span className="text-sm font-medium text-white">{openCount}</span>
        <span className="text-xs text-slate-muted">open</span>
      </div>
      <div className="w-px h-4 bg-slate-border" />
      <div className="flex items-center gap-1.5">
        <AlertTriangle className={cn('w-3.5 h-3.5', overdueCount > 0 ? 'text-rose-400' : 'text-slate-muted')} />
        <span className={cn('text-sm font-medium', overdueCount > 0 ? 'text-rose-400' : 'text-white')}>{overdueCount}</span>
        <span className="text-xs text-slate-muted">overdue</span>
      </div>
      <div className="w-px h-4 bg-slate-border" />
      <div className="flex items-center gap-1.5">
        <Target className={cn('w-3.5 h-3.5', slaAttainment >= 90 ? 'text-emerald-400' : slaAttainment >= 80 ? 'text-amber-400' : 'text-rose-400')} />
        <span className={cn('text-sm font-medium', slaAttainment >= 90 ? 'text-emerald-400' : slaAttainment >= 80 ? 'text-amber-400' : 'text-rose-400')}>
          {slaAttainment.toFixed(0)}%
        </span>
        <span className="text-xs text-slate-muted">SLA</span>
      </div>
    </div>
  );
}

// Mobile overdue badge
function MobileOverdueBadge() {
  const { data: dashboard } = useConsolidatedSupportDashboard();
  const { data: slaBreach } = useSupportSlaBreachesSummary({ days: 30 });
  const overdueCount = slaBreach?.currently_overdue ?? dashboard?.summary?.overdue_tickets ?? 0;

  if (overdueCount === 0) return null;

  return (
    <Link href="/support/sla" className="lg:hidden relative p-2 text-rose-400 hover:bg-slate-elevated rounded-lg transition-colors">
      <AlertTriangle className="w-5 h-5" />
      <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-rose-500 text-white text-[9px] font-bold flex items-center justify-center">
        {overdueCount > 9 ? '9+' : overdueCount}
      </span>
    </Link>
  );
}

export default function SupportLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuleLayout
      moduleName="Dotmac"
      moduleSubtitle="Support"
      sidebarTitle="Support Desk"
      sidebarDescription="Omnichannel helpdesk & SLA management"
      baseRoute="/support"
      accentColor="teal"
      icon={Headphones}
      sections={sections}
      quickLinks={quickLinks}
      workflowPhases={workflowPhases}
      getWorkflowPhase={getWorkflowPhase}
      workflowSteps={workflowSteps}
      headerContent={
        <>
          <LiveMetrics />
          <MobileOverdueBadge />
        </>
      }
    >
      {children}
    </ModuleLayout>
  );
}
