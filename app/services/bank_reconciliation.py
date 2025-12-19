"""
Bank Reconciliation Service

Provides bank reconciliation functionality:
- Start reconciliation for a bank account and date range
- Match bank transactions to payments/receipts
- Calculate outstanding items
- Complete reconciliation with difference handling
- Import bank statements (CSV, OFX)
"""
import csv
import io
import re
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from app.models.accounting import (
    BankAccount,
    BankTransaction,
    BankTransactionStatus,
    BankTransactionPayment,
    BankReconciliation,
    BankReconciliationStatus,
    GLEntry,
)
from app.models.payment import Payment
from app.services.audit_logger import AuditLogger, serialize_for_audit
from app.services.transaction_manager import transactional_session


class ReconciliationError(Exception):
    """Exception raised for reconciliation-related errors."""
    pass


class BankReconciliationService:
    """Service for bank reconciliation operations."""

    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = AuditLogger(db)

    def _get_reconciliation(self, reconciliation_id: int) -> BankReconciliation:
        reconciliation = self.db.query(BankReconciliation).filter(
            BankReconciliation.id == reconciliation_id
        ).first()
        if not reconciliation:
            raise ReconciliationError(f"Reconciliation {reconciliation_id} not found")
        if reconciliation.status in {BankReconciliationStatus.COMPLETED, BankReconciliationStatus.CANCELLED}:
            raise ReconciliationError("Reconciliation is not open for matching")
        return reconciliation

    @staticmethod
    def _normalize_date(value: Optional[date | datetime]) -> Optional[date]:
        if value is None:
            return None
        return value.date() if hasattr(value, "date") else value

    def get_bank_account(self, bank_account_id: int) -> BankAccount:
        """Get bank account by ID."""
        account = self.db.query(BankAccount).filter(BankAccount.id == bank_account_id).first()
        if not account:
            raise ReconciliationError(f"Bank account {bank_account_id} not found")
        return account

    def start_reconciliation(
        self,
        bank_account_id: int,
        from_date: date,
        to_date: date,
        statement_opening_balance: Decimal,
        statement_closing_balance: Decimal,
        user_id: int,
    ) -> BankReconciliation:
        """
        Start a new bank reconciliation.

        Args:
            bank_account_id: Bank account ID
            from_date: Statement start date
            to_date: Statement end date
            statement_opening_balance: Opening balance from bank statement
            statement_closing_balance: Closing balance from bank statement
            user_id: User starting the reconciliation

        Returns:
            New BankReconciliation record
        """
        with transactional_session(self.db):
            bank_account = self.get_bank_account(bank_account_id)

            # Check for existing open reconciliation
            existing = self.db.query(BankReconciliation).filter(
                and_(
                    BankReconciliation.bank_account == bank_account.account_name,
                    BankReconciliation.status.in_([
                        BankReconciliationStatus.DRAFT,
                        BankReconciliationStatus.IN_PROGRESS,
                    ]),
                )
            ).first()

            if existing:
                raise ReconciliationError(
                    f"An open reconciliation already exists for this account (ID: {existing.id})"
                )

            # Calculate GL opening balance (sum of transactions before from_date)
            gl_opening = self._calculate_gl_balance(bank_account.account_name, from_date)

            reconciliation = BankReconciliation(
                bank_account=bank_account.account_name,
                company=bank_account.company,
                from_date=from_date,
                to_date=to_date,
                bank_statement_opening_balance=statement_opening_balance,
                bank_statement_closing_balance=statement_closing_balance,
                account_opening_balance=gl_opening,
                status=BankReconciliationStatus.IN_PROGRESS,
            )
            self.db.add(reconciliation)
            self.db.flush()

            self.audit_logger.log_create(
                doctype="bank_reconciliation",
                document_id=reconciliation.id,
                user_id=user_id,
                document_name=f"{bank_account.account_name} {from_date} - {to_date}",
                new_values=serialize_for_audit(reconciliation),
            )

            return reconciliation

    def get_outstanding_items(
        self,
        reconciliation_id: int,
        bank_limit: Optional[int] = None,
        bank_offset: int = 0,
        gl_limit: Optional[int] = None,
        gl_offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get outstanding (unmatched) items for a reconciliation.

        Returns:
            Dict with unmatched bank transactions and GL entries
        """
        reconciliation = self.db.query(BankReconciliation).filter(
            BankReconciliation.id == reconciliation_id
        ).first()

        if not reconciliation:
            raise ReconciliationError(f"Reconciliation {reconciliation_id} not found")

        # Get unmatched bank transactions
        bank_query = self.db.query(BankTransaction).filter(
            and_(
                BankTransaction.bank_account == reconciliation.bank_account,
                BankTransaction.date >= reconciliation.from_date,
                BankTransaction.date <= reconciliation.to_date,
                BankTransaction.status != BankTransactionStatus.RECONCILED,
            )
        ).order_by(BankTransaction.date)
        total_bank = bank_query.count()
        if bank_offset:
            bank_query = bank_query.offset(bank_offset)
        if bank_limit is not None:
            bank_query = bank_query.limit(bank_limit)
        unmatched_bank_txns = bank_query.all()

        # Get unreconciled GL entries for this bank account
        gl_query = self.db.query(GLEntry).filter(
            and_(
                GLEntry.account == reconciliation.bank_account,
                GLEntry.posting_date >= reconciliation.from_date,
                GLEntry.posting_date <= reconciliation.to_date,
                GLEntry.is_cancelled == False,
                # Not yet matched to a bank transaction
                ~GLEntry.voucher_no.in_(
                    self.db.query(BankTransactionPayment.payment_entry)
                    .join(BankTransaction)
                    .filter(BankTransaction.status == BankTransactionStatus.RECONCILED)
                ),
            )
        ).order_by(GLEntry.posting_date)
        total_gl = gl_query.count()
        if gl_offset:
            gl_query = gl_query.offset(gl_offset)
        if gl_limit is not None:
            gl_query = gl_query.limit(gl_limit)
        unmatched_gl = gl_query.all()

        return {
            "reconciliation_id": reconciliation.id,
            "bank_account": reconciliation.bank_account,
            "from_date": reconciliation.from_date.isoformat(),
            "to_date": reconciliation.to_date.isoformat(),
            "unmatched_bank_transactions": [
                {
                    "id": t.id,
                    "date": t.date.isoformat() if t.date else None,
                    "description": t.description,
                    "deposit": float(t.deposit or 0),
                    "withdrawal": float(t.withdrawal or 0),
                    "reference_number": t.reference_number,
                    "status": t.status.value,
                }
                for t in unmatched_bank_txns
            ],
            "unmatched_gl_entries": [
                {
                    "id": e.id,
                    "posting_date": e.posting_date.isoformat() if e.posting_date else None,
                    "voucher_type": e.voucher_type,
                    "voucher_no": e.voucher_no,
                    "debit": float(e.debit or 0),
                    "credit": float(e.credit or 0),
                    "party": e.party,
                    "remarks": e.remarks,
                }
                for e in unmatched_gl
            ],
            "summary": {
                "unmatched_bank_count": len(unmatched_bank_txns),
                "unmatched_gl_count": len(unmatched_gl),
                "unmatched_bank_total_count": total_bank,
                "unmatched_gl_total_count": total_gl,
                "unmatched_bank_total": float(sum(
                    (t.deposit or Decimal("0")) - (t.withdrawal or Decimal("0"))
                    for t in unmatched_bank_txns
                )),
                "unmatched_gl_total": float(sum(
                    (e.debit or Decimal("0")) - (e.credit or Decimal("0"))
                    for e in unmatched_gl
                )),
            },
        }

    def match_transaction(
        self,
        bank_transaction_id: int,
        gl_entry_ids: List[int],
        user_id: int,
        reconciliation_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Match a bank transaction to one or more GL entries.

        Args:
            bank_transaction_id: Bank transaction ID
            gl_entry_ids: List of GL entry IDs to match
            user_id: User performing the match
            reconciliation_id: Optional reconciliation to validate scope

        Returns:
            Match result
        """
        with transactional_session(self.db):
            if not gl_entry_ids:
                raise ReconciliationError("No GL entries provided for matching")

            reconciliation = None
            if reconciliation_id is not None:
                reconciliation = self._get_reconciliation(reconciliation_id)

            bank_txn = self.db.query(BankTransaction).filter(
                BankTransaction.id == bank_transaction_id
            ).first()

            if not bank_txn:
                raise ReconciliationError(f"Bank transaction {bank_transaction_id} not found")

            if bank_txn.status == BankTransactionStatus.RECONCILED:
                raise ReconciliationError("Bank transaction is already reconciled")

            gl_entries = self.db.query(GLEntry).filter(
                GLEntry.id.in_(gl_entry_ids)
            ).all()

            if len(gl_entries) != len(gl_entry_ids):
                raise ReconciliationError("One or more GL entries not found")

            if reconciliation is not None:
                txn_date = self._normalize_date(bank_txn.date)
                if txn_date is None:
                    raise ReconciliationError("Bank transaction date is missing")
                if bank_txn.bank_account != reconciliation.bank_account:
                    raise ReconciliationError("Bank transaction not in reconciliation account")
                if txn_date < reconciliation.from_date or txn_date > reconciliation.to_date:
                    raise ReconciliationError("Bank transaction not in reconciliation period")

                for gl_entry in gl_entries:
                    gl_date = self._normalize_date(gl_entry.posting_date)
                    if gl_date is None:
                        raise ReconciliationError("GL entry posting date is missing")
                    if gl_entry.account != reconciliation.bank_account:
                        raise ReconciliationError("GL entry not in reconciliation account")
                    if gl_date < reconciliation.from_date or gl_date > reconciliation.to_date:
                        raise ReconciliationError("GL entry not in reconciliation period")
                    if gl_entry.is_cancelled:
                        raise ReconciliationError("GL entry is cancelled")

            # Calculate totals
            bank_amount = (bank_txn.deposit or Decimal("0")) - (bank_txn.withdrawal or Decimal("0"))
            gl_amount = sum(
                (e.debit or Decimal("0")) - (e.credit or Decimal("0"))
                for e in gl_entries
            )

            # Check if amounts match (within tolerance)
            difference = abs(bank_amount - gl_amount)
            if difference > Decimal("0.01"):
                raise ReconciliationError(
                    f"Amounts don't match. Bank: {bank_amount}, GL: {gl_amount}, Difference: {difference}"
                )

            # Create payment links
            for gl_entry in gl_entries:
                payment_link = BankTransactionPayment(
                    bank_transaction_id=bank_txn.id,
                    payment_document=gl_entry.voucher_type,
                    payment_entry=gl_entry.voucher_no,
                    allocated_amount=abs((gl_entry.debit or Decimal("0")) - (gl_entry.credit or Decimal("0"))),
                )
                self.db.add(payment_link)

            # Update bank transaction status
            bank_txn.status = BankTransactionStatus.RECONCILED
            self.db.flush()

            self.audit_logger.log(
                doctype="bank_transaction",
                document_id=bank_txn.id,
                action="reconcile",
                user_id=user_id,
                document_name=bank_txn.reference_number or str(bank_txn.id),
                new_values={"status": "reconciled", "matched_entries": gl_entry_ids},
                remarks=f"Matched to {len(gl_entries)} GL entries",
            )

            return {
                "bank_transaction_id": bank_txn.id,
                "matched_gl_entries": gl_entry_ids,
                "bank_amount": float(bank_amount),
                "gl_amount": float(gl_amount),
                "status": "reconciled",
            }

    def auto_match(
        self,
        reconciliation_id: int,
        user_id: int,
    ) -> Dict[str, Any]:
        """
        Automatically match bank transactions to GL entries based on amount and date.

        Args:
            reconciliation_id: Reconciliation ID
            user_id: User performing the auto-match

        Returns:
            Auto-match results
        """
        self._get_reconciliation(reconciliation_id)
        outstanding = self.get_outstanding_items(reconciliation_id)

        matched = []
        unmatched_bank = []

        bank_txns = {t["id"]: t for t in outstanding["unmatched_bank_transactions"]}
        gl_entries = outstanding["unmatched_gl_entries"]

        used_gl_ids = set()

        for bank_id, bank_txn in bank_txns.items():
            bank_amount = bank_txn["deposit"] - bank_txn["withdrawal"]

            # Look for matching GL entry by amount
            for gl in gl_entries:
                if gl["id"] in used_gl_ids:
                    continue

                gl_amount = gl["debit"] - gl["credit"]

                # Match by amount (within tolerance)
                if abs(bank_amount - gl_amount) < 0.02:
                    try:
                        self.match_transaction(
                            bank_id,
                            [gl["id"]],
                            user_id,
                            reconciliation_id=reconciliation_id,
                        )
                        matched.append({
                            "bank_transaction_id": bank_id,
                            "gl_entry_id": gl["id"],
                            "amount": bank_amount,
                        })
                        used_gl_ids.add(gl["id"])
                        break
                    except ReconciliationError:
                        continue
            else:
                unmatched_bank.append(bank_id)

        return {
            "matched_count": len(matched),
            "unmatched_count": len(unmatched_bank),
            "matches": matched,
        }

    def complete_reconciliation(
        self,
        reconciliation_id: int,
        user_id: int,
        adjustment_account: Optional[str] = None,
        adjustment_remarks: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Complete the reconciliation.

        Args:
            reconciliation_id: Reconciliation ID
            user_id: User completing the reconciliation
            adjustment_account: Account for any difference adjustment
            adjustment_remarks: Remarks for adjustment

        Returns:
            Completion result
        """
        with transactional_session(self.db):
            reconciliation = self.db.query(BankReconciliation).filter(
                BankReconciliation.id == reconciliation_id
            ).first()

            if not reconciliation:
                raise ReconciliationError(f"Reconciliation {reconciliation_id} not found")

            if reconciliation.status == BankReconciliationStatus.COMPLETED:
                raise ReconciliationError("Reconciliation is already completed")

            # Calculate final balances
            outstanding = self.get_outstanding_items(reconciliation_id)

            gl_closing = self._calculate_gl_balance(
                reconciliation.bank_account,
                reconciliation.to_date,
                include_date=True,
            )

            statement_movement = (
                reconciliation.bank_statement_closing_balance -
                reconciliation.bank_statement_opening_balance
            )

            gl_movement = gl_closing - reconciliation.account_opening_balance

            difference = reconciliation.bank_statement_closing_balance - gl_closing

            # Update reconciliation
            reconciliation.status = BankReconciliationStatus.COMPLETED
            reconciliation.total_amount = gl_closing
            self.db.flush()

            self.audit_logger.log(
                doctype="bank_reconciliation",
                document_id=reconciliation.id,
                action="complete",
                user_id=user_id,
                document_name=f"{reconciliation.bank_account}",
                new_values={
                    "status": "completed",
                    "gl_closing_balance": float(gl_closing),
                    "difference": float(difference),
                },
            )

            return {
                "reconciliation_id": reconciliation.id,
                "status": "completed",
                "statement_opening": float(reconciliation.bank_statement_opening_balance),
                "statement_closing": float(reconciliation.bank_statement_closing_balance),
                "gl_opening": float(reconciliation.account_opening_balance),
                "gl_closing": float(gl_closing),
                "statement_movement": float(statement_movement),
                "gl_movement": float(gl_movement),
                "difference": float(difference),
                "is_balanced": abs(difference) < Decimal("0.01"),
                "outstanding_items": outstanding["summary"],
            }

    def import_statement_csv(
        self,
        bank_account_id: int,
        csv_content: str,
        user_id: int,
        date_format: str = "%Y-%m-%d",
        has_header: bool = True,
    ) -> Dict[str, Any]:
        """
        Import bank statement from CSV.

        Expected columns: date, description, deposit, withdrawal, reference

        Args:
            bank_account_id: Bank account ID
            csv_content: CSV file content
            user_id: User performing import
            date_format: Date format in CSV
            has_header: Whether CSV has header row

        Returns:
            Import result
        """
        bank_account = self.get_bank_account(bank_account_id)

        reader = csv.reader(io.StringIO(csv_content))

        if has_header:
            next(reader)  # Skip header

        imported = []
        errors = []

        for row_num, row in enumerate(reader, start=2 if has_header else 1):
            try:
                if len(row) < 4:
                    errors.append(f"Row {row_num}: Not enough columns")
                    continue

                txn_date = datetime.strptime(row[0].strip(), date_format).date()
                description = row[1].strip()
                deposit = Decimal(row[2].strip() or "0")
                withdrawal = Decimal(row[3].strip() or "0")
                reference = row[4].strip() if len(row) > 4 else None

                txn = BankTransaction(
                    bank_account=bank_account.account_name,
                    date=txn_date,
                    description=description,
                    deposit=deposit,
                    withdrawal=withdrawal,
                    reference_number=reference,
                    status=BankTransactionStatus.PENDING,
                )
                self.db.add(txn)
                imported.append({
                    "row": row_num,
                    "date": txn_date.isoformat(),
                    "amount": float(deposit - withdrawal),
                })

            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")

        if imported:
            self.db.flush()

            self.audit_logger.log(
                doctype="bank_transaction",
                document_id=0,
                action="import",
                user_id=user_id,
                document_name=bank_account.account_name,
                new_values={"imported_count": len(imported)},
                remarks=f"CSV import: {len(imported)} transactions",
            )

        return {
            "bank_account": bank_account.account_name,
            "imported_count": len(imported),
            "error_count": len(errors),
            "imported": imported[:20],  # First 20 for preview
            "errors": errors[:10],  # First 10 errors
        }

    def get_reconciliation_status(
        self,
        bank_account_id: int,
    ) -> Dict[str, Any]:
        """Get current reconciliation status for a bank account."""
        bank_account = self.get_bank_account(bank_account_id)

        # Get latest reconciliation
        latest = self.db.query(BankReconciliation).filter(
            BankReconciliation.bank_account == bank_account.account_name
        ).order_by(desc(BankReconciliation.to_date)).first()

        # Count unreconciled transactions
        unreconciled_count = self.db.query(func.count(BankTransaction.id)).filter(
            and_(
                BankTransaction.bank_account == bank_account.account_name,
                BankTransaction.status != BankTransactionStatus.RECONCILED,
            )
        ).scalar()

        # Calculate current GL balance
        current_balance = self._calculate_gl_balance(
            bank_account.account_name,
            date.today(),
            include_date=True,
        )

        return {
            "bank_account_id": bank_account.id,
            "bank_account_name": bank_account.account_name,
            "current_gl_balance": float(current_balance),
            "unreconciled_transactions": unreconciled_count,
            "last_reconciliation": {
                "id": latest.id,
                "to_date": latest.to_date.isoformat(),
                "status": latest.status.value,
                "closing_balance": float(latest.bank_statement_closing_balance),
            } if latest else None,
        }

    def _calculate_gl_balance(
        self,
        account_name: str,
        as_of_date: date,
        include_date: bool = False,
    ) -> Decimal:
        """Calculate GL balance for an account as of a date."""
        query = self.db.query(
            func.sum(GLEntry.debit - GLEntry.credit)
        ).filter(
            and_(
                GLEntry.account == account_name,
                GLEntry.is_cancelled == False,
            )
        )

        if include_date:
            query = query.filter(GLEntry.posting_date <= as_of_date)
        else:
            query = query.filter(GLEntry.posting_date < as_of_date)

        result = query.scalar()
        return result or Decimal("0")
