"""Performance management models for KPI/KRA scorecards and reviews."""
from __future__ import annotations

import enum
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, Text, ForeignKey, Enum, Index, JSON, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# =============================================================================
# ENUMS
# =============================================================================


class EvaluationPeriodType(enum.Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
    CUSTOM = "custom"


class EvaluationPeriodStatus(enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SCORING = "scoring"
    REVIEW = "review"
    FINALIZED = "finalized"
    ARCHIVED = "archived"


class KPIDataSource(enum.Enum):
    MANUAL = "manual"
    TICKETING = "ticketing"
    FIELD_SERVICE = "field_service"
    FINANCE = "finance"
    CRM = "crm"
    ATTENDANCE = "attendance"
    PROJECT = "project"


class KPIAggregation(enum.Enum):
    SUM = "sum"
    AVG = "avg"
    COUNT = "count"
    MIN = "min"
    MAX = "max"
    PERCENT = "percent"
    RATIO = "ratio"


class ScoringMethod(enum.Enum):
    LINEAR = "linear"
    THRESHOLD = "threshold"
    BAND = "band"
    BINARY = "binary"


class ScorecardInstanceStatus(enum.Enum):
    PENDING = "pending"
    COMPUTING = "computing"
    COMPUTED = "computed"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    DISPUTED = "disputed"
    FINALIZED = "finalized"


class OverrideReason(enum.Enum):
    DATA_CORRECTION = "data_correction"
    EXTENUATING_CIRCUMSTANCES = "extenuating_circumstances"
    PARTIAL_PERIOD = "partial_period"
    SYSTEM_ERROR = "system_error"
    MANAGERIAL_DISCRETION = "managerial_discretion"
    OTHER = "other"


# =============================================================================
# CORE ENTITIES
# =============================================================================


class EvaluationPeriod(Base):
    """Evaluation window for performance scoring."""
    __tablename__ = "evaluation_periods"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    period_type: Mapped[EvaluationPeriodType] = mapped_column(Enum(EvaluationPeriodType), nullable=False)
    status: Mapped[EvaluationPeriodStatus] = mapped_column(
        Enum(EvaluationPeriodStatus), default=EvaluationPeriodStatus.DRAFT, index=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    scoring_deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    review_deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<EvaluationPeriod {self.code} ({self.start_date} to {self.end_date})>"


class KRADefinition(Base):
    """Key Result Area definition."""
    __tablename__ = "kra_definitions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    kpis: Mapped[List["KRAKPIMap"]] = relationship(
        back_populates="kra", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<KRA {self.code}>"


class KPIDefinition(Base):
    """KPI definition and scoring metadata."""
    __tablename__ = "kpi_definitions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data_source: Mapped[KPIDataSource] = mapped_column(Enum(KPIDataSource), nullable=False)
    aggregation: Mapped[KPIAggregation] = mapped_column(Enum(KPIAggregation), nullable=False)
    query_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    scoring_method: Mapped[ScoringMethod] = mapped_column(Enum(ScoringMethod), nullable=False)
    min_value: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    target_value: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    max_value: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    threshold_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    higher_is_better: Mapped[bool] = mapped_column(default=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    kra_mappings: Mapped[List["KRAKPIMap"]] = relationship(
        back_populates="kpi", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<KPI {self.code}>"


class KRAKPIMap(Base):
    """Join table linking KRAs to KPIs with weights and ordering."""
    __tablename__ = "kra_kpi_map"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    kra_id: Mapped[int] = mapped_column(ForeignKey("kra_definitions.id", ondelete="CASCADE"), nullable=False)
    kpi_id: Mapped[int] = mapped_column(ForeignKey("kpi_definitions.id", ondelete="CASCADE"), nullable=False)
    weightage: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    idx: Mapped[int] = mapped_column(default=0)

    kra: Mapped["KRADefinition"] = relationship(back_populates="kpis")
    kpi: Mapped["KPIDefinition"] = relationship(back_populates="kra_mappings")

    __table_args__ = (
        Index("ix_kra_kpi_unique", "kra_id", "kpi_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<KRAKPIMap kra={self.kra_id} kpi={self.kpi_id}>"


class ScorecardTemplate(Base):
    """Scorecard templates per role/department."""
    __tablename__ = "scorecard_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    applicable_departments: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    applicable_designations: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(default=1)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_default: Mapped[bool] = mapped_column(default=False)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    items: Mapped[List["ScorecardTemplateItem"]] = relationship(
        back_populates="template", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ScorecardTemplate {self.code} v{self.version}>"


class ScorecardTemplateItem(Base):
    """KRAs assigned to a template with weights."""
    __tablename__ = "scorecard_template_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("scorecard_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kra_id: Mapped[int] = mapped_column(ForeignKey("kra_definitions.id"), nullable=False, index=True)
    weightage: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    idx: Mapped[int] = mapped_column(default=0)

    template: Mapped["ScorecardTemplate"] = relationship(back_populates="items")
    kra: Mapped["KRADefinition"] = relationship()

    __table_args__ = (
        Index("ix_template_kra_unique", "template_id", "kra_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<ScorecardTemplateItem template={self.template_id} kra={self.kra_id}>"


class KPIBinding(Base):
    """Binding of KPI to employee/department context with target overrides."""
    __tablename__ = "kpi_bindings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    kpi_id: Mapped[int] = mapped_column(ForeignKey("kpi_definitions.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    designation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("designations.id"), nullable=True, index=True)
    target_override: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    effective_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_kpi_bindings_kpi_employee", "kpi_id", "employee_id"),
        Index("ix_kpi_bindings_kpi_department", "kpi_id", "department_id"),
    )

    def __repr__(self) -> str:
        return f"<KPIBinding kpi={self.kpi_id} employee={self.employee_id}>"


class EmployeeScorecardInstance(Base):
    """Employee scorecard for a specific evaluation period."""
    __tablename__ = "employee_scorecard_instances"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    evaluation_period_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_periods.id"), nullable=False, index=True
    )
    template_id: Mapped[int] = mapped_column(ForeignKey("scorecard_templates.id"), nullable=False, index=True)
    status: Mapped[ScorecardInstanceStatus] = mapped_column(
        Enum(ScorecardInstanceStatus), default=ScorecardInstanceStatus.PENDING, index=True
    )
    total_weighted_score: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    final_rating: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    finalized_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    finalized_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    kpi_results: Mapped[List["KPIResult"]] = relationship(
        back_populates="scorecard_instance", cascade="all, delete-orphan"
    )
    kra_results: Mapped[List["KRAResult"]] = relationship(
        back_populates="scorecard_instance", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_scorecard_employee_period", "employee_id", "evaluation_period_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<ScorecardInstance emp={self.employee_id} period={self.evaluation_period_id}>"


class KPIResult(Base):
    """Computed KPI result for a scorecard instance."""
    __tablename__ = "kpi_results"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    scorecard_instance_id: Mapped[int] = mapped_column(
        ForeignKey("employee_scorecard_instances.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kpi_id: Mapped[int] = mapped_column(ForeignKey("kpi_definitions.id"), nullable=False, index=True)
    kra_id: Mapped[Optional[int]] = mapped_column(ForeignKey("kra_definitions.id"), nullable=True, index=True)
    raw_value: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    target_value: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    computed_score: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    final_score: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    weightage_in_kra: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    weighted_score: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    evidence_links: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    scorecard_instance: Mapped["EmployeeScorecardInstance"] = relationship(back_populates="kpi_results")

    def __repr__(self) -> str:
        return f"<KPIResult scorecard={self.scorecard_instance_id} kpi={self.kpi_id}>"


class KRAResult(Base):
    """Computed KRA result for a scorecard instance."""
    __tablename__ = "kra_results"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    scorecard_instance_id: Mapped[int] = mapped_column(
        ForeignKey("employee_scorecard_instances.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kra_id: Mapped[int] = mapped_column(ForeignKey("kra_definitions.id"), nullable=False, index=True)
    computed_score: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    final_score: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    weightage_in_scorecard: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    weighted_score: Mapped[Optional[Decimal]] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    scorecard_instance: Mapped["EmployeeScorecardInstance"] = relationship(back_populates="kra_results")

    def __repr__(self) -> str:
        return f"<KRAResult scorecard={self.scorecard_instance_id} kra={self.kra_id}>"


class ScoreOverride(Base):
    """Audit record for score overrides at KPI/KRA/overall level."""
    __tablename__ = "score_overrides"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    scorecard_instance_id: Mapped[int] = mapped_column(
        ForeignKey("employee_scorecard_instances.id", ondelete="CASCADE"), nullable=False, index=True
    )
    override_type: Mapped[str] = mapped_column(String(50), nullable=False)
    kpi_result_id: Mapped[Optional[int]] = mapped_column(ForeignKey("kpi_results.id"), nullable=True, index=True)
    kra_result_id: Mapped[Optional[int]] = mapped_column(ForeignKey("kra_results.id"), nullable=True, index=True)
    original_score: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    overridden_score: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    reason: Mapped[OverrideReason] = mapped_column(Enum(OverrideReason), nullable=False)
    justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    overridden_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ScoreOverride scorecard={self.scorecard_instance_id} reason={self.reason}>"


class PerformanceReviewNote(Base):
    """Notes/comments attached during review."""
    __tablename__ = "performance_review_notes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    scorecard_instance_id: Mapped[int] = mapped_column(
        ForeignKey("employee_scorecard_instances.id", ondelete="CASCADE"), nullable=False, index=True
    )
    note_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    kpi_result_id: Mapped[Optional[int]] = mapped_column(ForeignKey("kpi_results.id"), nullable=True, index=True)
    kra_result_id: Mapped[Optional[int]] = mapped_column(ForeignKey("kra_results.id"), nullable=True, index=True)
    is_private: Mapped[bool] = mapped_column(default=False)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<PerformanceReviewNote scorecard={self.scorecard_instance_id}>"


class BonusPolicy(Base):
    """Bonus policy bands."""
    __tablename__ = "bonus_policies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    score_bands: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    applicable_period_types: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<BonusPolicy {self.code}>"


class PerformanceSnapshot(Base):
    """Denormalized snapshot for analytics."""
    __tablename__ = "performance_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    evaluation_period_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_periods.id"), nullable=False, index=True
    )
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    employee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    final_score: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    final_rating: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    kra_scores: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (
        Index("ix_snapshot_employee_period", "employee_id", "evaluation_period_id"),
        Index("ix_snapshot_period_department", "evaluation_period_id", "department_id"),
    )

    def __repr__(self) -> str:
        return f"<PerformanceSnapshot emp={self.employee_id} period={self.evaluation_period_id}>"
