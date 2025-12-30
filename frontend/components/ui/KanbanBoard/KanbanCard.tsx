'use client';

import Image from 'next/image';
import { cn } from '@/lib/utils';
import { GripVertical } from 'lucide-react';

// =============================================================================
// KANBAN CARD
// =============================================================================

export interface KanbanCardProps {
  /** Whether this card is currently being dragged */
  isDragging?: boolean;
  /** Whether a move operation is in progress for this card */
  isMoving?: boolean;
  /** Drag start handler */
  onDragStart: (e: React.DragEvent) => void;
  /** Drag end handler */
  onDragEnd: () => void;
  /** Card content */
  children: React.ReactNode;
  /** Show drag handle */
  showHandle?: boolean;
  /** Custom class name */
  className?: string;
}

export function KanbanCard({
  isDragging = false,
  isMoving = false,
  onDragStart,
  onDragEnd,
  children,
  showHandle = true,
  className,
}: KanbanCardProps) {
  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      className={cn(
        'group bg-slate-card border border-slate-border rounded-lg cursor-grab active:cursor-grabbing',
        'hover:border-slate-muted transition-colors',
        isDragging && 'opacity-50 scale-95',
        isMoving && 'animate-pulse',
        className
      )}
    >
      <div className="flex">
        {showHandle && (
          <div className="flex-shrink-0 flex items-center px-1 text-slate-muted opacity-0 group-hover:opacity-100 transition-opacity">
            <GripVertical className="w-4 h-4" />
          </div>
        )}
        <div className="flex-1 min-w-0 p-3">{children}</div>
      </div>
    </div>
  );
}

// =============================================================================
// KANBAN CARD PRESETS (Common card layouts)
// =============================================================================

export interface OpportunityCardData {
  id: string | number;
  name: string;
  customerName?: string;
  value: number;
  probability: number;
  closeDate?: string;
  ownerName?: string;
  ownerAvatar?: string;
}

export interface OpportunityCardProps {
  opportunity: OpportunityCardData;
  formatCurrency?: (value: number) => string;
  formatDate?: (date: string) => string;
  onClick?: () => void;
}

/**
 * Pre-built opportunity card for sales pipelines
 */
export function OpportunityCard({
  opportunity,
  formatCurrency = (v) => v.toLocaleString(),
  formatDate = (d) => d,
  onClick,
}: OpportunityCardProps) {
  const getProbabilityColor = (prob: number) => {
    if (prob >= 70) return 'bg-emerald-500/20 text-emerald-400';
    if (prob >= 40) return 'bg-amber-500/20 text-amber-400';
    return 'bg-slate-500/20 text-slate-400';
  };

  const content = (
    <>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h4 className="font-medium text-foreground text-sm truncate">{opportunity.name}</h4>
          {opportunity.customerName && (
            <p className="text-xs text-slate-muted mt-0.5 truncate">{opportunity.customerName}</p>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between mt-3">
        <div className="text-teal-electric text-sm font-medium">
          {formatCurrency(opportunity.value)}
        </div>
        <div className={cn('text-xs px-1.5 py-0.5 rounded', getProbabilityColor(opportunity.probability))}>
          {opportunity.probability}%
        </div>
      </div>

      {opportunity.closeDate && (
        <div className="flex items-center gap-1 mt-2 text-xs text-slate-muted">
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          {formatDate(opportunity.closeDate)}
        </div>
      )}
    </>
  );

  if (onClick) {
    return (
      <button onClick={onClick} className="w-full text-left">
        {content}
      </button>
    );
  }

  return content;
}

export interface TaskCardData {
  id: string | number;
  title: string;
  description?: string;
  priority?: 'low' | 'medium' | 'high' | 'urgent';
  dueDate?: string;
  assignee?: { name: string; avatar?: string };
  labels?: { name: string; color: string }[];
}

export interface TaskCardProps {
  task: TaskCardData;
  formatDate?: (date: string) => string;
  onClick?: () => void;
}

/**
 * Pre-built task card for project boards
 */
export function TaskCard({
  task,
  formatDate = (d) => d,
  onClick,
}: TaskCardProps) {
  const priorityColors: Record<string, string> = {
    low: 'bg-slate-500/20 text-slate-400',
    medium: 'bg-blue-500/20 text-blue-400',
    high: 'bg-amber-500/20 text-amber-400',
    urgent: 'bg-red-500/20 text-red-400',
  };

  const content = (
    <>
      {task.labels && task.labels.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {task.labels.map((label) => (
            <span
              key={label.name}
              className="px-1.5 py-0.5 text-xs rounded"
              style={{ backgroundColor: `${label.color}20`, color: label.color }}
            >
              {label.name}
            </span>
          ))}
        </div>
      )}

      <h4 className="font-medium text-foreground text-sm">{task.title}</h4>

      {task.description && (
        <p className="text-xs text-slate-muted mt-1 line-clamp-2">{task.description}</p>
      )}

      <div className="flex items-center justify-between mt-3">
        <div className="flex items-center gap-2">
          {task.priority && (
            <span className={cn('text-xs px-1.5 py-0.5 rounded capitalize', priorityColors[task.priority])}>
              {task.priority}
            </span>
          )}
          {task.dueDate && (
            <span className="text-xs text-slate-muted">{formatDate(task.dueDate)}</span>
          )}
        </div>
        {task.assignee && (
          <div className="flex items-center gap-1">
            {task.assignee.avatar ? (
              <Image
                src={task.assignee.avatar}
                alt={task.assignee.name}
                width={20}
                height={20}
                sizes="20px"
                className="w-5 h-5 rounded-full"
              />
            ) : (
              <div className="w-5 h-5 rounded-full bg-slate-elevated flex items-center justify-center text-xs text-slate-muted">
                {task.assignee.name.charAt(0)}
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );

  if (onClick) {
    return (
      <button onClick={onClick} className="w-full text-left">
        {content}
      </button>
    );
  }

  return content;
}

export default KanbanCard;
