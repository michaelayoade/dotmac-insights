'use client';

import { useState } from 'react';
import { useAccountingDunningQueue, useCustomerCreditMutations } from '@/hooks/useApi';
import { DataTable } from '@/components/DataTable';
import { AlertTriangle, Bell, Mail, Loader2 } from 'lucide-react';
import { formatCurrency } from '@/lib/utils';

export default function DunningQueuePage() {
  const { data, isLoading, error, mutate } = useAccountingDunningQueue();
  const { sendDunning } = useCustomerCreditMutations();
  const [sending, setSending] = useState(false);

  const rows = data?.queue || data || [];

  const columns = [
    { key: 'invoice_number', header: 'Invoice', render: (item: any) => item.invoice_number || `#${item.invoice_id}` },
    { key: 'customer_name', header: 'Customer' },
    { key: 'due_date', header: 'Due Date' },
    { key: 'days_overdue', header: 'Days Overdue' },
    {
      key: 'balance',
      header: 'Balance',
      align: 'right' as const,
      render: (item: any) => <span className="font-mono text-foreground">{formatCurrency(item.balance, item.currency || 'NGN')}</span>,
    },
    { key: 'last_dunning_stage', header: 'Last Stage' },
  ];

  const triggerSend = async () => {
    setSending(true);
    await sendDunning({});
    await mutate();
    setSending(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Dunning Queue</h1>
          <p className="text-slate-muted text-sm">Invoices ready for follow-up notices.</p>
        </div>
        <button
          onClick={triggerSend}
          disabled={sending}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90 disabled:opacity-60"
        >
          {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
          Send notices
        </button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>Failed to load dunning queue.</span>
        </div>
      )}

      <DataTable
        columns={columns}
        data={rows}
        keyField="invoice_id"
        loading={isLoading}
        emptyMessage="No invoices awaiting dunning."
      />
    </div>
  );
}
