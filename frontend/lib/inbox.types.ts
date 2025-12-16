/**
 * Inbox (Omnichannel) TypeScript types
 */

// Enums
export type ConversationStatus = 'open' | 'pending' | 'resolved' | 'archived';
export type ConversationPriority = 'low' | 'medium' | 'high' | 'urgent';
export type MessageDirection = 'inbound' | 'outbound';
export type ChannelType = 'email' | 'chat' | 'whatsapp' | 'phone' | 'sms' | 'social';

// Channel
export interface InboxChannel {
  id: number;
  name: string;
  type: ChannelType;
  is_active: boolean;
  config?: Record<string, unknown>;
  created_at: string;
  updated_at?: string;
}

// Participant
export interface ConversationParticipant {
  id: number;
  name?: string;
  email?: string;
  phone?: string;
  role: 'customer' | 'agent' | 'cc' | 'bcc';
  joined_at: string;
}

// Message
export interface InboxMessage {
  id: number;
  conversation_id: number;
  direction: MessageDirection;
  content: string;
  content_type?: string;
  sender_name?: string;
  sender_email?: string;
  agent_id?: number;
  attachments?: MessageAttachment[];
  meta?: Record<string, unknown>;
  created_at: string;
}

export interface MessageAttachment {
  id: number;
  filename: string;
  mime_type: string;
  size: number;
  url?: string;
}

// Conversation
export interface InboxConversation {
  id: number;
  channel_id: number;
  channel?: InboxChannel;
  subject?: string;
  status: ConversationStatus;
  priority?: ConversationPriority;
  is_starred: boolean;
  unread_count: number;
  tags?: string[];

  // Contact info
  contact_name?: string;
  contact_email?: string;
  contact_phone?: string;

  // Assignment
  assigned_agent_id?: number;
  assigned_agent?: { id: number; display_name?: string; email: string };
  assigned_team_id?: number;
  assigned_team?: { id: number; name: string };
  assigned_at?: string;

  // Linked records
  customer_id?: number;
  ticket_id?: number;
  lead_id?: number;

  // Response metrics
  first_response_at?: string;
  resolved_at?: string;

  // Timestamps
  last_message_at?: string;
  created_at: string;
  updated_at?: string;

  // Preview
  preview?: string;
  last_message?: InboxMessage;
  messages?: InboxMessage[];
  participants?: ConversationParticipant[];
}

// Contact
export interface InboxContact {
  id: number;
  name: string;
  email?: string;
  phone?: string;
  company?: string;
  job_title?: string;
  tags?: string[];
  meta?: Record<string, unknown>;
  customer_id?: number;
  lead_id?: number;
  total_conversations: number;
  last_contact_at?: string;
  created_at: string;
  updated_at?: string;
  recent_conversations?: Array<{
    id: number;
    subject?: string;
    status: string;
    channel_type?: string;
    last_message_at?: string;
  }>;
}

// Routing Rule
export interface RoutingCondition {
  type: 'channel' | 'keyword' | 'tag' | 'priority' | 'contact_company';
  operator: 'contains' | 'equals' | 'starts_with';
  value: string;
}

export interface InboxRoutingRule {
  id: number;
  name: string;
  description?: string;
  conditions: RoutingCondition[];
  action_type: 'assign_agent' | 'assign_team' | 'add_tag' | 'create_ticket' | 'set_priority';
  action_value?: string;
  action_config?: Record<string, unknown>;
  priority: number;
  is_active: boolean;
  match_count: number;
  created_at: string;
  updated_at?: string;
}

// Analytics
export interface InboxAnalyticsSummary {
  period_days: number;
  total_conversations: number;
  open_count: number;
  pending_count: number;
  resolved_today: number;
  total_unread: number;
  unassigned_count: number;
  total_messages: number;
  inbound_messages: number;
  outbound_messages: number;
  avg_first_response_hours?: number;
  by_status: Record<string, number>;
  by_channel: Record<string, number>;
}

export interface InboxVolumeData {
  period_days: number;
  daily_volume: Array<{ date: string; count: number }>;
  channel_by_day: Array<{ date: string; [channel: string]: string | number }>;
}

export interface InboxAgentStats {
  id: number;
  name: string;
  conversations: number;
  messages_sent: number;
  avg_response_time_hours?: number;
}

export interface InboxChannelStats {
  id: number;
  name: string;
  type: string;
  conversation_count: number;
  avg_response_time_hours?: number;
}

// API Request/Response types
export interface ConversationListParams {
  status?: ConversationStatus;
  priority?: ConversationPriority;
  channel_id?: number;
  assigned_agent_id?: number;
  assigned_team_id?: number;
  is_unassigned?: boolean;
  is_starred?: boolean;
  search?: string;
  tag?: string;
  customer_id?: number;
  sort_by?: 'last_message_at' | 'created_at' | 'priority';
  sort_order?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

export interface ConversationListResponse {
  total: number;
  limit: number;
  offset: number;
  data: InboxConversation[];
}

export interface ConversationUpdatePayload {
  status?: ConversationStatus;
  priority?: ConversationPriority;
  is_starred?: boolean;
  tags?: string[];
}

export interface AssignPayload {
  agent_id?: number;
  team_id?: number;
}

export interface SendMessagePayload {
  content: string;
  content_type?: string;
}

export interface CreateTicketPayload {
  subject?: string;
  priority?: string;
  description?: string;
}

export interface CreateLeadPayload {
  name?: string;
  company?: string;
  source?: string;
}

export interface ContactListParams {
  search?: string;
  company?: string;
  tag?: string;
  has_customer?: boolean;
  has_lead?: boolean;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

export interface ContactListResponse {
  total: number;
  limit: number;
  offset: number;
  data: InboxContact[];
}

export interface ContactCreatePayload {
  name: string;
  email?: string;
  phone?: string;
  company?: string;
  job_title?: string;
  tags?: string[];
  customer_id?: number;
  lead_id?: number;
}

export interface ContactUpdatePayload {
  name?: string;
  email?: string;
  phone?: string;
  company?: string;
  job_title?: string;
  tags?: string[];
  customer_id?: number;
  lead_id?: number;
}

export interface RoutingRuleListParams {
  is_active?: boolean;
  action_type?: string;
  limit?: number;
  offset?: number;
}

export interface RoutingRuleListResponse {
  total: number;
  limit: number;
  offset: number;
  data: InboxRoutingRule[];
}

export interface RoutingRuleCreatePayload {
  name: string;
  description?: string;
  conditions: RoutingCondition[];
  action_type: string;
  action_value?: string;
  action_config?: Record<string, unknown>;
  priority?: number;
  is_active?: boolean;
}

export interface RoutingRuleUpdatePayload {
  name?: string;
  description?: string;
  conditions?: RoutingCondition[];
  action_type?: string;
  action_value?: string;
  action_config?: Record<string, unknown>;
  priority?: number;
  is_active?: boolean;
}

export interface CompanyListResponse {
  total: number;
  limit: number;
  offset: number;
  data: Array<{ company: string; contact_count: number }>;
}
