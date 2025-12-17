/**
 * CRM Domain API
 * Includes: Leads, Opportunities, Activities, Contacts, Pipeline
 */

import { fetchApi } from '../core';

// =============================================================================
// TYPES
// =============================================================================

// Lead Types
export interface Lead {
  id: number;
  lead_name: string;
  company_name?: string;
  email_id?: string;
  phone?: string;
  mobile_no?: string;
  website?: string;
  source?: string;
  lead_owner?: string;
  territory?: string;
  industry?: string;
  market_segment?: string;
  city?: string;
  state?: string;
  country?: string;
  notes?: string;
  status: string;
  qualification_status?: string;
  converted: boolean;
  created_at: string;
  updated_at: string;
}

export interface LeadListResponse {
  items: Lead[];
  total: number;
  page: number;
  page_size: number;
}

export interface LeadSummaryResponse {
  total_leads: number;
  new_leads: number;
  qualified_leads: number;
  converted_leads: number;
  lost_leads: number;
  by_status: Record<string, number>;
  by_source: Record<string, number>;
}

export interface LeadCreatePayload {
  lead_name: string;
  company_name?: string;
  email_id?: string;
  phone?: string;
  mobile_no?: string;
  website?: string;
  source?: string;
  lead_owner?: string;
  territory?: string;
  industry?: string;
  market_segment?: string;
  city?: string;
  state?: string;
  country?: string;
  notes?: string;
}

export interface LeadConvertPayload {
  customer_name?: string;
  customer_type?: string;
  create_opportunity?: boolean;
  opportunity_name?: string;
  deal_value?: number;
}

export interface LeadConvertResponse {
  success: boolean;
  customer_id: number;
  contact_id: number;
  opportunity_id?: number;
}

export interface LeadListParams {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
  source?: string;
  territory?: string;
  converted?: boolean;
}

// Opportunity Types
export interface OpportunityStage {
  id: number;
  name: string;
  probability: number;
  color?: string;
}

export interface Opportunity {
  id: number;
  name: string;
  description?: string;
  lead_id?: number;
  lead_name?: string;
  customer_id?: number;
  customer_name?: string;
  stage_id?: number;
  stage?: OpportunityStage;
  stage_name?: string;
  status: string;
  currency: string;
  deal_value: number;
  probability: number;
  weighted_value: number;
  expected_close_date?: string;
  actual_close_date?: string;
  owner_id?: number;
  sales_person_id?: number;
  source?: string;
  campaign?: string;
  lost_reason?: string;
  competitor?: string;
  quotation_id?: number;
  sales_order_id?: number;
  created_at: string;
  updated_at: string;
}

export interface OpportunityListResponse {
  items: Opportunity[];
  total: number;
  page: number;
  page_size: number;
}

export interface PipelineSummaryResponse {
  total_opportunities: number;
  total_value: number;
  weighted_value: number;
  won_count: number;
  won_value: number;
  lost_count: number;
  by_stage: {
    stage_id: number;
    stage_name: string;
    color?: string;
    probability: number;
    count: number;
    value: number;
  }[];
  avg_deal_size: number;
  win_rate: number;
}

export interface OpportunityCreatePayload {
  name: string;
  description?: string;
  lead_id?: number;
  customer_id?: number;
  stage_id?: number;
  deal_value?: number;
  probability?: number;
  expected_close_date?: string;
  owner_id?: number;
  sales_person_id?: number;
  source?: string;
  campaign?: string;
}

export interface OpportunityListParams {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
  stage_id?: number;
  customer_id?: number;
  owner_id?: number;
  min_value?: number;
  max_value?: number;
}

// Activity Types
export interface Activity {
  id: number;
  activity_type: string;
  subject: string;
  description?: string;
  status: string;
  lead_id?: number;
  customer_id?: number;
  opportunity_id?: number;
  lead_name?: string;
  customer_name?: string;
  opportunity_name?: string;
  contact_id?: number;
  scheduled_at?: string;
  duration_minutes?: number;
  completed_at?: string;
  owner_id?: number;
  assigned_to_id?: number;
  priority?: string;
  reminder_at?: string;
  call_direction?: string;
  call_outcome?: string;
  created_at: string;
  updated_at: string;
}

export interface ActivityListResponse {
  items: Activity[];
  total: number;
  page: number;
  page_size: number;
}

export interface ActivitySummaryResponse {
  total_activities: number;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
  overdue_count: number;
  today_count: number;
  upcoming_week: number;
}

export interface ActivityCreatePayload {
  activity_type: string;
  subject: string;
  description?: string;
  lead_id?: number;
  customer_id?: number;
  opportunity_id?: number;
  contact_id?: number;
  scheduled_at?: string;
  duration_minutes?: number;
  owner_id?: number;
  assigned_to_id?: number;
  priority?: string;
  reminder_at?: string;
  call_direction?: string;
}

export interface ActivityListParams {
  page?: number;
  page_size?: number;
  activity_type?: string;
  status?: string;
  lead_id?: number;
  customer_id?: number;
  opportunity_id?: number;
  owner_id?: number;
  assigned_to_id?: number;
  start_date?: string;
  end_date?: string;
}

export interface ActivityTimelineParams {
  customer_id?: number;
  lead_id?: number;
  opportunity_id?: number;
  limit?: number;
}

export interface ActivityTimelineResponse {
  items: Activity[];
  count: number;
}

// Contact Types
export interface Contact {
  id: number;
  customer_id?: number;
  lead_id?: number;
  first_name: string;
  last_name?: string;
  full_name: string;
  email?: string;
  phone?: string;
  mobile?: string;
  designation?: string;
  department?: string;
  is_primary: boolean;
  is_billing_contact: boolean;
  is_decision_maker: boolean;
  is_active: boolean;
  unsubscribed: boolean;
  linkedin_url?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface ContactListResponse {
  items: Contact[];
  total: number;
  page: number;
  page_size: number;
}

export interface ContactCreatePayload {
  customer_id?: number;
  lead_id?: number;
  first_name: string;
  last_name?: string;
  email?: string;
  phone?: string;
  mobile?: string;
  designation?: string;
  department?: string;
  is_primary?: boolean;
  is_billing_contact?: boolean;
  is_decision_maker?: boolean;
  linkedin_url?: string;
  notes?: string;
}

export interface ContactListParams {
  page?: number;
  page_size?: number;
  search?: string;
  customer_id?: number;
  lead_id?: number;
  is_primary?: boolean;
  is_decision_maker?: boolean;
  is_active?: boolean;
}

export interface ContactsByEntityResponse {
  items: Contact[];
  count: number;
}

// Pipeline Stage Types
export interface PipelineStage {
  id: number;
  name: string;
  sequence: number;
  probability: number;
  is_won: boolean;
  is_lost: boolean;
  is_active: boolean;
  color?: string;
  opportunity_count: number;
  opportunity_value: number;
  created_at: string;
  updated_at: string;
}

export interface PipelineViewResponse {
  stages: PipelineStage[];
  unassigned_count: number;
  unassigned_value: number;
  total_value: number;
  weighted_value: number;
}

export interface KanbanColumn {
  stage_id: number;
  stage_name: string;
  color?: string;
  probability: number;
  opportunities: {
    id: number;
    name: string;
    customer_name?: string;
    deal_value: number;
    probability: number;
    expected_close_date?: string;
  }[];
  count: number;
  value: number;
}

export interface KanbanViewResponse {
  columns: KanbanColumn[];
  total_opportunities: number;
  total_value: number;
}

export interface PipelineStageCreatePayload {
  name: string;
  sequence?: number;
  probability?: number;
  is_won?: boolean;
  is_lost?: boolean;
  color?: string;
}

export interface PipelineStageUpdatePayload {
  name?: string;
  sequence?: number;
  probability?: number;
  is_won?: boolean;
  is_lost?: boolean;
  is_active?: boolean;
  color?: string;
}

// Common response types
export interface SuccessResponse {
  success: boolean;
}

export interface SeedDefaultStagesResponse {
  success: boolean;
  message: string;
}

// =============================================================================
// API
// =============================================================================

export const crmApi = {
  // =========================================================================
  // LEADS
  // =========================================================================

  getLeads: (params?: LeadListParams) =>
    fetchApi<LeadListResponse>('/crm/leads', { params }),

  getLeadsSummary: () =>
    fetchApi<LeadSummaryResponse>('/crm/leads/summary'),

  getLead: (id: number) =>
    fetchApi<Lead>(`/crm/leads/${id}`),

  createLead: (payload: LeadCreatePayload) =>
    fetchApi<Lead>('/crm/leads', { method: 'POST', body: JSON.stringify(payload) }),

  updateLead: (id: number, payload: Partial<LeadCreatePayload>) =>
    fetchApi<Lead>(`/crm/leads/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),

  convertLead: (id: number, payload: LeadConvertPayload) =>
    fetchApi<LeadConvertResponse>(`/crm/leads/${id}/convert`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  qualifyLead: (id: number) =>
    fetchApi<SuccessResponse>(`/crm/leads/${id}/qualify`, { method: 'POST' }),

  disqualifyLead: (id: number, reason?: string) =>
    fetchApi<SuccessResponse>(`/crm/leads/${id}/disqualify`, {
      method: 'POST',
      params: { reason },
    }),

  // =========================================================================
  // OPPORTUNITIES
  // =========================================================================

  getOpportunities: (params?: OpportunityListParams) =>
    fetchApi<OpportunityListResponse>('/crm/opportunities', { params }),

  getPipelineSummary: () =>
    fetchApi<PipelineSummaryResponse>('/crm/opportunities/pipeline'),

  getOpportunity: (id: number) =>
    fetchApi<Opportunity>(`/crm/opportunities/${id}`),

  createOpportunity: (payload: OpportunityCreatePayload) =>
    fetchApi<Opportunity>('/crm/opportunities', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateOpportunity: (id: number, payload: Partial<OpportunityCreatePayload>) =>
    fetchApi<Opportunity>(`/crm/opportunities/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  moveOpportunityStage: (id: number, stageId: number) =>
    fetchApi<SuccessResponse>(`/crm/opportunities/${id}/move-stage`, {
      method: 'POST',
      params: { stage_id: stageId },
    }),

  markOpportunityWon: (id: number) =>
    fetchApi<SuccessResponse>(`/crm/opportunities/${id}/won`, { method: 'POST' }),

  markOpportunityLost: (id: number, reason?: string, competitor?: string) =>
    fetchApi<SuccessResponse>(`/crm/opportunities/${id}/lost`, {
      method: 'POST',
      params: { reason, competitor },
    }),

  // =========================================================================
  // ACTIVITIES
  // =========================================================================

  getActivities: (params?: ActivityListParams) =>
    fetchApi<ActivityListResponse>('/crm/activities', { params }),

  getActivitiesSummary: () =>
    fetchApi<ActivitySummaryResponse>('/crm/activities/summary'),

  getActivityTimeline: (params: ActivityTimelineParams) =>
    fetchApi<ActivityTimelineResponse>('/crm/activities/timeline', { params }),

  getActivity: (id: number) =>
    fetchApi<Activity>(`/crm/activities/${id}`),

  createActivity: (payload: ActivityCreatePayload) =>
    fetchApi<Activity>('/crm/activities', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateActivity: (id: number, payload: Partial<ActivityCreatePayload>) =>
    fetchApi<Activity>(`/crm/activities/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  completeActivity: (id: number, outcome?: string, notes?: string) =>
    fetchApi<SuccessResponse>(`/crm/activities/${id}/complete`, {
      method: 'POST',
      params: { outcome, notes },
    }),

  cancelActivity: (id: number) =>
    fetchApi<SuccessResponse>(`/crm/activities/${id}/cancel`, { method: 'POST' }),

  deleteActivity: (id: number) =>
    fetchApi<SuccessResponse>(`/crm/activities/${id}`, { method: 'DELETE' }),

  // =========================================================================
  // CONTACTS
  // =========================================================================

  getContacts: (params?: ContactListParams) =>
    fetchApi<ContactListResponse>('/crm/contacts', { params }),

  getCustomerContacts: (customerId: number) =>
    fetchApi<ContactsByEntityResponse>(`/crm/contacts/by-customer/${customerId}`),

  getLeadContacts: (leadId: number) =>
    fetchApi<ContactsByEntityResponse>(`/crm/contacts/by-lead/${leadId}`),

  getContact: (id: number) =>
    fetchApi<Contact>(`/crm/contacts/${id}`),

  createContact: (payload: ContactCreatePayload) =>
    fetchApi<Contact>('/crm/contacts', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateContact: (id: number, payload: Partial<ContactCreatePayload>) =>
    fetchApi<Contact>(`/crm/contacts/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  setContactPrimary: (id: number) =>
    fetchApi<SuccessResponse>(`/crm/contacts/${id}/set-primary`, { method: 'POST' }),

  deleteContact: (id: number) =>
    fetchApi<SuccessResponse>(`/crm/contacts/${id}`, { method: 'DELETE' }),

  // =========================================================================
  // PIPELINE
  // =========================================================================

  getPipelineStages: (includeInactive?: boolean) =>
    fetchApi<PipelineStage[]>('/crm/pipeline/stages', {
      params: { include_inactive: includeInactive },
    }),

  getPipelineView: () =>
    fetchApi<PipelineViewResponse>('/crm/pipeline/view'),

  getKanbanView: (ownerId?: number) =>
    fetchApi<KanbanViewResponse>('/crm/pipeline/kanban', {
      params: { owner_id: ownerId },
    }),

  createPipelineStage: (payload: PipelineStageCreatePayload) =>
    fetchApi<PipelineStage>('/crm/pipeline/stages', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updatePipelineStage: (id: number, payload: PipelineStageUpdatePayload) =>
    fetchApi<PipelineStage>(`/crm/pipeline/stages/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  reorderPipelineStages: (stageIds: number[]) =>
    fetchApi<SuccessResponse>('/crm/pipeline/stages/reorder', {
      method: 'POST',
      body: JSON.stringify(stageIds),
    }),

  deletePipelineStage: (id: number) =>
    fetchApi<SuccessResponse>(`/crm/pipeline/stages/${id}`, { method: 'DELETE' }),

  seedDefaultPipelineStages: () =>
    fetchApi<SeedDefaultStagesResponse>('/crm/pipeline/seed-default-stages', {
      method: 'POST',
    }),
};

// =============================================================================
// STANDALONE FUNCTIONS (for backward compatibility)
// =============================================================================

export const getLeads = crmApi.getLeads;
export const getLeadsSummary = crmApi.getLeadsSummary;
export const getLead = crmApi.getLead;
export const createLead = crmApi.createLead;
export const updateLead = crmApi.updateLead;
export const convertLead = crmApi.convertLead;
export const qualifyLead = crmApi.qualifyLead;
export const disqualifyLead = crmApi.disqualifyLead;

export const getOpportunities = crmApi.getOpportunities;
export const getPipelineSummary = crmApi.getPipelineSummary;
export const getOpportunity = crmApi.getOpportunity;
export const createOpportunity = crmApi.createOpportunity;
export const updateOpportunity = crmApi.updateOpportunity;
export const moveOpportunityStage = crmApi.moveOpportunityStage;
export const markOpportunityWon = crmApi.markOpportunityWon;
export const markOpportunityLost = crmApi.markOpportunityLost;

export const getActivities = crmApi.getActivities;
export const getActivitiesSummary = crmApi.getActivitiesSummary;
export const getActivityTimeline = crmApi.getActivityTimeline;
export const getActivity = crmApi.getActivity;
export const createActivity = crmApi.createActivity;
export const updateActivity = crmApi.updateActivity;
export const completeActivity = crmApi.completeActivity;
export const cancelActivity = crmApi.cancelActivity;
export const deleteActivity = crmApi.deleteActivity;

export const getContacts = crmApi.getContacts;
export const getCustomerContacts = crmApi.getCustomerContacts;
export const getLeadContacts = crmApi.getLeadContacts;
export const getContact = crmApi.getContact;
export const createContact = crmApi.createContact;
export const updateContact = crmApi.updateContact;
export const setContactPrimary = crmApi.setContactPrimary;
export const deleteContact = crmApi.deleteContact;

export const getPipelineStages = crmApi.getPipelineStages;
export const getPipelineView = crmApi.getPipelineView;
export const getKanbanView = crmApi.getKanbanView;
export const createPipelineStage = crmApi.createPipelineStage;
export const updatePipelineStage = crmApi.updatePipelineStage;
export const reorderPipelineStages = crmApi.reorderPipelineStages;
export const deletePipelineStage = crmApi.deletePipelineStage;
export const seedDefaultPipelineStages = crmApi.seedDefaultPipelineStages;

export default crmApi;
