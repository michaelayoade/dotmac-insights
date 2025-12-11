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
  Building,
  Calendar,
  Landmark,
} from 'lucide-react';

const tabs = [
  { name: 'Dashboard', href: '/accounting', icon: LayoutDashboard },
  { name: 'Chart of Accounts', href: '/accounting/chart-of-accounts', icon: BookOpen },
  { name: 'Trial Balance', href: '/accounting/trial-balance', icon: Scale },
  { name: 'Balance Sheet', href: '/accounting/balance-sheet', icon: FileSpreadsheet },
  { name: 'Income Statement', href: '/accounting/income-statement', icon: TrendingUp },
  { name: 'General Ledger', href: '/accounting/general-ledger', icon: BookMarked },
  { name: 'Journal Entries', href: '/accounting/journal-entries', icon: ClipboardList },
  { name: 'Accounts Payable', href: '/accounting/accounts-payable', icon: ArrowDownToLine },
  { name: 'Accounts Receivable', href: '/accounting/accounts-receivable', icon: Users },
  { name: 'Suppliers', href: '/accounting/suppliers', icon: Building },
  { name: 'Bank Accounts', href: '/accounting/bank-accounts', icon: Landmark },
];

export default function AccountingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Accounting</h1>
        <p className="text-slate-muted text-sm mt-1">
          Financial reports, journal entries, and accounting data
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-slate-border overflow-x-auto">
        <nav className="-mb-px flex space-x-1 min-w-max">
          {tabs.map((tab) => {
            const isActive =
              tab.href === '/accounting'
                ? pathname === '/accounting'
                : pathname.startsWith(tab.href);
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

      {/* Page Content */}
      {children}
    </div>
  );
}
