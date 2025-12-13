'use client';

import { useState } from 'react';
import { AlertTriangle, Filter, MessageCircle } from 'lucide-react';
import { useSupportCannedCategories, useSupportCannedResponses } from '@/hooks/useApi';

export default function SupportCannedResponsesPage() {
  const [category, setCategory] = useState('');
  const [scope, setScope] = useState('');
  const responses = useSupportCannedResponses({
    category: category || undefined,
    scope: scope || undefined,
    limit: 50,
  });
  const categories = useSupportCannedCategories();

  const list = responses.data?.data || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <MessageCircle className="w-5 h-5 text-teal-electric" />
        <div>
          <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Support</p>
          <h1 className="text-xl font-semibold text-white">Canned Responses</h1>
          <p className="text-slate-muted text-sm">Shortcodes and templates</p>
        </div>
      </div>

      {(responses.error || categories.error) && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>Failed to load canned responses</span>
        </div>
      )}

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-teal-electric" />
          <span className="text-white text-sm font-medium">Filters</span>
        </div>
        <select
          value={scope}
          onChange={(e) => setScope(e.target.value)}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        >
          <option value="">Scope: All</option>
          <option value="personal">Personal</option>
          <option value="team">Team</option>
          <option value="global">Global</option>
        </select>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        >
          <option value="">Category: All</option>
          {(categories.data || []).map((cat) => (
            <option key={cat} value={cat}>{cat}</option>
          ))}
        </select>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        {!responses.data ? (
          <p className="text-slate-muted text-sm">Loading responses…</p>
        ) : list.length === 0 ? (
          <p className="text-slate-muted text-sm">No canned responses found.</p>
        ) : (
          <div className="space-y-2">
            {list.map((resp) => (
              <div key={resp.id} className="border border-slate-border rounded-lg px-3 py-2">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-white font-semibold">{resp.name}</p>
                    <p className="text-slate-muted text-xs">{resp.shortcode || 'No shortcode'}</p>
                  </div>
                  <span className="text-xs text-slate-muted px-2 py-1 rounded border border-slate-border">
                    {resp.scope}
                  </span>
                </div>
                <p className="text-slate-muted text-sm line-clamp-2 mt-1">{resp.content}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
