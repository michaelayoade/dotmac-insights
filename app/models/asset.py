from __future__ import annotations

from sqlalchemy import String, Text, Enum, Date, ForeignKey, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.employee import Employee


# ============= ASSET CATEGORY =============
class AssetCategory(Base):
    """Asset categories for grouping fixed assets from ERPNext.

    Asset Categories define depreciation settings and accounting defaults
    for groups of similar assets (e.g., Computers, Furniture, Vehicles).
    """

    __tablename__ = "asset_categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Basic Info
    asset_category_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Depreciation Settings
    enable_cwip_accounting: Mapped[bool] = mapped_column(default=False)  # Capital Work in Progress

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    finance_books: Mapped[List["AssetCategoryFinanceBook"]] = relationship(
        back_populates="asset_category", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AssetCategory {self.asset_category_name}>"


# ============= ASSET CATEGORY FINANCE BOOK (Child Table) =============
class AssetCategoryFinanceBook(Base):
    """Finance book depreciation settings for Asset Categories.

    Defines default depreciation method, rates, and accounts for each
    finance book within an asset category.
    """

    __tablename__ = "asset_category_finance_books"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    asset_category_id: Mapped[int] = mapped_column(
        ForeignKey("asset_categories.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Finance Book reference
    finance_book: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Depreciation method
    depreciation_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    total_number_of_depreciations: Mapped[int] = mapped_column(default=0)
    frequency_of_depreciation: Mapped[int] = mapped_column(default=12)  # months

    # Accounts
    fixed_asset_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    accumulated_depreciation_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    depreciation_expense_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    capital_work_in_progress_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Relationship
    asset_category: Mapped["AssetCategory"] = relationship(back_populates="finance_books")

    def __repr__(self) -> str:
        return f"<AssetCategoryFinanceBook {self.finance_book} - {self.depreciation_method}>"


# ============= ASSET STATUS =============
class AssetStatus(enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    PARTIALLY_DEPRECIATED = "partially_depreciated"
    FULLY_DEPRECIATED = "fully_depreciated"
    SOLD = "sold"
    SCRAPPED = "scrapped"
    IN_MAINTENANCE = "in_maintenance"
    OUT_OF_ORDER = "out_of_order"


# ============= ASSET (Fixed Asset Register) =============
class Asset(Base):
    """Fixed Assets from ERPNext Asset Management module.

    Represents physical or intangible assets owned by the company,
    tracking their value, depreciation, location, and lifecycle.
    """

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Basic Info
    asset_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    asset_category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    item_code: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    item_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Company and Location
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    custodian: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # ERPNext employee name
    custodian_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"), nullable=True, index=True
    )  # FK for local queries
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cost_center: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Purchase Info
    purchase_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    available_for_use_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    gross_purchase_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    purchase_receipt: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    purchase_invoice: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    supplier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Asset Value
    asset_quantity: Mapped[int] = mapped_column(default=1)
    opening_accumulated_depreciation: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    asset_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))  # Current book value

    # Depreciation Settings
    calculate_depreciation: Mapped[bool] = mapped_column(default=True)
    is_existing_asset: Mapped[bool] = mapped_column(default=False)
    is_composite_asset: Mapped[bool] = mapped_column(default=False)

    # Status
    status: Mapped[AssetStatus] = mapped_column(Enum(AssetStatus), default=AssetStatus.DRAFT, index=True)
    docstatus: Mapped[int] = mapped_column(default=0)

    # Disposal Info
    disposal_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    journal_entry_for_scrap: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Insurance
    insured_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    insurance_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    insurance_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    comprehensive_insurance: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Warranty
    warranty_expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Maintenance
    maintenance_required: Mapped[bool] = mapped_column(default=False)
    next_depreciation_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Description
    asset_owner: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Company/Supplier
    asset_owner_company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Serial/Identification
    serial_no: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    finance_books: Mapped[List["AssetFinanceBook"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
    depreciation_schedules: Mapped[List["AssetDepreciationSchedule"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
    custodian_employee: Mapped[Optional["Employee"]] = relationship(
        "Employee",
        foreign_keys=[custodian_id],
        backref="custodian_assets"
    )

    def __repr__(self) -> str:
        return f"<Asset {self.asset_name} ({self.erpnext_id})>"


# ============= ASSET FINANCE BOOK (Child Table) =============
class AssetFinanceBook(Base):
    """Finance book depreciation settings for individual Assets.

    Each asset can have multiple finance books with different depreciation
    methods (e.g., one for tax purposes, one for financial reporting).
    """

    __tablename__ = "asset_finance_books"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Finance Book reference
    finance_book: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Depreciation method
    depreciation_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    total_number_of_depreciations: Mapped[int] = mapped_column(default=0)
    frequency_of_depreciation: Mapped[int] = mapped_column(default=12)  # months
    depreciation_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Values
    expected_value_after_useful_life: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    value_after_depreciation: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    daily_depreciation_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))

    # Rate-based depreciation
    rate_of_depreciation: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0"))

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # ERPNext child row name
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationship
    asset: Mapped["Asset"] = relationship(back_populates="finance_books")

    def __repr__(self) -> str:
        return f"<AssetFinanceBook {self.finance_book} - {self.depreciation_method}>"


# ============= ASSET DEPRECIATION SCHEDULE (Child Table) =============
class AssetDepreciationSchedule(Base):
    """Depreciation schedule rows for Assets.

    Contains the planned depreciation entries for an asset, showing
    when depreciation should be posted and how much.
    """

    __tablename__ = "asset_depreciation_schedules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Finance Book (depreciation schedules are per finance book)
    finance_book: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Schedule details
    schedule_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    depreciation_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    accumulated_depreciation_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))

    # Journal Entry for booked depreciation
    journal_entry: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Status
    depreciation_booked: Mapped[bool] = mapped_column(default=False)

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # ERPNext child row name
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationship
    asset: Mapped["Asset"] = relationship(back_populates="depreciation_schedules")

    def __repr__(self) -> str:
        return f"<AssetDepreciationSchedule {self.schedule_date} - {self.depreciation_amount}>"
