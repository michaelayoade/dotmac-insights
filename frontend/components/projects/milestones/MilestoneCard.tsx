'use client';

import { useState } from 'react';
import {
  Target,
  Calendar,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Edit,
  Trash2,
  ListTodo,
  ChevronDown,
  ChevronRight,
  User,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { Milestone } from '@/lib/api/domains/projects';
import { cn } from '@/lib/utils';
import { formatDate } from '@/lib/formatters';
import { Button, StatusPill } from '@/components/ui';
import type { StatusTone } from '@/lib/status-pill';

interface MilestoneCardProps {
  milestone: Milestone;
  onEdit?: (milestone: Milestone) => void;
  onDelete?: (milestone: Milestone) => void;
  onTaskClick?: (taskId: number) => void;
  showActions?: boolean;
}

// Progress bar component
function ProgressBar({ percent, className }: { percent: number; className?: string }) {
  const color = percent >= 100 ? 'bg-green-500' : percent >= 50 ? 'bg-teal-500' : 'bg-blue-500';
  return (
    <div className={cn('h-2 bg-slate-700 rounded-full overflow-hidden', className)}>
      <div
        className={cn('h-full transition-all duration-500', color)}
        style={{ width: `${Math.min(100, percent)}%` }}
      />
    </div>
  );
}

// Status config
const statusConfig: Record<string, { icon: LucideIcon; tone: StatusTone; label: string }> = {
  planned: { icon: Target, tone: 'default', label: 'Planned' },
  in_progress: { icon: Clock, tone: 'info', label: 'In Progress' },
  completed: { icon: CheckCircle2, tone: 'success', label: 'Completed' },
  on_hold: { icon: AlertTriangle, tone: 'warning', label: 'On Hold' },
};

export function MilestoneCard({
  milestone,
  onEdit,
  onDelete,
  onTaskClick,
  showActions = true,
}: MilestoneCardProps) {
  const [expanded, setExpanded] = useState(false);

  const config = statusConfig[milestone.status] || statusConfig.planned;
  const isOverdue = milestone.is_overdue && milestone.status !== 'completed';

  return (
    <div
      className={cn(
        'bg-slate-card border rounded-xl transition-all',
        isOverdue ? 'border-red-500/30' : 'border-slate-border'
      )}
    >
      {/* Header */}
      <div className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 mb-2">
              <h3 className="text-foreground font-semibold truncate">{milestone.name}</h3>
              <StatusPill
                label={config.label}
                tone={config.tone}
                size="sm"
                icon={config.icon}
              />
              {isOverdue && (
                <span className="text-red-400 text-xs flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" />
                  Overdue
                </span>
              )}
            </div>
            {milestone.description && (
              <p className="text-slate-muted text-sm line-clamp-2 mb-3">
                {milestone.description}
              </p>
            )}

            {/* Dates */}
            <div className="flex items-center gap-4 text-xs text-slate-muted">
              {milestone.planned_start_date && (
                <span className="flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  Start: {formatDate(milestone.planned_start_date)}
                </span>
              )}
              {milestone.planned_end_date && (
                <span className={cn('flex items-center gap-1', isOverdue && 'text-red-400')}>
                  <Calendar className="w-3 h-3" />
                  Due: {formatDate(milestone.planned_end_date)}
                </span>
              )}
              <span className="flex items-center gap-1">
                <ListTodo className="w-3 h-3" />
                {milestone.task_count} task{milestone.task_count !== 1 ? 's' : ''}
              </span>
            </div>
          </div>

          {/* Actions */}
          {showActions && (
            <div className="flex items-center gap-1">
              {onEdit && (
                <Button
                  onClick={() => onEdit(milestone)}
                  className="p-2 rounded-lg text-slate-muted hover:text-foreground hover:bg-slate-elevated transition-colors"
                  title="Edit milestone"
                >
                  <Edit className="w-4 h-4" />
                </Button>
              )}
              {onDelete && (
                <Button
                  onClick={() => onDelete(milestone)}
                  className="p-2 rounded-lg text-slate-muted hover:text-red-400 hover:bg-red-500/10 transition-colors"
                  title="Delete milestone"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              )}
            </div>
          )}
        </div>

        {/* Progress */}
        <div className="mt-4">
          <div className="flex items-center justify-between text-sm mb-2">
            <span className="text-slate-muted">Progress</span>
            <span className="text-foreground font-medium">{milestone.percent_complete}%</span>
          </div>
          <ProgressBar percent={milestone.percent_complete} />
        </div>
      </div>

      {/* Tasks Section (expandable) */}
      {milestone.tasks && milestone.tasks.length > 0 && (
        <>
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full px-4 py-2 flex items-center gap-2 text-sm text-slate-muted hover:text-foreground border-t border-slate-border bg-slate-elevated/50 transition-colors"
          >
            {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            <ListTodo className="w-4 h-4" />
            <span>Tasks ({milestone.tasks.length})</span>
          </button>

          {expanded && (
            <div className="border-t border-slate-border">
              {milestone.tasks.map((task) => (
                <div
                  key={task.id}
                  onClick={() => onTaskClick?.(task.id)}
                  className={cn(
                    'px-4 py-3 flex items-center gap-3 border-b border-slate-border last:border-b-0 hover:bg-slate-elevated/50 transition-colors',
                    onTaskClick && 'cursor-pointer'
                  )}
                >
                  <div
                    className={cn(
                      'w-2 h-2 rounded-full',
                      task.status === 'completed'
                        ? 'bg-green-500'
                        : task.status === 'working'
                        ? 'bg-amber-500'
                        : task.is_overdue
                        ? 'bg-red-500'
                        : 'bg-blue-500'
                    )}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-foreground text-sm truncate">{task.subject}</p>
                    <div className="flex items-center gap-3 text-xs text-slate-muted mt-0.5">
                      {task.assigned_to && (
                        <span className="flex items-center gap-1">
                          <User className="w-3 h-3" />
                          {task.assigned_to.split('@')[0]}
                        </span>
                      )}
                      {task.exp_end_date && (
                        <span className={cn(task.is_overdue && task.status !== 'completed' && 'text-red-400')}>
                          {formatDate(task.exp_end_date)}
                        </span>
                      )}
                    </div>
                  </div>
                  <span className="text-xs text-slate-muted capitalize">
                    {task.status?.replace('_', ' ')}
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default MilestoneCard;
