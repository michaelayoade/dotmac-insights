'use client';

import { Mail, Plus, Settings, CheckCircle, XCircle, Trash2, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui';

const EMAIL_ACCOUNTS = [
  { id: '1', email: 'support@company.com', name: 'Support Email', provider: 'Gmail', status: 'connected', lastSync: '2 min ago' },
  { id: '2', email: 'sales@company.com', name: 'Sales Email', provider: 'Outlook', status: 'connected', lastSync: '5 min ago' },
  { id: '3', email: 'info@company.com', name: 'General Inquiries', provider: 'IMAP', status: 'error', lastSync: 'Failed' },
];

export default function EmailChannelPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-blue-500/10 border border-blue-500/30 flex items-center justify-center">
            <Mail className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Email Channel</h1>
            <p className="text-slate-muted text-sm">Connect and manage email accounts</p>
          </div>
        </div>
        <Button className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500 text-foreground rounded-lg text-sm font-medium hover:bg-blue-600 transition-colors">
          <Plus className="w-4 h-4" />
          Connect Account
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Connected Accounts</p>
          <p className="text-2xl font-bold text-foreground">{EMAIL_ACCOUNTS.filter((a) => a.status === 'connected').length}</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Emails Today</p>
          <p className="text-2xl font-bold text-blue-400">127</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Avg Response Time</p>
          <p className="text-2xl font-bold text-emerald-400">2.5h</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Pending</p>
          <p className="text-2xl font-bold text-amber-400">23</p>
        </div>
      </div>

      {/* Account list */}
      <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        <div className="p-4 border-b border-slate-border">
          <h2 className="text-foreground font-semibold">Connected Accounts</h2>
        </div>
        {EMAIL_ACCOUNTS.map((account) => (
          <div key={account.id} className="flex items-center justify-between p-4 border-b border-slate-border/50 last:border-0">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                <Mail className="w-5 h-5 text-blue-400" />
              </div>
              <div>
                <p className="text-foreground font-medium">{account.name}</p>
                <p className="text-sm text-slate-muted">{account.email}</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <span className={cn(
                  'px-2 py-0.5 rounded text-xs font-medium',
                  account.status === 'connected' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                )}>
                  {account.status === 'connected' ? 'Connected' : 'Error'}
                </span>
                <p className="text-xs text-slate-muted mt-1">{account.lastSync}</p>
              </div>
              <div className="flex items-center gap-1">
                <Button className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded-lg transition-colors" title="Sync now">
                  <RefreshCw className="w-4 h-4" />
                </Button>
                <Button className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded-lg transition-colors" title="Settings">
                  <Settings className="w-4 h-4" />
                </Button>
                <Button className="p-2 text-slate-muted hover:text-rose-400 hover:bg-slate-elevated rounded-lg transition-colors" title="Remove">
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Setup guide */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <h3 className="text-foreground font-semibold mb-4">Supported Providers</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-lg border border-slate-border hover:border-blue-500/50 transition-colors text-center cursor-pointer">
            <div className="w-10 h-10 rounded-lg bg-red-500/10 mx-auto mb-2 flex items-center justify-center">
              <Mail className="w-5 h-5 text-red-400" />
            </div>
            <p className="text-foreground text-sm font-medium">Gmail</p>
            <p className="text-xs text-slate-muted">OAuth 2.0</p>
          </div>
          <div className="p-4 rounded-lg border border-slate-border hover:border-blue-500/50 transition-colors text-center cursor-pointer">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 mx-auto mb-2 flex items-center justify-center">
              <Mail className="w-5 h-5 text-blue-400" />
            </div>
            <p className="text-foreground text-sm font-medium">Outlook</p>
            <p className="text-xs text-slate-muted">Microsoft 365</p>
          </div>
          <div className="p-4 rounded-lg border border-slate-border hover:border-blue-500/50 transition-colors text-center cursor-pointer">
            <div className="w-10 h-10 rounded-lg bg-slate-500/10 mx-auto mb-2 flex items-center justify-center">
              <Mail className="w-5 h-5 text-slate-400" />
            </div>
            <p className="text-foreground text-sm font-medium">IMAP/SMTP</p>
            <p className="text-xs text-slate-muted">Custom server</p>
          </div>
          <div className="p-4 rounded-lg border border-slate-border hover:border-blue-500/50 transition-colors text-center cursor-pointer">
            <div className="w-10 h-10 rounded-lg bg-violet-500/10 mx-auto mb-2 flex items-center justify-center">
              <Mail className="w-5 h-5 text-violet-400" />
            </div>
            <p className="text-foreground text-sm font-medium">Yahoo Mail</p>
            <p className="text-xs text-slate-muted">OAuth 2.0</p>
          </div>
        </div>
      </div>
    </div>
  );
}
