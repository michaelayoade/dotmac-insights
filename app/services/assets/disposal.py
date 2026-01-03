"""Asset disposal service - business logic for asset disposal operations.

This service encapsulates all asset disposal business logic:
- Asset sale (with optional invoice creation)
- Asset scrapping (write-off to expense)
- Asset write-off
- Gain/loss calculation
- GL posting for disposals

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Session, selectinload

from app.models.asset import Asset, AssetCategory, AssetCategoryFinanceBook, AssetStatus
from app.models.accounting import Account, JournalEntry, JournalEntryItem

from app.services.errors import NotFoundError, ValidationError

from .types import (
    DisposalType,
    DisposalData,
    DisposalResult,
    CapitalizationAccounts,
)

# Default GL account names - should be configured via settings in production
DEFAULT_CASH_ACCOUNT = "Cash"
DEFAULT_GAIN_LOSS_ACCOUNT = "Gain/Loss on Asset Disposal"

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["AssetDisposalService"]


class AssetDisposalService:
    """Service for asset disposal business logic.

    Handles all forms of asset disposal:
    - Sale: Asset sold to a buyer, creates receivable if requested
    - Scrap: Asset written off with no proceeds
    - Write-off: Asset removed from books (e.g., stolen, destroyed)

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
    # Disposal Operations
    # -------------------------------------------------------------------------

    def dispose_asset(self, asset_id: int, data: DisposalData) -> DisposalResult:
        """Dispose of an asset (sale, scrap, or write-off).

        This is the main entry point for all disposal operations.

        Args:
            asset_id: The asset ID to dispose.
            data: Disposal data including type, date, and optional sale amount.

        Returns:
            DisposalResult with disposal details and journal entry.

        Raises:
            NotFoundError: If asset not found.
            ValidationError: If asset cannot be disposed.
        """
        asset = (
            self.db.query(Asset)
            .options(selectinload(Asset.finance_books))
            .filter(Asset.id == asset_id)
            .first()
        )
        if not asset:
            raise NotFoundError(f"Asset {asset_id} not found")

        # Validate asset can be disposed
        valid_statuses = [
            AssetStatus.SUBMITTED,
            AssetStatus.PARTIALLY_DEPRECIATED,
            AssetStatus.FULLY_DEPRECIATED,
            AssetStatus.IN_MAINTENANCE,
        ]
        if asset.status not in valid_statuses:
            raise ValidationError(
                f"Cannot dispose asset with status {asset.status.value}. "
                f"Must be in: {', '.join(s.value for s in valid_statuses)}"
            )

        # Dispatch to appropriate handler
        if data.disposal_type == DisposalType.SALE:
            return self._dispose_by_sale(asset, data)
        elif data.disposal_type == DisposalType.SCRAP:
            return self._dispose_by_scrap(asset, data)
        elif data.disposal_type == DisposalType.WRITE_OFF:
            return self._dispose_by_write_off(asset, data)
        else:
            raise ValidationError(f"Unknown disposal type: {data.disposal_type}")

    def _dispose_by_sale(self, asset: Asset, data: DisposalData) -> DisposalResult:
        """Dispose asset by sale.

        Creates journal entry:
        - Debit: Cash/Bank or Receivable for sale amount
        - Debit: Accumulated Depreciation for total depreciation
        - Credit: Fixed Asset Account for original cost
        - Credit/Debit: Gain/Loss on Disposal for difference
        """
        if data.sale_amount < Decimal("0"):
            raise ValidationError("Sale amount cannot be negative")

        # Calculate gain/loss
        book_value = asset.asset_value
        gain_loss = self.calculate_gain_loss(asset, data.sale_amount)

        # Get GL accounts
        accounts = self._get_disposal_accounts(asset.asset_category)
        if not accounts:
            raise ValidationError(
                f"GL accounts not configured for category '{asset.asset_category}'"
            )

        # Create disposal journal entry
        journal_entry = self._create_sale_journal_entry(
            asset=asset,
            accounts=accounts,
            disposal_date=data.disposal_date,
            sale_amount=data.sale_amount,
            gain_loss=gain_loss,
            remarks=data.remarks,
        )

        # Update asset status
        asset.status = AssetStatus.SOLD
        asset.disposal_date = data.disposal_date
        asset.updated_at = datetime.utcnow()

        # Create invoice if requested
        invoice_id = None
        if data.create_invoice and data.buyer_party_id and data.sale_amount > 0:
            invoice_id = self._create_sale_invoice(
                asset=asset,
                data=data,
            )

        self.db.flush()

        return DisposalResult(
            asset_id=asset.id,
            disposal_type=DisposalType.SALE,
            disposal_date=data.disposal_date,
            book_value_at_disposal=book_value,
            sale_amount=data.sale_amount,
            gain_loss=gain_loss,
            journal_entry_id=journal_entry.id,
            journal_entry_number=journal_entry.erpnext_id or str(journal_entry.id),
            invoice_id=invoice_id,
        )

    def _dispose_by_scrap(self, asset: Asset, data: DisposalData) -> DisposalResult:
        """Dispose asset by scrapping.

        Creates journal entry:
        - Debit: Accumulated Depreciation for total depreciation
        - Debit: Loss on Disposal for remaining book value
        - Credit: Fixed Asset Account for original cost
        """
        book_value = asset.asset_value
        gain_loss = -book_value  # Always a loss when scrapping

        # Get GL accounts
        accounts = self._get_disposal_accounts(asset.asset_category)
        if not accounts:
            raise ValidationError(
                f"GL accounts not configured for category '{asset.asset_category}'"
            )

        # Create scrap journal entry
        journal_entry = self._create_scrap_journal_entry(
            asset=asset,
            accounts=accounts,
            disposal_date=data.disposal_date,
            remarks=data.remarks,
        )

        # Update asset status
        asset.status = AssetStatus.SCRAPPED
        asset.disposal_date = data.disposal_date
        asset.journal_entry_for_scrap = str(journal_entry.id)
        asset.updated_at = datetime.utcnow()

        self.db.flush()

        return DisposalResult(
            asset_id=asset.id,
            disposal_type=DisposalType.SCRAP,
            disposal_date=data.disposal_date,
            book_value_at_disposal=book_value,
            sale_amount=Decimal("0"),
            gain_loss=gain_loss,
            journal_entry_id=journal_entry.id,
            journal_entry_number=journal_entry.erpnext_id or str(journal_entry.id),
        )

    def _dispose_by_write_off(self, asset: Asset, data: DisposalData) -> DisposalResult:
        """Dispose asset by write-off.

        Similar to scrap but may use different accounts for different scenarios
        (e.g., theft, obsolescence, damage).
        """
        book_value = asset.asset_value
        gain_loss = -book_value

        # Get GL accounts
        accounts = self._get_disposal_accounts(asset.asset_category)
        if not accounts:
            raise ValidationError(
                f"GL accounts not configured for category '{asset.asset_category}'"
            )

        # Create write-off journal entry (same as scrap)
        journal_entry = self._create_scrap_journal_entry(
            asset=asset,
            accounts=accounts,
            disposal_date=data.disposal_date,
            remarks=data.remarks or "Asset write-off",
        )

        # Update asset status
        asset.status = AssetStatus.SCRAPPED
        asset.disposal_date = data.disposal_date
        asset.journal_entry_for_scrap = str(journal_entry.id)
        asset.updated_at = datetime.utcnow()

        self.db.flush()

        return DisposalResult(
            asset_id=asset.id,
            disposal_type=DisposalType.WRITE_OFF,
            disposal_date=data.disposal_date,
            book_value_at_disposal=book_value,
            sale_amount=Decimal("0"),
            gain_loss=gain_loss,
            journal_entry_id=journal_entry.id,
            journal_entry_number=journal_entry.erpnext_id or str(journal_entry.id),
        )

    # -------------------------------------------------------------------------
    # Calculations
    # -------------------------------------------------------------------------

    def calculate_gain_loss(self, asset: Asset, sale_amount: Decimal) -> Decimal:
        """Calculate gain or loss on asset disposal.

        Gain/Loss = Sale Amount - Book Value

        Args:
            asset: The asset being disposed.
            sale_amount: The sale proceeds.

        Returns:
            Positive value indicates gain, negative indicates loss.
        """
        book_value = asset.asset_value or Decimal("0")
        return sale_amount - book_value

    # -------------------------------------------------------------------------
    # GL Account Helpers
    # -------------------------------------------------------------------------

    def _get_disposal_accounts(
        self, category_name: Optional[str], finance_book: Optional[str] = None
    ) -> Optional[CapitalizationAccounts]:
        """Get GL accounts for asset disposal.

        Uses the same accounts as capitalization plus gain/loss account.
        """
        if not category_name:
            return None

        category = (
            self.db.query(AssetCategory)
            .options(selectinload(AssetCategory.finance_books))
            .filter(AssetCategory.asset_category_name == category_name)
            .first()
        )

        if not category or not category.finance_books:
            return None

        # Find matching finance book
        fb = None
        for cat_fb in category.finance_books:
            if cat_fb.finance_book == finance_book:
                fb = cat_fb
                break

        # Fall back to first
        if not fb:
            fb = category.finance_books[0]

        # All accounts must be configured
        if not fb.fixed_asset_account or not fb.accumulated_depreciation_account:
            return None

        # Use category's gain/loss account if configured, otherwise use default
        gain_loss_account = getattr(fb, 'gain_loss_on_disposal_account', None) or DEFAULT_GAIN_LOSS_ACCOUNT

        return CapitalizationAccounts(
            fixed_asset_account=fb.fixed_asset_account,
            accumulated_depreciation_account=fb.accumulated_depreciation_account,
            depreciation_expense_account=fb.depreciation_expense_account or "",
            capital_work_in_progress_account=fb.capital_work_in_progress_account,
            gain_loss_on_disposal_account=gain_loss_account,
        )

    # -------------------------------------------------------------------------
    # Journal Entry Creation
    # -------------------------------------------------------------------------

    def _create_sale_journal_entry(
        self,
        asset: Asset,
        accounts: CapitalizationAccounts,
        disposal_date: date,
        sale_amount: Decimal,
        gain_loss: Decimal,
        remarks: Optional[str] = None,
    ) -> JournalEntry:
        """Create a journal entry for asset sale.

        Entries:
        - Debit: Cash/Receivable = sale_amount
        - Debit: Accumulated Depreciation = total depreciation
        - Credit: Fixed Asset = gross_purchase_amount
        - Credit/Debit: Gain/Loss = difference
        """
        # Calculate amounts
        gross_cost = asset.gross_purchase_amount or Decimal("0")
        accumulated_depreciation = gross_cost - (asset.asset_value or Decimal("0"))

        remark = remarks or f"Sale of {asset.asset_name}"

        # Total debits and credits
        total_debit = sale_amount + accumulated_depreciation
        total_credit = gross_cost
        if gain_loss > 0:
            total_credit += gain_loss  # Gain is a credit
        else:
            total_debit += abs(gain_loss)  # Loss is a debit

        je = JournalEntry(
            voucher_type="Journal Entry",
            posting_date=datetime.combine(disposal_date, datetime.min.time()),
            user_remark=remark,
            company=asset.company or "Default Company",
            total_debit=max(total_debit, total_credit),
            total_credit=max(total_debit, total_credit),
            docstatus=1,
        )
        self.db.add(je)
        self.db.flush()

        je.erpnext_id = f"DISP-{je.id:06d}"

        # Debit: Cash/Bank or Receivable for sale amount
        if sale_amount > 0:
            # Use configured cash account or default
            cash_account_name = DEFAULT_CASH_ACCOUNT
            cash_account = (
                self.db.query(Account)
                .filter(Account.account_name == cash_account_name)
                .first()
            )
            cash_item = JournalEntryItem(
                journal_entry_id=je.id,
                account=cash_account_name,
                account_id=cash_account.id if cash_account else None,
                debit=sale_amount,
                credit=Decimal("0"),
                debit_in_account_currency=sale_amount,
                credit_in_account_currency=Decimal("0"),
                exchange_rate=Decimal("1"),
            )
            self.db.add(cash_item)

        # Debit: Accumulated Depreciation
        if accumulated_depreciation > 0:
            accum_account = (
                self.db.query(Account)
                .filter(Account.account_name == accounts.accumulated_depreciation_account)
                .first()
            )
            accum_item = JournalEntryItem(
                journal_entry_id=je.id,
                account=accounts.accumulated_depreciation_account,
                account_id=accum_account.id if accum_account else None,
                debit=accumulated_depreciation,
                credit=Decimal("0"),
                debit_in_account_currency=accumulated_depreciation,
                credit_in_account_currency=Decimal("0"),
                exchange_rate=Decimal("1"),
            )
            self.db.add(accum_item)

        # Credit: Fixed Asset Account
        fixed_account = (
            self.db.query(Account)
            .filter(Account.account_name == accounts.fixed_asset_account)
            .first()
        )
        fixed_item = JournalEntryItem(
            journal_entry_id=je.id,
            account=accounts.fixed_asset_account,
            account_id=fixed_account.id if fixed_account else None,
            debit=Decimal("0"),
            credit=gross_cost,
            debit_in_account_currency=Decimal("0"),
            credit_in_account_currency=gross_cost,
            exchange_rate=Decimal("1"),
        )
        self.db.add(fixed_item)

        # Credit/Debit: Gain/Loss on Disposal
        if gain_loss != 0:
            gain_loss_account_name = accounts.gain_loss_on_disposal_account or "Gain/Loss on Asset Disposal"
            gain_loss_item = JournalEntryItem(
                journal_entry_id=je.id,
                account=gain_loss_account_name,
                debit=abs(gain_loss) if gain_loss < 0 else Decimal("0"),
                credit=gain_loss if gain_loss > 0 else Decimal("0"),
                debit_in_account_currency=abs(gain_loss) if gain_loss < 0 else Decimal("0"),
                credit_in_account_currency=gain_loss if gain_loss > 0 else Decimal("0"),
                exchange_rate=Decimal("1"),
            )
            self.db.add(gain_loss_item)

        self.db.flush()
        return je

    def _create_scrap_journal_entry(
        self,
        asset: Asset,
        accounts: CapitalizationAccounts,
        disposal_date: date,
        remarks: Optional[str] = None,
    ) -> JournalEntry:
        """Create a journal entry for asset scrap/write-off.

        Entries:
        - Debit: Accumulated Depreciation = total depreciation
        - Debit: Loss on Disposal = remaining book value
        - Credit: Fixed Asset = gross_purchase_amount
        """
        gross_cost = asset.gross_purchase_amount or Decimal("0")
        book_value = asset.asset_value or Decimal("0")
        accumulated_depreciation = gross_cost - book_value

        remark = remarks or f"Scrap of {asset.asset_name}"

        je = JournalEntry(
            voucher_type="Journal Entry",
            posting_date=datetime.combine(disposal_date, datetime.min.time()),
            user_remark=remark,
            company=asset.company or "Default Company",
            total_debit=gross_cost,
            total_credit=gross_cost,
            docstatus=1,
        )
        self.db.add(je)
        self.db.flush()

        je.erpnext_id = f"SCRAP-{je.id:06d}"

        # Debit: Accumulated Depreciation
        if accumulated_depreciation > 0:
            accum_account = (
                self.db.query(Account)
                .filter(Account.account_name == accounts.accumulated_depreciation_account)
                .first()
            )
            accum_item = JournalEntryItem(
                journal_entry_id=je.id,
                account=accounts.accumulated_depreciation_account,
                account_id=accum_account.id if accum_account else None,
                debit=accumulated_depreciation,
                credit=Decimal("0"),
                debit_in_account_currency=accumulated_depreciation,
                credit_in_account_currency=Decimal("0"),
                exchange_rate=Decimal("1"),
            )
            self.db.add(accum_item)

        # Debit: Loss on Disposal (remaining book value)
        if book_value > 0:
            gain_loss_account_name = accounts.gain_loss_on_disposal_account or "Gain/Loss on Asset Disposal"
            loss_item = JournalEntryItem(
                journal_entry_id=je.id,
                account=gain_loss_account_name,
                debit=book_value,
                credit=Decimal("0"),
                debit_in_account_currency=book_value,
                credit_in_account_currency=Decimal("0"),
                exchange_rate=Decimal("1"),
            )
            self.db.add(loss_item)

        # Credit: Fixed Asset Account
        fixed_account = (
            self.db.query(Account)
            .filter(Account.account_name == accounts.fixed_asset_account)
            .first()
        )
        fixed_item = JournalEntryItem(
            journal_entry_id=je.id,
            account=accounts.fixed_asset_account,
            account_id=fixed_account.id if fixed_account else None,
            debit=Decimal("0"),
            credit=gross_cost,
            debit_in_account_currency=Decimal("0"),
            credit_in_account_currency=gross_cost,
            exchange_rate=Decimal("1"),
        )
        self.db.add(fixed_item)

        self.db.flush()
        return je

    def _create_sale_invoice(
        self, asset: Asset, data: DisposalData
    ) -> Optional[int]:
        """Create an invoice for asset sale (if AR integration exists).

        This is a placeholder - actual implementation would depend on
        the invoicing system in use.

        Returns:
            Invoice ID if created, None otherwise.
        """
        # TODO: Implement AR invoice creation when asset is sold
        # This would create an Invoice record for the buyer
        return None
