from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
from datetime import datetime
import asyncio
import structlog

from app.database import get_db, SessionLocal
from app.sync.splynx import SplynxSync
from app.sync.erpnext import ERPNextSync
from app.sync.chatwoot import ChatwootSync
from app.models.sync_log import SyncLog, SyncSource, SyncStatus

logger = structlog.get_logger()
router = APIRouter()


def run_sync_in_background(sync_class, full_sync: bool, source_name: str):
    """Run sync in background with its own database session."""
    async def _run():
        db = SessionLocal()
        try:
            logger.info(f"background_sync_started", source=source_name, full_sync=full_sync)
            sync_client = sync_class(db)
            await sync_client.sync_all(full_sync=full_sync)
            logger.info(f"background_sync_completed", source=source_name)
        except Exception as e:
            logger.error(f"background_sync_failed", source=source_name, error=str(e))
        finally:
            db.close()

    # Run the async function
    asyncio.create_task(_run(), name=f"{source_name}_sync")


@router.get("/status")
async def get_sync_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get the status of all sync operations."""
    sources = [SyncSource.SPLYNX, SyncSource.ERPNEXT, SyncSource.CHATWOOT]
    status = {}

    for source in sources:
        last_sync = (
            db.query(SyncLog)
            .filter(SyncLog.source == source)
            .order_by(SyncLog.started_at.desc())
            .first()
        )

        if last_sync:
            status[source.value] = {
                "last_sync": last_sync.started_at.isoformat() if last_sync.started_at else None,
                "status": last_sync.status.value,
                "entity_type": last_sync.entity_type,
                "records_created": last_sync.records_created,
                "records_updated": last_sync.records_updated,
                "duration_seconds": last_sync.duration_seconds,
                "error": last_sync.error_message,
            }
        else:
            status[source.value] = {
                "last_sync": None,
                "status": "never_synced",
            }

    return status


@router.post("/test-connections")
async def test_all_connections(db: Session = Depends(get_db)) -> Dict[str, bool]:
    """Test connections to all external systems."""
    results = {}

    splynx = SplynxSync(db)
    results["splynx"] = await splynx.test_connection()

    erpnext = ERPNextSync(db)
    results["erpnext"] = await erpnext.test_connection()

    chatwoot = ChatwootSync(db)
    results["chatwoot"] = await chatwoot.test_connection()

    return results


@router.post("/splynx")
async def sync_splynx(full_sync: bool = False) -> Dict[str, str]:
    """Trigger Splynx sync."""
    run_sync_in_background(SplynxSync, full_sync, "splynx")
    return {"message": "Splynx sync started", "full_sync": full_sync}


@router.post("/erpnext")
async def sync_erpnext(full_sync: bool = False) -> Dict[str, str]:
    """Trigger ERPNext sync."""
    run_sync_in_background(ERPNextSync, full_sync, "erpnext")
    return {"message": "ERPNext sync started", "full_sync": full_sync}


@router.post("/chatwoot")
async def sync_chatwoot(full_sync: bool = False) -> Dict[str, str]:
    """Trigger Chatwoot sync."""
    run_sync_in_background(ChatwootSync, full_sync, "chatwoot")
    return {"message": "Chatwoot sync started", "full_sync": full_sync}


@router.post("/all")
async def sync_all(full_sync: bool = False) -> Dict[str, str]:
    """Trigger sync for all sources."""
    async def run_all_syncs():
        db = SessionLocal()
        try:
            logger.info("full_sync_started", full_sync=full_sync)

            # Sync in order: Splynx first (master customer data), then ERPNext, then Chatwoot
            splynx = SplynxSync(db)
            await splynx.sync_all(full_sync=full_sync)

            erpnext = ERPNextSync(db)
            await erpnext.sync_all(full_sync=full_sync)

            chatwoot = ChatwootSync(db)
            await chatwoot.sync_all(full_sync=full_sync)

            logger.info("full_sync_completed")
        except Exception as e:
            logger.error("full_sync_failed", error=str(e))
        finally:
            db.close()

    asyncio.create_task(run_all_syncs(), name="full_sync_all_sources")
    return {"message": "Full sync started for all sources", "full_sync": full_sync}


@router.get("/logs")
async def get_sync_logs(
    source: str = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list:
    """Get recent sync logs."""
    query = db.query(SyncLog).order_by(SyncLog.started_at.desc())

    if source:
        try:
            source_enum = SyncSource(source)
            query = query.filter(SyncLog.source == source_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid source: {source}")

    logs = query.limit(limit).all()

    return [
        {
            "id": log.id,
            "source": log.source.value,
            "entity_type": log.entity_type,
            "sync_type": log.sync_type,
            "status": log.status.value,
            "records_fetched": log.records_fetched,
            "records_created": log.records_created,
            "records_updated": log.records_updated,
            "records_failed": log.records_failed,
            "started_at": log.started_at.isoformat() if log.started_at else None,
            "completed_at": log.completed_at.isoformat() if log.completed_at else None,
            "duration_seconds": log.duration_seconds,
            "error_message": log.error_message,
        }
        for log in logs
    ]
