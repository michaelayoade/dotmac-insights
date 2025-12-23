'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useGatewayPayments, useGatewayMutations } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { AlertTriangle, CreditCard, RefreshCw, Eye, RotateCcw } from 'lucide-react';

import { useErrorHandler } from '@/hooks/useErrorHandler';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import { Button, StatusPill } from '@/components/ui';
import { formatAccountingCurrency, formatAccountingDate } from '@/lib/formatters/accounting';

function getStatusBadge(status: string) {
  const tones: Record<string, StatusTone> = {
    success: 'success',
    pending: 'warning',
    failed: 'danger',
    abandoned: 'default',
    refunded: 'info',
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

export default function GatewayPaymentsPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [status, setStatus] = useState('');
  const [provider, setProvider] = useState('');
  const [selectedPayment, setSelectedPayment] = useState<any>(null);
  const [showVerifyModal, setShowVerifyModal] = useState(false);
  const [showRefundModal, setShowRefundModal] = useState(false);

  const { data, isLoading, error, mutate } = useGatewayPayments({
    status: status || undefined,
    provider: provider || undefined,
    limit: pageSize,
    offset: (page - 1) * pageSize,
  });

  const { verifyPayment, refundPayment } = useGatewayMutations();
  const { handleError, handleSuccess } = useErrorHandler();

  const handleVerify = async (reference: string) => {
    try {
      await verifyPayment(reference);
      mutate();
      setShowVerifyModal(false);
      setSelectedPayment(null);
      handleSuccess('Payment verified successfully');
    } catch (err: any) {
      handleError(err, 'Verification failed');
    }
  };

  const handleRefund = async (reference: string, amount?: number) => {
    try {
      await refundPayment(reference, amount);
      mutate();
      setShowRefundModal(false);
      setSelectedPayment(null);
      handleSuccess('Refund processed successfully');
    } catch (err: any) {
      handleError(err, 'Refund failed');
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
      key: 'customer_email',
      header: 'Customer',
      render: (item: any) => <span className="text-slate-muted text-sm">{item.customer_email || '-'}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => getStatusBadge(item.status),
    },
    {
      key: 'paid_at',
      header: 'Paid At',
      render: (item: any) => <span className="text-slate-muted text-sm">{formatAccountingDate(item.paid_at)}</span>,
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
          {item.status === 'pending' && (
            <Button
              onClick={() => { setSelectedPayment(item); setShowVerifyModal(true); }}
              className="p-1.5 rounded hover:bg-slate-700 text-slate-muted hover:text-teal-electric transition-colors"
              title="Verify payment"
            >
              <RefreshCw className="w-4 h-4" />
            </Button>
          )}
          {item.status === 'success' && (
            <Button
              onClick={() => { setSelectedPayment(item); setShowRefundModal(true); }}
              className="p-1.5 rounded hover:bg-slate-700 text-slate-muted hover:text-purple-400 transition-colors"
              title="Refund payment"
            >
              <RotateCcw className="w-4 h-4" />
            </Button>
          )}
          <Button
            onClick={() => router.push(`/books/gateway/payments/${item.reference}`)}
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
          <p className="text-red-400">Failed to load payments</p>
        </div>
      )}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CreditCard className="w-5 h-5 text-teal-electric" />
          <h1 className="text-xl font-semibold text-foreground">Online Payments</h1>
        </div>
        <Button
          onClick={() => mutate()}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-muted transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </Button>
      </div>

      <div className="flex flex-wrap gap-4 items-center">
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          className="input-field"
          data-testid="gateway-payments-status-filter"
        >
          <option value="">All Status</option>
          <option value="success">Success</option>
          <option value="pending">Pending</option>
          <option value="failed">Failed</option>
          <option value="abandoned">Abandoned</option>
          <option value="refunded">Refunded</option>
        </select>
        <select
          value={provider}
          onChange={(e) => { setProvider(e.target.value); setPage(1); }}
          className="input-field"
          data-testid="gateway-payments-provider-filter"
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
        emptyMessage="No payments found"
        onRowClick={(item) => router.push(`/books/gateway/payments/${(item as any).reference}`)}
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

      {/* Verify Modal */}
      {showVerifyModal && selectedPayment && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setShowVerifyModal(false)}>
          <div className="bg-slate-800 rounded-xl p-6 max-w-md w-full mx-4 border border-slate-border" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-foreground mb-4">Verify Payment</h3>
            <p className="text-slate-muted mb-4">
              Verify payment status with the provider for reference: <span className="text-teal-electric font-mono">{selectedPayment.reference}</span>
            </p>
            <div className="flex justify-end gap-3">
              <Button onClick={() => setShowVerifyModal(false)} variant="secondary">
                Cancel
              </Button>
              <Button onClick={() => handleVerify(selectedPayment.reference)} module="books">
                Verify
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Refund Modal */}
      {showRefundModal && selectedPayment && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setShowRefundModal(false)}>
          <div className="bg-slate-800 rounded-xl p-6 max-w-md w-full mx-4 border border-slate-border" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-foreground mb-4">Refund Payment</h3>
            <p className="text-slate-muted mb-4">
              Refund payment <span className="text-teal-electric font-mono">{selectedPayment.reference}</span>
            </p>
            <div className="mb-4 p-3 bg-slate-900 rounded-lg">
              <div className="text-sm text-slate-muted">Amount</div>
              <div className="text-lg font-mono text-foreground">{formatAccountingCurrency(selectedPayment.amount, selectedPayment.currency)}</div>
            </div>
            <div className="flex justify-end gap-3">
              <Button
                onClick={() => setShowRefundModal(false)}
                className="px-4 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground transition-colors"
              >
                Cancel
              </Button>
              <Button
                onClick={() => handleRefund(selectedPayment.reference)}
                className="px-4 py-2 rounded-lg bg-purple-500 text-foreground font-semibold hover:bg-purple-600 transition-colors"
              >
                Full Refund
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
