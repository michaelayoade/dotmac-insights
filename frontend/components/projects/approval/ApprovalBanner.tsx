'use client';

import { useState } from 'react';
import {
  ShieldCheck,
  Clock,
  CheckCircle2,
  XCircle,
  Send,
  Loader2,
  AlertTriangle,
} from 'lucide-react';
import type { ProjectApprovalStatus, ApprovalStatusType } from '@/lib/api/domains/projects';
import { useProjectApprovalStatus, useCanApproveProject, useApprovalMutations } from '@/hooks/useApi';
import { formatDate } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui';

interface ApprovalBannerProps {
  projectId: number;
  onApprovalChange?: () => void;
}

const statusConfig: Record<ApprovalStatusType, { icon: typeof Clock; color: string; bgColor: string; label: string }> = {
  draft: { icon: Clock, color: 'text-slate-muted', bgColor: 'bg-slate-elevated', label: 'Draft' },
  pending: { icon: Clock, color: 'text-amber-400', bgColor: 'bg-amber-500/10', label: 'Pending Approval' },
  approved: { icon: CheckCircle2, color: 'text-emerald-400', bgColor: 'bg-emerald-500/10', label: 'Approved' },
  rejected: { icon: XCircle, color: 'text-red-400', bgColor: 'bg-red-500/10', label: 'Rejected' },
  cancelled: { icon: XCircle, color: 'text-slate-muted', bgColor: 'bg-slate-elevated', label: 'Cancelled' },
  posted: { icon: CheckCircle2, color: 'text-teal-electric', bgColor: 'bg-teal-electric/10', label: 'Posted' },
};

export function ApprovalBanner({ projectId, onApprovalChange }: ApprovalBannerProps) {
  const { data: approvalStatus, isLoading, mutate } = useProjectApprovalStatus(projectId);
  const { data: canApproveData } = useCanApproveProject(projectId);
  const { submitForApproval, approve, reject } = useApprovalMutations();

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [error, setError] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="bg-slate-card border border-slate-border rounded-xl p-4 flex items-center gap-3">
        <Loader2 className="w-5 h-5 text-slate-muted animate-spin" />
        <span className="text-slate-muted text-sm">Loading approval status...</span>
      </div>
    );
  }

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      await submitForApproval(projectId);
      mutate();
      onApprovalChange?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleApprove = async () => {
    setIsApproving(true);
    setError(null);
    try {
      await approve(projectId);
      mutate();
      onApprovalChange?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve');
    } finally {
      setIsApproving(false);
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) return;
    setIsApproving(true);
    setError(null);
    try {
      await reject(projectId, rejectReason);
      setShowRejectModal(false);
      setRejectReason('');
      mutate();
      onApprovalChange?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reject');
    } finally {
      setIsApproving(false);
    }
  };

  // No approval workflow yet
  if (!approvalStatus?.has_approval) {
    return (
      <div className="bg-slate-card border border-slate-border rounded-xl p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-slate-elevated">
            <ShieldCheck className="w-5 h-5 text-slate-muted" />
          </div>
          <div>
            <p className="text-foreground font-medium text-sm">No approval required</p>
            <p className="text-slate-muted text-xs">Submit for approval to start the workflow</p>
          </div>
        </div>
        <Button
          onClick={handleSubmit}
          disabled={isSubmitting}
          className="px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-medium text-sm hover:bg-teal-electric/90 inline-flex items-center gap-2"
        >
          {isSubmitting ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
          Submit for Approval
        </Button>
      </div>
    );
  }

  const status: ApprovalStatusType = approvalStatus.status || 'draft';
  const config = statusConfig[status] || statusConfig.draft;
  const Icon = config.icon;
  const canApprove = canApproveData?.can_approve && status === 'pending';

  return (
    <>
      <div className={cn('rounded-xl p-4 border', config.bgColor, 'border-current/20')}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={cn('p-2 rounded-lg', config.bgColor)}>
              <Icon className={cn('w-5 h-5', config.color)} />
            </div>
            <div>
              <p className={cn('font-medium text-sm', config.color)}>{config.label}</p>
              <div className="flex items-center gap-3 text-xs text-slate-muted mt-0.5">
                {approvalStatus.current_step_name && (
                  <span>Step: {approvalStatus.current_step_name}</span>
                )}
                {approvalStatus.submitted_at && (
                  <span>Submitted: {formatDate(approvalStatus.submitted_at)}</span>
                )}
                {approvalStatus.approved_at && (
                  <span>Approved: {formatDate(approvalStatus.approved_at)}</span>
                )}
                {approvalStatus.rejected_at && (
                  <span>Rejected: {formatDate(approvalStatus.rejected_at)}</span>
                )}
              </div>
              {status === 'rejected' && approvalStatus.rejection_reason && (
                <p className="text-red-400 text-xs mt-1">
                  Reason: {approvalStatus.rejection_reason}
                </p>
              )}
            </div>
          </div>

          {canApprove && (
            <div className="flex items-center gap-2">
              <Button
                onClick={() => setShowRejectModal(true)}
                disabled={isApproving}
                className="px-4 py-2 rounded-lg border border-red-500/30 text-red-400 font-medium text-sm hover:bg-red-500/10 inline-flex items-center gap-2"
              >
                <XCircle className="w-4 h-4" />
                Reject
              </Button>
              <Button
                onClick={handleApprove}
                disabled={isApproving}
                className="px-4 py-2 rounded-lg bg-emerald-500 text-white font-medium text-sm hover:bg-emerald-600 inline-flex items-center gap-2"
              >
                {isApproving ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <CheckCircle2 className="w-4 h-4" />
                )}
                Approve
              </Button>
            </div>
          )}

          {status === 'rejected' && (
            <Button
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-medium text-sm hover:bg-teal-electric/90 inline-flex items-center gap-2"
            >
              {isSubmitting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
              Resubmit
            </Button>
          )}
        </div>

        {error && (
          <div className="mt-3 bg-red-500/10 border border-red-500/30 rounded-lg p-3 flex items-center gap-2 text-red-400 text-sm">
            <AlertTriangle className="w-4 h-4" />
            {error}
          </div>
        )}
      </div>

      {/* Reject Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowRejectModal(false)} />
          <div className="relative bg-slate-card border border-slate-border rounded-xl shadow-xl w-full max-w-md mx-4 p-5">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2.5 rounded-full bg-red-500/10">
                <XCircle className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <h3 className="text-foreground font-semibold">Reject Project</h3>
                <p className="text-slate-muted text-sm">Provide a reason for rejection</p>
              </div>
            </div>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Enter rejection reason..."
              rows={3}
              className="w-full px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground text-sm placeholder-slate-muted focus:border-red-400 focus:ring-1 focus:ring-red-400 outline-none resize-none"
            />
            <div className="flex items-center justify-end gap-2 mt-4">
              <Button
                onClick={() => setShowRejectModal(false)}
                className="px-3 py-1.5 rounded-md border border-slate-border text-slate-muted text-sm hover:text-foreground"
              >
                Cancel
              </Button>
              <Button
                onClick={handleReject}
                disabled={!rejectReason.trim() || isApproving}
                className="px-3 py-1.5 rounded-md bg-red-500 text-white text-sm hover:bg-red-600 disabled:opacity-50 inline-flex items-center gap-2"
              >
                {isApproving && <Loader2 className="w-4 h-4 animate-spin" />}
                Reject
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default ApprovalBanner;
