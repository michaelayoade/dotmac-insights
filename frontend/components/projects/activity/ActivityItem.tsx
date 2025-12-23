'use client';

import {
  Plus,
  Edit,
  ArrowRightLeft,
  UserPlus,
  MessageSquare,
  Paperclip,
  Flag,
  CheckCircle2,
  Send,
  Check,
  X,
} from 'lucide-react';
import type { ProjectActivity, ProjectActivityType } from '@/lib/api/domains/projects';
import { formatDate } from '@/lib/formatters';
import { cn } from '@/lib/utils';

interface ActivityItemProps {
  activity: ProjectActivity;
}

const activityConfig: Record<
  ProjectActivityType,
  { icon: React.ComponentType<{ className?: string }>; color: string; bgColor: string }
> = {
  created: { icon: Plus, color: 'text-teal-electric', bgColor: 'bg-teal-electric/20' },
  updated: { icon: Edit, color: 'text-blue-400', bgColor: 'bg-blue-400/20' },
  status_changed: { icon: ArrowRightLeft, color: 'text-purple-400', bgColor: 'bg-purple-400/20' },
  assigned: { icon: UserPlus, color: 'text-amber-400', bgColor: 'bg-amber-400/20' },
  comment_added: { icon: MessageSquare, color: 'text-slate-muted', bgColor: 'bg-slate-elevated' },
  attachment_added: { icon: Paperclip, color: 'text-indigo-400', bgColor: 'bg-indigo-400/20' },
  milestone_completed: { icon: Flag, color: 'text-emerald-400', bgColor: 'bg-emerald-400/20' },
  task_completed: { icon: CheckCircle2, color: 'text-emerald-400', bgColor: 'bg-emerald-400/20' },
  approval_submitted: { icon: Send, color: 'text-amber-400', bgColor: 'bg-amber-400/20' },
  approval_approved: { icon: Check, color: 'text-emerald-400', bgColor: 'bg-emerald-400/20' },
  approval_rejected: { icon: X, color: 'text-red-400', bgColor: 'bg-red-400/20' },
};

export function ActivityItem({ activity }: ActivityItemProps) {
  const config = activityConfig[activity.activity_type] || activityConfig.updated;
  const Icon = config.icon;
  const actorInitial = (activity.actor_name || activity.actor_email || 'S')[0].toUpperCase();

  return (
    <div className="flex gap-3 group">
      {/* Icon */}
      <div className="flex-shrink-0 relative">
        <div
          className={cn(
            'w-8 h-8 rounded-full flex items-center justify-center',
            config.bgColor
          )}
        >
          <Icon className={cn('w-4 h-4', config.color)} />
        </div>
        {/* Timeline connector */}
        <div className="absolute top-8 left-1/2 -translate-x-1/2 w-px h-full bg-slate-border group-last:hidden" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 pb-4">
        <div className="flex items-start gap-2">
          <p className="text-sm text-foreground">
            {activity.description}
          </p>
        </div>

        {/* Value change display */}
        {activity.from_value && activity.to_value && (
          <div className="mt-1.5 flex items-center gap-2 text-xs">
            <span className="px-2 py-0.5 rounded bg-red-500/10 text-red-400 line-through">
              {activity.from_value}
            </span>
            <ArrowRightLeft className="w-3 h-3 text-slate-muted" />
            <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400">
              {activity.to_value}
            </span>
          </div>
        )}

        {/* Changed fields list */}
        {activity.changed_fields && activity.changed_fields.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {activity.changed_fields.map((field) => (
              <span
                key={field}
                className="text-xs px-1.5 py-0.5 rounded bg-slate-elevated text-slate-muted"
              >
                {field.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        )}

        {/* Meta info */}
        <div className="mt-1 flex items-center gap-2 text-xs text-slate-muted">
          {(activity.actor_name || activity.actor_email) && (
            <>
              <div className="w-4 h-4 rounded-full bg-teal-electric/20 flex items-center justify-center text-teal-electric text-[10px] font-semibold">
                {actorInitial}
              </div>
              <span>{activity.actor_name || activity.actor_email?.split('@')[0]}</span>
              <span>•</span>
            </>
          )}
          <span>{formatDate(activity.created_at)}</span>
        </div>
      </div>
    </div>
  );
}

export default ActivityItem;
