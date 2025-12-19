'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import {
  CheckCircle,
  XCircle,
  Clock,
  FileText,
  Wallet2,
  User,
  Calendar,
  DollarSign,
  AlertTriangle,
  Loader2,
  ChevronDown,
  ChevronRight,
  Eye,
  Filter,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useExpenseClaims, useExpenseMutations, useCashAdvances, useCashAdvanceMutations } from '@/hooks/useExpenses';
import { useErrorHandler } from '@/hooks/useErrorHandler';
import type { ExpenseClaim, CashAdvance } from '@/lib/expenses.types';

type ItemType = 'claim' | 'advance';

interface ApprovalItem {
  id: number;
  type: ItemType;
  title: string;
  number?: string;
  employee_id: number;
  amount: number;
  currency: string;
  date: string;
  description?: string;
  lineCount?: number;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function formatCurrency(amount: number, currency: string = 'NGN'): string {
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(amount);
}

export default function ApprovalsPage() {
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [processing, setProcessing] = useState(false);
  const [expandedItem, setExpandedItem] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [filterType, setFilterType] = useState<'all' | 'claims' | 'advances'>('all');

  const { data: claims, isLoading: claimsLoading } = useExpenseClaims({ status: 'pending_approval' });
  const { data: advances, isLoading: advancesLoading } = useCashAdvances({ status: 'pending_approval' });

  const { approveClaim, rejectClaim } = useExpenseMutations();
  const { approveAdvance, rejectAdvance } = useCashAdvanceMutations();
  const { handleError } = useErrorHandler();

  const isLoading = claimsLoading || advancesLoading;

  // Combine claims and advances into unified list
  const items = useMemo(() => {
    const result: ApprovalItem[] = [];

    if (filterType !== 'advances') {
      claims?.forEach((c) => {
        result.push({
          id: c.id,
          type: 'claim',
          title: c.title,
          number: c.claim_number || undefined,
          employee_id: c.employee_id,
          amount: c.total_claimed_amount,
          currency: c.currency,
          date: c.claim_date,
          lineCount: c.lines?.length,
        });
      });
    }

    if (filterType !== 'claims') {
      advances?.forEach((a) => {
        result.push({
          id: a.id,
          type: 'advance',
          title: a.purpose,
          number: a.advance_number || undefined,
          employee_id: a.employee_id,
          amount: a.requested_amount,
          currency: a.currency,
          date: a.request_date,
          description: a.destination || undefined,
        });
      });
    }

    // Sort by date descending
    result.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
    return result;
  }, [claims, advances, filterType]);

  const totalAmount = items.reduce((sum, item) => sum + item.amount, 0);
  const claimCount = claims?.length || 0;
  const advanceCount = advances?.length || 0;

  const itemKey = (item: ApprovalItem) => `${item.type}-${item.id}`;

  const toggleSelect = (item: ApprovalItem) => {
    const key = itemKey(item);
    const newSelected = new Set(selectedItems);
    if (newSelected.has(key)) {
      newSelected.delete(key);
    } else {
      newSelected.add(key);
    }
    setSelectedItems(newSelected);
  };

  const toggleSelectAll = () => {
    if (selectedItems.size === items.length) {
      setSelectedItems(new Set());
    } else {
      setSelectedItems(new Set(items.map(itemKey)));
    }
  };

  const handleBulkApprove = async () => {
    if (selectedItems.size === 0) return;

    setProcessing(true);
    try {
      const promises: Promise<unknown>[] = [];

      for (const key of Array.from(selectedItems)) {
        const [type, idStr] = key.split('-');
        const id = parseInt(idStr);

        if (type === 'claim') {
          promises.push(approveClaim(id));
        } else if (type === 'advance') {
          promises.push(approveAdvance(id));
        }
      }

      await Promise.all(promises);
      setSelectedItems(new Set());
    } catch (err) {
      handleError(err, 'Some approvals failed');
    } finally {
      setProcessing(false);
    }
  };

  const handleBulkReject = async () => {
    if (selectedItems.size === 0 || !rejectReason.trim()) return;

    setProcessing(true);
    try {
      const promises: Promise<unknown>[] = [];

      for (const key of Array.from(selectedItems)) {
        const [type, idStr] = key.split('-');
        const id = parseInt(idStr);

        if (type === 'claim') {
          promises.push(rejectClaim(id, rejectReason));
        } else if (type === 'advance') {
          promises.push(rejectAdvance(id, rejectReason));
        }
      }

      await Promise.all(promises);
      setSelectedItems(new Set());
      setShowRejectModal(false);
      setRejectReason('');
    } catch (err) {
      handleError(err, 'Some rejections failed');
    } finally {
      setProcessing(false);
    }
  };

  const handleSingleApprove = async (item: ApprovalItem) => {
    setProcessing(true);
    try {
      if (item.type === 'claim') {
        await approveClaim(item.id);
      } else {
        await approveAdvance(item.id);
      }
    } catch (err) {
      handleError(err, 'Approval failed');
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center">
          <Clock className="w-5 h-5 text-amber-400" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-white">Pending Approvals</h1>
          <p className="text-slate-muted text-sm">Review and approve expense claims and cash advances</p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-2 text-slate-muted text-sm mb-1">
            <Clock className="w-4 h-4" />
            <span>Total Pending</span>
          </div>
          <p className="text-2xl font-bold text-white">{items.length}</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-2 text-slate-muted text-sm mb-1">
            <DollarSign className="w-4 h-4" />
            <span>Total Amount</span>
          </div>
          <p className="text-2xl font-bold text-white">{formatCurrency(totalAmount)}</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-2 text-slate-muted text-sm mb-1">
            <FileText className="w-4 h-4" />
            <span>Expense Claims</span>
          </div>
          <p className="text-2xl font-bold text-sky-400">{claimCount}</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-2 text-slate-muted text-sm mb-1">
            <Wallet2 className="w-4 h-4" />
            <span>Cash Advances</span>
          </div>
          <p className="text-2xl font-bold text-amber-400">{advanceCount}</p>
        </div>
      </div>

      {/* Actions Bar */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={selectedItems.size === items.length && items.length > 0}
                onChange={toggleSelectAll}
                className="w-4 h-4 rounded border-slate-border bg-slate-elevated text-violet-500 focus:ring-violet-500/50"
              />
              <span className="text-sm text-slate-muted">
                {selectedItems.size > 0 ? `${selectedItems.size} selected` : 'Select all'}
              </span>
            </label>

            <div className="h-6 w-px bg-slate-border" />

            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-slate-muted" />
              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value as any)}
                className="bg-slate-elevated border border-slate-border rounded-lg px-2 py-1 text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
              >
                <option value="all">All types</option>
                <option value="claims">Claims only</option>
                <option value="advances">Advances only</option>
              </select>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowRejectModal(true)}
              disabled={selectedItems.size === 0 || processing}
              className="flex items-center gap-2 px-4 py-2 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 text-sm font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <XCircle className="w-4 h-4" />
              Reject Selected
            </button>
            <button
              onClick={handleBulkApprove}
              disabled={selectedItems.size === 0 || processing}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {processing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <CheckCircle className="w-4 h-4" />
              )}
              Approve Selected
            </button>
          </div>
        </div>
      </div>

      {/* Items List */}
      <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-violet-400" />
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-12 text-slate-muted">
            <CheckCircle className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p className="text-lg font-medium">All caught up!</p>
            <p className="text-sm">No pending approvals at this time.</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-border">
            {items.map((item) => {
              const key = itemKey(item);
              const isSelected = selectedItems.has(key);
              const isExpanded = expandedItem === key;

              return (
                <div
                  key={key}
                  className={cn(
                    'transition-colors',
                    isSelected ? 'bg-violet-500/5' : 'hover:bg-slate-elevated/50'
                  )}
                >
                  <div className="flex items-center gap-4 p-4">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleSelect(item)}
                      className="w-4 h-4 rounded border-slate-border bg-slate-elevated text-violet-500 focus:ring-violet-500/50"
                    />

                    <button
                      onClick={() => setExpandedItem(isExpanded ? null : key)}
                      className="p-1 text-slate-muted hover:text-white transition-colors"
                    >
                      {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                    </button>

                    <div
                      className={cn(
                        'p-2 rounded-lg',
                        item.type === 'claim' ? 'bg-sky-500/15 text-sky-300' : 'bg-amber-500/15 text-amber-300'
                      )}
                    >
                      {item.type === 'claim' ? <FileText className="w-4 h-4" /> : <Wallet2 className="w-4 h-4" />}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-white font-medium truncate">{item.title}</p>
                        {item.number && (
                          <span className="text-xs text-slate-muted font-mono">#{item.number}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-xs text-slate-muted mt-0.5">
                        <span className="flex items-center gap-1">
                          <User className="w-3 h-3" />
                          Employee #{item.employee_id}
                        </span>
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          {formatDate(item.date)}
                        </span>
                        {item.type === 'claim' && item.lineCount && (
                          <span>{item.lineCount} line{item.lineCount > 1 ? 's' : ''}</span>
                        )}
                      </div>
                    </div>

                    <div className="text-right">
                      <p className="text-white font-semibold">{formatCurrency(item.amount, item.currency)}</p>
                      <p className="text-xs text-slate-muted">{item.currency}</p>
                    </div>

                    <div className="flex items-center gap-1">
                      <Link
                        href={item.type === 'claim' ? `/expenses/claims/${item.id}` : `/expenses/advances/${item.id}`}
                        className="p-2 text-slate-muted hover:text-white hover:bg-slate-elevated rounded-lg transition-colors"
                        title="View details"
                      >
                        <Eye className="w-4 h-4" />
                      </Link>
                      <button
                        onClick={() => handleSingleApprove(item)}
                        disabled={processing}
                        className="p-2 text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10 rounded-lg transition-colors disabled:opacity-50"
                        title="Approve"
                      >
                        <CheckCircle className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* Expanded Details */}
                  {isExpanded && (
                    <div className="px-4 pb-4 pl-16">
                      <div className="bg-slate-elevated rounded-lg p-3 text-sm">
                        {item.type === 'claim' ? (
                          <div>
                            <p className="text-slate-muted">Expense claim with {item.lineCount} line items</p>
                            <Link
                              href={`/expenses/claims/${item.id}`}
                              className="text-violet-400 hover:text-violet-300 text-xs mt-2 inline-block"
                            >
                              View full claim details &rarr;
                            </Link>
                          </div>
                        ) : (
                          <div>
                            <p className="text-white mb-1">Purpose: {item.title}</p>
                            {item.description && (
                              <p className="text-slate-muted">Destination: {item.description}</p>
                            )}
                            <Link
                              href={`/expenses/advances/${item.id}`}
                              className="text-violet-400 hover:text-violet-300 text-xs mt-2 inline-block"
                            >
                              View full advance details &rarr;
                            </Link>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Reject Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-slate-card border border-slate-border rounded-xl w-full max-w-md mx-4 shadow-2xl">
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-border">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-rose-400" />
                Reject {selectedItems.size} Item{selectedItems.size > 1 ? 's' : ''}
              </h3>
              <button onClick={() => setShowRejectModal(false)} className="text-slate-muted hover:text-white">
                <XCircle className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <p className="text-sm text-slate-muted">
                Please provide a reason for rejecting the selected items. This will be visible to the submitters.
              </p>
              <div>
                <label className="block text-sm text-slate-muted mb-1">Rejection Reason *</label>
                <textarea
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  rows={3}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-rose-500/50 resize-none"
                  placeholder="Enter reason for rejection..."
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  onClick={() => setShowRejectModal(false)}
                  className="px-4 py-2 text-sm text-slate-muted hover:text-white transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleBulkReject}
                  disabled={!rejectReason.trim() || processing}
                  className="flex items-center gap-2 px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
                >
                  {processing && <Loader2 className="w-4 h-4 animate-spin" />}
                  Reject
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
