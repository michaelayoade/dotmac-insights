'use client';

import { useAccountingBankAccounts } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { AlertTriangle, Landmark, Building2, CreditCard, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { formatAccountingCurrency } from '@/lib/formatters/accounting';

interface BankAccountCardProps {
  account: any;
}

function BankAccountCard({ account }: BankAccountCardProps) {
  const isActive = account.status === 'active' || account.is_active !== false;

  return (
    <div className={cn(
      'bg-slate-card border rounded-xl p-6 hover:border-teal-electric/50 transition-colors',
      isActive ? 'border-slate-border' : 'border-slate-border/50 opacity-75'
    )}>
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-teal-electric/20 rounded-lg">
            <Landmark className="w-6 h-6 text-teal-electric" />
          </div>
          <div>
            <h3 className="text-foreground font-semibold">{account.account_name || account.name}</h3>
            <p className="text-slate-muted text-sm">{account.bank_name}</p>
          </div>
        </div>
        <span className={cn(
          'px-2 py-1 rounded-full text-xs font-medium border flex items-center gap-1',
          isActive
            ? 'bg-green-500/20 text-green-400 border-green-500/30'
            : 'bg-slate-500/20 text-slate-400 border-slate-500/30'
        )}>
          {isActive ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
          {isActive ? 'Active' : 'Inactive'}
        </span>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-slate-muted text-sm">Account Number</span>
          <span className="font-mono text-foreground">
            {account.account_number ? `****${String(account.account_number).slice(-4)}` : '-'}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-muted text-sm">Account Type</span>
          <span className="text-foreground capitalize">{account.account_type || 'Checking'}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-muted text-sm">Currency</span>
          <span className="text-foreground">{account.currency || 'NGN'}</span>
        </div>

        <div className="pt-3 mt-3 border-t border-slate-border">
          <div className="flex items-center justify-between">
            <span className="text-slate-muted text-sm">Current Balance</span>
            <span className={cn(
              'font-mono font-bold text-lg',
              (account.balance || account.current_balance || 0) >= 0 ? 'text-green-400' : 'text-red-400'
            )}>
              {formatAccountingCurrency(account.balance || account.current_balance, account.currency)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function BankAccountsPage() {
  const { data, isLoading, error } = useAccountingBankAccounts();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-teal-electric" />
      </div>
    );
  }

  const accounts = (data as any)?.accounts || (data as any)?.data || [];
  const totalBalance = accounts.reduce((sum: number, acc: any) => sum + (acc.balance || acc.current_balance || 0), 0);
  const activeCount = accounts.filter((acc: any) => acc.status === 'active' || acc.is_active !== false).length;

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load bank accounts</p>
        </div>
      )}
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <Building2 className="w-5 h-5 text-slate-muted" />
            <p className="text-slate-muted text-sm">Total Accounts</p>
          </div>
          <p className="text-3xl font-bold text-foreground">{accounts.length}</p>
          <p className="text-slate-muted text-sm mt-1">{activeCount} active</p>
        </div>
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <CreditCard className="w-5 h-5 text-green-400" />
            <p className="text-green-400 text-sm">Total Balance</p>
          </div>
          <p className="text-3xl font-bold text-green-400">{formatAccountingCurrency(totalBalance)}</p>
          <p className="text-green-400/70 text-sm mt-1">Across all accounts</p>
        </div>
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <Landmark className="w-5 h-5 text-blue-400" />
            <p className="text-blue-400 text-sm">Banks</p>
          </div>
          <p className="text-3xl font-bold text-blue-400">
            {new Set(accounts.map((acc: any) => acc.bank_name)).size}
          </p>
          <p className="text-blue-400/70 text-sm mt-1">Different banks</p>
        </div>
      </div>

      {/* Bank Account Cards */}
      {accounts.length === 0 ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-12 text-center">
          <Landmark className="w-12 h-12 text-slate-muted mx-auto mb-4" />
          <p className="text-slate-muted">No bank accounts found</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {accounts.map((account: any) => (
            <BankAccountCard key={account.id} account={account} />
          ))}
        </div>
      )}
    </div>
  );
}
