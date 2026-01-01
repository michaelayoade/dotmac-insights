"""
Zoho Books Import API Endpoints

Provides endpoints to import accounting data from Zoho Books CSV exports.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
import os
import io
import csv
import structlog

from app.database import get_db
from app.services.zoho_import import ZohoImportService

router = APIRouter(prefix="/zoho-import", tags=["Zoho Import"])
logger = structlog.get_logger(__name__)


class ImportRequest(BaseModel):
    """Request model for import operations."""
    directory_path: str


class ImportResponse(BaseModel):
    """Response model for import operations."""
    success: bool
    message: str
    stats: Optional[Dict[str, Dict[str, int]]] = None


class SingleFileImportRequest(BaseModel):
    """Request model for single file import."""
    file_path: str
    import_type: str  # "bank_transactions", "gl_entries", "suppliers", "accounts"


@router.post("/import-all", response_model=ImportResponse)
def import_all_zoho_data(
    request: ImportRequest,
    db: Session = Depends(get_db),
):
    """
    Import all available data from a Zoho Books export directory.

    The directory should have the following structure:
    ```
    directory_path/
      ├── Finance Documents/
      │   ├── BANK/
      │   │   └── *.csv
      │   ├── INCOME/
      │   ├── ACCOUNT PAYABLES/
      │   └── ...
      └── Chart Of Accounts/
          └── ...
    ```

    This endpoint imports:
    - Chart of Accounts from directory structure
    - Bank Transactions from BANK/*.csv files
    - GL Entries from all transaction CSV files
    - Suppliers from ACCOUNT PAYABLES/Accounts Payable.csv
    """
    logger.info("Starting Zoho import", directory=request.directory_path)

    if not os.path.exists(request.directory_path):
        raise HTTPException(
            status_code=400,
            detail=f"Directory not found: {request.directory_path}"
        )

    try:
        import_service = ZohoImportService(db)
        stats = import_service.import_all_from_directory(request.directory_path)

        total_created = sum(
            s.get("created", 0) for s in stats.values()
        )
        total_updated = sum(
            s.get("updated", 0) for s in stats.values()
        )
        total_errors = sum(
            s.get("errors", 0) for s in stats.values()
        )

        return ImportResponse(
            success=True,
            message=f"Import completed: {total_created} created, {total_updated} updated, {total_errors} errors",
            stats=stats,
        )
    except Exception as e:
        logger.error("Zoho import failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Import failed: {str(e)}"
        )


@router.post("/import-file", response_model=ImportResponse)
def import_single_file(
    request: SingleFileImportRequest,
    db: Session = Depends(get_db),
):
    """
    Import data from a single CSV file.

    Supported import_type values:
    - "bank_transactions": Import bank transaction records
    - "gl_entries": Import general ledger entries
    - "suppliers": Import suppliers from AP data
    - "accounts": Import chart of accounts from directory
    """
    logger.info("Starting single file import", file_path=request.file_path, type=request.import_type)

    if not os.path.exists(request.file_path):
        raise HTTPException(
            status_code=400,
            detail=f"File or directory not found: {request.file_path}"
        )

    try:
        import_service = ZohoImportService(db)

        if request.import_type == "bank_transactions":
            stats = import_service.import_bank_transactions_from_csv(request.file_path)
            category = "bank_transactions"
        elif request.import_type == "gl_entries":
            stats = import_service.import_gl_entries_from_csv(request.file_path)
            category = "gl_entries"
        elif request.import_type == "suppliers":
            stats = import_service.import_suppliers_from_csv(request.file_path)
            category = "suppliers"
        elif request.import_type == "accounts":
            stats = import_service.import_accounts_from_directory(request.file_path)
            category = "accounts"
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid import_type: {request.import_type}. "
                       f"Must be one of: bank_transactions, gl_entries, suppliers, accounts"
            )

        return ImportResponse(
            success=True,
            message=f"Import completed: {stats.get('created', 0)} created, "
                   f"{stats.get('updated', 0)} updated, {stats.get('errors', 0)} errors",
            stats={category: stats},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Single file import failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Import failed: {str(e)}"
        )


@router.get("/preview-directory")
def preview_directory(
    directory_path: str,
):
    """
    Preview what files would be imported from a directory.
    Returns a list of all CSV files found in the directory structure.
    """
    if not os.path.exists(directory_path):
        raise HTTPException(
            status_code=400,
            detail=f"Directory not found: {directory_path}"
        )

    files_found: dict[str, list[str]] = {
        "bank_files": [],
        "income_files": [],
        "expense_files": [],
        "liability_files": [],
        "other_files": [],
    }

    try:
        for root, dirs, files in os.walk(directory_path):
            for filename in files:
                if filename.endswith(".csv"):
                    file_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(file_path, directory_path)
                    folder_name = relative_path.split(os.sep)[0] if os.sep in relative_path else ""

                    if "BANK" in folder_name.upper() or "CASH" in folder_name.upper():
                        files_found["bank_files"].append(relative_path)
                    elif "INCOME" in folder_name.upper():
                        files_found["income_files"].append(relative_path)
                    elif "EXPENSE" in folder_name.upper() or "COST" in folder_name.upper():
                        files_found["expense_files"].append(relative_path)
                    elif "LIABILITY" in folder_name.upper() or "PAYABLE" in folder_name.upper():
                        files_found["liability_files"].append(relative_path)
                    else:
                        files_found["other_files"].append(relative_path)

        total_files = sum(len(v) for v in files_found.values())

        return {
            "directory": directory_path,
            "total_csv_files": total_files,
            "files": files_found,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error scanning directory: {str(e)}"
        )


@router.post("/upload-csv", response_model=ImportResponse)
async def upload_csv_file(
    file: UploadFile = File(...),
    import_type: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Upload and import a single CSV file.

    Supported import_type values:
    - "bank_transactions": Import bank transaction records
    - "gl_entries": Import general ledger entries
    - "suppliers": Import suppliers from AP data

    The file should be a CSV file exported from Zoho Books with columns:
    date, account_name, transaction_details, transaction_id, debit, credit, etc.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="File must be a CSV file"
        )

    logger.info("Processing uploaded CSV file", filename=file.filename, type=import_type)

    try:
        # Read the file content
        content = await file.read()
        content_str = content.decode('utf-8-sig')

        # Parse the CSV
        csv_reader = csv.DictReader(io.StringIO(content_str))
        rows = list(csv_reader)

        if not rows:
            raise HTTPException(
                status_code=400,
                detail="CSV file is empty or has no data rows"
            )

        import_service = ZohoImportService(db)

        if import_type == "bank_transactions":
            stats = _process_bank_transactions_from_rows(import_service, rows)
            category = "bank_transactions"
        elif import_type == "gl_entries":
            stats = _process_gl_entries_from_rows(import_service, rows)
            category = "gl_entries"
        elif import_type == "suppliers":
            stats = _process_suppliers_from_rows(import_service, rows)
            category = "suppliers"
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid import_type: {import_type}. "
                       f"Must be one of: bank_transactions, gl_entries, suppliers"
            )

        return ImportResponse(
            success=True,
            message=f"Import completed: {stats.get('created', 0)} created, "
                   f"{stats.get('updated', 0)} updated, {stats.get('errors', 0)} errors",
            stats={category: stats},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("CSV upload import failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Import failed: {str(e)}"
        )


@router.post("/upload-multiple-csv", response_model=ImportResponse)
async def upload_multiple_csv_files(
    files: List[UploadFile] = File(...),
    import_type: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Upload and import multiple CSV files at once.
    All files will be processed with the same import_type.
    """
    logger.info("Processing multiple CSV files", count=len(files), type=import_type)

    total_stats = {"created": 0, "updated": 0, "errors": 0}

    for file in files:
        if not file.filename or not file.filename.endswith(".csv"):
            logger.warning("Skipping non-CSV file", filename=file.filename)
            continue

        try:
            content = await file.read()
            content_str = content.decode('utf-8-sig')
            csv_reader = csv.DictReader(io.StringIO(content_str))
            rows = list(csv_reader)

            if not rows:
                continue

            import_service = ZohoImportService(db)

            if import_type == "bank_transactions":
                stats = _process_bank_transactions_from_rows(import_service, rows)
            elif import_type == "gl_entries":
                stats = _process_gl_entries_from_rows(import_service, rows)
            elif import_type == "suppliers":
                stats = _process_suppliers_from_rows(import_service, rows)
            else:
                continue

            total_stats["created"] += stats.get("created", 0)
            total_stats["updated"] += stats.get("updated", 0)
            total_stats["errors"] += stats.get("errors", 0)

            logger.info("File processed", filename=file.filename, stats=stats)

        except Exception as e:
            logger.error("Error processing file", filename=file.filename, error=str(e))
            total_stats["errors"] += 1

    return ImportResponse(
        success=True,
        message=f"Batch import completed: {total_stats['created']} created, "
               f"{total_stats['updated']} updated, {total_stats['errors']} errors",
        stats={import_type: total_stats},
    )


def _process_bank_transactions_from_rows(service: ZohoImportService, rows: List[Dict]) -> Dict[str, int]:
    """Process bank transaction rows from parsed CSV."""
    for row in rows:
        try:
            service._process_bank_transaction_row(row)
        except Exception as e:
            logger.error("Error processing bank transaction row", error=str(e))
            service.stats["bank_transactions"]["errors"] += 1

    service.db.commit()
    return service.stats["bank_transactions"]


def _process_gl_entries_from_rows(service: ZohoImportService, rows: List[Dict]) -> Dict[str, int]:
    """Process GL entry rows from parsed CSV."""
    for row in rows:
        try:
            service._process_gl_entry_row(row)
        except Exception as e:
            logger.error("Error processing GL entry row", error=str(e))
            service.stats["gl_entries"]["errors"] += 1

    service.db.commit()
    return service.stats["gl_entries"]


def _process_suppliers_from_rows(service: ZohoImportService, rows: List[Dict]) -> Dict[str, int]:
    """Process supplier rows from parsed CSV."""
    suppliers_seen = {}
    for row in rows:
        try:
            supplier_name = row.get("transaction_details", "").strip()
            if not supplier_name or supplier_name in suppliers_seen:
                continue
            suppliers_seen[supplier_name] = True
            service._process_supplier(supplier_name, row)
        except Exception as e:
            logger.error("Error processing supplier row", error=str(e))
            service.stats["suppliers"]["errors"] += 1

    service.db.commit()
    return service.stats["suppliers"]
