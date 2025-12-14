/**
 * OFX (Open Financial Exchange) Parser for bank transaction imports
 * Supports OFX 1.x (SGML-like) and OFX 2.x (XML) formats
 * Also handles QFX (Quicken Financial Exchange) files
 */

export interface OFXTransaction {
  fitid: string; // Financial institution transaction ID
  dtposted: string; // Transaction date (ISO format)
  trnamt: number; // Amount (positive = deposit, negative = withdrawal)
  trntype: string; // Transaction type (CREDIT, DEBIT, CHECK, etc.)
  name?: string; // Payee name
  memo?: string; // Memo/description
  checknum?: string; // Check number
}

export interface OFXParseResult {
  bankId?: string;
  branchId?: string;
  accountId?: string;
  accountType?: string;
  currency?: string;
  statementStart?: string;
  statementEnd?: string;
  ledgerBalance?: number;
  availableBalance?: number;
  transactions: OFXTransaction[];
}

export interface MappedOFXTransaction {
  transaction_date: string;
  amount: number;
  transaction_type: 'deposit' | 'withdrawal';
  description: string;
  reference_number: string;
}

/**
 * Extract a tag value from OFX content
 * Works with both SGML-style (<TAG>value) and XML-style (<TAG>value</TAG>)
 */
function extractTag(content: string, tag: string): string {
  // Try XML-style first: <TAG>value</TAG>
  const xmlRegex = new RegExp(`<${tag}>([^<]*)</${tag}>`, 'i');
  const xmlMatch = content.match(xmlRegex);
  if (xmlMatch) {
    return xmlMatch[1].trim();
  }

  // Try SGML-style: <TAG>value (no closing tag, value ends at newline or next tag)
  const sgmlRegex = new RegExp(`<${tag}>([^<\\n\\r]+)`, 'i');
  const sgmlMatch = content.match(sgmlRegex);
  if (sgmlMatch) {
    return sgmlMatch[1].trim();
  }

  return '';
}

/**
 * Parse OFX date format (YYYYMMDDHHMMSS or YYYYMMDD) to ISO date
 */
function parseOFXDate(dateStr: string): string {
  if (!dateStr || dateStr.length < 8) return '';

  // Remove timezone info if present (e.g., [0:GMT])
  const cleanDate = dateStr.replace(/\[.*\]/, '').trim();

  const year = cleanDate.slice(0, 4);
  const month = cleanDate.slice(4, 6);
  const day = cleanDate.slice(6, 8);

  // Validate the parsed date
  const parsed = new Date(`${year}-${month}-${day}`);
  if (isNaN(parsed.getTime())) return '';

  return `${year}-${month}-${day}`;
}

/**
 * Parse OFX content into structured data
 */
export function parseOFX(content: string): OFXParseResult {
  const result: OFXParseResult = {
    transactions: [],
  };

  // Remove XML declaration and SGML header if present
  let xmlContent = content;
  const ofxStart = content.indexOf('<OFX>');
  if (ofxStart >= 0) {
    xmlContent = content.slice(ofxStart);
  }

  // Extract bank account info
  result.bankId = extractTag(xmlContent, 'BANKID');
  result.branchId = extractTag(xmlContent, 'BRANCHID');
  result.accountId = extractTag(xmlContent, 'ACCTID');
  result.accountType = extractTag(xmlContent, 'ACCTTYPE');
  result.currency = extractTag(xmlContent, 'CURDEF');

  // Extract statement dates
  result.statementStart = parseOFXDate(extractTag(xmlContent, 'DTSTART'));
  result.statementEnd = parseOFXDate(extractTag(xmlContent, 'DTEND'));

  // Extract balances
  const ledgerBalStr = extractTag(xmlContent, 'BALAMT');
  if (ledgerBalStr) {
    const ledgerBal = parseFloat(ledgerBalStr);
    if (!isNaN(ledgerBal)) result.ledgerBalance = ledgerBal;
  }

  const availBalStr = extractTag(xmlContent, 'AVAILBAL');
  if (availBalStr) {
    // AVAILBAL might be a container, try to get BALAMT inside it
    const availMatch = xmlContent.match(/<AVAILBAL>([\s\S]*?)(?:<\/AVAILBAL>|<LEDGERBAL>|$)/i);
    if (availMatch) {
      const availBal = parseFloat(extractTag(availMatch[1], 'BALAMT'));
      if (!isNaN(availBal)) result.availableBalance = availBal;
    }
  }

  // Extract all transactions
  // Handle both XML-style and SGML-style STMTTRN blocks
  const trnRegex = /<STMTTRN>([\s\S]*?)(?:<\/STMTTRN>|(?=<STMTTRN>)|(?=<\/BANKTRANLIST>)|$)/gi;
  let match;

  while ((match = trnRegex.exec(xmlContent)) !== null) {
    const block = match[1];

    const transaction: OFXTransaction = {
      fitid: extractTag(block, 'FITID'),
      dtposted: parseOFXDate(extractTag(block, 'DTPOSTED')),
      trnamt: parseFloat(extractTag(block, 'TRNAMT')) || 0,
      trntype: extractTag(block, 'TRNTYPE'),
      name: extractTag(block, 'NAME'),
      memo: extractTag(block, 'MEMO'),
      checknum: extractTag(block, 'CHECKNUM'),
    };

    // Only add valid transactions
    if (transaction.dtposted && transaction.fitid) {
      result.transactions.push(transaction);
    }
  }

  return result;
}

/**
 * Map OFX transactions to our standard format
 */
export function mapOFXToTransactions(ofxResult: OFXParseResult): MappedOFXTransaction[] {
  return ofxResult.transactions
    .map((tx) => {
      const amount = Math.abs(tx.trnamt);
      const type: 'deposit' | 'withdrawal' = tx.trnamt >= 0 ? 'deposit' : 'withdrawal';

      // Build description from name and memo
      let description = '';
      if (tx.name) description = tx.name;
      if (tx.memo) {
        description = description ? `${description} - ${tx.memo}` : tx.memo;
      }

      // Use FITID as reference, or check number if available
      const reference = tx.checknum || tx.fitid;

      return {
        transaction_date: tx.dtposted,
        amount,
        transaction_type: type,
        description,
        reference_number: reference,
      };
    })
    .filter((tx) => tx.amount > 0 && tx.transaction_date);
}

/**
 * Get human-readable account type
 */
export function getAccountTypeLabel(accountType?: string): string {
  if (!accountType) return 'Unknown';

  const types: Record<string, string> = {
    CHECKING: 'Checking',
    SAVINGS: 'Savings',
    MONEYMRKT: 'Money Market',
    CREDITLINE: 'Credit Line',
    CD: 'Certificate of Deposit',
  };

  return types[accountType.toUpperCase()] || accountType;
}

/**
 * Get human-readable transaction type
 */
export function getTransactionTypeLabel(trntype?: string): string {
  if (!trntype) return 'Unknown';

  const types: Record<string, string> = {
    CREDIT: 'Credit',
    DEBIT: 'Debit',
    INT: 'Interest',
    DIV: 'Dividend',
    FEE: 'Fee',
    SRVCHG: 'Service Charge',
    DEP: 'Deposit',
    ATM: 'ATM',
    POS: 'Point of Sale',
    XFER: 'Transfer',
    CHECK: 'Check',
    PAYMENT: 'Payment',
    CASH: 'Cash',
    DIRECTDEP: 'Direct Deposit',
    DIRECTDEBIT: 'Direct Debit',
    REPEATPMT: 'Recurring Payment',
    OTHER: 'Other',
  };

  return types[trntype.toUpperCase()] || trntype;
}

/**
 * Validate OFX parse result
 */
export function validateOFXResult(result: OFXParseResult): { valid: boolean; errors: string[]; warnings: string[] } {
  const errors: string[] = [];
  const warnings: string[] = [];

  if (result.transactions.length === 0) {
    errors.push('No transactions found in the file');
  }

  if (!result.accountId) {
    warnings.push('Account ID could not be extracted from the file');
  }

  if (!result.currency) {
    warnings.push('Currency could not be determined, defaulting to account currency');
  }

  // Check for transactions with missing dates
  const missingDates = result.transactions.filter((tx) => !tx.dtposted).length;
  if (missingDates > 0) {
    warnings.push(`${missingDates} transaction(s) have missing or invalid dates`);
  }

  return { valid: errors.length === 0, errors, warnings };
}

/**
 * Detect if content is OFX format
 */
export function isOFXContent(content: string): boolean {
  return content.includes('<OFX>') || content.includes('OFXHEADER:');
}
