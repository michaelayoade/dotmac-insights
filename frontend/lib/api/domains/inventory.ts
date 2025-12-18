/**
 * Inventory Domain API
 * Includes: Items, Warehouses, Stock Entries, Ledger, Batches, Serials, Transfers
 */

import { fetchApi } from '../core';

// =============================================================================
// TYPES
// =============================================================================

// Item Types
export interface InventoryItemPayload {
  item_code?: string;
  item_name?: string;
  description?: string | null;
  item_group?: string | null;
  uom?: string | null;
  brand?: string | null;
  is_stock_item?: boolean;
  default_warehouse?: string | null;
  reorder_level?: number | null;
  reorder_qty?: number | null;
  valuation_rate?: number | null;
  standard_selling_rate?: number | null;
  standard_buying_rate?: number | null;
  serial_number_series?: string | null;
  barcode?: string | null;
  status?: string | null;
}

export interface InventoryItem {
  id: number;
  item_code: string;
  item_name: string;
  item_group?: string | null;
  stock_uom?: string | null;
  is_stock_item?: boolean;
  valuation_rate?: number;
  total_stock_qty?: number;
  stock_by_warehouse?: Record<string, number> | null;
}

export interface InventoryItemListResponse {
  total: number;
  limit: number;
  offset: number;
  items: InventoryItem[];
}

// Warehouse Types
export interface InventoryWarehousePayload {
  name?: string;
  parent_warehouse?: string | null;
  company?: string | null;
  is_group?: boolean;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  contact_person?: string | null;
  status?: string | null;
}

export interface InventoryWarehouse {
  id: number;
  erpnext_id?: string | null;
  warehouse_name: string;
  parent_warehouse?: string | null;
  company?: string | null;
  warehouse_type?: string | null;
  is_group?: boolean;
  disabled?: boolean;
  account?: string | null;
}

export interface InventoryWarehouseListResponse {
  total: number;
  limit: number;
  offset: number;
  warehouses: InventoryWarehouse[];
}

// Stock Entry Types
export interface InventoryStockEntryLine {
  item_code: string;
  qty: number;
  uom: string;
  s_warehouse?: string | null;
  t_warehouse?: string | null;
  rate?: number | null;
  serial_nos?: string[] | null;
}

export interface InventoryStockEntryPayload {
  entry_type: 'material_receipt' | 'material_issue' | 'material_transfer';
  posting_date?: string | null;
  company?: string | null;
  remarks?: string | null;
  lines: InventoryStockEntryLine[];
}

export interface InventoryStockEntry {
  id: number;
  erpnext_id?: string | null;
  stock_entry_type: string;
  purpose?: string | null;
  posting_date?: string | null;
  from_warehouse?: string | null;
  to_warehouse?: string | null;
  total_amount?: number;
  docstatus?: number;
  work_order?: string | null;
  purchase_order?: string | null;
  sales_order?: string | null;
}

export interface InventoryStockEntryListResponse {
  total: number;
  limit: number;
  offset: number;
  entries: InventoryStockEntry[];
}

// Stock Ledger Types
export interface InventoryStockLedgerEntry {
  id: number;
  erpnext_id?: string | null;
  item_code: string;
  warehouse: string;
  posting_date?: string | null;
  posting_time?: string | null;
  actual_qty: number;
  qty_after_transaction: number;
  incoming_rate?: number;
  outgoing_rate?: number;
  valuation_rate?: number;
  stock_value?: number;
  stock_value_difference?: number;
  voucher_type?: string | null;
  voucher_no?: string | null;
  batch_no?: string | null;
}

export interface InventoryStockLedgerListResponse {
  total: number;
  limit: number;
  offset: number;
  entries: InventoryStockLedgerEntry[];
}

// Stock Summary Types
export interface InventoryStockSummaryItem {
  item_code: string;
  item_name?: string | null;
  item_group?: string | null;
  stock_uom?: string | null;
  total_qty: number;
  total_value: number;
  valuation_rate?: number;
  warehouses?: Array<{ warehouse: string; qty: number; value: number }>;
}

export interface InventoryStockSummaryResponse {
  total_value: number;
  total_items: number;
  total_qty?: number;
  items: InventoryStockSummaryItem[];
}

// Reorder Alerts
export interface InventoryReorderAlert {
  id: number;
  item_code: string;
  item_name?: string | null;
  item_group?: string | null;
  stock_uom?: string | null;
  reorder_level: number;
  reorder_qty: number;
  safety_stock: number;
  current_stock: number;
  shortage: number;
}

export interface InventoryReorderAlertsResponse {
  total: number;
  alerts: InventoryReorderAlert[];
}

// Transfer Types
export interface InventoryTransferItemPayload {
  item_code: string;
  item_name?: string;
  qty: number;
  uom?: string;
  valuation_rate?: number;
  batch_no?: string;
  serial_no?: string;
}

export interface InventoryTransfer {
  id: number;
  transfer_number?: string | null;
  from_warehouse?: string | null;
  to_warehouse?: string | null;
  request_date?: string | null;
  required_date?: string | null;
  transfer_date?: string | null;
  total_qty: number;
  total_value: number;
  status: string;
  approval_status?: string | null;
  remarks?: string | null;
  created_by?: string | null;
  items?: InventoryTransferItemPayload[];
}

export interface InventoryTransferListResponse {
  total: number;
  limit: number;
  offset: number;
  transfers: InventoryTransfer[];
}

export interface InventoryTransferPayload {
  from_warehouse: string;
  to_warehouse: string;
  required_date?: string;
  remarks?: string;
  items: InventoryTransferItemPayload[];
}

// Batch Types
export interface InventoryBatch {
  id: number;
  batch_id: string;
  item_code?: string | null;
  item_name?: string | null;
  manufacturing_date?: string | null;
  expiry_date?: string | null;
  batch_qty: number;
  supplier?: string | null;
  disabled: boolean;
}

export interface InventoryBatchListResponse {
  total: number;
  limit: number;
  offset: number;
  batches: InventoryBatch[];
}

export interface InventoryBatchPayload {
  batch_id: string;
  item_code: string;
  item_name?: string;
  manufacturing_date?: string;
  expiry_date?: string;
  supplier?: string;
  description?: string;
}

// Serial Number Types
export interface InventorySerial {
  id: number;
  serial_no: string;
  item_code?: string | null;
  item_name?: string | null;
  warehouse?: string | null;
  batch_no?: string | null;
  status: string;
  customer?: string | null;
  delivery_date?: string | null;
  warranty_expiry_date?: string | null;
}

export interface InventorySerialListResponse {
  total: number;
  limit: number;
  offset: number;
  serials: InventorySerial[];
}

export interface InventorySerialPayload {
  serial_no: string;
  item_code: string;
  item_name?: string;
  warehouse?: string;
  batch_no?: string;
  supplier?: string;
  purchase_date?: string;
  warranty_period?: number;
  description?: string;
}

// Valuation Types
export interface InventoryValuation {
  item_code: string;
  item_name?: string;
  warehouse?: string;
  qty: number;
  valuation_rate: number;
  stock_value: number;
}

export interface InventoryValuationDetail {
  item_code: string;
  item_name?: string;
  total_qty: number;
  avg_valuation_rate: number;
  total_value: number;
  by_warehouse: Array<{
    warehouse: string;
    qty: number;
    valuation_rate: number;
    stock_value: number;
  }>;
}

// =============================================================================
// INVENTORY API
// =============================================================================

export const inventoryApi = {
  // -------------------------------------------------------------------------
  // Items
  // -------------------------------------------------------------------------

  /** List inventory items */
  getItems: (params?: {
    item_group?: string;
    warehouse?: string;
    has_stock?: boolean;
    search?: string;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<InventoryItemListResponse>('/inventory/items', { params }),

  /** Get item detail */
  getItemDetail: (id: number | string) =>
    fetchApi<InventoryItem>(`/inventory/items/${id}`),

  /** Create an item */
  createItem: (body: InventoryItemPayload) =>
    fetchApi<InventoryItem>('/inventory/items', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** Update an item */
  updateItem: (id: number | string, body: Partial<InventoryItemPayload>) =>
    fetchApi<InventoryItem>(`/inventory/items/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  /** Delete an item */
  deleteItem: (id: number | string) =>
    fetchApi<void>(`/inventory/items/${id}`, { method: 'DELETE' }),

  // -------------------------------------------------------------------------
  // Warehouses
  // -------------------------------------------------------------------------

  /** List warehouses */
  getWarehouses: (params?: {
    include_disabled?: boolean;
    is_group?: boolean;
    company?: string;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<InventoryWarehouseListResponse>('/inventory/warehouses', { params }),

  /** Get warehouse detail */
  getWarehouseDetail: (id: number | string) =>
    fetchApi<InventoryWarehouse>(`/inventory/warehouses/${id}`),

  /** Create a warehouse */
  createWarehouse: (body: InventoryWarehousePayload) =>
    fetchApi<InventoryWarehouse>('/inventory/warehouses', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** Update a warehouse */
  updateWarehouse: (id: number | string, body: Partial<InventoryWarehousePayload>) =>
    fetchApi<InventoryWarehouse>(`/inventory/warehouses/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  /** Delete a warehouse */
  deleteWarehouse: (id: number | string) =>
    fetchApi<void>(`/inventory/warehouses/${id}`, { method: 'DELETE' }),

  // -------------------------------------------------------------------------
  // Stock Entries
  // -------------------------------------------------------------------------

  /** List stock entries */
  getStockEntries: (params?: {
    stock_entry_type?: string;
    from_warehouse?: string;
    to_warehouse?: string;
    start_date?: string;
    end_date?: string;
    docstatus?: number;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<InventoryStockEntryListResponse>('/inventory/stock-entries', { params }),

  /** Get stock entry detail */
  getStockEntryDetail: (id: number | string) =>
    fetchApi<InventoryStockEntry>(`/inventory/stock-entries/${id}`),

  /** Create a stock entry */
  createStockEntry: (body: InventoryStockEntryPayload) =>
    fetchApi<InventoryStockEntry>('/inventory/stock-entries', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** Update a stock entry */
  updateStockEntry: (
    id: number | string,
    body: { posting_date?: string; remarks?: string; docstatus?: number }
  ) =>
    fetchApi<InventoryStockEntry>(`/inventory/stock-entries/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  /** Delete a stock entry */
  deleteStockEntry: (id: number | string) =>
    fetchApi<void>(`/inventory/stock-entries/${id}`, { method: 'DELETE' }),

  /** Post stock entry to GL */
  postStockEntryToGL: (id: number | string) =>
    fetchApi<{ status: string }>(`/inventory/stock-entries/${id}/post-gl`, {
      method: 'POST',
    }),

  // -------------------------------------------------------------------------
  // Stock Ledger
  // -------------------------------------------------------------------------

  /** Get stock ledger entries */
  getStockLedger: (params?: {
    item_code?: string;
    warehouse?: string;
    voucher_type?: string;
    voucher_no?: string;
    start_date?: string;
    end_date?: string;
    include_cancelled?: boolean;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<InventoryStockLedgerListResponse>('/inventory/stock-ledger', { params }),

  // -------------------------------------------------------------------------
  // Stock Summary
  // -------------------------------------------------------------------------

  /** Get stock summary */
  getStockSummary: (params?: { warehouse?: string; item_group?: string }) =>
    fetchApi<InventoryStockSummaryResponse>('/inventory/summary', { params }),

  // -------------------------------------------------------------------------
  // Valuation
  // -------------------------------------------------------------------------

  /** Get inventory valuation */
  getValuation: (params?: Record<string, string | number | boolean | undefined>) =>
    fetchApi<InventoryValuation[]>('/inventory/valuation', { params }),

  /** Get valuation detail for an item */
  getValuationDetail: (
    itemCode: string,
    params?: Record<string, string | number | boolean | undefined>
  ) =>
    fetchApi<InventoryValuationDetail>(`/inventory/valuation/${itemCode}`, { params }),

  // -------------------------------------------------------------------------
  // Reorder Alerts
  // -------------------------------------------------------------------------

  /** Get reorder alerts */
  getReorderAlerts: (params?: { limit?: number }) =>
    fetchApi<InventoryReorderAlertsResponse>('/inventory/reorder-alerts', { params }),

  // -------------------------------------------------------------------------
  // Transfers
  // -------------------------------------------------------------------------

  /** List transfer requests */
  getTransfers: (params?: {
    status?: string;
    from_warehouse?: string;
    to_warehouse?: string;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<InventoryTransferListResponse>('/inventory/transfers', { params }),

  /** Create a transfer request */
  createTransfer: (body: InventoryTransferPayload) =>
    fetchApi<InventoryTransfer>('/inventory/transfers', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** Submit a transfer request */
  submitTransfer: (id: number | string) =>
    fetchApi<InventoryTransfer>(`/inventory/transfers/${id}/submit`, { method: 'POST' }),

  /** Approve a transfer request */
  approveTransfer: (id: number | string) =>
    fetchApi<InventoryTransfer>(`/inventory/transfers/${id}/approve`, { method: 'POST' }),

  /** Reject a transfer request */
  rejectTransfer: (id: number | string, reason: string) =>
    fetchApi<InventoryTransfer>(`/inventory/transfers/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  /** Execute a transfer request */
  executeTransfer: (id: number | string) =>
    fetchApi<InventoryTransfer>(`/inventory/transfers/${id}/execute`, { method: 'POST' }),

  // -------------------------------------------------------------------------
  // Batches
  // -------------------------------------------------------------------------

  /** List batches */
  getBatches: (params?: {
    item_code?: string;
    include_disabled?: boolean;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<InventoryBatchListResponse>('/inventory/batches', { params }),

  /** Create a batch */
  createBatch: (body: InventoryBatchPayload) =>
    fetchApi<InventoryBatch>('/inventory/batches', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  // -------------------------------------------------------------------------
  // Serial Numbers
  // -------------------------------------------------------------------------

  /** List serial numbers */
  getSerials: (params?: {
    item_code?: string;
    warehouse?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<InventorySerialListResponse>('/inventory/serials', { params }),

  /** Create a serial number */
  createSerial: (body: InventorySerialPayload) =>
    fetchApi<InventorySerial>('/inventory/serials', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
};

// =============================================================================
// STANDALONE EXPORTS (for backward compatibility)
// =============================================================================

// Items
export const getInventoryItems = inventoryApi.getItems;
export const getInventoryItemDetail = inventoryApi.getItemDetail;
export const createInventoryItem = inventoryApi.createItem;
export const updateInventoryItem = inventoryApi.updateItem;
export const deleteInventoryItem = inventoryApi.deleteItem;

// Warehouses
export const getInventoryWarehouses = inventoryApi.getWarehouses;
export const getInventoryWarehouseDetail = inventoryApi.getWarehouseDetail;
export const createInventoryWarehouse = inventoryApi.createWarehouse;
export const updateInventoryWarehouse = inventoryApi.updateWarehouse;
export const deleteInventoryWarehouse = inventoryApi.deleteWarehouse;

// Stock Entries
export const getInventoryStockEntries = inventoryApi.getStockEntries;
export const getInventoryStockEntryDetail = inventoryApi.getStockEntryDetail;
export const createInventoryStockEntry = inventoryApi.createStockEntry;
export const updateInventoryStockEntry = inventoryApi.updateStockEntry;
export const deleteInventoryStockEntry = inventoryApi.deleteStockEntry;
export const postInventoryStockEntryToGL = inventoryApi.postStockEntryToGL;

// Stock Ledger
export const getInventoryStockLedger = inventoryApi.getStockLedger;

// Stock Summary
export const getInventoryStockSummary = inventoryApi.getStockSummary;

// Valuation
export const getInventoryValuation = inventoryApi.getValuation;
export const getInventoryValuationDetail = inventoryApi.getValuationDetail;

// Reorder Alerts
export const getInventoryReorderAlerts = inventoryApi.getReorderAlerts;

// Transfers
export const getInventoryTransfers = inventoryApi.getTransfers;
export const createInventoryTransfer = inventoryApi.createTransfer;
export const submitInventoryTransfer = inventoryApi.submitTransfer;
export const approveInventoryTransfer = inventoryApi.approveTransfer;
export const rejectInventoryTransfer = inventoryApi.rejectTransfer;
export const executeInventoryTransfer = inventoryApi.executeTransfer;

// Batches
export const getInventoryBatches = inventoryApi.getBatches;
export const createInventoryBatch = inventoryApi.createBatch;

// Serials
export const getInventorySerials = inventoryApi.getSerials;
export const createInventorySerial = inventoryApi.createSerial;
