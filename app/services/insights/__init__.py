"""Insights service module.

Provides deep analytics and insights capabilities for web modules and background tasks.
NOT exposed via API endpoints.
"""
from .insights import InsightsService
from .insights_types import (
    # Completeness types
    DataCompletenessResult,
    CompletenessRecommendation,
    FieldCompleteness,
    SystemLinkage,
    # Customer types
    CustomerSegmentsResult,
    SegmentData,
    CustomerHealthResult,
    PaymentBehavior,
    PaymentTiming,
    PaymentTimingDistribution,
    SupportIntensity,
    ChurnIndicators,
    RiskSegments,
    ChurnRiskResult,
    PlanChangesResult,
    PlanTransition,
    # Relationship types
    RelationshipMapResult,
    # Financial types
    FinancialInsightsResult,
    AgingBucket,
    # Operational types
    OperationalInsightsResult,
    TicketMetrics,
    ConversationMetrics,
    NetworkHealthResult,
    # Anomaly types
    AnomaliesResult,
    Anomaly,
    Pattern,
    AnomalySummary,
    # Availability types
    DataAvailabilityResult,
    MissingData,
)

__all__ = [
    # Service
    "InsightsService",
    # Completeness types
    "DataCompletenessResult",
    "CompletenessRecommendation",
    "FieldCompleteness",
    "SystemLinkage",
    # Customer types
    "CustomerSegmentsResult",
    "SegmentData",
    "CustomerHealthResult",
    "PaymentBehavior",
    "PaymentTiming",
    "PaymentTimingDistribution",
    "SupportIntensity",
    "ChurnIndicators",
    "RiskSegments",
    "ChurnRiskResult",
    "PlanChangesResult",
    "PlanTransition",
    # Relationship types
    "RelationshipMapResult",
    # Financial types
    "FinancialInsightsResult",
    "AgingBucket",
    # Operational types
    "OperationalInsightsResult",
    "TicketMetrics",
    "ConversationMetrics",
    "NetworkHealthResult",
    # Anomaly types
    "AnomaliesResult",
    "Anomaly",
    "Pattern",
    "AnomalySummary",
    # Availability types
    "DataAvailabilityResult",
    "MissingData",
]
