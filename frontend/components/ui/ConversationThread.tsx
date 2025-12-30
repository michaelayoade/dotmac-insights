'use client';

import NextImage from 'next/image';
import { useState, useRef, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import {
  User,
  Bot,
  Paperclip,
  Send,
  MoreHorizontal,
  Reply,
  ThumbsUp,
  ThumbsDown,
  Clock,
  Check,
  CheckCheck,
  AlertCircle,
  Image,
  FileText,
  Download,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

// =============================================================================
// TYPES
// =============================================================================

export interface MessageAuthor {
  id: string | number;
  name: string;
  avatar?: string;
  role?: 'customer' | 'agent' | 'system' | 'bot';
  isCurrentUser?: boolean;
}

export interface MessageAttachment {
  id: string;
  name: string;
  type: 'image' | 'file' | 'document';
  url: string;
  size?: number;
  mimeType?: string;
  thumbnailUrl?: string;
}

export interface MessageReaction {
  type: 'like' | 'dislike';
  count: number;
  userReacted?: boolean;
}

export type MessageStatus = 'sending' | 'sent' | 'delivered' | 'read' | 'failed';

export interface ThreadMessage {
  id: string | number;
  content: string;
  author: MessageAuthor;
  timestamp: string | Date;
  status?: MessageStatus;
  attachments?: MessageAttachment[];
  reactions?: MessageReaction[];
  isInternal?: boolean;
  replyTo?: {
    id: string | number;
    authorName: string;
    preview: string;
  };
  metadata?: Record<string, unknown>;
}

// =============================================================================
// CONVERSATION THREAD
// =============================================================================

export interface ConversationThreadProps {
  /** Messages in the thread */
  messages: ThreadMessage[];
  /** Current user ID (to determine message alignment) */
  currentUserId?: string | number;
  /** Callback when a new message is sent */
  onSendMessage?: (content: string, attachments?: File[]) => void;
  /** Callback when message reaction changes */
  onReaction?: (messageId: string | number, type: 'like' | 'dislike') => void;
  /** Callback when reply is clicked */
  onReply?: (message: ThreadMessage) => void;
  /** Loading state */
  loading?: boolean;
  /** Read-only mode (no input) */
  readOnly?: boolean;
  /** Show internal notes toggle */
  showInternalToggle?: boolean;
  /** Callback when internal toggle changes */
  onInternalToggle?: (isInternal: boolean) => void;
  /** Placeholder for input */
  inputPlaceholder?: string;
  /** Allow attachments */
  allowAttachments?: boolean;
  /** Max attachment size in bytes */
  maxAttachmentSize?: number;
  /** Accepted file types */
  acceptedFileTypes?: string;
  /** Empty state message */
  emptyMessage?: string;
  /** Custom class name */
  className?: string;
  /** Auto scroll to bottom on new message */
  autoScroll?: boolean;
}

export function ConversationThread({
  messages,
  currentUserId,
  onSendMessage,
  onReaction,
  onReply,
  loading = false,
  readOnly = false,
  showInternalToggle = false,
  onInternalToggle,
  inputPlaceholder = 'Type a message...',
  allowAttachments = true,
  maxAttachmentSize = 10 * 1024 * 1024, // 10MB
  acceptedFileTypes = 'image/*,.pdf,.doc,.docx,.xls,.xlsx',
  emptyMessage = 'No messages yet',
  className,
  autoScroll = true,
}: ConversationThreadProps) {
  const [inputValue, setInputValue] = useState('');
  const [isInternal, setIsInternal] = useState(false);
  const [pendingAttachments, setPendingAttachments] = useState<File[]>([]);
  const [replyingTo, setReplyingTo] = useState<ThreadMessage | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto scroll to bottom on new messages
  useEffect(() => {
    if (autoScroll && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, autoScroll]);

  // Handle send message
  const handleSend = useCallback(() => {
    if (!inputValue.trim() && pendingAttachments.length === 0) return;

    onSendMessage?.(inputValue.trim(), pendingAttachments);
    setInputValue('');
    setPendingAttachments([]);
    setReplyingTo(null);
  }, [inputValue, pendingAttachments, onSendMessage]);

  // Handle key press
  const handleKeyPress = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  // Handle file selection
  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files || []);
      const validFiles = files.filter((file) => file.size <= maxAttachmentSize);
      setPendingAttachments((prev) => [...prev, ...validFiles]);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    },
    [maxAttachmentSize]
  );

  // Handle internal toggle
  const handleInternalToggle = useCallback(() => {
    const newValue = !isInternal;
    setIsInternal(newValue);
    onInternalToggle?.(newValue);
  }, [isInternal, onInternalToggle]);

  // Handle reply
  const handleReply = useCallback(
    (message: ThreadMessage) => {
      setReplyingTo(message);
      onReply?.(message);
      inputRef.current?.focus();
    },
    [onReply]
  );

  // Remove pending attachment
  const removeAttachment = useCallback((index: number) => {
    setPendingAttachments((prev) => prev.filter((_, i) => i !== index));
  }, []);

  // Group messages by date
  const groupedMessages = messages.reduce((groups, message) => {
    const date = new Date(message.timestamp).toLocaleDateString();
    if (!groups[date]) {
      groups[date] = [];
    }
    groups[date].push(message);
    return groups;
  }, {} as Record<string, ThreadMessage[]>);

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="w-6 h-6 border-2 border-teal-electric border-t-transparent rounded-full animate-spin" />
          </div>
        ) : messages.length === 0 ? (
          <div className="flex items-center justify-center py-8 text-slate-muted text-sm">
            {emptyMessage}
          </div>
        ) : (
          Object.entries(groupedMessages).map(([date, dateMessages]) => (
            <div key={date}>
              {/* Date Separator */}
              <div className="flex items-center gap-3 my-4">
                <div className="flex-1 h-px bg-slate-border" />
                <span className="text-xs text-slate-muted font-medium">{date}</span>
                <div className="flex-1 h-px bg-slate-border" />
              </div>

              {/* Messages for this date */}
              <div className="space-y-3">
                {dateMessages.map((message) => (
                  <MessageBubble
                    key={message.id}
                    message={message}
                    isOwn={message.author.isCurrentUser || message.author.id === currentUserId}
                    onReaction={onReaction}
                    onReply={() => handleReply(message)}
                  />
                ))}
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      {!readOnly && (
        <div className="border-t border-slate-border p-4 bg-background">
          {/* Reply Preview */}
          {replyingTo && (
            <div className="flex items-center justify-between mb-2 p-2 bg-slate-elevated rounded-lg">
              <div className="flex items-center gap-2 text-xs text-slate-muted">
                <Reply className="w-3 h-3" />
                <span>Replying to {replyingTo.author.name}</span>
                <span className="truncate max-w-[200px]">
                  {replyingTo.content.substring(0, 50)}
                  {replyingTo.content.length > 50 ? '...' : ''}
                </span>
              </div>
              <button
                onClick={() => setReplyingTo(null)}
                className="text-slate-muted hover:text-foreground"
              >
                ×
              </button>
            </div>
          )}

          {/* Pending Attachments */}
          {pendingAttachments.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2">
              {pendingAttachments.map((file, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 px-2 py-1 bg-slate-elevated rounded text-xs"
                >
                  <Paperclip className="w-3 h-3 text-slate-muted" />
                  <span className="truncate max-w-[150px]">{file.name}</span>
                  <button
                    onClick={() => removeAttachment(idx)}
                    className="text-slate-muted hover:text-coral-alert"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Internal Toggle */}
          {showInternalToggle && (
            <div className="flex items-center gap-2 mb-2">
              <button
                onClick={handleInternalToggle}
                className={cn(
                  'flex items-center gap-1.5 px-2 py-1 text-xs rounded-full transition-colors',
                  isInternal
                    ? 'bg-amber-500/20 text-amber-500 border border-amber-500/30'
                    : 'bg-slate-elevated text-slate-muted border border-slate-border'
                )}
              >
                <AlertCircle className="w-3 h-3" />
                Internal Note
              </button>
            </div>
          )}

          {/* Input */}
          <div className="flex items-end gap-2">
            <div className="flex-1 relative">
              <textarea
                ref={inputRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyPress}
                placeholder={inputPlaceholder}
                rows={1}
                className={cn(
                  'w-full px-4 py-2.5 bg-slate-elevated border rounded-xl resize-none',
                  'border-slate-border focus:border-teal-electric focus:outline-none',
                  'text-sm placeholder:text-slate-muted',
                  'min-h-[42px] max-h-[120px]'
                )}
                style={{
                  height: 'auto',
                  minHeight: '42px',
                }}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement;
                  target.style.height = 'auto';
                  target.style.height = `${Math.min(target.scrollHeight, 120)}px`;
                }}
              />
            </div>

            {/* Attachment Button */}
            {allowAttachments && (
              <>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept={acceptedFileTypes}
                  onChange={handleFileSelect}
                  className="hidden"
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="p-2.5 rounded-xl bg-slate-elevated border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-muted transition-colors"
                  title="Attach file"
                >
                  <Paperclip className="w-5 h-5" />
                </button>
              </>
            )}

            {/* Send Button */}
            <button
              type="button"
              onClick={handleSend}
              disabled={!inputValue.trim() && pendingAttachments.length === 0}
              className={cn(
                'p-2.5 rounded-xl transition-colors',
                inputValue.trim() || pendingAttachments.length > 0
                  ? 'bg-teal-electric text-foreground hover:bg-teal-glow'
                  : 'bg-slate-elevated border border-slate-border text-slate-muted cursor-not-allowed'
              )}
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// MESSAGE BUBBLE
// =============================================================================

interface MessageBubbleProps {
  message: ThreadMessage;
  isOwn: boolean;
  onReaction?: (messageId: string | number, type: 'like' | 'dislike') => void;
  onReply?: () => void;
}

function MessageBubble({ message, isOwn, onReaction, onReply }: MessageBubbleProps) {
  const [showActions, setShowActions] = useState(false);

  // Format time
  const time = new Date(message.timestamp).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });

  // Avatar icon based on role
  const AvatarIcon: LucideIcon =
    message.author.role === 'bot' ? Bot : message.author.role === 'system' ? AlertCircle : User;

  // Status icon
  const StatusIcon = () => {
    switch (message.status) {
      case 'sending':
        return <Clock className="w-3 h-3 text-slate-muted" />;
      case 'sent':
        return <Check className="w-3 h-3 text-slate-muted" />;
      case 'delivered':
        return <CheckCheck className="w-3 h-3 text-slate-muted" />;
      case 'read':
        return <CheckCheck className="w-3 h-3 text-teal-electric" />;
      case 'failed':
        return <AlertCircle className="w-3 h-3 text-coral-alert" />;
      default:
        return null;
    }
  };

  return (
    <div
      className={cn('flex gap-3', isOwn ? 'flex-row-reverse' : 'flex-row')}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      {/* Avatar */}
      <div
        className={cn(
          'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
          message.author.role === 'system'
            ? 'bg-amber-500/20'
            : message.author.role === 'bot'
            ? 'bg-purple-500/20'
            : isOwn
            ? 'bg-teal-electric/20'
            : 'bg-slate-elevated'
        )}
      >
        {message.author.avatar ? (
          <NextImage
            src={message.author.avatar}
            alt={message.author.name}
            width={32}
            height={32}
            sizes="32px"
            className="w-full h-full rounded-full object-cover"
          />
        ) : (
          <AvatarIcon
            className={cn(
              'w-4 h-4',
              message.author.role === 'system'
                ? 'text-amber-500'
                : message.author.role === 'bot'
                ? 'text-purple-500'
                : isOwn
                ? 'text-teal-electric'
                : 'text-slate-muted'
            )}
          />
        )}
      </div>

      {/* Message Content */}
      <div className={cn('flex flex-col max-w-[70%]', isOwn ? 'items-end' : 'items-start')}>
        {/* Author Name */}
        <span className="text-xs text-slate-muted mb-1">{message.author.name}</span>

        {/* Reply Preview */}
        {message.replyTo && (
          <div className="text-xs text-slate-muted bg-slate-elevated/50 px-2 py-1 rounded mb-1 border-l-2 border-slate-muted">
            <span className="font-medium">{message.replyTo.authorName}</span>
            <p className="truncate">{message.replyTo.preview}</p>
          </div>
        )}

        {/* Bubble */}
        <div
          className={cn(
            'relative px-4 py-2.5 rounded-2xl',
            message.isInternal
              ? 'bg-amber-500/15 border border-amber-500/30'
              : isOwn
              ? 'bg-teal-electric text-foreground'
              : 'bg-slate-elevated border border-slate-border'
          )}
        >
          {/* Internal Badge */}
          {message.isInternal && (
            <span className="absolute -top-2 left-2 text-[10px] bg-amber-500 text-white px-1.5 rounded">
              Internal
            </span>
          )}

          {/* Text Content */}
          <p className="text-sm whitespace-pre-wrap break-words">{message.content}</p>

          {/* Attachments */}
          {message.attachments && message.attachments.length > 0 && (
            <div className="mt-2 space-y-2">
              {message.attachments.map((attachment) => (
                <AttachmentPreview key={attachment.id} attachment={attachment} />
              ))}
            </div>
          )}
        </div>

        {/* Meta Row */}
        <div className="flex items-center gap-2 mt-1">
          <span className="text-[10px] text-slate-muted">{time}</span>
          {isOwn && <StatusIcon />}

          {/* Reactions */}
          {message.reactions && message.reactions.length > 0 && (
            <div className="flex items-center gap-1">
              {message.reactions.map((reaction) => (
                <button
                  key={reaction.type}
                  onClick={() => onReaction?.(message.id, reaction.type)}
                  className={cn(
                    'flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px]',
                    reaction.userReacted
                      ? 'bg-teal-electric/20 text-teal-electric'
                      : 'bg-slate-elevated text-slate-muted hover:bg-slate-border'
                  )}
                >
                  {reaction.type === 'like' ? (
                    <ThumbsUp className="w-2.5 h-2.5" />
                  ) : (
                    <ThumbsDown className="w-2.5 h-2.5" />
                  )}
                  {reaction.count}
                </button>
              ))}
            </div>
          )}

          {/* Actions */}
          {showActions && (
            <div className="flex items-center gap-1 ml-auto">
              <button
                onClick={onReply}
                className="p-1 rounded hover:bg-slate-elevated text-slate-muted hover:text-foreground"
                title="Reply"
              >
                <Reply className="w-3 h-3" />
              </button>
              <button
                onClick={() => onReaction?.(message.id, 'like')}
                className="p-1 rounded hover:bg-slate-elevated text-slate-muted hover:text-foreground"
                title="Like"
              >
                <ThumbsUp className="w-3 h-3" />
              </button>
              <button
                className="p-1 rounded hover:bg-slate-elevated text-slate-muted hover:text-foreground"
                title="More"
              >
                <MoreHorizontal className="w-3 h-3" />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// ATTACHMENT PREVIEW
// =============================================================================

interface AttachmentPreviewProps {
  attachment: MessageAttachment;
}

function AttachmentPreview({ attachment }: AttachmentPreviewProps) {
  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (attachment.type === 'image') {
    return (
      <a
        href={attachment.url}
        target="_blank"
        rel="noopener noreferrer"
        className="block rounded-lg overflow-hidden hover:opacity-90 transition-opacity"
      >
        <NextImage
          src={attachment.thumbnailUrl || attachment.url}
          alt={attachment.name}
          width={200}
          height={150}
          sizes="200px"
          className="max-w-[200px] max-h-[150px] object-cover"
        />
      </a>
    );
  }

  return (
    <a
      href={attachment.url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-2 p-2 bg-slate-elevated/50 rounded-lg hover:bg-slate-elevated transition-colors"
    >
      <div className="w-8 h-8 rounded bg-slate-border flex items-center justify-center">
        {attachment.type === 'document' ? (
          <FileText className="w-4 h-4 text-slate-muted" />
        ) : (
          <Paperclip className="w-4 h-4 text-slate-muted" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium truncate">{attachment.name}</p>
        {attachment.size && (
          <p className="text-[10px] text-slate-muted">{formatSize(attachment.size)}</p>
        )}
      </div>
      <Download className="w-4 h-4 text-slate-muted" />
    </a>
  );
}

// =============================================================================
// EXPORTS
// =============================================================================

export default ConversationThread;
