'use client';

import {
  LayoutDashboard,
  Package,
  Warehouse,
  ClipboardList,
  ArrowLeftRight,
  FileBarChart,
  History,
  AlertTriangle,
  Settings,
  Boxes,
  Receipt,
  Layers,
  Hash,
  Tag,
} from 'lucide-react';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import { ModuleLayout, QuickLink, WorkflowPhase, WorkflowStep } from '@/components/ModuleLayout';
import type { NavSection } from '@/components/ModuleLayout/types';

// Inventory Management Flow:
// 1. RECEIVE: Purchase receipts, stock entries
// 2. STORE: Warehouse management, tracking
// 3. ISSUE: Sales issues, transfers
// 4. REPORT: Valuation, analysis

const sections: NavSection[] = [
  {
    key: 'overview',
    label: 'Dashboard',
    description: 'Stock overview',
    icon: LayoutDashboard,
    items: [
      { name: 'Dashboard', href: '/inventory', description: 'Stock overview' },
    ],
  },
  {
    key: 'stock',
    label: 'Stock',
    description: 'Items & warehouses',
    icon: Package,
    items: [
      { name: 'Items', href: '/inventory/items', description: 'Item master with stock' },
      { name: 'Warehouses', href: '/inventory/warehouses', description: 'Storage locations' },
      { name: 'Stock Ledger', href: '/inventory/stock-ledger', description: 'Movement history' },
    ],
  },
  {
    key: 'transactions',
    label: 'Transactions',
    description: 'Stock movements',
    icon: ArrowLeftRight,
    items: [
      { name: 'Stock Entries', href: '/inventory/stock-entries', description: 'In/out transactions' },
      { name: 'Transfers', href: '/inventory/transfers', description: 'Warehouse transfers' },
      { name: 'Purchase Receipts', href: '/inventory/purchase-receipts', description: 'From bills' },
      { name: 'Sales Issues', href: '/inventory/sales-issues', description: 'From invoices' },
    ],
  },
  {
    key: 'tracking',
    label: 'Tracking',
    description: 'Batches & serials',
    icon: Layers,
    items: [
      { name: 'Batches', href: '/inventory/batches', description: 'Batch tracking' },
      { name: 'Serial Numbers', href: '/inventory/serials', description: 'Serial tracking' },
    ],
  },
  {
    key: 'reports',
    label: 'Reports',
    description: 'Valuation & analysis',
    icon: FileBarChart,
    items: [
      { name: 'Valuation', href: '/inventory/valuation', description: 'FIFO/Avg reports' },
      { name: 'Stock Summary', href: '/inventory/summary', description: 'Aggregated view' },
      { name: 'Reorder Alerts', href: '/inventory/reorder', description: 'Low stock items' },
    ],
  },
  {
    key: 'costing',
    label: 'Costing',
    description: 'Landed cost allocation',
    icon: Receipt,
    items: [
      { name: 'Landed Cost', href: '/inventory/landed-cost-vouchers', description: 'Cost allocation' },
    ],
  },
  {
    key: 'config',
    label: 'Configuration',
    description: 'Settings & preferences',
    icon: Settings,
    items: [
      { name: 'Settings', href: '/inventory/settings', description: 'Preferences' },
    ],
  },
];

const quickLinks: QuickLink[] = [
  { label: 'Items', href: '/inventory/items', icon: Package, color: 'orange-400' },
  { label: 'Stock Entry', href: '/inventory/stock-entries', icon: ClipboardList, color: 'amber-400' },
  { label: 'Valuation', href: '/inventory/valuation', icon: FileBarChart, color: 'emerald-400' },
  { label: 'Reorder', href: '/inventory/reorder', icon: AlertTriangle, color: 'rose-400' },
];

const workflowPhases: WorkflowPhase[] = [
  { key: 'receive', label: 'Receive', description: 'Inbound stock' },
  { key: 'store', label: 'Store', description: 'Warehouse mgmt' },
  { key: 'issue', label: 'Issue', description: 'Outbound stock' },
];

const workflowSteps: WorkflowStep[] = [
  { label: 'Receive goods', color: 'emerald' },
  { label: 'Store & track', color: 'orange' },
  { label: 'Issue & transfer', color: 'amber' },
  { label: 'Value & report', color: 'cyan' },
];

function getWorkflowPhase(sectionKey: string | null): string {
  if (!sectionKey) return 'receive';
  if (sectionKey === 'stock' || sectionKey === 'tracking') return 'store';
  if (sectionKey === 'transactions') return 'issue';
  return 'receive';
}

export default function InventoryLayout({ children }: { children: React.ReactNode }) {
  const { hasAccess, isLoading: authLoading } = useRequireScope('inventory:read');

  if (authLoading) {
    return (
      <div className="min-h-screen bg-slate-deep flex justify-center items-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-400" />
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
      moduleSubtitle="Inventory"
      sidebarTitle="Stock Management"
      sidebarDescription="Items, warehouses, and movements"
      baseRoute="/inventory"
      accentColor="orange"
      icon={Boxes}
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
