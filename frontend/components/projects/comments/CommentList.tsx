'use client';

import { useState } from 'react';
import {
  MessageSquare,
  Loader2,
  AlertTriangle,
} from 'lucide-react';
import type { EntityType, ProjectComment } from '@/lib/api/domains/projects';
import { useEntityComments, useCommentMutations } from '@/hooks/useApi';
import { useAuth } from '@/lib/auth-context';
import { CommentItem } from './CommentItem';
import { CommentForm } from './CommentForm';
import { Button } from '@/components/ui';

interface CommentListProps {
  entityType: EntityType;
  entityId: number;
  title?: string;
}

export function CommentList({
  entityType,
  entityId,
  title = 'Comments',
}: CommentListProps) {
  const { user } = useAuth();
  const { data, isLoading, error, mutate } = useEntityComments(entityType, entityId);
  const { createComment, updateComment, deleteComment } = useCommentMutations();
  const [deleteConfirm, setDeleteConfirm] = useState<ProjectComment | null>(null);

  const comments = data?.data || [];

  const handleCreate = async (content: string) => {
    await createComment(entityType, entityId, { content });
    mutate();
  };

  const handleEdit = async (comment: ProjectComment, newContent: string) => {
    await updateComment(comment.id, { content: newContent }, entityType, entityId);
    mutate();
  };

  const handleDelete = async () => {
    if (deleteConfirm) {
      await deleteComment(deleteConfirm.id, entityType, entityId);
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
        <p className="text-red-400 text-sm">Failed to load comments</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <MessageSquare className="w-4 h-4 text-teal-electric" />
        <h3 className="text-foreground font-semibold">{title} ({data?.total || 0})</h3>
      </div>

      {/* Comment Form */}
      <CommentForm onSubmit={handleCreate} />

      {/* Comments List */}
      {comments.length > 0 ? (
        <div className="space-y-4 pt-4 border-t border-slate-border">
          {comments.map((comment) => (
            <CommentItem
              key={comment.id}
              comment={comment}
              currentUserId={user?.id}
              onEdit={handleEdit}
              onDelete={setDeleteConfirm}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-slate-muted">
          <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">No comments yet</p>
          <p className="text-xs mt-1">Be the first to add a comment</p>
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
                <h3 className="text-foreground font-semibold">Delete Comment</h3>
                <p className="text-slate-muted text-sm">This action cannot be undone</p>
              </div>
            </div>
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

export default CommentList;
