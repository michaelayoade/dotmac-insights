"""Scorecard Template Service."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.performance import (
    ScorecardTemplate,
    ScorecardTemplateItem,
    EmployeeScorecardInstance,
    KRADefinition,
)
from app.services.types import PaginationParams, PaginatedResult
from app.services.errors import NotFoundError, ValidationError, ConflictError

from .types import TemplateFilters, TemplateCreateData, TemplateUpdateData


class ScorecardTemplateService:
    """Service for scorecard template management."""

    def __init__(self, db: Session):
        self.db = db

    def list_templates(
        self,
        filters: TemplateFilters,
        pagination: PaginationParams,
    ) -> PaginatedResult[ScorecardTemplate]:
        """List scorecard templates with filtering and pagination."""
        query = self.db.query(ScorecardTemplate)

        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    ScorecardTemplate.name.ilike(search_term),
                    ScorecardTemplate.code.ilike(search_term),
                    ScorecardTemplate.description.ilike(search_term),
                )
            )

        if filters.is_active is not None:
            query = query.filter(ScorecardTemplate.is_active == filters.is_active)

        if filters.is_default is not None:
            query = query.filter(ScorecardTemplate.is_default == filters.is_default)

        total = query.count()

        # Apply sorting
        sort_column = getattr(ScorecardTemplate, filters.sort_by, ScorecardTemplate.name)
        if filters.sort_order == "desc":
            sort_column = sort_column.desc()

        templates = query.order_by(sort_column).offset(pagination.offset).limit(pagination.limit).all()

        return PaginatedResult(data=templates, total=total)

    def get_template(self, template_id: int) -> ScorecardTemplate:
        """Get a template by ID."""
        template = self.db.query(ScorecardTemplate).filter(
            ScorecardTemplate.id == template_id
        ).first()
        if not template:
            raise NotFoundError(f"Template {template_id} not found")
        return template

    def get_template_by_code(self, code: str) -> Optional[ScorecardTemplate]:
        """Get a template by code."""
        return self.db.query(ScorecardTemplate).filter(
            ScorecardTemplate.code == code
        ).first()

    def get_default_template(self) -> Optional[ScorecardTemplate]:
        """Get the default active template."""
        return self.db.query(ScorecardTemplate).filter(
            ScorecardTemplate.is_default == True,
            ScorecardTemplate.is_active == True,
        ).first()

    def get_item_count(self, template_id: int) -> int:
        """Get the number of items in a template."""
        return self.db.query(func.count(ScorecardTemplateItem.id)).filter(
            ScorecardTemplateItem.template_id == template_id
        ).scalar() or 0

    def get_scorecard_count(self, template_id: int) -> int:
        """Get the number of scorecards using a template."""
        return self.db.query(func.count(EmployeeScorecardInstance.id)).filter(
            EmployeeScorecardInstance.template_id == template_id
        ).scalar() or 0

    def create_template(self, data: TemplateCreateData) -> ScorecardTemplate:
        """Create a new scorecard template."""
        # Check code uniqueness
        existing = self.db.query(ScorecardTemplate).filter(
            ScorecardTemplate.code == data.code
        ).first()
        if existing:
            raise ConflictError(f"Template with code '{data.code}' already exists")

        # If setting as default, unset other defaults
        if data.is_default:
            self.db.query(ScorecardTemplate).filter(
                ScorecardTemplate.is_default == True
            ).update({"is_default": False})

        template = ScorecardTemplate(
            code=data.code,
            name=data.name,
            description=data.description,
            applicable_departments=data.applicable_departments,
            applicable_designations=data.applicable_designations,
            is_default=data.is_default,
            is_active=data.is_active,
        )
        self.db.add(template)
        self.db.flush()
        return template

    def update_template(self, template_id: int, data: TemplateUpdateData) -> ScorecardTemplate:
        """Update a scorecard template."""
        template = self.get_template(template_id)

        if data.name is not None:
            template.name = data.name
        if data.description is not None:
            template.description = data.description
        if data.applicable_departments is not None:
            template.applicable_departments = data.applicable_departments
        if data.applicable_designations is not None:
            template.applicable_designations = data.applicable_designations
        if data.is_active is not None:
            template.is_active = data.is_active

        # Handle is_default specially
        if data.is_default is not None:
            if data.is_default:
                # Unset other defaults
                self.db.query(ScorecardTemplate).filter(
                    ScorecardTemplate.id != template_id,
                    ScorecardTemplate.is_default == True
                ).update({"is_default": False})
            template.is_default = data.is_default

        self.db.flush()
        return template

    def delete_template(self, template_id: int) -> None:
        """Delete a scorecard template."""
        template = self.get_template(template_id)

        # Check if template is used by scorecards
        scorecard_count = self.get_scorecard_count(template_id)
        if scorecard_count > 0:
            raise ValidationError(f"Cannot delete template used by {scorecard_count} scorecards")

        # Delete template items first
        self.db.query(ScorecardTemplateItem).filter(
            ScorecardTemplateItem.template_id == template_id
        ).delete()

        self.db.delete(template)
        self.db.flush()

    # ============= TEMPLATE ITEMS =============

    def list_items(self, template_id: int) -> List[ScorecardTemplateItem]:
        """Get all items in a template."""
        self.get_template(template_id)  # Verify template exists
        return self.db.query(ScorecardTemplateItem).filter(
            ScorecardTemplateItem.template_id == template_id
        ).order_by(ScorecardTemplateItem.sequence).all()

    def add_item(
        self,
        template_id: int,
        kra_id: int,
        weight: Decimal,
        sequence: Optional[int] = None,
    ) -> ScorecardTemplateItem:
        """Add a KRA item to a template."""
        self.get_template(template_id)  # Verify template exists

        # Verify KRA exists
        kra = self.db.query(KRADefinition).filter(KRADefinition.id == kra_id).first()
        if not kra:
            raise NotFoundError(f"KRA {kra_id} not found")

        # Check if KRA is already in template
        existing = self.db.query(ScorecardTemplateItem).filter(
            ScorecardTemplateItem.template_id == template_id,
            ScorecardTemplateItem.kra_id == kra_id,
        ).first()
        if existing:
            raise ConflictError("KRA is already in this template")

        # Determine sequence
        if sequence is None:
            max_seq = self.db.query(func.max(ScorecardTemplateItem.sequence)).filter(
                ScorecardTemplateItem.template_id == template_id
            ).scalar() or 0
            sequence = max_seq + 1

        item = ScorecardTemplateItem(
            template_id=template_id,
            kra_id=kra_id,
            weight=weight,
            sequence=sequence,
        )
        self.db.add(item)
        self.db.flush()
        return item

    def update_item(
        self,
        item_id: int,
        weight: Optional[Decimal] = None,
        sequence: Optional[int] = None,
    ) -> ScorecardTemplateItem:
        """Update a template item."""
        item = self.db.query(ScorecardTemplateItem).filter(
            ScorecardTemplateItem.id == item_id
        ).first()
        if not item:
            raise NotFoundError(f"Template item {item_id} not found")

        if weight is not None:
            item.weight = weight
        if sequence is not None:
            item.sequence = sequence

        self.db.flush()
        return item

    def remove_item(self, template_id: int, item_id: int) -> None:
        """Remove an item from a template."""
        item = self.db.query(ScorecardTemplateItem).filter(
            ScorecardTemplateItem.id == item_id,
            ScorecardTemplateItem.template_id == template_id,
        ).first()

        if not item:
            raise NotFoundError("Template item not found")

        self.db.delete(item)
        self.db.flush()

    def reorder_items(self, template_id: int, item_ids: List[int]) -> None:
        """Reorder items in a template."""
        self.get_template(template_id)  # Verify template exists

        for idx, item_id in enumerate(item_ids):
            self.db.query(ScorecardTemplateItem).filter(
                ScorecardTemplateItem.id == item_id,
                ScorecardTemplateItem.template_id == template_id,
            ).update({"sequence": idx + 1})

        self.db.flush()
