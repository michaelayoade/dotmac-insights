"""Type definitions for CRM Customer Health web service.

These dataclasses define the contract for customer health operations
in the web module (sync session pattern).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID


class HealthGrade(str, Enum):
    """Customer health grade classification."""

    EXCELLENT = "excellent"  # 80-100
    GOOD = "good"  # 60-79
    AT_RISK = "at_risk"  # 40-59
    CRITICAL = "critical"  # 0-39


class ChurnRiskLevel(str, Enum):
    """Churn risk level classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CustomerHealthSummary:
    """Summary of a customer's health metrics."""

    party_id: UUID
    party_name: str
    health_score: int  # 0-100
    health_grade: HealthGrade
    churn_risk: ChurnRiskLevel
    total_opportunities: int
    won_opportunities: int
    lost_opportunities: int
    win_rate: float  # 0-100
    total_value: Decimal
    last_activity_date: Optional[datetime] = None


@dataclass
class HealthDistribution:
    """Distribution of customers across health grades."""

    total: int
    excellent: int
    good: int
    at_risk: int
    critical: int

    @property
    def excellent_pct(self) -> float:
        return (self.excellent / self.total * 100) if self.total > 0 else 0

    @property
    def good_pct(self) -> float:
        return (self.good / self.total * 100) if self.total > 0 else 0

    @property
    def at_risk_pct(self) -> float:
        return (self.at_risk / self.total * 100) if self.total > 0 else 0

    @property
    def critical_pct(self) -> float:
        return (self.critical / self.total * 100) if self.total > 0 else 0


@dataclass
class ChurnRiskDistribution:
    """Distribution of customers across churn risk levels."""

    low: int
    medium: int
    high: int
    critical: int

    @property
    def total_at_risk(self) -> int:
        return self.high + self.critical


@dataclass
class CustomerHealthDashboard:
    """Complete dashboard data for customer health page."""

    health_distribution: HealthDistribution
    churn_distribution: ChurnRiskDistribution
    customers: list[CustomerHealthSummary]
    avg_health_score: float
    total_revenue_at_risk: Decimal


@dataclass
class HealthFilters:
    """Filters for customer health queries."""

    grade: Optional[HealthGrade] = None
    risk: Optional[ChurnRiskLevel] = None
    min_value: Optional[Decimal] = None
    limit: int = 100
