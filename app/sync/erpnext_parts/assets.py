"""Asset and Vehicle sync functions for ERPNext.

This module handles syncing of:
- Asset Categories (with finance book child tables)
- Assets (Fixed Asset Register with depreciation schedules)
- Vehicles (Fleet Management)
"""
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, Optional

import httpx
import structlog

from app.models.asset import (
    Asset,
    AssetStatus,
    AssetCategory,
    AssetCategoryFinanceBook,
    AssetFinanceBook,
    AssetDepreciationSchedule,
)
from app.models.vehicle import Vehicle
from app.models.employee import Employee

if TYPE_CHECKING:
    from app.sync.erpnext import ERPNextSync

logger = structlog.get_logger()


def _coerce_bool(value: Any) -> bool:
    """Convert any value to boolean."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _parse_date(value: Any) -> Optional[date]:
    """Parse ISO date string to date object."""
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return datetime.fromisoformat(str(value)).date()
    except (ValueError, TypeError):
        return None


def _parse_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    """Parse value to Decimal with fallback."""
    try:
        return Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError):
        return default


def _map_asset_status(value: Any, docstatus: Any) -> AssetStatus:
    """Map ERPNext asset status to our enum."""
    if value:
        key = str(value).strip().lower().replace(" ", "_")
        mapping = {
            "draft": AssetStatus.DRAFT,
            "submitted": AssetStatus.SUBMITTED,
            "partially_depreciated": AssetStatus.PARTIALLY_DEPRECIATED,
            "fully_depreciated": AssetStatus.FULLY_DEPRECIATED,
            "sold": AssetStatus.SOLD,
            "scrapped": AssetStatus.SCRAPPED,
            "in_maintenance": AssetStatus.IN_MAINTENANCE,
            "out_of_order": AssetStatus.OUT_OF_ORDER,
        }
        if key in mapping:
            return mapping[key]
    # Fall back to docstatus
    if docstatus == 0:
        return AssetStatus.DRAFT
    return AssetStatus.SUBMITTED


# ============= ASSET CATEGORY SYNC =============

async def sync_asset_categories(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync asset categories from ERPNext."""
    sync_client.start_sync("asset_categories", "full" if full_sync else "incremental")

    try:
        filters = sync_client._get_incremental_filter("asset_categories", full_sync)
        categories = await sync_client._fetch_all_doctype(
            client,
            "Asset Category",
            fields=[
                "name",
                "asset_category_name",
                "enable_cwip_accounting",
                "modified",
            ],
            filters=filters,
        )

        for cat_data in categories:
            erpnext_id = cat_data.get("name")
            existing = None
            if erpnext_id:
                existing = sync_client.db.query(AssetCategory).filter(
                    AssetCategory.erpnext_id == erpnext_id
                ).first()

            if existing:
                existing.asset_category_name = cat_data.get("asset_category_name") or existing.asset_category_name
                existing.enable_cwip_accounting = _coerce_bool(cat_data.get("enable_cwip_accounting"))
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
                category = existing
            else:
                category = AssetCategory(
                    erpnext_id=erpnext_id,
                    asset_category_name=cat_data.get("asset_category_name") or erpnext_id or "Unknown",
                    enable_cwip_accounting=_coerce_bool(cat_data.get("enable_cwip_accounting")),
                )
                sync_client.db.add(category)
                sync_client.increment_created()

            sync_client.db.flush()

            # Fetch full document for child tables
            if erpnext_id:
                try:
                    cat_doc = await sync_client._fetch_document(client, "Asset Category", str(erpnext_id))
                    finance_books = cat_doc.get("finance_books", [])

                    # Clear existing children
                    sync_client.db.query(AssetCategoryFinanceBook).filter(
                        AssetCategoryFinanceBook.asset_category_id == category.id
                    ).delete()

                    # Add new children
                    for idx, fb in enumerate(finance_books):
                        child = AssetCategoryFinanceBook(
                            asset_category_id=category.id,
                            finance_book=fb.get("finance_book"),
                            depreciation_method=fb.get("depreciation_method"),
                            total_number_of_depreciations=int(fb.get("total_number_of_depreciations") or 0),
                            frequency_of_depreciation=int(fb.get("frequency_of_depreciation") or 12),
                            fixed_asset_account=fb.get("fixed_asset_account"),
                            accumulated_depreciation_account=fb.get("accumulated_depreciation_account"),
                            depreciation_expense_account=fb.get("depreciation_expense_account"),
                            capital_work_in_progress_account=fb.get("capital_work_in_progress_account"),
                            idx=idx,
                        )
                        sync_client.db.add(child)
                except Exception as e:
                    logger.warning("asset_category_children_failed", category=erpnext_id, error=str(e))

        sync_client.db.commit()
        sync_client._update_sync_cursor("asset_categories", categories, len(categories))
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


# ============= ASSET SYNC =============

async def sync_assets(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync fixed assets from ERPNext."""
    sync_client.start_sync("assets", "full" if full_sync else "incremental")

    try:
        filters = sync_client._get_incremental_filter("assets", full_sync)
        # Use minimal fields to avoid 417 errors from missing custom fields
        assets = await sync_client._fetch_all_doctype(
            client,
            "Asset",
            fields=["name", "modified"],
            filters=filters,
        )

        for asset_ref in assets:
            erpnext_id = asset_ref.get("name")
            if not erpnext_id:
                continue

            # Fetch full document to get all fields including child tables
            try:
                asset_data = await sync_client._fetch_document(client, "Asset", str(erpnext_id))
            except Exception as e:
                logger.warning("asset_fetch_failed", asset=erpnext_id, error=str(e))
                continue

            existing = sync_client.db.query(Asset).filter(
                Asset.erpnext_id == erpnext_id
            ).first()

            status = _map_asset_status(asset_data.get("status"), asset_data.get("docstatus"))

            if existing:
                existing.asset_name = asset_data.get("asset_name") or existing.asset_name
                existing.asset_category = asset_data.get("asset_category")
                existing.item_code = asset_data.get("item_code")
                existing.item_name = asset_data.get("item_name")
                existing.company = asset_data.get("company")
                existing.location = asset_data.get("location")
                existing.custodian = asset_data.get("custodian")
                existing.department = asset_data.get("department")
                existing.cost_center = asset_data.get("cost_center")
                existing.purchase_date = _parse_date(asset_data.get("purchase_date"))
                existing.available_for_use_date = _parse_date(asset_data.get("available_for_use_date"))
                existing.gross_purchase_amount = _parse_decimal(asset_data.get("gross_purchase_amount"))
                existing.purchase_receipt = asset_data.get("purchase_receipt")
                existing.purchase_invoice = asset_data.get("purchase_invoice")
                existing.supplier = asset_data.get("supplier")
                existing.asset_quantity = int(asset_data.get("asset_quantity") or 1)
                existing.opening_accumulated_depreciation = _parse_decimal(asset_data.get("opening_accumulated_depreciation"))
                existing.calculate_depreciation = _coerce_bool(asset_data.get("calculate_depreciation"))
                existing.is_existing_asset = _coerce_bool(asset_data.get("is_existing_asset"))
                existing.is_composite_asset = _coerce_bool(asset_data.get("is_composite_asset"))
                existing.status = status
                existing.docstatus = int(asset_data.get("docstatus") or 0)
                existing.disposal_date = _parse_date(asset_data.get("disposal_date"))
                existing.journal_entry_for_scrap = asset_data.get("journal_entry_for_scrap")
                existing.insured_value = _parse_decimal(asset_data.get("insured_value"))
                existing.insurance_start_date = _parse_date(asset_data.get("insurance_start_date"))
                existing.insurance_end_date = _parse_date(asset_data.get("insurance_end_date"))
                existing.comprehensive_insurance = asset_data.get("comprehensive_insurance")
                existing.warranty_expiry_date = _parse_date(asset_data.get("warranty_expiry_date"))
                existing.maintenance_required = _coerce_bool(asset_data.get("maintenance_required"))
                existing.next_depreciation_date = _parse_date(asset_data.get("next_depreciation_date"))
                existing.asset_owner = asset_data.get("asset_owner")
                existing.asset_owner_company = asset_data.get("asset_owner_company")
                existing.serial_no = asset_data.get("serial_no")
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
                asset = existing
            else:
                asset = Asset(
                    erpnext_id=erpnext_id,
                    asset_name=asset_data.get("asset_name") or erpnext_id or "Unknown",
                    asset_category=asset_data.get("asset_category"),
                    item_code=asset_data.get("item_code"),
                    item_name=asset_data.get("item_name"),
                    company=asset_data.get("company"),
                    location=asset_data.get("location"),
                    custodian=asset_data.get("custodian"),
                    department=asset_data.get("department"),
                    cost_center=asset_data.get("cost_center"),
                    purchase_date=_parse_date(asset_data.get("purchase_date")),
                    available_for_use_date=_parse_date(asset_data.get("available_for_use_date")),
                    gross_purchase_amount=_parse_decimal(asset_data.get("gross_purchase_amount")),
                    purchase_receipt=asset_data.get("purchase_receipt"),
                    purchase_invoice=asset_data.get("purchase_invoice"),
                    supplier=asset_data.get("supplier"),
                    asset_quantity=int(asset_data.get("asset_quantity") or 1),
                    opening_accumulated_depreciation=_parse_decimal(asset_data.get("opening_accumulated_depreciation")),
                    calculate_depreciation=_coerce_bool(asset_data.get("calculate_depreciation")),
                    is_existing_asset=_coerce_bool(asset_data.get("is_existing_asset")),
                    is_composite_asset=_coerce_bool(asset_data.get("is_composite_asset")),
                    status=status,
                    docstatus=int(asset_data.get("docstatus") or 0),
                    disposal_date=_parse_date(asset_data.get("disposal_date")),
                    journal_entry_for_scrap=asset_data.get("journal_entry_for_scrap"),
                    insured_value=_parse_decimal(asset_data.get("insured_value")),
                    insurance_start_date=_parse_date(asset_data.get("insurance_start_date")),
                    insurance_end_date=_parse_date(asset_data.get("insurance_end_date")),
                    comprehensive_insurance=asset_data.get("comprehensive_insurance"),
                    warranty_expiry_date=_parse_date(asset_data.get("warranty_expiry_date")),
                    maintenance_required=_coerce_bool(asset_data.get("maintenance_required")),
                    next_depreciation_date=_parse_date(asset_data.get("next_depreciation_date")),
                    asset_owner=asset_data.get("asset_owner"),
                    asset_owner_company=asset_data.get("asset_owner_company"),
                    serial_no=asset_data.get("serial_no"),
                )
                sync_client.db.add(asset)
                sync_client.increment_created()

            sync_client.db.flush()

            # Sync child tables (finance books, depreciation schedules) - we already have full doc
            try:
                # Sync finance books
                finance_books = asset_data.get("finance_books", [])
                sync_client.db.query(AssetFinanceBook).filter(
                    AssetFinanceBook.asset_id == asset.id
                ).delete()
                for idx, fb in enumerate(finance_books):
                    child = AssetFinanceBook(
                        asset_id=asset.id,
                        finance_book=fb.get("finance_book"),
                        depreciation_method=fb.get("depreciation_method"),
                        total_number_of_depreciations=int(fb.get("total_number_of_depreciations") or 0),
                        frequency_of_depreciation=int(fb.get("frequency_of_depreciation") or 12),
                        depreciation_start_date=_parse_date(fb.get("depreciation_start_date")),
                        expected_value_after_useful_life=_parse_decimal(fb.get("expected_value_after_useful_life")),
                        value_after_depreciation=_parse_decimal(fb.get("value_after_depreciation")),
                        daily_depreciation_amount=_parse_decimal(fb.get("daily_depreciation_amount")),
                        rate_of_depreciation=_parse_decimal(fb.get("rate_of_depreciation")),
                        idx=idx,
                        erpnext_name=fb.get("name"),
                    )
                    sync_client.db.add(child)

                # Update asset_value from first finance book
                if finance_books:
                    asset.asset_value = _parse_decimal(finance_books[0].get("value_after_depreciation"))

                # Sync depreciation schedules
                schedules = asset_data.get("schedules", [])
                sync_client.db.query(AssetDepreciationSchedule).filter(
                    AssetDepreciationSchedule.asset_id == asset.id
                ).delete()
                for idx, sch in enumerate(schedules):
                    schedule_entry = AssetDepreciationSchedule(
                        asset_id=asset.id,
                        finance_book=sch.get("finance_book"),
                        schedule_date=_parse_date(sch.get("schedule_date")),
                        depreciation_amount=_parse_decimal(sch.get("depreciation_amount")),
                        accumulated_depreciation_amount=_parse_decimal(sch.get("accumulated_depreciation_amount")),
                        journal_entry=sch.get("journal_entry"),
                        depreciation_booked=_coerce_bool(sch.get("journal_entry")),  # Has JE = booked
                        idx=idx,
                        erpnext_name=sch.get("name"),
                    )
                    sync_client.db.add(schedule_entry)

            except Exception as e:
                logger.warning("asset_children_failed", asset=erpnext_id, error=str(e))

        sync_client.db.commit()
        sync_client._update_sync_cursor("assets", assets, len(assets))
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


# ============= VEHICLE SYNC =============

async def sync_vehicles(
    sync_client: "ERPNextSync",
    client: httpx.AsyncClient,
    full_sync: bool = False,
) -> None:
    """Sync vehicles from ERPNext Fleet Management."""
    sync_client.start_sync("vehicles", "full" if full_sync else "incremental")

    try:
        filters = sync_client._get_incremental_filter("vehicles", full_sync)
        # Use minimal fields to avoid 417 errors from missing custom fields
        vehicles = await sync_client._fetch_all_doctype(
            client,
            "Vehicle",
            fields=["name", "modified"],
            filters=filters,
        )

        # Build employee lookup
        employees_by_erpnext_id: Dict[str, int] = {
            e.erpnext_id: e.id
            for e in sync_client.db.query(Employee).filter(Employee.erpnext_id.isnot(None)).all()
            if e.erpnext_id
        }

        for vehicle_ref in vehicles:
            erpnext_id = vehicle_ref.get("name")
            if not erpnext_id:
                continue

            # Fetch full document to get all fields
            try:
                vehicle_data = await sync_client._fetch_document(client, "Vehicle", str(erpnext_id))
            except Exception as e:
                logger.warning("vehicle_fetch_failed", vehicle=erpnext_id, error=str(e))
                continue

            license_plate = vehicle_data.get("license_plate") or erpnext_id or "Unknown"
            existing = sync_client.db.query(Vehicle).filter(
                Vehicle.erpnext_id == erpnext_id
            ).first()

            # Resolve employee FK
            employee_ref = vehicle_data.get("employee")
            employee_id = employees_by_erpnext_id.get(employee_ref) if employee_ref else None

            # Map docstatus to is_active (2 = Cancelled = inactive)
            docstatus = int(vehicle_data.get("docstatus") or 0)
            is_active = docstatus != 2

            # Parse integer fields safely
            def _safe_int(val):
                try:
                    return int(val) if val else None
                except (ValueError, TypeError):
                    return None

            if existing:
                existing.license_plate = license_plate
                existing.make = vehicle_data.get("make")
                existing.model = vehicle_data.get("model")
                existing.chassis_no = vehicle_data.get("chassis_no")
                existing.doors = _safe_int(vehicle_data.get("doors"))
                existing.wheels = _safe_int(vehicle_data.get("wheels"))
                existing.vehicle_value = _parse_decimal(vehicle_data.get("vehicle_value"))
                existing.fuel_type = vehicle_data.get("fuel_type")
                if "last_odometer" in vehicle_data and vehicle_data.get("last_odometer") not in (None, ""):
                    existing.odometer_value = _parse_decimal(vehicle_data.get("last_odometer"))
                if "uom" in vehicle_data and vehicle_data.get("uom") is not None:
                    existing.uom = vehicle_data.get("uom")
                existing.employee = employee_ref
                existing.employee_id = employee_id
                existing.location = vehicle_data.get("location")
                existing.docstatus = docstatus
                existing.is_active = is_active
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                vehicle = Vehicle(
                    erpnext_id=erpnext_id,
                    license_plate=license_plate,
                    make=vehicle_data.get("make"),
                    model=vehicle_data.get("model"),
                    chassis_no=vehicle_data.get("chassis_no"),
                    doors=_safe_int(vehicle_data.get("doors")),
                    wheels=_safe_int(vehicle_data.get("wheels")),
                    vehicle_value=_parse_decimal(vehicle_data.get("vehicle_value")),
                    fuel_type=vehicle_data.get("fuel_type"),
                    odometer_value=_parse_decimal(vehicle_data.get("last_odometer"))
                    if vehicle_data.get("last_odometer") not in (None, "")
                    else None,
                    uom=vehicle_data.get("uom") if "uom" in vehicle_data else None,
                    employee=employee_ref,
                    employee_id=employee_id,
                    location=vehicle_data.get("location"),
                    docstatus=docstatus,
                    is_active=is_active,
                )
                sync_client.db.add(vehicle)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client._update_sync_cursor("vehicles", vehicles, len(vehicles))
        sync_client.complete_sync()

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
