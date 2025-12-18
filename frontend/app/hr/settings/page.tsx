'use client';

import { useState, useEffect } from 'react';
import {
  Settings,
  Calendar,
  Clock,
  Wallet,
  Users,
  Target,
  Bell,
  Briefcase,
  Check,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useHRSettings, useHRSettingsMutations } from '@/hooks/useApi';
import type {
  HRSettingsResponse,
  HRSettingsUpdate,
  LeaveAccountingFrequency,
  ProRataMethod,
  PayrollFrequency,
  OvertimeCalculation,
  GratuityCalculation,
  AttendanceMarkingMode,
  AppraisalFrequency,
  EmployeeIDFormat,
  WeekDay,
} from '@/lib/api';

type TabKey = 'leave' | 'attendance' | 'payroll' | 'lifecycle' | 'performance' | 'display';

const tabs: { key: TabKey; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: 'leave', label: 'Leave Policy', icon: Calendar },
  { key: 'attendance', label: 'Attendance & Shifts', icon: Clock },
  { key: 'payroll', label: 'Payroll & Benefits', icon: Wallet },
  { key: 'lifecycle', label: 'Lifecycle & Recruitment', icon: Users },
  { key: 'performance', label: 'Performance & Training', icon: Target },
  { key: 'display', label: 'Display & Notifications', icon: Bell },
];

// Preset options
const leaveAccountingOptions: { value: LeaveAccountingFrequency; label: string; desc: string }[] = [
  { value: 'ANNUAL', label: 'Annual', desc: 'Full allocation at year start' },
  { value: 'MONTHLY', label: 'Monthly', desc: 'Monthly accrual' },
  { value: 'QUARTERLY', label: 'Quarterly', desc: 'Quarterly accrual' },
  { value: 'BIANNUAL', label: 'Biannual', desc: 'Twice yearly' },
];

const proRataOptions: { value: ProRataMethod; label: string }[] = [
  { value: 'LINEAR', label: 'Linear (Simple proportional)' },
  { value: 'CALENDAR_DAYS', label: 'Calendar Days' },
  { value: 'WORKING_DAYS', label: 'Working Days' },
  { value: 'MONTHLY', label: 'Full Month Allocation' },
];

const attendanceModeOptions: { value: AttendanceMarkingMode; label: string; desc: string }[] = [
  { value: 'MANUAL', label: 'Manual', desc: 'Manual entry only' },
  { value: 'BIOMETRIC', label: 'Biometric', desc: 'Fingerprint/face devices' },
  { value: 'GEOLOCATION', label: 'Geolocation', desc: 'GPS-based check-in' },
  { value: 'HYBRID', label: 'Hybrid', desc: 'Multiple methods allowed' },
];

const payrollFrequencyOptions: { value: PayrollFrequency; label: string }[] = [
  { value: 'WEEKLY', label: 'Weekly' },
  { value: 'BIWEEKLY', label: 'Biweekly' },
  { value: 'MONTHLY', label: 'Monthly' },
  { value: 'SEMIMONTHLY', label: 'Semimonthly (1st and 15th)' },
];

const overtimeCalcOptions: { value: OvertimeCalculation; label: string }[] = [
  { value: 'HOURLY_RATE', label: 'Hourly Rate' },
  { value: 'DAILY_RATE', label: 'Daily Rate' },
  { value: 'MONTHLY_RATE', label: 'Monthly Salary' },
];

const gratuityCalcOptions: { value: GratuityCalculation; label: string }[] = [
  { value: 'LAST_SALARY', label: 'Last Drawn Salary' },
  { value: 'AVERAGE_SALARY', label: 'Average Salary' },
  { value: 'BASIC_SALARY', label: 'Basic Salary Only' },
];

const appraisalFrequencyOptions: { value: AppraisalFrequency; label: string }[] = [
  { value: 'ANNUAL', label: 'Annual' },
  { value: 'SEMIANNUAL', label: 'Semi-Annual' },
  { value: 'QUARTERLY', label: 'Quarterly' },
  { value: 'MONTHLY', label: 'Monthly' },
];

const employeeIdFormatOptions: { value: EmployeeIDFormat; label: string; example: string }[] = [
  { value: 'NUMERIC', label: 'Numeric', example: 'EMP001' },
  { value: 'ALPHANUMERIC', label: 'Alphanumeric', example: 'EMP-A001' },
  { value: 'YEAR_BASED', label: 'Year-Based', example: 'EMP-2024-001' },
  { value: 'DEPARTMENT_BASED', label: 'Department-Based', example: 'IT-001' },
];

const weekDays: WeekDay[] = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY'];

const currencyOptions = ['NGN', 'USD', 'EUR', 'GBP', 'KES', 'GHS', 'ZAR'];

export default function HRSettingsPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('leave');
  const { data: settings, isLoading, error } = useHRSettings();
  const { updateSettings } = useHRSettingsMutations();
  const [form, setForm] = useState<Partial<HRSettingsResponse>>({});
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const updateForm = (updater: (prev: Partial<HRSettingsResponse>) => Partial<HRSettingsResponse>) =>
    setForm(updater);

  useEffect(() => {
    if (settings) {
      setForm(settings);
    }
  }, [settings]);

  const buildUpdatePayload = (data: Partial<HRSettingsResponse>): HRSettingsUpdate => {
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
        <div className="text-slate-muted">Loading HR settings...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-6 text-center">
        <p className="text-rose-400">Failed to load HR settings. The settings may not be initialized yet.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-white">HR Settings</h1>
        <p className="text-slate-muted text-sm">Configure leave policies, payroll, attendance, and HR operations.</p>
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
        {activeTab === 'leave' && <LeaveTab form={form} setForm={setForm} updateForm={updateForm} />}
        {activeTab === 'attendance' && <AttendanceTab form={form} setForm={setForm} updateForm={updateForm} />}
        {activeTab === 'payroll' && <PayrollTab form={form} setForm={setForm} updateForm={updateForm} />}
        {activeTab === 'lifecycle' && <LifecycleTab form={form} setForm={setForm} updateForm={updateForm} />}
        {activeTab === 'performance' && <PerformanceTab form={form} setForm={setForm} updateForm={updateForm} />}
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
  form: Partial<HRSettingsResponse>;
  setForm: React.Dispatch<React.SetStateAction<Partial<HRSettingsResponse>>>;
  updateForm: (updater: (prev: Partial<HRSettingsResponse>) => Partial<HRSettingsResponse>) => void;
}

function LeaveTab({ form, updateForm }: TabProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card title="Leave Accounting" icon={Calendar}>
        <div className="space-y-4">
          <FormField label="Accounting Frequency">
            <select
              value={form.leave_accounting_frequency || 'ANNUAL'}
              onChange={(e) => updateForm((p) => ({ ...p, leave_accounting_frequency: e.target.value as LeaveAccountingFrequency }))}
              className="input-field"
            >
              {leaveAccountingOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label} - {opt.desc}</option>
              ))}
            </select>
          </FormField>
          <FormField label="Pro-Rata Method">
            <select
              value={form.pro_rata_method || 'WORKING_DAYS'}
              onChange={(e) => updateForm((p) => ({ ...p, pro_rata_method: e.target.value as ProRataMethod }))}
              className="input-field"
            >
              {proRataOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </FormField>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="Max Carryforward Days">
              <input
                type="number"
                min={0}
                value={form.max_carryforward_days ?? 5}
                onChange={(e) => updateForm((p) => ({ ...p, max_carryforward_days: Number(e.target.value) }))}
                className="input-field"
              />
            </FormField>
            <FormField label="Carryforward Expiry (Months)">
              <input
                type="number"
                min={0}
                value={form.carryforward_expiry_months ?? 3}
                onChange={(e) => updateForm((p) => ({ ...p, carryforward_expiry_months: Number(e.target.value) }))}
                className="input-field"
              />
            </FormField>
          </div>
        </div>
      </Card>

      <Card title="Leave Rules" icon={Settings}>
        <div className="space-y-4">
          <FormField label="Min Leave Notice (Days)">
            <input
              type="number"
              min={0}
              value={form.min_leave_notice_days ?? 1}
              onChange={(e) => updateForm((p) => ({ ...p, min_leave_notice_days: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
          <FormField label="Sick Leave Auto-Approve (Days)">
            <input
              type="number"
              min={0}
              value={form.sick_leave_auto_approve_days ?? 2}
              onChange={(e) => updateForm((p) => ({ ...p, sick_leave_auto_approve_days: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
          <FormField label="Medical Certificate After (Days)">
            <input
              type="number"
              min={0}
              value={form.medical_certificate_required_after_days ?? 2}
              onChange={(e) => updateForm((p) => ({ ...p, medical_certificate_required_after_days: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
          <div className="space-y-2 pt-2">
            <CheckboxField
              label="Allow negative leave balance"
              checked={form.allow_negative_leave_balance ?? false}
              onChange={(v) => updateForm((p) => ({ ...p, allow_negative_leave_balance: v }))}
            />
            <CheckboxField
              label="Allow leave overlap"
              checked={form.allow_leave_overlap ?? false}
              onChange={(v) => updateForm((p) => ({ ...p, allow_leave_overlap: v }))}
            />
          </div>
        </div>
      </Card>
    </div>
  );
}

function AttendanceTab({ form, updateForm }: TabProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card title="Attendance Mode" icon={Clock}>
        <div className="space-y-4">
          <FormField label="Marking Mode">
            <select
              value={form.attendance_marking_mode || 'MANUAL'}
              onChange={(e) => updateForm((p) => ({ ...p, attendance_marking_mode: e.target.value as AttendanceMarkingMode }))}
              className="input-field"
            >
              {attendanceModeOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label} - {opt.desc}</option>
              ))}
            </select>
          </FormField>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="Late Entry Grace (Min)">
              <input
                type="number"
                min={0}
                value={form.late_entry_grace_minutes ?? 15}
                onChange={(e) => updateForm((p) => ({ ...p, late_entry_grace_minutes: Number(e.target.value) }))}
                className="input-field"
              />
            </FormField>
            <FormField label="Early Exit Grace (Min)">
              <input
                type="number"
                min={0}
                value={form.early_exit_grace_minutes ?? 15}
                onChange={(e) => updateForm((p) => ({ ...p, early_exit_grace_minutes: Number(e.target.value) }))}
                className="input-field"
              />
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="Half Day Threshold (Hrs)">
              <input
                type="number"
                min={0}
                step={0.5}
                value={form.half_day_hours_threshold ?? 4}
                onChange={(e) => updateForm((p) => ({ ...p, half_day_hours_threshold: Number(e.target.value) }))}
                className="input-field"
              />
            </FormField>
            <FormField label="Full Day Threshold (Hrs)">
              <input
                type="number"
                min={0}
                step={0.5}
                value={form.full_day_hours_threshold ?? 8}
                onChange={(e) => updateForm((p) => ({ ...p, full_day_hours_threshold: Number(e.target.value) }))}
                className="input-field"
              />
            </FormField>
          </div>
          <div className="space-y-2 pt-2">
            <CheckboxField
              label="Require checkout"
              checked={form.require_checkout ?? true}
              onChange={(v) => updateForm((p) => ({ ...p, require_checkout: v }))}
            />
            <CheckboxField
              label="Auto-mark absent"
              checked={form.auto_mark_absent_enabled ?? true}
              onChange={(v) => updateForm((p) => ({ ...p, auto_mark_absent_enabled: v }))}
            />
            <CheckboxField
              label="Allow backdated attendance"
              checked={form.allow_backdated_attendance ?? false}
              onChange={(v) => updateForm((p) => ({ ...p, allow_backdated_attendance: v }))}
            />
          </div>
        </div>
      </Card>

      <Card title="Shift & Geolocation" icon={Briefcase}>
        <div className="space-y-4">
          <FormField label="Max Weekly Hours">
            <input
              type="number"
              min={0}
              value={form.max_weekly_hours ?? 48}
              onChange={(e) => updateForm((p) => ({ ...p, max_weekly_hours: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
          <FormField label="Night Shift Allowance (%)">
            <input
              type="number"
              min={0}
              step={0.5}
              value={form.night_shift_allowance_percent ?? 10}
              onChange={(e) => updateForm((p) => ({ ...p, night_shift_allowance_percent: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
          <FormField label="Shift Change Notice (Days)">
            <input
              type="number"
              min={0}
              value={form.shift_change_notice_days ?? 3}
              onChange={(e) => updateForm((p) => ({ ...p, shift_change_notice_days: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
          <div className="space-y-2 pt-2">
            <CheckboxField
              label="Require geolocation check-in"
              checked={form.geolocation_required ?? false}
              onChange={(v) => updateForm((p) => ({ ...p, geolocation_required: v }))}
            />
          </div>
          {form.geolocation_required && (
            <FormField label="Geolocation Radius (Meters)">
              <input
                type="number"
                min={10}
                value={form.geolocation_radius_meters ?? 100}
                onChange={(e) => updateForm((p) => ({ ...p, geolocation_radius_meters: Number(e.target.value) }))}
                className="input-field"
              />
            </FormField>
          )}
        </div>
      </Card>
    </div>
  );
}

function PayrollTab({ form, updateForm }: TabProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card title="Payroll Settings" icon={Wallet}>
        <div className="space-y-4">
          <FormField label="Payroll Frequency">
            <select
              value={form.payroll_frequency || 'MONTHLY'}
              onChange={(e) => updateForm((p) => ({ ...p, payroll_frequency: e.target.value as PayrollFrequency }))}
              className="input-field"
            >
              {payrollFrequencyOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </FormField>
          <FormField label="Salary Currency">
            <select
              value={form.salary_currency || 'NGN'}
              onChange={(e) => updateForm((p) => ({ ...p, salary_currency: e.target.value }))}
              className="input-field"
            >
              {currencyOptions.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </FormField>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="Payment Day">
              <input
                type="number"
                min={0}
                max={31}
                value={form.salary_payment_day ?? 28}
                onChange={(e) => updateForm((p) => ({ ...p, salary_payment_day: Number(e.target.value) }))}
                className="input-field"
              />
            </FormField>
            <FormField label="Cutoff Day">
              <input
                type="number"
                min={1}
                max={31}
                value={form.payroll_cutoff_day ?? 25}
                onChange={(e) => updateForm((p) => ({ ...p, payroll_cutoff_day: Number(e.target.value) }))}
                className="input-field"
              />
            </FormField>
          </div>
          <div className="space-y-2 pt-2">
            <CheckboxField
              label="Allow salary advance"
              checked={form.allow_salary_advance ?? true}
              onChange={(v) => updateForm((p) => ({ ...p, allow_salary_advance: v }))}
            />
          </div>
          {form.allow_salary_advance && (
            <div className="grid grid-cols-2 gap-4">
              <FormField label="Max Advance (%)">
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={form.max_advance_percent ?? 50}
                  onChange={(e) => updateForm((p) => ({ ...p, max_advance_percent: Number(e.target.value) }))}
                  className="input-field"
                />
              </FormField>
              <FormField label="Max Advance Months">
                <input
                  type="number"
                  min={1}
                  value={form.max_advance_months ?? 2}
                  onChange={(e) => updateForm((p) => ({ ...p, max_advance_months: Number(e.target.value) }))}
                  className="input-field"
                />
              </FormField>
            </div>
          )}
        </div>
      </Card>

      <Card title="Overtime" icon={Clock}>
        <div className="space-y-4">
          <CheckboxField
            label="Enable overtime"
            checked={form.overtime_enabled ?? true}
            onChange={(v) => updateForm((p) => ({ ...p, overtime_enabled: v }))}
          />
          {form.overtime_enabled && (
            <>
              <FormField label="Calculation Method">
                <select
                  value={form.overtime_calculation || 'HOURLY_RATE'}
                  onChange={(e) => updateForm((p) => ({ ...p, overtime_calculation: e.target.value as OvertimeCalculation }))}
                  className="input-field"
                >
                  {overtimeCalcOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </FormField>
              <div className="grid grid-cols-3 gap-3">
                <FormField label="Weekday (x)">
                  <input
                    type="number"
                    min={1}
                    step={0.25}
                    value={form.overtime_multiplier_weekday ?? 1.5}
                    onChange={(e) => updateForm((p) => ({ ...p, overtime_multiplier_weekday: Number(e.target.value) }))}
                    className="input-field"
                  />
                </FormField>
                <FormField label="Weekend (x)">
                  <input
                    type="number"
                    min={1}
                    step={0.25}
                    value={form.overtime_multiplier_weekend ?? 2}
                    onChange={(e) => updateForm((p) => ({ ...p, overtime_multiplier_weekend: Number(e.target.value) }))}
                    className="input-field"
                  />
                </FormField>
                <FormField label="Holiday (x)">
                  <input
                    type="number"
                    min={1}
                    step={0.25}
                    value={form.overtime_multiplier_holiday ?? 2.5}
                    onChange={(e) => updateForm((p) => ({ ...p, overtime_multiplier_holiday: Number(e.target.value) }))}
                    className="input-field"
                  />
                </FormField>
              </div>
              <CheckboxField
                label="Require overtime approval"
                checked={form.require_overtime_approval ?? true}
                onChange={(v) => updateForm((p) => ({ ...p, require_overtime_approval: v }))}
              />
            </>
          )}
        </div>
      </Card>

      <Card title="Benefits - Gratuity" icon={Wallet}>
        <div className="space-y-4">
          <CheckboxField
            label="Enable gratuity"
            checked={form.gratuity_enabled ?? true}
            onChange={(v) => updateForm((p) => ({ ...p, gratuity_enabled: v }))}
          />
          {form.gratuity_enabled && (
            <>
              <FormField label="Calculation Method">
                <select
                  value={form.gratuity_calculation || 'LAST_SALARY'}
                  onChange={(e) => updateForm((p) => ({ ...p, gratuity_calculation: e.target.value as GratuityCalculation }))}
                  className="input-field"
                >
                  {gratuityCalcOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </FormField>
              <div className="grid grid-cols-2 gap-4">
                <FormField label="Eligibility (Years)">
                  <input
                    type="number"
                    min={0}
                    value={form.gratuity_eligibility_years ?? 5}
                    onChange={(e) => updateForm((p) => ({ ...p, gratuity_eligibility_years: Number(e.target.value) }))}
                    className="input-field"
                  />
                </FormField>
                <FormField label="Days Per Year">
                  <input
                    type="number"
                    min={0}
                    value={form.gratuity_days_per_year ?? 15}
                    onChange={(e) => updateForm((p) => ({ ...p, gratuity_days_per_year: Number(e.target.value) }))}
                    className="input-field"
                  />
                </FormField>
              </div>
            </>
          )}
        </div>
      </Card>

      <Card title="Benefits - Pension & PF" icon={Wallet}>
        <div className="space-y-4">
          <CheckboxField
            label="Enable pension"
            checked={form.pension_enabled ?? true}
            onChange={(v) => updateForm((p) => ({ ...p, pension_enabled: v }))}
          />
          {form.pension_enabled && (
            <div className="grid grid-cols-2 gap-4">
              <FormField label="Employer (%)">
                <input
                  type="number"
                  min={0}
                  step={0.5}
                  value={form.pension_employer_percent ?? 10}
                  onChange={(e) => updateForm((p) => ({ ...p, pension_employer_percent: Number(e.target.value) }))}
                  className="input-field"
                />
              </FormField>
              <FormField label="Employee (%)">
                <input
                  type="number"
                  min={0}
                  step={0.5}
                  value={form.pension_employee_percent ?? 8}
                  onChange={(e) => updateForm((p) => ({ ...p, pension_employee_percent: Number(e.target.value) }))}
                  className="input-field"
                />
              </FormField>
            </div>
          )}
          <CheckboxField
            label="Enable NHF (National Housing Fund)"
            checked={form.nhf_enabled ?? true}
            onChange={(v) => updateForm((p) => ({ ...p, nhf_enabled: v }))}
          />
          {form.nhf_enabled && (
            <FormField label="NHF Rate (%)">
              <input
                type="number"
                min={0}
                step={0.5}
                value={form.nhf_percent ?? 2.5}
                onChange={(e) => updateForm((p) => ({ ...p, nhf_percent: Number(e.target.value) }))}
                className="input-field"
              />
            </FormField>
          )}
        </div>
      </Card>
    </div>
  );
}

function LifecycleTab({ form, updateForm }: TabProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card title="Probation & Notice" icon={Users}>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <FormField label="Probation (Months)">
              <input
                type="number"
                min={0}
                value={form.default_probation_months ?? 3}
                onChange={(e) => updateForm((p) => ({ ...p, default_probation_months: Number(e.target.value) }))}
                className="input-field"
              />
            </FormField>
            <FormField label="Max Extension (Months)">
              <input
                type="number"
                min={0}
                value={form.max_probation_extension_months ?? 3}
                onChange={(e) => updateForm((p) => ({ ...p, max_probation_extension_months: Number(e.target.value) }))}
                className="input-field"
              />
            </FormField>
          </div>
          <FormField label="Notice Period (Days)">
            <input
              type="number"
              min={0}
              value={form.default_notice_period_days ?? 30}
              onChange={(e) => updateForm((p) => ({ ...p, default_notice_period_days: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
          <FormField label="Final Settlement (Days)">
            <input
              type="number"
              min={0}
              value={form.final_settlement_days ?? 30}
              onChange={(e) => updateForm((p) => ({ ...p, final_settlement_days: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
          <div className="space-y-2 pt-2">
            <CheckboxField
              label="Require exit interview"
              checked={form.require_exit_interview ?? true}
              onChange={(v) => updateForm((p) => ({ ...p, require_exit_interview: v }))}
            />
            <CheckboxField
              label="Require clearance before settlement"
              checked={form.require_clearance_before_settlement ?? true}
              onChange={(v) => updateForm((p) => ({ ...p, require_clearance_before_settlement: v }))}
            />
          </div>
        </div>
      </Card>

      <Card title="Recruitment" icon={Briefcase}>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <FormField label="Job Posting Valid (Days)">
              <input
                type="number"
                min={1}
                value={form.job_posting_validity_days ?? 30}
                onChange={(e) => updateForm((p) => ({ ...p, job_posting_validity_days: Number(e.target.value) }))}
                className="input-field"
              />
            </FormField>
            <FormField label="Offer Valid (Days)">
              <input
                type="number"
                min={1}
                value={form.offer_validity_days ?? 7}
                onChange={(e) => updateForm((p) => ({ ...p, offer_validity_days: Number(e.target.value) }))}
                className="input-field"
              />
            </FormField>
          </div>
          <FormField label="Interview Duration (Min)">
            <input
              type="number"
              min={15}
              step={15}
              value={form.default_interview_duration_minutes ?? 60}
              onChange={(e) => updateForm((p) => ({ ...p, default_interview_duration_minutes: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
          <FormField label="Document Submission (Days)">
            <input
              type="number"
              min={1}
              value={form.document_submission_days ?? 7}
              onChange={(e) => updateForm((p) => ({ ...p, document_submission_days: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
          <div className="space-y-2 pt-2">
            <CheckboxField
              label="Require background check"
              checked={form.require_background_check ?? false}
              onChange={(v) => updateForm((p) => ({ ...p, require_background_check: v }))}
            />
            <CheckboxField
              label="Allow offer negotiation"
              checked={form.allow_offer_negotiation ?? true}
              onChange={(v) => updateForm((p) => ({ ...p, allow_offer_negotiation: v }))}
            />
          </div>
        </div>
      </Card>
    </div>
  );
}

function PerformanceTab({ form, updateForm }: TabProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card title="Performance Appraisal" icon={Target}>
        <div className="space-y-4">
          <FormField label="Appraisal Frequency">
            <select
              value={form.appraisal_frequency || 'ANNUAL'}
              onChange={(e) => updateForm((p) => ({ ...p, appraisal_frequency: e.target.value as AppraisalFrequency }))}
              className="input-field"
            >
              {appraisalFrequencyOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </FormField>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="Cycle Start Month">
              <select
                value={form.appraisal_cycle_start_month ?? 1}
                onChange={(e) => updateForm((p) => ({ ...p, appraisal_cycle_start_month: Number(e.target.value) }))}
                className="input-field"
              >
                {['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'].map((m, i) => (
                  <option key={i + 1} value={i + 1}>{m}</option>
                ))}
              </select>
            </FormField>
            <FormField label="Rating Scale">
              <select
                value={form.appraisal_rating_scale ?? 5}
                onChange={(e) => updateForm((p) => ({ ...p, appraisal_rating_scale: Number(e.target.value) }))}
                className="input-field"
              >
                <option value={3}>1-3</option>
                <option value={5}>1-5</option>
                <option value={10}>1-10</option>
              </select>
            </FormField>
          </div>
          <FormField label="Min Rating for Promotion">
            <input
              type="number"
              min={1}
              max={form.appraisal_rating_scale ?? 5}
              step={0.5}
              value={form.min_rating_for_promotion ?? 4}
              onChange={(e) => updateForm((p) => ({ ...p, min_rating_for_promotion: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
          <div className="space-y-2 pt-2">
            <CheckboxField
              label="Require self-review"
              checked={form.require_self_review ?? true}
              onChange={(v) => updateForm((p) => ({ ...p, require_self_review: v }))}
            />
            <CheckboxField
              label="Require peer review"
              checked={form.require_peer_review ?? false}
              onChange={(v) => updateForm((p) => ({ ...p, require_peer_review: v }))}
            />
            <CheckboxField
              label="Enable 360-degree feedback"
              checked={form.enable_360_feedback ?? false}
              onChange={(v) => updateForm((p) => ({ ...p, enable_360_feedback: v }))}
            />
          </div>
        </div>
      </Card>

      <Card title="Training & Development" icon={Target}>
        <div className="space-y-4">
          <FormField label="Mandatory Training Hours (Yearly)">
            <input
              type="number"
              min={0}
              value={form.mandatory_training_hours_yearly ?? 40}
              onChange={(e) => updateForm((p) => ({ ...p, mandatory_training_hours_yearly: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
          <FormField label="Completion Threshold (%)">
            <input
              type="number"
              min={0}
              max={100}
              value={form.training_completion_threshold_percent ?? 80}
              onChange={(e) => updateForm((p) => ({ ...p, training_completion_threshold_percent: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
          <CheckboxField
            label="Require training approval"
            checked={form.require_training_approval ?? true}
            onChange={(v) => updateForm((p) => ({ ...p, require_training_approval: v }))}
          />
        </div>
      </Card>

      <Card title="Work Week" icon={Calendar}>
        <div className="space-y-4">
          <FormField label="Working Days">
            <div className="flex flex-wrap gap-2">
              {weekDays.map((day) => {
                const isSelected = (form.work_week_days || ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY']).includes(day);
                return (
                  <button
                    key={day}
                    type="button"
                    onClick={() => {
                      const current = form.work_week_days || ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY'];
                      updateForm((p) => ({
                        ...p,
                        work_week_days: isSelected
                          ? current.filter((d: string) => d !== day)
                          : [...current, day],
                      }));
                    }}
                    className={cn(
                      'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                      isSelected
                        ? 'bg-teal-electric/20 text-teal-electric border border-teal-electric/40'
                        : 'bg-slate-elevated text-slate-muted border border-slate-border'
                    )}
                  >
                    {day.slice(0, 3)}
                  </button>
                );
              })}
            </div>
          </FormField>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="Standard Work Hours/Day">
              <input
                type="number"
                min={1}
                max={24}
                step={0.5}
                value={form.standard_work_hours_per_day ?? 8}
                onChange={(e) => updateForm((p) => ({ ...p, standard_work_hours_per_day: Number(e.target.value) }))}
                className="input-field"
              />
            </FormField>
            <FormField label="Max Work Hours/Day">
              <input
                type="number"
                min={1}
                max={24}
                value={form.max_work_hours_per_day ?? 12}
                onChange={(e) => updateForm((p) => ({ ...p, max_work_hours_per_day: Number(e.target.value) }))}
                className="input-field"
              />
            </FormField>
          </div>
        </div>
      </Card>
    </div>
  );
}

function DisplayTab({ form, updateForm }: TabProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card title="Employee ID Format" icon={Settings}>
        <div className="space-y-4">
          <FormField label="ID Format">
            <select
              value={form.employee_id_format || 'NUMERIC'}
              onChange={(e) => updateForm((p) => ({ ...p, employee_id_format: e.target.value as EmployeeIDFormat }))}
              className="input-field"
            >
              {employeeIdFormatOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label} (e.g. {opt.example})</option>
              ))}
            </select>
          </FormField>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="Prefix">
              <input
                type="text"
                value={form.employee_id_prefix ?? 'EMP'}
                onChange={(e) => updateForm((p) => ({ ...p, employee_id_prefix: e.target.value.toUpperCase() }))}
                className="input-field"
                maxLength={10}
              />
            </FormField>
            <FormField label="Min Digits">
              <input
                type="number"
                min={2}
                max={10}
                value={form.employee_id_min_digits ?? 4}
                onChange={(e) => updateForm((p) => ({ ...p, employee_id_min_digits: Number(e.target.value) }))}
                className="input-field"
              />
            </FormField>
          </div>
          <div className="p-3 bg-slate-elevated rounded-lg">
            <span className="text-slate-muted text-xs">Preview: </span>
            <span className="text-teal-electric font-mono">
              {form.employee_id_prefix || 'EMP'}-{'0'.repeat((form.employee_id_min_digits ?? 4) - 1)}1
            </span>
          </div>
        </div>
      </Card>

      <Card title="Notifications" icon={Bell}>
        <div className="space-y-4">
          <FormField label="Leave Balance Warning (Days)">
            <input
              type="number"
              min={0}
              value={form.notify_leave_balance_below ?? 3}
              onChange={(e) => updateForm((p) => ({ ...p, notify_leave_balance_below: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
          <FormField label="Appraisal Due Alert (Days)">
            <input
              type="number"
              min={0}
              value={form.notify_appraisal_due_days ?? 7}
              onChange={(e) => updateForm((p) => ({ ...p, notify_appraisal_due_days: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
          <FormField label="Probation End Alert (Days)">
            <input
              type="number"
              min={0}
              value={form.notify_probation_end_days ?? 14}
              onChange={(e) => updateForm((p) => ({ ...p, notify_probation_end_days: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
          <FormField label="Contract Expiry Alert (Days)">
            <input
              type="number"
              min={0}
              value={form.notify_contract_expiry_days ?? 30}
              onChange={(e) => updateForm((p) => ({ ...p, notify_contract_expiry_days: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
          <FormField label="Document Expiry Alert (Days)">
            <input
              type="number"
              min={0}
              value={form.notify_document_expiry_days ?? 30}
              onChange={(e) => updateForm((p) => ({ ...p, notify_document_expiry_days: Number(e.target.value) }))}
              className="input-field"
            />
          </FormField>
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
