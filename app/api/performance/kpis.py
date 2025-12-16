"""
KPI Definitions API - KPI management and bindings
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel
from enum import Enum

from app.database import get_db
from app.auth import Require
from app.models.performance import (
    KPIDefinition,
    KPIDataSource,
    KPIAggregation,
    ScoringMethod,
    KPIBinding,
    KRAKPIMap,
)

router = APIRouter(prefix="/kpis", tags=["performance-kpis"])


# ============= SCHEMAS =============
class DataSourceEnum(str, Enum):
    manual = "manual"
    ticketing = "ticketing"
    field_service = "field_service"
    finance = "finance"
    crm = "crm"
    attendance = "attendance"
    project = "project"


class AggregationEnum(str, Enum):
    sum = "sum"
    avg = "avg"
    count = "count"
    min = "min"
    max = "max"
    percent = "percent"
    ratio = "ratio"


class ScoringMethodEnum(str, Enum):
    linear = "linear"
    threshold = "threshold"
    band = "band"
    binary = "binary"


class KPICreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    data_source: DataSourceEnum
    aggregation: AggregationEnum
    query_config: Optional[dict] = None
    scoring_method: ScoringMethodEnum
    min_value: Optional[float] = None
    target_value: Optional[float] = None
    max_value: Optional[float] = None
    threshold_config: Optional[dict] = None
    higher_is_better: bool = True


class KPIUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    query_config: Optional[dict] = None
    scoring_method: Optional[ScoringMethodEnum] = None
    min_value: Optional[float] = None
    target_value: Optional[float] = None
    max_value: Optional[float] = None
    threshold_config: Optional[dict] = None
    higher_is_better: Optional[bool] = None


class KPIResponse(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str]
    data_source: str
    aggregation: str
    query_config: Optional[dict]
    scoring_method: str
    min_value: Optional[float]
    target_value: Optional[float]
    max_value: Optional[float]
    threshold_config: Optional[dict]
    higher_is_better: bool
    created_at: datetime
    updated_at: datetime
    kra_count: int = 0

    class Config:
        from_attributes = True


class KPIListResponse(BaseModel):
    items: List[KPIResponse]
    total: int


class KPIBindingCreate(BaseModel):
    employee_id: Optional[int] = None
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    target_override: Optional[float] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None


class KPIBindingResponse(BaseModel):
    id: int
    kpi_id: int
    employee_id: Optional[int]
    department_id: Optional[int]
    designation_id: Optional[int]
    target_override: Optional[float]
    effective_from: Optional[date]
    effective_to: Optional[date]
    created_at: datetime

    class Config:
        from_attributes = True


# ============= ENDPOINTS =============
@router.get("", response_model=KPIListResponse, dependencies=[Depends(Require("performance:read"))])
async def list_kpis(
    search: Optional[str] = None,
    data_source: Optional[DataSourceEnum] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List KPI definitions."""
    query = db.query(KPIDefinition)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            KPIDefinition.name.ilike(search_term) |
            KPIDefinition.code.ilike(search_term) |
            KPIDefinition.description.ilike(search_term)
        )

    if data_source:
        query = query.filter(KPIDefinition.data_source == KPIDataSource(data_source.value))

    total = query.count()
    kpis = query.order_by(KPIDefinition.code).offset(offset).limit(limit).all()

    items = []
    for kpi in kpis:
        kra_count = db.query(func.count(KRAKPIMap.id)).filter(KRAKPIMap.kpi_id == kpi.id).scalar() or 0

        items.append(KPIResponse(
            id=kpi.id,
            code=kpi.code,
            name=kpi.name,
            description=kpi.description,
            data_source=kpi.data_source.value,
            aggregation=kpi.aggregation.value,
            query_config=kpi.query_config,
            scoring_method=kpi.scoring_method.value,
            min_value=float(kpi.min_value) if kpi.min_value else None,
            target_value=float(kpi.target_value) if kpi.target_value else None,
            max_value=float(kpi.max_value) if kpi.max_value else None,
            threshold_config=kpi.threshold_config,
            higher_is_better=kpi.higher_is_better,
            created_at=kpi.created_at,
            updated_at=kpi.updated_at,
            kra_count=kra_count,
        ))

    return KPIListResponse(items=items, total=total)


@router.get("/{kpi_id}", response_model=KPIResponse, dependencies=[Depends(Require("performance:read"))])
async def get_kpi(kpi_id: int, db: Session = Depends(get_db)):
    """Get a single KPI definition."""
    kpi = db.query(KPIDefinition).filter(KPIDefinition.id == kpi_id).first()
    if not kpi:
        raise HTTPException(status_code=404, detail="KPI not found")

    kra_count = db.query(func.count(KRAKPIMap.id)).filter(KRAKPIMap.kpi_id == kpi.id).scalar() or 0

    return KPIResponse(
        id=kpi.id,
        code=kpi.code,
        name=kpi.name,
        description=kpi.description,
        data_source=kpi.data_source.value,
        aggregation=kpi.aggregation.value,
        query_config=kpi.query_config,
        scoring_method=kpi.scoring_method.value,
        min_value=float(kpi.min_value) if kpi.min_value else None,
        target_value=float(kpi.target_value) if kpi.target_value else None,
        max_value=float(kpi.max_value) if kpi.max_value else None,
        threshold_config=kpi.threshold_config,
        higher_is_better=kpi.higher_is_better,
        created_at=kpi.created_at,
        updated_at=kpi.updated_at,
        kra_count=kra_count,
    )


@router.post("", response_model=KPIResponse, dependencies=[Depends(Require("performance:write"))])
async def create_kpi(payload: KPICreate, db: Session = Depends(get_db)):
    """Create a new KPI definition."""
    existing = db.query(KPIDefinition).filter(KPIDefinition.code == payload.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"KPI with code '{payload.code}' already exists")

    kpi = KPIDefinition(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        data_source=KPIDataSource(payload.data_source.value),
        aggregation=KPIAggregation(payload.aggregation.value),
        query_config=payload.query_config,
        scoring_method=ScoringMethod(payload.scoring_method.value),
        min_value=Decimal(str(payload.min_value)) if payload.min_value is not None else None,
        target_value=Decimal(str(payload.target_value)) if payload.target_value is not None else None,
        max_value=Decimal(str(payload.max_value)) if payload.max_value is not None else None,
        threshold_config=payload.threshold_config,
        higher_is_better=payload.higher_is_better,
    )
    db.add(kpi)
    db.commit()
    db.refresh(kpi)

    return KPIResponse(
        id=kpi.id,
        code=kpi.code,
        name=kpi.name,
        description=kpi.description,
        data_source=kpi.data_source.value,
        aggregation=kpi.aggregation.value,
        query_config=kpi.query_config,
        scoring_method=kpi.scoring_method.value,
        min_value=float(kpi.min_value) if kpi.min_value else None,
        target_value=float(kpi.target_value) if kpi.target_value else None,
        max_value=float(kpi.max_value) if kpi.max_value else None,
        threshold_config=kpi.threshold_config,
        higher_is_better=kpi.higher_is_better,
        created_at=kpi.created_at,
        updated_at=kpi.updated_at,
        kra_count=0,
    )


@router.patch("/{kpi_id}", response_model=KPIResponse, dependencies=[Depends(Require("performance:write"))])
async def update_kpi(kpi_id: int, payload: KPIUpdate, db: Session = Depends(get_db)):
    """Update a KPI definition."""
    kpi = db.query(KPIDefinition).filter(KPIDefinition.id == kpi_id).first()
    if not kpi:
        raise HTTPException(status_code=404, detail="KPI not found")

    update_data = payload.model_dump(exclude_unset=True)

    if 'scoring_method' in update_data:
        update_data['scoring_method'] = ScoringMethod(update_data['scoring_method'].value)

    for key in ['min_value', 'target_value', 'max_value']:
        if key in update_data and update_data[key] is not None:
            update_data[key] = Decimal(str(update_data[key]))

    for key, value in update_data.items():
        setattr(kpi, key, value)

    db.commit()
    db.refresh(kpi)

    return await get_kpi(kpi_id, db)


@router.delete("/{kpi_id}", dependencies=[Depends(Require("performance:write"))])
async def delete_kpi(kpi_id: int, db: Session = Depends(get_db)):
    """Delete a KPI definition."""
    kpi = db.query(KPIDefinition).filter(KPIDefinition.id == kpi_id).first()
    if not kpi:
        raise HTTPException(status_code=404, detail="KPI not found")

    # Check if KPI is linked to any KRA
    link_count = db.query(func.count(KRAKPIMap.id)).filter(KRAKPIMap.kpi_id == kpi_id).scalar() or 0
    if link_count > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete KPI linked to {link_count} KRAs")

    db.delete(kpi)
    db.commit()

    return {"success": True, "message": "KPI deleted"}


# ============= BINDINGS =============
@router.get("/{kpi_id}/bindings", response_model=List[KPIBindingResponse], dependencies=[Depends(Require("performance:read"))])
async def list_kpi_bindings(kpi_id: int, db: Session = Depends(get_db)):
    """List target bindings for a KPI."""
    kpi = db.query(KPIDefinition).filter(KPIDefinition.id == kpi_id).first()
    if not kpi:
        raise HTTPException(status_code=404, detail="KPI not found")

    bindings = db.query(KPIBinding).filter(KPIBinding.kpi_id == kpi_id).all()

    return [
        KPIBindingResponse(
            id=b.id,
            kpi_id=b.kpi_id,
            employee_id=b.employee_id,
            department_id=b.department_id,
            designation_id=b.designation_id,
            target_override=float(b.target_override) if b.target_override else None,
            effective_from=b.effective_from,
            effective_to=b.effective_to,
            created_at=b.created_at,
        )
        for b in bindings
    ]


@router.post("/{kpi_id}/bindings", response_model=KPIBindingResponse, dependencies=[Depends(Require("performance:write"))])
async def create_kpi_binding(kpi_id: int, payload: KPIBindingCreate, db: Session = Depends(get_db)):
    """Create a target binding for a KPI."""
    kpi = db.query(KPIDefinition).filter(KPIDefinition.id == kpi_id).first()
    if not kpi:
        raise HTTPException(status_code=404, detail="KPI not found")

    binding = KPIBinding(
        kpi_id=kpi_id,
        employee_id=payload.employee_id,
        department_id=payload.department_id,
        designation_id=payload.designation_id,
        target_override=Decimal(str(payload.target_override)) if payload.target_override else None,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
    )
    db.add(binding)
    db.commit()
    db.refresh(binding)

    return KPIBindingResponse(
        id=binding.id,
        kpi_id=binding.kpi_id,
        employee_id=binding.employee_id,
        department_id=binding.department_id,
        designation_id=binding.designation_id,
        target_override=float(binding.target_override) if binding.target_override else None,
        effective_from=binding.effective_from,
        effective_to=binding.effective_to,
        created_at=binding.created_at,
    )


@router.delete("/{kpi_id}/bindings/{binding_id}", dependencies=[Depends(Require("performance:write"))])
async def delete_kpi_binding(kpi_id: int, binding_id: int, db: Session = Depends(get_db)):
    """Delete a KPI binding."""
    binding = db.query(KPIBinding).filter(
        KPIBinding.id == binding_id,
        KPIBinding.kpi_id == kpi_id
    ).first()

    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found")

    db.delete(binding)
    db.commit()

    return {"success": True, "message": "Binding deleted"}
