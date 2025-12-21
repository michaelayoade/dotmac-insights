'use client';

import { useState } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import {
  ClipboardList,
  Search,
  Filter,
  Plus,
  MapPin,
  Calendar,
  User,
  AlertTriangle,
  Clock,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { fieldServiceApi, FieldServiceOrder, FieldServiceOrderPriority, FieldServiceOrderStatus } from '@/lib/api';
import { cn } from '@/lib/utils';

const statusConfig: Record<FieldServiceOrderStatus, { color: string; bg: string; label: string }> = {
  draft: { color: 'text-slate-400', bg: 'bg-slate-500/10', label: 'Draft' },
  scheduled: { color: 'text-blue-400', bg: 'bg-blue-500/10', label: 'Scheduled' },
  dispatched: { color: 'text-purple-400', bg: 'bg-purple-500/10', label: 'Dispatched' },
  en_route: { color: 'text-amber-400', bg: 'bg-amber-500/10', label: 'En Route' },
  on_site: { color: 'text-cyan-400', bg: 'bg-cyan-500/10', label: 'On Site' },
  in_progress: { color: 'text-teal-400', bg: 'bg-teal-500/10', label: 'In Progress' },
  completed: { color: 'text-green-400', bg: 'bg-green-500/10', label: 'Completed' },
  cancelled: { color: 'text-red-400', bg: 'bg-red-500/10', label: 'Cancelled' },
  rescheduled: { color: 'text-orange-400', bg: 'bg-orange-500/10', label: 'Rescheduled' },
  failed: { color: 'text-red-400', bg: 'bg-red-500/10', label: 'Failed' },
};

const priorityConfig: Record<string, { color: string; bg: string }> = {
  emergency: { color: 'text-red-500', bg: 'bg-red-500/10' },
  urgent: { color: 'text-orange-500', bg: 'bg-orange-500/10' },
  high: { color: 'text-amber-500', bg: 'bg-amber-500/10' },
  medium: { color: 'text-blue-500', bg: 'bg-blue-500/10' },
  low: { color: 'text-slate-400', bg: 'bg-slate-400/10' },
};

export default function ServiceOrdersPage() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [priorityFilter, setPriorityFilter] = useState<string>('all');
  const [page, setPage] = useState(1);
  const limit = 20;

  const { data, isLoading } = useSWR(
    ['field-service-orders', search, statusFilter, priorityFilter, page],
    () => fieldServiceApi.getOrders({
      search: search || undefined,
      status: statusFilter !== 'all' ? statusFilter as FieldServiceOrderStatus : undefined,
      priority: priorityFilter !== 'all' ? priorityFilter as FieldServiceOrderPriority : undefined,
      offset: (page - 1) * limit,
      limit,
    })
  );

  const orders = data?.data || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / limit);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-foreground">Service Orders</h2>
          <p className="text-sm text-slate-muted">
            {total} order{total !== 1 ? 's' : ''} total
          </p>
        </div>
        <Link
          href="/field-service/orders/new"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Order
        </Link>
      </div>

      {/* Filters */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="flex flex-wrap gap-4">
          {/* Search */}
          <div className="flex-1 min-w-[250px]">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
              <input
                type="text"
                placeholder="Search orders, customers, technicians..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground placeholder-slate-muted focus:outline-none focus:border-teal-electric/50"
              />
            </div>
          </div>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:border-teal-electric/50"
          >
            <option value="all">All Status</option>
            {Object.entries(statusConfig).map(([value, { label }]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>

          {/* Priority Filter */}
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:border-teal-electric/50"
          >
            <option value="all">All Priority</option>
            <option value="emergency">Emergency</option>
            <option value="urgent">Urgent</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>
      </div>

      {/* Orders List */}
      <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-slate-muted">Loading orders...</div>
        ) : orders.length === 0 ? (
          <div className="p-12 text-center">
            <ClipboardList className="w-12 h-12 mx-auto mb-3 text-slate-muted opacity-50" />
            <p className="text-lg text-slate-muted mb-2">No orders found</p>
            <p className="text-sm text-slate-muted mb-4">
              {search || statusFilter !== 'all' || priorityFilter !== 'all'
                ? 'Try adjusting your filters'
                : 'Create your first service order'}
            </p>
            <Link
              href="/field-service/orders/new"
              className="text-teal-electric hover:underline"
            >
              Create a new order
            </Link>
          </div>
        ) : (
          <>
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-border bg-slate-elevated/50">
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-muted uppercase tracking-wider">Order</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-muted uppercase tracking-wider">Customer</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-muted uppercase tracking-wider">Schedule</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-muted uppercase tracking-wider">Technician</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-muted uppercase tracking-wider">Priority</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-muted uppercase tracking-wider">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-border">
                {orders.map((order: FieldServiceOrder) => {
                  const status = statusConfig[order.status as FieldServiceOrderStatus] || statusConfig.draft;
                  const priority = priorityConfig[order.priority] || priorityConfig.medium;

                  return (
                    <tr key={order.id} className="hover:bg-slate-elevated/30 transition-colors">
                      <td className="px-4 py-4">
                        <Link
                          href={`/field-service/orders/${order.id}`}
                          className="block"
                        >
                          <p className="text-foreground font-medium hover:text-teal-electric transition-colors">
                            {order.order_number}
                          </p>
                          <p className="text-sm text-slate-muted truncate max-w-[200px]">
                            {order.title}
                          </p>
                        </Link>
                      </td>
                      <td className="px-4 py-4">
                        <p className="text-foreground text-sm">{order.customer_name || 'N/A'}</p>
                        <div className="flex items-center gap-1 text-xs text-slate-muted mt-0.5">
                          <MapPin className="w-3 h-3" />
                          {order.city || 'Unknown'}
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        {order.scheduled_date ? (
                          <div className="flex items-center gap-1 text-sm text-foreground">
                            <Calendar className="w-3.5 h-3.5 text-slate-muted" />
                            {new Date(order.scheduled_date).toLocaleDateString('en-NG', {
                              month: 'short',
                              day: 'numeric',
                            })}
                            {order.scheduled_start_time && (
                              <span className="text-slate-muted ml-1">
                                {order.scheduled_start_time}
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-sm text-slate-muted">Not scheduled</span>
                        )}
                      </td>
                      <td className="px-4 py-4">
                        {order.technician_name ? (
                          <div className="flex items-center gap-2">
                            <div className="w-6 h-6 rounded-full bg-slate-elevated flex items-center justify-center">
                              <User className="w-3.5 h-3.5 text-slate-muted" />
                            </div>
                            <span className="text-sm text-foreground">{order.technician_name}</span>
                          </div>
                        ) : (
                          <span className="text-sm text-amber-400 flex items-center gap-1">
                            <AlertTriangle className="w-3.5 h-3.5" />
                            Unassigned
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-4">
                        <span className={cn(
                          'px-2 py-1 rounded text-xs font-medium capitalize',
                          priority.color,
                          priority.bg
                        )}>
                          {order.priority}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        <span className={cn(
                          'px-2 py-1 rounded text-xs font-medium',
                          status.color,
                          status.bg
                        )}>
                          {status.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-slate-border">
                <p className="text-sm text-slate-muted">
                  Showing {(page - 1) * limit + 1} to {Math.min(page * limit, total)} of {total}
                </p>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="p-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span className="text-sm text-foreground px-2">
                    Page {page} of {totalPages}
                  </span>
                  <button
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className="p-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
