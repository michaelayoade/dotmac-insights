'use client';

import {
  Activity,
  Loader2,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';
import type { EntityType } from '@/lib/api/domains/projects';
import { useEntityActivities, useProjectActivityTimeline } from '@/hooks/useApi';
import { ActivityItem } from './ActivityItem';
import { Button } from '@/components/ui';

interface ActivityFeedProps {
  entityType: EntityType;
  entityId: number;
  title?: string;
  /** If true and entityType is 'project', shows combined timeline */
  showTimeline?: boolean;
  /** Max items to show initially */
  limit?: number;
}

export function ActivityFeed({
  entityType,
  entityId,
  title = 'Activity',
  showTimeline = false,
  limit = 50,
}: ActivityFeedProps) {
  // Use timeline API for projects with showTimeline, otherwise use entity activities
  const timelineResult = useProjectActivityTimeline(
    showTimeline && entityType === 'project' ? entityId : null,
    limit
  );
  const entityResult = useEntityActivities(
    !showTimeline || entityType !== 'project' ? entityType : null,
    !showTimeline || entityType !== 'project' ? entityId : null,
    { limit }
  );

  const isTimeline = showTimeline && entityType === 'project';
  const { data, isLoading, error, mutate } = isTimeline ? timelineResult : entityResult;

  const activities = isTimeline
    ? (data as { data?: unknown[] })?.data || []
    : (data as { data?: unknown[] })?.data || [];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-6 h-6 text-teal-electric animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-center">
        <AlertTriangle className="w-6 h-6 text-red-400 mx-auto mb-2" />
        <p className="text-red-400 text-sm">Failed to load activity</p>
        <Button
          onClick={() => mutate()}
          className="mt-2 text-xs text-slate-muted hover:text-foreground"
        >
          <RefreshCw className="w-3 h-3 mr-1" />
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-teal-electric" />
          <h3 className="text-foreground font-semibold">
            {title} {isTimeline ? '(All)' : ''}
          </h3>
        </div>
        <Button
          onClick={() => mutate()}
          className="p-1.5 text-slate-muted hover:text-foreground transition-colors"
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4" />
        </Button>
      </div>

      {/* Activity List */}
      {activities.length > 0 ? (
        <div className="relative">
          {activities.map((activity: unknown, index: number) => (
            <ActivityItem
              key={(activity as { id: number }).id || index}
              activity={activity as Parameters<typeof ActivityItem>[0]['activity']}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-slate-muted">
          <Activity className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">No activity yet</p>
          <p className="text-xs mt-1">Actions on this {entityType} will appear here</p>
        </div>
      )}
    </div>
  );
}

export default ActivityFeed;
