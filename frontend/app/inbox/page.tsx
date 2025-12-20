'use client';

import { useState, useMemo, useCallback, useEffect } from 'react';
import {
  MoreVertical,
  Mail,
  MessageCircle,
  Phone,
  Send,
  Paperclip,
  Smile,
  Clock,
  User,
  Tag,
  CheckCircle,
  AlertCircle,
  Archive,
  Trash2,
  CornerUpLeft,
  Star,
  StarOff,
  UserPlus,
  Ticket,
  Building2,
  Inbox as InboxIcon,
  MessageSquare,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  useInboxConversations,
  useInboxConversation,
  useInboxConversationMutations,
  useInboxAnalyticsSummary,
} from '@/hooks/useInbox';
import type {
  InboxMessage,
  ConversationStatus,
  ConversationPriority,
  ChannelType,
} from '@/lib/inbox.types';
import { ErrorState, SearchInput, StatGrid } from '@/components/ui';
import { StatCard } from '@/components/StatCard';
import { useErrorHandler } from '@/hooks/useErrorHandler';
import { useRequireScope } from '@/lib/auth-context';

// Channel icons and colors
const CHANNEL_ICONS: Record<ChannelType, React.ElementType> = {
  email: Mail,
  chat: MessageCircle,
  whatsapp: MessageCircle,
  phone: Phone,
  sms: MessageCircle,
  social: MessageCircle,
};

const CHANNEL_COLORS: Record<ChannelType, string> = {
  email: 'text-blue-400',
  chat: 'text-emerald-400',
  whatsapp: 'text-green-400',
  phone: 'text-violet-400',
  sms: 'text-cyan-400',
  social: 'text-pink-400',
};

const STATUS_COLORS: Record<ConversationStatus, string> = {
  open: 'bg-blue-500',
  pending: 'bg-amber-500',
  resolved: 'bg-emerald-500',
  archived: 'bg-slate-500',
};

const PRIORITY_COLORS: Record<ConversationPriority, string> = {
  low: 'text-slate-400',
  medium: 'text-blue-400',
  high: 'text-amber-400',
  urgent: 'text-rose-400',
};

function formatTimeAgo(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins} min ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

function formatMessageTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();

  if (isToday) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

// Loading skeleton component
function ConversationListSkeleton() {
  return (
    <div className="space-y-0">
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="p-4 border-b border-slate-border/50 animate-pulse">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-full bg-slate-elevated" />
            <div className="flex-1 space-y-2">
              <div className="flex items-center gap-2">
                <div className="h-4 w-24 bg-slate-elevated rounded" />
                <div className="h-3 w-16 bg-slate-elevated rounded ml-auto" />
              </div>
              <div className="h-3 w-3/4 bg-slate-elevated rounded" />
              <div className="h-3 w-1/2 bg-slate-elevated rounded" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// Local empty state for inline use
function InboxEmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-slate-muted p-6">
      <InboxIcon className="w-12 h-12 mb-3 opacity-50" />
      <p className="text-sm font-medium text-white mb-1">{title}</p>
      <p className="text-xs text-slate-muted">{description}</p>
    </div>
  );
}

export default function InboxPage() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<ConversationStatus | 'all'>('all');
  const [channelFilter, setChannelFilter] = useState<string>('all');
  const [replyText, setReplyText] = useState('');
  const [showActions, setShowActions] = useState(false);
  const [isSending, setIsSending] = useState(false);

  // API hooks
  const listParams = useMemo(() => ({
    status: statusFilter !== 'all' ? statusFilter : undefined,
    search: searchQuery || undefined,
    sort_by: 'last_message_at' as const,
    sort_order: 'desc' as const,
    limit: 50,
  }), [statusFilter, searchQuery]);

  const {
    data: conversationsData,
    error: conversationsError,
    isLoading: conversationsLoading,
    mutate: refreshConversations,
  } = useInboxConversations(listParams);

  const {
    data: selectedConversation,
    error: conversationError,
    isLoading: conversationLoading,
  } = useInboxConversation(selectedId ?? undefined);

  const {
    data: analytics,
    isLoading: analyticsLoading,
  } = useInboxAnalyticsSummary({ days: 1 });

  const mutations = useInboxConversationMutations();
  const { handleError, handleSuccess } = useErrorHandler();
  const { hasAccess: canWrite } = useRequireScope('inbox:write');

  const conversations = conversationsData?.data;

  // Filter conversations client-side for channel filter
  const filteredConversations = useMemo(() => {
    const convList = conversations ?? [];
    if (channelFilter === 'all') return convList;
    return convList.filter((c) => c.channel?.type === channelFilter);
  }, [conversations, channelFilter]);

  // Handle conversation selection
  const handleSelectConversation = useCallback((id: number) => {
    setSelectedId(id);
    setShowActions(false);
    // Mark as read when selected
    mutations.markRead(id).catch(console.error);
  }, [mutations]);

  // Auto-select the first conversation when none is selected
  useEffect(() => {
    if (!selectedId && filteredConversations.length > 0) {
      handleSelectConversation(filteredConversations[0].id);
    }
  }, [filteredConversations, handleSelectConversation, selectedId]);

  // Handle send reply
  const handleSendReply = async () => {
    if (!replyText.trim() || !selectedId || isSending) return;

    setIsSending(true);
    try {
      await mutations.sendMessage(selectedId, { content: replyText.trim() });
      setReplyText('');
      await refreshConversations();
    } catch (error) {
      handleError(error, 'Failed to send message');
    } finally {
      setIsSending(false);
    }
  };

  // Handle star toggle
  const handleToggleStar = async () => {
    if (!selectedConversation) return;
    try {
      await mutations.starConversation(selectedConversation.id, !selectedConversation.is_starred);
    } catch (error) {
      handleError(error, 'Failed to toggle star');
    }
  };

  // Handle create ticket
  const handleCreateTicket = async () => {
    if (!selectedConversation) return;
    if (!canWrite) {
      handleError('Access denied', 'Access denied');
      return;
    }
    try {
      const result = await mutations.createTicket(selectedConversation.id);
      handleSuccess(`Ticket created: #${result.ticket_id}`);
      setShowActions(false);
    } catch (error) {
      handleError(error, 'Failed to create ticket');
    }
  };

  // Handle create lead
  const handleCreateLead = async () => {
    if (!selectedConversation) return;
    if (!canWrite) {
      handleError('Access denied', 'Access denied');
      return;
    }
    try {
      const result = await mutations.createLead(selectedConversation.id);
      handleSuccess(`Lead created: #${result.lead_id}`);
      setShowActions(false);
    } catch (error) {
      handleError(error, 'Failed to create lead');
    }
  };

  // Handle archive
  const handleArchive = async () => {
    if (!selectedConversation) return;
    try {
      await mutations.archive(selectedConversation.id);
      setSelectedId(null);
      setShowActions(false);
      await refreshConversations();
    } catch (error) {
      handleError(error, 'Failed to archive conversation');
    }
  };

  return (
    <div className="h-[calc(100vh-180px)] min-h-[600px] flex flex-col">
      {/* Header stats */}
      <StatGrid columns={4} className="mb-4">
        <StatCard
          title="Open"
          value={analytics?.open_count ?? 0}
          icon={InboxIcon}
          loading={analyticsLoading}
        />
        <StatCard
          title="Pending"
          value={analytics?.pending_count ?? 0}
          icon={Clock}
          variant="warning"
          loading={analyticsLoading}
        />
        <StatCard
          title="Resolved Today"
          value={analytics?.resolved_today ?? 0}
          icon={CheckCircle}
          variant="success"
          loading={analyticsLoading}
        />
        <StatCard
          title="Unread"
          value={analytics?.total_unread ?? 0}
          icon={AlertCircle}
          loading={analyticsLoading}
        />
      </StatGrid>

      {/* Main split panel */}
      <div className="flex-1 flex bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        {/* Left panel - Conversation list */}
        <div className="w-full md:w-96 border-r border-slate-border flex flex-col">
          {/* Search and filters */}
          <div className="p-3 border-b border-slate-border space-y-3">
            <SearchInput
              value={searchQuery}
              onChange={setSearchQuery}
              placeholder="Search conversations..."
            />
            <div className="flex gap-2">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as ConversationStatus | 'all')}
                aria-label="Filter by status"
                className="flex-1 bg-slate-elevated border border-slate-border rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
              >
                <option value="all">All Status</option>
                <option value="open">Open</option>
                <option value="pending">Pending</option>
                <option value="resolved">Resolved</option>
                <option value="archived">Archived</option>
              </select>
              <select
                value={channelFilter}
                onChange={(e) => setChannelFilter(e.target.value)}
                aria-label="Filter by channel"
                className="flex-1 bg-slate-elevated border border-slate-border rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
              >
                <option value="all">All Channels</option>
                <option value="email">Email</option>
                <option value="chat">Chat</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="phone">Phone</option>
              </select>
            </div>
          </div>

          {/* Conversation list */}
          <div className="flex-1 overflow-y-auto" role="listbox" aria-label="Conversations">
            {conversationsLoading ? (
              <ConversationListSkeleton />
            ) : conversationsError ? (
              <ErrorState
                message="Failed to load conversations"
                onRetry={() => refreshConversations()}
              />
            ) : filteredConversations.length === 0 ? (
              <InboxEmptyState
                title="No conversations found"
                description={searchQuery ? 'Try adjusting your search' : 'New conversations will appear here'}
              />
            ) : (
              filteredConversations.map((conv) => {
                const channelType = (conv.channel?.type || 'email') as ChannelType;
                const ChannelIcon = CHANNEL_ICONS[channelType] || Mail;
                const isSelected = selectedId === conv.id;

                return (
                  <button
                    key={conv.id}
                    onClick={() => handleSelectConversation(conv.id)}
                    role="option"
                    aria-selected={isSelected}
                    className={cn(
                      'w-full text-left p-4 border-b border-slate-border/50 hover:bg-slate-elevated/50 transition-colors focus:outline-none focus:bg-slate-elevated/50',
                      isSelected && 'bg-blue-500/10 border-l-2 border-l-blue-500'
                    )}
                  >
                    <div className="flex items-start gap-3">
                      {/* Avatar */}
                      <div className="relative shrink-0">
                        <div className="w-10 h-10 rounded-full bg-slate-elevated flex items-center justify-center text-white font-semibold">
                          {(conv.contact_name || conv.contact_email || '?').charAt(0).toUpperCase()}
                        </div>
                        <div
                          className={cn(
                            'absolute -bottom-0.5 -right-0.5 w-4 h-4 rounded-full flex items-center justify-center',
                            channelType === 'email' && 'bg-blue-500/20',
                            channelType === 'chat' && 'bg-emerald-500/20',
                            channelType === 'whatsapp' && 'bg-green-500/20',
                            channelType === 'phone' && 'bg-violet-500/20'
                          )}
                        >
                          <ChannelIcon className={cn('w-2.5 h-2.5', CHANNEL_COLORS[channelType])} />
                        </div>
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <div className="flex items-center gap-2 min-w-0">
                            <span className={cn('font-semibold truncate', conv.unread_count > 0 ? 'text-white' : 'text-slate-200')}>
                              {conv.contact_name || conv.contact_email || 'Unknown'}
                            </span>
                            {conv.is_starred && <Star className="w-3 h-3 text-amber-400 fill-amber-400 shrink-0" />}
                          </div>
                          <span className="text-[10px] text-slate-muted shrink-0">
                            {formatTimeAgo(conv.last_message_at)}
                          </span>
                        </div>

                        <p className={cn('text-sm truncate mb-1', conv.unread_count > 0 ? 'text-slate-200 font-medium' : 'text-slate-muted')}>
                          {conv.subject || 'No subject'}
                        </p>

                        <p className="text-xs text-slate-muted truncate">{conv.preview || ''}</p>

                        <div className="flex items-center gap-2 mt-2">
                          <div className={cn('w-2 h-2 rounded-full', STATUS_COLORS[conv.status as ConversationStatus] || 'bg-slate-500')} />
                          {conv.unread_count > 0 && (
                            <span className="px-1.5 py-0.5 rounded-full bg-blue-500 text-[10px] font-semibold text-white">
                              {conv.unread_count}
                            </span>
                          )}
                          {conv.priority === 'urgent' && (
                            <span className="px-1.5 py-0.5 rounded-full bg-rose-500/20 text-[10px] font-medium text-rose-400">
                              Urgent
                            </span>
                          )}
                          {(conv.tags || []).slice(0, 2).map((tag) => (
                            <span key={tag} className="px-1.5 py-0.5 rounded bg-slate-elevated text-[10px] text-slate-muted">
                              {tag}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Right panel - Conversation detail */}
        <div className="hidden md:flex flex-1 flex-col">
          {conversationLoading && selectedId ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader2 className="w-8 h-8 animate-spin text-blue-400" />
            </div>
          ) : conversationError && selectedId ? (
            <ErrorState message="Failed to load conversation" />
          ) : selectedConversation ? (
            <>
              {/* Conversation header */}
              <div className="p-4 border-b border-slate-border">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-full bg-slate-elevated flex items-center justify-center text-white font-semibold text-lg">
                      {(selectedConversation.contact_name || selectedConversation.contact_email || '?').charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-lg font-semibold text-white">
                          {selectedConversation.contact_name || selectedConversation.contact_email || 'Unknown'}
                        </h2>
                        {selectedConversation.assigned_agent && (
                          <span className="px-2 py-0.5 rounded bg-slate-elevated text-xs text-slate-muted flex items-center gap-1">
                            <Building2 className="w-3 h-3" />
                            {selectedConversation.assigned_agent.display_name || selectedConversation.assigned_agent.email}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-slate-muted">{selectedConversation.contact_email}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleToggleStar}
                      className="p-2 text-slate-muted hover:text-white hover:bg-slate-elevated rounded-lg transition-colors"
                      title={selectedConversation.is_starred ? 'Unstar' : 'Star'}
                      aria-label={selectedConversation.is_starred ? 'Unstar conversation' : 'Star conversation'}
                    >
                      {selectedConversation.is_starred ? (
                        <Star className="w-5 h-5 text-amber-400 fill-amber-400" />
                      ) : (
                        <StarOff className="w-5 h-5" />
                      )}
                    </button>
                    <div className="relative">
                      <button
                        onClick={() => setShowActions(!showActions)}
                        className="p-2 text-slate-muted hover:text-white hover:bg-slate-elevated rounded-lg transition-colors"
                        aria-label="More actions"
                        aria-expanded={showActions}
                      >
                        <MoreVertical className="w-5 h-5" />
                      </button>
                      {showActions && (
                        <div className="absolute right-0 top-full mt-1 w-48 bg-slate-card border border-slate-border rounded-lg shadow-xl z-10 py-1">
                          <button
                            onClick={handleCreateTicket}
                            className="w-full px-4 py-2 text-sm text-left text-white hover:bg-slate-elevated flex items-center gap-2"
                          >
                            <Ticket className="w-4 h-4" />
                            Create Support Ticket
                          </button>
                          <button
                            onClick={handleCreateLead}
                            className="w-full px-4 py-2 text-sm text-left text-white hover:bg-slate-elevated flex items-center gap-2"
                          >
                            <UserPlus className="w-4 h-4" />
                            Create Sales Lead
                          </button>
                          <button className="w-full px-4 py-2 text-sm text-left text-white hover:bg-slate-elevated flex items-center gap-2">
                            <User className="w-4 h-4" />
                            Assign to Agent
                          </button>
                          <hr className="my-1 border-slate-border" />
                          <button
                            onClick={handleArchive}
                            className="w-full px-4 py-2 text-sm text-left text-white hover:bg-slate-elevated flex items-center gap-2"
                          >
                            <Archive className="w-4 h-4" />
                            Archive
                          </button>
                          <button className="w-full px-4 py-2 text-sm text-left text-rose-400 hover:bg-slate-elevated flex items-center gap-2">
                            <Trash2 className="w-4 h-4" />
                            Delete
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Subject and metadata */}
                <div className="mt-4 flex items-center justify-between">
                  <div>
                    <h3 className="text-white font-medium">{selectedConversation.subject || 'No subject'}</h3>
                    <div className="flex items-center gap-3 mt-2 text-xs text-slate-muted">
                      <span className="flex items-center gap-1">
                        <div className={cn('w-2 h-2 rounded-full', STATUS_COLORS[selectedConversation.status as ConversationStatus] || 'bg-slate-500')} />
                        <span className="capitalize">{selectedConversation.status}</span>
                      </span>
                      <span className={cn('flex items-center gap-1', PRIORITY_COLORS[selectedConversation.priority as ConversationPriority] || 'text-slate-400')}>
                        <AlertCircle className="w-3 h-3" />
                        <span className="capitalize">{selectedConversation.priority || 'medium'}</span>
                      </span>
                      {selectedConversation.assigned_agent && (
                        <span className="flex items-center gap-1">
                          <User className="w-3 h-3" />
                          {selectedConversation.assigned_agent.display_name || selectedConversation.assigned_agent.email}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {(selectedConversation.tags || []).map((tag) => (
                      <span key={tag} className="px-2 py-1 rounded bg-slate-elevated text-xs text-slate-muted flex items-center gap-1">
                        <Tag className="w-3 h-3" />
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Messages thread */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4" role="log" aria-label="Message history">
                {(selectedConversation.messages || []).length === 0 ? (
                  <div className="flex items-center justify-center h-full text-slate-muted">
                    <p className="text-sm">No messages yet</p>
                  </div>
                ) : (
                  (selectedConversation.messages || []).map((msg: InboxMessage) => {
                    const isAgent = msg.direction === 'outbound';
                    return (
                      <div
                        key={msg.id}
                        className={cn('flex gap-3', isAgent && 'flex-row-reverse')}
                      >
                        <div
                          className={cn(
                            'w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold shrink-0',
                            isAgent ? 'bg-blue-500/20 text-blue-400' : 'bg-slate-elevated text-white'
                          )}
                        >
                          {(msg.sender_name || (isAgent ? 'A' : 'C')).charAt(0).toUpperCase()}
                        </div>
                        <div className={cn('flex-1 max-w-[70%]', isAgent && 'flex flex-col items-end')}>
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-sm font-medium text-white">
                              {msg.sender_name || (isAgent ? 'Agent' : 'Customer')}
                            </span>
                            <span className="text-xs text-slate-muted">{formatMessageTime(msg.created_at)}</span>
                          </div>
                          <div
                            className={cn(
                              'rounded-xl px-4 py-3 text-sm',
                              isAgent
                                ? 'bg-blue-500/20 text-blue-100'
                                : 'bg-slate-elevated text-slate-200'
                            )}
                          >
                            {msg.content}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              {/* Reply composer */}
              <div className="p-4 border-t border-slate-border">
                <div className="bg-slate-elevated rounded-xl">
                  <textarea
                    value={replyText}
                    onChange={(e) => setReplyText(e.target.value)}
                    placeholder="Type your reply..."
                    aria-label="Reply message"
                    rows={3}
                    disabled={isSending}
                    className="w-full bg-transparent px-4 py-3 text-sm text-white placeholder:text-slate-muted resize-none focus:outline-none disabled:opacity-50"
                  />
                  <div className="flex items-center justify-between px-4 pb-3">
                    <div className="flex items-center gap-2">
                      <button
                        className="p-2 text-slate-muted hover:text-white hover:bg-slate-border/50 rounded-lg transition-colors"
                        title="Attach file"
                        aria-label="Attach file"
                      >
                        <Paperclip className="w-4 h-4" />
                      </button>
                      <button
                        className="p-2 text-slate-muted hover:text-white hover:bg-slate-border/50 rounded-lg transition-colors"
                        title="Insert emoji"
                        aria-label="Insert emoji"
                      >
                        <Smile className="w-4 h-4" />
                      </button>
                      <button
                        className="p-2 text-slate-muted hover:text-white hover:bg-slate-border/50 rounded-lg transition-colors"
                        title="Canned response"
                        aria-label="Use canned response"
                      >
                        <CornerUpLeft className="w-4 h-4" />
                      </button>
                    </div>
                    <div className="flex items-center gap-2">
                      <select
                        className="bg-slate-border/50 border-0 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                        aria-label="Send action"
                      >
                        <option>Send & Keep Open</option>
                        <option>Send & Resolve</option>
                        <option>Send & Archive</option>
                      </select>
                      <button
                        onClick={handleSendReply}
                        disabled={!replyText.trim() || isSending}
                        className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        {isSending ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Send className="w-4 h-4" />
                        )}
                        Send
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-slate-muted">
              <div className="text-center">
                <MessageSquare className="w-16 h-16 mx-auto mb-4 opacity-30" />
                <p className="text-lg font-medium text-white mb-2">Select a conversation</p>
                <p className="text-sm">Choose from the list to view details</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
