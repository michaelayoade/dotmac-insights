'use client';

import {
  LayoutDashboard,
  FileText,
  CreditCard,
  ShoppingCart,
  FileX,
  Users,
  Calendar,
  TrendingUp,
  Settings,
} from 'lucide-react';
import { ModuleLayout, NavSection, QuickLink, WorkflowPhase, WorkflowStep } from '@/components/ModuleLayout';

// Purchasing Flow:
// 1. ORDER: Create purchase orders, manage requisitions
// 2. RECEIVE: Process bills, track deliveries
// 3. PAY: Make payments, manage AP aging
// 4. ANALYZE: Vendor analytics, spend analysis

const sections: NavSection[] = [
  {
    key: 'overview',
    label: 'Dashboard',
    description: 'AP overview & metrics',
    icon: LayoutDashboard,
    items: [
      { name: 'Dashboard', href: '/purchasing', description: 'Overview & KPIs' },
      { name: 'Analytics', href: '/purchasing/analytics', description: 'Spend analysis' },
    ],
  },
  {
    key: 'orders',
    label: 'Procurement',
    description: 'Orders & requisitions',
    icon: ShoppingCart,
    items: [
      { name: 'Purchase Orders', href: '/purchasing/orders', description: 'Create & track orders' },
    ],
  },
  {
    key: 'payables',
    label: 'Accounts Payable',
    description: 'Bills & payments',
    icon: FileText,
    items: [
      { name: 'Bills', href: '/purchasing/bills', description: 'Supplier invoices' },
      { name: 'Payments', href: '/purchasing/payments', description: 'Outgoing payments' },
      { name: 'Debit Notes', href: '/purchasing/debit-notes', description: 'Supplier credits' },
      { name: 'AP Aging', href: '/purchasing/aging', description: 'Aging analysis' },
    ],
  },
  {
    key: 'vendors',
    label: 'Vendors',
    description: 'Supplier management',
    icon: Users,
    items: [
      { name: 'Suppliers', href: '/purchasing/suppliers', description: 'Vendor directory' },
    ],
  },
];

const quickLinks: QuickLink[] = [
  { label: 'New Order', href: '/purchasing/orders/new', icon: ShoppingCart, color: 'violet-400' },
  { label: 'New Bill', href: '/purchasing/bills/new', icon: FileText, color: 'amber-400' },
  { label: 'Pay', href: '/purchasing/payments/new', icon: CreditCard, color: 'emerald-400' },
  { label: 'Aging', href: '/purchasing/aging', icon: Calendar, color: 'rose-400' },
];

const workflowPhases: WorkflowPhase[] = [
  { key: 'order', label: 'Order', description: 'Create POs' },
  { key: 'receive', label: 'Receive', description: 'Process bills' },
  { key: 'pay', label: 'Pay', description: 'Make payments' },
];

const workflowSteps: WorkflowStep[] = [
  { label: 'Create purchase order', color: 'violet' },
  { label: 'Receive & bill', color: 'amber' },
  { label: 'Approve payment', color: 'teal' },
  { label: 'Settle AP', color: 'emerald' },
];

function getWorkflowPhase(sectionKey: string | null): string {
  if (!sectionKey) return 'order';
  if (sectionKey === 'orders') return 'order';
  if (sectionKey === 'payables') return 'receive';
  return 'pay';
}

export default function PurchasingLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuleLayout
      moduleName="Dotmac"
      moduleSubtitle="Purchasing"
      sidebarTitle="Accounts Payable"
      sidebarDescription="Vendor management & procurement"
      baseRoute="/purchasing"
      accentColor="violet"
      icon={ShoppingCart}
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
