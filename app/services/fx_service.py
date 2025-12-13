"""
Foreign Exchange Service

Provides exchange rate lookups and currency revaluation functionality:
- Get exchange rate for a currency pair on a specific date
- Calculate unrealized gains/losses on foreign currency balances
- Generate revaluation journal entries
"""
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc

from app.models.accounting_ext import (
    ExchangeRate,
    ExchangeRateSource,
    RevaluationEntry,
    FiscalPeriod,
    AccountingControl,
)
from app.models.accounting import (
    Account,
    AccountType,
    GLEntry,
    JournalEntry,
    JournalEntryAccount,
    JournalEntryType,
)
from app.services.audit_logger import AuditLogger, serialize_for_audit


class FXError(Exception):
    """Exception raised for FX-related errors."""
    pass


class RateNotFoundError(FXError):
    """Raised when exchange rate is not found."""
    pass


class FXService:
    """Service for foreign exchange operations."""

    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = AuditLogger(db)

    def get_rate(
        self,
        from_currency: str,
        to_currency: str,
        rate_date: date,
        fallback_to_latest: bool = True,
    ) -> Optional[Decimal]:
        """
        Get exchange rate for a currency pair on a specific date.

        Args:
            from_currency: Source currency code (e.g., "USD")
            to_currency: Target currency code (e.g., "NGN")
            rate_date: Date to get rate for
            fallback_to_latest: If True, use latest available rate if exact date not found

        Returns:
            Exchange rate as Decimal, or None if not found
        """
        from_curr = from_currency.upper()
        to_curr = to_currency.upper()

        # Same currency - rate is 1
        if from_curr == to_curr:
            return Decimal("1")

        # Try exact date first
        rate = (
            self.db.query(ExchangeRate)
            .filter(
                and_(
                    ExchangeRate.from_currency == from_curr,
                    ExchangeRate.to_currency == to_curr,
                    ExchangeRate.rate_date == rate_date,
                )
            )
            .first()
        )

        if rate:
            return rate.rate

        # Try reverse rate
        reverse_rate = (
            self.db.query(ExchangeRate)
            .filter(
                and_(
                    ExchangeRate.from_currency == to_curr,
                    ExchangeRate.to_currency == from_curr,
                    ExchangeRate.rate_date == rate_date,
                )
            )
            .first()
        )

        if reverse_rate and reverse_rate.rate != Decimal("0"):
            return Decimal("1") / reverse_rate.rate

        # Fallback to latest available rate
        if fallback_to_latest:
            latest = (
                self.db.query(ExchangeRate)
                .filter(
                    and_(
                        ExchangeRate.from_currency == from_curr,
                        ExchangeRate.to_currency == to_curr,
                        ExchangeRate.rate_date <= rate_date,
                    )
                )
                .order_by(desc(ExchangeRate.rate_date))
                .first()
            )

            if latest:
                return latest.rate

            # Try reverse latest
            reverse_latest = (
                self.db.query(ExchangeRate)
                .filter(
                    and_(
                        ExchangeRate.from_currency == to_curr,
                        ExchangeRate.to_currency == from_curr,
                        ExchangeRate.rate_date <= rate_date,
                    )
                )
                .order_by(desc(ExchangeRate.rate_date))
                .first()
            )

            if reverse_latest and reverse_latest.rate != Decimal("0"):
                return Decimal("1") / reverse_latest.rate

        return None

    def get_rate_or_raise(
        self,
        from_currency: str,
        to_currency: str,
        rate_date: date,
    ) -> Decimal:
        """Get exchange rate or raise RateNotFoundError."""
        rate = self.get_rate(from_currency, to_currency, rate_date)
        if rate is None:
            raise RateNotFoundError(
                f"No exchange rate found for {from_currency}/{to_currency} on or before {rate_date}"
            )
        return rate

    def convert(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        rate_date: date,
    ) -> Decimal:
        """
        Convert amount from one currency to another.

        Args:
            amount: Amount to convert
            from_currency: Source currency
            to_currency: Target currency
            rate_date: Date for exchange rate

        Returns:
            Converted amount
        """
        rate = self.get_rate_or_raise(from_currency, to_currency, rate_date)
        return amount * rate

    def get_foreign_currency_accounts(self, base_currency: str = "NGN") -> List[Account]:
        """
        Get all accounts that may have foreign currency balances.

        These are typically Asset and Liability accounts that can hold
        balances in currencies other than the base currency.
        """
        return (
            self.db.query(Account)
            .filter(
                and_(
                    Account.root_type.in_([AccountType.ASSET, AccountType.LIABILITY]),
                    Account.is_group == False,
                    Account.disabled == False,
                )
            )
            .all()
        )

    def calculate_unrealized_gains_losses(
        self,
        period: FiscalPeriod,
        base_currency: str = "NGN",
    ) -> List[Dict[str, Any]]:
        """
        Calculate unrealized FX gains/losses for foreign currency accounts.

        For each account with foreign currency balance:
        1. Get the original balance in foreign currency
        2. Get the current exchange rate
        3. Calculate the revalued amount in base currency
        4. Determine gain/loss vs. book value

        Args:
            period: Fiscal period to calculate for
            base_currency: Base/functional currency

        Returns:
            List of dicts with account revaluation details
        """
        results = []

        # Get accounts with potential FX exposure
        # In a real implementation, you'd track currency per account or GL entry
        # For now, we'll look for accounts with currency indicators in their names
        # or use GL entries with account_currency different from base

        # Get unique currencies from GL entries
        currencies_query = (
            self.db.query(func.distinct(GLEntry.voucher_type))
            .filter(
                and_(
                    GLEntry.posting_date <= period.end_date,
                    GLEntry.is_cancelled == False,
                )
            )
            .all()
        )

        # For each foreign currency account, calculate revaluation
        accounts = self.get_foreign_currency_accounts(base_currency)

        for account in accounts:
            # Get account balance in account currency
            balance_result = (
                self.db.query(
                    func.sum(GLEntry.debit_in_account_currency).label("debit"),
                    func.sum(GLEntry.credit_in_account_currency).label("credit"),
                    func.sum(GLEntry.debit).label("debit_base"),
                    func.sum(GLEntry.credit).label("credit_base"),
                )
                .filter(
                    and_(
                        GLEntry.account == account.account_name,
                        GLEntry.posting_date <= period.end_date,
                        GLEntry.is_cancelled == False,
                    )
                )
                .first()
            )

            if not balance_result:
                continue

            debit_fc = balance_result.debit or Decimal("0")
            credit_fc = balance_result.credit or Decimal("0")
            debit_base = balance_result.debit_base or Decimal("0")
            credit_base = balance_result.credit_base or Decimal("0")

            balance_fc = debit_fc - credit_fc
            balance_base = debit_base - credit_base

            # Skip if no foreign currency activity
            if balance_fc == Decimal("0") or balance_fc == balance_base:
                continue

            # Determine the foreign currency (simplified - assume USD for non-NGN amounts)
            # In production, you'd track this per GL entry or account
            foreign_currency = "USD"  # Placeholder

            # Get current rate
            current_rate = self.get_rate(foreign_currency, base_currency, period.end_date)
            if not current_rate:
                continue

            # Calculate revalued amount
            revalued_amount = balance_fc * current_rate
            gain_loss = revalued_amount - balance_base

            if abs(gain_loss) > Decimal("0.01"):  # Ignore tiny differences
                results.append({
                    "account_id": account.id,
                    "account_name": account.account_name,
                    "account_number": account.account_number,
                    "original_currency": foreign_currency,
                    "original_amount": balance_fc,
                    "book_value_base": balance_base,
                    "exchange_rate": current_rate,
                    "revalued_amount": revalued_amount,
                    "gain_loss": gain_loss,
                    "is_gain": gain_loss > Decimal("0"),
                })

        return results

    def preview_revaluation(
        self,
        period_id: int,
        base_currency: str = "NGN",
    ) -> Dict[str, Any]:
        """
        Preview FX revaluation for a fiscal period without posting.

        Args:
            period_id: Fiscal period ID
            base_currency: Base/functional currency

        Returns:
            Dict with revaluation preview details
        """
        period = self.db.query(FiscalPeriod).filter(FiscalPeriod.id == period_id).first()
        if not period:
            raise FXError(f"Fiscal period {period_id} not found")

        entries = self.calculate_unrealized_gains_losses(period, base_currency)

        total_gain = sum(e["gain_loss"] for e in entries if e["gain_loss"] > 0)
        total_loss = sum(abs(e["gain_loss"]) for e in entries if e["gain_loss"] < 0)
        net_gain_loss = total_gain - total_loss

        return {
            "period_id": period.id,
            "period_name": period.period_name,
            "as_of_date": period.end_date.isoformat(),
            "base_currency": base_currency,
            "entries": [
                {
                    "account_id": e["account_id"],
                    "account_name": e["account_name"],
                    "original_currency": e["original_currency"],
                    "original_amount": str(e["original_amount"]),
                    "book_value": str(e["book_value_base"]),
                    "exchange_rate": str(e["exchange_rate"]),
                    "revalued_amount": str(e["revalued_amount"]),
                    "gain_loss": str(e["gain_loss"]),
                    "type": "gain" if e["is_gain"] else "loss",
                }
                for e in entries
            ],
            "summary": {
                "total_accounts": len(entries),
                "total_gain": str(total_gain),
                "total_loss": str(total_loss),
                "net_gain_loss": str(net_gain_loss),
            },
        }

    def apply_revaluation(
        self,
        period_id: int,
        user_id: int,
        base_currency: str = "NGN",
        fx_gain_account: Optional[str] = None,
        fx_loss_account: Optional[str] = None,
    ) -> JournalEntry:
        """
        Apply FX revaluation by creating adjustment journal entries.

        Args:
            period_id: Fiscal period ID
            user_id: User applying the revaluation
            base_currency: Base/functional currency
            fx_gain_account: Account for FX gains (defaults from controls)
            fx_loss_account: Account for FX losses (defaults from controls)

        Returns:
            Created JournalEntry

        Raises:
            FXError: If revaluation fails
        """
        period = self.db.query(FiscalPeriod).filter(FiscalPeriod.id == period_id).first()
        if not period:
            raise FXError(f"Fiscal period {period_id} not found")

        # Block revaluation on hard-closed periods
        if period.status == FiscalPeriodStatus.HARD_CLOSED:
            raise FXError(f"Period {period.period_name} is hard-closed and cannot be revalued")

        # Prevent duplicate revaluation for this period/base currency
        existing = (
            self.db.query(RevaluationEntry)
            .filter(
                RevaluationEntry.fiscal_period_id == period.id,
                RevaluationEntry.base_currency == base_currency,
            )
            .first()
        )
        if existing:
            raise FXError(f"Revaluation for period {period.period_name} and base currency {base_currency} already exists")

        # Get FX accounts from controls if not provided
        controls = self.db.query(AccountingControl).filter(
            AccountingControl.company.is_(None)
        ).first()

        gain_account = fx_gain_account or (controls.fx_gain_account if controls else None)
        loss_account = fx_loss_account or (controls.fx_loss_account if controls else None)

        if not gain_account or not loss_account:
            raise FXError(
                "FX gain and loss accounts not configured. "
                "Set them in Accounting Controls or provide as parameters."
            )

        # Calculate revaluation entries
        entries = self.calculate_unrealized_gains_losses(period, base_currency)

        if not entries:
            raise FXError("No foreign currency balances to revalue")

        # Create journal entry
        je = JournalEntry(
            voucher_type=JournalEntryType.EXCHANGE_RATE_REVALUATION,
            posting_date=period.end_date,
            user_remark=f"FX Revaluation for {period.period_name}",
            total_debit=Decimal("0"),
            total_credit=Decimal("0"),
            docstatus=1,  # Posted
        )
        self.db.add(je)
        self.db.flush()

        total_debit = Decimal("0")
        total_credit = Decimal("0")
        idx = 0

        # Create revaluation entries and JE lines
        for entry in entries:
            gain_loss = entry["gain_loss"]

            # Create RevaluationEntry record
            reval_entry = RevaluationEntry(
                fiscal_period_id=period.id,
                account_id=entry["account_id"],
                account_name=entry["account_name"],
                original_currency=entry["original_currency"],
                original_amount=entry["original_amount"],
                base_currency=base_currency,
                exchange_rate_used=entry["exchange_rate"],
                revalued_amount=entry["revalued_amount"],
                gain_loss_amount=gain_loss,
                is_realized=False,
                journal_entry_id=je.id,
                created_by_id=user_id,
            )
            self.db.add(reval_entry)

            # Create JE lines
            idx += 1

            if gain_loss > Decimal("0"):
                # Gain: Debit the account, Credit FX Gain
                # Debit account (increase asset or decrease liability)
                je_line_account = JournalEntryAccount(
                    journal_entry_id=je.id,
                    account=entry["account_id"] or entry["account_name"],
                    debit=gain_loss,
                    credit=Decimal("0"),
                    idx=idx,
                    user_remark=f"FX revaluation gain - {entry['original_currency']}",
                )
                self.db.add(je_line_account)
                total_debit += gain_loss

                idx += 1
                # Credit FX Gain (income)
                je_line_gain = JournalEntryAccount(
                    journal_entry_id=je.id,
                    account=gain_account,
                    debit=Decimal("0"),
                    credit=gain_loss,
                    idx=idx,
                    user_remark=f"FX gain on {entry['account_name']}",
                )
                self.db.add(je_line_gain)
                total_credit += gain_loss

            else:
                # Loss: Credit the account, Debit FX Loss
                loss_amount = abs(gain_loss)

                # Credit account (decrease asset or increase liability)
                je_line_account = JournalEntryAccount(
                    journal_entry_id=je.id,
                    account=entry["account_id"] or entry["account_name"],
                    debit=Decimal("0"),
                    credit=loss_amount,
                    idx=idx,
                    user_remark=f"FX revaluation loss - {entry['original_currency']}",
                )
                self.db.add(je_line_account)
                total_credit += loss_amount

                idx += 1
                # Debit FX Loss (expense)
                je_line_loss = JournalEntryAccount(
                    journal_entry_id=je.id,
                    account=loss_account,
                    debit=loss_amount,
                    credit=Decimal("0"),
                    idx=idx,
                    user_remark=f"FX loss on {entry['account_name']}",
                )
                self.db.add(je_line_loss)
                total_debit += loss_amount

        # Update JE totals
        je.total_debit = total_debit
        je.total_credit = total_credit

        self.db.flush()

        # Audit log
        self.audit_logger.log_create(
            doctype="journal_entry",
            document_id=je.id,
            user_id=user_id,
            document_name=f"FX-Reval-{period.period_name}",
            new_values=serialize_for_audit(je),
            remarks=f"FX Revaluation: {len(entries)} accounts, net {total_debit - total_credit}",
        )

        return je

    def get_revaluation_history(
        self,
        period_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get history of FX revaluations.

        Args:
            period_id: Optional filter by period
            limit: Max records to return

        Returns:
            List of revaluation summaries
        """
        query = self.db.query(RevaluationEntry)

        if period_id:
            query = query.filter(RevaluationEntry.fiscal_period_id == period_id)

        entries = query.order_by(desc(RevaluationEntry.created_at)).limit(limit).all()

        # Group by journal entry
        je_groups: Dict[int, List[RevaluationEntry]] = {}
        for entry in entries:
            je_id = entry.journal_entry_id
            if je_id not in je_groups:
                je_groups[je_id] = []
            je_groups[je_id].append(entry)

        results = []
        for je_id, group in je_groups.items():
            period = self.db.query(FiscalPeriod).filter(
                FiscalPeriod.id == group[0].fiscal_period_id
            ).first()

            total_gain = sum(e.gain_loss_amount for e in group if e.gain_loss_amount > 0)
            total_loss = sum(abs(e.gain_loss_amount) for e in group if e.gain_loss_amount < 0)

            results.append({
                "journal_entry_id": je_id,
                "period_id": group[0].fiscal_period_id,
                "period_name": period.period_name if period else None,
                "created_at": group[0].created_at.isoformat(),
                "account_count": len(group),
                "total_gain": str(total_gain),
                "total_loss": str(total_loss),
                "net_gain_loss": str(total_gain - total_loss),
            })

        return results
