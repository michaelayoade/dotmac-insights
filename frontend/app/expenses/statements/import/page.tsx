'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Upload,
  FileSpreadsheet,
  ArrowLeft,
  ArrowRight,
  Check,
  X,
  AlertTriangle,
  Loader2,
  MapPin,
  Eye,
  CheckCircle,
  Calendar,
  DollarSign,
  Building2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useCorporateCards, useStatementMutations } from '@/hooks/useExpenses';
import type { CorporateCardTransactionCreatePayload } from '@/lib/expenses.types';
import { LoadingState, Button } from '@/components/ui';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

type Step = 'upload' | 'mapping' | 'preview' | 'importing';

interface ParsedRow {
  [key: string]: string;
}

interface ColumnMapping {
  transaction_date: string;
  amount: string;
  merchant_name: string;
  description: string;
  transaction_reference: string;
  posting_date?: string;
  original_amount?: string;
  original_currency?: string;
}

const REQUIRED_FIELDS = ['transaction_date', 'amount'] as const;
const OPTIONAL_FIELDS = ['merchant_name', 'description', 'transaction_reference', 'posting_date', 'original_amount', 'original_currency'] as const;

const FIELD_LABELS: Record<string, string> = {
  transaction_date: 'Transaction Date',
  amount: 'Amount',
  merchant_name: 'Merchant Name',
  description: 'Description',
  transaction_reference: 'Reference',
  posting_date: 'Posting Date',
  original_amount: 'Original Amount',
  original_currency: 'Original Currency',
};

function parseCSV(text: string): { headers: string[]; rows: ParsedRow[] } {
  const lines = text.trim().split('\n');
  if (lines.length < 2) {
    return { headers: [], rows: [] };
  }

  // Parse header
  const headers = parseCSVLine(lines[0]);

  // Parse rows
  const rows: ParsedRow[] = [];
  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVLine(lines[i]);
    if (values.length === headers.length) {
      const row: ParsedRow = {};
      headers.forEach((h, idx) => {
        row[h] = values[idx];
      });
      rows.push(row);
    }
  }

  return { headers, rows };
}

function parseCSVLine(line: string): string[] {
  const result: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === ',' && !inQuotes) {
      result.push(current.trim());
      current = '';
    } else {
      current += char;
    }
  }
  result.push(current.trim());
  return result;
}

function parseDate(value: string): string | null {
  if (!value) return null;

  // Try common date formats
  const formats = [
    /^(\d{4})-(\d{2})-(\d{2})/, // YYYY-MM-DD
    /^(\d{2})\/(\d{2})\/(\d{4})/, // DD/MM/YYYY or MM/DD/YYYY
    /^(\d{2})-(\d{2})-(\d{4})/, // DD-MM-YYYY
  ];

  for (const format of formats) {
    const match = value.match(format);
    if (match) {
      // Assume YYYY-MM-DD if first group is 4 digits
      if (match[1].length === 4) {
        return `${match[1]}-${match[2]}-${match[3]}`;
      }
      // Otherwise assume DD/MM/YYYY format
      return `${match[3]}-${match[2]}-${match[1]}`;
    }
  }

  // Try native Date parsing as fallback
  const date = new Date(value);
  if (!isNaN(date.getTime())) {
    return date.toISOString().split('T')[0];
  }

  return null;
}

function parseAmount(value: string): number | null {
  if (!value) return null;
  // Remove currency symbols, commas, spaces
  const cleaned = value.replace(/[^0-9.-]/g, '');
  const num = parseFloat(cleaned);
  return isNaN(num) ? null : num;
}

export default function StatementImportPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('expenses:write');
  const router = useRouter();
  const [step, setStep] = useState<Step>('upload');
  const [file, setFile] = useState<File | null>(null);
  const [csvData, setCsvData] = useState<{ headers: string[]; rows: ParsedRow[] }>({ headers: [], rows: [] });
  const [mapping, setMapping] = useState<Partial<ColumnMapping>>({});
  const [cardId, setCardId] = useState<number | null>(null);
  const [periodStart, setPeriodStart] = useState('');
  const [periodEnd, setPeriodEnd] = useState('');
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [parseErrors, setParseErrors] = useState<string[]>([]);

  const canFetch = !authLoading && !missingScope;
  const { data: cards } = useCorporateCards({}, { isPaused: () => !canFetch });
  const { importStatement } = useStatementMutations();

  const handleFileSelect = useCallback(async (selectedFile: File) => {
    setFile(selectedFile);
    setImportError(null);

    try {
      const text = await selectedFile.text();
      const parsed = parseCSV(text);

      if (parsed.headers.length === 0) {
        setImportError('Could not parse CSV file. Please check the format.');
        return;
      }

      setCsvData(parsed);

      // Auto-map columns based on header names
      const autoMapping: Partial<ColumnMapping> = {};
      const headerLower = parsed.headers.map(h => h.toLowerCase());

      // Try to auto-detect columns
      const mappings: [keyof ColumnMapping, string[]][] = [
        ['transaction_date', ['date', 'transaction date', 'trans date', 'txn date', 'posted']],
        ['amount', ['amount', 'transaction amount', 'debit', 'value']],
        ['merchant_name', ['merchant', 'merchant name', 'vendor', 'payee', 'description']],
        ['description', ['description', 'memo', 'narrative', 'details']],
        ['transaction_reference', ['reference', 'ref', 'transaction id', 'auth code']],
        ['posting_date', ['posting date', 'post date', 'settled']],
        ['original_amount', ['original amount', 'foreign amount']],
        ['original_currency', ['original currency', 'foreign currency', 'currency']],
      ];

      for (const [field, keywords] of mappings) {
        for (const keyword of keywords) {
          const idx = headerLower.findIndex(h => h.includes(keyword));
          if (idx !== -1 && !Object.values(autoMapping).includes(parsed.headers[idx])) {
            autoMapping[field] = parsed.headers[idx];
            break;
          }
        }
      }

      setMapping(autoMapping);
      setStep('mapping');
    } catch (err) {
      setImportError('Failed to read file');
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && (droppedFile.name.endsWith('.csv') || droppedFile.type === 'text/csv')) {
      handleFileSelect(droppedFile);
    } else {
      setImportError('Please upload a CSV file');
    }
  }, [handleFileSelect]);

  const validateMapping = (): boolean => {
    return REQUIRED_FIELDS.every(field => mapping[field]);
  };

  const parseTransactions = (): { transactions: CorporateCardTransactionCreatePayload[]; errors: string[] } => {
    const transactions: CorporateCardTransactionCreatePayload[] = [];
    const errors: string[] = [];

    csvData.rows.forEach((row, idx) => {
      const rowNum = idx + 2; // Account for header row and 0-indexing

      // Parse date
      const dateValue = mapping.transaction_date ? row[mapping.transaction_date] : '';
      const parsedDate = parseDate(dateValue);
      if (!parsedDate) {
        errors.push(`Row ${rowNum}: Invalid date "${dateValue}"`);
        return;
      }

      // Parse amount
      const amountValue = mapping.amount ? row[mapping.amount] : '';
      const parsedAmount = parseAmount(amountValue);
      if (parsedAmount === null) {
        errors.push(`Row ${rowNum}: Invalid amount "${amountValue}"`);
        return;
      }

      const txn: CorporateCardTransactionCreatePayload = {
        card_id: cardId!,
        transaction_date: parsedDate,
        amount: parsedAmount,
        merchant_name: mapping.merchant_name ? row[mapping.merchant_name] : undefined,
        description: mapping.description ? row[mapping.description] : undefined,
        transaction_reference: mapping.transaction_reference ? row[mapping.transaction_reference] : undefined,
      };

      // Optional fields
      if (mapping.posting_date && row[mapping.posting_date]) {
        const postDate = parseDate(row[mapping.posting_date]);
        if (postDate) txn.posting_date = postDate;
      }

      if (mapping.original_amount && row[mapping.original_amount]) {
        const origAmount = parseAmount(row[mapping.original_amount]);
        if (origAmount !== null) txn.original_amount = origAmount;
      }

      if (mapping.original_currency && row[mapping.original_currency]) {
        txn.original_currency = row[mapping.original_currency];
      }

      transactions.push(txn);
    });

    return { transactions, errors };
  };

  const handlePreview = () => {
    if (!validateMapping()) {
      setImportError('Please map all required fields');
      return;
    }
    if (!cardId) {
      setImportError('Please select a card');
      return;
    }
    if (!periodStart || !periodEnd) {
      setImportError('Please enter statement period dates');
      return;
    }

    const { errors } = parseTransactions();
    setParseErrors(errors);
    setStep('preview');
  };

  const handleImport = async () => {
    if (!cardId) return;

    setImporting(true);
    setImportError(null);

    try {
      const { transactions, errors } = parseTransactions();

      if (transactions.length === 0) {
        setImportError('No valid transactions to import');
        setImporting(false);
        return;
      }

      await importStatement({
        card_id: cardId,
        period_start: periodStart,
        period_end: periodEnd,
        import_source: 'csv_upload',
        original_filename: file?.name,
        transactions,
      });

      router.push('/expenses/statements');
    } catch (err) {
      setImportError(err instanceof Error ? err.message : 'Import failed');
    } finally {
      setImporting(false);
    }
  };

  const { transactions: parsedTransactions } = step === 'preview' ? parseTransactions() : { transactions: [] };

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the expenses:write permission to import statements."
        backHref="/expenses/statements"
        backLabel="Back to Statements"
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          href="/expenses/statements"
          className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-violet-500/10 border border-violet-500/30 flex items-center justify-center">
            <Upload className="w-5 h-5 text-violet-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Import Statement</h1>
            <p className="text-slate-muted text-sm">Upload CSV bank statement</p>
          </div>
        </div>
      </div>

      {/* Progress Steps */}
      <div className="flex items-center justify-center gap-2">
        {(['upload', 'mapping', 'preview', 'importing'] as Step[]).map((s, idx) => (
          <div key={s} className="flex items-center">
            <div
              className={cn(
                'w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors',
                step === s
                  ? 'bg-violet-500 text-foreground'
                  : ['upload', 'mapping', 'preview', 'importing'].indexOf(step) > idx
                  ? 'bg-emerald-500/20 text-emerald-400'
                  : 'bg-slate-elevated text-slate-muted'
              )}
            >
              {['upload', 'mapping', 'preview', 'importing'].indexOf(step) > idx ? (
                <Check className="w-4 h-4" />
              ) : (
                idx + 1
              )}
            </div>
            {idx < 3 && (
              <div
                className={cn(
                  'w-12 h-0.5 mx-1',
                  ['upload', 'mapping', 'preview', 'importing'].indexOf(step) > idx
                    ? 'bg-emerald-500/50'
                    : 'bg-slate-border'
                )}
              />
            )}
          </div>
        ))}
      </div>

      {/* Error Display */}
      {importError && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-400 flex-shrink-0" />
          <p className="text-sm text-rose-400">{importError}</p>
          <Button onClick={() => setImportError(null)} className="ml-auto text-rose-400 hover:text-rose-300">
            <X className="w-4 h-4" />
          </Button>
        </div>
      )}

      {/* Step Content */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-6">
        {/* Step 1: Upload */}
        {step === 'upload' && (
          <div className="space-y-6">
            <div className="text-center">
              <FileSpreadsheet className="w-12 h-12 text-violet-400 mx-auto mb-3" />
              <h2 className="text-lg font-semibold text-foreground">Upload Bank Statement</h2>
              <p className="text-sm text-slate-muted mt-1">CSV format with transaction data</p>
            </div>

            <div
              onDrop={handleDrop}
              onDragOver={(e) => e.preventDefault()}
              onClick={() => document.getElementById('csv-upload')?.click()}
              className="border-2 border-dashed border-slate-border hover:border-violet-400/50 rounded-xl p-12 cursor-pointer transition-colors text-center"
            >
              <input
                id="csv-upload"
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
              />
              <Upload className="w-10 h-10 text-slate-muted mx-auto mb-3" />
              <p className="text-foreground font-medium">Drop CSV file here or click to browse</p>
              <p className="text-xs text-slate-muted mt-2">Supports standard bank statement CSV exports</p>
            </div>
          </div>
        )}

        {/* Step 2: Column Mapping */}
        {step === 'mapping' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
                  <MapPin className="w-5 h-5 text-violet-400" />
                  Map Columns
                </h2>
                <p className="text-sm text-slate-muted mt-1">
                  Found {csvData.rows.length} rows with {csvData.headers.length} columns
                </p>
              </div>
              <span className="text-xs text-slate-muted">{file?.name}</span>
            </div>

            {/* Card & Period Selection */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bg-slate-elevated rounded-lg">
              <div>
                <label className="block text-sm text-slate-muted mb-1">Corporate Card *</label>
                <select
                  value={cardId || ''}
                  onChange={(e) => setCardId(e.target.value ? Number(e.target.value) : null)}
                  className="w-full bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                >
                  <option value="">Select card...</option>
                  {cards?.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.card_name} (****{c.card_number_last4})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-slate-muted mb-1">Period Start *</label>
                <input
                  type="date"
                  value={periodStart}
                  onChange={(e) => setPeriodStart(e.target.value)}
                  className="w-full bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-muted mb-1">Period End *</label>
                <input
                  type="date"
                  value={periodEnd}
                  onChange={(e) => setPeriodEnd(e.target.value)}
                  className="w-full bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                />
              </div>
            </div>

            {/* Column Mapping */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[...REQUIRED_FIELDS, ...OPTIONAL_FIELDS].map((field) => (
                <div key={field}>
                  <label className="block text-sm text-slate-muted mb-1">
                    {FIELD_LABELS[field]}
                    {REQUIRED_FIELDS.includes(field as any) && <span className="text-rose-400 ml-1">*</span>}
                  </label>
                  <select
                    value={mapping[field as keyof ColumnMapping] || ''}
                    onChange={(e) =>
                      setMapping((prev) => ({
                        ...prev,
                        [field]: e.target.value || undefined,
                      }))
                    }
                    className={cn(
                      'w-full bg-slate-elevated border rounded-lg px-3 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50',
                      mapping[field as keyof ColumnMapping]
                        ? 'border-emerald-500/50'
                        : REQUIRED_FIELDS.includes(field as any)
                        ? 'border-rose-500/50'
                        : 'border-slate-border'
                    )}
                  >
                    <option value="">-- Select column --</option>
                    {csvData.headers.map((h) => (
                      <option key={h} value={h}>
                        {h}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>

            {/* Sample Data Preview */}
            <div>
              <h3 className="text-sm font-medium text-slate-muted mb-2">Sample Data (first 3 rows)</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-slate-elevated">
                      {csvData.headers.map((h) => (
                        <th key={h} className="px-2 py-1 text-left text-slate-muted font-medium">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {csvData.rows.slice(0, 3).map((row, idx) => (
                      <tr key={idx} className="border-t border-slate-border">
                        {csvData.headers.map((h) => (
                          <td key={h} className="px-2 py-1 text-foreground">
                            {row[h]}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="flex justify-between pt-4">
              <Button
                onClick={() => {
                  setStep('upload');
                  setCsvData({ headers: [], rows: [] });
                  setFile(null);
                }}
                className="px-4 py-2 text-slate-muted hover:text-foreground transition-colors"
              >
                Back
              </Button>
              <Button
                onClick={handlePreview}
                disabled={!validateMapping() || !cardId || !periodStart || !periodEnd}
                className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 text-foreground text-sm font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Preview <ArrowRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}

        {/* Step 3: Preview */}
        {step === 'preview' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
                  <Eye className="w-5 h-5 text-violet-400" />
                  Review Transactions
                </h2>
                <p className="text-sm text-slate-muted mt-1">
                  {parsedTransactions.length} transactions ready to import
                </p>
              </div>
              {parseErrors.length > 0 && (
                <span className="px-2 py-1 bg-amber-500/10 text-amber-400 text-xs rounded">
                  {parseErrors.length} rows skipped
                </span>
              )}
            </div>

            {/* Parse Errors */}
            {parseErrors.length > 0 && (
              <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
                <p className="text-sm text-amber-400 font-medium mb-2">Skipped Rows:</p>
                <ul className="text-xs text-amber-300 space-y-1 max-h-24 overflow-y-auto">
                  {parseErrors.map((err, idx) => (
                    <li key={idx}>{err}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Summary */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-slate-elevated rounded-lg p-3">
                <p className="text-xs text-slate-muted">Transactions</p>
                <p className="text-xl font-bold text-foreground">{parsedTransactions.length}</p>
              </div>
              <div className="bg-slate-elevated rounded-lg p-3">
                <p className="text-xs text-slate-muted">Total Amount</p>
                <p className="text-xl font-bold text-foreground">
                  {parsedTransactions.reduce((sum, t) => sum + t.amount, 0).toLocaleString()}
                </p>
              </div>
              <div className="bg-slate-elevated rounded-lg p-3">
                <p className="text-xs text-slate-muted">Period</p>
                <p className="text-sm font-medium text-foreground">
                  {periodStart} to {periodEnd}
                </p>
              </div>
              <div className="bg-slate-elevated rounded-lg p-3">
                <p className="text-xs text-slate-muted">Card</p>
                <p className="text-sm font-medium text-foreground">
                  {cards?.find((c) => c.id === cardId)?.card_name || `Card #${cardId}`}
                </p>
              </div>
            </div>

            {/* Transaction List */}
            <div className="max-h-80 overflow-y-auto border border-slate-border rounded-lg">
              <table className="w-full text-sm">
                <thead className="bg-slate-elevated sticky top-0">
                  <tr className="text-left text-slate-muted">
                    <th className="px-3 py-2">Date</th>
                    <th className="px-3 py-2">Merchant</th>
                    <th className="px-3 py-2">Description</th>
                    <th className="px-3 py-2 text-right">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-border">
                  {parsedTransactions.slice(0, 50).map((txn, idx) => (
                    <tr key={idx} className="bg-slate-card hover:bg-slate-elevated/50">
                      <td className="px-3 py-2 text-foreground">{txn.transaction_date}</td>
                      <td className="px-3 py-2 text-foreground">{txn.merchant_name || '-'}</td>
                      <td className="px-3 py-2 text-slate-muted truncate max-w-xs">
                        {txn.description || '-'}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-foreground">
                        {txn.amount.toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {parsedTransactions.length > 50 && (
                <p className="text-center text-xs text-slate-muted py-2">
                  Showing 50 of {parsedTransactions.length} transactions
                </p>
              )}
            </div>

            <div className="flex justify-between pt-4">
              <Button
                onClick={() => setStep('mapping')}
                className="px-4 py-2 text-slate-muted hover:text-foreground transition-colors"
              >
                Back
              </Button>
              <Button
                onClick={handleImport}
                disabled={importing || parsedTransactions.length === 0}
                className="flex items-center gap-2 px-6 py-2 bg-emerald-600 hover:bg-emerald-700 text-foreground text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
              >
                {importing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Importing...
                  </>
                ) : (
                  <>
                    <CheckCircle className="w-4 h-4" />
                    Import {parsedTransactions.length} Transactions
                  </>
                )}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}