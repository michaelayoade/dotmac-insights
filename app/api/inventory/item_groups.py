"""Item Groups API endpoints.

Thin wrapper around ItemGroupService for item group CRUD operations.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.inventory import ItemGroupService, ItemGroupFilters, ItemGroupCreateData, ItemGroupUpdateData
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError, ConflictError

from ._deps import (
    get_item_group_service,
    RequireInventoryRead,
    RequireInventoryWrite,
    handle_service_error,
)
from .schemas import ItemGroupCreateRequest, ItemGroupUpdateRequest

router = APIRouter(prefix="/item-groups", tags=["inventory"])


@router.get("", dependencies=[RequireInventoryRead])
async def list_item_groups(
    search: str | None = None,
    parent_item_group: str | None = None,
    is_group: bool | None = None,
    sort_by: str = Query(default="item_group_name"),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    service: ItemGroupService = Depends(get_item_group_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List item groups with optional filtering."""
    filters = ItemGroupFilters(
        search=search,
        parent_item_group=parent_item_group,
        is_group=is_group,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    pagination = PaginationParams(offset=offset, limit=limit)

    result = service.list_item_groups(filters, pagination)

    return {
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "item_groups": [
            {
                "id": group.id,
                "erpnext_id": group.erpnext_id,
                "item_group_name": group.item_group_name,
                "parent_item_group": group.parent_item_group,
                "is_group": group.is_group,
                "lft": group.lft,
                "rgt": group.rgt,
            }
            for group in result.items
        ],
    }


@router.get("/tree", dependencies=[RequireInventoryRead])
async def get_item_group_tree(
    service: ItemGroupService = Depends(get_item_group_service),
) -> Dict[str, Any]:
    """Get item group hierarchy as a tree structure."""
    root_groups = service.get_root_groups()

    def build_tree(groups):
        """Recursively build tree structure."""
        tree = []
        for group in groups:
            children = service.get_child_groups(group.item_group_name)
            node = {
                "id": group.id,
                "item_group_name": group.item_group_name,
                "is_group": group.is_group,
                "children": build_tree(children) if children else [],
            }
            tree.append(node)
        return tree

    return {"tree": build_tree(root_groups)}


@router.get("/{group_id}", dependencies=[RequireInventoryRead])
async def get_item_group(
    group_id: int,
    service: ItemGroupService = Depends(get_item_group_service),
) -> Dict[str, Any]:
    """Get an item group by ID."""
    try:
        group = service.get_item_group(group_id)
    except NotFoundError as e:
        handle_service_error(e)

    return {
        "id": group.id,
        "erpnext_id": group.erpnext_id,
        "item_group_name": group.item_group_name,
        "parent_item_group": group.parent_item_group,
        "is_group": group.is_group,
        "lft": group.lft,
        "rgt": group.rgt,
    }


@router.post("", dependencies=[RequireInventoryWrite])
async def create_item_group(
    payload: ItemGroupCreateRequest,
    service: ItemGroupService = Depends(get_item_group_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new item group."""
    try:
        data = ItemGroupCreateData(
            item_group_name=payload.item_group_name,
            parent_item_group=payload.parent_item_group,
            is_group=payload.is_group,
            lft=payload.lft,
            rgt=payload.rgt,
        )
        group = service.create_item_group(data)
        db.commit()
    except (ValidationError, ConflictError) as e:
        db.rollback()
        handle_service_error(e)

    return {"id": group.id, "item_group_name": group.item_group_name}


@router.patch("/{group_id}", dependencies=[RequireInventoryWrite])
async def update_item_group(
    group_id: int,
    payload: ItemGroupUpdateRequest,
    service: ItemGroupService = Depends(get_item_group_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update an existing item group."""
    try:
        data = ItemGroupUpdateData(
            item_group_name=payload.item_group_name,
            parent_item_group=payload.parent_item_group,
            is_group=payload.is_group,
            lft=payload.lft,
            rgt=payload.rgt,
        )
        group = service.update_item_group(group_id, data)
        db.commit()
    except (NotFoundError, ValidationError, ConflictError) as e:
        db.rollback()
        handle_service_error(e)

    return {"id": group.id, "item_group_name": group.item_group_name}


@router.delete("/{group_id}", dependencies=[RequireInventoryWrite])
async def delete_item_group(
    group_id: int,
    service: ItemGroupService = Depends(get_item_group_service),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete an item group."""
    try:
        service.delete_item_group(group_id)
        db.commit()
    except (NotFoundError, ValidationError) as e:
        db.rollback()
        handle_service_error(e)

    return {"status": "deleted", "item_group_id": group_id}
