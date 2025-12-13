'use client';

import { BarChart3 } from 'lucide-react';

export default function ProjectsAnalyticsPage() {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <BarChart3 className="w-5 h-5 text-teal-electric" />
        <div>
          <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Projects</p>
          <h1 className="text-xl font-semibold text-white">Analytics</h1>
          <p className="text-slate-muted text-sm">Performance, throughput, and health (coming soon)</p>
        </div>
      </div>
      <div className="bg-slate-card border border-slate-border rounded-xl p-4 text-slate-muted text-sm">
        Analytics widgets will live here. Connect to the project analytics endpoints once available.
      </div>
    </div>
  );
}
