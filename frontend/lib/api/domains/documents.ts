/**
 * Documents Domain API
 * Includes: Document Attachments, Number Formats
 */

import { fetchApi } from '../core';

// =============================================================================
// TYPES
// =============================================================================

export type DocumentType =
  | 'invoice'
  | 'bill'
  | 'payment'
  | 'receipt'
  | 'credit_note'
  | 'debit_note'
  | 'journal_entry'
  | 'purchase_order'
  | 'sales_order'
  | 'quotation'
  | 'delivery_note'
  | 'goods_receipt';

export type ResetFrequency = 'never' | 'yearly' | 'monthly' | 'quarterly';

// Document Attachments
export interface DocumentAttachment {
  id: number;
  doctype: string;
  document_id: number;
  file_name: string;
  file_path: string;
  file_type?: string;
  file_size?: number;
  attachment_type?: string;
  is_primary: boolean;
  description?: string;
  uploaded_at?: string;
  uploaded_by_id?: number;
}

export interface DocumentAttachmentList {
  total: number;
  attachments: DocumentAttachment[];
}

export interface DocumentAttachmentUploadResponse {
  message: string;
  id: number;
  file_name: string;
  file_size: number;
}

export interface UploadAttachmentOptions {
  attachment_type?: string;
  description?: string;
  is_primary?: boolean;
}

export interface UpdateAttachmentPayload {
  description?: string;
  attachment_type?: string;
  is_primary?: boolean;
}

// Document Number Formats
export interface DocumentNumberFormatResponse {
  id: number;
  document_type: DocumentType;
  company: string | null;
  prefix: string;
  format_pattern: string;
  min_digits: number;
  starting_number: number;
  current_number: number;
  reset_frequency: ResetFrequency;
  last_reset_date: string | null;
  last_reset_period: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DocumentNumberFormatCreate {
  document_type: DocumentType;
  company?: string | null;
  prefix: string;
  format_pattern: string;
  min_digits?: number;
  starting_number?: number;
  reset_frequency?: ResetFrequency;
  is_active?: boolean;
}

export interface DocumentNumberFormatUpdate {
  prefix?: string;
  format_pattern?: string;
  min_digits?: number;
  starting_number?: number;
  reset_frequency?: ResetFrequency;
  is_active?: boolean;
}

export interface NumberFormatPreviewRequest {
  format_pattern: string;
  prefix: string;
  min_digits?: number;
  sequence_number?: number;
  posting_date?: string;
}

export interface NumberFormatPreviewResponse {
  preview: string;
  variables_used: string[];
}

export interface NextNumberResponse {
  next_number: string;
  sequence_number: number;
}

// =============================================================================
// DOCUMENTS API
// =============================================================================

export const documentsApi = {
  // -------------------------------------------------------------------------
  // Document Attachments
  // -------------------------------------------------------------------------

  /** Get attachments for a document */
  getDocumentAttachments: (doctype: string, docId: number) =>
    fetchApi<DocumentAttachmentList>(`/accounting/documents/${doctype}/${docId}/attachments`),

  /** Upload an attachment to a document */
  uploadAttachment: async (
    doctype: string,
    docId: number,
    file: File,
    options?: UploadAttachmentOptions
  ) => {
    const formData = new FormData();
    formData.append('file', file);
    if (options?.attachment_type) formData.append('attachment_type', options.attachment_type);
    if (options?.description) formData.append('description', options.description);
    if (options?.is_primary !== undefined) formData.append('is_primary', String(options.is_primary));

    return fetchApi<DocumentAttachmentUploadResponse>(
      `/accounting/documents/${doctype}/${docId}/attachments`,
      { method: 'POST', body: formData }
    );
  },

  /** Get a specific attachment by ID */
  getAttachment: (attachmentId: number) =>
    fetchApi<DocumentAttachment>(`/accounting/attachments/${attachmentId}`),

  /** Delete an attachment */
  deleteAttachment: (attachmentId: number) =>
    fetchApi<void>(`/accounting/attachments/${attachmentId}`, { method: 'DELETE' }),

  /** Update attachment metadata */
  updateAttachment: (attachmentId: number, payload: UpdateAttachmentPayload) =>
    fetchApi<DocumentAttachment>(`/accounting/attachments/${attachmentId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  // -------------------------------------------------------------------------
  // Document Number Formats
  // -------------------------------------------------------------------------

  /** List number formats */
  getNumberFormats: (params?: { document_type?: DocumentType; company?: string }) =>
    fetchApi<DocumentNumberFormatResponse[]>('/books/settings/number-formats', { params }),

  /** Create a number format */
  createNumberFormat: (body: DocumentNumberFormatCreate) =>
    fetchApi<DocumentNumberFormatResponse>('/books/settings/number-formats', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** Get a specific number format */
  getNumberFormat: (id: number) =>
    fetchApi<DocumentNumberFormatResponse>(`/books/settings/number-formats/${id}`),

  /** Update a number format */
  updateNumberFormat: (id: number, body: DocumentNumberFormatUpdate) =>
    fetchApi<DocumentNumberFormatResponse>(`/books/settings/number-formats/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  /** Delete a number format */
  deleteNumberFormat: (id: number) =>
    fetchApi<void>(`/books/settings/number-formats/${id}`, { method: 'DELETE' }),

  /** Preview a number format */
  previewNumberFormat: (body: NumberFormatPreviewRequest) =>
    fetchApi<NumberFormatPreviewResponse>('/books/settings/number-formats/preview', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** Get next number for a document type */
  getNextNumber: (documentType: DocumentType, company?: string) =>
    fetchApi<NextNumberResponse>(`/books/settings/number-formats/next/${documentType}`, {
      params: company ? { company } : undefined,
    }),
};

// =============================================================================
// STANDALONE EXPORTS (for backward compatibility)
// =============================================================================

// Attachments
export const getDocumentAttachments = documentsApi.getDocumentAttachments;
export const uploadAttachment = documentsApi.uploadAttachment;
export const getAttachment = documentsApi.getAttachment;
export const deleteAttachment = documentsApi.deleteAttachment;
export const updateAttachment = documentsApi.updateAttachment;

// Number Formats
export const getNumberFormats = documentsApi.getNumberFormats;
export const createNumberFormat = documentsApi.createNumberFormat;
export const getNumberFormat = documentsApi.getNumberFormat;
export const updateNumberFormat = documentsApi.updateNumberFormat;
export const deleteNumberFormat = documentsApi.deleteNumberFormat;
export const previewNumberFormat = documentsApi.previewNumberFormat;
export const getNextNumber = documentsApi.getNextNumber;
