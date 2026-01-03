"""Asset management services.

This package contains all asset-related business logic:
- AssetService: Core CRUD operations for assets
- AssetCategoryService: Category management
- DepreciationService: Depreciation calculation and posting
- AssetCapitalizationService: CWIP to fixed asset transfers
- AssetDisposalService: Asset sale, scrap, and write-off
- AssetMaintenanceService: Maintenance tracking and alerts

Usage:
    from app.services.assets import AssetService, DepreciationService

    def my_route(db: Session = Depends(get_db)):
        asset_service = AssetService(db, principal)
        assets = asset_service.list_assets(filters, pagination)
        db.commit()  # Routes control transaction
"""
from .assets import AssetService
from .categories import AssetCategoryService
from .depreciation import DepreciationService
from .capitalization import AssetCapitalizationService
from .disposal import AssetDisposalService
from .maintenance import AssetMaintenanceService

from .types import (
    # Enums
    DepreciationMethod,
    DisposalType,
    # Asset types
    AssetFilters,
    AssetCreateData,
    AssetUpdateData,
    AssetFinanceBookData,
    # Category types
    CategoryFilters,
    CategoryCreateData,
    CategoryUpdateData,
    CategoryFinanceBookData,
    # Depreciation types
    DepreciationScheduleRow,
    PendingDepreciation,
    DepreciationPostResult,
    # Disposal types
    DisposalData,
    DisposalResult,
    # Capitalization types
    CapitalizationData,
    CapitalizationAccounts,
    CapitalizationResult,
    # Maintenance types
    MaintenanceFilters,
    MaintenanceCompleteData,
    AssetAlert,
)

__all__ = [
    # Services
    "AssetService",
    "AssetCategoryService",
    "DepreciationService",
    "AssetCapitalizationService",
    "AssetDisposalService",
    "AssetMaintenanceService",
    # Enums
    "DepreciationMethod",
    "DisposalType",
    # Asset types
    "AssetFilters",
    "AssetCreateData",
    "AssetUpdateData",
    "AssetFinanceBookData",
    # Category types
    "CategoryFilters",
    "CategoryCreateData",
    "CategoryUpdateData",
    "CategoryFinanceBookData",
    # Depreciation types
    "DepreciationScheduleRow",
    "PendingDepreciation",
    "DepreciationPostResult",
    # Disposal types
    "DisposalData",
    "DisposalResult",
    # Capitalization types
    "CapitalizationData",
    "CapitalizationAccounts",
    "CapitalizationResult",
    # Maintenance types
    "MaintenanceFilters",
    "MaintenanceCompleteData",
    "AssetAlert",
]
