'use client';

import { useState, useEffect } from 'react';
import {
  Settings,
  Clock,
  Users,
  Bell,
  Target,
  MessageSquare,
  BookOpen,
  Zap,
  Globe,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useSupportSettings, useSupportSettingsMutations } from '@/hooks/useApi';
import type {
  SupportSettingsResponse,
  SupportSettingsUpdate,
  WorkingHoursType,
  DefaultRoutingStrategy,
  TicketAutoCloseAction,
  CSATSurveyTrigger,
  TicketPriorityDefault,
  NotificationChannel,
  WeekDay,
  WeeklyScheduleDay,
} from '@/lib/api';

type TabKey = 'hours' | 'routing' | 'autoclose' | 'csat' | 'kb' | 'display';

const tabs: { key: TabKey; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: 'hours', label: 'Business Hours & SLA', icon: Clock },
  { key: 'routing', label: 'Ticket Routing', icon: Users },
  { key: 'autoclose', label: 'Auto-Close & Escalation', icon: Zap },
  { key: 'csat', label: 'CSAT & Portal', icon: MessageSquare },
  { key: 'kb', label: 'Knowledge Base', icon: BookOpen },
  { key: 'display', label: 'Display & Notifications', icon: Bell },
];

// Preset options
const workingHoursOptions: { value: WorkingHoursType; label: string; desc: string }[] = [
  { value: 'STANDARD', label: 'Standard', desc: '9 AM - 5 PM, Mon-Fri' },
  { value: 'EXTENDED', label: 'Extended', desc: '8 AM - 8 PM, Mon-Sat' },
  { value: 'ROUND_THE_CLOCK', label: '24/7', desc: 'Always available' },
  { value: 'CUSTOM', label: 'Custom', desc: 'Set custom schedule' },
];

const routingStrategyOptions: { value: DefaultRoutingStrategy; label: string; desc: string }[] = [
  { value: 'ROUND_ROBIN', label: 'Round Robin', desc: 'Distribute evenly in order' },
  { value: 'LEAST_BUSY', label: 'Least Busy', desc: 'Assign to agent with fewest tickets' },
  { value: 'SKILL_BASED', label: 'Skill-Based', desc: 'Match by agent skills' },
  { value: 'LOAD_BALANCED', label: 'Load Balanced', desc: 'Balance by workload score' },
  { value: 'MANUAL', label: 'Manual', desc: 'No auto-assignment' },
];

const autoCloseActionOptions: { value: TicketAutoCloseAction; label: string }[] = [
  { value: 'CLOSE', label: 'Close ticket' },
  { value: 'ARCHIVE', label: 'Archive ticket' },
  { value: 'NOTIFY_ONLY', label: 'Notify customer only' },
];

const csatTriggerOptions: { value: CSATSurveyTrigger; label: string; desc: string }[] = [
  { value: 'ON_RESOLVE', label: 'On Resolve', desc: 'Send when ticket marked resolved' },
  { value: 'ON_CLOSE', label: 'On Close', desc: 'Send when ticket closed' },
  { value: 'MANUAL', label: 'Manual', desc: 'Agent triggers survey' },
  { value: 'DISABLED', label: 'Disabled', desc: 'No automatic surveys' },
];

const priorityOptions: { value: TicketPriorityDefault; label: string }[] = [
  { value: 'LOW', label: 'Low' },
  { value: 'MEDIUM', label: 'Medium' },
  { value: 'HIGH', label: 'High' },
  { value: 'URGENT', label: 'Urgent' },
];

const notificationChannelOptions: { value: NotificationChannel; label: string }[] = [
  { value: 'EMAIL', label: 'Email' },
  { value: 'IN_APP', label: 'In-App' },
  { value: 'SMS', label: 'SMS' },
  { value: 'SLACK', label: 'Slack' },
  { value: 'WEBHOOK', label: 'Webhook' },
];

const weekDays: WeekDay[] = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY'];

const timezoneOptions = [
  'Africa/Lagos',
  'Africa/Nairobi',
  'Africa/Johannesburg',
  'Africa/Cairo',
  'Europe/London',
  'Europe/Paris',
  'America/New_York',
  'America/Los_Angeles',
  'Asia/Dubai',
  'Asia/Singapore',
  'UTC',
];

const dateFormatOptions = ['YYYY-MM-DD', 'DD/MM/YYYY', 'MM/DD/YYYY', 'DD-MM-YYYY'];
const timeFormatOptions = ['HH:mm', 'hh:mm A', 'HH:mm:ss'];

export default function SupportSettingsPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('hours');
  const { data: settings, isLoading, error } = useSupportSettings();
  const { updateSettings } = useSupportSettingsMutations();
  const [form, setForm] = useState<Partial<SupportSettingsResponse>>({});
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const updateForm = (updater: (prev: Partial<SupportSettingsResponse>) => Partial<SupportSettingsResponse>) =>
    setForm(updater);

  useEffect(() => {
    if (settings) {
      setForm(settings);
    }
  }, [settings]);

  const buildUpdatePayload = (data: Partial<SupportSettingsResponse>): SupportSettingsUpdate => {
    const { id, company, created_at, updated_at, ...rest } = data as any;
    return rest;
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveMessage(null);
    try {
      await updateSettings(buildUpdatePayload(form));
      setSaveMessage('Settings saved successfully');
    } catch (e: any) {
      setSaveMessage(e.message || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-muted">Loading support settings...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-6 text-center">
        <p className="text-rose-400">Failed to load support settings. The settings may not be initialized yet.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-white">Support Settings</h1>
        <p className="text-slate-muted text-sm">Configure helpdesk, SLA, routing, CSAT, and support operations.</p>
      </header>

      {/* Tabs */}
      <div className="border-b border-slate-border overflow-x-auto">
        <nav className="-mb-px flex space-x-1 min-w-max">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={cn(
                  'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap',
                  isActive
                    ? 'border-teal-electric text-teal-electric'
                    : 'border-transparent text-slate-muted hover:text-white hover:border-slate-border'
                )}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="space-y-6">
        {activeTab === 'hours' && <HoursTab form={form} setForm={setForm} updateForm={updateForm} />}
        {activeTab === 'routing' && <RoutingTab form={form} setForm={setForm} updateForm={updateForm} />}
        {activeTab === 'autoclose' && <AutoCloseTab form={form} setForm={setForm} updateForm={updateForm} />}
        {activeTab === 'csat' && <CSATTab form={form} setForm={setForm} updateForm={updateForm} />}
        {activeTab === 'kb' && <KBTab form={form} setForm={setForm} updateForm={updateForm} />}
        {activeTab === 'display' && <DisplayTab form={form} setForm={setForm} updateForm={updateForm} />}
      </div>

      {/* Save Button */}
      <div className="flex items-center justify-end gap-4 pt-4 border-t border-slate-border">
        {saveMessage && (
          <span className={cn('text-sm', saveMessage.includes('success') ? 'text-emerald-400' : 'text-rose-400')}>
            {saveMessage}
          </span>
        )}
        <button
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-2 px-6 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
      </div>
    </div>
  );
}

// Tab Components
interface TabProps {
  form: Partial<SupportSettingsResponse>;
  setForm: React.Dispatch<React.SetStateAction<Partial<SupportSettingsResponse>>>;
  updateForm: (updater: (prev: Partial<SupportSettingsResponse>) => Partial<SupportSettingsResponse>) => void;
}

type WeeklyScheduleEntry = { start: string; end: string; closed?: boolean };

function HoursTab({ form, setForm, updateForm }: TabProps) {
  const updateSchedule = (day: WeekDay, field: keyof WeeklyScheduleEntry, value: string | boolean) => {
    updateForm((p) => {
      const current = (p.weekly_schedule || {}) as Record<WeekDay, WeeklyScheduleEntry>;
      const daySchedule = current[day] || { start: '09:00', end: '17:00', closed: false };
      return {
        ...p,
        weekly_schedule: {
          ...current,
          [day]: {
            ...daySchedule,
            [field]: value,
          },
        } as Record<WeekDay, WeeklyScheduleEntry>,
      };
    });
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card title="Business Hours" icon={Clock}>
        <div className="space-y-4">
          <FormField label="Working Hours Type">
            <select
              value={form.working_hours_type || 'STANDARD'}
              onChange={(e) => updateForm((p) => ({ ...p, working_hours_type: e.target.value as WorkingHoursType }))}
              className="input-field"
            >
              {workingHoursOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label} - {opt.desc}</option>
              ))}
            </select>
          </FormField>
          <FormField label="Timezone">
            <select
              value={form.timezone || 'Africa/Lagos'}
              onChange={(e) => updateForm((p) => ({ ...p, timezone: e.target.value }))}
              className="input-field"
            >
              {timezoneOptions.map((tz) => (
                <option key={tz} value={tz}>{tz}</option>
              ))}
            </select>
          </FormField>
        </div>
      </Card>

      {form.working_hours_type === 'CUSTOM' && (
        <Card title="Weekly Schedule" icon={Clock}>
          <div className="space-y-3">
      {weekDays.map((day) => {
        const schedule = form.weekly_schedule?.[day] || { start: '09:00', end: '17:00', closed: false };
        return (
          <div key={day} className="flex items-center gap-3">
                  <span className="w-16 text-sm text-slate-muted">{day.slice(0, 3)}</span>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={schedule.closed}
                      onChange={(e) => updateSchedule(day, 'closed', e.target.checked)}
                      className="w-4 h-4 rounded border-slate-border bg-slate-elevated text-teal-electric"
                    />
                    <span className="text-xs text-slate-muted">Closed</span>
                  </label>
                  {!schedule.closed && (
                    <>
                      <input
                        type="time"
                        value={schedule.start}
                        onChange={(e) => updateSchedule(day, 'start', e.target.value)}
                        className="input-field w-28 text-sm"
                      />
                      <span className="text-slate-muted">to</span>
                      <input
                        type="time"
                        value={schedule.end}
                        onChange={(e) => updateSchedule(day, 'end', e.target.value)}
                        className="input-field w-28 text-sm"
                      />
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </Card>
      )}

      <Card title="SLA Settings" icon={Target}>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <FormField label="First Response (Hrs)">
              <input
                type="number"
                min={0}
                value={form.default_first_response_hours ?? 4}
                onChange={(e) => updateForm((p) => ({ ...p, default_first_response_hours: Number(e.target.value) }))}
                className="input-field"
              />
            </FormField>
            <FormField label="Resolution (Hrs)">
              <input
                type="number"
                min={0}
                value={form.default_resolution_hours ?? 24}
                onChange={(e) => updateForm((p) => ({ ...p, default_resolution_hours: Number(e.target.value) }))}
                className="input-field"
              />
            </FormField>
          </div>
          <FormField label="Warning Threshold (%)">
            <input
              type="number"
              min={0}
              max={100}
              value={form.sla_warning_threshold_percent ?? 75}
              onChange={(e) => updateForm((p) => ({ ...p, sla_warning_threshold_percent: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
          <div className="space-y-2 pt-2">
            <CheckboxField
              label="Include holidays in SLA calculation"
              checked={form.sla_include_holidays ?? false}
              onChange={(v) => updateForm((p) => ({ ...p, sla_include_holidays: v }))}
            />
            <CheckboxField
              label="Include weekends in SLA calculation"
              checked={form.sla_include_weekends ?? false}
              onChange={(v) => updateForm((p) => ({ ...p, sla_include_weekends: v }))}
            />
          </div>
        </div>
      </Card>
    </div>
  );
}

function RoutingTab({ form, setForm, updateForm }: TabProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card title="Routing Strategy" icon={Users}>
        <div className="space-y-4">
          <FormField label="Default Routing">
            <select
              value={form.default_routing_strategy || 'ROUND_ROBIN'}
              onChange={(e) => updateForm((p) => ({ ...p, default_routing_strategy: e.target.value as DefaultRoutingStrategy }))}
              className="input-field"
            >
              {routingStrategyOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label} - {opt.desc}</option>
              ))}
            </select>
          </FormField>
          <div className="space-y-2 pt-2">
            <CheckboxField
              label="Enable auto-assignment"
              checked={form.auto_assign_enabled ?? true}
              onChange={(v) => updateForm((p) => ({ ...p, auto_assign_enabled: v }))}
            />
          </div>
          {form.auto_assign_enabled && (
            <div className="grid grid-cols-2 gap-4">
              <FormField label="Max Tickets Per Agent">
                <input
                  type="number"
                  min={1}
                  value={form.max_tickets_per_agent ?? 50}
                  onChange={(e) => updateForm((p) => ({ ...p, max_tickets_per_agent: Number(e.target.value) }))}
                  className="input-field"
                />
              </FormField>
              <FormField label="Rebalance Threshold (%)">
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={form.rebalance_threshold_percent ?? 20}
                  onChange={(e) => updateForm((p) => ({ ...p, rebalance_threshold_percent: Number(e.target.value) }))}
                  className="input-field"
                />
              </FormField>
            </div>
          )}
        </div>
      </Card>

      <Card title="Default Priority & Type" icon={Target}>
        <div className="space-y-4">
          <FormField label="Default Priority">
            <select
              value={form.default_priority || 'MEDIUM'}
              onChange={(e) => updateForm((p) => ({ ...p, default_priority: e.target.value as TicketPriorityDefault }))}
              className="input-field"
            >
              {priorityOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </FormField>
          <FormField label="Default Ticket Type">
            <input
              type="text"
              value={form.default_ticket_type ?? ''}
              onChange={(e) => updateForm((p) => ({ ...p, default_ticket_type: e.target.value || null }))}
              placeholder="e.g., Support, Question"
              className="input-field"
            />
          </FormField>
          <div className="space-y-2 pt-2">
            <CheckboxField
              label="Allow customer to select priority"
              checked={form.allow_customer_priority_selection ?? false}
              onChange={(v) => updateForm((p) => ({ ...p, allow_customer_priority_selection: v }))}
            />
            <CheckboxField
              label="Allow customer to select team"
              checked={form.allow_customer_team_selection ?? false}
              onChange={(v) => updateForm((p) => ({ ...p, allow_customer_team_selection: v }))}
            />
          </div>
        </div>
      </Card>
    </div>
  );
}

function AutoCloseTab({ form, setForm, updateForm }: TabProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card title="Auto-Close Settings" icon={Zap}>
        <div className="space-y-4">
          <CheckboxField
            label="Enable auto-close"
            checked={form.auto_close_enabled ?? true}
            onChange={(v) => updateForm((p) => ({ ...p, auto_close_enabled: v }))}
          />
          {form.auto_close_enabled && (
            <>
              <FormField label="Close resolved tickets after (days)">
                <input
                  type="number"
                  min={1}
                  value={form.auto_close_resolved_days ?? 7}
                  onChange={(e) => updateForm((p) => ({ ...p, auto_close_resolved_days: Number(e.target.value) }))}
                  className="input-field"
                />
              </FormField>
              <FormField label="Action on auto-close">
                <select
                  value={form.auto_close_action || 'CLOSE'}
                  onChange={(e) => updateForm((p) => ({ ...p, auto_close_action: e.target.value as TicketAutoCloseAction }))}
                  className="input-field"
                >
                  {autoCloseActionOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </FormField>
              <CheckboxField
                label="Notify customer on auto-close"
                checked={form.auto_close_notify_customer ?? true}
                onChange={(v) => updateForm((p) => ({ ...p, auto_close_notify_customer: v }))}
              />
            </>
          )}
        </div>
      </Card>

      <Card title="Reopen Settings" icon={Zap}>
        <div className="space-y-4">
          <CheckboxField
            label="Allow customer to reopen tickets"
            checked={form.allow_customer_reopen ?? true}
            onChange={(v) => updateForm((p) => ({ ...p, allow_customer_reopen: v }))}
          />
          {form.allow_customer_reopen && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <FormField label="Reopen Window (Days)">
                  <input
                    type="number"
                    min={1}
                    value={form.reopen_window_days ?? 14}
                    onChange={(e) => updateForm((p) => ({ ...p, reopen_window_days: Number(e.target.value) }))}
                    className="input-field"
                  />
                </FormField>
                <FormField label="Max Reopens Allowed">
                  <input
                    type="number"
                    min={1}
                    value={form.max_reopens_allowed ?? 3}
                    onChange={(e) => updateForm((p) => ({ ...p, max_reopens_allowed: Number(e.target.value) }))}
                    className="input-field"
                  />
                </FormField>
              </div>
            </>
          )}
        </div>
      </Card>

      <Card title="Escalation Settings" icon={Zap}>
        <div className="space-y-4">
          <CheckboxField
            label="Enable escalation"
            checked={form.escalation_enabled ?? true}
            onChange={(v) => updateForm((p) => ({ ...p, escalation_enabled: v }))}
          />
          {form.escalation_enabled && (
            <>
              <CheckboxField
                label="Notify manager on escalation"
                checked={form.escalation_notify_manager ?? true}
                onChange={(v) => updateForm((p) => ({ ...p, escalation_notify_manager: v }))}
              />
              <CheckboxField
                label="Escalate on idle time"
                checked={form.idle_escalation_enabled ?? true}
                onChange={(v) => updateForm((p) => ({ ...p, idle_escalation_enabled: v }))}
              />
              {form.idle_escalation_enabled && (
                <FormField label="Idle hours before escalation">
                  <input
                    type="number"
                    min={1}
                    value={form.idle_hours_before_escalation ?? 24}
                    onChange={(e) => updateForm((p) => ({ ...p, idle_hours_before_escalation: Number(e.target.value) }))}
                    className="input-field"
                  />
                </FormField>
              )}
              <CheckboxField
                label="Escalate on multiple reopens"
                checked={form.reopen_escalation_enabled ?? true}
                onChange={(v) => updateForm((p) => ({ ...p, reopen_escalation_enabled: v }))}
              />
              {form.reopen_escalation_enabled && (
                <FormField label="Reopen count for escalation">
                  <input
                    type="number"
                    min={1}
                    value={form.reopen_count_for_escalation ?? 2}
                    onChange={(e) => updateForm((p) => ({ ...p, reopen_count_for_escalation: Number(e.target.value) }))}
                    className="input-field"
                  />
                </FormField>
              )}
            </>
          )}
        </div>
      </Card>

      <Card title="Data Retention" icon={Settings}>
        <div className="space-y-4">
          <FormField label="Archive closed tickets after (days)">
            <input
              type="number"
              min={0}
              value={form.archive_closed_tickets_days ?? 90}
              onChange={(e) => updateForm((p) => ({ ...p, archive_closed_tickets_days: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
          <FormField label="Delete archived tickets after (days)">
            <input
              type="number"
              min={0}
              value={form.delete_archived_tickets_days ?? 365}
              onChange={(e) => updateForm((p) => ({ ...p, delete_archived_tickets_days: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
          <p className="text-xs text-slate-muted">Set to 0 to disable archiving/deletion.</p>
        </div>
      </Card>
    </div>
  );
}

function CSATTab({ form, setForm, updateForm }: TabProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card title="CSAT Survey Settings" icon={MessageSquare}>
        <div className="space-y-4">
          <CheckboxField
            label="Enable CSAT surveys"
            checked={form.csat_enabled ?? true}
            onChange={(v) => updateForm((p) => ({ ...p, csat_enabled: v }))}
          />
          {form.csat_enabled && (
            <>
              <FormField label="Survey Trigger">
                <select
                  value={form.csat_survey_trigger || 'ON_RESOLVE'}
                  onChange={(e) => updateForm((p) => ({ ...p, csat_survey_trigger: e.target.value as CSATSurveyTrigger }))}
                  className="input-field"
                >
                  {csatTriggerOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label} - {opt.desc}</option>
                  ))}
                </select>
              </FormField>
              <FormField label="Delay before sending (hours)">
                <input
                  type="number"
                  min={0}
                  value={form.csat_delay_hours ?? 1}
                  onChange={(e) => updateForm((p) => ({ ...p, csat_delay_hours: Number(e.target.value) }))}
                  className="input-field"
                />
              </FormField>
              <CheckboxField
                label="Enable reminder"
                checked={form.csat_reminder_enabled ?? true}
                onChange={(v) => updateForm((p) => ({ ...p, csat_reminder_enabled: v }))}
              />
              {form.csat_reminder_enabled && (
                <FormField label="Reminder after (days)">
                  <input
                    type="number"
                    min={1}
                    value={form.csat_reminder_days ?? 3}
                    onChange={(e) => updateForm((p) => ({ ...p, csat_reminder_days: Number(e.target.value) }))}
                    className="input-field"
                  />
                </FormField>
              )}
              <FormField label="Survey expiry (days)">
                <input
                  type="number"
                  min={1}
                  value={form.csat_survey_expiry_days ?? 14}
                  onChange={(e) => updateForm((p) => ({ ...p, csat_survey_expiry_days: Number(e.target.value) }))}
                  className="input-field"
                />
              </FormField>
            </>
          )}
        </div>
      </Card>

      <Card title="Customer Portal" icon={Globe}>
        <div className="space-y-4">
          <CheckboxField
            label="Enable customer portal"
            checked={form.portal_enabled ?? true}
            onChange={(v) => updateForm((p) => ({ ...p, portal_enabled: v }))}
          />
          {form.portal_enabled && (
            <>
              <CheckboxField
                label="Allow ticket creation via portal"
                checked={form.portal_ticket_creation_enabled ?? true}
                onChange={(v) => updateForm((p) => ({ ...p, portal_ticket_creation_enabled: v }))}
              />
              <CheckboxField
                label="Show ticket history"
                checked={form.portal_show_ticket_history ?? true}
                onChange={(v) => updateForm((p) => ({ ...p, portal_show_ticket_history: v }))}
              />
              <CheckboxField
                label="Show knowledge base"
                checked={form.portal_show_knowledge_base ?? true}
                onChange={(v) => updateForm((p) => ({ ...p, portal_show_knowledge_base: v }))}
              />
              <CheckboxField
                label="Show FAQ"
                checked={form.portal_show_faq ?? true}
                onChange={(v) => updateForm((p) => ({ ...p, portal_show_faq: v }))}
              />
              <CheckboxField
                label="Require login"
                checked={form.portal_require_login ?? true}
                onChange={(v) => updateForm((p) => ({ ...p, portal_require_login: v }))}
              />
            </>
          )}
        </div>
      </Card>
    </div>
  );
}

function KBTab({ form, setForm, updateForm }: TabProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card title="Knowledge Base Settings" icon={BookOpen}>
        <div className="space-y-4">
          <CheckboxField
            label="Enable knowledge base"
            checked={form.kb_enabled ?? true}
            onChange={(v) => updateForm((p) => ({ ...p, kb_enabled: v }))}
          />
          {form.kb_enabled && (
            <>
              <CheckboxField
                label="Public access (no login required)"
                checked={form.kb_public_access ?? true}
                onChange={(v) => updateForm((p) => ({ ...p, kb_public_access: v }))}
              />
              <CheckboxField
                label="Suggest articles when creating ticket"
                checked={form.kb_suggest_articles_on_create ?? true}
                onChange={(v) => updateForm((p) => ({ ...p, kb_suggest_articles_on_create: v }))}
              />
              <CheckboxField
                label="Track article helpfulness (thumbs up/down)"
                checked={form.kb_track_article_helpfulness ?? true}
                onChange={(v) => updateForm((p) => ({ ...p, kb_track_article_helpfulness: v }))}
              />
            </>
          )}
        </div>
      </Card>
    </div>
  );
}

function DisplayTab({ form, setForm, updateForm }: TabProps) {
  const toggleChannel = (channel: NotificationChannel) => {
    const current = form.notification_channels || ['EMAIL', 'IN_APP'];
    const isSelected = current.includes(channel);
    updateForm((p) => ({
      ...p,
      notification_channels: isSelected
        ? current.filter((c) => c !== channel)
        : [...current, channel],
    }));
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card title="Ticket ID Format" icon={Settings}>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <FormField label="Prefix">
              <input
                type="text"
                value={form.ticket_id_prefix ?? 'TKT'}
                onChange={(e) => updateForm((p) => ({ ...p, ticket_id_prefix: e.target.value.toUpperCase() }))}
                className="input-field"
                maxLength={10}
              />
            </FormField>
            <FormField label="Min Digits">
              <input
                type="number"
                min={2}
                max={10}
                value={form.ticket_id_min_digits ?? 5}
                onChange={(e) => updateForm((p) => ({ ...p, ticket_id_min_digits: Number(e.target.value) }))}
                className="input-field"
              />
            </FormField>
          </div>
          <div className="p-3 bg-slate-elevated rounded-lg">
            <span className="text-slate-muted text-xs">Preview: </span>
            <span className="text-teal-electric font-mono">
              {form.ticket_id_prefix || 'TKT'}-{'0'.repeat((form.ticket_id_min_digits ?? 5) - 1)}1
            </span>
          </div>
        </div>
      </Card>

      <Card title="Date & Time Format" icon={Clock}>
        <div className="space-y-4">
          <FormField label="Date Format">
            <select
              value={form.date_format || 'YYYY-MM-DD'}
              onChange={(e) => updateForm((p) => ({ ...p, date_format: e.target.value }))}
              className="input-field"
            >
              {dateFormatOptions.map((f) => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>
          </FormField>
          <FormField label="Time Format">
            <select
              value={form.time_format || 'HH:mm'}
              onChange={(e) => updateForm((p) => ({ ...p, time_format: e.target.value }))}
              className="input-field"
            >
              {timeFormatOptions.map((f) => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>
          </FormField>
        </div>
      </Card>

      <Card title="Notification Channels" icon={Bell}>
        <div className="space-y-4">
          <FormField label="Enabled Channels">
            <div className="flex flex-wrap gap-2">
              {notificationChannelOptions.map((opt) => {
                const isSelected = (form.notification_channels || ['EMAIL', 'IN_APP']).includes(opt.value);
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => toggleChannel(opt.value)}
                    className={cn(
                      'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                      isSelected
                        ? 'bg-teal-electric/20 text-teal-electric border border-teal-electric/40'
                        : 'bg-slate-elevated text-slate-muted border border-slate-border'
                    )}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </FormField>
          <div className="space-y-2 pt-2">
            <CheckboxField
              label="Notify assigned agent"
              checked={form.notify_assigned_agent ?? true}
              onChange={(v) => updateForm((p) => ({ ...p, notify_assigned_agent: v }))}
            />
            <CheckboxField
              label="Notify team on unassigned tickets"
              checked={form.notify_team_on_unassigned ?? true}
              onChange={(v) => updateForm((p) => ({ ...p, notify_team_on_unassigned: v }))}
            />
            <CheckboxField
              label="Notify customer on status change"
              checked={form.notify_customer_on_status_change ?? true}
              onChange={(v) => updateForm((p) => ({ ...p, notify_customer_on_status_change: v }))}
            />
            <CheckboxField
              label="Notify customer on reply"
              checked={form.notify_customer_on_reply ?? true}
              onChange={(v) => updateForm((p) => ({ ...p, notify_customer_on_reply: v }))}
            />
          </div>
        </div>
      </Card>

      <Card title="Queue Display" icon={Settings}>
        <div className="space-y-4">
          <FormField label="Unassigned warning (minutes)">
            <input
              type="number"
              min={0}
              value={form.unassigned_warning_minutes ?? 30}
              onChange={(e) => updateForm((p) => ({ ...p, unassigned_warning_minutes: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
          <FormField label="Queue refresh interval (seconds)">
            <input
              type="number"
              min={5}
              value={form.queue_refresh_seconds ?? 30}
              onChange={(e) => updateForm((p) => ({ ...p, queue_refresh_seconds: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
          <CheckboxField
            label="Highlight overdue tickets"
            checked={form.overdue_highlight_enabled ?? true}
            onChange={(v) => updateForm((p) => ({ ...p, overdue_highlight_enabled: v }))}
          />
        </div>
      </Card>

      <Card title="Email Integration" icon={Bell}>
        <div className="space-y-4">
          <CheckboxField
            label="Enable email-to-ticket"
            checked={form.email_to_ticket_enabled ?? true}
            onChange={(v) => updateForm((p) => ({ ...p, email_to_ticket_enabled: v }))}
          />
          {form.email_to_ticket_enabled && (
            <FormField label="Reply-to address">
              <input
                type="email"
                value={form.email_reply_to_address ?? ''}
                onChange={(e) => updateForm((p) => ({ ...p, email_reply_to_address: e.target.value || null }))}
                placeholder="support@company.com"
                className="input-field"
              />
            </FormField>
          )}
        </div>
      </Card>

      <Card title="External Integrations" icon={Globe}>
        <div className="space-y-4">
          <CheckboxField
            label="Sync to ERPNext"
            checked={form.sync_to_erpnext ?? false}
            onChange={(v) => updateForm((p) => ({ ...p, sync_to_erpnext: v }))}
          />
          <CheckboxField
            label="Sync to Splynx"
            checked={form.sync_to_splynx ?? false}
            onChange={(v) => updateForm((p) => ({ ...p, sync_to_splynx: v }))}
          />
          <CheckboxField
            label="Sync to Chatwoot"
            checked={form.sync_to_chatwoot ?? false}
            onChange={(v) => updateForm((p) => ({ ...p, sync_to_chatwoot: v }))}
          />
        </div>
      </Card>
    </div>
  );
}

// Shared Components
function Card({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-4">
      <div className="flex items-center gap-2">
        <Icon className="w-4 h-4 text-teal-electric" />
        <h2 className="text-white font-semibold text-sm">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="block text-sm text-slate-muted">{label}</label>
      {children}
    </div>
  );
}

function CheckboxField({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 cursor-pointer">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="w-4 h-4 rounded border-slate-border bg-slate-elevated text-teal-electric focus:ring-teal-electric/50"
      />
      <span className="text-slate-200 text-sm">{label}</span>
    </label>
  );
}
