"""Banking service for bank accounts and transactions.

This module handles:
- Bank Account CRUD with GL-derived balances
- Bank Transaction CRUD with splits
- Bank statement import (CSV/OFX)
- Transaction reconciliation status

Note: Full bank reconciliation workflow is handled by BankReconciliationService.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.accounting import BankAccount, BankTransaction, BankTransactionStatus, GLEntry
from app.models.bank_transaction_split import BankTransactionSplit
from app.services.base import paginate
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams

from .banking_types import (
    BankAccountBalanceInfo,
    BankAccountCreateData,
    BankAccountUpdateData,
    BankTransactionCreateData,
    BankTransactionFilters,
    BankTransactionSplitData,
    BankTransactionUpdateData,
    ImportColumnMapping,
    ImportResult,
    ParsedTransaction,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["BankingService"]


class BankingService:
    """Service for bank account and transaction management."""

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # ============= BANK ACCOUNTS =============

    def list_bank_accounts(
        self,
        include_disabled: bool = False,
        as_of_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """List bank accounts with GL-derived balances.

        Args:
            include_disabled: Include disabled accounts
            as_of_date: Calculate balances as of this date

        Returns:
            Dict with accounts list and total balance
        """
        query = self.db.query(BankAccount)
        if not include_disabled:
            query = query.filter(BankAccount.disabled == False)

        accounts = query.all()

        # Calculate balances from GL entries
        cutoff = as_of_date or date.today()
        gl_accounts = [acc.account for acc in accounts if acc.account]

        account_balances: Dict[str, float] = {}
        if gl_accounts:
            balance_query = self.db.query(
                GLEntry.account,
                func.sum(GLEntry.debit).label("total_debit"),
                func.sum(GLEntry.credit).label("total_credit"),
            ).filter(
                GLEntry.is_cancelled == False,
                GLEntry.posting_date <= cutoff,
                GLEntry.account.in_(gl_accounts),
            ).group_by(GLEntry.account)

            for row in balance_query.all():
                debit = row.total_debit or Decimal("0")
                credit = row.total_credit or Decimal("0")
                account_balances[row.account] = float(debit - credit)

        total_balance = sum(account_balances.values())

        return {
            "total": len(accounts),
            "total_balance": total_balance,
            "as_of_date": cutoff.isoformat(),
            "accounts": [
                BankAccountBalanceInfo(
                    id=acc.id,
                    erpnext_id=acc.erpnext_id,
                    name=acc.account_name,
                    bank=acc.bank,
                    account_no=acc.bank_account_no,
                    gl_account=acc.account,
                    company=acc.company,
                    currency=acc.currency,
                    is_default=acc.is_default,
                    balance=account_balances.get(acc.account or "", 0.0),
                )
                for acc in accounts
            ],
        }

    def get_bank_account(self, account_id: int) -> BankAccount:
        """Get a bank account by ID.

        Args:
            account_id: Bank account ID

        Returns:
            BankAccount model instance

        Raises:
            NotFoundError: If account not found
        """
        account = self.db.query(BankAccount).filter(BankAccount.id == account_id).first()
        if not account:
            raise NotFoundError("Bank account not found")
        return account

    def find_bank_account(self, identifier: str) -> Optional[BankAccount]:
        """Find bank account by name, account number, or GL account.

        Args:
            identifier: Account name, bank account number, or GL account

        Returns:
            BankAccount if found, None otherwise
        """
        return self.db.query(BankAccount).filter(
            or_(
                BankAccount.account_name == identifier,
                BankAccount.bank_account_no == identifier,
                BankAccount.account == identifier,
            )
        ).first()

    def create_bank_account(self, data: BankAccountCreateData) -> BankAccount:
        """Create a new bank account.

        Args:
            data: Bank account creation data

        Returns:
            Created BankAccount
        """
        account = BankAccount(
            account_name=data.account_name,
            bank=data.bank,
            bank_account_no=data.bank_account_no,
            account=data.account,
            company=data.company,
            currency=data.currency,
            is_company_account=data.is_company_account,
            is_default=data.is_default,
            disabled=data.disabled,
        )
        self.db.add(account)
        self.db.flush()
        return account

    def update_bank_account(
        self,
        account_id: int,
        data: BankAccountUpdateData,
    ) -> BankAccount:
        """Update a bank account.

        Args:
            account_id: Bank account ID
            data: Update data

        Returns:
            Updated BankAccount

        Raises:
            NotFoundError: If account not found
        """
        account = self.get_bank_account(account_id)

        if data.account_name is not None:
            account.account_name = data.account_name
        if data.bank is not None:
            account.bank = data.bank
        if data.bank_account_no is not None:
            account.bank_account_no = data.bank_account_no
        if data.account is not None:
            account.account = data.account
        if data.company is not None:
            account.company = data.company
        if data.currency is not None:
            account.currency = data.currency
        if data.is_company_account is not None:
            account.is_company_account = data.is_company_account
        if data.is_default is not None:
            account.is_default = data.is_default
        if data.disabled is not None:
            account.disabled = data.disabled

        self.db.flush()
        return account

    def disable_bank_account(self, account_id: int) -> None:
        """Disable a bank account (soft delete).

        Args:
            account_id: Bank account ID

        Raises:
            NotFoundError: If account not found
        """
        account = self.get_bank_account(account_id)
        account.disabled = True
        self.db.flush()

    # ============= BANK TRANSACTIONS =============

    def list_transactions(
        self,
        filters: BankTransactionFilters,
        pagination: PaginationParams,
    ) -> PaginatedResult[BankTransaction]:
        """List bank transactions with filtering.

        Args:
            filters: Transaction filters
            pagination: Pagination parameters

        Returns:
            Paginated transaction results
        """
        query = self.db.query(BankTransaction)

        if filters.bank_account:
            query = query.filter(
                BankTransaction.bank_account.ilike(f"%{filters.bank_account}%")
            )

        if filters.status:
            try:
                status_enum = BankTransactionStatus(filters.status.lower())
                query = query.filter(BankTransaction.status == status_enum)
            except ValueError:
                raise ValidationError(f"Invalid status: {filters.status}")

        if filters.transaction_type:
            query = query.filter(BankTransaction.transaction_type == filters.transaction_type)

        if filters.start_date:
            query = query.filter(BankTransaction.date >= filters.start_date)

        if filters.end_date:
            query = query.filter(BankTransaction.date <= filters.end_date)

        if filters.min_amount:
            query = query.filter(
                or_(
                    BankTransaction.deposit >= filters.min_amount,
                    BankTransaction.withdrawal >= filters.min_amount,
                )
            )

        if filters.max_amount:
            query = query.filter(
                and_(
                    or_(
                        BankTransaction.deposit <= filters.max_amount,
                        BankTransaction.deposit == 0,
                    ),
                    or_(
                        BankTransaction.withdrawal <= filters.max_amount,
                        BankTransaction.withdrawal == 0,
                    ),
                )
            )

        if filters.unallocated_only:
            query = query.filter(BankTransaction.unallocated_amount > 0)

        if filters.search:
            query = query.filter(
                or_(
                    BankTransaction.description.ilike(f"%{filters.search}%"),
                    BankTransaction.reference_number.ilike(f"%{filters.search}%"),
                    BankTransaction.bank_party_name.ilike(f"%{filters.search}%"),
                )
            )

        # Sorting
        sort_column = getattr(BankTransaction, filters.sort_by, BankTransaction.date)
        if filters.sort_dir == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        return paginate(query, pagination)

    def get_transaction(self, transaction_id: int) -> BankTransaction:
        """Get a bank transaction by ID.

        Args:
            transaction_id: Transaction ID

        Returns:
            BankTransaction model instance

        Raises:
            NotFoundError: If transaction not found
        """
        txn = self.db.query(BankTransaction).filter(
            BankTransaction.id == transaction_id
        ).first()
        if not txn:
            raise NotFoundError("Bank transaction not found")
        return txn

    def create_transaction(
        self,
        data: BankTransactionCreateData,
        user_id: Optional[int] = None,
        auto_create_bank_account: bool = False,
    ) -> BankTransaction:
        """Create a manual bank transaction.

        Args:
            data: Transaction creation data
            user_id: ID of user creating the transaction
            auto_create_bank_account: Auto-create bank account if not found

        Returns:
            Created BankTransaction

        Raises:
            ValidationError: If bank account not found and auto_create is False
        """
        # Find or create bank account
        bank_account = self.find_bank_account(data.bank_account)

        if not bank_account:
            if auto_create_bank_account:
                bank_account = BankAccount(
                    account_name=data.bank_account,
                    currency=data.currency,
                    is_company_account=True,
                )
                self.db.add(bank_account)
                self.db.flush()
            else:
                raise ValidationError("Bank account not found")

        # Create transaction
        txn = BankTransaction(
            date=data.date,
            bank_account=bank_account.account_name,
            bank_account_id=bank_account.id,
            company=bank_account.company,
            deposit=data.deposit,
            withdrawal=data.withdrawal,
            currency=data.currency,
            description=data.description,
            reference_number=data.reference_number,
            transaction_type=data.transaction_type,
            payee_name=data.payee_name,
            payee_account=data.payee_account,
            party_type=data.party_type,
            party=data.party,
            status=BankTransactionStatus.UNRECONCILED,
            is_manual_entry=True,
            created_by_id=user_id,
        )

        # Calculate unallocated amount
        amount = txn.deposit if txn.deposit > 0 else txn.withdrawal
        txn.unallocated_amount = amount
        txn.allocated_amount = Decimal("0")

        self.db.add(txn)
        self.db.flush()

        # Add splits if provided
        for idx, split_data in enumerate(data.splits):
            split = BankTransactionSplit(
                bank_transaction_id=txn.id,
                amount=split_data.amount,
                account=split_data.account,
                cost_center=split_data.cost_center,
                tax_code_id=split_data.tax_code_id,
                tax_rate=split_data.tax_rate,
                tax_amount=split_data.tax_amount,
                memo=split_data.memo,
                party_type=split_data.party_type,
                party=split_data.party,
                idx=idx,
            )
            self.db.add(split)

        self.db.flush()
        return txn

    def update_transaction(
        self,
        transaction_id: int,
        data: BankTransactionUpdateData,
    ) -> BankTransaction:
        """Update a bank transaction.

        Only unreconciled transactions can be updated.

        Args:
            transaction_id: Transaction ID
            data: Update data

        Returns:
            Updated BankTransaction

        Raises:
            NotFoundError: If transaction not found
            ValidationError: If transaction is reconciled
        """
        txn = self.get_transaction(transaction_id)

        if txn.status == BankTransactionStatus.RECONCILED:
            raise ValidationError("Cannot update reconciled transaction")

        if data.date is not None:
            txn.date = data.date
        if data.bank_account is not None:
            txn.bank_account = data.bank_account
        if data.deposit is not None:
            txn.deposit = data.deposit
        if data.withdrawal is not None:
            txn.withdrawal = data.withdrawal
        if data.description is not None:
            txn.description = data.description
        if data.reference_number is not None:
            txn.reference_number = data.reference_number
        if data.transaction_type is not None:
            txn.transaction_type = data.transaction_type
        if data.payee_name is not None:
            txn.payee_name = data.payee_name
        if data.payee_account is not None:
            txn.payee_account = data.payee_account
        if data.party_type is not None:
            txn.party_type = data.party_type
        if data.party is not None:
            txn.party = data.party

        # Recalculate unallocated
        amount = txn.deposit if txn.deposit > 0 else txn.withdrawal
        txn.unallocated_amount = amount - txn.allocated_amount

        self.db.flush()
        return txn

    def delete_transaction(self, transaction_id: int) -> None:
        """Delete a bank transaction.

        Only unreconciled manual entries can be deleted.

        Args:
            transaction_id: Transaction ID

        Raises:
            NotFoundError: If transaction not found
            ValidationError: If transaction cannot be deleted
        """
        txn = self.get_transaction(transaction_id)

        if txn.status == BankTransactionStatus.RECONCILED:
            raise ValidationError("Cannot delete reconciled transaction")

        if not txn.is_manual_entry:
            raise ValidationError("Cannot delete imported transaction")

        # Delete splits first
        self.db.query(BankTransactionSplit).filter(
            BankTransactionSplit.bank_transaction_id == transaction_id
        ).delete()

        self.db.delete(txn)
        self.db.flush()

    # ============= TRANSACTION SPLITS =============

    def add_splits(
        self,
        transaction_id: int,
        splits: List[BankTransactionSplitData],
    ) -> List[int]:
        """Add splits to a bank transaction.

        Args:
            transaction_id: Transaction ID
            splits: List of split data

        Returns:
            List of created split IDs

        Raises:
            NotFoundError: If transaction not found
            ValidationError: If transaction is reconciled
        """
        txn = self.get_transaction(transaction_id)

        if txn.status == BankTransactionStatus.RECONCILED:
            raise ValidationError("Cannot modify reconciled transaction")

        # Get current max idx
        max_idx = self.db.query(func.max(BankTransactionSplit.idx)).filter(
            BankTransactionSplit.bank_transaction_id == transaction_id
        ).scalar() or -1

        created_ids = []
        for idx, split_data in enumerate(splits, start=max_idx + 1):
            split = BankTransactionSplit(
                bank_transaction_id=transaction_id,
                amount=split_data.amount,
                account=split_data.account,
                cost_center=split_data.cost_center,
                tax_code_id=split_data.tax_code_id,
                tax_rate=split_data.tax_rate,
                tax_amount=split_data.tax_amount,
                memo=split_data.memo,
                party_type=split_data.party_type,
                party=split_data.party,
                idx=idx,
            )
            self.db.add(split)
            self.db.flush()
            created_ids.append(split.id)

        return created_ids

    def delete_split(self, transaction_id: int, split_id: int) -> None:
        """Delete a split from a bank transaction.

        Args:
            transaction_id: Transaction ID
            split_id: Split ID

        Raises:
            NotFoundError: If transaction or split not found
            ValidationError: If transaction is reconciled
        """
        txn = self.get_transaction(transaction_id)

        if txn.status == BankTransactionStatus.RECONCILED:
            raise ValidationError("Cannot modify reconciled transaction")

        split = self.db.query(BankTransactionSplit).filter(
            BankTransactionSplit.id == split_id,
            BankTransactionSplit.bank_transaction_id == transaction_id,
        ).first()
        if not split:
            raise NotFoundError("Split not found")

        self.db.delete(split)
        self.db.flush()

    # ============= RECONCILIATION STATUS =============

    def reconcile_transaction(self, transaction_id: int) -> BankTransaction:
        """Mark a bank transaction as reconciled.

        Args:
            transaction_id: Transaction ID

        Returns:
            Updated transaction

        Raises:
            NotFoundError: If transaction not found
            ValidationError: If already reconciled
        """
        txn = self.get_transaction(transaction_id)

        if txn.status == BankTransactionStatus.RECONCILED:
            raise ValidationError("Transaction is already reconciled")

        txn.status = BankTransactionStatus.RECONCILED
        self.db.flush()
        return txn

    def unreconcile_transaction(self, transaction_id: int) -> BankTransaction:
        """Unreconcile a bank transaction.

        Args:
            transaction_id: Transaction ID

        Returns:
            Updated transaction

        Raises:
            NotFoundError: If transaction not found
            ValidationError: If not reconciled
        """
        txn = self.get_transaction(transaction_id)

        if txn.status != BankTransactionStatus.RECONCILED:
            raise ValidationError("Transaction is not reconciled")

        txn.status = BankTransactionStatus.UNRECONCILED
        self.db.flush()
        return txn

    # ============= IMPORT =============

    def parse_csv(
        self,
        content: str,
        mapping: ImportColumnMapping,
    ) -> List[ParsedTransaction]:
        """Parse CSV content into transaction records.

        Args:
            content: CSV file content
            mapping: Column mapping configuration

        Returns:
            List of parsed transactions
        """
        transactions = []
        reader = csv.DictReader(io.StringIO(content))

        for row_num, row in enumerate(reader, start=2):
            try:
                # Parse date
                date_str = row.get(mapping.date_column, "").strip()
                if not date_str:
                    continue

                # Try multiple date formats
                txn_date = None
                for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]:
                    try:
                        txn_date = datetime.strptime(date_str[:10], fmt)
                        break
                    except ValueError:
                        continue

                if not txn_date:
                    continue

                # Parse amount
                deposit = Decimal("0")
                withdrawal = Decimal("0")

                if mapping.amount_column:
                    amount_str = row.get(mapping.amount_column, "0")
                    amount_str = re.sub(r"[^\d.\-]", "", amount_str)
                    amount = Decimal(amount_str) if amount_str else Decimal("0")
                    if amount >= 0:
                        deposit = amount
                    else:
                        withdrawal = abs(amount)
                else:
                    if mapping.deposit_column:
                        dep_str = row.get(mapping.deposit_column, "0")
                        dep_str = re.sub(r"[^\d.]", "", dep_str)
                        deposit = Decimal(dep_str) if dep_str else Decimal("0")
                    if mapping.withdrawal_column:
                        with_str = row.get(mapping.withdrawal_column, "0")
                        with_str = re.sub(r"[^\d.]", "", with_str)
                        withdrawal = Decimal(with_str) if with_str else Decimal("0")

                # Skip zero transactions
                if deposit == 0 and withdrawal == 0:
                    continue

                transactions.append(ParsedTransaction(
                    date=txn_date,
                    deposit=deposit,
                    withdrawal=withdrawal,
                    description=row.get(mapping.description_column or "", ""),
                    reference_number=row.get(mapping.reference_column or "", ""),
                    row_num=row_num,
                ))

            except Exception:
                # Skip invalid rows
                continue

        return transactions

    def parse_ofx(self, content: str) -> List[ParsedTransaction]:
        """Parse OFX/QFX content into transaction records.

        Args:
            content: OFX file content

        Returns:
            List of parsed transactions
        """
        transactions = []

        # Extract STMTTRN blocks using regex
        trn_pattern = re.compile(
            r"<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|(?=</BANKTRANLIST>))",
            re.DOTALL | re.IGNORECASE,
        )

        def extract_tag(block: str, tag: str) -> str:
            # Try XML style first
            xml_match = re.search(rf"<{tag}>([^<]*)</{tag}>", block, re.IGNORECASE)
            if xml_match:
                return xml_match.group(1).strip()
            # Try SGML style
            sgml_match = re.search(rf"<{tag}>([^<\n\r]+)", block, re.IGNORECASE)
            if sgml_match:
                return sgml_match.group(1).strip()
            return ""

        for row_num, match in enumerate(trn_pattern.finditer(content), start=1):
            block = match.group(1)

            # Parse date (YYYYMMDD format)
            date_str = extract_tag(block, "DTPOSTED")
            if len(date_str) < 8:
                continue
            try:
                txn_date = datetime.strptime(date_str[:8], "%Y%m%d")
            except ValueError:
                continue

            # Parse amount
            amount_str = extract_tag(block, "TRNAMT")
            try:
                amount = Decimal(amount_str)
            except (ValueError, TypeError, InvalidOperation):
                continue

            deposit = amount if amount >= 0 else Decimal("0")
            withdrawal = abs(amount) if amount < 0 else Decimal("0")

            # Build description from NAME and MEMO
            name = extract_tag(block, "NAME")
            memo = extract_tag(block, "MEMO")
            description = f"{name} - {memo}".strip(" -") if name or memo else ""

            # Reference from FITID or CHECKNUM
            reference = extract_tag(block, "CHECKNUM") or extract_tag(block, "FITID")

            transactions.append(ParsedTransaction(
                date=txn_date,
                deposit=deposit,
                withdrawal=withdrawal,
                description=description,
                reference_number=reference,
                row_num=row_num,
                fitid=extract_tag(block, "FITID"),
            ))

        return transactions

    def import_transactions(
        self,
        bank_account: str,
        transactions: List[ParsedTransaction],
        skip_duplicates: bool = True,
        user_id: Optional[int] = None,
    ) -> ImportResult:
        """Import parsed transactions into the database.

        Args:
            bank_account: Bank account name to import into
            transactions: List of parsed transactions
            skip_duplicates: Skip transactions that already exist
            user_id: ID of user performing import

        Returns:
            Import result with counts and errors
        """
        result = ImportResult()

        for txn_data in transactions:
            try:
                # Check for duplicates
                if skip_duplicates:
                    existing = self._find_duplicate_transaction(
                        bank_account,
                        txn_data,
                    )
                    if existing:
                        result.skipped_count += 1
                        continue

                # Create transaction
                amount = txn_data.deposit if txn_data.deposit > 0 else txn_data.withdrawal
                txn = BankTransaction(
                    date=txn_data.date,
                    bank_account=bank_account,
                    deposit=txn_data.deposit,
                    withdrawal=txn_data.withdrawal,
                    currency="NGN",
                    description=txn_data.description,
                    reference_number=txn_data.reference_number,
                    transaction_id=txn_data.fitid,
                    transaction_type="deposit" if txn_data.deposit > 0 else "withdrawal",
                    status=BankTransactionStatus.UNRECONCILED,
                    unallocated_amount=amount,
                    allocated_amount=Decimal("0"),
                    is_manual_entry=False,
                    created_by_id=user_id,
                )

                self.db.add(txn)
                self.db.flush()

                result.imported_count += 1
                result.transaction_ids.append(txn.id)

            except Exception as e:
                result.errors.append({
                    "row": txn_data.row_num,
                    "error": str(e),
                })

        return result

    def _find_duplicate_transaction(
        self,
        bank_account: str,
        txn_data: ParsedTransaction,
    ) -> Optional[BankTransaction]:
        """Find duplicate transaction in database.

        Args:
            bank_account: Bank account name
            txn_data: Transaction data to check

        Returns:
            Existing transaction if duplicate found, None otherwise
        """
        # Check by date and amounts
        existing = self.db.query(BankTransaction).filter(
            BankTransaction.bank_account == bank_account,
            BankTransaction.date == txn_data.date,
            BankTransaction.deposit == txn_data.deposit,
            BankTransaction.withdrawal == txn_data.withdrawal,
        ).first()
        if existing:
            return existing

        # Check by reference number
        if txn_data.reference_number:
            existing = self.db.query(BankTransaction).filter(
                BankTransaction.bank_account == bank_account,
                BankTransaction.reference_number == txn_data.reference_number,
            ).first()
            if existing:
                return existing

        # Check by FITID for OFX imports
        if txn_data.fitid:
            existing = self.db.query(BankTransaction).filter(
                BankTransaction.bank_account == bank_account,
                BankTransaction.transaction_id == txn_data.fitid,
            ).first()
            if existing:
                return existing

        return None
