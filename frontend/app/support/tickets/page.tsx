'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { LifeBuoy, Search, Plus, Filter, AlertTriangle, Tag, Clock } from 'lucide-react';
import { DataTable, Pagination } from '@/components/DataTable';
import { useSupportDashboard, useSupportOverview, useSupportTickets } from '@/hooks/useApi';
import { cn } from '@/lib/utils';

function formatDate(dateStr: string | null | undefined) {
  if (!dateStr) return '-';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-NG', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export default function SupportTicketsPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [priority, setPriority] = useState<string>('');
  const [status, setStatus] = useState<string>('');
  const [ticketType, setTicketType] = useState<string>('');
  const [agent, setAgent] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');

  const { data, isLoading, error } = useSupportTickets({
    priority: priority || undefined,
    status: status || undefined,
    ticket_type: ticketType || undefined,
    agent: agent || undefined,
    start: startDate || undefined,
    end: endDate || undefined,
    limit: pageSize,
    offset: (page - 1) * pageSize,
  });

  const { data: overview } = useSupportOverview({
    priority: priority || undefined,
    ticket_type: ticketType || undefined,
    agent: agent || undefined,
    start: startDate || undefined,
    end: endDate || undefined,
  });

  const tickets = data?.tickets || [];
  const total = data?.total || 0;
  const { data: supportDashboard } = useSupportDashboard();

  const columns = [
    {
      key: 'ticket',
      header: 'Ticket',
      render: (item: any) => (
        <div className="flex flex-col">
          <span className="font-mono text-white font-semibold">{item.ticket_number || `#${item.id}`}</span>
          <span className="text-slate-200 text-sm line-clamp-1">{item.subject || '-'}</span>
        </div>
      ),
    },
    {
      key: 'priority',
      header: 'Priority',
      render: (item: any) => {
        const pri = item.priority || 'medium';
        const color =
          pri === 'urgent'
            ? 'bg-red-500/10 text-red-400 border-red-500/30'
            : pri === 'high'
            ? 'bg-orange-500/10 text-orange-400 border-orange-500/30'
            : pri === 'medium'
            ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30'
            : 'bg-slate-500/10 text-slate-300 border-slate-500/30';
        return (
          <span className={cn('px-2 py-1 rounded-full text-xs font-medium border inline-flex items-center gap-1', color)}>
            <Tag className="w-3 h-3" />
            {pri}
          </span>
        );
      },
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => (
        <span className="text-slate-200 capitalize text-sm">{item.status || '-'}</span>
      ),
    },
    {
      key: 'type',
      header: 'Type',
      render: (item: any) => <span className="text-slate-200 text-sm">{item.ticket_type || '-'}</span>,
    },
    {
      key: 'assigned',
      header: 'Assigned',
      render: (item: any) => <span className="text-slate-200 text-sm">{item.assigned_to || 'Unassigned'}</span>,
    },
    {
      key: 'resolution_by',
      header: 'Resolution By',
      render: (item: any) => (
        <div className="flex items-center gap-1 text-sm text-slate-200">
          <Clock className="w-3 h-3 text-slate-muted" />
          {formatDate(item.resolution_by)}
        </div>
      ),
    },
    {
      key: 'created',
      header: 'Created',
      render: (item: any) => <span className="text-slate-200 text-sm">{formatDate(item.created_at)}</span>,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-teal-electric/10 border border-teal-electric/30 flex items-center justify-center">
            <LifeBuoy className="w-5 h-5 text-teal-electric" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Support Tickets</h1>
            <p className="text-slate-muted text-sm">Browse, filter, and drill into customer tickets</p>
          </div>
        </div>
        <Link
          href="/support/tickets/new"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90"
        >
          <Plus className="w-4 h-4" />
          New ticket
        </Link>
      </div>

      {supportDashboard && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
          <SummaryCard label="Total" value={supportDashboard.tickets.total} />
          <SummaryCard label="Open" value={supportDashboard.tickets.open} />
          <SummaryCard label="Resolved" value={supportDashboard.tickets.resolved} />
          <SummaryCard label="SLA Met" value={supportDashboard.sla.met} />
          <SummaryCard label="Overdue" value={supportDashboard.metrics.overdue_tickets} variant="warning" />
        </div>
      )}

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-teal-electric" />
          <span className="text-white text-sm font-medium">Filters</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <input
            value={agent}
            onChange={(e) => {
              setAgent(e.target.value);
              setPage(1);
            }}
            placeholder="Agent/email"
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <input
            value={ticketType}
            onChange={(e) => {
              setTicketType(e.target.value);
              setPage(1);
            }}
            placeholder="Ticket type"
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
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
            <option value="urgent">Urgent</option>
          </select>
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
            <option value="replied">Replied</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
            <option value="on_hold">On Hold</option>
          </select>
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
                setPage(1);
              }}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50 flex-1"
            />
            <span className="text-slate-muted text-xs">to</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value);
                setPage(1);
              }}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50 flex-1"
            />
          </div>
          {(priority || status || ticketType || agent || startDate || endDate) && (
            <button
              onClick={() => {
                setPriority('');
                setStatus('');
                setTicketType('');
                setAgent('');
                setStartDate('');
                setEndDate('');
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
          <span>Failed to load tickets</span>
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={tickets}
          keyField="id"
          loading={isLoading}
          emptyMessage="No tickets found"
          onRowClick={(item) => router.push(`/support/tickets/${(item as any).id}`)}
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

function SummaryCard({ label, value, variant }: { label: string; value: number | string; variant?: 'warning' }) {
  return (
    <div className={cn('rounded-xl p-4 border', variant === 'warning' ? 'bg-red-500/10 border-red-500/30' : 'bg-slate-card border-slate-border')}>
      <p className={cn('text-sm mb-1', variant === 'warning' ? 'text-red-400' : 'text-slate-muted')}>{label}</p>
      <p className={cn('text-2xl font-bold', variant === 'warning' ? 'text-red-400' : 'text-white')}>{value}</p>
    </div>
  );
}
