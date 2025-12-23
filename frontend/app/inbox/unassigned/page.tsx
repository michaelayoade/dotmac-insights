'use client';

import Link from 'next/link';
import { Inbox, Clock, MessageSquare, ArrowRight, UserPlus } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui';

const UNASSIGNED_CONVERSATIONS = [
  { id: '2', contact: 'Michael Chen', subject: 'Product demo request', channel: 'chat', priority: 'medium', lastActivity: '15 min ago', unread: 1 },
  { id: '6', contact: 'James Wilson', subject: 'Technical support needed', channel: 'email', priority: 'high', lastActivity: '30 min ago', unread: 3 },
  { id: '7', contact: 'Maria Garcia', subject: 'Pricing question', channel: 'whatsapp', priority: 'low', lastActivity: '45 min ago', unread: 1 },
];

export default function UnassignedPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center">
            <Inbox className="w-5 h-5 text-amber-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Unassigned</h1>
            <p className="text-slate-muted text-sm">New conversations waiting for assignment</p>
          </div>
        </div>
        <span className="px-3 py-1 rounded-full bg-amber-500/20 text-amber-400 text-sm font-medium">
          {UNASSIGNED_CONVERSATIONS.length} waiting
        </span>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        {UNASSIGNED_CONVERSATIONS.map((conv, idx) => (
          <div
            key={conv.id}
            className={cn(
              'flex items-center justify-between p-4',
              idx !== UNASSIGNED_CONVERSATIONS.length - 1 && 'border-b border-slate-border/50'
            )}
          >
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-full bg-slate-elevated flex items-center justify-center text-foreground font-semibold">
                {conv.contact.charAt(0)}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-foreground">{conv.contact}</span>
                  <span className="px-1.5 py-0.5 rounded-full bg-blue-500 text-[10px] font-semibold text-foreground">
                    {conv.unread}
                  </span>
                  {conv.priority === 'high' && (
                    <span className="px-1.5 py-0.5 rounded-full bg-amber-500/20 text-[10px] font-medium text-amber-400">
                      High
                    </span>
                  )}
                </div>
                <p className="text-sm text-slate-muted">{conv.subject}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-right">
                <span className="px-2 py-0.5 rounded text-xs font-medium capitalize bg-slate-elevated text-slate-muted">
                  {conv.channel}
                </span>
                <p className="text-xs text-slate-muted mt-1 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {conv.lastActivity}
                </p>
              </div>
              <Button className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded-lg transition-colors" title="Assign to me">
                <UserPlus className="w-4 h-4" />
              </Button>
              <Link href={`/inbox?id=${conv.id}`} className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded-lg transition-colors">
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
