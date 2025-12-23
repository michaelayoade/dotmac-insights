'use client';

import { MessageCircle, Copy, Settings, Eye, Code, Palette } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui';

export default function ChatChannelPage() {
  // Widget key should be configured per-tenant - this is a placeholder for the embed code example
  const widgetKey = process.env.NEXT_PUBLIC_CHAT_WIDGET_KEY || 'YOUR_WIDGET_KEY';
  const widgetCode = `<script src="https://inbox.dotmac.com/widget.js" data-key="${widgetKey}"></script>`;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center">
            <MessageCircle className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Live Chat Widget</h1>
            <p className="text-slate-muted text-sm">Embed chat on your website</p>
          </div>
        </div>
        <span className="px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-400 text-sm font-medium">Active</span>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Active Chats</p>
          <p className="text-2xl font-bold text-emerald-400">12</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Chats Today</p>
          <p className="text-2xl font-bold text-foreground">89</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Avg Wait Time</p>
          <p className="text-2xl font-bold text-blue-400">45s</p>
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <p className="text-slate-muted text-sm">Satisfaction</p>
          <p className="text-2xl font-bold text-amber-400">4.8/5</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Embed code */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Code className="w-5 h-5 text-blue-400" />
            <h2 className="text-lg font-semibold text-foreground">Embed Code</h2>
          </div>
          <p className="text-sm text-slate-muted mb-4">
            Add this code to your website just before the closing &lt;/body&gt; tag.
          </p>
          <div className="bg-slate-elevated rounded-lg p-4 font-mono text-sm text-slate-200 overflow-x-auto">
            {widgetCode}
          </div>
          <Button className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-slate-elevated text-foreground rounded-lg text-sm font-medium hover:bg-slate-border transition-colors">
            <Copy className="w-4 h-4" />
            Copy Code
          </Button>
        </div>

        {/* Widget preview */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Eye className="w-5 h-5 text-emerald-400" />
            <h2 className="text-lg font-semibold text-foreground">Widget Preview</h2>
          </div>
          <div className="bg-slate-elevated rounded-lg p-6 relative min-h-[300px]">
            {/* Mock chat widget */}
            <div className="absolute bottom-4 right-4 w-72">
              <div className="bg-white rounded-xl shadow-xl overflow-hidden">
                <div className="bg-emerald-500 px-4 py-3">
                  <p className="text-foreground font-semibold">Dotmac Support</p>
                  <p className="text-emerald-100 text-sm">We typically reply in minutes</p>
                </div>
                <div className="p-4 space-y-3">
                  <div className="bg-gray-100 rounded-lg px-3 py-2 text-sm text-gray-700 max-w-[80%]">
                    Hi! How can we help you today?
                  </div>
                  <div className="flex justify-end">
                    <div className="bg-emerald-500 rounded-lg px-3 py-2 text-sm text-foreground max-w-[80%]">
                      I have a question about pricing
                    </div>
                  </div>
                </div>
                <div className="px-4 pb-4">
                  <input
                    type="text"
                    placeholder="Type a message..."
                    className="w-full bg-gray-100 rounded-lg px-4 py-2 text-sm text-gray-700 focus:outline-none"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Customization */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Palette className="w-5 h-5 text-violet-400" />
          <h2 className="text-lg font-semibold text-foreground">Customization</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm text-slate-muted mb-2">Primary Color</label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                defaultValue="#10b981"
                className="w-10 h-10 rounded-lg border border-slate-border cursor-pointer"
              />
              <input
                type="text"
                defaultValue="#10b981"
                className="flex-1 bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm text-slate-muted mb-2">Widget Title</label>
            <input
              type="text"
              defaultValue="Dotmac Support"
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-muted mb-2">Welcome Message</label>
            <input
              type="text"
              defaultValue="Hi! How can we help you today?"
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
