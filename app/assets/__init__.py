"""
Asset Management API Module

Provides REST API endpoints for managing fixed assets, depreciation,
maintenance, and asset lifecycle tracking.

All business logic is delegated to services in app/services/assets/.
Routes are thin wrappers that:
- Parse and validate input
- Call service methods
- Map service exceptions to HTTP responses
- Control transaction boundaries (commit/rollback)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List, NoReturn
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict

from app.database import get_db
from app.auth import Principal, get_current_principal
from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.types import PaginationParams
from app.services.assets import (
    AssetService,
    AssetCategoryService,
    DepreciationService,
    AssetCapitalizationService,
    AssetDisposalService,
    AssetMaintenanceService,
    # Types
    AssetFilters,
    AssetCreateData,
    AssetUpdateData,
    AssetFinanceBookData,
    CategoryFilters,
    CategoryCreateData,
    CategoryUpdateData,
    CategoryFinanceBookData,
    DisposalType,
    DisposalData,
    CapitalizationData,
    MaintenanceCompleteData,
)
from app.models.asset import AssetStatus

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

    model_config = ConfigDict(from_attributes=True)


class AssetCreatePayload(BaseModel):
    asset_name: str
    asset_category: str
    gross_purchase_amount: Decimal = Decimal("0")
    purchase_date: Optional[date] = None
    available_for_use_date: Optional[date] = None
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    custodian_id: Optional[int] = None
    department: Optional[str] = None
    cost_center: Optional[str] = None
    description: Optional[str] = None
    serial_no: Optional[str] = None
    asset_quantity: int = 1
    calculate_depreciation: bool = True
    is_existing_asset: bool = False
    opening_accumulated_depreciation: Decimal = Decimal("0")
    # Insurance
    insured_value: Decimal = Decimal("0")
    insurance_start_date: Optional[date] = None
    insurance_end_date: Optional[date] = None
    comprehensive_insurance: Optional[str] = None
    # Warranty
    warranty_expiry_date: Optional[date] = None
    # Maintenance
    maintenance_required: bool = False
    # Finance books
    finance_books: Optional[List[AssetFinanceBookSchema]] = None


class AssetUpdatePayload(BaseModel):
    asset_name: Optional[str] = None
    asset_category: Optional[str] = None
    location: Optional[str] = None
    custodian_id: Optional[int] = None
    department: Optional[str] = None
    cost_center: Optional[str] = None
    maintenance_required: Optional[bool] = None
    description: Optional[str] = None
    serial_no: Optional[str] = None
    insured_value: Optional[Decimal] = None
    insurance_start_date: Optional[date] = None
    insurance_end_date: Optional[date] = None
    comprehensive_insurance: Optional[str] = None
    warranty_expiry_date: Optional[date] = None


class CategoryCreatePayload(BaseModel):
    asset_category_name: str
    enable_cwip_accounting: bool = False
    finance_books: Optional[List[dict]] = None


class CategoryUpdatePayload(BaseModel):
    asset_category_name: Optional[str] = None
    enable_cwip_accounting: Optional[bool] = None


class DisposalPayload(BaseModel):
    disposal_date: date
    disposal_type: str  # "sale" | "scrap" | "write_off"
    sale_amount: Decimal = Decimal("0")
    buyer_name: Optional[str] = None
    buyer_party_id: Optional[int] = None
    remarks: Optional[str] = None
    create_invoice: bool = False


class CapitalizationPayload(BaseModel):
    capitalization_date: date
    remarks: Optional[str] = None


class DepreciationPostPayload(BaseModel):
    schedule_ids: List[int]


class MaintenanceCompletePayload(BaseModel):
    completion_date: Optional[date] = None
    maintenance_cost: Decimal = Decimal("0")
    next_maintenance_date: Optional[date] = None
    remarks: Optional[str] = None
    capitalize_cost: bool = False


# ============= SERVICE DEPENDENCY PROVIDERS =============

def get_asset_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> AssetService:
    return AssetService(db, principal)


def get_category_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> AssetCategoryService:
    return AssetCategoryService(db, principal)


def get_depreciation_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> DepreciationService:
    return DepreciationService(db, principal)


def get_capitalization_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> AssetCapitalizationService:
    return AssetCapitalizationService(db, principal)


def get_disposal_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> AssetDisposalService:
    return AssetDisposalService(db, principal)


def get_maintenance_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> AssetMaintenanceService:
    return AssetMaintenanceService(db, principal)


# ============= ERROR HANDLER =============

def handle_service_error(e: Exception) -> NoReturn:
    """Convert service exceptions to HTTP exceptions.

    This function always raises an HTTPException and never returns.

    Args:
        e: The exception from the service layer.

    Raises:
        HTTPException: With appropriate status code based on exception type.
    """
    if isinstance(e, NotFoundError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, ValidationError):
        raise HTTPException(status_code=422, detail=str(e))
    if isinstance(e, ConflictError):
        raise HTTPException(status_code=409, detail=str(e))
    # Catch-all for unexpected exceptions
    raise HTTPException(status_code=500, detail=str(e))


# ============= ASSET ENDPOINTS =============

@router.get("")
def list_assets(
    status: Optional[str] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by asset category"),
    location: Optional[str] = Query(None, description="Filter by location"),
    custodian_id: Optional[int] = Query(None, description="Filter by custodian ID"),
    department: Optional[str] = Query(None, description="Filter by department"),
    search: Optional[str] = Query(None, description="Search by name, serial, item code"),
    include_disposed: bool = Query(False, description="Include disposed assets"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("asset_name"),
    sort_dir: str = Query("asc"),
    db: Session = Depends(get_db),
    service: AssetService = Depends(get_asset_service),
):
    """List all assets with filtering options."""
    try:
        # Parse status enum if provided
        status_enum = None
        if status:
            try:
                status_enum = AssetStatus(status)
            except ValueError:
                pass

        filters = AssetFilters(
            search=search,
            status=status_enum,
            category=category,
            location=location,
            custodian_id=custodian_id,
            department=department,
            include_disposed=include_disposed,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )
        pagination = PaginationParams(offset=offset, limit=limit)

        result = service.list_assets(filters, pagination)

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
                    "custodian_id": a.custodian_id,
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
                for a in result.items
            ],
            "total": result.total,
            "limit": limit,
            "offset": offset,
        }
    except (NotFoundError, ValidationError, ConflictError) as e:
        handle_service_error(e)


@router.get("/summary")
def get_assets_summary(
    db: Session = Depends(get_db),
    service: AssetService = Depends(get_asset_service),
    maintenance_service: AssetMaintenanceService = Depends(get_maintenance_service),
):
    """Get summary statistics for assets."""
    try:
        summary = service.get_asset_summary()
        by_category = service.get_assets_by_category()
        alerts = maintenance_service.get_alert_summary(days_ahead=30)

        return {
            "totals": {
                "count": summary["total_count"],
                "book_value": summary["total_value"],
            },
            "by_status": summary["by_status"],
            "by_category": by_category,
            "alerts": alerts,
        }
    except (NotFoundError, ValidationError, ConflictError) as e:
        handle_service_error(e)


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
    service: DepreciationService = Depends(get_depreciation_service),
):
    """Get depreciation schedules across assets."""
    from app.models.asset import AssetDepreciationSchedule, Asset
    from sqlalchemy import select, func, and_
    from sqlalchemy.orm import selectinload

    query = (
        db.query(AssetDepreciationSchedule)
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
        query = query.filter(and_(*conditions))

    # Count
    total = query.count()

    # Apply ordering and pagination
    schedules = (
        query.order_by(AssetDepreciationSchedule.schedule_date)
        .offset(offset)
        .limit(limit)
        .all()
    )

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
    service: DepreciationService = Depends(get_depreciation_service),
):
    """Get pending depreciation entries due for posting."""
    try:
        target_date = as_of_date or date.today()
        pending = service.get_pending_depreciation(as_of_date=target_date)

        total_amount = sum(p.depreciation_amount for p in pending)

        return {
            "pending_entries": [
                {
                    "id": p.schedule_id,
                    "asset_id": p.asset_id,
                    "asset_name": p.asset_name,
                    "asset_category": p.asset_category,
                    "schedule_date": p.schedule_date.isoformat() if p.schedule_date else None,
                    "depreciation_amount": float(p.depreciation_amount),
                    "book_value_before": float(p.book_value_before),
                    "book_value_after": float(p.book_value_after),
                }
                for p in pending
            ],
            "total_pending_amount": float(total_amount),
            "count": len(pending),
            "as_of_date": target_date.isoformat(),
        }
    except (NotFoundError, ValidationError, ConflictError) as e:
        handle_service_error(e)


@router.post("/depreciation/post")
def post_depreciation_batch(
    payload: DepreciationPostPayload,
    db: Session = Depends(get_db),
    service: DepreciationService = Depends(get_depreciation_service),
):
    """Post multiple depreciation entries in a batch."""
    try:
        result = service.post_depreciation_batch(payload.schedule_ids)
        db.commit()

        return {
            "message": f"Posted {result.schedules_posted} depreciation entries",
            "journal_entry_id": result.journal_entry_id,
            "journal_entry_number": result.journal_entry_number,
            "total_depreciation": float(result.total_depreciation),
            "schedules_posted": result.schedules_posted,
        }
    except (NotFoundError, ValidationError, ConflictError) as e:
        db.rollback()
        handle_service_error(e)


@router.get("/{asset_id}")
def get_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    service: AssetService = Depends(get_asset_service),
):
    """Get detailed information for a single asset."""
    try:
        asset = service.get_asset(asset_id, include_schedules=True)

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
            "custodian_id": asset.custodian_id,
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
    except (NotFoundError, ValidationError, ConflictError) as e:
        handle_service_error(e)


@router.post("")
def create_asset(
    payload: AssetCreatePayload,
    db: Session = Depends(get_db),
    service: AssetService = Depends(get_asset_service),
):
    """Create a new asset."""
    try:
        # Convert payload to service data
        finance_books_data = []
        if payload.finance_books:
            for fb in payload.finance_books:
                finance_books_data.append(AssetFinanceBookData(
                    finance_book=fb.finance_book,
                    depreciation_method=fb.depreciation_method or "straight_line",
                    total_number_of_depreciations=fb.total_number_of_depreciations,
                    frequency_of_depreciation=fb.frequency_of_depreciation,
                    depreciation_start_date=fb.depreciation_start_date,
                    expected_value_after_useful_life=fb.expected_value_after_useful_life,
                    rate_of_depreciation=fb.rate_of_depreciation,
                ))

        data = AssetCreateData(
            asset_name=payload.asset_name,
            asset_category=payload.asset_category,
            gross_purchase_amount=payload.gross_purchase_amount,
            purchase_date=payload.purchase_date,
            available_for_use_date=payload.available_for_use_date,
            item_code=payload.item_code,
            item_name=payload.item_name,
            location=payload.location,
            custodian_id=payload.custodian_id,
            department=payload.department,
            cost_center=payload.cost_center,
            company=payload.company,
            description=payload.description,
            serial_no=payload.serial_no,
            asset_quantity=payload.asset_quantity,
            calculate_depreciation=payload.calculate_depreciation,
            is_existing_asset=payload.is_existing_asset,
            opening_accumulated_depreciation=payload.opening_accumulated_depreciation,
            insured_value=payload.insured_value,
            insurance_start_date=payload.insurance_start_date,
            insurance_end_date=payload.insurance_end_date,
            comprehensive_insurance=payload.comprehensive_insurance,
            warranty_expiry_date=payload.warranty_expiry_date,
            maintenance_required=payload.maintenance_required,
            finance_books=finance_books_data,
        )

        asset = service.create_asset(data)
        db.commit()

        return {"id": asset.id, "message": "Asset created successfully"}
    except (NotFoundError, ValidationError, ConflictError) as e:
        db.rollback()
        handle_service_error(e)


@router.patch("/{asset_id}")
def update_asset(
    asset_id: int,
    payload: AssetUpdatePayload,
    db: Session = Depends(get_db),
    service: AssetService = Depends(get_asset_service),
):
    """Update an existing asset."""
    try:
        data = AssetUpdateData(
            asset_name=payload.asset_name,
            asset_category=payload.asset_category,
            location=payload.location,
            custodian_id=payload.custodian_id,
            department=payload.department,
            cost_center=payload.cost_center,
            description=payload.description,
            serial_no=payload.serial_no,
            insured_value=payload.insured_value,
            insurance_start_date=payload.insurance_start_date,
            insurance_end_date=payload.insurance_end_date,
            comprehensive_insurance=payload.comprehensive_insurance,
            warranty_expiry_date=payload.warranty_expiry_date,
            maintenance_required=payload.maintenance_required,
        )

        asset = service.update_asset(asset_id, data)
        db.commit()

        return {"id": asset.id, "message": "Asset updated successfully"}
    except (NotFoundError, ValidationError, ConflictError) as e:
        db.rollback()
        handle_service_error(e)


@router.delete("/{asset_id}")
def delete_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    service: AssetService = Depends(get_asset_service),
):
    """Delete an asset (only draft assets)."""
    try:
        service.delete_asset(asset_id)
        db.commit()
        return {"message": "Asset deleted successfully"}
    except (NotFoundError, ValidationError, ConflictError) as e:
        db.rollback()
        handle_service_error(e)


@router.post("/{asset_id}/submit")
def submit_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    service: AssetService = Depends(get_asset_service),
):
    """Submit asset for use (change status from draft to submitted)."""
    try:
        asset = service.submit_asset(asset_id)
        db.commit()
        return {"id": asset.id, "message": "Asset submitted successfully", "status": asset.status.value}
    except (NotFoundError, ValidationError, ConflictError) as e:
        db.rollback()
        handle_service_error(e)


@router.post("/{asset_id}/capitalize")
def capitalize_asset(
    asset_id: int,
    payload: CapitalizationPayload,
    db: Session = Depends(get_db),
    service: AssetCapitalizationService = Depends(get_capitalization_service),
):
    """Capitalize an asset (transfer from CWIP to fixed asset)."""
    try:
        data = CapitalizationData(
            capitalization_date=payload.capitalization_date,
            remarks=payload.remarks,
        )
        result = service.capitalize_asset(asset_id, data)
        db.commit()

        return {
            "id": result.asset_id,
            "message": "Asset capitalized successfully",
            "journal_entry_id": result.journal_entry_id,
            "journal_entry_number": result.journal_entry_number,
            "amount_capitalized": float(result.amount_capitalized),
        }
    except (NotFoundError, ValidationError, ConflictError) as e:
        db.rollback()
        handle_service_error(e)


@router.post("/{asset_id}/dispose")
def dispose_asset(
    asset_id: int,
    payload: DisposalPayload,
    db: Session = Depends(get_db),
    service: AssetDisposalService = Depends(get_disposal_service),
):
    """Dispose of an asset (sale, scrap, or write-off)."""
    try:
        # Parse disposal type
        try:
            disposal_type = DisposalType(payload.disposal_type)
        except ValueError:
            raise ValidationError(f"Invalid disposal type: {payload.disposal_type}")

        data = DisposalData(
            disposal_date=payload.disposal_date,
            disposal_type=disposal_type,
            sale_amount=payload.sale_amount,
            buyer_name=payload.buyer_name,
            buyer_party_id=payload.buyer_party_id,
            remarks=payload.remarks,
            create_invoice=payload.create_invoice,
        )
        result = service.dispose_asset(asset_id, data)
        db.commit()

        return {
            "id": result.asset_id,
            "message": f"Asset {result.disposal_type.value} successfully",
            "disposal_type": result.disposal_type.value,
            "book_value_at_disposal": float(result.book_value_at_disposal),
            "sale_amount": float(result.sale_amount),
            "gain_loss": float(result.gain_loss),
            "journal_entry_id": result.journal_entry_id,
            "journal_entry_number": result.journal_entry_number,
        }
    except (NotFoundError, ValidationError, ConflictError) as e:
        db.rollback()
        handle_service_error(e)


@router.post("/{asset_id}/scrap")
def scrap_asset(
    asset_id: int,
    scrap_date: Optional[date] = None,
    db: Session = Depends(get_db),
    service: AssetDisposalService = Depends(get_disposal_service),
):
    """Scrap an asset (mark as scrapped)."""
    try:
        data = DisposalData(
            disposal_date=scrap_date or date.today(),
            disposal_type=DisposalType.SCRAP,
        )
        result = service.dispose_asset(asset_id, data)
        db.commit()

        return {
            "id": result.asset_id,
            "message": "Asset scrapped successfully",
            "journal_entry_id": result.journal_entry_id,
        }
    except (NotFoundError, ValidationError, ConflictError) as e:
        db.rollback()
        handle_service_error(e)


@router.post("/{asset_id}/depreciate")
def depreciate_asset(
    asset_id: int,
    as_of_date: Optional[date] = None,
    db: Session = Depends(get_db),
    service: DepreciationService = Depends(get_depreciation_service),
):
    """Post all pending depreciation for an asset."""
    try:
        pending = service.get_pending_depreciation_for_asset(asset_id, as_of_date)
        if not pending:
            return {"message": "No pending depreciation entries", "posted": 0}

        schedule_ids = [p.schedule_id for p in pending]
        result = service.post_depreciation_batch(schedule_ids)
        db.commit()

        return {
            "message": f"Posted {result.schedules_posted} depreciation entries",
            "posted": result.schedules_posted,
            "total_depreciation": float(result.total_depreciation),
            "journal_entry_id": result.journal_entry_id,
        }
    except (NotFoundError, ValidationError, ConflictError) as e:
        db.rollback()
        handle_service_error(e)


# ============= ASSET CATEGORY ENDPOINTS =============

@router.get("/categories/")
def list_asset_categories(
    search: Optional[str] = Query(None),
    enable_cwip_accounting: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    service: AssetCategoryService = Depends(get_category_service),
):
    """List all asset categories."""
    try:
        filters = CategoryFilters(
            search=search,
            enable_cwip_accounting=enable_cwip_accounting,
        )
        pagination = PaginationParams(offset=offset, limit=limit)

        result = service.list_categories(filters, pagination)

        return {
            "categories": [
                {
                    "id": c.id,
                    "erpnext_id": c.erpnext_id,
                    "asset_category_name": c.asset_category_name,
                    "enable_cwip_accounting": c.enable_cwip_accounting,
                    "finance_books": [
                        {
                            "id": fb.id,
                            "finance_book": fb.finance_book,
                            "depreciation_method": fb.depreciation_method,
                            "total_number_of_depreciations": fb.total_number_of_depreciations,
                            "frequency_of_depreciation": fb.frequency_of_depreciation,
                            "fixed_asset_account": fb.fixed_asset_account,
                            "accumulated_depreciation_account": fb.accumulated_depreciation_account,
                            "depreciation_expense_account": fb.depreciation_expense_account,
                            "capital_work_in_progress_account": fb.capital_work_in_progress_account,
                        }
                        for fb in c.finance_books
                    ],
                }
                for c in result.items
            ],
            "total": result.total,
            "limit": limit,
            "offset": offset,
        }
    except (NotFoundError, ValidationError, ConflictError) as e:
        handle_service_error(e)


@router.get("/categories/{category_id}")
def get_asset_category(
    category_id: int,
    db: Session = Depends(get_db),
    service: AssetCategoryService = Depends(get_category_service),
):
    """Get a single asset category."""
    try:
        category = service.get_category(category_id)
        return {
            "id": category.id,
            "erpnext_id": category.erpnext_id,
            "asset_category_name": category.asset_category_name,
            "enable_cwip_accounting": category.enable_cwip_accounting,
            "finance_books": [
                {
                    "id": fb.id,
                    "finance_book": fb.finance_book,
                    "depreciation_method": fb.depreciation_method,
                    "total_number_of_depreciations": fb.total_number_of_depreciations,
                    "frequency_of_depreciation": fb.frequency_of_depreciation,
                    "fixed_asset_account": fb.fixed_asset_account,
                    "accumulated_depreciation_account": fb.accumulated_depreciation_account,
                    "depreciation_expense_account": fb.depreciation_expense_account,
                    "capital_work_in_progress_account": fb.capital_work_in_progress_account,
                }
                for fb in category.finance_books
            ],
        }
    except (NotFoundError, ValidationError, ConflictError) as e:
        handle_service_error(e)


@router.post("/categories/")
def create_asset_category(
    payload: CategoryCreatePayload,
    db: Session = Depends(get_db),
    service: AssetCategoryService = Depends(get_category_service),
):
    """Create a new asset category."""
    try:
        finance_books_data = []
        if payload.finance_books:
            for fb in payload.finance_books:
                finance_books_data.append(CategoryFinanceBookData(
                    finance_book=fb.get("finance_book"),
                    depreciation_method=fb.get("depreciation_method", "straight_line"),
                    total_number_of_depreciations=fb.get("total_number_of_depreciations", 60),
                    frequency_of_depreciation=fb.get("frequency_of_depreciation", 12),
                    fixed_asset_account=fb.get("fixed_asset_account"),
                    accumulated_depreciation_account=fb.get("accumulated_depreciation_account"),
                    depreciation_expense_account=fb.get("depreciation_expense_account"),
                    capital_work_in_progress_account=fb.get("capital_work_in_progress_account"),
                ))

        data = CategoryCreateData(
            asset_category_name=payload.asset_category_name,
            enable_cwip_accounting=payload.enable_cwip_accounting,
            finance_books=finance_books_data,
        )

        category = service.create_category(data)
        db.commit()

        return {"id": category.id, "message": "Asset category created successfully"}
    except (NotFoundError, ValidationError, ConflictError) as e:
        db.rollback()
        handle_service_error(e)


@router.patch("/categories/{category_id}")
def update_asset_category(
    category_id: int,
    payload: CategoryUpdatePayload,
    db: Session = Depends(get_db),
    service: AssetCategoryService = Depends(get_category_service),
):
    """Update an asset category."""
    try:
        data = CategoryUpdateData(
            asset_category_name=payload.asset_category_name,
            enable_cwip_accounting=payload.enable_cwip_accounting,
        )
        category = service.update_category(category_id, data)
        db.commit()

        return {"id": category.id, "message": "Asset category updated successfully"}
    except (NotFoundError, ValidationError, ConflictError) as e:
        db.rollback()
        handle_service_error(e)


@router.delete("/categories/{category_id}")
def delete_asset_category(
    category_id: int,
    db: Session = Depends(get_db),
    service: AssetCategoryService = Depends(get_category_service),
):
    """Delete an asset category."""
    try:
        service.delete_category(category_id)
        db.commit()
        return {"message": "Asset category deleted successfully"}
    except (NotFoundError, ValidationError, ConflictError) as e:
        db.rollback()
        handle_service_error(e)


# ============= MAINTENANCE ENDPOINTS =============

@router.get("/maintenance/due")
def get_maintenance_due(
    days_ahead: int = Query(7, description="Days to look ahead"),
    db: Session = Depends(get_db),
    service: AssetMaintenanceService = Depends(get_maintenance_service),
):
    """Get assets requiring maintenance."""
    try:
        assets = service.get_due_maintenance(days_ahead=days_ahead)

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
    except (NotFoundError, ValidationError, ConflictError) as e:
        handle_service_error(e)


@router.post("/{asset_id}/mark-maintenance")
def mark_for_maintenance(
    asset_id: int,
    db: Session = Depends(get_db),
    service: AssetMaintenanceService = Depends(get_maintenance_service),
):
    """Mark an asset as requiring maintenance."""
    try:
        asset = service.mark_in_maintenance(asset_id)
        db.commit()
        return {"id": asset.id, "message": "Asset marked for maintenance", "status": asset.status.value}
    except (NotFoundError, ValidationError, ConflictError) as e:
        db.rollback()
        handle_service_error(e)


@router.post("/{asset_id}/complete-maintenance")
def complete_maintenance(
    asset_id: int,
    payload: Optional[MaintenanceCompletePayload] = None,
    db: Session = Depends(get_db),
    service: AssetMaintenanceService = Depends(get_maintenance_service),
):
    """Mark maintenance as complete for an asset."""
    try:
        data = None
        if payload:
            data = MaintenanceCompleteData(
                completion_date=payload.completion_date or date.today(),
                maintenance_cost=payload.maintenance_cost,
                next_maintenance_date=payload.next_maintenance_date,
                remarks=payload.remarks,
                capitalize_cost=payload.capitalize_cost,
            )

        asset = service.complete_maintenance(asset_id, data)
        db.commit()
        return {"id": asset.id, "message": "Maintenance completed", "status": asset.status.value}
    except (NotFoundError, ValidationError, ConflictError) as e:
        db.rollback()
        handle_service_error(e)


# ============= WARRANTY ENDPOINTS =============

@router.get("/warranty/expiring")
def get_warranty_expiring(
    days: int = Query(30, description="Days until warranty expiry"),
    db: Session = Depends(get_db),
    service: AssetMaintenanceService = Depends(get_maintenance_service),
):
    """Get assets with warranty expiring soon."""
    try:
        assets = service.get_expiring_warranties(days_ahead=days)
        today = date.today()

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
    except (NotFoundError, ValidationError, ConflictError) as e:
        handle_service_error(e)


# ============= INSURANCE ENDPOINTS =============

@router.get("/insurance/expiring")
def get_insurance_expiring(
    days: int = Query(30, description="Days until insurance expiry"),
    db: Session = Depends(get_db),
    service: AssetMaintenanceService = Depends(get_maintenance_service),
):
    """Get assets with insurance expiring soon."""
    try:
        assets = service.get_expiring_insurance(days_ahead=days)
        today = date.today()

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
    except (NotFoundError, ValidationError, ConflictError) as e:
        handle_service_error(e)


# ============= ALERTS ENDPOINT =============

@router.get("/alerts")
def get_asset_alerts(
    days_ahead: int = Query(30, description="Days to look ahead"),
    db: Session = Depends(get_db),
    service: AssetMaintenanceService = Depends(get_maintenance_service),
):
    """Get all asset alerts (maintenance, warranty, insurance)."""
    try:
        alerts = service.get_all_alerts(days_ahead=days_ahead)
        summary = service.get_alert_summary(days_ahead=days_ahead)

        return {
            "alerts": [
                {
                    "alert_type": a.alert_type,
                    "asset_id": a.asset_id,
                    "asset_name": a.asset_name,
                    "location": a.location,
                    "custodian_name": a.custodian_name,
                    "due_date": a.due_date.isoformat() if a.due_date else None,
                    "days_until_due": a.days_until_due,
                }
                for a in alerts
            ],
            "summary": summary,
        }
    except (NotFoundError, ValidationError, ConflictError) as e:
        handle_service_error(e)


# ============= CWIP ENDPOINTS =============

@router.get("/cwip")
def get_cwip_assets(
    db: Session = Depends(get_db),
    service: AssetCapitalizationService = Depends(get_capitalization_service),
):
    """Get assets in Capital Work in Progress (awaiting capitalization)."""
    try:
        assets = service.get_cwip_assets()
        summary = service.get_cwip_summary()

        return {
            "assets": [
                {
                    "id": a.id,
                    "asset_name": a.asset_name,
                    "asset_category": a.asset_category,
                    "gross_purchase_amount": float(a.gross_purchase_amount),
                    "purchase_date": a.purchase_date.isoformat() if a.purchase_date else None,
                    "supplier": a.supplier,
                }
                for a in assets
            ],
            "summary": {
                "total_count": summary["total_count"],
                "total_value": float(summary["total_value"]),
                "by_category": summary["by_category"],
            },
        }
    except (NotFoundError, ValidationError, ConflictError) as e:
        handle_service_error(e)
