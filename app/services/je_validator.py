"""
Journal Entry Validator Service

Provides comprehensive validation for journal entries including:
- Balanced check: sum(debits) == sum(credits)
- Account checks: not disabled, not group account
- Period check: posting_date in OPEN period
- Unique voucher number enforcement
- Backdating cutoff (configurable days)
- Required attachments by doctype (if configured)
"""
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.accounting_ext import AccountingControl
from app.models.accounting import (
    Account,
    JournalEntry,
    JournalEntryAccount,
)
from app.services.period_manager import PeriodManager, PeriodError


class ValidationError(Exception):
    """Exception raised when validation fails."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


class JEValidator:
    """Service for validating journal entries."""

    def __init__(self, db: Session):
        self.db = db
        self.period_manager = PeriodManager(db)

    def validate(
        self,
        je: JournalEntry,
        accounts: Optional[List[JournalEntryAccount]] = None,
        skip_period_check: bool = False,
        skip_voucher_check: bool = False,
    ) -> Tuple[bool, List[str]]:
        """
        Perform full validation on a journal entry.

        Args:
            je: The JournalEntry to validate
            accounts: Optional list of JE account lines (if not yet associated)
            skip_period_check: Skip period validation (for system entries)
            skip_voucher_check: Skip voucher number uniqueness check

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Get account lines
        if accounts is None:
            accounts = je.accounts if hasattr(je, 'accounts') else []

        # 1. Basic required fields
        basic_errors = self._validate_basic_fields(je)
        errors.extend(basic_errors)

        # 2. Must have at least 2 account lines
        if len(accounts) < 2:
            errors.append("Journal entry must have at least 2 account lines")

        # 3. Balanced check
        balance_errors = self._validate_balanced(accounts)
        errors.extend(balance_errors)

        # 4. Account validity checks
        account_errors = self._validate_accounts(accounts)
        errors.extend(account_errors)

        # 5. Period check
        if not skip_period_check and je.posting_date:
            period_errors = self._validate_period(je.posting_date)
            errors.extend(period_errors)

        # 6. Voucher number uniqueness
        if not skip_voucher_check and je.erpnext_id:
            voucher_errors = self._validate_voucher_unique(je)
            errors.extend(voucher_errors)

        # 7. Backdating check
        if je.posting_date:
            backdating_errors = self._validate_backdating(je.posting_date)
            errors.extend(backdating_errors)

        return (len(errors) == 0, errors)

    def validate_or_raise(
        self,
        je: JournalEntry,
        accounts: Optional[List[JournalEntryAccount]] = None,
        **kwargs,
    ) -> None:
        """
        Validate journal entry and raise ValidationError if invalid.

        Args:
            je: The JournalEntry to validate
            accounts: Optional list of JE account lines
            **kwargs: Additional args passed to validate()

        Raises:
            ValidationError: If validation fails
        """
        is_valid, errors = self.validate(je, accounts, **kwargs)
        if not is_valid:
            raise ValidationError(errors)

    def _validate_basic_fields(self, je: JournalEntry) -> List[str]:
        """Validate basic required fields."""
        errors = []

        if not je.posting_date:
            errors.append("Posting date is required")

        if not je.voucher_type:
            errors.append("Voucher type is required")

        return errors

    def _validate_balanced(
        self,
        accounts: List[JournalEntryAccount],
    ) -> List[str]:
        """
        Validate that debits equal credits.

        The sum of all debits must equal the sum of all credits for the
        journal entry to be balanced.
        """
        errors = []

        if not accounts:
            return errors

        total_debit = sum(
            (a.debit or Decimal("0")) for a in accounts
        )
        total_credit = sum(
            (a.credit or Decimal("0")) for a in accounts
        )

        # Use tolerance for floating point comparison
        tolerance = Decimal("0.01")
        difference = abs(total_debit - total_credit)

        if difference > tolerance:
            errors.append(
                f"Journal entry is not balanced. "
                f"Total debit: {total_debit}, Total credit: {total_credit}, "
                f"Difference: {difference}"
            )

        return errors

    def _validate_accounts(
        self,
        accounts: List[JournalEntryAccount],
    ) -> List[str]:
        """
        Validate each account line.

        Checks:
        - Account exists
        - Account is not disabled
        - Account is not a group account
        - Debit and credit are not both non-zero
        - At least one of debit/credit is non-zero
        """
        errors = []

        for idx, line in enumerate(accounts, 1):
            line_prefix = f"Line {idx}"

            # Check account specified
            if not line.account:
                errors.append(f"{line_prefix}: Account is required")
                continue

            # Look up account
            account = (
                self.db.query(Account)
                .filter(Account.account_name == line.account)
                .first()
            )

            if not account:
                errors.append(
                    f"{line_prefix}: Account '{line.account}' not found in chart of accounts"
                )
                continue

            # Check not disabled
            if account.disabled:
                errors.append(
                    f"{line_prefix}: Account '{line.account}' is disabled"
                )

            # Check not group account
            if account.is_group:
                errors.append(
                    f"{line_prefix}: Cannot post to group account '{line.account}'. "
                    "Select a leaf account."
                )

            # Validate debit/credit values
            debit = line.debit or Decimal("0")
            credit = line.credit or Decimal("0")

            if debit < Decimal("0"):
                errors.append(f"{line_prefix}: Debit cannot be negative")

            if credit < Decimal("0"):
                errors.append(f"{line_prefix}: Credit cannot be negative")

            if debit > Decimal("0") and credit > Decimal("0"):
                errors.append(
                    f"{line_prefix}: Cannot have both debit and credit on same line. "
                    f"Debit: {debit}, Credit: {credit}"
                )

            if debit == Decimal("0") and credit == Decimal("0"):
                errors.append(
                    f"{line_prefix}: Either debit or credit must be non-zero"
                )

        return errors

    def _validate_period(self, posting_date: date) -> List[str]:
        """Validate posting date is within an open period."""
        errors = []

        # Convert datetime to date if needed
        if isinstance(posting_date, datetime):
            posting_date = posting_date.date()

        is_valid, error_msg = self.period_manager.validate_posting_date(posting_date)
        if not is_valid:
            errors.append(error_msg)

        return errors

    def _validate_voucher_unique(self, je: JournalEntry) -> List[str]:
        """Validate voucher number is unique."""
        errors = []

        if not je.erpnext_id:
            return errors

        # Check for existing JE with same voucher number
        existing = (
            self.db.query(JournalEntry)
            .filter(
                and_(
                    JournalEntry.erpnext_id == je.erpnext_id,
                    JournalEntry.id != je.id if je.id else True,
                )
            )
            .first()
        )

        if existing:
            errors.append(
                f"Voucher number '{je.erpnext_id}' is already in use"
            )

        return errors

    def _validate_backdating(self, posting_date: date) -> List[str]:
        """Validate posting date is within allowed backdating window."""
        errors = []

        # Convert datetime to date if needed
        if isinstance(posting_date, datetime):
            posting_date = posting_date.date()

        # Get controls
        controls = self.db.query(AccountingControl).filter(
            AccountingControl.company.is_(None)
        ).first()

        if not controls:
            return errors  # No controls configured

        today = date.today()

        # Check backdating
        if posting_date < today:
            days_back = (today - posting_date).days
            if days_back > controls.backdating_days_allowed:
                errors.append(
                    f"Cannot backdate more than {controls.backdating_days_allowed} days. "
                    f"Posting date is {days_back} days in the past."
                )

        # Check future posting
        if posting_date > today:
            days_forward = (posting_date - today).days
            if days_forward > controls.future_posting_days_allowed:
                errors.append(
                    f"Cannot post more than {controls.future_posting_days_allowed} days in future. "
                    f"Posting date is {days_forward} days ahead."
                )

        return errors

    def validate_attachment_requirements(
        self,
        doctype: str,
        has_attachment: bool,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if attachment is required for a document type.

        Args:
            doctype: Document type
            has_attachment: Whether document has an attachment

        Returns:
            Tuple of (is_valid, error_message)
        """
        controls = self.db.query(AccountingControl).filter(
            AccountingControl.company.is_(None)
        ).first()

        if not controls:
            return (True, None)

        # Map doctype to control field
        requirement_map = {
            "journal_entry": controls.require_attachment_journal_entry,
            "expense": controls.require_attachment_expense,
            "payment": controls.require_attachment_payment,
            "invoice": controls.require_attachment_invoice,
        }

        requires_attachment = requirement_map.get(doctype, False)

        if requires_attachment and not has_attachment:
            return (
                False,
                f"Attachment is required for {doctype.replace('_', ' ')}s"
            )

        return (True, None)


class AccountValidator:
    """Service for validating chart of accounts operations."""

    def __init__(self, db: Session):
        self.db = db

    def validate_create(self, account_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate account creation.

        Args:
            account_data: Dict with account fields

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Required fields
        if not account_data.get("account_name"):
            errors.append("Account name is required")

        if not account_data.get("root_type"):
            errors.append("Root type (Asset/Liability/Equity/Income/Expense) is required")

        # Check unique account name
        if account_data.get("account_name"):
            existing = (
                self.db.query(Account)
                .filter(Account.account_name == account_data["account_name"])
                .first()
            )
            if existing:
                errors.append(f"Account '{account_data['account_name']}' already exists")

        # Check unique account number
        if account_data.get("account_number"):
            existing = (
                self.db.query(Account)
                .filter(Account.account_number == account_data["account_number"])
                .first()
            )
            if existing:
                errors.append(f"Account number '{account_data['account_number']}' already exists")

        # Validate parent account
        if account_data.get("parent_account"):
            parent = (
                self.db.query(Account)
                .filter(Account.account_name == account_data["parent_account"])
                .first()
            )
            if not parent:
                errors.append(f"Parent account '{account_data['parent_account']}' not found")
            elif not parent.is_group:
                errors.append(f"Parent account '{account_data['parent_account']}' is not a group account")

        return (len(errors) == 0, errors)

    def validate_update(
        self,
        account: Account,
        updates: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        """
        Validate account update.

        Args:
            account: Existing Account to update
            updates: Dict with fields to update

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Can't change root_type if account has transactions
        if "root_type" in updates and updates["root_type"] != account.root_type:
            if self._account_has_transactions(account):
                errors.append("Cannot change root type of account with existing transactions")

        # Can't change is_group if not empty
        if "is_group" in updates and updates["is_group"] != account.is_group:
            if account.is_group and self._account_has_children(account):
                errors.append("Cannot convert group account with child accounts")
            if not account.is_group and self._account_has_transactions(account):
                errors.append("Cannot convert account with transactions to group")

        # Check unique name if changing
        if "account_name" in updates and updates["account_name"] != account.account_name:
            existing = (
                self.db.query(Account)
                .filter(
                    and_(
                        Account.account_name == updates["account_name"],
                        Account.id != account.id,
                    )
                )
                .first()
            )
            if existing:
                errors.append(f"Account name '{updates['account_name']}' already exists")

        return (len(errors) == 0, errors)

    def validate_disable(self, account: Account) -> Tuple[bool, List[str]]:
        """
        Validate account can be disabled.

        Args:
            account: Account to disable

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check for outstanding balance
        from app.models.accounting import GLEntry

        balance = (
            self.db.query(
                func.sum(GLEntry.debit) - func.sum(GLEntry.credit)
            )
            .filter(
                and_(
                    GLEntry.account == account.account_name,
                    GLEntry.is_cancelled == False,
                )
            )
            .scalar()
        )

        if balance and abs(balance) > Decimal("0.01"):
            errors.append(
                f"Cannot disable account with outstanding balance of {balance}"
            )

        # Check for child accounts
        if account.is_group and self._account_has_children(account):
            errors.append("Cannot disable group account with child accounts")

        return (len(errors) == 0, errors)

    def _account_has_transactions(self, account: Account) -> bool:
        """Check if account has any GL entries."""
        from app.models.accounting import GLEntry

        count = (
            self.db.query(func.count(GLEntry.id))
            .filter(GLEntry.account == account.account_name)
            .scalar()
        )
        return count > 0

    def _account_has_children(self, account: Account) -> bool:
        """Check if account has child accounts."""
        count = (
            self.db.query(func.count(Account.id))
            .filter(Account.parent_account == account.account_name)
            .scalar()
        )
        return count > 0


class SupplierValidator:
    """Service for validating supplier operations."""

    def __init__(self, db: Session):
        self.db = db

    def validate_create(self, supplier_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate supplier creation."""
        errors = []

        if not supplier_data.get("supplier_name"):
            errors.append("Supplier name is required")

        # Check unique supplier name
        if supplier_data.get("supplier_name"):
            from app.models.accounting import Supplier
            existing = (
                self.db.query(Supplier)
                .filter(Supplier.supplier_name == supplier_data["supplier_name"])
                .first()
            )
            if existing:
                errors.append(f"Supplier '{supplier_data['supplier_name']}' already exists")

        return (len(errors) == 0, errors)

    def validate_disable(self, supplier_id: int) -> Tuple[bool, List[str]]:
        """Validate supplier can be disabled."""
        errors = []

        from app.models.accounting import PurchaseInvoice

        # Check for unpaid invoices
        unpaid = (
            self.db.query(func.count(PurchaseInvoice.id))
            .filter(
                and_(
                    PurchaseInvoice.supplier == str(supplier_id),
                    PurchaseInvoice.outstanding_amount > Decimal("0"),
                )
            )
            .scalar()
        )

        if unpaid > 0:
            errors.append(f"Cannot disable supplier with {unpaid} unpaid invoices")

        return (len(errors) == 0, errors)
