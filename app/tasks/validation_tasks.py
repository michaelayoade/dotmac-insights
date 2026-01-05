"""Background tasks for soft validation audits."""
from __future__ import annotations

from typing import Dict, List, Optional, Type

import structlog

from app.database import SessionLocal
from app.worker import celery_app
from app.services.validation.soft_validation_service import SoftValidationService, finance_models

logger = structlog.get_logger()


def _resolve_models(model_names: Optional[List[str]] = None) -> List[Type]:
    models = finance_models()
    if not model_names:
        return models
    model_map = {model.__name__.lower(): model for model in models}
    return [model_map[name.lower()] for name in model_names if name.lower() in model_map]


@celery_app.task(name="app.tasks.validation_tasks.audit_finance_validation")
def audit_finance_validation(
    batch_size: int = 500,
    model_names: Optional[List[str]] = None,
) -> Dict[str, object]:
    """Backfill soft validation findings for finance records."""
    db = SessionLocal()
    try:
        models = _resolve_models(model_names)
        validator = SoftValidationService(db)
        summary: Dict[str, object] = {"validated": 0, "issues": 0, "models": {}}

        for model in models:
            model_name = model.__name__
            last_id = 0
            model_validated = 0
            model_issues = 0

            while True:
                rows = (
                    db.query(model)
                    .filter(model.id > last_id)
                    .order_by(model.id.asc())
                    .limit(batch_size)
                    .all()
                )
                if not rows:
                    break
                for row in rows:
                    warnings = validator.validate_and_store(row)
                    model_issues += len(warnings)
                model_validated += len(rows)
                last_id = rows[-1].id
                db.commit()

            summary["validated"] = int(summary["validated"]) + model_validated
            summary["issues"] = int(summary["issues"]) + model_issues
            summary["models"][model_name] = {
                "validated": model_validated,
                "issues": model_issues,
            }

        logger.info("finance_validation_backfill_complete", summary=summary)
        return summary
    except Exception as exc:
        db.rollback()
        logger.exception("finance_validation_backfill_failed", error=str(exc))
        raise
    finally:
        db.close()
