'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { Landmark, CreditCard } from 'lucide-react';

const tabs = [
  { name: 'Bank Transactions', href: '/banking/bank-transactions', icon: Landmark },
  { name: 'Bank Accounts', href: '/banking/bank-accounts', icon: CreditCard },
];

export default function BankingLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Banking</h1>
        <p className="text-slate-muted text-sm mt-1">
          Bank transactions, reconciliations, and balances.
        </p>
      </div>

      <div className="border-b border-slate-border overflow-x-auto">
        <nav className="-mb-px flex space-x-1 min-w-max">
          {tabs.map((tab) => {
            const isActive = pathname.startsWith(tab.href);
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
