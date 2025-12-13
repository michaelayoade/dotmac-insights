'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
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
  Lock,
  Bell,
  ShieldCheck,
  Settings,
} from 'lucide-react';

const tabGroups = [
  {
    label: 'Accounting',
    items: [
      { name: 'Dashboard', href: '/books', icon: LayoutDashboard },
      { name: 'General Ledger', href: '/books/general-ledger', icon: BookMarked },
      { name: 'Trial Balance', href: '/books/trial-balance', icon: Scale },
      { name: 'Income Statement', href: '/books/income-statement', icon: TrendingUp },
      { name: 'Balance Sheet', href: '/books/balance-sheet', icon: ShieldCheck },
      { name: 'Journal Entries', href: '/books/journal-entries', icon: ClipboardList },
      { name: 'Chart of Accounts', href: '/books/chart-of-accounts', icon: BookOpen },
      { name: 'Taxes', href: '/books/taxes', icon: Landmark },
    ],
  },
  {
    label: 'Accounts Receivable',
    items: [
      { name: 'AR Overview', href: '/books/accounts-receivable', icon: Users },
      { name: 'Invoices', href: '/books/ar/invoices', icon: FileSpreadsheet },
      { name: 'Payments', href: '/books/ar/payments', icon: CreditCard },
      { name: 'Credit Notes', href: '/books/ar/credit-notes', icon: BookOpen },
      { name: 'Credit Management', href: '/books/accounts-receivable/credit', icon: Lock },
      { name: 'Dunning', href: '/books/accounts-receivable/dunning', icon: Bell },
    ],
  },
  {
    label: 'Accounts Payable',
    items: [
      { name: 'AP Overview', href: '/books/accounts-payable', icon: ArrowDownToLine },
      { name: 'Bills', href: '/books/ap/bills', icon: FileSpreadsheet },
      { name: 'Payments', href: '/books/ap/payments', icon: CreditCard },
      { name: 'Debit Notes', href: '/books/ap/debit-notes', icon: BookOpen },
      { name: 'Suppliers', href: '/books/suppliers', icon: Users },
    ],
  },
  {
    label: 'Banking',
    items: [
      { name: 'Bank Accounts', href: '/books/bank-accounts', icon: CreditCard },
      { name: 'Transactions', href: '/books/bank-transactions', icon: CreditCard },
    ],
  },
  {
    label: 'Configuration',
    items: [
      { name: 'Settings', href: '/books/settings', icon: Settings },
      { name: 'Controls', href: '/books/controls', icon: Lock },
    ],
  },
  {
    label: 'Docs & Help',
    items: [
      { name: 'Docs & Exports', href: '/books/docs', icon: BookOpen },
    ],
  },
];

export default function BooksLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isActiveHref = (href: string) => (href === '/books' ? pathname === '/books' : pathname.startsWith(href));

  const activeGroup = tabGroups.find((group) => group.items.some((item) => isActiveHref(item.href))) ?? tabGroups[0];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Books</h1>
        <p className="text-slate-muted text-sm mt-1">
          Accounting, banking, and financial reporting in one place
        </p>
      </div>

      <div className="border-b border-slate-border overflow-x-auto">
        <div className="flex items-center gap-3 mb-2 text-slate-muted text-xs px-1">
          <span>{activeGroup.label}</span>
        </div>
        <nav className="-mb-px flex space-x-1 min-w-max">
          {activeGroup.items.map((tab) => {
            const isActive = isActiveHref(tab.href);
            const Icon = tab.icon;
            return (
              <Link
                key={tab.name}
                href={tab.href}
                className={cn(
                  'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap',
                  isActive
                    ? 'border-teal-electric text-teal-electric'
                    : 'border-transparent text-slate-muted hover:text-white hover:border-slate-border'
                )}
              >
                <Icon className="w-4 h-4" />
                {tab.name}
              </Link>
            );
          })}
        </nav>
      </div>

      {children}
    </div>
  );
}
