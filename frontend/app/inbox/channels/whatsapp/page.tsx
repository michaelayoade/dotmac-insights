'use client';

import { MessageCircle, Phone, CheckCircle, AlertCircle, Settings, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui';

export default function WhatsAppChannelPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-green-500/10 border border-green-500/30 flex items-center justify-center">
            <MessageCircle className="w-5 h-5 text-green-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">WhatsApp Business</h1>
            <p className="text-slate-muted text-sm">Connect your WhatsApp Business account</p>
          </div>
        </div>
        <span className="px-3 py-1 rounded-full bg-amber-500/20 text-amber-400 text-sm font-medium">Pending Setup</span>
      </div>

      {/* Setup status */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-6">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 rounded-xl bg-green-500/10 flex items-center justify-center">
            <MessageCircle className="w-8 h-8 text-green-400" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-foreground">Connect WhatsApp Business API</h2>
            <p className="text-slate-muted">Receive and respond to WhatsApp messages directly in your inbox</p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-center gap-4 p-4 rounded-lg bg-slate-elevated">
            <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center">
              <CheckCircle className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="flex-1">
              <p className="text-foreground font-medium">Meta Business Account</p>
              <p className="text-sm text-slate-muted">Required for WhatsApp Business API access</p>
            </div>
            <Button className="px-4 py-2 bg-slate-border text-foreground rounded-lg text-sm font-medium hover:bg-slate-muted transition-colors">
              Verify
            </Button>
          </div>

          <div className="flex items-center gap-4 p-4 rounded-lg bg-slate-elevated">
            <div className="w-8 h-8 rounded-full bg-slate-500/20 flex items-center justify-center">
              <AlertCircle className="w-4 h-4 text-slate-400" />
            </div>
            <div className="flex-1">
              <p className="text-foreground font-medium">Phone Number Verification</p>
              <p className="text-sm text-slate-muted">Verify your business phone number</p>
            </div>
            <Button className="px-4 py-2 bg-green-500 text-foreground rounded-lg text-sm font-medium hover:bg-green-600 transition-colors">
              Connect
            </Button>
          </div>

          <div className="flex items-center gap-4 p-4 rounded-lg bg-slate-elevated opacity-50">
            <div className="w-8 h-8 rounded-full bg-slate-500/20 flex items-center justify-center">
              <Settings className="w-4 h-4 text-slate-400" />
            </div>
            <div className="flex-1">
              <p className="text-foreground font-medium">Configure Templates</p>
              <p className="text-sm text-slate-muted">Set up message templates for outbound messages</p>
            </div>
            <span className="text-xs text-slate-muted">Pending</span>
          </div>
        </div>
      </div>

      {/* Features */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center mb-3">
            <MessageCircle className="w-5 h-5 text-green-400" />
          </div>
          <h3 className="text-foreground font-semibold mb-2">Two-Way Messaging</h3>
          <p className="text-sm text-slate-muted">Receive and respond to customer messages in real-time</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center mb-3">
            <Phone className="w-5 h-5 text-blue-400" />
          </div>
          <h3 className="text-foreground font-semibold mb-2">Message Templates</h3>
          <p className="text-sm text-slate-muted">Pre-approved templates for notifications and updates</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="w-10 h-10 rounded-lg bg-violet-500/10 flex items-center justify-center mb-3">
            <Settings className="w-5 h-5 text-violet-400" />
          </div>
          <h3 className="text-foreground font-semibold mb-2">Rich Media</h3>
          <p className="text-sm text-slate-muted">Send images, documents, and interactive buttons</p>
        </div>
      </div>

      {/* Documentation link */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-foreground font-semibold">Need help setting up?</h3>
            <p className="text-sm text-slate-muted">Check our documentation for step-by-step instructions</p>
          </div>
          <a
            href="#"
            className="inline-flex items-center gap-2 px-4 py-2 bg-slate-elevated text-foreground rounded-lg text-sm font-medium hover:bg-slate-border transition-colors"
          >
            View Documentation
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>
      </div>
    </div>
  );
}
