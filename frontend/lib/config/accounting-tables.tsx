'use client';

import { cn } from '@/lib/utils';
import {
  formatAccountingCurrency,
  formatAccountingCurrencyOrDash,
  formatAccountingDate,
} from '@/lib/formatters/accounting';
import {
  ArrowDownRight,
  ArrowUpRight,
  BookOpen,
  Building,
  CheckCircle2,
  ChevronRight,
  Folder,
  FolderOpen,
  Mail,
  Phone,
  XCircle,
} from 'lucide-react';
import type { AccountingGeneralLedgerEntry } from '@/lib/api';

const getAccountTypeColor = (type: string) => {
  const colors: Record<string, string> = {
    asset: 'text-blue-400',
    liability: 'text-red-400',
    equity: 'text-green-400',
    income: 'text-teal-400',
    revenue: 'text-teal-400',
    expense: 'text-orange-400',
  };
  return colors[type?.toLowerCase()] || 'text-slate-muted';
};

const getAccountTypeBadgeColor = (type: string) => {
  const colors: Record<string, string> = {
    asset: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    liability: 'bg-red-500/20 text-red-400 border-red-500/30',
    equity: 'bg-green-500/20 text-green-400 border-green-500/30',
    income: 'bg-teal-500/20 text-teal-400 border-teal-500/30',
    revenue: 'bg-teal-500/20 text-teal-400 border-teal-500/30',
    expense: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  };
  return colors[type?.toLowerCase()] || 'bg-slate-500/20 text-slate-400 border-slate-500/30';
};

export const getTrialBalanceColumns = () => ([
  {
    key: 'account_number',
    header: 'Account #',
    sortable: true,
    render: (item: any) => (
      <span className="font-mono text-teal-electric">{item.account_number}</span>
    ),
  },
  {
    key: 'account_name',
    header: 'Account Name',
    sortable: true,
    render: (item: any) => (
      <span className="text-foreground">{item.account_name}</span>
    ),
  },
  {
    key: 'account_type',
    header: 'Type',
    render: (item: any) => (
      <span className={cn('capitalize', getAccountTypeColor(item.account_type))}>
        {item.account_type || '-'}
      </span>
    ),
  },
  {
    key: 'debit',
    header: 'Debit',
    align: 'right' as const,
    render: (item: any) => (
      <span className={cn('font-mono', item.debit > 0 ? 'text-blue-400' : 'text-slate-muted')}>
        {item.debit > 0 ? formatAccountingCurrency(item.debit) : '-'}
      </span>
    ),
  },
  {
    key: 'credit',
    header: 'Credit',
    align: 'right' as const,
    render: (item: any) => (
      <span className={cn('font-mono', item.credit > 0 ? 'text-green-400' : 'text-slate-muted')}>
        {item.credit > 0 ? formatAccountingCurrency(item.credit) : '-'}
      </span>
    ),
  },
  {
    key: 'balance',
    header: 'Balance',
    align: 'right' as const,
    render: (item: any) => (
      <span
        className={cn(
          'font-mono font-semibold',
          (item.balance || 0) >= 0 ? 'text-foreground' : 'text-red-400'
        )}
      >
        {formatAccountingCurrency(item.balance ?? 0)}
      </span>
    ),
  },
]);

export const getSuppliersColumns = () => ([
  {
    key: 'name',
    header: 'Supplier Name',
    sortable: true,
    render: (item: any) => (
      <div className="flex items-center gap-2">
        <Building className="w-4 h-4 text-teal-electric" />
        <span className="text-foreground font-medium">{item.name || item.supplier_name}</span>
      </div>
    ),
  },
  {
    key: 'code',
    header: 'Code',
    render: (item: any) => (
      <span className="font-mono text-slate-muted">{item.code || item.supplier_code || '-'}</span>
    ),
  },
  {
    key: 'contact',
    header: 'Contact',
    render: (item: any) => (
      <div className="space-y-1">
        {item.email && (
          <div className="flex items-center gap-1 text-sm">
            <Mail className="w-3 h-3 text-slate-muted" />
            <span className="text-foreground-secondary">{item.email}</span>
          </div>
        )}
        {item.phone && (
          <div className="flex items-center gap-1 text-sm">
            <Phone className="w-3 h-3 text-slate-muted" />
            <span className="text-foreground-secondary">{item.phone}</span>
          </div>
        )}
        {!item.email && !item.phone && <span className="text-slate-muted">-</span>}
      </div>
    ),
  },
  {
    key: 'balance',
    header: 'Outstanding',
    align: 'right' as const,
    render: (item: any) => (
      <span
        className={cn(
          'font-mono',
          (item.balance || item.outstanding_balance || 0) > 0 ? 'text-orange-400' : 'text-green-400'
        )}
      >
        {formatAccountingCurrency(item.balance ?? item.outstanding_balance ?? 0)}
      </span>
    ),
  },
  {
    key: 'total_purchases',
    header: 'Total Purchases',
    align: 'right' as const,
    render: (item: any) => (
      <span className="font-mono text-foreground">
        {formatAccountingCurrency(item.total_purchases ?? item.total_invoices ?? 0)}
      </span>
    ),
  },
  {
    key: 'status',
    header: 'Status',
    render: (item: any) => {
      const isActive = item.status === 'active' || item.is_active !== false;
      return (
        <span
          className={cn(
            'px-2 py-1 rounded-full text-xs font-medium border flex items-center gap-1 w-fit',
            isActive
              ? 'bg-green-500/20 text-green-400 border-green-500/30'
              : 'bg-slate-500/20 text-slate-400 border-slate-500/30'
          )}
        >
          {isActive ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
          {isActive ? 'Active' : 'Inactive'}
        </span>
      );
    },
  },
]);

export const getChartOfAccountsColumns = () => ([
  {
    key: 'account_number',
    header: 'Account #',
    sortable: true,
    render: (item: any) => (
      <div className="flex items-center gap-2">
        <BookOpen className="w-4 h-4 text-teal-electric" />
        <span className="font-mono text-teal-electric">{item.account_number || '-'}</span>
      </div>
    ),
  },
  {
    key: 'account_name',
    header: 'Account Name',
    sortable: true,
    render: (item: any) => (
      <div className="flex items-center gap-2">
        {item.is_group ? (
          <FolderOpen className="w-4 h-4 text-yellow-400" />
        ) : item.parent_account ? (
          <ChevronRight className="w-4 h-4 text-slate-muted ml-4" />
        ) : (
          <Folder className="w-4 h-4 text-slate-muted" />
        )}
        <span className={cn('text-foreground', item.is_group && 'font-semibold')}>
          {item.name || item.account_name}
        </span>
      </div>
    ),
  },
  {
    key: 'account_type',
    header: 'Type',
    render: (item: any) => (
      <span
        className={cn(
          'px-2 py-1 rounded-full text-xs font-medium border capitalize',
          getAccountTypeBadgeColor(item.root_type || item.account_type)
        )}
      >
        {item.root_type || item.account_type || '-'}
      </span>
    ),
  },
  {
    key: 'balance',
    header: 'Balance',
    align: 'right' as const,
    render: (item: any) => (
      <span
        className={cn(
          'font-mono',
          (item.balance || 0) >= 0 ? 'text-green-400' : 'text-red-400'
        )}
      >
        {formatAccountingCurrency(item.balance ?? 0)}
      </span>
    ),
  },
  {
    key: 'description',
    header: 'Description',
    render: (item: any) => (
      <span className="text-slate-muted text-sm truncate max-w-[200px] block">
        {item.description || '-'}
      </span>
    ),
  },
  {
    key: 'is_active',
    header: 'Status',
    render: (item: any) => (
      <span
        className={cn(
          'px-2 py-1 rounded-full text-xs font-medium border',
          !item.disabled
            ? 'bg-green-500/20 text-green-400 border-green-500/30'
            : 'bg-slate-500/20 text-slate-400 border-slate-500/30'
        )}
      >
        {!item.disabled ? 'Active' : 'Inactive'}
      </span>
    ),
  },
]);

export const getGeneralLedgerColumns = () => ([
  {
    key: 'date',
    header: 'Date',
    sortable: true,
    render: (item: AccountingGeneralLedgerEntry) => (
      <span className="text-slate-muted">{formatAccountingDate(item.posting_date)}</span>
    ),
  },
  {
    key: 'account',
    header: 'Account',
    render: (item: AccountingGeneralLedgerEntry) => (
      <div>
        <span className="font-mono text-teal-electric text-sm">{item.account}</span>
        <span className="text-foreground ml-2">{item.account_name || ''}</span>
      </div>
    ),
  },
  {
    key: 'description',
    header: 'Description',
    render: (item: AccountingGeneralLedgerEntry) => (
      <span className="text-foreground-secondary text-sm truncate max-w-[250px] block">
        {item.remarks || item.voucher_no || item.party || '-'}
      </span>
    ),
  },
  {
    key: 'debit',
    header: 'Debit',
    align: 'right' as const,
    render: (item: AccountingGeneralLedgerEntry) => (
      <div className="flex items-center justify-end gap-1">
        {(item.debit || 0) > 0 && <ArrowUpRight className="w-3 h-3 text-blue-400" />}
        <span className={cn('font-mono', (item.debit || 0) > 0 ? 'text-blue-400' : 'text-slate-muted')}>
          {(item.debit || 0) > 0 ? formatAccountingCurrency(item.debit || 0) : '-'}
        </span>
      </div>
    ),
  },
  {
    key: 'credit',
    header: 'Credit',
    align: 'right' as const,
    render: (item: AccountingGeneralLedgerEntry) => (
      <div className="flex items-center justify-end gap-1">
        {(item.credit || 0) > 0 && <ArrowDownRight className="w-3 h-3 text-green-400" />}
        <span className={cn('font-mono', (item.credit || 0) > 0 ? 'text-green-400' : 'text-slate-muted')}>
          {(item.credit || 0) > 0 ? formatAccountingCurrency(item.credit || 0) : '-'}
        </span>
      </div>
    ),
  },
  {
    key: 'balance',
    header: 'Running Balance',
    align: 'right' as const,
    render: (item: AccountingGeneralLedgerEntry) => (
      <span
        className={cn(
          'font-mono font-semibold',
          (item.balance || 0) >= 0 ? 'text-foreground' : 'text-red-400'
        )}
      >
        {formatAccountingCurrencyOrDash(item.balance)}
      </span>
    ),
  },
  {
    key: 'reference',
    header: 'Reference',
    render: (item: AccountingGeneralLedgerEntry) => (
      <div className="text-slate-muted text-xs font-mono space-y-0.5">
        <div>{item.voucher_no || '-'}</div>
        {item.voucher_type && <div className="uppercase tracking-wide">{item.voucher_type}</div>}
      </div>
    ),
  },
]);
