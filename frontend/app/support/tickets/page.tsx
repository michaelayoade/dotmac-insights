'use client';

import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  LifeBuoy,
  Plus,
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
} from 'lucide-react';
import { DataTable, Pagination } from '@/components/DataTable';
import { SelectableStatCard } from '@/components/StatCard';
import { useConsolidatedSupportDashboard, useSupportTickets, useSupportSlaBreachesSummary, useSupportTeams } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { formatDate, formatRelativeTime } from '@/lib/formatters';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import { usePersistentState } from '@/hooks/usePersistentState';
import { ErrorDisplay } from '@/components/insights/shared';
import { Button, FilterCard, FilterInput, FilterSelect, LoadingState, StatusPill } from '@/components/ui';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';


function PriorityBadge({ priority }: { priority: string }) {
  const colors: Record<string, string> = {
    urgent: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
    high: 'bg-orange-500/10 text-orange-400 border-orange-500/30',
    medium: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    low: 'bg-slate-500/10 text-foreground-secondary border-slate-500/30',
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
  const tones: Record<string, StatusTone> = {
    open: 'info',
    in_progress: 'warning',
    pending: 'warning',
    resolved: 'success',
    closed: 'default',
    replied: 'info',
    on_hold: 'warning',
  };

  return (
    <StatusPill
      label={formatStatusLabel(status)}
      tone={tones[status] || 'default'}
    />
  );
}

export default function SupportTicketsPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('support:read');
  const router = useRouter();
  const [filters, setFilters] = usePersistentState<{
    page: number;
    pageSize: number;
    priority: string;
    status: string;
    ticketType: string;
    agent: string;
    teamId: string;
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
    teamId: '',
    startDate: '',
    endDate: '',
    quickFilter: '',
  });
  const { page, pageSize, priority, status, ticketType, agent, teamId, startDate, endDate, quickFilter } = filters;
  const canFetch = !authLoading && !missingScope;

  // Fetch teams for filter dropdown
  const { data: teamsData } = useSupportTeams({ isPaused: () => !canFetch });
  const teams = teamsData?.teams || [];
  const offset = (page - 1) * pageSize;

  const { data, isLoading, error, mutate } = useSupportTickets({
    priority: (priority as any) || undefined,
    status: status || undefined,
    ticket_type: ticketType || undefined,
    agent: agent || undefined,
    team_id: teamId ? Number(teamId) : undefined,
    start: startDate || undefined,
    end: endDate || undefined,
    limit: pageSize,
    offset,
  }, { isPaused: () => !canFetch });

  const { data: supportDashboard } = useConsolidatedSupportDashboard(undefined, { isPaused: () => !canFetch });
  const { data: slaBreach } = useSupportSlaBreachesSummary({ days: 30 }, { isPaused: () => !canFetch });
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
      teamId: '',
      startDate: '',
      endDate: '',
      quickFilter: '',
      page: 1,
    });
  };

  const hasActiveFilters = priority || status || ticketType || agent || teamId || startDate || endDate;

  const columns = [
    {
      key: 'ticket',
      header: 'Ticket',
      render: (item: any) => (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-foreground font-semibold">{item.ticket_number || `#${item.id}`}</span>
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
          <div className="text-xs text-slate-muted">{formatRelativeTime(item.created_at)}</div>
        </div>
      ),
    },
  ];

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the support:read permission to view tickets."
        backHref="/support"
        backLabel="Back to Support"
      />
    );
  }

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
            <h1 className="text-2xl font-bold text-foreground">Support Tickets</h1>
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
          <SelectableStatCard
            title="Total"
            value={totalTickets}
            icon={Inbox}
          />
          <SelectableStatCard
            title="Open"
            value={openTickets}
            icon={AlertTriangle}
            variant="info"
            onClick={() => handleQuickFilter('open')}
            active={quickFilter === 'open'}
          />
          <SelectableStatCard
            title="Resolved"
            value={resolvedTickets}
            icon={CheckCircle}
            variant="success"
            onClick={() => handleQuickFilter('resolved')}
            active={quickFilter === 'resolved'}
          />
          <SelectableStatCard
            title="SLA Attainment"
            value={`${slaAttainment.toFixed(0)}%`}
            icon={Target}
          />
          <SelectableStatCard
            title="Overdue"
            value={slaBreach?.currently_overdue ?? supportDashboard.summary.overdue_tickets}
            icon={XCircle}
            variant="danger"
          />
          <SelectableStatCard
            title="Unassigned"
            value={supportDashboard.summary.unassigned_tickets}
            icon={Users}
          />
        </div>
      )}

      {/* Filters */}
      <FilterCard
        actions={hasActiveFilters && (
          <Button
            onClick={clearFilters}
            className="text-slate-muted text-sm hover:text-foreground transition-colors flex items-center gap-1"
          >
            <XCircle className="w-3 h-3" />
            Clear all
          </Button>
        )}
        contentClassName="space-y-4"
      >
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
          <FilterInput
            value={agent}
            onChange={(e) => {
              setFilters((prev) => ({ ...prev, agent: e.target.value, page: 1 }));
            }}
            placeholder="Search agent/email..."
          />
          <FilterSelect
            value={teamId}
            onChange={(e) => {
              setFilters((prev) => ({ ...prev, teamId: e.target.value, page: 1 }));
            }}
          >
            <option value="">All Teams</option>
            {teams.map((team: any) => (
              <option key={team.id} value={team.id}>
                {team.team_name}
              </option>
            ))}
          </FilterSelect>
          <FilterInput
            value={ticketType}
            onChange={(e) => {
              setFilters((prev) => ({ ...prev, ticketType: e.target.value, page: 1 }));
            }}
            placeholder="Ticket type..."
          />
          <FilterSelect
            value={priority}
            onChange={(e) => {
              setFilters((prev) => ({ ...prev, priority: e.target.value, quickFilter: '', page: 1 }));
            }}
          >
            <option value="">All Priorities</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="urgent">Urgent</option>
          </FilterSelect>
          <FilterSelect
            value={status}
            onChange={(e) => {
              setFilters((prev) => ({ ...prev, status: e.target.value, quickFilter: '', page: 1 }));
            }}
          >
            <option value="">All Statuses</option>
            <option value="open">Open</option>
            <option value="in_progress">In Progress</option>
            <option value="pending">Pending</option>
            <option value="replied">Replied</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
            <option value="on_hold">On Hold</option>
          </FilterSelect>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <span className="text-slate-muted text-xs">Date range:</span>
          <div className="flex items-center gap-2">
            <FilterInput
              type="date"
              value={startDate}
              onChange={(e) => {
                setFilters((prev) => ({ ...prev, startDate: e.target.value, page: 1 }));
              }}
              className="max-w-[170px]"
            />
            <ChevronRight className="w-4 h-4 text-slate-muted" />
            <FilterInput
              type="date"
              value={endDate}
              onChange={(e) => {
                setFilters((prev) => ({ ...prev, endDate: e.target.value, page: 1 }));
              }}
              className="max-w-[170px]"
            />
          </div>
        </div>
      </FilterCard>

      {/* Results Info */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-muted">
          Showing {tickets.length} of {total} tickets
        </span>
        {hasActiveFilters && (
          <div className="flex items-center gap-2 flex-wrap">
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
            {teamId && (
              <span className="px-2 py-1 rounded-full bg-slate-elevated text-xs text-slate-muted">
                Team: {teams.find((t: any) => t.id === Number(teamId))?.team_name || teamId}
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
