"""
General data import service with connector-based processing for accounting domains.
"""

from __future__ import annotations

import csv
import hashlib
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional

import structlog
from sqlalchemy.orm import Session

from app.config import settings
from app.models.accounting import (
    Account,
    AccountType,
    BankTransaction,
    BankTransactionStatus,
    GLEntry,
    Supplier,
)

logger = structlog.get_logger(__name__)


def parse_import_date(date_str: str) -> Optional[datetime]:
    """Parse common date formats (DD/MM/YYYY or ISO)."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%d/%m/%Y")
    except ValueError:
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            logger.warning("Could not parse date", date_str=date_str)
            return None


def parse_decimal_str(value: str) -> Decimal:
    """Parse decimal value from string, raising on invalid input."""
    if value is None or str(value).strip() == "":
        return Decimal("0")
    try:
        cleaned = str(value).replace(",", "").replace("₦", "").replace("$", "").strip()
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        raise ValueError(f"Could not parse decimal: {value}")


def map_root_type(value: str) -> Optional[AccountType]:
    """Map text root_type to AccountType enum."""
    if value is None:
        return None
    mapping = {
        "asset": AccountType.ASSET,
        "liability": AccountType.LIABILITY,
        "equity": AccountType.EQUITY,
        "income": AccountType.INCOME,
        "expense": AccountType.EXPENSE,
    }
    return mapping.get(value.strip().lower())


class DataImportService:
    """Connector-driven import service."""

    def __init__(self, db: Optional[Session], batch_size: Optional[int] = None, max_errors: int = 100):
        self.db = db
        self.batch_size = batch_size or settings.data_import_batch_size or 1000
        self.max_errors = max_errors
        self.reset_stats()

    def reset_stats(self) -> None:
        self.stats: Dict[str, Dict[str, int]] = {
            "bank_transactions": {"created": 0, "updated": 0, "errors": 0},
            "gl_entries": {"created": 0, "updated": 0, "errors": 0},
            "suppliers": {"created": 0, "updated": 0, "errors": 0},
            "accounts": {"created": 0, "updated": 0, "errors": 0},
        }

    # ------------------------------------------------------------------ Validation
    def validate_rows(self, domain: str, rows: List[Dict[str, str]], max_errors: Optional[int] = None) -> List[str]:
        """Validate schema and parse-ability of rows; returns list of error strings."""
        errors: List[str] = []
        limit = max_errors or self.max_errors
        required = self._required_columns(domain)
        if not rows:
            return ["no rows provided"]
        missing = required.difference(set(rows[0].keys()))
        if missing:
            return [f"missing columns: {', '.join(sorted(missing))}"]

        for idx, row in enumerate(rows, start=1):
            try:
                self._validate_row(domain, row)
            except Exception as e:  # noqa: BLE001
                errors.append(f"row {idx}: {e}")
                if len(errors) >= limit:
                    break
        return errors

    # ------------------------------------------------------------------ Imports
    def import_csv_file(self, domain: str, file_path: str, purge: bool = False) -> Dict[str, int]:
        """Import CSV file for the given domain."""
        self.reset_stats()
        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to read CSV", file_path=file_path, error=str(e))
            raise
        return self.import_rows(domain, rows, purge=purge)

    def import_rows(self, domain: str, rows: List[Dict[str, str]], purge: bool = False) -> Dict[str, int]:
        """Import in-memory rows for the given domain."""
        self.reset_stats()
        required = self._required_columns(domain)
        missing = required.difference(set(rows[0].keys() if rows else []))
        if missing:
            raise ValueError(f"Missing required columns for {domain}: {', '.join(sorted(missing))}")

        if domain == "gl_entries" and purge:
            deleted = self.purge_domain(domain)
            logger.info("Purged existing GL entries before import", deleted=deleted)

        handler_map = {
            "bank_transactions": self._process_bank_transaction_row,
            "gl_entries": self._process_gl_entry_row,
            "suppliers": self._process_supplier_row,
            "accounts": self._process_account_row,
        }
        handler = handler_map.get(domain)
        if not handler:
            raise ValueError(f"Unsupported domain: {domain}")

        processed = 0
        for row in rows:
            try:
                handler(row)
                processed += 1
                self._commit_batch(processed)
            except Exception as e:  # noqa: BLE001
                logger.error("Error processing import row", domain=domain, error=str(e))
                self.stats[domain]["errors"] += 1
        self.db.commit()
        return self.stats[domain]

    # ------------------------------------------------------------------ Domain handlers
    def _process_bank_transaction_row(self, row: Dict[str, str]) -> None:
        transaction_id = (row.get("transaction_id") or "").strip()
        if not transaction_id:
            raise ValueError("transaction_id is required")

        existing = self.db.query(BankTransaction).filter(BankTransaction.transaction_id == transaction_id).first()
        date = parse_import_date(row.get("date", ""))
        debit = parse_decimal_str(row.get("debit", "0"))
        credit = parse_decimal_str(row.get("credit", "0"))

        if existing:
            existing.date = date
            existing.bank_account = row.get("account_name", "")
            existing.deposit = credit
            existing.withdrawal = debit
            existing.description = row.get("description") or row.get("transaction_details", "")
            existing.reference_number = row.get("reference_number", "")
            existing.transaction_type = row.get("transaction_type", "")
            existing.currency = row.get("currency_code", "NGN") or "NGN"
            existing.party = row.get("party") or row.get("transaction_details", "")
            self.stats["bank_transactions"]["updated"] += 1
        else:
            txn = BankTransaction(
                transaction_id=transaction_id,
                date=date,
                bank_account=row.get("account_name", ""),
                deposit=credit,
                withdrawal=debit,
                description=row.get("description") or row.get("transaction_details", ""),
                reference_number=row.get("reference_number", ""),
                transaction_type=row.get("transaction_type", ""),
                currency=row.get("currency_code", "NGN") or "NGN",
                party=row.get("party") or row.get("transaction_details", ""),
                status=BankTransactionStatus.SETTLED,
            )
            self.db.add(txn)
            self.stats["bank_transactions"]["created"] += 1

    def _process_gl_entry_row(self, row: Dict[str, str]) -> None:
        transaction_id = (row.get("transaction_id") or "").strip()
        account_name = (row.get("account_name") or "").strip()
        if not transaction_id or not account_name:
            raise ValueError("transaction_id and account_name are required")

        unique_id = self._stable_gl_id(transaction_id, account_name)
        existing = self.db.query(GLEntry).filter(GLEntry.erpnext_id == unique_id).first()

        date = parse_import_date(row.get("date", ""))
        debit = parse_decimal_str(row.get("debit", "0"))
        credit = parse_decimal_str(row.get("credit", "0"))

        if existing:
            existing.posting_date = date
            existing.account = account_name
            existing.debit = debit
            existing.credit = credit
            existing.debit_in_account_currency = debit
            existing.credit_in_account_currency = credit
            existing.voucher_type = row.get("transaction_type", "")
            existing.voucher_no = row.get("reference_number", "")
            existing.party = row.get("party") or row.get("transaction_details", "")
            existing.fiscal_year = str(date.year) if date else None
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
                party=row.get("party") or row.get("transaction_details", ""),
                fiscal_year=str(date.year) if date else None,
            )
            self.db.add(entry)
            self.stats["gl_entries"]["created"] += 1

    def _process_supplier_row(self, row: Dict[str, str]) -> None:
        supplier_name = (row.get("supplier_name") or row.get("name") or row.get("transaction_details") or "").strip()
        if not supplier_name:
            raise ValueError("supplier_name is required")

        existing = self.db.query(Supplier).filter(Supplier.supplier_name == supplier_name).first()
        currency = row.get("currency_code", "NGN") or "NGN"
        if existing:
            existing.default_currency = currency
            self.stats["suppliers"]["updated"] += 1
        else:
            supplier = Supplier(
                supplier_name=supplier_name,
                default_currency=currency,
                supplier_group="Imported",
            )
            self.db.add(supplier)
            self.stats["suppliers"]["created"] += 1

    def _process_account_row(self, row: Dict[str, str]) -> None:
        name = (row.get("account_name") or row.get("name") or "").strip()
        if not name:
            raise ValueError("account_name is required")

        root_type = map_root_type(row.get("root_type") or "")
        if not root_type:
            raise ValueError("root_type must be one of: asset, liability, equity, income, expense")

        parent = row.get("parent_account") or row.get("parent") or None
        is_group = str(row.get("is_group", "")).lower() in {"1", "true", "yes"}

        existing = self.db.query(Account).filter(Account.account_name == name).first()
        if existing:
            existing.root_type = root_type
            existing.parent_account = parent
            existing.is_group = is_group
            self.stats["accounts"]["updated"] += 1
        else:
            account = Account(
                account_name=name,
                root_type=root_type,
                parent_account=parent,
                is_group=is_group,
            )
            self.db.add(account)
            self.stats["accounts"]["created"] += 1

    # ------------------------------------------------------------------ Helpers
    def purge_domain(self, domain: str) -> int:
        """Purge imported records for a domain (currently GL entries only)."""
        if domain != "gl_entries":
            return 0
        deleted = self.db.query(GLEntry).filter(GLEntry.erpnext_id.like("import-gl-%")).delete(synchronize_session=False)
        self.db.commit()
        return deleted

    def _commit_batch(self, processed: int) -> None:
        if processed % self.batch_size == 0:
            self.db.commit()

    @staticmethod
    def _stable_gl_id(transaction_id: str, account_name: str) -> str:
        digest = hashlib.sha256(f"{transaction_id}:{account_name}".encode()).hexdigest()
        return f"import-gl-{digest[:16]}"

    @staticmethod
    def _required_columns(domain: str) -> set:
        required_map = {
            "bank_transactions": {"transaction_id", "account_name", "date", "debit", "credit"},
            "gl_entries": {"transaction_id", "account_name", "date", "debit", "credit"},
            "suppliers": set(),
            "accounts": {"account_name", "root_type"},
        }
        if domain not in required_map:
            raise ValueError(f"Unsupported domain: {domain}")
        return required_map[domain]

    def _validate_row(self, domain: str, row: Dict[str, str]) -> None:
        if domain in {"bank_transactions", "gl_entries"}:
            if not (row.get("transaction_id") or "").strip():
                raise ValueError("transaction_id is required")
            if not (row.get("account_name") or "").strip():
                raise ValueError("account_name is required")
            date_str = row.get("date", "")
            if date_str and parse_import_date(date_str) is None:
                raise ValueError("date could not be parsed")
            parse_decimal_str(row.get("debit", "0"))
            parse_decimal_str(row.get("credit", "0"))
        elif domain == "suppliers":
            if not ((row.get("supplier_name") or row.get("name") or row.get("transaction_details") or "").strip()):
                raise ValueError("supplier_name is required")
        elif domain == "accounts":
            if not (row.get("account_name") or row.get("name")):
                raise ValueError("account_name is required")
            if not map_root_type(row.get("root_type") or ""):
                raise ValueError("root_type must be one of: asset, liability, equity, income, expense")
