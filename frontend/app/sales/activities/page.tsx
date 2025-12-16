'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import {
  Plus,
  Search,
  Filter,
  Phone,
  Mail,
  Calendar,
  CheckSquare,
  FileText,
  Video,
  Clock,
  CheckCircle,
  XCircle,
  MoreHorizontal,
  Building2,
  User,
  Target,
  AlertCircle,
} from 'lucide-react';
import { useActivities, useUpcomingActivities, useOverdueActivities, useActivityMutations } from '@/hooks/useApi';
import { formatDate, formatDistanceToNow, isToday, isTomorrow, isPast } from '@/lib/date';
import type { Activity } from '@/lib/api';

const activityTypeIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  call: Phone,
  meeting: Calendar,
  email: Mail,
  task: CheckSquare,
  note: FileText,
  demo: Video,
  follow_up: Clock,
};

const activityTypeColors: Record<string, string> = {
  call: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  meeting: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  email: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  task: 'bg-violet-500/20 text-violet-400 border-violet-500/30',
  note: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
  demo: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  follow_up: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
};

const statusColors: Record<string, string> = {
  planned: 'bg-blue-500/20 text-blue-400',
  completed: 'bg-emerald-500/20 text-emerald-400',
  cancelled: 'bg-slate-500/20 text-slate-400',
};

export default function ActivitiesPage() {
  const searchParams = useSearchParams();
  const [search, setSearch] = useState('');
  const [activityType, setActivityType] = useState<string>('');
  const [status, setStatus] = useState<string>('');
  const [page, setPage] = useState(1);

  // Get filter from URL params
  const leadId = searchParams.get('lead_id');
  const customerId = searchParams.get('customer_id');
  const opportunityId = searchParams.get('opportunity_id');

  const { data: activities, isLoading } = useActivities({
    search: search || undefined,
    activity_type: activityType || undefined,
    status: status || undefined,
    lead_id: leadId ? parseInt(leadId) : undefined,
    customer_id: customerId ? parseInt(customerId) : undefined,
    opportunity_id: opportunityId ? parseInt(opportunityId) : undefined,
    page,
    page_size: 20,
  });

  const { data: upcoming } = useUpcomingActivities(5);
  const { data: overdue } = useOverdueActivities();
  const { completeActivity, cancelActivity } = useActivityMutations();

  const handleComplete = async (id: number) => {
    try {
      await completeActivity(id);
    } catch (error) {
      console.error('Failed to complete activity:', error);
    }
  };

  const handleCancel = async (id: number) => {
    try {
      await cancelActivity(id);
    } catch (error) {
      console.error('Failed to cancel activity:', error);
    }
  };

  const getScheduleLabel = (date: string) => {
    const d = new Date(date);
    if (isToday(d)) return 'Today';
    if (isTomorrow(d)) return 'Tomorrow';
    if (isPast(d)) return 'Overdue';
    return formatDate(d, 'MMM d');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Activities</h1>
          <p className="text-sm text-slate-400 mt-1">
            Track calls, meetings, tasks, and follow-ups
          </p>
        </div>
        <Link
          href="/sales/activities/new"
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Activity
        </Link>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
          <div className="text-sm text-slate-400">Today</div>
          <div className="text-2xl font-semibold text-white mt-1">
            {upcoming?.items?.filter((a: Activity) => a.scheduled_at && isToday(new Date(a.scheduled_at))).length || 0}
          </div>
        </div>
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
          <div className="text-sm text-slate-400">Upcoming</div>
          <div className="text-2xl font-semibold text-blue-400 mt-1">
            {upcoming?.items?.length || 0}
          </div>
        </div>
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
          <div className="text-sm text-red-400">Overdue</div>
          <div className="text-2xl font-semibold text-red-400 mt-1">
            {overdue?.items?.length || 0}
          </div>
        </div>
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
          <div className="text-sm text-slate-400">Completed Today</div>
          <div className="text-2xl font-semibold text-emerald-400 mt-1">
            {activities?.items?.filter((a: Activity) => a.status === 'completed' && a.completed_at && isToday(new Date(a.completed_at))).length || 0}
          </div>
        </div>
      </div>

      {/* Overdue Alert */}
      {overdue && overdue.items?.length > 0 && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
          <div className="flex items-center gap-2 text-red-400 mb-3">
            <AlertCircle className="w-5 h-5" />
            <span className="font-medium">Overdue Activities</span>
          </div>
          <div className="space-y-2">
            {overdue.items.slice(0, 3).map((activity: Activity) => {
              const Icon = activityTypeIcons[activity.activity_type] || Clock;
              return (
                <div key={activity.id} className="flex items-center justify-between bg-slate-800/50 rounded-lg p-3">
                  <div className="flex items-center gap-3">
                    <Icon className="w-4 h-4 text-red-400" />
                    <div>
                      <div className="text-white text-sm">{activity.subject}</div>
                      <div className="text-xs text-slate-400">
                        {activity.scheduled_at && formatDistanceToNow(activity.scheduled_at)}
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => handleComplete(activity.id)}
                    className="px-3 py-1 text-xs bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 rounded-lg transition-colors"
                  >
                    Complete
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search activities..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
          />
        </div>
        <select
          value={activityType}
          onChange={(e) => setActivityType(e.target.value)}
          className="px-4 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
        >
          <option value="">All Types</option>
          <option value="call">Calls</option>
          <option value="meeting">Meetings</option>
          <option value="email">Emails</option>
          <option value="task">Tasks</option>
          <option value="demo">Demos</option>
          <option value="follow_up">Follow-ups</option>
        </select>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="px-4 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
        >
          <option value="">All Status</option>
          <option value="planned">Planned</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      {/* Activities List */}
      <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-400" />
          </div>
        ) : activities?.items?.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-slate-400">
            <Calendar className="w-12 h-12 mb-4 opacity-50" />
            <p>No activities found</p>
            <Link
              href="/sales/activities/new"
              className="mt-4 text-emerald-400 hover:text-emerald-300"
            >
              Create your first activity
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-slate-700/50">
            {activities?.items?.map((activity: Activity) => {
              const Icon = activityTypeIcons[activity.activity_type] || Clock;
              const isOverdue = activity.scheduled_at && isPast(new Date(activity.scheduled_at)) && activity.status === 'planned';

              return (
                <div
                  key={activity.id}
                  className={`flex items-center gap-4 p-4 hover:bg-slate-700/30 transition-colors ${
                    isOverdue ? 'bg-red-500/5' : ''
                  }`}
                >
                  {/* Type Icon */}
                  <div className={`p-2.5 rounded-lg border ${activityTypeColors[activity.activity_type] || activityTypeColors.task}`}>
                    <Icon className="w-4 h-4" />
                  </div>

                  {/* Main Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-white">{activity.subject}</span>
                      <span className={`px-2 py-0.5 rounded text-xs ${statusColors[activity.status]}`}>
                        {activity.status}
                      </span>
                      {isOverdue && (
                        <span className="px-2 py-0.5 rounded text-xs bg-red-500/20 text-red-400">
                          Overdue
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-4 mt-1 text-sm text-slate-400">
                      {activity.customer_name && (
                        <span className="flex items-center gap-1">
                          <Building2 className="w-3 h-3" />
                          {activity.customer_name}
                        </span>
                      )}
                      {activity.lead_name && (
                        <span className="flex items-center gap-1">
                          <User className="w-3 h-3" />
                          {activity.lead_name}
                        </span>
                      )}
                      {activity.opportunity_name && (
                        <span className="flex items-center gap-1">
                          <Target className="w-3 h-3" />
                          {activity.opportunity_name}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Schedule */}
                  {activity.scheduled_at && (
                    <div className="text-right">
                      <div className={`text-sm font-medium ${isOverdue ? 'text-red-400' : 'text-white'}`}>
                        {getScheduleLabel(activity.scheduled_at)}
                      </div>
                      <div className="text-xs text-slate-500">
                        {formatDate(activity.scheduled_at, 'h:mm a')}
                      </div>
                    </div>
                  )}

                  {/* Actions */}
                  {activity.status === 'planned' && (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleComplete(activity.id)}
                        className="p-1.5 text-emerald-400 hover:bg-emerald-500/20 rounded-lg transition-colors"
                        title="Mark Complete"
                      >
                        <CheckCircle className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleCancel(activity.id)}
                        className="p-1.5 text-slate-400 hover:bg-slate-500/20 rounded-lg transition-colors"
                        title="Cancel"
                      >
                        <XCircle className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                  <button
                    onClick={(e) => e.preventDefault()}
                    className="p-1.5 text-slate-400 hover:bg-slate-700/50 rounded-lg transition-colors"
                  >
                    <MoreHorizontal className="w-4 h-4" />
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {/* Pagination */}
        {activities && activities.total > 20 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-700/50">
            <div className="text-sm text-slate-400">
              Showing {((page - 1) * 20) + 1} to {Math.min(page * 20, activities.total)} of {activities.total}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 text-sm bg-slate-700/50 hover:bg-slate-700 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={page * 20 >= activities.total}
                className="px-3 py-1.5 text-sm bg-slate-700/50 hover:bg-slate-700 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
