'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  Upload,
  FileSpreadsheet,
  CheckCircle,
  XCircle,
  Clock,
  Play,
  RotateCcw,
  Trash2,
  Plus,
  ChevronRight,
  AlertTriangle,
} from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { migrationApi, MigrationJob, MigrationStatus } from '@/lib/api/domains';
import { formatDistanceToNow } from 'date-fns';

const statusConfig: Record<MigrationStatus, { icon: React.ElementType; color: string; label: string }> = {
  pending: { icon: Clock, color: 'text-slate-400', label: 'Pending' },
  uploaded: { icon: Upload, color: 'text-blue-400', label: 'Uploaded' },
  mapped: { icon: FileSpreadsheet, color: 'text-purple-400', label: 'Mapped' },
  validating: { icon: Clock, color: 'text-yellow-400', label: 'Validating' },
  validated: { icon: CheckCircle, color: 'text-green-400', label: 'Validated' },
  running: { icon: Play, color: 'text-teal-400 animate-pulse', label: 'Running' },
  completed: { icon: CheckCircle, color: 'text-green-500', label: 'Completed' },
  failed: { icon: XCircle, color: 'text-red-500', label: 'Failed' },
  cancelled: { icon: XCircle, color: 'text-slate-400', label: 'Cancelled' },
  rolled_back: { icon: RotateCcw, color: 'text-orange-400', label: 'Rolled Back' },
};

function JobCard({ job, onDelete }: { job: MigrationJob; onDelete: (id: number) => void }) {
  const config = statusConfig[job.status] || statusConfig.pending;
  const StatusIcon = config.icon;

  return (
    <Link
      href={`/admin/migration/${job.id}`}
      className="group bg-slate-card border border-slate-border rounded-xl p-4 hover:border-teal-electric/50 transition-colors block"
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-foreground font-semibold truncate">{job.name}</h3>
            <span className="text-xs bg-slate-700 px-2 py-0.5 rounded text-slate-300">
              {job.entity_type}
            </span>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <StatusIcon className={`w-4 h-4 ${config.color}`} />
            <span className={`text-sm ${config.color}`}>{config.label}</span>
            {job.total_rows > 0 && (
              <span className="text-slate-muted text-sm">
                {job.processed_rows}/{job.total_rows} rows
              </span>
            )}
          </div>
          {job.status === 'running' && job.total_rows > 0 && (
            <div className="mt-2">
              <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-teal-electric transition-all"
                  style={{ width: `${job.progress_percent}%` }}
                />
              </div>
              <span className="text-xs text-slate-muted mt-0.5">{job.progress_percent}%</span>
            </div>
          )}
          {job.status === 'completed' && (
            <div className="flex items-center gap-3 mt-2 text-xs text-slate-muted">
              <span className="text-green-400">{job.created_records} created</span>
              <span className="text-blue-400">{job.updated_records} updated</span>
              {job.skipped_records > 0 && (
                <span className="text-yellow-400">{job.skipped_records} skipped</span>
              )}
              {job.failed_records > 0 && (
                <span className="text-red-400">{job.failed_records} failed</span>
              )}
            </div>
          )}
          {job.error_message && (
            <div className="flex items-center gap-1 mt-2 text-xs text-red-400">
              <AlertTriangle className="w-3 h-3" />
              <span className="truncate">{job.error_message}</span>
            </div>
          )}
          <p className="text-slate-muted text-xs mt-2">
            Created {formatDistanceToNow(new Date(job.created_at), { addSuffix: true })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {['pending', 'completed', 'failed', 'cancelled', 'rolled_back'].includes(job.status) && (
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onDelete(job.id);
              }}
              className="p-1.5 rounded hover:bg-slate-700 text-slate-muted hover:text-red-400 transition-colors"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
          <ChevronRight className="w-5 h-5 text-slate-muted group-hover:text-teal-electric transition-colors" />
        </div>
      </div>
    </Link>
  );
}

export default function MigrationPage() {
  const queryClient = useQueryClient();
  const [isCreating, setIsCreating] = useState(false);
  const [newJobName, setNewJobName] = useState('');
  const [newJobEntity, setNewJobEntity] = useState('');

  const { data: jobsData, isLoading: jobsLoading } = useQuery({
    queryKey: ['migration', 'jobs'],
    queryFn: () => migrationApi.listJobs({ limit: 50 }),
  });

  const { data: entities } = useQuery({
    queryKey: ['migration', 'entities'],
    queryFn: () => migrationApi.listEntities(),
  });

  const createMutation = useMutation({
    mutationFn: migrationApi.createJob,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['migration', 'jobs'] });
      setIsCreating(false);
      setNewJobName('');
      setNewJobEntity('');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: migrationApi.deleteJob,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['migration', 'jobs'] });
    },
  });

  const handleCreate = () => {
    if (newJobName && newJobEntity) {
      createMutation.mutate({ name: newJobName, entity_type: newJobEntity });
    }
  };

  const handleDelete = (id: number) => {
    if (confirm('Are you sure you want to delete this migration job?')) {
      deleteMutation.mutate(id);
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Data Migration</h1>
          <p className="text-slate-muted text-sm mt-1">
            Import data from external sources with mapping, validation, and cleaning.
          </p>
        </div>
        <button
          onClick={() => setIsCreating(true)}
          className="flex items-center gap-2 px-4 py-2 bg-teal-electric text-white rounded-lg hover:bg-teal-electric/90 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Migration
        </button>
      </header>

      {isCreating && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <h2 className="text-lg font-semibold text-foreground mb-4">Create New Migration</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-slate-muted mb-1">Job Name</label>
              <input
                type="text"
                value={newJobName}
                onChange={(e) => setNewJobName(e.target.value)}
                placeholder="e.g., Customer Import Q4 2024"
                className="w-full px-3 py-2 bg-slate-900 border border-slate-border rounded-lg text-foreground placeholder:text-slate-muted focus:outline-none focus:border-teal-electric"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-muted mb-1">Entity Type</label>
              <select
                value={newJobEntity}
                onChange={(e) => setNewJobEntity(e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-border rounded-lg text-foreground focus:outline-none focus:border-teal-electric"
              >
                <option value="">Select entity type...</option>
                {entities?.map((entity) => (
                  <option key={entity.type} value={entity.type}>
                    {entity.display_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleCreate}
                disabled={!newJobName || !newJobEntity || createMutation.isPending}
                className="px-4 py-2 bg-teal-electric text-white rounded-lg hover:bg-teal-electric/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {createMutation.isPending ? 'Creating...' : 'Create'}
              </button>
              <button
                onClick={() => setIsCreating(false)}
                className="px-4 py-2 text-slate-muted hover:text-foreground transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {jobsLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[...Array(4)].map((_, i) => (
            <div
              key={i}
              className="bg-slate-card border border-slate-border rounded-xl p-4 animate-pulse"
            >
              <div className="h-4 w-32 bg-slate-700 rounded mb-2" />
              <div className="h-3 w-24 bg-slate-700 rounded mb-2" />
              <div className="h-3 w-48 bg-slate-700 rounded" />
            </div>
          ))}
        </div>
      ) : jobsData?.jobs?.length === 0 ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-8 text-center">
          <FileSpreadsheet className="w-12 h-12 text-slate-muted mx-auto mb-3" />
          <h3 className="text-lg font-semibold text-foreground mb-1">No migrations yet</h3>
          <p className="text-slate-muted text-sm mb-4">
            Create your first migration to import data from CSV or JSON files.
          </p>
          <button
            onClick={() => setIsCreating(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-teal-electric text-white rounded-lg hover:bg-teal-electric/90 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Create Migration
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {jobsData?.jobs?.map((job) => (
            <JobCard key={job.id} job={job} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </div>
  );
}
