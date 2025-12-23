'use client';

import { useState } from 'react';
import {
  Paperclip,
  Loader2,
  AlertTriangle,
} from 'lucide-react';
import type { EntityType, ProjectAttachment } from '@/lib/api/domains/projects';
import { useEntityAttachments, useAttachmentMutations } from '@/hooks/useApi';
import { AttachmentItem } from './AttachmentItem';
import { AttachmentUpload } from './AttachmentUpload';
import { Button } from '@/components/ui';

interface AttachmentListProps {
  entityType: EntityType;
  entityId: number;
  title?: string;
  canUpload?: boolean;
  canDelete?: boolean;
}

export function AttachmentList({
  entityType,
  entityId,
  title = 'Attachments',
  canUpload = true,
  canDelete = true,
}: AttachmentListProps) {
  const { data, isLoading, error, mutate } = useEntityAttachments(entityType, entityId);
  const { uploadAttachment, deleteAttachment, getDownloadUrl } = useAttachmentMutations();
  const [deleteConfirm, setDeleteConfirm] = useState<ProjectAttachment | null>(null);

  const attachments = data?.data || [];

  const handleUpload = async (file: File, options?: { description?: string }) => {
    await uploadAttachment(entityType, entityId, file, options);
    mutate();
  };

  const handleDownload = (attachment: ProjectAttachment) => {
    const url = getDownloadUrl(attachment.id);
    window.open(url, '_blank');
  };

  const handleDelete = async () => {
    if (deleteConfirm) {
      await deleteAttachment(deleteConfirm.id);
      setDeleteConfirm(null);
      mutate();
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-6 h-6 text-teal-electric animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-center">
        <AlertTriangle className="w-6 h-6 text-red-400 mx-auto mb-2" />
        <p className="text-red-400 text-sm">Failed to load attachments</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Paperclip className="w-4 h-4 text-teal-electric" />
        <h3 className="text-foreground font-semibold">{title} ({data?.total || 0})</h3>
      </div>

      {/* Upload */}
      {canUpload && <AttachmentUpload onUpload={handleUpload} />}

      {/* Attachments List */}
      {attachments.length > 0 ? (
        <div className="space-y-2">
          {attachments.map((attachment) => (
            <AttachmentItem
              key={attachment.id}
              attachment={attachment}
              onDownload={handleDownload}
              onDelete={canDelete ? setDeleteConfirm : undefined}
              canDelete={canDelete}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-slate-muted">
          <Paperclip className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">No attachments yet</p>
          {canUpload && <p className="text-xs mt-1">Upload files to attach them</p>}
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setDeleteConfirm(null)} />
          <div className="relative bg-slate-card border border-slate-border rounded-xl shadow-xl w-full max-w-sm mx-4 p-5">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2.5 rounded-full bg-red-500/10">
                <AlertTriangle className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <h3 className="text-foreground font-semibold">Delete Attachment</h3>
                <p className="text-slate-muted text-sm">This action cannot be undone</p>
              </div>
            </div>
            <p className="text-sm text-foreground mb-4">
              Are you sure you want to delete <strong>{deleteConfirm.file_name}</strong>?
            </p>
            <div className="flex items-center justify-end gap-2">
              <Button
                onClick={() => setDeleteConfirm(null)}
                className="px-3 py-1.5 rounded-md border border-slate-border text-slate-muted text-sm hover:text-foreground hover:border-slate-border/70"
              >
                Cancel
              </Button>
              <Button
                onClick={handleDelete}
                className="px-3 py-1.5 rounded-md bg-red-500 text-white text-sm hover:bg-red-600"
              >
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default AttachmentList;
