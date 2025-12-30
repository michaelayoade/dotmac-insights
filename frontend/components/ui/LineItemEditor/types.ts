// =============================================================================
// LINE ITEM EDITOR TYPES
// =============================================================================

export type ColumnType = 'text' | 'number' | 'currency' | 'select' | 'date' | 'checkbox' | 'entity' | 'readonly';

export interface SelectOption {
  value: string | number;
  label: string;
}

export interface LineItemColumn<T> {
  /** Unique key for the column (matches field in row data) */
  key: keyof T;
  /** Column header label */
  header: string;
  /** Column width (CSS value) */
  width?: string;
  /** Column type */
  type: ColumnType;
  /** Options for select type */
  options?: SelectOption[];
  /** Entity type for entity picker */
  entityType?: string;
  /** Whether the column is editable */
  editable?: boolean;
  /** Whether the field is required */
  required?: boolean;
  /** Placeholder text */
  placeholder?: string;
  /** Compute function for derived values */
  compute?: (row: T, allRows: T[], rowIndex: number) => unknown;
  /** Format function for display (readonly columns) */
  format?: (value: unknown, row: T) => string;
  /** Validation function */
  validate?: (value: unknown, row: T) => string | null;
  /** Custom render function */
  render?: (value: unknown, row: T, rowIndex: number, onChange: (value: unknown) => void) => React.ReactNode;
  /** Text alignment */
  align?: 'left' | 'center' | 'right';
  /** Minimum value (for number/currency) */
  min?: number;
  /** Maximum value (for number/currency) */
  max?: number;
  /** Step value (for number) */
  step?: number;
  /** Currency code (for currency type) */
  currency?: string;
  /** Additional class names */
  className?: string;
}

export interface TotalConfig<T> {
  /** Column key to sum */
  key: keyof T;
  /** Label for the total row */
  label: string;
  /** Format function */
  format?: (value: number) => string;
  /** Custom calculation function */
  calculate?: (rows: T[]) => number;
}

export interface LineItemValidation {
  rowIndex: number;
  column: string;
  message: string;
}
