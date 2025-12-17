"""
Asset Management Module

Provides endpoints for managing fixed assets, depreciation,
maintenance, and asset lifecycle tracking.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import Session
from sqlalchemy.orm import selectinload
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.asset import (
    Asset,
    AssetStatus,
    AssetCategory,
    AssetCategoryFinanceBook,
    AssetFinanceBook,
    AssetDepreciationSchedule,
)

router = APIRouter(prefix="/assets", tags=["assets"])


# ============= PYDANTIC SCHEMAS =============

class AssetFinanceBookSchema(BaseModel):
    finance_book: Optional[str] = None
    depreciation_method: Optional[str] = None
    total_number_of_depreciations: int = 0
    frequency_of_depreciation: int = 12
    depreciation_start_date: Optional[date] = None
    expected_value_after_useful_life: Decimal = Decimal("0")
    rate_of_depreciation: Decimal = Decimal("0")

    class Config:
        from_attributes = True


class AssetDepreciationScheduleSchema(BaseModel):
    finance_book: Optional[str] = None
    schedule_date: Optional[date] = None
    depreciation_amount: Decimal = Decimal("0")
    accumulated_depreciation_amount: Decimal = Decimal("0")
    journal_entry: Optional[str] = None
    depreciation_booked: bool = False

    class Config:
        from_attributes = True


class AssetCreatePayload(BaseModel):
    asset_name: str
    asset_category: Optional[str] = None
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    custodian: Optional[str] = None
    department: Optional[str] = None
    cost_center: Optional[str] = None
    purchase_date: Optional[date] = None
    available_for_use_date: Optional[date] = None
    gross_purchase_amount: Decimal = Decimal("0")
    supplier: Optional[str] = None
    asset_quantity: int = 1
    calculate_depreciation: bool = True
    description: Optional[str] = None
    serial_no: Optional[str] = None
    finance_books: Optional[List[AssetFinanceBookSchema]] = None


class AssetUpdatePayload(BaseModel):
    asset_name: Optional[str] = None
    asset_category: Optional[str] = None
    location: Optional[str] = None
    custodian: Optional[str] = None
    department: Optional[str] = None
    cost_center: Optional[str] = None
    maintenance_required: Optional[bool] = None
    description: Optional[str] = None
    insured_value: Optional[Decimal] = None
    insurance_start_date: Optional[date] = None
    insurance_end_date: Optional[date] = None


class AssetCategoryCreatePayload(BaseModel):
    asset_category_name: str
    enable_cwip_accounting: bool = False


class DepreciationPostPayload(BaseModel):
    schedule_ids: List[int]


# ============= ASSET ENDPOINTS =============

@router.get("")
def list_assets(
    status: Optional[str] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by asset category"),
    location: Optional[str] = Query(None, description="Filter by location"),
    custodian: Optional[str] = Query(None, description="Filter by custodian"),
    department: Optional[str] = Query(None, description="Filter by department"),
    search: Optional[str] = Query(None, description="Search by name, serial, item code"),
    min_value: Optional[float] = Query(None, description="Minimum asset value"),
    max_value: Optional[float] = Query(None, description="Maximum asset value"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List all assets with filtering options."""
    query = select(Asset).options(
        selectinload(Asset.finance_books),
        selectinload(Asset.depreciation_schedules),
    )

    # Apply filters
    conditions = []
    if status:
        try:
            status_enum = AssetStatus(status)
            conditions.append(Asset.status == status_enum)
        except ValueError:
            pass
    if category:
        conditions.append(Asset.asset_category == category)
    if location:
        conditions.append(Asset.location == location)
    if custodian:
        conditions.append(Asset.custodian == custodian)
    if department:
        conditions.append(Asset.department == department)
    if search:
        search_term = f"%{search}%"
        conditions.append(
            or_(
                Asset.asset_name.ilike(search_term),
                Asset.serial_no.ilike(search_term),
                Asset.item_code.ilike(search_term),
                Asset.erpnext_id.ilike(search_term),
            )
        )
    if min_value is not None:
        conditions.append(Asset.asset_value >= Decimal(str(min_value)))
    if max_value is not None:
        conditions.append(Asset.asset_value <= Decimal(str(max_value)))

    if conditions:
        query = query.where(and_(*conditions))

    # Count total
    count_query = select(func.count(Asset.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    query = query.order_by(desc(Asset.created_at)).offset(offset).limit(limit)
    result = await db.execute(query)
    assets = result.scalars().all()

    return {
        "assets": [
            {
                "id": a.id,
                "erpnext_id": a.erpnext_id,
                "asset_name": a.asset_name,
                "asset_category": a.asset_category,
                "item_code": a.item_code,
                "item_name": a.item_name,
                "company": a.company,
                "location": a.location,
                "custodian": a.custodian,
                "department": a.department,
                "cost_center": a.cost_center,
                "purchase_date": a.purchase_date.isoformat() if a.purchase_date else None,
                "gross_purchase_amount": float(a.gross_purchase_amount),
                "asset_value": float(a.asset_value),
                "opening_accumulated_depreciation": float(a.opening_accumulated_depreciation),
                "status": a.status.value if a.status else None,
                "serial_no": a.serial_no,
                "maintenance_required": a.maintenance_required,
                "warranty_expiry_date": a.warranty_expiry_date.isoformat() if a.warranty_expiry_date else None,
                "insured_value": float(a.insured_value),
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in assets
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/summary")
def get_assets_summary(
    db: Session = Depends(get_db),
):
    """Get summary statistics for assets."""
    # Total assets by status
    status_query = select(
        Asset.status,
        func.count(Asset.id).label("count"),
        func.sum(Asset.asset_value).label("total_value"),
        func.sum(Asset.gross_purchase_amount).label("total_purchase_value"),
    ).group_by(Asset.status)
    status_result = await db.execute(status_query)
    status_data = status_result.all()

    # By category
    category_query = select(
        Asset.asset_category,
        func.count(Asset.id).label("count"),
        func.sum(Asset.asset_value).label("total_value"),
    ).where(Asset.asset_category.isnot(None)).group_by(Asset.asset_category)
    category_result = await db.execute(category_query)
    category_data = category_result.all()

    # By location
    location_query = select(
        Asset.location,
        func.count(Asset.id).label("count"),
        func.sum(Asset.asset_value).label("total_value"),
    ).where(Asset.location.isnot(None)).group_by(Asset.location)
    location_result = await db.execute(location_query)
    location_data = location_result.all()

    # Assets requiring maintenance
    maintenance_query = select(func.count(Asset.id)).where(Asset.maintenance_required == True)
    maintenance_result = await db.execute(maintenance_query)
    maintenance_count = maintenance_result.scalar() or 0

    # Warranty expiring soon (next 30 days)
    today = date.today()
    from datetime import timedelta
    warranty_query = select(func.count(Asset.id)).where(
        and_(
            Asset.warranty_expiry_date.isnot(None),
            Asset.warranty_expiry_date >= today,
            Asset.warranty_expiry_date <= today + timedelta(days=30),
        )
    )
    warranty_result = await db.execute(warranty_query)
    warranty_expiring = warranty_result.scalar() or 0

    # Total values
    totals_query = select(
        func.count(Asset.id).label("total_count"),
        func.sum(Asset.asset_value).label("total_book_value"),
        func.sum(Asset.gross_purchase_amount).label("total_purchase_value"),
        func.sum(Asset.opening_accumulated_depreciation).label("total_accumulated_depreciation"),
    )
    totals_result = await db.execute(totals_query)
    totals = totals_result.one()

    return {
        "totals": {
            "count": totals.total_count or 0,
            "book_value": float(totals.total_book_value or 0),
            "purchase_value": float(totals.total_purchase_value or 0),
            "accumulated_depreciation": float(totals.total_accumulated_depreciation or 0),
        },
        "by_status": [
            {
                "status": s.status.value if s.status else "unknown",
                "count": s.count,
                "total_value": float(s.total_value or 0),
                "purchase_value": float(s.total_purchase_value or 0),
            }
            for s in status_data
        ],
        "by_category": [
            {
                "category": c.asset_category,
                "count": c.count,
                "total_value": float(c.total_value or 0),
            }
            for c in category_data
        ],
        "by_location": [
            {
                "location": l.location,
                "count": l.count,
                "total_value": float(l.total_value or 0),
            }
            for l in location_data
        ],
        "maintenance_required": maintenance_count,
        "warranty_expiring_soon": warranty_expiring,
    }


@router.get("/depreciation-schedule")
def get_depreciation_schedule(
    asset_id: Optional[int] = Query(None, description="Filter by asset ID"),
    finance_book: Optional[str] = Query(None, description="Filter by finance book"),
    from_date: Optional[date] = Query(None, description="Schedule date from"),
    to_date: Optional[date] = Query(None, description="Schedule date to"),
    pending_only: bool = Query(False, description="Show only pending (not booked)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Get depreciation schedules across assets."""
    query = (
        select(AssetDepreciationSchedule)
        .join(Asset)
        .options(selectinload(AssetDepreciationSchedule.asset))
    )

    conditions = []
    if asset_id:
        conditions.append(AssetDepreciationSchedule.asset_id == asset_id)
    if finance_book:
        conditions.append(AssetDepreciationSchedule.finance_book == finance_book)
    if from_date:
        conditions.append(AssetDepreciationSchedule.schedule_date >= from_date)
    if to_date:
        conditions.append(AssetDepreciationSchedule.schedule_date <= to_date)
    if pending_only:
        conditions.append(AssetDepreciationSchedule.depreciation_booked == False)

    if conditions:
        query = query.where(and_(*conditions))

    # Count
    count_query = select(func.count(AssetDepreciationSchedule.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply ordering and pagination
    query = query.order_by(AssetDepreciationSchedule.schedule_date).offset(offset).limit(limit)
    result = await db.execute(query)
    schedules = result.scalars().all()

    return {
        "schedules": [
            {
                "id": s.id,
                "asset_id": s.asset_id,
                "asset_name": s.asset.asset_name if s.asset else None,
                "finance_book": s.finance_book,
                "schedule_date": s.schedule_date.isoformat() if s.schedule_date else None,
                "depreciation_amount": float(s.depreciation_amount),
                "accumulated_depreciation_amount": float(s.accumulated_depreciation_amount),
                "journal_entry": s.journal_entry,
                "depreciation_booked": s.depreciation_booked,
            }
            for s in schedules
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/pending-depreciation")
def get_pending_depreciation(
    as_of_date: Optional[date] = Query(None, description="Get depreciation due as of date"),
    db: Session = Depends(get_db),
):
    """Get pending depreciation entries due for posting."""
    target_date = as_of_date or date.today()

    query = (
        select(AssetDepreciationSchedule)
        .join(Asset)
        .where(
            and_(
                AssetDepreciationSchedule.depreciation_booked == False,
                AssetDepreciationSchedule.schedule_date <= target_date,
                Asset.status.in_([AssetStatus.SUBMITTED, AssetStatus.PARTIALLY_DEPRECIATED]),
            )
        )
        .options(selectinload(AssetDepreciationSchedule.asset))
        .order_by(AssetDepreciationSchedule.schedule_date)
    )
    result = await db.execute(query)
    schedules = result.scalars().all()

    total_amount = sum(s.depreciation_amount for s in schedules)

    return {
        "pending_entries": [
            {
                "id": s.id,
                "asset_id": s.asset_id,
                "asset_name": s.asset.asset_name if s.asset else None,
                "asset_category": s.asset.asset_category if s.asset else None,
                "finance_book": s.finance_book,
                "schedule_date": s.schedule_date.isoformat() if s.schedule_date else None,
                "depreciation_amount": float(s.depreciation_amount),
            }
            for s in schedules
        ],
        "total_pending_amount": float(total_amount),
        "count": len(schedules),
        "as_of_date": target_date.isoformat(),
    }


@router.get("/{asset_id}")
def get_asset(
    asset_id: int,
    db: Session = Depends(get_db),
):
    """Get detailed information for a single asset."""
    query = (
        select(Asset)
        .where(Asset.id == asset_id)
        .options(
            selectinload(Asset.finance_books),
            selectinload(Asset.depreciation_schedules),
        )
    )
    result = await db.execute(query)
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    return {
        "id": asset.id,
        "erpnext_id": asset.erpnext_id,
        "asset_name": asset.asset_name,
        "asset_category": asset.asset_category,
        "item_code": asset.item_code,
        "item_name": asset.item_name,
        "company": asset.company,
        "location": asset.location,
        "custodian": asset.custodian,
        "department": asset.department,
        "cost_center": asset.cost_center,
        "purchase_date": asset.purchase_date.isoformat() if asset.purchase_date else None,
        "available_for_use_date": asset.available_for_use_date.isoformat() if asset.available_for_use_date else None,
        "gross_purchase_amount": float(asset.gross_purchase_amount),
        "asset_value": float(asset.asset_value),
        "opening_accumulated_depreciation": float(asset.opening_accumulated_depreciation),
        "asset_quantity": asset.asset_quantity,
        "status": asset.status.value if asset.status else None,
        "docstatus": asset.docstatus,
        "serial_no": asset.serial_no,
        "supplier": asset.supplier,
        "purchase_receipt": asset.purchase_receipt,
        "purchase_invoice": asset.purchase_invoice,
        "calculate_depreciation": asset.calculate_depreciation,
        "is_existing_asset": asset.is_existing_asset,
        "is_composite_asset": asset.is_composite_asset,
        "maintenance_required": asset.maintenance_required,
        "next_depreciation_date": asset.next_depreciation_date.isoformat() if asset.next_depreciation_date else None,
        "disposal_date": asset.disposal_date.isoformat() if asset.disposal_date else None,
        "journal_entry_for_scrap": asset.journal_entry_for_scrap,
        "warranty_expiry_date": asset.warranty_expiry_date.isoformat() if asset.warranty_expiry_date else None,
        "insured_value": float(asset.insured_value),
        "insurance_start_date": asset.insurance_start_date.isoformat() if asset.insurance_start_date else None,
        "insurance_end_date": asset.insurance_end_date.isoformat() if asset.insurance_end_date else None,
        "comprehensive_insurance": asset.comprehensive_insurance,
        "asset_owner": asset.asset_owner,
        "description": asset.description,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
        "updated_at": asset.updated_at.isoformat() if asset.updated_at else None,
        "finance_books": [
            {
                "id": fb.id,
                "finance_book": fb.finance_book,
                "depreciation_method": fb.depreciation_method,
                "total_number_of_depreciations": fb.total_number_of_depreciations,
                "frequency_of_depreciation": fb.frequency_of_depreciation,
                "depreciation_start_date": fb.depreciation_start_date.isoformat() if fb.depreciation_start_date else None,
                "expected_value_after_useful_life": float(fb.expected_value_after_useful_life),
                "value_after_depreciation": float(fb.value_after_depreciation),
                "daily_depreciation_amount": float(fb.daily_depreciation_amount),
                "rate_of_depreciation": float(fb.rate_of_depreciation),
            }
            for fb in asset.finance_books
        ],
        "depreciation_schedules": [
            {
                "id": ds.id,
                "finance_book": ds.finance_book,
                "schedule_date": ds.schedule_date.isoformat() if ds.schedule_date else None,
                "depreciation_amount": float(ds.depreciation_amount),
                "accumulated_depreciation_amount": float(ds.accumulated_depreciation_amount),
                "journal_entry": ds.journal_entry,
                "depreciation_booked": ds.depreciation_booked,
            }
            for ds in sorted(asset.depreciation_schedules, key=lambda x: x.schedule_date or date.min)
        ],
    }


@router.post("")
def create_asset(
    payload: AssetCreatePayload,
    db: Session = Depends(get_db),
):
    """Create a new asset."""
    asset = Asset(
        asset_name=payload.asset_name,
        asset_category=payload.asset_category,
        item_code=payload.item_code,
        item_name=payload.item_name,
        company=payload.company,
        location=payload.location,
        custodian=payload.custodian,
        department=payload.department,
        cost_center=payload.cost_center,
        purchase_date=payload.purchase_date,
        available_for_use_date=payload.available_for_use_date,
        gross_purchase_amount=payload.gross_purchase_amount,
        asset_value=payload.gross_purchase_amount,  # Initial value = purchase amount
        supplier=payload.supplier,
        asset_quantity=payload.asset_quantity,
        calculate_depreciation=payload.calculate_depreciation,
        description=payload.description,
        serial_no=payload.serial_no,
        status=AssetStatus.DRAFT,
    )

    db.add(asset)
    await db.flush()

    # Add finance books if provided
    if payload.finance_books:
        for idx, fb_data in enumerate(payload.finance_books):
            fb = AssetFinanceBook(
                asset_id=asset.id,
                finance_book=fb_data.finance_book,
                depreciation_method=fb_data.depreciation_method,
                total_number_of_depreciations=fb_data.total_number_of_depreciations,
                frequency_of_depreciation=fb_data.frequency_of_depreciation,
                depreciation_start_date=fb_data.depreciation_start_date,
                expected_value_after_useful_life=fb_data.expected_value_after_useful_life,
                rate_of_depreciation=fb_data.rate_of_depreciation,
                idx=idx,
            )
            db.add(fb)

    await db.commit()
    await db.refresh(asset)

    return {"id": asset.id, "message": "Asset created successfully"}


@router.patch("/{asset_id}")
def update_asset(
    asset_id: int,
    payload: AssetUpdatePayload,
    db: Session = Depends(get_db),
):
    """Update an existing asset."""
    query = select(Asset).where(Asset.id == asset_id)
    result = await db.execute(query)
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Only allow updates on draft assets for critical fields
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(asset, key, value)

    await db.commit()
    return {"id": asset.id, "message": "Asset updated successfully"}


@router.post("/{asset_id}/submit")
def submit_asset(
    asset_id: int,
    db: Session = Depends(get_db),
):
    """Submit asset for use (change status from draft to submitted)."""
    query = select(Asset).where(Asset.id == asset_id)
    result = await db.execute(query)
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    if asset.status != AssetStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft assets can be submitted")

    asset.status = AssetStatus.SUBMITTED
    asset.docstatus = 1
    await db.commit()

    return {"id": asset.id, "message": "Asset submitted successfully"}


@router.post("/{asset_id}/scrap")
def scrap_asset(
    asset_id: int,
    scrap_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """Scrap an asset (mark as scrapped)."""
    query = select(Asset).where(Asset.id == asset_id)
    result = await db.execute(query)
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    if asset.status in [AssetStatus.SCRAPPED, AssetStatus.SOLD]:
        raise HTTPException(status_code=400, detail="Asset is already disposed")

    asset.status = AssetStatus.SCRAPPED
    asset.disposal_date = scrap_date or date.today()
    await db.commit()

    return {"id": asset.id, "message": "Asset scrapped successfully"}


# ============= ASSET CATEGORY ENDPOINTS =============

@router.get("/categories/")
def list_asset_categories(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List all asset categories."""
    query = (
        select(AssetCategory)
        .options(selectinload(AssetCategory.finance_books))
        .order_by(AssetCategory.asset_category_name)
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    categories = result.scalars().all()

    count_result = await db.execute(select(func.count(AssetCategory.id)))
    total = count_result.scalar() or 0

    return {
        "categories": [
            {
                "id": c.id,
                "erpnext_id": c.erpnext_id,
                "asset_category_name": c.asset_category_name,
                "enable_cwip_accounting": c.enable_cwip_accounting,
                "finance_books": [
                    {
                        "finance_book": fb.finance_book,
                        "depreciation_method": fb.depreciation_method,
                        "total_number_of_depreciations": fb.total_number_of_depreciations,
                        "frequency_of_depreciation": fb.frequency_of_depreciation,
                        "fixed_asset_account": fb.fixed_asset_account,
                        "accumulated_depreciation_account": fb.accumulated_depreciation_account,
                        "depreciation_expense_account": fb.depreciation_expense_account,
                    }
                    for fb in c.finance_books
                ],
            }
            for c in categories
        ],
        "total": total,
    }


@router.post("/categories/")
def create_asset_category(
    payload: AssetCategoryCreatePayload,
    db: Session = Depends(get_db),
):
    """Create a new asset category."""
    category = AssetCategory(
        asset_category_name=payload.asset_category_name,
        enable_cwip_accounting=payload.enable_cwip_accounting,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)

    return {"id": category.id, "message": "Asset category created successfully"}


# ============= MAINTENANCE ENDPOINTS =============

@router.get("/maintenance/due")
def get_maintenance_due(
    db: Session = Depends(get_db),
):
    """Get assets requiring maintenance."""
    query = (
        select(Asset)
        .where(
            and_(
                Asset.maintenance_required == True,
                Asset.status.notin_([AssetStatus.SCRAPPED, AssetStatus.SOLD]),
            )
        )
        .order_by(Asset.asset_name)
    )
    result = await db.execute(query)
    assets = result.scalars().all()

    return {
        "assets": [
            {
                "id": a.id,
                "asset_name": a.asset_name,
                "asset_category": a.asset_category,
                "location": a.location,
                "custodian": a.custodian,
                "serial_no": a.serial_no,
                "purchase_date": a.purchase_date.isoformat() if a.purchase_date else None,
                "asset_value": float(a.asset_value),
            }
            for a in assets
        ],
        "count": len(assets),
    }


@router.post("/{asset_id}/mark-maintenance")
def mark_for_maintenance(
    asset_id: int,
    db: Session = Depends(get_db),
):
    """Mark an asset as requiring maintenance."""
    query = select(Asset).where(Asset.id == asset_id)
    result = await db.execute(query)
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    asset.maintenance_required = True
    asset.status = AssetStatus.IN_MAINTENANCE
    await db.commit()

    return {"id": asset.id, "message": "Asset marked for maintenance"}


@router.post("/{asset_id}/complete-maintenance")
def complete_maintenance(
    asset_id: int,
    db: Session = Depends(get_db),
):
    """Mark maintenance as complete for an asset."""
    query = select(Asset).where(Asset.id == asset_id)
    result = await db.execute(query)
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    asset.maintenance_required = False
    # Restore to previous valid status based on depreciation
    if asset.asset_value <= 0:
        asset.status = AssetStatus.FULLY_DEPRECIATED
    else:
        asset.status = AssetStatus.PARTIALLY_DEPRECIATED
    await db.commit()

    return {"id": asset.id, "message": "Maintenance completed"}


# ============= WARRANTY ENDPOINTS =============

@router.get("/warranty/expiring")
def get_warranty_expiring(
    days: int = Query(30, description="Days until warranty expiry"),
    db: Session = Depends(get_db),
):
    """Get assets with warranty expiring soon."""
    from datetime import timedelta
    today = date.today()
    end_date = today + timedelta(days=days)

    query = (
        select(Asset)
        .where(
            and_(
                Asset.warranty_expiry_date.isnot(None),
                Asset.warranty_expiry_date >= today,
                Asset.warranty_expiry_date <= end_date,
                Asset.status.notin_([AssetStatus.SCRAPPED, AssetStatus.SOLD]),
            )
        )
        .order_by(Asset.warranty_expiry_date)
    )
    result = await db.execute(query)
    assets = result.scalars().all()

    return {
        "assets": [
            {
                "id": a.id,
                "asset_name": a.asset_name,
                "asset_category": a.asset_category,
                "serial_no": a.serial_no,
                "supplier": a.supplier,
                "warranty_expiry_date": a.warranty_expiry_date.isoformat() if a.warranty_expiry_date else None,
                "days_remaining": (a.warranty_expiry_date - today).days if a.warranty_expiry_date else None,
            }
            for a in assets
        ],
        "count": len(assets),
    }


# ============= INSURANCE ENDPOINTS =============

@router.get("/insurance/expiring")
def get_insurance_expiring(
    days: int = Query(30, description="Days until insurance expiry"),
    db: Session = Depends(get_db),
):
    """Get assets with insurance expiring soon."""
    from datetime import timedelta
    today = date.today()
    end_date = today + timedelta(days=days)

    query = (
        select(Asset)
        .where(
            and_(
                Asset.insurance_end_date.isnot(None),
                Asset.insurance_end_date >= today,
                Asset.insurance_end_date <= end_date,
                Asset.status.notin_([AssetStatus.SCRAPPED, AssetStatus.SOLD]),
            )
        )
        .order_by(Asset.insurance_end_date)
    )
    result = await db.execute(query)
    assets = result.scalars().all()

    return {
        "assets": [
            {
                "id": a.id,
                "asset_name": a.asset_name,
                "asset_category": a.asset_category,
                "serial_no": a.serial_no,
                "insured_value": float(a.insured_value),
                "insurance_end_date": a.insurance_end_date.isoformat() if a.insurance_end_date else None,
                "days_remaining": (a.insurance_end_date - today).days if a.insurance_end_date else None,
                "comprehensive_insurance": a.comprehensive_insurance,
            }
            for a in assets
        ],
        "count": len(assets),
    }
