'use client';

import { useState, useMemo, useCallback } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import {
  Calendar,
  ChevronLeft,
  ChevronRight,
  Clock,
  MapPin,
  User,
  Grid3X3,
  List,
  Truck,
  AlertTriangle,
  Loader2,
  X,
} from 'lucide-react';
import { fieldServiceApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Button, FilterSelect } from '@/components/ui';

type ViewMode = 'calendar' | 'dispatch' | 'list';

const statusColors: Record<string, string> = {
  draft: 'bg-slate-500',
  scheduled: 'bg-blue-500',
  dispatched: 'bg-purple-500',
  en_route: 'bg-amber-500',
  on_site: 'bg-cyan-500',
  in_progress: 'bg-teal-500',
  completed: 'bg-green-500',
  cancelled: 'bg-red-500',
};

const priorityColors: Record<string, string> = {
  emergency: 'border-l-red-500',
  urgent: 'border-l-orange-500',
  high: 'border-l-amber-500',
  medium: 'border-l-blue-500',
  low: 'border-l-slate-500',
};

export default function SchedulePage() {
  const [viewMode, setViewMode] = useState<ViewMode>('calendar');
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedTeam, setSelectedTeam] = useState<string>('all');
  const [draggedOrder, setDraggedOrder] = useState<any>(null);
  const [dropTargetTech, setDropTargetTech] = useState<number | null>(null);
  const [isDispatching, setIsDispatching] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Get start and end of current month/week
  const dateRange = useMemo(() => {
    const start = new Date(currentDate.getFullYear(), currentDate.getMonth(), 1);
    const end = new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 0);
    return {
      start: start.toISOString().split('T')[0],
      end: end.toISOString().split('T')[0],
    };
  }, [currentDate]);

  const { data: ordersData, isLoading: ordersLoading } = useSWR(
    ['field-service-calendar', dateRange, selectedTeam],
    () => fieldServiceApi.getCalendar({
      start_date: dateRange.start,
      end_date: dateRange.end,
      team_id: selectedTeam !== 'all' ? parseInt(selectedTeam) : undefined,
    })
  );

  const { data: teams } = useSWR('field-teams', () =>
    fieldServiceApi.getTeams().then(r => r.data || [])
  );

  const { data: dispatchData, mutate: mutateDispatch } = useSWR(
    viewMode === 'dispatch' ? ['dispatch-board', dateRange.start] : null,
    () => fieldServiceApi.getDispatchBoard({ date: dateRange.start })
  );

  // Drag and drop handlers
  const handleDragStart = useCallback((e: React.DragEvent, order: any) => {
    setDraggedOrder(order);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', order.id.toString());
  }, []);

  const handleDragEnd = useCallback(() => {
    setDraggedOrder(null);
    setDropTargetTech(null);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent, techId: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDropTargetTech(techId);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDropTargetTech(null);
  }, []);

  const handleDrop = useCallback(async (e: React.DragEvent, techId: number) => {
    e.preventDefault();
    setDropTargetTech(null);

    if (!draggedOrder) return;

    setIsDispatching(true);
    setErrorMessage(null);

    try {
      await fieldServiceApi.dispatchOrder(draggedOrder.id, {
        technician_id: techId,
        notify_customer: true,
      });
      mutateDispatch();
    } catch (error: any) {
      const detail = error.response?.data?.detail;
      if (typeof detail === 'object' && detail?.message) {
        setErrorMessage(detail.message);
      } else if (typeof detail === 'string') {
        setErrorMessage(detail);
      } else {
        setErrorMessage('Failed to dispatch order');
      }
    } finally {
      setIsDispatching(false);
      setDraggedOrder(null);
    }
  }, [draggedOrder, mutateDispatch]);

  // Generate calendar days
  const calendarDays = useMemo(() => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startOffset = firstDay.getDay();

    const days: (Date | null)[] = [];

    // Add empty cells for days before month starts
    for (let i = 0; i < startOffset; i++) {
      days.push(null);
    }

    // Add all days of the month
    for (let d = 1; d <= lastDay.getDate(); d++) {
      days.push(new Date(year, month, d));
    }

    return days;
  }, [currentDate]);

  // Group orders by date
  const ordersByDate = useMemo(() => {
    const grouped: Record<string, any[]> = {};
    (ordersData || []).forEach((order: any) => {
      const date = order.scheduled_date;
      if (!grouped[date]) grouped[date] = [];
      grouped[date].push(order);
    });
    return grouped;
  }, [ordersData]);

  const navigateMonth = (direction: number) => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + direction, 1));
  };

  const today = new Date().toISOString().split('T')[0];
  const dispatchBoard = dispatchData as any;
  const unassignedOrders = dispatchBoard?.unassigned || [];
  const dispatchTechnicians = dispatchBoard?.technicians || (Array.isArray(dispatchData) ? dispatchData : []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            onClick={() => navigateMonth(-1)}
            className="p-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70 transition-colors"
          >
            <ChevronLeft className="w-5 h-5" />
          </Button>
          <h2 className="text-xl font-semibold text-foreground min-w-[200px] text-center">
            {currentDate.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
          </h2>
          <Button
            onClick={() => navigateMonth(1)}
            className="p-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70 transition-colors"
          >
            <ChevronRight className="w-5 h-5" />
          </Button>
          <Button
            onClick={() => setCurrentDate(new Date())}
            className="px-3 py-1.5 rounded-lg border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70 transition-colors"
          >
            Today
          </Button>
        </div>

        <div className="flex items-center gap-3">
          {/* Team Filter */}
          <FilterSelect
            value={selectedTeam}
            onChange={(e) => setSelectedTeam(e.target.value)}
          >
            <option value="all">All Teams</option>
            {teams?.map((team: any) => (
              <option key={team.id} value={team.id}>{team.name}</option>
            ))}
          </FilterSelect>

          {/* View Toggle */}
          <div className="flex items-center bg-slate-elevated border border-slate-border rounded-lg p-1">
            <Button
              onClick={() => setViewMode('calendar')}
              className={cn(
                'flex items-center gap-2 px-3 py-1.5 rounded text-sm transition-colors',
                viewMode === 'calendar'
                  ? 'bg-teal-electric text-slate-950'
                  : 'text-slate-muted hover:text-foreground'
              )}
            >
              <Grid3X3 className="w-4 h-4" />
              Calendar
            </Button>
            <Button
              onClick={() => setViewMode('dispatch')}
              className={cn(
                'flex items-center gap-2 px-3 py-1.5 rounded text-sm transition-colors',
                viewMode === 'dispatch'
                  ? 'bg-teal-electric text-slate-950'
                  : 'text-slate-muted hover:text-foreground'
              )}
            >
              <Truck className="w-4 h-4" />
              Dispatch
            </Button>
            <Button
              onClick={() => setViewMode('list')}
              className={cn(
                'flex items-center gap-2 px-3 py-1.5 rounded text-sm transition-colors',
                viewMode === 'list'
                  ? 'bg-teal-electric text-slate-950'
                  : 'text-slate-muted hover:text-foreground'
              )}
            >
              <List className="w-4 h-4" />
              List
            </Button>
          </div>
        </div>
      </div>

      {/* Calendar View */}
      {viewMode === 'calendar' && (
        <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
          {/* Day Headers */}
          <div className="grid grid-cols-7 border-b border-slate-border bg-slate-elevated/50">
            {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => (
              <div key={day} className="p-3 text-center text-sm font-medium text-slate-muted">
                {day}
              </div>
            ))}
          </div>

          {/* Calendar Grid */}
          <div className="grid grid-cols-7">
            {calendarDays.map((date, idx) => {
              if (!date) {
                return <div key={idx} className="min-h-[120px] bg-slate-elevated/20 border-b border-r border-slate-border" />;
              }

              const dateStr = date.toISOString().split('T')[0];
              const dayOrders = ordersByDate[dateStr] || [];
              const isToday = dateStr === today;

              return (
                <div
                  key={idx}
                  className={cn(
                    'min-h-[120px] p-2 border-b border-r border-slate-border',
                    isToday && 'bg-teal-electric/5'
                  )}
                >
                  <div className={cn(
                    'text-sm font-medium mb-2',
                    isToday ? 'text-teal-electric' : 'text-slate-muted'
                  )}>
                    {date.getDate()}
                  </div>
                  <div className="space-y-1">
                    {dayOrders.slice(0, 3).map((order: any) => (
                      <Link
                        key={order.id}
                        href={`/field-service/orders/${order.id}`}
                        className={cn(
                          'block px-2 py-1 rounded text-xs truncate border-l-2 transition-colors',
                          'bg-slate-elevated hover:bg-slate-elevated/80',
                          priorityColors[order.priority] || 'border-l-slate-500'
                        )}
                      >
                        <div className="flex items-center gap-1">
                          <div className={cn('w-1.5 h-1.5 rounded-full', statusColors[order.status])} />
                          <span className="text-foreground truncate">{order.title}</span>
                        </div>
                        {order.scheduled_start_time && (
                          <span className="text-slate-muted">{order.scheduled_start_time}</span>
                        )}
                      </Link>
                    ))}
                    {dayOrders.length > 3 && (
                      <div className="text-xs text-slate-muted px-2">
                        +{dayOrders.length - 3} more
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Dispatch Board View */}
      {viewMode === 'dispatch' && (
        <div className="space-y-4">
          {/* Error Message */}
          {errorMessage && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 flex items-center justify-between">
              <div className="flex items-center gap-2 text-red-400">
                <AlertTriangle className="w-5 h-5" />
                <span>{errorMessage}</span>
              </div>
              <Button onClick={() => setErrorMessage(null)} className="text-red-400 hover:text-red-300">
                <X className="w-4 h-4" />
              </Button>
            </div>
          )}

          {/* Dispatching Indicator */}
          {isDispatching && (
            <div className="bg-teal-electric/10 border border-teal-electric/30 rounded-lg px-4 py-3 flex items-center gap-2 text-teal-electric">
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Dispatching order...</span>
            </div>
          )}

          {/* Drag & Drop Instructions */}
          <p className="text-sm text-slate-muted">
            Drag unassigned orders to a technician column to dispatch
          </p>

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Unassigned Orders */}
            <div className="bg-slate-card border border-slate-border rounded-xl">
              <div className="p-4 border-b border-slate-border">
                <h3 className="font-semibold text-foreground flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  Unassigned
                  <span className="text-sm text-slate-muted">
                    ({unassignedOrders.length})
                  </span>
                </h3>
              </div>
              <div className="p-4 space-y-2 max-h-[500px] overflow-y-auto">
                {unassignedOrders.length > 0 ? (
                  unassignedOrders.map((order: any) => (
                    <div
                      key={order.id}
                      draggable
                      onDragStart={(e) => handleDragStart(e, order)}
                      onDragEnd={handleDragEnd}
                      className={cn(
                        'p-3 rounded-lg border-l-2 bg-slate-elevated cursor-grab active:cursor-grabbing transition-all',
                        priorityColors[order.priority],
                        draggedOrder?.id === order.id && 'opacity-50 scale-95'
                      )}
                    >
                      <Link href={`/field-service/orders/${order.id}`} className="block">
                        <p className="text-foreground text-sm font-medium truncate">{order.title}</p>
                        <div className="flex items-center gap-2 text-xs text-slate-muted mt-1">
                          <MapPin className="w-3 h-3" />
                          {order.city || 'Unknown'}
                        </div>
                      </Link>
                    </div>
                  ))
                ) : (
                  <p className="text-slate-muted text-sm text-center py-4">
                    All orders assigned
                  </p>
                )}
              </div>
            </div>

            {/* Technician Columns */}
            {dispatchTechnicians?.slice(0, 3).map((tech: any) => (
              <div
                key={tech.id}
                onDragOver={(e) => handleDragOver(e, tech.id)}
                onDragLeave={handleDragLeave}
                onDrop={(e) => handleDrop(e, tech.id)}
                className={cn(
                  'bg-slate-card border-2 rounded-xl transition-all',
                  dropTargetTech === tech.id
                    ? 'border-teal-electric bg-teal-electric/5'
                    : 'border-slate-border'
                )}
              >
                <div className="p-4 border-b border-slate-border">
                  <div className="flex items-center gap-3">
                    <div className={cn(
                      'w-8 h-8 rounded-full flex items-center justify-center transition-colors',
                      dropTargetTech === tech.id ? 'bg-teal-electric/20' : 'bg-slate-elevated'
                    )}>
                      <User className={cn(
                        'w-4 h-4',
                        dropTargetTech === tech.id ? 'text-teal-electric' : 'text-slate-muted'
                      )} />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground text-sm">{tech.name}</h3>
                      <p className="text-xs text-slate-muted">{tech.orders?.length || 0} orders</p>
                    </div>
                  </div>
                </div>
                <div className={cn(
                  'p-4 space-y-2 max-h-[500px] overflow-y-auto min-h-[100px] transition-colors',
                  dropTargetTech === tech.id && 'bg-teal-electric/5'
                )}>
                  {dropTargetTech === tech.id && (
                    <div className="border-2 border-dashed border-teal-electric rounded-lg p-3 text-center">
                      <p className="text-sm text-teal-electric">Drop here to assign</p>
                    </div>
                  )}
                  {tech.orders?.length > 0 ? (
                    tech.orders.map((order: any) => (
                      <Link
                        key={order.id}
                        href={`/field-service/orders/${order.id}`}
                        className={cn(
                          'block p-3 rounded-lg border-l-2 bg-slate-elevated hover:bg-slate-elevated/80 transition-colors',
                          priorityColors[order.priority]
                        )}
                      >
                        <div className="flex items-center gap-2">
                          <div className={cn('w-2 h-2 rounded-full', statusColors[order.status])} />
                          <p className="text-foreground text-sm font-medium truncate">{order.title}</p>
                        </div>
                        <div className="flex items-center justify-between text-xs text-slate-muted mt-1">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {order.scheduled_start_time || 'TBD'}
                          </span>
                          <span className="flex items-center gap-1">
                            <MapPin className="w-3 h-3" />
                            {order.city || 'N/A'}
                          </span>
                        </div>
                      </Link>
                    ))
                  ) : !dropTargetTech && (
                    <p className="text-slate-muted text-sm text-center py-4">
                      No orders assigned
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* List View */}
      {viewMode === 'list' && (
        <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-border bg-slate-elevated/50">
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-muted uppercase">Date</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-muted uppercase">Time</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-muted uppercase">Order</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-muted uppercase">Customer</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-muted uppercase">Technician</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-muted uppercase">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-border">
              {ordersLoading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-muted">
                    Loading...
                  </td>
                </tr>
              ) : ordersData && ordersData.length > 0 ? (
                ordersData.map((order: any) => (
                  <tr key={order.id} className="hover:bg-slate-elevated/30 transition-colors">
                    <td className="px-4 py-3 text-sm text-foreground">
                      {order.scheduled_date
                        ? new Date(order.scheduled_date).toLocaleDateString('en-NG', {
                            month: 'short',
                            day: 'numeric',
                          })
                        : 'TBD'}
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-muted">
                      {order.scheduled_start_time || 'TBD'}
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/field-service/orders/${order.id}`}
                        className="text-foreground text-sm hover:text-teal-electric transition-colors"
                      >
                        {order.title}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-muted">
                      {order.customer_name || 'N/A'}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      {order.technician_name ? (
                        <span className="text-foreground">{order.technician_name}</span>
                      ) : (
                        <span className="text-amber-400">Unassigned</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className={cn('w-2 h-2 rounded-full', statusColors[order.status])} />
                        <span className="text-sm text-slate-muted capitalize">
                          {order.status.replace('_', ' ')}
                        </span>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-muted">
                    No orders scheduled for this period
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center gap-6 text-sm text-slate-muted">
        <span className="font-medium">Status:</span>
        {Object.entries(statusColors).map(([status, color]) => (
          <div key={status} className="flex items-center gap-1.5">
            <div className={cn('w-2 h-2 rounded-full', color)} />
            <span className="capitalize">{status.replace('_', ' ')}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
