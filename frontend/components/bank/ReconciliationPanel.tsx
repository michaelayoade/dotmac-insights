'use client';

import { useState, useMemo } from 'react';
import { cn } from '@/lib/utils';
import { useBankTransactionSuggestions, useBankTransactionMutations } from '@/hooks/useApi';
import {
  Link2,
  AlertTriangle,
  Check,
  FileText,
  Receipt,
  CreditCard,
  Loader2,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

interface ReconciliationPanelProps {
  transactionId: number | string;
  transactionAmount: number;
  currentAllocated: number;
  currency?: string;
  onReconcileComplete?: () => void;
}

interface Allocation {
  document_type: string;
  document_id: number | string;
  document_name: string;
  allocated_amount: number;
}

export function ReconciliationPanel({
  transactionId,
  transactionAmount,
  currentAllocated,
  currency = 'NGN',
  onReconcileComplete,
}: ReconciliationPanelProps) {
  const { data, isLoading, error } = useBankTransactionSuggestions(transactionId, { limit: 10 });
  const { reconcile } = useBankTransactionMutations();

  const [allocations, setAllocations] = useState<Map<string, Allocation>>(new Map());
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(true);

  const unallocatedAmount = transactionAmount - currentAllocated;

  const totalNewAllocation = useMemo(() => {
    return Array.from(allocations.values()).reduce((sum, a) => sum + a.allocated_amount, 0);
  }, [allocations]);

  const remainingToAllocate = unallocatedAmount - totalNewAllocation;

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-NG', {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
    }).format(value);
  };

  const formatDate = (date?: string) => {
    if (!date) return '-';
    return new Date(date).toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  };

  const getDocumentIcon = (type: string) => {
    switch (type) {
      case 'Sales Invoice':
        return <Receipt className="w-4 h-4 text-green-400" />;
      case 'Purchase Invoice':
        return <FileText className="w-4 h-4 text-amber-400" />;
      case 'Payment Entry':
        return <CreditCard className="w-4 h-4 text-blue-400" />;
      default:
        return <FileText className="w-4 h-4 text-slate-muted" />;
    }
  };

  const getMatchScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-400 bg-green-500/10 border-green-500/30';
    if (score >= 50) return 'text-amber-400 bg-amber-500/10 border-amber-500/30';
    return 'text-slate-muted bg-slate-elevated border-slate-border';
  };

  const handleAllocationChange = (
    documentType: string,
    documentId: number | string,
    documentName: string,
    amount: number
  ) => {
    const key = `${documentType}-${documentId}`;
    const newAllocations = new Map(allocations);

    if (amount > 0) {
      newAllocations.set(key, {
        document_type: documentType,
        document_id: documentId,
        document_name: documentName,
        allocated_amount: amount,
      });
    } else {
      newAllocations.delete(key);
    }

    setAllocations(newAllocations);
  };

  const handleQuickMatch = (suggestion: NonNullable<typeof data>['suggestions'][0]) => {
    const maxAllocation = Math.min(suggestion.outstanding_amount, remainingToAllocate);
    if (maxAllocation > 0) {
      handleAllocationChange(
        suggestion.document_type,
        suggestion.document_id,
        suggestion.document_name,
        maxAllocation
      );
    }
  };

  const handleSubmit = async () => {
    if (allocations.size === 0) return;

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      await reconcile(transactionId, {
        allocations: Array.from(allocations.values()).map((a) => ({
          document_type: a.document_type,
          document_id: a.document_id,
          allocated_amount: a.allocated_amount,
        })),
      });

      setAllocations(new Map());
      onReconcileComplete?.();
    } catch (err: any) {
      setSubmitError(err?.message || 'Failed to reconcile transaction');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (unallocatedAmount <= 0) {
    return (
      <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
        <div className="flex items-center gap-2 text-green-400">
          <Check className="w-5 h-5" />
          <span className="font-medium">Fully Reconciled</span>
        </div>
        <p className="text-green-400/70 text-sm mt-1">
          This transaction has been fully allocated to documents.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-4 flex items-center justify-between hover:bg-slate-elevated/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Link2 className="w-5 h-5 text-teal-electric" />
          <span className="text-white font-medium">Reconciliation</span>
          <span className="text-slate-muted text-sm">
            ({formatCurrency(unallocatedAmount)} unallocated)
          </span>
        </div>
        {expanded ? (
          <ChevronUp className="w-5 h-5 text-slate-muted" />
        ) : (
          <ChevronDown className="w-5 h-5 text-slate-muted" />
        )}
      </button>

      {expanded && (
        <div className="border-t border-slate-border">
          {/* Allocation Summary */}
          <div className="p-4 bg-slate-elevated/50 border-b border-slate-border">
            <div className="flex flex-wrap gap-4 text-sm">
              <div>
                <span className="text-slate-muted">Transaction Amount:</span>{' '}
                <span className="text-white font-medium">{formatCurrency(transactionAmount)}</span>
              </div>
              <div>
                <span className="text-slate-muted">Already Allocated:</span>{' '}
                <span className="text-green-400 font-medium">{formatCurrency(currentAllocated)}</span>
              </div>
              <div>
                <span className="text-slate-muted">New Allocations:</span>{' '}
                <span className="text-teal-electric font-medium">{formatCurrency(totalNewAllocation)}</span>
              </div>
              <div>
                <span className="text-slate-muted">Remaining:</span>{' '}
                <span
                  className={cn('font-medium', remainingToAllocate > 0 ? 'text-amber-400' : 'text-green-400')}
                >
                  {formatCurrency(remainingToAllocate)}
                </span>
              </div>
            </div>
          </div>

          {/* Loading State */}
          {isLoading && (
            <div className="p-8 text-center">
              <Loader2 className="w-6 h-6 text-teal-electric animate-spin mx-auto mb-2" />
              <p className="text-slate-muted text-sm">Finding matching documents...</p>
            </div>
          )}

          {/* Error State */}
          {error && (
            <div className="p-4">
              <div className="flex items-center gap-2 text-coral-alert">
                <AlertTriangle className="w-5 h-5" />
                <span>Failed to load suggestions</span>
              </div>
            </div>
          )}

          {/* Suggestions */}
          {data && data.suggestions.length > 0 && (
            <div className="p-4">
              <p className="text-slate-muted text-sm mb-3">Match Suggestions</p>
              <div className="space-y-2">
                {data.suggestions.map((suggestion) => {
                  const key = `${suggestion.document_type}-${suggestion.document_id}`;
                  const allocation = allocations.get(key);
                  const isSelected = !!allocation;

                  return (
                    <div
                      key={key}
                      className={cn(
                        'border rounded-lg p-3 transition-colors',
                        isSelected
                          ? 'border-teal-electric/50 bg-teal-electric/5'
                          : 'border-slate-border hover:border-slate-muted'
                      )}
                    >
                      <div className="flex items-start gap-3">
                        {/* Document Info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            {getDocumentIcon(suggestion.document_type)}
                            <span className="text-white font-medium truncate">{suggestion.document_name}</span>
                            <span
                              className={cn(
                                'text-xs px-1.5 py-0.5 rounded border',
                                getMatchScoreColor(suggestion.match_score)
                              )}
                            >
                              {suggestion.match_score}%
                            </span>
                          </div>
                          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-muted">
                            <span>{suggestion.document_type}</span>
                            <span>{suggestion.party_name}</span>
                            <span>Due: {formatDate(suggestion.due_date)}</span>
                          </div>
                          {suggestion.match_reasons.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-2">
                              {suggestion.match_reasons.map((reason, i) => (
                                <span
                                  key={i}
                                  className="text-xs px-1.5 py-0.5 bg-slate-elevated rounded text-slate-muted"
                                >
                                  {reason}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Outstanding Amount */}
                        <div className="text-right shrink-0">
                          <p className="text-slate-muted text-xs">Outstanding</p>
                          <p className="text-white font-mono">{formatCurrency(suggestion.outstanding_amount)}</p>
                        </div>

                        {/* Allocation Input */}
                        <div className="shrink-0 w-32">
                          <div className="flex flex-col gap-1">
                            <input
                              type="number"
                              min="0"
                              max={Math.min(suggestion.outstanding_amount, unallocatedAmount)}
                              step="0.01"
                              value={allocation?.allocated_amount || ''}
                              onChange={(e) =>
                                handleAllocationChange(
                                  suggestion.document_type,
                                  suggestion.document_id,
                                  suggestion.document_name,
                                  parseFloat(e.target.value) || 0
                                )
                              }
                              placeholder="0.00"
                              className="input-field text-right text-sm"
                            />
                            <button
                              type="button"
                              onClick={() => handleQuickMatch(suggestion)}
                              className="text-xs text-teal-electric hover:underline"
                            >
                              Match full
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* No Suggestions */}
          {data && data.suggestions.length === 0 && (
            <div className="p-8 text-center">
              <FileText className="w-8 h-8 text-slate-muted mx-auto mb-2" />
              <p className="text-slate-muted">No matching documents found</p>
              <p className="text-slate-muted text-sm mt-1">
                You can manually search for documents to allocate this transaction.
              </p>
            </div>
          )}

          {/* Submit Error */}
          {submitError && (
            <div className="px-4 pb-4">
              <div className="flex items-center gap-2 text-coral-alert text-sm">
                <AlertTriangle className="w-4 h-4" />
                <span>{submitError}</span>
              </div>
            </div>
          )}

          {/* Actions */}
          {allocations.size > 0 && (
            <div className="p-4 border-t border-slate-border bg-slate-elevated/30">
              <div className="flex items-center justify-between">
                <div className="text-sm">
                  <span className="text-slate-muted">Allocating </span>
                  <span className="text-teal-electric font-medium">{formatCurrency(totalNewAllocation)}</span>
                  <span className="text-slate-muted"> to </span>
                  <span className="text-white">{allocations.size} document(s)</span>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setAllocations(new Map())}
                    className="px-3 py-2 text-sm text-slate-muted hover:text-white border border-slate-border rounded-lg hover:border-slate-muted transition-colors"
                    disabled={isSubmitting}
                  >
                    Clear
                  </button>
                  <button
                    type="button"
                    onClick={handleSubmit}
                    disabled={isSubmitting || totalNewAllocation <= 0}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90 disabled:opacity-60 transition-colors"
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Reconciling...
                      </>
                    ) : (
                      <>
                        <Check className="w-4 h-4" />
                        Reconcile
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ReconciliationPanel;
