'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useGatewayTransfers, useGatewayMutations, useBanks } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { AlertTriangle, Banknote, RefreshCw, Plus, Eye, Send } from 'lucide-react';

import { paymentsApi } from '@/lib/api';
import { useErrorHandler } from '@/hooks/useErrorHandler';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import { Button, StatusPill } from '@/components/ui';
import { formatAccountingCurrency, formatAccountingDate } from '@/lib/formatters/accounting';

function getStatusBadge(status: string) {
  const tones: Record<string, StatusTone> = {
    success: 'success',
    pending: 'warning',
    processing: 'info',
    failed: 'danger',
    reversed: 'info',
  };
  return (
    <StatusPill
      label={formatStatusLabel(status)}
      tone={tones[status] || 'default'}
      className="border border-current/30"
    />
  );
}

function getProviderBadge(provider: string) {
  const styles: Record<string, string> = {
    paystack: 'bg-blue-500/20 text-blue-400',
    flutterwave: 'bg-orange-500/20 text-orange-400',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${styles[provider] || 'bg-slate-500/20 text-slate-400'}`}>
      {provider}
    </span>
  );
}

export default function GatewayTransfersPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [status, setStatus] = useState('');
  const [provider, setProvider] = useState('');
  const [selection, setSelection] = useState<Record<string, boolean>>({});
  const [bulkStatus, setBulkStatus] = useState<{ state: 'idle' | 'running' | 'error' | 'success'; message?: string }>({
    state: 'idle',
  });
  const [showNewModal, setShowNewModal] = useState(false);
  const [selectedTransfer, setSelectedTransfer] = useState<any>(null);

  const { data, isLoading, error, mutate } = useGatewayTransfers({
    status: status || undefined,
    limit: pageSize,
    offset: (page - 1) * pageSize,
  });

  const { initiateTransfer, verifyTransfer, payPayrollTransfers } = useGatewayMutations();
  const { handleError, handleSuccess } = useErrorHandler();

  const handleVerify = async (reference: string) => {
    try {
      await verifyTransfer(reference);
      mutate();
      handleSuccess('Transfer verified successfully');
    } catch (err: any) {
      handleError(err, 'Verification failed');
    }
  };

  const handlePayPayroll = async () => {
    const ids = (data?.items || [])
      .filter((item: any) => selection[item.reference])
      .filter((item: any) => item.transfer_type === 'payroll' && item.status === 'pending')
      .map((item: any) => item.id)
      .filter(Boolean);

    if (!ids.length) {
      setBulkStatus({ state: 'error', message: 'Select pending payroll transfers first.' });
      return;
    }

    try {
      setBulkStatus({ state: 'running' });
      await payPayrollTransfers({ transfer_ids: ids });
      setBulkStatus({ state: 'success', message: `Triggered payout for ${ids.length} payroll transfers.` });
      setSelection({});
      mutate();
    } catch (err: any) {
      setBulkStatus({ state: 'error', message: err?.message || 'Bulk payout failed' });
    }
  };

  const columns = [
    {
      key: 'reference',
      header: 'Reference',
      render: (item: any) => (
        <div>
          <span className="font-mono text-teal-electric text-sm">{item.reference}</span>
          {item.provider_reference && (
            <div className="text-xs text-slate-muted mt-0.5">{item.provider_reference}</div>
          )}
        </div>
      ),
    },
    {
      key: 'provider',
      header: 'Provider',
      render: (item: any) => getProviderBadge(item.provider),
    },
    {
      key: 'recipient',
      header: 'Recipient',
      render: (item: any) => (
        <div>
          <div className="text-foreground text-sm">{item.recipient_name || '-'}</div>
          <div className="text-xs text-slate-muted font-mono">
            {item.recipient_account} @ {item.recipient_bank_code}
          </div>
        </div>
      ),
    },
    {
      key: 'amount',
      header: 'Amount',
      align: 'right' as const,
      render: (item: any) => (
        <div className="text-right">
          <span className="font-mono text-foreground">{formatAccountingCurrency(item.amount, item.currency)}</span>
          {item.fees > 0 && (
            <div className="text-xs text-slate-muted">Fee: {formatAccountingCurrency(item.fees, item.currency)}</div>
          )}
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => getStatusBadge(item.status),
    },
    {
      key: 'narration',
      header: 'Narration',
      render: (item: any) => <span className="text-slate-muted text-sm truncate max-w-[180px] block">{item.narration || '-'}</span>,
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (item: any) => <span className="text-slate-muted text-sm">{formatAccountingDate(item.created_at)}</span>,
    },
    {
      key: 'actions',
      header: '',
      render: (item: any) => (
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          {(item.status === 'pending' || item.status === 'processing') && (
            <Button
              onClick={() => handleVerify(item.reference)}
              className="p-1.5 rounded hover:bg-slate-700 text-slate-muted hover:text-teal-electric transition-colors"
              title="Verify transfer"
            >
              <RefreshCw className="w-4 h-4" />
            </Button>
          )}
          <Button
            onClick={() => router.push(`/books/gateway/transfers/${item.reference}`)}
            className="p-1.5 rounded hover:bg-slate-700 text-slate-muted hover:text-foreground transition-colors"
            title="View details"
          >
            <Eye className="w-4 h-4" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load transfers</p>
        </div>
      )}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Banknote className="w-5 h-5 text-teal-electric" />
          <h1 className="text-xl font-semibold text-foreground">Bank Transfers</h1>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={() => mutate()} variant="secondary" icon={RefreshCw}>
            Refresh
          </Button>
          <Button onClick={() => setShowNewModal(true)} module="books" icon={Plus}>
            New Transfer
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-4 items-center">
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          className="input-field"
        >
          <option value="">All Status</option>
          <option value="success">Success</option>
          <option value="pending">Pending</option>
          <option value="processing">Processing</option>
          <option value="failed">Failed</option>
          <option value="reversed">Reversed</option>
        </select>
        <select
          value={provider}
          onChange={(e) => { setProvider(e.target.value); setPage(1); }}
          className="input-field"
        >
          <option value="">All Providers</option>
          <option value="paystack">Paystack</option>
          <option value="flutterwave">Flutterwave</option>
        </select>
      </div>

      <DataTable
        columns={columns}
        data={data?.items || []}
        keyField="reference"
        loading={isLoading}
        emptyMessage="No transfers found"
        selectable
        selectedRowIds={selection}
        onSelectChange={(selected) => setSelection(selected)}
        onRowClick={(item) => router.push(`/books/gateway/transfers/${(item as any).reference}`)}
      />

    {data && data.items && data.items.length >= pageSize && (
      <Pagination
        total={(page * pageSize) + (data.items.length === pageSize ? 1 : 0)}
        limit={pageSize}
        offset={(page - 1) * pageSize}
        onPageChange={(newOffset) => setPage(Math.floor(newOffset / pageSize) + 1)}
        onLimitChange={(newLimit) => { setPageSize(newLimit); setPage(1); }}
      />
    )}

    <div className="mt-4 flex items-center justify-between">
      <div className="text-sm">
        {bulkStatus.state === 'error' && <span className="text-red-400">{bulkStatus.message}</span>}
        {bulkStatus.state === 'success' && <span className="text-emerald-400">{bulkStatus.message}</span>}
        {bulkStatus.state === 'running' && <span className="text-slate-muted">Paying payroll transfers...</span>}
      </div>
      <div className="flex gap-3">
        <Button
          onClick={handlePayPayroll}
          variant="success"
          icon={Send}
          disabled={bulkStatus.state === 'running'}
        >
          Pay selected payroll transfers
        </Button>
        <Button onClick={() => setShowNewModal(true)} variant="secondary" icon={Plus}>
          New transfer
        </Button>
      </div>
    </div>

    {/* New Transfer Modal */}
    {showNewModal && (
      <NewTransferModal
        onClose={() => setShowNewModal(false)}
        onSuccess={() => {
            setShowNewModal(false);
            mutate();
          }}
          initiateTransfer={initiateTransfer}
        />
      )}
    </div>
  );
}

interface NewTransferModalProps {
  onClose: () => void;
  onSuccess: () => void;
  initiateTransfer: (data: any) => Promise<any>;
}

function NewTransferModal({ onClose, onSuccess, initiateTransfer }: NewTransferModalProps) {
  const [form, setForm] = useState({
    amount: '',
    bank_code: '',
    account_number: '',
    account_name: '',
    narration: '',
    provider: 'paystack',
  });
  const [loading, setLoading] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [error, setError] = useState('');

  const { data: banksData } = useBanks({ country: 'nigeria' });

  const handleResolve = async () => {
    if (!form.bank_code || !form.account_number || form.account_number.length !== 10) {
      return;
    }
    setResolving(true);
    try {
      const result = await paymentsApi.resolveAccount({ account_number: form.account_number, bank_code: form.bank_code });
      setForm((prev) => ({ ...prev, account_name: result.account_name }));
    } catch (err: any) {
      setError('Could not resolve account');
    } finally {
      setResolving(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await initiateTransfer({
        amount: parseFloat(form.amount),
        bank_code: form.bank_code,
        account_number: form.account_number,
        account_name: form.account_name,
        narration: form.narration || 'Transfer',
        provider: form.provider,
      });
      onSuccess();
    } catch (err: any) {
      setError(err.message || 'Transfer failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-slate-800 rounded-xl p-6 max-w-lg w-full mx-4 border border-slate-border" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
          <Send className="w-5 h-5 text-teal-electric" />
          New Bank Transfer
        </h3>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-slate-muted mb-1">Amount (NGN)</label>
              <input
                type="number"
                value={form.amount}
                onChange={(e) => setForm((prev) => ({ ...prev, amount: e.target.value }))}
                className="input-field w-full"
                placeholder="0.00"
                required
                min="100"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-muted mb-1">Provider</label>
              <select
                value={form.provider}
                onChange={(e) => setForm((prev) => ({ ...prev, provider: e.target.value }))}
                className="input-field w-full"
              >
                <option value="paystack">Paystack</option>
                <option value="flutterwave">Flutterwave</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm text-slate-muted mb-1">Bank</label>
            <select
              value={form.bank_code}
              onChange={(e) => { setForm((prev) => ({ ...prev, bank_code: e.target.value, account_name: '' })); }}
              className="input-field w-full"
              required
            >
              <option value="">Select bank</option>
              {banksData?.banks?.map((bank: any) => (
                <option key={bank.code} value={bank.code}>{bank.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm text-slate-muted mb-1">Account Number</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={form.account_number}
                onChange={(e) => setForm((prev) => ({ ...prev, account_number: e.target.value.replace(/\D/g, '').slice(0, 10), account_name: '' }))}
                className="input-field flex-1"
                placeholder="0123456789"
                maxLength={10}
                required
              />
              <Button
                type="button"
                onClick={handleResolve}
                disabled={resolving || !form.bank_code || form.account_number.length !== 10}
                className="px-3 py-2 rounded-lg border border-slate-border text-sm text-slate-muted hover:text-foreground disabled:opacity-50 transition-colors"
              >
                {resolving ? 'Checking...' : 'Verify'}
              </Button>
            </div>
          </div>

          {form.account_name && (
            <div className="p-3 bg-green-500/10 border border-green-500/30 rounded-lg">
              <div className="text-xs text-green-400 mb-1">Account Name</div>
              <div className="text-foreground font-medium">{form.account_name}</div>
            </div>
          )}

          <div>
            <label className="block text-sm text-slate-muted mb-1">Narration</label>
            <input
              type="text"
              value={form.narration}
              onChange={(e) => setForm((prev) => ({ ...prev, narration: e.target.value }))}
              className="input-field w-full"
              placeholder="Payment for..."
              maxLength={100}
            />
          </div>

          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" onClick={onClose} variant="secondary">
              Cancel
            </Button>
            <Button type="submit" disabled={loading || !form.account_name} loading={loading} module="books">
              {loading ? 'Processing...' : 'Send Transfer'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
