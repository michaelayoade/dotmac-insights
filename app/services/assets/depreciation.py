"""Depreciation service - business logic for asset depreciation.

This service encapsulates all depreciation-related business logic:
- Schedule calculation (straight-line, declining balance, written-down value)
- Pending depreciation queries
- GL posting via journal entries
- Batch depreciation posting

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING, List, Optional, Tuple

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, selectinload

from app.models.asset import (
    Asset,
    AssetCategory,
    AssetDepreciationSchedule,
    AssetFinanceBook,
    AssetStatus,
)
from app.models.accounting import Account, JournalEntry, JournalEntryItem

from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams
from app.services.base import paginate

from .types import (
    DepreciationMethod,
    DepreciationScheduleRow,
    PendingDepreciation,
    DepreciationPostResult,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["DepreciationService"]


class DepreciationService:
    """Service for depreciation business logic.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for audit fields).
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Schedule Calculation
    # -------------------------------------------------------------------------

    def calculate_depreciation_schedule(
        self,
        asset: Asset,
        finance_book: AssetFinanceBook,
    ) -> List[DepreciationScheduleRow]:
        """Calculate depreciation schedule for an asset's finance book.

        Args:
            asset: The asset to calculate depreciation for.
            finance_book: The finance book settings to use.

        Returns:
            List of DepreciationScheduleRow for the schedule.

        Raises:
            ValidationError: If calculation cannot be performed.
        """
        if not asset.calculate_depreciation:
            return []

        method = finance_book.depreciation_method or DepreciationMethod.STRAIGHT_LINE.value
        start_date = finance_book.depreciation_start_date or asset.available_for_use_date

        if not start_date:
            raise ValidationError("Depreciation start date is required")

        total_depreciations = finance_book.total_number_of_depreciations or 60
        frequency = finance_book.frequency_of_depreciation or 12  # months

        # Calculate depreciable amount
        purchase_amount = asset.gross_purchase_amount or Decimal("0")
        opening_depreciation = asset.opening_accumulated_depreciation or Decimal("0")
        salvage_value = finance_book.expected_value_after_useful_life or Decimal("0")

        depreciable_amount = purchase_amount - opening_depreciation - salvage_value

        if depreciable_amount <= Decimal("0"):
            return []

        # Generate schedule based on method
        if method == DepreciationMethod.STRAIGHT_LINE.value:
            return self._calculate_straight_line(
                start_date=start_date,
                depreciable_amount=depreciable_amount,
                opening_depreciation=opening_depreciation,
                total_depreciations=total_depreciations,
                frequency=frequency,
            )
        elif method == DepreciationMethod.DOUBLE_DECLINING_BALANCE.value:
            return self._calculate_double_declining(
                start_date=start_date,
                purchase_amount=purchase_amount,
                opening_depreciation=opening_depreciation,
                salvage_value=salvage_value,
                total_depreciations=total_depreciations,
                frequency=frequency,
            )
        elif method == DepreciationMethod.WRITTEN_DOWN_VALUE.value:
            rate = finance_book.rate_of_depreciation or Decimal("20")  # Default 20%
            return self._calculate_written_down_value(
                start_date=start_date,
                purchase_amount=purchase_amount,
                opening_depreciation=opening_depreciation,
                salvage_value=salvage_value,
                rate=rate,
                total_depreciations=total_depreciations,
                frequency=frequency,
            )
        else:
            # Manual or unknown - no auto calculation
            return []

    def _calculate_straight_line(
        self,
        start_date: date,
        depreciable_amount: Decimal,
        opening_depreciation: Decimal,
        total_depreciations: int,
        frequency: int,
    ) -> List[DepreciationScheduleRow]:
        """Calculate straight-line depreciation schedule.

        Formula: depreciation = (cost - salvage) / useful_life
        """
        if total_depreciations <= 0:
            return []

        # Calculate period depreciation
        period_depreciation = (depreciable_amount / Decimal(total_depreciations)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # Calculate interval between periods
        months_per_period = 12 // frequency if frequency > 0 else 1

        schedule = []
        accumulated = opening_depreciation
        remaining = depreciable_amount

        for i in range(total_depreciations):
            # Calculate schedule date
            schedule_date = start_date + relativedelta(months=i * months_per_period)

            # Last period takes remainder to avoid rounding issues
            if i == total_depreciations - 1:
                depreciation = remaining
            else:
                depreciation = min(period_depreciation, remaining)

            accumulated += depreciation
            remaining -= depreciation
            book_value = depreciable_amount + opening_depreciation - accumulated

            if depreciation > Decimal("0"):
                schedule.append(DepreciationScheduleRow(
                    schedule_date=schedule_date,
                    depreciation_amount=depreciation,
                    accumulated_depreciation=accumulated,
                    book_value=max(book_value, Decimal("0")),
                ))

        return schedule

    def _calculate_double_declining(
        self,
        start_date: date,
        purchase_amount: Decimal,
        opening_depreciation: Decimal,
        salvage_value: Decimal,
        total_depreciations: int,
        frequency: int,
    ) -> List[DepreciationScheduleRow]:
        """Calculate double declining balance depreciation.

        Formula: depreciation = 2 * (1/useful_life) * book_value
        """
        if total_depreciations <= 0:
            return []

        # Double declining rate
        rate = Decimal("2") / Decimal(total_depreciations)
        months_per_period = 12 // frequency if frequency > 0 else 1

        schedule = []
        book_value = purchase_amount - opening_depreciation
        accumulated = opening_depreciation

        for i in range(total_depreciations):
            schedule_date = start_date + relativedelta(months=i * months_per_period)

            # Stop if at salvage value
            if book_value <= salvage_value:
                break

            # Calculate depreciation
            depreciation = (book_value * rate).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            # Don't depreciate below salvage value
            max_depreciation = book_value - salvage_value
            depreciation = min(depreciation, max_depreciation)

            if depreciation <= Decimal("0"):
                break

            accumulated += depreciation
            book_value -= depreciation

            schedule.append(DepreciationScheduleRow(
                schedule_date=schedule_date,
                depreciation_amount=depreciation,
                accumulated_depreciation=accumulated,
                book_value=book_value,
            ))

        return schedule

    def _calculate_written_down_value(
        self,
        start_date: date,
        purchase_amount: Decimal,
        opening_depreciation: Decimal,
        salvage_value: Decimal,
        rate: Decimal,
        total_depreciations: int,
        frequency: int,
    ) -> List[DepreciationScheduleRow]:
        """Calculate written down value (reducing balance) depreciation.

        Formula: depreciation = rate% * book_value
        """
        if total_depreciations <= 0:
            return []

        # Convert rate to decimal (e.g., 20% -> 0.20)
        rate_decimal = rate / Decimal("100")
        months_per_period = 12 // frequency if frequency > 0 else 1

        schedule = []
        book_value = purchase_amount - opening_depreciation
        accumulated = opening_depreciation

        for i in range(total_depreciations):
            schedule_date = start_date + relativedelta(months=i * months_per_period)

            # Stop if at salvage value
            if book_value <= salvage_value:
                break

            # Calculate depreciation
            depreciation = (book_value * rate_decimal).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            # Don't depreciate below salvage value
            max_depreciation = book_value - salvage_value
            depreciation = min(depreciation, max_depreciation)

            if depreciation <= Decimal("0"):
                break

            accumulated += depreciation
            book_value -= depreciation

            schedule.append(DepreciationScheduleRow(
                schedule_date=schedule_date,
                depreciation_amount=depreciation,
                accumulated_depreciation=accumulated,
                book_value=book_value,
            ))

        return schedule

    # -------------------------------------------------------------------------
    # Pending Depreciation Queries
    # -------------------------------------------------------------------------

    def get_pending_depreciation(
        self,
        as_of_date: Optional[date] = None,
        finance_book: Optional[str] = None,
    ) -> List[PendingDepreciation]:
        """Get all pending depreciation entries due as of a date.

        Args:
            as_of_date: Date to check (defaults to today).
            finance_book: Filter by finance book (None = all books).

        Returns:
            List of PendingDepreciation entries ready to be posted.
        """
        if as_of_date is None:
            as_of_date = date.today()

        # Query pending schedules
        query = (
            self.db.query(AssetDepreciationSchedule)
            .join(Asset, Asset.id == AssetDepreciationSchedule.asset_id)
            .filter(
                AssetDepreciationSchedule.depreciation_booked == False,
                AssetDepreciationSchedule.schedule_date <= as_of_date,
                Asset.status.in_([
                    AssetStatus.SUBMITTED,
                    AssetStatus.PARTIALLY_DEPRECIATED,
                ]),
            )
            .order_by(
                AssetDepreciationSchedule.schedule_date,
                Asset.asset_name,
            )
        )

        if finance_book is not None:
            query = query.filter(AssetDepreciationSchedule.finance_book == finance_book)

        schedules = query.all()

        # Build pending list with GL accounts
        pending_list = []
        for schedule in schedules:
            asset = self.db.query(Asset).filter(Asset.id == schedule.asset_id).first()
            if not asset:
                continue

            # Get GL accounts from category
            accounts = self._get_depreciation_accounts(asset.asset_category, schedule.finance_book)

            # Calculate book value before and after
            book_value_before = asset.asset_value
            book_value_after = book_value_before - schedule.depreciation_amount

            pending_list.append(PendingDepreciation(
                asset_id=asset.id,
                asset_name=asset.asset_name,
                asset_category=asset.asset_category or "",
                schedule_id=schedule.id,
                schedule_date=schedule.schedule_date,
                depreciation_amount=schedule.depreciation_amount,
                accumulated_depreciation=schedule.accumulated_depreciation_amount,
                book_value_before=book_value_before,
                book_value_after=book_value_after,
                depreciation_expense_account=accounts[0],
                accumulated_depreciation_account=accounts[1],
            ))

        return pending_list

    def get_pending_depreciation_for_asset(
        self,
        asset_id: int,
        as_of_date: Optional[date] = None,
    ) -> List[PendingDepreciation]:
        """Get pending depreciation entries for a specific asset.

        Args:
            asset_id: The asset ID.
            as_of_date: Date to check (defaults to today).

        Returns:
            List of PendingDepreciation entries.
        """
        if as_of_date is None:
            as_of_date = date.today()

        asset = self.db.query(Asset).filter(Asset.id == asset_id).first()
        if not asset:
            raise NotFoundError(f"Asset {asset_id} not found")

        schedules = (
            self.db.query(AssetDepreciationSchedule)
            .filter(
                AssetDepreciationSchedule.asset_id == asset_id,
                AssetDepreciationSchedule.depreciation_booked == False,
                AssetDepreciationSchedule.schedule_date <= as_of_date,
            )
            .order_by(AssetDepreciationSchedule.schedule_date)
            .all()
        )

        pending_list = []
        book_value = asset.asset_value

        for schedule in schedules:
            accounts = self._get_depreciation_accounts(asset.asset_category, schedule.finance_book)
            book_value_after = book_value - schedule.depreciation_amount

            pending_list.append(PendingDepreciation(
                asset_id=asset.id,
                asset_name=asset.asset_name,
                asset_category=asset.asset_category or "",
                schedule_id=schedule.id,
                schedule_date=schedule.schedule_date,
                depreciation_amount=schedule.depreciation_amount,
                accumulated_depreciation=schedule.accumulated_depreciation_amount,
                book_value_before=book_value,
                book_value_after=book_value_after,
                depreciation_expense_account=accounts[0],
                accumulated_depreciation_account=accounts[1],
            ))

            book_value = book_value_after

        return pending_list

    def _get_depreciation_accounts(
        self, category_name: Optional[str], finance_book: Optional[str]
    ) -> Tuple[Optional[str], Optional[str]]:
        """Get depreciation expense and accumulated depreciation accounts.

        Returns:
            Tuple of (depreciation_expense_account, accumulated_depreciation_account)
        """
        if not category_name:
            return (None, None)

        from app.models.asset import AssetCategory, AssetCategoryFinanceBook

        category = (
            self.db.query(AssetCategory)
            .options(selectinload(AssetCategory.finance_books))
            .filter(AssetCategory.asset_category_name == category_name)
            .first()
        )

        if not category or not category.finance_books:
            return (None, None)

        # Find matching finance book
        fb = None
        for cat_fb in category.finance_books:
            if cat_fb.finance_book == finance_book:
                fb = cat_fb
                break

        # Fall back to first
        if not fb:
            fb = category.finance_books[0]

        return (fb.depreciation_expense_account, fb.accumulated_depreciation_account)

    # -------------------------------------------------------------------------
    # Post Depreciation
    # -------------------------------------------------------------------------

    def post_depreciation(self, schedule_id: int) -> DepreciationPostResult:
        """Post a single depreciation entry to GL.

        Creates a journal entry for the depreciation.

        Args:
            schedule_id: The depreciation schedule ID.

        Returns:
            DepreciationPostResult with journal entry details.

        Raises:
            NotFoundError: If schedule not found.
            ValidationError: If already posted or accounts not configured.
        """
        schedule = (
            self.db.query(AssetDepreciationSchedule)
            .filter(AssetDepreciationSchedule.id == schedule_id)
            .first()
        )
        if not schedule:
            raise NotFoundError(f"Depreciation schedule {schedule_id} not found")

        if schedule.depreciation_booked:
            raise ValidationError("Depreciation already posted")

        asset = self.db.query(Asset).filter(Asset.id == schedule.asset_id).first()
        if not asset:
            raise NotFoundError(f"Asset for schedule {schedule_id} not found")

        # Get accounts
        expense_account, accum_account = self._get_depreciation_accounts(
            asset.asset_category, schedule.finance_book
        )

        if not expense_account or not accum_account:
            raise ValidationError(
                f"GL accounts not configured for category '{asset.asset_category}'"
            )

        # Create journal entry
        journal_entry = self._create_depreciation_journal_entry(
            asset=asset,
            schedule=schedule,
            expense_account=expense_account,
            accum_account=accum_account,
        )

        # Mark schedule as booked
        schedule.depreciation_booked = True
        schedule.journal_entry = str(journal_entry.id)

        # Update asset value
        asset.asset_value -= schedule.depreciation_amount

        # Update asset status if needed
        if asset.asset_value <= Decimal("0"):
            asset.status = AssetStatus.FULLY_DEPRECIATED
        elif asset.status == AssetStatus.SUBMITTED:
            asset.status = AssetStatus.PARTIALLY_DEPRECIATED

        # Find next depreciation date
        next_schedule = (
            self.db.query(AssetDepreciationSchedule)
            .filter(
                AssetDepreciationSchedule.asset_id == asset.id,
                AssetDepreciationSchedule.depreciation_booked == False,
            )
            .order_by(AssetDepreciationSchedule.schedule_date)
            .first()
        )
        asset.next_depreciation_date = next_schedule.schedule_date if next_schedule else None

        self.db.flush()

        return DepreciationPostResult(
            journal_entry_id=journal_entry.id,
            journal_entry_number=journal_entry.erpnext_id or str(journal_entry.id),
            schedules_posted=1,
            total_depreciation=schedule.depreciation_amount,
        )

    def post_depreciation_batch(
        self, schedule_ids: List[int]
    ) -> DepreciationPostResult:
        """Post multiple depreciation entries in a single journal entry.

        Groups all schedules into one journal entry for efficiency.

        Args:
            schedule_ids: List of depreciation schedule IDs.

        Returns:
            DepreciationPostResult with journal entry details.

        Raises:
            ValidationError: If any schedule is invalid.
        """
        if not schedule_ids:
            raise ValidationError("No schedules provided")

        schedules = (
            self.db.query(AssetDepreciationSchedule)
            .filter(AssetDepreciationSchedule.id.in_(schedule_ids))
            .all()
        )

        if len(schedules) != len(schedule_ids):
            raise ValidationError("Some schedules not found")

        # Validate all schedules
        total_depreciation = Decimal("0")
        entries_by_account: dict = {}  # (expense, accum) -> amount

        for schedule in schedules:
            if schedule.depreciation_booked:
                raise ValidationError(f"Schedule {schedule.id} already posted")

            asset = self.db.query(Asset).filter(Asset.id == schedule.asset_id).first()
            if not asset:
                raise ValidationError(f"Asset for schedule {schedule.id} not found")

            expense_account, accum_account = self._get_depreciation_accounts(
                asset.asset_category, schedule.finance_book
            )

            if not expense_account or not accum_account:
                raise ValidationError(
                    f"GL accounts not configured for category '{asset.asset_category}'"
                )

            key = (expense_account, accum_account)
            entries_by_account[key] = entries_by_account.get(key, Decimal("0")) + schedule.depreciation_amount
            total_depreciation += schedule.depreciation_amount

        # Create single journal entry
        journal_entry = self._create_batch_depreciation_journal_entry(
            entries_by_account=entries_by_account,
            posting_date=date.today(),
        )

        # Mark all schedules as booked and update assets
        for schedule in schedules:
            schedule.depreciation_booked = True
            schedule.journal_entry = str(journal_entry.id)

            asset = self.db.query(Asset).filter(Asset.id == schedule.asset_id).first()
            if asset:
                asset.asset_value -= schedule.depreciation_amount

                if asset.asset_value <= Decimal("0"):
                    asset.status = AssetStatus.FULLY_DEPRECIATED
                elif asset.status == AssetStatus.SUBMITTED:
                    asset.status = AssetStatus.PARTIALLY_DEPRECIATED

                # Update next depreciation date
                next_schedule = (
                    self.db.query(AssetDepreciationSchedule)
                    .filter(
                        AssetDepreciationSchedule.asset_id == asset.id,
                        AssetDepreciationSchedule.depreciation_booked == False,
                    )
                    .order_by(AssetDepreciationSchedule.schedule_date)
                    .first()
                )
                asset.next_depreciation_date = next_schedule.schedule_date if next_schedule else None

        self.db.flush()

        return DepreciationPostResult(
            journal_entry_id=journal_entry.id,
            journal_entry_number=journal_entry.erpnext_id or str(journal_entry.id),
            schedules_posted=len(schedules),
            total_depreciation=total_depreciation,
        )

    def _create_depreciation_journal_entry(
        self,
        asset: Asset,
        schedule: AssetDepreciationSchedule,
        expense_account: str,
        accum_account: str,
    ) -> JournalEntry:
        """Create a journal entry for a single depreciation."""
        je = JournalEntry(
            voucher_type="Depreciation Entry",
            posting_date=datetime.combine(schedule.schedule_date, datetime.min.time()),
            user_remark=f"Depreciation for {asset.asset_name} - {schedule.schedule_date}",
            company=asset.company or "Default Company",
            total_debit=schedule.depreciation_amount,
            total_credit=schedule.depreciation_amount,
            docstatus=1,  # Posted
        )
        self.db.add(je)
        self.db.flush()

        # Generate entry number
        je.erpnext_id = f"DEP-{je.id:06d}"

        # Debit expense account
        expense_account_obj = (
            self.db.query(Account).filter(Account.account_name == expense_account).first()
        )
        expense_item = JournalEntryItem(
            journal_entry_id=je.id,
            account=expense_account,
            account_id=expense_account_obj.id if expense_account_obj else None,
            debit=schedule.depreciation_amount,
            credit=Decimal("0"),
            debit_in_account_currency=schedule.depreciation_amount,
            credit_in_account_currency=Decimal("0"),
            exchange_rate=Decimal("1"),
        )
        self.db.add(expense_item)

        # Credit accumulated depreciation account
        accum_account_obj = (
            self.db.query(Account).filter(Account.account_name == accum_account).first()
        )
        accum_item = JournalEntryItem(
            journal_entry_id=je.id,
            account=accum_account,
            account_id=accum_account_obj.id if accum_account_obj else None,
            debit=Decimal("0"),
            credit=schedule.depreciation_amount,
            debit_in_account_currency=Decimal("0"),
            credit_in_account_currency=schedule.depreciation_amount,
            exchange_rate=Decimal("1"),
        )
        self.db.add(accum_item)

        self.db.flush()
        return je

    def _create_batch_depreciation_journal_entry(
        self,
        entries_by_account: dict,
        posting_date: date,
    ) -> JournalEntry:
        """Create a journal entry for batch depreciation."""
        total = sum(entries_by_account.values())

        je = JournalEntry(
            voucher_type="Depreciation Entry",
            posting_date=datetime.combine(posting_date, datetime.min.time()),
            user_remark=f"Batch depreciation for {posting_date}",
            company="Default Company",
            total_debit=total,
            total_credit=total,
            docstatus=1,  # Posted
        )
        self.db.add(je)
        self.db.flush()

        je.erpnext_id = f"DEP-{je.id:06d}"

        for (expense_account, accum_account), amount in entries_by_account.items():
            # Debit expense
            expense_account_obj = (
                self.db.query(Account).filter(Account.account_name == expense_account).first()
            )
            expense_item = JournalEntryItem(
                journal_entry_id=je.id,
                account=expense_account,
                account_id=expense_account_obj.id if expense_account_obj else None,
                debit=amount,
                credit=Decimal("0"),
                debit_in_account_currency=amount,
                credit_in_account_currency=Decimal("0"),
                exchange_rate=Decimal("1"),
            )
            self.db.add(expense_item)

            # Credit accumulated
            accum_account_obj = (
                self.db.query(Account).filter(Account.account_name == accum_account).first()
            )
            accum_item = JournalEntryItem(
                journal_entry_id=je.id,
                account=accum_account,
                account_id=accum_account_obj.id if accum_account_obj else None,
                debit=Decimal("0"),
                credit=amount,
                debit_in_account_currency=Decimal("0"),
                credit_in_account_currency=amount,
                exchange_rate=Decimal("1"),
            )
            self.db.add(accum_item)

        self.db.flush()
        return je

    # -------------------------------------------------------------------------
    # Reverse Depreciation
    # -------------------------------------------------------------------------

    def reverse_depreciation(self, schedule_id: int) -> DepreciationPostResult:
        """Reverse a posted depreciation entry.

        Creates a reversal journal entry.

        Args:
            schedule_id: The depreciation schedule ID.

        Returns:
            DepreciationPostResult with reversal journal entry details.

        Raises:
            NotFoundError: If schedule not found.
            ValidationError: If not posted or cannot be reversed.
        """
        schedule = (
            self.db.query(AssetDepreciationSchedule)
            .filter(AssetDepreciationSchedule.id == schedule_id)
            .first()
        )
        if not schedule:
            raise NotFoundError(f"Depreciation schedule {schedule_id} not found")

        if not schedule.depreciation_booked:
            raise ValidationError("Depreciation not posted - nothing to reverse")

        asset = self.db.query(Asset).filter(Asset.id == schedule.asset_id).first()
        if not asset:
            raise NotFoundError(f"Asset for schedule {schedule_id} not found")

        # Get accounts
        expense_account, accum_account = self._get_depreciation_accounts(
            asset.asset_category, schedule.finance_book
        )

        if not expense_account or not accum_account:
            raise ValidationError(
                f"GL accounts not configured for category '{asset.asset_category}'"
            )

        # Create reversal journal entry (swap debits/credits)
        je = JournalEntry(
            voucher_type="Depreciation Entry",
            posting_date=datetime.combine(date.today(), datetime.min.time()),
            user_remark=f"Reversal: Depreciation for {asset.asset_name} - {schedule.schedule_date}",
            company=asset.company or "Default Company",
            total_debit=schedule.depreciation_amount,
            total_credit=schedule.depreciation_amount,
            docstatus=1,
        )
        self.db.add(je)
        self.db.flush()

        je.erpnext_id = f"DEP-REV-{je.id:06d}"

        # Credit expense (reversal)
        expense_account_obj = (
            self.db.query(Account).filter(Account.account_name == expense_account).first()
        )
        expense_item = JournalEntryItem(
            journal_entry_id=je.id,
            account=expense_account,
            account_id=expense_account_obj.id if expense_account_obj else None,
            debit=Decimal("0"),
            credit=schedule.depreciation_amount,
            debit_in_account_currency=Decimal("0"),
            credit_in_account_currency=schedule.depreciation_amount,
            exchange_rate=Decimal("1"),
        )
        self.db.add(expense_item)

        # Debit accumulated (reversal)
        accum_account_obj = (
            self.db.query(Account).filter(Account.account_name == accum_account).first()
        )
        accum_item = JournalEntryItem(
            journal_entry_id=je.id,
            account=accum_account,
            account_id=accum_account_obj.id if accum_account_obj else None,
            debit=schedule.depreciation_amount,
            credit=Decimal("0"),
            debit_in_account_currency=schedule.depreciation_amount,
            credit_in_account_currency=Decimal("0"),
            exchange_rate=Decimal("1"),
        )
        self.db.add(accum_item)

        # Unmark schedule
        schedule.depreciation_booked = False
        schedule.journal_entry = None

        # Restore asset value
        asset.asset_value += schedule.depreciation_amount

        # Restore asset status
        if asset.status == AssetStatus.FULLY_DEPRECIATED:
            asset.status = AssetStatus.PARTIALLY_DEPRECIATED

        # Update next depreciation date
        asset.next_depreciation_date = schedule.schedule_date

        self.db.flush()

        return DepreciationPostResult(
            journal_entry_id=je.id,
            journal_entry_number=je.erpnext_id or str(je.id),
            schedules_posted=1,
            total_depreciation=schedule.depreciation_amount,
        )
