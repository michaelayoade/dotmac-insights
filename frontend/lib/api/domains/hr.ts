/**
 * HR Domain API
 * Includes: Leave, Attendance, Recruitment, Payroll, Training, Appraisals, Lifecycle
 */

import { fetchApi } from '../core';

// =============================================================================
// GENERIC LIST RESPONSE
// =============================================================================

export interface HrListResponse<T> {
  data: T[];
  total: number;
  limit?: number;
  offset?: number;
  items?: T[];
}

// =============================================================================
// LEAVE MANAGEMENT
// =============================================================================

export interface HrLeaveType {
  id?: number;
  leave_type?: string;
  name?: string;
  is_lwp?: boolean;
  is_carry_forward?: boolean;
}

export interface HrHolidayItem {
  holiday_date: string;
  description?: string | null;
  weekly_off?: boolean;
  idx?: number;
}

export interface HrHolidayListPayload {
  holiday_list_name: string;
  from_date: string;
  to_date: string;
  company?: string | null;
  weekly_off?: string | null;
  holidays?: HrHolidayItem[];
}

export interface HrHolidayList extends HrHolidayListPayload {
  id?: number;
}

export interface HrLeavePolicyDetail {
  leave_type?: string;
  annual_allocation?: number;
  max_leaves?: number;
  idx?: number;
}

export interface HrLeavePolicyPayload {
  leave_policy_name: string;
  company?: string | null;
  details?: HrLeavePolicyDetail[];
}

export interface HrLeavePolicy extends HrLeavePolicyPayload {
  id?: number;
}

export interface HrLeaveAllocationPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  leave_type: string;
  leave_type_id?: number;
  from_date: string;
  to_date: string;
  new_leaves_allocated?: number;
  total_leaves_allocated?: number;
  unused_leaves?: number;
  carry_forwarded_leaves?: number;
  carry_forwarded_leaves_count?: number;
  leave_policy?: string;
  status?: string;
  docstatus?: number;
  company?: string;
}

export interface HrLeaveAllocation extends HrLeaveAllocationPayload {
  id?: number;
}

export interface HrLeaveApplicationPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  leave_type: string;
  leave_type_id?: number;
  from_date: string;
  to_date: string;
  total_leave_days?: number;
  half_day?: boolean;
  half_day_date?: string | null;
  status?: string;
  company?: string;
  description?: string | null;
  docstatus?: number;
  leave_allocation?: string | null;
}

export interface HrLeaveApplication extends HrLeaveApplicationPayload {
  id?: number;
}

// =============================================================================
// ATTENDANCE & SHIFTS
// =============================================================================

export interface HrShiftType {
  id?: number;
  shift_type?: string;
  name?: string;
  company?: string;
}

export interface HrShiftAssignmentPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  shift_type: string;
  shift_type_id?: number;
  from_date: string;
  to_date?: string;
  status?: string;
  company?: string;
  docstatus?: number;
}

export interface HrShiftAssignment extends HrShiftAssignmentPayload {
  id?: number;
}

export interface HrAttendancePayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  attendance_date: string;
  status: string;
  leave_type?: string | null;
  leave_application?: string | null;
  shift?: string | null;
  company?: string;
  in_time?: string | null;
  out_time?: string | null;
  working_hours?: number;
  check_in_latitude?: number;
  check_in_longitude?: number;
  check_out_latitude?: number;
  check_out_longitude?: number;
  device_info?: string | null;
  late_entry?: boolean;
  early_exit?: boolean;
  docstatus?: number;
}

export interface HrAttendance extends HrAttendancePayload {
  id?: number;
}

export interface HrAttendanceRequestPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  from_date: string;
  to_date: string;
  status?: string;
  company?: string;
  reason?: string | null;
  docstatus?: number;
}

export interface HrAttendanceRequest extends HrAttendanceRequestPayload {
  id?: number;
}

// =============================================================================
// RECRUITMENT
// =============================================================================

export interface HrJobOpeningPayload {
  job_title: string;
  status?: string;
  company?: string;
  designation?: string;
  department?: string;
  branch?: string;
  posting_date?: string;
  expected_date?: string;
  vacancies?: number;
  description?: string | null;
  docstatus?: number;
}

export interface HrJobOpening extends HrJobOpeningPayload {
  id?: number;
}

export interface HrJobApplicantPayload {
  applicant_name: string;
  email_id: string;
  status?: string;
  job_title?: string;
  source?: string;
  applicant_id?: string;
  company?: string;
  application_date?: string;
  docstatus?: number;
}

export interface HrJobApplicant extends HrJobApplicantPayload {
  id?: number;
}

export interface HrJobOfferTerm {
  offer_term?: string;
  value?: string;
  value_type?: string;
  idx?: number;
}

export interface HrJobOfferPayload {
  job_applicant: string;
  job_applicant_id?: number;
  job_applicant_name?: string;
  job_title?: string;
  company?: string;
  status?: string;
  offer_date?: string;
  designation?: string;
  salary_structure?: string;
  terms?: HrJobOfferTerm[];
}

export interface HrJobOffer extends HrJobOfferPayload {
  id?: number;
}

export interface HrInterviewPayload {
  job_applicant_id: number;
  scheduled_at: string;
  interviewer: string;
  location?: string | null;
  mode?: string | null;
  feedback?: string | null;
  rating?: number | null;
  result?: string | null;
  status?: string;
}

export interface HrInterview extends HrInterviewPayload {
  id?: number;
}

// =============================================================================
// PAYROLL
// =============================================================================

export interface HrSalaryComponentPayload {
  salary_component: string;
  abbr?: string;
  type: string;
  company?: string;
  depends_on_payment_days?: boolean;
  do_not_include_in_total?: boolean;
  round_to_the_nearest_integer?: boolean;
}

export interface HrSalaryComponent extends HrSalaryComponentPayload {
  id?: number;
}

export interface HrSalaryStructureLine {
  salary_component: string;
  abbr?: string;
  amount?: number;
  default_amount?: number;
  idx?: number;
}

export interface HrSalaryStructurePayload {
  name: string;
  company?: string;
  is_active?: boolean;
  currency?: string;
  earnings?: HrSalaryStructureLine[];
  deductions?: HrSalaryStructureLine[];
}

export interface HrSalaryStructure extends HrSalaryStructurePayload {
  id?: number;
}

export interface HrSalaryStructureAssignmentPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  salary_structure: string;
  from_date: string;
  to_date?: string;
  base?: number;
  variable?: number;
  company?: string;
}

export interface HrSalaryStructureAssignment extends HrSalaryStructureAssignmentPayload {
  id?: number;
}

export interface HrPayrollEntryPayload {
  company: string;
  posting_date: string;
  payroll_frequency: string;
  start_date: string;
  end_date: string;
  status?: string;
  docstatus?: number;
}

export interface HrPayrollEntry extends HrPayrollEntryPayload {
  id?: number;
}

export interface HrSalarySlipPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  department?: string;
  designation?: string;
  branch?: string;
  salary_structure?: string;
  posting_date: string;
  start_date: string;
  end_date: string;
  payroll_frequency?: string;
  company: string;
  currency?: string;
  total_working_days?: number;
  absent_days?: number;
  payment_days?: number;
  leave_without_pay?: number;
  gross_pay?: number;
  total_deduction?: number;
  net_pay?: number;
  rounded_total?: number;
  status?: string;
  docstatus?: number;
  bank_name?: string | null;
  bank_account_no?: string | null;
  payroll_entry?: string | null;
  earnings?: HrSalaryStructureLine[];
  deductions?: HrSalaryStructureLine[];
}

export interface HrSalarySlip extends HrSalarySlipPayload {
  id?: number;
}

export interface HrPayrollPayoutItem {
  salary_slip_id: number;
  account_number: string;
  bank_code: string;
  account_name?: string | null;
}

export interface HrPayrollPayoutRequest {
  payouts: HrPayrollPayoutItem[];
  provider?: string | null;
  currency?: string | null;
}

// =============================================================================
// HR SETTINGS
// =============================================================================

export type LeaveAccountingFrequency = 'ANNUAL' | 'MONTHLY' | 'QUARTERLY' | 'BIANNUAL';
export type ProRataMethod = 'LINEAR' | 'CALENDAR_DAYS' | 'WORKING_DAYS' | 'MONTHLY';
export type PayrollFrequency = 'WEEKLY' | 'BIWEEKLY' | 'MONTHLY' | 'SEMIMONTHLY';
export type OvertimeCalculation = 'HOURLY_RATE' | 'DAILY_RATE' | 'MONTHLY_RATE';
export type GratuityCalculation = 'LAST_SALARY' | 'AVERAGE_SALARY' | 'BASIC_SALARY';
export type AttendanceMarkingMode = 'MANUAL' | 'BIOMETRIC' | 'GEOLOCATION' | 'HYBRID';
export type AppraisalFrequency = 'ANNUAL' | 'SEMIANNUAL' | 'QUARTERLY' | 'MONTHLY';
export type EmployeeIDFormat = 'NUMERIC' | 'ALPHANUMERIC' | 'YEAR_BASED' | 'DEPARTMENT_BASED';
export type WeekDay = 'MONDAY' | 'TUESDAY' | 'WEDNESDAY' | 'THURSDAY' | 'FRIDAY' | 'SATURDAY' | 'SUNDAY';

export interface HRSettingsResponse {
  id: number;
  company: string | null;
  leave_accounting_frequency: LeaveAccountingFrequency;
  pro_rata_method: ProRataMethod;
  max_carryforward_days: number;
  carryforward_expiry_months: number;
  min_leave_notice_days: number;
  allow_negative_leave_balance: boolean;
  allow_leave_overlap: boolean;
  sick_leave_auto_approve_days: number;
  medical_certificate_required_after_days: number;
  attendance_marking_mode: AttendanceMarkingMode;
  allow_backdated_attendance: boolean;
  backdated_attendance_days: number;
  auto_mark_absent_enabled: boolean;
  late_entry_grace_minutes: number;
  early_exit_grace_minutes: number;
  half_day_hours_threshold: number;
  full_day_hours_threshold: number;
  require_checkout: boolean;
  geolocation_required: boolean;
  geolocation_radius_meters: number;
  default_shift_id?: number | null;
  max_weekly_hours: number;
  night_shift_allowance_percent: number;
  shift_change_notice_days: number;
  payroll_frequency: PayrollFrequency;
  salary_payment_day: number;
  payroll_cutoff_day: number;
  allow_salary_advance: boolean;
  max_advance_percent: number;
  max_advance_months: number;
  salary_currency: string;
  overtime_enabled: boolean;
  overtime_calculation: OvertimeCalculation;
  overtime_multiplier_weekday: number;
  overtime_multiplier_weekend: number;
  overtime_multiplier_holiday: number;
  min_overtime_hours: number;
  require_overtime_approval?: boolean;
  gratuity_enabled?: boolean;
  gratuity_calculation?: GratuityCalculation;
  gratuity_eligibility_years?: number;
  gratuity_days_per_year?: number;
  pension_enabled?: boolean;
  pension_employer_percent?: number;
  pension_employee_percent?: number;
  nhf_enabled?: boolean;
  nhf_percent?: number;
  default_probation_months?: number;
  max_probation_extension_months?: number;
  default_notice_period_days?: number;
  final_settlement_days?: number;
  require_exit_interview?: boolean;
  require_clearance_before_settlement?: boolean;
  job_posting_validity_days?: number;
  offer_validity_days?: number;
  appraisal_frequency?: AppraisalFrequency;
  employee_id_format?: EmployeeIDFormat;
  work_week?: WeekDay[];
  display_currency?: string;
  // Recruitment
  default_interview_duration_minutes?: number;
  document_submission_days?: number;
  require_background_check?: boolean;
  allow_offer_negotiation?: boolean;
  // Performance & Training
  appraisal_cycle_start_month?: number;
  appraisal_rating_scale?: number;
  min_rating_for_promotion?: number;
  require_self_review?: boolean;
  require_peer_review?: boolean;
  enable_360_feedback?: boolean;
  mandatory_training_hours_yearly?: number;
  training_completion_threshold_percent?: number;
  require_training_approval?: boolean;
  // Work Week
  work_week_days?: WeekDay[];
  standard_work_hours_per_day?: number;
  max_work_hours_per_day?: number;
  // Display / IDs
  employee_id_prefix?: string;
  employee_id_min_digits?: number;
  // Notifications
  notify_leave_balance_below?: number;
  notify_appraisal_due_days?: number;
  notify_probation_end_days?: number;
  notify_contract_expiry_days?: number;
  notify_document_expiry_days?: number;
}

export type HRSettingsUpdate = Partial<HRSettingsResponse>;

// =============================================================================
// TRAINING
// =============================================================================

export interface HrTrainingProgramPayload {
  program_name: string;
  description?: string | null;
  company?: string;
}

export interface HrTrainingProgram extends HrTrainingProgramPayload {
  id?: number;
}

export interface HrTrainingEventEmployee {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  attendance?: string;
  feedback?: string | null;
  idx?: number;
}

export interface HrTrainingEventPayload {
  training_event_name: string;
  training_program: string;
  status?: string;
  company?: string;
  start_time?: string;
  end_time?: string;
  location?: string | null;
  instructor?: string | null;
  employees?: HrTrainingEventEmployee[];
}

export interface HrTrainingEvent extends HrTrainingEventPayload {
  id?: number;
}

export interface HrTrainingResultPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  training_event: string;
  result?: string;
  score?: number;
  company?: string;
}

export interface HrTrainingResult extends HrTrainingResultPayload {
  id?: number;
}

// =============================================================================
// APPRAISALS
// =============================================================================

export interface HrAppraisalTemplateGoal {
  goal: string;
  weightage?: number;
  idx?: number;
}

export interface HrAppraisalTemplatePayload {
  template_name: string;
  company?: string;
  goals?: HrAppraisalTemplateGoal[];
}

export interface HrAppraisalTemplate extends HrAppraisalTemplatePayload {
  id?: number;
}

export interface HrAppraisalGoal {
  goal: string;
  weightage?: number;
  score?: number;
  rating?: string;
  idx?: number;
}

export interface HrAppraisalPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  company?: string;
  status?: string;
  appraisal_template?: string;
  start_date?: string;
  end_date?: string;
  goals?: HrAppraisalGoal[];
}

export interface HrAppraisal extends HrAppraisalPayload {
  id?: number;
}

// =============================================================================
// EMPLOYEE LIFECYCLE
// =============================================================================

export interface HrOnboardingActivity {
  activity: string;
  status?: string;
  idx?: number;
}

export interface HrEmployeeOnboardingPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  company?: string;
  status?: string;
  activities?: HrOnboardingActivity[];
}

export interface HrEmployeeOnboarding extends HrEmployeeOnboardingPayload {
  id?: number;
}

export interface HrSeparationActivity {
  activity: string;
  status?: string;
  idx?: number;
}

export interface HrEmployeeSeparationPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  company?: string;
  reason?: string;
  notice_date?: string;
  relieving_date?: string;
  status?: string;
  activities?: HrSeparationActivity[];
}

export interface HrEmployeeSeparation extends HrEmployeeSeparationPayload {
  id?: number;
}

export interface HrEmployeePromotionDetail {
  promotion_based_on?: string;
  current_designation?: string;
  new_designation?: string;
  idx?: number;
}

export interface HrEmployeePromotionPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  promotion_date: string;
  company?: string;
  status?: string;
  details?: HrEmployeePromotionDetail[];
}

export interface HrEmployeePromotion extends HrEmployeePromotionPayload {
  id?: number;
}

export interface HrEmployeeTransferDetail {
  from_department?: string;
  to_department?: string;
  idx?: number;
}

export interface HrEmployeeTransferPayload {
  employee: string;
  employee_id?: number;
  employee_name?: string;
  company?: string;
  transfer_date: string;
  status?: string;
  details?: HrEmployeeTransferDetail[];
}

export interface HrEmployeeTransfer extends HrEmployeeTransferPayload {
  id?: number;
}

// =============================================================================
// ANALYTICS
// =============================================================================

export interface HrAnalyticsOverview {
  leave_by_status?: Record<string, number>;
  attendance_status_30d?: Record<string, number>;
  recruitment_funnel?: Record<string, number>;
  payroll_30d?: {
    gross_total?: number;
    deduction_total?: number;
    net_total?: number;
    slip_count?: number;
  };
  training_events_by_status?: Record<string, number>;
  appraisals_by_status?: Record<string, number>;
}

export interface HrLeaveTrendPoint {
  month: string;
  count: number;
}

export interface HrAttendanceTrendPoint {
  date: string;
  status_counts?: Record<string, number>;
  total?: number;
}

export interface HrPayrollSummary {
  gross_total?: number;
  deduction_total?: number;
  net_total?: number;
  average_gross?: number;
  average_net?: number;
  slip_count?: number;
}

export interface HrPayrollTrendPoint {
  month: string;
  gross_total?: number;
  deduction_total?: number;
  net_total?: number;
  slip_count?: number;
}

export interface HrPayrollComponentBreakdown {
  salary_component?: string;
  component_type?: string;
  amount?: number;
  count?: number;
}

export interface HrRecruitmentFunnel {
  openings?: Record<string, number>;
  applicants?: Record<string, number>;
  offers?: Record<string, number>;
}

export interface HrAppraisalStatusBreakdown {
  status_counts?: Record<string, number>;
}

export interface HrLifecycleEventsBreakdown {
  onboarding?: Record<string, number>;
  separation?: Record<string, number>;
  promotion?: Record<string, number>;
  transfer?: Record<string, number>;
}

export interface HrEmployee {
  id: number;
  name: string;
  email?: string;
  employee_number?: string;
  department?: string;
  designation?: string;
  status?: string;
}

export interface HrEmployeeListResponse {
  items: HrEmployee[];
  total: number;
  limit: number;
  offset: number;
}

export interface HrEmployeePayload {
  employee_name?: string;
  first_name?: string;
  last_name?: string;
  gender?: string;
  date_of_birth?: string;
  date_of_joining?: string;
  department?: string;
  designation?: string;
  status?: string;
  company_email?: string;
  personal_email?: string;
  cell_number?: string;
  company?: string;
  employment_type?: string;
  holiday_list?: string;
}

// Department Types
export interface HrDepartment {
  id: number;
  name: string;
  department_name?: string;
  parent_department?: string | null;
  company?: string | null;
  is_group?: boolean;
  disabled?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface HrDepartmentListResponse {
  items: HrDepartment[];
  total: number;
}

export interface HrDepartmentPayload {
  department_name: string;
  parent_department?: string | null;
  company?: string | null;
  is_group?: boolean;
}

// Designation Types
export interface HrDesignation {
  id: number;
  name: string;
  designation_name?: string;
  description?: string | null;
  disabled?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface HrDesignationListResponse {
  items: HrDesignation[];
  total: number;
}

export interface HrDesignationPayload {
  designation_name: string;
  description?: string | null;
}

// =============================================================================
// PARAM TYPES
// =============================================================================

export interface HrLeaveTypeListParams {
  search?: string;
  is_lwp?: boolean;
  is_carry_forward?: boolean;
  limit?: number;
  offset?: number;
}

export interface HrHolidayListParams {
  search?: string;
  company?: string;
  from_date?: string;
  to_date?: string;
  limit?: number;
  offset?: number;
}

export interface HrLeaveAllocationListParams {
  employee_id?: number;
  leave_type_id?: number;
  status?: string;
  from_date?: string;
  to_date?: string;
  company?: string;
  limit?: number;
  offset?: number;
}

export interface HrLeaveApplicationListParams {
  employee_id?: number;
  leave_type_id?: number;
  status?: string;
  from_date?: string;
  to_date?: string;
  company?: string;
  limit?: number;
  offset?: number;
}

export interface HrAttendanceListParams {
  employee_id?: number;
  status?: string;
  attendance_date?: string;
  company?: string;
  limit?: number;
  offset?: number;
}

export interface HrJobOpeningListParams {
  status?: string;
  company?: string;
  posting_date_from?: string;
  posting_date_to?: string;
  limit?: number;
  offset?: number;
}

export interface HrJobApplicantListParams {
  status?: string;
  job_title?: string;
  posting_date_from?: string;
  posting_date_to?: string;
  limit?: number;
  offset?: number;
}

export interface HrPayrollEntryListParams {
  company?: string;
  posting_date_from?: string;
  posting_date_to?: string;
  limit?: number;
  offset?: number;
}

export interface HrTrainingEventListParams {
  status?: string;
  company?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
}

export interface HrAppraisalListParams {
  employee_id?: number;
  status?: string;
  company?: string;
  limit?: number;
  offset?: number;
}

// =============================================================================
// API OBJECT
// =============================================================================

export const hrApi = {
  // Leave Types
  getLeaveTypes: (params?: HrLeaveTypeListParams) =>
    fetchApi<HrListResponse<HrLeaveType>>('/hr/leave-types', { params: params as any }),

  getLeaveTypeDetail: (id: number | string) =>
    fetchApi<HrLeaveType>(`/hr/leave-types/${id}`),

  // Holiday Lists
  getHolidayLists: (params?: HrHolidayListParams) =>
    fetchApi<HrListResponse<HrHolidayList>>('/hr/holiday-lists', { params: params as any }),

  getHolidayListDetail: (id: number | string) =>
    fetchApi<HrHolidayList>(`/hr/holiday-lists/${id}`),

  createHolidayList: (body: HrHolidayListPayload) =>
    fetchApi<HrHolidayList>('/hr/holiday-lists', { method: 'POST', body: JSON.stringify(body) }),

  updateHolidayList: (id: number | string, body: Partial<HrHolidayListPayload>) =>
    fetchApi<HrHolidayList>(`/hr/holiday-lists/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteHolidayList: (id: number | string) =>
    fetchApi<void>(`/hr/holiday-lists/${id}`, { method: 'DELETE' }),

  // Leave Policies
  getLeavePolicies: (params?: { search?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrLeavePolicy>>('/hr/leave-policies', { params }),

  getLeavePolicyDetail: (id: number | string) =>
    fetchApi<HrLeavePolicy>(`/hr/leave-policies/${id}`),

  createLeavePolicy: (body: HrLeavePolicyPayload) =>
    fetchApi<HrLeavePolicy>('/hr/leave-policies', { method: 'POST', body: JSON.stringify(body) }),

  updateLeavePolicy: (id: number | string, body: Partial<HrLeavePolicyPayload>) =>
    fetchApi<HrLeavePolicy>(`/hr/leave-policies/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteLeavePolicy: (id: number | string) =>
    fetchApi<void>(`/hr/leave-policies/${id}`, { method: 'DELETE' }),

  // Leave Allocations
  getLeaveAllocations: (params?: HrLeaveAllocationListParams) =>
    fetchApi<HrListResponse<HrLeaveAllocation>>('/hr/leave-allocations', { params: params as any }),

  getLeaveAllocationDetail: (id: number | string) =>
    fetchApi<HrLeaveAllocation>(`/hr/leave-allocations/${id}`),

  createLeaveAllocation: (body: HrLeaveAllocationPayload) =>
    fetchApi<HrLeaveAllocation>('/hr/leave-allocations', { method: 'POST', body: JSON.stringify(body) }),

  updateLeaveAllocation: (id: number | string, body: Partial<HrLeaveAllocationPayload>) =>
    fetchApi<HrLeaveAllocation>(`/hr/leave-allocations/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteLeaveAllocation: (id: number | string) =>
    fetchApi<void>(`/hr/leave-allocations/${id}`, { method: 'DELETE' }),

  bulkCreateLeaveAllocations: (body: { employee_ids: number[]; leave_policy_id: number; from_date: string; to_date: string; company?: string }) =>
    fetchApi<{ created: number; employee_ids: number[] }>('/hr/leave-allocations/bulk', { method: 'POST', body: JSON.stringify(body) }),

  // Leave Applications
  getLeaveApplications: (params?: HrLeaveApplicationListParams) =>
    fetchApi<HrListResponse<HrLeaveApplication>>('/hr/leave-applications', { params: params as any }),

  getLeaveApplicationDetail: (id: number | string) =>
    fetchApi<HrLeaveApplication>(`/hr/leave-applications/${id}`),

  createLeaveApplication: (body: HrLeaveApplicationPayload) =>
    fetchApi<HrLeaveApplication>('/hr/leave-applications', { method: 'POST', body: JSON.stringify(body) }),

  updateLeaveApplication: (id: number | string, body: Partial<HrLeaveApplicationPayload>) =>
    fetchApi<HrLeaveApplication>(`/hr/leave-applications/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteLeaveApplication: (id: number | string) =>
    fetchApi<void>(`/hr/leave-applications/${id}`, { method: 'DELETE' }),

  approveLeaveApplication: (id: number | string) =>
    fetchApi<void>(`/hr/leave-applications/${id}/approve`, { method: 'POST' }),

  rejectLeaveApplication: (id: number | string) =>
    fetchApi<void>(`/hr/leave-applications/${id}/reject`, { method: 'POST' }),

  cancelLeaveApplication: (id: number | string) =>
    fetchApi<void>(`/hr/leave-applications/${id}/cancel`, { method: 'POST' }),

  bulkApproveLeaveApplications: (body: { application_ids: (number | string)[] }) =>
    fetchApi<void>('/hr/leave-applications/bulk/approve', { method: 'POST', body: JSON.stringify(body) }),

  bulkRejectLeaveApplications: (body: { application_ids: (number | string)[] }) =>
    fetchApi<void>('/hr/leave-applications/bulk/reject', { method: 'POST', body: JSON.stringify(body) }),

  // Shifts
  getShiftTypes: (params?: { search?: string; company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrShiftType>>('/hr/shift-types', { params }),

  getShiftTypeDetail: (id: number | string) =>
    fetchApi<HrShiftType>(`/hr/shift-types/${id}`),

  getShiftAssignments: (params?: { employee_id?: number; shift_type_id?: number; start_date?: string; end_date?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrShiftAssignment>>('/hr/shift-assignments', { params }),

  getShiftAssignmentDetail: (id: number | string) =>
    fetchApi<HrShiftAssignment>(`/hr/shift-assignments/${id}`),

  createShiftAssignment: (body: HrShiftAssignmentPayload) =>
    fetchApi<HrShiftAssignment>('/hr/shift-assignments', { method: 'POST', body: JSON.stringify(body) }),

  updateShiftAssignment: (id: number | string, body: Partial<HrShiftAssignmentPayload>) =>
    fetchApi<HrShiftAssignment>(`/hr/shift-assignments/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteShiftAssignment: (id: number | string) =>
    fetchApi<void>(`/hr/shift-assignments/${id}`, { method: 'DELETE' }),

  // Attendance
  getAttendances: (params?: HrAttendanceListParams) =>
    fetchApi<HrListResponse<HrAttendance>>('/hr/attendances', { params: params as any }),

  getAttendanceDetail: (id: number | string) =>
    fetchApi<HrAttendance>(`/hr/attendances/${id}`),

  createAttendance: (body: HrAttendancePayload) =>
    fetchApi<HrAttendance>('/hr/attendances', { method: 'POST', body: JSON.stringify(body) }),

  updateAttendance: (id: number | string, body: Partial<HrAttendancePayload>) =>
    fetchApi<HrAttendance>(`/hr/attendances/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteAttendance: (id: number | string) =>
    fetchApi<void>(`/hr/attendances/${id}`, { method: 'DELETE' }),

  checkInAttendance: (id: number | string, body?: { latitude?: number; longitude?: number; device_info?: string }) =>
    fetchApi<HrAttendance>(`/hr/attendances/${id}/check-in`, { method: 'POST', body: JSON.stringify(body || {}) }),

  checkOutAttendance: (id: number | string, body?: { latitude?: number; longitude?: number }) =>
    fetchApi<HrAttendance>(`/hr/attendances/${id}/check-out`, { method: 'POST', body: JSON.stringify(body || {}) }),

  bulkMarkAttendance: (body: { employee_ids: (number | string)[]; attendance_date: string; status: string }) =>
    fetchApi<void>('/hr/attendances/bulk/mark', { method: 'POST', body: JSON.stringify(body) }),

  // Attendance Requests
  getAttendanceRequests: (params?: { employee_id?: number; status?: string; from_date?: string; to_date?: string; company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrAttendanceRequest>>('/hr/attendance-requests', { params }),

  getAttendanceRequestDetail: (id: number | string) =>
    fetchApi<HrAttendanceRequest>(`/hr/attendance-requests/${id}`),

  createAttendanceRequest: (body: HrAttendanceRequestPayload) =>
    fetchApi<HrAttendanceRequest>('/hr/attendance-requests', { method: 'POST', body: JSON.stringify(body) }),

  updateAttendanceRequest: (id: number | string, body: Partial<HrAttendanceRequestPayload>) =>
    fetchApi<HrAttendanceRequest>(`/hr/attendance-requests/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteAttendanceRequest: (id: number | string) =>
    fetchApi<void>(`/hr/attendance-requests/${id}`, { method: 'DELETE' }),

  approveAttendanceRequest: (id: number | string) =>
    fetchApi<void>(`/hr/attendance-requests/${id}/approve`, { method: 'POST' }),

  rejectAttendanceRequest: (id: number | string) =>
    fetchApi<void>(`/hr/attendance-requests/${id}/reject`, { method: 'POST' }),

  bulkApproveAttendanceRequests: (body: { request_ids: (number | string)[] }) =>
    fetchApi<void>('/hr/attendance-requests/bulk/approve', { method: 'POST', body: JSON.stringify(body) }),

  bulkRejectAttendanceRequests: (body: { request_ids: (number | string)[] }) =>
    fetchApi<void>('/hr/attendance-requests/bulk/reject', { method: 'POST', body: JSON.stringify(body) }),

  // Job Openings
  getJobOpenings: (params?: HrJobOpeningListParams) =>
    fetchApi<HrListResponse<HrJobOpening>>('/hr/job-openings', { params: params as any }),

  getJobOpeningDetail: (id: number | string) =>
    fetchApi<HrJobOpening>(`/hr/job-openings/${id}`),

  createJobOpening: (body: HrJobOpeningPayload) =>
    fetchApi<HrJobOpening>('/hr/job-openings', { method: 'POST', body: JSON.stringify(body) }),

  updateJobOpening: (id: number | string, body: Partial<HrJobOpeningPayload>) =>
    fetchApi<HrJobOpening>(`/hr/job-openings/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteJobOpening: (id: number | string) =>
    fetchApi<void>(`/hr/job-openings/${id}`, { method: 'DELETE' }),

  // Job Applicants
  getJobApplicants: (params?: HrJobApplicantListParams) =>
    fetchApi<HrListResponse<HrJobApplicant>>('/hr/job-applicants', { params: params as any }),

  getJobApplicantDetail: (id: number | string) =>
    fetchApi<HrJobApplicant>(`/hr/job-applicants/${id}`),

  createJobApplicant: (body: HrJobApplicantPayload) =>
    fetchApi<HrJobApplicant>('/hr/job-applicants', { method: 'POST', body: JSON.stringify(body) }),

  updateJobApplicant: (id: number | string, body: Partial<HrJobApplicantPayload>) =>
    fetchApi<HrJobApplicant>(`/hr/job-applicants/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteJobApplicant: (id: number | string) =>
    fetchApi<void>(`/hr/job-applicants/${id}`, { method: 'DELETE' }),

  screenJobApplicant: (id: number | string) =>
    fetchApi<void>(`/hr/job-applicants/${id}/screen`, { method: 'POST' }),

  scheduleInterviewForJobApplicant: (id: number | string, body: { interview_date: string; interviewer: string; location?: string; notes?: string }) =>
    fetchApi<void>(`/hr/job-applicants/${id}/schedule-interview`, { method: 'POST', body: JSON.stringify(body) }),

  makeOfferForJobApplicant: (id: number | string, body: { offer_id: number | string }) =>
    fetchApi<void>(`/hr/job-applicants/${id}/make-offer`, { method: 'POST', body: JSON.stringify(body) }),

  withdrawJobApplicant: (id: number | string) =>
    fetchApi<void>(`/hr/job-applicants/${id}/withdraw`, { method: 'POST' }),

  // Job Offers
  getJobOffers: (params?: { status?: string; company?: string; job_applicant?: string; offer_date_from?: string; offer_date_to?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrJobOffer>>('/hr/job-offers', { params }),

  getJobOfferDetail: (id: number | string) =>
    fetchApi<HrJobOffer>(`/hr/job-offers/${id}`),

  createJobOffer: (body: HrJobOfferPayload) =>
    fetchApi<HrJobOffer>('/hr/job-offers', { method: 'POST', body: JSON.stringify(body) }),

  updateJobOffer: (id: number | string, body: Partial<HrJobOfferPayload>) =>
    fetchApi<HrJobOffer>(`/hr/job-offers/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteJobOffer: (id: number | string) =>
    fetchApi<void>(`/hr/job-offers/${id}`, { method: 'DELETE' }),

  sendJobOffer: (id: number | string) =>
    fetchApi<void>(`/hr/job-offers/${id}/send`, { method: 'POST' }),

  voidJobOffer: (id: number | string, body: { void_reason: string; voided_at?: string }) =>
    fetchApi<void>(`/hr/job-offers/${id}/void`, { method: 'POST', body: JSON.stringify(body) }),

  acceptJobOffer: (id: number | string) =>
    fetchApi<void>(`/hr/job-offers/${id}/accept`, { method: 'POST' }),

  rejectJobOffer: (id: number | string) =>
    fetchApi<void>(`/hr/job-offers/${id}/reject`, { method: 'POST' }),

  bulkSendJobOffers: (body: { offer_ids: (number | string)[]; delivery_method?: string }) =>
    fetchApi<void>('/hr/job-offers/bulk/send', { method: 'POST', body: JSON.stringify(body) }),

  // Interviews
  getInterviews: (params?: { job_applicant_id?: number; status?: string; interviewer?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrInterview>>('/hr/interviews', { params }),

  getInterviewDetail: (id: number | string) =>
    fetchApi<HrInterview>(`/hr/interviews/${id}`),

  createInterview: (body: HrInterviewPayload) =>
    fetchApi<HrInterview>('/hr/interviews', { method: 'POST', body: JSON.stringify(body) }),

  updateInterview: (id: number | string, body: Partial<HrInterviewPayload>) =>
    fetchApi<HrInterview>(`/hr/interviews/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  completeInterview: (id: number | string, body: { feedback?: string; rating?: number; result?: string }) =>
    fetchApi<HrInterview>(`/hr/interviews/${id}/complete`, { method: 'POST', body: JSON.stringify(body) }),

  cancelInterview: (id: number | string) =>
    fetchApi<void>(`/hr/interviews/${id}/cancel`, { method: 'POST' }),

  markNoShowInterview: (id: number | string) =>
    fetchApi<void>(`/hr/interviews/${id}/no-show`, { method: 'POST' }),

  // Salary Components
  getSalaryComponents: (params?: { component_type?: string; company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrSalaryComponent>>('/hr/salary-components', { params }),

  getSalaryComponentDetail: (id: number | string) =>
    fetchApi<HrSalaryComponent>(`/hr/salary-components/${id}`),

  createSalaryComponent: (body: HrSalaryComponentPayload) =>
    fetchApi<HrSalaryComponent>('/hr/salary-components', { method: 'POST', body: JSON.stringify(body) }),

  updateSalaryComponent: (id: number | string, body: Partial<HrSalaryComponentPayload>) =>
    fetchApi<HrSalaryComponent>(`/hr/salary-components/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteSalaryComponent: (id: number | string) =>
    fetchApi<void>(`/hr/salary-components/${id}`, { method: 'DELETE' }),

  // Salary Structures
  getSalaryStructures: (params?: { company?: string; is_active?: boolean; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrSalaryStructure>>('/hr/salary-structures', { params }),

  getSalaryStructureDetail: (id: number | string) =>
    fetchApi<HrSalaryStructure>(`/hr/salary-structures/${id}`),

  createSalaryStructure: (body: HrSalaryStructurePayload) =>
    fetchApi<HrSalaryStructure>('/hr/salary-structures', { method: 'POST', body: JSON.stringify(body) }),

  updateSalaryStructure: (id: number | string, body: Partial<HrSalaryStructurePayload>) =>
    fetchApi<HrSalaryStructure>(`/hr/salary-structures/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteSalaryStructure: (id: number | string) =>
    fetchApi<void>(`/hr/salary-structures/${id}`, { method: 'DELETE' }),

  // Salary Structure Assignments
  getSalaryStructureAssignments: (params?: { employee_id?: number; from_date?: string; to_date?: string; company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrSalaryStructureAssignment>>('/hr/salary-structure-assignments', { params }),

  getSalaryStructureAssignmentDetail: (id: number | string) =>
    fetchApi<HrSalaryStructureAssignment>(`/hr/salary-structure-assignments/${id}`),

  createSalaryStructureAssignment: (body: HrSalaryStructureAssignmentPayload) =>
    fetchApi<HrSalaryStructureAssignment>('/hr/salary-structure-assignments', { method: 'POST', body: JSON.stringify(body) }),

  updateSalaryStructureAssignment: (id: number | string, body: Partial<HrSalaryStructureAssignmentPayload>) =>
    fetchApi<HrSalaryStructureAssignment>(`/hr/salary-structure-assignments/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteSalaryStructureAssignment: (id: number | string) =>
    fetchApi<void>(`/hr/salary-structure-assignments/${id}`, { method: 'DELETE' }),

  // Payroll Entries
  getPayrollEntries: (params?: HrPayrollEntryListParams) =>
    fetchApi<HrListResponse<HrPayrollEntry>>('/hr/payroll-entries', { params: params as any }),

  getPayrollEntryDetail: (id: number | string) =>
    fetchApi<HrPayrollEntry>(`/hr/payroll-entries/${id}`),

  createPayrollEntry: (body: HrPayrollEntryPayload) =>
    fetchApi<HrPayrollEntry>('/hr/payroll-entries', { method: 'POST', body: JSON.stringify(body) }),

  updatePayrollEntry: (id: number | string, body: Partial<HrPayrollEntryPayload>) =>
    fetchApi<HrPayrollEntry>(`/hr/payroll-entries/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deletePayrollEntry: (id: number | string) =>
    fetchApi<void>(`/hr/payroll-entries/${id}`, { method: 'DELETE' }),

  generatePayrollSlips: (id: number | string, body: { company: string; department?: string | null; branch?: string | null; designation?: string | null; start_date: string; end_date: string; regenerate?: boolean }) =>
    fetchApi<void>(`/hr/payroll-entries/${id}/generate-slips`, { method: 'POST', body: JSON.stringify(body) }),

  regeneratePayrollSlips: (id: number | string, body: { overwrite_drafts?: boolean }) =>
    fetchApi<void>(`/hr/payroll-entries/${id}/regenerate-slips`, { method: 'POST', body: JSON.stringify(body) }),

  initiatePayrollPayouts: (entryId: number | string, body: HrPayrollPayoutRequest) =>
    fetchApi<void>(`/hr/payroll-entries/${entryId}/initiate-payouts`, { method: 'POST', body: JSON.stringify(body) }),

  handoffPayrollToBooks: (entryId: number | string, body: HrPayrollPayoutRequest) =>
    fetchApi<void>(`/hr/payroll-entries/${entryId}/handoff-to-books`, { method: 'POST', body: JSON.stringify(body) }),

  // Training Programs
  getTrainingPrograms: (params?: { search?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrTrainingProgram>>('/hr/training-programs', { params }),

  getTrainingProgramDetail: (id: number | string) =>
    fetchApi<HrTrainingProgram>(`/hr/training-programs/${id}`),

  createTrainingProgram: (body: HrTrainingProgramPayload) =>
    fetchApi<HrTrainingProgram>('/hr/training-programs', { method: 'POST', body: JSON.stringify(body) }),

  updateTrainingProgram: (id: number | string, body: Partial<HrTrainingProgramPayload>) =>
    fetchApi<HrTrainingProgram>(`/hr/training-programs/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteTrainingProgram: (id: number | string) =>
    fetchApi<void>(`/hr/training-programs/${id}`, { method: 'DELETE' }),

  // Training Events
  getTrainingEvents: (params?: HrTrainingEventListParams) =>
    fetchApi<HrListResponse<HrTrainingEvent>>('/hr/training-events', { params: params as any }),

  getTrainingEventDetail: (id: number | string) =>
    fetchApi<HrTrainingEvent>(`/hr/training-events/${id}`),

  createTrainingEvent: (body: HrTrainingEventPayload) =>
    fetchApi<HrTrainingEvent>('/hr/training-events', { method: 'POST', body: JSON.stringify(body) }),

  updateTrainingEvent: (id: number | string, body: Partial<HrTrainingEventPayload>) =>
    fetchApi<HrTrainingEvent>(`/hr/training-events/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteTrainingEvent: (id: number | string) =>
    fetchApi<void>(`/hr/training-events/${id}`, { method: 'DELETE' }),

  enrollTrainingEvent: (id: number | string, body: { employee_ids: (number | string)[] }) =>
    fetchApi<void>(`/hr/training-events/${id}/enroll`, { method: 'POST', body: JSON.stringify(body) }),

  completeTrainingEvent: (id: number | string) =>
    fetchApi<void>(`/hr/training-events/${id}/complete`, { method: 'POST' }),

  // Training Results
  getTrainingResults: (params?: { employee_id?: number; training_event?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrTrainingResult>>('/hr/training-results', { params }),

  getTrainingResultDetail: (id: number | string) =>
    fetchApi<HrTrainingResult>(`/hr/training-results/${id}`),

  createTrainingResult: (body: HrTrainingResultPayload) =>
    fetchApi<HrTrainingResult>('/hr/training-results', { method: 'POST', body: JSON.stringify(body) }),

  updateTrainingResult: (id: number | string, body: Partial<HrTrainingResultPayload>) =>
    fetchApi<HrTrainingResult>(`/hr/training-results/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteTrainingResult: (id: number | string) =>
    fetchApi<void>(`/hr/training-results/${id}`, { method: 'DELETE' }),

  // Appraisal Templates
  getAppraisalTemplates: (params?: { company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrAppraisalTemplate>>('/hr/appraisal-templates', { params }),

  getAppraisalTemplateDetail: (id: number | string) =>
    fetchApi<HrAppraisalTemplate>(`/hr/appraisal-templates/${id}`),

  createAppraisalTemplate: (body: HrAppraisalTemplatePayload) =>
    fetchApi<HrAppraisalTemplate>('/hr/appraisal-templates', { method: 'POST', body: JSON.stringify(body) }),

  updateAppraisalTemplate: (id: number | string, body: Partial<HrAppraisalTemplatePayload>) =>
    fetchApi<HrAppraisalTemplate>(`/hr/appraisal-templates/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteAppraisalTemplate: (id: number | string) =>
    fetchApi<void>(`/hr/appraisal-templates/${id}`, { method: 'DELETE' }),

  // Appraisals
  getAppraisals: (params?: HrAppraisalListParams) =>
    fetchApi<HrListResponse<HrAppraisal>>('/hr/appraisals', { params: params as any }),

  getAppraisalDetail: (id: number | string) =>
    fetchApi<HrAppraisal>(`/hr/appraisals/${id}`),

  createAppraisal: (body: HrAppraisalPayload) =>
    fetchApi<HrAppraisal>('/hr/appraisals', { method: 'POST', body: JSON.stringify(body) }),

  updateAppraisal: (id: number | string, body: Partial<HrAppraisalPayload>) =>
    fetchApi<HrAppraisal>(`/hr/appraisals/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteAppraisal: (id: number | string) =>
    fetchApi<void>(`/hr/appraisals/${id}`, { method: 'DELETE' }),

  submitAppraisal: (id: number | string) =>
    fetchApi<void>(`/hr/appraisals/${id}/submit`, { method: 'POST' }),

  reviewAppraisal: (id: number | string) =>
    fetchApi<void>(`/hr/appraisals/${id}/review`, { method: 'POST' }),

  closeAppraisal: (id: number | string) =>
    fetchApi<void>(`/hr/appraisals/${id}/close`, { method: 'POST' }),

  // Employee Onboarding
  getEmployeeOnboardings: (params?: { employee_id?: number; company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrEmployeeOnboarding>>('/hr/employee-onboardings', { params }),

  getEmployeeOnboardingDetail: (id: number | string) =>
    fetchApi<HrEmployeeOnboarding>(`/hr/employee-onboardings/${id}`),

  createEmployeeOnboarding: (body: HrEmployeeOnboardingPayload) =>
    fetchApi<HrEmployeeOnboarding>('/hr/employee-onboardings', { method: 'POST', body: JSON.stringify(body) }),

  updateEmployeeOnboarding: (id: number | string, body: Partial<HrEmployeeOnboardingPayload>) =>
    fetchApi<HrEmployeeOnboarding>(`/hr/employee-onboardings/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteEmployeeOnboarding: (id: number | string) =>
    fetchApi<void>(`/hr/employee-onboardings/${id}`, { method: 'DELETE' }),

  // Employee Separations
  getEmployeeSeparations: (params?: { employee_id?: number; company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrEmployeeSeparation>>('/hr/employee-separations', { params }),

  getEmployeeSeparationDetail: (id: number | string) =>
    fetchApi<HrEmployeeSeparation>(`/hr/employee-separations/${id}`),

  createEmployeeSeparation: (body: HrEmployeeSeparationPayload) =>
    fetchApi<HrEmployeeSeparation>('/hr/employee-separations', { method: 'POST', body: JSON.stringify(body) }),

  updateEmployeeSeparation: (id: number | string, body: Partial<HrEmployeeSeparationPayload>) =>
    fetchApi<HrEmployeeSeparation>(`/hr/employee-separations/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteEmployeeSeparation: (id: number | string) =>
    fetchApi<void>(`/hr/employee-separations/${id}`, { method: 'DELETE' }),

  // Employee Promotions
  getEmployeePromotions: (params?: { employee_id?: number; company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrEmployeePromotion>>('/hr/employee-promotions', { params }),

  getEmployeePromotionDetail: (id: number | string) =>
    fetchApi<HrEmployeePromotion>(`/hr/employee-promotions/${id}`),

  createEmployeePromotion: (body: HrEmployeePromotionPayload) =>
    fetchApi<HrEmployeePromotion>('/hr/employee-promotions', { method: 'POST', body: JSON.stringify(body) }),

  updateEmployeePromotion: (id: number | string, body: Partial<HrEmployeePromotionPayload>) =>
    fetchApi<HrEmployeePromotion>(`/hr/employee-promotions/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteEmployeePromotion: (id: number | string) =>
    fetchApi<void>(`/hr/employee-promotions/${id}`, { method: 'DELETE' }),

  // Employee Transfers
  getEmployeeTransfers: (params?: { employee_id?: number; company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrListResponse<HrEmployeeTransfer>>('/hr/employee-transfers', { params }),

  getEmployeeTransferDetail: (id: number | string) =>
    fetchApi<HrEmployeeTransfer>(`/hr/employee-transfers/${id}`),

  createEmployeeTransfer: (body: HrEmployeeTransferPayload) =>
    fetchApi<HrEmployeeTransfer>('/hr/employee-transfers', { method: 'POST', body: JSON.stringify(body) }),

  updateEmployeeTransfer: (id: number | string, body: Partial<HrEmployeeTransferPayload>) =>
    fetchApi<HrEmployeeTransfer>(`/hr/employee-transfers/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteEmployeeTransfer: (id: number | string) =>
    fetchApi<void>(`/hr/employee-transfers/${id}`, { method: 'DELETE' }),

  // -------------------------------------------------------------------------
  // Employees
  // -------------------------------------------------------------------------

  /** List employees */
  getEmployees: (params?: { search?: string; department?: string; status?: string; limit?: number; offset?: number }) =>
    fetchApi<HrEmployeeListResponse>('/hr/employees', { params }),

  /** Get employee detail */
  getEmployee: (id: number | string) =>
    fetchApi<HrEmployee>(`/hr/employees/${id}`),

  /** Create an employee */
  createEmployee: (body: HrEmployeePayload) =>
    fetchApi<HrEmployee>('/hr/employees', { method: 'POST', body: JSON.stringify(body) }),

  /** Update an employee */
  updateEmployee: (id: number | string, body: Partial<HrEmployeePayload>) =>
    fetchApi<HrEmployee>(`/hr/employees/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  /** Delete an employee (soft) */
  deleteEmployee: (id: number | string) =>
    fetchApi<void>(`/hr/employees/${id}`, { method: 'DELETE' }),

  // -------------------------------------------------------------------------
  // Departments
  // -------------------------------------------------------------------------

  /** List departments */
  getDepartments: (params?: { search?: string; company?: string; limit?: number; offset?: number }) =>
    fetchApi<HrDepartmentListResponse>('/hr/departments', { params }),

  /** Get department detail */
  getDepartment: (id: number | string) =>
    fetchApi<HrDepartment>(`/hr/departments/${id}`),

  /** Create a department */
  createDepartment: (body: HrDepartmentPayload) =>
    fetchApi<HrDepartment>('/hr/departments', { method: 'POST', body: JSON.stringify(body) }),

  /** Update a department */
  updateDepartment: (id: number | string, body: Partial<HrDepartmentPayload>) =>
    fetchApi<HrDepartment>(`/hr/departments/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  /** Delete a department */
  deleteDepartment: (id: number | string) =>
    fetchApi<void>(`/hr/departments/${id}`, { method: 'DELETE' }),

  // -------------------------------------------------------------------------
  // Designations
  // -------------------------------------------------------------------------

  /** List designations */
  getDesignations: (params?: { search?: string; limit?: number; offset?: number }) =>
    fetchApi<HrDesignationListResponse>('/hr/designations', { params }),

  /** Get designation detail */
  getDesignation: (id: number | string) =>
    fetchApi<HrDesignation>(`/hr/designations/${id}`),

  /** Create a designation */
  createDesignation: (body: HrDesignationPayload) =>
    fetchApi<HrDesignation>('/hr/designations', { method: 'POST', body: JSON.stringify(body) }),

  /** Update a designation */
  updateDesignation: (id: number | string, body: Partial<HrDesignationPayload>) =>
    fetchApi<HrDesignation>(`/hr/designations/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  /** Delete a designation */
  deleteDesignation: (id: number | string) =>
    fetchApi<void>(`/hr/designations/${id}`, { method: 'DELETE' }),

  // Analytics
  getAnalyticsOverview: (params?: { company?: string }) =>
    fetchApi<HrAnalyticsOverview>('/hr/analytics/overview', { params }),

  getAnalyticsLeaveTrend: (params?: { company?: string; months?: number }) =>
    fetchApi<HrLeaveTrendPoint[]>('/hr/analytics/leave-trend', { params }),

  getAnalyticsAttendanceTrend: (params?: { company?: string; days?: number }) =>
    fetchApi<HrAttendanceTrendPoint[]>('/hr/analytics/attendance-trend', { params }),

  getAnalyticsPayrollSummary: (params?: { company?: string; department?: string; start_date?: string; end_date?: string; status?: string }) =>
    fetchApi<HrPayrollSummary>('/hr/analytics/payroll-summary', { params }),

  getAnalyticsPayrollTrend: (params?: { company?: string; department?: string; start_date?: string; end_date?: string }) =>
    fetchApi<HrPayrollTrendPoint[]>('/hr/analytics/payroll-trend', { params }),

  getAnalyticsPayrollComponents: (params?: { component_type?: string; company?: string; start_date?: string; end_date?: string; limit?: number }) =>
    fetchApi<HrPayrollComponentBreakdown[]>('/hr/analytics/payroll-components', { params }),

  getAnalyticsRecruitmentFunnel: (params?: { company?: string; job_title?: string; start_date?: string; end_date?: string }) =>
    fetchApi<HrRecruitmentFunnel>('/hr/analytics/recruitment-funnel', { params }),

  getAnalyticsAppraisalStatus: (params?: { company?: string; department?: string; start_date?: string; end_date?: string }) =>
    fetchApi<HrAppraisalStatusBreakdown>('/hr/analytics/appraisal-status', { params }),

  getAnalyticsLifecycleEvents: (params?: { company?: string; start_date?: string; end_date?: string }) =>
    fetchApi<HrLifecycleEventsBreakdown>('/hr/analytics/lifecycle-events', { params }),

  // Settings
  getHRSettings: (params?: { company?: string }) =>
    fetchApi<HRSettingsResponse>('/hr/settings', { params }),

  updateHRSettings: (body: HRSettingsUpdate, company?: string) =>
    fetchApi<HRSettingsResponse>('/hr/settings', {
      method: 'PUT',
      body: JSON.stringify(body),
      params: company ? { company } : undefined,
    }),

  seedHRDefaults: () =>
    fetchApi<{ status: string }>('/hr/settings/seed-defaults', { method: 'POST' }),
};
