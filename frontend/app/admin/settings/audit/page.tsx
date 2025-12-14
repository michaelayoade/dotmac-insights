'use client';

import { useState } from 'react';
import { History, ChevronDown, ChevronUp } from 'lucide-react';
import { useSettingsAuditLog } from '@/hooks/useApi';
import { cn } from '@/lib/utils';

export default function SettingsAuditPage() {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const { data: entries, isLoading } = useSettingsAuditLog({ limit: 100 });

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString('en-NG', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatJson = (jsonStr: string | null | undefined) => {
    if (!jsonStr) return null;
    try {
      return JSON.stringify(JSON.parse(jsonStr), null, 2);
    } catch {
      return jsonStr;
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex items-center gap-3">
        <History className="w-6 h-6 text-teal-electric" />
        <div>
          <h1 className="text-2xl font-bold text-white">Audit Log</h1>
          <p className="text-slate-muted text-sm">
            Track all changes made to application settings.
          </p>
        </div>
      </header>

      <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
        {isLoading ? (
          <div className="p-6 space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center gap-4 animate-pulse">
                <div className="h-4 w-24 bg-slate-700 rounded" />
                <div className="h-4 w-32 bg-slate-700 rounded" />
                <div className="h-4 w-48 bg-slate-700 rounded" />
              </div>
            ))}
          </div>
        ) : !entries?.length ? (
          <div className="p-12 text-center">
            <History className="w-12 h-12 text-slate-muted mx-auto mb-4" />
            <p className="text-slate-muted">No audit entries yet</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-border">
            {entries.map((entry) => (
              <div key={entry.id}>
                <button
                  onClick={() =>
                    setExpandedId(expandedId === entry.id ? null : entry.id)
                  }
                  className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-elevated/50 transition-colors text-left"
                >
                  <div className="flex items-center gap-4">
                    <span
                      className={cn(
                        'px-2 py-0.5 text-xs font-medium rounded',
                        entry.action === 'create' &&
                          'bg-emerald-500/20 text-emerald-300',
                        entry.action === 'update' &&
                          'bg-blue-500/20 text-blue-300',
                        entry.action === 'delete' && 'bg-red-500/20 text-red-300',
                        entry.action === 'test' &&
                          'bg-yellow-500/20 text-yellow-300'
                      )}
                    >
                      {entry.action}
                    </span>
                    <span className="text-white font-medium">
                      {entry.group_name}
                    </span>
                    <span className="text-slate-muted text-sm">
                      by {entry.user_email}
                    </span>
                    {entry.ip_address && (
                      <span className="text-slate-muted text-xs">
                        ({entry.ip_address})
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-slate-muted text-sm">
                      {formatDate(entry.created_at)}
                    </span>
                    {expandedId === entry.id ? (
                      <ChevronUp className="w-4 h-4 text-slate-muted" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-slate-muted" />
                    )}
                  </div>
                </button>

                {expandedId === entry.id && (
                  <div className="px-4 pb-4 space-y-4">
                    {entry.old_value_redacted && (
                      <div>
                        <p className="text-xs text-slate-muted uppercase tracking-wider mb-2">
                          Previous Value
                        </p>
                        <pre className="bg-slate-elevated rounded-lg p-3 text-xs text-slate-300 overflow-x-auto">
                          {formatJson(entry.old_value_redacted)}
                        </pre>
                      </div>
                    )}
                    {entry.new_value_redacted && (
                      <div>
                        <p className="text-xs text-slate-muted uppercase tracking-wider mb-2">
                          New Value
                        </p>
                        <pre className="bg-slate-elevated rounded-lg p-3 text-xs text-slate-300 overflow-x-auto">
                          {formatJson(entry.new_value_redacted)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
