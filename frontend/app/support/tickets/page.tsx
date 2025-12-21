'use client';

import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  LifeBuoy,
  Plus,
  Filter,
  AlertTriangle,
  Tag,
  Clock,
  User,
  CheckCircle,
  XCircle,
  Inbox,
  TrendingUp,
  Users,
  Target,
  ChevronRight,
  Search,
} from 'lucide-react';
import { DataTable, Pagination } from '@/components/DataTable';
import { useConsolidatedSupportDashboard, useSupportTickets, useSupportSlaBreachesSummary } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { usePersistentState } from '@/hooks/usePersistentState';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';

function formatDate(dateStr: string | null | undefined) {
  if (!dateStr) return '-';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-NG', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function formatTimeAgo(dateStr: string | null | undefined) {
  if (!dateStr) return '-';
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffHours / 24);

  if (diffDays > 0) return `${diffDays}d ago`;
  if (diffHours > 0) return `${diffHours}h ago`;
  return 'Just now';
}

function StatCard({
  label,
  value,
  icon: Icon,
  variant,
  onClick,
  active,
}: {
  label: string;
  value: number | string;
  icon?: React.ElementType;
  variant?: 'default' | 'warning' | 'success' | 'info';
  onClick?: () => void;
  active?: boolean;
}) {
  const variants = {
    default: 'bg-slate-card border-slate-border',
    warning: 'bg-rose-500/10 border-rose-500/30',
    success: 'bg-emerald-500/10 border-emerald-500/30',
    info: 'bg-blue-500/10 border-blue-500/30',
  };
  const textVariants = {
    default: 'text-white',
    warning: 'text-rose-400',
    success: 'text-emerald-400',
    info: 'text-blue-400',
  };
  const v = variant || 'default';

  return (
    <button
      onClick={onClick}
      className={cn(
        'rounded-xl p-4 border text-left transition-all',
        variants[v],
        onClick && 'hover:border-opacity-80 cursor-pointer',
        active && 'ring-2 ring-teal-electric ring-offset-2 ring-offset-slate-950'
      )}
    >
      <div className="flex items-center justify-between">
        <p className={cn('text-sm', v === 'default' ? 'text-slate-muted' : textVariants[v])}>{label}</p>
        {Icon && <Icon className={cn('w-4 h-4', textVariants[v])} />}
      </div>
      <p className={cn('text-2xl font-bold mt-1', textVariants[v])}>{value}</p>
    </button>
  );
}

function PriorityBadge({ priority }: { priority: string }) {
  const colors: Record<string, string> = {
    urgent: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
    high: 'bg-orange-500/10 text-orange-400 border-orange-500/30',
    medium: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    low: 'bg-slate-500/10 text-slate-300 border-slate-500/30',
  };
  const color = colors[priority] || colors.medium;

  return (
    <span className={cn('px-2 py-1 rounded-full text-xs font-medium border inline-flex items-center gap-1', color)}>
      <Tag className="w-3 h-3" />
      {priority}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    open: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
    in_progress: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    pending: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
    resolved: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    closed: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
    replied: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30',
    on_hold: 'bg-orange-500/10 text-orange-400 border-orange-500/30',
  };
  const color = colors[status] || colors.open;

  return (
    <span className={cn('px-2 py-1 rounded-full text-xs font-medium border capitalize', color)}>
      {status.replace(/_/g, ' ')}
    </span>
  );
}

export default function SupportTicketsPage() {
  const router = useRouter();
  const [filters, setFilters] = usePersistentState<{
    page: number;
    pageSize: number;
    priority: string;
    status: string;
    ticketType: string;
    agent: string;
    startDate: string;
    endDate: string;
    quickFilter: string;
  }>('support.tickets.filters', {
    page: 1,
    pageSize: 20,
    priority: '',
    status: '',
    ticketType: '',
    agent: '',
    startDate: '',
    endDate: '',
    quickFilter: '',
  });
  const { page, pageSize, priority, status, ticketType, agent, startDate, endDate, quickFilter } = filters;
  const offset = (page - 1) * pageSize;

  const { data, isLoading, error, mutate } = useSupportTickets({
    priority: (priority as any) || undefined,
    status: status || undefined,
    ticket_type: ticketType || undefined,
    agent: agent || undefined,
    start: startDate || undefined,
    end: endDate || undefined,
    limit: pageSize,
    offset,
  });

  const { data: supportDashboard } = useConsolidatedSupportDashboard();
  const { data: slaBreach } = useSupportSlaBreachesSummary({ days: 30 });
  const openTickets = supportDashboard?.summary?.open_tickets ?? 0;
  const resolvedTickets = supportDashboard?.summary?.resolved_tickets ?? 0;
  const totalTickets = openTickets + resolvedTickets;
  const slaAttainment = supportDashboard?.summary?.sla_attainment ?? 0;

  const tickets = data?.tickets || [];
  const total = data?.total || 0;

  const handleQuickFilter = (filter: string) => {
    if (quickFilter === filter) {
      setFilters((prev) => ({ ...prev, quickFilter: '', status: '', priority: '', page: 1 }));
    } else {
      setFilters((prev) => ({ ...prev, quickFilter: filter, page: 1 }));
      if (filter === 'open') {
        setFilters((prev) => ({ ...prev, status: 'open', priority: '' }));
      } else if (filter === 'urgent') {
        setFilters((prev) => ({ ...prev, priority: 'urgent', status: '' }));
      } else if (filter === 'resolved') {
        setFilters((prev) => ({ ...prev, status: 'resolved', priority: '' }));
      }
    }
  };

  const clearFilters = () => {
    setFilters({
      ...filters,
      priority: '',
      status: '',
      ticketType: '',
      agent: '',
      startDate: '',
      endDate: '',
      quickFilter: '',
      page: 1,
    });
  };

  const hasActiveFilters = priority || status || ticketType || agent || startDate || endDate;

  const columns = [
    {
      key: 'ticket',
      header: 'Ticket',
      render: (item: any) => (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-white font-semibold">{item.ticket_number || `#${item.id}`}</span>
            {item.is_overdue && (
              <span className="px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-400 text-[10px] font-medium">
                OVERDUE
              </span>
            )}
          </div>
          <span className="text-slate-200 text-sm line-clamp-1">{item.subject || '-'}</span>
          <span className="text-slate-muted text-xs">{item.customer_name || item.customer_email || '-'}</span>
        </div>
      ),
    },
    {
      key: 'priority',
      header: 'Priority',
      render: (item: any) => <PriorityBadge priority={item.priority || 'medium'} />,
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => <StatusBadge status={item.status || 'open'} />,
    },
    {
      key: 'type',
      header: 'Type',
      render: (item: any) => (
        <span className="text-slate-200 text-sm">{item.ticket_type || '-'}</span>
      ),
    },
    {
      key: 'assigned',
      header: 'Assigned',
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <User className="w-3 h-3 text-slate-muted" />
          <span className={cn('text-sm', item.assigned_to ? 'text-slate-200' : 'text-amber-400')}>
            {item.assigned_to || 'Unassigned'}
          </span>
        </div>
      ),
    },
    {
      key: 'resolution_by',
      header: 'Due',
      render: (item: any) => {
        const isOverdue = item.resolution_by && new Date(item.resolution_by) < new Date();
        return (
          <div className={cn('flex items-center gap-1 text-sm', isOverdue ? 'text-rose-400' : 'text-slate-200')}>
            <Clock className="w-3 h-3" />
            {formatDate(item.resolution_by)}
          </div>
        );
      },
    },
    {
      key: 'created',
      header: 'Created',
      render: (item: any) => (
        <div className="text-slate-200 text-sm">
          <div>{formatDate(item.created_at)}</div>
          <div className="text-xs text-slate-muted">{formatTimeAgo(item.created_at)}</div>
        </div>
      ),
    },
  ];

  if (isLoading) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load support tickets."
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-teal-electric/10 border border-teal-electric/30 flex items-center justify-center">
            <LifeBuoy className="w-5 h-5 text-teal-electric" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Support Tickets</h1>
            <p className="text-slate-muted text-sm">Browse, filter, and manage customer tickets</p>
          </div>
        </div>
        <Link
          href="/support/tickets/new"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New ticket
        </Link>
      </div>

      {/* Quick Stats */}
      {supportDashboard && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
          <StatCard
            label="Total"
            value={totalTickets}
            icon={Inbox}
          />
          <StatCard
            label="Open"
            value={openTickets}
            icon={AlertTriangle}
            variant="info"
            onClick={() => handleQuickFilter('open')}
            active={quickFilter === 'open'}
          />
          <StatCard
            label="Resolved"
            value={resolvedTickets}
            icon={CheckCircle}
            variant="success"
            onClick={() => handleQuickFilter('resolved')}
            active={quickFilter === 'resolved'}
          />
          <StatCard
            label="SLA Attainment"
            value={`${slaAttainment.toFixed(0)}%`}
            icon={Target}
          />
          <StatCard
            label="Overdue"
            value={slaBreach?.currently_overdue ?? supportDashboard.summary.overdue_tickets}
            icon={XCircle}
            variant="warning"
          />
          <StatCard
            label="Unassigned"
            value={supportDashboard.summary.unassigned_tickets}
            icon={Users}
          />
        </div>
      )}

      {/* Filters */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-teal-electric" />
            <span className="text-white text-sm font-medium">Filters</span>
          </div>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="text-slate-muted text-sm hover:text-white transition-colors flex items-center gap-1"
            >
              <XCircle className="w-3 h-3" />
              Clear all
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
            <input
              value={agent}
              onChange={(e) => {
                setFilters((prev) => ({ ...prev, agent: e.target.value, page: 1 }));
              }}
              placeholder="Search agent/email..."
              className="w-full bg-slate-elevated border border-slate-border rounded-lg pl-10 pr-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
          </div>
          <input
          value={ticketType}
          onChange={(e) => {
            setFilters((prev) => ({ ...prev, ticketType: e.target.value, page: 1 }));
          }}
          placeholder="Ticket type..."
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          />
          <select
          value={priority}
          onChange={(e) => {
            setFilters((prev) => ({ ...prev, priority: e.target.value, quickFilter: '', page: 1 }));
          }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="">All Priorities</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="urgent">Urgent</option>
          </select>
          <select
          value={status}
          onChange={(e) => {
            setFilters((prev) => ({ ...prev, status: e.target.value, quickFilter: '', page: 1 }));
          }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="">All Statuses</option>
            <option value="open">Open</option>
            <option value="in_progress">In Progress</option>
            <option value="pending">Pending</option>
            <option value="replied">Replied</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
            <option value="on_hold">On Hold</option>
          </select>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <span className="text-slate-muted text-xs">Date range:</span>
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={startDate}
              onChange={(e) => {
                setFilters((prev) => ({ ...prev, startDate: e.target.value, page: 1 }));
              }}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
            <ChevronRight className="w-4 h-4 text-slate-muted" />
            <input
              type="date"
              value={endDate}
              onChange={(e) => {
                setFilters((prev) => ({ ...prev, endDate: e.target.value, page: 1 }));
              }}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
          </div>
        </div>
      </div>

      {/* Results Info */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-muted">
          Showing {tickets.length} of {total} tickets
        </span>
        {hasActiveFilters && (
          <div className="flex items-center gap-2">
            {priority && (
              <span className="px-2 py-1 rounded-full bg-slate-elevated text-xs text-slate-muted">
                Priority: {priority}
              </span>
            )}
            {status && (
              <span className="px-2 py-1 rounded-full bg-slate-elevated text-xs text-slate-muted">
                Status: {status}
              </span>
            )}
            {ticketType && (
              <span className="px-2 py-1 rounded-full bg-slate-elevated text-xs text-slate-muted">
                Type: {ticketType}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Data Table */}
      {error ? (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 text-rose-400 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>Failed to load tickets. Please try again.</span>
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={tickets}
          keyField="id"
          loading={isLoading}
          emptyMessage="No tickets found matching your filters"
          onRowClick={(item) => router.push(`/support/tickets/${(item as any).id}`)}
        />
      )}

      {/* Pagination */}
      {total > pageSize && (
        <Pagination
          total={total}
          limit={pageSize}
          offset={offset}
          onPageChange={(newOffset) =>
            setFilters((prev) => ({ ...prev, page: Math.floor(newOffset / pageSize) + 1 }))
          }
          onLimitChange={(newLimit) => {
            setFilters((prev) => ({ ...prev, pageSize: newLimit, page: 1 }));
          }}
        />
      )}
    </div>
  );
}
