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
} from 'lucide-react';

const tabs = [
  { name: 'Dashboard', href: '/books', icon: LayoutDashboard },
  { name: 'Chart of Accounts', href: '/books/chart-of-accounts', icon: BookOpen },
  { name: 'Trial Balance', href: '/books/trial-balance', icon: Scale },
  { name: 'Balance Sheet', href: '/books/balance-sheet', icon: FileSpreadsheet },
  { name: 'Income Statement', href: '/books/income-statement', icon: TrendingUp },
  { name: 'General Ledger', href: '/books/general-ledger', icon: BookMarked },
  { name: 'Journal Entries', href: '/books/journal-entries', icon: ClipboardList },
  { name: 'Accounts Payable', href: '/books/accounts-payable', icon: ArrowDownToLine },
  { name: 'Accounts Receivable', href: '/books/accounts-receivable', icon: Users },
  { name: 'AR Invoices', href: '/books/ar/invoices', icon: FileSpreadsheet },
  { name: 'AR Payments', href: '/books/ar/payments', icon: CreditCard },
  { name: 'AR Credit Notes', href: '/books/ar/credit-notes', icon: BookOpen },
  { name: 'AP Bills', href: '/books/ap/bills', icon: FileSpreadsheet },
  { name: 'AP Payments', href: '/books/ap/payments', icon: CreditCard },
  { name: 'AP Debit Notes', href: '/books/ap/debit-notes', icon: BookOpen },
  { name: 'Taxes', href: '/books/taxes', icon: Landmark },
  { name: 'Bank Transactions', href: '/books/bank-transactions', icon: CreditCard },
  { name: 'Bank Accounts', href: '/books/bank-accounts', icon: CreditCard },
  { name: 'Controls', href: '/books/controls', icon: ClipboardList },
];

export default function BooksLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Books</h1>
        <p className="text-slate-muted text-sm mt-1">
          Accounting, banking, and financial reporting in one place
        </p>
      </div>

      <div className="border-b border-slate-border overflow-x-auto">
        <nav className="-mb-px flex space-x-1 min-w-max">
          {tabs.map((tab) => {
            const isActive = tab.href === '/books' ? pathname === '/books' : pathname.startsWith(tab.href);
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
