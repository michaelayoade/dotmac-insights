"""Performance service types."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional, List, Dict, Any


@dataclass
class PeriodFilters:
    """Filters for evaluation periods."""
    status: Optional[str] = None
    period_type: Optional[str] = None
    year: Optional[int] = None
    sort_by: str = "start_date"
    sort_order: str = "desc"


@dataclass
class PeriodCreateData:
    """Data for creating an evaluation period."""
    code: str
    name: str
    period_type: str
    start_date: date
    end_date: date
    scoring_deadline: Optional[date] = None
    review_deadline: Optional[date] = None


@dataclass
class PeriodUpdateData:
    """Data for updating an evaluation period."""
    name: Optional[str] = None
    scoring_deadline: Optional[date] = None
    review_deadline: Optional[date] = None


@dataclass
class KPIFilters:
    """Filters for KPI definitions."""
    search: Optional[str] = None
    data_source: Optional[str] = None
    sort_by: str = "code"
    sort_order: str = "asc"


@dataclass
class KPICreateData:
    """Data for creating a KPI definition."""
    code: str
    name: str
    data_source: str
    aggregation: str
    scoring_method: str
    description: Optional[str] = None
    query_config: Optional[Dict[str, Any]] = None
    min_value: Optional[Decimal] = None
    target_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    threshold_config: Optional[Dict[str, Any]] = None
    higher_is_better: bool = True


@dataclass
class KPIUpdateData:
    """Data for updating a KPI definition."""
    name: Optional[str] = None
    description: Optional[str] = None
    query_config: Optional[Dict[str, Any]] = None
    scoring_method: Optional[str] = None
    min_value: Optional[Decimal] = None
    target_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    threshold_config: Optional[Dict[str, Any]] = None
    higher_is_better: Optional[bool] = None


@dataclass
class KRAFilters:
    """Filters for KRA definitions."""
    search: Optional[str] = None
    is_active: Optional[bool] = None
    sort_by: str = "code"
    sort_order: str = "asc"


@dataclass
class KRACreateData:
    """Data for creating a KRA definition."""
    code: str
    name: str
    description: Optional[str] = None
    weight: Decimal = Decimal("1.0")
    applicable_departments: Optional[List[str]] = None
    applicable_designations: Optional[List[str]] = None
    is_active: bool = True


@dataclass
class KRAUpdateData:
    """Data for updating a KRA definition."""
    name: Optional[str] = None
    description: Optional[str] = None
    weight: Optional[Decimal] = None
    applicable_departments: Optional[List[str]] = None
    applicable_designations: Optional[List[str]] = None
    is_active: Optional[bool] = None


@dataclass
class TemplateFilters:
    """Filters for scorecard templates."""
    search: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    sort_by: str = "name"
    sort_order: str = "asc"


@dataclass
class TemplateCreateData:
    """Data for creating a scorecard template."""
    code: str
    name: str
    description: Optional[str] = None
    applicable_departments: Optional[List[str]] = None
    applicable_designations: Optional[List[str]] = None
    is_default: bool = False
    is_active: bool = True


@dataclass
class TemplateUpdateData:
    """Data for updating a scorecard template."""
    name: Optional[str] = None
    description: Optional[str] = None
    applicable_departments: Optional[List[str]] = None
    applicable_designations: Optional[List[str]] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


@dataclass
class ScorecardFilters:
    """Filters for scorecard instances."""
    employee_id: Optional[int] = None
    period_id: Optional[int] = None
    status: Optional[str] = None
    department: Optional[str] = None
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    sort_by: str = "created_at"
    sort_order: str = "desc"


@dataclass
class PeriodStats:
    """Statistics for an evaluation period."""
    scorecard_count: int = 0
    computed_count: int = 0
    finalized_count: int = 0
    pending_count: int = 0
    in_review_count: int = 0


@dataclass
class KPIBindingData:
    """Data for creating a KPI binding."""
    kpi_id: int
    employee_id: Optional[int] = None
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    target_override: Optional[Decimal] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
