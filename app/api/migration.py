"""
Data migration API endpoints.

Provides endpoints for:
- Migration job management (CRUD)
- File upload and parsing
- Field mapping configuration
- Validation and preview
- Execution and progress tracking
- Rollback
"""
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import Require
from app.database import get_db
from app.models.migration import MigrationStatus, DedupStrategy, EntityType
from app.services.migration.service import MigrationService
from app.services.migration.registry import (
    list_entities,
    get_entity_config,
    get_entity_fields,
    get_migration_order,
    get_dependencies,
    check_dependencies_migrated,
)


router = APIRouter(
    prefix="/migration",
    tags=["Data Migration"],
    dependencies=[Depends(Require("admin:write"))]
)


# ============================================================================
# Schemas
# ============================================================================

class CreateJobRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Job name")
    entity_type: str = Field(..., description="Target entity type (e.g., 'contacts', 'invoices')")


class SaveMappingRequest(BaseModel):
    field_mapping: Dict[str, str] = Field(..., description="Source column -> target field mapping")
    cleaning_rules: Optional[Dict] = Field(None, description="Data cleaning configuration")
    dedup_strategy: Optional[str] = Field(None, description="skip, update, or merge")
    dedup_fields: Optional[List[str]] = Field(None, description="Fields to check for duplicates")


class JobResponse(BaseModel):
    id: int
    name: str
    entity_type: str
    source_type: Optional[str]
    status: str
    total_rows: int
    processed_rows: int
    created_records: int
    updated_records: int
    skipped_records: int
    failed_records: int
    progress_percent: float
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]

    class Config:
        from_attributes = True


class JobDetailResponse(JobResponse):
    source_columns: Optional[List[str]]
    sample_rows: Optional[List[Dict]]
    field_mapping: Optional[Dict[str, str]]
    cleaning_rules: Optional[Dict]
    dedup_strategy: Optional[str]
    dedup_fields: Optional[List[str]]
    validation_result: Optional[Dict]


class EntityInfo(BaseModel):
    type: str
    display_name: str
    description: str
    required_fields: List[str]
    unique_fields: List[str]
    dependencies: List[str]


class FieldInfo(BaseModel):
    name: str
    type: str
    required: bool = False
    unique: bool = False
    description: Optional[str] = None
    enum_values: Optional[List[str]] = None
    default: Optional[Any] = None


class EntitySchemaResponse(BaseModel):
    entity_type: str
    display_name: str
    fields: List[FieldInfo]
    required_fields: List[str]
    unique_fields: List[str]


class PreviewRow(BaseModel):
    row_number: int
    source: Dict[str, Any]
    transformed: Dict[str, Any]
    warnings: List[Dict]


class ValidationResponse(BaseModel):
    is_valid: bool
    error_count: int
    warning_count: int
    errors: List[Dict]
    warnings: List[Dict]


class ProgressResponse(BaseModel):
    job_id: int
    status: str
    total_rows: int
    processed_rows: int
    created_records: int
    updated_records: int
    skipped_records: int
    failed_records: int
    progress_percent: float
    started_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]


class RecordResponse(BaseModel):
    id: int
    row_number: int
    action: Optional[str]
    error_message: Optional[str]
    source_data: Optional[Dict]
    transformed_data: Optional[Dict]


# ============================================================================
# Helper functions
# ============================================================================

def _job_to_response(job) -> JobResponse:
    """Convert MigrationJob to JobResponse."""
    return JobResponse(
        id=job.id,
        name=job.name,
        entity_type=job.entity_type.value,
        source_type=job.source_type.value if job.source_type else None,
        status=job.status.value,
        total_rows=job.total_rows,
        processed_rows=job.processed_rows,
        created_records=job.created_records,
        updated_records=job.updated_records,
        skipped_records=job.skipped_records,
        failed_records=job.failed_records,
        progress_percent=job.progress_percent,
        created_at=job.created_at.isoformat() if job.created_at else None,
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        error_message=job.error_message,
    )


def _job_to_detail_response(job) -> JobDetailResponse:
    """Convert MigrationJob to JobDetailResponse."""
    return JobDetailResponse(
        id=job.id,
        name=job.name,
        entity_type=job.entity_type.value,
        source_type=job.source_type.value if job.source_type else None,
        status=job.status.value,
        total_rows=job.total_rows,
        processed_rows=job.processed_rows,
        created_records=job.created_records,
        updated_records=job.updated_records,
        skipped_records=job.skipped_records,
        failed_records=job.failed_records,
        progress_percent=job.progress_percent,
        created_at=job.created_at.isoformat() if job.created_at else None,
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        error_message=job.error_message,
        source_columns=job.source_columns,
        sample_rows=job.sample_rows,
        field_mapping=job.field_mapping,
        cleaning_rules=job.cleaning_rules,
        dedup_strategy=job.dedup_strategy.value if job.dedup_strategy else None,
        dedup_fields=job.dedup_fields,
        validation_result=job.validation_result,
    )


# ============================================================================
# Entity Registry Endpoints
# ============================================================================

@router.get("/entities", response_model=List[EntityInfo])
def list_supported_entities() -> List[EntityInfo]:
    """List all supported entity types for migration."""
    entities = list_entities()
    return [EntityInfo(**e) for e in entities]


@router.get("/migration-order")
def get_recommended_migration_order() -> Dict:
    """Get recommended migration order based on dependencies.

    Returns entities sorted so dependencies come before dependents.
    """
    order = get_migration_order()
    entities_info = []

    for entity_type in order:
        config = get_entity_config(entity_type)
        if config:
            entities_info.append({
                "type": entity_type,
                "display_name": config.get("display_name", entity_type),
                "dependencies": config.get("dependencies", []),
            })

    return {
        "order": order,
        "entities": entities_info
    }


@router.get("/entities/{entity_type}/dependencies")
def get_entity_dependencies(entity_type: str) -> Dict:
    """Get dependencies for an entity type."""
    config = get_entity_config(entity_type)
    if not config:
        raise HTTPException(status_code=404, detail=f"Unknown entity type: {entity_type}")

    dependencies = get_dependencies(entity_type)
    dep_details = []

    for dep in dependencies:
        dep_config = get_entity_config(dep)
        if dep_config:
            dep_details.append({
                "type": dep,
                "display_name": dep_config.get("display_name", dep),
                "description": dep_config.get("description", ""),
            })

    return {
        "entity_type": entity_type,
        "display_name": config.get("display_name", entity_type),
        "dependencies": dep_details,
    }


@router.get("/entities/{entity_type}/schema", response_model=EntitySchemaResponse)
def get_entity_schema(entity_type: str) -> EntitySchemaResponse:
    """Get field schema for an entity type."""
    config = get_entity_config(entity_type)
    if not config:
        raise HTTPException(status_code=404, detail=f"Unknown entity type: {entity_type}")

    fields_config = config.get("fields", {})
    fields = []
    for name, cfg in fields_config.items():
        fields.append(FieldInfo(
            name=name,
            type=cfg.get("type", "string").value if hasattr(cfg.get("type"), "value") else str(cfg.get("type", "string")),
            required=cfg.get("required", False),
            unique=cfg.get("unique", False),
            description=cfg.get("description"),
            enum_values=cfg.get("enum_values"),
            default=cfg.get("default"),
        ))

    return EntitySchemaResponse(
        entity_type=entity_type,
        display_name=config.get("display_name", entity_type),
        fields=fields,
        required_fields=config.get("required_fields", []),
        unique_fields=config.get("unique_fields", []),
    )


# ============================================================================
# Job Management Endpoints
# ============================================================================

@router.post("/jobs", response_model=JobResponse)
def create_migration_job(
    request: CreateJobRequest,
    db: Session = Depends(get_db),
) -> JobResponse:
    """Create a new migration job."""
    try:
        service = MigrationService(db)
        job = service.create_job(request.name, request.entity_type)
        return _job_to_response(job)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs", response_model=Dict)
def list_migration_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Dict:
    """List migration jobs."""
    service = MigrationService(db)

    status_enum = MigrationStatus(status) if status else None
    jobs, total = service.list_jobs(
        status=status_enum,
        entity_type=entity_type,
        limit=limit,
        offset=offset
    )

    return {
        "jobs": [_job_to_response(j) for j in jobs],
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
def get_migration_job(
    job_id: int,
    db: Session = Depends(get_db),
) -> JobDetailResponse:
    """Get migration job details."""
    service = MigrationService(db)
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_detail_response(job)


@router.delete("/jobs/{job_id}")
def delete_migration_job(
    job_id: int,
    db: Session = Depends(get_db),
) -> Dict:
    """Delete a migration job."""
    service = MigrationService(db)
    try:
        if service.delete_job(job_id):
            return {"success": True, "message": "Job deleted"}
        raise HTTPException(status_code=404, detail="Job not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# File Upload Endpoints
# ============================================================================

@router.post("/jobs/{job_id}/upload", response_model=JobDetailResponse)
async def upload_source_file(
    job_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> JobDetailResponse:
    """Upload a source file for migration."""
    service = MigrationService(db)

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    try:
        job = service.upload_file(job_id, content, file.filename)
        return _job_to_detail_response(job)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs/{job_id}/columns")
def get_parsed_columns(
    job_id: int,
    db: Session = Depends(get_db),
) -> Dict:
    """Get parsed columns from uploaded file."""
    service = MigrationService(db)
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "columns": job.source_columns or [],
        "total_rows": job.total_rows
    }


@router.get("/jobs/{job_id}/sample")
def get_sample_rows(
    job_id: int,
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> Dict:
    """Get sample rows from uploaded file."""
    service = MigrationService(db)
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "sample_rows": (job.sample_rows or [])[:limit],
        "columns": job.source_columns or [],
        "total_rows": job.total_rows
    }


# ============================================================================
# Field Mapping Endpoints
# ============================================================================

@router.post("/jobs/{job_id}/mapping/suggest")
def suggest_field_mapping(
    job_id: int,
    db: Session = Depends(get_db),
) -> Dict:
    """Auto-suggest field mappings based on column names."""
    service = MigrationService(db)
    suggestions = service.suggest_mapping(job_id)
    return {"suggestions": suggestions}


@router.put("/jobs/{job_id}/mapping", response_model=JobDetailResponse)
def save_field_mapping(
    job_id: int,
    request: SaveMappingRequest,
    db: Session = Depends(get_db),
) -> JobDetailResponse:
    """Save field mapping and configuration."""
    service = MigrationService(db)
    try:
        job = service.save_mapping(
            job_id,
            request.field_mapping,
            request.cleaning_rules,
            request.dedup_strategy,
            request.dedup_fields
        )
        return _job_to_detail_response(job)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Validation & Preview Endpoints
# ============================================================================

@router.post("/jobs/{job_id}/validate", response_model=ValidationResponse)
def validate_migration(
    job_id: int,
    db: Session = Depends(get_db),
) -> ValidationResponse:
    """Run validation on migration data (dry-run)."""
    service = MigrationService(db)
    try:
        result = service.validate(job_id)
        return ValidationResponse(**result.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs/{job_id}/preview", response_model=List[PreviewRow])
def get_preview(
    job_id: int,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[PreviewRow]:
    """Get preview of transformed data."""
    service = MigrationService(db)
    try:
        preview = service.get_preview(job_id, limit, offset)
        return [PreviewRow(**p) for p in preview]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs/{job_id}/duplicates")
def get_duplicate_report(
    job_id: int,
    db: Session = Depends(get_db),
) -> Dict:
    """Get duplicate detection report."""
    service = MigrationService(db)
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.dedup_fields:
        return {"message": "No dedup fields configured", "duplicates": []}

    # Load and check for duplicates
    rows = service._load_all_rows(job)
    transformed = service._transform_rows(rows, job)
    duplicates = service.validator.detect_duplicates(
        transformed,
        job.dedup_fields,
        job.entity_type.value
    )

    return duplicates


# ============================================================================
# Execution Endpoints
# ============================================================================

@router.post("/jobs/{job_id}/execute", response_model=ProgressResponse)
def execute_migration(
    job_id: int,
    db: Session = Depends(get_db),
) -> ProgressResponse:
    """Start migration execution.

    In production, this should trigger a Celery task.
    For now, it runs synchronously.
    """
    service = MigrationService(db)
    try:
        # TODO: In production, dispatch to Celery task
        service.execute(job_id)
        progress = service.get_progress(job_id)
        return ProgressResponse(**progress)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs/{job_id}/progress", response_model=ProgressResponse)
def get_progress(
    job_id: int,
    db: Session = Depends(get_db),
) -> ProgressResponse:
    """Get real-time migration progress."""
    service = MigrationService(db)
    progress = service.get_progress(job_id)
    if "error" in progress:
        raise HTTPException(status_code=404, detail=progress["error"])
    return ProgressResponse(**progress)


@router.post("/jobs/{job_id}/cancel")
def cancel_migration(
    job_id: int,
    db: Session = Depends(get_db),
) -> Dict:
    """Cancel a running migration."""
    service = MigrationService(db)
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != MigrationStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Can only cancel running migrations")

    job.cancel()
    db.commit()

    return {"success": True, "message": "Migration cancelled"}


# ============================================================================
# Rollback Endpoints
# ============================================================================

@router.get("/jobs/{job_id}/rollback-preview")
def preview_rollback(
    job_id: int,
    db: Session = Depends(get_db),
) -> Dict:
    """Preview what would be rolled back."""
    service = MigrationService(db)
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != MigrationStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Can only rollback completed migrations")

    return {
        "job_id": job_id,
        "records_to_rollback": job.created_records + job.updated_records,
        "created_records": job.created_records,
        "updated_records": job.updated_records,
    }


@router.post("/jobs/{job_id}/rollback")
def rollback_migration(
    job_id: int,
    db: Session = Depends(get_db),
) -> Dict:
    """Rollback a completed migration."""
    service = MigrationService(db)
    try:
        result = service.rollback(job_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Record Endpoints
# ============================================================================

@router.get("/jobs/{job_id}/records", response_model=Dict)
def list_migration_records(
    job_id: int,
    action: Optional[str] = Query(None, description="Filter by action (created, updated, skipped, failed)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Dict:
    """List migration records for a job."""
    service = MigrationService(db)
    records, total = service.get_records(job_id, action, limit, offset)

    return {
        "records": [
            RecordResponse(
                id=r.id,
                row_number=r.row_number,
                action=r.action.value if r.action else None,
                error_message=r.error_message,
                source_data=r.source_data,
                transformed_data=r.transformed_data,
            )
            for r in records
        ],
        "total": total,
        "limit": limit,
        "offset": offset
    }
