'use client';

import { Landmark, CreditCard } from 'lucide-react';
import { ModuleLayout, NavSection } from '@/components/ModuleLayout';

const sections: NavSection[] = [
  {
    key: 'banking',
    label: 'Banking',
    description: 'Accounts and transactions',
    icon: Landmark,
    items: [
      { name: 'Bank Transactions', href: '/banking/bank-transactions', description: 'Ledger activity' },
      { name: 'Bank Accounts', href: '/banking/bank-accounts', description: 'Account balances' },
    ],
  },
];

export default function BankingLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuleLayout
      moduleName="Dotmac"
      moduleSubtitle="Banking"
      sidebarTitle="Banking"
      sidebarDescription="Transactions and balances"
      baseRoute="/banking"
      accentColor="blue"
      icon={CreditCard}
      sections={sections}
    >
      {children}
    </ModuleLayout>
  );
}
