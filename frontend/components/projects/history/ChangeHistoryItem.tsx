'use client';

import {
  Clock,
  User,
  FileEdit,
  PlusCircle,
  CheckCircle,
  XCircle,
  RefreshCw,
  MessageSquare,
  Paperclip,
  Flag,
  ClipboardCheck,
} from 'lucide-react';
import type { ChangeHistoryItem as ChangeHistoryItemType } from '@/lib/api/domains/projects';

const actionIcons: Record<string, React.ReactNode> = {
  create: <PlusCircle className="w-4 h-4 text-emerald-400" />,
  created: <PlusCircle className="w-4 h-4 text-emerald-400" />,
  update: <FileEdit className="w-4 h-4 text-amber-400" />,
  updated: <FileEdit className="w-4 h-4 text-amber-400" />,
  status_changed: <RefreshCw className="w-4 h-4 text-cyan-400" />,
  assigned: <User className="w-4 h-4 text-purple-400" />,
  comment_added: <MessageSquare className="w-4 h-4 text-blue-400" />,
  attachment_added: <Paperclip className="w-4 h-4 text-slate-400" />,
  milestone_completed: <Flag className="w-4 h-4 text-emerald-400" />,
  task_completed: <CheckCircle className="w-4 h-4 text-emerald-400" />,
  approval_submitted: <ClipboardCheck className="w-4 h-4 text-amber-400" />,
  approval_approved: <CheckCircle className="w-4 h-4 text-emerald-400" />,
  approval_rejected: <XCircle className="w-4 h-4 text-rose-400" />,
  approve: <CheckCircle className="w-4 h-4 text-emerald-400" />,
  reject: <XCircle className="w-4 h-4 text-rose-400" />,
  submit: <ClipboardCheck className="w-4 h-4 text-amber-400" />,
  delete: <XCircle className="w-4 h-4 text-rose-400" />,
};

const actionLabels: Record<string, string> = {
  create: 'Created',
  created: 'Created',
  update: 'Updated',
  updated: 'Updated',
  status_changed: 'Status Changed',
  assigned: 'Assigned',
  comment_added: 'Comment Added',
  attachment_added: 'Attachment Added',
  milestone_completed: 'Milestone Completed',
  task_completed: 'Task Completed',
  approval_submitted: 'Submitted for Approval',
  approval_approved: 'Approved',
  approval_rejected: 'Rejected',
  approve: 'Approved',
  reject: 'Rejected',
  submit: 'Submitted',
  delete: 'Deleted',
};

function formatFieldName(field: string): string {
  return field
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (str) => str.toUpperCase())
    .trim();
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

interface ChangeHistoryItemProps {
  item: ChangeHistoryItemType;
}

export function ChangeHistoryItem({ item }: ChangeHistoryItemProps) {
  const actionKey = item.action?.toLowerCase() || 'update';
  const icon = actionIcons[actionKey] || <FileEdit className="w-4 h-4 text-slate-400" />;
  const label = actionLabels[actionKey] || item.action || 'Changed';

  const formattedDate = item.timestamp
    ? new Date(item.timestamp).toLocaleString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    : null;

  const hasChangedFields = item.changed_fields && item.changed_fields.length > 0;
  const hasOldNewValues = item.old_values || item.new_values;

  return (
    <div className="flex gap-3 py-3 border-b border-slate-700/30 last:border-0">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center">
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-medium text-slate-200">{label}</span>
          <span className="text-xs px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
            {item.source}
          </span>
        </div>

        {item.description && (
          <p className="text-sm text-slate-400 mb-2">{item.description}</p>
        )}

        {item.from_value && item.to_value && (
          <p className="text-sm text-slate-400 mb-2">
            <span className="text-slate-500">from</span>{' '}
            <span className="text-slate-300">{item.from_value}</span>{' '}
            <span className="text-slate-500">to</span>{' '}
            <span className="text-slate-300">{item.to_value}</span>
          </p>
        )}

        {hasChangedFields && hasOldNewValues && (
          <div className="text-xs bg-slate-900/50 rounded p-2 mt-2 space-y-1">
            {item.changed_fields?.map((field) => {
              const oldVal = item.old_values?.[field];
              const newVal = item.new_values?.[field];
              return (
                <div key={field} className="flex items-start gap-2">
                  <span className="text-slate-500 font-medium min-w-[100px]">
                    {formatFieldName(field)}:
                  </span>
                  <span className="text-slate-400 line-through">{formatValue(oldVal)}</span>
                  <span className="text-slate-300">{formatValue(newVal)}</span>
                </div>
              );
            })}
          </div>
        )}

        {item.remarks && (
          <p className="text-xs text-slate-500 mt-2 italic">"{item.remarks}"</p>
        )}

        <div className="flex items-center gap-3 mt-2 text-xs text-slate-500">
          {item.actor_name && (
            <span className="flex items-center gap-1">
              <User className="w-3 h-3" />
              {item.actor_name}
            </span>
          )}
          {formattedDate && (
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formattedDate}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
