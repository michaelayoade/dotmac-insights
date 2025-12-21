'use client';

import { useState } from 'react';
import { DataTable, Pagination } from '@/components/DataTable';
import { useHrAppraisalTemplates, useHrAppraisals, useHrAppraisalMutations } from '@/hooks/useApi';
import { cn, formatDate } from '@/lib/utils';
import { Award, Target, FileEdit, CheckCircle2, Clock, Send, Eye, XCircle, AlertCircle } from 'lucide-react';

function extractList<T>(response: any) {
  const items = response?.data || [];
  const total = response?.total ?? items.length;
  return { items, total };
}

function FormLabel({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <label className="block text-xs text-slate-muted mb-1">
      {children}
      {required && <span className="text-rose-400 ml-0.5">*</span>}
    </label>
  );
}

function StatusBadge({ status }: { status: string }) {
  const normalizedStatus = (status || 'draft').toLowerCase();
  const config: Record<string, { bg: string; border: string; text: string; icon: React.ReactNode }> = {
    draft: { bg: 'bg-slate-500/10', border: 'border-slate-500/40', text: 'text-foreground-secondary', icon: <FileEdit className="w-3 h-3" /> },
    submitted: { bg: 'bg-amber-500/10', border: 'border-amber-500/40', text: 'text-amber-300', icon: <Send className="w-3 h-3" /> },
    'under review': { bg: 'bg-violet-500/10', border: 'border-violet-500/40', text: 'text-violet-300', icon: <Eye className="w-3 h-3" /> },
    completed: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/40', text: 'text-emerald-300', icon: <CheckCircle2 className="w-3 h-3" /> },
    closed: { bg: 'bg-cyan-500/10', border: 'border-cyan-500/40', text: 'text-cyan-300', icon: <XCircle className="w-3 h-3" /> },
  };
  const style = config[normalizedStatus] || config.draft;
  return (
    <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border', style.bg, style.border, style.text)}>
      {style.icon}
      <span className="capitalize">{status || 'Draft'}</span>
    </span>
  );
}

function StatCard({
  label,
  value,
  icon: Icon,
  tone = 'text-amber-400',
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  tone?: string;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-4 flex items-center justify-between">
      <div>
        <p className="text-slate-muted text-sm">{label}</p>
        <p className="text-2xl font-bold text-foreground">{value}</p>
      </div>
      <div className="p-2 rounded-lg bg-slate-elevated">
        <Icon className={cn('w-5 h-5', tone)} />
      </div>
    </div>
  );
}

const SINGLE_COMPANY = '';

export default function HrAppraisalsPage() {
  const [status, setStatus] = useState('draft');
  const [limit, setLimit] = useState(20);
  const [offset, setOffset] = useState(0);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: templates, isLoading: templatesLoading } = useHrAppraisalTemplates({ company: SINGLE_COMPANY || undefined });
  const { data: appraisals, isLoading: appraisalsLoading } = useHrAppraisals({
    company: SINGLE_COMPANY || undefined,
    status: status || undefined,
    limit,
    offset,
  });
  const appraisalMutations = useHrAppraisalMutations();

  const templateList = extractList(templates);
  const appraisalList = extractList(appraisals);

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <StatCard label="Appraisal Templates" value={templateList.total} icon={Target} tone="text-amber-400" />
        <StatCard label="Appraisals" value={appraisalList.total} icon={Award} tone="text-violet-400" />
      </div>

      {/* Filters */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <p className="text-xs text-slate-muted mb-3">Filter Appraisals</p>
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <FormLabel>Status</FormLabel>
            <select
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setOffset(0);
              }}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
            >
              <option value="">All statuses</option>
              <option value="draft">Draft</option>
              <option value="submitted">Submitted</option>
              <option value="under review">Under Review</option>
              <option value="completed">Completed</option>
              <option value="closed">Closed</option>
            </select>
          </div>
        </div>
      </div>

      {/* Appraisal Templates */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <Target className="w-4 h-4 text-amber-400" />
          <h3 className="text-foreground font-semibold">Appraisal Templates</h3>
        </div>
        <DataTable
          columns={[
            { key: 'template_name', header: 'Template Name', render: (item: any) => <span className="text-foreground font-medium">{item.template_name}</span> },
            { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
            {
              key: 'goals',
              header: 'Goals',
              align: 'right' as const,
              render: (item: any) => (
                <span className="inline-flex items-center gap-1 text-foreground">
                  <Target className="w-3 h-3 text-slate-muted" />
                  {item.goals?.length ?? 0}
                </span>
              ),
            },
          ]}
          data={(templateList.items || []).map((item: any) => ({ ...item, id: item.id || item.template_name }))}
          keyField="id"
          loading={templatesLoading}
          emptyMessage="No appraisal templates"
        />
      </div>

      {/* Appraisals */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <Award className="w-4 h-4 text-violet-400" />
          <h3 className="text-foreground font-semibold">Appraisals</h3>
        </div>
        <DataTable
          columns={[
            { key: 'employee', header: 'Employee Name', render: (item: any) => <span className="text-foreground font-medium">{item.employee_name || item.employee}</span> },
            { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
            { key: 'appraisal_template', header: 'Template', render: (item: any) => <span className="text-slate-muted text-sm">{item.appraisal_template || '—'}</span> },
            {
              key: 'start_date',
              header: 'Review Period',
              render: (item: any) => <span className="text-slate-muted text-sm">{`${formatDate(item.start_date)} – ${formatDate(item.end_date)}`}</span>,
            },
            {
              key: 'status',
              header: 'Status',
              render: (item: any) => <StatusBadge status={item.status} />,
            },
            {
              key: 'goals',
              header: 'Goals',
              align: 'right' as const,
              render: (item: any) => (
                <span className="inline-flex items-center gap-1 text-foreground">
                  <Target className="w-3 h-3 text-slate-muted" />
                  {item.goals?.length ?? 0}
                </span>
              ),
            },
            {
              key: 'actions',
              header: 'Actions',
              render: (item: any) => {
                const isDraft = !item.status || item.status === 'draft';
                const isSubmitted = item.status === 'submitted';
                const canClose = item.status === 'completed' || item.status === 'under review';
                return (
                  <div className="flex gap-2 text-xs">
                    {isDraft && (
                      <button
                        onClick={(e) => { e.stopPropagation(); appraisalMutations.submit(item.id).catch((err: any) => setActionError(err?.message || 'Submit failed')); }}
                        className="px-2 py-1 rounded border border-amber-500/40 text-amber-300 hover:bg-amber-500/10"
                      >
                        Submit
                      </button>
                    )}
                    {isSubmitted && (
                      <button
                        onClick={(e) => { e.stopPropagation(); appraisalMutations.review(item.id).catch((err: any) => setActionError(err?.message || 'Review failed')); }}
                        className="px-2 py-1 rounded border border-violet-500/40 text-violet-300 hover:bg-violet-500/10"
                      >
                        Review
                      </button>
                    )}
                    {canClose && (
                      <button
                        onClick={(e) => { e.stopPropagation(); appraisalMutations.close(item.id).catch((err: any) => setActionError(err?.message || 'Close failed')); }}
                        className="px-2 py-1 rounded border border-slate-border text-slate-muted hover:bg-slate-elevated/50"
                      >
                        Close
                      </button>
                    )}
                  </div>
                );
              },
            },
          ]}
          data={(appraisalList.items || []).map((item: any) => ({ ...item, id: item.id || `${item.employee}-${item.start_date}` }))}
          keyField="id"
          loading={appraisalsLoading}
          emptyMessage="No appraisals"
        />
        {appraisalList.total > limit && (
          <Pagination
            total={appraisalList.total}
            limit={limit}
            offset={offset}
            onPageChange={setOffset}
            onLimitChange={(val) => {
              setLimit(val);
              setOffset(0);
            }}
          />
        )}
      </div>
      {actionError && (
        <div className="bg-rose-500/10 border border-rose-500/40 rounded-lg p-3">
          <p className="text-rose-300 text-sm">{actionError}</p>
        </div>
      )}
    </div>
  );
}
