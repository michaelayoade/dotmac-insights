'use client';

import {
  Clock,
  CheckCircle2,
  XCircle,
  Send,
  AlertTriangle,
  History,
  Loader2,
} from 'lucide-react';
import type { ApprovalHistoryItem } from '@/lib/api/domains/projects';
import { useProjectApprovalStatus } from '@/hooks/useApi';
import { formatDate } from '@/lib/formatters';
import { cn } from '@/lib/utils';

interface ApprovalHistoryProps {
  projectId: number;
}

const actionConfig: Record<string, { icon: typeof Clock; color: string }> = {
  submit: { icon: Send, color: 'text-blue-400' },
  approve: { icon: CheckCircle2, color: 'text-emerald-400' },
  reject: { icon: XCircle, color: 'text-red-400' },
  cancel: { icon: AlertTriangle, color: 'text-slate-muted' },
  escalate: { icon: Clock, color: 'text-amber-400' },
  post: { icon: CheckCircle2, color: 'text-teal-electric' },
};

export function ApprovalHistory({ projectId }: ApprovalHistoryProps) {
  const { data: approvalStatus, isLoading, error } = useProjectApprovalStatus(projectId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-6 h-6 text-teal-electric animate-spin" />
      </div>
    );
  }

  if (error || !approvalStatus?.has_approval) {
    return (
      <div className="text-center py-8 text-slate-muted">
        <History className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p className="text-sm">No approval history</p>
      </div>
    );
  }

  const history = approvalStatus.history || [];

  if (history.length === 0) {
    return (
      <div className="text-center py-8 text-slate-muted">
        <History className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p className="text-sm">No approval actions yet</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <History className="w-4 h-4 text-teal-electric" />
        <h3 className="text-foreground font-semibold">Approval History</h3>
      </div>

      <div className="relative">
        {history.map((item, index) => {
          const config = actionConfig[item.action] || actionConfig.submit;
          const Icon = config.icon;

          return (
            <div key={index} className="flex gap-3 group">
              {/* Icon */}
              <div className="flex-shrink-0 relative">
                <div className={cn('w-8 h-8 rounded-full flex items-center justify-center bg-slate-elevated')}>
                  <Icon className={cn('w-4 h-4', config.color)} />
                </div>
                {index < history.length - 1 && (
                  <div className="absolute top-8 left-1/2 -translate-x-1/2 w-px h-full bg-slate-border" />
                )}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0 pb-4">
                <div className="flex items-center gap-2">
                  <span className={cn('font-medium text-sm capitalize', config.color)}>
                    {item.action}
                  </span>
                  <span className="text-xs text-slate-muted">
                    Step {item.step_order}
                  </span>
                </div>
                {item.remarks && (
                  <p className="text-sm text-foreground mt-1">{item.remarks}</p>
                )}
                <p className="text-xs text-slate-muted mt-1">
                  {formatDate(item.action_at)}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default ApprovalHistory;
