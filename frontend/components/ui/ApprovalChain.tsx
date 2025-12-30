'use client';

import Image from 'next/image';
import { cn } from '@/lib/utils';
import {
  Check,
  X,
  Clock,
  User,
  ChevronRight,
  AlertCircle,
  MessageSquare,
  SkipForward,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

// =============================================================================
// TYPES
// =============================================================================

export type ApprovalStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'skipped'
  | 'waiting'
  | 'cancelled';

export interface ApprovalStep {
  id: string | number;
  /** Step order (1, 2, 3...) */
  order: number;
  /** Step title (e.g., "Manager Approval") */
  title: string;
  /** Approver info */
  approver: {
    id: string | number;
    name: string;
    email?: string;
    avatar?: string;
    title?: string;
  };
  /** Current status */
  status: ApprovalStatus;
  /** Status timestamp */
  statusAt?: string | Date;
  /** Approver comments */
  comments?: string;
  /** Is this step optional */
  optional?: boolean;
  /** Deadline */
  dueDate?: string | Date;
  /** Is overdue */
  isOverdue?: boolean;
}

// =============================================================================
// APPROVAL CHAIN
// =============================================================================

export interface ApprovalChainProps {
  /** Approval steps */
  steps: ApprovalStep[];
  /** Current active step (by order) */
  currentStep?: number;
  /** Orientation */
  orientation?: 'horizontal' | 'vertical';
  /** Show timeline connector */
  showConnector?: boolean;
  /** Compact mode */
  compact?: boolean;
  /** On step click */
  onStepClick?: (step: ApprovalStep) => void;
  /** On approve */
  onApprove?: (step: ApprovalStep) => void;
  /** On reject */
  onReject?: (step: ApprovalStep) => void;
  /** Show action buttons */
  showActions?: boolean;
  /** Current user ID (to show action buttons for current user's steps) */
  currentUserId?: string | number;
  /** Empty state */
  emptyMessage?: string;
  /** Custom class name */
  className?: string;
}

export function ApprovalChain({
  steps,
  currentStep,
  orientation = 'vertical',
  showConnector = true,
  compact = false,
  onStepClick,
  onApprove,
  onReject,
  showActions = false,
  currentUserId,
  emptyMessage = 'No approval steps',
  className,
}: ApprovalChainProps) {
  const sortedSteps = [...steps].sort((a, b) => a.order - b.order);
  const isHorizontal = orientation === 'horizontal';

  if (steps.length === 0) {
    return (
      <div className="text-center py-8 text-slate-muted text-sm">{emptyMessage}</div>
    );
  }

  return (
    <div
      className={cn(
        'flex',
        isHorizontal ? 'flex-row items-start gap-2' : 'flex-col gap-0',
        className
      )}
    >
      {sortedSteps.map((step, index) => {
        const isLast = index === sortedSteps.length - 1;
        const isCurrent = step.order === currentStep;
        const canAction =
          showActions &&
          step.status === 'pending' &&
          currentUserId &&
          step.approver.id === currentUserId;

        return (
          <div
            key={step.id}
            className={cn(
              'flex',
              isHorizontal ? 'flex-col items-center flex-1' : 'flex-row'
            )}
          >
            {/* Step Content */}
            <ApprovalStepCard
              step={step}
              isCurrent={isCurrent}
              compact={compact}
              onClick={onStepClick ? () => onStepClick(step) : undefined}
              onApprove={canAction && onApprove ? () => onApprove(step) : undefined}
              onReject={canAction && onReject ? () => onReject(step) : undefined}
              isHorizontal={isHorizontal}
            />

            {/* Connector */}
            {showConnector && !isLast && (
              <div
                className={cn(
                  'flex items-center justify-center',
                  isHorizontal ? 'py-2' : 'px-5'
                )}
              >
                {isHorizontal ? (
                  <ChevronRight
                    className={cn(
                      'w-5 h-5',
                      step.status === 'approved'
                        ? 'text-emerald-500'
                        : 'text-slate-muted'
                    )}
                  />
                ) : (
                  <div
                    className={cn(
                      'w-0.5 h-8',
                      step.status === 'approved'
                        ? 'bg-emerald-500'
                        : step.status === 'rejected'
                        ? 'bg-coral-alert'
                        : 'bg-slate-border'
                    )}
                  />
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// =============================================================================
// APPROVAL STEP CARD
// =============================================================================

interface ApprovalStepCardProps {
  step: ApprovalStep;
  isCurrent?: boolean;
  compact?: boolean;
  onClick?: () => void;
  onApprove?: () => void;
  onReject?: () => void;
  isHorizontal?: boolean;
}

function ApprovalStepCard({
  step,
  isCurrent,
  compact,
  onClick,
  onApprove,
  onReject,
  isHorizontal,
}: ApprovalStepCardProps) {
  const statusConfig: Record<
    ApprovalStatus,
    { icon: LucideIcon; color: string; bg: string; label: string }
  > = {
    pending: {
      icon: Clock,
      color: 'text-amber-500',
      bg: 'bg-amber-500/20',
      label: 'Pending',
    },
    approved: {
      icon: Check,
      color: 'text-emerald-500',
      bg: 'bg-emerald-500/20',
      label: 'Approved',
    },
    rejected: {
      icon: X,
      color: 'text-coral-alert',
      bg: 'bg-coral-alert/20',
      label: 'Rejected',
    },
    skipped: {
      icon: SkipForward,
      color: 'text-slate-muted',
      bg: 'bg-slate-elevated',
      label: 'Skipped',
    },
    waiting: {
      icon: Clock,
      color: 'text-slate-muted',
      bg: 'bg-slate-elevated',
      label: 'Waiting',
    },
    cancelled: {
      icon: X,
      color: 'text-slate-muted',
      bg: 'bg-slate-elevated',
      label: 'Cancelled',
    },
  };

  const config = statusConfig[step.status];
  const StatusIcon = config.icon;

  const formatDate = (date: string | Date) => {
    return new Date(date).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (compact) {
    return (
      <div
        className={cn(
          'flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors',
          isCurrent ? 'border-teal-electric bg-teal-electric/5' : 'border-slate-border',
          onClick && 'cursor-pointer hover:bg-slate-elevated'
        )}
        onClick={onClick}
      >
        <div className={cn('w-6 h-6 rounded-full flex items-center justify-center', config.bg)}>
          <StatusIcon className={cn('w-3.5 h-3.5', config.color)} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground truncate">
            {step.approver.name}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'relative p-4 rounded-xl border transition-colors',
        isCurrent ? 'border-teal-electric bg-teal-electric/5' : 'border-slate-border bg-background',
        onClick && 'cursor-pointer hover:bg-slate-elevated',
        isHorizontal ? 'w-full' : 'flex-1'
      )}
      onClick={onClick}
    >
      {/* Order Badge */}
      <div className="absolute -top-2 -left-2 w-6 h-6 rounded-full bg-slate-deep border border-slate-border flex items-center justify-center">
        <span className="text-xs font-medium text-slate-muted">{step.order}</span>
      </div>

      {/* Header */}
      <div className="flex items-start gap-3">
        {/* Avatar / Status Icon */}
        <div className={cn('w-10 h-10 rounded-full flex items-center justify-center', config.bg)}>
          {step.approver.avatar ? (
            <Image
              src={step.approver.avatar}
              alt={step.approver.name}
              width={40}
              height={40}
              sizes="40px"
              className="w-full h-full rounded-full object-cover"
            />
          ) : (
            <StatusIcon className={cn('w-5 h-5', config.color)} />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground">{step.title}</p>
          <div className="flex items-center gap-2 mt-0.5">
            <User className="w-3 h-3 text-slate-muted" />
            <span className="text-xs text-slate-muted truncate">{step.approver.name}</span>
            {step.approver.title && (
              <>
                <span className="text-slate-muted">·</span>
                <span className="text-xs text-slate-muted truncate">{step.approver.title}</span>
              </>
            )}
          </div>
        </div>

        {/* Status Badge */}
        <div
          className={cn(
            'px-2 py-0.5 rounded-full text-xs font-medium flex items-center gap-1',
            config.bg,
            config.color
          )}
        >
          <StatusIcon className="w-3 h-3" />
          {config.label}
        </div>
      </div>

      {/* Status Details */}
      {step.statusAt && (
        <div className="mt-3 text-xs text-slate-muted">
          {step.status === 'approved' && `Approved on ${formatDate(step.statusAt)}`}
          {step.status === 'rejected' && `Rejected on ${formatDate(step.statusAt)}`}
          {step.status === 'pending' && step.dueDate && (
            <span className={step.isOverdue ? 'text-coral-alert' : ''}>
              {step.isOverdue ? 'Overdue since' : 'Due by'} {formatDate(step.dueDate)}
            </span>
          )}
        </div>
      )}

      {/* Comments */}
      {step.comments && (
        <div className="mt-3 flex items-start gap-2 p-2 bg-slate-elevated rounded-lg">
          <MessageSquare className="w-4 h-4 text-slate-muted flex-shrink-0 mt-0.5" />
          <p className="text-xs text-slate-muted">{step.comments}</p>
        </div>
      )}

      {/* Optional Badge */}
      {step.optional && (
        <div className="mt-2">
          <span className="text-[10px] text-slate-muted bg-slate-elevated px-2 py-0.5 rounded">
            Optional
          </span>
        </div>
      )}

      {/* Action Buttons */}
      {(onApprove || onReject) && (
        <div className="mt-3 flex items-center gap-2">
          {onApprove && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onApprove();
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-500 text-foreground text-xs font-medium rounded-lg hover:bg-emerald-400 transition-colors"
            >
              <Check className="w-3.5 h-3.5" />
              Approve
            </button>
          )}
          {onReject && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onReject();
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-coral-alert/20 text-coral-alert text-xs font-medium rounded-lg hover:bg-coral-alert/30 transition-colors"
            >
              <X className="w-3.5 h-3.5" />
              Reject
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// APPROVAL SUMMARY
// =============================================================================

export interface ApprovalSummaryProps {
  steps: ApprovalStep[];
  className?: string;
}

export function ApprovalSummary({ steps, className }: ApprovalSummaryProps) {
  const approved = steps.filter((s) => s.status === 'approved').length;
  const rejected = steps.filter((s) => s.status === 'rejected').length;
  const pending = steps.filter((s) => s.status === 'pending').length;
  const total = steps.length;

  const overallStatus =
    rejected > 0
      ? 'rejected'
      : approved === total
      ? 'approved'
      : pending > 0
      ? 'pending'
      : 'unknown';

  const statusConfig: Record<string, { color: string; bg: string; label: string }> = {
    approved: { color: 'text-emerald-500', bg: 'bg-emerald-500/20', label: 'Approved' },
    rejected: { color: 'text-coral-alert', bg: 'bg-coral-alert/20', label: 'Rejected' },
    pending: { color: 'text-amber-500', bg: 'bg-amber-500/20', label: 'Pending Approval' },
    unknown: { color: 'text-slate-muted', bg: 'bg-slate-elevated', label: 'Unknown' },
  };

  const config = statusConfig[overallStatus];

  return (
    <div className={cn('flex items-center justify-between p-4 bg-slate-card rounded-xl border border-slate-border', className)}>
      <div className="flex items-center gap-3">
        <div className={cn('px-3 py-1 rounded-full text-sm font-medium', config.bg, config.color)}>
          {config.label}
        </div>
        <span className="text-sm text-slate-muted">
          {approved} of {total} approved
        </span>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-full bg-emerald-500" />
          <span className="text-xs text-slate-muted">{approved}</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-full bg-amber-500" />
          <span className="text-xs text-slate-muted">{pending}</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-full bg-coral-alert" />
          <span className="text-xs text-slate-muted">{rejected}</span>
        </div>
      </div>
    </div>
  );
}

export default ApprovalChain;
