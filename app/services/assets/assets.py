"""Asset service - business logic for fixed asset management.

This service encapsulates all asset-related business logic:
- CRUD operations for assets
- Status transitions (submit, scrap, dispose)
- Finance book management
- Depreciation schedule generation (delegated to DepreciationService)

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.models.asset import (
    Asset,
    AssetCategory,
    AssetDepreciationSchedule,
    AssetFinanceBook,
    AssetStatus,
)

from app.services.base import paginate, safe_filter, scoped_query
from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.types import PaginatedResult, PaginationParams

from .types import (
    AssetFilters,
    AssetCreateData,
    AssetUpdateData,
    AssetFinanceBookData,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["AssetService"]

# Allowed filter fields for safe_filter
ALLOWED_FILTERS = {"status", "asset_category", "location", "custodian_id", "department"}
ALLOWED_SORTS = {
    "asset_name",
    "asset_category",
    "purchase_date",
    "gross_purchase_amount",
    "asset_value",
    "status",
    "location",
    "id",
    "created_at",
}


class AssetService:
    """Service for asset business logic.

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

    def list_assets(
        self,
        filters: Optional[AssetFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Asset]:
        """List assets with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters (offset, limit).

        Returns:
            PaginatedResult containing assets and total count.
        """
        if filters is None:
            filters = AssetFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(Asset)
        query = scoped_query(query, self.principal)

        # Exclude disposed assets unless requested
        if not filters.include_disposed:
            query = query.filter(
                Asset.status.notin_([AssetStatus.SOLD, AssetStatus.SCRAPPED])
            )

        # Apply simple equality filters
        filter_dict = {
            "status": filters.status,
            "asset_category": filters.category,
            "location": filters.location,
            "custodian_id": filters.custodian_id,
            "department": filters.department,
        }
        query = safe_filter(query, Asset, filter_dict, ALLOWED_FILTERS)

        # Date range filters
        if filters.purchase_date_from:
            query = query.filter(Asset.purchase_date >= filters.purchase_date_from)
        if filters.purchase_date_to:
            query = query.filter(Asset.purchase_date <= filters.purchase_date_to)

        # Search
        if filters.search:
            if len(filters.search) < 2:
                raise ValidationError("Search query must be at least 2 characters")
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    Asset.asset_name.ilike(search_term),
                    Asset.serial_no.ilike(search_term),
                    Asset.item_code.ilike(search_term),
                    Asset.description.ilike(search_term),
                )
            )

        # Sorting
        sort_key = filters.sort_by if filters.sort_by in ALLOWED_SORTS else "asset_name"
        sort_column = getattr(Asset, sort_key, Asset.asset_name)
        if filters.sort_dir == "asc":
            query = query.order_by(sort_column.asc(), Asset.id.asc())
        else:
            query = query.order_by(sort_column.desc(), Asset.id.desc())

        return paginate(query, pagination)

    def get_asset(self, asset_id: int, *, include_schedules: bool = False) -> Asset:
        """Get an asset by ID.

        Args:
            asset_id: The asset ID.
            include_schedules: Whether to eagerly load depreciation schedules.

        Returns:
            The Asset object with finance books loaded.

        Raises:
            NotFoundError: If asset not found.
        """
        query = self.db.query(Asset).options(selectinload(Asset.finance_books))

        if include_schedules:
            query = query.options(selectinload(Asset.depreciation_schedules))

        asset = query.filter(Asset.id == asset_id).first()

        if not asset:
            raise NotFoundError(f"Asset {asset_id} not found")
        return asset

    def get_asset_by_name(self, asset_name: str) -> Optional[Asset]:
        """Get an asset by name (for uniqueness checks).

        Args:
            asset_name: The asset name.

        Returns:
            The Asset object if found, None otherwise.
        """
        return self.db.query(Asset).filter(Asset.asset_name == asset_name).first()

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    def create_asset(self, data: AssetCreateData) -> Asset:
        """Create a new asset.

        Args:
            data: Asset creation data.

        Returns:
            The newly created Asset.

        Raises:
            ValidationError: If validation fails.
            ConflictError: If asset name already exists.
        """
        # Validate category exists
        category = self.db.query(AssetCategory).filter(
            AssetCategory.asset_category_name == data.asset_category
        ).first()
        if not category:
            raise ValidationError(f"Asset category '{data.asset_category}' not found")

        # Check for duplicate name
        existing = self.get_asset_by_name(data.asset_name)
        if existing:
            raise ConflictError(f"Asset with name '{data.asset_name}' already exists")

        # Validate amounts
        if data.gross_purchase_amount < Decimal("0"):
            raise ValidationError("Gross purchase amount cannot be negative")

        # Create asset
        asset = Asset(
            asset_name=data.asset_name,
            asset_category=data.asset_category,
            gross_purchase_amount=data.gross_purchase_amount,
            asset_value=data.gross_purchase_amount - data.opening_accumulated_depreciation,
            purchase_date=data.purchase_date,
            available_for_use_date=data.available_for_use_date or data.purchase_date,
            item_code=data.item_code,
            item_name=data.item_name,
            location=data.location,
            custodian_id=data.custodian_id,
            department=data.department,
            cost_center=data.cost_center,
            company=data.company,
            description=data.description,
            serial_no=data.serial_no,
            asset_quantity=data.asset_quantity,
            calculate_depreciation=data.calculate_depreciation,
            is_existing_asset=data.is_existing_asset,
            opening_accumulated_depreciation=data.opening_accumulated_depreciation,
            # Insurance
            insured_value=data.insured_value,
            insurance_start_date=data.insurance_start_date,
            insurance_end_date=data.insurance_end_date,
            comprehensive_insurance=data.comprehensive_insurance,
            # Warranty
            warranty_expiry_date=data.warranty_expiry_date,
            # Maintenance
            maintenance_required=data.maintenance_required,
            # Status
            status=AssetStatus.DRAFT,
            docstatus=0,
        )
        self.db.add(asset)
        self.db.flush()

        # Create finance books
        self._create_finance_books(asset, data.finance_books, category)

        return asset

    def _create_finance_books(
        self,
        asset: Asset,
        finance_books: List[AssetFinanceBookData],
        category: AssetCategory,
    ) -> None:
        """Create finance book records for an asset.

        If no finance books provided, creates default from category settings.
        """
        if not finance_books:
            # Use category defaults if available
            if category.finance_books:
                for idx, cat_fb in enumerate(category.finance_books):
                    fb = AssetFinanceBook(
                        asset_id=asset.id,
                        finance_book=cat_fb.finance_book,
                        depreciation_method=cat_fb.depreciation_method,
                        total_number_of_depreciations=cat_fb.total_number_of_depreciations,
                        frequency_of_depreciation=cat_fb.frequency_of_depreciation,
                        depreciation_start_date=asset.available_for_use_date,
                        expected_value_after_useful_life=Decimal("0"),
                        value_after_depreciation=asset.asset_value,
                        idx=idx,
                    )
                    self.db.add(fb)
            else:
                # Create a single default finance book
                fb = AssetFinanceBook(
                    asset_id=asset.id,
                    finance_book=None,  # Default/single book
                    depreciation_method="straight_line",
                    total_number_of_depreciations=60,  # 5 years monthly
                    frequency_of_depreciation=12,
                    depreciation_start_date=asset.available_for_use_date,
                    expected_value_after_useful_life=Decimal("0"),
                    value_after_depreciation=asset.asset_value,
                    idx=0,
                )
                self.db.add(fb)
        else:
            # Use provided finance books
            for idx, fb_data in enumerate(finance_books):
                fb = AssetFinanceBook(
                    asset_id=asset.id,
                    finance_book=fb_data.finance_book,
                    depreciation_method=fb_data.depreciation_method,
                    total_number_of_depreciations=fb_data.total_number_of_depreciations,
                    frequency_of_depreciation=fb_data.frequency_of_depreciation,
                    depreciation_start_date=fb_data.depreciation_start_date or asset.available_for_use_date,
                    expected_value_after_useful_life=fb_data.expected_value_after_useful_life,
                    rate_of_depreciation=fb_data.rate_of_depreciation,
                    value_after_depreciation=asset.asset_value,
                    idx=idx,
                )
                self.db.add(fb)

        self.db.flush()

    def update_asset(self, asset_id: int, data: AssetUpdateData) -> Asset:
        """Update an existing asset.

        Only draft assets can have core fields updated.
        Some fields (location, custodian, etc.) can be updated at any time.

        Args:
            asset_id: The asset ID.
            data: Update data (only non-None fields are applied).

        Returns:
            The updated Asset.

        Raises:
            NotFoundError: If asset not found.
            ValidationError: If update not allowed due to status.
        """
        asset = self.get_asset(asset_id)

        # Fields that can only be updated in draft status
        if asset.status != AssetStatus.DRAFT:
            if data.asset_name is not None or data.asset_category is not None:
                raise ValidationError(
                    f"Cannot modify asset name or category when status is {asset.status.value}"
                )

        # Apply updates
        if data.asset_name is not None:
            # Check for duplicate
            existing = self.get_asset_by_name(data.asset_name)
            if existing and existing.id != asset_id:
                raise ConflictError(f"Asset with name '{data.asset_name}' already exists")
            asset.asset_name = data.asset_name

        if data.asset_category is not None:
            category = self.db.query(AssetCategory).filter(
                AssetCategory.asset_category_name == data.asset_category
            ).first()
            if not category:
                raise ValidationError(f"Asset category '{data.asset_category}' not found")
            asset.asset_category = data.asset_category

        # These can be updated at any time
        if data.location is not None:
            asset.location = data.location
        if data.custodian_id is not None:
            asset.custodian_id = data.custodian_id
        if data.department is not None:
            asset.department = data.department
        if data.cost_center is not None:
            asset.cost_center = data.cost_center
        if data.description is not None:
            asset.description = data.description
        if data.serial_no is not None:
            asset.serial_no = data.serial_no

        # Insurance updates
        if data.insured_value is not None:
            asset.insured_value = data.insured_value
        if data.insurance_start_date is not None:
            asset.insurance_start_date = data.insurance_start_date
        if data.insurance_end_date is not None:
            asset.insurance_end_date = data.insurance_end_date
        if data.comprehensive_insurance is not None:
            asset.comprehensive_insurance = data.comprehensive_insurance

        # Warranty
        if data.warranty_expiry_date is not None:
            asset.warranty_expiry_date = data.warranty_expiry_date

        # Maintenance
        if data.maintenance_required is not None:
            asset.maintenance_required = data.maintenance_required

        asset.updated_at = datetime.utcnow()
        self.db.flush()
        return asset

    def delete_asset(self, asset_id: int) -> None:
        """Delete an asset (only draft assets).

        Args:
            asset_id: The asset ID.

        Raises:
            NotFoundError: If asset not found.
            ValidationError: If asset cannot be deleted.
        """
        asset = self.get_asset(asset_id)

        if asset.status != AssetStatus.DRAFT:
            raise ValidationError(
                f"Cannot delete asset with status {asset.status.value}. "
                "Only draft assets can be deleted."
            )

        # Delete related records (cascades handle finance_books and schedules)
        self.db.delete(asset)
        self.db.flush()

    # -------------------------------------------------------------------------
    # Workflow Transitions
    # -------------------------------------------------------------------------

    def submit_asset(self, asset_id: int) -> Asset:
        """Submit an asset (moves from DRAFT to SUBMITTED).

        This validates the asset and generates depreciation schedule.

        Args:
            asset_id: The asset ID.

        Returns:
            The submitted Asset.

        Raises:
            NotFoundError: If asset not found.
            ValidationError: If asset cannot be submitted.
        """
        asset = self.get_asset(asset_id, include_schedules=True)

        if asset.status != AssetStatus.DRAFT:
            raise ValidationError(
                f"Cannot submit asset with status {asset.status.value}. "
                "Only draft assets can be submitted."
            )

        # Validate required fields
        if not asset.purchase_date:
            raise ValidationError("Purchase date is required to submit asset")
        if not asset.available_for_use_date:
            raise ValidationError("Available for use date is required to submit asset")
        if asset.gross_purchase_amount <= 0:
            raise ValidationError("Gross purchase amount must be greater than zero")

        # Validate finance book exists
        if not asset.finance_books:
            raise ValidationError("At least one finance book is required")

        # Generate depreciation schedule if needed
        if asset.calculate_depreciation and not asset.depreciation_schedules:
            self._generate_depreciation_schedule(asset)

        # Update status
        asset.status = AssetStatus.SUBMITTED
        asset.docstatus = 1
        asset.updated_at = datetime.utcnow()

        self.db.flush()
        return asset

    def _generate_depreciation_schedule(self, asset: Asset) -> None:
        """Generate depreciation schedule for an asset.

        This creates schedule rows based on the finance book settings.
        The actual calculation logic is in DepreciationService.
        """
        from .depreciation import DepreciationService

        depreciation_service = DepreciationService(self.db, self.principal)

        for finance_book in asset.finance_books:
            schedules = depreciation_service.calculate_depreciation_schedule(
                asset, finance_book
            )

            for idx, schedule_row in enumerate(schedules):
                schedule = AssetDepreciationSchedule(
                    asset_id=asset.id,
                    finance_book=finance_book.finance_book,
                    schedule_date=schedule_row.schedule_date,
                    depreciation_amount=schedule_row.depreciation_amount,
                    accumulated_depreciation_amount=schedule_row.accumulated_depreciation,
                    idx=idx,
                    depreciation_booked=False,
                )
                self.db.add(schedule)

        self.db.flush()

    def mark_in_maintenance(self, asset_id: int) -> Asset:
        """Mark an asset as being in maintenance.

        Args:
            asset_id: The asset ID.

        Returns:
            The updated Asset.

        Raises:
            NotFoundError: If asset not found.
            ValidationError: If status transition not allowed.
        """
        asset = self.get_asset(asset_id)

        valid_statuses = [
            AssetStatus.SUBMITTED,
            AssetStatus.PARTIALLY_DEPRECIATED,
            AssetStatus.FULLY_DEPRECIATED,
        ]
        if asset.status not in valid_statuses:
            raise ValidationError(
                f"Cannot mark asset as in maintenance with status {asset.status.value}"
            )

        asset.status = AssetStatus.IN_MAINTENANCE
        asset.updated_at = datetime.utcnow()
        self.db.flush()
        return asset

    def complete_maintenance(self, asset_id: int) -> Asset:
        """Mark asset as back from maintenance.

        Returns asset to previous appropriate status based on depreciation.

        Args:
            asset_id: The asset ID.

        Returns:
            The updated Asset.

        Raises:
            NotFoundError: If asset not found.
            ValidationError: If asset not in maintenance.
        """
        asset = self.get_asset(asset_id, include_schedules=True)

        if asset.status != AssetStatus.IN_MAINTENANCE:
            raise ValidationError("Asset is not in maintenance")

        # Determine correct status based on depreciation
        if not asset.calculate_depreciation:
            asset.status = AssetStatus.SUBMITTED
        elif asset.asset_value <= Decimal("0"):
            asset.status = AssetStatus.FULLY_DEPRECIATED
        elif asset.depreciation_schedules:
            booked = sum(1 for s in asset.depreciation_schedules if s.depreciation_booked)
            if booked > 0:
                asset.status = AssetStatus.PARTIALLY_DEPRECIATED
            else:
                asset.status = AssetStatus.SUBMITTED
        else:
            asset.status = AssetStatus.SUBMITTED

        asset.updated_at = datetime.utcnow()
        self.db.flush()
        return asset

    # -------------------------------------------------------------------------
    # Summary & Statistics
    # -------------------------------------------------------------------------

    def get_asset_summary(self) -> dict:
        """Get summary statistics for assets.

        Returns:
            Dictionary with counts and values by status.
        """
        from sqlalchemy import func

        # Count by status
        status_counts = (
            self.db.query(Asset.status, func.count(Asset.id))
            .group_by(Asset.status)
            .all()
        )

        # Total value by status
        status_values = (
            self.db.query(Asset.status, func.sum(Asset.asset_value))
            .group_by(Asset.status)
            .all()
        )

        counts = {status.value: count for status, count in status_counts}
        values = {status.value: float(value or 0) for status, value in status_values}

        total_count = sum(counts.values())
        total_value = sum(values.values())

        return {
            "total_count": total_count,
            "total_value": total_value,
            "by_status": {
                "counts": counts,
                "values": values,
            },
        }

    def get_assets_by_category(self) -> List[dict]:
        """Get asset counts and values grouped by category.

        Returns:
            List of category summaries.
        """
        from sqlalchemy import func

        results = (
            self.db.query(
                Asset.asset_category,
                func.count(Asset.id).label("count"),
                func.sum(Asset.gross_purchase_amount).label("purchase_value"),
                func.sum(Asset.asset_value).label("book_value"),
            )
            .filter(Asset.status.notin_([AssetStatus.SOLD, AssetStatus.SCRAPPED]))
            .group_by(Asset.asset_category)
            .order_by(func.sum(Asset.asset_value).desc())
            .all()
        )

        return [
            {
                "category": row.asset_category or "Uncategorized",
                "count": row.count,
                "purchase_value": float(row.purchase_value or 0),
                "book_value": float(row.book_value or 0),
            }
            for row in results
        ]

    def get_filter_options(self) -> dict:
        """Get distinct values for filter dropdowns.

        Returns:
            Dictionary with 'categories' and 'locations' lists for dropdowns.
        """
        categories = (
            self.db.query(Asset.asset_category)
            .distinct()
            .filter(Asset.asset_category.isnot(None))
            .order_by(Asset.asset_category)
            .all()
        )
        locations = (
            self.db.query(Asset.location)
            .distinct()
            .filter(Asset.location.isnot(None))
            .order_by(Asset.location)
            .all()
        )

        return {
            "categories": [{"value": c[0], "label": c[0]} for c in categories if c[0]],
            "locations": [{"value": l[0], "label": l[0]} for l in locations if l[0]],
        }
