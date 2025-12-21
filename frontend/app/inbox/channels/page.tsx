'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  Globe,
  Mail,
  MessageCircle,
  Phone,
  Plus,
  Settings,
  CheckCircle,
  XCircle,
  ArrowRight,
  Zap,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface Channel {
  id: string;
  name: string;
  type: 'email' | 'chat' | 'whatsapp' | 'phone';
  status: 'active' | 'inactive' | 'pending';
  description: string;
  stats: {
    conversations: number;
    responseTime: string;
  };
}

const CHANNELS: Channel[] = [
  {
    id: 'email-1',
    name: 'Support Email',
    type: 'email',
    status: 'active',
    description: 'support@company.com',
    stats: { conversations: 234, responseTime: '2.5h' },
  },
  {
    id: 'email-2',
    name: 'Sales Email',
    type: 'email',
    status: 'active',
    description: 'sales@company.com',
    stats: { conversations: 156, responseTime: '1.2h' },
  },
  {
    id: 'chat-1',
    name: 'Website Chat',
    type: 'chat',
    status: 'active',
    description: 'Live chat widget on website',
    stats: { conversations: 89, responseTime: '45s' },
  },
  {
    id: 'whatsapp-1',
    name: 'WhatsApp Business',
    type: 'whatsapp',
    status: 'pending',
    description: '+234 800 123 4567',
    stats: { conversations: 0, responseTime: '-' },
  },
  {
    id: 'phone-1',
    name: 'Voice Channel',
    type: 'phone',
    status: 'inactive',
    description: 'Call logging integration',
    stats: { conversations: 45, responseTime: '-' },
  },
];

const CHANNEL_ICONS = {
  email: Mail,
  chat: MessageCircle,
  whatsapp: MessageCircle,
  phone: Phone,
};

const CHANNEL_COLORS = {
  email: { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-400' },
  chat: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400' },
  whatsapp: { bg: 'bg-green-500/10', border: 'border-green-500/30', text: 'text-green-400' },
  phone: { bg: 'bg-violet-500/10', border: 'border-violet-500/30', text: 'text-violet-400' },
};

export default function ChannelsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center">
            <Globe className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Channels</h1>
            <p className="text-slate-muted text-sm">Configure communication channels</p>
          </div>
        </div>
        <button className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500 text-foreground rounded-lg text-sm font-medium hover:bg-blue-600 transition-colors">
          <Plus className="w-4 h-4" />
          Add Channel
        </button>
      </div>

      {/* Channel stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-2 text-slate-muted text-sm mb-1">
            <Globe className="w-4 h-4" />
            <span>Total Channels</span>
          </div>
          <p className="text-2xl font-bold text-foreground">{CHANNELS.length}</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-2 text-slate-muted text-sm mb-1">
            <CheckCircle className="w-4 h-4" />
            <span>Active</span>
          </div>
          <p className="text-2xl font-bold text-emerald-400">{CHANNELS.filter((c) => c.status === 'active').length}</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-2 text-slate-muted text-sm mb-1">
            <MessageCircle className="w-4 h-4" />
            <span>This Month</span>
          </div>
          <p className="text-2xl font-bold text-blue-400">{CHANNELS.reduce((sum, c) => sum + c.stats.conversations, 0)}</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-2 text-slate-muted text-sm mb-1">
            <Zap className="w-4 h-4" />
            <span>Avg Response</span>
          </div>
          <p className="text-2xl font-bold text-amber-400">1.5h</p>
        </div>
      </div>

      {/* Channel list */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {CHANNELS.map((channel) => {
          const Icon = CHANNEL_ICONS[channel.type];
          const colors = CHANNEL_COLORS[channel.type];

          return (
            <div
              key={channel.id}
              className="bg-slate-card border border-slate-border rounded-xl p-5 hover:border-slate-border/80 transition-colors"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', colors.bg, colors.border, 'border')}>
                    <Icon className={cn('w-5 h-5', colors.text)} />
                  </div>
                  <div>
                    <h3 className="text-foreground font-semibold">{channel.name}</h3>
                    <p className="text-sm text-slate-muted">{channel.description}</p>
                  </div>
                </div>
                <span
                  className={cn(
                    'px-2 py-1 rounded-full text-xs font-medium capitalize',
                    channel.status === 'active' && 'bg-emerald-500/20 text-emerald-400',
                    channel.status === 'inactive' && 'bg-slate-500/20 text-slate-400',
                    channel.status === 'pending' && 'bg-amber-500/20 text-amber-400'
                  )}
                >
                  {channel.status}
                </span>
              </div>

              <div className="flex items-center justify-between pt-4 border-t border-slate-border/50">
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-slate-muted">
                    <span className="text-foreground font-medium">{channel.stats.conversations}</span> conversations
                  </span>
                  <span className="text-slate-muted">
                    Avg: <span className="text-foreground font-medium">{channel.stats.responseTime}</span>
                  </span>
                </div>
                <Link
                  href={`/inbox/channels/${channel.type}`}
                  className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded-lg transition-colors"
                >
                  <Settings className="w-4 h-4" />
                </Link>
              </div>
            </div>
          );
        })}
      </div>

      {/* Quick setup guides */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <h3 className="text-foreground font-semibold mb-4">Quick Setup</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          <Link href="/inbox/channels/email" className="p-3 rounded-lg border border-slate-border hover:border-blue-500/50 transition-colors">
            <Mail className="w-5 h-5 text-blue-400 mb-2" />
            <p className="text-foreground text-sm font-medium">Connect Email</p>
            <p className="text-xs text-slate-muted">IMAP, Gmail, Outlook</p>
          </Link>
          <Link href="/inbox/channels/chat" className="p-3 rounded-lg border border-slate-border hover:border-emerald-500/50 transition-colors">
            <MessageCircle className="w-5 h-5 text-emerald-400 mb-2" />
            <p className="text-foreground text-sm font-medium">Setup Live Chat</p>
            <p className="text-xs text-slate-muted">Widget for your website</p>
          </Link>
          <Link href="/inbox/channels/whatsapp" className="p-3 rounded-lg border border-slate-border hover:border-green-500/50 transition-colors">
            <MessageCircle className="w-5 h-5 text-green-400 mb-2" />
            <p className="text-foreground text-sm font-medium">WhatsApp Business</p>
            <p className="text-xs text-slate-muted">API integration</p>
          </Link>
          <Link href="/inbox/channels/phone" className="p-3 rounded-lg border border-slate-border hover:border-violet-500/50 transition-colors">
            <Phone className="w-5 h-5 text-violet-400 mb-2" />
            <p className="text-foreground text-sm font-medium">Voice Channel</p>
            <p className="text-xs text-slate-muted">Call logging</p>
          </Link>
        </div>
      </div>
    </div>
  );
}
