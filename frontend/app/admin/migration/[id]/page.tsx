'use client';

import { useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Upload,
  FileSpreadsheet,
  CheckCircle,
  XCircle,
  Clock,
  Play,
  RotateCcw,
  Settings,
  Eye,
  AlertTriangle,
  ChevronRight,
  Check,
  X,
} from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useDropzone } from 'react-dropzone';
import {
  migrationApi,
  MigrationJobDetail,
  EntitySchemaResponse,
  MigrationStatus,
} from '@/lib/api/domains';

// Wizard steps
const STEPS = [
  { id: 'upload', label: 'Upload', description: 'Upload source file' },
  { id: 'mapping', label: 'Mapping', description: 'Map fields' },
  { id: 'cleaning', label: 'Cleaning', description: 'Configure cleaning' },
  { id: 'validate', label: 'Validate', description: 'Dry-run validation' },
  { id: 'execute', label: 'Execute', description: 'Run migration' },
];

function getActiveStep(status: MigrationStatus): number {
  switch (status) {
    case 'pending':
      return 0;
    case 'uploaded':
      return 1;
    case 'mapped':
      return 2;
    case 'validating':
    case 'validated':
      return 3;
    case 'running':
    case 'completed':
    case 'failed':
    case 'cancelled':
    case 'rolled_back':
      return 4;
    default:
      return 0;
  }
}

// Step 1: Upload
function UploadStep({ job, onRefresh }: { job: MigrationJobDetail; onRefresh: () => void }) {
  const uploadMutation = useMutation({
    mutationFn: (file: File) => migrationApi.uploadFile(job.id, file),
    onSuccess: onRefresh,
  });

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        uploadMutation.mutate(acceptedFiles[0]);
      }
    },
    [uploadMutation]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/json': ['.json'],
    },
    maxFiles: 1,
  });

  if (job.source_columns && job.source_columns.length > 0) {
    return (
      <div className="space-y-4">
        <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-5 h-5 text-green-500" />
            <span className="text-green-500 font-medium">File uploaded successfully</span>
          </div>
          <p className="text-slate-muted text-sm mt-1">
            {job.total_rows} rows, {job.source_columns.length} columns
          </p>
        </div>
        <div>
          <h4 className="text-sm font-medium text-foreground mb-2">Detected Columns</h4>
          <div className="flex flex-wrap gap-2">
            {job.source_columns.map((col) => (
              <span key={col} className="px-2 py-1 bg-slate-700 rounded text-xs text-foreground">
                {col}
              </span>
            ))}
          </div>
        </div>
        {job.sample_rows && job.sample_rows.length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-foreground mb-2">Sample Data</h4>
            <div className="overflow-x-auto">
              <table className="min-w-full text-xs">
                <thead>
                  <tr className="border-b border-slate-border">
                    {job.source_columns.slice(0, 6).map((col) => (
                      <th key={col} className="text-left py-2 px-2 text-slate-muted font-medium">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {job.sample_rows.slice(0, 5).map((row, i) => (
                    <tr key={i} className="border-b border-slate-border/50">
                      {job.source_columns!.slice(0, 6).map((col) => (
                        <td key={col} className="py-1.5 px-2 text-foreground truncate max-w-[150px]">
                          {String(row[col] ?? '')}
                        </td>
                      ))}
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

  return (
    <div
      {...getRootProps()}
      className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
        isDragActive
          ? 'border-teal-electric bg-teal-electric/5'
          : 'border-slate-border hover:border-slate-500'
      }`}
    >
      <input {...getInputProps()} />
      <Upload
        className={`w-12 h-12 mx-auto mb-3 ${isDragActive ? 'text-teal-electric' : 'text-slate-muted'}`}
      />
      {uploadMutation.isPending ? (
        <p className="text-teal-electric">Uploading...</p>
      ) : isDragActive ? (
        <p className="text-teal-electric">Drop file here...</p>
      ) : (
        <>
          <p className="text-foreground mb-1">Drag & drop your file here</p>
          <p className="text-slate-muted text-sm">or click to browse (CSV, JSON)</p>
        </>
      )}
      {uploadMutation.isError && (
        <p className="text-red-400 text-sm mt-2">
          Upload failed: {(uploadMutation.error as Error).message}
        </p>
      )}
    </div>
  );
}

// Step 2: Field Mapping
function MappingStep({
  job,
  schema,
  onRefresh,
}: {
  job: MigrationJobDetail;
  schema?: EntitySchemaResponse;
  onRefresh: () => void;
}) {
  const [mapping, setMapping] = useState<Record<string, string>>(job.field_mapping || {});

  const { data: suggestions } = useQuery({
    queryKey: ['migration', job.id, 'suggest'],
    queryFn: () => migrationApi.suggestMapping(job.id),
    enabled: !!job.source_columns,
  });

  // Apply suggestions on first load
  useState(() => {
    if (suggestions?.suggestions && Object.keys(mapping).length === 0) {
      setMapping(suggestions.suggestions);
    }
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      migrationApi.saveMapping(job.id, {
        field_mapping: mapping,
        dedup_strategy: 'skip',
        dedup_fields: schema?.unique_fields || [],
      }),
    onSuccess: onRefresh,
  });

  const targetFields = schema?.fields || [];
  const requiredFields = schema?.required_fields || [];

  const handleMappingChange = (sourceCol: string, targetField: string) => {
    setMapping((prev) => {
      const next = { ...prev };
      if (targetField) {
        next[sourceCol] = targetField;
      } else {
        delete next[sourceCol];
      }
      return next;
    });
  };

  const mappedTargets = new Set(Object.values(mapping));
  const missingRequired = requiredFields.filter((f) => !mappedTargets.has(f));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-medium text-foreground">Map Source Columns to Target Fields</h4>
          <p className="text-slate-muted text-xs">
            Required fields: {requiredFields.join(', ')}
          </p>
        </div>
        {suggestions?.suggestions && Object.keys(suggestions.suggestions).length > 0 && (
          <button
            onClick={() => setMapping(suggestions.suggestions)}
            className="text-xs text-teal-electric hover:underline"
          >
            Apply Suggestions
          </button>
        )}
      </div>

      <div className="space-y-2 max-h-[400px] overflow-y-auto">
        {job.source_columns?.map((col) => (
          <div key={col} className="flex items-center gap-3 p-2 bg-slate-900 rounded-lg">
            <span className="text-sm text-foreground flex-1 min-w-0 truncate">{col}</span>
            <ChevronRight className="w-4 h-4 text-slate-muted flex-shrink-0" />
            <select
              value={mapping[col] || ''}
              onChange={(e) => handleMappingChange(col, e.target.value)}
              className="flex-1 min-w-0 px-2 py-1.5 bg-slate-800 border border-slate-border rounded text-sm text-foreground focus:outline-none focus:border-teal-electric"
            >
              <option value="">-- Skip --</option>
              {targetFields.map((field) => (
                <option
                  key={field.name}
                  value={field.name}
                  disabled={mappedTargets.has(field.name) && mapping[col] !== field.name}
                >
                  {field.name}
                  {field.required && ' *'}
                  {mappedTargets.has(field.name) && mapping[col] !== field.name && ' (mapped)'}
                </option>
              ))}
            </select>
          </div>
        ))}
      </div>

      {missingRequired.length > 0 && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-yellow-500" />
            <span className="text-yellow-500 text-sm">
              Missing required fields: {missingRequired.join(', ')}
            </span>
          </div>
        </div>
      )}

      <button
        onClick={() => saveMutation.mutate()}
        disabled={missingRequired.length > 0 || saveMutation.isPending}
        className="w-full py-2 bg-teal-electric text-white rounded-lg hover:bg-teal-electric/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {saveMutation.isPending ? 'Saving...' : 'Save Mapping'}
      </button>
    </div>
  );
}

// Step 3: Validation
function ValidateStep({ job, onRefresh }: { job: MigrationJobDetail; onRefresh: () => void }) {
  const validateMutation = useMutation({
    mutationFn: () => migrationApi.validate(job.id),
    onSuccess: onRefresh,
  });

  const validation = job.validation_result;

  return (
    <div className="space-y-4">
      {!validation ? (
        <div className="text-center py-8">
          <Eye className="w-12 h-12 text-slate-muted mx-auto mb-3" />
          <p className="text-foreground mb-4">Run validation to check your data before importing</p>
          <button
            onClick={() => validateMutation.mutate()}
            disabled={validateMutation.isPending}
            className="px-6 py-2 bg-teal-electric text-white rounded-lg hover:bg-teal-electric/90 transition-colors disabled:opacity-50"
          >
            {validateMutation.isPending ? 'Validating...' : 'Run Validation'}
          </button>
        </div>
      ) : (
        <>
          <div
            className={`p-4 rounded-lg ${
              validation.is_valid
                ? 'bg-green-500/10 border border-green-500/30'
                : 'bg-red-500/10 border border-red-500/30'
            }`}
          >
            <div className="flex items-center gap-2">
              {validation.is_valid ? (
                <CheckCircle className="w-5 h-5 text-green-500" />
              ) : (
                <XCircle className="w-5 h-5 text-red-500" />
              )}
              <span className={validation.is_valid ? 'text-green-500' : 'text-red-500'}>
                {validation.is_valid ? 'Validation passed' : 'Validation failed'}
              </span>
            </div>
            <div className="flex items-center gap-4 mt-2 text-sm">
              <span className="text-red-400">{validation.error_count} errors</span>
              <span className="text-yellow-400">{validation.warning_count} warnings</span>
            </div>
          </div>

          {validation.errors && validation.errors.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-red-400 mb-2">Errors</h4>
              <div className="space-y-1 max-h-[200px] overflow-y-auto">
                {validation.errors.slice(0, 20).map((err, i) => (
                  <div key={i} className="text-xs bg-red-500/10 rounded p-2">
                    <span className="text-slate-muted">Row {err.row || '-'}</span>
                    {err.field && <span className="text-red-400 ml-2">{err.field}</span>}
                    <span className="text-foreground ml-2">{err.message}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {validation.warnings && validation.warnings.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-yellow-400 mb-2">Warnings</h4>
              <div className="space-y-1 max-h-[150px] overflow-y-auto">
                {validation.warnings.slice(0, 10).map((warn, i) => (
                  <div key={i} className="text-xs bg-yellow-500/10 rounded p-2">
                    <span className="text-slate-muted">Row {warn.row || '-'}</span>
                    {warn.field && <span className="text-yellow-400 ml-2">{warn.field}</span>}
                    <span className="text-foreground ml-2">{warn.message}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <button
            onClick={() => validateMutation.mutate()}
            disabled={validateMutation.isPending}
            className="text-sm text-teal-electric hover:underline"
          >
            Re-run Validation
          </button>
        </>
      )}
    </div>
  );
}

// Step 4: Execute
function ExecuteStep({ job, onRefresh }: { job: MigrationJobDetail; onRefresh: () => void }) {
  const queryClient = useQueryClient();

  const executeMutation = useMutation({
    mutationFn: () => migrationApi.execute(job.id),
    onSuccess: () => {
      onRefresh();
      // Poll for progress
      const interval = setInterval(async () => {
        const progress = await migrationApi.getProgress(job.id);
        queryClient.setQueryData(['migration', 'job', job.id], (old: MigrationJobDetail) => ({
          ...old,
          ...progress,
        }));
        if (['completed', 'failed', 'cancelled'].includes(progress.status)) {
          clearInterval(interval);
          onRefresh();
        }
      }, 2000);
    },
  });

  const rollbackMutation = useMutation({
    mutationFn: () => migrationApi.rollback(job.id),
    onSuccess: onRefresh,
  });

  if (job.status === 'running') {
    return (
      <div className="text-center py-8">
        <div className="w-16 h-16 border-4 border-teal-electric border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <h4 className="text-lg font-semibold text-foreground mb-2">Migration in Progress</h4>
        <p className="text-slate-muted mb-4">
          {job.processed_rows} / {job.total_rows} rows processed ({job.progress_percent}%)
        </p>
        <div className="h-2 bg-slate-700 rounded-full overflow-hidden max-w-md mx-auto">
          <div
            className="h-full bg-teal-electric transition-all"
            style={{ width: `${job.progress_percent}%` }}
          />
        </div>
      </div>
    );
  }

  if (job.status === 'completed') {
    return (
      <div className="text-center py-8">
        <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
        <h4 className="text-lg font-semibold text-foreground mb-2">Migration Complete</h4>
        <div className="flex items-center justify-center gap-6 text-sm mb-6">
          <span className="text-green-400">{job.created_records} created</span>
          <span className="text-blue-400">{job.updated_records} updated</span>
          {job.skipped_records > 0 && (
            <span className="text-yellow-400">{job.skipped_records} skipped</span>
          )}
          {job.failed_records > 0 && (
            <span className="text-red-400">{job.failed_records} failed</span>
          )}
        </div>
        <button
          onClick={() => {
            if (confirm('Are you sure you want to rollback this migration?')) {
              rollbackMutation.mutate();
            }
          }}
          disabled={rollbackMutation.isPending}
          className="px-4 py-2 bg-orange-500/20 text-orange-400 border border-orange-500/30 rounded-lg hover:bg-orange-500/30 transition-colors"
        >
          {rollbackMutation.isPending ? 'Rolling back...' : 'Rollback Migration'}
        </button>
      </div>
    );
  }

  if (job.status === 'failed') {
    return (
      <div className="text-center py-8">
        <XCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
        <h4 className="text-lg font-semibold text-foreground mb-2">Migration Failed</h4>
        <p className="text-red-400 mb-4">{job.error_message}</p>
        <button
          onClick={() => executeMutation.mutate()}
          disabled={executeMutation.isPending}
          className="px-6 py-2 bg-teal-electric text-white rounded-lg hover:bg-teal-electric/90 transition-colors"
        >
          Retry Migration
        </button>
      </div>
    );
  }

  return (
    <div className="text-center py-8">
      <Play className="w-16 h-16 text-teal-electric mx-auto mb-4" />
      <h4 className="text-lg font-semibold text-foreground mb-2">Ready to Execute</h4>
      <p className="text-slate-muted mb-4">
        {job.total_rows} rows will be processed. This action cannot be undone (but can be rolled back).
      </p>
      <button
        onClick={() => executeMutation.mutate()}
        disabled={executeMutation.isPending}
        className="px-8 py-3 bg-teal-electric text-white rounded-lg hover:bg-teal-electric/90 transition-colors text-lg font-medium"
      >
        {executeMutation.isPending ? 'Starting...' : 'Start Migration'}
      </button>
    </div>
  );
}

export default function MigrationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const jobId = Number(params.id);

  const {
    data: job,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ['migration', 'job', jobId],
    queryFn: () => migrationApi.getJob(jobId),
    refetchInterval: (data) => (data?.status === 'running' ? 2000 : false),
  });

  const { data: schema } = useQuery({
    queryKey: ['migration', 'schema', job?.entity_type],
    queryFn: () => migrationApi.getEntitySchema(job!.entity_type),
    enabled: !!job?.entity_type,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="w-8 h-8 border-2 border-teal-electric border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!job) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold text-foreground mb-2">Job not found</h2>
        <Link href="/admin/migration" className="text-teal-electric hover:underline">
          Back to migrations
        </Link>
      </div>
    );
  }

  const activeStep = getActiveStep(job.status);

  return (
    <div className="space-y-6">
      <header className="flex items-center gap-4">
        <Link
          href="/admin/migration"
          className="p-2 rounded-lg hover:bg-slate-700 text-slate-muted hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-foreground">{job.name}</h1>
          <p className="text-slate-muted text-sm">
            {job.entity_type} migration &bull; {job.total_rows} rows
          </p>
        </div>
      </header>

      {/* Progress Steps */}
      <div className="flex items-center justify-between bg-slate-card border border-slate-border rounded-xl p-4">
        {STEPS.map((step, i) => {
          const isActive = i === activeStep;
          const isComplete = i < activeStep;
          return (
            <div key={step.id} className="flex items-center flex-1">
              <div className="flex flex-col items-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                    isComplete
                      ? 'bg-green-500 text-white'
                      : isActive
                        ? 'bg-teal-electric text-white'
                        : 'bg-slate-700 text-slate-muted'
                  }`}
                >
                  {isComplete ? <Check className="w-4 h-4" /> : i + 1}
                </div>
                <span
                  className={`text-xs mt-1 ${isActive ? 'text-teal-electric' : 'text-slate-muted'}`}
                >
                  {step.label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div
                  className={`flex-1 h-0.5 mx-2 ${isComplete ? 'bg-green-500' : 'bg-slate-700'}`}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Step Content */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-6">
        {activeStep === 0 && <UploadStep job={job} onRefresh={refetch} />}
        {activeStep === 1 && <MappingStep job={job} schema={schema} onRefresh={refetch} />}
        {activeStep === 2 && <MappingStep job={job} schema={schema} onRefresh={refetch} />}
        {activeStep === 3 && <ValidateStep job={job} onRefresh={refetch} />}
        {activeStep === 4 && <ExecuteStep job={job} onRefresh={refetch} />}
      </div>
    </div>
  );
}
