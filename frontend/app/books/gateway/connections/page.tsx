'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useOpenBankingConnections, useGatewayMutations } from '@/hooks/useApi';
import { DataTable } from '@/components/DataTable';
import { AlertTriangle, Building2, RefreshCw, Unlink, Eye, Link as LinkIcon, CheckCircle, XCircle, Clock } from 'lucide-react';
import { formatCurrency } from '@/lib/utils';
import { paymentsApi } from '@/lib/api';
import { useErrorHandler } from '@/hooks/useErrorHandler';

function formatDate(date: string | null | undefined) {
  if (!date) return '-';
  return new Date(date).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getStatusBadge(status: string) {
  const config: Record<string, { icon: any; className: string }> = {
    connected: { icon: CheckCircle, className: 'bg-green-500/20 text-green-400 border-green-500/30' },
    disconnected: { icon: XCircle, className: 'bg-red-500/20 text-red-400 border-red-500/30' },
    expired: { icon: Clock, className: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' },
    pending: { icon: Clock, className: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
  };
  const { icon: Icon, className } = config[status] || config.pending;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${className}`}>
      <Icon className="w-3 h-3" />
      {status}
    </span>
  );
}

function getProviderBadge(provider: string) {
  const styles: Record<string, string> = {
    mono: 'bg-purple-500/20 text-purple-400',
    okra: 'bg-green-500/20 text-green-400',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${styles[provider] || 'bg-slate-500/20 text-slate-400'}`}>
      {provider}
    </span>
  );
}

export default function OpenBankingConnectionsPage() {
  const router = useRouter();
  const [status, setStatus] = useState('');
  const [provider, setProvider] = useState('');
  const [selectedConnection, setSelectedConnection] = useState<any>(null);
  const [showUnlinkModal, setShowUnlinkModal] = useState(false);
  const [showTransactionsModal, setShowTransactionsModal] = useState(false);

  const { data, isLoading, error, mutate } = useOpenBankingConnections({
    status: status || undefined,
    provider: provider || undefined,
  });

  const { unlinkOpenBankingAccount } = useGatewayMutations();
  const { handleError, handleSuccess } = useErrorHandler();

  const handleUnlink = async (accountId: number) => {
    try {
      await unlinkOpenBankingAccount(accountId);
      mutate();
      setShowUnlinkModal(false);
      setSelectedConnection(null);
      handleSuccess('Account unlinked successfully');
    } catch (err: any) {
      handleError(err, 'Failed to unlink account');
    }
  };

  const columns = [
    {
      key: 'bank_name',
      header: 'Bank Account',
      render: (item: any) => (
        <div>
          <div className="text-foreground font-medium">{item.bank_name}</div>
          <div className="text-xs text-slate-muted font-mono">{item.account_number}</div>
        </div>
      ),
    },
    {
      key: 'account_name',
      header: 'Account Name',
      render: (item: any) => <span className="text-slate-200">{item.account_name}</span>,
    },
    {
      key: 'provider',
      header: 'Provider',
      render: (item: any) => getProviderBadge(item.provider),
    },
    {
      key: 'balance',
      header: 'Balance',
      align: 'right' as const,
      render: (item: any) => (
        <div className="text-right">
          {item.balance != null ? (
            <>
              <span className="font-mono text-foreground">{formatCurrency(item.balance, item.currency)}</span>
              {item.balance_updated_at && (
                <div className="text-xs text-slate-muted">Updated {formatDate(item.balance_updated_at)}</div>
              )}
            </>
          ) : (
            <span className="text-slate-muted">-</span>
          )}
        </div>
      ),
    },
    {
      key: 'account_type',
      header: 'Type',
      render: (item: any) => <span className="text-slate-muted text-sm capitalize">{item.account_type || '-'}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => getStatusBadge(item.status),
    },
    {
      key: 'last_synced_at',
      header: 'Last Synced',
      render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.last_synced_at)}</span>,
    },
    {
      key: 'actions',
      header: '',
      render: (item: any) => (
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => { setSelectedConnection(item); setShowTransactionsModal(true); }}
            className="p-1.5 rounded hover:bg-slate-700 text-slate-muted hover:text-teal-electric transition-colors"
            title="View transactions"
          >
            <Eye className="w-4 h-4" />
          </button>
          {item.status === 'connected' && (
            <button
              onClick={() => { setSelectedConnection(item); setShowUnlinkModal(true); }}
              className="p-1.5 rounded hover:bg-slate-700 text-slate-muted hover:text-red-400 transition-colors"
              title="Unlink account"
            >
              <Unlink className="w-4 h-4" />
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load connections</p>
        </div>
      )}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Building2 className="w-5 h-5 text-teal-electric" />
          <h1 className="text-xl font-semibold text-foreground">Open Banking Connections</h1>
        </div>
        <button
          onClick={() => mutate()}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-muted transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Info Banner */}
      <div className="bg-purple-500/10 border border-purple-500/30 rounded-xl p-4">
        <div className="flex items-start gap-3">
          <LinkIcon className="w-5 h-5 text-purple-400 mt-0.5" />
          <div>
            <h3 className="text-sm font-semibold text-purple-400 mb-1">What is Open Banking?</h3>
            <p className="text-sm text-slate-muted">
              Connect customer bank accounts via Mono or Okra to fetch real-time balances, transaction history, and verify account ownership.
              Perfect for loan applications, income verification, and automated reconciliation.
            </p>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-4 items-center">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="input-field"
          data-testid="gateway-connections-status-filter"
        >
          <option value="">All Status</option>
          <option value="connected">Connected</option>
          <option value="disconnected">Disconnected</option>
          <option value="expired">Expired</option>
          <option value="pending">Pending</option>
        </select>
        <select
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
          className="input-field"
          data-testid="gateway-connections-provider-filter"
        >
          <option value="">All Providers</option>
          <option value="mono">Mono</option>
          <option value="okra">Okra</option>
        </select>
      </div>

      {(() => {
        const connections = data?.items ?? data?.data ?? (Array.isArray(data) ? data : []);
        return (
          <DataTable
            columns={columns}
            data={connections}
            keyField="id"
            loading={isLoading}
            emptyMessage="No linked accounts found"
          />
        );
      })()}

      {/* Stats Cards */}
      {(() => {
        const connections = data?.items ?? data?.data ?? (Array.isArray(data) ? data : []);
        return connections.length ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-800/50 border border-slate-border rounded-xl p-4">
            <div className="text-2xl font-bold text-foreground">{connections.length}</div>
            <div className="text-sm text-slate-muted">Total Connections</div>
          </div>
          <div className="bg-slate-800/50 border border-slate-border rounded-xl p-4">
            <div className="text-2xl font-bold text-green-400">
              {connections.filter((c: any) => c.status === 'connected').length}
            </div>
            <div className="text-sm text-slate-muted">Active</div>
          </div>
          <div className="bg-slate-800/50 border border-slate-border rounded-xl p-4">
            <div className="text-2xl font-bold text-purple-400">
              {connections.filter((c: any) => c.provider === 'mono').length}
            </div>
            <div className="text-sm text-slate-muted">Via Mono</div>
          </div>
          <div className="bg-slate-800/50 border border-slate-border rounded-xl p-4">
            <div className="text-2xl font-bold text-teal-electric">
              {connections.filter((c: any) => c.provider === 'okra').length}
            </div>
            <div className="text-sm text-slate-muted">Via Okra</div>
          </div>
        </div>
        ) : null;
      })()}

      {/* Unlink Modal */}
      {showUnlinkModal && selectedConnection && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setShowUnlinkModal(false)}>
          <div className="bg-slate-800 rounded-xl p-6 max-w-md w-full mx-4 border border-slate-border" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-foreground mb-4">Unlink Account</h3>
            <p className="text-slate-muted mb-4">
              Are you sure you want to unlink <span className="text-foreground">{selectedConnection.bank_name}</span> account ending in <span className="font-mono text-teal-electric">{selectedConnection.account_number?.slice(-4)}</span>?
            </p>
            <p className="text-sm text-yellow-400 mb-4">
              This will revoke access to transaction data from this account.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowUnlinkModal(false)}
                className="px-4 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleUnlink(selectedConnection.id)}
                className="px-4 py-2 rounded-lg bg-red-500 text-foreground font-semibold hover:bg-red-600 transition-colors"
              >
                Unlink
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Transactions Modal */}
      {showTransactionsModal && selectedConnection && (
        <TransactionsModal
          connection={selectedConnection}
          onClose={() => { setShowTransactionsModal(false); setSelectedConnection(null); }}
        />
      )}
    </div>
  );
}

interface TransactionsModalProps {
  connection: any;
  onClose: () => void;
}

function TransactionsModal({ connection, onClose }: TransactionsModalProps) {
  const [transactions, setTransactions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useState(() => {
    paymentsApi.getOpenBankingTransactions(connection.id, { limit: 50 })
      .then((data) => {
        const txns = Array.isArray(data) ? data : data?.transactions || [];
        setTransactions(txns);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  });

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-slate-800 rounded-xl p-6 max-w-3xl w-full mx-4 max-h-[80vh] overflow-hidden flex flex-col border border-slate-border" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-foreground">{connection.bank_name} Transactions</h3>
            <p className="text-sm text-slate-muted font-mono">{connection.account_number}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-slate-700 text-slate-muted hover:text-foreground transition-colors"
          >
            <XCircle className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-electric"></div>
            </div>
          ) : error ? (
            <div className="text-center py-8 text-red-400">{error}</div>
          ) : transactions.length === 0 ? (
            <div className="text-center py-8 text-slate-muted">No transactions found</div>
          ) : (
            <div className="space-y-2">
              {transactions.map((tx: any, idx: number) => (
                <div key={tx.transaction_id || idx} className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-foreground truncate">{tx.narration}</div>
                    <div className="text-xs text-slate-muted">
                      {new Date(tx.date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
                      {tx.category && <span className="ml-2 text-purple-400">{tx.category}</span>}
                    </div>
                  </div>
                  <div className={`text-right font-mono ${tx.type === 'credit' ? 'text-green-400' : 'text-red-400'}`}>
                    {tx.type === 'credit' ? '+' : '-'}{formatCurrency(Math.abs(tx.amount), connection.currency)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
