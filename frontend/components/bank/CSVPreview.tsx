'use client';

import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import { AlertTriangle, Check } from 'lucide-react';
import type { CSVParseResult, CSVColumnMapping, MappedTransaction } from '@/lib/parsers/csv';
import { mapCSVToTransactions, validateMapping } from '@/lib/parsers/csv';

interface CSVPreviewProps {
  csvData: CSVParseResult;
  mapping: CSVColumnMapping;
  onMappingChange: (mapping: CSVColumnMapping) => void;
  previewCount?: number;
}

export function CSVPreview({ csvData, mapping, onMappingChange, previewCount = 5 }: CSVPreviewProps) {
  const { headers, rows, rowCount } = csvData;

  const validation = useMemo(() => validateMapping(mapping), [mapping]);

  const previewTransactions = useMemo(() => {
    if (!validation.valid) return [];
    return mapCSVToTransactions(rows.slice(0, previewCount), mapping);
  }, [rows, mapping, previewCount, validation.valid]);

  const handleMappingChange = (field: keyof CSVColumnMapping, value: string) => {
    const newMapping = { ...mapping, [field]: value || undefined };

    // If amount column is set, clear deposit/withdrawal columns
    if (field === 'amount_column' && value) {
      delete newMapping.deposit_column;
      delete newMapping.withdrawal_column;
    }

    // If deposit or withdrawal is set, clear amount column
    if ((field === 'deposit_column' || field === 'withdrawal_column') && value) {
      delete newMapping.amount_column;
    }

    onMappingChange(newMapping);
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-NG', {
      style: 'currency',
      currency: 'NGN',
      minimumFractionDigits: 2,
    }).format(value);
  };

  return (
    <div className="space-y-6">
      {/* Column Mapping */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <h3 className="text-white font-medium mb-4">Column Mapping</h3>
        <p className="text-slate-muted text-sm mb-4">
          Map your CSV columns to transaction fields. Found {rowCount} rows.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Date Column - Required */}
          <div className="space-y-1.5">
            <label className="block text-sm text-slate-muted">
              Date Column <span className="text-coral-alert">*</span>
            </label>
            <select
              value={mapping.date_column || ''}
              onChange={(e) => handleMappingChange('date_column', e.target.value)}
              className="input-field"
            >
              <option value="">Select column...</option>
              {headers.map((header) => (
                <option key={header} value={header}>
                  {header}
                </option>
              ))}
            </select>
          </div>

          {/* Amount Column - Option 1 */}
          <div className="space-y-1.5">
            <label className="block text-sm text-slate-muted">Amount Column</label>
            <select
              value={mapping.amount_column || ''}
              onChange={(e) => handleMappingChange('amount_column', e.target.value)}
              className="input-field"
              disabled={!!mapping.deposit_column || !!mapping.withdrawal_column}
            >
              <option value="">Select column...</option>
              {headers.map((header) => (
                <option key={header} value={header}>
                  {header}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-muted">Or use separate Deposit/Withdrawal columns</p>
          </div>

          {/* Description Column */}
          <div className="space-y-1.5">
            <label className="block text-sm text-slate-muted">Description Column</label>
            <select
              value={mapping.description_column || ''}
              onChange={(e) => handleMappingChange('description_column', e.target.value)}
              className="input-field"
            >
              <option value="">Select column...</option>
              {headers.map((header) => (
                <option key={header} value={header}>
                  {header}
                </option>
              ))}
            </select>
          </div>

          {/* Deposit Column - Option 2 */}
          <div className="space-y-1.5">
            <label className="block text-sm text-slate-muted">Deposit Column</label>
            <select
              value={mapping.deposit_column || ''}
              onChange={(e) => handleMappingChange('deposit_column', e.target.value)}
              className="input-field"
              disabled={!!mapping.amount_column}
            >
              <option value="">Select column...</option>
              {headers.map((header) => (
                <option key={header} value={header}>
                  {header}
                </option>
              ))}
            </select>
          </div>

          {/* Withdrawal Column - Option 2 */}
          <div className="space-y-1.5">
            <label className="block text-sm text-slate-muted">Withdrawal Column</label>
            <select
              value={mapping.withdrawal_column || ''}
              onChange={(e) => handleMappingChange('withdrawal_column', e.target.value)}
              className="input-field"
              disabled={!!mapping.amount_column}
            >
              <option value="">Select column...</option>
              {headers.map((header) => (
                <option key={header} value={header}>
                  {header}
                </option>
              ))}
            </select>
          </div>

          {/* Reference Column */}
          <div className="space-y-1.5">
            <label className="block text-sm text-slate-muted">Reference Column</label>
            <select
              value={mapping.reference_column || ''}
              onChange={(e) => handleMappingChange('reference_column', e.target.value)}
              className="input-field"
            >
              <option value="">Select column...</option>
              {headers.map((header) => (
                <option key={header} value={header}>
                  {header}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Validation Messages */}
        {!validation.valid && (
          <div className="mt-4 p-3 bg-coral-alert/10 border border-coral-alert/30 rounded-lg">
            <div className="flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-coral-alert mt-0.5" />
              <div className="text-sm text-coral-alert">
                {validation.errors.map((error, i) => (
                  <p key={i}>{error}</p>
                ))}
              </div>
            </div>
          </div>
        )}

        {validation.valid && (
          <div className="mt-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg">
            <div className="flex items-center gap-2 text-sm text-green-400">
              <Check className="w-4 h-4" />
              <span>Mapping is valid</span>
            </div>
          </div>
        )}
      </div>

      {/* Preview Table */}
      {validation.valid && previewTransactions.length > 0 && (
        <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
          <div className="p-4 border-b border-slate-border">
            <h3 className="text-white font-medium">Preview</h3>
            <p className="text-slate-muted text-sm">
              Showing first {previewTransactions.length} of {rowCount} transactions
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
                    <td className="px-4 py-3 text-white">{tx.transaction_date}</td>
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

      {/* Raw Data Preview */}
      <details className="bg-slate-card border border-slate-border rounded-xl">
        <summary className="p-4 cursor-pointer text-slate-muted text-sm hover:text-white transition-colors">
          View raw CSV data ({headers.length} columns)
        </summary>
        <div className="p-4 pt-0 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-slate-elevated">
                {headers.map((header) => (
                  <th key={header} className="text-left text-slate-muted font-medium px-3 py-2 whitespace-nowrap">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 5).map((row, index) => (
                <tr key={index} className="border-t border-slate-border">
                  {headers.map((header) => (
                    <td key={header} className="px-3 py-2 text-slate-muted whitespace-nowrap max-w-[150px] truncate">
                      {row[header] || '-'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}

export default CSVPreview;
