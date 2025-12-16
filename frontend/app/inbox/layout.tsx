'use client';

import {
  LayoutDashboard,
  MessageSquare,
  Users,
  GitBranch,
  BarChart3,
  Settings,
  Mail,
  MessageCircle,
  Phone,
  Globe,
  Inbox,
} from 'lucide-react';
import { ModuleLayout, NavSection, QuickLink, WorkflowPhase, WorkflowStep } from '@/components/ModuleLayout';

// Omnichannel Inbox Flow:
// 1. RECEIVE: Incoming messages across channels
// 2. TRIAGE: Route, assign, prioritize
// 3. RESPOND: Reply, resolve, escalate
// 4. INTEGRATE: Create tickets, leads, follow-ups

const sections: NavSection[] = [
  {
    key: 'workspace',
    label: 'Workspace',
    description: 'Agent inbox & conversations',
    icon: LayoutDashboard,
    items: [
      { name: 'Inbox', href: '/inbox', description: 'Unified conversation inbox' },
      { name: 'My Assigned', href: '/inbox/assigned', description: 'Your conversations' },
      { name: 'Unassigned', href: '/inbox/unassigned', description: 'Queue of new messages' },
    ],
  },
  {
    key: 'channels',
    label: 'Channels',
    description: 'Communication channels',
    icon: Globe,
    items: [
      { name: 'All Channels', href: '/inbox/channels', description: 'Channel configuration' },
      { name: 'Email', href: '/inbox/channels/email', description: 'Email accounts' },
      { name: 'Chat', href: '/inbox/channels/chat', description: 'Live chat widget' },
      { name: 'WhatsApp', href: '/inbox/channels/whatsapp', description: 'WhatsApp Business' },
    ],
  },
  {
    key: 'contacts',
    label: 'Contacts',
    description: 'Customer directory',
    icon: Users,
    items: [
      { name: 'All Contacts', href: '/inbox/contacts', description: 'Unified contact list' },
      { name: 'Companies', href: '/inbox/contacts/companies', description: 'Organizations' },
    ],
  },
  {
    key: 'routing',
    label: 'Routing',
    description: 'Assignment rules',
    icon: GitBranch,
    items: [
      { name: 'Rules', href: '/inbox/routing', description: 'Auto-assignment rules' },
      { name: 'Teams', href: '/inbox/routing/teams', description: 'Team queues' },
    ],
  },
  {
    key: 'analytics',
    label: 'Analytics',
    description: 'Performance metrics',
    icon: BarChart3,
    items: [
      { name: 'Overview', href: '/inbox/analytics', description: 'Conversation metrics' },
      { name: 'Agent Performance', href: '/inbox/analytics/agents', description: 'Response times' },
      { name: 'Channel Stats', href: '/inbox/analytics/channels', description: 'By channel' },
    ],
  },
  {
    key: 'config',
    label: 'Settings',
    description: 'Preferences',
    icon: Settings,
    items: [
      { name: 'Settings', href: '/inbox/settings', description: 'Inbox preferences' },
      { name: 'Canned Responses', href: '/inbox/settings/canned', description: 'Quick replies' },
      { name: 'Signatures', href: '/inbox/settings/signatures', description: 'Email signatures' },
    ],
  },
];

const quickLinks: QuickLink[] = [
  { label: 'Inbox', href: '/inbox', icon: Inbox, color: 'blue-400' },
  { label: 'Channels', href: '/inbox/channels', icon: Globe, color: 'cyan-400' },
  { label: 'Contacts', href: '/inbox/contacts', icon: Users, color: 'emerald-400' },
  { label: 'Analytics', href: '/inbox/analytics', icon: BarChart3, color: 'amber-400' },
];

const workflowPhases: WorkflowPhase[] = [
  { key: 'receive', label: 'Receive', description: 'Incoming messages' },
  { key: 'triage', label: 'Triage', description: 'Route & assign' },
  { key: 'respond', label: 'Respond', description: 'Reply & resolve' },
];

const workflowSteps: WorkflowStep[] = [
  { label: 'Message arrives', color: 'blue' },
  { label: 'Auto-route/assign', color: 'violet' },
  { label: 'Agent responds', color: 'emerald' },
  { label: 'Create ticket/lead', color: 'amber' },
];

function getWorkflowPhase(sectionKey: string | null): string {
  if (!sectionKey) return 'receive';
  if (sectionKey === 'workspace') return 'respond';
  if (sectionKey === 'routing') return 'triage';
  if (sectionKey === 'channels') return 'receive';
  return 'receive';
}

export default function InboxLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuleLayout
      moduleName="Dotmac"
      moduleSubtitle="Inbox"
      sidebarTitle="Omnichannel Inbox"
      sidebarDescription="Unified conversations across channels"
      baseRoute="/inbox"
      accentColor="blue"
      icon={MessageSquare}
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
