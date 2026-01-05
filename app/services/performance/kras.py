"""KRA Definition Service."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional, List

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.performance import (
    KRADefinition,
    KRAKPIMap,
    ScorecardTemplateItem,
)
from app.services.types import PaginationParams, PaginatedResult
from app.services.errors import NotFoundError, ValidationError, ConflictError

from .types import KRAFilters, KRACreateData, KRAUpdateData


class KRAService:
    """Service for KRA definition management."""

    def __init__(self, db: Session):
        self.db = db

    def list_kras(
        self,
        filters: KRAFilters,
        pagination: PaginationParams,
    ) -> PaginatedResult[KRADefinition]:
        """List KRA definitions with filtering and pagination."""
        query = self.db.query(KRADefinition)

        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    KRADefinition.name.ilike(search_term),
                    KRADefinition.code.ilike(search_term),
                    KRADefinition.description.ilike(search_term),
                )
            )

        if filters.is_active is not None:
            query = query.filter(KRADefinition.is_active == filters.is_active)

        total = query.count()

        # Apply sorting
        sort_column = getattr(KRADefinition, filters.sort_by, KRADefinition.code)
        if filters.sort_order == "desc":
            sort_column = sort_column.desc()

        kras = query.order_by(sort_column).offset(pagination.offset).limit(pagination.limit).all()

        return PaginatedResult(data=kras, total=total)

    def get_kra(self, kra_id: int) -> KRADefinition:
        """Get a KRA by ID."""
        kra = self.db.query(KRADefinition).filter(
            KRADefinition.id == kra_id
        ).first()
        if not kra:
            raise NotFoundError(f"KRA {kra_id} not found")
        return kra

    def get_kpi_count(self, kra_id: int) -> int:
        """Get the number of KPIs linked to a KRA."""
        return self.db.query(func.count(KRAKPIMap.id)).filter(
            KRAKPIMap.kra_id == kra_id
        ).scalar() or 0

    def get_template_count(self, kra_id: int) -> int:
        """Get the number of templates using a KRA."""
        return self.db.query(func.count(ScorecardTemplateItem.id)).filter(
            ScorecardTemplateItem.kra_id == kra_id
        ).scalar() or 0

    def create_kra(self, data: KRACreateData) -> KRADefinition:
        """Create a new KRA definition."""
        # Check code uniqueness
        existing = self.db.query(KRADefinition).filter(
            KRADefinition.code == data.code
        ).first()
        if existing:
            raise ConflictError(f"KRA with code '{data.code}' already exists")

        kra = KRADefinition(
            code=data.code,
            name=data.name,
            description=data.description,
            weight=data.weight,
            applicable_departments=data.applicable_departments,
            applicable_designations=data.applicable_designations,
            is_active=data.is_active,
        )
        self.db.add(kra)
        self.db.flush()
        return kra

    def update_kra(self, kra_id: int, data: KRAUpdateData) -> KRADefinition:
        """Update a KRA definition."""
        kra = self.get_kra(kra_id)

        if data.name is not None:
            kra.name = data.name
        if data.description is not None:
            kra.description = data.description
        if data.weight is not None:
            kra.weight = data.weight
        if data.applicable_departments is not None:
            kra.applicable_departments = data.applicable_departments
        if data.applicable_designations is not None:
            kra.applicable_designations = data.applicable_designations
        if data.is_active is not None:
            kra.is_active = data.is_active

        self.db.flush()
        return kra

    def delete_kra(self, kra_id: int) -> None:
        """Delete a KRA definition."""
        kra = self.get_kra(kra_id)

        # Check if KRA is used in templates
        template_count = self.get_template_count(kra_id)
        if template_count > 0:
            raise ValidationError(f"Cannot delete KRA used in {template_count} templates")

        # Check if KRA has linked KPIs
        kpi_count = self.get_kpi_count(kra_id)
        if kpi_count > 0:
            raise ValidationError(f"Cannot delete KRA with {kpi_count} linked KPIs")

        self.db.delete(kra)
        self.db.flush()

    def link_kpi(self, kra_id: int, kpi_id: int, weight: Decimal = Decimal("1.0")) -> KRAKPIMap:
        """Link a KPI to a KRA."""
        # Verify KRA exists
        self.get_kra(kra_id)

        # Check if link already exists
        existing = self.db.query(KRAKPIMap).filter(
            KRAKPIMap.kra_id == kra_id,
            KRAKPIMap.kpi_id == kpi_id,
        ).first()
        if existing:
            raise ConflictError("KPI is already linked to this KRA")

        link = KRAKPIMap(
            kra_id=kra_id,
            kpi_id=kpi_id,
            weight=weight,
        )
        self.db.add(link)
        self.db.flush()
        return link

    def unlink_kpi(self, kra_id: int, kpi_id: int) -> None:
        """Unlink a KPI from a KRA."""
        link = self.db.query(KRAKPIMap).filter(
            KRAKPIMap.kra_id == kra_id,
            KRAKPIMap.kpi_id == kpi_id,
        ).first()

        if not link:
            raise NotFoundError("KPI link not found")

        self.db.delete(link)
        self.db.flush()

    def get_linked_kpis(self, kra_id: int) -> List[KRAKPIMap]:
        """Get all KPIs linked to a KRA."""
        self.get_kra(kra_id)  # Verify KRA exists
        return self.db.query(KRAKPIMap).filter(KRAKPIMap.kra_id == kra_id).all()
