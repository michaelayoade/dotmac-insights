"""
Territories API

Manages geographic territories/regions for CRM.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict

from app.database import get_db
from app.auth import Require
from app.models.sales import Territory

router = APIRouter(prefix="/territories", tags=["crm-config-territories"])


# =============================================================================
# SCHEMAS
# =============================================================================

class TerritoryBase(BaseModel):
    """Base schema for territories."""
    territory_name: str
    parent_territory: Optional[str] = None
    territory_manager: Optional[str] = None
    is_group: bool = False


class TerritoryCreate(TerritoryBase):
    """Schema for creating a territory."""
    pass


class TerritoryUpdate(BaseModel):
    """Schema for updating a territory."""
    territory_name: Optional[str] = None
    parent_territory: Optional[str] = None
    territory_manager: Optional[str] = None
    is_group: Optional[bool] = None


class TerritoryResponse(BaseModel):
    """Schema for territory response."""
    id: int
    erpnext_id: Optional[str]
    territory_name: str
    parent_territory: Optional[str]
    territory_manager: Optional[str]
    is_group: bool
    lft: Optional[int]
    rgt: Optional[int]

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("", dependencies=[Depends(Require("crm:read"))])
async def list_territories(
    search: Optional[str] = None,
    parent: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List territories with filtering."""
    query = db.query(Territory)

    if search:
        query = query.filter(Territory.territory_name.ilike(f"%{search}%"))

    if parent:
        query = query.filter(Territory.parent_territory == parent)

    total = query.count()
    territories = query.order_by(Territory.territory_name).offset(offset).limit(limit).all()

    return {
        "data": [
            {
                "id": t.id,
                "erpnext_id": t.erpnext_id,
                "territory_name": t.territory_name,
                "parent_territory": t.parent_territory,
                "territory_manager": t.territory_manager,
                "is_group": t.is_group,
                "lft": t.lft,
                "rgt": t.rgt,
            }
            for t in territories
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{territory_id}", dependencies=[Depends(Require("crm:read"))])
async def get_territory(territory_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get a territory by ID."""
    territory = db.query(Territory).filter(Territory.id == territory_id).first()
    if not territory:
        raise HTTPException(status_code=404, detail="Territory not found")

    return {
        "id": territory.id,
        "erpnext_id": territory.erpnext_id,
        "territory_name": territory.territory_name,
        "parent_territory": territory.parent_territory,
        "territory_manager": territory.territory_manager,
        "is_group": territory.is_group,
        "lft": territory.lft,
        "rgt": territory.rgt,
    }


@router.post("", dependencies=[Depends(Require("crm:write"))], status_code=201)
async def create_territory(
    payload: TerritoryCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new territory."""
    # Check for duplicate name
    existing = db.query(Territory).filter(
        Territory.territory_name == payload.territory_name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Territory name already exists")

    territory = Territory(
        territory_name=payload.territory_name,
        parent_territory=payload.parent_territory,
        territory_manager=payload.territory_manager,
        is_group=payload.is_group,
    )

    db.add(territory)
    db.commit()
    db.refresh(territory)

    return {"id": territory.id, "territory_name": territory.territory_name}


@router.patch("/{territory_id}", dependencies=[Depends(Require("crm:write"))])
async def update_territory(
    territory_id: int,
    payload: TerritoryUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a territory."""
    territory = db.query(Territory).filter(Territory.id == territory_id).first()
    if not territory:
        raise HTTPException(status_code=404, detail="Territory not found")

    update_data = payload.model_dump(exclude_unset=True)

    # Check for duplicate name if updating
    if "territory_name" in update_data:
        existing = db.query(Territory).filter(
            Territory.territory_name == update_data["territory_name"],
            Territory.id != territory_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Territory name already exists")

    for key, value in update_data.items():
        setattr(territory, key, value)

    db.commit()
    db.refresh(territory)

    return {"id": territory.id, "territory_name": territory.territory_name}


@router.delete("/{territory_id}", dependencies=[Depends(Require("crm:write"))])
async def delete_territory(territory_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Delete a territory."""
    territory = db.query(Territory).filter(Territory.id == territory_id).first()
    if not territory:
        raise HTTPException(status_code=404, detail="Territory not found")

    # Check for child territories
    children = db.query(Territory).filter(
        Territory.parent_territory == territory.territory_name
    ).count()
    if children > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete territory with child territories"
        )

    db.delete(territory)
    db.commit()

    return {"success": True, "message": "Territory deleted"}
