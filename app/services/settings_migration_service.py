"""Service layer for settings migration views and status updates."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.migration import MigrationJob, MigrationRecord, MigrationStatus, RecordAction
from app.utils.datetime_utils import utc_now


class SettingsMigrationService:
    """Service for migration dashboard queries and lightweight updates."""

    def __init__(self, db: Session):
        self.db = db

    def list_jobs(
        self,
        *,
        status_filter: Optional[MigrationStatus],
        page: int,
        per_page: int,
    ) -> tuple[list[MigrationJob], int]:
        query = self.db.query(MigrationJob).order_by(desc(MigrationJob.created_at))
        if status_filter:
            query = query.filter(MigrationJob.status == status_filter)

        total = query.count()
        jobs = query.offset((page - 1) * per_page).limit(per_page).all()
        return jobs, total

    def get_job_stats(self) -> dict[str, int]:
        return {
            "total": self.db.query(func.count(MigrationJob.id)).scalar() or 0,
            "running": (
                self.db.query(func.count(MigrationJob.id))
                .filter(MigrationJob.status == MigrationStatus.RUNNING)
                .scalar()
                or 0
            ),
            "completed": (
                self.db.query(func.count(MigrationJob.id))
                .filter(MigrationJob.status == MigrationStatus.COMPLETED)
                .scalar()
                or 0
            ),
            "failed": (
                self.db.query(func.count(MigrationJob.id))
                .filter(MigrationJob.status == MigrationStatus.FAILED)
                .scalar()
                or 0
            ),
        }

    def get_job(self, job_id: int) -> Optional[MigrationJob]:
        return self.db.query(MigrationJob).filter(MigrationJob.id == job_id).first()

    def list_records(
        self,
        *,
        job_id: int,
        action: Optional[RecordAction],
        page: int,
        per_page: int,
    ) -> tuple[list[MigrationRecord], int]:
        query = (
            self.db.query(MigrationRecord)
            .filter(MigrationRecord.job_id == job_id)
            .order_by(MigrationRecord.row_number)
        )
        if action:
            query = query.filter(MigrationRecord.action == action)

        total = query.count()
        records = query.offset((page - 1) * per_page).limit(per_page).all()
        return records, total

    def get_record_action_counts(self, job_id: int) -> dict[str, int]:
        return {
            "created": (
                self.db.query(func.count(MigrationRecord.id))
                .filter(
                    MigrationRecord.job_id == job_id,
                    MigrationRecord.action == RecordAction.CREATED,
                )
                .scalar()
                or 0
            ),
            "updated": (
                self.db.query(func.count(MigrationRecord.id))
                .filter(
                    MigrationRecord.job_id == job_id,
                    MigrationRecord.action == RecordAction.UPDATED,
                )
                .scalar()
                or 0
            ),
            "skipped": (
                self.db.query(func.count(MigrationRecord.id))
                .filter(
                    MigrationRecord.job_id == job_id,
                    MigrationRecord.action == RecordAction.SKIPPED,
                )
                .scalar()
                or 0
            ),
            "failed": (
                self.db.query(func.count(MigrationRecord.id))
                .filter(
                    MigrationRecord.job_id == job_id,
                    MigrationRecord.action == RecordAction.FAILED,
                )
                .scalar()
                or 0
            ),
        }

    def cancel_job(self, job: MigrationJob) -> None:
        job.status = MigrationStatus.CANCELLED
        job.error_message = "Cancelled by user"
        job.completed_at = utc_now()
        self.db.commit()

    def get_rollback_counts(self, job_id: int) -> tuple[int, int]:
        created_records = (
            self.db.query(MigrationRecord)
            .filter(
                MigrationRecord.job_id == job_id,
                MigrationRecord.action == RecordAction.CREATED,
            )
            .count()
        )
        updated_records = (
            self.db.query(MigrationRecord)
            .filter(
                MigrationRecord.job_id == job_id,
                MigrationRecord.action == RecordAction.UPDATED,
            )
            .count()
        )
        return created_records, updated_records

    def list_duplicates(
        self,
        *,
        job_id: int,
        page: int,
        per_page: int,
    ) -> tuple[list[MigrationRecord], int]:
        query = (
            self.db.query(MigrationRecord)
            .filter(
                MigrationRecord.job_id == job_id,
                MigrationRecord.action == RecordAction.SKIPPED,
            )
            .order_by(MigrationRecord.row_number)
        )

        total = query.count()
        duplicates = query.offset((page - 1) * per_page).limit(per_page).all()
        return duplicates, total

    def delete_job(self, job: MigrationJob) -> None:
        self.db.delete(job)
        self.db.commit()
