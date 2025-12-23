'use client';

import {
  LayoutDashboard,
  BookOpen,
  Scale,
  FileSpreadsheet,
  Users,
  Landmark,
} from 'lucide-react';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import { ModuleLayout } from '@/components/ModuleLayout';
import type { NavSectionType as NavSection } from '@/components/ModuleLayout';

const sections: NavSection[] = [
  {
    key: 'overview',
    label: 'Overview',
    description: 'Financial snapshot',
    icon: LayoutDashboard,
    items: [
      { name: 'Dashboard', href: '/accounting', description: 'Key metrics' },
    ],
  },
  {
    key: 'ledgers',
    label: 'Ledgers',
    description: 'Core accounting data',
    icon: BookOpen,
    items: [
      { name: 'Chart of Accounts', href: '/accounting/chart-of-accounts', description: 'Account structure' },
      { name: 'General Ledger', href: '/accounting/general-ledger', description: 'Journal rollups' },
      { name: 'Journal Entries', href: '/accounting/journal-entries', description: 'Daily postings' },
    ],
  },
  {
    key: 'statements',
    label: 'Statements',
    description: 'Financial reports',
    icon: FileSpreadsheet,
    items: [
      { name: 'Trial Balance', href: '/accounting/trial-balance', description: 'Balances check' },
      { name: 'Balance Sheet', href: '/accounting/balance-sheet', description: 'Assets and liabilities' },
      { name: 'Income Statement', href: '/accounting/income-statement', description: 'Profit and loss' },
    ],
  },
  {
    key: 'payables',
    label: 'Payables & Receivables',
    description: 'AR/AP management',
    icon: Users,
    items: [
      { name: 'Accounts Payable', href: '/accounting/accounts-payable', description: 'Bills and vendors' },
      { name: 'Accounts Receivable', href: '/accounting/accounts-receivable', description: 'Invoices and aging' },
      { name: 'Suppliers', href: '/accounting/suppliers', description: 'Vendor records' },
    ],
  },
  {
    key: 'banking',
    label: 'Banking',
    description: 'Linked accounts',
    icon: Landmark,
    items: [
      { name: 'Bank Accounts', href: '/accounting/bank-accounts', description: 'Account balances' },
    ],
  },
];

export default function AccountingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { hasAccess, isLoading: authLoading } = useRequireScope('accounting:read');

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
      moduleSubtitle="Accounting"
      sidebarTitle="Accounting"
      sidebarDescription="Reports, ledgers, and reconciliations"
      baseRoute="/accounting"
      accentColor="amber"
      icon={Scale}
      sections={sections}
    >
      {children}
    </ModuleLayout>
  );
}
