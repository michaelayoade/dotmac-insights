/**
 * Projects Domain API
 * Includes: Projects, Tasks, Dashboard, Analytics
 */

import { fetchApi } from '../core';

// =============================================================================
// TYPES
// =============================================================================

export type ProjectStatus = 'open' | 'completed' | 'cancelled' | 'on_hold';
export type ProjectPriority = 'low' | 'medium' | 'high';

export interface ProjectUser {
  user?: string | null;
  full_name?: string | null;
  email?: string | null;
  project_status?: string | null;
  view_attachments?: boolean;
  welcome_email_sent?: boolean;
  idx?: number;
}

export interface ProjectListItem {
  id: number;
  erpnext_id: string | null;
  project_name: string;
  project_type: string | null;
  status: ProjectStatus;
  priority: ProjectPriority | null;
  department: string | null;
  customer_id: number | null;
  percent_complete: number | null;
  expected_start_date: string | null;
  expected_end_date: string | null;
  estimated_costing: number | null;
  total_billed_amount: number | null;
  is_overdue: boolean;
  task_count: number | null;
  created_at: string | null;
  write_back_status?: string | null;
}

export interface ProjectListResponse {
  total: number;
  limit: number;
  offset: number;
  data: ProjectListItem[];
}

export interface ProjectDetail extends ProjectListItem {
  company?: string | null;
  cost_center?: string | null;
  project_manager_id?: number | null;
  project_manager?: string | null;
  erpnext_customer?: string | null;
  erpnext_sales_order?: string | null;
  percent_complete_method?: string | null;
  is_active?: string | null;
  actual_time?: number | null;
  total_consumed_material_cost?: number | null;
  total_costing_amount?: number | null;
  total_expense_claim?: number | null;
  total_purchase_cost?: number | null;
  total_sales_amount?: number | null;
  total_billable_amount?: number | null;
  gross_margin?: number | null;
  per_gross_margin?: number | null;
  collect_progress?: boolean;
  frequency?: string | null;
  message?: string | null;
  notes?: string | null;
  actual_start_date?: string | null;
  actual_end_date?: string | null;
  from_time?: string | null;
  to_time?: string | null;
  customer?: Record<string, unknown> | null;
  users?: ProjectUser[];
  tasks?: unknown[];
  task_stats?: Record<string, unknown>;
  expenses?: unknown[];
  time_tracking?: Record<string, unknown>;
}

export interface ProjectPayload {
  project_name?: string;
  project_type?: string | null;
  status?: ProjectStatus;
  priority?: ProjectPriority;
  department?: string | null;
  company?: string | null;
  cost_center?: string | null;
  customer_id?: number | null;
  project_manager_id?: number | null;
  erpnext_customer?: string | null;
  erpnext_sales_order?: string | null;
  percent_complete?: number | null;
  percent_complete_method?: string | null;
  is_active?: string | null;
  actual_time?: number | null;
  total_consumed_material_cost?: number | null;
  estimated_costing?: number | null;
  total_costing_amount?: number | null;
  total_expense_claim?: number | null;
  total_purchase_cost?: number | null;
  total_sales_amount?: number | null;
  total_billable_amount?: number | null;
  total_billed_amount?: number | null;
  gross_margin?: number | null;
  per_gross_margin?: number | null;
  collect_progress?: boolean;
  frequency?: string | null;
  message?: string | null;
  notes?: string | null;
  expected_start_date?: string | null;
  expected_end_date?: string | null;
  actual_start_date?: string | null;
  actual_end_date?: string | null;
  from_time?: string | null;
  to_time?: string | null;
  users?: ProjectUser[];
}

export interface ProjectsDashboard {
  cards?: Record<string, number>;
  projects?: {
    total?: number;
    active?: number;
    completed?: number;
    on_hold?: number;
    cancelled?: number;
  };
  tasks?: {
    total?: number;
    open?: number;
    overdue?: number;
  };
  financials?: {
    total_billed?: number;
  };
  metrics?: {
    avg_completion_percent?: number;
    due_this_week?: number;
    [key: string]: unknown;
  };
  by_priority?: Record<string, number>;
}

export interface ProjectTaskListResponse {
  total: number;
  limit: number;
  offset: number;
  data: unknown[];
}

export interface ProjectListParams {
  status?: string;
  priority?: ProjectPriority;
  customer_id?: number;
  project_type?: string;
  department?: string;
  search?: string;
  overdue_only?: boolean;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
}

export interface ProjectTaskParams {
  project_id?: number;
  status?: string;
  priority?: string;
  assigned_to?: string;
  task_type?: string;
  search?: string;
  overdue_only?: boolean;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
}

export interface ProjectTaskUpdatePayload {
  assigned_to?: string;
}

export interface ProjectTaskCreatePayload {
  subject: string;
  project_id?: number;
  status?: string;
  priority?: string;
  assigned_to?: string;
  task_type?: string;
  exp_start_date?: string;
  exp_end_date?: string;
  description?: string;
}

export interface ProjectTask {
  id: number;
  subject?: string;
}

// =============================================================================
// MILESTONE TYPES
// =============================================================================

export type MilestoneStatus = 'planned' | 'in_progress' | 'completed' | 'on_hold';

export interface Milestone {
  id: number;
  project_id: number;
  name: string;
  description?: string | null;
  status: MilestoneStatus;
  planned_start_date?: string | null;
  planned_end_date?: string | null;
  actual_start_date?: string | null;
  actual_end_date?: string | null;
  percent_complete: number;
  idx: number;
  is_overdue: boolean;
  task_count: number;
  tasks?: Array<{
    id: number;
    erpnext_id?: string | null;
    subject: string;
    status?: string | null;
    priority?: string | null;
    assigned_to?: string | null;
    progress: number;
    exp_start_date?: string | null;
    exp_end_date?: string | null;
    is_overdue: boolean;
  }>;
  created_by_id?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface MilestoneListResponse {
  total: number;
  data: Milestone[];
}

export interface MilestoneCreatePayload {
  name: string;
  description?: string | null;
  status?: MilestoneStatus;
  planned_start_date?: string | null;
  planned_end_date?: string | null;
  actual_start_date?: string | null;
  actual_end_date?: string | null;
  percent_complete?: number;
  idx?: number;
}

export interface MilestoneUpdatePayload {
  name?: string;
  description?: string | null;
  status?: MilestoneStatus;
  planned_start_date?: string | null;
  planned_end_date?: string | null;
  actual_start_date?: string | null;
  actual_end_date?: string | null;
  percent_complete?: number;
  idx?: number;
}

// =============================================================================
// COMMENT TYPES
// =============================================================================

export type EntityType = 'project' | 'task' | 'milestone';

export interface ProjectComment {
  id: number;
  entity_type: EntityType;
  entity_id: number;
  content: string;
  author_id: number;
  author_name?: string | null;
  author_email?: string | null;
  is_edited: boolean;
  edited_at?: string | null;
  created_at?: string | null;
}

export interface CommentListResponse {
  total: number;
  limit: number;
  offset: number;
  data: ProjectComment[];
}

export interface CommentCreatePayload {
  content: string;
}

export interface CommentUpdatePayload {
  content: string;
}

// =============================================================================
// ACTIVITY TYPES
// =============================================================================

export type ProjectActivityType =
  | 'created'
  | 'updated'
  | 'status_changed'
  | 'assigned'
  | 'comment_added'
  | 'attachment_added'
  | 'milestone_completed'
  | 'task_completed'
  | 'approval_submitted'
  | 'approval_approved'
  | 'approval_rejected';

export interface ProjectActivity {
  id: number;
  entity_type: EntityType;
  entity_id: number;
  activity_type: ProjectActivityType;
  description: string;
  from_value?: string | null;
  to_value?: string | null;
  changed_fields?: string[] | null;
  actor_id?: number | null;
  actor_name?: string | null;
  actor_email?: string | null;
  created_at?: string | null;
}

export interface ActivityListResponse {
  total: number;
  limit: number;
  offset: number;
  data: ProjectActivity[];
}

export interface ActivityTimelineResponse {
  project_id: number;
  total: number;
  data: ProjectActivity[];
}

// =============================================================================
// ATTACHMENT TYPES
// =============================================================================

export interface ProjectAttachment {
  id: number;
  doctype?: string;
  document_id?: number;
  file_name: string;
  file_path?: string;
  file_type?: string | null;
  file_size?: number | null;
  attachment_type?: string | null;
  is_primary: boolean;
  description?: string | null;
  uploaded_at?: string | null;
  uploaded_by_id?: number | null;
}

export interface AttachmentListResponse {
  total: number;
  data: ProjectAttachment[];
}

// =============================================================================
// APPROVAL TYPES
// =============================================================================

export type ApprovalStatusType = 'draft' | 'pending' | 'approved' | 'rejected' | 'cancelled' | 'posted';

// =============================================================================
// TEMPLATE TYPES
// =============================================================================

export interface MilestoneTemplateItem {
  id: number;
  project_template_id: number;
  name: string;
  description?: string | null;
  start_day_offset: number;
  end_day_offset: number;
  idx: number;
}

export interface TaskTemplateItem {
  id: number;
  project_template_id: number;
  subject: string;
  description?: string | null;
  priority: ProjectPriority;
  start_day_offset: number;
  duration_days: number;
  default_assigned_role?: string | null;
  parent_template_id?: number | null;
  milestone_template_id?: number | null;
  is_group: boolean;
  idx: number;
}

export interface ProjectTemplate {
  id: number;
  name: string;
  description?: string | null;
  project_type?: string | null;
  default_priority: ProjectPriority;
  estimated_duration_days?: number | null;
  default_notes?: string | null;
  is_active: boolean;
  company?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  milestone_templates?: MilestoneTemplateItem[];
  task_templates?: TaskTemplateItem[];
  milestones?: MilestoneTemplateItem[];
  tasks?: TaskTemplateItem[];
  milestone_count?: number;
  task_count?: number;
}

export interface ProjectTemplateListResponse {
  total: number;
  data: ProjectTemplate[];
}

export interface MilestoneTemplatePayload {
  name: string;
  description?: string | null;
  start_day_offset?: number;
  end_day_offset?: number;
  idx?: number;
}

export interface TaskTemplatePayload {
  subject: string;
  description?: string | null;
  priority?: ProjectPriority;
  start_day_offset?: number;
  duration_days?: number;
  default_assigned_role?: string | null;
  parent_template_id?: number | null;
  milestone_template_id?: number | null;
  is_group?: boolean;
  idx?: number;
}

export interface ProjectTemplateCreatePayload {
  name: string;
  description?: string | null;
  project_type?: string | null;
  default_priority?: ProjectPriority;
  estimated_duration_days?: number | null;
  default_notes?: string | null;
  is_active?: boolean;
  milestone_templates?: MilestoneTemplatePayload[];
  task_templates?: TaskTemplatePayload[];
}

export interface ProjectTemplateUpdatePayload {
  name?: string;
  description?: string | null;
  project_type?: string | null;
  default_priority?: ProjectPriority;
  estimated_duration_days?: number | null;
  default_notes?: string | null;
  is_active?: boolean;
  milestone_templates?: MilestoneTemplatePayload[];
  task_templates?: TaskTemplatePayload[];
}

export interface CreateFromTemplatePayload {
  project_name: string;
  expected_start_date?: string;
  customer_id?: number | null;
  project_manager_id?: number | null;
  notes?: string | null;
}

export interface ApprovalHistoryItem {
  step_order: number;
  action: string;
  user_id: number;
  remarks?: string | null;
  action_at: string;
}

export interface ProjectApprovalStatus {
  project_id: number;
  has_approval: boolean;
  approval_id?: number;
  status?: ApprovalStatusType | null;
  current_step?: number | null;
  current_step_name?: string | null;
  amount?: string | null;
  submitted_at?: string | null;
  submitted_by_id?: number | null;
  approved_at?: string | null;
  approved_by_id?: number | null;
  rejected_at?: string | null;
  rejected_by_id?: number | null;
  rejection_reason?: string | null;
  posted_at?: string | null;
  posted_by_id?: number | null;
  message?: string;
  history?: ApprovalHistoryItem[];
}

// =============================================================================
// CHANGE HISTORY TYPES
// =============================================================================

export type HistorySource = 'audit' | 'activity';

export interface ChangeHistoryItem {
  id: string;
  source: HistorySource;
  timestamp?: string | null;
  action?: string | null;
  actor_id?: number | null;
  actor_name?: string | null;
  actor_email?: string | null;
  description?: string | null;
  changed_fields?: string[] | null;
  old_values?: Record<string, unknown> | null;
  new_values?: Record<string, unknown> | null;
  from_value?: string | null;
  to_value?: string | null;
  remarks?: string | null;
}

export interface ChangeHistoryResponse {
  entity_type: EntityType;
  entity_id: number;
  total: number;
  data: ChangeHistoryItem[];
}

// =============================================================================
// API
// =============================================================================

export const projectsApi = {
  // =========================================================================
  // PROJECTS
  // =========================================================================

  getProjects: (params?: ProjectListParams) =>
    fetchApi<ProjectListResponse>('/projects', {
      params: params ? ({ ...params } as Record<string, unknown>) : undefined,
    }),

  getProjectDetail: (id: number) => fetchApi<ProjectDetail>(`/projects/${id}`),

  createProject: (body: ProjectPayload & { project_name: string }) =>
    fetchApi<ProjectDetail>('/projects', { method: 'POST', body: JSON.stringify(body) }),

  updateProject: (id: number, body: ProjectPayload) =>
    fetchApi<ProjectDetail>(`/projects/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteProject: (id: number) =>
    fetchApi<{ message: string; id: number }>(`/projects/${id}`, { method: 'DELETE' }),

  // =========================================================================
  // DASHBOARD & ANALYTICS
  // =========================================================================

  getProjectsDashboard: () => fetchApi<ProjectsDashboard>('/projects/dashboard'),

  getProjectsStatusTrend: (months = 12) =>
    fetchApi<unknown>('/projects/analytics/status-trend', { params: { months } }),

  getProjectsTaskDistribution: () =>
    fetchApi<unknown>('/projects/analytics/task-distribution'),

  getProjectsPerformance: () => fetchApi<unknown>('/projects/analytics/project-performance'),

  getProjectsDepartmentSummary: (months = 12) =>
    fetchApi<unknown>('/projects/analytics/department-summary', { params: { months } }),

  // =========================================================================
  // TASKS
  // =========================================================================

  getProjectTasks: (params?: ProjectTaskParams) =>
    fetchApi<ProjectTaskListResponse>('/projects/tasks', {
      params: params ? ({ ...params } as Record<string, unknown>) : undefined,
    }),

  createTask: (body: ProjectTaskCreatePayload) =>
    fetchApi<ProjectTask>('/projects/tasks', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getTaskDetail: (id: number) => fetchApi<unknown>(`/projects/tasks/${id}`),

  updateTask: (id: number, body: ProjectTaskUpdatePayload) =>
    fetchApi<unknown>(`/projects/tasks/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  // =========================================================================
  // GANTT CHART
  // =========================================================================

  /**
   * Get tasks with full dependency data for Gantt chart.
   * Returns all tasks for a project with their dependencies.
   */
  getProjectGanttData: (projectId: number) =>
    fetchApi<{
      tasks: Array<{
        id: number;
        subject: string;
        status: string;
        priority: string;
        progress: number | null;
        exp_start_date: string | null;
        exp_end_date: string | null;
        assigned_to: string | null;
        parent_task_id: number | null;
        is_group: boolean;
        depends_on: number[];
      }>;
      date_range: {
        min_date: string | null;
        max_date: string | null;
      };
    }>(`/projects/${projectId}/gantt`),

  // =========================================================================
  // MILESTONES
  // =========================================================================

  /** List all milestones for a project */
  getProjectMilestones: (projectId: number, status?: MilestoneStatus) =>
    fetchApi<MilestoneListResponse>(`/projects/${projectId}/milestones`, {
      params: status ? { status } : undefined,
    }),

  /** Get a specific milestone with its tasks */
  getMilestone: (milestoneId: number) =>
    fetchApi<Milestone>(`/projects/milestones/${milestoneId}`),

  /** Create a new milestone */
  createMilestone: (projectId: number, body: MilestoneCreatePayload) =>
    fetchApi<Milestone>(`/projects/${projectId}/milestones`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** Update a milestone */
  updateMilestone: (milestoneId: number, body: MilestoneUpdatePayload) =>
    fetchApi<Milestone>(`/projects/milestones/${milestoneId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  /** Delete a milestone */
  deleteMilestone: (milestoneId: number) =>
    fetchApi<{ message: string; id: number }>(`/projects/milestones/${milestoneId}`, {
      method: 'DELETE',
    }),

  /** Assign or unassign a task to a milestone */
  assignTaskToMilestone: (taskId: number, milestoneId: number | null) =>
    fetchApi<{ message: string; task_id: number; milestone_id: number | null }>(
      `/projects/tasks/${taskId}/milestone`,
      {
        method: 'POST',
        params: milestoneId !== null ? { milestone_id: milestoneId } : undefined,
      }
    ),

  // =========================================================================
  // COMMENTS
  // =========================================================================

  /** List comments for an entity */
  getEntityComments: (
    entityType: EntityType,
    entityId: number,
    params?: { limit?: number; offset?: number }
  ) =>
    fetchApi<CommentListResponse>(`/projects/${entityType}/${entityId}/comments`, {
      params: params as Record<string, unknown>,
    }),

  /** Create a comment */
  createComment: (entityType: EntityType, entityId: number, body: CommentCreatePayload) =>
    fetchApi<ProjectComment>(`/projects/${entityType}/${entityId}/comments`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** Update a comment */
  updateComment: (commentId: number, body: CommentUpdatePayload) =>
    fetchApi<ProjectComment>(`/projects/comments/${commentId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  /** Delete a comment */
  deleteComment: (commentId: number) =>
    fetchApi<{ message: string; id: number }>(`/projects/comments/${commentId}`, {
      method: 'DELETE',
    }),

  // =========================================================================
  // ACTIVITY FEED
  // =========================================================================

  /** List activities for an entity */
  getEntityActivities: (
    entityType: EntityType,
    entityId: number,
    params?: { activity_type?: ProjectActivityType; limit?: number; offset?: number }
  ) =>
    fetchApi<ActivityListResponse>(`/projects/${entityType}/${entityId}/activities`, {
      params: params as Record<string, unknown>,
    }),

  /** Get combined activity timeline for a project */
  getProjectActivityTimeline: (projectId: number, limit?: number) =>
    fetchApi<ActivityTimelineResponse>(`/projects/${projectId}/activity-timeline`, {
      params: limit ? { limit } : undefined,
    }),

  // =========================================================================
  // ATTACHMENTS
  // =========================================================================

  /** List attachments for an entity */
  getEntityAttachments: (entityType: EntityType, entityId: number) =>
    fetchApi<AttachmentListResponse>(`/projects/${entityType}/${entityId}/attachments`),

  /** Upload an attachment */
  uploadAttachment: (
    entityType: EntityType,
    entityId: number,
    file: File,
    options?: { attachment_type?: string; description?: string; is_primary?: boolean }
  ) => {
    const formData = new FormData();
    formData.append('file', file);
    if (options?.attachment_type) formData.append('attachment_type', options.attachment_type);
    if (options?.description) formData.append('description', options.description);
    if (options?.is_primary) formData.append('is_primary', 'true');

    return fetchApi<{ message: string; id: number; file_name: string; file_size: number }>(
      `/projects/${entityType}/${entityId}/attachments`,
      {
        method: 'POST',
        body: formData,
        headers: {}, // Let browser set Content-Type for FormData
      }
    );
  },

  /** Get attachment details */
  getAttachment: (attachmentId: number) =>
    fetchApi<ProjectAttachment>(`/projects/attachments/${attachmentId}`),

  /** Delete an attachment */
  deleteAttachment: (attachmentId: number) =>
    fetchApi<{ message: string; id: number }>(`/projects/attachments/${attachmentId}`, {
      method: 'DELETE',
    }),

  /** Get attachment download URL */
  getAttachmentDownloadUrl: (attachmentId: number) =>
    `/api/projects/attachments/${attachmentId}/download`,

  // =========================================================================
  // APPROVAL WORKFLOWS
  // =========================================================================

  /** Get approval status for a project */
  getProjectApprovalStatus: (projectId: number) =>
    fetchApi<ProjectApprovalStatus>(`/projects/${projectId}/approval-status`),

  /** Submit project for approval */
  submitProjectForApproval: (projectId: number, remarks?: string) =>
    fetchApi<{ message: string; project_id: number; approval_id: number; status: string }>(
      `/projects/${projectId}/submit-approval`,
      {
        method: 'POST',
        body: JSON.stringify({ remarks }),
      }
    ),

  /** Approve a project */
  approveProject: (projectId: number, remarks?: string) =>
    fetchApi<{ message: string; project_id: number; approval_id: number; status: string; current_step: number }>(
      `/projects/${projectId}/approve`,
      {
        method: 'POST',
        body: JSON.stringify({ remarks }),
      }
    ),

  /** Reject a project */
  rejectProject: (projectId: number, reason: string) =>
    fetchApi<{ message: string; project_id: number; approval_id: number; status: string; reason: string }>(
      `/projects/${projectId}/reject`,
      {
        method: 'POST',
        body: JSON.stringify({ reason }),
      }
    ),

  /** Check if current user can approve */
  canApproveProject: (projectId: number) =>
    fetchApi<{ project_id: number; user_id: number; can_approve: boolean }>(
      `/projects/${projectId}/can-approve`
    ),

  // =========================================================================
  // PROJECT TEMPLATES
  // =========================================================================

  /** List all project templates */
  getTemplates: (params?: { active_only?: boolean; is_active?: boolean; project_type?: string }) =>
    fetchApi<ProjectTemplateListResponse>('/projects/templates', {
      params: params as Record<string, unknown>,
    }),

  /** Get a specific template with milestones and tasks */
  getTemplate: (templateId: number) =>
    fetchApi<ProjectTemplate>(`/projects/templates/${templateId}`),

  /** Create a new project template */
  createTemplate: (body: ProjectTemplateCreatePayload) =>
    fetchApi<ProjectTemplate>('/projects/templates', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** Update a project template */
  updateTemplate: (templateId: number, body: ProjectTemplateUpdatePayload) =>
    fetchApi<ProjectTemplate>(`/projects/templates/${templateId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  /** Delete a project template */
  deleteTemplate: (templateId: number) =>
    fetchApi<{ message: string; id: number }>(`/projects/templates/${templateId}`, {
      method: 'DELETE',
    }),

  /** Create a new project from a template */
  createFromTemplate: (templateId: number, body: CreateFromTemplatePayload) =>
    fetchApi<{ message: string; project_id: number; project_name: string; milestones_created: number; tasks_created: number }>(
      `/projects/from-template/${templateId}`,
      {
        method: 'POST',
        body: JSON.stringify(body),
      }
    ),

  // =========================================================================
  // CHANGE HISTORY
  // =========================================================================

  /** Get change history for an entity */
  getEntityHistory: (
    entityType: EntityType,
    entityId: number,
    params?: { limit?: number; offset?: number }
  ) =>
    fetchApi<ChangeHistoryResponse>(`/projects/${entityType}/${entityId}/history`, {
      params: params as Record<string, unknown>,
    }),
};

export default projectsApi;
