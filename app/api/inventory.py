"""Inventory API endpoints for stock management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, desc
from typing import Dict, Any, Optional, List
from datetime import datetime, date
from decimal import Decimal
import structlog

from app.database import get_db
from app.auth import Require, get_current_principal, Principal
from app.models.inventory import (
    Warehouse,
    StockEntry,
    StockEntryDetail,
    StockLedgerEntry,
    LandedCostVoucher,
    LandedCostItem,
    LandedCostTax,
)
from app.models.sales import Item
from pydantic import validator

router = APIRouter(prefix="/inventory", tags=["inventory"])
logger = structlog.get_logger()


def _parse_date(value: Optional[str], field_name: str) -> Optional[date]:
    """Parse date string to date object."""
    if not value:
        return None
    try:
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format for {field_name}")


def _to_decimal(value: Optional[float | int | str], field: str) -> Decimal:
    """Convert incoming numeric values to Decimal."""
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid numeric value for {field}")


def _map_entry_type(entry_type: str) -> str:
    """Map compact entry type to ERPNext-style string."""
    mapping = {
        "material_receipt": "Material Receipt",
        "material_issue": "Material Issue",
        "material_transfer": "Material Transfer",
        "material_transfer_for_manufacture": "Material Transfer for Manufacture",
        "material_consumption_for_manufacture": "Material Consumption for Manufacture",
        "manufacture": "Manufacture",
        "repack": "Repack",
        "send_to_subcontractor": "Send to Subcontractor",
    }
    return mapping.get(entry_type.lower(), entry_type)


def _validate_stock_entry_request(entry_type_raw: str, lines: List[StockEntryLine]) -> str:
    allowed = {
        "material_receipt",
        "material_issue",
        "material_transfer",
        "material_transfer_for_manufacture",
        "material_consumption_for_manufacture",
        "manufacture",
        "repack",
        "send_to_subcontractor",
    }
    entry_key = entry_type_raw.lower()
    if entry_key not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid entry_type: {entry_type_raw}")

    if not lines:
        raise HTTPException(status_code=400, detail="At least one line is required")

    seen_serials: set[str] = set()
    for line in lines:
        if line.qty is None or line.qty <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be greater than zero")
        if line.rate is None or line.rate < 0:
            raise HTTPException(status_code=400, detail="Rate must be zero or positive")

        serials = line.serial_nos or []
        for s in serials:
            if s in seen_serials:
                raise HTTPException(status_code=400, detail=f"Duplicate serial number: {s}")
            seen_serials.add(s)

        if entry_key == "material_receipt":
            if not line.t_warehouse:
                raise HTTPException(status_code=400, detail="material_receipt requires t_warehouse")
        elif entry_key == "material_issue":
            if not line.s_warehouse:
                raise HTTPException(status_code=400, detail="material_issue requires s_warehouse")
        elif entry_key.startswith("material_transfer"):
            if not line.s_warehouse or not line.t_warehouse:
                raise HTTPException(status_code=400, detail="material_transfer requires both s_warehouse and t_warehouse")
            if line.s_warehouse == line.t_warehouse:
                raise HTTPException(status_code=400, detail="Source and target warehouse cannot match for transfer")

    return _map_entry_type(entry_key)


# Pydantic request schemas
class ItemCreateRequest(BaseModel):
    item_code: str = Field(..., min_length=1)
    item_name: str = Field(..., min_length=1)
    description: Optional[str] = None
    item_group: Optional[str] = None
    uom: Optional[str] = None
    default_warehouse: Optional[str] = None
    valuation_rate: Optional[float] = None
    standard_selling_rate: Optional[float] = None
    is_stock_item: bool = True
    status: str = Field(default="active", pattern="^(active|inactive)$")


class ItemUpdateRequest(BaseModel):
    item_name: Optional[str] = None
    description: Optional[str] = None
    item_group: Optional[str] = None
    uom: Optional[str] = None
    default_warehouse: Optional[str] = None
    valuation_rate: Optional[float] = None
    standard_selling_rate: Optional[float] = None
    is_stock_item: Optional[bool] = None
    status: Optional[str] = Field(default=None, pattern="^(active|inactive)$")


class WarehouseCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    parent_warehouse: Optional[str] = None
    company: Optional[str] = None
    is_group: bool = False
    address: Optional[str] = None
    status: str = Field(default="active", pattern="^(active|inactive)$")


class WarehouseUpdateRequest(BaseModel):
    name: Optional[str] = None
    parent_warehouse: Optional[str] = None
    company: Optional[str] = None
    is_group: Optional[bool] = None
    address: Optional[str] = None
    status: Optional[str] = Field(default=None, pattern="^(active|inactive)$")


class StockEntryLine(BaseModel):
    item_code: str
    qty: float
    uom: Optional[str] = None
    s_warehouse: Optional[str] = None
    t_warehouse: Optional[str] = None
    rate: float = 0
    serial_nos: Optional[List[str]] = None


class StockEntryCreateRequest(BaseModel):
    entry_type: str = Field(..., description="material_receipt|material_issue|material_transfer|...")
    posting_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    company: Optional[str] = None
    remarks: Optional[str] = None
    lines: List[StockEntryLine]


class StockEntryUpdateRequest(BaseModel):
    posting_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    remarks: Optional[str] = None
    docstatus: Optional[int] = Field(default=None, ge=0, le=2, description="0=draft, 1=submitted, 2=cancelled")


# ============= WRITE ENDPOINTS (LOCAL) =============

@router.post("/items", dependencies=[Depends(Require("inventory:write"))])
async def create_item(
    request: ItemCreateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a local inventory item (does not push upstream)."""
    existing = db.query(Item).filter(Item.item_code == request.item_code).first()
    if existing:
        raise HTTPException(status_code=409, detail="Item code already exists")

    item = Item(
        item_code=request.item_code,
        item_name=request.item_name,
        item_group=request.item_group,
        description=request.description,
        stock_uom=request.uom,
        default_warehouse=request.default_warehouse,
        is_stock_item=request.is_stock_item,
        is_sales_item=True,
        is_purchase_item=True,
        valuation_rate=_to_decimal(request.valuation_rate, "valuation_rate"),
        standard_rate=_to_decimal(request.standard_selling_rate, "standard_selling_rate"),
        disabled=request.status == "inactive",
        last_synced_at=datetime.utcnow(),
        origin_system="local",
        write_back_status="pending",
        created_by_id=principal.id,
        updated_by_id=principal.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    logger.info("inventory_item_created", item_id=item.id, item_code=item.item_code, principal_id=principal.id, principal_type=principal.type)

    return {
        "id": item.id,
        "item_code": item.item_code,
        "item_name": item.item_name,
        "item_group": item.item_group,
        "stock_uom": item.stock_uom,
        "valuation_rate": float(item.valuation_rate or 0),
        "standard_rate": float(item.standard_rate or 0),
        "is_stock_item": item.is_stock_item,
        "status": "inactive" if item.disabled else "active",
    }


@router.patch("/items/{item_id}", dependencies=[Depends(Require("inventory:write"))])
async def update_item(
    item_id: int,
    request: ItemUpdateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a local inventory item."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if request.item_name is not None:
        item.item_name = request.item_name
    if request.description is not None:
        item.description = request.description
    if request.item_group is not None:
        item.item_group = request.item_group
    if request.uom is not None:
        item.stock_uom = request.uom
    if request.default_warehouse is not None:
        item.default_warehouse = request.default_warehouse
    if request.valuation_rate is not None:
        item.valuation_rate = _to_decimal(request.valuation_rate, "valuation_rate")
    if request.standard_selling_rate is not None:
        item.standard_rate = _to_decimal(request.standard_selling_rate, "standard_selling_rate")
    if request.is_stock_item is not None:
        item.is_stock_item = request.is_stock_item
    if request.status is not None:
        item.disabled = request.status == "inactive"

    db.commit()
    db.refresh(item)

    logger.info("inventory_item_updated", item_id=item.id, item_code=item.item_code, principal_id=principal.id, principal_type=principal.type)

    return {
        "id": item.id,
        "item_code": item.item_code,
        "item_name": item.item_name,
        "item_group": item.item_group,
        "stock_uom": item.stock_uom,
        "valuation_rate": float(item.valuation_rate or 0),
        "standard_rate": float(item.standard_rate or 0),
        "is_stock_item": item.is_stock_item,
        "status": "inactive" if item.disabled else "active",
    }


@router.delete("/items/{item_id}", dependencies=[Depends(Require("inventory:write"))])
async def delete_item(
    item_id: int,
    soft: bool = Query(default=True, description="Soft delete by disabling the item"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete or disable an item. Hard delete only allowed for local (erpnext_id is null)."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if soft or item.erpnext_id:
        item.disabled = True
        db.commit()
        logger.info("inventory_item_disabled", item_id=item.id, item_code=item.item_code, principal_id=principal.id, principal_type=principal.type)
        return {"status": "disabled", "item_id": item_id}

    db.delete(item)
    db.commit()
    logger.info("inventory_item_deleted", item_id=item_id, principal_id=principal.id, principal_type=principal.type)
    return {"status": "deleted", "item_id": item_id}


@router.post("/warehouses", dependencies=[Depends(Require("inventory:write"))])
async def create_warehouse(
    request: WarehouseCreateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a local warehouse (group or leaf)."""
    existing = db.query(Warehouse).filter(Warehouse.warehouse_name == request.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Warehouse already exists")

    wh = Warehouse(
        warehouse_name=request.name,
        parent_warehouse=request.parent_warehouse,
        company=request.company,
        is_group=request.is_group,
        disabled=request.status == "inactive",
        last_synced_at=datetime.utcnow(),
        origin_system="local",
        write_back_status="pending",
        created_by_id=principal.id,
        updated_by_id=principal.id,
    )
    db.add(wh)
    db.commit()
    db.refresh(wh)

    logger.info("inventory_warehouse_created", warehouse_id=wh.id, warehouse_name=wh.warehouse_name, principal_id=principal.id, principal_type=principal.type)

    return {
        "id": wh.id,
        "warehouse_name": wh.warehouse_name,
        "parent_warehouse": wh.parent_warehouse,
        "company": wh.company,
        "is_group": wh.is_group,
        "status": "inactive" if wh.disabled else "active",
    }


@router.patch("/warehouses/{warehouse_id}", dependencies=[Depends(Require("inventory:write"))])
async def update_warehouse(
    warehouse_id: int,
    request: WarehouseUpdateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a warehouse."""
    wh = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
    if not wh:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    if request.name is not None:
        wh.warehouse_name = request.name
    if request.parent_warehouse is not None:
        wh.parent_warehouse = request.parent_warehouse
    if request.company is not None:
        wh.company = request.company
    if request.is_group is not None:
        wh.is_group = request.is_group
    if request.status is not None:
        wh.disabled = request.status == "inactive"

    wh.updated_by_id = principal.id
    wh.write_back_status = "pending"

    db.commit()
    db.refresh(wh)

    logger.info("inventory_warehouse_updated", warehouse_id=wh.id, warehouse_name=wh.warehouse_name, principal_id=principal.id, principal_type=principal.type)

    return {
        "id": wh.id,
        "warehouse_name": wh.warehouse_name,
        "parent_warehouse": wh.parent_warehouse,
        "company": wh.company,
        "is_group": wh.is_group,
        "status": "inactive" if wh.disabled else "active",
    }


@router.delete("/warehouses/{warehouse_id}", dependencies=[Depends(Require("inventory:write"))])
async def delete_warehouse(
    warehouse_id: int,
    soft: bool = Query(default=True, description="Soft delete by disabling the warehouse"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete or disable a warehouse. Hard delete only allowed for local rows."""
    wh = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
    if not wh:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    if soft or wh.erpnext_id:
        wh.disabled = True
        wh.is_deleted = True
        wh.deleted_at = datetime.utcnow()
        wh.deleted_by_id = principal.id
        wh.write_back_status = "pending"
        db.commit()
        logger.info("inventory_warehouse_disabled", warehouse_id=wh.id, warehouse_name=wh.warehouse_name, principal_id=principal.id, principal_type=principal.type)
        return {"status": "disabled", "warehouse_id": warehouse_id}

    db.delete(wh)
    db.commit()
    logger.info("inventory_warehouse_deleted", warehouse_id=warehouse_id, principal_id=principal.id, principal_type=principal.type)
    return {"status": "deleted", "warehouse_id": warehouse_id}


@router.post("/stock-entries", dependencies=[Depends(Require("inventory:write"))])
async def create_stock_entry(
    request: StockEntryCreateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a local stock entry with line items."""
    posting_date = _parse_date(request.posting_date, "posting_date")
    entry_type = _validate_stock_entry_request(request.entry_type, request.lines)

    entry = StockEntry(
        stock_entry_type=entry_type,
        posting_date=posting_date,
        company=request.company,
        remarks=request.remarks,
        docstatus=0,
        from_warehouse=None,
        to_warehouse=None,
        last_synced_at=datetime.utcnow(),
        origin_system="local",
        write_back_status="pending",
        created_by_id=principal.id,
    )
    db.add(entry)
    db.flush()

    total_incoming = Decimal("0")
    total_outgoing = Decimal("0")
    total_amount = Decimal("0")

    for idx, line in enumerate(request.lines, start=1):
        qty = _to_decimal(line.qty, "qty")
        rate = _to_decimal(line.rate, "rate")
        amount = qty * rate
        detail = StockEntryDetail(
            stock_entry_id=entry.id,
            item_code=line.item_code,
            item_name=None,
            description=None,
            uom=line.uom,
            qty=qty,
            transfer_qty=qty,
            s_warehouse=line.s_warehouse,
            t_warehouse=line.t_warehouse,
            basic_rate=rate,
            basic_amount=amount,
            valuation_rate=rate,
            amount=amount,
            serial_no=",".join(line.serial_nos) if line.serial_nos else None,
            idx=idx,
        )
        db.add(detail)
        entry_key = entry_type.lower()
        if entry_key.startswith("material receipt"):
            total_incoming += amount
        elif entry_key.startswith("material issue"):
            total_outgoing += amount
        total_amount += amount

    entry.total_incoming_value = total_incoming
    entry.total_outgoing_value = total_outgoing
    entry.total_amount = total_amount
    entry.updated_by_id = principal.id
    entry.write_back_status = "pending"

    db.commit()
    db.refresh(entry)

    logger.info(
        "inventory_stock_entry_created",
        entry_id=entry.id,
        entry_type=entry.stock_entry_type,
        line_count=len(entry.items),
        principal_id=principal.id,
        principal_type=principal.type,
    )

    return {
        "id": entry.id,
        "stock_entry_type": entry.stock_entry_type,
        "posting_date": entry.posting_date.isoformat() if entry.posting_date else None,
        "company": entry.company,
        "remarks": entry.remarks,
        "total_amount": float(entry.total_amount or 0),
        "lines": [
            {
                "item_code": line.item_code,
                "qty": float(line.qty or 0),
                "uom": line.uom,
                "s_warehouse": line.s_warehouse,
                "t_warehouse": line.t_warehouse,
                "rate": float(line.basic_rate or 0),
                "amount": float(line.amount or 0),
                "serial_nos": (line.serial_no.split(",") if line.serial_no else []),
            }
            for line in sorted(entry.items, key=lambda x: x.idx)
        ],
    }


@router.patch("/stock-entries/{entry_id}", dependencies=[Depends(Require("inventory:write"))])
async def update_stock_entry(
    entry_id: int,
    request: StockEntryUpdateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update remarks/posting date or cancel a stock entry (local only)."""
    entry = (
        db.query(StockEntry)
        .options(joinedload(StockEntry.items))
        .filter(StockEntry.id == entry_id, StockEntry.is_deleted == False)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Stock entry not found")

    if request.posting_date is not None:
        parsed_date = _parse_date(request.posting_date, "posting_date")
        entry.posting_date = datetime.combine(parsed_date, datetime.min.time()) if parsed_date else None
    if request.remarks is not None:
        entry.remarks = request.remarks
    if request.docstatus is not None:
        if entry.docstatus == 2 and request.docstatus != 2:
            raise HTTPException(status_code=400, detail="Cannot change a cancelled entry")
        entry.docstatus = request.docstatus
        if request.docstatus == 2:
            entry.is_deleted = True
            entry.deleted_at = datetime.utcnow()
            entry.deleted_by_id = principal.id

    entry.updated_by_id = principal.id
    entry.write_back_status = "pending"
    db.commit()
    db.refresh(entry)

    return {
        "id": entry.id,
        "docstatus": entry.docstatus,
        "is_deleted": entry.is_deleted,
        "posting_date": entry.posting_date.isoformat() if entry.posting_date else None,
        "remarks": entry.remarks,
    }


@router.delete("/stock-entries/{entry_id}", dependencies=[Depends(Require("inventory:write"))])
async def delete_stock_entry(
    entry_id: int,
    soft: bool = Query(default=True, description="Soft delete by marking cancelled"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete or cancel a stock entry."""
    entry = db.query(StockEntry).filter(StockEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Stock entry not found")

    if soft or entry.erpnext_id:
        entry.is_deleted = True
        entry.docstatus = 2
        entry.deleted_at = datetime.utcnow()
        entry.deleted_by_id = principal.id
        entry.write_back_status = "pending"
        db.commit()
        return {"status": "cancelled", "entry_id": entry_id}

    db.delete(entry)
    db.commit()
    return {"status": "deleted", "entry_id": entry_id}


# ============= WAREHOUSES =============

@router.get("/warehouses", dependencies=[Depends(Require("inventory:read"))])
async def list_warehouses(
    include_disabled: bool = False,
    is_group: Optional[bool] = None,
    company: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List all warehouses.

    Returns hierarchical warehouse structure with stock summary.
    """
    query = db.query(Warehouse).filter(Warehouse.is_deleted == False)

    if not include_disabled:
        query = query.filter(Warehouse.disabled == False)

    if is_group is not None:
        query = query.filter(Warehouse.is_group == is_group)

    if company:
        query = query.filter(Warehouse.company == company)

    total = query.count()
    warehouses = query.order_by(Warehouse.lft, Warehouse.warehouse_name).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "warehouses": [
            {
                "id": wh.id,
                "erpnext_id": wh.erpnext_id,
                "warehouse_name": wh.warehouse_name,
                "parent_warehouse": wh.parent_warehouse,
                "company": wh.company,
                "warehouse_type": wh.warehouse_type,
                "is_group": wh.is_group,
                "disabled": wh.disabled,
                "account": wh.account,
            }
            for wh in warehouses
        ],
    }


@router.get("/warehouses/{warehouse_id}", dependencies=[Depends(Require("inventory:read"))])
async def get_warehouse(
    warehouse_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get warehouse detail with current stock levels."""
    warehouse = (
        db.query(Warehouse)
        .filter(Warehouse.id == warehouse_id, Warehouse.is_deleted == False)
        .first()
    )
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    # Get current stock levels for this warehouse
    stock_summary = db.query(
        StockLedgerEntry.item_code,
        func.sum(StockLedgerEntry.actual_qty).label("total_qty"),
        func.max(StockLedgerEntry.valuation_rate).label("valuation_rate"),
    ).filter(
        StockLedgerEntry.warehouse == warehouse.erpnext_id,
        StockLedgerEntry.is_cancelled == False,
    ).group_by(StockLedgerEntry.item_code).all()

    items_in_stock = [
        {
            "item_code": row.item_code,
            "quantity": float(row.total_qty or 0),
            "valuation_rate": float(row.valuation_rate or 0),
            "stock_value": float((row.total_qty or 0) * (row.valuation_rate or 0)),
        }
        for row in stock_summary
        if row.total_qty and float(row.total_qty) != 0
    ]

    return {
        "id": warehouse.id,
        "erpnext_id": warehouse.erpnext_id,
        "warehouse_name": warehouse.warehouse_name,
        "parent_warehouse": warehouse.parent_warehouse,
        "company": warehouse.company,
        "warehouse_type": warehouse.warehouse_type,
        "is_group": warehouse.is_group,
        "disabled": warehouse.disabled,
        "account": warehouse.account,
        "last_synced_at": warehouse.last_synced_at.isoformat() if warehouse.last_synced_at else None,
        "items_in_stock": items_in_stock,
        "total_stock_value": sum(item["stock_value"] for item in items_in_stock),
    }


# ============= ITEMS (STOCK VIEW) =============

@router.get("/items", dependencies=[Depends(Require("inventory:read"))])
async def list_items_with_stock(
    item_group: Optional[str] = None,
    warehouse: Optional[str] = None,
    has_stock: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List items with their stock levels.

    Combines Item master data with Stock Ledger balances.
    """
    query = db.query(Item).filter(Item.disabled == False)

    if item_group:
        query = query.filter(Item.item_group == item_group)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Item.item_code.ilike(search_term)) | (Item.item_name.ilike(search_term))
        )

    total = query.count()
    items = query.order_by(Item.item_code).offset(offset).limit(limit).all()

    # Get stock levels for these items
    item_codes = [item.item_code for item in items if item.item_code]

    stock_query = db.query(
        StockLedgerEntry.item_code,
        StockLedgerEntry.warehouse,
        func.sum(StockLedgerEntry.actual_qty).label("qty"),
        func.max(StockLedgerEntry.valuation_rate).label("valuation_rate"),
    ).filter(
        StockLedgerEntry.item_code.in_(item_codes),
        StockLedgerEntry.is_cancelled == False,
    )

    if warehouse:
        stock_query = stock_query.filter(StockLedgerEntry.warehouse == warehouse)

    stock_query = stock_query.group_by(StockLedgerEntry.item_code, StockLedgerEntry.warehouse)
    stock_data = stock_query.all()

    # Build stock map: item_code -> warehouse -> qty
    stock_map: Dict[str, Dict[str, float]] = {}
    for row in stock_data:
        if row.item_code not in stock_map:
            stock_map[row.item_code] = {}
        stock_map[row.item_code][row.warehouse] = float(row.qty or 0)

    result_items = []
    for item in items:
        item_stock = stock_map.get(item.item_code, {})
        total_qty = sum(item_stock.values())

        # Filter by has_stock if requested
        if has_stock is True and total_qty <= 0:
            continue
        if has_stock is False and total_qty > 0:
            continue

        result_items.append({
            "id": item.id,
            "item_code": item.item_code,
            "item_name": item.item_name,
            "item_group": item.item_group,
            "stock_uom": item.stock_uom,
            "is_stock_item": item.is_stock_item,
            "valuation_rate": float(item.valuation_rate or 0),
            "total_stock_qty": total_qty,
            "stock_by_warehouse": item_stock if item_stock else None,
        })

    return {
        "total": len(result_items),
        "limit": limit,
        "offset": offset,
        "items": result_items,
    }


@router.get("/items/{item_id}", dependencies=[Depends(Require("inventory:read"))])
async def get_item_stock(
    item_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed stock information for a specific item."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item or item.disabled:
        raise HTTPException(status_code=404, detail="Item not found")

    # Get stock by warehouse
    stock_by_warehouse = db.query(
        StockLedgerEntry.warehouse,
        func.sum(StockLedgerEntry.actual_qty).label("qty"),
        func.max(StockLedgerEntry.valuation_rate).label("valuation_rate"),
        func.max(StockLedgerEntry.posting_date).label("last_transaction"),
    ).filter(
        StockLedgerEntry.item_code == item.item_code,
        StockLedgerEntry.is_cancelled == False,
    ).group_by(StockLedgerEntry.warehouse).all()

    # Get recent transactions
    recent_transactions = db.query(StockLedgerEntry).filter(
        StockLedgerEntry.item_code == item.item_code,
        StockLedgerEntry.is_cancelled == False,
    ).order_by(desc(StockLedgerEntry.posting_date)).limit(20).all()

    warehouses = [
        {
            "warehouse": row.warehouse,
            "quantity": float(row.qty or 0),
            "valuation_rate": float(row.valuation_rate or 0),
            "stock_value": float((row.qty or 0) * (row.valuation_rate or 0)),
            "last_transaction": row.last_transaction.isoformat() if row.last_transaction else None,
        }
        for row in stock_by_warehouse
        if row.qty and float(row.qty) != 0
    ]

    return {
        "id": item.id,
        "item_code": item.item_code,
        "item_name": item.item_name,
        "item_group": item.item_group,
        "stock_uom": item.stock_uom,
        "valuation_rate": float(item.valuation_rate or 0),
        "is_stock_item": item.is_stock_item,
        "total_stock_qty": sum(w["quantity"] for w in warehouses),
        "total_stock_value": sum(w["stock_value"] for w in warehouses),
        "stock_by_warehouse": warehouses,
        "recent_transactions": [
            {
                "posting_date": txn.posting_date.isoformat() if txn.posting_date else None,
                "warehouse": txn.warehouse,
                "actual_qty": float(txn.actual_qty or 0),
                "qty_after_transaction": float(txn.qty_after_transaction or 0),
                "voucher_type": txn.voucher_type,
                "voucher_no": txn.voucher_no,
            }
            for txn in recent_transactions
        ],
    }


# ============= STOCK ENTRIES =============

@router.get("/stock-entries", dependencies=[Depends(Require("inventory:read"))])
async def list_stock_entries(
    stock_entry_type: Optional[str] = None,
    from_warehouse: Optional[str] = None,
    to_warehouse: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    docstatus: Optional[int] = Query(default=None, ge=0, le=2),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List stock entries (inventory transactions).

    Stock entry types include:
    - Material Issue
    - Material Receipt
    - Material Transfer
    - Manufacture
    - Repack
    """
    query = db.query(StockEntry).filter(StockEntry.is_deleted == False)

    if stock_entry_type:
        query = query.filter(StockEntry.stock_entry_type == stock_entry_type)

    if from_warehouse:
        query = query.filter(StockEntry.from_warehouse == from_warehouse)

    if to_warehouse:
        query = query.filter(StockEntry.to_warehouse == to_warehouse)

    if docstatus is not None:
        query = query.filter(StockEntry.docstatus == docstatus)

    start_dt = _parse_date(start_date, "start_date")
    end_dt = _parse_date(end_date, "end_date")

    if start_dt:
        query = query.filter(StockEntry.posting_date >= start_dt)
    if end_dt:
        query = query.filter(StockEntry.posting_date <= end_dt)

    total = query.count()
    entries = query.order_by(desc(StockEntry.posting_date)).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "entries": [
            {
                "id": entry.id,
                "erpnext_id": entry.erpnext_id,
                "stock_entry_type": entry.stock_entry_type,
                "purpose": entry.purpose,
                "posting_date": entry.posting_date.isoformat() if entry.posting_date else None,
                "from_warehouse": entry.from_warehouse,
                "to_warehouse": entry.to_warehouse,
                "total_amount": float(entry.total_amount or 0),
                "docstatus": entry.docstatus,
                "work_order": entry.work_order,
                "purchase_order": entry.purchase_order,
                "sales_order": entry.sales_order,
            }
            for entry in entries
        ],
    }


@router.get("/stock-entries/{entry_id}", dependencies=[Depends(Require("inventory:read"))])
async def get_stock_entry(
    entry_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get stock entry detail with line items."""
    entry = db.query(StockEntry).options(
        joinedload(StockEntry.items)
    ).filter(StockEntry.id == entry_id, StockEntry.is_deleted == False).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Stock entry not found")

    return {
        "id": entry.id,
        "erpnext_id": entry.erpnext_id,
        "stock_entry_type": entry.stock_entry_type,
        "purpose": entry.purpose,
        "posting_date": entry.posting_date.isoformat() if entry.posting_date else None,
        "posting_time": entry.posting_time,
        "from_warehouse": entry.from_warehouse,
        "to_warehouse": entry.to_warehouse,
        "company": entry.company,
        "total_incoming_value": float(entry.total_incoming_value or 0),
        "total_outgoing_value": float(entry.total_outgoing_value or 0),
        "value_difference": float(entry.value_difference or 0),
        "total_amount": float(entry.total_amount or 0),
        "docstatus": entry.docstatus,
        "is_opening": entry.is_opening,
        "is_return": entry.is_return,
        "remarks": entry.remarks,
        "work_order": entry.work_order,
        "purchase_order": entry.purchase_order,
        "sales_order": entry.sales_order,
        "delivery_note": entry.delivery_note,
        "purchase_receipt": entry.purchase_receipt,
        "last_synced_at": entry.last_synced_at.isoformat() if entry.last_synced_at else None,
        "items": [
            {
                "id": item.id,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "description": item.description,
                "uom": item.uom,
                "qty": float(item.qty or 0),
                "s_warehouse": item.s_warehouse,
                "t_warehouse": item.t_warehouse,
                "basic_rate": float(item.basic_rate or 0),
                "basic_amount": float(item.basic_amount or 0),
                "valuation_rate": float(item.valuation_rate or 0),
                "amount": float(item.amount or 0),
                "batch_no": item.batch_no,
                "serial_no": item.serial_no,
            }
            for item in sorted(entry.items, key=lambda x: x.idx)
        ],
    }


# ============= STOCK LEDGER =============

@router.get("/stock-ledger", dependencies=[Depends(Require("inventory:read"))])
async def list_stock_ledger_entries(
    item_code: Optional[str] = None,
    warehouse: Optional[str] = None,
    voucher_type: Optional[str] = None,
    voucher_no: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    include_cancelled: bool = False,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List stock ledger entries (inventory movement audit trail).

    This is the detailed record of every inventory movement.
    """
    query = db.query(StockLedgerEntry)

    if not include_cancelled:
        query = query.filter(StockLedgerEntry.is_cancelled == False)

    if item_code:
        query = query.filter(StockLedgerEntry.item_code == item_code)

    if warehouse:
        query = query.filter(StockLedgerEntry.warehouse == warehouse)

    if voucher_type:
        query = query.filter(StockLedgerEntry.voucher_type == voucher_type)

    if voucher_no:
        query = query.filter(StockLedgerEntry.voucher_no == voucher_no)

    start_dt = _parse_date(start_date, "start_date")
    end_dt = _parse_date(end_date, "end_date")

    if start_dt:
        query = query.filter(StockLedgerEntry.posting_date >= start_dt)
    if end_dt:
        query = query.filter(StockLedgerEntry.posting_date <= end_dt)

    total = query.count()
    entries = query.order_by(
        desc(StockLedgerEntry.posting_date),
        desc(StockLedgerEntry.id)
    ).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "entries": [
            {
                "id": sle.id,
                "erpnext_id": sle.erpnext_id,
                "item_code": sle.item_code,
                "warehouse": sle.warehouse,
                "posting_date": sle.posting_date.isoformat() if sle.posting_date else None,
                "posting_time": sle.posting_time,
                "actual_qty": float(sle.actual_qty or 0),
                "qty_after_transaction": float(sle.qty_after_transaction or 0),
                "incoming_rate": float(sle.incoming_rate or 0),
                "outgoing_rate": float(sle.outgoing_rate or 0),
                "valuation_rate": float(sle.valuation_rate or 0),
                "stock_value": float(sle.stock_value or 0),
                "stock_value_difference": float(sle.stock_value_difference or 0),
                "voucher_type": sle.voucher_type,
                "voucher_no": sle.voucher_no,
                "batch_no": sle.batch_no,
            }
            for sle in entries
        ],
    }


# ============= STOCK SUMMARY =============

@router.get("/summary", dependencies=[Depends(Require("inventory:read"))])
async def get_stock_summary(
    warehouse: Optional[str] = None,
    item_group: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get stock summary by item and warehouse.

    Returns aggregated stock levels for reporting.
    """
    # Get current stock levels grouped by item
    query = db.query(
        StockLedgerEntry.item_code,
        StockLedgerEntry.warehouse,
        func.sum(StockLedgerEntry.actual_qty).label("qty"),
        func.max(StockLedgerEntry.valuation_rate).label("valuation_rate"),
    ).filter(
        StockLedgerEntry.is_cancelled == False,
    )

    if warehouse:
        query = query.filter(StockLedgerEntry.warehouse == warehouse)

    query = query.group_by(StockLedgerEntry.item_code, StockLedgerEntry.warehouse)
    stock_data = query.all()

    # Get item details
    item_codes = list(set(row.item_code for row in stock_data if row.item_code))
    items_query = db.query(Item).filter(Item.item_code.in_(item_codes))

    if item_group:
        items_query = items_query.filter(Item.item_group == item_group)

    items = {item.item_code: item for item in items_query.all()}

    # Build summary
    summary_by_item: Dict[str, Dict[str, Any]] = {}
    for row in stock_data:
        if row.item_code not in items:
            continue

        item = items[row.item_code]
        if row.item_code not in summary_by_item:
            summary_by_item[row.item_code] = {
                "item_code": row.item_code,
                "item_name": item.item_name,
                "item_group": item.item_group,
                "stock_uom": item.stock_uom,
                "total_qty": 0,
                "total_value": 0,
                "warehouses": [],
            }

        qty = float(row.qty or 0)
        value = qty * float(row.valuation_rate or 0)

        if qty != 0:
            summary_by_item[row.item_code]["total_qty"] += qty
            summary_by_item[row.item_code]["total_value"] += value
            summary_by_item[row.item_code]["warehouses"].append({
                "warehouse": row.warehouse,
                "qty": qty,
                "valuation_rate": float(row.valuation_rate or 0),
                "value": value,
            })

    # Filter out items with zero stock
    summary_list = [s for s in summary_by_item.values() if s["total_qty"] != 0]

    # Calculate totals
    total_items = len(summary_list)
    total_qty = sum(s["total_qty"] for s in summary_list)
    total_value = sum(s["total_value"] for s in summary_list)

    return {
        "total_items": total_items,
        "total_qty": total_qty,
        "total_value": total_value,
        "items": sorted(summary_list, key=lambda x: x["item_code"]),
    }


# ============= INVENTORY VALUATION =============

@router.get("/valuation-report", dependencies=[Depends(Require("inventory:read"))])
async def get_inventory_valuation_report(
    as_of_date: Optional[str] = Query(None, description="Valuation as of date (YYYY-MM-DD)"),
    warehouse: Optional[str] = Query(None, description="Filter by warehouse"),
    item_group: Optional[str] = Query(None, description="Filter by item group"),
    valuation_method: str = Query("fifo", description="Valuation method: fifo, lifo, or weighted_average"),
    include_zero_stock: bool = Query(False, description="Include items with zero stock"),
    currency: Optional[str] = Query(None, description="Currency for valuation"),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get comprehensive inventory valuation report.

    Supports multiple valuation methods:
    - FIFO (First In First Out)
    - LIFO (Last In First Out)
    - Weighted Average

    Returns detailed valuation per item and warehouse with cost analysis.
    """
    as_of = _parse_date(as_of_date, "as_of_date") or date.today()

    # Build base query for stock as of date
    sle_query = db.query(
        StockLedgerEntry.item_code,
        StockLedgerEntry.warehouse,
        func.sum(StockLedgerEntry.actual_qty).label("qty"),
        func.sum(StockLedgerEntry.stock_value_difference).label("total_value"),
    ).filter(
        StockLedgerEntry.is_cancelled == False,
        StockLedgerEntry.posting_date <= as_of,
    )

    if warehouse:
        sle_query = sle_query.filter(StockLedgerEntry.warehouse == warehouse)

    sle_query = sle_query.group_by(
        StockLedgerEntry.item_code,
        StockLedgerEntry.warehouse,
    )

    stock_data = sle_query.all()

    # Get item master data
    item_codes = list(set(row.item_code for row in stock_data if row.item_code))
    items_query = db.query(Item).filter(Item.item_code.in_(item_codes))

    if item_group:
        items_query = items_query.filter(Item.item_group == item_group)

    items_map = {item.item_code: item for item in items_query.all()}

    # Calculate valuation for each item/warehouse combination
    valuation_data = []
    total_qty = Decimal("0")
    total_value = Decimal("0")

    for row in stock_data:
        if row.item_code not in items_map:
            continue

        item = items_map[row.item_code]
        qty = Decimal(str(row.qty or 0))

        if not include_zero_stock and qty <= 0:
            continue

        # Get valuation rate based on method
        if valuation_method == "fifo":
            # For FIFO, use earliest incoming rates still in stock
            val_rate = _calculate_fifo_rate(db, row.item_code, row.warehouse, as_of, qty)
        elif valuation_method == "lifo":
            # For LIFO, use latest incoming rates
            val_rate = _calculate_lifo_rate(db, row.item_code, row.warehouse, as_of, qty)
        else:
            # Weighted average - use current valuation rate
            latest_sle = db.query(StockLedgerEntry).filter(
                StockLedgerEntry.item_code == row.item_code,
                StockLedgerEntry.warehouse == row.warehouse,
                StockLedgerEntry.is_cancelled == False,
                StockLedgerEntry.posting_date <= as_of,
            ).order_by(desc(StockLedgerEntry.posting_date), desc(StockLedgerEntry.id)).first()
            val_rate = Decimal(str(latest_sle.valuation_rate or 0)) if latest_sle else Decimal("0")

        stock_value = qty * val_rate

        valuation_data.append({
            "item_code": row.item_code,
            "item_name": item.item_name,
            "item_group": item.item_group,
            "warehouse": row.warehouse,
            "quantity": float(qty),
            "uom": item.stock_uom,
            "valuation_rate": float(val_rate),
            "stock_value": float(stock_value),
            "standard_rate": float(item.standard_rate or 0),
            "last_purchase_rate": float(item.last_purchase_rate or 0) if hasattr(item, 'last_purchase_rate') else None,
        })

        total_qty += qty
        total_value += stock_value

    # Sort by value descending
    valuation_data.sort(key=lambda x: x["stock_value"], reverse=True)

    # Apply pagination
    paginated = valuation_data[offset:offset + limit]

    # Group by item group for summary
    by_group: Dict[str, Dict[str, Any]] = {}
    for item_data in valuation_data:
        group = item_data["item_group"] or "Uncategorized"
        if group not in by_group:
            by_group[group] = {"total_qty": 0, "total_value": 0, "item_count": 0}
        by_group[group]["total_qty"] += item_data["quantity"]
        by_group[group]["total_value"] += item_data["stock_value"]
        by_group[group]["item_count"] += 1

    return {
        "as_of_date": as_of.isoformat(),
        "valuation_method": valuation_method,
        "warehouse_filter": warehouse,
        "item_group_filter": item_group,
        "summary": {
            "total_items": len(valuation_data),
            "total_quantity": float(total_qty),
            "total_value": float(total_value),
            "by_item_group": [
                {
                    "item_group": group,
                    "item_count": data["item_count"],
                    "total_qty": data["total_qty"],
                    "total_value": data["total_value"],
                    "percent_of_total": round(data["total_value"] / float(total_value) * 100, 2) if total_value > 0 else 0,
                }
                for group, data in sorted(by_group.items(), key=lambda x: x[1]["total_value"], reverse=True)
            ],
        },
        "total": len(valuation_data),
        "offset": offset,
        "limit": limit,
        "items": paginated,
    }


def _calculate_fifo_rate(db: Session, item_code: str, warehouse: str, as_of: date, qty_needed: Decimal) -> Decimal:
    """Calculate FIFO valuation rate by taking earliest receipts first."""
    # Get all incoming transactions (positive actual_qty) in chronological order
    receipts = db.query(StockLedgerEntry).filter(
        StockLedgerEntry.item_code == item_code,
        StockLedgerEntry.warehouse == warehouse,
        StockLedgerEntry.is_cancelled == False,
        StockLedgerEntry.posting_date <= as_of,
        StockLedgerEntry.actual_qty > 0,
    ).order_by(StockLedgerEntry.posting_date.asc(), StockLedgerEntry.id.asc()).all()

    # Get total consumed qty
    total_consumed = db.query(func.sum(StockLedgerEntry.actual_qty)).filter(
        StockLedgerEntry.item_code == item_code,
        StockLedgerEntry.warehouse == warehouse,
        StockLedgerEntry.is_cancelled == False,
        StockLedgerEntry.posting_date <= as_of,
        StockLedgerEntry.actual_qty < 0,
    ).scalar() or Decimal("0")
    total_consumed = abs(Decimal(str(total_consumed)))

    # FIFO: consume from earliest receipts
    remaining_consumed = total_consumed
    fifo_layers = []

    for receipt in receipts:
        receipt_qty = Decimal(str(receipt.actual_qty))
        if remaining_consumed >= receipt_qty:
            # This entire receipt is consumed
            remaining_consumed -= receipt_qty
        else:
            # Part or all of this receipt remains
            remaining_qty = receipt_qty - remaining_consumed
            remaining_consumed = Decimal("0")
            fifo_layers.append({
                "qty": remaining_qty,
                "rate": Decimal(str(receipt.incoming_rate or receipt.valuation_rate or 0)),
            })

    # Calculate weighted average of remaining layers for qty_needed
    if not fifo_layers:
        return Decimal("0")

    total_value = Decimal("0")
    qty_allocated = Decimal("0")

    for layer in fifo_layers:
        take_qty = min(layer["qty"], qty_needed - qty_allocated)
        total_value += take_qty * layer["rate"]
        qty_allocated += take_qty
        if qty_allocated >= qty_needed:
            break

    return total_value / qty_allocated if qty_allocated > 0 else Decimal("0")


def _calculate_lifo_rate(db: Session, item_code: str, warehouse: str, as_of: date, qty_needed: Decimal) -> Decimal:
    """Calculate LIFO valuation rate by taking latest receipts first."""
    # Get all incoming transactions in reverse chronological order
    receipts = db.query(StockLedgerEntry).filter(
        StockLedgerEntry.item_code == item_code,
        StockLedgerEntry.warehouse == warehouse,
        StockLedgerEntry.is_cancelled == False,
        StockLedgerEntry.posting_date <= as_of,
        StockLedgerEntry.actual_qty > 0,
    ).order_by(StockLedgerEntry.posting_date.desc(), StockLedgerEntry.id.desc()).all()

    # For LIFO, take from latest receipts
    total_value = Decimal("0")
    qty_allocated = Decimal("0")

    for receipt in receipts:
        receipt_qty = Decimal(str(receipt.actual_qty))
        take_qty = min(receipt_qty, qty_needed - qty_allocated)
        rate = Decimal(str(receipt.incoming_rate or receipt.valuation_rate or 0))
        total_value += take_qty * rate
        qty_allocated += take_qty
        if qty_allocated >= qty_needed:
            break

    return total_value / qty_allocated if qty_allocated > 0 else Decimal("0")


@router.get("/valuation-report/{item_code}", dependencies=[Depends(Require("inventory:read"))])
async def get_item_valuation_detail(
    item_code: str,
    as_of_date: Optional[str] = Query(None, description="Valuation as of date"),
    valuation_method: str = Query("fifo", description="Valuation method"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed valuation for a specific item with cost layer breakdown."""
    as_of = _parse_date(as_of_date, "as_of_date") or date.today()

    item = db.query(Item).filter(Item.item_code == item_code).first()
    if not item or item.disabled:
        raise HTTPException(status_code=404, detail="Item not found")

    # Get stock by warehouse
    stock_by_warehouse = db.query(
        StockLedgerEntry.warehouse,
        func.sum(StockLedgerEntry.actual_qty).label("qty"),
    ).filter(
        StockLedgerEntry.item_code == item_code,
        StockLedgerEntry.is_cancelled == False,
        StockLedgerEntry.posting_date <= as_of,
    ).group_by(StockLedgerEntry.warehouse).all()

    warehouses_data = []
    total_qty = Decimal("0")
    total_value = Decimal("0")

    for wh_row in stock_by_warehouse:
        qty = Decimal(str(wh_row.qty or 0))
        if qty <= 0:
            continue

        # Calculate valuation rate
        if valuation_method == "fifo":
            val_rate = _calculate_fifo_rate(db, item_code, wh_row.warehouse, as_of, qty)
        elif valuation_method == "lifo":
            val_rate = _calculate_lifo_rate(db, item_code, wh_row.warehouse, as_of, qty)
        else:
            latest_sle = db.query(StockLedgerEntry).filter(
                StockLedgerEntry.item_code == item_code,
                StockLedgerEntry.warehouse == wh_row.warehouse,
                StockLedgerEntry.is_cancelled == False,
                StockLedgerEntry.posting_date <= as_of,
            ).order_by(desc(StockLedgerEntry.posting_date)).first()
            val_rate = Decimal(str(latest_sle.valuation_rate or 0)) if latest_sle else Decimal("0")

        stock_value = qty * val_rate
        total_qty += qty
        total_value += stock_value

        warehouses_data.append({
            "warehouse": wh_row.warehouse,
            "quantity": float(qty),
            "valuation_rate": float(val_rate),
            "stock_value": float(stock_value),
        })

    # Get cost layers (recent receipts)
    cost_layers = db.query(StockLedgerEntry).filter(
        StockLedgerEntry.item_code == item_code,
        StockLedgerEntry.is_cancelled == False,
        StockLedgerEntry.posting_date <= as_of,
        StockLedgerEntry.actual_qty > 0,
    ).order_by(desc(StockLedgerEntry.posting_date)).limit(20).all()

    # Get landed costs if any
    landed_costs = db.query(LandedCostItem).filter(
        LandedCostItem.item_code == item_code,
    ).all()

    total_landed_cost = sum(float(lc.applicable_charges or 0) for lc in landed_costs)

    return {
        "as_of_date": as_of.isoformat(),
        "valuation_method": valuation_method,
        "item": {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "item_group": item.item_group,
            "stock_uom": item.stock_uom,
            "default_warehouse": item.default_warehouse,
        },
        "valuation_summary": {
            "total_quantity": float(total_qty),
            "total_value": float(total_value),
            "average_rate": float(total_value / total_qty) if total_qty > 0 else 0,
            "total_landed_cost": total_landed_cost,
        },
        "by_warehouse": warehouses_data,
        "cost_layers": [
            {
                "posting_date": layer.posting_date.isoformat() if layer.posting_date else None,
                "warehouse": layer.warehouse,
                "quantity": float(layer.actual_qty or 0),
                "incoming_rate": float(layer.incoming_rate or 0),
                "voucher_type": layer.voucher_type,
                "voucher_no": layer.voucher_no,
            }
            for layer in cost_layers
        ],
    }


# ============= LANDED COST =============

class LandedCostItemInput(BaseModel):
    item_code: str
    qty: float
    rate: float
    warehouse: Optional[str] = None


class LandedCostTaxInput(BaseModel):
    expense_account: str
    description: Optional[str] = None
    amount: float


class LandedCostVoucherCreateRequest(BaseModel):
    posting_date: Optional[str] = None
    company: Optional[str] = None
    distribute_charges_based_on: str = Field(default="Qty", pattern="^(Qty|Amount|Manual)$")
    purchase_receipt: Optional[str] = None
    purchase_invoice: Optional[str] = None
    remarks: Optional[str] = None
    items: List[LandedCostItemInput]
    taxes: List[LandedCostTaxInput]


@router.post("/landed-cost-vouchers", dependencies=[Depends(Require("inventory:write"))])
async def create_landed_cost_voucher(
    request: LandedCostVoucherCreateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a landed cost voucher to allocate additional costs to inventory.

    Distributes charges across items based on:
    - Qty: Proportional to quantity
    - Amount: Proportional to item value
    - Manual: Uses pre-specified applicable_charges
    """
    if not request.items:
        raise HTTPException(status_code=400, detail="At least one item is required")
    if not request.taxes:
        raise HTTPException(status_code=400, detail="At least one tax/charge is required")

    posting_date = _parse_date(request.posting_date, "posting_date")
    total_charges = sum(_to_decimal(t.amount, "tax_amount") for t in request.taxes)

    # Create voucher
    voucher = LandedCostVoucher(
        posting_date=posting_date,
        company=request.company,
        distribute_charges_based_on=request.distribute_charges_based_on,
        purchase_receipt=request.purchase_receipt,
        purchase_invoice=request.purchase_invoice,
        total_taxes_and_charges=total_charges,
        remarks=request.remarks,
        docstatus=0,
        created_by_id=principal.id,
        updated_by_id=principal.id,
    )
    db.add(voucher)
    db.flush()

    # Calculate distribution basis
    if request.distribute_charges_based_on == "Qty":
        total_basis = sum(_to_decimal(item.qty, "qty") for item in request.items)
    else:  # Amount
        total_basis = sum(_to_decimal(item.qty, "qty") * _to_decimal(item.rate, "rate") for item in request.items)

    # Add items with allocated charges
    for idx, item_input in enumerate(request.items, start=1):
        qty = _to_decimal(item_input.qty, "qty")
        rate = _to_decimal(item_input.rate, "rate")
        amount = qty * rate

        if request.distribute_charges_based_on == "Qty":
            item_basis = qty
        else:
            item_basis = amount

        # Calculate proportional charges
        if total_basis > 0:
            applicable_charges = (item_basis / total_basis) * total_charges
        else:
            applicable_charges = Decimal("0")

        lc_item = LandedCostItem(
            voucher_id=voucher.id,
            item_code=item_input.item_code,
            qty=qty,
            rate=rate,
            amount=amount,
            applicable_charges=applicable_charges,
            warehouse=item_input.warehouse,
            idx=idx,
        )
        db.add(lc_item)

    # Add taxes
    for idx, tax_input in enumerate(request.taxes, start=1):
        lc_tax = LandedCostTax(
            voucher_id=voucher.id,
            expense_account=tax_input.expense_account,
            description=tax_input.description,
            amount=_to_decimal(tax_input.amount, "amount"),
            idx=idx,
        )
        db.add(lc_tax)

    db.commit()
    db.refresh(voucher)

    logger.info(
        "landed_cost_voucher_created",
        voucher_id=voucher.id,
        total_charges=float(total_charges),
        item_count=len(request.items),
        principal_id=principal.id,
    )

    return {
        "id": voucher.id,
        "posting_date": voucher.posting_date.isoformat() if voucher.posting_date else None,
        "distribute_charges_based_on": voucher.distribute_charges_based_on,
        "total_taxes_and_charges": float(voucher.total_taxes_and_charges),
        "docstatus": voucher.docstatus,
        "items": [
            {
                "item_code": item.item_code,
                "qty": float(item.qty),
                "rate": float(item.rate),
                "amount": float(item.amount),
                "applicable_charges": float(item.applicable_charges),
                "warehouse": item.warehouse,
            }
            for item in sorted(voucher.items, key=lambda x: x.idx)
        ],
        "taxes": [
            {
                "expense_account": tax.expense_account,
                "description": tax.description,
                "amount": float(tax.amount),
            }
            for tax in sorted(voucher.taxes, key=lambda x: x.idx)
        ],
    }


@router.get("/landed-cost-vouchers", dependencies=[Depends(Require("inventory:read"))])
async def list_landed_cost_vouchers(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    purchase_receipt: Optional[str] = None,
    docstatus: Optional[int] = Query(None, ge=0, le=2),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List landed cost vouchers."""
    query = db.query(LandedCostVoucher).filter(LandedCostVoucher.is_deleted == False)

    start_dt = _parse_date(start_date, "start_date")
    end_dt = _parse_date(end_date, "end_date")

    if start_dt:
        query = query.filter(LandedCostVoucher.posting_date >= start_dt)
    if end_dt:
        query = query.filter(LandedCostVoucher.posting_date <= end_dt)

    if purchase_receipt:
        query = query.filter(LandedCostVoucher.purchase_receipt == purchase_receipt)

    if docstatus is not None:
        query = query.filter(LandedCostVoucher.docstatus == docstatus)

    total = query.count()
    vouchers = query.order_by(desc(LandedCostVoucher.posting_date)).offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "vouchers": [
            {
                "id": v.id,
                "posting_date": v.posting_date.isoformat() if v.posting_date else None,
                "company": v.company,
                "distribute_charges_based_on": v.distribute_charges_based_on,
                "purchase_receipt": v.purchase_receipt,
                "purchase_invoice": v.purchase_invoice,
                "total_taxes_and_charges": float(v.total_taxes_and_charges),
                "docstatus": v.docstatus,
                "remarks": v.remarks,
            }
            for v in vouchers
        ],
    }


@router.get("/landed-cost-vouchers/{voucher_id}", dependencies=[Depends(Require("inventory:read"))])
async def get_landed_cost_voucher(
    voucher_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get landed cost voucher detail with items and taxes."""
    voucher = db.query(LandedCostVoucher).options(
        joinedload(LandedCostVoucher.items),
        joinedload(LandedCostVoucher.taxes),
    ).filter(
        LandedCostVoucher.id == voucher_id,
        LandedCostVoucher.is_deleted == False,
    ).first()

    if not voucher:
        raise HTTPException(status_code=404, detail="Landed cost voucher not found")

    return {
        "id": voucher.id,
        "posting_date": voucher.posting_date.isoformat() if voucher.posting_date else None,
        "company": voucher.company,
        "distribute_charges_based_on": voucher.distribute_charges_based_on,
        "purchase_receipt": voucher.purchase_receipt,
        "purchase_invoice": voucher.purchase_invoice,
        "total_taxes_and_charges": float(voucher.total_taxes_and_charges),
        "docstatus": voucher.docstatus,
        "remarks": voucher.remarks,
        "created_at": voucher.created_at.isoformat() if voucher.created_at else None,
        "items": [
            {
                "id": item.id,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": float(item.qty),
                "rate": float(item.rate),
                "amount": float(item.amount),
                "applicable_charges": float(item.applicable_charges),
                "warehouse": item.warehouse,
            }
            for item in sorted(voucher.items, key=lambda x: x.idx)
        ],
        "taxes": [
            {
                "id": tax.id,
                "expense_account": tax.expense_account,
                "description": tax.description,
                "amount": float(tax.amount),
            }
            for tax in sorted(voucher.taxes, key=lambda x: x.idx)
        ],
    }


@router.patch("/landed-cost-vouchers/{voucher_id}/submit", dependencies=[Depends(Require("inventory:write"))])
async def submit_landed_cost_voucher(
    voucher_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Submit a landed cost voucher to apply charges to inventory valuation."""
    voucher = db.query(LandedCostVoucher).options(
        joinedload(LandedCostVoucher.items),
    ).filter(
        LandedCostVoucher.id == voucher_id,
        LandedCostVoucher.is_deleted == False,
    ).first()

    if not voucher:
        raise HTTPException(status_code=404, detail="Landed cost voucher not found")

    if voucher.docstatus != 0:
        raise HTTPException(status_code=400, detail="Only draft vouchers can be submitted")

    # In a real implementation, this would create stock ledger entries
    # to adjust the valuation of affected items
    voucher.docstatus = 1
    voucher.updated_by_id = principal.id
    db.commit()

    logger.info(
        "landed_cost_voucher_submitted",
        voucher_id=voucher.id,
        principal_id=principal.id,
    )

    return {
        "id": voucher.id,
        "docstatus": voucher.docstatus,
        "message": "Landed cost voucher submitted successfully",
    }


# ============= STOCK ENTRY GL POSTING =============
@router.post("/stock-entries/{entry_id}/post", dependencies=[Depends(Require("inventory:write"))])
async def post_stock_entry_to_gl(
    entry_id: int,
    inventory_account: Optional[str] = None,
    expense_account: Optional[str] = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Post a stock entry to the General Ledger."""
    from app.services.inventory_posting_service import InventoryPostingService

    entry = db.query(StockEntry).filter(
        StockEntry.id == entry_id,
        StockEntry.is_deleted == False,
    ).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Stock entry not found")

    if entry.docstatus != 1:
        raise HTTPException(status_code=400, detail="Only submitted entries can be posted to GL")

    posting_service = InventoryPostingService(db)
    journal_entry = posting_service.post_stock_entry(
        entry,
        inventory_account=inventory_account,
        expense_account=expense_account,
        user_id=principal.id,
    )
    db.commit()

    logger.info(
        "stock_entry_posted_to_gl",
        entry_id=entry.id,
        journal_entry_id=journal_entry.id if journal_entry else None,
        principal_id=principal.id,
    )

    return {
        "id": entry.id,
        "journal_entry_id": journal_entry.id if journal_entry else None,
        "message": "Stock entry posted to GL" if journal_entry else "No GL entry needed for this type",
    }


# ============= REORDER ALERTS =============
@router.get("/reorder-alerts", dependencies=[Depends(Require("inventory:read"))])
async def get_reorder_alerts(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, le=500),
) -> Dict[str, Any]:
    """Get items below reorder level."""
    # Subquery to get current stock by item
    stock_subquery = (
        db.query(
            StockLedgerEntry.item_code,
            func.sum(StockLedgerEntry.actual_qty).label("total_qty"),
        )
        .filter(StockLedgerEntry.is_cancelled == False)
        .group_by(StockLedgerEntry.item_code)
        .subquery()
    )

    # Find items where stock is below reorder level
    alerts = (
        db.query(
            Item.id,
            Item.item_code,
            Item.item_name,
            Item.item_group,
            Item.stock_uom,
            Item.reorder_level,
            Item.reorder_qty,
            Item.safety_stock,
            func.coalesce(stock_subquery.c.total_qty, Decimal("0")).label("current_stock"),
        )
        .outerjoin(stock_subquery, Item.item_code == stock_subquery.c.item_code)
        .filter(
            Item.is_stock_item == True,
            Item.disabled == False,
            Item.reorder_level > 0,
            func.coalesce(stock_subquery.c.total_qty, Decimal("0")) <= Item.reorder_level,
        )
        .order_by(
            (func.coalesce(stock_subquery.c.total_qty, Decimal("0")) - Item.reorder_level).asc()
        )
        .limit(limit)
        .all()
    )

    return {
        "total": len(alerts),
        "alerts": [
            {
                "id": a.id,
                "item_code": a.item_code,
                "item_name": a.item_name,
                "item_group": a.item_group,
                "stock_uom": a.stock_uom,
                "reorder_level": float(a.reorder_level) if a.reorder_level else 0,
                "reorder_qty": float(a.reorder_qty) if a.reorder_qty else 0,
                "safety_stock": float(a.safety_stock) if a.safety_stock else 0,
                "current_stock": float(a.current_stock) if a.current_stock else 0,
                "shortage": float(a.reorder_level - a.current_stock) if a.reorder_level and a.current_stock else 0,
            }
            for a in alerts
        ],
    }


# ============= TRANSFER REQUESTS =============
class TransferRequestItemInput(BaseModel):
    item_code: str
    item_name: Optional[str] = None
    qty: float
    uom: Optional[str] = None
    valuation_rate: Optional[float] = 0
    batch_no: Optional[str] = None
    serial_no: Optional[str] = None


class TransferRequestCreate(BaseModel):
    from_warehouse: str
    to_warehouse: str
    required_date: Optional[str] = None
    remarks: Optional[str] = None
    items: List[TransferRequestItemInput]


@router.get("/transfers", dependencies=[Depends(Require("inventory:read"))])
async def list_transfer_requests(
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    from_warehouse: Optional[str] = None,
    to_warehouse: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    """List transfer requests."""
    from app.models.inventory import TransferRequest, TransferStatus

    query = db.query(TransferRequest).filter(TransferRequest.is_deleted == False)

    if status:
        try:
            status_enum = TransferStatus(status)
            query = query.filter(TransferRequest.status == status_enum)
        except ValueError:
            pass

    if from_warehouse:
        query = query.filter(TransferRequest.from_warehouse.ilike(f"%{from_warehouse}%"))
    if to_warehouse:
        query = query.filter(TransferRequest.to_warehouse.ilike(f"%{to_warehouse}%"))

    total = query.count()
    transfers = query.order_by(desc(TransferRequest.request_date)).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "transfers": [
            {
                "id": t.id,
                "from_warehouse": t.from_warehouse,
                "to_warehouse": t.to_warehouse,
                "request_date": t.request_date.isoformat() if t.request_date else None,
                "required_date": t.required_date.isoformat() if t.required_date else None,
                "transfer_date": t.transfer_date.isoformat() if t.transfer_date else None,
                "total_qty": float(t.total_qty) if t.total_qty else 0,
                "total_value": float(t.total_value) if t.total_value else 0,
                "status": t.status.value,
                "remarks": t.remarks,
            }
            for t in transfers
        ],
    }


@router.post("/transfers", dependencies=[Depends(Require("inventory:write"))])
async def create_transfer_request(
    data: TransferRequestCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new transfer request."""
    from app.models.inventory import TransferRequest, TransferRequestItem, TransferStatus

    if not data.items:
        raise HTTPException(status_code=400, detail="At least one item is required")

    required_date = _parse_date(data.required_date, "required_date") if data.required_date else None

    total_qty = sum(item.qty for item in data.items)
    total_value = sum(item.qty * (item.valuation_rate or 0) for item in data.items)

    transfer = TransferRequest(
        from_warehouse=data.from_warehouse,
        to_warehouse=data.to_warehouse,
        required_date=required_date,
        total_qty=Decimal(str(total_qty)),
        total_value=Decimal(str(total_value)),
        status=TransferStatus.DRAFT,
        remarks=data.remarks,
        requested_by_id=principal.id,
        created_by_id=principal.id,
    )
    db.add(transfer)
    db.flush()

    for idx, item in enumerate(data.items):
        transfer_item = TransferRequestItem(
            transfer_id=transfer.id,
            item_code=item.item_code,
            item_name=item.item_name,
            qty=Decimal(str(item.qty)),
            uom=item.uom,
            valuation_rate=Decimal(str(item.valuation_rate or 0)),
            amount=Decimal(str(item.qty * (item.valuation_rate or 0))),
            batch_no=item.batch_no,
            serial_no=item.serial_no,
            idx=idx,
        )
        db.add(transfer_item)

    db.commit()

    logger.info("transfer_request_created", transfer_id=transfer.id, principal_id=principal.id)

    return {
        "id": transfer.id,
        "status": transfer.status.value,
        "message": "Transfer request created successfully",
    }


@router.post("/transfers/{transfer_id}/submit", dependencies=[Depends(Require("inventory:write"))])
async def submit_transfer_request(
    transfer_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Submit a transfer request for approval."""
    from app.models.inventory import TransferRequest, TransferStatus

    transfer = db.query(TransferRequest).filter(
        TransferRequest.id == transfer_id,
        TransferRequest.is_deleted == False,
    ).first()

    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer request not found")

    if transfer.status != TransferStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft transfers can be submitted")

    transfer.status = TransferStatus.PENDING_APPROVAL
    transfer.updated_by_id = principal.id
    db.commit()

    return {"id": transfer.id, "status": transfer.status.value, "message": "Transfer submitted for approval"}


@router.post("/transfers/{transfer_id}/approve", dependencies=[Depends(Require("inventory:approve"))])
async def approve_transfer_request(
    transfer_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Approve a transfer request."""
    from app.models.inventory import TransferRequest, TransferStatus

    transfer = db.query(TransferRequest).filter(
        TransferRequest.id == transfer_id,
        TransferRequest.is_deleted == False,
    ).first()

    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer request not found")

    if transfer.status != TransferStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=400, detail="Only pending transfers can be approved")

    transfer.status = TransferStatus.APPROVED
    transfer.approved_by_id = principal.id
    transfer.approved_at = datetime.utcnow()
    transfer.updated_by_id = principal.id
    db.commit()

    return {"id": transfer.id, "status": transfer.status.value, "message": "Transfer approved"}


@router.post("/transfers/{transfer_id}/reject", dependencies=[Depends(Require("inventory:approve"))])
async def reject_transfer_request(
    transfer_id: int,
    reason: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Reject a transfer request."""
    from app.models.inventory import TransferRequest, TransferStatus

    transfer = db.query(TransferRequest).filter(
        TransferRequest.id == transfer_id,
        TransferRequest.is_deleted == False,
    ).first()

    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer request not found")

    if transfer.status != TransferStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=400, detail="Only pending transfers can be rejected")

    transfer.status = TransferStatus.REJECTED
    transfer.rejection_reason = reason
    transfer.updated_by_id = principal.id
    db.commit()

    return {"id": transfer.id, "status": transfer.status.value, "message": "Transfer rejected"}


@router.post("/transfers/{transfer_id}/execute", dependencies=[Depends(Require("inventory:write"))])
async def execute_transfer_request(
    transfer_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Execute an approved transfer request (create stock entries)."""
    from app.models.inventory import TransferRequest, TransferRequestItem, TransferStatus

    transfer = db.query(TransferRequest).options(
        joinedload(TransferRequest.items)
    ).filter(
        TransferRequest.id == transfer_id,
        TransferRequest.is_deleted == False,
    ).first()

    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer request not found")

    if transfer.status != TransferStatus.APPROVED:
        raise HTTPException(status_code=400, detail="Only approved transfers can be executed")

    # Create outbound stock entry (from source warehouse)
    outbound_entry = StockEntry(
        stock_entry_type="Material Transfer",
        posting_date=datetime.utcnow(),
        from_warehouse=transfer.from_warehouse,
        to_warehouse=transfer.to_warehouse,
        total_outgoing_value=transfer.total_value,
        total_incoming_value=transfer.total_value,
        total_amount=transfer.total_value,
        docstatus=1,
        origin_system="local",
        created_by_id=principal.id,
    )
    db.add(outbound_entry)
    db.flush()

    for item in transfer.items:
        detail = StockEntryDetail(
            stock_entry_id=outbound_entry.id,
            item_code=item.item_code,
            item_name=item.item_name,
            qty=item.qty,
            transfer_qty=item.qty,
            s_warehouse=transfer.from_warehouse,
            t_warehouse=transfer.to_warehouse,
            basic_rate=item.valuation_rate,
            basic_amount=item.amount,
            valuation_rate=item.valuation_rate,
            amount=item.amount,
            batch_no=item.batch_no,
            serial_no=item.serial_no,
            idx=item.idx,
        )
        db.add(detail)

    transfer.status = TransferStatus.COMPLETED
    transfer.transfer_date = datetime.utcnow()
    transfer.outbound_stock_entry_id = outbound_entry.id
    transfer.updated_by_id = principal.id
    db.commit()

    logger.info(
        "transfer_executed",
        transfer_id=transfer.id,
        stock_entry_id=outbound_entry.id,
        principal_id=principal.id,
    )

    return {
        "id": transfer.id,
        "status": transfer.status.value,
        "stock_entry_id": outbound_entry.id,
        "message": "Transfer executed successfully",
    }


# ============= BATCHES =============
@router.get("/batches", dependencies=[Depends(Require("inventory:read"))])
async def list_batches(
    db: Session = Depends(get_db),
    item_code: Optional[str] = None,
    include_disabled: bool = False,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    """List inventory batches."""
    from app.models.inventory import Batch

    query = db.query(Batch)

    if not include_disabled:
        query = query.filter(Batch.disabled == False)
    if item_code:
        query = query.filter(Batch.item_code.ilike(f"%{item_code}%"))

    total = query.count()
    batches = query.order_by(desc(Batch.created_at)).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "batches": [
            {
                "id": b.id,
                "batch_id": b.batch_id,
                "item_code": b.item_code,
                "item_name": b.item_name,
                "manufacturing_date": b.manufacturing_date.isoformat() if b.manufacturing_date else None,
                "expiry_date": b.expiry_date.isoformat() if b.expiry_date else None,
                "batch_qty": float(b.batch_qty) if b.batch_qty else 0,
                "supplier": b.supplier,
                "disabled": b.disabled,
            }
            for b in batches
        ],
    }


class BatchCreate(BaseModel):
    batch_id: str
    item_code: str
    item_name: Optional[str] = None
    manufacturing_date: Optional[str] = None
    expiry_date: Optional[str] = None
    supplier: Optional[str] = None
    description: Optional[str] = None


@router.post("/batches", dependencies=[Depends(Require("inventory:write"))])
async def create_batch(
    data: BatchCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new batch."""
    from app.models.inventory import Batch

    existing = db.query(Batch).filter(Batch.batch_id == data.batch_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Batch ID already exists")

    mfg_date = _parse_date(data.manufacturing_date, "manufacturing_date") if data.manufacturing_date else None
    exp_date = _parse_date(data.expiry_date, "expiry_date") if data.expiry_date else None

    batch = Batch(
        batch_id=data.batch_id,
        item_code=data.item_code,
        item_name=data.item_name,
        manufacturing_date=mfg_date,
        expiry_date=exp_date,
        supplier=data.supplier,
        description=data.description,
        created_by_id=principal.id,
    )
    db.add(batch)
    db.commit()

    return {"id": batch.id, "batch_id": batch.batch_id, "message": "Batch created successfully"}


# ============= SERIAL NUMBERS =============
@router.get("/serials", dependencies=[Depends(Require("inventory:read"))])
async def list_serial_numbers(
    db: Session = Depends(get_db),
    item_code: Optional[str] = None,
    warehouse: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    """List serial numbers."""
    from app.models.inventory import SerialNumber, SerialStatus

    query = db.query(SerialNumber)

    if item_code:
        query = query.filter(SerialNumber.item_code.ilike(f"%{item_code}%"))
    if warehouse:
        query = query.filter(SerialNumber.warehouse.ilike(f"%{warehouse}%"))
    if status:
        try:
            status_enum = SerialStatus(status)
            query = query.filter(SerialNumber.status == status_enum)
        except ValueError:
            pass

    total = query.count()
    serials = query.order_by(desc(SerialNumber.created_at)).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "serials": [
            {
                "id": s.id,
                "serial_no": s.serial_no,
                "item_code": s.item_code,
                "item_name": s.item_name,
                "warehouse": s.warehouse,
                "batch_no": s.batch_no,
                "status": s.status.value,
                "customer": s.customer,
                "delivery_date": s.delivery_date.isoformat() if s.delivery_date else None,
                "warranty_expiry_date": s.warranty_expiry_date.isoformat() if s.warranty_expiry_date else None,
            }
            for s in serials
        ],
    }


class SerialNumberCreate(BaseModel):
    serial_no: str
    item_code: str
    item_name: Optional[str] = None
    warehouse: Optional[str] = None
    batch_no: Optional[str] = None
    supplier: Optional[str] = None
    purchase_date: Optional[str] = None
    warranty_period: Optional[int] = None
    description: Optional[str] = None


@router.post("/serials", dependencies=[Depends(Require("inventory:write"))])
async def create_serial_number(
    data: SerialNumberCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new serial number."""
    from app.models.inventory import SerialNumber, SerialStatus
    from datetime import timedelta

    existing = db.query(SerialNumber).filter(SerialNumber.serial_no == data.serial_no).first()
    if existing:
        raise HTTPException(status_code=400, detail="Serial number already exists")

    purchase_date = _parse_date(data.purchase_date, "purchase_date") if data.purchase_date else None
    warranty_expiry = None
    if purchase_date and data.warranty_period:
        warranty_expiry = purchase_date + timedelta(days=data.warranty_period)

    serial = SerialNumber(
        serial_no=data.serial_no,
        item_code=data.item_code,
        item_name=data.item_name,
        warehouse=data.warehouse,
        batch_no=data.batch_no,
        status=SerialStatus.ACTIVE,
        supplier=data.supplier,
        purchase_date=purchase_date,
        warranty_period=data.warranty_period,
        warranty_expiry_date=warranty_expiry,
        description=data.description,
        created_by_id=principal.id,
    )
    db.add(serial)
    db.commit()

    return {"id": serial.id, "serial_no": serial.serial_no, "message": "Serial number created successfully"}
