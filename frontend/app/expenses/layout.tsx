'use client';

import {
  LayoutDashboard,
  FileText,
  Wallet2,
  Settings,
  CreditCard,
  Receipt,
  FileSpreadsheet,
  BarChart3,
  ClipboardCheck,
  Download,
} from 'lucide-react';
import { ModuleLayout, NavSection, QuickLink, WorkflowPhase, WorkflowStep } from '@/components/ModuleLayout';

// Expense Management Flow:
// 1. SUBMIT: Employees submit expense claims or request advances
// 2. APPROVE: Managers review and approve submissions
// 3. RECONCILE: Match card transactions, import statements
// 4. REPORT: Generate reports and export data

const sections: NavSection[] = [
  {
    key: 'overview',
    label: 'Dashboard',
    description: 'Overview and pending actions',
    icon: LayoutDashboard,
    items: [
      { name: 'Overview', href: '/expenses', description: 'Workspace metrics' },
      { name: 'Approvals', href: '/expenses/approvals', description: 'Pending reviews' },
    ],
  },
  {
    key: 'submissions',
    label: 'Submissions',
    description: 'Claims and advances',
    icon: FileText,
    items: [
      { name: 'Claims', href: '/expenses/claims', description: 'Submit & approve' },
      { name: 'Cash Advances', href: '/expenses/advances', description: 'Disburse & settle' },
    ],
  },
  {
    key: 'cards',
    label: 'Corporate Cards',
    description: 'Card management & transactions',
    icon: CreditCard,
    items: [
      { name: 'Cards', href: '/expenses/cards', description: 'Card management' },
      { name: 'Transactions', href: '/expenses/transactions', description: 'Card transactions' },
      { name: 'Statements', href: '/expenses/statements', description: 'Reconciliation' },
      { name: 'Card Analytics', href: '/expenses/card-analytics', description: 'Spend insights' },
    ],
  },
  {
    key: 'reporting',
    label: 'Reporting',
    description: 'Reports and exports',
    icon: Download,
    items: [
      { name: 'Reports', href: '/expenses/reports', description: 'Export data' },
    ],
  },
  {
    key: 'config',
    label: 'Configuration',
    description: 'Policies and settings',
    icon: Settings,
    items: [
      { name: 'Settings', href: '/expenses/settings', description: 'Policies & limits' },
    ],
  },
];

const quickLinks: QuickLink[] = [
  { label: 'New Claim', href: '/expenses/claims/new', icon: FileText, color: 'sky-400' },
  { label: 'Approvals', href: '/expenses/approvals', icon: ClipboardCheck, color: 'amber-400' },
  { label: 'Cards', href: '/expenses/cards', icon: CreditCard, color: 'violet-400' },
  { label: 'Reports', href: '/expenses/reports', icon: BarChart3, color: 'emerald-400' },
];

const workflowPhases: WorkflowPhase[] = [
  { key: 'submit', label: 'Submit', description: 'Create claims & requests' },
  { key: 'approve', label: 'Approve', description: 'Review & authorize' },
  { key: 'reconcile', label: 'Reconcile', description: 'Match & report' },
];

const workflowSteps: WorkflowStep[] = [
  { label: 'Submit claim/advance', color: 'sky' },
  { label: 'Manager approval', color: 'amber' },
  { label: 'Match transactions', color: 'violet' },
  { label: 'Generate reports', color: 'emerald' },
];

function getWorkflowPhase(sectionKey: string | null): string {
  if (!sectionKey) return 'submit';
  if (sectionKey === 'submissions') return 'submit';
  if (sectionKey === 'overview') return 'approve';
  return 'reconcile';
}

export default function ExpensesLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuleLayout
      moduleName="Dotmac"
      moduleSubtitle="Expenses"
      sidebarTitle="Expense Controls"
      sidebarDescription="Claims, advances, and policies"
      baseRoute="/expenses"
      accentColor="sky"
      icon={Wallet2}
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
