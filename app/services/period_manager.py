"""
Period Manager Service

Handles fiscal period operations including:
- Period lookup and validation
- Period close/reopen with enforcement
- Closing entry generation (Income/Expense → Retained Earnings)
- Period status management
"""
from typing import Optional, List, Tuple
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.accounting_ext import (
    FiscalPeriod,
    FiscalPeriodStatus,
    FiscalPeriodType,
    AccountingControl,
    AuditAction,
)
from app.models.accounting import (
    FiscalYear,
    Account,
    AccountType,
    JournalEntry,
    JournalEntryAccount,
    JournalEntryType,
    GLEntry,
)
from app.services.audit_logger import AuditLogger, serialize_for_audit


class PeriodError(Exception):
    """Exception raised for period-related errors."""
    pass


class PeriodClosedError(PeriodError):
    """Exception raised when attempting to post to a closed period."""
    pass


class PeriodNotFoundError(PeriodError):
    """Exception raised when no matching period is found."""
    pass


class PeriodManager:
    """Service for managing fiscal periods."""

    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = AuditLogger(db)

    def get_period_for_date(self, posting_date: date) -> Optional[FiscalPeriod]:
        """
        Get the fiscal period containing a given date.

        Args:
            posting_date: The date to look up

        Returns:
            FiscalPeriod if found, None otherwise
        """
        return (
            self.db.query(FiscalPeriod)
            .filter(
                and_(
                    FiscalPeriod.start_date <= posting_date,
                    FiscalPeriod.end_date >= posting_date,
                )
            )
            .first()
        )

    def validate_period_open(
        self,
        posting_date: date,
        allow_soft_closed: bool = False,
    ) -> FiscalPeriod:
        """
        Validate that a posting date falls within an open period.

        Args:
            posting_date: The date to validate
            allow_soft_closed: If True, allow posting to soft-closed periods

        Returns:
            The validated FiscalPeriod

        Raises:
            PeriodNotFoundError: If no period contains the date
            PeriodClosedError: If the period is closed
        """
        period = self.get_period_for_date(posting_date)

        if not period:
            raise PeriodNotFoundError(
                f"No fiscal period found for date {posting_date}. "
                "Please create the appropriate fiscal period."
            )

        if period.status == FiscalPeriodStatus.HARD_CLOSED:
            raise PeriodClosedError(
                f"Period {period.period_name} is hard-closed and cannot accept postings."
            )

        if period.status == FiscalPeriodStatus.SOFT_CLOSED and not allow_soft_closed:
            raise PeriodClosedError(
                f"Period {period.period_name} is soft-closed. "
                "Reopen the period or contact an administrator."
            )

        return period

    def validate_posting_date(
        self,
        posting_date: date,
        user_id: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """
        Comprehensive posting date validation including:
        - Period open check
        - Backdating limits
        - Future posting limits

        Args:
            posting_date: The date to validate
            user_id: Optional user ID for logging

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get accounting controls
        controls = self.db.query(AccountingControl).filter(
            AccountingControl.company.is_(None)
        ).first()

        if not controls:
            # Create default controls if not exist
            controls = AccountingControl()
            self.db.add(controls)
            self.db.flush()

        today = date.today()

        # Check backdating limit
        if posting_date < today:
            days_back = (today - posting_date).days
            if days_back > controls.backdating_days_allowed:
                return (
                    False,
                    f"Cannot post more than {controls.backdating_days_allowed} days "
                    f"in the past. Date is {days_back} days ago."
                )

        # Check future posting limit
        if posting_date > today:
            days_forward = (posting_date - today).days
            if days_forward > controls.future_posting_days_allowed:
                return (
                    False,
                    f"Cannot post more than {controls.future_posting_days_allowed} days "
                    f"in the future. Date is {days_forward} days ahead."
                )

        # Check period is open
        try:
            self.validate_period_open(posting_date)
        except PeriodNotFoundError as e:
            return (False, str(e))
        except PeriodClosedError as e:
            return (False, str(e))

        return (True, "")

    def close_period(
        self,
        period_id: int,
        user_id: int,
        soft_close: bool = True,
        remarks: Optional[str] = None,
    ) -> FiscalPeriod:
        """
        Close a fiscal period.

        Args:
            period_id: ID of the period to close
            user_id: ID of the user performing the close
            soft_close: If True, soft-close (allows reopening); if False, hard-close
            remarks: Optional remarks for the audit log

        Returns:
            Updated FiscalPeriod

        Raises:
            PeriodNotFoundError: If period not found
            PeriodError: If period is already hard-closed
        """
        period = self.db.query(FiscalPeriod).filter(FiscalPeriod.id == period_id).first()

        if not period:
            raise PeriodNotFoundError(f"Period with ID {period_id} not found")

        if period.status == FiscalPeriodStatus.HARD_CLOSED:
            raise PeriodError(
                f"Period {period.period_name} is already hard-closed and cannot be modified."
            )

        old_values = serialize_for_audit(period)

        # Update period status
        period.status = (
            FiscalPeriodStatus.SOFT_CLOSED if soft_close
            else FiscalPeriodStatus.HARD_CLOSED
        )
        period.closed_at = datetime.utcnow()
        period.closed_by_id = user_id
        period.updated_at = datetime.utcnow()

        self.db.flush()

        # Audit log
        new_values = serialize_for_audit(period)
        self.audit_logger.log_close(
            doctype="fiscal_period",
            document_id=period.id,
            user_id=user_id,
            document_name=period.period_name,
            old_values=old_values,
            new_values=new_values,
            remarks=remarks or f"{'Soft' if soft_close else 'Hard'}-closed period",
        )

        return period

    def reopen_period(
        self,
        period_id: int,
        user_id: int,
        remarks: Optional[str] = None,
    ) -> FiscalPeriod:
        """
        Reopen a soft-closed fiscal period.

        Args:
            period_id: ID of the period to reopen
            user_id: ID of the user performing the reopen
            remarks: Optional remarks for the audit log

        Returns:
            Updated FiscalPeriod

        Raises:
            PeriodNotFoundError: If period not found
            PeriodError: If period is hard-closed
        """
        period = self.db.query(FiscalPeriod).filter(FiscalPeriod.id == period_id).first()

        if not period:
            raise PeriodNotFoundError(f"Period with ID {period_id} not found")

        if period.status == FiscalPeriodStatus.HARD_CLOSED:
            raise PeriodError(
                f"Period {period.period_name} is hard-closed and cannot be reopened. "
                "Contact system administrator."
            )

        if period.status == FiscalPeriodStatus.OPEN:
            return period  # Already open, no action needed

        old_values = serialize_for_audit(period)

        # Reopen the period
        period.status = FiscalPeriodStatus.OPEN
        period.reopened_at = datetime.utcnow()
        period.reopened_by_id = user_id
        period.updated_at = datetime.utcnow()

        self.db.flush()

        # Audit log
        new_values = serialize_for_audit(period)
        self.audit_logger.log_reopen(
            doctype="fiscal_period",
            document_id=period.id,
            user_id=user_id,
            document_name=period.period_name,
            old_values=old_values,
            new_values=new_values,
            remarks=remarks or "Period reopened",
        )

        return period

    def get_income_expense_balances(
        self,
        period: FiscalPeriod,
    ) -> List[dict]:
        """
        Get account balances for all Income and Expense accounts in a period.

        Args:
            period: The fiscal period to calculate balances for

        Returns:
            List of dicts with account info and balance
        """
        # Query GL entries for the period, grouped by account
        results = (
            self.db.query(
                GLEntry.account,
                func.sum(GLEntry.debit).label("total_debit"),
                func.sum(GLEntry.credit).label("total_credit"),
            )
            .filter(
                and_(
                    GLEntry.posting_date >= period.start_date,
                    GLEntry.posting_date <= period.end_date,
                    GLEntry.is_cancelled == False,
                )
            )
            .group_by(GLEntry.account)
            .all()
        )

        # Get account details for income/expense accounts
        balances = []
        for account_name, total_debit, total_credit in results:
            account = (
                self.db.query(Account)
                .filter(Account.account_name == account_name)
                .first()
            )

            if account and account.root_type in (AccountType.INCOME, AccountType.EXPENSE):
                balance = (total_debit or Decimal("0")) - (total_credit or Decimal("0"))

                # For income accounts, credit balance is positive (net income)
                # For expense accounts, debit balance is positive (net expense)
                balances.append({
                    "account_id": account.id,
                    "account_name": account_name,
                    "account_number": account.account_number,
                    "root_type": account.root_type,
                    "total_debit": total_debit or Decimal("0"),
                    "total_credit": total_credit or Decimal("0"),
                    "balance": balance,
                })

        return balances

    def generate_closing_entries(
        self,
        period_id: int,
        user_id: int,
        retained_earnings_account: Optional[str] = None,
        remarks: Optional[str] = None,
    ) -> JournalEntry:
        """
        Generate closing journal entries for a fiscal period.

        This creates a journal entry that:
        1. Debits all Income accounts (zeroing them out)
        2. Credits all Expense accounts (zeroing them out)
        3. Credits/Debits Retained Earnings for the net income/loss

        Args:
            period_id: ID of the period to close
            user_id: ID of the user generating the entries
            retained_earnings_account: Account name for retained earnings
            remarks: Optional remarks for the journal entry

        Returns:
            Created JournalEntry

        Raises:
            PeriodNotFoundError: If period not found
            PeriodError: If period is not soft-closed or retained earnings not configured
        """
        period = self.db.query(FiscalPeriod).filter(FiscalPeriod.id == period_id).first()

        if not period:
            raise PeriodNotFoundError(f"Period with ID {period_id} not found")

        # Get accounting controls for retained earnings account
        controls = self.db.query(AccountingControl).filter(
            AccountingControl.company.is_(None)
        ).first()

        re_account = retained_earnings_account or (
            controls.retained_earnings_account if controls else None
        )

        if not re_account:
            raise PeriodError(
                "Retained earnings account not configured. "
                "Please set up the account in Accounting Controls."
            )

        # Verify retained earnings account exists
        re_account_obj = (
            self.db.query(Account)
            .filter(Account.account_name == re_account)
            .first()
        )
        if not re_account_obj:
            raise PeriodError(
                f"Retained earnings account '{re_account}' not found in chart of accounts."
            )

        # Check period already has a closing entry
        if period.closing_journal_entry_id:
            raise PeriodError(
                f"Period {period.period_name} already has a closing entry. "
                "To regenerate, first remove the existing entry."
            )

        # Get income/expense balances
        balances = self.get_income_expense_balances(period)

        if not balances:
            raise PeriodError(
                f"No income or expense account activity found for period {period.period_name}."
            )

        # Calculate totals
        total_income = sum(
            b["total_credit"] - b["total_debit"]
            for b in balances
            if b["root_type"] == AccountType.INCOME
        )
        total_expense = sum(
            b["total_debit"] - b["total_credit"]
            for b in balances
            if b["root_type"] == AccountType.EXPENSE
        )
        net_income = total_income - total_expense

        # Create journal entry
        je = JournalEntry(
            voucher_type=JournalEntryType.JOURNAL_ENTRY,
            posting_date=period.end_date,
            total_debit=Decimal("0"),
            total_credit=Decimal("0"),
            user_remark=remarks or f"Closing entries for {period.period_name}",
            is_opening=False,
            docstatus=1,  # Posted
        )
        self.db.add(je)
        self.db.flush()

        # Create JE account lines
        total_je_debit = Decimal("0")
        total_je_credit = Decimal("0")
        idx = 0

        for balance in balances:
            if balance["balance"] == Decimal("0"):
                continue

            idx += 1

            if balance["root_type"] == AccountType.INCOME:
                # Income has credit balance, debit to close
                je_line = JournalEntryAccount(
                    journal_entry_id=je.id,
                    account=balance["account_name"],
                    debit=balance["total_credit"] - balance["total_debit"],
                    credit=Decimal("0"),
                    idx=idx,
                )
                total_je_debit += je_line.debit
            else:
                # Expense has debit balance, credit to close
                je_line = JournalEntryAccount(
                    journal_entry_id=je.id,
                    account=balance["account_name"],
                    debit=Decimal("0"),
                    credit=balance["total_debit"] - balance["total_credit"],
                    idx=idx,
                )
                total_je_credit += je_line.credit

            self.db.add(je_line)

        # Add retained earnings line
        idx += 1
        if net_income >= Decimal("0"):
            # Net income - credit retained earnings
            re_line = JournalEntryAccount(
                journal_entry_id=je.id,
                account=re_account,
                debit=Decimal("0"),
                credit=net_income,
                idx=idx,
            )
            total_je_credit += net_income
        else:
            # Net loss - debit retained earnings
            re_line = JournalEntryAccount(
                journal_entry_id=je.id,
                account=re_account,
                debit=abs(net_income),
                credit=Decimal("0"),
                idx=idx,
            )
            total_je_debit += abs(net_income)

        self.db.add(re_line)

        # Update JE totals
        je.total_debit = total_je_debit
        je.total_credit = total_je_credit

        # Link closing entry to period
        period.closing_journal_entry_id = je.id
        period.updated_at = datetime.utcnow()

        self.db.flush()

        # Audit log
        self.audit_logger.log_create(
            doctype="journal_entry",
            document_id=je.id,
            user_id=user_id,
            document_name=f"Closing-{period.period_name}",
            new_values=serialize_for_audit(je),
            remarks=f"Closing entries for period {period.period_name}. Net income: {net_income}",
        )

        return je

    def create_fiscal_periods_for_year(
        self,
        fiscal_year_id: int,
        period_type: FiscalPeriodType = FiscalPeriodType.MONTH,
        user_id: Optional[int] = None,
    ) -> List[FiscalPeriod]:
        """
        Auto-create fiscal periods for a fiscal year.

        Args:
            fiscal_year_id: ID of the fiscal year
            period_type: Type of periods to create (month/quarter)
            user_id: Optional user ID for audit

        Returns:
            List of created FiscalPeriod objects

        Raises:
            PeriodError: If fiscal year not found
        """
        from calendar import monthrange
        from dateutil.relativedelta import relativedelta

        fiscal_year = (
            self.db.query(FiscalYear)
            .filter(FiscalYear.id == fiscal_year_id)
            .first()
        )

        if not fiscal_year:
            raise PeriodError(f"Fiscal year with ID {fiscal_year_id} not found")

        if not fiscal_year.year_start_date or not fiscal_year.year_end_date:
            raise PeriodError(
                f"Fiscal year {fiscal_year.year} missing start or end date"
            )

        periods = []
        current_start = fiscal_year.year_start_date

        if period_type == FiscalPeriodType.MONTH:
            while current_start <= fiscal_year.year_end_date:
                # End of month
                _, last_day = monthrange(current_start.year, current_start.month)
                current_end = date(current_start.year, current_start.month, last_day)

                # Don't exceed fiscal year end
                if current_end > fiscal_year.year_end_date:
                    current_end = fiscal_year.year_end_date

                period_name = current_start.strftime("%Y-%m")

                # Check if period already exists
                existing = (
                    self.db.query(FiscalPeriod)
                    .filter(
                        and_(
                            FiscalPeriod.fiscal_year_id == fiscal_year_id,
                            FiscalPeriod.period_name == period_name,
                        )
                    )
                    .first()
                )

                if not existing:
                    period = FiscalPeriod(
                        fiscal_year_id=fiscal_year_id,
                        period_name=period_name,
                        period_type=FiscalPeriodType.MONTH,
                        start_date=current_start,
                        end_date=current_end,
                        status=FiscalPeriodStatus.OPEN,
                    )
                    self.db.add(period)
                    periods.append(period)

                # Move to next month
                current_start = current_end + relativedelta(days=1)

        elif period_type == FiscalPeriodType.QUARTER:
            quarter = 1
            while current_start <= fiscal_year.year_end_date:
                # End of quarter (3 months from start)
                current_end = current_start + relativedelta(months=3, days=-1)

                # Don't exceed fiscal year end
                if current_end > fiscal_year.year_end_date:
                    current_end = fiscal_year.year_end_date

                period_name = f"{fiscal_year.year}-Q{quarter}"

                # Check if period already exists
                existing = (
                    self.db.query(FiscalPeriod)
                    .filter(
                        and_(
                            FiscalPeriod.fiscal_year_id == fiscal_year_id,
                            FiscalPeriod.period_name == period_name,
                        )
                    )
                    .first()
                )

                if not existing:
                    period = FiscalPeriod(
                        fiscal_year_id=fiscal_year_id,
                        period_name=period_name,
                        period_type=FiscalPeriodType.QUARTER,
                        start_date=current_start,
                        end_date=current_end,
                        status=FiscalPeriodStatus.OPEN,
                    )
                    self.db.add(period)
                    periods.append(period)

                # Move to next quarter
                current_start = current_end + relativedelta(days=1)
                quarter += 1

        self.db.flush()

        # Audit log for batch creation
        if periods and user_id:
            self.audit_logger.log_create(
                doctype="fiscal_period",
                document_id=periods[0].id,
                user_id=user_id,
                document_name=f"Batch: {fiscal_year.year}",
                new_values={"count": len(periods), "type": period_type.value},
                remarks=f"Auto-created {len(periods)} {period_type.value} periods for {fiscal_year.year}",
            )

        return periods

    def get_period_summary(self, period_id: int) -> dict:
        """
        Get a summary of a fiscal period including status and activity.

        Args:
            period_id: ID of the period

        Returns:
            Dict with period summary info
        """
        period = self.db.query(FiscalPeriod).filter(FiscalPeriod.id == period_id).first()

        if not period:
            raise PeriodNotFoundError(f"Period with ID {period_id} not found")

        # Count GL entries in period
        gl_count = (
            self.db.query(func.count(GLEntry.id))
            .filter(
                and_(
                    GLEntry.posting_date >= period.start_date,
                    GLEntry.posting_date <= period.end_date,
                    GLEntry.is_cancelled == False,
                )
            )
            .scalar()
        )

        # Count JE entries in period
        je_count = (
            self.db.query(func.count(JournalEntry.id))
            .filter(
                and_(
                    JournalEntry.posting_date >= period.start_date,
                    JournalEntry.posting_date <= period.end_date,
                    JournalEntry.docstatus == 1,
                )
            )
            .scalar()
        )

        # Get income/expense summary
        balances = self.get_income_expense_balances(period)
        total_income = sum(
            b["total_credit"] - b["total_debit"]
            for b in balances
            if b["root_type"] == AccountType.INCOME
        )
        total_expense = sum(
            b["total_debit"] - b["total_credit"]
            for b in balances
            if b["root_type"] == AccountType.EXPENSE
        )

        return {
            "id": period.id,
            "period_name": period.period_name,
            "period_type": period.period_type.value,
            "start_date": period.start_date.isoformat(),
            "end_date": period.end_date.isoformat(),
            "status": period.status.value,
            "closed_at": period.closed_at.isoformat() if period.closed_at else None,
            "closed_by_id": period.closed_by_id,
            "has_closing_entry": period.closing_journal_entry_id is not None,
            "closing_journal_entry_id": period.closing_journal_entry_id,
            "gl_entry_count": gl_count,
            "journal_entry_count": je_count,
            "total_income": str(total_income),
            "total_expense": str(total_expense),
            "net_income": str(total_income - total_expense),
        }
