"""Asset category service - business logic for asset categories.

This service encapsulates all asset category business logic:
- CRUD operations for categories
- Finance book defaults management
- GL account configuration

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.models.asset import AssetCategory, AssetCategoryFinanceBook

from app.services.base import paginate
from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.types import PaginatedResult, PaginationParams
from app.services.validation.soft_validation_service import SoftValidationService

from .types import (
    CategoryFilters,
    CategoryCreateData,
    CategoryUpdateData,
    CategoryFinanceBookData,
    CapitalizationAccounts,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["AssetCategoryService"]

ALLOWED_SORTS = {
    "asset_category_name",
    "id",
    "created_at",
}


class AssetCategoryService:
    """Service for asset category business logic.

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
    # Queries
    # -------------------------------------------------------------------------

    def list_categories(
        self,
        filters: Optional[CategoryFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[AssetCategory]:
        """List asset categories with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters (offset, limit).

        Returns:
            PaginatedResult containing categories and total count.
        """
        if filters is None:
            filters = CategoryFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(AssetCategory).options(
            selectinload(AssetCategory.finance_books)
        )

        # CWIP filter
        if filters.enable_cwip_accounting is not None:
            query = query.filter(
                AssetCategory.enable_cwip_accounting == filters.enable_cwip_accounting
            )

        # Search
        if filters.search:
            if len(filters.search) < 2:
                raise ValidationError("Search query must be at least 2 characters")
            query = query.filter(
                AssetCategory.asset_category_name.ilike(f"%{filters.search}%")
            )

        # Sorting
        sort_key = filters.sort_by if filters.sort_by in ALLOWED_SORTS else "asset_category_name"
        sort_column = getattr(AssetCategory, sort_key, AssetCategory.asset_category_name)
        if filters.sort_dir == "asc":
            query = query.order_by(sort_column.asc(), AssetCategory.id.asc())
        else:
            query = query.order_by(sort_column.desc(), AssetCategory.id.desc())

        return paginate(query, pagination)

    def get_category(self, category_id: int) -> AssetCategory:
        """Get a category by ID.

        Args:
            category_id: The category ID.

        Returns:
            The AssetCategory object with finance books loaded.

        Raises:
            NotFoundError: If category not found.
        """
        category = (
            self.db.query(AssetCategory)
            .options(selectinload(AssetCategory.finance_books))
            .filter(AssetCategory.id == category_id)
            .first()
        )
        if not category:
            raise NotFoundError(f"Asset category {category_id} not found")
        return category

    def get_category_by_name(self, category_name: str) -> Optional[AssetCategory]:
        """Get a category by name.

        Args:
            category_name: The category name.

        Returns:
            The AssetCategory object if found, None otherwise.
        """
        return (
            self.db.query(AssetCategory)
            .options(selectinload(AssetCategory.finance_books))
            .filter(AssetCategory.asset_category_name == category_name)
            .first()
        )

    def get_all_categories(self) -> List[AssetCategory]:
        """Get all categories (for dropdowns).

        Returns:
            List of all categories ordered by name.
        """
        return (
            self.db.query(AssetCategory)
            .order_by(AssetCategory.asset_category_name)
            .all()
        )

    def get_assets_in_category(
        self, category_name: str, limit: int = 50, offset: int = 0
    ) -> tuple:
        """Get assets belonging to a category with count.

        Args:
            category_name: The category name to filter by.
            limit: Maximum number of assets to return.
            offset: Number of assets to skip.

        Returns:
            Tuple of (assets list, total count).
        """
        from app.models.asset import Asset

        query = (
            self.db.query(Asset)
            .filter(Asset.asset_category == category_name)
            .order_by(Asset.asset_name)
        )

        total = query.count()
        assets = query.offset(offset).limit(limit).all()

        return assets, total

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def create_category(self, data: CategoryCreateData) -> AssetCategory:
        """Create a new asset category.

        Args:
            data: Category creation data.

        Returns:
            The newly created AssetCategory.

        Raises:
            ConflictError: If category name already exists.
        """
        # Check for duplicate name
        existing = self.get_category_by_name(data.asset_category_name)
        if existing:
            raise ConflictError(
                f"Asset category '{data.asset_category_name}' already exists"
            )

        # Create category
        category = AssetCategory(
            asset_category_name=data.asset_category_name,
            enable_cwip_accounting=data.enable_cwip_accounting,
        )
        self.db.add(category)
        self.db.flush()

        # Create finance books
        self._create_finance_books(category, data.finance_books)
        validator = SoftValidationService(self.db)
        for fb in category.finance_books:
            validator.validate_and_store(fb)
        validator.validate_and_store(category)

        return category

    def _create_finance_books(
        self,
        category: AssetCategory,
        finance_books: List[CategoryFinanceBookData],
    ) -> None:
        """Create finance book records for a category."""
        if not finance_books:
            # Create a default finance book with standard settings
            fb = AssetCategoryFinanceBook(
                asset_category_id=category.id,
                finance_book=None,  # Default/single book
                depreciation_method="straight_line",
                total_number_of_depreciations=60,
                frequency_of_depreciation=12,
                idx=0,
            )
            self.db.add(fb)
        else:
            for idx, fb_data in enumerate(finance_books):
                fb = AssetCategoryFinanceBook(
                    asset_category_id=category.id,
                    finance_book=fb_data.finance_book,
                    depreciation_method=fb_data.depreciation_method,
                    total_number_of_depreciations=fb_data.total_number_of_depreciations,
                    frequency_of_depreciation=fb_data.frequency_of_depreciation,
                    fixed_asset_account=fb_data.fixed_asset_account,
                    accumulated_depreciation_account=fb_data.accumulated_depreciation_account,
                    depreciation_expense_account=fb_data.depreciation_expense_account,
                    capital_work_in_progress_account=fb_data.capital_work_in_progress_account,
                    idx=idx,
                )
                self.db.add(fb)

        self.db.flush()

    def update_category(self, category_id: int, data: CategoryUpdateData) -> AssetCategory:
        """Update an existing category.

        Args:
            category_id: The category ID.
            data: Update data (only non-None fields are applied).

        Returns:
            The updated AssetCategory.

        Raises:
            NotFoundError: If category not found.
            ConflictError: If new name conflicts with existing category.
        """
        category = self.get_category(category_id)

        if data.asset_category_name is not None:
            # Check for duplicate
            existing = self.get_category_by_name(data.asset_category_name)
            if existing and existing.id != category_id:
                raise ConflictError(
                    f"Asset category '{data.asset_category_name}' already exists"
                )
            category.asset_category_name = data.asset_category_name

        if data.enable_cwip_accounting is not None:
            category.enable_cwip_accounting = data.enable_cwip_accounting

        category.updated_at = datetime.utcnow()
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(category)
        return category

    def delete_category(self, category_id: int) -> None:
        """Delete a category.

        Cannot delete if assets are using this category.

        Args:
            category_id: The category ID.

        Raises:
            NotFoundError: If category not found.
            ValidationError: If category is in use.
        """
        from app.models.asset import Asset

        category = self.get_category(category_id)

        # Check if any assets use this category
        asset_count = (
            self.db.query(Asset)
            .filter(Asset.asset_category == category.asset_category_name)
            .count()
        )
        if asset_count > 0:
            raise ValidationError(
                f"Cannot delete category '{category.asset_category_name}' - "
                f"it is used by {asset_count} asset(s)"
            )

        # Delete (cascades handle finance_books)
        self.db.delete(category)
        self.db.flush()

    # -------------------------------------------------------------------------
    # Finance Book Management
    # -------------------------------------------------------------------------

    def add_finance_book(
        self, category_id: int, data: CategoryFinanceBookData
    ) -> AssetCategoryFinanceBook:
        """Add a finance book configuration to a category.

        Args:
            category_id: The category ID.
            data: Finance book data.

        Returns:
            The newly created AssetCategoryFinanceBook.

        Raises:
            NotFoundError: If category not found.
            ConflictError: If finance book already exists for this category.
        """
        category = self.get_category(category_id)

        # Check for duplicate finance book
        for fb in category.finance_books:
            if fb.finance_book == data.finance_book:
                raise ConflictError(
                    f"Finance book '{data.finance_book or 'Default'}' "
                    f"already exists for this category"
                )

        # Determine next idx
        max_idx = max((fb.idx for fb in category.finance_books), default=-1)

        fb = AssetCategoryFinanceBook(
            asset_category_id=category_id,
            finance_book=data.finance_book,
            depreciation_method=data.depreciation_method,
            total_number_of_depreciations=data.total_number_of_depreciations,
            frequency_of_depreciation=data.frequency_of_depreciation,
            fixed_asset_account=data.fixed_asset_account,
            accumulated_depreciation_account=data.accumulated_depreciation_account,
            depreciation_expense_account=data.depreciation_expense_account,
            capital_work_in_progress_account=data.capital_work_in_progress_account,
            idx=max_idx + 1,
        )
        self.db.add(fb)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(fb)
        return fb

    def update_finance_book(
        self, finance_book_id: int, data: CategoryFinanceBookData
    ) -> AssetCategoryFinanceBook:
        """Update a finance book configuration.

        Args:
            finance_book_id: The finance book record ID.
            data: Updated finance book data.

        Returns:
            The updated AssetCategoryFinanceBook.

        Raises:
            NotFoundError: If finance book not found.
        """
        fb = (
            self.db.query(AssetCategoryFinanceBook)
            .filter(AssetCategoryFinanceBook.id == finance_book_id)
            .first()
        )
        if not fb:
            raise NotFoundError(f"Finance book {finance_book_id} not found")

        fb.depreciation_method = data.depreciation_method
        fb.total_number_of_depreciations = data.total_number_of_depreciations
        fb.frequency_of_depreciation = data.frequency_of_depreciation
        fb.fixed_asset_account = data.fixed_asset_account
        fb.accumulated_depreciation_account = data.accumulated_depreciation_account
        fb.depreciation_expense_account = data.depreciation_expense_account
        fb.capital_work_in_progress_account = data.capital_work_in_progress_account

        self.db.flush()
        SoftValidationService(self.db).validate_and_store(fb)
        return fb

    def delete_finance_book(self, finance_book_id: int) -> None:
        """Delete a finance book configuration.

        Cannot delete the last finance book in a category.

        Args:
            finance_book_id: The finance book record ID.

        Raises:
            NotFoundError: If finance book not found.
            ValidationError: If it's the only finance book in the category.
        """
        fb = (
            self.db.query(AssetCategoryFinanceBook)
            .filter(AssetCategoryFinanceBook.id == finance_book_id)
            .first()
        )
        if not fb:
            raise NotFoundError(f"Finance book {finance_book_id} not found")

        # Check if it's the last one
        count = (
            self.db.query(AssetCategoryFinanceBook)
            .filter(AssetCategoryFinanceBook.asset_category_id == fb.asset_category_id)
            .count()
        )
        if count <= 1:
            raise ValidationError(
                "Cannot delete the last finance book from a category"
            )

        self.db.delete(fb)
        self.db.flush()

    # -------------------------------------------------------------------------
    # GL Account Helpers
    # -------------------------------------------------------------------------

    def get_category_gl_accounts(
        self, category_name: str, finance_book: Optional[str] = None
    ) -> Optional[CapitalizationAccounts]:
        """Get GL accounts for a category's finance book.

        Args:
            category_name: The category name.
            finance_book: The finance book name (None for default).

        Returns:
            CapitalizationAccounts if found, None otherwise.
        """
        category = self.get_category_by_name(category_name)
        if not category or not category.finance_books:
            return None

        # Find matching finance book
        fb = None
        for cat_fb in category.finance_books:
            if cat_fb.finance_book == finance_book:
                fb = cat_fb
                break

        # Fall back to first finance book
        if not fb:
            fb = category.finance_books[0]

        # All accounts must be configured
        if not fb.fixed_asset_account or not fb.accumulated_depreciation_account or not fb.depreciation_expense_account:
            return None

        return CapitalizationAccounts(
            fixed_asset_account=fb.fixed_asset_account,
            accumulated_depreciation_account=fb.accumulated_depreciation_account,
            depreciation_expense_account=fb.depreciation_expense_account,
            capital_work_in_progress_account=fb.capital_work_in_progress_account,
        )
