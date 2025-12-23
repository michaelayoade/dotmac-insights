'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { useAccountingBankAccounts, useBankTransactionMutations } from '@/hooks/useApi';
import { FileUpload } from '@/components/bank/FileUpload';
import { CSVPreview } from '@/components/bank/CSVPreview';
import { OFXPreview } from '@/components/bank/OFXPreview';
import { parseCSV, autoDetectMapping, validateMapping, mapCSVToTransactions } from '@/lib/parsers/csv';
import type { CSVParseResult, CSVColumnMapping } from '@/lib/parsers/csv';
import { parseOFX, validateOFXResult, mapOFXToTransactions } from '@/lib/parsers/ofx';
import type { OFXParseResult } from '@/lib/parsers/ofx';
import { Button, LinkButton } from '@/components/ui';
import {
  ArrowLeft,
  ArrowRight,
  Upload,
  FileText,
  Check,
  AlertTriangle,
  Loader2,
  CheckCircle,
  XCircle,
} from 'lucide-react';

type Step = 1 | 2 | 3 | 4;
type FileFormat = 'csv' | 'ofx' | null;

interface ImportState {
  step: Step;
  selectedFile: File | null;
  selectedAccount: string;
  fileFormat: FileFormat;
  csvData: CSVParseResult | null;
  ofxData: OFXParseResult | null;
  columnMapping: CSVColumnMapping;
  skipDuplicates: boolean;
  isImporting: boolean;
  importResult: {
    imported_count: number;
    skipped_count: number;
    errors: Array<{ row: number; error: string }>;
  } | null;
  error: string | null;
}

export default function ImportBankTransactionsPage() {
  const router = useRouter();
  const { data: bankAccountsData } = useAccountingBankAccounts();
  const { importTransactions } = useBankTransactionMutations();

  const [state, setState] = useState<ImportState>({
    step: 1,
    selectedFile: null,
    selectedAccount: '',
    fileFormat: null,
    csvData: null,
    ofxData: null,
    columnMapping: { date_column: '' },
    skipDuplicates: true,
    isImporting: false,
    importResult: null,
    error: null,
  });

  const bankAccounts = (bankAccountsData as any)?.accounts || [];

  const detectFileFormat = (filename: string): FileFormat => {
    const ext = filename.split('.').pop()?.toLowerCase();
    if (ext === 'csv') return 'csv';
    if (ext === 'ofx' || ext === 'qfx') return 'ofx';
    return null;
  };

  const handleFileSelect = useCallback(async (file: File) => {
    const format = detectFileFormat(file.name);
    if (!format) {
      setState((prev) => ({ ...prev, error: 'Unsupported file format' }));
      return;
    }

    setState((prev) => ({
      ...prev,
      selectedFile: file,
      fileFormat: format,
      error: null,
    }));

    // Parse file content
    try {
      const content = await file.text();

      if (format === 'csv') {
        const parsed = parseCSV(content);
        const autoMapping = autoDetectMapping(parsed.headers);
        setState((prev) => ({
          ...prev,
          csvData: parsed,
          columnMapping: { date_column: '', ...autoMapping },
        }));
      } else {
        const parsed = parseOFX(content);
        setState((prev) => ({
          ...prev,
          ofxData: parsed,
        }));
      }
    } catch (err) {
      setState((prev) => ({ ...prev, error: 'Failed to parse file' }));
    }
  }, []);

  const handleFileRemove = useCallback(() => {
    setState((prev) => ({
      ...prev,
      selectedFile: null,
      fileFormat: null,
      csvData: null,
      ofxData: null,
      columnMapping: { date_column: '' },
      error: null,
    }));
  }, []);

  const canProceedToStep2 = state.selectedFile && state.selectedAccount;

  const canProceedToStep3 = () => {
    if (state.fileFormat === 'csv') {
      return state.csvData && validateMapping(state.columnMapping).valid;
    }
    if (state.fileFormat === 'ofx') {
      return state.ofxData && validateOFXResult(state.ofxData).valid;
    }
    return false;
  };

  const getTransactionCount = () => {
    if (state.fileFormat === 'csv' && state.csvData) {
      const mapped = mapCSVToTransactions(state.csvData.rows, state.columnMapping);
      return mapped.length;
    }
    if (state.fileFormat === 'ofx' && state.ofxData) {
      return mapOFXToTransactions(state.ofxData).length;
    }
    return 0;
  };

  const handleImport = async () => {
    if (!state.selectedFile || !state.selectedAccount) return;

    setState((prev) => ({ ...prev, isImporting: true, error: null }));

    try {
      const formData = new FormData();
      formData.append('file', state.selectedFile);
      formData.append('account', state.selectedAccount);
      formData.append('format', state.fileFormat || 'csv');
      formData.append('skip_duplicates', String(state.skipDuplicates));

      if (state.fileFormat === 'csv') {
        formData.append('column_mapping', JSON.stringify(state.columnMapping));
      }

      const result = await importTransactions(formData);

      setState((prev) => ({
        ...prev,
        step: 4,
        importResult: result,
        isImporting: false,
      }));
    } catch (err: any) {
      setState((prev) => ({
        ...prev,
        error: err?.message || 'Import failed',
        isImporting: false,
      }));
    }
  };

  const renderStep1 = () => (
    <div className="space-y-6">
      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
        <h2 className="text-foreground font-medium">1. Select Bank Account</h2>
        <select
          value={state.selectedAccount}
          onChange={(e) => setState((prev) => ({ ...prev, selectedAccount: e.target.value }))}
          className="input-field"
        >
          <option value="">Select bank account...</option>
          {bankAccounts.map((acc: any) => (
            <option key={acc.name || acc.account_name} value={acc.name || acc.account_name}>
              {acc.account_name || acc.name} - {acc.bank || 'Unknown Bank'}
            </option>
          ))}
        </select>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
        <h2 className="text-foreground font-medium">2. Upload Statement File</h2>
        <FileUpload
          accept=".csv,.ofx,.qfx"
          maxSizeMB={10}
          onFileSelect={handleFileSelect}
          onFileRemove={handleFileRemove}
          selectedFile={state.selectedFile}
          error={state.error || undefined}
        />
      </div>

      <div className="flex justify-end">
        <Button
          onClick={() => setState((prev) => ({ ...prev, step: 2 }))}
          disabled={!canProceedToStep2}
          module="books"
          icon={ArrowRight}
          iconPosition="right"
        >
          Continue
        </Button>
      </div>
    </div>
  );

  const renderStep2 = () => (
    <div className="space-y-6">
      {state.fileFormat === 'csv' && state.csvData && (
        <CSVPreview
          csvData={state.csvData}
          mapping={state.columnMapping}
          onMappingChange={(mapping) => setState((prev) => ({ ...prev, columnMapping: mapping }))}
        />
      )}

      {state.fileFormat === 'ofx' && state.ofxData && <OFXPreview ofxData={state.ofxData} />}

      <div className="flex justify-between">
        <Button onClick={() => setState((prev) => ({ ...prev, step: 1 }))} variant="secondary" icon={ArrowLeft}>
          Back
        </Button>
        <Button
          onClick={() => setState((prev) => ({ ...prev, step: 3 }))}
          disabled={!canProceedToStep3()}
          module="books"
          icon={ArrowRight}
          iconPosition="right"
        >
          Continue
        </Button>
      </div>
    </div>
  );

  const renderStep3 = () => {
    const transactionCount = getTransactionCount();

    return (
      <div className="space-y-6">
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <h2 className="text-foreground font-medium text-lg mb-4">Confirm Import</h2>

          <div className="space-y-4">
            <div className="flex items-center justify-between py-3 border-b border-slate-border">
              <span className="text-slate-muted">File</span>
              <span className="text-foreground font-medium">{state.selectedFile?.name}</span>
            </div>
            <div className="flex items-center justify-between py-3 border-b border-slate-border">
              <span className="text-slate-muted">Bank Account</span>
              <span className="text-foreground font-medium">{state.selectedAccount}</span>
            </div>
            <div className="flex items-center justify-between py-3 border-b border-slate-border">
              <span className="text-slate-muted">Format</span>
              <span className="text-foreground font-medium uppercase">{state.fileFormat}</span>
            </div>
            <div className="flex items-center justify-between py-3 border-b border-slate-border">
              <span className="text-slate-muted">Transactions to Import</span>
              <span className="text-teal-electric font-bold text-xl">{transactionCount}</span>
            </div>
            <div className="flex items-center justify-between py-3">
              <div>
                <span className="text-slate-muted">Skip Duplicates</span>
                <p className="text-slate-muted text-xs mt-0.5">
                  Skip transactions that already exist based on date, amount, and reference
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={state.skipDuplicates}
                  onChange={(e) => setState((prev) => ({ ...prev, skipDuplicates: e.target.checked }))}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-slate-elevated peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-teal-electric"></div>
              </label>
            </div>
          </div>
        </div>

        {state.error && (
          <div className="bg-coral-alert/10 border border-coral-alert/30 rounded-xl p-4 flex items-center gap-2 text-coral-alert">
            <AlertTriangle className="w-5 h-5" />
            <span>{state.error}</span>
          </div>
        )}

        <div className="flex justify-between">
          <Button onClick={() => setState((prev) => ({ ...prev, step: 2 }))} disabled={state.isImporting} variant="secondary" icon={ArrowLeft}>
            Back
          </Button>
          <Button onClick={handleImport} disabled={state.isImporting} loading={state.isImporting} module="books" icon={Upload}>
            {state.isImporting ? 'Importing...' : 'Import Transactions'}
          </Button>
        </div>
      </div>
    );
  };

  const renderStep4 = () => {
    const result = state.importResult;
    const hasErrors = result && result.errors.length > 0;

    return (
      <div className="space-y-6">
        <div className="bg-slate-card border border-slate-border rounded-xl p-6 text-center">
          {result && result.imported_count > 0 ? (
            <>
              <CheckCircle className="w-16 h-16 text-green-400 mx-auto mb-4" />
              <h2 className="text-foreground font-bold text-2xl mb-2">Import Complete</h2>
              <p className="text-slate-muted">
                Successfully imported {result.imported_count} transaction(s)
              </p>
            </>
          ) : (
            <>
              <XCircle className="w-16 h-16 text-coral-alert mx-auto mb-4" />
              <h2 className="text-foreground font-bold text-2xl mb-2">Import Failed</h2>
              <p className="text-slate-muted">No transactions were imported</p>
            </>
          )}
        </div>

        {result && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4 text-center">
              <p className="text-green-400 text-sm mb-1">Imported</p>
              <p className="text-3xl font-bold text-green-400">{result.imported_count}</p>
            </div>
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 text-center">
              <p className="text-amber-400 text-sm mb-1">Skipped</p>
              <p className="text-3xl font-bold text-amber-400">{result.skipped_count}</p>
            </div>
            <div className="bg-coral-alert/10 border border-coral-alert/30 rounded-xl p-4 text-center">
              <p className="text-coral-alert text-sm mb-1">Errors</p>
              <p className="text-3xl font-bold text-coral-alert">{result.errors.length}</p>
            </div>
          </div>
        )}

        {hasErrors && (
          <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
            <div className="p-4 border-b border-slate-border">
              <h3 className="text-foreground font-medium">Error Details</h3>
            </div>
            <div className="max-h-48 overflow-y-auto">
              {result.errors.map((err, idx) => (
                <div
                  key={idx}
                  className="px-4 py-2 border-b border-slate-border last:border-0 flex items-center gap-3"
                >
                  <span className="text-slate-muted text-sm">Row {err.row}</span>
                  <span className="text-coral-alert text-sm">{err.error}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex justify-between">
          <Button
            onClick={() =>
              setState({
                step: 1,
                selectedFile: null,
                selectedAccount: '',
                fileFormat: null,
                csvData: null,
                ofxData: null,
                columnMapping: { date_column: '' },
                skipDuplicates: true,
                isImporting: false,
                importResult: null,
                error: null,
              })
            }
            variant="secondary"
            icon={Upload}
          >
            Import Another
          </Button>
          <LinkButton href="/books/bank-transactions" module="books" icon={ArrowRight} iconPosition="right">
            View Transactions
          </LinkButton>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          href="/books/bank-transactions"
          className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-foreground">Import Bank Transactions</h1>
          <p className="text-slate-muted text-sm">Import transactions from CSV or OFX files</p>
        </div>
      </div>

      {/* Progress Steps */}
      <div className="flex items-center justify-center gap-2">
        {[1, 2, 3, 4].map((step) => (
          <div key={step} className="flex items-center">
            <div
              className={cn(
                'w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors',
                state.step === step
                  ? 'bg-teal-electric text-foreground'
                  : state.step > step
                    ? 'bg-green-500 text-foreground'
                    : 'bg-slate-elevated text-slate-muted'
              )}
            >
              {state.step > step ? <Check className="w-4 h-4" /> : step}
            </div>
            {step < 4 && (
              <div
                className={cn(
                  'w-12 h-0.5 mx-1',
                  state.step > step ? 'bg-green-500' : 'bg-slate-border'
                )}
              />
            )}
          </div>
        ))}
      </div>

      {/* Step Labels */}
      <div className="flex justify-center gap-8 text-xs text-slate-muted">
        <span className={cn(state.step === 1 && 'text-teal-electric')}>Upload</span>
        <span className={cn(state.step === 2 && 'text-teal-electric')}>Preview</span>
        <span className={cn(state.step === 3 && 'text-teal-electric')}>Confirm</span>
        <span className={cn(state.step === 4 && 'text-teal-electric')}>Complete</span>
      </div>

      {/* Step Content */}
      {state.step === 1 && renderStep1()}
      {state.step === 2 && renderStep2()}
      {state.step === 3 && renderStep3()}
      {state.step === 4 && renderStep4()}
    </div>
  );
}
