'use client';

import { useState } from 'react';
import { DataTable, Pagination } from '@/components/DataTable';
import { useHrTrainingPrograms, useHrTrainingEvents, useHrTrainingResults } from '@/hooks/useApi';
import { cn, formatDate, formatDateTime } from '@/lib/utils';
import { GraduationCap, MapPin, Users } from 'lucide-react';

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

export default function HrTrainingPage() {
  const [status, setStatus] = useState('scheduled');
  const [company, setCompany] = useState('');
  const [eventLimit, setEventLimit] = useState(20);
  const [eventOffset, setEventOffset] = useState(0);
  const [resultLimit, setResultLimit] = useState(20);
  const [resultOffset, setResultOffset] = useState(0);

  const { data: programs, isLoading: programsLoading } = useHrTrainingPrograms();
  const { data: events, isLoading: eventsLoading } = useHrTrainingEvents({
    status: status || undefined,
    company: company || undefined,
    limit: eventLimit,
    offset: eventOffset,
  });
  const { data: results, isLoading: resultsLoading } = useHrTrainingResults({
    limit: resultLimit,
    offset: resultOffset,
    employee_id: undefined,
  });

  const programList = extractList(programs);
  const eventList = extractList(events);
  const resultList = extractList(results);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard label="Training Programs" value={programList.total} icon={GraduationCap} tone="text-teal-electric" />
        <StatCard label="Events" value={eventList.total} icon={MapPin} tone="text-purple-300" />
        <StatCard label="Results" value={resultList.total} icon={Users} tone="text-green-300" />
      </div>

      <div className="flex flex-wrap gap-3 items-center">
        <input
          type="text"
          placeholder="Company"
          value={company}
          onChange={(e) => {
            setCompany(e.target.value);
            setEventOffset(0);
          }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        />
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setEventOffset(0);
          }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        >
          <option value="">All statuses</option>
          <option value="scheduled">Scheduled</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      <DataTable
        columns={[
          { key: 'program_name', header: 'Program', render: (item: any) => <span className="text-white">{item.program_name}</span> },
          { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
          { key: 'description', header: 'Description', render: (item: any) => <span className="text-slate-muted text-sm truncate max-w-[200px] block">{item.description || '—'}</span> },
        ]}
        data={(programList.items || []).map((item: any) => ({ ...item, id: item.id || item.program_name }))}
        keyField="id"
        loading={programsLoading}
        emptyMessage="No training programs"
      />

      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <MapPin className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Training Events</h3>
        </div>
        <DataTable
          columns={[
            { key: 'training_event_name', header: 'Event', render: (item: any) => <span className="text-white">{item.training_event_name}</span> },
            { key: 'training_program', header: 'Program', render: (item: any) => <span className="text-slate-muted text-sm">{item.training_program}</span> },
            { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
            {
              key: 'start_time',
              header: 'Start',
              render: (item: any) => <span className="text-slate-muted text-sm">{formatDateTime(item.start_time)}</span>,
            },
            {
              key: 'end_time',
              header: 'End',
              render: (item: any) => <span className="text-slate-muted text-sm">{formatDateTime(item.end_time)}</span>,
            },
            {
              key: 'employees',
              header: 'Participants',
              align: 'right' as const,
              render: (item: any) => <span className="font-mono text-white">{item.employees?.length ?? 0}</span>,
            },
            {
              key: 'status',
              header: 'Status',
              render: (item: any) => (
                <span className={cn('px-2 py-1 rounded-full text-xs border capitalize', item.status === 'completed' ? 'border-green-400 text-green-300 bg-green-500/10' : item.status === 'cancelled' ? 'border-red-400 text-red-300 bg-red-500/10' : 'border-amber-400 text-amber-300 bg-amber-500/10')}>
                  {item.status || 'scheduled'}
                </span>
              ),
            },
          ]}
          data={(eventList.items || []).map((item: any) => ({ ...item, id: item.id || item.training_event_name }))}
          keyField="id"
          loading={eventsLoading}
          emptyMessage="No training events"
        />
        {eventList.total > eventLimit && (
          <Pagination
            total={eventList.total}
            limit={eventLimit}
            offset={eventOffset}
            onPageChange={setEventOffset}
            onLimitChange={(val) => {
              setEventLimit(val);
              setEventOffset(0);
            }}
          />
        )}
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <Users className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Training Results</h3>
        </div>
        <DataTable
          columns={[
            { key: 'employee', header: 'Employee', render: (item: any) => <span className="text-white">{item.employee_name || item.employee}</span> },
            { key: 'training_event', header: 'Event', render: (item: any) => <span className="text-slate-muted text-sm">{item.training_event}</span> },
            { key: 'result', header: 'Result', render: (item: any) => <span className="text-slate-muted text-sm capitalize">{item.result || '—'}</span> },
            { key: 'score', header: 'Score', align: 'right' as const, render: (item: any) => <span className="font-mono text-white">{item.score ?? '—'}</span> },
            { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
          ]}
          data={(resultList.items || []).map((item: any) => ({ ...item, id: item.id || `${item.employee}-${item.training_event}` }))}
          keyField="id"
          loading={resultsLoading}
          emptyMessage="No training results"
        />
        {resultList.total > resultLimit && (
          <Pagination
            total={resultList.total}
            limit={resultLimit}
            offset={resultOffset}
            onPageChange={setResultOffset}
            onLimitChange={(val) => {
              setResultLimit(val);
              setResultOffset(0);
            }}
          />
        )}
      </div>
    </div>
  );
}
