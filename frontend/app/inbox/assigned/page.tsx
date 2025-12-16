'use client';

import Link from 'next/link';
import { User, Clock, MessageSquare, ArrowRight } from 'lucide-react';
import { cn } from '@/lib/utils';

const ASSIGNED_CONVERSATIONS = [
  { id: '1', contact: 'Sarah Johnson', subject: 'Issue with invoice #INV-2024-001', channel: 'email', status: 'open', priority: 'high', lastActivity: '2 min ago', unread: 2 },
  { id: '3', contact: 'Emma Williams', subject: 'Order status inquiry', channel: 'whatsapp', status: 'pending', priority: 'low', lastActivity: '1 hour ago', unread: 0 },
  { id: '5', contact: 'Lisa Anderson', subject: 'Contract renewal discussion', channel: 'phone', status: 'snoozed', priority: 'urgent', lastActivity: 'Yesterday', unread: 0 },
];

export default function AssignedPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-blue-500/10 border border-blue-500/30 flex items-center justify-center">
            <User className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">My Assigned</h1>
            <p className="text-slate-muted text-sm">Conversations assigned to you</p>
          </div>
        </div>
        <span className="px-3 py-1 rounded-full bg-blue-500/20 text-blue-400 text-sm font-medium">
          {ASSIGNED_CONVERSATIONS.length} conversations
        </span>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        {ASSIGNED_CONVERSATIONS.map((conv, idx) => (
          <Link
            key={conv.id}
            href={`/inbox?id=${conv.id}`}
            className={cn(
              'flex items-center justify-between p-4 hover:bg-slate-elevated/50 transition-colors',
              idx !== ASSIGNED_CONVERSATIONS.length - 1 && 'border-b border-slate-border/50'
            )}
          >
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-full bg-slate-elevated flex items-center justify-center text-white font-semibold">
                {conv.contact.charAt(0)}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-white">{conv.contact}</span>
                  {conv.unread > 0 && (
                    <span className="px-1.5 py-0.5 rounded-full bg-blue-500 text-[10px] font-semibold text-white">
                      {conv.unread}
                    </span>
                  )}
                  {conv.priority === 'urgent' && (
                    <span className="px-1.5 py-0.5 rounded-full bg-rose-500/20 text-[10px] font-medium text-rose-400">
                      Urgent
                    </span>
                  )}
                </div>
                <p className="text-sm text-slate-muted">{conv.subject}</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <span className={cn(
                  'px-2 py-0.5 rounded text-xs font-medium capitalize',
                  conv.status === 'open' && 'bg-blue-500/20 text-blue-400',
                  conv.status === 'pending' && 'bg-amber-500/20 text-amber-400',
                  conv.status === 'snoozed' && 'bg-slate-500/20 text-slate-400'
                )}>
                  {conv.status}
                </span>
                <p className="text-xs text-slate-muted mt-1 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {conv.lastActivity}
                </p>
              </div>
              <ArrowRight className="w-4 h-4 text-slate-muted" />
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
