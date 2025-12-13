'use client';

import { useState } from 'react';
import { DataTable, Pagination } from '@/components/DataTable';
import { useHrAppraisalTemplates, useHrAppraisals, useHrAppraisalMutations } from '@/hooks/useApi';
import { cn, formatDate } from '@/lib/utils';
import { Award, Target } from 'lucide-react';

function extractList<T>(response: any) {
  const items = response?.data || [];
  const total = response?.total ?? items.length;
  return { items, total };
}

function StatCard({
  label,
  value,
  icon: Icon,
  tone = 'text-teal-electric',
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
        <p className="text-2xl font-bold text-white">{value}</p>
      </div>
      <div className="p-2 rounded-lg bg-slate-elevated">
        <Icon className={cn('w-5 h-5', tone)} />
      </div>
    </div>
  );
}

export default function HrAppraisalsPage() {
  const [status, setStatus] = useState('draft');
  const [company, setCompany] = useState('');
  const [limit, setLimit] = useState(20);
  const [offset, setOffset] = useState(0);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: templates, isLoading: templatesLoading } = useHrAppraisalTemplates({ company: company || undefined });
  const { data: appraisals, isLoading: appraisalsLoading } = useHrAppraisals({
    company: company || undefined,
    status: status || undefined,
    limit,
    offset,
  });
  const appraisalMutations = useHrAppraisalMutations();

  const templateList = extractList(templates);
  const appraisalList = extractList(appraisals);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <StatCard label="Appraisal Templates" value={templateList.total} icon={Target} tone="text-teal-electric" />
        <StatCard label="Appraisals" value={appraisalList.total} icon={Award} tone="text-purple-300" />
      </div>

      <div className="flex flex-wrap gap-3 items-center">
        <input
          type="text"
          placeholder="Company"
          value={company}
          onChange={(e) => {
            setCompany(e.target.value);
            setOffset(0);
          }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        />
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setOffset(0);
          }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        >
          <option value="">All statuses</option>
          <option value="draft">Draft</option>
          <option value="submitted">Submitted</option>
          <option value="completed">Completed</option>
        </select>
      </div>

      <DataTable
        columns={[
          { key: 'template_name', header: 'Template', render: (item: any) => <span className="text-white">{item.template_name}</span> },
          { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
          {
            key: 'goals',
            header: 'Goals',
            align: 'right' as const,
            render: (item: any) => <span className="font-mono text-white">{item.goals?.length ?? 0}</span>,
          },
        ]}
        data={(templateList.items || []).map((item: any) => ({ ...item, id: item.id || item.template_name }))}
        keyField="id"
        loading={templatesLoading}
        emptyMessage="No appraisal templates"
      />

      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <Award className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Appraisals</h3>
        </div>
        <DataTable
          columns={[
            { key: 'employee', header: 'Employee', render: (item: any) => <span className="text-white">{item.employee_name || item.employee}</span> },
            { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
            { key: 'appraisal_template', header: 'Template', render: (item: any) => <span className="text-slate-muted text-sm">{item.appraisal_template || '—'}</span> },
            {
              key: 'start_date',
              header: 'Period',
              render: (item: any) => <span className="text-slate-muted text-sm">{`${formatDate(item.start_date)} – ${formatDate(item.end_date)}`}</span>,
            },
            {
              key: 'status',
              header: 'Status',
              render: (item: any) => (
                <span className={cn('px-2 py-1 rounded-full text-xs border capitalize', item.status === 'completed' ? 'border-green-400 text-green-300 bg-green-500/10' : 'border-amber-400 text-amber-300 bg-amber-500/10')}>
                  {item.status || 'draft'}
                </span>
              ),
            },
            {
              key: 'goals',
              header: 'Goals',
              align: 'right' as const,
              render: (item: any) => <span className="font-mono text-white">{item.goals?.length ?? 0}</span>,
            },
            {
              key: 'actions',
              header: 'Actions',
              render: (item: any) => (
                <div className="flex gap-2 text-xs">
                  <button
                    onClick={(e) => { e.stopPropagation(); appraisalMutations.submit(item.id).catch((err: any) => setActionError(err?.message || 'Submit failed')); }}
                    className="px-2 py-1 rounded border border-teal-electric text-teal-electric hover:bg-teal-electric/10"
                  >
                    Submit
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); appraisalMutations.review(item.id).catch((err: any) => setActionError(err?.message || 'Review failed')); }}
                    className="px-2 py-1 rounded border border-amber-400 text-amber-300 hover:bg-amber-500/10"
                  >
                    Review
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); appraisalMutations.close(item.id).catch((err: any) => setActionError(err?.message || 'Close failed')); }}
                    className="px-2 py-1 rounded border border-slate-border text-slate-muted hover:bg-slate-elevated/50"
                  >
                    Close
                  </button>
                </div>
              ),
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
        {actionError && <p className="text-red-400 text-sm">{actionError}</p>}
      </div>
    </div>
  );
}
