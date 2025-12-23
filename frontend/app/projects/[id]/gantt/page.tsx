'use client';

/**
 * Full-Screen Gantt Chart Page
 *
 * Dedicated page for viewing project timeline in full-screen mode
 * with expanded controls and visualization.
 */

import { useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  AlertTriangle,
  ArrowLeft,
  Maximize2,
  Minimize2,
  Download,
  Printer,
} from 'lucide-react';
import { useProjectDetail } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { GanttChart, type ZoomLevel } from '@/components/projects/gantt';

export default function ProjectGanttPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params?.id);
  const isValidId = Number.isFinite(id);

  const { data: project, isLoading, error } = useProjectDetail(isValidId ? id : null);
  const [zoomLevel, setZoomLevel] = useState<ZoomLevel>('week');
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Toggle fullscreen mode
  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  // Handle fullscreen change events
  if (typeof window !== 'undefined') {
    document.addEventListener('fullscreenchange', () => {
      setIsFullscreen(!!document.fullscreenElement);
    });
  }

  if (!isValidId) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-base p-6">
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center max-w-md">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Invalid project ID.</p>
          <Link
            href="/projects"
            className="mt-3 inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to projects
          </Link>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-base p-6">
        <div className="h-16 bg-slate-card border border-slate-border rounded-xl animate-pulse mb-4" />
        <div className="h-[calc(100vh-140px)] bg-slate-card border border-slate-border rounded-xl animate-pulse" />
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-base p-6">
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center max-w-md">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load project</p>
          <button
            onClick={() => router.back()}
            className="mt-3 inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-foreground hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={cn(
      'min-h-screen bg-slate-base flex flex-col',
      isFullscreen ? 'p-4' : 'p-6'
    )}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <Link
            href={`/projects/${id}`}
            className="inline-flex items-center justify-center w-10 h-10 rounded-lg border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <h1 className="text-xl font-bold text-foreground">{project.project_name}</h1>
            <p className="text-sm text-slate-muted">Project Timeline</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Fullscreen toggle */}
          <button
            onClick={toggleFullscreen}
            className={cn(
              'inline-flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors',
              'border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70'
            )}
            title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
          >
            {isFullscreen ? (
              <Minimize2 className="w-4 h-4" />
            ) : (
              <Maximize2 className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>

      {/* Gantt Chart - Full height */}
      <div className="flex-1 min-h-0">
        <GanttChart
          projectId={id}
          height={isFullscreen ? window.innerHeight - 120 : Math.max(600, window.innerHeight - 200)}
          zoomLevel={zoomLevel}
          onZoomChange={setZoomLevel}
          showDependencies={true}
          showTodayMarker={true}
          showProgress={true}
          onTaskClick={(task) => {
            router.push(`/projects/tasks/${task.id}`);
          }}
        />
      </div>

      {/* Legend */}
      <div className="mt-4 flex items-center justify-center gap-6 text-xs text-slate-muted">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-blue-500" />
          <span>Open</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-amber-500" />
          <span>Working</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-teal-500" />
          <span>Completed</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-purple-500" />
          <span>Pending Review</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-slate-500" />
          <span>Cancelled</span>
        </div>
        <div className="flex items-center gap-2 ml-4">
          <div className="w-6 h-0.5 border-t-2 border-dashed border-red-500" />
          <span>Today</span>
        </div>
        <div className="flex items-center gap-2">
          <svg width="24" height="10" viewBox="0 0 24 10">
            <path
              d="M 0 5 Q 12 0 24 5"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className="text-slate-muted"
            />
            <polygon points="22,3 24,5 22,7" fill="currentColor" className="text-slate-muted" />
          </svg>
          <span>Dependency</span>
        </div>
      </div>
    </div>
  );
}
