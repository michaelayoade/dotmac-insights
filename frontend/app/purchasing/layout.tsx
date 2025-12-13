'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  FileText,
  CreditCard,
  ShoppingCart,
  FileX,
  Users,
  Receipt,
  Calendar,
  TrendingUp,
} from 'lucide-react';

const tabs = [
  { name: 'Dashboard', href: '/purchasing', icon: LayoutDashboard },
  { name: 'Bills', href: '/purchasing/bills', icon: FileText },
  { name: 'Payments', href: '/purchasing/payments', icon: CreditCard },
  { name: 'Purchase Orders', href: '/purchasing/orders', icon: ShoppingCart },
  { name: 'Debit Notes', href: '/purchasing/debit-notes', icon: FileX },
  { name: 'Suppliers', href: '/purchasing/suppliers', icon: Users },
  { name: 'Expenses', href: '/purchasing/expenses', icon: Receipt },
  { name: 'AP Aging', href: '/purchasing/aging', icon: Calendar },
  { name: 'Analytics', href: '/purchasing/analytics', icon: TrendingUp },
];

export default function PurchasingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Purchasing</h1>
        <p className="text-slate-muted text-sm mt-1">
          Vendor management, bills, expenses, and accounts payable
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-slate-border overflow-x-auto">
        <nav className="-mb-px flex space-x-1 min-w-max">
          {tabs.map((tab) => {
            const isActive =
              tab.href === '/purchasing'
                ? pathname === '/purchasing'
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
