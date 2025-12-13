'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { DataTable, Pagination } from '@/components/DataTable';
import { useProjects, useProjectsDashboard } from '@/hooks/useApi';
import { Filter, Plus, ClipboardList, AlertTriangle, Tag, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';

function formatDate(dateStr: string | null | undefined) {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleDateString('en-NG', { year: 'numeric', month: 'short', day: 'numeric' });
}

export default function ProjectsPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [status, setStatus] = useState<string>('');
  const [priority, setPriority] = useState<string>('');
  const [department, setDepartment] = useState<string>('');
  const [projectType, setProjectType] = useState<string>('');
  const [search, setSearch] = useState<string>('');

  const { data, isLoading, error } = useProjects({
    status: status || undefined,
    priority: (priority || undefined) as any,
    department: department || undefined,
    project_type: projectType || undefined,
    search: search || undefined,
    limit: pageSize,
    offset: (page - 1) * pageSize,
  });

  const { data: dashboard } = useProjectsDashboard();

  const projects = data?.data || [];
  const total = data?.total || 0;

  const columns = [
    {
      key: 'name',
      header: 'Project',
      render: (item: any) => (
        <div className="flex flex-col">
          <span className="font-mono text-white font-semibold">{item.erpnext_id || item.project_name}</span>
          <span className="text-slate-200 text-sm line-clamp-1">{item.department || '-'}</span>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => <span className="text-slate-200 capitalize text-sm">{item.status}</span>,
    },
    {
      key: 'priority',
      header: 'Priority',
      render: (item: any) => {
        const pri = item.priority || 'medium';
        const color =
          pri === 'high'
            ? 'bg-orange-500/10 text-orange-400 border-orange-500/30'
            : pri === 'low'
            ? 'bg-slate-500/10 text-slate-300 border-slate-500/30'
            : 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30';
        return (
          <span className={cn('px-2 py-1 rounded-full text-xs font-medium border inline-flex items-center gap-1', color)}>
            <Tag className="w-3 h-3" />
            {pri}
          </span>
        );
      },
    },
    {
      key: 'progress',
      header: 'Progress',
      render: (item: any) => (
        <div className="text-sm text-slate-200">{item.percent_complete ?? 0}%</div>
      ),
    },
    {
      key: 'dates',
      header: 'Expected Dates',
      render: (item: any) => (
        <div className="text-sm text-slate-200 space-y-1">
          <div className="flex items-center gap-1">
            <Clock className="w-3 h-3 text-slate-muted" />
            <span>{formatDate(item.expected_start_date)}</span>
          </div>
          <div className="flex items-center gap-1">
            <Clock className="w-3 h-3 text-slate-muted" />
            <span>{formatDate(item.expected_end_date)}</span>
          </div>
        </div>
      ),
    },
    {
      key: 'tasks',
      header: 'Tasks',
      render: (item: any) => <span className="text-slate-200 text-sm">{item.task_count ?? 0}</span>,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-teal-electric/10 border border-teal-electric/30 flex items-center justify-center">
            <ClipboardList className="w-5 h-5 text-teal-electric" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Projects</h1>
            <p className="text-slate-muted text-sm">Plan, track, and deliver projects across teams</p>
          </div>
        </div>
        <Link
          href="/projects/new"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90"
        >
          <Plus className="w-4 h-4" />
          New Project
        </Link>
      </div>

      {dashboard?.cards && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {Object.entries(dashboard.cards).map(([label, value]) => (
            <SummaryCard key={label} label={label} value={value as number} />
          ))}
        </div>
      )}

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-teal-electric" />
          <span className="text-white text-sm font-medium">Filters</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search projects"
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="">Status</option>
            <option value="open">Open</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
            <option value="on_hold">On Hold</option>
          </select>
          <select
            value={priority}
            onChange={(e) => {
              setPriority(e.target.value);
              setPage(1);
            }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="">Priority</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
          <input
            value={department}
            onChange={(e) => {
              setDepartment(e.target.value);
              setPage(1);
            }}
            placeholder="Department"
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <input
            value={projectType}
            onChange={(e) => {
              setProjectType(e.target.value);
              setPage(1);
            }}
            placeholder="Project type"
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          {(status || priority || department || projectType || search) && (
            <button
              onClick={() => {
                setStatus('');
                setPriority('');
                setDepartment('');
                setProjectType('');
                setSearch('');
                setPage(1);
              }}
              className="text-slate-muted text-sm hover:text-white transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {error ? (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>Failed to load projects</span>
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={projects}
          keyField="id"
          loading={isLoading}
          emptyMessage="No projects found"
          onRowClick={(item) => router.push(`/projects/${(item as any).id}`)}
        />
      )}

      {total > pageSize && (
        <Pagination
          total={total}
          pageSize={pageSize}
          page={page}
          onPageChange={setPage}
          onPageSizeChange={setPageSize}
        />
      )}
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl p-4 bg-slate-card border border-slate-border">
      <p className="text-slate-muted text-sm mb-1 capitalize">{label.replace(/_/g, ' ')}</p>
      <p className="text-2xl font-bold text-white">{value}</p>
    </div>
  );
}
