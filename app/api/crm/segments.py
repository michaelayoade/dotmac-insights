"""
Segments API - Contact segmentation management.

Manage static and dynamic contact segments for targeted marketing.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Any
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Principal, get_current_principal
from app.utils.company_context import get_company_id
from app.services.crm.segments import SegmentService
from app.services.crm.segment_types import (
    SegmentFilters,
    SegmentCreateData,
    SegmentUpdateData,
    SegmentRuleData,
    SegmentMembershipData,
)

router = APIRouter(prefix="/segments", tags=["crm-segments"])


def get_segment_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> SegmentService:
    """Create a SegmentService instance."""
    company_id = get_company_id(principal)
    return SegmentService(db, company_id, principal.user_id)


# ============= SCHEMAS =============
class SegmentRule(BaseModel):
    """A rule for dynamic segments."""

    field: str
    operator: str  # equals, not_equals, contains, gt, lt, gte, lte, in, not_in
    value: Any
    conjunction: str = "AND"


class SegmentCreate(BaseModel):
    """Create a segment."""

    name: str
    description: Optional[str] = None
    segment_type: str = "static"  # static, dynamic
    rules: List[SegmentRule] = Field(default_factory=list)
    rule_conjunction: str = "AND"
    auto_refresh: bool = True
    refresh_interval_hours: int = 24
    is_active: bool = True
    party_ids: List[int] = Field(default_factory=list)  # For static segments


class SegmentUpdate(BaseModel):
    """Update a segment."""

    name: Optional[str] = None
    description: Optional[str] = None
    rules: Optional[List[SegmentRule]] = None
    rule_conjunction: Optional[str] = None
    auto_refresh: Optional[bool] = None
    refresh_interval_hours: Optional[int] = None
    is_active: Optional[bool] = None


class MembershipRequest(BaseModel):
    """Add/remove members from a segment."""

    party_ids: List[int]
    source: str = "manual"


# ============= SEGMENT ENDPOINTS =============
@router.get("")
async def list_segments(
    search: Optional[str] = None,
    segment_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    service: SegmentService = Depends(get_segment_service),
):
    """List segments."""
    filters = SegmentFilters(
        search=search,
        segment_type=segment_type,
        is_active=is_active,
    )
    segments, total = service.list_segments(filters, skip, limit)
    return {
        "items": [_serialize_segment(s) for s in segments],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/summary")
async def get_summary(
    service: SegmentService = Depends(get_segment_service),
):
    """Get segments summary."""
    summary = service.get_summary()
    return {
        "total_segments": summary.total_segments,
        "active_segments": summary.active_segments,
        "static_segments": summary.static_segments,
        "dynamic_segments": summary.dynamic_segments,
        "total_members": summary.total_members,
        "avg_segment_size": summary.avg_segment_size,
        "largest_segment_name": summary.largest_segment_name,
        "largest_segment_size": summary.largest_segment_size,
    }


@router.post("")
async def create_segment(
    data: SegmentCreate,
    service: SegmentService = Depends(get_segment_service),
    db: Session = Depends(get_db),
):
    """Create a segment."""
    rules = [
        SegmentRuleData(
            field=r.field,
            operator=r.operator,
            value=r.value,
            conjunction=r.conjunction,
        )
        for r in data.rules
    ]
    create_data = SegmentCreateData(
        name=data.name,
        description=data.description,
        segment_type=data.segment_type,
        rules=rules,
        rule_conjunction=data.rule_conjunction,
        auto_refresh=data.auto_refresh,
        refresh_interval_hours=data.refresh_interval_hours,
        is_active=data.is_active,
        party_ids=data.party_ids,
    )
    segment = service.create_segment(create_data)
    db.commit()
    return _serialize_segment(segment)


@router.get("/{segment_id}")
async def get_segment(
    segment_id: int,
    service: SegmentService = Depends(get_segment_service),
):
    """Get a segment by ID."""
    segment = service.get_segment(segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    return _serialize_segment(segment)


@router.patch("/{segment_id}")
async def update_segment(
    segment_id: int,
    data: SegmentUpdate,
    service: SegmentService = Depends(get_segment_service),
    db: Session = Depends(get_db),
):
    """Update a segment."""
    rules = None
    if data.rules is not None:
        rules = [
            SegmentRuleData(
                field=r.field,
                operator=r.operator,
                value=r.value,
                conjunction=r.conjunction,
            )
            for r in data.rules
        ]
    update_data = SegmentUpdateData(
        name=data.name,
        description=data.description,
        rules=rules,
        rule_conjunction=data.rule_conjunction,
        auto_refresh=data.auto_refresh,
        refresh_interval_hours=data.refresh_interval_hours,
        is_active=data.is_active,
    )
    segment = service.update_segment(segment_id, update_data)
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    db.commit()
    return _serialize_segment(segment)


@router.delete("/{segment_id}")
async def delete_segment(
    segment_id: int,
    service: SegmentService = Depends(get_segment_service),
    db: Session = Depends(get_db),
):
    """Delete a segment."""
    if not service.delete_segment(segment_id):
        raise HTTPException(status_code=404, detail="Segment not found")
    db.commit()
    return {"success": True}


@router.post("/{segment_id}/refresh")
async def refresh_segment(
    segment_id: int,
    service: SegmentService = Depends(get_segment_service),
    db: Session = Depends(get_db),
):
    """Refresh a dynamic segment."""
    member_count = service.refresh_segment(segment_id)
    db.commit()
    return {"success": True, "member_count": member_count}


@router.get("/{segment_id}/analytics")
async def get_segment_analytics(
    segment_id: int,
    service: SegmentService = Depends(get_segment_service),
):
    """Get analytics for a segment."""
    analytics = service.get_segment_analytics(segment_id)
    if not analytics:
        raise HTTPException(status_code=404, detail="Segment not found")
    return {
        "segment_id": analytics.segment_id,
        "segment_name": analytics.segment_name,
        "segment_type": analytics.segment_type,
        "member_count": analytics.member_count,
        "member_growth_30d": analytics.member_growth_30d,
        "member_growth_rate": analytics.member_growth_rate,
        "party_type_breakdown": analytics.party_type_breakdown,
        "engagement_score_distribution": analytics.engagement_score_distribution,
        "preferred_channel_breakdown": analytics.preferred_channel_breakdown,
        "avg_engagement_score": analytics.avg_engagement_score,
        "contacts_with_email": analytics.contacts_with_email,
        "contacts_with_phone": analytics.contacts_with_phone,
        "do_not_contact_count": analytics.do_not_contact_count,
        "created_at": analytics.created_at.isoformat() if analytics.created_at else None,
        "last_refreshed_at": analytics.last_refreshed_at.isoformat() if analytics.last_refreshed_at else None,
        "next_refresh_at": analytics.next_refresh_at.isoformat() if analytics.next_refresh_at else None,
    }


# ============= MEMBERSHIP ENDPOINTS =============
@router.get("/{segment_id}/members")
async def list_members(
    segment_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    service: SegmentService = Depends(get_segment_service),
):
    """List members of a segment."""
    members, total = service.get_members(segment_id, skip, limit)
    return {
        "items": [_serialize_party(p) for p in members],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.post("/{segment_id}/members")
async def add_members(
    segment_id: int,
    data: MembershipRequest,
    service: SegmentService = Depends(get_segment_service),
    db: Session = Depends(get_db),
):
    """Add members to a static segment."""
    membership_data = SegmentMembershipData(
        party_ids=data.party_ids,
        source=data.source,
    )
    memberships = service.add_members(segment_id, membership_data)
    db.commit()
    return {"added": len(memberships)}


@router.delete("/{segment_id}/members")
async def remove_members(
    segment_id: int,
    data: MembershipRequest,
    service: SegmentService = Depends(get_segment_service),
    db: Session = Depends(get_db),
):
    """Remove members from a static segment."""
    membership_data = SegmentMembershipData(
        party_ids=data.party_ids,
        source=data.source,
    )
    removed = service.remove_members(segment_id, membership_data)
    db.commit()
    return {"removed": removed}


@router.get("/{segment_id}/members/{party_id}/check")
async def check_membership(
    segment_id: int,
    party_id: int,
    service: SegmentService = Depends(get_segment_service),
):
    """Check if a party is a member of a segment."""
    is_member = service.is_member(segment_id, party_id)
    return {"is_member": is_member}


# ============= SERIALIZERS =============
def _serialize_segment(segment) -> dict:
    """Serialize a segment."""
    return {
        "id": segment.id,
        "name": segment.name,
        "description": segment.description,
        "segment_type": segment.segment_type,
        "rules": segment.rules,
        "rule_conjunction": segment.rule_conjunction,
        "auto_refresh": segment.auto_refresh,
        "refresh_interval_hours": segment.refresh_interval_hours,
        "is_active": segment.is_active,
        "created_at": segment.created_at.isoformat() if segment.created_at else None,
        "updated_at": segment.updated_at.isoformat() if segment.updated_at else None,
        "last_refreshed_at": segment.last_refreshed_at.isoformat() if segment.last_refreshed_at else None,
        "next_refresh_at": segment.next_refresh_at.isoformat() if segment.next_refresh_at else None,
    }


def _serialize_party(party) -> dict:
    """Serialize a party for membership list."""
    return {
        "id": party.id,
        "name": party.name,
        "display_name": party.display_name,
        "party_type": party.party_type,
        "email": party.email,
        "phone": party.phone,
        "engagement_score": party.engagement_score,
    }
