/**
 * Gantt Chart Data Hook
 *
 * Fetches and transforms project task data for the Gantt chart.
 * Uses the dedicated /projects/{id}/gantt endpoint for optimized data.
 */

import { useMemo } from 'react';
import useSWR, { type SWRConfiguration } from 'swr';
import { projectsApi } from '@/lib/api/domains';
import type {
  GanttTask,
  GanttDependency,
  GanttApiResponse,
  ZoomLevel,
  GanttLayout,
} from '@/components/projects/gantt/types';
import {
  transformApiTasks,
  extractDependencies,
  sortTasksForGantt,
  calculateLayout,
  calculateDateRange,
} from '@/components/projects/gantt/utils';
import { DEFAULT_GANTT_CONFIG } from '@/components/projects/gantt/constants';

// =============================================================================
// TYPES
// =============================================================================

export interface GanttDataResult {
  tasks: GanttTask[];
  dependencies: GanttDependency[];
  dateRange: { start: Date; end: Date };
  layout: GanttLayout | null;
  isLoading: boolean;
  error: Error | null;
  mutate: () => void;
}

// =============================================================================
// HOOK
// =============================================================================

/**
 * Fetch and transform project task data for Gantt chart rendering.
 *
 * @param projectId - The project ID to fetch tasks for
 * @param zoomLevel - Current zoom level (affects layout calculation)
 * @param config - SWR configuration options
 */
export function useGanttData(
  projectId: number | null,
  zoomLevel: ZoomLevel = 'week',
  config?: SWRConfiguration
): GanttDataResult {
  // Fetch data from API
  const { data, isLoading, error, mutate } = useSWR(
    projectId ? (['project-gantt', projectId] as const) : null,
    ([, id]) => projectsApi.getProjectGanttData(id),
    {
      revalidateOnFocus: false,
      ...config,
    }
  );

  // Transform API response to GanttTask array
  const tasks = useMemo(() => {
    if (!data?.tasks) return [];

    // Transform and sort tasks
    const transformed = transformApiTasks(data as GanttApiResponse);
    return sortTasksForGantt(transformed);
  }, [data]);

  // Extract dependencies from tasks
  const dependencies = useMemo(() => {
    return extractDependencies(tasks);
  }, [tasks]);

  // Calculate date range
  const dateRange = useMemo(() => {
    return calculateDateRange(tasks);
  }, [tasks]);

  // Calculate layout based on zoom level
  const layout = useMemo(() => {
    if (tasks.length === 0) return null;
    return calculateLayout(tasks, zoomLevel, DEFAULT_GANTT_CONFIG);
  }, [tasks, zoomLevel]);

  return {
    tasks,
    dependencies,
    dateRange: {
      start: dateRange.startDate,
      end: dateRange.endDate,
    },
    layout,
    isLoading,
    error: error || null,
    mutate,
  };
}

// =============================================================================
// FALLBACK HOOK (Uses existing task list API)
// =============================================================================

/**
 * Fallback hook that uses the existing task list API.
 * Use this if the dedicated /gantt endpoint is not available.
 *
 * Note: This is less efficient as it requires fetching individual task details
 * to get dependency information.
 */
export function useGanttDataFallback(
  projectId: number | null,
  zoomLevel: ZoomLevel = 'week',
  config?: SWRConfiguration
): GanttDataResult {
  // Fetch task list
  const { data, isLoading, error, mutate } = useSWR(
    projectId ? (['project-gantt-fallback', projectId] as const) : null,
    async ([, id]) => {
      // Fetch all tasks for the project
      const response = await projectsApi.getProjectTasks({
        project_id: id,
        limit: 500, // Get all tasks
      });

      // Transform to GanttApiResponse format
      const tasks = (response.data || []).map((task: any) => ({
        id: task.id,
        subject: task.subject || 'Untitled',
        status: task.status || 'open',
        priority: task.priority || 'medium',
        progress: task.progress || 0,
        exp_start_date: task.exp_start_date,
        exp_end_date: task.exp_end_date,
        assigned_to: task.assigned_to,
        parent_task_id: task.parent_task_id,
        is_group: task.is_group || false,
        depends_on: task.depends_on?.map((d: any) => d.dependent_task_id).filter(Boolean) || [],
      }));

      return { tasks, date_range: { min_date: null, max_date: null } };
    },
    {
      revalidateOnFocus: false,
      ...config,
    }
  );

  // Transform to GanttTask array
  const tasks = useMemo(() => {
    if (!data?.tasks) return [];
    const transformed = transformApiTasks(data as GanttApiResponse);
    return sortTasksForGantt(transformed);
  }, [data]);

  // Extract dependencies
  const dependencies = useMemo(() => {
    return extractDependencies(tasks);
  }, [tasks]);

  // Calculate date range
  const dateRange = useMemo(() => {
    return calculateDateRange(tasks);
  }, [tasks]);

  // Calculate layout
  const layout = useMemo(() => {
    if (tasks.length === 0) return null;
    return calculateLayout(tasks, zoomLevel, DEFAULT_GANTT_CONFIG);
  }, [tasks, zoomLevel]);

  return {
    tasks,
    dependencies,
    dateRange: {
      start: dateRange.startDate,
      end: dateRange.endDate,
    },
    layout,
    isLoading,
    error: error || null,
    mutate,
  };
}

export default useGanttData;
