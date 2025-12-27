"""
General data import API endpoints.
"""

from typing import Dict, List
from pathlib import Path
import io
import csv

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Require
from app.config import settings
from app.database import get_db
from app.services.data_import import DataImportService

router = APIRouter(prefix="/imports", tags=["imports"], dependencies=[Depends(Require("admin:write"))])


class ImportFileRequest(BaseModel):
    file_path: str
    domain: str
    purge_existing: bool = False


class ImportResponse(BaseModel):
    success: bool
    message: str
    stats: Dict[str, Dict[str, int]]


class ValidationResponse(BaseModel):
    valid: bool
    message: str
    errors: List[str] = []


def _resolve_safe_path(raw_path: str) -> Path:
    """Ensure requested path stays under the configured import root."""
    base_dir = getattr(settings, "data_import_base_dir", None)
    if not base_dir:
        raise HTTPException(status_code=500, detail="Data import base directory is not configured")
    base = Path(base_dir).expanduser().resolve()
    candidate = Path(raw_path).expanduser().resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=400, detail="Path must be inside the configured data import base directory")
    return candidate


def _validate_domain(domain: str) -> str:
    supported = {"bank_transactions", "gl_entries", "suppliers", "accounts"}
    normalized = domain.strip().lower()
    if normalized not in supported:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid domain: {domain}. Supported domains: {', '.join(sorted(supported))}",
        )
    return normalized


@router.get("/domains")
def list_domains() -> Dict[str, List[str]]:
    """List supported import domains."""
    return {"domains": ["bank_transactions", "gl_entries", "suppliers", "accounts"]}


@router.post("/validate-csv", response_model=ValidationResponse)
async def validate_csv(
    file: UploadFile = File(...),
    domain: str = Form(...),
    db: Session = Depends(get_db),
) -> ValidationResponse:
    """Dry-run CSV validation without writing to the database."""
    domain = _validate_domain(domain)
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content = await file.read()
    csv_reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    rows = list(csv_reader)
    if not rows:
        raise HTTPException(status_code=400, detail="CSV file is empty or has no data rows")

    service = DataImportService(db)  # Validation only; no DB writes
    errors = service.validate_rows(domain, rows)
    if errors:
        return ValidationResponse(valid=False, message=f"Found {len(errors)} error(s); showing first {len(errors)}.", errors=errors)
    return ValidationResponse(valid=True, message="Validation passed", errors=[])


@router.post("/upload-csv", response_model=ImportResponse)
async def upload_csv(
    file: UploadFile = File(...),
    domain: str = Form(...),
    purge_existing: bool = Form(False),
    db: Session = Depends(get_db),
) -> ImportResponse:
    """Upload and import a CSV file for a supported domain."""
    domain = _validate_domain(domain)
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content = await file.read()
    csv_reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    rows = list(csv_reader)
    if not rows:
        raise HTTPException(status_code=400, detail="CSV file is empty or has no data rows")

    service = DataImportService(db)
    errors = service.validate_rows(domain, rows)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    stats = service.import_rows(domain, rows, purge=purge_existing)
    return ImportResponse(
        success=True,
        message=f"Import completed: {stats.get('created', 0)} created, {stats.get('updated', 0)} updated, {stats.get('errors', 0)} errors",
        stats={domain: stats},
    )


@router.post("/import-file", response_model=ImportResponse)
def import_file(
    request: ImportFileRequest,
    db: Session = Depends(get_db),
) -> ImportResponse:
    """Import a CSV file already present on the server (within the configured base dir)."""
    domain = _validate_domain(request.domain)
    safe_path = _resolve_safe_path(request.file_path)
    if not safe_path.exists():
        raise HTTPException(status_code=400, detail=f"File not found: {safe_path}")

    service = DataImportService(db)
    try:
        stats = service.import_csv_file(domain, str(safe_path), purge=request.purge_existing)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ImportResponse(
        success=True,
        message=f"Import completed: {stats.get('created', 0)} created, {stats.get('updated', 0)} updated, {stats.get('errors', 0)} errors",
        stats={domain: stats},
    )
