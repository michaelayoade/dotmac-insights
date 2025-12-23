'use client';

import { useState } from 'react';
import { DataTable, Pagination } from '@/components/DataTable';
import { useHrAppraisalTemplates, useHrAppraisals, useHrAppraisalMutations } from '@/hooks/useApi';
import { cn, formatDate } from '@/lib/utils';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import { Award, Target, FileEdit, CheckCircle2, Clock, Send, Eye, XCircle, AlertCircle } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Button, FilterCard, FilterSelect, StatusPill } from '@/components/ui';
import { StatCard } from '@/components/StatCard';

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
  const config: Record<string, { tone: StatusTone; icon: LucideIcon; label?: string }> = {
    draft: { tone: 'default', icon: FileEdit },
    submitted: { tone: 'warning', icon: Send },
    'under review': { tone: 'info', icon: Eye, label: 'Under review' },
    completed: { tone: 'success', icon: CheckCircle2 },
    closed: { tone: 'info', icon: XCircle },
  };
  const style = config[normalizedStatus] || config.draft;
  return (
    <StatusPill
      label={style.label || formatStatusLabel(status || 'draft')}
      tone={style.tone}
      icon={style.icon}
      className="border border-current/30"
    />
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
        <StatCard title="Appraisal Templates" value={templateList.total} icon={Target} colorClass="text-amber-400" />
        <StatCard title="Appraisals" value={appraisalList.total} icon={Award} colorClass="text-violet-400" />
      </div>

      {/* Filters */}
      <FilterCard title="Filter Appraisals" contentClassName="flex flex-wrap gap-3 items-end" iconClassName="text-amber-400">
        <div>
          <FormLabel>Status</FormLabel>
          <FilterSelect
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="submitted">Submitted</option>
            <option value="under review">Under Review</option>
            <option value="completed">Completed</option>
            <option value="closed">Closed</option>
          </FilterSelect>
        </div>
      </FilterCard>

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
                      <Button
                        onClick={(e) => { e.stopPropagation(); appraisalMutations.submit(item.id).catch((err: any) => setActionError(err?.message || 'Submit failed')); }}
                        className="px-2 py-1 rounded border border-amber-500/40 text-amber-300 hover:bg-amber-500/10"
                      >
                        Submit
                      </Button>
                    )}
                    {isSubmitted && (
                      <Button
                        onClick={(e) => { e.stopPropagation(); appraisalMutations.review(item.id).catch((err: any) => setActionError(err?.message || 'Review failed')); }}
                        className="px-2 py-1 rounded border border-violet-500/40 text-violet-300 hover:bg-violet-500/10"
                      >
                        Review
                      </Button>
                    )}
                    {canClose && (
                      <Button
                        onClick={(e) => { e.stopPropagation(); appraisalMutations.close(item.id).catch((err: any) => setActionError(err?.message || 'Close failed')); }}
                        className="px-2 py-1 rounded border border-slate-border text-slate-muted hover:bg-slate-elevated/50"
                      >
                        Close
                      </Button>
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
