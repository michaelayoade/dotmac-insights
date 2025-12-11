"""
Zoho Books CSV Import Service

Imports accounting data from Zoho Books CSV exports into the database.
Supports: Bank Transactions, Journal Entries (GL Entries), Suppliers, Chart of Accounts
"""

from __future__ import annotations

import csv
import os
import structlog
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple

from sqlalchemy.orm import Session

from app.models.accounting import (
    Account,
    AccountType,
    BankTransaction,
    BankTransactionStatus,
    GLEntry,
    Supplier,
    JournalEntry,
    JournalEntryType,
)

logger = structlog.get_logger(__name__)


def parse_zoho_date(date_str: str) -> Optional[datetime]:
    """Parse date from Zoho Books format (DD/MM/YYYY)."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%d/%m/%Y")
    except ValueError:
        try:
            return datetime.strptime(date_str.strip(), "%Y-%m-%d")
        except ValueError:
            logger.warning("Could not parse date", date_str=date_str)
            return None


def parse_decimal(value: str) -> Decimal:
    """Parse decimal value from string, handling various formats."""
    if not value or value.strip() == "":
        return Decimal("0")
    try:
        # Remove commas and currency symbols
        cleaned = value.replace(",", "").replace("₦", "").replace("$", "").strip()
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        logger.warning("Could not parse decimal", value=value)
        return Decimal("0")


def map_account_type(account_group: str, account_type: str) -> Optional[AccountType]:
    """Map Zoho account types to our enum."""
    type_mapping = {
        "asset": AccountType.ASSET,
        "liability": AccountType.LIABILITY,
        "equity": AccountType.EQUITY,
        "income": AccountType.INCOME,
        "expense": AccountType.EXPENSE,
    }

    # Try account_group first, then account_type
    group_lower = (account_group or "").lower()
    type_lower = (account_type or "").lower()

    return type_mapping.get(group_lower) or type_mapping.get(type_lower)


class ZohoImportService:
    """Service to import Zoho Books CSV data."""

    def __init__(self, db: Session):
        self.db = db
        self.stats = {
            "bank_transactions": {"created": 0, "updated": 0, "errors": 0},
            "gl_entries": {"created": 0, "updated": 0, "errors": 0},
            "accounts": {"created": 0, "updated": 0, "errors": 0},
            "suppliers": {"created": 0, "updated": 0, "errors": 0},
        }

    def import_bank_transactions_from_csv(self, file_path: str) -> Dict[str, int]:
        """
        Import bank transactions from a Zoho Books CSV file.

        CSV columns expected:
        date, account_name, transaction_details, transaction_id, reference_transaction_id,
        offset_account_id, offset_account_type, transaction_type, reference_number,
        entity_number, debit, credit, net_amount, contact_id, account_id, project_ids,
        currency_code, account_group, account_type, branch_name
        """
        logger.info("Importing bank transactions", file_path=file_path)

        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    try:
                        self._process_bank_transaction_row(row)
                    except Exception as e:
                        logger.error("Error processing bank transaction row", error=str(e), row=row)
                        self.stats["bank_transactions"]["errors"] += 1

                self.db.commit()
        except Exception as e:
            logger.error("Error reading CSV file", error=str(e), file_path=file_path)
            self.db.rollback()
            raise

        return self.stats["bank_transactions"]

    def _process_bank_transaction_row(self, row: Dict[str, str]) -> None:
        """Process a single bank transaction row."""
        transaction_id = row.get("transaction_id", "").strip()
        if not transaction_id:
            return

        # Check for existing transaction
        existing = self.db.query(BankTransaction).filter(
            BankTransaction.transaction_id == transaction_id
        ).first()

        date = parse_zoho_date(row.get("date", ""))
        debit = parse_decimal(row.get("debit", "0"))
        credit = parse_decimal(row.get("credit", "0"))

        if existing:
            existing.date = date
            existing.bank_account = row.get("account_name", "")
            existing.deposit = credit  # Credits are deposits in bank
            existing.withdrawal = debit  # Debits are withdrawals in bank
            existing.description = row.get("transaction_details", "")
            existing.reference_number = row.get("reference_number", "")
            existing.transaction_type = row.get("transaction_type", "")
            existing.currency = row.get("currency_code", "NGN") or "NGN"
            existing.party = row.get("transaction_details", "")
            self.stats["bank_transactions"]["updated"] += 1
        else:
            txn = BankTransaction(
                transaction_id=transaction_id,
                date=date,
                bank_account=row.get("account_name", ""),
                deposit=credit,
                withdrawal=debit,
                description=row.get("transaction_details", ""),
                reference_number=row.get("reference_number", ""),
                transaction_type=row.get("transaction_type", ""),
                currency=row.get("currency_code", "NGN") or "NGN",
                party=row.get("transaction_details", ""),
                status=BankTransactionStatus.SETTLED,
            )
            self.db.add(txn)
            self.stats["bank_transactions"]["created"] += 1

    def import_gl_entries_from_csv(self, file_path: str) -> Dict[str, int]:
        """
        Import GL entries (journal entries) from a Zoho Books CSV file.
        These represent the actual ledger entries for all transaction types.
        """
        logger.info("Importing GL entries", file_path=file_path)

        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    try:
                        self._process_gl_entry_row(row)
                    except Exception as e:
                        logger.error("Error processing GL entry row", error=str(e), row=row)
                        self.stats["gl_entries"]["errors"] += 1

                self.db.commit()
        except Exception as e:
            logger.error("Error reading CSV file", error=str(e), file_path=file_path)
            self.db.rollback()
            raise

        return self.stats["gl_entries"]

    def _process_gl_entry_row(self, row: Dict[str, str]) -> None:
        """Process a single GL entry row."""
        transaction_id = row.get("transaction_id", "").strip()
        account_name = row.get("account_name", "").strip()

        if not transaction_id or not account_name:
            return

        # Create a unique ID combining transaction_id and account
        unique_id = f"zoho-{transaction_id}-{hash(account_name)}"

        # Check for existing entry
        existing = self.db.query(GLEntry).filter(
            GLEntry.erpnext_id == unique_id
        ).first()

        date = parse_zoho_date(row.get("date", ""))
        debit = parse_decimal(row.get("debit", "0"))
        credit = parse_decimal(row.get("credit", "0"))

        if existing:
            existing.posting_date = date
            existing.account = account_name
            existing.debit = debit
            existing.credit = credit
            existing.voucher_type = row.get("transaction_type", "")
            existing.voucher_no = row.get("reference_number", "")
            existing.party = row.get("transaction_details", "")
            self.stats["gl_entries"]["updated"] += 1
        else:
            entry = GLEntry(
                erpnext_id=unique_id,
                posting_date=date,
                account=account_name,
                debit=debit,
                credit=credit,
                debit_in_account_currency=debit,
                credit_in_account_currency=credit,
                voucher_type=row.get("transaction_type", ""),
                voucher_no=row.get("reference_number", ""),
                party=row.get("transaction_details", ""),
                fiscal_year=str(date.year) if date else None,
            )
            self.db.add(entry)
            self.stats["gl_entries"]["created"] += 1

    def import_suppliers_from_csv(self, file_path: str) -> Dict[str, int]:
        """
        Import suppliers from Accounts Payable CSV.
        Extracts unique supplier names from transaction details.
        """
        logger.info("Importing suppliers from AP data", file_path=file_path)

        suppliers_seen: Dict[str, bool] = {}

        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    try:
                        supplier_name = row.get("transaction_details", "").strip()
                        if not supplier_name or supplier_name in suppliers_seen:
                            continue

                        suppliers_seen[supplier_name] = True
                        self._process_supplier(supplier_name, row)
                    except Exception as e:
                        logger.error("Error processing supplier row", error=str(e))
                        self.stats["suppliers"]["errors"] += 1

                self.db.commit()
        except Exception as e:
            logger.error("Error reading CSV file", error=str(e), file_path=file_path)
            self.db.rollback()
            raise

        return self.stats["suppliers"]

    def _process_supplier(self, supplier_name: str, row: Dict[str, str]) -> None:
        """Process a single supplier."""
        # Check for existing supplier
        existing = self.db.query(Supplier).filter(
            Supplier.supplier_name == supplier_name
        ).first()

        currency = row.get("currency_code", "NGN") or "NGN"

        if existing:
            existing.default_currency = currency
            self.stats["suppliers"]["updated"] += 1
        else:
            supplier = Supplier(
                supplier_name=supplier_name,
                default_currency=currency,
                supplier_group="Zoho Import",
            )
            self.db.add(supplier)
            self.stats["suppliers"]["created"] += 1

    def import_accounts_from_directory(self, base_dir: str) -> Dict[str, int]:
        """
        Import chart of accounts by scanning the Finance Documents directory structure.
        Each folder represents an account category, and CSV files are sub-accounts.
        """
        logger.info("Importing accounts from directory structure", base_dir=base_dir)

        # Map folder names to account types
        folder_type_mapping = {
            "BANK": AccountType.ASSET,
            "CASH": AccountType.ASSET,
            "INCOME": AccountType.INCOME,
            "COST OF GOODS SOLD": AccountType.EXPENSE,
            "OTHER CURRENT LIABILITY": AccountType.LIABILITY,
            "LONG TERM LIABILITY": AccountType.LIABILITY,
            "ACCOUNT PAYABLES": AccountType.LIABILITY,
            "OTHER INCOME": AccountType.INCOME,
            "Accounts Receivable": AccountType.ASSET,
            "Equity": AccountType.EQUITY,
            "Fixed Assets": AccountType.ASSET,
            "Input Tax": AccountType.ASSET,
            "Output Tax": AccountType.LIABILITY,
            "Other Current Assets 2022-2024": AccountType.ASSET,
            "Other Expense": AccountType.EXPENSE,
            "Payment Clearing Account": AccountType.ASSET,
            "Stock": AccountType.ASSET,
        }

        try:
            for folder in os.listdir(base_dir):
                folder_path = os.path.join(base_dir, folder)
                if not os.path.isdir(folder_path):
                    continue

                account_type = folder_type_mapping.get(folder, AccountType.ASSET)

                # Create parent account for the folder
                self._ensure_account(folder, account_type, is_group=True)

                # Process CSV files as child accounts
                for filename in os.listdir(folder_path):
                    if filename.endswith(".csv"):
                        account_name = filename.replace(".csv", "")
                        self._ensure_account(account_name, account_type, parent=folder)

            self.db.commit()
        except Exception as e:
            logger.error("Error importing accounts", error=str(e))
            self.db.rollback()
            raise

        return self.stats["accounts"]

    def _ensure_account(
        self,
        name: str,
        root_type: AccountType,
        parent: Optional[str] = None,
        is_group: bool = False
    ) -> Account:
        """Ensure an account exists, creating if necessary."""
        existing = self.db.query(Account).filter(
            Account.account_name == name
        ).first()

        if existing:
            self.stats["accounts"]["updated"] += 1
            return existing

        account = Account(
            account_name=name,
            root_type=root_type,
            parent_account=parent,
            is_group=is_group,
        )
        self.db.add(account)
        self.stats["accounts"]["created"] += 1
        return account

    def import_all_from_directory(self, zoho_export_dir: str) -> Dict[str, Dict[str, int]]:
        """
        Import all available data from a Zoho Books export directory.

        Expected structure:
        zoho_export_dir/
          ├── Finance Documents/
          │   ├── BANK/
          │   │   └── *.csv (bank transaction files)
          │   ├── INCOME/
          │   │   └── *.csv
          │   ├── ACCOUNT PAYABLES/
          │   │   └── Accounts Payable.csv
          │   └── ...
          └── Chart Of Accounts/
              └── *.csv
        """
        logger.info("Starting full Zoho Books import", directory=zoho_export_dir)

        finance_docs = os.path.join(zoho_export_dir, "Finance Documents")
        chart_of_accounts = os.path.join(zoho_export_dir, "Chart Of Accounts")

        # Import accounts from directory structure
        if os.path.exists(finance_docs):
            self.import_accounts_from_directory(finance_docs)

        if os.path.exists(chart_of_accounts):
            self.import_accounts_from_directory(chart_of_accounts)

        # Import bank transactions
        bank_dir = os.path.join(finance_docs, "BANK")
        if os.path.exists(bank_dir):
            for filename in os.listdir(bank_dir):
                if filename.endswith(".csv"):
                    file_path = os.path.join(bank_dir, filename)
                    self.import_bank_transactions_from_csv(file_path)

        # Import GL entries from all account folders
        if os.path.exists(finance_docs):
            for folder in os.listdir(finance_docs):
                folder_path = os.path.join(finance_docs, folder)
                if not os.path.isdir(folder_path):
                    continue

                for filename in os.listdir(folder_path):
                    if filename.endswith(".csv"):
                        file_path = os.path.join(folder_path, filename)
                        self.import_gl_entries_from_csv(file_path)

        # Import suppliers from AP
        ap_file = os.path.join(finance_docs, "ACCOUNT PAYABLES", "Accounts Payable.csv")
        if os.path.exists(ap_file):
            self.import_suppliers_from_csv(ap_file)

        logger.info("Zoho Books import completed", stats=self.stats)
        return self.stats
