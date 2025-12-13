'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertTriangle, ArrowLeft, ClipboardList, Calendar, Tag, Users, FileText } from 'lucide-react';
import { useProjectDetail } from '@/hooks/useApi';
import { cn } from '@/lib/utils';

function formatDate(date: string | null | undefined) {
  if (!date) return '-';
  return new Date(date).toLocaleDateString('en-NG', { year: 'numeric', month: 'short', day: 'numeric' });
}

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params?.id);
  const { data, isLoading, error } = useProjectDetail(Number.isFinite(id) ? id : null);

  if (isLoading) {
    return (
      <div className="bg-slate-card border border-slate-border rounded-xl p-6">
        <div className="h-6 w-28 bg-slate-elevated rounded mb-3 animate-pulse" />
        <div className="space-y-2">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-4 bg-slate-elevated rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Failed to load project</p>
        <button
          onClick={() => router.back()}
          className="mt-3 inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
      </div>
    );
  }

  const writeBackClass = cn(
    'px-2 py-1 rounded-full text-xs font-semibold border',
    data.write_back_status === 'pending' && 'border-yellow-500/40 text-yellow-400 bg-yellow-500/10',
    data.write_back_status === 'failed' && 'border-red-500/40 text-red-400 bg-red-500/10',
    data.write_back_status === 'synced' && 'border-green-500/40 text-green-400 bg-green-500/10'
  );

  const summaryRows = [
    { label: 'Department', value: data.department || '-' },
    { label: 'Status', value: data.status || '-' },
    { label: 'Priority', value: data.priority || '-' },
    { label: 'Progress', value: `${data.percent_complete ?? 0}%` },
    { label: 'Expected Start', value: formatDate(data.expected_start_date) },
    { label: 'Expected End', value: formatDate(data.expected_end_date) },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/projects"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to projects
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Project</p>
            <h1 className="text-xl font-semibold text-white">{data.project_name}</h1>
            {data.write_back_status && <span className={writeBackClass}>Write-back: {data.write_back_status}</span>}
          </div>
        </div>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
        {summaryRows.map((row) => (
          <div key={row.label}>
            <p className="text-slate-muted text-xs uppercase tracking-[0.1em]">{row.label}</p>
            <p className="text-white font-semibold">{row.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <ClipboardList className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Details</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-slate-200">
            <div>
              <p className="text-slate-muted">Type</p>
              <p className="text-white font-semibold">{data.project_type || '-'}</p>
            </div>
            <div>
              <p className="text-slate-muted">Customer</p>
              <p className="text-white font-semibold">{data.customer?.name || data.customer_id || '-'}</p>
            </div>
            <div>
              <p className="text-slate-muted">Manager</p>
              <p className="text-white font-semibold">{data.project_manager || '-'}</p>
            </div>
            <div>
              <p className="text-slate-muted">Cost Center</p>
              <p className="text-white font-semibold">{data.cost_center || '-'}</p>
            </div>
            <div>
              <p className="text-slate-muted">Expected Start</p>
              <p className="text-white font-semibold">{formatDate(data.expected_start_date)}</p>
            </div>
            <div>
              <p className="text-slate-muted">Expected End</p>
              <p className="text-white font-semibold">{formatDate(data.expected_end_date)}</p>
            </div>
          </div>
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Financials</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-slate-200">
            <div>
              <p className="text-slate-muted">Estimated Costing</p>
              <p className="text-white font-semibold">{data.estimated_costing ?? 0}</p>
            </div>
            <div>
              <p className="text-slate-muted">Total Billed</p>
              <p className="text-white font-semibold">{data.total_billed_amount ?? 0}</p>
            </div>
            <div>
              <p className="text-slate-muted">Total Costing</p>
              <p className="text-white font-semibold">{data.total_costing_amount ?? 0}</p>
            </div>
            <div>
              <p className="text-slate-muted">Gross Margin</p>
              <p className="text-white font-semibold">{data.gross_margin ?? 0}</p>
            </div>
          </div>
        </div>
      </div>

      {data.users?.length ? (
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-teal-electric" />
            <h3 className="text-white font-semibold">Team</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-slate-muted">
                <tr>
                  <th className="text-left px-2 py-2">Name</th>
                  <th className="text-left px-2 py-2">Email</th>
                  <th className="text-left px-2 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {data.users.map((u, idx) => (
                  <tr key={idx} className="border-t border-slate-border/60">
                    <td className="px-2 py-2 text-white">{u.full_name || u.user}</td>
                    <td className="px-2 py-2 text-slate-200">{u.email || '-'}</td>
                    <td className="px-2 py-2 text-slate-200">{u.project_status || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}
