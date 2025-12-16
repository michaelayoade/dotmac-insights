'use client';

import {
  LayoutDashboard,
  BookOpen,
  Scale,
  FileSpreadsheet,
  TrendingUp,
  BookMarked,
  ClipboardList,
  Users,
  ArrowDownToLine,
  Landmark,
  CreditCard,
  PiggyBank,
  Lock,
  Bell,
  ShieldCheck,
  Settings,
  Receipt,
  Banknote,
  Calculator,
  Activity,
  BadgePercent,
} from 'lucide-react';
import { ModuleLayout, NavSection, QuickLink, WorkflowPhase, WorkflowStep } from '@/components/ModuleLayout';

// Books & Accounting Flow:
// 1. CAPTURE: Record transactions (invoices, bills, payments)
// 2. MANAGE: Handle AR/AP, banking, reconciliation
// 3. CLOSE: Period close, tax filing, compliance
// 4. REPORT: Generate financial statements and reports

const sections: NavSection[] = [
  {
    key: 'overview',
    label: 'Dashboard',
    description: 'KPIs & shortcuts',
    icon: LayoutDashboard,
    items: [
      { name: 'Dashboard', href: '/books', description: 'Overview & metrics' },
    ],
  },
  {
    key: 'sales',
    label: 'Sales (AR)',
    description: 'Customer billing & payments',
    icon: FileSpreadsheet,
    items: [
      { name: 'Invoices', href: '/books/accounts-receivable/invoices', description: 'Customer billing' },
      { name: 'Payments', href: '/books/accounts-receivable/payments', description: 'Incoming payments' },
      { name: 'Credit Notes', href: '/books/accounts-receivable/credit-notes', description: 'Customer credits' },
      { name: 'Customers', href: '/books/accounts-receivable/customers', description: 'AR by customer' },
      { name: 'AR Overview', href: '/books/accounts-receivable', description: 'Receivable health' },
      { name: 'Credit Mgmt', href: '/books/accounts-receivable/credit', description: 'Limits & reviews' },
      { name: 'Dunning', href: '/books/accounts-receivable/dunning', description: 'Reminders & stages' },
    ],
  },
  {
    key: 'purchases',
    label: 'Purchases (AP)',
    description: 'Supplier invoices & payments',
    icon: ArrowDownToLine,
    items: [
      { name: 'Bills', href: '/books/accounts-payable/bills', description: 'Supplier invoices' },
      { name: 'Payments', href: '/books/accounts-payable/payments', description: 'Outgoing payments' },
      { name: 'Debit Notes', href: '/books/accounts-payable/debit-notes', description: 'Supplier credits' },
      { name: 'Suppliers', href: '/books/accounts-payable/suppliers', description: 'AP by supplier' },
      { name: 'AP Overview', href: '/books/accounts-payable', description: 'Payables status' },
    ],
  },
  {
    key: 'banking',
    label: 'Banking',
    description: 'Accounts & transactions',
    icon: Landmark,
    items: [
      { name: 'Bank Accounts', href: '/books/bank-accounts', description: 'Account setup' },
      { name: 'Transactions', href: '/books/bank-transactions', description: 'Activity & imports' },
    ],
  },
  {
    key: 'gateway',
    label: 'Payment Gateway',
    description: 'Online payments & transfers',
    icon: CreditCard,
    items: [
      { name: 'Online Payments', href: '/books/gateway/payments', description: 'Card & bank payments' },
      { name: 'Bank Transfers', href: '/books/gateway/transfers', description: 'Payouts & disbursements' },
      { name: 'Banks & NUBAN', href: '/books/gateway/banks', description: 'Bank lookup' },
      { name: 'Open Banking', href: '/books/gateway/connections', description: 'Linked accounts' },
    ],
  },
  {
    key: 'tax',
    label: 'Tax & Compliance',
    description: 'VAT, WHT, PAYE, CIT',
    icon: BadgePercent,
    items: [
      { name: 'Tax Dashboard', href: '/books/tax', description: 'Tax overview' },
      { name: 'VAT', href: '/books/tax/vat', description: 'Value Added Tax' },
      { name: 'WHT', href: '/books/tax/wht', description: 'Withholding Tax' },
      { name: 'PAYE', href: '/books/tax/paye', description: 'Employee tax' },
      { name: 'CIT', href: '/books/tax/cit', description: 'Company Income Tax' },
      { name: 'Filing Calendar', href: '/books/tax/filing', description: 'Deadlines & reminders' },
      { name: 'E-Invoice', href: '/books/tax/einvoice', description: 'FIRS BIS 3.0' },
      { name: 'Tax Settings', href: '/books/tax/settings', description: 'Tax configuration' },
    ],
  },
  {
    key: 'reports',
    label: 'Financial Reports',
    description: 'Statements & analysis',
    icon: TrendingUp,
    items: [
      { name: 'Balance Sheet', href: '/books/balance-sheet', description: 'Position overview' },
      { name: 'Income Statement', href: '/books/income-statement', description: 'P&L view' },
      { name: 'Cash Flow', href: '/books/cash-flow', description: 'Cash movements' },
      { name: 'Equity Statement', href: '/books/equity-statement', description: 'Equity changes' },
    ],
  },
  {
    key: 'ledger',
    label: 'General Ledger',
    description: 'Accounts & entries',
    icon: BookMarked,
    items: [
      { name: 'General Ledger', href: '/books/general-ledger', description: 'All postings' },
      { name: 'GL Expenses', href: '/books/gl-expenses', description: 'Expense entries' },
      { name: 'Trial Balance', href: '/books/trial-balance', description: 'Accounts snapshot' },
      { name: 'Journal Entries', href: '/books/journal-entries', description: 'Manual entries' },
      { name: 'Chart of Accounts', href: '/books/chart-of-accounts', description: 'Account structure' },
    ],
  },
  {
    key: 'config',
    label: 'Configuration',
    description: 'Preferences & setup',
    icon: Settings,
    items: [
      { name: 'Settings', href: '/books/settings', description: 'Books configuration' },
    ],
  },
];

const quickLinks: QuickLink[] = [
  { label: 'New Invoice', href: '/books/accounts-receivable/invoices/new', icon: Receipt, color: 'teal-400' },
  { label: 'New Bill', href: '/books/accounts-payable/bills/new', icon: ClipboardList, color: 'amber-400' },
  { label: 'New Payment', href: '/books/accounts-receivable/payments/new', icon: Banknote, color: 'emerald-400' },
  { label: 'Banking', href: '/books/bank-transactions', icon: CreditCard, color: 'cyan-400' },
];

const workflowPhases: WorkflowPhase[] = [
  { key: 'capture', label: 'Capture', description: 'Record transactions' },
  { key: 'manage', label: 'Manage', description: 'AR/AP & banking' },
  { key: 'report', label: 'Report', description: 'Statements & analysis' },
];

const workflowSteps: WorkflowStep[] = [
  { label: 'Capture transactions', color: 'teal' },
  { label: 'Manage AR/AP', color: 'amber' },
  { label: 'Reconcile banking', color: 'emerald' },
  { label: 'Publish statements', color: 'cyan' },
];

function getWorkflowPhase(sectionKey: string | null): string {
  if (!sectionKey) return 'capture';
  if (sectionKey === 'sales' || sectionKey === 'purchases') return 'capture';
  if (sectionKey === 'banking' || sectionKey === 'gateway' || sectionKey === 'tax' || sectionKey === 'ledger') return 'manage';
  if (sectionKey === 'reports') return 'report';
  return 'capture';
}

export default function BooksLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuleLayout
      moduleName="Dotmac"
      moduleSubtitle="Books"
      sidebarTitle="Books & Accounting"
      sidebarDescription="Transactions, reconciliation, and reporting"
      baseRoute="/books"
      accentColor="teal"
      icon={Activity}
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
