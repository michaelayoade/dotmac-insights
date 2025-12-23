'use client';

import { useState } from 'react';
import {
  User,
  Clock,
  Edit,
  Trash2,
  MoreVertical,
  Check,
  X,
} from 'lucide-react';
import type { ProjectComment } from '@/lib/api/domains/projects';
import { cn } from '@/lib/utils';
import { formatDate } from '@/lib/formatters';
import { Button } from '@/components/ui';

interface CommentItemProps {
  comment: ProjectComment;
  currentUserId?: number;
  onEdit?: (comment: ProjectComment, newContent: string) => Promise<void>;
  onDelete?: (comment: ProjectComment) => void;
}

export function CommentItem({
  comment,
  currentUserId,
  onEdit,
  onDelete,
}: CommentItemProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(comment.content);
  const [isSaving, setIsSaving] = useState(false);
  const [showMenu, setShowMenu] = useState(false);

  const isAuthor = currentUserId && comment.author_id === currentUserId;
  const authorInitial = (comment.author_name || comment.author_email || '?')[0].toUpperCase();

  const handleSave = async () => {
    if (!editContent.trim() || editContent === comment.content) {
      setIsEditing(false);
      setEditContent(comment.content);
      return;
    }
    setIsSaving(true);
    try {
      await onEdit?.(comment, editContent);
      setIsEditing(false);
    } catch {
      // Error handled by parent
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditContent(comment.content);
  };

  return (
    <div className="flex gap-3 group">
      {/* Avatar */}
      <div className="flex-shrink-0">
        <div className="w-9 h-9 rounded-full bg-teal-electric/20 flex items-center justify-center text-teal-electric text-sm font-semibold">
          {authorInitial}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-foreground text-sm">
              {comment.author_name || comment.author_email?.split('@')[0] || 'Unknown'}
            </span>
            <span className="text-xs text-slate-muted flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDate(comment.created_at)}
            </span>
            {comment.is_edited && (
              <span className="text-xs text-slate-muted italic">(edited)</span>
            )}
          </div>

          {/* Actions Menu */}
          {isAuthor && !isEditing && (
            <div className="relative">
              <button
                onClick={() => setShowMenu(!showMenu)}
                className="p-1.5 rounded-md text-slate-muted hover:text-foreground hover:bg-slate-elevated transition-colors opacity-0 group-hover:opacity-100"
              >
                <MoreVertical className="w-4 h-4" />
              </button>
              {showMenu && (
                <>
                  <div
                    className="fixed inset-0 z-10"
                    onClick={() => setShowMenu(false)}
                  />
                  <div className="absolute right-0 top-full mt-1 bg-slate-card border border-slate-border rounded-lg shadow-xl py-1 min-w-[120px] z-20">
                    {onEdit && (
                      <button
                        onClick={() => {
                          setIsEditing(true);
                          setShowMenu(false);
                        }}
                        className="w-full px-3 py-1.5 text-left text-sm text-foreground hover:bg-slate-elevated flex items-center gap-2"
                      >
                        <Edit className="w-3.5 h-3.5" />
                        Edit
                      </button>
                    )}
                    {onDelete && (
                      <button
                        onClick={() => {
                          onDelete(comment);
                          setShowMenu(false);
                        }}
                        className="w-full px-3 py-1.5 text-left text-sm text-red-400 hover:bg-red-500/10 flex items-center gap-2"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        Delete
                      </button>
                    )}
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* Comment Content */}
        {isEditing ? (
          <div className="mt-2 space-y-2">
            <textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              className="w-full px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground text-sm placeholder-slate-muted focus:border-teal-electric focus:ring-1 focus:ring-teal-electric outline-none transition-colors resize-none"
              rows={3}
              disabled={isSaving}
            />
            <div className="flex items-center gap-2">
              <Button
                onClick={handleSave}
                disabled={isSaving || !editContent.trim()}
                className="px-3 py-1.5 rounded-md bg-teal-electric text-slate-950 text-sm font-medium hover:bg-teal-electric/90 disabled:opacity-50 inline-flex items-center gap-1.5"
              >
                <Check className="w-3.5 h-3.5" />
                Save
              </Button>
              <Button
                onClick={handleCancel}
                disabled={isSaving}
                className="px-3 py-1.5 rounded-md border border-slate-border text-slate-muted text-sm hover:text-foreground hover:border-slate-border/70 inline-flex items-center gap-1.5"
              >
                <X className="w-3.5 h-3.5" />
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <p className="mt-1 text-foreground text-sm whitespace-pre-wrap">{comment.content}</p>
        )}
      </div>
    </div>
  );
}

export default CommentItem;
