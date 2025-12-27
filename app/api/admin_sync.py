"""Admin Sync API endpoints for DLQ, cursors, outbound logs, and scheduling.

Provides management operations for:
- DLQ (Dead Letter Queue): View/retry/resolve failed sync records
- Cursors: View/reset sync cursors per source and entity
- Outbound Logs: View outbound sync operations
- Schedules: CRUD for sync schedules (requires SyncSchedule model)
- Dashboard: Aggregated sync statistics
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from enum import Enum

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from app.auth import Require
from app.database import get_db
from app.models.sync_cursor import SyncCursor, FailedSyncRecord
from app.models.sync_log import SyncLog, SyncSource, SyncStatus
from app.models.sync_schedule import SyncSchedule
from app.models.outbound_sync import OutboundSyncLog, SyncStatus as OutboundStatus
from app.utils.datetime_utils import utc_now

logger = structlog.get_logger()
router = APIRouter(prefix="/admin/sync", tags=["admin-sync"])


# ============================================================================
# Pydantic Schemas - DLQ
# ============================================================================


class DlqRecordResponse(BaseModel):
    id: int
    source: str
    entity_type: str
    external_id: Optional[str]
    error_message: str
    error_type: Optional[str]
    retry_count: int
    max_retries: int
    is_resolved: bool
    resolution_notes: Optional[str]
    created_at: datetime
    last_retry_at: Optional[datetime]
    resolved_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class DlqDetailResponse(DlqRecordResponse):
    payload: str


class DlqResolveRequest(BaseModel):
    notes: Optional[str] = None


class DlqBatchRetryRequest(BaseModel):
    source: Optional[str] = None
    entity_type: Optional[str] = None
    ids: Optional[List[int]] = None


class DlqStatsResponse(BaseModel):
    total: int
    unresolved: int
    resolved: int
    pending_retry: int
    max_retries_reached: int
    by_source: Dict[str, int]
    by_entity: Dict[str, int]


class DlqListResponse(BaseModel):
    items: List[DlqRecordResponse]
    total: int


# ============================================================================
# Pydantic Schemas - Cursors
# ============================================================================


class CursorResponse(BaseModel):
    id: int
    source: str
    entity_type: str
    last_sync_timestamp: Optional[datetime]
    last_modified_at: Optional[datetime]
    last_id: Optional[str]
    cursor_value: Optional[str]
    records_synced: int
    last_sync_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CursorResetRequest(BaseModel):
    reason: Optional[str] = None


class CursorUpdateRequest(BaseModel):
    last_sync_timestamp: Optional[datetime] = None
    last_modified_at: Optional[datetime] = None
    last_id: Optional[str] = None
    cursor_value: Optional[str] = None


class CursorHealthResponse(BaseModel):
    total_cursors: int
    healthy: int
    stale: int  # Not synced in >24h
    critical: int  # Not synced in >72h
    stale_cursors: List[CursorResponse]


class CursorListResponse(BaseModel):
    items: List[CursorResponse]
    total: int


# ============================================================================
# Pydantic Schemas - Outbound
# ============================================================================


class OutboundLogResponse(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    target_system: str
    operation: str
    status: str
    external_id: Optional[str]
    error_message: Optional[str]
    retry_count: int
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class OutboundDetailResponse(OutboundLogResponse):
    request_payload: Optional[dict]
    response_payload: Optional[dict]
    idempotency_key: Optional[str]
    payload_hash: Optional[str]


class OutboundStatsResponse(BaseModel):
    total: int
    success: int
    failed: int
    pending: int
    skipped: int
    by_target: Dict[str, Dict[str, int]]
    by_entity: Dict[str, Dict[str, int]]


class OutboundListResponse(BaseModel):
    items: List[OutboundLogResponse]
    total: int


# ============================================================================
# Pydantic Schemas - Dashboard
# ============================================================================


class SyncSourceStatus(BaseModel):
    source: str
    last_sync_at: Optional[datetime]
    last_status: Optional[str]
    last_entity: Optional[str]
    total_syncs_today: int
    success_rate: float
    records_synced_today: int
    failed_records: int


class DashboardResponse(BaseModel):
    total_syncs_today: int
    success_rate: float
    total_failed_records: int
    active_schedules: int
    sources: List[SyncSourceStatus]
    recent_logs: List[Dict[str, Any]]


class EntityStatusResponse(BaseModel):
    source: str
    entity_type: str
    last_sync_at: Optional[datetime]
    records_synced: int
    cursor_value: Optional[str]
    failed_count: int


# ============================================================================
# DLQ Endpoints
# ============================================================================


@router.get(
    "/dlq",
    response_model=DlqListResponse,
    dependencies=[Depends(Require("sync:read"))],
)
async def list_dlq_records(
    source: Optional[str] = None,
    entity_type: Optional[str] = None,
    is_resolved: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List failed sync records from the Dead Letter Queue."""
    query = db.query(FailedSyncRecord)

    if source:
        try:
            source_enum = SyncSource(source)
            query = query.filter(FailedSyncRecord.source == source_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid source: {source}")

    if entity_type:
        query = query.filter(FailedSyncRecord.entity_type == entity_type)

    if is_resolved is not None:
        query = query.filter(FailedSyncRecord.is_resolved == is_resolved)

    total = query.count()
    records = query.order_by(FailedSyncRecord.created_at.desc()).offset(offset).limit(limit).all()

    return DlqListResponse(
        items=[
            DlqRecordResponse(
                id=r.id,
                source=r.source.value,
                entity_type=r.entity_type,
                external_id=r.external_id,
                error_message=r.error_message,
                error_type=r.error_type,
                retry_count=r.retry_count,
                max_retries=r.max_retries,
                is_resolved=r.is_resolved,
                resolution_notes=r.resolution_notes,
                created_at=r.created_at,
                last_retry_at=r.last_retry_at,
                resolved_at=r.resolved_at,
            )
            for r in records
        ],
        total=total,
    )


@router.get(
    "/dlq/stats",
    response_model=DlqStatsResponse,
    dependencies=[Depends(Require("sync:read"))],
)
async def get_dlq_stats(db: Session = Depends(get_db)):
    """Get DLQ statistics."""
    total = db.query(FailedSyncRecord).count()
    unresolved = db.query(FailedSyncRecord).filter(FailedSyncRecord.is_resolved == False).count()
    resolved = db.query(FailedSyncRecord).filter(FailedSyncRecord.is_resolved == True).count()
    pending_retry = db.query(FailedSyncRecord).filter(
        and_(
            FailedSyncRecord.is_resolved == False,
            FailedSyncRecord.retry_count < FailedSyncRecord.max_retries,
        )
    ).count()
    max_retries_reached = db.query(FailedSyncRecord).filter(
        and_(
            FailedSyncRecord.is_resolved == False,
            FailedSyncRecord.retry_count >= FailedSyncRecord.max_retries,
        )
    ).count()

    # Group by source
    by_source_query = (
        db.query(FailedSyncRecord.source, func.count(FailedSyncRecord.id))
        .filter(FailedSyncRecord.is_resolved == False)
        .group_by(FailedSyncRecord.source)
        .all()
    )
    by_source = {str(s.value): c for s, c in by_source_query}

    # Group by entity
    by_entity_query = (
        db.query(FailedSyncRecord.entity_type, func.count(FailedSyncRecord.id))
        .filter(FailedSyncRecord.is_resolved == False)
        .group_by(FailedSyncRecord.entity_type)
        .all()
    )
    by_entity = {e: c for e, c in by_entity_query}

    return DlqStatsResponse(
        total=total,
        unresolved=unresolved,
        resolved=resolved,
        pending_retry=pending_retry,
        max_retries_reached=max_retries_reached,
        by_source=by_source,
        by_entity=by_entity,
    )


@router.get(
    "/dlq/{record_id}",
    response_model=DlqDetailResponse,
    dependencies=[Depends(Require("sync:read"))],
)
async def get_dlq_record(record_id: int, db: Session = Depends(get_db)):
    """Get a specific DLQ record with full payload."""
    record = db.query(FailedSyncRecord).filter(FailedSyncRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="DLQ record not found")

    return DlqDetailResponse(
        id=record.id,
        source=record.source.value,
        entity_type=record.entity_type,
        external_id=record.external_id,
        error_message=record.error_message,
        error_type=record.error_type,
        retry_count=record.retry_count,
        max_retries=record.max_retries,
        is_resolved=record.is_resolved,
        resolution_notes=record.resolution_notes,
        created_at=record.created_at,
        last_retry_at=record.last_retry_at,
        resolved_at=record.resolved_at,
        payload=record.payload,
    )


@router.post(
    "/dlq/{record_id}/retry",
    dependencies=[Depends(Require("sync:write"))],
)
async def retry_dlq_record(record_id: int, db: Session = Depends(get_db)):
    """Retry a failed sync record."""
    record = db.query(FailedSyncRecord).filter(FailedSyncRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="DLQ record not found")

    if record.is_resolved:
        raise HTTPException(status_code=400, detail="Record is already resolved")

    # Mark retry attempt
    record.mark_retry()
    record.next_retry_at = utc_now()  # Schedule for immediate retry
    db.commit()

    logger.info("dlq_record_retry_requested", record_id=record_id, source=record.source.value)

    return {
        "status": "retry_scheduled",
        "record_id": record_id,
        "retry_count": record.retry_count,
    }


@router.post(
    "/dlq/retry-batch",
    dependencies=[Depends(Require("sync:write"))],
)
async def retry_dlq_batch(request: DlqBatchRetryRequest, db: Session = Depends(get_db)):
    """Retry multiple failed sync records."""
    query = db.query(FailedSyncRecord).filter(FailedSyncRecord.is_resolved == False)

    if request.ids:
        query = query.filter(FailedSyncRecord.id.in_(request.ids))
    else:
        if request.source:
            try:
                source_enum = SyncSource(request.source)
                query = query.filter(FailedSyncRecord.source == source_enum)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid source: {request.source}")
        if request.entity_type:
            query = query.filter(FailedSyncRecord.entity_type == request.entity_type)

    # Only retry records that can still be retried
    query = query.filter(FailedSyncRecord.retry_count < FailedSyncRecord.max_retries)

    records = query.all()
    count = 0
    for record in records:
        record.mark_retry()
        record.next_retry_at = utc_now()
        count += 1

    db.commit()

    logger.info("dlq_batch_retry_requested", count=count)

    return {"status": "batch_retry_scheduled", "count": count}


@router.patch(
    "/dlq/{record_id}/resolve",
    dependencies=[Depends(Require("sync:write"))],
)
async def resolve_dlq_record(
    record_id: int,
    request: DlqResolveRequest,
    db: Session = Depends(get_db),
):
    """Mark a DLQ record as resolved."""
    record = db.query(FailedSyncRecord).filter(FailedSyncRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="DLQ record not found")

    if record.is_resolved:
        raise HTTPException(status_code=400, detail="Record is already resolved")

    record.mark_resolved(notes=request.notes)
    db.commit()

    logger.info("dlq_record_resolved", record_id=record_id)

    return {"status": "resolved", "record_id": record_id}


@router.delete(
    "/dlq/{record_id}",
    dependencies=[Depends(Require("sync:write"))],
)
async def delete_dlq_record(record_id: int, db: Session = Depends(get_db)):
    """Delete a DLQ record."""
    record = db.query(FailedSyncRecord).filter(FailedSyncRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="DLQ record not found")

    db.delete(record)
    db.commit()

    logger.info("dlq_record_deleted", record_id=record_id)

    return {"status": "deleted", "record_id": record_id}


# ============================================================================
# Cursor Endpoints
# ============================================================================


@router.get(
    "/cursors",
    response_model=CursorListResponse,
    dependencies=[Depends(Require("sync:read"))],
)
async def list_cursors(
    source: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List all sync cursors."""
    query = db.query(SyncCursor)

    if source:
        try:
            source_enum = SyncSource(source)
            query = query.filter(SyncCursor.source == source_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid source: {source}")

    total = query.count()
    cursors = query.order_by(SyncCursor.source, SyncCursor.entity_type).offset(offset).limit(limit).all()

    return CursorListResponse(
        items=[
            CursorResponse(
                id=c.id,
                source=c.source.value,
                entity_type=c.entity_type,
                last_sync_timestamp=c.last_sync_timestamp,
                last_modified_at=c.last_modified_at,
                last_id=c.last_id,
                cursor_value=c.cursor_value,
                records_synced=c.records_synced,
                last_sync_at=c.last_sync_at,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in cursors
        ],
        total=total,
    )


@router.get(
    "/cursors/health",
    response_model=CursorHealthResponse,
    dependencies=[Depends(Require("sync:read"))],
)
async def get_cursor_health(db: Session = Depends(get_db)):
    """Check health of sync cursors."""
    now = utc_now()
    stale_threshold = now - timedelta(hours=24)
    critical_threshold = now - timedelta(hours=72)

    all_cursors = db.query(SyncCursor).all()
    total = len(all_cursors)

    stale_cursors = []
    healthy = 0
    stale = 0
    critical = 0

    for cursor in all_cursors:
        if not cursor.last_sync_at:
            critical += 1
            stale_cursors.append(cursor)
        elif cursor.last_sync_at < critical_threshold:
            critical += 1
            stale_cursors.append(cursor)
        elif cursor.last_sync_at < stale_threshold:
            stale += 1
            stale_cursors.append(cursor)
        else:
            healthy += 1

    return CursorHealthResponse(
        total_cursors=total,
        healthy=healthy,
        stale=stale,
        critical=critical,
        stale_cursors=[
            CursorResponse(
                id=c.id,
                source=c.source.value,
                entity_type=c.entity_type,
                last_sync_timestamp=c.last_sync_timestamp,
                last_modified_at=c.last_modified_at,
                last_id=c.last_id,
                cursor_value=c.cursor_value,
                records_synced=c.records_synced,
                last_sync_at=c.last_sync_at,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in stale_cursors
        ],
    )


@router.get(
    "/cursors/{source}/{entity_type}",
    response_model=CursorResponse,
    dependencies=[Depends(Require("sync:read"))],
)
async def get_cursor(source: str, entity_type: str, db: Session = Depends(get_db)):
    """Get a specific sync cursor."""
    try:
        source_enum = SyncSource(source)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid source: {source}")

    cursor = (
        db.query(SyncCursor)
        .filter(SyncCursor.source == source_enum, SyncCursor.entity_type == entity_type)
        .first()
    )
    if not cursor:
        raise HTTPException(status_code=404, detail="Cursor not found")

    return CursorResponse(
        id=cursor.id,
        source=cursor.source.value,
        entity_type=cursor.entity_type,
        last_sync_timestamp=cursor.last_sync_timestamp,
        last_modified_at=cursor.last_modified_at,
        last_id=cursor.last_id,
        cursor_value=cursor.cursor_value,
        records_synced=cursor.records_synced,
        last_sync_at=cursor.last_sync_at,
        created_at=cursor.created_at,
        updated_at=cursor.updated_at,
    )


@router.post(
    "/cursors/{source}/{entity_type}/reset",
    dependencies=[Depends(Require("sync:write"))],
)
async def reset_cursor(
    source: str,
    entity_type: str,
    request: CursorResetRequest,
    db: Session = Depends(get_db),
):
    """Reset a sync cursor for full re-sync."""
    try:
        source_enum = SyncSource(source)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid source: {source}")

    cursor = (
        db.query(SyncCursor)
        .filter(SyncCursor.source == source_enum, SyncCursor.entity_type == entity_type)
        .first()
    )
    if not cursor:
        raise HTTPException(status_code=404, detail="Cursor not found")

    old_values = {
        "last_sync_timestamp": cursor.last_sync_timestamp,
        "last_modified_at": cursor.last_modified_at,
        "last_id": cursor.last_id,
        "records_synced": cursor.records_synced,
    }

    cursor.reset()
    db.commit()

    logger.info(
        "cursor_reset",
        source=source,
        entity_type=entity_type,
        reason=request.reason,
        old_values=str(old_values),
    )

    return {
        "status": "reset",
        "source": source,
        "entity_type": entity_type,
        "reason": request.reason,
    }


@router.patch(
    "/cursors/{source}/{entity_type}",
    response_model=CursorResponse,
    dependencies=[Depends(Require("sync:write"))],
)
async def update_cursor(
    source: str,
    entity_type: str,
    request: CursorUpdateRequest,
    db: Session = Depends(get_db),
):
    """Manually update a sync cursor."""
    try:
        source_enum = SyncSource(source)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid source: {source}")

    cursor = (
        db.query(SyncCursor)
        .filter(SyncCursor.source == source_enum, SyncCursor.entity_type == entity_type)
        .first()
    )
    if not cursor:
        raise HTTPException(status_code=404, detail="Cursor not found")

    if request.last_sync_timestamp is not None:
        cursor.last_sync_timestamp = request.last_sync_timestamp
    if request.last_modified_at is not None:
        cursor.last_modified_at = request.last_modified_at
    if request.last_id is not None:
        cursor.last_id = request.last_id
    if request.cursor_value is not None:
        cursor.cursor_value = request.cursor_value

    db.commit()
    db.refresh(cursor)

    logger.info("cursor_updated", source=source, entity_type=entity_type)

    return CursorResponse(
        id=cursor.id,
        source=cursor.source.value,
        entity_type=cursor.entity_type,
        last_sync_timestamp=cursor.last_sync_timestamp,
        last_modified_at=cursor.last_modified_at,
        last_id=cursor.last_id,
        cursor_value=cursor.cursor_value,
        records_synced=cursor.records_synced,
        last_sync_at=cursor.last_sync_at,
        created_at=cursor.created_at,
        updated_at=cursor.updated_at,
    )


# ============================================================================
# Outbound Log Endpoints
# ============================================================================


@router.get(
    "/outbound",
    response_model=OutboundListResponse,
    dependencies=[Depends(Require("sync:read"))],
)
async def list_outbound_logs(
    target_system: Optional[str] = None,
    entity_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List outbound sync logs."""
    query = db.query(OutboundSyncLog)

    if target_system:
        query = query.filter(OutboundSyncLog.target_system == target_system)
    if entity_type:
        query = query.filter(OutboundSyncLog.entity_type == entity_type)
    if status:
        query = query.filter(OutboundSyncLog.status == status)

    total = query.count()
    logs = query.order_by(OutboundSyncLog.created_at.desc()).offset(offset).limit(limit).all()

    return OutboundListResponse(
        items=[
            OutboundLogResponse(
                id=log.id,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                target_system=log.target_system,
                operation=log.operation,
                status=log.status,
                external_id=log.external_id,
                error_message=log.error_message,
                retry_count=log.retry_count,
                created_at=log.created_at,
                completed_at=log.completed_at,
            )
            for log in logs
        ],
        total=total,
    )


@router.get(
    "/outbound/stats",
    response_model=OutboundStatsResponse,
    dependencies=[Depends(Require("sync:read"))],
)
async def get_outbound_stats(db: Session = Depends(get_db)):
    """Get outbound sync statistics."""
    total = db.query(OutboundSyncLog).count()
    success = db.query(OutboundSyncLog).filter(OutboundSyncLog.status == "success").count()
    failed = db.query(OutboundSyncLog).filter(OutboundSyncLog.status == "failed").count()
    pending = db.query(OutboundSyncLog).filter(OutboundSyncLog.status == "pending").count()
    skipped = db.query(OutboundSyncLog).filter(OutboundSyncLog.status == "skipped").count()

    # By target system
    by_target_query = (
        db.query(
            OutboundSyncLog.target_system,
            OutboundSyncLog.status,
            func.count(OutboundSyncLog.id),
        )
        .group_by(OutboundSyncLog.target_system, OutboundSyncLog.status)
        .all()
    )
    by_target: Dict[str, Dict[str, int]] = {}
    for target, stat, count in by_target_query:
        if target not in by_target:
            by_target[target] = {}
        by_target[target][stat] = count

    # By entity type
    by_entity_query = (
        db.query(
            OutboundSyncLog.entity_type,
            OutboundSyncLog.status,
            func.count(OutboundSyncLog.id),
        )
        .group_by(OutboundSyncLog.entity_type, OutboundSyncLog.status)
        .all()
    )
    by_entity: Dict[str, Dict[str, int]] = {}
    for entity, stat, count in by_entity_query:
        if entity not in by_entity:
            by_entity[entity] = {}
        by_entity[entity][stat] = count

    return OutboundStatsResponse(
        total=total,
        success=success,
        failed=failed,
        pending=pending,
        skipped=skipped,
        by_target=by_target,
        by_entity=by_entity,
    )


@router.get(
    "/outbound/{log_id}",
    response_model=OutboundDetailResponse,
    dependencies=[Depends(Require("sync:read"))],
)
async def get_outbound_log(log_id: int, db: Session = Depends(get_db)):
    """Get detailed outbound sync log."""
    log = db.query(OutboundSyncLog).filter(OutboundSyncLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Outbound log not found")

    return OutboundDetailResponse(
        id=log.id,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        target_system=log.target_system,
        operation=log.operation,
        status=log.status,
        external_id=log.external_id,
        error_message=log.error_message,
        retry_count=log.retry_count,
        created_at=log.created_at,
        completed_at=log.completed_at,
        request_payload=log.request_payload,
        response_payload=log.response_payload,
        idempotency_key=log.idempotency_key,
        payload_hash=log.payload_hash,
    )


@router.post(
    "/outbound/{log_id}/retry",
    dependencies=[Depends(Require("sync:write"))],
)
async def retry_outbound_log(log_id: int, db: Session = Depends(get_db)):
    """Retry a failed outbound sync."""
    log = db.query(OutboundSyncLog).filter(OutboundSyncLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Outbound log not found")

    if log.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed logs can be retried")

    # Reset status to pending for retry
    log.status = "pending"
    log.next_retry_at = utc_now()
    db.commit()

    logger.info("outbound_retry_requested", log_id=log_id, entity_type=log.entity_type)

    return {"status": "retry_scheduled", "log_id": log_id}


# ============================================================================
# Dashboard Endpoints
# ============================================================================


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    dependencies=[Depends(Require("sync:read"))],
)
async def get_sync_dashboard(db: Session = Depends(get_db)):
    """Get aggregated sync dashboard data."""
    today = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Total syncs today
    total_syncs_today = (
        db.query(SyncLog)
        .filter(SyncLog.started_at >= today)
        .count()
    )

    # Success rate
    successful_today = (
        db.query(SyncLog)
        .filter(SyncLog.started_at >= today, SyncLog.status == SyncStatus.COMPLETED)
        .count()
    )
    success_rate = (successful_today / total_syncs_today * 100) if total_syncs_today > 0 else 0

    # Total failed records
    total_failed_records = (
        db.query(FailedSyncRecord)
        .filter(FailedSyncRecord.is_resolved == False)
        .count()
    )

    # Active schedules
    active_schedules = (
        db.query(SyncSchedule)
        .filter(SyncSchedule.is_enabled == True)
        .count()
    )

    # Per-source status
    sources_status = []
    for source in SyncSource:
        last_sync = (
            db.query(SyncLog)
            .filter(SyncLog.source == source)
            .order_by(SyncLog.started_at.desc())
            .first()
        )

        source_syncs_today = (
            db.query(SyncLog)
            .filter(SyncLog.source == source, SyncLog.started_at >= today)
            .count()
        )
        source_success_today = (
            db.query(SyncLog)
            .filter(
                SyncLog.source == source,
                SyncLog.started_at >= today,
                SyncLog.status == SyncStatus.COMPLETED,
            )
            .count()
        )
        source_records_today = (
            db.query(func.coalesce(func.sum(SyncLog.records_created + SyncLog.records_updated), 0))
            .filter(SyncLog.source == source, SyncLog.started_at >= today)
            .scalar()
        ) or 0

        source_failed = (
            db.query(FailedSyncRecord)
            .filter(FailedSyncRecord.source == source, FailedSyncRecord.is_resolved == False)
            .count()
        )

        sources_status.append(
            SyncSourceStatus(
                source=source.value,
                last_sync_at=last_sync.started_at if last_sync else None,
                last_status=last_sync.status.value if last_sync else None,
                last_entity=last_sync.entity_type if last_sync else None,
                total_syncs_today=source_syncs_today,
                success_rate=(source_success_today / source_syncs_today * 100) if source_syncs_today > 0 else 0,
                records_synced_today=source_records_today,
                failed_records=source_failed,
            )
        )

    # Recent logs
    recent_logs = (
        db.query(SyncLog)
        .order_by(SyncLog.started_at.desc())
        .limit(5)
        .all()
    )
    recent_logs_data = [
        {
            "id": log.id,
            "source": log.source.value,
            "entity_type": log.entity_type,
            "status": log.status.value,
            "started_at": log.started_at.isoformat() if log.started_at else None,
            "records_created": log.records_created,
            "records_updated": log.records_updated,
        }
        for log in recent_logs
    ]

    return DashboardResponse(
        total_syncs_today=total_syncs_today,
        success_rate=round(success_rate, 1),
        total_failed_records=total_failed_records,
        active_schedules=active_schedules,
        sources=sources_status,
        recent_logs=recent_logs_data,
    )


@router.get(
    "/entities",
    response_model=List[EntityStatusResponse],
    dependencies=[Depends(Require("sync:read"))],
)
async def get_entity_status(db: Session = Depends(get_db)):
    """Get entity-level sync status combining cursors and failed counts."""
    cursors = db.query(SyncCursor).all()

    result = []
    for cursor in cursors:
        failed_count = (
            db.query(FailedSyncRecord)
            .filter(
                FailedSyncRecord.source == cursor.source,
                FailedSyncRecord.entity_type == cursor.entity_type,
                FailedSyncRecord.is_resolved == False,
            )
            .count()
        )

        result.append(
            EntityStatusResponse(
                source=cursor.source.value,
                entity_type=cursor.entity_type,
                last_sync_at=cursor.last_sync_at,
                records_synced=cursor.records_synced,
                cursor_value=cursor.cursor_value[:100] if cursor.cursor_value else None,
                failed_count=failed_count,
            )
        )

    return result


# ============================================================================
# Pydantic Schemas - Schedules
# ============================================================================


class ScheduleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    task_name: str
    cron_expression: str
    kwargs: Optional[dict]
    is_enabled: bool
    is_system: bool
    last_run_at: Optional[datetime]
    last_run_status: Optional[str]
    last_error: Optional[str]
    next_run_at: Optional[datetime]
    run_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScheduleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    task_name: str = Field(..., min_length=1, max_length=255)
    cron_expression: str = Field(..., min_length=1, max_length=100)
    kwargs: Optional[dict] = None
    is_enabled: bool = True


class ScheduleUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    task_name: Optional[str] = Field(None, min_length=1, max_length=255)
    cron_expression: Optional[str] = Field(None, min_length=1, max_length=100)
    kwargs: Optional[dict] = None
    is_enabled: Optional[bool] = None


class ScheduleListResponse(BaseModel):
    items: List[ScheduleResponse]
    total: int


class AvailableTask(BaseModel):
    name: str
    description: str
    default_kwargs: Optional[dict] = None


# ============================================================================
# Schedule Endpoints
# ============================================================================


# List of available sync tasks that can be scheduled
AVAILABLE_SYNC_TASKS = [
    AvailableTask(
        name="app.tasks.sync_tasks.sync_splynx_all",
        description="Full Splynx sync (all entities)",
        default_kwargs={"full_sync": False},
    ),
    AvailableTask(
        name="app.tasks.sync_tasks.sync_splynx_customers",
        description="Splynx customers sync",
        default_kwargs={"full_sync": False},
    ),
    AvailableTask(
        name="app.tasks.sync_tasks.sync_splynx_invoices",
        description="Splynx invoices sync",
        default_kwargs={"full_sync": False},
    ),
    AvailableTask(
        name="app.tasks.sync_tasks.sync_splynx_payments",
        description="Splynx payments sync",
        default_kwargs={"full_sync": False},
    ),
    AvailableTask(
        name="app.tasks.sync_tasks.sync_splynx_services",
        description="Splynx services sync",
        default_kwargs={"full_sync": False},
    ),
    AvailableTask(
        name="app.tasks.sync_tasks.sync_erpnext_all",
        description="Full ERPNext sync (all entities)",
        default_kwargs={"full_sync": False},
    ),
    AvailableTask(
        name="app.tasks.sync_tasks.sync_erpnext_accounting",
        description="ERPNext accounting sync",
        default_kwargs={"full_sync": False},
    ),
    AvailableTask(
        name="app.tasks.sync_tasks.sync_erpnext_hr",
        description="ERPNext HR sync",
        default_kwargs={"full_sync": False},
    ),
    AvailableTask(
        name="app.tasks.sync_tasks.sync_chatwoot_all",
        description="Full Chatwoot sync",
        default_kwargs={"full_sync": False},
    ),
]


@router.get(
    "/schedules",
    response_model=ScheduleListResponse,
    dependencies=[Depends(Require("sync:read"))],
)
async def list_schedules(
    is_enabled: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    """List all sync schedules."""
    query = db.query(SyncSchedule)

    if is_enabled is not None:
        query = query.filter(SyncSchedule.is_enabled == is_enabled)

    total = query.count()
    schedules = query.order_by(SyncSchedule.name).all()

    return ScheduleListResponse(
        items=[
            ScheduleResponse(
                id=s.id,
                name=s.name,
                description=s.description,
                task_name=s.task_name,
                cron_expression=s.cron_expression,
                kwargs=s.kwargs,
                is_enabled=s.is_enabled,
                is_system=s.is_system,
                last_run_at=s.last_run_at,
                last_run_status=s.last_run_status,
                last_error=s.last_error,
                next_run_at=s.next_run_at,
                run_count=s.run_count,
                created_at=s.created_at,
            )
            for s in schedules
        ],
        total=total,
    )


@router.get(
    "/schedules/tasks",
    response_model=List[AvailableTask],
    dependencies=[Depends(Require("sync:read"))],
)
async def list_available_tasks():
    """List available sync tasks that can be scheduled."""
    return AVAILABLE_SYNC_TASKS


@router.get(
    "/schedules/{schedule_id}",
    response_model=ScheduleResponse,
    dependencies=[Depends(Require("sync:read"))],
)
async def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Get a specific schedule."""
    schedule = db.query(SyncSchedule).filter(SyncSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return ScheduleResponse(
        id=schedule.id,
        name=schedule.name,
        description=schedule.description,
        task_name=schedule.task_name,
        cron_expression=schedule.cron_expression,
        kwargs=schedule.kwargs,
        is_enabled=schedule.is_enabled,
        is_system=schedule.is_system,
        last_run_at=schedule.last_run_at,
        last_run_status=schedule.last_run_status,
        last_error=schedule.last_error,
        next_run_at=schedule.next_run_at,
        run_count=schedule.run_count,
        created_at=schedule.created_at,
    )


@router.post(
    "/schedules",
    response_model=ScheduleResponse,
    dependencies=[Depends(Require("sync:write"))],
)
async def create_schedule(
    request: ScheduleCreateRequest,
    db: Session = Depends(get_db),
):
    """Create a new sync schedule."""
    # Check for duplicate name
    existing = db.query(SyncSchedule).filter(SyncSchedule.name == request.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Schedule name already exists")

    # Validate task name
    valid_tasks = [t.name for t in AVAILABLE_SYNC_TASKS]
    if request.task_name not in valid_tasks:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task name. Available tasks: {', '.join(valid_tasks)}",
        )

    schedule = SyncSchedule(
        name=request.name,
        description=request.description,
        task_name=request.task_name,
        cron_expression=request.cron_expression,
        kwargs=request.kwargs or {},
        is_enabled=request.is_enabled,
        is_system=False,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)

    logger.info("schedule_created", schedule_id=schedule.id, name=schedule.name)

    return ScheduleResponse(
        id=schedule.id,
        name=schedule.name,
        description=schedule.description,
        task_name=schedule.task_name,
        cron_expression=schedule.cron_expression,
        kwargs=schedule.kwargs,
        is_enabled=schedule.is_enabled,
        is_system=schedule.is_system,
        last_run_at=schedule.last_run_at,
        last_run_status=schedule.last_run_status,
        last_error=schedule.last_error,
        next_run_at=schedule.next_run_at,
        run_count=schedule.run_count,
        created_at=schedule.created_at,
    )


@router.patch(
    "/schedules/{schedule_id}",
    response_model=ScheduleResponse,
    dependencies=[Depends(Require("sync:write"))],
)
async def update_schedule(
    schedule_id: int,
    request: ScheduleUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update a sync schedule."""
    schedule = db.query(SyncSchedule).filter(SyncSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if schedule.is_system:
        raise HTTPException(status_code=400, detail="Cannot modify system schedules")

    if request.name is not None and request.name != schedule.name:
        existing = db.query(SyncSchedule).filter(
            SyncSchedule.name == request.name,
            SyncSchedule.id != schedule_id,
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Schedule name already exists")
        schedule.name = request.name

    if request.description is not None:
        schedule.description = request.description
    if request.task_name is not None:
        valid_tasks = [t.name for t in AVAILABLE_SYNC_TASKS]
        if request.task_name not in valid_tasks:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid task name. Available tasks: {', '.join(valid_tasks)}",
            )
        schedule.task_name = request.task_name
    if request.cron_expression is not None:
        schedule.cron_expression = request.cron_expression
    if request.kwargs is not None:
        schedule.kwargs = request.kwargs
    if request.is_enabled is not None:
        schedule.is_enabled = request.is_enabled

    db.commit()
    db.refresh(schedule)

    logger.info("schedule_updated", schedule_id=schedule.id)

    return ScheduleResponse(
        id=schedule.id,
        name=schedule.name,
        description=schedule.description,
        task_name=schedule.task_name,
        cron_expression=schedule.cron_expression,
        kwargs=schedule.kwargs,
        is_enabled=schedule.is_enabled,
        is_system=schedule.is_system,
        last_run_at=schedule.last_run_at,
        last_run_status=schedule.last_run_status,
        last_error=schedule.last_error,
        next_run_at=schedule.next_run_at,
        run_count=schedule.run_count,
        created_at=schedule.created_at,
    )


@router.delete(
    "/schedules/{schedule_id}",
    dependencies=[Depends(Require("sync:write"))],
)
async def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Delete a sync schedule."""
    schedule = db.query(SyncSchedule).filter(SyncSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if schedule.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete system schedules")

    db.delete(schedule)
    db.commit()

    logger.info("schedule_deleted", schedule_id=schedule_id)

    return {"status": "deleted", "schedule_id": schedule_id}


@router.post(
    "/schedules/{schedule_id}/run",
    dependencies=[Depends(Require("sync:write"))],
)
async def run_schedule_now(schedule_id: int, db: Session = Depends(get_db)):
    """Trigger immediate execution of a schedule."""
    schedule = db.query(SyncSchedule).filter(SyncSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Try to import and run the Celery task
    try:
        from app.worker import celery_app
        from celery import current_app

        # Send the task
        task = celery_app.send_task(
            schedule.task_name,
            kwargs=schedule.kwargs or {},
        )

        # Update schedule tracking
        schedule.mark_run_started()
        db.commit()

        logger.info(
            "schedule_run_triggered",
            schedule_id=schedule.id,
            task_name=schedule.task_name,
            task_id=task.id,
        )

        return {
            "status": "triggered",
            "schedule_id": schedule_id,
            "task_id": task.id,
        }
    except ImportError:
        raise HTTPException(status_code=503, detail="Celery not available")
    except Exception as e:
        logger.error("schedule_run_failed", schedule_id=schedule_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")
