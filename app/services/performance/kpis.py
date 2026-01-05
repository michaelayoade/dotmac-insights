"""KPI Definition Service."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional, Dict, Any, List

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.performance import (
    KPIDefinition,
    KPIDataSource,
    KPIAggregation,
    ScoringMethod,
    KPIBinding,
    KRAKPIMap,
)
from app.services.types import PaginationParams, PaginatedResult
from app.services.errors import NotFoundError, ValidationError, ConflictError

from .types import KPIFilters, KPICreateData, KPIUpdateData, KPIBindingData


class KPIService:
    """Service for KPI definition management."""

    def __init__(self, db: Session):
        self.db = db

    def list_kpis(
        self,
        filters: KPIFilters,
        pagination: PaginationParams,
    ) -> PaginatedResult[KPIDefinition]:
        """List KPI definitions with filtering and pagination."""
        query = self.db.query(KPIDefinition)

        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    KPIDefinition.name.ilike(search_term),
                    KPIDefinition.code.ilike(search_term),
                    KPIDefinition.description.ilike(search_term),
                )
            )

        if filters.data_source:
            try:
                source_enum = KPIDataSource(filters.data_source)
                query = query.filter(KPIDefinition.data_source == source_enum)
            except ValueError:
                raise ValidationError(f"Invalid data source: {filters.data_source}")

        total = query.count()

        # Apply sorting
        sort_column = getattr(KPIDefinition, filters.sort_by, KPIDefinition.code)
        if filters.sort_order == "desc":
            sort_column = sort_column.desc()

        kpis = query.order_by(sort_column).offset(pagination.offset).limit(pagination.limit).all()

        return PaginatedResult(data=kpis, total=total)

    def get_kpi(self, kpi_id: int) -> KPIDefinition:
        """Get a KPI by ID."""
        kpi = self.db.query(KPIDefinition).filter(
            KPIDefinition.id == kpi_id
        ).first()
        if not kpi:
            raise NotFoundError(f"KPI {kpi_id} not found")
        return kpi

    def get_kra_count(self, kpi_id: int) -> int:
        """Get the number of KRAs linked to a KPI."""
        return self.db.query(func.count(KRAKPIMap.id)).filter(
            KRAKPIMap.kpi_id == kpi_id
        ).scalar() or 0

    def create_kpi(self, data: KPICreateData) -> KPIDefinition:
        """Create a new KPI definition."""
        # Check code uniqueness
        existing = self.db.query(KPIDefinition).filter(
            KPIDefinition.code == data.code
        ).first()
        if existing:
            raise ConflictError(f"KPI with code '{data.code}' already exists")

        try:
            data_source = KPIDataSource(data.data_source)
            aggregation = KPIAggregation(data.aggregation)
            scoring_method = ScoringMethod(data.scoring_method)
        except ValueError as e:
            raise ValidationError(str(e))

        kpi = KPIDefinition(
            code=data.code,
            name=data.name,
            description=data.description,
            data_source=data_source,
            aggregation=aggregation,
            query_config=data.query_config,
            scoring_method=scoring_method,
            min_value=data.min_value,
            target_value=data.target_value,
            max_value=data.max_value,
            threshold_config=data.threshold_config,
            higher_is_better=data.higher_is_better,
        )
        self.db.add(kpi)
        self.db.flush()
        return kpi

    def update_kpi(self, kpi_id: int, data: KPIUpdateData) -> KPIDefinition:
        """Update a KPI definition."""
        kpi = self.get_kpi(kpi_id)

        if data.name is not None:
            kpi.name = data.name
        if data.description is not None:
            kpi.description = data.description
        if data.query_config is not None:
            kpi.query_config = data.query_config
        if data.scoring_method is not None:
            try:
                kpi.scoring_method = ScoringMethod(data.scoring_method)
            except ValueError:
                raise ValidationError(f"Invalid scoring method: {data.scoring_method}")
        if data.min_value is not None:
            kpi.min_value = data.min_value
        if data.target_value is not None:
            kpi.target_value = data.target_value
        if data.max_value is not None:
            kpi.max_value = data.max_value
        if data.threshold_config is not None:
            kpi.threshold_config = data.threshold_config
        if data.higher_is_better is not None:
            kpi.higher_is_better = data.higher_is_better

        self.db.flush()
        return kpi

    def delete_kpi(self, kpi_id: int) -> None:
        """Delete a KPI definition."""
        kpi = self.get_kpi(kpi_id)

        # Check if KPI is linked to any KRA
        link_count = self.get_kra_count(kpi_id)
        if link_count > 0:
            raise ValidationError(f"Cannot delete KPI linked to {link_count} KRAs")

        self.db.delete(kpi)
        self.db.flush()

    # ============= BINDINGS =============

    def list_bindings(
        self,
        kpi_id: int,
        pagination: PaginationParams,
    ) -> PaginatedResult[KPIBinding]:
        """List target bindings for a KPI."""
        # Verify KPI exists
        self.get_kpi(kpi_id)

        query = self.db.query(KPIBinding).filter(KPIBinding.kpi_id == kpi_id)
        total = query.count()
        bindings = query.offset(pagination.offset).limit(pagination.limit).all()

        return PaginatedResult(data=bindings, total=total)

    def create_binding(self, data: KPIBindingData) -> KPIBinding:
        """Create a target binding for a KPI."""
        # Verify KPI exists
        self.get_kpi(data.kpi_id)

        binding = KPIBinding(
            kpi_id=data.kpi_id,
            employee_id=data.employee_id,
            department_id=data.department_id,
            designation_id=data.designation_id,
            target_override=data.target_override,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
        )
        self.db.add(binding)
        self.db.flush()
        return binding

    def delete_binding(self, kpi_id: int, binding_id: int) -> None:
        """Delete a KPI binding."""
        binding = self.db.query(KPIBinding).filter(
            KPIBinding.id == binding_id,
            KPIBinding.kpi_id == kpi_id
        ).first()

        if not binding:
            raise NotFoundError("Binding not found")

        self.db.delete(binding)
        self.db.flush()
