"""Performance services module.

This package contains all performance management business logic:
- EvaluationPeriodService: Period lifecycle management
- KPIService: KPI definitions and bindings
- KRAService: KRA definitions and KPI linkages
- ScorecardTemplateService: Template management
- ScorecardService: Scorecard instances and scoring

Usage:
    from app.services.performance import EvaluationPeriodService, KPIService

    def my_route(db: Session = Depends(get_db)):
        period_service = EvaluationPeriodService(db)
        periods = period_service.list_periods(filters, pagination)
        db.commit()  # Routes control transaction
"""
from .periods import EvaluationPeriodService
from .kpis import KPIService
from .kras import KRAService
from .templates import ScorecardTemplateService
from .scorecards import ScorecardService

from .types import (
    # Period types
    PeriodFilters,
    PeriodCreateData,
    PeriodUpdateData,
    PeriodStats,
    # KPI types
    KPIFilters,
    KPICreateData,
    KPIUpdateData,
    KPIBindingData,
    # KRA types
    KRAFilters,
    KRACreateData,
    KRAUpdateData,
    # Template types
    TemplateFilters,
    TemplateCreateData,
    TemplateUpdateData,
    # Scorecard types
    ScorecardFilters,
)

__all__ = [
    # Services
    "EvaluationPeriodService",
    "KPIService",
    "KRAService",
    "ScorecardTemplateService",
    "ScorecardService",
    # Period types
    "PeriodFilters",
    "PeriodCreateData",
    "PeriodUpdateData",
    "PeriodStats",
    # KPI types
    "KPIFilters",
    "KPICreateData",
    "KPIUpdateData",
    "KPIBindingData",
    # KRA types
    "KRAFilters",
    "KRACreateData",
    "KRAUpdateData",
    # Template types
    "TemplateFilters",
    "TemplateCreateData",
    "TemplateUpdateData",
    # Scorecard types
    "ScorecardFilters",
]
