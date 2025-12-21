'use client';

import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import { AlertTriangle, Check, Landmark, Calendar, CreditCard, Info } from 'lucide-react';
import type { OFXParseResult, MappedOFXTransaction } from '@/lib/parsers/ofx';
import { mapOFXToTransactions, getAccountTypeLabel, validateOFXResult } from '@/lib/parsers/ofx';

interface OFXPreviewProps {
  ofxData: OFXParseResult;
  previewCount?: number;
}

export function OFXPreview({ ofxData, previewCount = 5 }: OFXPreviewProps) {
  const validation = useMemo(() => validateOFXResult(ofxData), [ofxData]);

  const mappedTransactions = useMemo(() => mapOFXToTransactions(ofxData), [ofxData]);

  const previewTransactions = useMemo(
    () => mappedTransactions.slice(0, previewCount),
    [mappedTransactions, previewCount]
  );

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-NG', {
      style: 'currency',
      currency: ofxData.currency || 'NGN',
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

  return (
    <div className="space-y-6">
      {/* Account Information */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <h3 className="text-foreground font-medium mb-4 flex items-center gap-2">
          <Landmark className="w-4 h-4 text-teal-electric" />
          Account Information
        </h3>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {ofxData.bankId && (
            <div>
              <p className="text-slate-muted text-xs uppercase tracking-wider mb-1">Bank ID</p>
              <p className="text-foreground font-mono">{ofxData.bankId}</p>
            </div>
          )}

          {ofxData.accountId && (
            <div>
              <p className="text-slate-muted text-xs uppercase tracking-wider mb-1">Account</p>
              <p className="text-foreground font-mono">****{ofxData.accountId.slice(-4)}</p>
            </div>
          )}

          {ofxData.accountType && (
            <div>
              <p className="text-slate-muted text-xs uppercase tracking-wider mb-1">Type</p>
              <p className="text-foreground">{getAccountTypeLabel(ofxData.accountType)}</p>
            </div>
          )}

          {ofxData.currency && (
            <div>
              <p className="text-slate-muted text-xs uppercase tracking-wider mb-1">Currency</p>
              <p className="text-foreground">{ofxData.currency}</p>
            </div>
          )}
        </div>

        {/* Statement Period */}
        {(ofxData.statementStart || ofxData.statementEnd) && (
          <div className="mt-4 pt-4 border-t border-slate-border">
            <div className="flex items-center gap-2 text-slate-muted text-sm">
              <Calendar className="w-4 h-4" />
              <span>
                Statement period: {formatDate(ofxData.statementStart)} to {formatDate(ofxData.statementEnd)}
              </span>
            </div>
          </div>
        )}

        {/* Balances */}
        {(ofxData.ledgerBalance !== undefined || ofxData.availableBalance !== undefined) && (
          <div className="mt-4 pt-4 border-t border-slate-border flex flex-wrap gap-6">
            {ofxData.ledgerBalance !== undefined && (
              <div>
                <p className="text-slate-muted text-xs uppercase tracking-wider mb-1">Ledger Balance</p>
                <p
                  className={cn(
                    'text-lg font-semibold font-mono',
                    ofxData.ledgerBalance >= 0 ? 'text-green-400' : 'text-coral-alert'
                  )}
                >
                  {formatCurrency(ofxData.ledgerBalance)}
                </p>
              </div>
            )}

            {ofxData.availableBalance !== undefined && (
              <div>
                <p className="text-slate-muted text-xs uppercase tracking-wider mb-1">Available Balance</p>
                <p
                  className={cn(
                    'text-lg font-semibold font-mono',
                    ofxData.availableBalance >= 0 ? 'text-green-400' : 'text-coral-alert'
                  )}
                >
                  {formatCurrency(ofxData.availableBalance)}
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Validation Messages */}
      {!validation.valid && (
        <div className="p-4 bg-coral-alert/10 border border-coral-alert/30 rounded-xl">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-5 h-5 text-coral-alert mt-0.5" />
            <div>
              <p className="text-coral-alert font-medium">Cannot import file</p>
              <ul className="text-sm text-coral-alert mt-1 list-disc list-inside">
                {validation.errors.map((error, i) => (
                  <li key={i}>{error}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {validation.warnings.length > 0 && (
        <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl">
          <div className="flex items-start gap-2">
            <Info className="w-5 h-5 text-amber-400 mt-0.5" />
            <div>
              <p className="text-amber-400 font-medium">Warnings</p>
              <ul className="text-sm text-amber-400 mt-1 list-disc list-inside">
                {validation.warnings.map((warning, i) => (
                  <li key={i}>{warning}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {validation.valid && (
        <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-xl">
          <div className="flex items-center gap-2 text-green-400">
            <Check className="w-5 h-5" />
            <span className="font-medium">
              Ready to import {mappedTransactions.length} transactions
            </span>
          </div>
        </div>
      )}

      {/* Transaction Summary */}
      {mappedTransactions.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-card border border-slate-border rounded-xl p-4">
            <div className="flex items-center gap-2 text-slate-muted text-sm mb-1">
              <CreditCard className="w-4 h-4" />
              Total Transactions
            </div>
            <p className="text-2xl font-bold text-foreground">{mappedTransactions.length}</p>
          </div>

          <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
            <p className="text-green-400 text-sm mb-1">Deposits</p>
            <p className="text-xl font-bold text-green-400">
              {formatCurrency(
                mappedTransactions.filter((t) => t.transaction_type === 'deposit').reduce((acc, t) => acc + t.amount, 0)
              )}
            </p>
            <p className="text-green-400/70 text-xs mt-1">
              {mappedTransactions.filter((t) => t.transaction_type === 'deposit').length} transactions
            </p>
          </div>

          <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
            <p className="text-blue-400 text-sm mb-1">Withdrawals</p>
            <p className="text-xl font-bold text-blue-400">
              {formatCurrency(
                mappedTransactions.filter((t) => t.transaction_type === 'withdrawal').reduce((acc, t) => acc + t.amount, 0)
              )}
            </p>
            <p className="text-blue-400/70 text-xs mt-1">
              {mappedTransactions.filter((t) => t.transaction_type === 'withdrawal').length} transactions
            </p>
          </div>

          <div className="bg-slate-card border border-slate-border rounded-xl p-4">
            <p className="text-slate-muted text-sm mb-1">Net Change</p>
            {(() => {
              const net =
                mappedTransactions.filter((t) => t.transaction_type === 'deposit').reduce((acc, t) => acc + t.amount, 0) -
                mappedTransactions.filter((t) => t.transaction_type === 'withdrawal').reduce((acc, t) => acc + t.amount, 0);
              return (
                <p className={cn('text-xl font-bold', net >= 0 ? 'text-green-400' : 'text-coral-alert')}>
                  {formatCurrency(net)}
                </p>
              );
            })()}
          </div>
        </div>
      )}

      {/* Preview Table */}
      {previewTransactions.length > 0 && (
        <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
          <div className="p-4 border-b border-slate-border">
            <h3 className="text-foreground font-medium">Transaction Preview</h3>
            <p className="text-slate-muted text-sm">
              Showing first {previewTransactions.length} of {mappedTransactions.length} transactions
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-elevated">
                  <th className="text-left text-slate-muted font-medium px-4 py-3">Date</th>
                  <th className="text-left text-slate-muted font-medium px-4 py-3">Type</th>
                  <th className="text-right text-slate-muted font-medium px-4 py-3">Amount</th>
                  <th className="text-left text-slate-muted font-medium px-4 py-3">Description</th>
                  <th className="text-left text-slate-muted font-medium px-4 py-3">Reference</th>
                </tr>
              </thead>
              <tbody>
                {previewTransactions.map((tx, index) => (
                  <tr key={index} className="border-t border-slate-border">
                    <td className="px-4 py-3 text-foreground">{formatDate(tx.transaction_date)}</td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                          tx.transaction_type === 'deposit'
                            ? 'bg-green-500/10 text-green-400 border border-green-500/30'
                            : 'bg-blue-500/10 text-blue-400 border border-blue-500/30'
                        )}
                      >
                        {tx.transaction_type === 'deposit' ? 'Deposit' : 'Withdrawal'}
                      </span>
                    </td>
                    <td
                      className={cn(
                        'px-4 py-3 text-right font-mono',
                        tx.transaction_type === 'deposit' ? 'text-green-400' : 'text-blue-400'
                      )}
                    >
                      {formatCurrency(tx.amount)}
                    </td>
                    <td className="px-4 py-3 text-slate-muted max-w-[200px] truncate">{tx.description || '-'}</td>
                    <td className="px-4 py-3 text-slate-muted font-mono text-xs">{tx.reference_number || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default OFXPreview;
