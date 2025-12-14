/**
 * CSV Parser for bank transaction imports
 */

export interface ParsedCSVRow {
  [key: string]: string;
}

export interface CSVParseResult {
  headers: string[];
  rows: ParsedCSVRow[];
  rowCount: number;
}

export interface CSVColumnMapping {
  date_column: string;
  amount_column?: string;
  deposit_column?: string;
  withdrawal_column?: string;
  description_column?: string;
  reference_column?: string;
}

export interface MappedTransaction {
  transaction_date: string;
  amount: number;
  transaction_type: 'deposit' | 'withdrawal';
  description: string;
  reference_number: string;
}

/**
 * Parse a CSV line handling quoted fields
 */
function parseCSVLine(line: string): string[] {
  const result: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    const nextChar = line[i + 1];

    if (char === '"') {
      if (inQuotes && nextChar === '"') {
        // Escaped quote inside quoted string
        current += '"';
        i++; // Skip next quote
      } else {
        // Toggle quote state
        inQuotes = !inQuotes;
      }
    } else if (char === ',' && !inQuotes) {
      result.push(current.trim());
      current = '';
    } else {
      current += char;
    }
  }
  result.push(current.trim());
  return result;
}

/**
 * Parse CSV content into headers and rows
 */
export function parseCSV(content: string): CSVParseResult {
  // Normalize line endings
  const normalizedContent = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  const lines = normalizedContent.split('\n').filter((line) => line.trim());

  if (lines.length === 0) {
    return { headers: [], rows: [], rowCount: 0 };
  }

  const headers = parseCSVLine(lines[0]);
  const rows: ParsedCSVRow[] = [];

  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVLine(lines[i]);
    // Skip empty rows
    if (values.every((v) => !v.trim())) continue;

    const row: ParsedCSVRow = {};
    headers.forEach((header, index) => {
      row[header] = values[index] || '';
    });
    rows.push(row);
  }

  return { headers, rows, rowCount: rows.length };
}

/**
 * Attempt to parse a date string in various formats
 */
function parseDate(dateStr: string): string {
  if (!dateStr) return '';

  // Remove extra whitespace
  dateStr = dateStr.trim();

  // Try ISO format first (YYYY-MM-DD)
  if (/^\d{4}-\d{2}-\d{2}/.test(dateStr)) {
    return dateStr.slice(0, 10);
  }

  // Try DD/MM/YYYY or DD-MM-YYYY
  const dmyMatch = dateStr.match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})/);
  if (dmyMatch) {
    const [, day, month, year] = dmyMatch;
    return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
  }

  // Try MM/DD/YYYY or MM-DD-YYYY
  const mdyMatch = dateStr.match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})/);
  if (mdyMatch) {
    const [, month, day, year] = mdyMatch;
    return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
  }

  // Try parsing with Date
  const parsed = new Date(dateStr);
  if (!isNaN(parsed.getTime())) {
    return parsed.toISOString().slice(0, 10);
  }

  return dateStr;
}

/**
 * Parse amount string removing currency symbols and handling negative values
 */
function parseAmount(amountStr: string): number {
  if (!amountStr) return 0;

  // Remove currency symbols and thousand separators
  let cleaned = amountStr
    .replace(/[₦$€£¥]/g, '')
    .replace(/,/g, '')
    .trim();

  // Handle parentheses as negative (accounting notation)
  if (cleaned.startsWith('(') && cleaned.endsWith(')')) {
    cleaned = '-' + cleaned.slice(1, -1);
  }

  const value = parseFloat(cleaned);
  return isNaN(value) ? 0 : value;
}

/**
 * Map parsed CSV rows to transaction objects using the column mapping
 */
export function mapCSVToTransactions(rows: ParsedCSVRow[], mapping: CSVColumnMapping): MappedTransaction[] {
  return rows
    .map((row) => {
      let amount = 0;
      let type: 'deposit' | 'withdrawal' = 'deposit';

      if (mapping.amount_column) {
        // Single amount column (positive = deposit, negative = withdrawal)
        const rawAmount = parseAmount(row[mapping.amount_column] || '');
        amount = Math.abs(rawAmount);
        type = rawAmount >= 0 ? 'deposit' : 'withdrawal';
      } else if (mapping.deposit_column || mapping.withdrawal_column) {
        // Separate deposit/withdrawal columns
        const deposit = parseAmount(row[mapping.deposit_column || ''] || '');
        const withdrawal = parseAmount(row[mapping.withdrawal_column || ''] || '');

        if (deposit > 0) {
          amount = deposit;
          type = 'deposit';
        } else if (withdrawal > 0) {
          amount = withdrawal;
          type = 'withdrawal';
        }
      }

      return {
        transaction_date: parseDate(row[mapping.date_column] || ''),
        amount,
        transaction_type: type,
        description: row[mapping.description_column || ''] || '',
        reference_number: row[mapping.reference_column || ''] || '',
      };
    })
    .filter((tx) => tx.amount > 0 && tx.transaction_date); // Filter out invalid transactions
}

/**
 * Auto-detect column mapping based on header names
 */
export function autoDetectMapping(headers: string[]): Partial<CSVColumnMapping> {
  const mapping: Partial<CSVColumnMapping> = {};

  const lowerHeaders = headers.map((h) => h.toLowerCase());

  // Date column detection
  const datePatterns = ['date', 'transaction date', 'posting date', 'value date', 'trans date'];
  for (const pattern of datePatterns) {
    const idx = lowerHeaders.findIndex((h) => h.includes(pattern));
    if (idx >= 0) {
      mapping.date_column = headers[idx];
      break;
    }
  }

  // Amount column detection
  const amountPatterns = ['amount', 'value', 'sum', 'total'];
  for (const pattern of amountPatterns) {
    const idx = lowerHeaders.findIndex((h) => h === pattern || h.includes(pattern));
    if (idx >= 0 && !lowerHeaders[idx].includes('deposit') && !lowerHeaders[idx].includes('withdrawal')) {
      mapping.amount_column = headers[idx];
      break;
    }
  }

  // Deposit column detection
  const depositPatterns = ['deposit', 'credit', 'money in', 'cr'];
  for (const pattern of depositPatterns) {
    const idx = lowerHeaders.findIndex((h) => h.includes(pattern));
    if (idx >= 0) {
      mapping.deposit_column = headers[idx];
      break;
    }
  }

  // Withdrawal column detection
  const withdrawalPatterns = ['withdrawal', 'debit', 'money out', 'dr'];
  for (const pattern of withdrawalPatterns) {
    const idx = lowerHeaders.findIndex((h) => h.includes(pattern));
    if (idx >= 0) {
      mapping.withdrawal_column = headers[idx];
      break;
    }
  }

  // Description column detection
  const descPatterns = ['description', 'narrative', 'details', 'memo', 'particulars', 'remarks'];
  for (const pattern of descPatterns) {
    const idx = lowerHeaders.findIndex((h) => h.includes(pattern));
    if (idx >= 0) {
      mapping.description_column = headers[idx];
      break;
    }
  }

  // Reference column detection
  const refPatterns = ['reference', 'ref', 'transaction id', 'trans id', 'check', 'cheque'];
  for (const pattern of refPatterns) {
    const idx = lowerHeaders.findIndex((h) => h.includes(pattern));
    if (idx >= 0) {
      mapping.reference_column = headers[idx];
      break;
    }
  }

  return mapping;
}

/**
 * Validate column mapping
 */
export function validateMapping(mapping: CSVColumnMapping): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  if (!mapping.date_column) {
    errors.push('Date column is required');
  }

  if (!mapping.amount_column && !mapping.deposit_column && !mapping.withdrawal_column) {
    errors.push('Either Amount column or Deposit/Withdrawal columns are required');
  }

  return { valid: errors.length === 0, errors };
}
