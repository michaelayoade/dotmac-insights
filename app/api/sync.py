from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
import asyncio
import structlog

from app.database import get_db, SessionLocal
from app.sync.splynx import SplynxSync
from app.sync.erpnext import ERPNextSync
from app.sync.chatwoot import ChatwootSync
from app.models.sync_log import SyncLog, SyncSource
from app.config import settings
from app.auth import Require

logger = structlog.get_logger()
router = APIRouter()

# Check if Celery is available
_celery_available = False
try:
    from app.tasks.sync_tasks import (
        sync_splynx_customers,
        sync_splynx_invoices,
        sync_splynx_payments,
        sync_splynx_services,
        sync_splynx_all,
        sync_splynx_credit_notes,
        sync_splynx_tickets,
        sync_splynx_tariffs,
        sync_splynx_routers,
        sync_erpnext_all,
        sync_erpnext_accounting,
        sync_erpnext_extended_accounting,
        sync_erpnext_hr,
        sync_chatwoot_all,
    )
    # Require explicit broker configuration
    _celery_available = bool(settings.redis_url)
except ImportError:
    pass


def get_celery_status() -> Dict[str, Any]:
    """Report Celery broker/worker availability."""
    celery_status: Dict[str, Any] = {
        "celery_enabled": _celery_available,
        "celery_workers": 0,
    }

    if not _celery_available:
        celery_status["celery_error"] = "Celery not configured"
        return celery_status

    try:
        from app.worker import celery_app

        ping = celery_app.control.ping(timeout=1.0)
        celery_status["celery_workers"] = len(ping)
    except Exception as exc:
        celery_status["celery_enabled"] = False
        celery_status["celery_error"] = str(exc)

    return celery_status


def run_sync_in_background(sync_class, full_sync: bool, source_name: str):
    """Run sync in background with its own database session.

    Fallback for when Celery is not available.
    """
    async def _run():
        db = SessionLocal()
        try:
            logger.info("background_sync_started", source=source_name, full_sync=full_sync)
            sync_client = sync_class(db)
            await sync_client.sync_all(full_sync=full_sync)
            logger.info("background_sync_completed", source=source_name)
        except Exception as e:
            logger.error("background_sync_failed", source=source_name, error=str(e))
        finally:
            db.close()

    # Run the async function
    asyncio.create_task(_run(), name=f"{source_name}_sync")


@router.get("/status", dependencies=[Depends(Require("sync:splynx:read", "sync:erpnext:read", "sync:chatwoot:read"))])
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

    # Add Celery status as separate dict entries
    return {**status, **get_celery_status()}


@router.post("/test-connections", dependencies=[Depends(Require("sync:splynx:read", "sync:erpnext:read", "sync:chatwoot:read"))])
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


@router.post("/splynx", dependencies=[Depends(Require("sync:splynx:write"))])
async def trigger_splynx_sync(full_sync: bool = False) -> Dict[str, Any]:
    """Trigger Splynx sync.

    If Celery is available, enqueues the task. Otherwise falls back to asyncio.
    """
    if _celery_available:
        task = sync_splynx_all.delay(full_sync=full_sync)
        return {
            "message": "Splynx sync enqueued",
            "task_id": task.id,
            "full_sync": full_sync,
            "backend": "celery",
        }
    else:
        run_sync_in_background(SplynxSync, full_sync, "splynx")
        return {
            "message": "Splynx sync started",
            "full_sync": full_sync,
            "backend": "asyncio",
        }


@router.post("/splynx/customers", dependencies=[Depends(Require("sync:splynx:write"))])
async def trigger_splynx_customers_sync(full_sync: bool = False) -> Dict[str, Any]:
    """Trigger Splynx customers sync only."""
    if _celery_available:
        task = sync_splynx_customers.delay(full_sync=full_sync)
        return {
            "message": "Splynx customers sync enqueued",
            "task_id": task.id,
            "full_sync": full_sync,
            "backend": "celery",
        }
    else:
        # Fallback to direct execution
        async def _run():
            db = SessionLocal()
            try:
                sync_client = SplynxSync(db)
                await sync_client.sync_customers_task(full_sync=full_sync)
            finally:
                db.close()
        asyncio.create_task(_run(), name="splynx_customers_sync")
        return {
            "message": "Splynx customers sync started",
            "full_sync": full_sync,
            "backend": "asyncio",
        }


@router.post("/splynx/invoices", dependencies=[Depends(Require("sync:splynx:write"))])
async def trigger_splynx_invoices_sync(full_sync: bool = False) -> Dict[str, Any]:
    """Trigger Splynx invoices sync only."""
    if _celery_available:
        task = sync_splynx_invoices.delay(full_sync=full_sync)
        return {
            "message": "Splynx invoices sync enqueued",
            "task_id": task.id,
            "full_sync": full_sync,
            "backend": "celery",
        }
    else:
        async def _run():
            db = SessionLocal()
            try:
                sync_client = SplynxSync(db)
                await sync_client.sync_invoices_task(full_sync=full_sync)
            finally:
                db.close()
        asyncio.create_task(_run(), name="splynx_invoices_sync")
        return {
            "message": "Splynx invoices sync started",
            "full_sync": full_sync,
            "backend": "asyncio",
        }


@router.post("/splynx/payments", dependencies=[Depends(Require("sync:splynx:write"))])
async def trigger_splynx_payments_sync(full_sync: bool = False) -> Dict[str, Any]:
    """Trigger Splynx payments sync only."""
    if _celery_available:
        task = sync_splynx_payments.delay(full_sync=full_sync)
        return {
            "message": "Splynx payments sync enqueued",
            "task_id": task.id,
            "full_sync": full_sync,
            "backend": "celery",
        }
    else:
        async def _run():
            db = SessionLocal()
            try:
                sync_client = SplynxSync(db)
                await sync_client.sync_payments_task(full_sync=full_sync)
            finally:
                db.close()
        asyncio.create_task(_run(), name="splynx_payments_sync")
        return {
            "message": "Splynx payments sync started",
            "full_sync": full_sync,
            "backend": "asyncio",
        }


@router.post("/splynx/services", dependencies=[Depends(Require("sync:splynx:write"))])
async def trigger_splynx_services_sync(full_sync: bool = False) -> Dict[str, Any]:
    """Trigger Splynx services sync only."""
    if _celery_available:
        task = sync_splynx_services.delay(full_sync=full_sync)
        return {
            "message": "Splynx services sync enqueued",
            "task_id": task.id,
            "full_sync": full_sync,
            "backend": "celery",
        }
    else:
        async def _run():
            db = SessionLocal()
            try:
                sync_client = SplynxSync(db)
                await sync_client.sync_services_task(full_sync=full_sync)
            finally:
                db.close()
        asyncio.create_task(_run(), name="splynx_services_sync")
        return {
            "message": "Splynx services sync started",
            "full_sync": full_sync,
            "backend": "asyncio",
        }


@router.post("/splynx/credit-notes", dependencies=[Depends(Require("sync:splynx:write"))])
async def trigger_splynx_credit_notes_sync(full_sync: bool = False) -> Dict[str, Any]:
    """Trigger Splynx credit notes sync only."""
    if _celery_available:
        task = sync_splynx_credit_notes.delay(full_sync=full_sync)
        return {
            "message": "Splynx credit notes sync enqueued",
            "task_id": task.id,
            "full_sync": full_sync,
            "backend": "celery",
        }
    else:
        async def _run():
            db = SessionLocal()
            try:
                sync_client = SplynxSync(db)
                await sync_client.sync_credit_notes_task(full_sync=full_sync)
            finally:
                db.close()
        asyncio.create_task(_run(), name="splynx_credit_notes_sync")
        return {
            "message": "Splynx credit notes sync started",
            "full_sync": full_sync,
            "backend": "asyncio",
        }


@router.post("/splynx/tickets", dependencies=[Depends(Require("sync:splynx:write"))])
async def trigger_splynx_tickets_sync(full_sync: bool = False) -> Dict[str, Any]:
    """Trigger Splynx tickets sync only."""
    if _celery_available:
        task = sync_splynx_tickets.delay(full_sync=full_sync)
        return {
            "message": "Splynx tickets sync enqueued",
            "task_id": task.id,
            "full_sync": full_sync,
            "backend": "celery",
        }
    else:
        async def _run():
            db = SessionLocal()
            try:
                sync_client = SplynxSync(db)
                await sync_client.sync_tickets_task(full_sync=full_sync)
            finally:
                db.close()
        asyncio.create_task(_run(), name="splynx_tickets_sync")
        return {
            "message": "Splynx tickets sync started",
            "full_sync": full_sync,
            "backend": "asyncio",
        }


@router.post("/splynx/tariffs", dependencies=[Depends(Require("sync:splynx:write"))])
async def trigger_splynx_tariffs_sync(full_sync: bool = False) -> Dict[str, Any]:
    """Trigger Splynx tariffs sync only."""
    if _celery_available:
        task = sync_splynx_tariffs.delay(full_sync=full_sync)
        return {
            "message": "Splynx tariffs sync enqueued",
            "task_id": task.id,
            "full_sync": full_sync,
            "backend": "celery",
        }
    else:
        async def _run():
            db = SessionLocal()
            try:
                sync_client = SplynxSync(db)
                await sync_client.sync_tariffs_task(full_sync=full_sync)
            finally:
                db.close()
        asyncio.create_task(_run(), name="splynx_tariffs_sync")
        return {
            "message": "Splynx tariffs sync started",
            "full_sync": full_sync,
            "backend": "asyncio",
        }


@router.post("/splynx/routers", dependencies=[Depends(Require("sync:splynx:write"))])
async def trigger_splynx_routers_sync(full_sync: bool = False) -> Dict[str, Any]:
    """Trigger Splynx routers sync only."""
    if _celery_available:
        task = sync_splynx_routers.delay(full_sync=full_sync)
        return {
            "message": "Splynx routers sync enqueued",
            "task_id": task.id,
            "full_sync": full_sync,
            "backend": "celery",
        }
    else:
        async def _run():
            db = SessionLocal()
            try:
                sync_client = SplynxSync(db)
                await sync_client.sync_routers_task(full_sync=full_sync)
            finally:
                db.close()
        asyncio.create_task(_run(), name="splynx_routers_sync")
        return {
            "message": "Splynx routers sync started",
            "full_sync": full_sync,
            "backend": "asyncio",
        }


@router.post("/erpnext", dependencies=[Depends(Require("sync:erpnext:write"))])
async def trigger_erpnext_sync(full_sync: bool = False) -> Dict[str, Any]:
    """Trigger ERPNext sync."""
    if _celery_available:
        task = sync_erpnext_all.delay(full_sync=full_sync)
        return {
            "message": "ERPNext sync enqueued",
            "task_id": task.id,
            "full_sync": full_sync,
            "backend": "celery",
        }
    else:
        run_sync_in_background(ERPNextSync, full_sync, "erpnext")
        return {"message": "ERPNext sync started", "full_sync": full_sync, "backend": "asyncio"}


@router.post("/erpnext/accounting", dependencies=[Depends(Require("sync:erpnext:write"))])
async def trigger_erpnext_accounting_sync(full_sync: bool = False) -> Dict[str, Any]:
    """Trigger ERPNext accounting sync (Chart of Accounts, GL Entries, Journal Entries, Purchase Invoices)."""
    if _celery_available:
        task = sync_erpnext_accounting.delay(full_sync=full_sync)
        return {
            "message": "ERPNext accounting sync enqueued",
            "task_id": task.id,
            "full_sync": full_sync,
            "backend": "celery",
        }
    else:
        async def _run():
            db = SessionLocal()
            try:
                sync_client = ERPNextSync(db)
                await sync_client.sync_accounting_task(full_sync=full_sync)
            finally:
                db.close()
        asyncio.create_task(_run(), name="erpnext_accounting_sync")
        return {"message": "ERPNext accounting sync started", "full_sync": full_sync, "backend": "asyncio"}


@router.post("/erpnext/extended-accounting", dependencies=[Depends(Require("sync:erpnext:write"))])
async def trigger_erpnext_extended_accounting_sync(full_sync: bool = False) -> Dict[str, Any]:
    """Trigger ERPNext extended accounting sync (Suppliers, Cost Centers, Fiscal Years, Bank Transactions)."""
    if _celery_available:
        task = sync_erpnext_extended_accounting.delay(full_sync=full_sync)
        return {
            "message": "ERPNext extended accounting sync enqueued",
            "task_id": task.id,
            "full_sync": full_sync,
            "backend": "celery",
        }
    else:
        async def _run():
            db = SessionLocal()
            try:
                sync_client = ERPNextSync(db)
                await sync_client.sync_extended_accounting_task(full_sync=full_sync)
            finally:
                db.close()
        asyncio.create_task(_run(), name="erpnext_extended_accounting_sync")
        return {"message": "ERPNext extended accounting sync started", "full_sync": full_sync, "backend": "asyncio"}


@router.post("/erpnext/hr", dependencies=[Depends(Require("sync:erpnext:write"))])
async def trigger_erpnext_hr_sync(full_sync: bool = False) -> Dict[str, Any]:
    """Trigger ERPNext HR sync (Employees, Departments, Leave, Payroll, Attendance)."""
    if _celery_available:
        task = sync_erpnext_hr.delay(full_sync=full_sync)
        return {
            "message": "ERPNext HR sync enqueued",
            "task_id": task.id,
            "full_sync": full_sync,
            "backend": "celery",
        }
    else:
        async def _run():
            db = SessionLocal()
            try:
                sync_client = ERPNextSync(db)
                await sync_client.sync_hr_task(full_sync=full_sync)
            finally:
                db.close()
        asyncio.create_task(_run(), name="erpnext_hr_sync")
        return {"message": "ERPNext HR sync started", "full_sync": full_sync, "backend": "asyncio"}


@router.post("/chatwoot", dependencies=[Depends(Require("sync:chatwoot:write"))])
async def trigger_chatwoot_sync(full_sync: bool = False) -> Dict[str, Any]:
    """Trigger Chatwoot sync."""
    if _celery_available:
        task = sync_chatwoot_all.delay(full_sync=full_sync)
        return {
            "message": "Chatwoot sync enqueued",
            "task_id": task.id,
            "full_sync": full_sync,
            "backend": "celery",
        }
    else:
        run_sync_in_background(ChatwootSync, full_sync, "chatwoot")
        return {"message": "Chatwoot sync started", "full_sync": full_sync, "backend": "asyncio"}


@router.post("/all", dependencies=[Depends(Require("sync:splynx:write", "sync:erpnext:write", "sync:chatwoot:write"))])
async def trigger_all_sync(full_sync: bool = False) -> Dict[str, Any]:
    """Trigger sync for all sources."""
    if _celery_available:
        # Enqueue all syncs via Celery for consistency/observability
        splynx_task = sync_splynx_all.delay(full_sync=full_sync)
        erpnext_task = sync_erpnext_all.delay(full_sync=full_sync)
        chatwoot_task = sync_chatwoot_all.delay(full_sync=full_sync)

        return {
            "message": "Full sync started for all sources",
            "splynx_task_id": splynx_task.id,
            "erpnext_task_id": erpnext_task.id,
            "chatwoot_task_id": chatwoot_task.id,
            "full_sync": full_sync,
            "backend": "celery",
        }
    else:
        # Fallback to asyncio for all
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
        return {
            "message": "Full sync started for all sources",
            "full_sync": full_sync,
            "backend": "asyncio",
        }


@router.get("/task/{task_id}", dependencies=[Depends(Require("sync:splynx:read", "sync:erpnext:read", "sync:chatwoot:read"))])
async def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get status of a Celery task by ID."""
    if not _celery_available:
        raise HTTPException(status_code=503, detail="Celery not available")

    from app.worker import celery_app
    result = celery_app.AsyncResult(task_id)

    response = {
        "task_id": task_id,
        "status": result.status,
    }

    if result.ready():
        if result.successful():
            response["result"] = result.result
        else:
            response["error"] = str(result.result)

    return response


@router.get("/logs", dependencies=[Depends(Require("sync:splynx:read", "sync:erpnext:read", "sync:chatwoot:read"))])
async def get_sync_logs(
    source: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
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
