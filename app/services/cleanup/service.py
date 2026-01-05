"""Cleanup service.

Orchestrates data quality scanning, issue detection, and cleanup operations.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
import time

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.models.cleanup import (
    CleanupRule,
    CleanupScan,
    CleanupIssue,
    CleanupJob,
    CleanupIssueType,
    CleanupActionType,
    IssueSeverity,
    IssueStatus,
    CleanupScanStatus,
    CleanupJobStatus,
    CleanupEntityType,
)
from app.utils.datetime_utils import utc_now


class CleanupService:
    """Orchestrates the data cleanup workflow."""

    def __init__(self, db: Session, user_id: Optional[int] = None):
        """Initialize the service.

        Args:
            db: Database session
            user_id: Current user ID
        """
        self.db = db
        self.user_id = user_id

    # =========================================================================
    # DASHBOARD & STATISTICS
    # =========================================================================

    def get_dashboard_stats(self) -> dict[str, Any]:
        """Get dashboard statistics.

        Returns:
            Dictionary with issue counts, quality score, recent items
        """
        # Count issues by severity
        severity_counts = (
            self.db.query(
                CleanupIssue.severity,
                func.count(CleanupIssue.id).label("count")
            )
            .filter(CleanupIssue.status == IssueStatus.OPEN)
            .group_by(CleanupIssue.severity)
            .all()
        )

        issue_counts = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        }
        total_issues = 0
        for severity, count in severity_counts:
            issue_counts[severity.value] = count
            total_issues += count

        # Get total record count for quality score calculation
        # For now, use a simple heuristic based on issues
        # In production, this would count actual records
        total_records = 1000  # Placeholder
        quality_score = max(0, 100 - (total_issues / max(total_records, 1) * 100))

        # Get recent issues
        recent_issues = (
            self.db.query(CleanupIssue)
            .filter(CleanupIssue.status == IssueStatus.OPEN)
            .order_by(desc(CleanupIssue.created_at))
            .limit(5)
            .all()
        )

        # Get recent jobs
        recent_jobs = (
            self.db.query(CleanupJob)
            .order_by(desc(CleanupJob.created_at))
            .limit(5)
            .all()
        )

        # Get last scan info
        last_scan = (
            self.db.query(CleanupScan)
            .filter(CleanupScan.status == CleanupScanStatus.COMPLETED)
            .order_by(desc(CleanupScan.completed_at))
            .first()
        )

        return {
            "issue_counts": issue_counts,
            "total_issues": total_issues,
            "quality_score": round(quality_score, 1),
            "recent_issues": recent_issues,
            "recent_jobs": recent_jobs,
            "last_scan": last_scan,
        }

    # =========================================================================
    # RULE MANAGEMENT
    # =========================================================================

    def create_rule(
        self,
        name: str,
        entity_type: str,
        issue_type: str,
        action_type: str,
        description: Optional[str] = None,
        detection_config: Optional[dict] = None,
        action_config: Optional[dict] = None,
        is_system: bool = False,
    ) -> CleanupRule:
        """Create a new cleanup rule.

        Args:
            name: Rule name
            entity_type: Target entity type
            issue_type: Type of issue to detect
            action_type: Action to take
            description: Optional description
            detection_config: Detection configuration
            action_config: Action configuration
            is_system: Whether this is a system rule

        Returns:
            Created CleanupRule
        """
        rule = CleanupRule(
            name=name,
            description=description,
            entity_type=CleanupEntityType(entity_type),
            issue_type=CleanupIssueType(issue_type),
            action_type=CleanupActionType(action_type),
            detection_config=detection_config,
            action_config=action_config,
            is_system=is_system,
            created_by_id=self.user_id,
        )
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def get_rule(self, rule_id: int) -> Optional[CleanupRule]:
        """Get a cleanup rule by ID."""
        return self.db.query(CleanupRule).filter(CleanupRule.id == rule_id).first()

    def list_rules(
        self,
        is_active: Optional[bool] = None,
        entity_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[CleanupRule], int]:
        """List cleanup rules.

        Args:
            is_active: Filter by active status
            entity_type: Filter by entity type
            limit: Max results
            offset: Offset for pagination

        Returns:
            Tuple of (rules, total_count)
        """
        query = self.db.query(CleanupRule)

        if is_active is not None:
            query = query.filter(CleanupRule.is_active == is_active)
        if entity_type:
            query = query.filter(CleanupRule.entity_type == CleanupEntityType(entity_type))

        total = query.count()
        rules = query.order_by(CleanupRule.created_at.desc()).offset(offset).limit(limit).all()

        return rules, total

    def update_rule(self, rule_id: int, **kwargs) -> Optional[CleanupRule]:
        """Update a cleanup rule."""
        rule = self.get_rule(rule_id)
        if not rule:
            return None

        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)

        self.db.commit()
        self.db.refresh(rule)
        return rule

    def delete_rule(self, rule_id: int) -> bool:
        """Delete a cleanup rule."""
        rule = self.get_rule(rule_id)
        if not rule:
            return False

        if rule.is_system:
            raise ValueError("Cannot delete system rules")

        self.db.delete(rule)
        self.db.commit()
        return True

    # =========================================================================
    # SCAN MANAGEMENT
    # =========================================================================

    def create_scan(
        self,
        entity_types: list[str],
        issue_types: Optional[list[str]] = None,
    ) -> CleanupScan:
        """Create a new cleanup scan.

        Args:
            entity_types: Entity types to scan
            issue_types: Optional filter for issue types

        Returns:
            Created CleanupScan
        """
        scan = CleanupScan(
            entity_types=[CleanupEntityType(et).value for et in entity_types],
            issue_types=[CleanupIssueType(it).value for it in issue_types] if issue_types else None,
            started_by_id=self.user_id,
        )
        self.db.add(scan)
        self.db.commit()
        self.db.refresh(scan)
        return scan

    def get_scan(self, scan_id: int) -> Optional[CleanupScan]:
        """Get a cleanup scan by ID."""
        return self.db.query(CleanupScan).filter(CleanupScan.id == scan_id).first()

    def list_scans(
        self,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[CleanupScan], int]:
        """List cleanup scans."""
        query = self.db.query(CleanupScan)

        if status:
            query = query.filter(CleanupScan.status == CleanupScanStatus(status))

        total = query.count()
        scans = query.order_by(desc(CleanupScan.started_at)).offset(offset).limit(limit).all()

        return scans, total

    def run_scan(self, scan_id: int) -> CleanupScan:
        """Execute a cleanup scan.

        Scans for data quality issues across specified entity types:
        - DUPLICATE: Records with same email/phone
        - MISSING_REQUIRED: Null in required fields
        - INVALID_FORMAT: Bad email/phone format
        - ORPHANED: FK references to deleted records

        Args:
            scan_id: Scan ID

        Returns:
            Updated CleanupScan
        """
        import re
        from app.models.party import Party

        scan = self.get_scan(scan_id)
        if not scan:
            raise ValueError(f"Scan {scan_id} not found")

        scan.start()
        self.db.commit()

        start_time = time.time()
        issues_found = 0
        records_scanned = 0
        entity_types = scan.entity_types or []
        issue_types = scan.issue_types  # None means all types

        # Scan Contacts if included
        if CleanupEntityType.CONTACT.value in entity_types:
            scan.current_step = "Scanning contacts..."
            scan.progress_pct = 10
            self.db.commit()

            parties = self.db.query(Party).all()
            records_scanned += len(parties)

            # Email format validation
            email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

            # Track emails for duplicate detection
            email_counts: dict[str, list[int]] = {}

            for party in parties:
                # Check for missing required fields
                if not issue_types or CleanupIssueType.MISSING_REQUIRED.value in issue_types:
                    missing_fields = []
                    if not party.name:
                        missing_fields.append("name")
                    if not party.primary_email and not party.primary_phone:
                        missing_fields.append("email or phone")

                    if missing_fields:
                        existing = self.db.query(CleanupIssue).filter(
                            CleanupIssue.entity_type == CleanupEntityType.CONTACT,
                            CleanupIssue.issue_type == CleanupIssueType.MISSING_REQUIRED,
                            CleanupIssue.record_ids.contains([party.id]),
                            CleanupIssue.status == IssueStatus.OPEN,
                        ).first()

                        if not existing:
                            issue = CleanupIssue(
                                scan_id=scan_id,
                                entity_type=CleanupEntityType.CONTACT,
                                issue_type=CleanupIssueType.MISSING_REQUIRED,
                                severity=IssueSeverity.MEDIUM,
                                title="Missing required fields on party",
                                description=f"Party '{party.name or 'Unknown'}' is missing: {', '.join(missing_fields)}",
                                field_name=missing_fields[0] if len(missing_fields) == 1 else "multiple",
                                record_ids=[party.id],
                                sample_values=[{"id": party.id, "name": party.name, "email": party.primary_email}],
                            )
                            self.db.add(issue)
                            issues_found += 1

                # Check for invalid email format
                if party.primary_email and (not issue_types or CleanupIssueType.INVALID_FORMAT.value in issue_types):
                    if not email_pattern.match(party.primary_email):
                        existing = self.db.query(CleanupIssue).filter(
                            CleanupIssue.entity_type == CleanupEntityType.CONTACT,
                            CleanupIssue.issue_type == CleanupIssueType.INVALID_FORMAT,
                            CleanupIssue.record_ids.contains([party.id]),
                            CleanupIssue.status == IssueStatus.OPEN,
                        ).first()

                        if not existing:
                            issue = CleanupIssue(
                                scan_id=scan_id,
                                entity_type=CleanupEntityType.CONTACT,
                                issue_type=CleanupIssueType.INVALID_FORMAT,
                                severity=IssueSeverity.LOW,
                                title="Invalid email format",
                                description=f"Party '{party.name or 'Unknown'}' has invalid email: {party.primary_email}",
                                field_name="email",
                                record_ids=[party.id],
                                sample_values=[{"id": party.id, "email": party.primary_email}],
                            )
                            self.db.add(issue)
                            issues_found += 1

                # Track for duplicate detection
                if party.primary_email:
                    email_lower = party.primary_email.lower()
                    if email_lower not in email_counts:
                        email_counts[email_lower] = []
                    email_counts[email_lower].append(party.id)

            # Check for duplicates
            if not issue_types or CleanupIssueType.DUPLICATE.value in issue_types:
                scan.current_step = "Checking for duplicates..."
                scan.progress_pct = 70
                self.db.commit()

                for email, contact_ids in email_counts.items():
                    if len(contact_ids) > 1:
                        existing = self.db.query(CleanupIssue).filter(
                            CleanupIssue.entity_type == CleanupEntityType.CONTACT,
                            CleanupIssue.issue_type == CleanupIssueType.DUPLICATE,
                            CleanupIssue.field_name == "email",
                            CleanupIssue.status == IssueStatus.OPEN,
                        ).first()

                        # Check if this exact set is already tracked
                        if existing and set(existing.record_ids) == set(contact_ids):
                            continue

                        issue = CleanupIssue(
                            scan_id=scan_id,
                            entity_type=CleanupEntityType.CONTACT,
                            issue_type=CleanupIssueType.DUPLICATE,
                            severity=IssueSeverity.HIGH,
                            title=f"Duplicate parties with email: {email}",
                            description=f"Found {len(contact_ids)} parties with the same email address",
                            field_name="email",
                            record_ids=contact_ids,
                            sample_values=[{"email": email, "count": len(contact_ids)}],
                        )
                        self.db.add(issue)
                        issues_found += 1

        # Complete the scan
        scan.progress_pct = 100
        scan.current_step = "Completed"
        duration = time.time() - start_time
        scan.complete(
            issues_found=issues_found,
            records_scanned=records_scanned,
            duration=duration,
        )
        self.db.commit()
        self.db.refresh(scan)

        return scan

    # =========================================================================
    # ISSUE MANAGEMENT
    # =========================================================================

    def get_issue(self, issue_id: int) -> Optional[CleanupIssue]:
        """Get a cleanup issue by ID."""
        return self.db.query(CleanupIssue).filter(CleanupIssue.id == issue_id).first()

    def list_issues(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        entity_type: Optional[str] = None,
        issue_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[CleanupIssue], int]:
        """List cleanup issues.

        Args:
            status: Filter by status
            severity: Filter by severity
            entity_type: Filter by entity type
            issue_type: Filter by issue type
            limit: Max results
            offset: Offset for pagination

        Returns:
            Tuple of (issues, total_count)
        """
        query = self.db.query(CleanupIssue)

        if status:
            query = query.filter(CleanupIssue.status == IssueStatus(status))
        if severity:
            query = query.filter(CleanupIssue.severity == IssueSeverity(severity))
        if entity_type:
            query = query.filter(CleanupIssue.entity_type == CleanupEntityType(entity_type))
        if issue_type:
            query = query.filter(CleanupIssue.issue_type == CleanupIssueType(issue_type))

        total = query.count()
        issues = query.order_by(
            # Sort by severity first, then by created_at
            CleanupIssue.severity,
            desc(CleanupIssue.created_at)
        ).offset(offset).limit(limit).all()

        return issues, total

    def ignore_issue(self, issue_id: int) -> Optional[CleanupIssue]:
        """Mark an issue as ignored."""
        issue = self.get_issue(issue_id)
        if not issue:
            return None

        issue.ignore()
        self.db.commit()
        self.db.refresh(issue)
        return issue

    def reopen_issue(self, issue_id: int) -> Optional[CleanupIssue]:
        """Reopen an issue."""
        issue = self.get_issue(issue_id)
        if not issue:
            return None

        issue.reopen()
        self.db.commit()
        self.db.refresh(issue)
        return issue

    # =========================================================================
    # JOB MANAGEMENT
    # =========================================================================

    def create_job(
        self,
        name: str,
        entity_type: str,
        record_ids: list[int],
        action_type: str,
        action_config: Optional[dict] = None,
        rule_id: Optional[int] = None,
        issue_ids: Optional[list[int]] = None,
    ) -> CleanupJob:
        """Create a new cleanup job.

        Args:
            name: Job name
            entity_type: Target entity type
            record_ids: Records to clean
            action_type: Action to perform
            action_config: Action configuration
            rule_id: Optional rule ID
            issue_ids: Optional issue IDs being resolved

        Returns:
            Created CleanupJob
        """
        job = CleanupJob(
            name=name,
            entity_type=CleanupEntityType(entity_type),
            record_ids=record_ids,
            action_type=CleanupActionType(action_type),
            action_config=action_config,
            rule_id=rule_id,
            issue_ids=issue_ids,
            created_by_id=self.user_id,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get_job(self, job_id: int) -> Optional[CleanupJob]:
        """Get a cleanup job by ID."""
        return self.db.query(CleanupJob).filter(CleanupJob.id == job_id).first()

    def list_jobs(
        self,
        status: Optional[str] = None,
        entity_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[CleanupJob], int]:
        """List cleanup jobs."""
        query = self.db.query(CleanupJob)

        if status:
            query = query.filter(CleanupJob.status == CleanupJobStatus(status))
        if entity_type:
            query = query.filter(CleanupJob.entity_type == CleanupEntityType(entity_type))

        total = query.count()
        jobs = query.order_by(desc(CleanupJob.created_at)).offset(offset).limit(limit).all()

        return jobs, total

    def preview_job(self, job_id: int) -> CleanupJob:
        """Generate preview for a cleanup job.

        Shows before/after values for each record that will be changed.

        Args:
            job_id: Job ID

        Returns:
            Updated CleanupJob with preview data
        """
        from app.models.party import Party

        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.start_preview()
        self.db.commit()

        preview_data = []
        record_ids = job.record_ids or []
        action_type = job.action_type
        action_config = job.action_config or {}

        # Handle Contact entity type
        if job.entity_type == CleanupEntityType.CONTACT:
            parties = self.db.query(Party).filter(Party.id.in_(record_ids)).all()

            for party in parties:
                before = {
                    "id": party.id,
                    "name": party.name,
                    "email": party.primary_email,
                    "phone": party.primary_phone,
                }
                after = before.copy()
                changes = []

                # Apply action preview
                if action_type == CleanupActionType.NORMALIZE:
                    # Normalize email to lowercase
                    if party.primary_email and party.primary_email != party.primary_email.lower():
                        after["email"] = party.primary_email.lower()
                        changes.append("email")

                    # Normalize phone (remove spaces, dashes)
                    if party.primary_phone:
                        normalized_phone = "".join(c for c in party.primary_phone if c.isdigit() or c == "+")
                        if normalized_phone != party.primary_phone:
                            after["phone"] = normalized_phone
                            changes.append("phone")

                    # Normalize name (trim, proper case)
                    if party.name:
                        normalized_name = " ".join(party.name.split()).title()
                        if normalized_name != party.name:
                            after["name"] = normalized_name
                            changes.append("name")

                elif action_type == CleanupActionType.SET_DEFAULT:
                    # Set default values for missing fields
                    defaults = action_config.get("defaults", {})
                    for field, default_value in defaults.items():
                        if not getattr(party, field, None):
                            after[field] = default_value
                            changes.append(field)

                elif action_type == CleanupActionType.DELETE:
                    # Mark for deletion
                    after = None
                    changes = ["DELETE"]

                if changes:
                    preview_data.append({
                        "record_id": party.id,
                        "before": before,
                        "after": after,
                        "changes": changes,
                    })

        job.complete_preview(preview_data=preview_data)
        self.db.commit()
        self.db.refresh(job)

        return job

    def execute_job(self, job_id: int, record_ids: Optional[list[int]] = None) -> CleanupJob:
        """Execute a cleanup job.

        Applies the cleanup action to records and stores rollback data.

        Args:
            job_id: Job ID
            record_ids: Optional subset of records to clean

        Returns:
            Updated CleanupJob
        """
        from app.models.party import Party, PartyStatus

        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Update record_ids if subset provided
        if record_ids is not None:
            job.record_ids = record_ids

        job.start_execution()
        self.db.commit()

        changes_log = []
        rollback_data = {}
        records_changed = 0
        records_failed = 0
        target_record_ids = job.record_ids or []
        action_type = job.action_type
        action_config = job.action_config or {}

        try:
            # Handle Contact entity type
            if job.entity_type == CleanupEntityType.CONTACT:
                parties = self.db.query(Party).filter(Party.id.in_(target_record_ids)).all()

                for party in parties:
                    try:
                        # Store original state for rollback
                        original = {
                            "id": party.id,
                            "name": party.name,
                            "email": party.primary_email,
                            "phone": party.primary_phone,
                            "status": party.status,
                        }
                        rollback_data[str(party.id)] = {
                            "table": "parties",
                            "snapshot": original,
                        }

                        changes = {}

                        if action_type == CleanupActionType.NORMALIZE:
                            # Normalize email to lowercase
                            if party.primary_email and party.primary_email != party.primary_email.lower():
                                old_email = party.primary_email
                                party.primary_email = party.primary_email.lower()
                                changes["email"] = {"before": old_email, "after": party.primary_email}

                            # Normalize phone
                            if party.primary_phone:
                                old_phone = party.primary_phone
                                normalized_phone = "".join(c for c in party.primary_phone if c.isdigit() or c == "+")
                                if normalized_phone != party.primary_phone:
                                    party.primary_phone = normalized_phone
                                    changes["phone"] = {"before": old_phone, "after": normalized_phone}

                            # Normalize name
                            if party.name:
                                old_name = party.name
                                normalized_name = " ".join(party.name.split()).title()
                                if normalized_name != party.name:
                                    party.name = normalized_name
                                    changes["name"] = {"before": old_name, "after": normalized_name}

                        elif action_type == CleanupActionType.SET_DEFAULT:
                            defaults = action_config.get("defaults", {})
                            for field, default_value in defaults.items():
                                if hasattr(party, field) and not getattr(party, field):
                                    old_value = getattr(party, field)
                                    setattr(party, field, default_value)
                                    changes[field] = {"before": old_value, "after": default_value}

                        elif action_type == CleanupActionType.DELETE:
                            # Soft delete if supported, otherwise mark
                            old_status = party.status
                            party.status = PartyStatus.INACTIVE
                            changes["status"] = {"before": old_status, "after": party.status}

                        if changes:
                            changes_log.append({
                                "record_id": party.id,
                                "timestamp": utc_now().isoformat(),
                                "changes": changes,
                            })
                            records_changed += 1

                    except Exception as e:
                        records_failed += 1
                        changes_log.append({
                            "record_id": party.id,
                            "timestamp": utc_now().isoformat(),
                            "error": str(e),
                        })

            # Mark associated issues as resolved
            if job.issue_ids:
                for issue_id in job.issue_ids:
                    issue = self.get_issue(issue_id)
                    if issue:
                        issue.resolve(job.id)

            # Complete the job
            job.records_failed = records_failed
            job.complete(
                records_changed=records_changed,
                changes_log=changes_log,
                rollback_data=rollback_data,
            )
            self.db.commit()

        except Exception as e:
            job.fail(str(e))
            self.db.commit()
            raise

        self.db.refresh(job)
        return job

    def rollback_job(self, job_id: int) -> CleanupJob:
        """Rollback a completed cleanup job.

        Restores original values from stored rollback data.

        Args:
            job_id: Job ID

        Returns:
            Updated CleanupJob
        """
        from app.models.party import Party, PartyStatus

        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if job.status != CleanupJobStatus.COMPLETED:
            raise ValueError(f"Can only rollback completed jobs")

        if not job.is_rollbackable:
            raise ValueError(f"Job {job_id} is not rollbackable")

        rollback_data = job.rollback_data or {}

        try:
            # Restore records from rollback data
            if job.entity_type == CleanupEntityType.CONTACT:
                for record_id_str, data in rollback_data.items():
                    record_id = int(record_id_str)
                    snapshot = data.get("snapshot", {})

                    party = self.db.query(Party).filter(Party.id == record_id).first()
                    if party and snapshot:
                        # Restore original values
                        if "name" in snapshot:
                            party.name = snapshot["name"]
                        if "email" in snapshot:
                            party.primary_email = snapshot["email"]
                        if "phone" in snapshot:
                            party.primary_phone = snapshot["phone"]
                        if "status" in snapshot:
                            status_value = snapshot["status"]
                            party.status = (
                                status_value
                                if isinstance(status_value, PartyStatus)
                                else PartyStatus(status_value)
                            )

            # Reopen associated issues
            if job.issue_ids:
                for issue_id in job.issue_ids:
                    issue = self.get_issue(issue_id)
                    if issue and issue.status == IssueStatus.RESOLVED:
                        issue.reopen()

            # Mark job as rolled back
            job.rollback(user_id=self.user_id)
            self.db.commit()

        except Exception as e:
            self.db.rollback()
            raise ValueError(f"Rollback failed: {str(e)}")

        self.db.refresh(job)
        return job
