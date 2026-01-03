"""Asset capitalization service - business logic for CWIP to fixed asset transfers.

This service encapsulates all capitalization-related business logic:
- Capitalize assets (move from CWIP to fixed asset)
- Transfer from work-in-progress
- GL posting for capitalization

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Session, selectinload

from app.models.asset import Asset, AssetCategory, AssetStatus
from app.models.accounting import Account, JournalEntry, JournalEntryItem

from app.services.errors import NotFoundError, ValidationError

from .types import (
    CapitalizationData,
    CapitalizationAccounts,
    CapitalizationResult,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["AssetCapitalizationService"]


class AssetCapitalizationService:
    """Service for asset capitalization business logic.

    Handles the transfer of assets from Capital Work in Progress (CWIP)
    to fixed asset accounts when an asset is ready for use.

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
    # Capitalization
    # -------------------------------------------------------------------------

    def capitalize_asset(
        self, asset_id: int, data: CapitalizationData
    ) -> CapitalizationResult:
        """Capitalize an asset (transfer from CWIP to fixed asset).

        This creates a journal entry that:
        - Debits the Fixed Asset account
        - Credits the CWIP account

        Args:
            asset_id: The asset ID to capitalize.
            data: Capitalization data including date and remarks.

        Returns:
            CapitalizationResult with journal entry details.

        Raises:
            NotFoundError: If asset not found.
            ValidationError: If asset cannot be capitalized.
        """
        asset = (
            self.db.query(Asset)
            .options(selectinload(Asset.finance_books))
            .filter(Asset.id == asset_id)
            .first()
        )
        if not asset:
            raise NotFoundError(f"Asset {asset_id} not found")

        # Validation
        if asset.status != AssetStatus.DRAFT:
            raise ValidationError(
                f"Asset must be in Draft status to capitalize. Current: {asset.status.value}"
            )

        if not asset.asset_category:
            raise ValidationError("Asset must have a category to capitalize")

        # Get accounts for the category
        accounts = self.get_capitalization_accounts(asset.asset_category)
        if not accounts:
            raise ValidationError(
                f"GL accounts not configured for category '{asset.asset_category}'"
            )

        if not accounts.capital_work_in_progress_account:
            raise ValidationError(
                f"CWIP account not configured for category '{asset.asset_category}'"
            )

        # Check if category has CWIP accounting enabled
        category = (
            self.db.query(AssetCategory)
            .filter(AssetCategory.asset_category_name == asset.asset_category)
            .first()
        )
        if not category or not category.enable_cwip_accounting:
            raise ValidationError(
                f"CWIP accounting not enabled for category '{asset.asset_category}'. "
                "Asset doesn't require capitalization."
            )

        # Create capitalization journal entry
        amount = asset.gross_purchase_amount
        journal_entry = self._create_capitalization_journal_entry(
            asset=asset,
            accounts=accounts,
            capitalization_date=data.capitalization_date,
            amount=amount,
            remarks=data.remarks,
        )

        # Update asset status
        asset.status = AssetStatus.SUBMITTED
        asset.docstatus = 1
        asset.available_for_use_date = data.capitalization_date
        asset.updated_at = datetime.utcnow()

        self.db.flush()

        return CapitalizationResult(
            asset_id=asset.id,
            capitalization_date=data.capitalization_date,
            amount_capitalized=amount,
            journal_entry_id=journal_entry.id,
            journal_entry_number=journal_entry.erpnext_id or str(journal_entry.id),
        )

    def get_capitalization_accounts(
        self, category_name: str, finance_book: Optional[str] = None
    ) -> Optional[CapitalizationAccounts]:
        """Get GL accounts for capitalizing assets in a category.

        Args:
            category_name: The asset category name.
            finance_book: Optional finance book name (None for default).

        Returns:
            CapitalizationAccounts if found, None otherwise.
        """
        from app.models.asset import AssetCategoryFinanceBook

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

        # All required accounts must be configured
        if not fb.fixed_asset_account or not fb.accumulated_depreciation_account or not fb.depreciation_expense_account:
            return None

        return CapitalizationAccounts(
            fixed_asset_account=fb.fixed_asset_account,
            accumulated_depreciation_account=fb.accumulated_depreciation_account,
            depreciation_expense_account=fb.depreciation_expense_account,
            capital_work_in_progress_account=fb.capital_work_in_progress_account,
        )

    def _create_capitalization_journal_entry(
        self,
        asset: Asset,
        accounts: CapitalizationAccounts,
        capitalization_date: date,
        amount: Decimal,
        remarks: Optional[str] = None,
    ) -> JournalEntry:
        """Create a journal entry for asset capitalization.

        Debit: Fixed Asset Account
        Credit: CWIP Account
        """
        remark = remarks or f"Capitalization of {asset.asset_name}"

        je = JournalEntry(
            voucher_type="Journal Entry",
            posting_date=datetime.combine(capitalization_date, datetime.min.time()),
            user_remark=remark,
            company=asset.company or "Default Company",
            total_debit=amount,
            total_credit=amount,
            docstatus=1,  # Posted
        )
        self.db.add(je)
        self.db.flush()

        je.erpnext_id = f"CAP-{je.id:06d}"

        # Debit Fixed Asset Account
        fixed_asset_account = (
            self.db.query(Account)
            .filter(Account.account_name == accounts.fixed_asset_account)
            .first()
        )
        debit_item = JournalEntryItem(
            journal_entry_id=je.id,
            account=accounts.fixed_asset_account,
            account_id=fixed_asset_account.id if fixed_asset_account else None,
            debit=amount,
            credit=Decimal("0"),
            debit_in_account_currency=amount,
            credit_in_account_currency=Decimal("0"),
            exchange_rate=Decimal("1"),
        )
        self.db.add(debit_item)

        # Credit CWIP Account
        cwip_account = (
            self.db.query(Account)
            .filter(Account.account_name == accounts.capital_work_in_progress_account)
            .first()
        )
        credit_item = JournalEntryItem(
            journal_entry_id=je.id,
            account=accounts.capital_work_in_progress_account,
            account_id=cwip_account.id if cwip_account else None,
            debit=Decimal("0"),
            credit=amount,
            debit_in_account_currency=Decimal("0"),
            credit_in_account_currency=amount,
            exchange_rate=Decimal("1"),
        )
        self.db.add(credit_item)

        self.db.flush()
        return je

    # -------------------------------------------------------------------------
    # CWIP Tracking
    # -------------------------------------------------------------------------

    def get_cwip_assets(self) -> list:
        """Get all assets currently in CWIP (draft with CWIP category).

        Returns:
            List of assets awaiting capitalization.
        """
        # Get categories with CWIP enabled
        cwip_categories = (
            self.db.query(AssetCategory.asset_category_name)
            .filter(AssetCategory.enable_cwip_accounting == True)
            .all()
        )
        category_names = [c[0] for c in cwip_categories]

        if not category_names:
            return []

        assets = (
            self.db.query(Asset)
            .filter(
                Asset.status == AssetStatus.DRAFT,
                Asset.asset_category.in_(category_names),
            )
            .order_by(Asset.purchase_date, Asset.asset_name)
            .all()
        )

        return assets

    def get_cwip_summary(self) -> dict:
        """Get summary of CWIP assets.

        Returns:
            Dictionary with count, total value, and breakdown by category.
        """
        from sqlalchemy import func

        # Get categories with CWIP enabled
        cwip_categories = (
            self.db.query(AssetCategory.asset_category_name)
            .filter(AssetCategory.enable_cwip_accounting == True)
            .all()
        )
        category_names = [c[0] for c in cwip_categories]

        if not category_names:
            return {
                "total_count": 0,
                "total_value": Decimal("0"),
                "by_category": [],
            }

        # Aggregate by category
        results = (
            self.db.query(
                Asset.asset_category,
                func.count(Asset.id).label("count"),
                func.sum(Asset.gross_purchase_amount).label("value"),
            )
            .filter(
                Asset.status == AssetStatus.DRAFT,
                Asset.asset_category.in_(category_names),
            )
            .group_by(Asset.asset_category)
            .all()
        )

        by_category = [
            {
                "category": row.asset_category,
                "count": row.count,
                "value": float(row.value or 0),
            }
            for row in results
        ]

        total_count = sum(item["count"] for item in by_category)
        total_value = sum(Decimal(str(item["value"])) for item in by_category)

        return {
            "total_count": total_count,
            "total_value": total_value,
            "by_category": by_category,
        }
