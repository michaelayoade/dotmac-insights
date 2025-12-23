'use client';

import { useState } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui';

interface CommentFormProps {
  onSubmit: (content: string) => Promise<void>;
  placeholder?: string;
  disabled?: boolean;
}

export function CommentForm({
  onSubmit,
  placeholder = 'Write a comment...',
  disabled = false,
}: CommentFormProps) {
  const [content, setContent] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      await onSubmit(content.trim());
      setContent('');
    } catch {
      // Error handled by parent
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Submit on Ctrl/Cmd + Enter
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-2">
      <div className="relative">
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          rows={3}
          disabled={disabled || isSubmitting}
          className={cn(
            'w-full px-4 py-3 bg-slate-elevated border border-slate-border rounded-lg text-foreground text-sm placeholder-slate-muted focus:border-teal-electric focus:ring-1 focus:ring-teal-electric outline-none transition-colors resize-none',
            disabled && 'opacity-50 cursor-not-allowed'
          )}
        />
      </div>
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-muted">
          Press Ctrl+Enter to submit
        </span>
        <Button
          type="submit"
          disabled={!content.trim() || disabled || isSubmitting}
          className={cn(
            'px-4 py-2 rounded-lg font-medium text-sm inline-flex items-center gap-2 transition-colors',
            content.trim() && !isSubmitting
              ? 'bg-teal-electric text-slate-950 hover:bg-teal-electric/90'
              : 'bg-slate-elevated text-slate-muted cursor-not-allowed'
          )}
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Posting...
            </>
          ) : (
            <>
              <Send className="w-4 h-4" />
              Post
            </>
          )}
        </Button>
      </div>
    </form>
  );
}

export default CommentForm;
