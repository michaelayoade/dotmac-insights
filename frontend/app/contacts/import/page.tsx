'use client';

import { useState, useCallback } from 'react';
import Link from 'next/link';
import {
  FileUp,
  Upload,
  FileText,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Users,
  ArrowRight,
  Download,
  Table,
  Loader2,
} from 'lucide-react';
import { fetchApi } from '@/lib/api/core';
import { PageHeader } from '@/components/ui';
import { cn } from '@/lib/utils';

type ImportStep = 'upload' | 'preview' | 'mapping' | 'importing' | 'complete';

interface ParsedRow {
  name?: string;
  email?: string;
  phone?: string;
  company_name?: string;
  contact_type?: string;
  category?: string;
  city?: string;
  state?: string;
  country?: string;
  notes?: string;
  tags?: string;
  source?: string;
  [key: string]: string | undefined;
}

interface ImportResult {
  total_submitted: number;
  created: number;
  skipped: number;
  errors: Array<{ row: number; name: string; error: string }>;
}

const REQUIRED_FIELDS = ['name'];
const OPTIONAL_FIELDS = [
  'email',
  'phone',
  'company_name',
  'contact_type',
  'category',
  'city',
  'state',
  'country',
  'notes',
  'tags',
  'source',
];

export default function ImportPage() {
  const [step, setStep] = useState<ImportStep>('upload');
  const [file, setFile] = useState<File | null>(null);
  const [parsedData, setParsedData] = useState<ParsedRow[]>([]);
  const [headers, setHeaders] = useState<string[]>([]);
  const [fieldMapping, setFieldMapping] = useState<Record<string, string>>({});
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Import options
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const [duplicateCheckField, setDuplicateCheckField] = useState<'email' | 'phone' | 'name'>('email');
  const [defaultSource, setDefaultSource] = useState('CSV Import');

  const parseCSV = useCallback((text: string) => {
    const lines = text.trim().split('\n');
    if (lines.length < 2) {
      throw new Error('CSV must have at least a header row and one data row');
    }

    const headerLine = lines[0];
    const csvHeaders = headerLine.split(',').map((h) => h.trim().replace(/^"|"$/g, '').toLowerCase());
    setHeaders(csvHeaders);

    // Auto-map fields
    const mapping: Record<string, string> = {};
    csvHeaders.forEach((header) => {
      const normalizedHeader = header.toLowerCase().replace(/[_\s-]/g, '');
      if (normalizedHeader.includes('name') && !normalizedHeader.includes('company')) {
        mapping['name'] = header;
      } else if (normalizedHeader.includes('email')) {
        mapping['email'] = header;
      } else if (normalizedHeader.includes('phone') || normalizedHeader.includes('mobile')) {
        mapping['phone'] = header;
      } else if (normalizedHeader.includes('company') || normalizedHeader.includes('organization')) {
        mapping['company_name'] = header;
      } else if (normalizedHeader.includes('city')) {
        mapping['city'] = header;
      } else if (normalizedHeader.includes('state') || normalizedHeader.includes('region')) {
        mapping['state'] = header;
      } else if (normalizedHeader.includes('country')) {
        mapping['country'] = header;
      } else if (normalizedHeader.includes('type')) {
        mapping['contact_type'] = header;
      } else if (normalizedHeader.includes('category')) {
        mapping['category'] = header;
      } else if (normalizedHeader.includes('notes') || normalizedHeader.includes('comment')) {
        mapping['notes'] = header;
      } else if (normalizedHeader.includes('source')) {
        mapping['source'] = header;
      } else if (normalizedHeader.includes('tag')) {
        mapping['tags'] = header;
      }
    });
    setFieldMapping(mapping);

    // Parse data rows
    const rows: ParsedRow[] = [];
    for (let i = 1; i < lines.length; i++) {
      const values = lines[i].split(',').map((v) => v.trim().replace(/^"|"$/g, ''));
      const row: ParsedRow = {};
      csvHeaders.forEach((header, idx) => {
        row[header] = values[idx] || '';
      });
      if (Object.values(row).some((v) => v)) {
        rows.push(row);
      }
    }

    return rows;
  }, []);

  const handleFileSelect = useCallback(
    (selectedFile: File) => {
      setFile(selectedFile);
      setError(null);

      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const text = e.target?.result as string;
          const rows = parseCSV(text);
          setParsedData(rows);
          setStep('preview');
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Failed to parse CSV file');
        }
      };
      reader.onerror = () => {
        setError('Failed to read file');
      };
      reader.readAsText(selectedFile);
    },
    [parseCSV]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile && droppedFile.name.endsWith('.csv')) {
        handleFileSelect(droppedFile);
      } else {
        setError('Please upload a CSV file');
      }
    },
    [handleFileSelect]
  );

  const handleImport = async () => {
    setImporting(true);
    setError(null);

    try {
      // Map parsed data to import format
      const contacts = parsedData.map((row) => {
        const mapped: Record<string, string | string[] | undefined> = {};
        Object.entries(fieldMapping).forEach(([targetField, sourceHeader]) => {
          if (sourceHeader && row[sourceHeader]) {
            if (targetField === 'tags') {
              mapped[targetField] = row[sourceHeader]?.split(',').map((t) => t.trim()) || [];
            } else {
              mapped[targetField] = row[sourceHeader];
            }
          }
        });
        return mapped;
      });

      const importResult = await fetchApi<ImportResult>('/contacts/import', {
        method: 'POST',
        body: JSON.stringify({
          contacts,
          skip_duplicates: skipDuplicates,
          duplicate_check_field: duplicateCheckField,
          default_source: defaultSource,
        }),
      });
      setResult(importResult);
      setStep('complete');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed');
    } finally {
      setImporting(false);
    }
  };

  const resetImport = () => {
    setStep('upload');
    setFile(null);
    setParsedData([]);
    setHeaders([]);
    setFieldMapping({});
    setResult(null);
    setError(null);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Import Contacts"
        subtitle="Bulk upload contacts from CSV file"
        icon={FileUp}
        iconClassName="bg-blue-500/10 border border-blue-500/30"
        actions={
          step !== 'upload' && step !== 'complete' && (
            <button
              onClick={resetImport}
              className="text-slate-muted text-sm hover:text-white transition-colors"
            >
              Start Over
            </button>
          )
        }
      />

      {/* Progress Steps */}
      <div className="bg-slate-card rounded-xl border border-slate-border p-4">
        <div className="flex items-center justify-between">
          {['upload', 'preview', 'mapping', 'importing', 'complete'].map((s, idx) => (
            <div key={s} className="flex items-center">
              <div
                className={cn(
                  'w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium',
                  step === s
                    ? 'bg-blue-500 text-white'
                    : ['upload', 'preview', 'mapping', 'importing', 'complete'].indexOf(step) > idx
                      ? 'bg-emerald-500 text-white'
                      : 'bg-slate-elevated text-slate-muted'
                )}
              >
                {['upload', 'preview', 'mapping', 'importing', 'complete'].indexOf(step) > idx ? (
                  <CheckCircle className="w-4 h-4" />
                ) : (
                  idx + 1
                )}
              </div>
              <span
                className={cn(
                  'ml-2 text-sm hidden md:inline',
                  step === s ? 'text-white' : 'text-slate-muted'
                )}
              >
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </span>
              {idx < 4 && (
                <ArrowRight className="w-4 h-4 text-slate-muted mx-4 hidden md:block" />
              )}
            </div>
          ))}
        </div>
      </div>

      {error && (
        <div className="bg-red-500/20 border border-red-500/30 rounded-lg p-4 flex items-center gap-3">
          <XCircle className="w-5 h-5 text-red-400" />
          <span className="text-red-400">{error}</span>
        </div>
      )}

      {/* Step: Upload */}
      {step === 'upload' && (
        <div className="space-y-6">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            className={cn(
              'border-2 border-dashed rounded-xl p-12 text-center transition-colors',
              dragOver
                ? 'border-blue-500 bg-blue-500/10'
                : 'border-slate-border hover:border-slate-muted'
            )}
          >
            <Upload className="w-12 h-12 text-slate-muted mx-auto mb-4" />
            <h3 className="text-white font-semibold mb-2">Drop your CSV file here</h3>
            <p className="text-slate-muted text-sm mb-4">or click to browse</p>
            <input
              type="file"
              accept=".csv"
              onChange={(e) => {
                const selectedFile = e.target.files?.[0];
                if (selectedFile) handleFileSelect(selectedFile);
              }}
              className="hidden"
              id="file-upload"
            />
            <label
              htmlFor="file-upload"
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-400 transition-colors cursor-pointer"
            >
              <FileText className="w-4 h-4" />
              Select CSV File
            </label>
          </div>

          {/* Template Download */}
          <div className="bg-slate-card rounded-xl border border-slate-border p-5">
            <div className="flex items-center gap-2 mb-4">
              <Download className="w-4 h-4 text-blue-400" />
              <h3 className="text-white font-semibold">Download Template</h3>
            </div>
            <p className="text-slate-muted text-sm mb-4">
              Use our template to ensure your data is formatted correctly.
            </p>
            <a
              href="data:text/csv;charset=utf-8,name,email,phone,company_name,contact_type,category,city,state,country,notes,tags,source%0AJohn Doe,john@example.com,+234 801 234 5678,Acme Corp,lead,business,Lagos,Lagos,Nigeria,Interested in enterprise plan,enterprise;priority,Website"
              download="contacts_template.csv"
              className="inline-flex items-center gap-2 px-4 py-2 bg-slate-elevated text-white rounded-lg hover:bg-slate-muted/20 transition-colors"
            >
              <Download className="w-4 h-4" />
              Download Template
            </a>

            <div className="mt-4 pt-4 border-t border-slate-border">
              <h4 className="text-white text-sm font-medium mb-2">Required Fields:</h4>
              <p className="text-slate-muted text-sm">name</p>

              <h4 className="text-white text-sm font-medium mt-3 mb-2">Optional Fields:</h4>
              <p className="text-slate-muted text-sm">
                email, phone, company_name, contact_type, category, city, state, country, notes, tags, source
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Step: Preview */}
      {step === 'preview' && (
        <div className="space-y-6">
          <div className="bg-slate-card rounded-xl border border-slate-border p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Table className="w-4 h-4 text-blue-400" />
                <h3 className="text-white font-semibold">Data Preview</h3>
              </div>
              <span className="text-slate-muted text-sm">{parsedData.length} rows found</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-border">
                    {headers.slice(0, 6).map((header) => (
                      <th key={header} className="text-left py-2 px-3 text-slate-muted font-medium">
                        {header}
                      </th>
                    ))}
                    {headers.length > 6 && (
                      <th className="text-left py-2 px-3 text-slate-muted font-medium">
                        +{headers.length - 6} more
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {parsedData.slice(0, 5).map((row, idx) => (
                    <tr key={idx} className="border-b border-slate-border/50">
                      {headers.slice(0, 6).map((header) => (
                        <td key={header} className="py-2 px-3 text-white">
                          {row[header] || '-'}
                        </td>
                      ))}
                      {headers.length > 6 && <td className="py-2 px-3 text-slate-muted">...</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {parsedData.length > 5 && (
              <p className="text-center text-slate-muted text-sm mt-4">
                Showing first 5 of {parsedData.length} rows
              </p>
            )}
          </div>

          <div className="flex justify-end gap-3">
            <button
              onClick={resetImport}
              className="px-4 py-2 text-slate-muted hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => setStep('mapping')}
              className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-400 transition-colors"
            >
              Continue to Mapping
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Step: Mapping */}
      {step === 'mapping' && (
        <div className="space-y-6">
          <div className="bg-slate-card rounded-xl border border-slate-border p-5">
            <div className="flex items-center gap-2 mb-4">
              <Table className="w-4 h-4 text-blue-400" />
              <h3 className="text-white font-semibold">Field Mapping</h3>
            </div>
            <p className="text-slate-muted text-sm mb-4">
              Match your CSV columns to contact fields. We've auto-detected some mappings.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[...REQUIRED_FIELDS, ...OPTIONAL_FIELDS].map((field) => (
                <div key={field} className="flex items-center gap-3">
                  <label className="w-32 text-sm text-slate-muted">
                    {field}
                    {REQUIRED_FIELDS.includes(field) && (
                      <span className="text-red-400 ml-1">*</span>
                    )}
                  </label>
                  <select
                    value={fieldMapping[field] || ''}
                    onChange={(e) =>
                      setFieldMapping((prev) => ({
                        ...prev,
                        [field]: e.target.value,
                      }))
                    }
                    className="flex-1 px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                  >
                    <option value="">-- Select column --</option>
                    {headers.map((header) => (
                      <option key={header} value={header}>
                        {header}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
          </div>

          {/* Import Options */}
          <div className="bg-slate-card rounded-xl border border-slate-border p-5">
            <h3 className="text-white font-semibold mb-4">Import Options</h3>

            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-white text-sm">Skip Duplicates</p>
                  <p className="text-slate-muted text-xs">Skip rows that match existing contacts</p>
                </div>
                <button
                  onClick={() => setSkipDuplicates(!skipDuplicates)}
                  className={cn(
                    'w-12 h-6 rounded-full transition-colors',
                    skipDuplicates ? 'bg-blue-500' : 'bg-slate-elevated'
                  )}
                >
                  <div
                    className={cn(
                      'w-5 h-5 rounded-full bg-white transition-transform',
                      skipDuplicates ? 'translate-x-6' : 'translate-x-0.5'
                    )}
                  />
                </button>
              </div>

              {skipDuplicates && (
                <div>
                  <label className="text-sm text-slate-muted block mb-2">
                    Check duplicates by:
                  </label>
                  <div className="flex gap-2">
                    {(['email', 'phone', 'name'] as const).map((field) => (
                      <button
                        key={field}
                        onClick={() => setDuplicateCheckField(field)}
                        className={cn(
                          'px-3 py-1 rounded text-sm transition-colors',
                          duplicateCheckField === field
                            ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                            : 'text-slate-muted hover:text-white bg-slate-elevated'
                        )}
                      >
                        {field}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <label className="text-sm text-slate-muted block mb-2">Default Source:</label>
                <input
                  type="text"
                  value={defaultSource}
                  onChange={(e) => setDefaultSource(e.target.value)}
                  className="w-full md:w-64 px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                  placeholder="e.g., CSV Import, Marketing Campaign"
                />
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-3">
            <button
              onClick={() => setStep('preview')}
              className="px-4 py-2 text-slate-muted hover:text-white transition-colors"
            >
              Back
            </button>
            <button
              onClick={() => {
                if (!fieldMapping['name']) {
                  setError('Please map the required "name" field');
                  return;
                }
                setStep('importing');
                handleImport();
              }}
              className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-400 transition-colors"
            >
              <Upload className="w-4 h-4" />
              Import {parsedData.length} Contacts
            </button>
          </div>
        </div>
      )}

      {/* Step: Importing */}
      {step === 'importing' && (
        <div className="bg-slate-card rounded-xl border border-slate-border p-12 text-center">
          <Loader2 className="w-12 h-12 text-blue-400 mx-auto mb-4 animate-spin" />
          <h3 className="text-white font-semibold mb-2">Importing Contacts</h3>
          <p className="text-slate-muted text-sm">Please wait while we process your data...</p>
        </div>
      )}

      {/* Step: Complete */}
      {step === 'complete' && result && (
        <div className="space-y-6">
          <div className="bg-slate-card rounded-xl border border-slate-border p-8 text-center">
            <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-4" />
            <h3 className="text-white font-semibold text-xl mb-2">Import Complete!</h3>
            <p className="text-slate-muted text-sm mb-6">
              Your contacts have been imported successfully.
            </p>

            <div className="grid grid-cols-3 gap-4 max-w-md mx-auto mb-6">
              <div className="bg-slate-elevated rounded-lg p-4">
                <p className="text-2xl font-bold text-emerald-400">{result.created}</p>
                <p className="text-xs text-slate-muted">Created</p>
              </div>
              <div className="bg-slate-elevated rounded-lg p-4">
                <p className="text-2xl font-bold text-amber-400">{result.skipped}</p>
                <p className="text-xs text-slate-muted">Skipped</p>
              </div>
              <div className="bg-slate-elevated rounded-lg p-4">
                <p className="text-2xl font-bold text-red-400">{result.errors.length}</p>
                <p className="text-xs text-slate-muted">Errors</p>
              </div>
            </div>

            <div className="flex justify-center gap-3">
              <button
                onClick={resetImport}
                className="px-4 py-2 bg-slate-elevated text-white rounded-lg hover:bg-slate-muted/20 transition-colors"
              >
                Import More
              </button>
              <Link
                href="/contacts/all"
                className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-400 transition-colors"
              >
                <Users className="w-4 h-4" />
                View Contacts
              </Link>
            </div>
          </div>

          {result.errors.length > 0 && (
            <div className="bg-slate-card rounded-xl border border-slate-border p-5">
              <div className="flex items-center gap-2 mb-4">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <h3 className="text-white font-semibold">Import Errors</h3>
              </div>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {result.errors.map((err, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between py-2 px-3 bg-slate-elevated rounded-lg text-sm"
                  >
                    <span className="text-white">
                      Row {err.row + 1}: {err.name}
                    </span>
                    <span className="text-red-400">{err.error}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
