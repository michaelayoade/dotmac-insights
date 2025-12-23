/**
 * Status Maps - Per-module status configurations
 *
 * Centralizes status definitions and their mappings to variants.
 * Use these instead of defining status arrays inline in pages.
 *
 * Usage:
 *   import { INVOICE_STATUSES, getInvoiceStatusOptions } from '@/lib/config/status-maps';
 */

import { type Variant, STATUS_VARIANT_MAP } from '@/lib/design-tokens';

// =============================================================================
// SALES STATUSES
// =============================================================================

export const INVOICE_STATUSES = [
  'draft',
  'pending',
  'paid',
  'partially_paid',
  'overdue',
  'cancelled',
] as const;
export type InvoiceStatus = (typeof INVOICE_STATUSES)[number];

export const QUOTATION_STATUSES = [
  'draft',
  'pending',
  'accepted',
  'rejected',
  'expired',
] as const;
export type QuotationStatus = (typeof QUOTATION_STATUSES)[number];

export const SALES_ORDER_STATUSES = [
  'draft',
  'submitted',
  'confirmed',
  'processing',
  'delivered',
  'cancelled',
] as const;
export type SalesOrderStatus = (typeof SALES_ORDER_STATUSES)[number];

export const LEAD_STATUSES = [
  'new',
  'contacted',
  'qualified',
  'unqualified',
  'converted',
  'lost',
] as const;
export type LeadStatus = (typeof LEAD_STATUSES)[number];

export const OPPORTUNITY_STATUSES = [
  'open',
  'qualified',
  'negotiation',
  'won',
  'lost',
] as const;
export type OpportunityStatus = (typeof OPPORTUNITY_STATUSES)[number];

// =============================================================================
// PURCHASING STATUSES
// =============================================================================

export const BILL_STATUSES = [
  'draft',
  'pending',
  'paid',
  'partially_paid',
  'overdue',
  'cancelled',
] as const;
export type BillStatus = (typeof BILL_STATUSES)[number];

export const PURCHASE_ORDER_STATUSES = [
  'draft',
  'submitted',
  'approved',
  'received',
  'cancelled',
] as const;
export type PurchaseOrderStatus = (typeof PURCHASE_ORDER_STATUSES)[number];

// =============================================================================
// SUPPORT STATUSES
// =============================================================================

export const TICKET_STATUSES = [
  'open',
  'pending',
  'in_progress',
  'resolved',
  'closed',
] as const;
export type TicketStatus = (typeof TICKET_STATUSES)[number];

export const TICKET_PRIORITIES = ['low', 'medium', 'high', 'urgent'] as const;
export type TicketPriority = (typeof TICKET_PRIORITIES)[number];

// =============================================================================
// HR STATUSES
// =============================================================================

export const EMPLOYEE_STATUSES = ['active', 'inactive', 'on_leave', 'terminated'] as const;
export type EmployeeStatus = (typeof EMPLOYEE_STATUSES)[number];

export const LEAVE_STATUSES = ['pending', 'approved', 'rejected', 'cancelled'] as const;
export type LeaveStatus = (typeof LEAVE_STATUSES)[number];

export const APPLICANT_STATUSES = [
  'new',
  'screened',
  'interviewed',
  'offered',
  'hired',
  'rejected',
  'withdrawn',
] as const;
export type ApplicantStatus = (typeof APPLICANT_STATUSES)[number];

// =============================================================================
// INVENTORY STATUSES
// =============================================================================

export const ITEM_STATUSES = ['active', 'inactive', 'discontinued'] as const;
export type ItemStatus = (typeof ITEM_STATUSES)[number];

export const TRANSFER_STATUSES = ['draft', 'pending', 'in_transit', 'received', 'cancelled'] as const;
export type TransferStatus = (typeof TRANSFER_STATUSES)[number];

// =============================================================================
// PROJECTS STATUSES
// =============================================================================

export const PROJECT_STATUSES = [
  'planning',
  'active',
  'on_hold',
  'completed',
  'cancelled',
] as const;
export type ProjectStatus = (typeof PROJECT_STATUSES)[number];

export const TASK_STATUSES = [
  'todo',
  'in_progress',
  'review',
  'completed',
  'blocked',
] as const;
export type TaskStatus = (typeof TASK_STATUSES)[number];

// =============================================================================
// COMMON STATUSES
// =============================================================================

export const ACTIVE_STATUSES = ['active', 'inactive'] as const;
export type ActiveStatus = (typeof ACTIVE_STATUSES)[number];

export const PAYMENT_STATUSES = [
  'pending',
  'processing',
  'completed',
  'failed',
  'refunded',
] as const;
export type PaymentStatus = (typeof PAYMENT_STATUSES)[number];

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Get variant for a status string using the central mapping
 */
export function getStatusVariant(status: string): Variant {
  const key = status.toLowerCase().replace(/[_-]/g, '');
  const normalizedKey = status.toLowerCase();
  return STATUS_VARIANT_MAP[normalizedKey] ?? STATUS_VARIANT_MAP[key] ?? 'default';
}

/**
 * Format status for display (title case, replace underscores)
 */
export function formatStatus(status: string): string {
  return status
    .replace(/[_-]/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// =============================================================================
// SELECT OPTIONS GENERATORS
// =============================================================================

interface StatusSelectOption {
  value: string;
  label: string;
}

/**
 * Convert status array to select options with "All" option
 */
function toSelectOptions(
  statuses: readonly string[],
  allLabel = 'All Statuses'
): StatusSelectOption[] {
  return [
    { value: '', label: allLabel },
    ...statuses.map((s) => ({ value: s, label: formatStatus(s) })),
  ];
}

// Pre-built select options
export const INVOICE_STATUS_OPTIONS = toSelectOptions(INVOICE_STATUSES);
export const QUOTATION_STATUS_OPTIONS = toSelectOptions(QUOTATION_STATUSES);
export const SALES_ORDER_STATUS_OPTIONS = toSelectOptions(SALES_ORDER_STATUSES);
export const LEAD_STATUS_OPTIONS = toSelectOptions(LEAD_STATUSES);
export const OPPORTUNITY_STATUS_OPTIONS = toSelectOptions(OPPORTUNITY_STATUSES);
export const BILL_STATUS_OPTIONS = toSelectOptions(BILL_STATUSES);
export const PURCHASE_ORDER_STATUS_OPTIONS = toSelectOptions(PURCHASE_ORDER_STATUSES);
export const TICKET_STATUS_OPTIONS = toSelectOptions(TICKET_STATUSES);
export const TICKET_PRIORITY_OPTIONS = toSelectOptions(TICKET_PRIORITIES, 'All Priorities');
export const EMPLOYEE_STATUS_OPTIONS = toSelectOptions(EMPLOYEE_STATUSES);
export const LEAVE_STATUS_OPTIONS = toSelectOptions(LEAVE_STATUSES);
export const APPLICANT_STATUS_OPTIONS = toSelectOptions(APPLICANT_STATUSES);
export const ITEM_STATUS_OPTIONS = toSelectOptions(ITEM_STATUSES);
export const TRANSFER_STATUS_OPTIONS = toSelectOptions(TRANSFER_STATUSES);
export const PROJECT_STATUS_OPTIONS = toSelectOptions(PROJECT_STATUSES);
export const TASK_STATUS_OPTIONS = toSelectOptions(TASK_STATUSES);
export const ACTIVE_STATUS_OPTIONS = toSelectOptions(ACTIVE_STATUSES, 'All');
export const PAYMENT_STATUS_OPTIONS = toSelectOptions(PAYMENT_STATUSES);
