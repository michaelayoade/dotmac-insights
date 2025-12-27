/**
 * Migration Domain API
 * Data migration tool - import, mapping, validation, execution
 */

import { fetchApi } from '../core';

// =============================================================================
// TYPES
// =============================================================================

export type MigrationStatus =
  | 'pending'
  | 'uploaded'
  | 'mapped'
  | 'validating'
  | 'validated'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'rolled_back';

export type DedupStrategy = 'skip' | 'update' | 'merge';

export type RecordAction = 'created' | 'updated' | 'skipped' | 'failed';

export interface EntityInfo {
  type: string;
  display_name: string;
  description: string;
  required_fields: string[];
  unique_fields: string[];
  dependencies: string[];
}

export interface FieldInfo {
  name: string;
  type: string;
  required?: boolean;
  unique?: boolean;
  description?: string;
  enum_values?: string[];
  default?: unknown;
}

export interface EntitySchemaResponse {
  entity_type: string;
  display_name: string;
  fields: FieldInfo[];
  required_fields: string[];
  unique_fields: string[];
}

export interface MigrationJob {
  id: number;
  name: string;
  entity_type: string;
  source_type: string | null;
  status: MigrationStatus;
  total_rows: number;
  processed_rows: number;
  created_records: number;
  updated_records: number;
  skipped_records: number;
  failed_records: number;
  progress_percent: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

export interface MigrationJobDetail extends MigrationJob {
  source_columns: string[] | null;
  sample_rows: Record<string, unknown>[] | null;
  field_mapping: Record<string, string> | null;
  cleaning_rules: Record<string, unknown> | null;
  dedup_strategy: DedupStrategy | null;
  dedup_fields: string[] | null;
  validation_result: ValidationResult | null;
}

export interface MigrationJobListResponse {
  jobs: MigrationJob[];
  total: number;
  limit: number;
  offset: number;
}

export interface CreateJobPayload {
  name: string;
  entity_type: string;
}

export interface SaveMappingPayload {
  field_mapping: Record<string, string>;
  cleaning_rules?: Record<string, unknown>;
  dedup_strategy?: DedupStrategy;
  dedup_fields?: string[];
}

export interface ValidationIssue {
  severity: 'error' | 'warning' | 'info';
  field: string | null;
  message: string;
  row: number | null;
  value: string | null;
}

export interface ValidationResult {
  is_valid: boolean;
  error_count: number;
  warning_count: number;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
}

export interface PreviewRow {
  row_number: number;
  source: Record<string, unknown>;
  transformed: Record<string, unknown>;
  warnings: Array<{
    field: string;
    original: unknown;
    cleaned: unknown;
    warnings: string[];
  }>;
}

export interface ProgressResponse {
  job_id: number;
  status: MigrationStatus;
  total_rows: number;
  processed_rows: number;
  created_records: number;
  updated_records: number;
  skipped_records: number;
  failed_records: number;
  progress_percent: number;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

export interface MigrationRecord {
  id: number;
  row_number: number;
  action: RecordAction | null;
  error_message: string | null;
  source_data: Record<string, unknown> | null;
  transformed_data: Record<string, unknown> | null;
}

export interface MigrationRecordListResponse {
  records: MigrationRecord[];
  total: number;
  limit: number;
  offset: number;
}

export interface DuplicateReport {
  in_file: Array<{
    field: string;
    value: unknown;
    rows: number[];
  }>;
  field_counts: Record<string, number>;
}

export interface JobListParams {
  status?: MigrationStatus;
  entity_type?: string;
  limit?: number;
  offset?: number;
}

// =============================================================================
// API FUNCTIONS
// =============================================================================

/**
 * List supported entity types for migration
 */
export async function listEntities(): Promise<EntityInfo[]> {
  return fetchApi<EntityInfo[]>('/api/migration/entities');
}

/**
 * Get recommended migration order based on dependencies
 */
export async function getMigrationOrder(): Promise<{
  order: string[];
  entities: Array<{
    type: string;
    display_name: string;
    dependencies: string[];
  }>;
}> {
  return fetchApi('/api/migration/migration-order');
}

/**
 * Get dependencies for an entity type
 */
export async function getEntityDependencies(entityType: string): Promise<{
  entity_type: string;
  display_name: string;
  dependencies: Array<{
    type: string;
    display_name: string;
    description: string;
  }>;
}> {
  return fetchApi(`/api/migration/entities/${entityType}/dependencies`);
}

/**
 * Get entity schema (fields, required, etc.)
 */
export async function getEntitySchema(entityType: string): Promise<EntitySchemaResponse> {
  return fetchApi<EntitySchemaResponse>(`/api/migration/entities/${entityType}/schema`);
}

/**
 * Create a new migration job
 */
export async function createJob(payload: CreateJobPayload): Promise<MigrationJob> {
  return fetchApi<MigrationJob>('/api/migration/jobs', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

/**
 * List migration jobs
 */
export async function listJobs(params?: JobListParams): Promise<MigrationJobListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set('status', params.status);
  if (params?.entity_type) searchParams.set('entity_type', params.entity_type);
  if (params?.limit) searchParams.set('limit', String(params.limit));
  if (params?.offset) searchParams.set('offset', String(params.offset));

  const query = searchParams.toString();
  return fetchApi<MigrationJobListResponse>(`/api/migration/jobs${query ? `?${query}` : ''}`);
}

/**
 * Get migration job details
 */
export async function getJob(jobId: number): Promise<MigrationJobDetail> {
  return fetchApi<MigrationJobDetail>(`/api/migration/jobs/${jobId}`);
}

/**
 * Delete a migration job
 */
export async function deleteJob(jobId: number): Promise<{ success: boolean; message: string }> {
  return fetchApi(`/api/migration/jobs/${jobId}`, { method: 'DELETE' });
}

/**
 * Upload source file for migration
 */
export async function uploadFile(jobId: number, file: File): Promise<MigrationJobDetail> {
  const formData = new FormData();
  formData.append('file', file);

  return fetchApi<MigrationJobDetail>(`/api/migration/jobs/${jobId}/upload`, {
    method: 'POST',
    body: formData,
    headers: {}, // Let browser set Content-Type with boundary
  });
}

/**
 * Get parsed columns from uploaded file
 */
export async function getColumns(jobId: number): Promise<{ columns: string[]; total_rows: number }> {
  return fetchApi(`/api/migration/jobs/${jobId}/columns`);
}

/**
 * Get sample rows from uploaded file
 */
export async function getSampleRows(
  jobId: number,
  limit = 10
): Promise<{ sample_rows: Record<string, unknown>[]; columns: string[]; total_rows: number }> {
  return fetchApi(`/api/migration/jobs/${jobId}/sample?limit=${limit}`);
}

/**
 * Get auto-suggested field mappings
 */
export async function suggestMapping(jobId: number): Promise<{ suggestions: Record<string, string> }> {
  return fetchApi(`/api/migration/jobs/${jobId}/mapping/suggest`, { method: 'POST' });
}

/**
 * Save field mapping and configuration
 */
export async function saveMapping(
  jobId: number,
  payload: SaveMappingPayload
): Promise<MigrationJobDetail> {
  return fetchApi<MigrationJobDetail>(`/api/migration/jobs/${jobId}/mapping`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

/**
 * Run validation (dry-run)
 */
export async function validate(jobId: number): Promise<ValidationResult> {
  return fetchApi<ValidationResult>(`/api/migration/jobs/${jobId}/validate`, { method: 'POST' });
}

/**
 * Get preview of transformed data
 */
export async function getPreview(
  jobId: number,
  limit = 100,
  offset = 0
): Promise<PreviewRow[]> {
  return fetchApi<PreviewRow[]>(`/api/migration/jobs/${jobId}/preview?limit=${limit}&offset=${offset}`);
}

/**
 * Get duplicate detection report
 */
export async function getDuplicates(jobId: number): Promise<DuplicateReport> {
  return fetchApi<DuplicateReport>(`/api/migration/jobs/${jobId}/duplicates`);
}

/**
 * Execute migration
 */
export async function execute(jobId: number): Promise<ProgressResponse> {
  return fetchApi<ProgressResponse>(`/api/migration/jobs/${jobId}/execute`, { method: 'POST' });
}

/**
 * Get migration progress
 */
export async function getProgress(jobId: number): Promise<ProgressResponse> {
  return fetchApi<ProgressResponse>(`/api/migration/jobs/${jobId}/progress`);
}

/**
 * Cancel running migration
 */
export async function cancel(jobId: number): Promise<{ success: boolean; message: string }> {
  return fetchApi(`/api/migration/jobs/${jobId}/cancel`, { method: 'POST' });
}

/**
 * Preview rollback
 */
export async function previewRollback(
  jobId: number
): Promise<{ job_id: number; records_to_rollback: number; created_records: number; updated_records: number }> {
  return fetchApi(`/api/migration/jobs/${jobId}/rollback-preview`);
}

/**
 * Rollback migration
 */
export async function rollback(
  jobId: number
): Promise<{ job_id: number; rolled_back_records: number; status: string }> {
  return fetchApi(`/api/migration/jobs/${jobId}/rollback`, { method: 'POST' });
}

/**
 * List migration records for a job
 */
export async function getRecords(
  jobId: number,
  params?: { action?: RecordAction; limit?: number; offset?: number }
): Promise<MigrationRecordListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.action) searchParams.set('action', params.action);
  if (params?.limit) searchParams.set('limit', String(params.limit));
  if (params?.offset) searchParams.set('offset', String(params.offset));

  const query = searchParams.toString();
  return fetchApi<MigrationRecordListResponse>(
    `/api/migration/jobs/${jobId}/records${query ? `?${query}` : ''}`
  );
}

// =============================================================================
// API OBJECT
// =============================================================================

export const migrationApi = {
  // Entities
  listEntities,
  getMigrationOrder,
  getEntityDependencies,
  getEntitySchema,

  // Jobs
  createJob,
  listJobs,
  getJob,
  deleteJob,

  // File handling
  uploadFile,
  getColumns,
  getSampleRows,

  // Mapping
  suggestMapping,
  saveMapping,

  // Validation & Preview
  validate,
  getPreview,
  getDuplicates,

  // Execution
  execute,
  getProgress,
  cancel,

  // Rollback
  previewRollback,
  rollback,

  // Records
  getRecords,
};
