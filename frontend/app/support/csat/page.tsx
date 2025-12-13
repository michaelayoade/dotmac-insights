'use client';

import { useState } from 'react';
import { BarChart3, Smile } from 'lucide-react';
import { useSupportCsatAgentPerformance, useSupportCsatSummary, useSupportCsatSurveys, useSupportCsatTrends } from '@/hooks/useApi';

export default function SupportCsatPage() {
  const [days, setDays] = useState(30);
  const surveys = useSupportCsatSurveys({ active_only: true });
  const summary = useSupportCsatSummary({ days });
  const agents = useSupportCsatAgentPerformance({ days });
  const trends = useSupportCsatTrends({ months: 6 });

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Smile className="w-5 h-5 text-teal-electric" />
        <div>
          <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Support</p>
          <h1 className="text-xl font-semibold text-white">CSAT & Feedback</h1>
          <p className="text-slate-muted text-sm">Surveys, responses, and trends</p>
        </div>
      </div>

      <div className="flex items-center gap-3 text-sm text-slate-muted">
        <label className="inline-flex items-center gap-2">
          <span>Window (days)</span>
          <input
            type="number"
            value={days}
            onChange={(e) => setDays(Number(e.target.value) || 30)}
            className="w-20 bg-slate-elevated border border-slate-border rounded px-2 py-1 text-white"
          />
        </label>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Stat title="Avg rating" value={summary.data?.average_rating?.toFixed?.(2) || '0.00'} />
        <Stat title="Responses" value={summary.data?.total_responses || 0} />
        <Stat title="Response rate" value={`${summary.data?.response_rate?.toFixed?.(1) ?? 0}%`} />
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-teal-electric" />
          <span className="text-white text-sm font-medium">Surveys</span>
        </div>
        {!surveys.data ? (
          <p className="text-slate-muted text-sm">Loading surveys…</p>
        ) : surveys.data.length === 0 ? (
          <p className="text-slate-muted text-sm">No surveys found.</p>
        ) : (
          <div className="space-y-2">
            {surveys.data.map((survey) => (
              <div key={survey.id} className="border border-slate-border rounded-lg px-3 py-2">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-white font-semibold">{survey.name}</p>
                    <p className="text-slate-muted text-xs">{survey.survey_type?.toUpperCase?.() || survey.survey_type}</p>
                  </div>
                  <span className="text-xs text-slate-muted px-2 py-1 rounded border border-slate-border">
                    {survey.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
                <p className="text-slate-muted text-xs">Trigger: {survey.trigger || '-'}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-teal-electric" />
            <span className="text-white text-sm font-medium">Agent performance ({days}d)</span>
          </div>
          {!agents.data ? (
            <p className="text-slate-muted text-sm">Loading agent stats…</p>
          ) : agents.data.length === 0 ? (
            <p className="text-slate-muted text-sm">No responses.</p>
          ) : (
            <div className="space-y-2">
              {agents.data.map((row) => (
                <div key={row.agent_id} className="border border-slate-border rounded-lg px-3 py-2">
                  <div className="flex items-center justify-between">
                    <p className="text-white font-semibold">{row.agent_name || row.agent_id}</p>
                    <span className="text-xs text-slate-muted">{row.response_count} responses</span>
                  </div>
                  <p className="text-slate-muted text-xs">
                    Avg: {row.avg_rating?.toFixed?.(2) ?? 0} • Satisfaction: {row.satisfaction_pct?.toFixed?.(1) ?? 0}%
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-teal-electric" />
            <span className="text-white text-sm font-medium">Trends (6m)</span>
          </div>
          {!trends.data ? (
            <p className="text-slate-muted text-sm">Loading trends…</p>
          ) : trends.data.length === 0 ? (
            <p className="text-slate-muted text-sm">No trend data.</p>
          ) : (
            <div className="space-y-2 text-sm text-slate-muted">
              {trends.data.map((t, idx) => (
                <p key={idx}>{t.period}: {t.avg_rating?.toFixed?.(2) ?? 0} ({t.response_count} responses)</p>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({ title, value }: { title: string; value: string | number }) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-4">
      <p className="text-slate-muted text-sm">{title}</p>
      <p className="text-2xl font-bold text-white">{value}</p>
    </div>
  );
}
