"""Journey service stubs for the Marketing module."""
from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.marketing import (
    CustomerJourney,
    JourneyEnrollment,
    JourneyEnrollmentStatus,
    JourneyStatus,
    JourneyStep,
    JourneyStepType,
    JourneyTemplate,
)
from app.services.errors import NotFoundError
from app.services.validation.soft_validation_service import SoftValidationService


def _format_datetime(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    return value.strftime("%b %d, %Y")


def _format_percentage(numerator: int, denominator: int) -> Optional[str]:
    if denominator <= 0:
        return None
    return f"{round((numerator / denominator) * 100)}%"


class JourneyService:
    """Provide journey listing and builder data."""

    def __init__(self, db: Session):
        self.db = db

    def list_journeys(self) -> List[Dict[str, Any]]:
        step_counts = dict(
            self.db.query(
                JourneyStep.journey_id,
                func.count(JourneyStep.id),
            )
            .group_by(JourneyStep.journey_id)
            .all()
        )
        active_counts = dict(
            self.db.query(
                JourneyEnrollment.journey_id,
                func.count(JourneyEnrollment.id),
            )
            .filter(JourneyEnrollment.status == JourneyEnrollmentStatus.ACTIVE)
            .group_by(JourneyEnrollment.journey_id)
            .all()
        )

        journeys = (
            self.db.query(CustomerJourney, JourneyTemplate)
            .outerjoin(JourneyTemplate, CustomerJourney.template_id == JourneyTemplate.id)
            .order_by(CustomerJourney.updated_at.desc())
            .all()
        )

        results: List[Dict[str, Any]] = []
        for journey, template in journeys:
            metrics = journey.metrics or {}
            total_enrolled = metrics.get("total_enrolled", 0)
            total_converted = metrics.get("total_converted", 0)
            journey_data: Dict[str, Any] = {
                "name": journey.name,
                "status": journey.status.value,
                "step_count": step_counts.get(journey.id, 0),
                "active_count": active_counts.get(journey.id, 0),
                "href": f"/marketing/journeys/{journey.id}/builder",
            }
            conversion_rate = _format_percentage(total_converted, total_enrolled)
            if conversion_rate:
                journey_data["conversion_rate"] = conversion_rate
            updated_at = _format_datetime(journey.updated_at)
            if updated_at:
                journey_data["updated_at"] = updated_at
            if template and template.category:
                journey_data["category"] = template.category
            results.append(journey_data)
        return results

    def list_templates(self) -> List[Dict[str, Any]]:
        templates = (
            self.db.query(JourneyTemplate)
            .order_by(JourneyTemplate.created_at.desc())
            .all()
        )
        results: List[Dict[str, Any]] = []
        for template in templates:
            config = template.template_config or {}
            steps = config.get("steps")
            steps_count = len(steps) if isinstance(steps, list) else config.get("step_count")
            steps_label = f"{steps_count} steps" if steps_count is not None else "--"
            results.append(
                {
                    "name": template.name,
                    "category": template.category or "General",
                    "steps": steps_label,
                    "goal": config.get("goal", "Lifecycle"),
                }
            )
        return results

    def get_journey_steps(self, journey_id: Optional[int] = None) -> List[Dict[str, Any]]:
        if journey_id is None:
            return []

        journey = (
            self.db.query(CustomerJourney)
            .filter(CustomerJourney.id == journey_id)
            .first()
        )
        if not journey:
            return []

        steps = (
            self.db.query(JourneyStep)
            .filter(JourneyStep.journey_id == journey_id)
            .order_by(JourneyStep.step_order.asc())
            .all()
        )
        status = journey.status.value
        results: List[Dict[str, Any]] = []
        for step in steps:
            timing_parts = []
            if step.delay_days:
                timing_parts.append(f"{step.delay_days}d")
            if step.delay_hours:
                timing_parts.append(f"{step.delay_hours}h")
            if step.delay_minutes:
                timing_parts.append(f"{step.delay_minutes}m")
            timing = " ".join(timing_parts) if timing_parts else "Immediate"
            results.append(
                {
                    "title": step.name or step.step_type.value.replace("_", " ").title(),
                    "status": status,
                    "type": step.step_type.value.replace("_", " ").title(),
                    "timing": timing,
                }
            )
        return results

    def get_template(self, template_id: int) -> JourneyTemplate:
        template = (
            self.db.query(JourneyTemplate)
            .filter(JourneyTemplate.id == template_id)
            .first()
        )
        if not template:
            raise NotFoundError("Journey template not found")
        return template

    def create_template(self, data: Dict[str, Any]) -> JourneyTemplate:
        template = JourneyTemplate(
            name=data["name"],
            category=data.get("category"),
            description=data.get("description"),
            template_config=data.get("template_config") or {},
            is_system_template=bool(data.get("is_system_template", False)),
        )
        self.db.add(template)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(template)
        return template

    def update_template(self, template_id: int, data: Dict[str, Any]) -> JourneyTemplate:
        template = self.get_template(template_id)
        for field in ["name", "category", "description", "template_config", "is_system_template"]:
            if field in data:
                setattr(template, field, data[field])
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(template)
        return template

    def delete_template(self, template_id: int) -> None:
        template = self.get_template(template_id)
        self.db.delete(template)

    def get_journey(self, journey_id: int) -> CustomerJourney:
        journey = (
            self.db.query(CustomerJourney)
            .filter(CustomerJourney.id == journey_id)
            .first()
        )
        if not journey:
            raise NotFoundError("Journey not found")
        return journey

    def create_journey(self, data: Dict[str, Any]) -> CustomerJourney:
        journey = CustomerJourney(
            name=data["name"],
            template_id=data.get("template_id"),
            campaign_id=data.get("campaign_id"),
            status=data.get("status", JourneyStatus.DRAFT),
            entry_trigger=data.get("entry_trigger"),
            exit_conditions=data.get("exit_conditions") or {},
            metrics=data.get("metrics") or {},
        )
        self.db.add(journey)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(journey)
        return journey

    def update_journey(self, journey_id: int, data: Dict[str, Any]) -> CustomerJourney:
        journey = self.get_journey(journey_id)
        for field in [
            "name",
            "template_id",
            "campaign_id",
            "status",
            "entry_trigger",
            "exit_conditions",
            "metrics",
        ]:
            if field in data:
                setattr(journey, field, data[field])
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(journey)
        return journey

    def delete_journey(self, journey_id: int) -> None:
        journey = self.get_journey(journey_id)
        self.db.delete(journey)

    def get_step(self, step_id: int) -> JourneyStep:
        step = (
            self.db.query(JourneyStep)
            .filter(JourneyStep.id == step_id)
            .first()
        )
        if not step:
            raise NotFoundError("Journey step not found")
        return step

    def create_step(self, data: Dict[str, Any]) -> JourneyStep:
        step = JourneyStep(
            journey_id=data["journey_id"],
            step_order=data.get("step_order", 0),
            step_type=data.get("step_type", JourneyStepType.EMAIL),
            name=data.get("name"),
            delay_days=data.get("delay_days", 0),
            delay_hours=data.get("delay_hours", 0),
            delay_minutes=data.get("delay_minutes", 0),
            content=data.get("content") or {},
            email_template_id=data.get("email_template_id"),
            webhook_url=data.get("webhook_url"),
            condition_config=data.get("condition_config") or {},
        )
        self.db.add(step)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(step)
        return step

    def update_step(self, step_id: int, data: Dict[str, Any]) -> JourneyStep:
        step = self.get_step(step_id)
        for field in [
            "step_order",
            "step_type",
            "name",
            "delay_days",
            "delay_hours",
            "delay_minutes",
            "content",
            "email_template_id",
            "webhook_url",
            "condition_config",
        ]:
            if field in data:
                setattr(step, field, data[field])
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(step)
        return step

    def delete_step(self, step_id: int) -> None:
        step = self.get_step(step_id)
        self.db.delete(step)
