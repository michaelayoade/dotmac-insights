'use client';

import { useState } from 'react';
import {
  FileText,
  Image,
  File,
  Download,
  Trash2,
  MoreVertical,
  Star,
  Clock,
} from 'lucide-react';
import type { ProjectAttachment } from '@/lib/api/domains/projects';
import { formatDate } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui';

interface AttachmentItemProps {
  attachment: ProjectAttachment;
  onDownload?: (attachment: ProjectAttachment) => void;
  onDelete?: (attachment: ProjectAttachment) => void;
  canDelete?: boolean;
}

function formatFileSize(bytes?: number | null): string {
  if (!bytes) return '-';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileIcon(fileType?: string | null, fileName?: string) {
  const ext = fileName?.split('.').pop()?.toLowerCase();
  const type = fileType?.split('/')[0];

  if (type === 'image' || ['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext || '')) {
    return Image;
  }
  if (['pdf', 'doc', 'docx', 'txt'].includes(ext || '')) {
    return FileText;
  }
  return File;
}

export function AttachmentItem({
  attachment,
  onDownload,
  onDelete,
  canDelete = false,
}: AttachmentItemProps) {
  const [showMenu, setShowMenu] = useState(false);
  const Icon = getFileIcon(attachment.file_type, attachment.file_name);

  return (
    <div className="flex items-center gap-3 p-3 bg-slate-elevated rounded-lg group hover:bg-slate-elevated/80 transition-colors">
      {/* File Icon */}
      <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-slate-card flex items-center justify-center">
        <Icon className="w-5 h-5 text-slate-muted" />
      </div>

      {/* File Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-foreground font-medium text-sm truncate">
            {attachment.file_name}
          </p>
          {attachment.is_primary && (
            <Star className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
          )}
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-muted mt-0.5">
          <span>{formatFileSize(attachment.file_size)}</span>
          {attachment.uploaded_at && (
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDate(attachment.uploaded_at)}
            </span>
          )}
          {attachment.attachment_type && (
            <span className="px-1.5 py-0.5 rounded bg-slate-card text-slate-muted">
              {attachment.attachment_type}
            </span>
          )}
        </div>
        {attachment.description && (
          <p className="text-xs text-slate-muted mt-1 truncate">{attachment.description}</p>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1">
        {onDownload && (
          <Button
            onClick={() => onDownload(attachment)}
            className="p-2 text-slate-muted hover:text-teal-electric transition-colors"
            title="Download"
          >
            <Download className="w-4 h-4" />
          </Button>
        )}

        {canDelete && onDelete && (
          <div className="relative">
            <button
              onClick={() => setShowMenu(!showMenu)}
              className="p-2 text-slate-muted hover:text-foreground transition-colors opacity-0 group-hover:opacity-100"
            >
              <MoreVertical className="w-4 h-4" />
            </button>
            {showMenu && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setShowMenu(false)} />
                <div className="absolute right-0 top-full mt-1 bg-slate-card border border-slate-border rounded-lg shadow-xl py-1 min-w-[120px] z-20">
                  <button
                    onClick={() => {
                      onDelete(attachment);
                      setShowMenu(false);
                    }}
                    className="w-full px-3 py-1.5 text-left text-sm text-red-400 hover:bg-red-500/10 flex items-center gap-2"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Delete
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default AttachmentItem;
