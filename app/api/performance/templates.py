"""
Scorecard Templates API - Template CRUD and management
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel

from app.database import get_db
from app.auth import Require
from app.models.performance import (
    ScorecardTemplate,
    ScorecardTemplateItem,
    KRADefinition,
)

router = APIRouter(prefix="/templates", tags=["performance-templates"])


# ============= SCHEMAS =============
class TemplateItemCreate(BaseModel):
    kra_id: int
    weightage: float
    idx: int = 0


class TemplateCreate(BaseModel):
    code: str
    name: str
    applicable_departments: Optional[List[str]] = None
    applicable_designations: Optional[List[str]] = None
    is_default: bool = False
    items: List[TemplateItemCreate] = []


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    applicable_departments: Optional[List[str]] = None
    applicable_designations: Optional[List[str]] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class TemplateItemResponse(BaseModel):
    id: int
    kra_id: int
    kra_code: str
    kra_name: str
    weightage: float
    idx: int

    class Config:
        from_attributes = True


class TemplateResponse(BaseModel):
    id: int
    code: str
    name: str
    applicable_departments: Optional[List[str]]
    applicable_designations: Optional[List[str]]
    version: int
    is_active: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime
    items: List[TemplateItemResponse] = []
    total_weightage: float = 0

    class Config:
        from_attributes = True


class TemplateListResponse(BaseModel):
    items: List[TemplateResponse]
    total: int


# ============= HELPERS =============
def build_template_response(template: ScorecardTemplate, db: Session) -> TemplateResponse:
    items = []
    total_weightage = 0.0

    for item in sorted(template.items, key=lambda x: x.idx):
        kra = db.query(KRADefinition).filter(KRADefinition.id == item.kra_id).first()
        if kra:
            items.append(TemplateItemResponse(
                id=item.id,
                kra_id=item.kra_id,
                kra_code=kra.code,
                kra_name=kra.name,
                weightage=float(item.weightage or 0),
                idx=item.idx,
            ))
            total_weightage += float(item.weightage or 0)

    return TemplateResponse(
        id=template.id,
        code=template.code,
        name=template.name,
        applicable_departments=template.applicable_departments,
        applicable_designations=template.applicable_designations,
        version=template.version,
        is_active=template.is_active,
        is_default=template.is_default,
        created_at=template.created_at,
        updated_at=template.updated_at,
        items=items,
        total_weightage=total_weightage,
    )


# ============= ENDPOINTS =============
@router.get("", response_model=TemplateListResponse, dependencies=[Depends(Require("performance:read"))])
async def list_templates(
    active_only: bool = Query(True),
    department: Optional[str] = None,
    designation: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List scorecard templates."""
    query = db.query(ScorecardTemplate).options(joinedload(ScorecardTemplate.items))

    if active_only:
        query = query.filter(ScorecardTemplate.is_active == True)

    # TODO: Add department/designation filtering with JSON contains

    total = query.count()
    templates = query.order_by(ScorecardTemplate.name).offset(offset).limit(limit).all()

    items = [build_template_response(t, db) for t in templates]

    return TemplateListResponse(items=items, total=total)


@router.get("/{template_id}", response_model=TemplateResponse, dependencies=[Depends(Require("performance:read"))])
async def get_template(template_id: int, db: Session = Depends(get_db)):
    """Get a single template with items."""
    template = db.query(ScorecardTemplate).options(
        joinedload(ScorecardTemplate.items)
    ).filter(ScorecardTemplate.id == template_id).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return build_template_response(template, db)


@router.post("", response_model=TemplateResponse, dependencies=[Depends(Require("performance:write"))])
async def create_template(payload: TemplateCreate, db: Session = Depends(get_db)):
    """Create a new scorecard template."""
    # Check code uniqueness
    existing = db.query(ScorecardTemplate).filter(ScorecardTemplate.code == payload.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Template with code '{payload.code}' already exists")

    # Validate total weightage
    total_weight = sum(item.weightage for item in payload.items)
    if payload.items and abs(total_weight - 100) > 0.01:
        raise HTTPException(status_code=400, detail=f"Total weightage must equal 100%. Current: {total_weight}%")

    # If setting as default, unset other defaults
    if payload.is_default:
        db.query(ScorecardTemplate).filter(ScorecardTemplate.is_default == True).update(
            {ScorecardTemplate.is_default: False}, synchronize_session=False
        )

    template = ScorecardTemplate(
        code=payload.code,
        name=payload.name,
        applicable_departments=payload.applicable_departments,
        applicable_designations=payload.applicable_designations,
        is_default=payload.is_default,
        version=1,
        is_active=True,
    )
    db.add(template)
    db.flush()

    # Add items
    for item_data in payload.items:
        # Validate KRA exists
        kra = db.query(KRADefinition).filter(KRADefinition.id == item_data.kra_id).first()
        if not kra:
            raise HTTPException(status_code=400, detail=f"KRA with id {item_data.kra_id} not found")

        item = ScorecardTemplateItem(
            template_id=template.id,
            kra_id=item_data.kra_id,
            weightage=Decimal(str(item_data.weightage)),
            idx=item_data.idx,
        )
        db.add(item)

    db.commit()
    db.refresh(template)

    return build_template_response(template, db)


@router.patch("/{template_id}", response_model=TemplateResponse, dependencies=[Depends(Require("performance:write"))])
async def update_template(template_id: int, payload: TemplateUpdate, db: Session = Depends(get_db)):
    """Update a template."""
    template = db.query(ScorecardTemplate).filter(ScorecardTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    update_data = payload.model_dump(exclude_unset=True)

    # If setting as default, unset others
    if update_data.get('is_default'):
        db.query(ScorecardTemplate).filter(
            ScorecardTemplate.id != template_id,
            ScorecardTemplate.is_default == True
        ).update({ScorecardTemplate.is_default: False}, synchronize_session=False)

    for key, value in update_data.items():
        setattr(template, key, value)

    db.commit()
    db.refresh(template)

    return build_template_response(template, db)


@router.put("/{template_id}/items", response_model=TemplateResponse, dependencies=[Depends(Require("performance:write"))])
async def update_template_items(
    template_id: int,
    items: List[TemplateItemCreate],
    db: Session = Depends(get_db),
):
    """Replace all template items."""
    template = db.query(ScorecardTemplate).filter(ScorecardTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Validate total weightage
    total_weight = sum(item.weightage for item in items)
    if abs(total_weight - 100) > 0.01:
        raise HTTPException(status_code=400, detail=f"Total weightage must equal 100%. Current: {total_weight}%")

    # Delete existing items
    db.query(ScorecardTemplateItem).filter(ScorecardTemplateItem.template_id == template_id).delete()

    # Add new items
    for item_data in items:
        kra = db.query(KRADefinition).filter(KRADefinition.id == item_data.kra_id).first()
        if not kra:
            raise HTTPException(status_code=400, detail=f"KRA with id {item_data.kra_id} not found")

        item = ScorecardTemplateItem(
            template_id=template.id,
            kra_id=item_data.kra_id,
            weightage=Decimal(str(item_data.weightage)),
            idx=item_data.idx,
        )
        db.add(item)

    # Increment version
    template.version += 1
    db.commit()
    db.refresh(template)

    return build_template_response(template, db)


@router.post("/{template_id}/clone", response_model=TemplateResponse, dependencies=[Depends(Require("performance:write"))])
async def clone_template(
    template_id: int,
    new_code: str = Query(...),
    new_name: str = Query(...),
    db: Session = Depends(get_db),
):
    """Clone a template with a new code and name."""
    source = db.query(ScorecardTemplate).options(
        joinedload(ScorecardTemplate.items)
    ).filter(ScorecardTemplate.id == template_id).first()

    if not source:
        raise HTTPException(status_code=404, detail="Source template not found")

    # Check new code uniqueness
    existing = db.query(ScorecardTemplate).filter(ScorecardTemplate.code == new_code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Template with code '{new_code}' already exists")

    new_template = ScorecardTemplate(
        code=new_code,
        name=new_name,
        applicable_departments=source.applicable_departments,
        applicable_designations=source.applicable_designations,
        version=1,
        is_active=True,
        is_default=False,
    )
    db.add(new_template)
    db.flush()

    # Clone items
    for item in source.items:
        new_item = ScorecardTemplateItem(
            template_id=new_template.id,
            kra_id=item.kra_id,
            weightage=item.weightage,
            idx=item.idx,
        )
        db.add(new_item)

    db.commit()
    db.refresh(new_template)

    return build_template_response(new_template, db)


@router.delete("/{template_id}", dependencies=[Depends(Require("performance:write"))])
async def delete_template(template_id: int, db: Session = Depends(get_db)):
    """Delete a template (soft delete by deactivating)."""
    template = db.query(ScorecardTemplate).filter(ScorecardTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Soft delete
    template.is_active = False
    db.commit()

    return {"success": True, "message": "Template deactivated"}
