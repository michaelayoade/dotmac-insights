"""
Analytics Module - SSR Dashboard and Reports.

Provides comprehensive business analytics across all domains:
- Revenue metrics (MRR, DSO, Aging)
- Customer analytics (Segments, Health, Churn)
- Support analytics (SLA, Volume, Agent Performance)
- HR analytics (Leave, Payroll, Recruitment)
- Operations analytics (Field Service, Expenses)
- Data insights (Quality, Anomalies)
"""

from app.modules.analytics.routes import router

__all__ = ["router"]
