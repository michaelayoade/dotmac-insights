"""
KRA Definitions API - Key Result Area management
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict

from app.database import get_db
from app.auth import Require
from app.models.performance import (
    KRADefinition,
    KRAKPIMap,
    KPIDefinition,
)

router = APIRouter(prefix="/kras", tags=["performance-kras"])


# ============= SCHEMAS =============
class KRACreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None


class KRAUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None


class KPILinkCreate(BaseModel):
    kpi_id: int
    weightage: float
    idx: int = 0


class KPILinkResponse(BaseModel):
    id: int
    kpi_id: int
    kpi_code: str
    kpi_name: str
    weightage: float
    idx: int

    model_config = ConfigDict(from_attributes=True)


class KRAResponse(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str]
    category: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    kpi_count: int = 0
    kpis: List[KPILinkResponse] = []

    model_config = ConfigDict(from_attributes=True)


class KRAListResponse(BaseModel):
    items: List[KRAResponse]
    total: int


# ============= HELPERS =============
def build_kra_response(kra: KRADefinition, db: Session, include_kpis: bool = False) -> KRAResponse:
    kpi_count = db.query(func.count(KRAKPIMap.id)).filter(KRAKPIMap.kra_id == kra.id).scalar() or 0

    kpis = []
    if include_kpis:
        mappings = db.query(KRAKPIMap).filter(KRAKPIMap.kra_id == kra.id).order_by(KRAKPIMap.idx).all()
        for m in mappings:
            kpi = db.query(KPIDefinition).filter(KPIDefinition.id == m.kpi_id).first()
            if kpi:
                kpis.append(KPILinkResponse(
                    id=m.id,
                    kpi_id=m.kpi_id,
                    kpi_code=kpi.code,
                    kpi_name=kpi.name,
                    weightage=float(m.weightage or 0),
                    idx=m.idx,
                ))

    return KRAResponse(
        id=kra.id,
        code=kra.code,
        name=kra.name,
        description=kra.description,
        category=kra.category,
        is_active=kra.is_active,
        created_at=kra.created_at,
        updated_at=kra.updated_at,
        kpi_count=kpi_count,
        kpis=kpis,
    )


# ============= ENDPOINTS =============
@router.get("", response_model=KRAListResponse, dependencies=[Depends(Require("performance:read"))])
async def list_kras(
    search: Optional[str] = None,
    category: Optional[str] = None,
    active_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List KRA definitions."""
    query = db.query(KRADefinition)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            KRADefinition.name.ilike(search_term) |
            KRADefinition.code.ilike(search_term)
        )

    if category:
        query = query.filter(KRADefinition.category == category)

    if active_only:
        query = query.filter(KRADefinition.is_active == True)

    total = query.count()
    kras = query.order_by(KRADefinition.code).offset(offset).limit(limit).all()

    items = [build_kra_response(kra, db) for kra in kras]

    return KRAListResponse(items=items, total=total)


@router.get("/categories", dependencies=[Depends(Require("performance:read"))])
async def list_kra_categories(db: Session = Depends(get_db)):
    """List distinct KRA categories."""
    categories = db.query(KRADefinition.category).filter(
        KRADefinition.category.isnot(None),
        KRADefinition.is_active == True
    ).distinct().all()

    return {"categories": [c[0] for c in categories if c[0]]}


@router.get("/{kra_id}", response_model=KRAResponse, dependencies=[Depends(Require("performance:read"))])
async def get_kra(kra_id: int, db: Session = Depends(get_db)):
    """Get a single KRA with its KPIs."""
    kra = db.query(KRADefinition).filter(KRADefinition.id == kra_id).first()
    if not kra:
        raise HTTPException(status_code=404, detail="KRA not found")

    return build_kra_response(kra, db, include_kpis=True)


@router.post("", response_model=KRAResponse, dependencies=[Depends(Require("performance:write"))])
async def create_kra(payload: KRACreate, db: Session = Depends(get_db)):
    """Create a new KRA definition."""
    existing = db.query(KRADefinition).filter(KRADefinition.code == payload.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"KRA with code '{payload.code}' already exists")

    kra = KRADefinition(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        is_active=True,
    )
    db.add(kra)
    db.commit()
    db.refresh(kra)

    return build_kra_response(kra, db)


@router.patch("/{kra_id}", response_model=KRAResponse, dependencies=[Depends(Require("performance:write"))])
async def update_kra(kra_id: int, payload: KRAUpdate, db: Session = Depends(get_db)):
    """Update a KRA definition."""
    kra = db.query(KRADefinition).filter(KRADefinition.id == kra_id).first()
    if not kra:
        raise HTTPException(status_code=404, detail="KRA not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(kra, key, value)

    db.commit()
    db.refresh(kra)

    return build_kra_response(kra, db, include_kpis=True)


@router.delete("/{kra_id}", dependencies=[Depends(Require("performance:write"))])
async def delete_kra(kra_id: int, db: Session = Depends(get_db)):
    """Delete a KRA (soft delete)."""
    kra = db.query(KRADefinition).filter(KRADefinition.id == kra_id).first()
    if not kra:
        raise HTTPException(status_code=404, detail="KRA not found")

    kra.is_active = False
    db.commit()

    return {"success": True, "message": "KRA deactivated"}


# ============= KPI LINKS =============
@router.get("/{kra_id}/kpis", response_model=List[KPILinkResponse], dependencies=[Depends(Require("performance:read"))])
async def list_kra_kpis(kra_id: int, db: Session = Depends(get_db)):
    """List KPIs linked to a KRA."""
    kra = db.query(KRADefinition).filter(KRADefinition.id == kra_id).first()
    if not kra:
        raise HTTPException(status_code=404, detail="KRA not found")

    mappings = db.query(KRAKPIMap).filter(KRAKPIMap.kra_id == kra_id).order_by(KRAKPIMap.idx).all()

    result = []
    for m in mappings:
        kpi = db.query(KPIDefinition).filter(KPIDefinition.id == m.kpi_id).first()
        if kpi:
            result.append(KPILinkResponse(
                id=m.id,
                kpi_id=m.kpi_id,
                kpi_code=kpi.code,
                kpi_name=kpi.name,
                weightage=float(m.weightage or 0),
                idx=m.idx,
            ))

    return result


@router.post("/{kra_id}/kpis", response_model=KPILinkResponse, dependencies=[Depends(Require("performance:write"))])
async def add_kpi_to_kra(kra_id: int, payload: KPILinkCreate, db: Session = Depends(get_db)):
    """Link a KPI to a KRA."""
    kra = db.query(KRADefinition).filter(KRADefinition.id == kra_id).first()
    if not kra:
        raise HTTPException(status_code=404, detail="KRA not found")

    kpi = db.query(KPIDefinition).filter(KPIDefinition.id == payload.kpi_id).first()
    if not kpi:
        raise HTTPException(status_code=404, detail="KPI not found")

    # Check if already linked
    existing = db.query(KRAKPIMap).filter(
        KRAKPIMap.kra_id == kra_id,
        KRAKPIMap.kpi_id == payload.kpi_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="KPI already linked to this KRA")

    mapping = KRAKPIMap(
        kra_id=kra_id,
        kpi_id=payload.kpi_id,
        weightage=Decimal(str(payload.weightage)),
        idx=payload.idx,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)

    return KPILinkResponse(
        id=mapping.id,
        kpi_id=mapping.kpi_id,
        kpi_code=kpi.code,
        kpi_name=kpi.name,
        weightage=float(mapping.weightage or 0),
        idx=mapping.idx,
    )


@router.put("/{kra_id}/kpis", response_model=List[KPILinkResponse], dependencies=[Depends(Require("performance:write"))])
async def replace_kra_kpis(kra_id: int, items: List[KPILinkCreate], db: Session = Depends(get_db)):
    """Replace all KPI links for a KRA."""
    kra = db.query(KRADefinition).filter(KRADefinition.id == kra_id).first()
    if not kra:
        raise HTTPException(status_code=404, detail="KRA not found")

    # Validate total weightage
    total_weight = sum(item.weightage for item in items)
    if items and abs(total_weight - 100) > 0.01:
        raise HTTPException(status_code=400, detail=f"Total KPI weightage must equal 100%. Current: {total_weight}%")

    # Delete existing mappings
    db.query(KRAKPIMap).filter(KRAKPIMap.kra_id == kra_id).delete()

    result = []
    for item in items:
        kpi = db.query(KPIDefinition).filter(KPIDefinition.id == item.kpi_id).first()
        if not kpi:
            raise HTTPException(status_code=400, detail=f"KPI with id {item.kpi_id} not found")

        mapping = KRAKPIMap(
            kra_id=kra_id,
            kpi_id=item.kpi_id,
            weightage=Decimal(str(item.weightage)),
            idx=item.idx,
        )
        db.add(mapping)
        db.flush()

        result.append(KPILinkResponse(
            id=mapping.id,
            kpi_id=mapping.kpi_id,
            kpi_code=kpi.code,
            kpi_name=kpi.name,
            weightage=float(mapping.weightage or 0),
            idx=mapping.idx,
        ))

    db.commit()

    return result


@router.delete("/{kra_id}/kpis/{mapping_id}", dependencies=[Depends(Require("performance:write"))])
async def remove_kpi_from_kra(kra_id: int, mapping_id: int, db: Session = Depends(get_db)):
    """Remove a KPI link from a KRA."""
    mapping = db.query(KRAKPIMap).filter(
        KRAKPIMap.id == mapping_id,
        KRAKPIMap.kra_id == kra_id
    ).first()

    if not mapping:
        raise HTTPException(status_code=404, detail="KPI link not found")

    db.delete(mapping)
    db.commit()

    return {"success": True, "message": "KPI unlinked from KRA"}
